import pytest

from incident_lens.evaluation.active_evidence.statistics import analyze
from incident_lens.evaluation.active_evidence.variants import ActiveProtocol
from incident_lens.incidentbench.experiment import run_order


def row(variant, case="a", **extra):
    return dict(
        variant=variant,
        incident_id=case,
        repeat_id=0,
        scenario_family_id="family",
        source_blueprint_id="shared",
        cohort="core",
        root_cause_correct=None,
        actual_http_requests=3,
        total_tokens=None,
        **extra,
    )


def test_schedule_reproducible():
    p = ActiveProtocol()
    assert run_order(["a", "b"], p) == run_order(["a", "b"], p)
    assert len(run_order(["a", "b"], p)) == 12


def test_null_cost_and_single_cluster():
    result = analyze([row("B1"), row("B4")], samples=10)
    tokens = next(r for r in result if r["baseline"] == "B1" and r["metric"] == "total_tokens")
    assert tokens["paired_n"] == 0 and tokens["ci95"] is None
    requests = next(
        r for r in result if r["baseline"] == "B1" and r["metric"] == "actual_http_requests"
    )
    assert requests["difference"] == 0 and requests["ci95"] is None
    assert requests["ci_reason"] == "fewer_than_two_independent_source_clusters"


@pytest.mark.parametrize("values", [{"cache_mode": "semantic"}, {"jobs": 2}])
def test_fairness_rejects(values):
    with pytest.raises(ValueError):
        ActiveProtocol(**values)


def test_duplicate_repeat_refused():
    with pytest.raises(ValueError):
        analyze([row("B1"), row("B1"), row("B4"), row("B4")], samples=10)
