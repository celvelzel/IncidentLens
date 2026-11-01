"""Canonical runtime names, their frozen historical aliases and the display labels."""

import pytest

from incident_lens.artifacts import validate_metadata
from incident_lens.evaluation.metrics import VARIANTS, aggregate
from incident_lens.incidentbench.schemas import VARIANTS as BENCHMARK_VARIANTS
from incident_lens.variants import (
    BENCHMARK_TO_RUNTIME,
    DISPLAY_LABELS,
    RUNTIME_VARIANTS,
    canonical_name,
    display_label,
    is_known_variant,
    normalize_variant,
)


def test_dynamic_is_the_primary_runtime_name():
    assert RUNTIME_VARIANTS == ("single", "fixed", "dynamic", "full")
    assert VARIANTS == RUNTIME_VARIANTS
    assert DISPLAY_LABELS["dynamic"] == "Dynamic"
    assert DISPLAY_LABELS["full"] == "Dynamic (with verifier)"


def test_legacy_alias_resolves_to_dynamic():
    assert normalize_variant("dynamic_no_verifier") == "dynamic"
    assert normalize_variant("no_verifier") == "dynamic"
    assert canonical_name("dynamic_no_verifier") == "dynamic"
    assert is_known_variant("dynamic_no_verifier")
    assert display_label("dynamic_no_verifier") == display_label("dynamic")


def test_unknown_variant_is_rejected_at_runtime_but_not_folded_when_grouping():
    with pytest.raises(ValueError, match="Unknown variant"):
        normalize_variant("unrecorded")
    assert canonical_name("unrecorded") == "unrecorded"
    assert not is_known_variant("unrecorded")


def test_benchmark_conditions_stay_frozen_and_map_to_runtime_names():
    # Saved protocol.json files validate against these names; changing them
    # would break every frozen batch.
    assert BENCHMARK_VARIANTS == (
        "strong_single_equivalent_tools",
        "fixed_four_equivalent_tools",
        "dynamic_no_verifier",
        "full",
    )
    assert BENCHMARK_TO_RUNTIME["dynamic_no_verifier"] == "dynamic"
    assert set(BENCHMARK_TO_RUNTIME) == set(BENCHMARK_VARIANTS)


@pytest.mark.parametrize("variant", ["dynamic", "dynamic_no_verifier"])
def test_saved_traces_still_validate(variant):
    validate_metadata({"schema_version": "v1", "provider": "mock", "variant": variant,
                       "cache_mode": "off"})


def test_aggregation_reports_one_dynamic_group_for_both_spellings():
    rows = [
        dict(variant="dynamic", source="mock", split="dev", status="RESOLVED",
             root_cause_correct=True, correct_abstention=None, misleading_correct=None,
             citation_count=1, valid_citation_count=1),
        dict(variant="dynamic_no_verifier", source="mock", split="dev", status="RESOLVED",
             root_cause_correct=True, correct_abstention=None, misleading_correct=None,
             citation_count=1, valid_citation_count=1),
    ]
    groups = aggregate(rows)
    assert [g["variant"] for g in groups] == ["dynamic"]
    assert groups[0]["runs"] == 2
