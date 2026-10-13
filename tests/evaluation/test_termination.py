"""Protocol normalization keeps malformed and legacy failures conservative."""

import copy

import pytest
from pydantic import ValidationError

from incident_lens.evaluation.termination import normalize_termination
from incident_lens.schemas.workflow import termination_result


def new_state(reason="INCONCLUSIVE"):
    terminal = termination_result(reason).model_dump()
    identity = {"incident_id": "case", "run_id": "run"}
    request = dict(
        identity,
        protocol_version="2",
        message_type="WORKFLOW_STOP_REQUESTED",
        stop_reason=reason,
        required_roles=[],
    )
    return dict(
        identity,
        workflow_status="FINISHED",
        termination=terminal,
        task_records=[],
        report=dict(
            identity,
            status="INCONCLUSIVE",
            root_cause=None,
            workflow_status="FINISHED",
            termination=terminal,
            stop_reason=reason,
        ),
        events=[
            dict(identity, event_type="WORKFLOW_STOP_REQUESTED", details=request),
            dict(identity, event_type="NORMAL_TERMINATION", details=terminal),
        ],
    )


@pytest.mark.parametrize(
    "reason",
    [
        "PLAN_READY",
        "DIAGNOSIS_READY",
        "INCONCLUSIVE",
        "NO_ALERT",
        "PLAN_FAILED",
        "BUDGET_EXHAUSTED",
        "UNRECOVERABLE_ERROR",
        "STOP_TIMEOUT",
    ],
)
def test_reason_table(reason):
    result = termination_result(
        reason,
        failure_stage="stop"
        if reason == "STOP_TIMEOUT"
        else "remediation"
        if reason == "PLAN_FAILED"
        else "runtime",
        stop_completed=reason != "STOP_TIMEOUT",
    )
    assert result.runtime_failure == (
        reason in {"BUDGET_EXHAUSTED", "UNRECOVERABLE_ERROR", "STOP_TIMEOUT"}
    )


def test_normal_protocol_and_no_input_mutation():
    state = new_state()
    original = copy.deepcopy(state)
    result = normalize_termination(state)
    assert result["protocol_valid"] and result["stop_completion"]
    assert not result["runtime_failure"]
    assert state == original


@pytest.mark.parametrize(
    "change",
    ["unknown", "missing", "conflict", "active", "late", "duplicate", "identity", "model_failure"],
)
def test_invalid_protocol_never_passes(change):
    state = new_state()
    if change == "unknown":
        state["termination"]["reason"] = "UNKNOWN"
    elif change == "missing":
        del state["termination"]["stop_completed"]
    elif change == "conflict":
        state["report"]["termination"] = dict(state["termination"], outcome="SUCCESS")
    elif change == "active":
        state["task_records"] = [{"status": "RUNNING"}]
    elif change == "late":
        state["events"].append({"event_type": "MERGE"})
    elif change == "duplicate":
        state["events"].append(copy.deepcopy(state["events"][0]))
    elif change == "identity":
        state["events"][0]["run_id"] = "other"
    else:
        state["events"].insert(0, {"event_type": "MODEL_FAILURE"})
    result = normalize_termination(state)
    assert not result["protocol_valid"] and not result["stop_completion"]
    assert result["runtime_failure"] and result["protocol_errors"]


@pytest.mark.parametrize(
    "event",
    [
        {"event_type": "STOP"},
        {"event_type": "MODEL_FAILURE"},
        {"event_type": "STOP", "details": {"message_type": "STOP", "stop_reason": "UNKNOWN"}},
        {"event_type": "STOP_ACK", "details": {"protocol_version": "2"}},
    ],
)
def test_historical_failures_remain_failures(event):
    state = {"report": {"status": "INCONCLUSIVE", "root_cause": None}, "events": [event]}
    assert normalize_termination(state)["runtime_failure"]


def test_historical_normal_abstention():
    state = {
        "report": {"status": "INCONCLUSIVE", "root_cause": None},
        "events": [
            {
                "event_type": "STOP",
                "details": {"message_type": "STOP", "stop_reason": "INCONCLUSIVE"},
            }
        ],
    }
    result = normalize_termination(state)
    assert result["protocol_valid"] and not result["runtime_failure"]


def test_inconsistent_result_rejected():
    with pytest.raises(ValidationError):
        termination_result("PLAN_READY", stop_completed=False)


@pytest.mark.parametrize(
    "fault",
    [
        "ack_missing",
        "ack_identity",
        "ack_late",
        "task_missing",
        "fatal_error",
        "invalid_reason_type",
    ],
)
def test_ack_and_transition_consistency(fault):
    state = new_state()
    identity = {"incident_id": "case", "run_id": "run"}
    if fault.startswith("ack"):
        state["events"][0]["details"]["required_roles"] = ["logs"]
        if fault != "ack_missing":
            ack = dict(
                identity,
                event_type="STOP_ACK",
                role="logs",
                details=dict(
                    identity,
                    protocol_version="2",
                    message_type="STOP_ACK",
                    stop_reason="INCONCLUSIVE",
                ),
            )
            if fault == "ack_identity":
                ack["details"]["run_id"] = "wrong"
                state["events"].insert(1, ack)
            else:
                state["events"].append(ack)
    elif fault == "task_missing":
        state["events"].insert(
            0,
            dict(
                identity,
                event_type="TASK_COMPLETED",
                role="logs",
                details={
                    "task_id": "task",
                    "attempt_id": "attempt",
                    "attempt": 1,
                    "status": "COMPLETED",
                    "error_code": None,
                },
            ),
        )
    elif fault == "fatal_error":
        state["events"].insert(0, {"event_type": "RUNTIME_ERROR", "details": {"stage": "verify"}})
    else:
        state["termination"]["reason"] = {"unknown": True}
    result = normalize_termination(state)
    assert not result["protocol_valid"] and not result["stop_completion"]
