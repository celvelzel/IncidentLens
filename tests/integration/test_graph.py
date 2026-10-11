import asyncio
import json

import pytest

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import finalize_errors
from incident_lens.schemas import Budget, Hypothesis, InvestigationState

EXPECTED = [
    "backend_pool_config_regression",
    "postgres_connection_exhaustion",
    "redis_unavailable",
    "payment_external_timeout",
    "backend_resource_saturation",
]


@pytest.mark.parametrize("number,mode", list(enumerate(EXPECTED, 1)))
async def test_five_seed_graph_runs(number, mode):
    state = await run_investigation(f"incident_{number:03}", MockProvider())
    assert state.report.status == "RESOLVED"
    assert state.report.root_cause.failure_mode == mode
    assert set(state.report.supporting_evidence_ids).issubset(state.evidence_index)
    assert state.tool_calls_used <= 12 and state.llm_calls_used <= 16
    assert InvestigationState.model_validate_json(state.model_dump_json()) == state


async def test_verifier_changes_route_and_no_parallel_findings_lost():
    state = await run_investigation("incident_001", MockProvider())
    assert [t.role for t in state.decisions[0].assignments] == ["logs", "metrics"]
    assert {f.role for f in state.findings[:2]} == {"logs", "metrics"}
    assert state.reviews[0].verdict == "insufficient"
    assert state.reviews[0].contradictions
    assert state.decisions[1].assignments == state.reviews[0].requested_checks
    assert state.decisions[2].assignments[0].filters["change_id"]
    assert any(h.status == "REJECTED" for h in state.hypotheses)
    assert "private/ground_truth.json" not in json.dumps(
        state.model_dump(mode="json")["public_summary"]
    )


async def test_missing_case_abstains_and_gate_blocks_fabrication():
    state = await run_investigation("incident_006", MockProvider())
    assert state.report.status == "INCONCLUSIVE" and state.report.root_cause is None
    fake = Hypothesis(
        hypothesis_id="fake",
        culprit_service="backend",
        failure_mode="guess",
        support_ids=["not-observed"],
        status="SUPPORTED",
    )
    assert finalize_errors(state, fake)


async def test_no_verifier_replans_from_safe_shared_catalog():
    state = await run_investigation("incident_001", MockProvider(), variant="dynamic_no_verifier")
    assert state.report.status == "RESOLVED"
    assert state.report.root_cause.failure_mode == "backend_pool_config_regression"
    assert state.reviews == []
    assert state.llm_calls_used == 12 and state.tool_calls_used == 6
    assert state.decisions[1].assignments[0].role == "changes"


async def test_dynamic_dispatch_rejects_more_than_two_assignments():
    from incident_lens.schemas import CoordinatorDecision

    class Oversized(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if issubclass(args[-1], CoordinatorDecision) and output.action == "INVESTIGATE":
                output.assignments.append(
                    output.assignments[0].model_copy(update={"task_id": "third"})
                )
            return output, usage

    state = await run_investigation("incident_001", Oversized())
    assert state.report.status == "INCONCLUSIVE"
    assert "at most two" in state.report.stop_reason
    assert state.tool_calls_used == 0 and state.llm_calls_used == 1


async def test_expert_hypothesis_aliases_merge_into_stable_cause_identity():
    class Aliases(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "AnalysisOutput":
                for hypothesis in output.hypotheses:
                    hypothesis.hypothesis_id = args[0] + "-" + hypothesis.hypothesis_id
            return output, usage

    state = await run_investigation("incident_001", Aliases())
    assert state.report.status == "RESOLVED"
    concepts = {(h.culprit_service, h.failure_mode) for h in state.hypotheses}
    assert len(concepts) == len(state.hypotheses)
    database = next(h for h in state.hypotheses if h.culprit_service == "postgres")
    assert database.status == "REJECTED" and database.support_ids and database.against_ids


async def test_duplicate_finding_id_cannot_silently_drop_an_expert():
    class Duplicate(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "AnalysisOutput":
                output.finding.finding_id = "same-for-both"
            return output, usage

    state = await run_investigation("incident_001", Duplicate())
    assert state.report.status == "INCONCLUSIVE"
    assert state.findings == [] and state.evidence_index == {}


async def test_hypothesis_citations_publish_even_when_not_in_finding():
    class NarrowFinding(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "AnalysisOutput":
                output.finding.evidence_ids = output.finding.evidence_ids[:1]
            return output, usage

    state = await run_investigation("incident_001", NarrowFinding())
    assert state.report.status == "RESOLVED"
    finding_refs = {eid for finding in state.findings for eid in finding.evidence_ids}
    hypothesis_refs = {eid for h in state.hypotheses for eid in h.support_ids + h.against_ids}
    assert hypothesis_refs - finding_refs
    assert hypothesis_refs.issubset(state.evidence_index)


async def test_same_batch_hypothesis_status_is_independent_of_task_order():
    class Reversed(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "DynamicDecision":
                output.assignments.reverse()
            return output, usage

    normal = await run_investigation("incident_001", MockProvider())
    reversed_state = await run_investigation("incident_001", Reversed())
    assert normal.report.status == reversed_state.report.status == "RESOLVED"
    assert normal.report.root_cause.failure_mode == reversed_state.report.root_cause.failure_mode
    assert (
        next(h for h in reversed_state.hypotheses if h.culprit_service == "postgres").status
        == "REJECTED"
    )


@pytest.mark.parametrize("reverse", [False, True])
async def test_conflicting_grounded_assessments_stay_open(reverse):
    class Conflicting(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "DynamicDecision" and reverse:
                output.assignments.reverse()
            if args[-1].__name__ == "AnalysisOutput" and args[0] == "logs":
                for h in output.hypotheses:
                    if h.culprit_service == "postgres":
                        h.status = "SUPPORTED"
            return output, usage

    state = await run_investigation("incident_001", Conflicting(), budget=Budget(max_rounds=1))
    h = next(h for h in state.hypotheses if h.culprit_service == "postgres")
    assert h.status == "OPEN" and h.support_ids and h.against_ids
    assert "Conflicting current assessments" in " ".join(h.open_questions)
    assert state.report.status == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "budget",
    [
        Budget(max_tool_calls=0),
        Budget(max_llm_calls=1),
        Budget(max_rounds=1),
        Budget(max_wall_seconds=0.001),
    ],
)
async def test_budget_exhaustion_terminates(budget):
    state = await run_investigation("incident_001", MockProvider(), budget=budget)
    assert state.report.status == "INCONCLUSIVE"
    assert state.llm_calls_used <= budget.max_llm_calls
    assert state.tool_calls_used <= budget.max_tool_calls
    assert state.report.stop_reason


async def test_parallel_incidents_do_not_share_state_or_provider_budget():
    provider = MockProvider()
    first, second = await asyncio.gather(
        run_investigation("incident_001", provider), run_investigation("incident_003", provider)
    )
    assert first.run_id != second.run_id
    assert not (set(first.evidence_index) & set(second.evidence_index))
    assert all(r.incident_id == first.incident_id for r in first.evidence_index.values())
    assert all(e.run_id == second.run_id for e in second.events)
    assert first.report.status == second.report.status == "RESOLVED"
