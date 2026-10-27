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
    fields = ("role", "question", "filters", "allowed_tools", "expected_discriminator")
    assert any(
        [{k: t[k] for k in fields} for t in d["coordinator_proposed_tasks"]]
        != [{k: t[k] for k in fields} for t in d["selector_executed_tasks"]]
        for d in selections
    )
    selected_ids = {t["task_id"] for d in selections for t in d["selector_executed_tasks"]}
    assert {t.task_id for t in state.tasks} == selected_ids
    # Verify reviews are runtime tasks too, so the selected check tasks are a
    # subset of everything assigned rather than the whole assigned set.
    assigned_ids = {e.task_id for e in state.events if e.event_type == "TASK_ASSIGNED"}
    assert selected_ids <= assigned_ids
    assert {t for t in assigned_ids if t.startswith("caes-")} == selected_ids
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


async def test_shadow_selector_failure_is_observation_only(monkeypatch):
    from incident_lens.orchestration.active_investigation import selector

    def fail(*args):
        raise RuntimeError("scorer failure")

    monkeypatch.setattr(selector, "select_candidates", fail)
    state = await run_investigation(
        "incident_001", MockProvider(), ROOT / "data", workflow=WorkflowOptions(shadow_caes=True)
    )
    assert state.report.status == "RESOLVED"
    assert (state.llm_calls_used, state.tool_calls_used) == (15, 9)
    assert any(e.event_type == "ACTION_POLICY_FALLBACK" for e in state.events)
    assert not any(e.event_type == "RUNTIME_ERROR" for e in state.events)


async def test_runtime_never_reads_oracle_or_private_files(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert not any(part in {"private", "local_oracles"} for part in path.parts)
        assert "ground_truth" not in path.name
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        ROOT / "data",
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    assert any(e.event_type == "ACTION_SELECTED" for e in state.events)


def test_snapshot_changes_with_visible_hypothesis():
    from incident_lens.orchestration.active_investigation.policy import visible_projection
    from incident_lens.schemas import Hypothesis

    run = InvestigationRun(MockProvider(), EvidenceProvider(ROOT / "data"), "incident_001")
    first = visible_projection(run, run.state)
    run.state.hypotheses.append(
        Hypothesis(hypothesis_id="h", culprit_service="backend", failure_mode="unknown")
    )
    assert (
        visible_projection(run, run.state).evidence_snapshot_sha256
        != first.evidence_snapshot_sha256
    )


async def test_stop_during_selection_prevents_publication(monkeypatch):
    from incident_lens.orchestration.active_investigation import selector

    original = selector.select_candidates
    run = InvestigationRun(
        MockProvider(),
        EvidenceProvider(ROOT / "data"),
        "incident_001",
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )

    def stop(*args):
        result = original(*args)
        run.stop_controller.stopped = run.stop_controller.frozen = True
        return result

    monkeypatch.setattr(selector, "select_candidates", stop)
    await run.coordinate({"investigation": run.state})
    assert not run.state.tasks
    assert not any(e.event_type == "ACTION_SELECTED" for e in run.state.events)


def test_measured_provider_cost_adapter_uses_delegate_recovery():
    from incident_lens.evaluation.runner import MeasuredProvider
    from incident_lens.orchestration.active_investigation.policy import budget_projection
    from incident_lens.orchestration.recovery import RecoveryConfig

    provider = MockProvider()
    provider.recovery = RecoveryConfig(enabled=True, max_physical_attempts_per_call=4)
    run = InvestigationRun(
        MeasuredProvider(provider), EvidenceProvider(ROOT / "data"), "incident_001"
    )
    assert budget_projection(run).physical_request_multiplier == 4


@pytest.mark.parametrize("physical_reserve,logical_reserve,selected", [(3, 2, 1), (9, 3, 0)])
def test_recovery_physical_reserve_normalized_once(physical_reserve, logical_reserve, selected):
    from incident_lens.orchestration.active_investigation.policy import apply_policy
    from incident_lens.orchestration.recovery import RecoveryConfig
    from incident_lens.schemas import InvestigationTask

    provider = MockProvider()
    provider.recovery = RecoveryConfig(
        enabled=True,
        max_physical_attempts_per_call=4,
        reserve_verifier_requests=physical_reserve,
    )
    run = InvestigationRun(
        provider,
        EvidenceProvider(ROOT / "data"),
        "incident_001",
        limits=Budget(max_llm_calls=18),
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    proposal = CoordinatorDecision(
        action="INVESTIGATE",
        reason="check",
        assignments=[
            InvestigationTask(
                task_id="proposal",
                role="logs",
                question="Inspect backend errors",
                reason="budget unit regression",
                allowed_tools=["query_logs", "fetch_evidence"],
                filters={"service": "backend"},
                expected_discriminator="backend errors",
            )
        ],
    )
    result = apply_policy(run, run.state, proposal)
    details = next(e.details for e in run.state.events if e.event_type == "ACTION_SELECTED")
    assert details["config"]["reserve_verifier_requests"] == logical_reserve
    # Physical 3 fits one logical retry bound (4), while the graph additionally
    # needs a final decision and review: reserve two logical calls (8), not 12.
    # Physical 9 conservatively rounds to 12: one task 8 + reserve12 exceeds18.
    assert len(result.assignments) == selected
    assert run.call_budget.snapshot().remaining_request_permits == 18


async def test_selector_reserves_both_final_decision_and_review_before_publishing_tasks():
    state = await run_investigation(
        "incident_001", MockProvider(), ROOT / "data",
        budget=Budget(max_llm_calls=4),
        workflow=WorkflowOptions(selection_policy="active_evidence"),
    )
    selected = [e.details for e in state.events if e.event_type == "ACTION_SELECTED"]
    assert selected and selected[0]["config"]["reserve_verifier_requests"] == 2
    assert all(not d["selector_executed_tasks"] for d in selected)
    assert state.tasks == []
    assert not state.termination.runtime_failure
    assert not any(e.event_type == "RUNTIME_ERROR" for e in state.events)
