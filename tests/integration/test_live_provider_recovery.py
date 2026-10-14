"""Deterministic regressions for the live-provider dispatch failure chain."""

import asyncio

import httpx
import pytest

from incident_lens.agents.service import AnalysisOutput, InvestigatorPlan, ToolCall
from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.llm import MockProvider, RealChatProvider
from incident_lens.llm.provider import ProviderError
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.schemas import Budget, CoordinatorDecision, Finding, InvestigationTask
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider
from incident_lens.tools.registry import HANDLERS


def task(name):
    return InvestigationTask(
        task_id=name, role="metrics", question="Check metrics", reason="Regression",
        expected_discriminator="cause versus missing data", allowed_tools=["query_metrics"],
    )


def make_run(profile="legacy_rca", variant="full", **options):
    run = InvestigationRun(
        MockProvider(), EvidenceProvider(), "incident_001",
        limits=Budget(max_llm_calls=32, max_tool_calls=24), variant=variant,
        workflow=WorkflowOptions(profile=profile, **options),
    )
    assignments = [task("gap"), task("peer")]
    run.state.tasks = assignments
    run.state.decisions = [CoordinatorDecision(
        action="INVESTIGATE", reason="Regression", assignments=assignments,
    )]
    for assignment in assignments:
        run.task_manager.assign(assignment.task_id, assignment.role)
    return run


def missing_plan(monkeypatch, service="inventory"):
    async def plan(*args):
        return InvestigatorPlan(calls=[ToolCall(tool_name="query_metrics", args={
            "service": service, "metric_names": [],
            "start_ts": "2030-01-01T00:00:00Z", "end_ts": "2030-01-01T01:00:00Z",
        })]), {"llm_calls": 1, "total_tokens": 0}

    monkeypatch.setattr("incident_lens.agents.service.plan_tools", plan)


@pytest.mark.parametrize("service", ["inventory", "payment"])
async def test_query_gap_is_neutral_completed_task(monkeypatch, service):
    missing_plan(monkeypatch, service)
    run = make_run()
    context, assignment, output = await run.execute_task(run.state, run.state.tasks[0])
    assert output.finding.evidence_ids == [] and output.hypotheses == []
    assert output.finding.relation == "neutral"
    assert output.finding.confidence_qualifier == "unknown"
    assert "not proof of healthy" in output.finding.claim
    assert run.task_manager.records[0].status == "COMPLETED"
    assert len(run.call_budget.usage) == 1  # No fabricated analysis/retry request.
    gap = next(e for e in run.state.events if e.event_type == "TOOL_DATA_GAP")
    assert gap.details["outcome"] == ("QUERY_NOT_FOUND" if service == "inventory" else "NO_DATA")
    merged = run.merge({"investigation": run.state, "local_results": [(context, assignment, output)]})
    assert not merged["investigation"].evidence_index


@pytest.mark.parametrize("profile,variant,options", [
    ("legacy_rca", "full", {}), ("legacy_rca", "fixed", {}),
    ("legacy_rca", "single", {}), ("incident_response", "full", {}),
    ("legacy_rca", "full", {"benchmark_rca": True, "database_equivalent_tools": True}),
])
async def test_missing_service_preserves_delayed_peer(monkeypatch, profile, variant, options):
    missing_plan(monkeypatch)
    run = make_run(profile, variant, **options)
    original = run.investigate
    completed = []

    async def slow(state, assignment):
        if assignment.task_id == "peer":
            await asyncio.sleep(.02)
            completed.append(assignment.task_id)
        return await original(state, assignment)

    run.investigate = slow
    result = await run.dispatch({"investigation": run.state})
    assert result["route"] == "merge" and len(result["local_results"]) == 2
    assert completed == ["peer"]
    assert len(run.task_manager.records) == 2
    assert all(r.status == "COMPLETED" for r in run.task_manager.records)
    assert not any(e.event_type == "RUNTIME_ERROR" for e in run.state.events)


@pytest.mark.parametrize("transformed", [False, True])
async def test_missing_service_plus_cancelled_call_has_clean_termination(monkeypatch, transformed):
    missing_plan(monkeypatch)
    run = make_run()
    original = run.investigate

    async def cancelled():
        await asyncio.sleep(.02)
        exc = ProviderError("PROVIDER_CANCELLED") if transformed else asyncio.CancelledError()
        exc.usage = {"llm_calls": 1, "total_tokens": None, "tokens_complete": False}
        raise exc

    async def investigate(state, assignment):
        if assignment.task_id == "peer":
            return await run.model_call("metrics", cancelled)
        return await original(state, assignment)

    run.investigate = investigate
    result = await run.dispatch({"investigation": run.state})
    assert result["route"] == "merge" and len(result["local_results"]) == 1
    merged = run.merge(result)
    run.state = merged["investigation"]
    run.state.stop_reason = "INCONCLUSIVE"
    await run.stop({"investigation": run.state})
    final = run.report({"investigation": run.state})["investigation"]
    score = normalize_termination(final.model_dump(mode="json"))
    assert score["protocol_valid"] is True and score["runtime_failure"] is False
    assert final.termination.reason == "INCONCLUSIVE"
    failure = next(e for e in final.events if e.event_type == "MODEL_FAILURE")
    assert failure.details["cancelled"] is True
    assert failure.details["cancellation_reason"] == "parent_cancelled"
    assert any(r.status == "CANCELLED" for r in final.task_records)


@pytest.mark.parametrize("code", ["PROVIDER_TRANSPORT_ERROR", "ROLE_TOOL_PROPOSAL_FORBIDDEN"])
async def test_only_provider_faults_retry_and_security_errors_remain_fatal(code):
    run = make_run()
    attempts = []

    async def broken(state, assignment):
        attempts.append(assignment.task_id)
        raise ProviderError(code)

    run.investigate = broken
    result = await run.dispatch({"investigation": run.state})
    assert result["route"] == "report"
    assert len(attempts) == (4 if code == "PROVIDER_TRANSPORT_ERROR" else 2)
    await run.stop({"investigation": run.state})
    assert run.state.termination.reason == "UNRECOVERABLE_ERROR"


@pytest.mark.parametrize("recovery", [False, True])
async def test_native_transport_cancellation_keeps_usage_and_not_provider_fault(recovery):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        measured = MeasuredProvider(RealChatProvider(
            "https://fixture.invalid/v1", "fixture", "fixture", client=client,
            recovery={"enabled": recovery},
        ))
        pending = asyncio.create_task(measured.structured_call(
            "coordinator", "", {}, CoordinatorDecision,
        ))
        await started.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError) as exc:
            await pending
    assert exc.value.usage["tokens_complete"] is False
    metrics = usage_metrics(measured, {"events": []})
    assert metrics["actual_http_requests"] == 1
    assert metrics["provider_failures"] == metrics["failed_model_calls"] == 0
    assert metrics["cancelled_model_calls"] == 1
    assert metrics["total_tokens"] is None


@pytest.mark.parametrize("exception,code", [
    (FileNotFoundError(), "SOURCE_UNAVAILABLE"), (OSError(), "SOURCE_UNAVAILABLE"),
    (KeyError(), "SOURCE_INVALID"), (ValueError(), "SOURCE_INVALID"),
])
def test_source_fault_is_never_a_tolerable_query_miss(monkeypatch, exception, code):
    run = make_run()

    def broken(*args):
        raise exception

    monkeypatch.setitem(HANDLERS, "query_metrics", broken)
    result = run.registry.execute(run.registry.create_context("metrics"), "query_metrics", {
        "service": "payment", "metric_names": [],
        "start_ts": "2030-01-01T00:00:00Z", "end_ts": "2030-01-01T01:00:00Z",
    })
    assert result.error_code == code and result.ok is False


async def test_mixed_tool_gap_keeps_actual_peer_evidence(monkeypatch):
    run = make_run()

    async def plan(*args):
        return InvestigatorPlan(calls=[ToolCall(tool_name="query_metrics", args={
            "service": service, "metric_names": [],
            "start_ts": "2000-01-01T00:00:00Z", "end_ts": "2100-01-01T00:00:00Z",
        }) for service in ["inventory", "backend"]]), {"llm_calls": 1, "total_tokens": 0}

    async def analyze(provider, context, assignment, records):
        assert records and all(r.service == "backend" for r in records)
        return AnalysisOutput(finding=Finding(
            finding_id="actual", task_id=assignment.task_id, run_id=run.run_id,
            incident_id="incident_001", role="metrics", claim="Actual observed metrics",
            evidence_ids=[r.evidence_id for r in records], relation="neutral",
            confidence_qualifier="unknown",
        ), hypotheses=[]), {"llm_calls": 1, "total_tokens": 0}

    monkeypatch.setattr("incident_lens.agents.service.plan_tools", plan)
    monkeypatch.setattr("incident_lens.agents.service.analyze", analyze)
    result = await run.execute_task(run.state, run.state.tasks[0])
    merged = run.merge({"investigation": run.state, "local_results": [result]})
    assert merged["investigation"].evidence_index
    assert "Data gaps" in merged["investigation"].findings[0].claim


async def test_repeated_empty_check_abstains_without_runtime_crash(monkeypatch):
    run = make_run()
    counter = 0

    async def decide(*args):
        nonlocal counter
        counter += 1
        return CoordinatorDecision(action="INVESTIGATE", reason="same query", assignments=[
            task("new-" + str(counter)),
        ]), {"llm_calls": 1, "total_tokens": 0}

    monkeypatch.setattr("incident_lens.agents.service.decide", decide)
    first = await run.coordinate({"investigation": run.state})
    assert first["route"] == "dispatch"
    second = await run.coordinate({"investigation": run.state})
    assert second["route"] == "report"
    assert run.state.stop_reason == "INCONCLUSIVE"
    assert not any(e.event_type == "RUNTIME_ERROR" for e in run.state.events)


def test_authentication_http_fault_is_not_retried():
    from incident_lens.llm.errors import classify_http

    assert not InvestigationRun.recoverable_task_error(ProviderError(
        "PROVIDER_HTTP_ERROR", failure=classify_http(401),
    ))


async def test_parent_cancel_drains_workers_and_preserves_cancelled_states():
    run = make_run()
    started = [asyncio.Event(), asyncio.Event()]

    async def slow(state, assignment):
        started[0 if assignment.task_id == "gap" else 1].set()
        await asyncio.Event().wait()

    run.investigate = slow
    pending = asyncio.create_task(run.dispatch({"investigation": run.state}))
    await asyncio.gather(*(event.wait() for event in started))
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not run.active_workers
    assert all(r.status == "CANCELLED" for r in run.task_manager.records)


@pytest.mark.parametrize("allow_partial", [True, False])
async def test_disabled_partial_policy_never_cancels_healthy_peer(allow_partial):
    run = make_run(continue_on_partial_failure=allow_partial, max_attempts=1)
    completed = []

    async def investigate(state, assignment):
        if assignment.task_id == "gap":
            raise ProviderError("PROVIDER_TRANSPORT_ERROR")
        await asyncio.sleep(.02)
        completed.append(assignment.task_id)
        return "healthy output"

    run.investigate = investigate
    result = await run.dispatch({"investigation": run.state})
    assert completed == ["peer"]
    assert result["route"] == ("merge" if allow_partial else "report")
    assert result["local_results"] == (["healthy output"] if allow_partial else [])


async def test_wall_deadline_keeps_dispatched_usage_and_budget_classification():
    async def handler(request):
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = MeasuredProvider(RealChatProvider(
            "https://fixture.invalid/v1", "fixture", "fixture", client=client,
        ))
        run = InvestigationRun(provider, EvidenceProvider(), "incident_001",
                               limits=Budget(max_wall_seconds=.05))
        result = await run.coordinate({"investigation": run.state})
    assert result["route"] == "report"
    assert run.state.stop_reason == "Wall-clock budget exhausted"
    await run.stop({"investigation": run.state})
    assert run.state.termination.reason == "BUDGET_EXHAUSTED"
    failure = next(e for e in run.state.events if e.event_type == "MODEL_FAILURE")
    assert failure.details["cancelled"] is True
    assert failure.details["cancellation_reason"] == "wall_budget_exhausted"
    assert failure.details["llm_calls"] == 1
    assert failure.details["tokens_complete"] is False
    metrics = usage_metrics(provider, run.state.model_dump(mode="json"))
    assert metrics["actual_http_requests"] == 1
    assert metrics["provider_failures"] == metrics["failed_model_calls"] == 0
