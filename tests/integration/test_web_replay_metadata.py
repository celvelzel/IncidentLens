"""Read-only replay metadata is allowlisted and bound to public saved artifacts."""
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from incident_lens.web import server


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    trace = json.loads((Path(__file__).parents[1] / "web/fixtures/mock-success.json").read_text())
    trace.update(provider="real", model_id="recorded-test-model")
    run = tmp_path / "results/recorded"
    run.mkdir(parents=True)
    (run / "trace.json").write_text(json.dumps(trace))
    (run / "result.json").write_text(json.dumps(trace["state"]["report"]))
    scope = {"incident_id": trace["state"]["incident_id"], "variant": trace["variant"],
             "protocol": {"provider_id": "real", "model_id": "recorded-test-model",
                          "protocol_id": "offline-test", "private_root": "NEVER_RETURN"},
             "source_commit": "test-commit", "private_root": "NEVER_RETURN"}
    (run / "scope.json").write_text(json.dumps(scope))
    (run / "verification.json").write_text(json.dumps({"source_unchanged": False,
        "source_drift": ["src/example.py"], "protocol_valid": True,
        "private_oracle": {"secret": "NEVER_RETURN"}}))
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(server, "_trace_cache", {})
    with TestClient(server.app) as client:
        yield client, run


def test_saved_metadata_is_allowlisted_and_replay_never_executes(recorded, monkeypatch):
    client, _ = recorded
    def forbidden(*args, **kwargs):
        pytest.fail("Replay must not construct a provider or run a graph")
    monkeypatch.setattr("incident_lens.orchestration.graph.run_investigation", forbidden)
    monkeypatch.setattr("incident_lens.llm.provider.RealChatProvider", forbidden)
    response = client.post("/api/replay", json={"path": "results/recorded/trace.json"})
    assert response.status_code == 200
    assert "NEVER_RETURN" not in response.text
    meta = response.json()["replay_metadata"]
    assert meta["verification"]["source_unchanged"] is False
    assert meta["protocol"]["protocol_id"] == "offline-test"
    assert meta["snapshot"] == "final_artifact_metadata"


@pytest.mark.parametrize("name", ["scope.json", "result.json", "verification.json"])
def test_corrupt_companion_does_not_break_trace_or_claim_verified_metadata(recorded, name):
    client, run = recorded
    (run / name).write_text("{broken")
    response = client.post("/api/replay", json={"path": "results/recorded/trace.json"})
    assert response.status_code == 200
    assert "verification" not in response.json()["replay_metadata"]
    assert response.json()["replay_metadata"]["warnings"]


def test_mismatched_scope_or_result_is_not_displayed_as_verified(recorded):
    client, run = recorded
    scope = json.loads((run / "scope.json").read_text())
    scope["incident_id"] = "incident_999"
    (run / "scope.json").write_text(json.dumps(scope))
    meta = client.post("/api/replay", json={"path": "results/recorded/trace.json"}).json()["replay_metadata"]
    assert "verification" not in meta
    assert "protocol" not in meta


def test_changed_additive_assessment_is_not_accepted_as_matching_companion(recorded):
    client, run = recorded
    result = json.loads((run / "result.json").read_text())
    result["assessment_basis"] = ["Altered companion assessment"]
    (run / "result.json").write_text(json.dumps(result))
    meta = client.post("/api/replay", json={"path": "results/recorded/trace.json"}).json()["replay_metadata"]
    assert "verification" not in meta
    assert meta["warnings"]


@pytest.mark.parametrize("content", ["{", "[]", "null", "{}"])
def test_missing_or_corrupt_trace_is_a_controlled_error(recorded, content):
    client, run = recorded
    (run / "trace.json").write_text(content)
    assert client.post("/api/replay", json={"path": "results/recorded/trace.json"}).status_code == 400
    (run / "trace.json").unlink()
    assert client.post("/api/replay", json={"path": "results/recorded/trace.json"}).status_code == 400


def test_unsafe_companion_is_not_read(recorded, monkeypatch):
    client, _ = recorded
    original = server._resolve_download_file
    def checked(path):
        if path.name == "scope.json":
            raise PermissionError("simulated reparse/link boundary")
        return original(path)
    monkeypatch.setattr(server, "_resolve_download_file", checked)
    meta = client.post("/api/replay", json={"path": "results/recorded/trace.json"}).json()["replay_metadata"]
    assert "verification" not in meta
    assert any("unsafe" in warning for warning in meta["warnings"])
