"""Actual LangGraph dynamic investigation service; no parallel Python loop."""

import asyncio
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from incident_lens.orchestration.budget import CallBudget
from incident_lens.orchestration.guards import (
    cause_discriminator,
    evidence_fingerprint,
    finalize_errors,
    review_fingerprint,
)
from incident_lens.orchestration.merge import merge_results
from incident_lens.schemas import (
    Budget,
    CoordinatorDecision,
    InvestigationState,
    InvestigationTask,
    RCAReport,
    TraceEvent,
)
from incident_lens.schemas.workflow import WorkflowOptions


class GraphState(TypedDict):
    investigation: InvestigationState
    local_results: list
    route: str


class InvestigationRun:
    def __init__(
        self,
        provider,
        evidence_provider,
        incident_id,
        limits=None,
        variant="full",
        workspace_id="incident-lens",
        run_id=None,
        cache=None,
        workflow=None,
    ):
        from incident_lens.tools import ToolRegistry

        self.provider = copy.copy(provider)
        self.evidence_provider = evidence_provider
        self.limits = limits or Budget()
        self.variant = variant
        self.workflow = workflow or WorkflowOptions()
        self.response_profile = self.workflow.profile == "incident_response"
        self.stage_calls = {"monitoring": 0, "remediation": 0}
        self.remediation_versions = set()
        self.active_workers = {}
        self.active_model_calls = {}
        self.cache = copy.copy(cache) if cache is not None else None
        if self.cache is not None:
            # Derive revision at each run boundary, including long-lived API adapters.
            # Keep the caller's adapter unchanged for concurrent-run isolation.
            self.cache.dataset_revision = evidence_provider.dataset_revision
        self.run_id = run_id or "run-" + uuid4().hex
        self.registry = ToolRegistry(
            evidence_provider,
            workspace_id,
            incident_id,
            self.run_id,
            max_tool_calls=self.limits.max_tool_calls,
            timeout_seconds=min(10.0, self.limits.max_wall_seconds),
            database_equivalent_tools=self.workflow.database_equivalent_tools,
        )
        self.call_budget = CallBudget(self.limits)
        if hasattr(self.provider, "request_guard"):
            self.provider.request_guard = self.consume_request
            self.call_budget.guarded_provider = True
        if hasattr(self.provider, "token_observer"):
            self.provider.token_observer = self.call_budget.observe_tokens
            self.call_budget.observed_tokens = True
        self.signatures = set()
        self.failed_finalizations = set()
        self.tool_events_offset = 0
        self.state = InvestigationState(
            workspace_id=workspace_id,
            incident_id=incident_id,
            run_id=self.run_id,
            public_summary=evidence_provider.load_case(incident_id),
            budgets=self.limits,
        )
        from incident_lens.orchestration.runtime import StopController, TaskManager

        self.task_manager = TaskManager(self.workflow.max_attempts, self.runtime_event)
        self.stop_controller = StopController(
            incident_id, self.run_id, self.runtime_event, self.workflow.ack_timeout_seconds
        )
        self.single_context = (
            self.registry.create_context("single") if variant == "single" else None
        )

    def event(self, state, event_type, role=None, source="runtime", message="", **details):
        event = TraceEvent(
            event_id=f"event-{len(state.events) + 1}",
            run_id=state.run_id,
            incident_id=state.incident_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            role=role,
            source=source,
            message=message,
            details=details,
        )
        state.events.append(event)

    def runtime_event(self, event_type, **details):
        if event_type == "STOP":
            error = next(
                (e for e in reversed(self.state.events) if e.event_type == "RUNTIME_ERROR"), None
            )
            if error and error.details.get("stage"):
                details["stage"] = error.details["stage"]
        self.event(self.state, event_type, **details)

    def consume_request(self):
        self.stop_controller.guard()
        self.call_budget.consume_request()

    async def model_call(self, role, function, *args):
        self.stop_controller.guard()
        pending = asyncio.create_task(self.call_budget.call(function, *args))
        self.active_model_calls[pending] = role
        try:
            result = await pending
            self.stop_controller.guard()
            return result
        finally:
            self.active_model_calls.pop(pending, None)

    async def stage_call(self, stage, function, *args):
        maximum = getattr(self.workflow, stage + "_max_calls")
        original_guard = getattr(self.provider, "request_guard", None)

        def guard():
            self.stop_controller.guard()
            if self.stage_calls[stage] >= maximum:
                raise RuntimeError(stage + " stage budget exhausted")
            self.stage_calls[stage] += 1
            self.call_budget.consume_request()

        if hasattr(self.provider, "request_guard"):
            self.provider.request_guard = guard
        else:
            if self.stage_calls[stage] >= maximum:
                raise RuntimeError(stage + " stage budget exhausted")
            self.stage_calls[stage] += 1
        try:
            if getattr(self.provider, "model_id", "") == "deterministic-public-policy-v1":
                guard()
            output, usage = await self.model_call(stage, function, *args)
            self.update_usage(self.state, usage, stage)
            return output
        finally:
            if hasattr(self.provider, "request_guard"):
                self.provider.request_guard = original_guard

    async def monitor(self, value):
        from incident_lens.agents.monitoring import monitor

        state = value["investigation"]
        self.state = state
        if self.workflow.monitor_mode == "legacy":
            return {"investigation": state, "route": "coordinate"}
        try:
            if any(
                r.incident_id != state.incident_id or r.service not in state.public_summary.services
                for r in self.workflow.snapshot
            ):
                raise ValueError("Monitoring snapshot identity mismatch")
            state.incident_alert = await self.stage_call(
                "monitoring",
                monitor,
                self.provider,
                state.incident_id,
                self.workflow.snapshot,
                self.workflow.monitor_mode,
            )
            self.event(
                state,
                "INCIDENT_ALERT",
                role="monitoring",
                alert=state.incident_alert.model_dump(mode="json"),
            )
            if state.incident_alert.status == "NO_ALERT":
                state.stop_reason = "NO_ALERT"
                return {"investigation": state, "route": "stop"}
            return {"investigation": state, "route": "coordinate"}
        except Exception as exc:
            state.stop_reason = self.safe_error(exc)
            return {"investigation": state, "route": "stop"}

    def payload(self, state, role="coordinator", fetched=None):
        value = state.model_dump(mode="json")
        value["variant"] = self.variant
        from incident_lens.security.context import ROLE_TOOL_ACL

        value["workflow_profile"] = self.workflow.profile
        value["database_enabled"] = self.response_profile and self.workflow.database_enabled
        value["role_tool_acl"] = {
            role: list(tools)
            for role, tools in ROLE_TOOL_ACL.items()
            if role != "database" or value["database_enabled"]
        }
        if self.workflow.database_equivalent_tools:
            from incident_lens.security.context import DATABASE_TOOLS

            for name in ("metrics", "single"):
                value["role_tool_acl"][name] += list(DATABASE_TOOLS)
        value["events"] = []
        if role == "verifier":
            value["evidence_index"] = {
                r.evidence_id: r.model_dump(mode="json") for r in fetched or []
            }
        elif self.variant != "single":
            value["evidence_index"] = {}
            value["evidence_catalog"] = {
                eid: {
                    "evidence_id": eid,
                    "service": record.service,
                    "source_type": record.source_type,
                    "source_path": record.source_path,
                    "metadata": {"change_id": record.metadata["change_id"]}
                    if "change_id" in record.metadata
                    else {},
                }
                for eid, record in state.evidence_index.items()
            }
            value["discriminator_matches"] = {
                h.hypothesis_id: [
                    eid
                    for eid, record in state.evidence_index.items()
                    if cause_discriminator(h, record)
                ]
                for h in state.hypotheses
            }
            value["database_health_normal"] = any(
                h.culprit_service == "postgres" and h.status == "REJECTED" and h.against_ids
                for h in state.hypotheses
            )
        return value

    def update_usage(self, state, usage, role):
        state.llm_calls_used = self.call_budget.calls
        state.tokens_used = self.call_budget.tokens
        from incident_lens.agents.service import PROMPT_VERSION

        details = {key: value for key, value in usage.items() if key != "source"}
        details["prompt_version"] = PROMPT_VERSION
        details["model_parameters"] = getattr(
            self.provider, "model_parameters", {"temperature": self.provider.temperature}
        )
        self.event(state, "LLM_CALL", role=role, source=usage.get("source", "model"), **details)

    def exhausted(self, state):
        if not self.call_budget.remaining_seconds():
            return "Wall-clock budget exhausted"
        if self.call_budget.calls >= self.limits.max_llm_calls:
            return "LLM call budget exhausted"
        if self.limits.max_tokens and self.call_budget.tokens >= self.limits.max_tokens:
            return "Token budget exhausted"
        return None

    async def coordinate(self, value):
        from incident_lens.agents.service import decide

        state = value["investigation"]
        self.state = state
        try:
            self.stop_controller.guard()
            reason = self.exhausted(state)
            if reason:
                raise RuntimeError(reason)
            if self.variant == "fixed" and not state.decisions:
                tasks = [
                    InvestigationTask(
                        task_id="fixed-" + role,
                        role=role,
                        question=f"Investigate {role} evidence for the incident",
                        allowed_tools=list(
                            __import__(
                                "incident_lens.security.context", fromlist=["ROLE_TOOL_ACL"]
                            ).ROLE_TOOL_ACL[role]
                        ),
                        reason="Fixed once-only baseline",
                        expected_discriminator="distinguish service failure from downstream symptom",
                    )
                    for role in ("logs", "metrics", "changes")
                ]
                decision = CoordinatorDecision(
                    action="INVESTIGATE", reason="Fixed schedule", assignments=tasks
                )
            elif self.variant == "fixed":
                candidates = [h for h in state.hypotheses if not finalize_errors(state, h, "fixed")]
                decision = CoordinatorDecision(
                    action="FINALIZE" if candidates else "ABSTAIN",
                    reason="Fixed schedule completed",
                    selected_hypothesis_id=candidates[0].hypothesis_id if candidates else None,
                    stop_reason="Fixed schedule completed",
                )
            else:
                decision, usage = await self.model_call(
                    "single" if self.variant == "single" else "coordinator",
                    decide,
                    self.provider,
                    self.payload(state),
                )
                self.update_usage(
                    state, usage, "single" if self.variant == "single" else "coordinator"
                )
                if decision.action == "INVESTIGATE" and len(decision.assignments) > 2:
                    raise RuntimeError("Coordinator may assign at most two tasks per round")
            state.decisions.append(decision)
            self.event(
                state,
                "DECISION",
                role="single" if self.variant == "single" else "coordinator",
                message=decision.reason,
                decision=decision.model_dump(mode="json"),
            )
            if decision.action == "ABSTAIN":
                state.stop_reason = decision.stop_reason
                return {"investigation": state, "route": "report"}
            if decision.action == "FINALIZE":
                return {"investigation": state, "route": "finalize"}
            if state.round_index >= self.limits.max_rounds:
                raise RuntimeError("Round budget exhausted")
            if self.registry.call_count >= self.limits.max_tool_calls:
                raise RuntimeError("Tool budget exhausted")
            signature = json.dumps(
                [(t.role, t.question, t.filters) for t in decision.assignments], sort_keys=True
            )
            # Repeated task against an unchanged board is a loop, not progress.
            signature += json.dumps(sorted(state.evidence_index))
            if signature in self.signatures:
                raise RuntimeError("Repeated investigation with unchanged evidence")
            self.signatures.add(signature)
            existing = {t.task_id for t in state.tasks}
            if any(t.task_id in existing for t in decision.assignments):
                raise RuntimeError("Task IDs must be fresh per assignment")
            state.tasks.extend(decision.assignments)
            for task in decision.assignments:
                self.task_manager.assign(task.task_id, task.role)
            state.round_index += 1
            return {"investigation": state, "route": "dispatch"}
        except Exception as exc:
            state.stop_reason = self.safe_error(exc)
            self.event(state, "RUNTIME_ERROR", message=state.stop_reason)
            return {"investigation": state, "route": "report"}

    @staticmethod
    def safe_error(exc):
        # Provider errors must be sanitized at adapter boundary. Unknown exceptions
        # expose their type only; no request payload, credentials or stack traces.
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return "TIMEOUT"
        merge_codes = {
            "Rejected worker identity/task mismatch": "MERGE_IDENTITY_MISMATCH",
            "Finding cites evidence not observed by this worker": "MERGE_UNOBSERVED_FINDING",
            "Hypothesis cites unpublished or unobserved evidence": "MERGE_UNOBSERVED_HYPOTHESIS",
            "Finding ID reused for a different observation/task": "MERGE_FINDING_ID_COLLISION",
            "Hypothesis ID reused for a different cause": "MERGE_HYPOTHESIS_ID_COLLISION",
        }
        if isinstance(exc, ValueError) and str(exc) in merge_codes:
            return merge_codes[str(exc)]
        known = str(exc)
        if (
            isinstance(exc, RuntimeError)
            and len(known) < 150
            and not any(x in known.lower() for x in ("key", "http", "bearer"))
        ):
            return known
        return type(exc).__name__

    async def investigate(self, state, task):
        from incident_lens.agents.service import analyze, plan_tools

        context = self.single_context or self.registry.create_context(task.role)
        role = "single" if self.variant == "single" else task.role
        minimal = {
            "findings": [f.model_dump(mode="json") for f in state.findings],
            "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
            "evidence_index": {
                eid: record.model_dump(mode="json") for eid, record in state.evidence_index.items()
            },
        }
        plan, usage = await self.model_call(
            role, plan_tools, self.provider, context, task, state.public_summary, minimal
        )
        self.update_usage(state, usage, role)
        records = []
        for call in plan.calls:
            if not self.call_budget.remaining_seconds():
                raise RuntimeError("Wall-clock budget exhausted")
            result = await asyncio.wait_for(
                asyncio.to_thread(self.registry.execute, context, call.tool_name, call.args),
                timeout=self.call_budget.remaining_seconds(),
            )
            self.event(
                state,
                "TOOL_CALL",
                role=role,
                tool_name=call.tool_name,
                args=call.args,
                result=result.model_dump(mode="json"),
                task_id=task.task_id,
            )
            if not result.ok:
                raise RuntimeError("Tool failed: " + str(result.error_code))
            records.extend(result.records)
        unique = {r.evidence_id: r for r in records}
        if self.cache is None:
            analysis, usage = await self.model_call(
                role, analyze, self.provider, context, task, list(unique.values())
            )
            self.update_usage(state, usage, role)
        else:

            async def execute_model():
                output, usage = await self.model_call(
                    role, analyze, self.provider, context, task, list(unique.values())
                )
                self.update_usage(state, usage, role)
                return output

            analysis = await self.cache.explain(
                context,
                task,
                list(unique.values()),
                self.registry,
                self.provider,
                execute_model,
                lambda kind, **data: self.event(state, kind, role=role, source="cache", **data),
            )
        return context, task, analysis

    async def dispatch(self, value):
        state = value["investigation"]
        self.state = state
        try:
            # Concurrent read-only investigators; state publication happens only
            # after all local outputs return. Provider/usage calls are observable.
            tasks = state.decisions[-1].assignments
            if self.variant == "single":
                results = []
                for task in tasks:
                    results.append(await self.execute_task(state, task))
            else:
                pending = [asyncio.create_task(self.execute_task(state, t)) for t in tasks]
                self.active_workers.update({t.task_id: p for t, p in zip(tasks, pending)})
                try:
                    if self.response_profile:
                        outcomes = await asyncio.gather(*pending, return_exceptions=True)
                        results = [r for r in outcomes if not isinstance(r, BaseException)]
                        failures = [r for r in outcomes if isinstance(r, BaseException)]
                        if failures and (
                            not results or not self.workflow.continue_on_partial_failure
                        ):
                            raise failures[0]
                    else:
                        results = await asyncio.gather(*pending)
                except Exception:
                    for worker in pending:
                        if not worker.done():
                            worker.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise
                finally:
                    self.active_workers.clear()
            state.tool_calls_used = self.registry.call_count
            return {"investigation": state, "local_results": results, "route": "merge"}
        except Exception as exc:
            state.tool_calls_used = self.registry.call_count
            state.stop_reason = self.safe_error(exc)
            self.event(state, "RUNTIME_ERROR", message=state.stop_reason)
            return {"investigation": state, "route": "report", "local_results": []}

    async def execute_task(self, state, task):
        while True:
            self.stop_controller.guard()
            self.task_manager.start(task.task_id)
            try:
                result = await self.investigate(state, task)
                self.stop_controller.guard()
                self.task_manager.complete(task.task_id)
                return result
            except asyncio.CancelledError:
                self.task_manager.cancel(task.task_id)
                raise
            except Exception as exc:
                if self.stop_controller.stopped:
                    self.task_manager.cancel(task.task_id)
                    raise
                self.task_manager.fail(task.task_id, self.safe_error(exc))
                if (
                    not self.response_profile
                    or not self.task_manager.can_retry(task.task_id)
                    or self.exhausted(state)
                ):
                    raise
                self.task_manager.assign(task.task_id, task.role)

    def merge(self, value):
        state = value["investigation"]
        try:
            self.stop_controller.guard()
            state = merge_results(state, value["local_results"], self.registry)
            self.event(
                state,
                "MERGE",
                findings=[f.model_dump(mode="json") for f in state.findings],
                hypotheses=[h.model_dump(mode="json") for h in state.hypotheses],
            )
            return {
                "investigation": state,
                "route": "verify" if self.variant in ("full", "single") else "coordinate",
            }
        except Exception as exc:
            state.stop_reason = self.safe_error(exc)
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="merge",
                error_type=type(exc).__name__,
            )
            return {"investigation": state, "route": "report"}

    async def verify(self, value):
        from incident_lens.agents.service import verify

        state = value["investigation"]
        try:
            # Fetch the shared evidence through verifier ACL before the provider
            # reviews it. No unqueried evidence is available in its payload.
            context = self.single_context or self.registry.create_context("verifier")
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.registry.execute,
                    context,
                    "fetch_evidence_by_ids",
                    {"ids": list(state.evidence_index)[:50]},
                ),
                timeout=self.call_budget.remaining_seconds(),
            )
            self.event(
                state,
                "TOOL_CALL",
                role="single" if self.variant == "single" else "verifier",
                tool_name="fetch_evidence_by_ids",
                result=result.model_dump(mode="json"),
            )
            if not result.ok:
                raise RuntimeError("Verifier tool failed: " + str(result.error_code))
            review, usage = await self.model_call(
                "single" if self.variant == "single" else "verifier",
                verify,
                self.provider,
                self.payload(state, "verifier", result.records),
            )
            self.update_usage(state, usage, "single" if self.variant == "single" else "verifier")
            if not set(review.cited_evidence_ids).issubset(
                {record.evidence_id for record in result.records}
            ):
                raise RuntimeError("Verifier cited unshared evidence")
            state.reviews.append(review)
            state.requested_checks = list(review.requested_checks)
            if (
                review.verdict == "sufficient"
                and not review.contradictions
                and not review.requested_checks
            ):
                state.open_questions = []
            candidate = next(
                (h for h in state.hypotheses if h.hypothesis_id == review.target_hypothesis_id),
                None,
            )
            self.event(
                state,
                "REVIEW",
                role="single" if self.variant == "single" else "verifier",
                review=review.model_dump(mode="json"),
                hypothesis_sha256=review_fingerprint(candidate) if candidate else None,
                evidence_sha256=evidence_fingerprint(state),
            )
            state.tool_calls_used = self.registry.call_count
            return {"investigation": state, "route": "coordinate"}
        except Exception as exc:
            state.stop_reason = self.safe_error(exc)
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="verify",
                error_type=type(exc).__name__,
            )
            return {"investigation": state, "route": "report"}

    def finalize(self, value):
        state = value["investigation"]
        selected = state.decisions[-1].selected_hypothesis_id
        candidate = next((h for h in state.hypotheses if h.hypothesis_id == selected), None)
        errors = (
            finalize_errors(state, candidate, self.variant) if candidate else ["Unknown hypothesis"]
        )
        if self.call_budget.calls > self.limits.max_llm_calls:
            errors.append("LLM budget audit failed")
        if self.limits.max_tokens and self.call_budget.tokens > self.limits.max_tokens:
            errors.append("Token budget audit failed")
        if not self.call_budget.remaining_seconds():
            errors.append("Wall-clock budget audit failed")
        if errors:
            state.open_questions = list(errors)
            self.event(state, "FINALIZE_REJECTED", errors=errors)
            attempt = (selected, tuple(sorted(state.evidence_index)))
            repeated = attempt in self.failed_finalizations
            self.failed_finalizations.add(attempt)
            if (
                not repeated
                and state.round_index < self.limits.max_rounds
                and not self.exhausted(state)
            ):
                return {"investigation": state, "route": "coordinate"}
            state.stop_reason = "; ".join(errors)
        else:
            supported = candidate.model_copy(update={"status": "SUPPORTED"})
            state.report = RCAReport(
                run_id=state.run_id,
                incident_id=state.incident_id,
                status="RESOLVED",
                root_cause=supported,
                causal_chain=supported.predicted_observations,
                supporting_evidence_ids=supported.support_ids,
                rejected_hypotheses=[h for h in state.hypotheses if h.status == "REJECTED"],
                stop_reason=state.decisions[-1].stop_reason or "Evidence sufficient",
            )
        return {
            "investigation": state,
            "route": "remediate"
            if self.response_profile and state.report is not None
            else "report",
        }

    async def remediate(self, value):
        from incident_lens.agents.remediation import remediate, root_cause_version, validate_plan

        state = value["investigation"]
        self.state = state
        report = state.report
        if not self.workflow.remediation_enabled:
            report.remediation_status = "SKIPPED"
            return {"investigation": state, "route": "stop"}
        version = root_cause_version(report)
        if version in self.remediation_versions:
            return {"investigation": state, "route": "stop"}
        task_id = "remediation-" + version
        self.task_manager.assign(task_id, "remediation")
        try:
            while True:
                self.task_manager.start(task_id)
                try:
                    plan = await self.stage_call(
                        "remediation", remediate, self.provider, report, state.evidence_index
                    )
                    validate_plan(plan, report, state.evidence_index)
                    self.stop_controller.guard()
                    report = RCAReport.model_validate_json(
                        report.model_copy(
                            update={"remediation_plan": plan, "remediation_status": "PLAN_READY"}
                        ).model_dump_json()
                    )
                    state.report = report
                    self.remediation_versions.add(version)
                    self.task_manager.complete(task_id)
                    self.event(
                        state,
                        "REMEDIATION_PLAN",
                        role="remediation",
                        plan=plan.model_dump(mode="json"),
                    )
                    break
                except Exception as exc:
                    self.task_manager.fail(task_id, self.safe_error(exc))
                    if not self.task_manager.can_retry(task_id) or self.exhausted(state):
                        raise
                    self.task_manager.assign(task_id, "remediation")
        except Exception as exc:
            report.remediation_status = "PLAN_FAILED"
            self.event(
                state, "REMEDIATION_FAILED", role="remediation", message=self.safe_error(exc)
            )
        return {"investigation": state, "route": "stop"}

    async def stop(self, value):
        state = value["investigation"]
        self.state = state
        state.workflow_status = "STOPPING"
        if state.report is not None:
            state.report.workflow_status = "STOPPING"
        reason = state.stop_reason or "INCONCLUSIVE"
        if state.report is not None and state.report.remediation_status == "PLAN_READY":
            reason = "PLAN_READY"
        elif state.report is not None and state.report.remediation_status == "PLAN_FAILED":
            reason = "PLAN_FAILED"
        elif "budget" in reason.lower():
            reason = "BUDGET_EXHAUSTED"
        elif reason != "NO_ALERT":
            normal_abstention = state.decisions and state.decisions[-1].action == "ABSTAIN"
            rejected_finalization = any(
                e.event_type == "FINALIZE_REJECTED" for e in state.events
            ) and not any(e.event_type == "RUNTIME_ERROR" for e in state.events)
            reason = (
                "INCONCLUSIVE"
                if not self.call_budget.failures
                and (
                    normal_abstention
                    or rejected_finalization
                    or reason
                    in ("INCONCLUSIVE", "Missing discriminating evidence", "Insufficient evidence")
                )
                else "UNRECOVERABLE_ERROR"
            )
            if state.report and state.report.status == "RESOLVED":
                reason = "PLAN_READY" if state.report.remediation_plan else "INCONCLUSIVE"
        self.task_manager.stop()
        self.registry.freeze()
        callbacks = {}
        workers_by_role = {}
        for task_id, worker in self.active_workers.items():
            role = next(t.role for t in state.tasks if t.task_id == task_id)
            workers_by_role.setdefault(role, []).append(worker)
        for pending, role in self.active_model_calls.items():
            workers_by_role.setdefault(role, []).append(pending)
        for role, workers in workers_by_role.items():

            async def cancel_workers(workers=workers):
                for worker in workers:
                    worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)

            callbacks[role] = cancel_workers
        await self.stop_controller.stop(reason, callbacks)
        state.task_records = list(self.task_manager.records)
        state.workflow_status = "FAILED" if reason == "UNRECOVERABLE_ERROR" else "FINISHED"
        if state.report:
            state.report.workflow_status = state.workflow_status
            state.report.diagnosis_status = (
                "RESOLVED" if state.report.status == "RESOLVED" else "INCONCLUSIVE"
            )
        return {"investigation": state, "route": "report"}

    def report(self, value):
        state = value["investigation"]
        for usage in self.call_budget.failures:
            self.event(
                state,
                "MODEL_FAILURE",
                source=usage.get("source", "model"),
                **{key: item for key, item in usage.items() if key != "source"},
            )
        if state.report is None:
            state.report = RCAReport(
                run_id=state.run_id,
                incident_id=state.incident_id,
                status="INCONCLUSIVE",
                unresolved=state.open_questions or ["Need additional discriminating evidence"],
                rejected_hypotheses=[h for h in state.hypotheses if h.status == "REJECTED"],
                stop_reason=state.stop_reason or "Insufficient evidence",
                diagnosis_status="INCONCLUSIVE" if self.response_profile else None,
                remediation_status="SKIPPED" if self.response_profile else "NOT_STARTED",
                workflow_status=state.workflow_status,
            )
        state.tool_calls_used = self.registry.call_count
        state.llm_calls_used = self.call_budget.calls
        state.tokens_used = self.call_budget.tokens
        self.event(
            state,
            "REPORT",
            report=state.report.model_dump(mode="json"),
            variant=self.variant,
            tokens_complete=bool(self.call_budget.usage)
            and all(
                item.get("tokens_complete", item.get("total_tokens") is not None)
                for item in self.call_budget.usage
            ),
        )
        # Revalidate every nested provenance/citation before writing artifacts.
        state = InvestigationState.model_validate_json(state.model_dump_json())
        return {"investigation": state}

    def compile(self):
        graph = StateGraph(GraphState)
        for name in (
            "monitor",
            "coordinate",
            "dispatch",
            "merge",
            "verify",
            "finalize",
            "remediate",
            "stop",
            "report",
        ):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "monitor" if self.response_profile else "coordinate")
        for name in (
            "monitor",
            "coordinate",
            "dispatch",
            "merge",
            "verify",
            "finalize",
            "remediate",
        ):
            graph.add_conditional_edges(
                name,
                lambda value: "stop" if value["route"] == "report" else value["route"],
                {
                    n: n
                    for n in (
                        "coordinate",
                        "dispatch",
                        "merge",
                        "verify",
                        "finalize",
                        "remediate",
                        "stop",
                    )
                },
            )
        graph.add_edge("stop", "report")
        graph.add_edge("report", END)
        return graph.compile()

    async def run(self):
        result = await self.compile().ainvoke(
            {"investigation": self.state, "local_results": [], "route": "coordinate"},
            config={"recursion_limit": 40},
        )
        return result["investigation"]


async def run_investigation(
    incident_id,
    provider,
    data_root=Path("data"),
    budget=None,
    variant="full",
    workspace_id="incident-lens",
    run_id=None,
    cache=None,
    workflow=None,
):
    from incident_lens.tools import EvidenceProvider

    if variant not in {"full", "single", "fixed", "dynamic_no_verifier"}:
        raise ValueError("Unknown variant")
    run = InvestigationRun(
        provider,
        EvidenceProvider(data_root),
        incident_id,
        budget,
        variant,
        workspace_id,
        run_id,
        cache,
        workflow,
    )
    return await run.run()
