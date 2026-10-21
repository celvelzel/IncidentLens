"""Prepared regressions for the next authorized offline run; not yet executed."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from incident_lens.evaluation.run_io import atomic_bytes
from scripts.retest_subagent_bridge import request_digest


def helper():
    path = Path(__file__).resolve().parents[2] / "analysis/wp_d/serve_bridge_response.py"
    spec = importlib.util.spec_from_file_location("wpd_bridge_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_fixture(tmp_path):
    bridge = tmp_path / "bridge"
    requests = bridge / "requests"
    requests.mkdir(parents=True)
    request = {"session_id": "session", "request_id": "req-0001",
               "messages": [{"role": "user", "content": "中文🙂" * 30}]}
    request["request_sha256"] = request_digest(request)
    path = requests / "req-0001.json"
    path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    serve = tmp_path / "serve"
    serve.mkdir()
    return bridge, serve, path


def test_atomic_exclusive_publication_keeps_original(tmp_path):
    path = tmp_path / "response.json"
    atomic_bytes(path, b"first", exclusive=True)
    with pytest.raises(FileExistsError):
        atomic_bytes(path, b"second", exclusive=True)
    assert path.read_bytes() == b"first"


def test_bridge_helper_preserves_crlf_and_whitespace(tmp_path):
    bridge, serve, _ = request_fixture(tmp_path)
    raw = b'  {"answer": true}\r\n'
    (serve / "req-0001.raw.json").write_bytes(raw)
    module = helper()
    module.build(bridge, serve, ["req-0001"])
    path = bridge / "responses/req-0001.json"
    assert json.loads(path.read_bytes())["content"].encode() == raw
    original = path.read_bytes()
    module.build(bridge, serve, ["req-0001"])
    assert path.read_bytes() == original
    (serve / "req-0001.raw.json").write_bytes(b'{}')
    with pytest.raises(FileExistsError):
        module.build(bridge, serve, ["req-0001"])
    assert path.read_bytes() == original


def test_modified_request_digest_is_refused(tmp_path):
    bridge, serve, path = request_fixture(tmp_path)
    request = json.loads(path.read_bytes())
    request["messages"][0]["content"] = "tampered"
    path.write_text(json.dumps(request), encoding="utf-8")
    (serve / "req-0001.raw.json").write_bytes(b'{}')
    with pytest.raises(ValueError, match="digest"):
        helper().build(bridge, serve, ["req-0001"])


def test_chunk_manifest_reconstructs_exact_messages(tmp_path):
    _, _, path = request_fixture(tmp_path)
    parts = helper().prepare(path, tmp_path / "parts", 41)
    joined = b"".join(part.read_bytes() for part, _ in parts)
    manifest = json.loads((tmp_path / "parts/req-0001.manifest.json").read_bytes())
    assert json.loads(joined) == json.loads(path.read_bytes())["messages"]
    assert hashlib.sha256(joined).hexdigest() == manifest["messages_sha256"]
    assert all(size <= 41 for _, size in parts)


@pytest.mark.parametrize("size", [0, 1, 3, -1])
def test_too_small_utf8_chunk_is_refused(size):
    with pytest.raises(ValueError):
        helper()._chunks("🙂", size)


async def test_task_schema_rejects_role_allowed_but_task_forbidden_tool():
    from incident_lens.agents.service import plan_tools

    class Endpoint:
        async def structured_call(self, role, system_prompt, payload, output_model):
            assert payload["effective_allowed_tools"] == ["query_metrics"]
            assert set(payload["tool_argument_schemas"]) == {"query_metrics"}
            # The provider adapter must see the invalidity to perform bounded repair.
            return output_model.model_validate({"calls": [{"tool_name": "get_dependencies", "args": {}}]}), {}

    with pytest.raises(ValueError):
        await plan_tools(Endpoint(), {"role": "metrics", "allowed_tools": ["query_metrics", "get_dependencies"]},
                         {"role": "metrics", "allowed_tools": ["query_metrics"]}, {"services": []}, {})


def test_resume_refuses_incomplete_completed_receipt_without_starting_child(tmp_path, monkeypatch):
    from argparse import Namespace

    from scripts import run_wpd_batch as batch

    key = {"incident": "incident_1001", "variant": "full", "repeat": 0}
    state = {"slots": {"slot-001": [{"path": "runs/slot-001/attempt-001", "status": "completed",
                                    "key": key, "artifacts": {}}]}}
    (tmp_path / "batch-state.json").write_text(json.dumps(state), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("child must not start during receipt rejection")

    monkeypatch.setattr(batch.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="complete artifact receipt"):
        batch.execute(Namespace(out=tmp_path), {"plan": {"mode": "bridge"}, "order": [key]})


def test_resume_refuses_nonprefix_schedule_without_starting_child(tmp_path, monkeypatch):
    from argparse import Namespace

    from scripts import run_wpd_batch as batch

    (tmp_path / "batch-state.json").write_text(json.dumps({"slots": {"slot-002": []}}), encoding="utf-8")
    with pytest.raises(ValueError, match="prefix"):
        batch.execute(Namespace(out=tmp_path), {"plan": {"mode": "bridge"}, "order": [{"incident": "incident_1001"}]})
