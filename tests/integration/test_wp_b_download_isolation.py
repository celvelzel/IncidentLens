"""Downloads share replay's oracle isolation and derive reports from valid state."""

import json

import pytest
from starlette.testclient import TestClient

from incident_lens.artifacts import save_run
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.web import server


@pytest.mark.parametrize("kind", ["trace", "report"])
async def test_download_rejects_private_trace(tmp_path, monkeypatch, kind):
    state = await run_investigation("incident_001", MockProvider())
    out = tmp_path / "results/run"
    trace = save_run(state, out, "mock")
    trace["state"]["events"][0]["details"]["benchmark_oracle"] = "PRIVATE_SENTINEL"
    (out / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "RESULTS_ROOT", tmp_path / "results")
    with TestClient(server.app) as client:
        result = client.get("/api/download", params={"path": "results/run/trace.json", "kind": kind})
    assert result.status_code == 400
    assert "PRIVATE_SENTINEL" not in result.text


async def test_download_regenerates_report_from_validated_trace(tmp_path, monkeypatch):
    state = await run_investigation("incident_001", MockProvider())
    out = tmp_path / "results/run"
    save_run(state, out, "mock")
    (out / "report.md").write_text("PRIVATE_SENTINEL", encoding="utf-8")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "RESULTS_ROOT", tmp_path / "results")
    with TestClient(server.app) as client:
        result = client.get("/api/download", params={"path": "results/run/trace.json", "kind": "report"})
    assert result.status_code == 200
    assert "PRIVATE_SENTINEL" not in result.text
    assert "incident_001" in result.text
