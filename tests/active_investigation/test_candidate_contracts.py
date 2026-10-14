import pytest
from pydantic import ValidationError

from incident_lens.orchestration.active_investigation.contracts import (
    BudgetView,
    CandidateAction,
    CostEstimate,
    PolicyConfig,
    SelectionDecision,
)


def candidate(**changes):
    values = dict(
        candidate_id="c1",
        decision_id="d1",
        incident_id="i1",
        run_id="r1",
        evidence_snapshot_sha256="hash",
        origin="coordinator_proposal",
        proposed_role="logs",
        question="Check errors",
        expected_discriminator="onset",
        allowed_tools=("query_logs",),
    )
    return CandidateAction(**(values | changes))


def test_roundtrip():
    item = candidate(filters={"service": "backend"})
    assert CandidateAction.model_validate_json(item.model_dump_json()) == item
    assert CandidateAction.model_json_schema()["additionalProperties"] is False


@pytest.mark.parametrize(
    "changes",
    [
        dict(proposed_role="coordinator"),
        dict(secret="x"),
        dict(question=""),
        dict(filters={"x": object()}),
    ],
)
def test_invalid_candidates(changes):
    with pytest.raises((ValidationError, ValueError)):
        candidate(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        dict(max_selected_tasks=3),
        dict(epsilon=0),
        dict(discrimination_weight=float("nan")),
        dict(use_extra_candidate_llm_call=True),
    ],
)
def test_invalid_config(changes):
    with pytest.raises(ValidationError):
        PolicyConfig(**changes)


def test_cost_unknown_is_null():
    cost = CostEstimate(estimated_model_requests=2, estimated_tool_calls=1)
    assert cost.estimated_tokens is None
    assert cost.estimated_latency_ms is None


def test_budget_no_negative():
    with pytest.raises(ValidationError):
        BudgetView(remaining_requests=-1, remaining_tools=1, remaining_seconds=1)


def test_selection_policy_strict():
    with pytest.raises(ValidationError):
        SelectionDecision(
            decision_id="d",
            policy="madeup",
            policy_version="v",
            evidence_snapshot_sha256="h",
            selected_candidate_ids=(),
            assessments=(),
            budget_snapshot_digest="b",
        )


def test_visible_projection_detaches_live_objects():
    from datetime import datetime, timezone

    from incident_lens.orchestration.active_investigation.contracts import VisibleState
    from incident_lens.schemas import Hypothesis
    from incident_lens.schemas.contracts import CasePublicInput

    summary = CasePublicInput(
        incident_id="i",
        title="incident",
        started_at=datetime.now(timezone.utc),
        observed_symptoms=[],
        services=["backend"],
    )
    hypothesis = Hypothesis(hypothesis_id="h", culprit_service="backend", failure_mode="unknown")
    visible = VisibleState(
        run_id="r",
        incident_id="i",
        decision_id="d",
        evidence_snapshot_sha256="x",
        public_summary=summary,
        hypotheses=(hypothesis,),
    )
    visible.hypotheses[0].status = "SUPPORTED"
    visible.public_summary.services.append("other")
    assert hypothesis.status == "OPEN"
    assert summary.services == ["backend"]
