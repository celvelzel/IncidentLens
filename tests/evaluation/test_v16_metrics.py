from incident_lens.evaluation.v16 import quality_row, summarize


def scored(**changes):
    row = dict(run_key="case.full.0", variant="full", incident_id="case",
               technical_completion=True, runtime_failure=False, identifiable=True,
               root_cause_correct=True, resolved=True, human_grounded_success=None)
    row.update(changes)
    return quality_row(row)


def test_match_does_not_imply_semantic_support():
    summary = summarize([scored()])[0]
    assert summary["mechanism_service_match_rate"]["rate"] == 1
    assert summary["root_cause_correct_rate"] == {
        "numerator": None, "denominator": 1, "reviewed_n": 0, "rate": None}


def test_failures_remain_in_all_attempt_and_labelled_denominators():
    failed = scored(technical_completion=False, runtime_failure=True,
                    root_cause_correct=False, resolved=False,
                    termination_reason="BUDGET_EXHAUSTED", correct_abstention=False)
    summary = summarize([scored(), failed])[0]
    assert summary["technical_completion_rate"]["rate"] == .5
    assert summary["mechanism_service_match_rate"]["denominator"] == 2
    assert summary["budget_exhausted_rate"]["rate"] == .5
    assert summary["runtime_failure_rate"]["rate"] == .5


def test_unscored_is_null_and_false_resolution_stratified():
    unknown = scored(identifiable=None, root_cause_correct=None)
    assert unknown["false_resolution"] is None
    missing = scored(identifiable=False, root_cause_correct=None)
    wrong = scored(root_cause_correct=False)
    result = summarize([unknown, missing, wrong])[0]
    assert result["false_resolution_rate"] == {"numerator": 2, "denominator": 2, "rate": 1}
    assert result["false_resolution_missing_rate"]["denominator"] == 1
    assert result["false_resolution_identifiable_rate"]["denominator"] == 1


def test_partial_review_cannot_replace_primary_denominator():
    rows = [scored(human_grounded_success=True), scored()]
    result = summarize(rows)[0]["root_cause_correct_rate"]
    assert result["reviewed_n"] == 1 and result["denominator"] == 2
    assert result["rate"] is None


def test_complete_review_can_establish_supported_quality():
    rows = [scored(human_grounded_success=True), scored(human_grounded_success=False)]
    assert summarize(rows)[0]["root_cause_correct_rate"]["rate"] == .5
