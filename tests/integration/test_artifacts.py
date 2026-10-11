import json

import pytest

from incident_lens.artifacts import load_replay, save_run
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation


async def test_replay_roundtrip_without_provider(tmp_path, monkeypatch):
    state = await run_investigation("incident_001", MockProvider())
    save_run(state, tmp_path, "mock")

    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not call provider")

    monkeypatch.setattr(MockProvider, "structured_call", forbidden)
    trace, replayed = load_replay(tmp_path / "trace.json")
    assert replayed == state and trace["provider"] == "mock"
    assert (
        json.loads((tmp_path / "result.json").read_text())["supporting_evidence_ids"]
        == state.report.supporting_evidence_ids
    )
    assert "backend_pool_config_regression" in (tmp_path / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "bad", [[], {"schema_version": "v1"}, {"schema_version": "v1", "provider": "invented"}]
)
def test_replay_rejects_invalid_envelope_before_rendering(tmp_path, bad):
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_replay(path)


async def test_replay_rejects_private_oracle_objects(tmp_path):
    state = await run_investigation("incident_001", MockProvider())
    trace = save_run(state, tmp_path, "mock")
    for target in (trace, trace["state"]["events"][0]["details"]):
        target["ground_truth"] = {"canary": "private"}
        (tmp_path / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
        with pytest.raises(ValueError):
            load_replay(tmp_path / "trace.json")
        target.pop("ground_truth")
