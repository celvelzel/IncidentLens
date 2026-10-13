"""Exercise the new Web API against public evidence without external model calls."""

import shutil

import pytest
from starlette.testclient import TestClient

from incident_lens.web import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    shutil.copytree(
        server.ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("private")
    )
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(server, "_trace_cache", {})
    with TestClient(server.app) as client:
        yield client


def test_web_serves_dashboard_assets_and_public_cases(client):
    assert client.get("/api/health").json() == {"ok": True}
    assert "IncidentLens" in client.get("/").text
    for path in ("/css/tokens.css", "/css/core.css", "/css/app.css", "/js/app.js"):
        assert client.get(path).status_code == 200
    cases = client.get("/api/cases").json()
    assert cases and cases[0]["incident_id"] == "incident_001"
    assert "root_cause_code" not in cases[0]


def test_web_mock_run_replay_and_download_without_reexecution(client, monkeypatch):
    response = client.post("/api/run", json={"incident_id": "incident_001"})
    assert response.status_code == 200
    result = response.json()
    assert result["trace"]["state"]["report"]["status"] == "RESOLVED"
    assert result["recorded"] is False
    assert client.get("/api/traces").json()[0]["path"] == result["path"]

    async def forbidden(*args, **kwargs):
        pytest.fail("Replay must not execute the investigation")

    monkeypatch.setattr("incident_lens.orchestration.graph.run_investigation", forbidden)
    replay = client.post("/api/replay", json={"path": result["path"]})
    assert replay.status_code == 200
    assert replay.json()["recorded"] is True
    assert replay.json()["trace"] == result["trace"]
    for kind in ("trace", "report"):
        download = client.get("/api/download", params={"path": result["path"], "kind": kind})
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]


@pytest.mark.parametrize("path", ["../trace.json", "data/trace.json", "results/report.md"])
def test_web_rejects_outside_paths_and_non_trace_files(client, path):
    assert client.post("/api/replay", json={"path": path}).status_code == 403
    assert client.get("/api/download", params={"path": path}).status_code == 403


def test_web_validates_requests_before_running(client):
    assert client.post("/api/run", json={"incident_id": "../private"}).status_code == 400
    assert (
        client.post("/api/run", json={"incident_id": "incident_001", "timeout": 0}).status_code
        == 400
    )
    assert client.post("/api/run", content="{").status_code == 400
