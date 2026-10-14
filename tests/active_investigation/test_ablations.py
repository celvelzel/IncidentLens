import pytest

from incident_lens.evaluation.active_evidence.variants import (
    VARIANTS,
    ActiveProtocol,
    workflow_values,
)
from incident_lens.orchestration.active_investigation.contracts import PolicyConfig


@pytest.mark.parametrize("variant,policy", list(VARIANTS.items()))
def test_real_mapping(variant, policy):
    values = workflow_values(variant, PolicyConfig())
    assert values["selection_policy"] == policy
    assert values["benchmark_fixed_four"] == (variant == "B0")
    assert values["remediation_enabled"] is False
    assert values["benchmark_rca"] and values["database_equivalent_tools"]


@pytest.mark.parametrize("variants", [["bad"], ["B1", "B1"], []])
def test_invalid_variants(variants):
    with pytest.raises(ValueError):
        ActiveProtocol(variants=variants)


def test_common_pool_config():
    config = PolicyConfig()
    values = [workflow_values(v, config) for v in ("B1c", "B2", "B3", "B4")]
    assert all(v["active_evidence_config"] is config for v in values)
    assert len({v["selection_policy"] for v in values}) == 4


def test_default_provider_model_matches():
    from incident_lens.llm import MockProvider

    assert ActiveProtocol().model_id == MockProvider.model_id
