"""The bridge is untrusted development transport, never physical HTTP."""

import asyncio
import copy
import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.llm.provider import ProviderError, RealChatProvider
from scripts.retest_subagent_bridge import FileQueueBridgeProvider, _atomic_write


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    optional: list[str] = []


async def respond(bridge, contents, mutate=None):
    served = set()
    while len(served) < len(contents):
        for path in sorted(bridge.requests_dir.glob("*.json")):
            if path.name in served:
                continue
            request = json.loads(path.read_text())
            envelope = {k: request[k] for k in ("session_id", "request_id", "request_sha256")}
            envelope["content"] = contents[len(served)]
            if mutate:
                mutate(envelope)
            _atomic_write(bridge.responses_dir / path.name, json.dumps(envelope))
            served.add(path.name)
        await asyncio.sleep(0.001)


async def test_bridge_matches_http_prompt_schema_and_counts_no_http(tmp_path):
    bridge = FileQueueBridgeProvider(tmp_path / "queue", poll_interval=0.001)
    measured = MeasuredProvider(bridge)
    worker = asyncio.create_task(respond(bridge, ['{"answer":"ok","optional":[]}']))
    value, usage = await measured.structured_call("coordinator", "system", {"input": 1}, Output)
    await worker
    captured = []

    def http_response(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content":
            '{"answer":"ok","optional":[]}'}}], "usage": {"total_tokens": 1}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(http_response)) as client:
        real = RealChatProvider("https://fixture.invalid", "k", "m", client=client)
        await real.structured_call("coordinator", "system", {"input": 1}, Output)
    request = json.loads(next(bridge.requests_dir.glob("*.json")).read_text())
    assert request["messages"] == captured[0]["messages"]
    assert request["json_schema"] == captured[0]["response_format"]["json_schema"]["schema"]
    assert value.answer == "ok"
    assert usage["tokens_complete"] is False
    metrics = usage_metrics(measured, {"events": []})
    assert metrics["llm_requests"] == 1
    assert metrics["actual_http_requests"] == 0
    assert len(list(bridge.receipts_dir.glob("*.json"))) == 1


@pytest.mark.parametrize("field", ["session_id", "request_id", "request_sha256"])
async def test_stale_or_wrong_response_fails_closed_and_reconciles(tmp_path, field):
    bridge = FileQueueBridgeProvider(tmp_path / "queue", poll_interval=0.001)
    reconciled = []
    bridge.request_guard = lambda: "permit"
    bridge.request_reconciler = lambda permit, usage: reconciled.append((permit, usage))
    worker = asyncio.create_task(respond(bridge, ['{"answer":"bad"}'],
                                       lambda e: e.update({field: "wrong"})))
    with pytest.raises(ProviderError, match="BRIDGE_RESPONSE_MISMATCH") as exc:
        await bridge.structured_call("coordinator", "", {}, Output)
    await worker
    assert reconciled == [("permit", None)]
    assert exc.value.usage["llm_calls"] == 1
    assert not list(bridge.receipts_dir.glob("*.json"))


async def test_timeout_cancellation_and_stop_reconcile_usage(tmp_path):
    for mode in ("timeout", "cancel", "stop"):
        bridge = FileQueueBridgeProvider(tmp_path / mode, poll_interval=0.001, call_timeout=0.02)
        settled = []
        bridge.request_guard = lambda: "permit"
        bridge.request_reconciler = lambda p, u: settled.append((p, u))
        call = asyncio.create_task(bridge.structured_call("coordinator", "", {}, Output))
        while not list(bridge.requests_dir.glob("*.json")):
            await asyncio.sleep(0.001)
        if mode == "cancel":
            call.cancel()
        if mode == "stop":
            def stop():
                raise RuntimeError("stop")
            bridge.stop_guard = stop
        with pytest.raises((ProviderError, asyncio.CancelledError, RuntimeError)) as exc:
            await call
        assert settled == [("permit", None)]
        assert exc.value.usage["bridge_requests"] == 1
        assert not exc.value.usage["tokens_complete"]


async def test_invalid_output_gets_only_one_repair_with_http_repair_message(tmp_path):
    bridge = FileQueueBridgeProvider(tmp_path / "queue", poll_interval=0.001)
    worker = asyncio.create_task(respond(bridge, ['{}', '{}']))
    with pytest.raises(ProviderError, match="STRUCTURED_OUTPUT_INVALID") as exc:
        await bridge.structured_call("coordinator", "", {}, Output)
    await worker
    assert exc.value.usage["bridge_requests"] == 2
    request = json.loads((bridge.requests_dir / "req-0001-repair.json").read_text())
    assert request["messages"][-1] == {"role": "user", "content":
        "Return valid JSON matching the supplied schema. One repair only."}
    assert len(list(bridge.receipts_dir.glob("*.json"))) == 2


def test_reused_queue_and_invalid_timing_rejected(tmp_path):
    FileQueueBridgeProvider(tmp_path / "queue")
    with pytest.raises(FileExistsError):
        FileQueueBridgeProvider(tmp_path / "queue")
    for bad in (0, -1, float("inf"), float("nan"), True):
        with pytest.raises(ValueError):
            FileQueueBridgeProvider(tmp_path / "invalid", call_timeout=bad)


async def test_shallow_copied_bridge_uses_unique_request_ids(tmp_path):
    bridge = FileQueueBridgeProvider(tmp_path / "queue", poll_interval=0.001)
    worker = asyncio.create_task(respond(bridge, ['{"answer":"a"}', '{"answer":"b"}']))
    await asyncio.gather(*(copy.copy(bridge).structured_call("coordinator", "", {}, Output)
                           for _ in range(2)))
    await worker
    assert len(list(bridge.requests_dir.glob("*.json"))) == 2
