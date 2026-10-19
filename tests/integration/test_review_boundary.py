import copy

import pytest

from incident_lens.agents.service import InvestigatorPlan, ToolCall, plan_tools
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.orchestration.guards import finalize_errors
from incident_lens.schemas import InvestigationTask
from incident_lens.tools import EvidenceProvider


async def test_rejected_competing_questions_and_stale_review_block_resolution():
    state = await run_investigation("incident_001", MockProvider())
    candidate = next(
        h for h in state.hypotheses if h.hypothesis_id == state.report.root_cause.hypothesis_id
    )
    assert finalize_errors(state, candidate) == []
    rejected = candidate.model_copy(update={"status": "REJECTED"})
    assert "Rejected hypothesis cannot be finalized" in finalize_errors(state, rejected)
    stale = candidate.model_copy(update={"predicted_observations": ["Unreviewed replacement"]})
    assert any("snapshot" in error for error in finalize_errors(state, stale))
    changed = state.model_copy(deep=True)
    record = next(iter(changed.evidence_index.values()))
    record.excerpt = "Changed after review"
    assert any("snapshot" in error for error in finalize_errors(changed, candidate))
    state.open_questions = ["Contradiction remains"]
    assert any("shared questions" in error for error in finalize_errors(state, candidate))
    state.open_questions = []
    competitor = next(h for h in state.hypotheses if h.status == "REJECTED")
    competitor.status = "OPEN"
    competitor.open_questions = ["Check independent competing cause"]
    assert any("Competing hypothesis" in error for error in finalize_errors(state, candidate))


async def test_refreshed_finalize_does_not_request_another_coordinator_decision():
    from incident_lens.evaluation.termination import normalize_termination
    from incident_lens.llm.provider import ProviderError
    from incident_lens.schemas import Budget, Hypothesis
    from incident_lens.schemas.workflow import WorkflowOptions

    class FinalizeThenHang(MockProvider):
        def __init__(self):
            self.seen = {"finalize_calls": 0}

        async def structured_call(self, role, system, payload, schema):
            result, usage = await super().structured_call(role, system, payload, schema)
            if schema.__name__ == "DynamicDecision" and result.action == "FINALIZE":
                self.seen["finalize_calls"] += 1
                if self.seen["finalize_calls"] > 1:
                    raise ProviderError("PROVIDER_TIMEOUT", usage)
                candidate = next(h for h in payload["hypotheses"]
                                 if h["hypothesis_id"] == result.selected_hypothesis_id)
                updated = Hypothesis.model_validate_json(__import__("json").dumps(candidate))
                updated.predicted_observations.append("Reconciled public chronology")
                result = result.model_copy(update={"hypothesis_updates": [updated]})
            return result, usage

    provider = FinalizeThenHang()
    state = await run_investigation(
        "incident_001", provider, budget=Budget(max_llm_calls=32),
        workflow=WorkflowOptions(benchmark_rca=True, database_equivalent_tools=True),
    )
    assert provider.seen["finalize_calls"] == 1
    assert state.report.status == "RESOLVED"
    assert state.termination.reason == "DIAGNOSIS_READY"
    assert normalize_termination(state.model_dump(mode="json"))["protocol_valid"]
    resumed = next(i for i, e in enumerate(state.events)
                   if e.event_type == "FINALIZE_RESUMED_AFTER_REVIEW")
    review_id = state.events[resumed].details["review_event_id"]
    reviewed = next(i for i, e in enumerate(state.events) if e.event_id == review_id)
    assert state.events[reviewed].event_type == "REVIEW"
    # Observability events may intervene; no model work or decision may do so.
    assert all(e.event_type == "REVIEW_EFFECT" for e in state.events[reviewed + 1:resumed])
    assert state.events[resumed - 1].details["review_event_id"] == review_id
    assert state.events[resumed + 1].event_type == "DIAGNOSIS_ACCEPTED"
    assert not any(e.event_type in {"LLM_CALL", "DECISION", "MODEL_FAILURE"}
                   for e in state.events[resumed + 1:])


async def test_role_payload_excludes_tool_history_and_limits_verifier_records():
    state = await run_investigation("incident_001", MockProvider())
    runtime = InvestigationRun(MockProvider(), EvidenceProvider("data"), "incident_001")
    untouched = state.model_dump_json()
    coordinator = runtime.payload(state)
    assert coordinator["events"] == [] and coordinator["evidence_index"] == {}
    assert all("excerpt" not in item for item in coordinator["evidence_catalog"].values())
    assert coordinator["query_history"]
    assert all("result" not in item and "excerpt" not in item
               for item in coordinator["query_history"])
    one = [next(iter(state.evidence_index.values()))]
    verifier = runtime.payload(state, "verifier", one)
    assert verifier["events"] == []
    assert set(verifier["evidence_index"]) == {one[0].evidence_id}
    assert state.model_dump_json() == untouched


async def test_reconciliation_requires_fresh_independent_review():
    from incident_lens.schemas import Budget, Hypothesis
    from incident_lens.schemas.workflow import WorkflowOptions

    class Reconcile(MockProvider):
        async def structured_call(self, role, system, payload, schema):
            result, usage = await super().structured_call(role, system, payload, schema)
            if schema.__name__ == "DynamicDecision" and result.action == "FINALIZE":
                candidate = next(h for h in payload["hypotheses"]
                                 if h["hypothesis_id"] == result.selected_hypothesis_id)
                updated = Hypothesis.model_validate_json(__import__("json").dumps(candidate))
                if "Reconciled public chronology" not in updated.predicted_observations:
                    updated.predicted_observations.append("Reconciled public chronology")
                    result = result.model_copy(update={"hypothesis_updates": [updated]})
            return result, usage

    state = await run_investigation(
        "incident_001", Reconcile(),
        budget=Budget(max_llm_calls=32),
        workflow=WorkflowOptions(benchmark_rca=True, database_equivalent_tools=True),
    )
    assert state.report.status == "RESOLVED"
    position = next(i for i, e in enumerate(state.events) if e.event_type == "HYPOTHESIS_RECONCILED")
    assert any(e.event_type == "REVIEW" for e in state.events[position + 1:])
    candidate = next(h for h in state.hypotheses
                     if h.hypothesis_id == state.report.root_cause.hypothesis_id)
    assert finalize_errors(state, candidate) == []


async def test_single_can_select_cross_specialty_tool_but_expert_cannot():
    class CrossTool(MockProvider):
        async def structured_call(self, role, system_prompt, user_payload, output_model):
            assert "single runtime identity" in system_prompt if role == "single" else True
            return InvestigatorPlan(calls=[ToolCall(tool_name="get_dependencies", args={})]), {
                "source": "mock",
                "llm_calls": 1,
            }

    runtime = InvestigationRun(
        CrossTool(), EvidenceProvider("data"), "incident_001", variant="single"
    )
    task = InvestigationTask(
        task_id="t",
        role="logs",
        question="Inspect cause",
        allowed_tools=["query_logs"],
        reason="test",
        expected_discriminator="dependency direction",
    )
    plan, _ = await plan_tools(
        runtime.provider, runtime.single_context, task, runtime.state.public_summary, {}
    )
    result = runtime.registry.execute(runtime.single_context, plan.calls[0].tool_name, {})
    assert result.ok
    from incident_lens.llm.provider import ProviderError

    with pytest.raises(ProviderError, match="ROLE_TOOL_PROPOSAL_FORBIDDEN"):
        await plan_tools(
            copy.copy(runtime.provider),
            runtime.registry.create_context("logs"),
            task,
            runtime.state.public_summary,
            {},
        )
