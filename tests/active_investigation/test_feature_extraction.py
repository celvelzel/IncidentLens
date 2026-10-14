from datetime import datetime, timezone

import pytest

from incident_lens.orchestration.active_investigation.contracts import (
    BudgetView,
    CandidateAction,
    VisibleState,
)
from incident_lens.orchestration.active_investigation.cost_estimator import estimate_cost
from incident_lens.orchestration.active_investigation.feature_extractors import extract_features
from incident_lens.schemas import Hypothesis, InvestigationTask
from incident_lens.schemas.contracts import CasePublicInput


def candidate(cid="c", **changes):
    return CandidateAction(
        **(
            dict(
                candidate_id=cid,
                decision_id="d",
                incident_id="i",
                run_id="r",
                evidence_snapshot_sha256="hash",
                origin="coordinator_proposal",
                proposed_role="logs",
                question="capacity",
                expected_discriminator="capacity high or normal",
                allowed_tools=("query_logs",),
                filters={"service": "backend"},
            )
            | changes
        )
    )


def visible(**changes):
    return VisibleState(
        **(
            dict(
                run_id="r",
                incident_id="i",
                decision_id="d",
                evidence_snapshot_sha256="hash",
                public_summary=CasePublicInput(
                    incident_id="i",
                    title="incident",
                    started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    observed_symptoms=[],
                    services=["backend"],
                ),
            )
            | changes
        )
    )


def budget(**changes):
    return BudgetView(
        **(dict(remaining_requests=20, remaining_tools=20, remaining_seconds=100) | changes)
    )


def hypotheses(predictions=("capacity high", "capacity normal")):
    return tuple(
        Hypothesis(
            hypothesis_id=f"h{i}",
            culprit_service="backend",
            failure_mode="same mode",
            predicted_observations=[p],
        )
        for i, p in enumerate(predictions)
    )


@pytest.mark.parametrize(
    "predictions", [("backend high", "backend normal"), ("capacity high", "capacity normal")]
)
def test_discrimination_is_hypothesis_permutation_invariant(predictions):
    hs = hypotheses(predictions)
    c = candidate(
        question="Check backend high load", expected_discriminator="high or normal capacity"
    )
    cost = estimate_cost(c, budget())
    forward = extract_features(c, visible(hypotheses=hs), cost)
    reverse = extract_features(c, visible(hypotheses=tuple(reversed(hs))), cost)
    assert forward.discrimination == reverse.discrimination


def task(c):
    return InvestigationTask(
        task_id="t",
        role=c.proposed_role,
        question=c.question,
        allowed_tools=list(c.allowed_tools),
        filters=c.filters,
        reason="published check",
        expected_discriminator=c.expected_discriminator,
    )


@pytest.fixture
def allow(monkeypatch):
    from incident_lens.orchestration.active_investigation import selector

    monkeypatch.setattr(selector, "check_eligibility", lambda *args: None)
    return selector


def features(c=None, v=None):
    c = c or candidate()
    return extract_features(c, v or visible(), estimate_cost(c, budget()))


def test_no_competition_bootstrap():
    f = features()
    assert f.discrimination == 0
    assert f.gate_contribution == 0.5


def test_distinct_predictions_not_mode_lookup():
    assert features(v=visible(hypotheses=hypotheses())).discrimination == 1
    assert (
        features(
            v=visible(hypotheses=hypotheses(("capacity high", "capacity high")))
        ).discrimination
        == 0
    )
    assert (
        features(
            candidate(question="deploy", expected_discriminator="version"),
            visible(hypotheses=hypotheses()),
        ).discrimination
        == 0
    )


def test_rejected_prediction_excluded():
    hs = hypotheses()
    hs[1].status = "REJECTED"
    assert features(v=visible(hypotheses=hs)).discrimination == 0


def test_requested_gap_independent_of_discrimination():
    c = candidate()
    f = features(c, visible(requested_checks=(task(c),)))
    assert f.gap_coverage == 1 and f.discrimination == 0


def test_open_question_gap():
    assert features(v=visible(open_questions=("capacity",))).gap_coverage == 1
    assert features(v=visible(open_questions=("deployment",))).gap_coverage == 0


def test_missing_source_gate_independent_of_discrimination():
    assert (
        features(v=visible(grounding_errors=("missing independent sources",))).gate_contribution
        == 1
    )
    assert (
        features(
            v=visible(evidence_sources=("logs",), grounding_errors=("missing sources",))
        ).gate_contribution
        == 0
    )


def test_redundancy_snapshot_and_window():
    from incident_lens.orchestration.active_investigation.candidate_generator import (
        candidate_signature,
    )

    c = candidate()
    v = visible(completed_signatures=(candidate_signature(c),))
    assert features(c, v).redundancy == 1
    assert features(candidate(filters={"service": "backend", "start": "new"}), v).redundancy == 0
    assert features(candidate(evidence_snapshot_sha256="new"), v).redundancy == 0


def test_features_finite_and_no_mutation():
    import math

    c, v = candidate(), visible(hypotheses=hypotheses())
    before = v.model_dump_json()
    f = features(c, v)
    assert before == v.model_dump_json()
    assert f == features(c, v)
    assert all(
        math.isfinite(x) and 0 <= x <= 1
        for x in (f.discrimination, f.gap_coverage, f.gate_contribution, f.redundancy)
    )


def test_generic_service_match_is_not_discrimination():
    assert (
        features(
            candidate(question="backend", expected_discriminator="backend"),
            visible(hypotheses=hypotheses(("backend capacity high", "backend latency normal"))),
        ).discrimination
        == 0
    )


def test_negation_preserved_in_requested_check():
    c = candidate(question="capacity not high")
    other = candidate(question="capacity high")
    assert features(c, visible(requested_checks=(task(other),))).gap_coverage == 0
