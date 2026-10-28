"""Distinguish observed causal competitors from hypothetical/background errors."""

import pytest

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import competitor_assessments, finalize_errors
from incident_lens.schemas import Hypothesis


@pytest.fixture
async def supported():
    state = await run_investigation("incident_001", MockProvider())
    candidate = next(h for h in state.hypotheses
                     if h.hypothesis_id == state.report.root_cause.hypothesis_id)
    assert not finalize_errors(state, candidate)
    return state, candidate


@pytest.mark.parametrize("kind", ["hypothetical", "generic_symptom", "unrelated_business_error"])
async def test_unsupported_alternative_is_preserved_without_veto(supported, kind):
    state, candidate = supported
    rival = Hypothesis(hypothesis_id="alternative", culprit_service="postgres",
                       failure_mode="postgres_connection_exhaustion",
                       open_questions=["Could an unobserved alternative exist?"])
    if kind == "generic_symptom":
        rival.support_ids = [eid for eid, r in state.evidence_index.items() if r.source_type == "logs"][:1]
    if kind == "unrelated_business_error":
        record = next(iter(state.evidence_index.values())).model_copy(update={
            "evidence_id": "background-order", "service": "payment", "source_type": "logs",
            "source_path": "public/logs.jsonl", "excerpt": "Order status not allowed to pay", "metadata": {},
        })
        state.evidence_index[record.evidence_id] = record
        rival.culprit_service = "payment"
        rival.failure_mode = "payment_external_timeout"
        rival.support_ids = [record.evidence_id]
    state.hypotheses.append(rival)
    assessment = competitor_assessments(state, candidate)[rival.hypothesis_id]
    assert not assessment["blocking"]
    assert assessment["reason"] == "no_observed_competing_mechanism"
    assert "Competing hypothesis remains unresolved" not in finalize_errors(state, candidate, "single")
    assert rival.status == "OPEN" and rival.open_questions


async def test_positive_competing_mechanism_still_blocks(supported):
    state, candidate = supported
    record = next(iter(state.evidence_index.values())).model_copy(update={
        "evidence_id": "positive-cap", "service": "postgres", "source_type": "database",
        "source_path": "public/database.jsonl", "excerpt": "Connections at server cap",
        "metadata": {"category": "connections", "connection_count": 155, "connection_limit": 100},
    })
    state.evidence_index[record.evidence_id] = record
    state.hypotheses.append(Hypothesis(
        hypothesis_id="observed-alternative", culprit_service="postgres",
        failure_mode="postgres_connection_exhaustion", support_ids=[record.evidence_id]))
    assert "Competing hypothesis remains unresolved" in finalize_errors(state, candidate, "single")


async def test_optional_questions_do_not_block_but_review_snapshot_is_still_required(supported):
    state, candidate = supported
    candidate.optional_questions = ["A longer baseline would improve presentation"]
    assert not finalize_errors(state, candidate, "single")
    assert any("snapshot" in error for error in finalize_errors(state, candidate, "full"))
    candidate.open_questions = ["Which service originated the failing operation?"]
    assert not finalize_errors(state, candidate, "single")
    assert any("snapshot" in error for error in finalize_errors(state, candidate, "full"))


async def test_true_contradictions_and_unobserved_rival_citations_are_not_ignored(supported):
    state, candidate = supported
    candidate.against_ids = [candidate.support_ids[0]]
    assert any("contradictory evidence" in error for error in finalize_errors(state, candidate, "single"))
    state.hypotheses.append(Hypothesis(hypothesis_id="bad-ref", culprit_service="postgres",
        failure_mode="postgres_connection_exhaustion", support_ids=["not-observed"]))
    assessment = competitor_assessments(state, candidate)["bad-ref"]
    assert assessment["blocking"] and assessment["reason"] == "unobserved_citations"
