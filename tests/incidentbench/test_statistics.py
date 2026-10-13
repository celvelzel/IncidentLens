import pytest

from incident_lens.incidentbench.statistics import paired_comparison


def rows():
    return [
        dict(
            incident_id=f"case{i}",
            scenario_family_id=f"family{i // 2}",
            variant=v,
            repeat_id=r,
            root_cause_correct=bool(v == "full"),
            cohort="core",
        )
        for i in range(4)
        for v in ("full", "baseline")
        for r in range(3)
    ]


def test_repeats_average_before_family_resampling():
    result = paired_comparison(rows(), "baseline", samples=100)
    assert result["paired_n"] == 4
    assert result["family_n"] == 2
    assert result["difference"] == 1
    assert result["ci95"] == [1, 1]
    assert result["exact_discordance_p"] is None
    assert result["small_family_warning"] is True


def test_missing_repeat_and_duplicate_refuse():
    with pytest.raises(ValueError, match="missing paired"):
        paired_comparison(rows()[:-1], "baseline")
    with pytest.raises(ValueError, match="duplicate"):
        paired_comparison(rows() + rows()[:1], "baseline")


def test_no_labels_has_no_accuracy_claim():
    assert paired_comparison([], "baseline")["status"] == "no_scored_pairs"
