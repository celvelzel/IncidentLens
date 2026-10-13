import pytest

from incident_lens.incidentbench.scorer import aggregate, score_benchmark_run
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation


async def test_correct_root_and_foreign_or_unobserved_citations():
    state = (await run_investigation("incident_001", MockProvider())).model_dump(mode="json")
    root = state["report"]["root_cause"]
    oracle = dict(
        incident_id="incident_001",
        scenario_family_id="synthetic",
        mechanism_id="synthetic",
        is_identifiable=True,
        true_primary_root={
            **{k: root[k] for k in ("culprit_service", "failure_mode")},
            "root_cause_code": "supplemental",
        },
        acceptable_support_sets=[{"evidence_ids": ["e1"], "rationale": "synthetic fixture"}],
        contradicting_evidence_ids=[],
        misleading_evidence_ids=[],
        required_discriminator_types=[],
        causal_sequence=[],
        identifiability_rationale="synthetic fixture",
    )
    # Existing seed's mode is supported by the benchmark schema.
    result = score_benchmark_run(state, oracle)
    assert result["root_cause_correct"] is True
    assert result["label_status"] == "provisional"
    assert result["human_support_rate"] is None
    oracle["true_primary_root"]["culprit_service"] = "wrong"
    assert score_benchmark_run(state, oracle)["root_cause_correct"] is False
    state["report"]["supporting_evidence_ids"].append("forged")
    assert score_benchmark_run(state)["citation_existence_validity"] < 1
    state["events"] = []
    assert score_benchmark_run(state)["valid_citation_count"] == 0


async def test_synthetic_double_review_is_supported_only_for_exact_claim_bundle():
    from incident_lens.incidentbench.citation_review import prepare_review_bundle

    state = (await run_investigation("incident_001", MockProvider())).model_dump(mode="json")
    bundle = prepare_review_bundle([state])
    records = [
        dict(
            claim_id=c["claim_id"],
            reviewer_id=r,
            review_label="INSUFFICIENT",
            rationale="synthetic test record",
            source="human",
            reviewed_at="2026-10-01T00:00:00Z",
        )
        for c in bundle
        for r in ("synthetic-reviewer-a", "synthetic-reviewer-b")
    ]
    result = score_benchmark_run(state, annotations={"bundle": bundle, "records": records})
    assert result["citation_existence_validity"] == 1
    assert result["unsupported_claim_rate"] == 1
    assert result["human_review_coverage"] == 1
    with pytest.raises(ValueError, match="exactly cover"):
        score_benchmark_run(state, annotations={"bundle": bundle[:1], "records": []})


def test_no_report_failure_stays_denominator_and_unknown_tokens_null():
    state = dict(
        incident_id="incident_001",
        run_id="failed",
        report=None,
        events=[],
        evidence_index={},
        execution_error={"code": "HTTP_429"},
        stop_reason="UNRECOVERABLE_ERROR",
    )
    score = score_benchmark_run(state)
    assert score["technical_completion"] is False
    assert score["citation_existence_validity"] is None
    row = dict(variant="full", total_tokens=None, **score)
    result = aggregate([row])[0]
    assert result["investigation_completion_rate"] == {"numerator": 0, "denominator": 1, "rate": 0}
    assert result["total_tokens"] is None


def test_unknown_annotations_are_rejected():
    with pytest.raises((ValueError, KeyError, ImportError, ModuleNotFoundError)):
        score_benchmark_run(
            dict(incident_id="incident_001", report=None, events=[], evidence_index={}),
            annotations={},
        )


def test_interrupted_requests_unknown_never_filled_with_zero():
    result = aggregate(
        [
            {"variant": "full", "actual_http_requests": 3},
            {"variant": "full", "actual_http_requests": None},
        ]
    )[0]
    assert result["total_http_attempts"] is None
    assert result["known_http_attempts_lower_bound"] == 3
    assert result["request_count_completeness"] == 0.5
