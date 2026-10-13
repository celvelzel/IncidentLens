"""Real LangGraph integration of V1.2 stages, failures and publication guards."""
import asyncio

import pytest

from incident_lens.agents.remediation import validate_plan
from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import ProviderError
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.schemas import Budget, InvestigationTask
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


def options(**updates):
    return WorkflowOptions(profile="incident_response", database_enabled=False, **updates)


def snapshot(abnormal):
    record = EvidenceProvider()._records("incident_001", "metrics")[0]
    return [record.model_copy(update={"metadata": {
        "metric_name": "error_rate", "value": 0.2 if abnormal else 0.001,
    }})]


async def test_normal_snapshot_stops_without_diagnosis_or_remediation():
    state = await run_investigation("incident_001", MockProvider(), workflow=options(
        monitor_mode="manual_snapshot", snapshot=snapshot(False)))
    assert state.incident_alert.status == "NO_ALERT"
    assert state.report.root_cause is None
    assert state.report.remediation_status == "SKIPPED"
    assert state.decisions == [] and state.tool_calls_used == 0
    assert state.workflow_status == "FINISHED"
    assert any(e.event_type == "STOP" and e.details.get("stop_reason") == "NO_ALERT"
               for e in state.events)


@pytest.mark.parametrize("mode", ["manual_snapshot", "offline_replay"])
async def test_anomaly_reaches_accepted_diagnosis_and_valid_plan(mode):
    state = await run_investigation("incident_001", MockProvider(),
                                    budget=Budget(max_llm_calls=20),
                                    workflow=options(monitor_mode=mode, snapshot=snapshot(True)))
    assert state.incident_alert.status == "ALERT"
    assert state.report.status == state.report.diagnosis_status == "RESOLVED"
    assert state.report.remediation_status == "PLAN_READY"
    assert state.report.remediation_plan.execution_mode == "PLAN_ONLY"
    validate_plan(state.report.remediation_plan, state.report, state.evidence_index)
    events = [e.event_type for e in state.events]
    assert events.index("INCIDENT_ALERT") < events.index("DECISION")
    assert events.index("REMEDIATION_PLAN") < events.index("STOP") < events.index("REPORT")
    assert state.task_records[-1].role == "remediation"
    assert state.task_records[-1].status == "COMPLETED"


@pytest.mark.parametrize("enabled", [True, False])
async def test_legacy_profile_never_routes_database_or_remediation(enabled):
    state = await run_investigation("incident_001", MockProvider(),
                                    workflow=WorkflowOptions(database_enabled=enabled))
    assert state.report.status == "RESOLVED"
    assert all(t.role != "database" for t in state.tasks)
    assert state.report.remediation_plan is None
    assert not any(e.event_type in {"INCIDENT_ALERT", "REMEDIATION_PLAN"} for e in state.events)


async def test_transient_task_failure_retries_and_resolves(monkeypatch):
    original = InvestigationRun.investigate
    failures = set()

    async def flaky(self, state, task):
        if task.role == "logs" and task.task_id not in failures:
            failures.add(task.task_id)
            raise RuntimeError("TRANSIENT_WORKER_FAILURE")
        return await original(self, state, task)

    monkeypatch.setattr(InvestigationRun, "investigate", flaky)
    state = await run_investigation("incident_001", MockProvider(),
                                    budget=Budget(max_llm_calls=24), workflow=options())
    assert state.report.status == "RESOLVED"
    logs = [r for r in state.task_records if r.role == "logs"]
    assert [r.status for r in logs] == ["FAILED", "COMPLETED"]
    assert [r.attempt for r in logs] == [1, 2]
    assert len({r.attempt_id for r in logs}) == 2


async def test_exhausted_worker_keeps_successful_peer_result(monkeypatch):
    original = InvestigationRun.investigate

    async def broken_logs(self, state, task):
        if task.role == "logs":
            raise RuntimeError("PERMANENT_WORKER_FAILURE")
        return await original(self, state, task)

    monkeypatch.setattr(InvestigationRun, "investigate", broken_logs)
    state = await run_investigation("incident_001", MockProvider(),
                                    budget=Budget(max_llm_calls=24), workflow=options())
    logs = [r for r in state.task_records if r.role == "logs"]
    assert logs and all(r.status == "FAILED" for r in logs)
    assert max(r.attempt for r in logs) == 2
    assert any(f.role == "metrics" for f in state.findings)
    assert state.evidence_index
    assert state.report is not None and state.workflow_status in {"FINISHED", "FAILED"}
    assert not state.report.remediation_plan or state.report.status == "RESOLVED"


async def test_frozen_runtime_rejects_late_merge_without_publication():
    run = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_001", workflow=options())
    await run.stop_controller.stop("INCONCLUSIVE")
    before = run.state.evidence_index.copy()
    output = run.merge({"investigation": run.state, "local_results": []})
    assert output["route"] == "report"
    assert run.state.evidence_index == before and run.state.findings == []
    assert not any(e.event_type == "MERGE" for e in run.state.events)


async def test_disabled_partial_recovery_discards_batch(monkeypatch):
    original = InvestigationRun.investigate

    async def broken_logs(self, state, task):
        if task.role == "logs":
            raise RuntimeError("PERMANENT_WORKER_FAILURE")
        return await original(self, state, task)

    monkeypatch.setattr(InvestigationRun, "investigate", broken_logs)
    state = await run_investigation("incident_001", MockProvider(), workflow=options(
        continue_on_partial_failure=False))
    assert state.report.status == "INCONCLUSIVE"
    assert state.evidence_index == {} and state.findings == []


@pytest.mark.parametrize("enabled", [True, False])
async def test_database_specialist_and_equivalent_metrics_tools(enabled):
    workflow = WorkflowOptions(profile="incident_response", database_enabled=enabled,
                               database_equivalent_tools=True)
    state = await run_investigation("incident_037", MockProvider(), workflow=workflow,
                                    budget=Budget(max_llm_calls=32, max_tool_calls=24))
    assert state.report.status == "RESOLVED"
    assert state.report.root_cause.failure_mode == "postgres_connection_exhaustion"
    assert any(t.role == "database" for t in state.tasks) == enabled
    assert any(r.source_type == "database" for r in state.evidence_index.values())
    assert any(e.role == ("database" if enabled else "metrics")
               and e.event_type == "TOOL_CALL"
               and e.details.get("tool_name", "").startswith("get_db_")
               for e in state.events)
    validate_plan(state.report.remediation_plan, state.report, state.evidence_index)


async def test_failed_remediation_preserves_accepted_diagnosis(monkeypatch):
    async def broken(*args):
        raise RuntimeError("PLAN_GENERATION_FAILED")

    monkeypatch.setattr("incident_lens.agents.remediation.remediate", broken)
    state = await run_investigation("incident_001", MockProvider(), workflow=options(),
                                    budget=Budget(max_llm_calls=24))
    assert state.report.status == state.report.diagnosis_status == "RESOLVED"
    assert state.report.remediation_status == "PLAN_FAILED"
    assert state.report.remediation_plan is None
    attempts = [r for r in state.task_records if r.role == "remediation"]
    assert [r.attempt for r in attempts] == [1, 2]
    assert all(r.status == "FAILED" for r in attempts)
    assert any(e.event_type == "STOP" and e.details.get("stop_reason") == "PLAN_FAILED"
               for e in state.events)


async def test_monitoring_stage_zero_budget_prevents_other_work():
    state = await run_investigation("incident_001", MockProvider(), workflow=options(
        monitor_mode="manual_snapshot", snapshot=snapshot(True), monitoring_max_calls=0))
    assert state.llm_calls_used == state.tool_calls_used == 0
    assert state.report.root_cause is None and state.report.remediation_plan is None
    assert state.decisions == []
    assert any(e.event_type == "STOP" and e.details.get("stop_reason") == "BUDGET_EXHAUSTED"
               for e in state.events)


async def test_each_provider_attempt_charged_to_stage_and_global_budget():
    provider = MockProvider()
    provider.model_id = "test-real-transport-stub"
    run = InvestigationRun(provider, EvidenceProvider(), "incident_001", workflow=options(
        monitoring_max_calls=2))

    async def internally_retrying():
        for _ in range(3):
            run.provider.request_guard()
        return None, {"llm_calls": 3}

    with pytest.raises(RuntimeError, match="monitoring stage budget exhausted"):
        await run.stage_call("monitoring", internally_retrying)
    assert run.stage_calls["monitoring"] == run.call_budget.calls == 2


async def test_remediation_reentry_reuses_valid_plan_without_new_task_or_call():
    run = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_037",
                           limits=Budget(max_llm_calls=24, max_tool_calls=24),
                           workflow=WorkflowOptions(profile="incident_response"))
    completed = await run.run()
    assert completed.report.remediation_status == "PLAN_READY"
    calls = run.call_budget.calls
    attempts = len(run.task_manager.records)
    plan = completed.report.remediation_plan.model_dump_json()
    await run.remediate({"investigation": completed})
    assert run.call_budget.calls == calls
    assert len(run.task_manager.records) == attempts
    assert completed.report.remediation_plan.model_dump_json() == plan


async def test_max_attempt_one_disables_worker_retry(monkeypatch):
    original = InvestigationRun.investigate

    async def broken_logs(self, state, task):
        if task.role == "logs":
            raise RuntimeError("WORKER_FAILED")
        return await original(self, state, task)

    monkeypatch.setattr(InvestigationRun, "investigate", broken_logs)
    state = await run_investigation("incident_001", MockProvider(), workflow=options(
        max_attempts=1, continue_on_partial_failure=False))
    logs = [r for r in state.task_records if r.role == "logs"]
    assert len(logs) == 1 and logs[0].attempt == 1 and logs[0].status == "FAILED"
    assert state.report.status == "INCONCLUSIVE"


@pytest.mark.parametrize("worker_count", [1, 2])
async def test_stop_cancels_transformed_provider_errors_and_every_same_role_worker(worker_count):
    run = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_001", workflow=options())
    started = [asyncio.Event() for _ in range(worker_count)]

    async def cancellation_transform(state, task):
        started[int(task.task_id.rsplit("-", 1)[-1])].set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Mirrors the production adapter's cancellation boundary.
            raise ProviderError("PROVIDER_CANCELLED") from None

    run.investigate = cancellation_transform
    for index in range(worker_count):
        task = InvestigationTask(task_id=f"cancel-test-{index}", role="logs",
                                 question="Check logs", allowed_tools=["query_logs"],
                                 reason="Cancellation audit", expected_discriminator="direct fault")
        run.state.tasks.append(task)
        run.task_manager.assign(task.task_id, task.role)
        run.active_workers[task.task_id] = asyncio.create_task(run.execute_task(run.state, task))
    await asyncio.gather(*(event.wait() for event in started))
    await run.stop({"investigation": run.state})
    assert all(worker.done() for worker in run.active_workers.values())
    assert len(run.state.task_records) == worker_count
    assert all(record.status == "CANCELLED" for record in run.state.task_records)
    assert sum(event.event_type == "STOP_ACK" for event in run.state.events) == 1
    events = [event.event_type for event in run.state.events]
    assert max(i for i, event in enumerate(events) if event == "TASK_CANCELLED") < events.index(
        "STOP_ACK")


@pytest.mark.parametrize("role", ["monitoring", "remediation", "coordinator", "verifier"])
async def test_stop_cancels_active_model_calls_outside_investigator_tasks(role):
    run = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_001", workflow=options())
    started = asyncio.Event()

    async def slow():
        started.set()
        await asyncio.Event().wait()

    pending = asyncio.create_task(run.model_call(role, slow))
    await started.wait()
    await run.stop({"investigation": run.state})
    await asyncio.gather(pending, return_exceptions=True)
    assert pending.done() and not run.active_model_calls
    assert any(e.event_type == "STOP_ACK" and e.role == role for e in run.state.events)
    with pytest.raises(RuntimeError, match="frozen"):
        run.consume_request()
