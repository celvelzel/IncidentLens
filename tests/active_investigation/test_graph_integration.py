"""Real Graph execution and authority preservation at the policy boundary."""

import builtins
from pathlib import Path

import pytest

from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.schemas import Budget, CoordinatorDecision
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider

ROOT = Path(__file__).resolve().parents[2]


def business(state):
    events = [
        (
            e.event_type,
            e.role,
            e.details.get("tool_name"),
            e.details.get("args"),
            e.details.get("decision", {}).get("action"),
        )
        for e in state.events
        if e.event_type in {"DECISION", "TOOL_CALL", "LLM_CALL"}
    ]
    # Independent specialists finish concurrently; compare each role's ordered
    # operations, preserving Coordinator decisions without assuming thread order.
    return {
        role: [event for event in events if event[1] == role]
        for role in {event[1] for event in events}
    }


async def test_shadow_keeps_original_execution_and_report():
    plain = await run_investigation("incident_001", MockProvider(), ROOT / "data", run_id="same")
    shadow = await run_investigation(
        "incident_001",
        MockProvider(),
        ROOT / "data",
        run_id="same",
        workflow=WorkflowOptions(shadow_caes=True),
    )
    assert business(plain) == business(shadow)
    assert plain.report == shadow.report
    assert plain.tasks == shadow.tasks
    assert (plain.llm_calls_used, plain.tool_calls_used) == (
        shadow.llm_calls_used,
        shadow.tool_calls_used,
    )
    assert not any(e.event_type == "ACTION_SELECTED" for e in plain.events)
    assert any(e.event_type == "ACTION_SELECTED" for e in shadow.events)


async def test_enabled_really_materializes_selected_tasks():
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        ROOT / "data",
        run_id="active",
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    selections = [e.details for e in state.events if e.event_type == "ACTION_SELECTED"]
    assert selections
    assert all(t.task_id.startswith("caes-") for t in state.tasks)
    assert any(d["coordinator_proposed_tasks"] != d["selector_executed_tasks"] for d in selections)
    selected_ids = {t["task_id"] for d in selections for t in d["selector_executed_tasks"]}
    assert {t.task_id for t in state.tasks} == selected_ids
    assert {e.task_id for e in state.events if e.event_type == "TASK_ASSIGNED"} == selected_ids
    assert state.tool_calls_used <= state.budgets.max_tool_calls
    assert state.llm_calls_used <= state.budgets.max_llm_calls
    assert state.termination.stop_completed


@pytest.mark.parametrize("action", ["FINALIZE", "ABSTAIN"])
async def test_terminal_coordinator_never_calls_caes(monkeypatch, action):
    import incident_lens.agents.service as service
    import incident_lens.orchestration.active_investigation.policy as policy

    async def terminal(*args):
        values = (
            dict(selected_hypothesis_id="unknown", stop_reason="test")
            if action == "FINALIZE"
            else dict(stop_reason="insufficient")
        )
        return CoordinatorDecision(action=action, reason="test", **values), dict(llm_calls=1)

    monkeypatch.setattr(service, "decide", terminal)
    monkeypatch.setattr(policy, "apply_policy", lambda *args: pytest.fail("terminal invoked CAES"))
    run = InvestigationRun(
        MockProvider(),
        EvidenceProvider(ROOT / "data"),
        "incident_001",
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    await run.coordinate({"investigation": run.state})
    assert not run.state.tasks
    assert run.state.decisions[-1].action == action


async def test_off_does_not_import_selector(monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.endswith("active_investigation.policy") or name.endswith(
            "active_investigation.selector"
        ):
            pytest.fail("disabled path imported policy/selector")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    state = await run_investigation("incident_001", MockProvider(), ROOT / "data")
    assert state.report.status == "RESOLVED"


async def test_stopped_runtime_no_selection_or_new_tasks():
    run = InvestigationRun(
        MockProvider(),
        EvidenceProvider(ROOT / "data"),
        "incident_001",
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    await run.stop_controller.stop("INCONCLUSIVE")
    count = run.call_budget.calls
    await run.coordinate({"investigation": run.state})
    assert not run.state.tasks
    assert run.call_budget.calls == count
    assert not any(e.event_type == "ACTION_SELECTED" for e in run.state.events)


async def test_tight_budget_no_overflow():
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        ROOT / "data",
        budget=Budget(max_llm_calls=3, max_tool_calls=2),
        workflow=WorkflowOptions(selection_policy="active_no_cost"),
    )
    assert not state.tasks
    assert state.stop_reason == "NO_USEFUL_ACTION"
    assert state.report.status == "INCONCLUSIVE"
    assert state.llm_calls_used == 1


def test_non_full_policy_rejected():
    with pytest.raises(ValueError, match="full dynamic"):
        InvestigationRun(
            MockProvider(),
            EvidenceProvider(ROOT / "data"),
            "incident_001",
            variant="single",
            workflow=WorkflowOptions(shadow_caes=True),
        )
