import pytest

from incident_lens.incidentbench.citation_review import (
    merge_reviews,
    prepare_review_bundle,
    review_coverage,
    validate_truth_reviews,
)


def record(reviewer, label="SUPPORTED"):
    return {
        "claim_id": "c1",
        "reviewer_id": reviewer,
        "review_label": label,
        "source": "human",
        "rationale": "actual evidence explanation",
        "reviewed_at": "2026-10-13T00:00:00Z",
    }


def test_pending_is_unknown():
    bundle = [{"claim_id": "c1"}]
    coverage = review_coverage(bundle, merge_reviews(bundle, []))
    assert coverage["human_support_rate"] is None
    assert coverage["coverage"] == 0


def test_duplicate_reviews_do_not_inflate():
    bundle = [{"claim_id": "c1"}]
    merged = merge_reviews(bundle, [record("a"), record("a"), record("b")])
    coverage = review_coverage(bundle, merged * 2)
    assert coverage["reviewed_claims"] == 1
    assert coverage["human_support_rate"] == 1


def test_conflict_pending_until_independent_adjudication():
    bundle = [{"claim_id": "c1"}]
    records = [record("a"), record("b", "INSUFFICIENT")]
    assert merge_reviews(bundle, records)[0]["review_label"] is None
    with pytest.raises(ValueError):
        merge_reviews(bundle, records, [record("a")])
    result = merge_reviews(bundle, records, [record("c", "INSUFFICIENT")])
    assert review_coverage(bundle, result)["unsupported_claim_rate"] == 1


@pytest.mark.parametrize(
    "field,value",
    [("source", "ai"), ("reviewed_at", None), ("rationale", ""), ("claim_id", "foreign")],
)
def test_authentic_record_contract(field, value):
    item = record("a")
    item[field] = value
    with pytest.raises(ValueError):
        merge_reviews([{"claim_id": "c1"}], [item])


def test_export_anonymous_pending():
    bundle = prepare_review_bundle(
        [
            {
                "run_id": "secret_full",
                "variant": "full",
                "model_id": "model",
                "report": {"root_cause": {"service": "backend"}, "citations": []},
            }
        ]
    )
    assert bundle and bundle[0]["annotation_status"] == "pending"
    assert (
        "secret_full" not in str(bundle)
        and "variant" not in str(bundle)
        and "model_id" not in str(bundle)
    )


def test_truth_reviewer_ids_alone_not_acceptance():
    with pytest.raises(ValueError):
        validate_truth_reviews(
            {"incident_id": "incident_100", "reviewer_ids": ["a", "b"]}, {"reviews": []}
        )
