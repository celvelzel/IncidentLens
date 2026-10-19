"""Conservative completed changes-scope loop regressions (no provider requests)."""

import pytest

from incident_lens.agents.service import InvestigatorPlan, ToolCall
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.schemas import CoordinatorDecision, InvestigationTask
from incident_lens.tools import EvidenceProvider
from incident_lens.tools.registry import HANDLERS


def assignment(name, service="backend", question="Inspect changes"):
    return InvestigationTask(
        task_id=name, role="changes", question=question,
        allowed_tools=["query_changes", "get_config_diff"], filters={"service": service},
        reason="Missing causal evidence", expected_discriminator="config mechanism",
    )


def setup_run(monkeypatch, empty=True):
    run = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_001")
    if empty:
        monkeypatch.setitem(HANDLERS, "query_changes", lambda *args: [])

    async def plan(provider, context, task, *args):
        return InvestigatorPlan(calls=[ToolCall(
            tool_name="query_changes", args=task.filters,
        )]), {"llm_calls": 1, "total_tokens": 0}

    monkeypatch.setattr("incident_lens.agents.service.plan_tools", plan)
    return run


async def publish(run, task):
    run.state.tasks.append(task)
    run.task_manager.assign(task.task_id, task.role)
    result = await run.execute_task(run.state, task)
    merged = run.merge({"investigation": run.state, "local_results": [result]})
    assert merged["route"] != "report"
    run.state = merged["investigation"]


async def propose(monkeypatch, run, tasks):
    async def decide(*args):
        return CoordinatorDecision(
            action="INVESTIGATE", reason="Need discriminator", assignments=tasks,
        ), {"llm_calls": 1, "total_tokens": 0}
    monkeypatch.setattr("incident_lens.agents.service.decide", decide)
    return await run.coordinate({"investigation": run.state})


async def test_paraphrased_completed_empty_scope_stops_normally(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("original"))
    history = run.payload(run.state)["query_history"][0]
    assert history["ok"] and history["completed"]
    assert history["record_count"] == 0 and history["next_cursor"] is None
    assert (await propose(monkeypatch, run, [assignment("new", question="Check deployments again")]))["route"] == "report"
    await run.stop({"investigation": run.state})
    run.report({"investigation": run.state})
    assert run.state.report.status == "INCONCLUSIVE"
    assert run.state.termination.reason == "INCONCLUSIVE"
    assert run.state.workflow_status == "FINISHED"
    assert not any(e.event_type == "RUNTIME_ERROR" for e in run.state.events)


async def test_new_scope_in_regrouped_batch_continues(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("original"))
    result = await propose(monkeypatch, run, [
        assignment("repeat", question="Again"), assignment("new", service="payment"),
    ])
    assert result["route"] == "dispatch"


async def test_failed_analysis_cannot_complete_scope(monkeypatch):
    run = setup_run(monkeypatch, empty=False)

    async def broken(*args):
        raise RuntimeError("Analysis failed")
    monkeypatch.setattr("incident_lens.agents.service.analyze", broken)
    task = assignment("broken")
    run.state.tasks.append(task)
    run.state.decisions.append(CoordinatorDecision(
        action="INVESTIGATE", reason="test", assignments=[task],
    ))
    run.task_manager.assign(task.task_id, task.role)
    result = await run.dispatch({"investigation": run.state})
    assert result["route"] == "report" and not run.completed_scopes
    await run.stop({"investigation": run.state})
    assert run.state.termination.reason == "UNRECOVERABLE_ERROR"


async def test_positive_observations_do_not_trigger_empty_scope_guard(monkeypatch):
    run = setup_run(monkeypatch, empty=False)
    await publish(run, assignment("positive"))
    assert run.state.evidence_index
    assert not run.completed_scopes
    assert (await propose(monkeypatch, run, [assignment("more", question="Inspect mechanism")]))["route"] == "dispatch"


@pytest.mark.parametrize("tools", [["query_metrics"], ["query_changes", "query_logs"]])
def test_other_tools_are_not_collapsed(tools):
    task = assignment("different").model_copy(update={"allowed_tools": tools})
    assert InvestigationRun.structured_scope(task) is None


async def test_unpublished_empty_query_does_not_complete_scope(monkeypatch):
    run = setup_run(monkeypatch)
    task = assignment("unpublished")
    run.state.tasks.append(task)
    run.task_manager.assign(task.task_id, task.role)
    await run.execute_task(run.state, task)
    assert not run.completed_scopes
    assert (await propose(monkeypatch, run, [assignment("retry", question="Try again")]))["route"] == "dispatch"


async def test_effective_scope_must_match_declared_filters(monkeypatch):
    run = setup_run(monkeypatch)

    async def broader(provider, context, task, *args):
        return InvestigatorPlan(calls=[ToolCall(
            tool_name="query_changes", args={},
        )]), {"llm_calls": 1, "total_tokens": 0}
    monkeypatch.setattr("incident_lens.agents.service.plan_tools", broader)
    await publish(run, assignment("mismatch"))
    assert not run.completed_scopes


async def test_new_evidence_invalidates_completed_scope(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("empty"))
    monkeypatch.undo()
    # Publish actual evidence from a different completed investigation.
    peer = setup_run(monkeypatch, empty=False)
    await publish(peer, assignment("positive"))
    run.state.evidence_index.update(peer.state.evidence_index)
    assert (await propose(monkeypatch, run, [assignment("retry", question="Reassess")]))["route"] == "dispatch"


async def test_completed_scope_can_abstain_at_round_admission_boundary(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("empty"))
    run.state.round_index = run.limits.max_rounds
    assert (await propose(monkeypatch, run, [assignment("retry", question="Again")]))["route"] == "report"
    assert run.state.stop_reason == "INCONCLUSIVE"


async def test_broad_empty_scope_covers_prose_narrowing(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("empty"))
    result = await propose(monkeypatch, run, [assignment(
        "narrower", question="Check only deployments after observation start",
    )])
    # A successful empty broad scope contains no records in any narrower window.
    assert result["route"] == "report" and run.state.stop_reason == "INCONCLUSIVE"


async def test_existing_token_exhaustion_remains_technical(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("empty"))
    run.limits.max_tokens = 1
    run.call_budget.tokens = 1
    result = await propose(monkeypatch, run, [assignment("retry", question="Again")])
    assert result["route"] == "report"
    await run.stop({"investigation": run.state})
    assert run.state.termination.reason == "BUDGET_EXHAUSTED"


async def test_known_change_with_unread_diff_remains_available(monkeypatch):
    run = setup_run(monkeypatch, empty=False)
    await publish(run, assignment("discovery"))
    change = next(r for r in run.state.evidence_index.values() if r.metadata.get("change_id"))
    change_id = change.metadata["change_id"]
    assert not any(r.source_type == "configs" for r in run.state.evidence_index.values())
    monkeypatch.setitem(HANDLERS, "query_changes", lambda *args: [])
    await publish(run, assignment("empty-slice"))
    assert run.completed_scopes
    task = assignment("diff", question=f"Read actual config diff for {change_id}")
    result = await propose(monkeypatch, run, [task])
    assert result["route"] == "dispatch"

    async def diff_plan(*args):
        return InvestigatorPlan(calls=[ToolCall(
            tool_name="get_config_diff", args={"change_id": change_id},
        )]), {"llm_calls": 1, "total_tokens": 0}
    monkeypatch.setattr("incident_lens.agents.service.plan_tools", diff_plan)
    local = await run.execute_task(run.state, task)
    merged = run.merge({"investigation": run.state, "local_results": [local]})
    assert merged["route"] != "report"
    assert any(r.source_type == "configs" for r in merged["investigation"].evidence_index.values())


async def test_single_full_context_acl_excluded_from_guard(monkeypatch):
    run = setup_run(monkeypatch)
    await publish(run, assignment("empty"))
    run.variant = "single"
    result = await propose(monkeypatch, run, [assignment("new-tool", question="Inspect logs")])
    assert result["route"] == "dispatch"
