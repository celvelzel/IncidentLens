import pytest

from incident_lens.incidentbench.family_split import split_ids, validate_family_split


def row(incident, split, **overrides):
    return (
        dict(
            incident_id=incident,
            split=split,
            scenario_family_id=incident,
            source_blueprint_id=incident,
            near_duplicate_cluster_id=incident,
            counterfactual_pair_id=None,
        )
        | overrides
    )


@pytest.mark.parametrize(
    "key",
    [
        "scenario_family_id",
        "source_blueprint_id",
        "near_duplicate_cluster_id",
        "counterfactual_pair_id",
    ],
)
def test_relatives_never_cross_splits(key):
    cases = [
        row("incident_001", "dev", **{key: "shared"}),
        row("incident_002", "test", **{key: "shared"}),
    ]
    with pytest.raises(ValueError, match="cross"):
        validate_family_split(cases)


def test_honest_empty_test_and_sorted_ids():
    cases = [row("incident_003", "seed"), row("incident_001", "seed")]
    assert split_ids(cases) == {"seed": ["incident_001", "incident_003"], "dev": [], "test": []}


def test_duplicate_incident_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_family_split([row("incident_001", "seed"), row("incident_001", "seed")])
