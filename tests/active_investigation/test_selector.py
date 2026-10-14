import pytest
from test_feature_extraction import (
    budget,
    candidate,
    hypotheses,
    task,
    visible,
)

from incident_lens.orchestration.active_investigation.contracts import PolicyConfig


def select(allow, candidates, v=None, b=None, policy="active_evidence", **config):
    return allow.select_candidates(
        tuple(candidates), v or visible(), b or budget(), {}, PolicyConfig(**config), policy
    )


def test_deterministic_tie(allow):
    cs = [candidate("z"), candidate("a", proposed_role="metrics")]
    assert select(allow, cs, max_selected_tasks=1).selected_candidate_ids == ("a",)
    assert select(allow, cs) == select(allow, cs)


def test_diversity(allow):
    cs = [candidate("a"), candidate("b"), candidate("c", proposed_role="metrics")]
    assert select(allow, cs).selected_candidate_ids == ("a", "c")


def test_aggregate_request_reserve(allow):
    cs = [candidate("a"), candidate("b", proposed_role="metrics")]
    assert len(select(allow, cs, b=budget(remaining_requests=4)).selected_candidate_ids) == 1
    assert len(select(allow, cs, b=budget(remaining_requests=5)).selected_candidate_ids) == 2
    assert select(allow, cs, b=budget(remaining_requests=2)).fallback_reason == "NO_USEFUL_ACTION"


def test_aggregate_tool_reserve(allow):
    cs = [candidate("a"), candidate("b", proposed_role="metrics")]
    assert len(select(allow, cs, b=budget(remaining_tools=3)).selected_candidate_ids) == 1
    assert len(select(allow, cs, b=budget(remaining_tools=5)).selected_candidate_ids) == 2


def test_ablation_rankings_actually_differ(allow, monkeypatch):
    # Constructed calibrated costs only; production uncalibrated fallback is uniform.
    original_estimate = allow.estimate_cost
    monkeypatch.setattr(
        allow,
        "estimate_cost",
        lambda c, b: original_estimate(c, b).model_copy(
            update={
                "estimated_tool_calls": 2 if c.candidate_id == "expensive" else 1,
                "source": "dev_aggregate",
            }
        ),
    )
    # Same published state/pool, four different first actions.
    first = candidate(
        "first", question="other", expected_discriminator="other", proposed_role="changes"
    )
    expensive = candidate(
        "expensive",
        question="capacity high",
        expected_discriminator="capacity high",
        allowed_tools=("a", "b"),
    )
    cheap = candidate(
        "cheap",
        question="capacity normal",
        expected_discriminator="capacity normal",
        proposed_role="metrics",
    )
    gap = candidate(
        "gap",
        question="request gap",
        expected_discriminator="request gap",
        proposed_role="database",
    )
    v = visible(
        hypotheses=hypotheses(),
        requested_checks=(task(gap),),
        evidence_sources=("changes", "metrics"),
        grounding_errors=("missing source",),
        open_questions=("capacity normal",),
    )
    cs = [first, expensive, cheap, gap]
    choices = {
        p: select(
            allow, cs, v=v, policy=p, max_selected_tasks=1, tool_weight=1
        ).selected_candidate_ids
        for p in ("first_eligible", "active_no_cost", "active_no_discrimination", "active_evidence")
    }
    assert choices == {
        "first_eligible": ("first",),
        "active_no_cost": ("expensive",),
        "active_no_discrimination": ("gap",),
        "active_evidence": ("cheap",),
    }


def test_negative_and_zero_no_selection(allow):
    assert (
        select(allow, [candidate()], v=visible(evidence_sources=("logs",))).selected_candidate_ids
        == ()
    )
    assert (
        select(
            allow,
            [candidate()],
            v=visible(evidence_sources=("logs",)),
            gate_weight=0,
            redundancy_weight=1,
        ).fallback_reason
        == "NO_USEFUL_ACTION"
    )


def test_hard_rejection_beats_value(allow, monkeypatch):
    monkeypatch.setattr(allow, "check_eligibility", lambda *args: "FORBIDDEN_TOOL")
    result = select(allow, [candidate()], v=visible(hypotheses=hypotheses()))
    assert result.selected_candidate_ids == ()
    assert result.assessments[0].reject_reason == "FORBIDDEN_TOOL"


def test_stopped(allow):
    assert (
        select(allow, [candidate()], v=visible(stopped=True)).assessments[0].reject_reason
        == "STOPPED"
    )


def test_off_must_bypass(allow):
    import pytest

    with pytest.raises(ValueError, match="bypass"):
        select(allow, [], policy="current_dynamic")


def test_negative_value_abstains(allow, monkeypatch):
    from incident_lens.orchestration.active_investigation.contracts import CandidateFeatures

    monkeypatch.setattr(
        allow,
        "extract_features",
        lambda c, v, cost: CandidateFeatures(
            discrimination=0, gap_coverage=0, gate_contribution=0, redundancy=1, cost=cost
        ),
    )
    result = select(allow, [candidate()])
    assert result.assessments[0].score < 0
    assert result.selected_candidate_ids == ()


def test_two_physical_tasks_and_verifier_reserve(allow):
    cs = [candidate("a"), candidate("b", proposed_role="metrics")]
    assert (
        len(
            select(
                allow, cs, b=budget(remaining_requests=9, physical_request_multiplier=2)
            ).selected_candidate_ids
        )
        == 1
    )
    assert (
        len(
            select(
                allow, cs, b=budget(remaining_requests=10, physical_request_multiplier=2)
            ).selected_candidate_ids
        )
        == 2
    )


def test_no_execution_dependencies():
    import ast
    from pathlib import Path

    from incident_lens.orchestration.active_investigation import (
        cost_estimator,
        feature_extractors,
        selector,
    )

    for module in (cost_estimator, feature_extractors, selector):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            any(
                part in name.split(".")
                for part in ("provider", "oracle", "evaluation", "tools", "graph")
            )
            for name in imports
        )


@pytest.fixture
def allow(monkeypatch):
    from incident_lens.orchestration.active_investigation import selector

    monkeypatch.setattr(selector, "check_eligibility", lambda *args: None)
    return selector
