import httpx
import pytest

from incident_lens.llm import MockProvider, ProviderError, RealChatProvider
from incident_lens.schemas import CoordinatorDecision


def valid():
    return '{"action":"ABSTAIN","reason":"missing","stop_reason":"missing"}'


@pytest.mark.asyncio
async def test_one_repair_measured_usage_and_json_schema():
    requests = []
    guard = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "invalid" if len(requests) == 1 else valid()}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        p = RealChatProvider("https://example.invalid/v1", "SECRET", "configured", client=client)
        p.request_guard = lambda: guard.append(True)
        result, usage = await p.structured_call("coordinator", "safe", {}, CoordinatorDecision)
    assert result.action == "ABSTAIN"
    assert usage["llm_calls"] == len(guard) == len(requests) == 2
    assert usage["total_tokens"] == 24
    import json

    body = json.loads(requests[0].content)
    assert body["response_format"]["json_schema"]["strict"] is True
    assert '"action"' in body["messages"][0]["content"]
    assert "not the input state" in body["messages"][0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,content,code,attempts",
    [
        (400, "SECRET private prompt", "STRUCTURED_OUTPUT_COMPATIBILITY_ERROR", 1),
        (200, "bad", "STRUCTURED_OUTPUT_INVALID", 2),
    ],
)
async def test_sanitized_bounded_errors(status, content, code, attempts):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        p = RealChatProvider("https://example.invalid", "SECRET", "configured", client=client)
        with pytest.raises(ProviderError) as error:
            await p.structured_call("coordinator", "private prompt", {}, CoordinatorDecision)
    assert str(error.value) == code
    assert len(calls) == attempts
    assert error.value.usage["total_tokens"] is None


@pytest.mark.asyncio
async def test_timeout_and_missing_usage():
    async def timeout(request):
        raise httpx.ReadTimeout("SECRET", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ProviderError, match="^PROVIDER_TIMEOUT$"):
            await RealChatProvider(
                "https://example.invalid", "SECRET", "m", client=client
            ).structured_call("coordinator", "", {}, CoordinatorDecision)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"choices": [{"message": {"content": valid()}}]})
        )
    ) as client:
        _, usage = await RealChatProvider(
            "https://example.invalid", "k", "m", client=client
        ).structured_call("coordinator", "", {}, CoordinatorDecision)
        assert usage["total_tokens"] is None


@pytest.mark.asyncio
async def test_mock_determinism_and_no_real_token_claim():
    p = MockProvider()
    a, usage = await p.structured_call(
        "coordinator", "", {"incident_id": "any"}, CoordinatorDecision
    )
    b, _ = await p.structured_call(
        "coordinator", "", {"incident_id": "another"}, CoordinatorDecision
    )
    assert a == b
    assert usage["source"] == "mock" and usage["total_tokens"] is None


@pytest.mark.parametrize("retries", [0, 1])
async def test_configured_repair_limit_is_enforced(retries):
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "invalid"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "fixture",
            "fixture",
            client=client,
            structured_repair_retries=retries,
        )
        with pytest.raises(ProviderError, match="STRUCTURED_OUTPUT_INVALID"):
            await provider.structured_call("coordinator", "", {}, CoordinatorDecision)
    assert len(calls) == retries + 1


@pytest.mark.parametrize("invalid", [-1, 2, True, "1"])
def test_repair_configuration_cannot_expand_hard_limit(invalid):
    with pytest.raises(ValueError):
        RealChatProvider(
            "https://fixture.invalid", "fixture", "fixture", structured_repair_retries=invalid
        )


async def test_explicit_json_mode_and_thinking_are_sent_without_schema_fallback():
    import json

    requests = []

    def response(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": valid()}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "fixture",
            "fixture",
            client=client,
            response_format_mode="json_object",
            thinking="disabled",
        )
        result, _ = await provider.structured_call("coordinator", "", {}, CoordinatorDecision)
    assert result.action == "ABSTAIN"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["thinking"] == {"type": "disabled"}
    assert "required output JSON Schema" in requests[0]["messages"][0]["content"]
    assert provider.model_parameters["response_format"] == "json_object"


@pytest.mark.parametrize(
    "options",
    [
        {"response_format_mode": "auto"},
        {"thinking": "auto"},
        {"timeout": 0},
        {"timeout": float("nan")},
    ],
)
def test_provider_configuration_is_explicit_and_bounded(options):
    with pytest.raises(ValueError):
        RealChatProvider("https://fixture.invalid", "fixture", "fixture", **options)
