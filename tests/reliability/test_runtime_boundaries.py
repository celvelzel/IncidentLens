"""Production requests must share the final permit across concurrent calls."""

import asyncio

import httpx

from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.permits import RequestPermitIssuer
from incident_lens.schemas import CoordinatorDecision


async def test_two_production_calls_final_permit():
    issuer = RequestPermitIssuer(max_requests=1, deadline=100.0, clock=lambda: 0.0)
    dispatched = []
    arrived, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        dispatched.append(request)
        arrived.set()
        await release.wait()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"action":"ABSTAIN","reason":"missing","stop_reason":"missing"}'
                        }
                    }
                ]
            },
        )

    def guard():
        permit = issuer.acquire()
        issuer.mark_dispatched(permit)
        return permit

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid",
            "synthetic",
            "fixture-model",
            client=client,
            recovery={"enabled": True},
        )
        provider.request_guard = guard
        provider.request_reconciler = issuer.reconcile
        first = asyncio.create_task(
            provider.structured_call("coordinator", "", {}, CoordinatorDecision)
        )
        await arrived.wait()
        second = asyncio.create_task(
            provider.structured_call("coordinator", "", {}, CoordinatorDecision)
        )
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
    assert len(dispatched) == 1
    assert sum(isinstance(result, RuntimeError) for result in results) == 1
    assert issuer.snapshot().remaining_request_permits == 0
