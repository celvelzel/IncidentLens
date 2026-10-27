"""An informative abstention remains an abstention for protocol and RCA scoring."""

import pytest
from pydantic import ValidationError

from incident_lens.evaluation.metrics import score_completed
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.report import populate_assessment, render_report
from incident_lens.schemas import Hypothesis, InvestigationState, RCAReport


class AbstainWithEvidence(MockProvider):
    def _decide(self, payload):
        result = super()._decide(payload)
        if result["action"] == "FINALIZE":
            result.update(action="ABSTAIN", selected_hypothesis_id=None,
                          stop_reason="Retain leading explanation without confirming attribution")
        return result


async def test_abstention_preserves_observations_and_next_step_without_success_credit():
    state = await run_investigation("incident_001", AbstainWithEvidence())
    report = state.report
    assert report.status == "INCONCLUSIVE" and report.root_cause is None
    assert report.assessment_level == "LIKELY"
    assert report.provisional_hypotheses[0].culprit_service == "backend"
    assert all(h.status == "OPEN" for h in report.provisional_hypotheses)
    assert report.provisional_observations and report.next_steps
    assert report.supporting_evidence_ids == []
    assert state.termination.outcome == "ABSTAINED"
    terminal = normalize_termination(state.model_dump(mode="json"))
    assert terminal["protocol_valid"] and terminal["termination_reason"] == "INCONCLUSIVE"
    assert not any(e.event_type == "DIAGNOSIS_ACCEPTED" for e in state.events)
    score = score_completed(state.model_dump(mode="json"), {
        "is_identifiable": True, "culprit_service": "backend", "failure_mode": "backend_pool_config_regression",
    })
    assert not score["root_cause_correct"]
    assert score["citation_count"] > 0 and score["citation_existence_validity"] == 1
    text = render_report(report)
    assert "Likely explanation — NOT confirmed" in text
    assert "DB_POOL_MAX" in text
    assert "Suggested next checks — not executed" in text
    # Predictions are not promoted into the observed evidence section.
    for predicted in report.provisional_hypotheses[0].predicted_observations:
        assert not any(predicted in line for line in report.provisional_observations)


async def test_provisional_citations_are_validated_like_confirmed_citations():
    state = await run_investigation("incident_001", AbstainWithEvidence())
    raw = state.model_dump(mode="json")
    raw["report"]["provisional_hypotheses"][0]["support_ids"] = ["fabricated"]
    with pytest.raises(ValidationError, match="all shared citations"):
        InvestigationState.model_validate_json(__import__("json").dumps(raw))


async def test_real_attribution_gap_stays_insufficient_and_optional_note_is_separate():
    state = await run_investigation("incident_001", AbstainWithEvidence())
    leading = next(h for h in state.hypotheses
                   if h.hypothesis_id == state.report.provisional_hypotheses[0].hypothesis_id)
    leading.open_questions = ["Does this mechanism originate the failing request?"]
    leading.optional_questions = ["A longer baseline would improve the explanation"]
    populate_assessment(state)
    assert state.report.assessment_level == "INSUFFICIENT"
    assert leading.open_questions[0] in state.report.unresolved
    assert leading.optional_questions[0] in state.report.optional_questions
    assert leading.optional_questions[0] not in state.report.unresolved
    assert any(leading.open_questions[0] in step for step in state.report.next_steps)
    assert state.report.root_cause is None


async def test_no_observations_does_not_invent_a_leading_cause():
    class EmptyAbstain(MockProvider):
        def _decide(self, payload):
            return {"action": "ABSTAIN", "reason": "No observed mechanism",
                    "assignments": [], "selected_hypothesis_id": None,
                    "stop_reason": "Evidence unavailable"}

    state = await run_investigation("incident_001", EmptyAbstain())
    assert state.report.assessment_level == "INSUFFICIENT"
    assert state.report.provisional_hypotheses == []
    assert state.report.next_steps


def test_tentative_labels_cannot_become_confirmed_roots_by_report_fields():
    h = Hypothesis(hypothesis_id="h1", culprit_service="backend", failure_mode="test",
                   support_ids=["E1"])
    with pytest.raises(ValidationError, match="CONFIRMED"):
        RCAReport(run_id="run1", incident_id="incident_001", status="INCONCLUSIVE",
                  stop_reason="pending", assessment_level="CONFIRMED", provisional_hypotheses=[h])
    with pytest.raises(ValidationError, match="OPEN"):
        RCAReport(run_id="run1", incident_id="incident_001", status="INCONCLUSIVE",
                  stop_reason="pending", provisional_hypotheses=[h.model_copy(update={"status": "SUPPORTED"})])
