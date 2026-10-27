import copy

import pytest

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.orchestration.guards import reviewed_finalization_ready
from incident_lens.tools import EvidenceProvider


@pytest.fixture
async def pending():
    state = await run_investigation("incident_001", MockProvider())
    state.report = None
    state.termination = None
    state.workflow_status = "RUNNING"
    assert reviewed_finalization_ready(state)
    return state


@pytest.mark.parametrize("fault", [
    "no_decision", "investigate", "abstain", "other_target", "unknown_target",
    "insufficient", "contradiction", "blocking_check", "no_citations",
    "candidate_drift", "evidence_drift", "missing_review_event", "shared_question",
    "competitor", "stopped", "terminal",
])
async def test_resume_never_bypasses_acceptance_guards(pending, fault):
    state = copy.deepcopy(pending)
    decision, review = state.decisions[-1], state.reviews[-1]
    candidate = next(h for h in state.hypotheses
                     if h.hypothesis_id == decision.selected_hypothesis_id)
    if fault == "no_decision":
        state.decisions = []
    elif fault in {"investigate", "abstain"}:
        state.decisions[-1] = decision.model_copy(update={"action": fault.upper()})
    elif fault == "other_target":
        review.target_hypothesis_id = "other"
    elif fault == "unknown_target":
        decision.selected_hypothesis_id = review.target_hypothesis_id = "unknown"
    elif fault == "insufficient":
        review.verdict = "insufficient"
    elif fault == "contradiction":
        review.contradictions = ["Contradiction"]
    elif fault == "blocking_check":
        review.requested_checks = [state.tasks[0]]
    elif fault == "no_citations":
        review.cited_evidence_ids = []
    elif fault == "candidate_drift":
        candidate.predicted_observations.append("Not reviewed")
    elif fault == "evidence_drift":
        next(iter(state.evidence_index.values())).excerpt = "Changed"
    elif fault == "missing_review_event":
        state.events = [e for e in state.events if e.event_type != "REVIEW"]
    elif fault == "shared_question":
        state.open_questions = ["Unresolved"]
    elif fault == "competitor":
        rival = next(h for h in state.hypotheses if h.hypothesis_id != candidate.hypothesis_id)
        rival.status = "OPEN"
        rival.open_questions = ["Unresolved competing cause"]
        positive = next(iter(state.evidence_index.values())).model_copy(update={
            "evidence_id": "incident_001-competing-cap", "service": "postgres",
            "source_type": "database", "source_path": "public/database.jsonl",
            "excerpt": "Connection admission rejected at server cap",
            "metadata": {"category": "connections", "connection_count": 155, "connection_limit": 100},
        })
        state.evidence_index[positive.evidence_id] = positive
        rival.support_ids = [positive.evidence_id]
    elif fault == "stopped":
        state.workflow_status = "STOPPING"
    elif fault == "terminal":
        state.termination = (await run_investigation("incident_001", MockProvider())).termination
    assert not reviewed_finalization_ready(state)


@pytest.mark.parametrize("variant", ["single", "fixed", "dynamic_no_verifier"])
async def test_resume_does_not_change_other_variants(pending, variant):
    assert not reviewed_finalization_ready(pending, variant)


async def test_finalizer_still_rejects_expired_budget_after_valid_review(pending):
    runtime = InvestigationRun(MockProvider(), EvidenceProvider("data"), "incident_001")
    runtime.call_budget.started -= runtime.limits.max_wall_seconds + 1
    result = runtime.finalize({"investigation": pending})
    assert result["route"] == "report"
    assert pending.report is None
    assert "Wall-clock budget audit failed" in pending.stop_reason


async def test_resume_event_after_stop_is_a_protocol_violation():
    from incident_lens.evaluation.termination import normalize_termination

    state = await run_investigation("incident_001", MockProvider())
    raw = state.model_dump(mode="json")
    raw["events"].append(raw["events"][-1] | {
        "event_id": "late-resume", "event_type": "FINALIZE_RESUMED_AFTER_REVIEW", "details": {},
    })
    summary = normalize_termination(raw)
    assert not summary["protocol_valid"]
    assert "publication or execution after stop request" in summary["protocol_errors"]
