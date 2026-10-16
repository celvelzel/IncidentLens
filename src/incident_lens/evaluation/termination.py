"""Read-only normalization of terminal protocols; never rewrite saved events."""

import json

from pydantic import ValidationError

from incident_lens.schemas.workflow import TerminationResult, termination_result

SCORING_VERSION = "2"
REQUEST = "WORKFLOW_STOP_REQUESTED"
TERMINALS = {"NORMAL_TERMINATION", "RUNTIME_FAILURE"}
FROZEN_MUTATIONS = {
    "TASK_ASSIGNED",
    "TASK_RUNNING",
    "TASK_COMPLETED",
    "MERGE",
    "REMEDIATION_PLAN",
    "TOOL_CALL",
    "LLM_CALL",
    "DECISION",
    "REVIEW",
    "DIAGNOSIS_ACCEPTED",
    "MODEL_RECOVERED",
    "TOOL_DATA_GAP",
    "BATCH_PARTIAL_FAILURE",
    "BATCH_CANCELLED",
    "INVESTIGATION_NO_PROGRESS",
    "STAGE_COMPLETED",
    "FINALIZE_RESUMED_AFTER_REVIEW",
}


def details(event):
    value = event.get("details")
    return value if isinstance(value, dict) else {}


def acceptance_matches(event, report, events):
    """A rescued acceptance also requires its checkpoint review to target the root cause."""
    if event.get("event_type") != "DIAGNOSIS_ACCEPTED":
        return False
    if (
        details(event).get("root_cause") != report.get("root_cause")
        or details(event).get("supporting_evidence_ids") != report.get("supporting_evidence_ids")
    ):
        return False
    if not details(event).get("rescued"):
        return True
    checkpoint = details(event).get("rescue_review_event_id")
    root_cause_id = (report.get("root_cause") or {}).get("hypothesis_id")
    return any(
        e.get("event_type") == "REVIEW"
        and e.get("event_id") == checkpoint
        and details(e).get("review", {}).get("target_hypothesis_id") == root_cause_id
        for e in events
    )


def accepted_diagnosis(state):
    report = state.get("report") or {}
    return (
        any(
            acceptance_matches(e, report, state.get("events", []))
            for e in state.get("events", [])
        )
        and report.get("status") == "RESOLVED"
        and report.get("root_cause") is not None
    )


def recovered_call_ids(events):
    """Recovery requires explicit matching calls, not an unrelated later success."""
    recovered = set()
    for position, event in enumerate(events):
        if event.get("event_type") != "MODEL_RECOVERED":
            continue
        data = details(event)
        task_id = data.get("task_id")
        if not task_id and not any(
            e.get("event_type") == "STAGE_COMPLETED"
            and details(e).get("stage") == data.get("stage")
            for e in events[:position]
        ):
            continue
        if task_id and not any(
            e.get("event_type") == "TASK_COMPLETED"
            and details(e).get("task_id") == task_id
            and details(e).get("attempt_id") == data.get("attempt_id")
            for e in events[:position]
        ):
            continue
        for call_id in data.get("call_ids", []):
            if any(
                e.get("event_type") == "MODEL_FAILURE"
                and details(e).get("call_id") == call_id
                and details(e).get("stage") == data.get("stage")
                and (not task_id or details(e).get("task_id") == task_id)
                for e in events[:position]
            ):
                recovered.add(call_id)
    return recovered


def _semantic_errors(state, result, new):
    report = state.get("report") or {}
    errors = []
    reason = result.reason
    resolved = report.get("status") == "RESOLVED" and bool(report.get("root_cause"))
    if reason in {"PLAN_READY", "DIAGNOSIS_READY", "PLAN_FAILED"} and not resolved:
        errors.append("terminal reason requires resolved diagnosis")
    if reason == "PLAN_READY" or report.get("remediation_status") == "PLAN_READY":
        if report.get("remediation_status") != "PLAN_READY" or not report.get("remediation_plan"):
            errors.append("PLAN_READY requires a plan")
        else:
            from incident_lens.agents.remediation import validate_plan
            from incident_lens.schemas import EvidenceRecord, RCAReport

            try:
                parsed = RCAReport.model_validate(report)
                index = {
                    key: EvidenceRecord.model_validate_json(json.dumps(value))
                    for key, value in state.get("evidence_index", {}).items()
                }
                validate_plan(parsed.remediation_plan, parsed, index)
            except (ValueError, TypeError, KeyError, RuntimeError):
                errors.append("remediation contract invalid")
    if reason == "PLAN_FAILED" and (
        report.get("remediation_status") != "PLAN_FAILED" or report.get("remediation_plan")
    ):
        errors.append("PLAN_FAILED conflicts with remediation result")
    if reason == "DIAGNOSIS_READY" and report.get("remediation_status") not in {
        "SKIPPED",
        "NOT_STARTED",
    }:
        errors.append("DIAGNOSIS_READY conflicts with remediation result")
    if reason in {"INCONCLUSIVE", "NO_ALERT"} and (
        report.get("status") != "INCONCLUSIVE" or report.get("root_cause") is not None
    ):
        errors.append("non-diagnosis terminal reason conflicts with report")
    if reason == "NO_ALERT" and (state.get("incident_alert") or {}).get("status") != "NO_ALERT":
        errors.append("NO_ALERT requires a monitoring result")
    if new:
        from incident_lens.schemas import RCAReport
        from incident_lens.schemas.workflow import TaskRecord

        try:
            RCAReport.model_validate(report)
        except (ValueError, TypeError):
            errors.append("invalid report contract")
        try:
            records = [TaskRecord.model_validate(r) for r in state.get("task_records", [])]
            observed = {}
            for event in state.get("events", []):
                if event.get("event_type") in {
                    "TASK_ASSIGNED",
                    "TASK_RUNNING",
                    "TASK_COMPLETED",
                    "TASK_FAILED",
                    "TASK_CANCELLED",
                }:
                    record = TaskRecord.model_validate(dict(details(event), role=event.get("role")))
                    observed[record.attempt_id] = record.model_dump()
            snapshots = {r.attempt_id: r.model_dump() for r in records}
            if len(snapshots) != len(records) or snapshots != observed:
                errors.append("task snapshots conflict with transition events")
        except (ValueError, TypeError):
            errors.append("invalid task record contract")
        expected = "FAILED" if result.outcome == "FAILED" else "FINISHED"
        if state.get("workflow_status") != expected or report.get("workflow_status") != expected:
            errors.append("workflow status conflicts with termination")
        if resolved and not accepted_diagnosis(state):
            errors.append("resolved report lacks matching acceptance checkpoint")
    return errors


def normalize_termination(state):
    """Classify new, structured V1.2 and pre-protocol histories conservatively."""
    events = state.get("events", [])
    report = state.get("report") or {}
    recovered = recovered_call_ids(events)
    failures = [
        e
        for e in events
        if e.get("event_type") == "MODEL_FAILURE" and not details(e).get("cancelled")
    ]
    unrecovered = [
        e
        for e in failures
        if not details(e).get("call_id") or details(e)["call_id"] not in recovered
    ]
    new = (
        state.get("termination") is not None
        or report.get("termination") is not None
        or any(
            e.get("event_type") in {REQUEST, *TERMINALS}
            or details(e).get("protocol_version") == "2"
            for e in events
        )
    )
    stops = [(i, e) for i, e in enumerate(events) if e.get("event_type") == "STOP"]
    result = None
    errors = []
    protocol_valid = None
    source = "legacy"
    if new:
        source = "v2"
        try:
            result = TerminationResult.model_validate(state.get("termination"))
            if report.get("termination") != result.model_dump():
                errors.append("state/report termination mismatch")
        except (ValidationError, TypeError):
            errors.append("missing or invalid termination result")
        requests = [(i, e) for i, e in enumerate(events) if e.get("event_type") == REQUEST]
        terminals = [(i, e) for i, e in enumerate(events) if e.get("event_type") in TERMINALS]
        if len(requests) != 1 or len(terminals) != 1 or stops:
            errors.append("expected one request and terminal, without legacy STOP")
        elif result:
            ri, request = requests[0]
            ti, terminal = terminals[0]
            rd = details(request)
            if ri >= ti or details(terminal) != result.model_dump():
                errors.append("terminal order or result mismatch")
            if terminal.get("event_type") != (
                "RUNTIME_FAILURE" if result.runtime_failure else "NORMAL_TERMINATION"
            ):
                errors.append("terminal event conflicts with runtime_failure")
            if rd.get("protocol_version") != "2" or rd.get("message_type") != REQUEST:
                errors.append("invalid request protocol")
            if rd.get("stop_reason") not in (
                {result.reason}
                if result.reason != "STOP_TIMEOUT"
                else {
                    "PLAN_READY",
                    "DIAGNOSIS_READY",
                    "INCONCLUSIVE",
                    "NO_ALERT",
                    "PLAN_FAILED",
                    "BUDGET_EXHAUSTED",
                    "UNRECOVERABLE_ERROR",
                }
            ):
                errors.append("request reason conflicts with termination")
            roles = rd.get("required_roles")
            if (
                not isinstance(roles, list)
                or any(not isinstance(r, str) for r in roles)
                or len(set(roles)) != len(roles)
            ):
                errors.append("invalid required ACK roles")
                roles = []
            acknowledgments = [
                (i, e) for i, e in enumerate(events) if e.get("event_type") == "STOP_ACK"
            ]
            ack_roles = [e.get("role", details(e).get("role")) for _, e in acknowledgments]
            if any(not isinstance(role, str) for role in ack_roles):
                errors.append("invalid ACK role")
                ack_roles = [role for role in ack_roles if isinstance(role, str)]
            if len(set(ack_roles)) != len(ack_roles) or not set(ack_roles).issubset(roles):
                errors.append("unexpected or duplicate ACK")
            for i, ack in acknowledgments:
                ad = details(ack)
                if (
                    not ri < i < ti
                    or ad.get("message_type") != "STOP_ACK"
                    or any(
                        ad.get(k) != rd.get(k)
                        for k in ("run_id", "incident_id", "stop_reason", "protocol_version")
                    )
                ):
                    errors.append("ACK identity or order mismatch")
            timeout = any(e.get("event_type") == "STOP_TIMEOUT" for e in events)
            if timeout != (result.reason == "STOP_TIMEOUT"):
                errors.append("timeout conflicts with termination")
            if timeout:
                timeouts = [
                    (i, e) for i, e in enumerate(events) if e.get("event_type") == "STOP_TIMEOUT"
                ]
                if (
                    len(timeouts) != 1
                    or not ri < timeouts[0][0] < ti
                    or (
                        details(timeouts[0][1]).get("missing_roles")
                        != sorted(set(roles) - set(ack_roles))
                    )
                    or not set(roles) - set(ack_roles)
                ):
                    errors.append("invalid timeout roles or order")
            if result.stop_completed and (
                set(ack_roles) != set(roles)
                or any(
                    r.get("status") in {"ASSIGNED", "RUNNING"}
                    for r in state.get("task_records", [])
                )
            ):
                errors.append("stop completed with unacknowledged or active tasks")
            # A rescued acceptance is published by report() after the stop request;
            # only a validated rescued checkpoint may cross the freeze boundary.
            if any(
                e.get("event_type") in FROZEN_MUTATIONS
                and not (details(e).get("rescued") and acceptance_matches(e, report, events))
                for e in events[ri + 1 :]
            ):
                errors.append("publication or execution after stop request")
            for _, e in requests + terminals + acknowledgments:
                for key in ("run_id", "incident_id"):
                    if e.get(key) != state.get(key):
                        errors.append("event identity mismatch")
            for key in ("run_id", "incident_id"):
                if rd.get(key) != state.get(key):
                    errors.append("request identity mismatch")
    elif stops and all(details(e).get("message_type") == "STOP" for _, e in stops):
        source = "v1.2"
        if len(stops) != 1:
            errors.append("multiple historical stop requests")
        reason = details(stops[-1][1]).get("stop_reason")
        try:
            result = termination_result(
                "STOP_TIMEOUT"
                if any(e.get("event_type") == "STOP_TIMEOUT" for e in events)
                else reason,
                failure_stage="stop"
                if any(e.get("event_type") == "STOP_TIMEOUT" for e in events)
                else "remediation"
                if reason == "PLAN_FAILED"
                else "runtime",
                stop_completed=not any(e.get("event_type") == "STOP_TIMEOUT" for e in events),
            )
        except (ValidationError, TypeError):
            errors.append("unknown historical stop reason")
        if any(e.get("event_type") in FROZEN_MUTATIONS for e in events[stops[0][0] + 1 :]):
            errors.append("historical mutation after stop")
        if any(r.get("status") in {"ASSIGNED", "RUNNING"} for r in state.get("task_records", [])):
            errors.append("historical active tasks after stop")
    if result:
        errors.extend(_semantic_errors(state, result, new))
    if new and result and not result.runtime_failure:
        if any(e.get("event_type") == "RUNTIME_ERROR" for e in events):
            errors.append("fatal runtime error contradicts normal termination")
        degraded = set()
        if accepted_diagnosis(state):
            for event in events:
                if event.get("event_type") == "DIAGNOSIS_ACCEPTED":
                    degraded.update(details(event).get("degraded_call_ids", []))
        for event in unrecovered:
            data = details(event)
            if result.reason == "PLAN_FAILED" and data.get("stage") == "remediation":
                continue
            if (
                data.get("call_id") in degraded
                and data.get("task_id")
                and any(
                    r.get("task_id") == data["task_id"] and r.get("status") == "FAILED"
                    for r in state.get("task_records", [])
                )
            ):
                continue
            errors.append("unrecovered model failure contradicts normal termination")
    if source != "legacy":
        protocol_valid = bool(result) and not errors
    historical_failure = (
        bool(stops)
        or bool(unrecovered)
        or any(e.get("event_type") in {"RUNTIME_ERROR", "STOP_TIMEOUT"} for e in events)
    )
    runtime_failure = (
        result.runtime_failure
        if protocol_valid
        else True
        if source != "legacy"
        else historical_failure
    )
    # Older structured traces do not prove which failed calls were safely bypassed.
    if source == "v1.2" and (
        unrecovered or any(e.get("event_type") == "RUNTIME_ERROR" for e in events)
    ):
        runtime_failure = True
    diagnosis_failure = runtime_failure
    if new and protocol_valid and accepted_diagnosis(state):
        diagnosis_failure = bool(
            result.runtime_failure and result.failure_stage not in {"remediation", "stop"}
        )
        accepted = next(
            i for i, e in enumerate(events) if e.get("event_type") == "DIAGNOSIS_ACCEPTED"
        )
        checkpoint = accepted
        rescued = details(events[accepted]).get("rescued") is True
        if rescued:
            review_id = details(events[accepted]).get("rescue_review_event_id")
            checkpoint = next(
                (
                    i
                    for i, e in enumerate(events)
                    if e.get("event_type") == "REVIEW" and e.get("event_id") == review_id
                ),
                accepted,
            )
        if any(
            e.get("event_type") == "RUNTIME_ERROR"
            and details(e).get("stage") not in {"remediation", "stop"}
            for e in events[:checkpoint]
        ):
            diagnosis_failure = True
        elif rescued and checkpoint != accepted:
            after = [
                e
                for e in events[checkpoint + 1 :]
                if e.get("event_type") == "RUNTIME_ERROR"
            ]
            if after and all(details(e).get("transport_error") is True for e in after):
                diagnosis_failure = False
    return {
        "scoring_version": SCORING_VERSION,
        "termination_source": source,
        "termination": result.model_dump() if result else None,
        "termination_reason": result.reason if result else None,
        "termination_outcome": result.outcome if result else None,
        "protocol_valid": protocol_valid,
        "protocol_errors": sorted(set(errors)),
        "runtime_failure": runtime_failure,
        "diagnosis_failure": diagnosis_failure,
        "stop_completion": bool(protocol_valid and result.stop_completed)
        if source != "legacy"
        else None,
        "recovered_model_failure_count": sum(
            details(e).get("call_id") in recovered for e in failures
        ),
        "unrecovered_model_failure_count": len(unrecovered),
    }
