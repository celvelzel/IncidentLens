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


async def test_default_protocol_runs_genuine_graph_all_six(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from incident_lens.evaluation.active_evidence import runner
    from incident_lens.llm import MockProvider

    dataset = Path(__file__).resolve().parents[2] / "data" / "incidentbench_v1"
    root, public, cases = runner.load_cases(dataset, "seed")
    # Bounded public-case smoke; run genuine Graph with the full public dataset lock.
    monkeypatch.setattr(runner, "load_cases", lambda *args: (root, public, cases[:1]))
    rows = await runner.run_experiment(
        dataset, "seed", MockProvider, tmp_path / "out", ActiveProtocol()
    )
    assert len(rows) == 6
    assert {row["variant"] for row in rows} == set(VARIANTS)
    assert not any(row["failure_category"] for row in rows)
    raw = [
        json.loads(line) for line in (tmp_path / "out" / "raw-runs.jsonl").read_text().splitlines()
    ]
    by_variant = {run["variant"]: run for run in raw}
    assert not any(
        e["event_type"] == "ACTION_SELECTED" for e in by_variant["B1"]["state"]["events"]
    )
    assert {task["role"] for task in by_variant["B0"]["state"]["tasks"]} == {
        "logs",
        "metrics",
        "database",
        "changes",
    }
    for variant in ("B1c", "B2", "B3", "B4"):
        events = [
            e
            for e in by_variant[variant]["state"]["events"]
            if e["event_type"] == "ACTION_SELECTED"
        ]
        assert events and events[0]["details"]["selection"]["policy"] == VARIANTS[variant]
