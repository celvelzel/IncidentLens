"""Offline evidence cannot silently become a live E2E acceptance result."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("v16_preflight", PROJECT / "scripts/v16_e2e_preflight.py")
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


@pytest.fixture
async def artifact(tmp_path):
    state = await run_investigation("incident_001", MockProvider())
    save_run(state, tmp_path, "real")  # Deliberately misleading envelope.
    (tmp_path / "scope.json").write_text(json.dumps({
        "retest_source_sha256": retest_snapshot(PROJECT),
    }))
    (tmp_path / "verification.json").write_text(json.dumps({
        "source_unchanged": True, "source_drift": [],
    }))
    return tmp_path


def write_trace(path, trace):
    (path / "trace.json").write_text(json.dumps(trace))
    (path / "result.json").write_text(json.dumps(trace["state"]["report"]))


@pytest.mark.parametrize("origin", ["mock", "MockTransport", "FileQueueBridge", "continuation"])
async def test_real_envelope_does_not_authenticate_live_execution(artifact, origin):
    trace = preflight.read_json(artifact / "trace.json")
    if origin == "mock":
        trace["provider"] = "mock"
        write_trace(artifact, trace)
    scope = preflight.read_json(artifact / "scope.json")
    scope["execution_origin"] = origin
    (artifact / "scope.json").write_text(json.dumps(scope))
    result = preflight.inspect_artifact(artifact, PROJECT, "positive")
    assert not result["live_verified"] and not result["g1_accepted"]
    assert result["semantic_review"] is None


async def test_source_change_rejects_technical_candidate(artifact):
    scope = preflight.read_json(artifact / "scope.json")
    scope["retest_source_sha256"]["src/removed.py"] = "old"
    (artifact / "scope.json").write_text(json.dumps(scope))
    result = preflight.inspect_artifact(artifact, PROJECT, "positive")
    assert "source_drift_or_missing_lock" in result["blockers"]
    assert not result["technical_matches_expectation"]


@pytest.mark.parametrize("fault", ["missing_ack", "post_stop_call", "runtime_error"])
async def test_stop_and_technical_failures_rejected(artifact, fault):
    trace = preflight.read_json(artifact / "trace.json")
    events = trace["state"]["events"]
    if fault == "missing_ack":
        events[:] = [event for event in events if event["event_type"] != "STOP_ACK"]
        request = next(e for e in events if e["event_type"] == "WORKFLOW_STOP_REQUESTED")
        request["details"]["required_roles"] = ["logs"]
    else:
        event = copy.deepcopy(events[-1])
        event["event_id"] = "injected"
        event["event_type"] = "LLM_CALL" if fault == "post_stop_call" else "RUNTIME_ERROR"
        events.append(event)
    write_trace(artifact, trace)
    result = preflight.inspect_artifact(artifact, PROJECT, "positive")
    assert not result["technical_matches_expectation"]
    assert not result["termination"]["protocol_valid"]


async def test_resolved_is_not_correct_abstention(artifact):
    result = preflight.inspect_artifact(artifact, PROJECT, "negative")
    assert "unexpected_diagnosis_outcome" in result["blockers"]


def test_missing_artifacts_fail_closed(tmp_path):
    result = preflight.inspect_artifact(tmp_path, PROJECT, "positive")
    assert len(result["missing"]) == 5
    assert not result["g1_accepted"]


def test_formal_protocol_rejected_before_dataset_read(tmp_path):
    from incident_lens.incidentbench.schemas import ExperimentProtocol

    # Use the checked-in protocol shape, changing only the prohibited mode.
    protocol = ExperimentProtocol(provider_id="real", model_id="test", formal=True)
    path = tmp_path / "protocol.json"
    path.write_text(protocol.model_dump_json())
    with pytest.raises(ValueError):
        preflight.prepare_inputs(tmp_path / "absent", path, PROJECT, tmp_path)


@pytest.mark.parametrize("variant", ["single", "fixed", "dynamic_no_verifier", "full"])
async def test_retest_runner_preserves_variant_metadata(tmp_path, monkeypatch, variant):
    """Exercise the existing runner with injected offline dependencies, no HTTP client."""
    import argparse
    from types import SimpleNamespace

    from incident_lens.incidentbench.schemas import ExperimentProtocol

    spec = importlib.util.spec_from_file_location("retest", PROJECT / "scripts/retest_live_provider_fix.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    state = await run_investigation("incident_001", MockProvider())
    monkeypatch.setattr(runner, "load_dotenv", lambda *a, **k: None)
    for key, value in {"BASE_URL": "https://unused.invalid", "API_KEY": "offline-fixture",
                       "MODEL": "offline-fixture"}.items():
        monkeypatch.setenv(f"INCIDENT_LENS_{key}", value)
    monkeypatch.setattr(runner, "RealChatProvider", lambda *a, **k: None)
    monkeypatch.setattr(runner, "MeasuredProvider", lambda *a: SimpleNamespace(model_parameters={}, calls=[]))
    monkeypatch.setattr(runner, "usage_metrics", lambda *a: {
        "token_usage_by_role": {}, "token_usage_basis": "offline_fixture",
    })
    monkeypatch.setattr(runner, "EvidenceProvider", lambda *a: SimpleNamespace(dataset_revision="fixture"))

    async def investigate(*args, **kwargs):
        return state

    monkeypatch.setattr(runner, "run_investigation", investigate)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(ExperimentProtocol(provider_id="real", model_id="offline-fixture").model_dump_json())
    output = tmp_path / "output"
    await runner.run(argparse.Namespace(protocol=protocol, dataset=tmp_path,
                                        out=output, incident="incident_001", variant=variant))
    assert preflight.read_json(output / "trace.json")["variant"] == variant
    measured = preflight.read_json(output / "measured-usage.json")
    assert measured == {"schema_version": 1, "calls": [], "token_usage_by_role": {},
                        "token_usage_basis": "offline_fixture"}
