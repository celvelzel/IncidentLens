"""Recomputable scores; citation existence is distinct from semantic support."""

from .termination import SCORING_VERSION, normalize_termination

VARIANTS = ("single", "fixed", "dynamic_no_verifier", "full")


def report_citations(report):
    if not report:
        return []
    ids = list(report.get("supporting_evidence_ids", []))
    for hypothesis in [report.get("root_cause"), *report.get("rejected_hypotheses", [])]:
        if hypothesis:
            ids.extend(hypothesis.get("support_ids", []))
            ids.extend(hypothesis.get("against_ids", []))
    return sorted(set(ids))


def citation_metrics(state):
    citations = report_citations(state.get("report"))
    index = state.get("evidence_index", {})
    observed = {
        record["evidence_id"]
        for event in state.get("events", [])
        if event.get("event_type") == "TOOL_CALL"
        for record in event.get("details", {}).get("result", {}).get("records", [])
        if record.get("incident_id") == state["incident_id"]
    }
    valid = [
        eid
        for eid in citations
        if eid in index
        and eid in observed
        and index[eid].get("incident_id") == state["incident_id"]
    ]
    return dict(
        citation_count=len(citations),
        valid_citation_count=len(valid),
        citation_existence_validity=len(valid) / len(citations) if citations else None,
    )


def score_completed(state, oracle):
    """The caller must finish execution before supplying the evaluator-only oracle."""
    report = state.get("report")
    if report is None:
        raise ValueError("evaluation requires a completed report")
    identifiable = oracle["is_identifiable"]
    if not isinstance(identifiable, bool):
        raise ValueError("oracle identifiability must be boolean")
    root = report.get("root_cause")
    terminal = normalize_termination(state)
    runtime_failure = terminal["runtime_failure"] or report.get("status") == "ERROR"
    diagnosis_match = bool(
        report["status"] == "RESOLVED"
        and root
        and root["culprit_service"] == oracle["culprit_service"]
        and root["failure_mode"] == oracle["failure_mode"]
    )
    correct = bool(not terminal["diagnosis_failure"] and diagnosis_match)
    alert = (state.get("incident_alert") or {}).get("status")
    no_alert = terminal["termination_reason"] == "NO_ALERT" or alert == "NO_ALERT"
    expected_alert = oracle.get("monitoring_expected_alert")
    monitoring_accuracy = (
        alert == expected_alert if alert and expected_alert in {"ALERT", "NO_ALERT"} else None
    )
    abstained = (
        not runtime_failure
        and terminal["protocol_valid"] is not False
        and not no_alert
        and report["status"] == "INCONCLUSIVE"
        and root is None
    )
    remediation = report.get("remediation_status")
    remediation_success = (
        remediation == "PLAN_READY" and terminal["protocol_valid"] is True
        if remediation in {"PLAN_READY", "PLAN_FAILED"}
        else None
    )
    workflow_success = False if runtime_failure else None
    if terminal["termination_source"] != "legacy":
        outcome = terminal["termination_outcome"]
        achieved = (
            correct
            if outcome == "SUCCESS"
            else (abstained and not identifiable)
            if outcome == "ABSTAINED"
            else False
        )
        if outcome == "NO_ACTION":
            # Monitoring has its own ground truth; RCA identifiability is not an alert oracle.
            achieved = monitoring_accuracy
        workflow_success = (
            False
            if not terminal["stop_completion"]
            or runtime_failure
            or terminal["protocol_valid"] is False
            else achieved
            if remediation_success is not False
            else False
        )
    index = state.get("evidence_index", {})
    misleading = bool(oracle.get("misleading_evidence_ids"))
    return dict(
        **{k: v for k, v in terminal.items() if k not in {"runtime_failure", "diagnosis_failure"}},
        identifiable=identifiable,
        runtime_failure=runtime_failure,
        diagnosis_match=diagnosis_match if identifiable and not no_alert else None,
        root_cause_correct=correct if identifiable and not no_alert else None,
        correct_abstention=abstained if not identifiable and not no_alert else None,
        remediation_success=remediation_success,
        workflow_success=workflow_success,
        monitoring_accuracy=monitoring_accuracy,
        misleading_case=misleading,
        misleading_correct=correct if misleading and identifiable and not no_alert else None,
        misleading_decoy_observed=bool(set(oracle.get("misleading_evidence_ids", [])) & set(index)),
        **citation_metrics(state),
        unsupported_claim_rate=None,
        semantic_review_status="unreviewed",
    )


def score_without_oracle(state):
    """Retain execution facts, but never invent answer quality when truth is unavailable."""
    terminal = normalize_termination(state)
    result = {k: v for k, v in terminal.items() if k != "diagnosis_failure"}
    if (state.get("report") or {}).get("status") == "ERROR":
        result["runtime_failure"] = True
    remediation = (state.get("report") or {}).get("remediation_status")
    result.update(
        dict(
            identifiable=None,
            diagnosis_match=None,
            root_cause_correct=None,
            correct_abstention=None,
            misleading_case=None,
            misleading_correct=None,
            misleading_decoy_observed=None,
            remediation_success=(remediation == "PLAN_READY" and terminal["protocol_valid"] is True)
            if remediation in {"PLAN_READY", "PLAN_FAILED"}
            else None,
            monitoring_accuracy=None,
            workflow_success=False
            if result["runtime_failure"]
            or result["protocol_valid"] is False
            or result["termination_outcome"] == "FAILED"
            else None,
            **citation_metrics(state),
            unsupported_claim_rate=None,
            semantic_review_status="unreviewed",
        )
    )
    return result


def aggregate(rows):
    versions = {r.get("scoring_version", "legacy") for r in rows}
    if len(versions) > 1:
        raise ValueError("cannot aggregate mixed scoring versions; recompute all rows first")
    result = []
    for variant in VARIANTS:
        group = [r for r in rows if r["variant"] == variant]
        if not group:
            continue

        def ratio(key):
            values = [r[key] for r in group if r.get(key) is not None]
            return sum(values), len(values), sum(values) / len(values) if values else None

        accuracy_n, accuracy_d, accuracy = ratio("root_cause_correct")
        abstention_n, abstention_d, abstention = ratio("correct_abstention")
        misleading_n, misleading_d, misleading = ratio("misleading_correct")
        citations = sum(r.get("citation_count", 0) for r in group)
        valid = sum(r.get("valid_citation_count", 0) for r in group)

        def measured_sum(key):
            values = [r.get(key) for r in group]
            return sum(values) if all(v is not None for v in values) else None

        result.append(
            dict(
                variant=variant,
                scoring_version=next(iter(versions), SCORING_VERSION),
                source=group[0]["source"],
                split=group[0]["split"],
                runs=len(group),
                error_runs=sum(r["status"] == "ERROR" for r in group),
                runtime_failure_runs=sum(bool(r.get("runtime_failure", False)) for r in group),
                resolved_runs=sum(r["status"] == "RESOLVED" for r in group),
                inconclusive_runs=sum(r["status"] == "INCONCLUSIVE" for r in group),
                root_cause_correct=accuracy_n,
                identifiable_denominator=accuracy_d,
                root_cause_accuracy=accuracy,
                correct_abstentions=abstention_n,
                unidentifiable_denominator=abstention_d,
                correct_abstention_rate=abstention,
                misleading_correct=misleading_n,
                misleading_identifiable_denominator=misleading_d,
                misleading_accuracy=misleading,
                valid_citations=valid,
                citation_denominator=citations,
                citation_existence_validity=valid / citations if citations else None,
                tool_calls=measured_sum("tool_calls"),
                llm_requests=measured_sum("llm_requests"),
                total_tokens=measured_sum("total_tokens"),
                cost_usd=measured_sum("cost_usd"),
                failed_calls=measured_sum("failed_calls"),
                latency_ms=measured_sum("latency_ms"),
                unsupported_claim_rate=None,
                semantic_review_status="unreviewed",
                cache_mode="off",
            )
        )
        for metric in (
            "diagnosis_match",
            "remediation_success",
            "stop_completion",
            "workflow_success",
            "protocol_valid",
            "monitoring_accuracy",
            "root_cause_correct",
            "correct_abstention",
            "misleading_correct",
        ):
            values = [r.get(metric) for r in group if r.get(metric) is not None]
            result[-1].update(
                {
                    metric + "_successes": sum(v is True for v in values),
                    metric + "_failures": sum(v is False for v in values),
                    metric + "_denominator": len(values),
                    metric + "_unknown": len(group) - len(values),
                    metric + "_rate": sum(v is True for v in values) / len(values)
                    if values
                    else None,
                }
            )
        result[-1]["runtime_failure_unknown"] = sum(r.get("runtime_failure") is None for r in group)
        for field in ("recovered_model_failure_count", "unrecovered_model_failure_count"):
            result[-1][field] = measured_sum(field)
    return result
