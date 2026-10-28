"""Deterministic public-payload policy for offline demonstrations, not evaluation."""

import json
import time
from datetime import datetime, timedelta

from .provider import LLMProvider, ProviderError, json_payload


def text(record):
    return (record.get("excerpt", "") + " " + json.dumps(record.get("metadata", {}))).lower()


def classify(record):
    """Classify observations, never incident identifiers or filesystem names."""
    s = text(record)
    service = record.get("service", "")
    m = record.get("metadata", {})
    if record.get("source_type") == "database":
        if (
            m.get("category") == "connections"
            and m.get("connection_limit", 0) > 0
            and m.get("connection_count", 0) >= m["connection_limit"]
        ):
            return "postgres", "postgres_connection_exhaustion", True
        if m.get("blocked_by") and m.get("duration_ms", 0) >= 1000:
            return "postgres", "postgres_lock_contention", True
        if m.get("category") == "slow_queries" and m.get("duration_ms", 0) >= 3000:
            return (
                "postgres",
                "postgres_lock_contention"
                if "lock" in m.get("wait_event", "")
                else "postgres_slow_query",
                True,
            )
    if "transaction lock" in s and any(w in s for w in ("wait", "blocked", "contention")):
        return "postgres", "postgres_lock_contention", False
    metric = record.get("metadata", {}).get("metric_name")
    value = record.get("metadata", {}).get("value")
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = None
    if value is not None:
        if service == "postgres" and (
            (metric == "connections_active" and value >= 100)
            or (metric == "connection_rejections" and value > 0)
        ):
            return "postgres", "postgres_connection_exhaustion", True
        if service == "redis" and metric == "availability" and value == 0:
            return "redis", "redis_unavailable", True
        if service == "payment" and (
            (metric == "p95_latency_ms" and value >= 3000)
            or (metric == "timeout_rate" and value > 0.5)
        ):
            return "payment", "payment_external_timeout", True
        if service == "backend" and (
            (metric == "cpu_percent" and value >= 90)
            or (metric == "worker_queue_depth" and value >= 100)
        ):
            return "backend", "backend_resource_saturation", True
        if service == "backend" and metric == "pool_waiters" and value > 0:
            return "backend", "backend_pool_config_regression", False
        return None
    if "db_pool_max" in s and any(w in s for w in ("2", "reduced", "decrease")):
        return "backend", "backend_pool_config_regression", True
    if service == "redis" and any(
        w in s for w in ("refused", "unavailable", "down", "availability=0", "availability: 0")
    ):
        return "redis", "redis_unavailable", True
    if service == "payment" and any(w in s for w in ("timeout", "timed out", "deadline")):
        return "payment", "payment_external_timeout", True
    if (
        service == "backend"
        and any(w in s for w in ("saturat", "cpu", "thread"))
        and any(w in s for w in ("95", "98", "99", "100", "exhaust", "saturat"))
    ):
        return "backend", "backend_resource_saturation", True
    if service == "postgres" and any(
        w in s
        for w in (
            "too many connections",
            "exhaust",
            "connection rejected",
            "remaining connection slots",
        )
    ):
        return "postgres", "postgres_connection_exhaustion", True
    if any(
        w in s
        for w in (
            "acquire timeout",
            "connection acquire",
            "db timeout",
            "database timeout",
            "database connection refused",
            "database acquire failed",
        )
    ):
        return "postgres", "postgres_connection_exhaustion", False
    if any(w in s for w in ("redis", "cache")) and any(
        w in s for w in ("refused", "unavailable", "timeout")
    ):
        return "redis", "redis_unavailable", False
    if "payment" in s and any(w in s for w in ("timeout", "deadline", "timed out")):
        return "payment", "payment_external_timeout", False
    if service == "backend" and "worker queue" in s:
        return "backend", "backend_resource_saturation", False
    return None


def task(role, index, question, filters=None):
    tools = {
        "logs": ["query_logs"],
        "metrics": ["query_metrics", "get_dependencies"],
        "changes": ["query_changes", "get_config_diff"],
        "database": [
            "get_db_connections",
            "get_db_lock_waits",
            "get_db_active_sessions",
            "get_db_slow_queries",
            "get_db_health_metrics",
        ],
    }
    return dict(
        task_id=f"check-{role}-{index}",
        role=role,
        question=question,
        allowed_tools=tools[role],
        filters=filters or {},
        reason="Resolve an evidence gap in the current candidate",
        expected_discriminator="Compare direct cause indicators with downstream symptoms",
    )


def records_from(state):
    records = state.get("evidence_index") or state.get("evidence_catalog", {})
    return list(records.values()) if isinstance(records, dict) else records


def normal_database(records):
    if any(
        r.get("source_type") == "database"
        and r.get("metadata", {}).get("category") == "connections"
        and r["metadata"].get("connection_limit", 0) > r["metadata"].get("connection_count", 0)
        for r in records
    ):
        return True
    return any(
        r["service"] == "postgres"
        and r["source_type"] == "metrics"
        and (
            (
                r.get("metadata", {}).get("metric_name") == "connections_active"
                and float(r.get("metadata", {}).get("value", 100)) < 80
            )
            or any(w in text(r) for w in ("normal", "healthy", "connections=30", "connections: 30"))
        )
        for r in records
    )


def review(state):
    records = records_from(state)
    hypotheses = state.get("hypotheses", [])
    candidate = next(
        (h for h in hypotheses if h["failure_mode"] == "backend_pool_config_regression"),
        next((h for h in hypotheses if h.get("status") != "REJECTED"), None),
    )
    database_normal = normal_database(records) or state.get("database_health_normal", False)
    if candidate is None and database_normal:
        candidate = next(
            (h for h in hypotheses if h["failure_mode"] == "postgres_connection_exhaustion"), None
        )
    target = candidate["hypothesis_id"] if candidate else "unresolved"
    ids = candidate.get("support_ids", []) if candidate else []
    supporting = [r for r in records if r["evidence_id"] in ids]
    distinct = {(r["source_type"], r["source_path"]) for r in supporting}
    discriminator = bool(
        candidate and set(ids).intersection(state.get("discriminator_matches", {}).get(target, []))
    ) or any(
        classify(r) and classify(r)[2] and candidate and classify(r)[1] == candidate["failure_mode"]
        for r in supporting
    )
    contradictions = []
    checks = []
    change = next(
        (
            r
            for r in records
            if r["source_type"] == "changes"
            and r["service"] == "backend"
            and r.get("metadata", {}).get("change_id")
        ),
        None,
    )
    pool_diff = any(
        r["source_type"] == "configs"
        and classify(r)
        and classify(r)[1] == "backend_pool_config_regression"
        and classify(r)[2]
        for r in records
    ) or bool(
        candidate
        and candidate["failure_mode"] == "backend_pool_config_regression"
        and set(candidate.get("support_ids", [])).intersection(
            state.get("discriminator_matches", {}).get(target, [])
        )
    )
    if (
        database_normal
        and candidate
        and candidate["failure_mode"]
        in ("postgres_connection_exhaustion", "backend_pool_config_regression")
        and not pool_diff
    ):
        contradictions = ["Observed normal database metrics challenge database exhaustion"]
        checks = [
            task(
                "changes",
                len(state.get("tasks", [])),
                "Check backend pool configuration and its recent change",
                {"service": "backend"},
            )
        ]
        if change:
            checks[0]["filters"]["change_id"] = change["metadata"]["change_id"]
    enough = bool(
        candidate
        and len({s for s, _ in distinct}) >= 2
        and len({path for _, path in distinct}) >= 2
        and discriminator
        and not contradictions
        and candidate.get("status") != "REJECTED"
    )
    if (
        candidate
        and not enough
        and not checks
        and candidate["culprit_service"] in ("redis", "payment")
    ):
        checks = [
            task(
                "metrics",
                len(state.get("tasks", [])),
                "Measure suspected dependency health",
                {"service": candidate["culprit_service"]},
            )
        ]
    if (
        candidate
        and not enough
        and not checks
        and candidate["failure_mode"] == "postgres_connection_exhaustion"
    ):
        checks = [
            task(
                "logs",
                len(state.get("tasks", [])),
                "Check direct database rejection observations",
                {"service": "postgres"},
            )
        ]
    return dict(
        target_hypothesis_id=target,
        verdict="sufficient" if enough else "insufficient",
        contradictions=contradictions,
        requested_checks=checks,
        cited_evidence_ids=list(
            dict.fromkeys(
                [r["evidence_id"] for r in supporting]
                + [r["evidence_id"] for r in records if normal_database([r])]
            )
        ),
        rationale="Independent sources and a cause discriminator support the candidate"
        if enough
        else "Missing independent causal support or an unresolved contradictory observation",
    )


class MockProvider(LLMProvider):
    model_id = "deterministic-public-policy-v1"

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        if self.request_guard is not None:
            self.request_guard()
        started = time.monotonic()
        p = json_payload(user_payload)
        name = output_model.__name__
        if name in ("CoordinatorDecision", "DynamicDecision"):
            result = self._decide(p)
        elif name == "InvestigatorPlan":
            result = self._plan(p)
        elif name == "AnalysisOutput":
            result = self._analyze(p)
        elif name == "Review":
            result = review(p)
        else:
            raise ProviderError("MOCK_UNSUPPORTED_SCHEMA")
        model = output_model.model_validate_json(json.dumps(result))
        return model, dict(
            source="mock",
            model_id=self.model_id,
            llm_calls=1,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            elapsed_ms=(time.monotonic() - started) * 1000,
        )

    def _decide(self, p):
        tasks = p.get("tasks", [])
        # Match the current runtime's mechanism/corroboration requirements using
        # only observations and gate feedback. Never infer from fixture IDs.
        if tasks and not p.get("fixed_schedule_completed"):
            observed = p.get("shared_observations", []) or list(p.get("evidence_index", {}).values())
            database_tools = p.get("database_enabled") and any(
                "get_db_connections" in tools for tools in p.get("role_tool_acl", {}).values())
            for candidate in p.get("hypotheses", []):
                service = candidate.get("culprit_service")
                errors = p.get("candidate_assessments", {}).get(candidate["hypothesis_id"], {}).get("finalize_errors", [])
                needs_own_log = any(error in errors for error in (
                    "No observed cause-specific discriminator for the candidate",
                    "No temporally compatible cross-source impact or corroboration"))
                checked = any(query.get("tool_name") == "query_logs"
                              and query.get("args", {}).get("service") == service
                              and query.get("ok") and query.get("completed")
                              and not query.get("next_cursor") for query in p.get("query_history", []))
                if (candidate.get("status") != "REJECTED" and service != "backend" and needs_own_log
                    and not (service == "postgres" and database_tools) and not checked and not any(r.get("source_type") == "logs" and r.get("service") == service for r in observed)):
                    return dict(action="INVESTIGATE", reason="Inspect the observed dependency mechanism",
                                assignments=[task("logs", len(tasks), "Inspect the dependency's own failure logs",
                                                  {"service": service})])
        checks = p.get("requested_checks", [])
        if not checks and p.get("reviews"):
            checks = p["reviews"][-1].get("requested_checks", [])
        completed = set(p.get("completed_task_ids", []))
        checks = [c for c in checks if c["task_id"] not in completed]
        latest = p.get("reviews", [])
        db_signal = any(
            h.get("culprit_service") == "postgres" for h in p.get("hypotheses", [])
        ) or any(
            "database" in s.lower() or "db " in s.lower()
            for s in p.get("public_summary", {}).get("observed_symptoms", [])
        )
        available_role = (
            "database"
            if p.get("database_enabled")
            else "metrics"
            if "get_db_connections" in p.get("role_tool_acl", {}).get("metrics", [])
            else None
        )
        if (
            tasks
            and db_signal
            and available_role
            and not any(t.get("filters", {}).get("database_internal") for t in tasks)
        ):
            assignment = task(
                available_role,
                len(tasks),
                "Distinguish database internal fault from upstream pool symptoms",
                {"database_internal": True, "service": "postgres"},
            )
            assignment["allowed_tools"] = p["role_tool_acl"][available_role]
            return dict(
                action="INVESTIGATE",
                reason="Database hypothesis requires internal checks",
                assignments=[assignment],
            )
        if p.get("variant") in ("single", "dynamic_no_verifier", "no_verifier"):
            latest = [review(p)]
            if not checks:
                checks = latest[-1]["requested_checks"]
        if latest and latest[-1]["verdict"] == "sufficient":
            return dict(
                action="FINALIZE",
                reason="Verifier accepted causal evidence",
                selected_hypothesis_id=latest[-1]["target_hypothesis_id"],
                stop_reason="Evidence sufficient",
            )
        completed_checks = {
            json.dumps((t["role"], t["question"], t.get("filters", {})), sort_keys=True)
            for t in tasks
            if t.get("task_id") in completed
        }
        checks = [
            c
            for c in checks
            if json.dumps((c["role"], c["question"], c.get("filters", {})), sort_keys=True)
            not in completed_checks
        ]
        checks = [check for check in checks if not (
            "query_logs" in check.get("allowed_tools", [])
            and check.get("filters", {}).get("service")
            and any(query.get("tool_name") == "query_logs" and query.get("ok")
                    and query.get("completed") and not query.get("next_cursor")
                    and all(query.get("args", {}).get(key) == value
                            for key, value in check["filters"].items())
                    for query in p.get("query_history", []))
        )]
        if checks:
            return dict(
                action="INVESTIGATE",
                reason="Follow verifier discriminating check",
                assignments=checks[:2],
            )
        if not tasks:
            return dict(
                action="INVESTIGATE",
                reason="Compare symptoms with service health",
                assignments=[
                    task("logs", 0, "Identify error propagation"),
                    task("metrics", 0, "Compare dependency health"),
                ],
            )
        if "changes" not in {t["role"] for t in tasks}:
            return dict(
                action="INVESTIGATE",
                reason="Check changes against observed symptoms",
                assignments=[
                    task(
                        "changes",
                        len(tasks),
                        "Check recent backend changes",
                        {"service": "backend"},
                    )
                ],
            )
        return dict(
            action="ABSTAIN",
            reason="Observed evidence lacks sufficient causal support",
            stop_reason="Missing discriminating evidence",
        )

    def _plan(self, p):
        role = p["task"]["role"]
        filters = p["task"].get("filters", {})
        summary = p["public_summary"]
        start = filters.get("start_ts", summary.get("started_at"))
        # Runtime may provide an explicit window; equal bounds still query incident-start records.
        end = filters.get("end_ts", summary.get("ended_at", "9999-12-31T23:59:59Z"))
        if role == "logs":
            calls = [
                dict(
                    tool_name="query_logs",
                    args=dict(
                        service=filters.get("service", "backend"),
                        start_ts=start,
                        end_ts=end,
                        limit=50,
                    ),
                )
            ]
        elif role == "database" or filters.get("database_internal"):
            calls = [
                dict(tool_name=name, args=dict(service="postgres", start_ts=start, end_ts=end))
                for name in ("get_db_connections", "get_db_lock_waits")
            ]
        elif role == "metrics":
            calls = [
                dict(
                    tool_name="query_metrics",
                    args=dict(
                        service=s,
                        metric_names=filters.get("metric_names", []),
                        start_ts=start,
                        end_ts=end,
                    ),
                )
                for s in ("postgres", "backend")
            ]
            if filters.get("service"):
                calls = [calls[0]]
                calls[0]["args"]["service"] = filters["service"]
            symptoms = " ".join(summary.get("observed_symptoms", [])).lower()
            for dependency in ("redis", "payment"):
                if dependency in symptoms:
                    calls[0]["args"]["service"] = dependency
        elif role == "changes":
            start = (
                (
                    datetime.fromisoformat(start.replace("Z", "+00:00")) - timedelta(minutes=10)
                ).isoformat()
                if start
                else None
            )
            facts = p.get("minimal_facts", [])
            change_id = filters.get("change_id")
            if not change_id and isinstance(facts, list):
                change_id = next(
                    (
                        f.get("metadata", {}).get("change_id")
                        for f in facts
                        if isinstance(f, dict)
                        and f.get("service") == "backend"
                        and f.get("metadata", {}).get("change_id")
                    ),
                    None,
                )
            calls = (
                [dict(tool_name="get_config_diff", args={"change_id": change_id})]
                if change_id
                else [
                    dict(
                        tool_name="query_changes",
                        args=dict(
                            service=filters.get("service", "backend"), start_ts=start, end_ts=end
                        ),
                    )
                ]
            )
            if change_id:
                calls.append(
                    dict(
                        tool_name="query_changes",
                        args=dict(service="backend", start_ts=start, end_ts=end),
                    )
                )
        else:
            raise ProviderError("MOCK_ROLE_UNSUPPORTED")
        return dict(calls=calls)

    def _analyze(self, p):
        c, t, records = p["context"], p["task"], p["records"]
        groups = {}
        for r in records:
            category = classify(r)
            if category:
                service, mode, decisive = category
                groups.setdefault((service, mode), []).append(r["evidence_id"])
        pool_changes = {
            r.get("metadata", {}).get("change_id")
            for r in records
            if r["source_type"] == "configs"
            and classify(r)
            and classify(r)[1] == "backend_pool_config_regression"
        }
        if pool_changes:
            groups.setdefault(("backend", "backend_pool_config_regression"), []).extend(
                r["evidence_id"]
                for r in records
                if r["source_type"] == "changes"
                and r.get("metadata", {}).get("change_id") in pool_changes
            )
        mechanisms = {
            "postgres_lock_contention": [
                "Blocking transaction holds a database lock",
                "Waiting queries exceed backend deadlines",
            ],
            "postgres_slow_query": [
                "Slow database execution delays queries",
                "Backend requests exceed deadlines",
            ],
            "backend_pool_config_regression": [
                "Reduced backend pool capacity causes local acquisition contention",
                "Acquisition deadlines fail while database capacity remains available",
            ],
            "postgres_connection_exhaustion": [
                "Database sessions reach server connection capacity",
                "New database sessions are rejected and backend requests fail",
            ],
            "redis_unavailable": [
                "Cache availability fails",
                "Backend synchronous fallback increases request work and errors",
            ],
            "payment_external_timeout": [
                "Payment upstream exceeds client deadlines",
                "Checkout requests fail and backend surfaces payment errors",
            ],
            "backend_resource_saturation": [
                "Backend compute or worker queue capacity saturates",
                "Requests exceed worker deadlines and upstream receives errors",
            ],
        }
        hypotheses = [
            dict(
                hypothesis_id="hyp-" + mode,
                culprit_service=service,
                failure_mode=mode,
                support_ids=ids,
                predicted_observations=[*mechanisms[mode]],
                status="OPEN",
            )
            for (service, mode), ids in groups.items()
        ]
        if normal_database(records):
            hypotheses.append(
                dict(
                    hypothesis_id="hyp-postgres_connection_exhaustion",
                    culprit_service="postgres",
                    failure_mode="postgres_connection_exhaustion",
                    support_ids=[],
                    against_ids=[r["evidence_id"] for r in records if normal_database([r])],
                    status="REJECTED",
                    predicted_observations=["Database capacity should be exhausted"],
                )
            )
        ids = [r["evidence_id"] for r in records]
        claim = "Observed evidence " + ", ".join(ids) if ids else "No matching public observations"
        if normal_database(records):
            claim += ": database health is normal; check backend pool configuration"
        return dict(
            finding=dict(
                finding_id="finding-" + t["task_id"],
                task_id=t["task_id"],
                run_id=c["run_id"],
                incident_id=c["incident_id"],
                role=t["role"],
                claim=claim,
                evidence_ids=ids,
                relation="supports" if hypotheses else "neutral",
                confidence_qualifier="supported" if ids else "unknown",
            ),
            hypotheses=hypotheses,
        )
