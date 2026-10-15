import pytest

from incident_lens.evaluation.v16 import quality_row, summarize, write_companion


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


def test_companion_completed_resume_preserves_bytes_and_refuses_mismatch(tmp_path):
    rows = [dict(run_key="one", variant="full", incident_id="case", source="mock",
                 technical_completion=True)]
    result = write_companion(tmp_path, rows)
    before = (tmp_path / "v16-metrics.json").read_bytes()
    assert write_companion(tmp_path, rows) == result
    rows[0]["technical_completion"] = False
    with pytest.raises(ValueError, match="retained unchanged"):
        write_companion(tmp_path, rows)
    assert (tmp_path / "v16-metrics.json").read_bytes() == before


def test_failed_stop_does_not_become_false_rca_or_disappear_from_denominator():
    rows = [scored(), scored(technical_completion=False, runtime_failure=True,
                             root_cause_correct=False, resolved=True)]
    assert rows[1]["false_resolution"] is None
    result = summarize(rows)[0]["false_resolution_rate"]
    assert result == {"numerator": None, "denominator": 2, "rate": None,
                      "unknown_n": 1, "known_false_resolution_n": 0}
    assert scored(identifiable=False, technical_completion=False, resolved=True)[
        "false_resolution"] is True


async def test_cli_completed_resume_validates_existing_companion(tmp_path, monkeypatch):
    import json
    import runpy
    from pathlib import Path
    from types import SimpleNamespace

    script = runpy.run_path(str(Path("scripts/run_incidentbench.py")))
    run = script["run"]
    rows = [dict(run_key="one", variant="full", incident_id="case", source="mock",
                 technical_completion=True)]

    async def completed(*args, **kwargs):
        assert kwargs["resume"] is True
        return rows

    monkeypatch.setitem(run.__globals__, "load_cases", lambda *args: (None, None, ["case"]))
    monkeypatch.setitem(run.__globals__, "run_experiment", completed)
    monkeypatch.setitem(run.__globals__, "load_dotenv", lambda *args, **kwargs: None)
    args = SimpleNamespace(out=tmp_path, resume=True, dataset=tmp_path, split="seed",
                           protocol=None, provider="mock", protocol_lock=None, oracle_root=None)
    write_companion(tmp_path, rows)
    before = (tmp_path / "v16-metrics.json").read_bytes()
    await run(args)
    assert (tmp_path / "v16-metrics.json").read_bytes() == before
    (tmp_path / "v16-metrics.json").write_text(json.dumps({"corrupted": True}))
    with pytest.raises(ValueError, match="retained unchanged"):
        await run(args)
    assert json.loads((tmp_path / "v16-metrics.json").read_text()) == {"corrupted": True}
