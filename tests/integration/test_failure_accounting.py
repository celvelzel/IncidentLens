import asyncio
from types import SimpleNamespace

import httpx
import pytest

from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.merge import merge_results
from incident_lens.schemas import Budget, Finding, InvestigationState, InvestigationTask
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider, ToolRegistry


async def test_failed_structured_repair_preserves_measured_usage():
    def response(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "invalid json"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid/v1", "fixture-secret", "fixture", client=client
        )
        state = await run_investigation("incident_001", provider)
    assert state.report.status == "INCONCLUSIVE"
    assert state.llm_calls_used == 2 and state.tokens_used == 14
    failure = next(e for e in state.events if e.event_type == "MODEL_FAILURE")
    assert failure.details["total_tokens"] == 14
    assert "fixture-secret" not in state.model_dump_json()


@pytest.mark.parametrize(
    "failure", ["retry_budget", "token_budget", "http_error", "wall_timeout", "bad_envelope"]
)
async def test_partial_or_cancelled_request_usage_is_not_invented(failure):
    calls = 0

    async def response(request):
        nonlocal calls
        calls += 1
        if failure == "wall_timeout":
            await asyncio.sleep(0.2)
        if calls == 2:
            if failure == "bad_envelope":
                return httpx.Response(200, json=[])
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "invalid json"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    budget = Budget(max_llm_calls=1) if failure == "retry_budget" else Budget()
    if failure == "wall_timeout":
        budget = Budget(max_wall_seconds=0.05)
    if failure == "token_budget":
        budget = Budget(max_tokens=5)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        state = await run_investigation(
            "incident_001",
            RealChatProvider(
                "https://fixture.invalid/v1", "fixture-secret", "fixture", client=client
            ),
            budget=budget,
            # This test isolates physical-request accounting; stage retries have
            # their own recovery tests and can now retry HTTP 5xx as intended.
            workflow=WorkflowOptions(max_attempts=1),
        )
    assert state.report.status == "INCONCLUSIVE"
    assert state.llm_calls_used == calls == (2 if failure in ("http_error", "bad_envelope") else 1)
    assert state.tokens_used == (0 if failure == "wall_timeout" else 7)
    event = next(e for e in state.events if e.event_type == "MODEL_FAILURE")
    report = next(e for e in state.events if e.event_type == "REPORT")
    assert report.details["tokens_complete"] is (failure in ("retry_budget", "token_budget"))
    assert event.details["total_tokens"] == (
        7 if failure in ("retry_budget", "token_budget") else None
    )


def test_merge_batch_rejection_cannot_publish_partial_evidence():
    provider = EvidenceProvider("data")
    registry = ToolRegistry(provider, "w", "incident_001", "r")
    context = registry.create_context("logs")
    case = provider.load_case("incident_001")
    result = registry.execute(
        context,
        "query_logs",
        {
            "service": "backend",
            "start_ts": case.started_at.isoformat(),
            "end_ts": "2099-01-01T00:00:00Z",
        },
    )
    tasks = [
        InvestigationTask(
            task_id=f"t{n}",
            role="logs",
            question="Inspect errors",
            allowed_tools=["query_logs"],
            reason="test",
            expected_discriminator="error onset",
        )
        for n in (1, 2)
    ]
    state = InvestigationState(
        workspace_id="w", incident_id="incident_001", run_id="r", public_summary=case, tasks=tasks
    )
    first = Finding(
        finding_id="f1",
        task_id="t1",
        run_id="r",
        incident_id="incident_001",
        role="logs",
        claim="Observed timeout",
        evidence_ids=[result.records[0].evidence_id],
        relation="supports",
        confidence_qualifier="weak",
    )
    wrong = first.model_copy(update={"finding_id": "f2", "task_id": "t2", "run_id": "foreign"})
    with pytest.raises(ValueError):
        merge_results(
            state,
            [
                (context, tasks[0], SimpleNamespace(finding=first, hypotheses=[])),
                (context, tasks[1], SimpleNamespace(finding=wrong, hypotheses=[])),
            ],
            registry,
        )
    assert registry.shared_records() == {}
    assert state.findings == []
