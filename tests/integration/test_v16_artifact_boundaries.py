"""V1.6 public replay authorization and failure-retention boundaries."""

import copy
import json
import stat

import pytest
from starlette.testclient import TestClient

from incident_lens.artifacts import load_replay, save_run
from incident_lens.cli import main
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.web import server


@pytest.fixture
async def saved(tmp_path):
    state = await run_investigation("incident_001", MockProvider())
    trace = save_run(state, tmp_path / "run", "mock")
    return tmp_path / "run", trace, state


@pytest.mark.parametrize("mutation", ["missing", "failed", "foreign", "changed", "acl"])
async def test_replay_rejects_unobserved_or_unauthorized_evidence(saved, mutation):
    out, trace, _ = saved
    trace = copy.deepcopy(trace)
    events = trace["state"]["events"]
    if mutation == "missing":
        trace["state"]["events"] = [e for e in events if e["event_type"] != "TOOL_CALL"]
    else:
        tools = [e for e in events if e["event_type"] == "TOOL_CALL"]
        if mutation == "failed":
            for event in tools:
                event["details"]["result"].update(ok=False, error_code="FORBIDDEN")
        else:
            event = next(e for e in tools if e["details"]["result"]["records"])
            record = event["details"]["result"]["records"][0]
            if mutation == "foreign":
                record["incident_id"] = "incident_999"
            elif mutation == "changed":
                record["excerpt"] = "fabricated replacement"
            else:
                event["role"] = "coordinator"
    (out / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError):
        load_replay(out / "trace.json")


@pytest.mark.parametrize("field", ["true_primary_root", "acceptable_support_sets", "reviewer_ids"])
async def test_replay_rejects_nested_private_label_fragments(saved, field):
    out, trace, _ = saved
    trace["state"]["events"][0]["details"]["nested"] = {field: []}
    (out / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError, match="Evaluator-only"):
        load_replay(out / "trace.json")


async def test_existing_artifacts_are_preserved_and_cli_refuses_before_execution(saved, monkeypatch):
    out, _, state = saved
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("Existing output must be rejected before provider construction")

    monkeypatch.setattr("incident_lens.llm.mock.MockProvider", forbidden)
    assert main(["run", "--case", "incident_001", "--out", str(out)]) == 2
    with pytest.raises(FileExistsError):
        save_run(state, out, "mock")
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}


def test_report_download_rechecks_sibling_confinement(tmp_path, monkeypatch):
    root = tmp_path / "results"
    run = root / "run"
    run.mkdir(parents=True)
    (run / "trace.json").write_text("{}")
    (run / "report.md").write_text("ordinary public report")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "RESULTS_ROOT", root)
    actual_lstat = type(run).lstat

    class ReparseInfo:
        st_mode = stat.S_IFREG
        st_file_attributes = 0x400

    def linked_report(path, *args, **kwargs):
        if path == run / "report.md":
            return ReparseInfo()
        return actual_lstat(path, *args, **kwargs)

    # Simulate Windows reparse attributes even when the host cannot create links.
    monkeypatch.setattr(type(run), "lstat", linked_report)
    with TestClient(server.app) as client:
        response = client.get("/api/download", params={"path": "results/run/trace.json",
                                                       "kind": "report"})
    assert response.status_code == 403
    assert "ordinary public report" not in response.text
