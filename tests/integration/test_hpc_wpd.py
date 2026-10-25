"""Offline regressions for the separate HPC entry; no real provider calls."""
import importlib.util
import json
import shutil
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hpc_wpd", ROOT / "hpc/run_wpd.py")
hpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hpc)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "configs/wp_d", tmp_path / "configs/wp_d")
    shutil.copytree(ROOT / "data/incidentbench_v16_dev", tmp_path / "data/incidentbench_v16_dev")
    shutil.copy(ROOT / "requirements.lock", tmp_path / "requirements.lock")
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    shutil.copytree(ROOT / "hpc", tmp_path / "hpc")
    (tmp_path / "analysis/wp_d").mkdir(parents=True)
    shutil.copy(ROOT / "analysis/wp_d/serve_bridge_response.py",
                tmp_path / "analysis/wp_d/serve_bridge_response.py")
    monkeypatch.setattr(hpc, "PROJECT", tmp_path)
    monkeypatch.setattr(hpc, "clean_checkout", lambda: "test-commit")
    monkeypatch.setenv("INCIDENT_LENS_BASE_URL", "https://discovery-api.intern-ai.org.cn/v1")
    monkeypatch.setenv("INCIDENT_LENS_API_KEY", "test-secret-never-save")
    monkeypatch.delenv("INCIDENT_LENS_MODEL", raising=False)
    monkeypatch.delenv("INCIDENT_LENS_THINKING", raising=False)
    return tmp_path


def test_initialize_preserves_original_and_freezes_new_session(sandbox):
    before = {p: p.read_bytes() for p in (sandbox / "configs").rglob("*") if p.is_file()}
    root = hpc.initialize("atria-test", "Atria-Dawn", 2)
    session = hpc.validate(root)
    assert session["slots"] == 40
    protocol = hpc.read(root / "inputs/protocol.json")
    original = hpc.read(sandbox / "configs/wp_d/api-protocol.json")
    assert {k: v for k, v in protocol.items() if k not in {"jobs", "model_id", "protocol_id"}} == {
        k: v for k, v in original.items() if k not in {"jobs", "model_id", "protocol_id"}}
    assert all(p.read_bytes() == content for p, content in before.items())
    with pytest.raises(FileExistsError):
        hpc.initialize("atria-test", "Atria-Dawn", 2)
    (root / "inputs/runtime.yaml").write_text("tampered")
    with pytest.raises(ValueError, match="changed"):
        hpc.validate(root)


@pytest.mark.parametrize("run_id", ["../old", "/absolute", "bad/name", "", "a.b"])
def test_reject_unsafe_session_paths(run_id):
    with pytest.raises(ValueError):
        hpc.session_path(run_id)


def test_environment_rejects_wrong_provider_and_model(sandbox, monkeypatch):
    session = {"model_id": "Atria-Dawn"}
    monkeypatch.setenv("INCIDENT_LENS_BASE_URL", "https://other.example/v1")
    with pytest.raises(ValueError, match="original provider"):
        hpc.environment(session)
    monkeypatch.setenv("INCIDENT_LENS_BASE_URL", "https://discovery-api.intern-ai.org.cn/v1")
    monkeypatch.setenv("INCIDENT_LENS_MODEL", "wrong")
    with pytest.raises(ValueError, match="conflicts"):
        hpc.environment(session)


async def test_probe_uses_adapter_and_only_success_produces_readiness(sandbox, monkeypatch):
    from incident_lens.llm import provider as module
    original = module.RealChatProvider
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(module, "RealChatProvider", lambda *a, **kw: original(*a, **kw, client=client))
    root = hpc.initialize("probe-test", "Atria-Dawn", 2)
    await hpc.probe(root, hpc.validate(root))
    receipt = hpc.read(root / "readiness.json")
    assert receipt["provider_compatible"] is True
    assert receipt["actual_http_requests"] == 1
    assert requests[0]["model"] == "Atria-Dawn"
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert "test-secret" not in (root / "readiness.json").read_text()
    with pytest.raises(FileExistsError):
        await hpc.probe(root, hpc.validate(root))
    await client.aclose()


async def test_failed_probe_cannot_prepare_readiness(sandbox, monkeypatch):
    from incident_lens.llm import provider as module

    class FailedProvider:
        def __init__(self, *a, **kw):
            pass

        async def structured_call(self, *a):
            raise RuntimeError("test-secret-never-save")

    monkeypatch.setattr(module, "RealChatProvider", FailedProvider)
    root = hpc.initialize("bad-probe", "Atria-Dawn", 2)
    with pytest.raises(RuntimeError, match="no batch"):
        await hpc.probe(root, hpc.validate(root))
    assert not (root / "readiness.json").exists()
    records = list(root.glob("probe-failed-*.json"))
    assert len(records) == 1
    assert "test-secret" not in records[0].read_text()


def test_fresh_preparation_contains_all_40_slots(sandbox, monkeypatch):
    from scripts import run_wpd_batch as runner
    monkeypatch.setattr(runner, "PROJECT", sandbox)
    root = hpc.initialize("matrix", "Atria-Dawn", 2)
    monkeypatch.setenv("INCIDENT_LENS_MODEL", "Atria-Dawn")
    # Synthetic UNIT receipt only; never a live readiness claim.
    receipt = root / "unit-receipt.json"
    hpc.write(receipt, {"model_id": "Atria-Dawn", "response_format": "json_schema",
                        "thinking": "disabled", "provider_compatible": True})
    manifest = runner.frozen_inputs(root / "inputs/plan.json", receipt)
    assert len(manifest["order"]) == 40
    assert len({(r["incident"], r["variant"], r["repeat"]) for r in manifest["order"]}) == 40
    assert {r["variant"] for r in manifest["order"]} == set(runner.VARIANTS)
    assert {r["incident"] for r in manifest["order"]} == {
        f"incident_{i}" for i in range(3001, 3011)}
    assert manifest["max_concurrency"] == 2


def test_batch_resume_does_not_enable_automatic_retry(sandbox, monkeypatch):
    root = hpc.initialize("resume", "Atria-Dawn", 2)
    session = hpc.validate(root)
    endpoint = hpc.environment(session)
    hpc.write(root / "readiness.json", {"source_commit": "test-commit",
        "endpoint_sha256": hpc.hashlib.sha256(endpoint.encode()).hexdigest()})
    calls = []
    monkeypatch.setattr(hpc.subprocess, "call", lambda command, **kw: calls.append(command) or 0)
    assert hpc.batch(root, session, "execute", resume=True) == 0
    assert "--resume" in calls[0]
    assert "--retry-failed" not in calls[0]
    assert "--retry-interrupted" not in calls[0]
