"""Actual LangGraph dynamic investigation service; no parallel Python loop."""

import asyncio
import copy
import hashlib
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from incident_lens.orchestration.budget import BudgetExceeded, CallBudget
from incident_lens.orchestration.guards import (
    cause_discriminator,
    competitor_assessments,
    evidence_fingerprint,
    finalize_errors,
    likely_assessment_errors,
    review_fingerprint,
    reviewed_finalization_ready,
)
from incident_lens.orchestration.merge import merge_results
from incident_lens.orchestration.report import observed_chain, populate_assessment
from incident_lens.schemas import (
    Budget,
    CoordinatorDecision,
    InvestigationState,
    InvestigationTask,
    RCAReport,
    TraceEvent,
)
from incident_lens.schemas.workflow import WorkflowOptions, termination_result


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
        journal=None,
    ):
        from incident_lens.tools import ToolRegistry

        self.provider = copy.copy(provider)
        self.journal = journal
        self.evidence_provider = evidence_provider
        self.limits = limits or Budget()
        self.variant = variant
        self.workflow = workflow or WorkflowOptions()
        if (
            self.workflow.selection_policy != "current_dynamic" or self.workflow.shadow_caes
        ) and variant != "full":
            raise ValueError("CAES requires full dynamic variant")
        if self.workflow.benchmark_fixed_four and variant != "fixed":
            raise ValueError("fixed-four option requires fixed variant")
        self.response_profile = self.workflow.profile == "incident_response"
        self.stage_calls = {"monitoring": 0, "remediation": 0}
        self.remediation_versions = set()
        self.active_workers = {}
        self.active_model_calls = {}
        self.call_sequence = 0
        self.call_context = ContextVar("incident_lens_call_context", default={})
        self.request_stage = ContextVar("incident_lens_request_stage", default=None)
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
        self.call_budget = CallBudget(
            self.limits,
            stage_limits={
                "monitoring": self.workflow.monitoring_max_calls,
                "remediation": self.workflow.remediation_max_calls,
            },
        )
        self.provider.recovery_snapshot = lambda: self.call_budget.snapshot(
            self.request_stage.get()
        )
        self.provider.stop_guard = lambda: self.stop_controller.guard()
        self.provider.event_observer = self.runtime_event
        self.provider.request_reconciler = self.call_budget.reconcile_request
        if hasattr(self.provider, "request_guard"):
            self.provider.request_guard = self.consume_request
            self.call_budget.guarded_provider = True
        if hasattr(self.provider, "token_observer"):
            self.provider.token_observer = self.call_budget.observe_tokens
            self.call_budget.observed_tokens = True
        self.signatures = set()
        self.completed_scopes = {}
        self.failed_finalizations = set()
        self.tool_events_offset = 0
        # One-shot guard for changes discovery: only the first query_changes may
        # drop time filters to expose the whole pack; later calls keep their
        # proposed window so a decisive NO_DATA can be observed.
        self.changes_discovery_done = False
        # Reviews recur after reconciliation; each invocation needs a fresh task id.
        self.verify_rounds = 0
        self.coordinate_rounds = 0
        self.last_review_signature = None
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
            task_id=details.get("task_id"),
            call_id=details.get("call_id"),
            source=source,
            message=message,
            details=details,
        )
        state.events.append(event)
        if self.journal is not None:
            self.journal.event(event, self)

    def runtime_event(self, event_type, **details):
        if event_type == "WORKFLOW_STOP_REQUESTED":
            error = next(
                (e for e in reversed(self.state.events) if e.event_type == "RUNTIME_ERROR"), None
            )
            if error and error.details.get("stage"):
                details["stage"] = error.details["stage"]
        self.event(self.state, event_type, **details)

    def consume_request(self):
        self.stop_controller.guard()
        stage = self.request_stage.get()
        maximum = getattr(self.workflow, stage + "_max_calls") if stage else None
        if stage and self.stage_calls[stage] >= maximum:
            raise BudgetExceeded(stage + " stage budget exhausted")
        from incident_lens.llm.provider import HTTP_CALL_CONTEXT

        permit = self.call_budget.consume_request(
            stage=stage,
            run_id=self.run_id,
            logical_call_id=HTTP_CALL_CONTEXT.get() or self.call_context.get().get("call_id", ""),
        )
        if stage:
            self.stage_calls[stage] += 1
        if self.journal is not None:
            self.journal.request(self, permit)
        return permit

    async def model_call(self, role, function, *args):
        self.stop_controller.guard()
        self.call_sequence += 1
        stage = (
            role
            if role in {"monitoring", "remediation"}
            else (
                "verify"
                if role == "verifier" or function.__name__ == "verify"
                else "coordinate"
                if role == "coordinator" or function.__name__ == "decide"
                else "diagnosis"
            )
        )
        metadata = {
            "stage": stage,
            **self.call_context.get(),
            "call_id": f"model-call-{self.call_sequence}",
        }
        token = self.call_context.set(metadata)
        if self.journal is not None:
            self.journal.model_activity(metadata, True)
        pending = asyncio.create_task(self.call_budget.call(function, *args, metadata=metadata))
        self.active_model_calls[pending] = role
        try:
            result = await pending
            self.stop_controller.guard()
            output, usage = result
            return output, dict(usage, stage=stage, call_id=metadata["call_id"])
        except BaseException as exc:
            for failure in self.call_budget.failures:
                if failure.get("call_id") == metadata["call_id"]:
                    self.event(
                        self.state,
                        "MODEL_FAILURE",
                        role=role,
                        source=failure.get("source", "model"),
                        **{k: v for k, v in failure.items() if k != "source"},
                        cancelled=isinstance(exc, asyncio.CancelledError)
                        or getattr(exc, "code", "") == "PROVIDER_CANCELLED"
                        or bool(getattr(exc, "cancellation_reason", None)),
                        cancellation_reason=(
                            getattr(exc, "cancellation_reason", None)
                            or ("workflow_stop" if self.stop_controller.stopped else "parent_cancelled")
                        )
                        if isinstance(exc, asyncio.CancelledError)
                        or getattr(exc, "code", "") == "PROVIDER_CANCELLED"
                        or getattr(exc, "cancellation_reason", None)
                        else None,
                    )
            raise
        finally:
            self.active_model_calls.pop(pending, None)
            self.call_context.reset(token)
            if self.journal is not None:
                self.journal.model_activity(metadata, False)

    async def stage_call(self, stage, function, *args):
        # The stable guard reads task-local stage; concurrent investigators never
        # inherit a temporary monitoring/remediation guard.
        token = self.request_stage.set(stage)
        try:
            if not hasattr(self.provider, "request_guard"):
                maximum = getattr(self.workflow, stage + "_max_calls")
                if self.stage_calls[stage] >= maximum:
                    raise BudgetExceeded(stage + " stage budget exhausted")
                self.stage_calls[stage] += 1
            if getattr(self.provider, "model_id", "") == "deterministic-public-policy-v1":
                self.consume_request()
            output, usage = await self.model_call(stage, function, *args)
            self.update_usage(self.state, usage, stage)
            return output
        finally:
            self.request_stage.reset(token)

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
            state.incident_alert = await self.retry_transient(
                state,
                "monitor-1",
                "monitoring",
                "monitoring",
                lambda: self.stage_call(
                    "monitoring",
                    monitor,
                    self.provider,
                    state.incident_id,
                    self.workflow.snapshot,
                    self.workflow.monitor_mode,
                ),
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
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="monitoring",
                **self.error_details(exc),
            )
            return {"investigation": state, "route": "stop"}

    def payload(self, state, role="coordinator", fetched=None):
        value = state.model_dump(mode="json")
        value["variant"] = self.variant
        value["acceptance_standard"] = "BEST_SUPPORTED_AVAILABLE"
        value["benchmark_rca"] = self.workflow.benchmark_rca
        from incident_lens.security.context import ROLE_TOOL_ACL

        value["workflow_profile"] = self.workflow.profile
        value["database_enabled"] = (
            self.response_profile or self.workflow.benchmark_rca
        ) and self.workflow.database_enabled
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
        from incident_lens.agents.service import FAILURE_MODES

        value["failure_mode_taxonomy"] = FAILURE_MODES
        value["candidate_assessments"] = self.candidate_assessments(state)
        remaining = max(0, self.limits.max_llm_calls - self.call_budget.calls)
        reserve = 1 + int(self.variant in {"full", "single"})
        value["investigation_budget"] = {
            "remaining_requests": remaining,
            "reserved_decision_and_review_requests": reserve,
            "minimum_requests_per_investigation": 2,
            "affordable_tasks": max(0, (remaining - reserve) // 2),
            "remaining_rounds": max(0, self.limits.max_rounds - state.round_index),
            "remaining_tool_calls": max(0, self.limits.max_tool_calls - self.registry.call_count),
        }
        rejected = next((e for e in reversed(state.events)
                         if e.event_type == "FINALIZE_REJECTED"), None)
        value["last_finalization_feedback"] = rejected.details if rejected else None
        # Keep executed query scope/results visible after stripping raw events.
        # Otherwise a narrow empty slice can masquerade as an absent source and
        # the coordinator repeatedly asks for telemetry already discovered.
        from incident_lens.orchestration.evidence_board import (
            database_coverage,
            query_history,
            shared_observations,
        )

        value["query_history"] = query_history(state)
        value["database_coverage"] = database_coverage(
            state, value["query_history"], value["role_tool_acl"])
        value["shared_observations"] = shared_observations(
            fetched or [] if role == "verifier" else state.evidence_index.values())
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

    def leading_review_ready(self, state):
        if self.variant != "full" or not state.decisions:
            return False
        decision = state.decisions[-1]
        candidate = next((h for h in state.hypotheses
                          if h.hypothesis_id == decision.proposed_hypothesis_id), None)
        return (decision.action == "ABSTAIN" and candidate is not None
                and not likely_assessment_errors(state, candidate, self.variant))

    def candidate_assessments(self, state):
        return {
            h.hypothesis_id: {
                "finalize_errors": finalize_errors(state, h, self.variant),
                "likely_errors": likely_assessment_errors(state, h, self.variant),
                "competing_hypothesis_ids": [other_id for other_id, assessment in
                                             competitor_assessments(state, h).items() if assessment["blocking"]],
                "alternative_assessments": competitor_assessments(state, h),
                "cause_discriminator_ids": [
                    eid for eid in h.support_ids if eid in state.evidence_index
                    and cause_discriminator(h, state.evidence_index[eid])
                ],
            }
            for h in state.hypotheses
        }

    @staticmethod
    def board_fingerprint(state):
        """Changes in assessment matter even when no new evidence IDs appeared."""
        value = {
            "evidence": evidence_fingerprint(state),
            "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
            "open_questions": state.open_questions,
            "requested_checks": [t.model_dump(mode="json") for t in state.requested_checks],
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def check_signature(check):
        return json.dumps([
            check.role, sorted(check.allowed_tools), check.filters,
            # Unstructured requests may differ materially despite empty filters.
            None if check.filters else [check.question, check.expected_discriminator],
        ], sort_keys=True)

    def update_usage(self, state, usage, role):
        state.llm_calls_used = self.call_budget.calls
        state.tokens_used = self.call_budget.tokens
        from incident_lens.agents.service import PROMPT_VERSION

        details = {key: value for key, value in usage.items() if key != "source"}
        details["prompt_version"] = PROMPT_VERSION
        details["model_parameters"] = getattr(
            self.provider, "model_parameters", {"temperature": self.provider.temperature}
        )
        details["stage"] = usage.get("stage") or self.call_context.get().get("stage") or (
            "verify" if role == "verifier" else "coordinate" if role == "coordinator" else "diagnosis"
        )
        # single mode also performs independent runtime stages under one identity.
        details["review_stage"] = details["stage"] == "verify"
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
        role = "single" if self.variant == "single" else "coordinator"
        # Each invocation needs a fresh task id so retries reuse it while later
        # rounds cannot collide with a completed record.
        self.coordinate_rounds += 1
        task_id = f"coordinate-{self.coordinate_rounds}"
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
                    for role in (
                        ("logs", "metrics", "database", "changes")
                        if self.workflow.benchmark_fixed_four
                        else ("logs", "metrics", "changes")
                    )
                ]
                decision = CoordinatorDecision(
                    action="INVESTIGATE", reason="Fixed schedule", assignments=tasks
                )
            elif self.variant == "fixed":
                if self.workflow.benchmark_rca:
                    payload = self.payload(state)
                    payload["fixed_schedule_completed"] = True
                    decision, usage = await self.retry_transient(
                        state,
                        task_id,
                        role,
                        "coordinate",
                        lambda: self.model_call(role, decide, self.provider, payload),
                    )
                    self.update_usage(state, usage, role)
                    if decision.action == "INVESTIGATE":
                        decision = CoordinatorDecision(
                            action="ABSTAIN", reason=decision.reason,
                            stop_reason="Fixed schedule completed with unresolved causal gaps",
                            hypothesis_updates=decision.hypothesis_updates,
                        )
                else:
                    candidates = [h for h in state.hypotheses if not finalize_errors(state, h, "fixed")]
                    decision = CoordinatorDecision(
                        action="FINALIZE" if candidates else "ABSTAIN",
                        reason="Fixed schedule completed",
                        selected_hypothesis_id=candidates[0].hypothesis_id if candidates else None,
                        stop_reason="Fixed schedule completed",
                    )
            else:
                decision, usage = await self.retry_transient(
                    state,
                    task_id,
                    role,
                    "coordinate",
                    lambda: self.model_call(role, decide, self.provider, self.payload(state)),
                )
                self.update_usage(state, usage, role)
                if decision.action == "INVESTIGATE" and len(decision.assignments) > 2:
                    raise RuntimeError("Coordinator may assign at most two tasks per round")
            if decision.action == "INVESTIGATE" and (
                self.workflow.selection_policy != "current_dynamic" or self.workflow.shadow_caes
            ):
                from incident_lens.orchestration.active_investigation.policy import apply_policy

                try:
                    decision = apply_policy(self, state, decision)
                except Exception as exc:
                    if not self.workflow.shadow_caes:
                        raise
                    # An observational failure cannot replace the original route.
                    self.stop_controller.guard()
                    if self.exhausted(state):
                        raise
                    self.event(
                        state,
                        "ACTION_POLICY_FALLBACK",
                        shadow=True,
                        reason=type(exc).__name__,
                        executed_original_proposal=True,
                    )
            state.decisions.append(decision)
            self.event(
                state,
                "DECISION",
                role="single" if self.variant == "single" else "coordinator",
                message=decision.reason,
                decision=decision.model_dump(mode="json"),
            )
            changed = False
            updates = {h.hypothesis_id: h for h in decision.hypothesis_updates}
            for index, hypothesis in enumerate(state.hypotheses):
                update = updates.get(hypothesis.hypothesis_id)
                if update is not None and update.model_dump() != hypothesis.model_dump():
                    state.hypotheses[index] = update
                    changed = True
            if changed:
                # Gate errors are separate from real shared causal questions.
                self.event(state, "HYPOTHESIS_RECONCILED",
                           hypothesis_updates=[h.model_dump(mode="json") for h in updates.values()])
            if decision.action == "ABSTAIN":
                state.stop_reason = decision.stop_reason
                self.event(state, "ABSTENTION_ASSESSMENT", role=role,
                           candidate_assessments=self.candidate_assessments(state),
                           shared_open_questions=list(state.open_questions),
                           reason=decision.stop_reason)
                candidate = next((h for h in state.hypotheses
                                  if h.hypothesis_id == decision.proposed_hypothesis_id), None)
                if self.variant == "full" and candidate is not None:
                    errors = likely_assessment_errors(state, candidate, self.variant)
                    review_errors = {
                        "Independent review has not endorsed a leading explanation",
                        "Leading review does not match the current candidate/evidence snapshot",
                    }
                    if (errors and set(errors).issubset(review_errors)
                        and self.call_budget.calls < self.limits.max_llm_calls
                        and self.registry.call_count < self.limits.max_tool_calls):
                        self.event(state, "LEADING_REVIEW_REQUESTED",
                                   proposed_hypothesis_id=candidate.hypothesis_id)
                        return {"investigation": state, "route": "verify"}
                return {"investigation": state, "route": "report"}
            if decision.action == "FINALIZE":
                if changed and self.variant == "full":
                    # Reconciliation cannot reuse acceptance of an older board.
                    return {"investigation": state, "route": "verify"}
                return {"investigation": state, "route": "finalize"}
            known_change = any(
                r.metadata.get("change_id") for r in state.evidence_index.values()
            )
            # A known change can still have an unread diff outside an empty
            # query slice. Single mode also permits its full context tool ACL,
            # so task.allowed_tools cannot bound its next effective query.
            completed_repeat = self.variant != "single" and bool(decision.assignments) and all(
                not (known_change and "get_config_diff" in t.allowed_tools)
                and self.completed_scopes.get(self.structured_scope(t)) == evidence_fingerprint(state)
                for t in decision.assignments
            )
            if completed_repeat and not self.exhausted(state):
                state.stop_reason = "INCONCLUSIVE"
                self.event(state, "INVESTIGATION_NO_PROGRESS",
                           reason="Completed empty changes scope without new evidence")
                return {"investigation": state, "route": "report"}
            if state.round_index >= self.limits.max_rounds:
                raise RuntimeError("Round budget exhausted")
            if self.registry.call_count >= self.limits.max_tool_calls:
                raise RuntimeError("Tool budget exhausted")
            remaining = self.limits.max_llm_calls - self.call_budget.calls
            reserve = 1 + int(self.variant in {"full", "single"})
            affordable = max(0, (remaining - reserve) // 2)
            if self.variant != "fixed" and len(decision.assignments) > affordable:
                if not affordable:
                    raise RuntimeError("LLM call budget cannot fund investigation and final decision")
                deferred = decision.assignments[affordable:]
                decision.assignments = decision.assignments[:affordable]
                self.event(state, "INVESTIGATION_BUDGET_RESERVED", reserved_requests=reserve,
                           deferred_task_ids=[t.task_id for t in deferred],
                           executed_task_ids=[t.task_id for t in decision.assignments])
            signature = json.dumps(
                [(t.role, t.allowed_tools, t.filters, t.expected_discriminator)
                 for t in decision.assignments], sort_keys=True
            )
            # Repeated task against an unchanged board is a loop, not progress.
            signature += self.board_fingerprint(state)
            if signature in self.signatures:
                state.stop_reason = "INCONCLUSIVE"
                self.event(state, "INVESTIGATION_NO_PROGRESS", reason="Repeated check without new evidence")
                return {"investigation": state, "route": "report"}
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
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="coordinate",
                **self.error_details(exc),
            )
            return {"investigation": state, "route": "report"}

    @staticmethod
    def structured_scope(task):
        # Empty filters leave the requested scope entirely in prose; never infer
        # equivalence there. Tool permissions are part of the requested check.
        if (
            not task.filters
            or not set(task.allowed_tools).issubset({"query_changes", "get_config_diff"})
            or "query_changes" not in task.allowed_tools
        ):
            return None
        return json.dumps(
            [task.role, sorted(task.allowed_tools), task.filters], sort_keys=True
        )

    @staticmethod
    def safe_error(exc):
        # Provider errors must be sanitized at adapter boundary. Unknown exceptions
        # expose their type only; no request payload, credentials or stack traces.
        from incident_lens.llm.provider import ProviderError

        if isinstance(exc, ProviderError) and exc.code in {
            "PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_ERROR", "PROVIDER_HTTP_ERROR",
            "STRUCTURED_OUTPUT_COMPATIBILITY_ERROR", "STRUCTURED_OUTPUT_INVALID",
            "REQUEST_BUDGET_EXCEEDED",
        }:
            return exc.code
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
        from incident_lens.agents.service import AnalysisOutput, ToolCall, analyze, plan_tools
        from incident_lens.schemas import Finding

        context = self.single_context or self.registry.create_context(task.role)
        role = "single" if self.variant == "single" else task.role
        minimal = {
            "benchmark_discovery": self.workflow.benchmark_rca,
            "changes_discovery_done": self.changes_discovery_done,
            "query_history": self.payload(state)["query_history"],
            "database_coverage": self.payload(state)["database_coverage"],
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
        if self.workflow.benchmark_rca and any(
            call.tool_name == "query_changes" for call in plan.calls
        ):
            # The first changes discovery (whole pack, filters stripped) is done;
            # every later query_changes must keep its proposed window.
            self.changes_discovery_done = True
        records = []
        gaps = []
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
            if not result.ok and result.error_code != "NOT_FOUND":
                raise RuntimeError("Tool failed: " + str(result.error_code))
            if not result.records:
                gap = dict(
                    call_id=result.call_id,
                    tool_name=call.tool_name,
                    args=call.args,
                    outcome="QUERY_NOT_FOUND" if not result.ok else "NO_DATA",
                )
                gaps.append(gap)
                self.event(state, "TOOL_DATA_GAP", role=role, task_id=task.task_id, **gap)
            records.extend(result.records)
            # Discovery and diff retrieval form one bounded changes investigation.
            # Use only a returned public change_id and a spare slot in the existing
            # two-call plan; execute via the registry so ACL/budget/events still apply.
            if (
                self.workflow.benchmark_rca
                and call.tool_name == "query_changes"
                and len(plan.calls) < 2
                and "get_config_diff" in context.allowed_tools
                and "get_config_diff" in task.allowed_tools
            ):
                change = next(
                    (r for r in result.records if r.metadata.get("change_id")), None
                )
                if change is not None:
                    plan.calls.append(ToolCall(
                        tool_name="get_config_diff",
                        args={"change_id": change.metadata["change_id"]},
                    ))
        unique = {r.evidence_id: r for r in records}
        if not unique:
            analysis = AnalysisOutput(
                finding=Finding(
                    finding_id="gap-" + hashlib.sha256(task.task_id.encode()).hexdigest(),
                    task_id=task.task_id,
                    run_id=state.run_id,
                    incident_id=state.incident_id,
                    role=task.role,
                    claim="No evidence for this query; this is not proof of healthy behavior. "
                    + json.dumps(gaps, ensure_ascii=False),
                    evidence_ids=[],
                    relation="neutral",
                    confidence_qualifier="unknown",
                    followup_question="Choose an available service, window or evidence source.",
                ),
                hypotheses=[],
            )
            return context, task, analysis
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
        if gaps:
            # A query miss is an observation, never additional causal support.
            analysis.finding.claim += " Data gaps (not evidence of health): " + json.dumps(gaps)
        return context, task, analysis

    async def dispatch(self, value):
        state = value["investigation"]
        self.state = state
        try:
            # Concurrent read-only investigators; state publication happens only
            # after all local outputs return. Provider/usage calls are observable.
            tasks = state.decisions[-1].assignments
            if self.variant == "single":
                outcomes = []
                for task in tasks:
                    try:
                        outcomes.append(await self.execute_task(state, task))
                    except Exception as exc:
                        outcomes.append(exc)
            else:
                pending = [asyncio.create_task(self.execute_task(state, t)) for t in tasks]
                self.active_workers.update({t.task_id: p for t, p in zip(tasks, pending)})
                try:
                    outcomes = await asyncio.gather(*pending, return_exceptions=True)
                except BaseException:
                    for worker in pending:
                        if not worker.done():
                            worker.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise
                finally:
                    self.active_workers.clear()
            results = [r for r in outcomes if not isinstance(r, BaseException)]
            failures = [r for r in outcomes if isinstance(r, BaseException)]
            fatal = [
                f for f in failures
                if not isinstance(f, asyncio.CancelledError) and not self.recoverable_task_error(f)
            ]
            if failures and all(isinstance(f, asyncio.CancelledError) for f in failures) and (
                not results or not self.workflow.continue_on_partial_failure
            ):
                state.stop_reason = "INCONCLUSIVE"
                self.event(state, "BATCH_CANCELLED", task_ids=[t.task_id for t in tasks])
                state.tool_calls_used = self.registry.call_count
                return {"investigation": state, "route": "report", "local_results": []}
            if fatal or (failures and (not results or not self.workflow.continue_on_partial_failure)):
                raise (fatal or failures)[0]
            if failures:
                self.event(state, "BATCH_PARTIAL_FAILURE", failed_tasks=[
                    t.task_id for t, outcome in zip(tasks, outcomes)
                    if isinstance(outcome, BaseException)
                ])
            state.tool_calls_used = self.registry.call_count
            return {"investigation": state, "local_results": results, "route": "merge"}
        except Exception as exc:
            state.tool_calls_used = self.registry.call_count
            state.stop_reason = self.safe_error(exc)
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="dispatch",
                **self.error_details(exc),
            )
            return {"investigation": state, "route": "report", "local_results": []}

    async def execute_task(self, state, task):
        while True:
            self.stop_controller.guard()
            attempt = self.task_manager.start(task.task_id)
            token = self.call_context.set(
                {"task_id": task.task_id, "attempt_id": attempt.attempt_id, "stage": "diagnosis"}
            )
            try:
                result = await self.investigate(state, task)
                self.stop_controller.guard()
                completed = self.task_manager.complete(task.task_id)
                self.record_recovery(completed, "diagnosis")
                return result
            except asyncio.CancelledError:
                self.task_manager.cancel(task.task_id)
                raise
            except Exception as exc:
                if self.stop_controller.stopped or getattr(exc, "code", "") == "PROVIDER_CANCELLED":
                    self.task_manager.cancel(task.task_id)
                    if not self.stop_controller.stopped:
                        cancellation = asyncio.CancelledError()
                        cancellation.usage = getattr(exc, "usage", None)
                        raise cancellation from None
                    raise
                self.task_manager.fail(task.task_id, self.safe_error(exc))
                if (
                    not self.recoverable_task_error(exc)
                    or not self.task_manager.can_retry(task.task_id)
                    or self.exhausted(state)
                    or not await self.wait_for_retry(state, exc, task.task_id, "diagnosis")
                ):
                    raise
                self.task_manager.assign(task.task_id, task.role)
            finally:
                self.call_context.reset(token)

    @staticmethod
    def recoverable_task_error(exc):
        """Retry bounded provider faults, never authority/protocol/source violations."""
        from incident_lens.llm.provider import ProviderError

        if isinstance(exc, ProviderError):
            if getattr(exc, "failure", None) is not None:
                if exc.usage.get("provider_recovery_enabled"):
                    return False
                return exc.failure.retryable
            return exc.code in {
                "PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_ERROR", "PROVIDER_HTTP_ERROR",
                "STRUCTURED_OUTPUT_INVALID",
            }
        return False

    def record_recovery(self, record, stage):
        call_ids = [
            e.details["call_id"]
            for e in self.state.events
            if e.event_type == "MODEL_FAILURE"
            and e.details.get("task_id") == record.task_id
            and not e.details.get("cancelled")
        ]
        if call_ids:
            self.event(
                self.state,
                "MODEL_RECOVERED",
                stage=stage,
                task_id=record.task_id,
                attempt_id=record.attempt_id,
                call_ids=call_ids,
            )

    @classmethod
    def error_details(cls, exc):
        from incident_lens.llm.provider import ProviderError

        code = getattr(exc, "code", "") or (
            "PROVIDER_TIMEOUT" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else ""
        )
        transport = isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or (
            isinstance(exc, ProviderError)
            and getattr(exc, "code", "") in {"PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_ERROR"}
        )
        details = {"error_code": code, "transport_error": transport}
        if getattr(exc, "failure", None) is not None:
            details["provider_failure"] = exc.failure.model_dump(mode="json")
        return details

    @classmethod
    def stage_retryable_error(cls, exc):
        """Restrict a stage re-issue to transport-class transients on top of the
        shared recoverability rule. The adapter already bounds structured repair and
        HTTP status handling internally, so re-driving those would double-count
        requests; authority/protocol/source violations stay fatal either way.
        """
        from incident_lens.llm.provider import ProviderError

        return cls.recoverable_task_error(exc) and isinstance(exc, ProviderError) and (
            getattr(exc, "failure", None) is not None
            or exc.code in {"PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_ERROR"}
        )

    async def wait_for_retry(self, state, exc, task_id, stage):
        """Back off transient task retries within the original attempt/wall budgets."""
        from incident_lens.llm.transport_retry import compute_backoff
        from incident_lens.orchestration.recovery import RecoveryConfig

        failure = getattr(exc, "failure", None)
        if failure is None or not failure.retryable:
            return True  # Preserve legacy bounded structured-output repair behavior.
        delegate = getattr(self.provider, "delegate", self.provider)
        config = getattr(delegate, "recovery", RecoveryConfig())
        attempts = [r for r in self.task_manager.records if r.task_id == task_id]
        delay = compute_backoff(max(0, len(attempts) - 1), failure.retry_after_seconds,
                                config, getattr(delegate, "rng", None))
        if delay + config.min_request_time_seconds + config.safety_margin_seconds > self.call_budget.remaining_seconds():
            self.event(state, "TASK_RETRY_DENIED", task_id=task_id, stage=stage,
                       reason="insufficient_remaining_wall_budget", delay_seconds=delay)
            return False
        self.event(state, "TASK_RETRY_SCHEDULED", task_id=task_id, stage=stage,
                   delay_seconds=delay, provider_failure=failure.model_dump(mode="json"))
        await asyncio.sleep(delay)
        self.stop_controller.guard()
        return not self.exhausted(state)

    async def retry_transient(self, state, task_id, role, stage, operation):
        """Bounded per-attempt retry shared by non-diagnosis stages.

        Mirrors the diagnosis/verify contract: only transient transport faults are
        retried, while protocol violations, cancellation, STOP and budget exhaustion
        fail closed. Binds self.state so runtime task events target this state.
        """
        self.state = state
        self.task_manager.assign(task_id, role)
        attempt = self.task_manager.start(task_id)
        while True:
            self.stop_controller.guard()
            token = self.call_context.set(
                {"task_id": task_id, "attempt_id": attempt.attempt_id, "stage": stage}
            )
            try:
                result = await operation()
            except asyncio.CancelledError:
                self.task_manager.cancel(task_id)
                raise
            except Exception as exc:
                if self.stop_controller.stopped or getattr(exc, "code", "") == "PROVIDER_CANCELLED":
                    self.task_manager.cancel(task_id)
                    raise
                self.task_manager.fail(task_id, self.safe_error(exc))
                if (
                    not self.stage_retryable_error(exc)
                    or not self.task_manager.can_retry(task_id)
                    or self.exhausted(state)
                    or not await self.wait_for_retry(state, exc, task_id, stage)
                ):
                    raise
                self.task_manager.assign(task_id, role)
                attempt = self.task_manager.start(task_id)
            else:
                completed = self.task_manager.complete(task_id)
                self.record_recovery(completed, stage)
                return result
            finally:
                self.call_context.reset(token)

    def merge(self, value):
        state = value["investigation"]
        try:
            self.stop_controller.guard()
            previous_ids = set(state.evidence_index)
            prior_review = next((e for e in reversed(state.events) if e.event_type == "REVIEW"), None)
            state = merge_results(state, value["local_results"], self.registry)
            if prior_review:
                new_ids = set(state.evidence_index) - previous_ids
                for check in prior_review.details.get("review", {}).get("requested_checks", []):
                    matched = []
                    for _, task, _ in value["local_results"]:
                        calls = [e.details for e in state.events if e.event_type == "TOOL_CALL"
                                 and e.task_id == task.task_id]
                        if (task.role == check["role"]
                                and (task.task_id == check["task_id"] or check.get("filters"))
                                and any(
                            c.get("tool_name") in check.get("allowed_tools", [])
                            and c.get("result", {}).get("ok") is True
                            and all(c.get("args", {}).get(k) == v
                                    for k, v in check.get("filters", {}).items())
                            for c in calls
                        )):
                            matched.append(task.task_id)
                    if matched:
                        matched_ids = {r["evidence_id"] for e in state.events
                                       if e.event_type == "TOOL_CALL" and e.task_id in matched
                                       for r in e.details.get("result", {}).get("records", [])}
                        self.event(state, "REVIEW_FOLLOWUP", review_event_id=prior_review.event_id,
                                   requested_task_id=check["task_id"], completed_task_ids=matched,
                                   new_evidence_ids=sorted(new_ids & matched_ids))
            for _, task, _ in value["local_results"]:
                scope = self.structured_scope(task)
                calls = [e.details for e in state.events
                         if e.event_type == "TOOL_CALL" and e.task_id == task.task_id]
                # Only exact, empty changes scopes can be safely compared without
                # prose: metric/log questions may select different effective calls.
                # Publication and successful, exhausted effective queries are both
                # required. Failed analysis, failed tools and partial pages cannot
                # turn a later retry into a normal abstention.
                if scope is not None and calls and all(
                    c.get("tool_name") == "query_changes"
                    and c.get("args") == task.filters
                    and c.get("result", {}).get("ok")
                    and not c.get("result", {}).get("records")
                    and c.get("result", {}).get("next_cursor") is None
                    for c in calls
                ):
                    self.completed_scopes[scope] = evidence_fingerprint(state)
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
                **self.error_details(exc),
            )
            return {"investigation": state, "route": "report"}

    async def verify(self, value):
        from incident_lens.agents.service import verify

        state = value["investigation"]
        # Runtime events (task transitions) are emitted against self.state, so
        # every node must bind it to its own investigation state first.
        self.state = state
        role = "single" if self.variant == "single" else "verifier"
        try:
            if not state.hypotheses:
                self.event(state, "REVIEW_SKIPPED", role=role, reason="no_candidate_to_review")
                return {"investigation": state, "route": "coordinate"}
            signature = self.board_fingerprint(state)
            selected = state.decisions[-1].selected_hypothesis_id if state.decisions else None
            if (signature == getattr(self, "last_review_signature", None) and state.reviews
                    and (selected is None or selected == state.reviews[-1].target_hypothesis_id)):
                self.event(state, "REVIEW_REUSED", role=role, board_sha256=signature,
                           reason="unchanged_evidence_and_assessment")
                return {"investigation": state,
                        "route": "report" if self.leading_review_ready(state) else
                                 "finalize" if reviewed_finalization_ready(state, self.variant) else "coordinate"}
            before = self.candidate_assessments(state)
            prior_checks = {
                self.check_signature(check)
                for old in state.reviews for check in old.requested_checks
            }
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
                role=role,
                tool_name="fetch_evidence_by_ids",
                result=result.model_dump(mode="json"),
            )
            if not result.ok:
                raise RuntimeError("Verifier tool failed: " + str(result.error_code))
            # The review gets the same bounded transient-fault retry as a diagnosis
            # task: one verify-stage timeout must not terminate an otherwise
            # complete investigation, while protocol violations still fail closed.
            self.verify_rounds += 1
            task_id = f"verify-{self.verify_rounds}"
            self.task_manager.assign(task_id, role)
            attempt = self.task_manager.start(task_id)
            while True:
                self.stop_controller.guard()
                token = self.call_context.set(
                    {
                        "task_id": task_id,
                        "attempt_id": attempt.attempt_id,
                        "stage": "verify",
                    }
                )
                try:
                    review, usage = await self.model_call(
                        role, verify, self.provider, self.payload(state, "verifier", result.records)
                    )
                    citation_validation = usage.get("review_citation_validation")
                    if citation_validation:
                        self.event(state, "REVIEW_CITATION_VALIDATION", role=role,
                                   **citation_validation, repaired=True)
                    invalid_ids = sorted(set(review.cited_evidence_ids) -
                                         {record.evidence_id for record in result.records})
                    if invalid_ids:
                        from incident_lens.llm.provider import ProviderError

                        # Defense in depth for providers that bypass the supplied
                        # output model. Never accept or silently trim this review.
                        self.update_usage(state, usage, role)
                        self.event(state, "REVIEW_CITATION_VALIDATION", role=role,
                                   allowed_evidence_ids=sorted(r.evidence_id for r in result.records),
                                   invalid_citation_attempts=[invalid_ids], repaired=False)
                        raise ProviderError("REVIEW_CITATION_INVALID")
                except asyncio.CancelledError:
                    self.task_manager.cancel(task_id)
                    raise
                except Exception as exc:
                    citation_validation = getattr(exc, "review_citation_validation", None)
                    if citation_validation:
                        self.event(state, "REVIEW_CITATION_VALIDATION", role=role,
                                   **citation_validation, repaired=False)
                    if self.stop_controller.stopped or getattr(exc, "code", "") == "PROVIDER_CANCELLED":
                        self.task_manager.cancel(task_id)
                        raise
                    self.task_manager.fail(task_id, self.safe_error(exc))
                    if (
                        not self.recoverable_task_error(exc)
                        or not self.task_manager.can_retry(task_id)
                        or self.exhausted(state)
                        or not await self.wait_for_retry(state, exc, task_id, "verify")
                    ):
                        raise
                    self.task_manager.assign(task_id, role)
                    attempt = self.task_manager.start(task_id)
                else:
                    completed = self.task_manager.complete(task_id)
                    self.record_recovery(completed, "verify")
                    break
                finally:
                    self.call_context.reset(token)
            self.update_usage(state, usage, role)
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
            review_event_id = state.events[-1].event_id
            after = self.candidate_assessments(state)
            target = review.target_hypothesis_id
            before_errors = before.get(target, {}).get("finalize_errors", [])
            after_errors = after.get(target, {}).get("finalize_errors", [])
            self.event(
                state, "REVIEW_EFFECT", role=role, review_event_id=review_event_id,
                target_hypothesis_id=target, board_sha256=signature,
                gate_errors_before=before_errors, gate_errors_after=after_errors,
                gate_discharged=bool(before_errors) and not after_errors,
                added_blockers=bool(set(after_errors) - set(before_errors)),
                repeated_requested_checks=sum(self.check_signature(c) in prior_checks
                                              for c in review.requested_checks),
                contradictions=list(review.contradictions),
                blocking_check_count=len(review.requested_checks),
                optional_check_count=len(review.optional_checks),
                benefit_assessment="pending_manual_or_paired_evaluation",
            )
            self.last_review_signature = self.board_fingerprint(state)
            state.tool_calls_used = self.registry.call_count
            if self.leading_review_ready(state):
                self.event(state, "LEADING_REVIEW_COMPLETED",
                           proposed_hypothesis_id=state.decisions[-1].proposed_hypothesis_id)
                return {"investigation": state, "route": "report"}
            if reviewed_finalization_ready(state, self.variant):
                self.stop_controller.guard()
                self.event(
                    state, "FINALIZE_RESUMED_AFTER_REVIEW",
                    selected_hypothesis_id=state.decisions[-1].selected_hypothesis_id,
                    review_event_id=review_event_id,
                    decision_index=len(state.decisions) - 1,
                )
                return {"investigation": state, "route": "finalize"}
            return {"investigation": state, "route": "coordinate"}
        except Exception as exc:
            state.stop_reason = self.safe_error(exc)
            self.event(
                state,
                "RUNTIME_ERROR",
                message=state.stop_reason,
                stage="verify",
                error_type=type(exc).__name__,
                **self.error_details(exc),
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
            # Gate diagnostics are feedback, never new causal evidence/questions.
            self.event(state, "FINALIZE_REJECTED", errors=errors,
                       selected_hypothesis_id=selected,
                       candidate_assessments=self.candidate_assessments(state))
            attempt = (selected, self.board_fingerprint(state), tuple(errors))
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
                causal_chain=observed_chain(state, supported),
                supporting_evidence_ids=supported.support_ids,
                rejected_hypotheses=[h for h in state.hypotheses if h.status == "REJECTED"],
                stop_reason=state.decisions[-1].stop_reason or "Evidence sufficient",
            )
            failed_tasks = {r.task_id for r in self.task_manager.records if r.status == "FAILED"}
            self.event(
                state,
                "DIAGNOSIS_ACCEPTED",
                root_cause=supported.model_dump(mode="json"),
                supporting_evidence_ids=supported.support_ids,
                degraded_call_ids=[
                    e.details["call_id"]
                    for e in state.events
                    if e.event_type == "MODEL_FAILURE"
                    and e.details.get("task_id") in failed_tasks
                    and e.details.get("stage") == "diagnosis"
                    and not e.details.get("cancelled")
                ],
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
                attempt = self.task_manager.start(task_id)
                token = self.call_context.set(
                    {"task_id": task_id, "attempt_id": attempt.attempt_id, "stage": "remediation"}
                )
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
                    completed = self.task_manager.complete(task_id)
                    self.record_recovery(completed, "remediation")
                    self.event(
                        state,
                        "REMEDIATION_PLAN",
                        role="remediation",
                        plan=plan.model_dump(mode="json"),
                    )
                    break
                except Exception as exc:
                    if self.stop_controller.stopped:
                        raise
                    self.task_manager.fail(task_id, self.safe_error(exc))
                    if not self.task_manager.can_retry(task_id) or self.exhausted(state):
                        raise
                    self.task_manager.assign(task_id, "remediation")
                finally:
                    self.call_context.reset(token)
        except Exception as exc:
            if self.stop_controller.stopped:
                return {"investigation": state, "route": "stop"}
            report.remediation_status = "PLAN_FAILED"
            self.remediation_error = self.safe_error(exc)
            if isinstance(exc, TimeoutError) or getattr(exc, "code", None) in {
                "PROVIDER_TIMEOUT",
                "PROVIDER_TRANSPORT_ERROR",
                "PROVIDER_HTTP_ERROR",
                "PROVIDER_CONFIGURATION_REQUIRED",
                "PROVIDER_CANCELLED",
            }:
                state.stop_reason = self.remediation_error
                self.event(
                    state,
                    "RUNTIME_ERROR",
                    stage="remediation",
                    message=self.remediation_error,
                    **self.error_details(exc),
                )
            self.event(
                state, "REMEDIATION_FAILED", role="remediation", message=self.safe_error(exc)
            )
        return {"investigation": state, "route": "stop"}

    async def stop(self, value):
        state = value["investigation"]
        self.state = state
        if state.termination is not None:
            return {"investigation": state, "route": "report"}
        state.workflow_status = "STOPPING"
        if state.report is not None:
            state.report.workflow_status = "STOPPING"
        reason = state.stop_reason or "INCONCLUSIVE"
        errors = [e for e in state.events if e.event_type == "RUNTIME_ERROR"]
        stage = errors[-1].details.get("stage", "runtime") if errors else "runtime"
        if errors:
            reason = "BUDGET_EXHAUSTED" if "budget" in reason.lower() else "UNRECOVERABLE_ERROR"
        elif state.report is not None and state.report.remediation_status == "PLAN_READY":
            reason = "PLAN_READY"
        elif state.report is not None and state.report.remediation_status == "PLAN_FAILED":
            reason = (
                "BUDGET_EXHAUSTED"
                if (
                    self.exhausted(state)
                    or "budget" in getattr(self, "remediation_error", "").lower()
                )
                else "PLAN_FAILED"
            )
            stage = "remediation"
        elif state.report is not None and state.report.status == "RESOLVED":
            reason = "DIAGNOSIS_READY"
        elif "budget" in reason.lower():
            reason = "BUDGET_EXHAUSTED"
        elif reason != "NO_ALERT":
            normal_abstention = state.decisions and state.decisions[-1].action == "ABSTAIN"
            rejected_finalization = any(
                e.event_type == "FINALIZE_REJECTED" for e in state.events
            ) and not any(e.event_type == "RUNTIME_ERROR" for e in state.events)
            reason = (
                "INCONCLUSIVE"
                if (
                    normal_abstention
                    or rejected_finalization
                    or reason
                    in ("INCONCLUSIVE", "Missing discriminating evidence", "Insufficient evidence")
                )
                else "UNRECOVERABLE_ERROR"
            )
            if reason == "INCONCLUSIVE" and self.call_budget.failures:
                from incident_lens.evaluation.termination import recovered_call_ids

                recovered = recovered_call_ids([e.model_dump(mode="json") for e in state.events])
                if any(
                    f.get("call_id") not in recovered
                    and f.get("error_code") not in {"CancelledError", "PROVIDER_CANCELLED"}
                    for f in self.call_budget.failures
                ):
                    reason = "UNRECOVERABLE_ERROR"
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
        # Assigned tasks without a running worker also need a terminal cancellation record.
        for record in self.task_manager.records:
            if (
                record.status in {"ASSIGNED", "RUNNING"}
                and record.task_id not in self.active_workers
            ):
                self.task_manager.cancel(record.task_id)
        await self.stop_controller.stop(reason, callbacks)
        if not self.stop_controller.completed:
            reason, stage = "STOP_TIMEOUT", "stop"
        state.task_records = list(self.task_manager.records)
        state.termination = termination_result(
            reason, failure_stage=stage, stop_completed=self.stop_controller.completed
        )
        state.workflow_status = "FAILED" if state.termination.outcome == "FAILED" else "FINISHED"
        if state.report:
            state.report.workflow_status = state.workflow_status
            state.report.diagnosis_status = (
                "RESOLVED" if state.report.status == "RESOLVED" else "INCONCLUSIVE"
            )
            state.report.termination = state.termination.model_copy(deep=True)
        self.event(
            state,
            "RUNTIME_FAILURE" if state.termination.runtime_failure else "NORMAL_TERMINATION",
            **state.termination.model_dump(mode="json"),
        )
        return {"investigation": state, "route": "report"}

    def rescue_report(self, state):
        runtime_errors = [e for e in state.events if e.event_type == "RUNTIME_ERROR"]
        if not runtime_errors or not all(
            e.details.get("transport_error") is True for e in runtime_errors
        ):
            return None
        if not state.decisions or state.decisions[-1].action == "ABSTAIN":
            return None
        stop_reason = state.stop_reason or ""
        if "budget" in stop_reason.lower() or stop_reason == "BUDGET_EXHAUSTED":
            return None
        candidates = [
            h for h in state.hypotheses if finalize_errors(state, h, self.variant) == []
        ]
        if len(candidates) != 1:
            return None
        hypothesis = candidates[0]
        review = next(
            (
                e
                for e in reversed(state.events)
                if e.event_type == "REVIEW"
                and e.details.get("review", {}).get("target_hypothesis_id")
                == hypothesis.hypothesis_id
                and e.details.get("review", {}).get("verdict") == "sufficient"
            ),
            None,
        )
        if review is None:
            return None
        supported = hypothesis.model_copy(update={"status": "SUPPORTED"})
        report = RCAReport(
            run_id=state.run_id,
            incident_id=state.incident_id,
            status="RESOLVED",
            root_cause=supported,
            causal_chain=observed_chain(state, supported),
            supporting_evidence_ids=supported.support_ids,
            rejected_hypotheses=[h for h in state.hypotheses if h.status == "REJECTED"],
            stop_reason=state.decisions[-1].stop_reason or "Evidence sufficient",
        )
        report.workflow_status = state.workflow_status
        report.diagnosis_status = "RESOLVED"
        if state.termination is not None:
            report.termination = state.termination.model_copy(deep=True)
        failed_tasks = {r.task_id for r in self.task_manager.records if r.status == "FAILED"}
        self.event(
            state,
            "DIAGNOSIS_ACCEPTED",
            root_cause=supported.model_dump(mode="json"),
            supporting_evidence_ids=supported.support_ids,
            rescued=True,
            rescue_review_event_id=review.event_id,
            degraded_call_ids=[
                e.details["call_id"]
                for e in state.events
                if e.event_type == "MODEL_FAILURE"
                and e.details.get("task_id") in failed_tasks
                and e.details.get("stage") == "diagnosis"
                and not e.details.get("cancelled")
            ],
        )
        return report

    def report(self, value):
        state = value["investigation"]
        if state.report is None:
            state.report = self.rescue_report(state)
        if state.report is None:
            rejected = next((e for e in reversed(state.events)
                             if e.event_type == "FINALIZE_REJECTED"), None)
            state.report = RCAReport(
                run_id=state.run_id,
                incident_id=state.incident_id,
                status="INCONCLUSIVE",
                unresolved=state.open_questions or (
                    rejected.details.get("errors") if rejected else None
                ) or ["Need additional discriminating evidence"],
                rejected_hypotheses=[h for h in state.hypotheses if h.status == "REJECTED"],
                stop_reason=state.stop_reason or "Insufficient evidence",
                diagnosis_status="INCONCLUSIVE" if self.response_profile else None,
                remediation_status="SKIPPED" if self.response_profile else "NOT_STARTED",
                workflow_status=state.workflow_status,
                termination=state.termination,
            )
        populate_assessment(state, self.variant)
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
            # Graph supersteps are not investigation rounds: merge/review/stop
            # need headroom even when a long-run round budget is increased.
            config={"recursion_limit": max(40, 12 * self.state.budgets.max_rounds + 20)},
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
    journal=None,
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
        journal,
    )
    return await run.run()
