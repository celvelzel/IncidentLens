"""Regression tests for the OhMyGPT adapter's physical request accounting."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError
from pydantic import BaseModel

from incident_lens.artifacts import validate_metadata
from incident_lens.llm.ohmygpt import OhMyGPTProvider, ohmygpt_async_client
from incident_lens.llm.provider import ProviderError


class Answer(BaseModel):
    answer: str


def response(answer="ok", *, tokens=17):
    return SimpleNamespace(
        model_dump=lambda mode: {
            "choices": [
                {"message": {"content": json.dumps({"answer": answer})}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": tokens - 10, "total_tokens": tokens},
        }
    )


def transport_failure():
    return APIConnectionError(
        request=httpx.Request("POST", "https://api.ohmygpt.com/v1/chat/completions")
    )


def provider_with(fake, guard=None, reconciler=None, stop_guard=None):
    provider = OhMyGPTProvider(api_key="local-test-key", client=fake)
    provider.request_guard = guard
    provider.request_reconciler = reconciler
    provider.stop_guard = stop_guard
    return provider


@pytest.mark.asyncio
async def test_retry_counts_every_physical_request_and_keeps_unknown_tokens(monkeypatch):
    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("incident_lens.llm.ohmygpt.asyncio.sleep", no_delay)
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(side_effect=[transport_failure(), response()])
        ))
    )
    permissions, reconciled, stopped = [], [], []

    def guard():
        permissions.append("permit")
        return len(permissions)

    p = provider_with(
        fake,
        guard=guard,
        reconciler=lambda permit, count: reconciled.append((permit, count)),
        stop_guard=lambda: stopped.append(True),
    )
    answer, usage = await p.structured_call("coordinator", "system", {}, Answer)
    assert answer.answer == "ok"
    assert fake.chat.completions.create.await_count == 2
    assert len(permissions) == len(stopped) == 2
    assert reconciled == [(1, None), (2, 17)]
    assert usage["llm_calls"] == usage["actual_http_requests"] == 2
    assert usage["transport_retries"] == 1
    assert len(usage["request_usage"]) == 2
    assert usage["requests_without_token_usage"] == 1
    assert usage["tokens_complete"] is False
    assert usage["total_tokens"] is None
    assert usage["measured_total_tokens"] == 17


@pytest.mark.asyncio
async def test_request_budget_denies_retry_without_dispatch(monkeypatch):
    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("incident_lens.llm.ohmygpt.asyncio.sleep", no_delay)
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(side_effect=[transport_failure(), response()])
        ))
    )
    checks, reconciled = [], []

    def guard():
        checks.append(True)
        if len(checks) == 2:
            raise RuntimeError("budget exceeded")
        return 123

    p = provider_with(fake, guard=guard,
                      reconciler=lambda permit, count: reconciled.append((permit, count)))
    with pytest.raises(ProviderError, match="REQUEST_BUDGET_EXCEEDED") as caught:
        await p.structured_call("coordinator", "system", {}, Answer)
    usage = caught.value.usage
    assert fake.chat.completions.create.await_count == 1
    assert len(checks) == 2
    assert reconciled == [(123, None)]
    assert usage["llm_calls"] == usage["actual_http_requests"] == 1
    assert len(usage["request_usage"]) == 1
    assert usage["tokens_complete"] is False


@pytest.mark.asyncio
async def test_retry_exhaustion_is_recorded_and_reconciled(monkeypatch):
    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("incident_lens.llm.ohmygpt.asyncio.sleep", no_delay)
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(side_effect=[transport_failure() for _ in range(3)])
        ))
    )
    reconciled = []
    p = provider_with(fake, guard=lambda: "permit",
                      reconciler=lambda permit, count: reconciled.append((permit, count)))
    with pytest.raises(ProviderError, match="PROVIDER_TRANSPORT_ERROR") as caught:
        await p.structured_call("coordinator", "system", {}, Answer)
    usage = caught.value.usage
    assert fake.chat.completions.create.await_count == 3
    assert usage["llm_calls"] == usage["actual_http_requests"] == 3
    assert usage["transport_retries"] == 2
    assert len(usage["request_usage"]) == len(reconciled) == 3
    assert usage["requests_without_token_usage"] == 3
    assert all(count is None for _, count in reconciled)


def test_sdk_automatic_retries_are_disabled():
    client = ohmygpt_async_client(api_key="local-test-key")
    assert client.max_retries == 0


@pytest.mark.parametrize("provider", ["mock", "real", "ohmygpt"])
def test_saved_trace_provider_names_are_valid(provider):
    validate_metadata({
        "schema_version": "v1", "provider": provider,
        "variant": "dynamic", "cache_mode": "off",
    })


def test_unknown_saved_trace_provider_is_rejected():
    with pytest.raises(ValueError, match="Invalid trace provider"):
        validate_metadata({
            "schema_version": "v1", "provider": "wrong",
            "variant": "dynamic", "cache_mode": "off",
        })
