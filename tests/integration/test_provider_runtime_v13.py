"""Production adapter recovery, budgets and task-local guard integration."""

import asyncio

import httpx
import pytest

from incident_lens.evaluation.runner import MeasuredProvider
from incident_lens.llm import ProviderError, RealChatProvider
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.schemas import Budget, CoordinatorDecision
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider

VALID = '{"action":"ABSTAIN","reason":"missing","stop_reason":"missing"}'


def envelope(content=VALID, total=3):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": total},
    }


@pytest.mark.parametrize(
    "sequence,expected,category",
    [
        ([429, 200], 2, None),
        ([503, 503, 200], 3, None),
        ([401], 1, "AUTHENTICATION_FAILED"),
        ([403], 1, "AUTHENTICATION_FAILED"),
        ([400], 1, "INVALID_REQUEST"),
        ([422], 1, "INVALID_REQUEST"),
        (["bad", 200], 2, None),
        (["schema", 200], 2, None),
        (["bad", "bad"], 2, "INVALID_JSON"),
    ],
)
async def test_production_adapter_sequences(sequence, expected, category):
    requests = []

    async def respond(request):
        value = sequence[min(len(requests), len(sequence) - 1)]
        requests.append(request)
        return httpx.Response(
            value if isinstance(value, int) else 200,
            json=envelope("not json" if value == "bad" else "{}" if value == "schema" else VALID),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = MeasuredProvider(
            RealChatProvider(
                "https://fixture.invalid",
                "fixture",
                "m",
                client=client,
                recovery={"enabled": True, "initial_backoff_seconds": 0.0},
            )
        )
        if category:
            with pytest.raises(ProviderError) as error:
                await provider.structured_call("coordinator", "", {}, CoordinatorDecision)
            assert error.value.failure.category == category
        else:
            _, usage = await provider.structured_call("coordinator", "", {}, CoordinatorDecision)
            assert usage["llm_calls"] == expected
            if sequence[0] in (429, 503):
                # This fixture supplies valid usage on error responses too.
                assert usage["total_tokens"] == expected * 3 and usage["tokens_complete"]
    assert provider.actual_requests == len(requests) == expected


async def test_stage_guard_isolation_measured_last_permit_and_retry():
    requests = []
    arrived = asyncio.Event()
    release = asyncio.Event()

    async def respond(request):
        requests.append(request)
        arrived.set()
        await release.wait()
        return httpx.Response(200, json=envelope())

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        measured = MeasuredProvider(
            RealChatProvider(
                "https://fixture.invalid", "k", "m", client=client, recovery={"enabled": True}
            )
        )
        run = InvestigationRun(
            measured,
            EvidenceProvider("data"),
            "incident_001",
            limits=Budget(max_llm_calls=2),
            workflow=WorkflowOptions(monitoring_max_calls=1),
        )

        async def call():
            return await run.provider.structured_call("coordinator", "", {}, CoordinatorDecision)

        stage = asyncio.create_task(run.stage_call("monitoring", call))
        await arrived.wait()
        investigation = asyncio.create_task(run.model_call("logs", call))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(stage, investigation)
        assert run.stage_calls["monitoring"] == 1
        assert run.call_budget.calls == measured.actual_requests == len(requests) == 2
        assert run.call_budget.snapshot("monitoring").stage_remaining == 0
        assert run.call_budget.tokens == 6


async def test_stop_cancels_production_backoff_and_preserves_dispatched_usage():
    sleeping = asyncio.Event()
    requests = []

    async def sleeper(delay):
        sleeping.set()
        await asyncio.Event().wait()

    async def respond(request):
        requests.append(request)
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        measured = MeasuredProvider(
            RealChatProvider(
                "https://fixture.invalid",
                "k",
                "m",
                client=client,
                recovery={"enabled": True},
                sleeper=sleeper,
            )
        )
        run = InvestigationRun(measured, EvidenceProvider("data"), "incident_001")
        call = asyncio.create_task(
            run.model_call(
                "logs", run.provider.structured_call, "logs", "", {}, CoordinatorDecision
            )
        )
        await sleeping.wait()

        async def cancel():
            for pending in list(run.active_model_calls):
                pending.cancel()
            await asyncio.gather(*list(run.active_model_calls), return_exceptions=True)

        await run.stop_controller.stop("INCONCLUSIVE", {"logs": cancel})
        with pytest.raises(asyncio.CancelledError):
            await call
        assert len(requests) == measured.actual_requests == run.call_budget.calls == 1
        assert measured.calls[0]["usage"]["total_tokens"] is None
        assert len(run.call_budget.failures) == 1
        assert not run.call_budget.snapshot().tokens_complete


@pytest.mark.parametrize("deny_kind", ["token_budget_exhausted", "wall_budget_exhausted"])
async def test_retry_denial_is_not_counted_as_dispatch(deny_kind):
    from incident_lens.orchestration.budget import BudgetExceeded

    requests = []
    permits = []

    async def sleeper(delay):
        permits.append("deny")

    def guard():
        if permits:
            raise BudgetExceeded(deny_kind)

    def respond(request):
        requests.append(request)
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "k",
            "m",
            client=client,
            recovery={"enabled": True},
            sleeper=sleeper,
        )
        provider.request_guard = guard
        with pytest.raises(ProviderError) as error:
            await provider.structured_call("logs", "", {}, CoordinatorDecision)
        assert len(requests) == error.value.usage["llm_calls"] == 1
        assert error.value.usage["transport_retries"] == 0
        assert error.value.failure.category == (
            "TOKEN_BUDGET_EXHAUSTED" if deny_kind.startswith("token") else "WALL_BUDGET_EXHAUSTED"
        )


async def test_stage_denial_does_not_count_undispatched_repair():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=envelope("invalid"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid", "k", "m", client=client, recovery={"enabled": True}
        )
        run = InvestigationRun(
            provider,
            EvidenceProvider("data"),
            "incident_001",
            limits=Budget(max_llm_calls=5),
            workflow=WorkflowOptions(monitoring_max_calls=1),
        )
        with pytest.raises(ProviderError) as error:
            await run.stage_call(
                "monitoring",
                run.provider.structured_call,
                "monitoring",
                "",
                {},
                CoordinatorDecision,
            )
        assert error.value.usage["repair_requests"] == 0
        assert run.call_budget.calls == len(requests) == 1


async def test_local_serialization_failure_does_not_dispatch_or_charge():
    requests = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: requests.append(r))
    ) as client:
        provider = MeasuredProvider(
            RealChatProvider(
                "https://fixture.invalid", "k", "m", client=client, recovery={"enabled": True}
            )
        )
        provider.delegate.temperature = float("nan")  # Invalid local state before serialization.
        run = InvestigationRun(provider, EvidenceProvider("data"), "incident_001")
        with pytest.raises(ProviderError) as error:
            await run.model_call(
                "logs",
                run.provider.structured_call,
                "logs",
                "",
                {},
                CoordinatorDecision,
            )
        assert error.value.failure.category == "INVALID_REQUEST"
        assert len(requests) == provider.actual_requests == run.call_budget.calls == 0
        assert run.call_budget.snapshot().remaining_request_permits == 16


@pytest.mark.parametrize("temperature", [float("nan"), float("inf"), True])
def test_nonfinite_configuration_rejected_before_any_admission(temperature):
    with pytest.raises(ValueError, match="Temperature"):
        RealChatProvider("https://fixture.invalid", "k", "m", temperature=temperature)


async def test_mock_metrics_do_not_claim_physical_http_requests():
    from incident_lens.evaluation.runner import usage_metrics
    from incident_lens.llm import MockProvider

    measured = MeasuredProvider(MockProvider())
    await measured.structured_call("coordinator", "", {}, CoordinatorDecision)
    metrics = usage_metrics(measured, {"events": []})
    assert metrics["llm_requests"] == 1
    assert metrics["actual_http_requests"] == 0
    assert metrics["logical_structured_calls"] == 1


async def test_legacy_repair_diagnostics_derived_without_changing_legacy_usage():
    from incident_lens.evaluation.runner import usage_metrics

    count = []

    def respond(request):
        count.append(request)
        return httpx.Response(200, json=envelope("bad" if len(count) == 1 else VALID))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        measured = MeasuredProvider(
            RealChatProvider("https://fixture.invalid", "k", "m", client=client)
        )
        await measured.structured_call("coordinator", "", {}, CoordinatorDecision)
    metrics = usage_metrics(measured, {"events": []})
    assert metrics["actual_http_requests"] == 2
    assert metrics["repair_requests"] == 1
    assert metrics["transport_retries"] == 0


@pytest.mark.parametrize("endpoint", ["ftp://fixture.invalid", "/relative", "fixture.invalid"])
def test_local_endpoint_invalidity_is_rejected_before_dispatch(endpoint):
    with pytest.raises(ValueError, match="Endpoint"):
        RealChatProvider(endpoint, "k", "m", recovery={"enabled": True})


async def test_failure_elapsed_is_observed_after_transport_failure():
    now = [0.0]

    def respond(request):
        now[0] += 3.0
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "k",
            "m",
            client=client,
            recovery={"enabled": True, "max_transport_retries": 0},
            clock=lambda: now[0],
        )
        with pytest.raises(ProviderError) as error:
            await provider.structured_call("logs", "", {}, CoordinatorDecision)
        assert error.value.failure.elapsed_ms == error.value.usage["elapsed_ms"] == 3000.0


async def test_schema_diagnostics_export_paths_without_sensitive_values_or_keys():
    events = []
    content = '{"action":"SENSITIVE_VALUE","reason":"safe","SENSITIVE_KEY":"value"}'
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=envelope(content)))
    ) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "SENSITIVE_KEY",
            "m",
            client=client,
            recovery={"enabled": True, "max_structured_repairs": 0},
        )
        provider.event_observer = lambda kind, **details: events.append(dict(kind=kind, **details))
        with pytest.raises(ProviderError):
            await provider.structured_call(
                "coordinator", "SENSITIVE_VALUE", {}, CoordinatorDecision
            )
    import json

    text = json.dumps(events)
    assert "validation_summary" in text and "action" in text
    assert "SENSITIVE_VALUE" not in text and "SENSITIVE_KEY" not in text


@pytest.mark.parametrize("mode", ["", 0, False])
def test_explicit_invalid_format_never_silently_selects_another_mode(mode):
    with pytest.raises(ValueError, match="response format"):
        RealChatProvider(
            "https://fixture.invalid",
            "k",
            "m",
            response_format_mode=mode,
            recovery={"enabled": True},
        )


@pytest.mark.parametrize("reliable", [False, True])
async def test_request_timeout_is_total_deadline_even_if_transport_ignores_httpx_timeout(reliable):
    import asyncio

    from incident_lens.llm.provider import ProviderError

    cancelled = []

    async def slow_response(request):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return httpx.Response(200, json=envelope(VALID))

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow_response)) as client:
        provider = MeasuredProvider(RealChatProvider(
            "https://fixture.invalid", "k", "m", client=client, timeout=0.02,
            recovery={"enabled": reliable, "max_transport_retries": 0,
                      "max_physical_attempts_per_call": 1},
        ))
        with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT") as exc:
            await provider.structured_call("coordinator", "", {}, CoordinatorDecision)
    assert cancelled == [True]
    assert provider.actual_requests == 1
    assert exc.value.usage["total_tokens"] is None
    assert not exc.value.usage["tokens_complete"]
