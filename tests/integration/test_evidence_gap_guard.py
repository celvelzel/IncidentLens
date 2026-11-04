"""Evidence-gap cost guard: stop searching when no round can change the answer.

The guard is calibrated against the frozen WP-D batch: 4 consecutive rounds
without a cause-specific discriminator never fired on an identifiable case and
fired on both unidentifiable ones. These tests pin that behaviour without
depending on a real provider.
"""

from datetime import datetime, timezone

import pytest

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import cause_discriminator
from incident_lens.schemas import Budget, EvidenceRecord, Hypothesis
from incident_lens.schemas.workflow import WorkflowOptions


async def test_default_limit_keeps_identifiable_cases_resolved():
    state = await run_investigation("incident_001", MockProvider(), variant="dynamic")
    assert state.report.status == "RESOLVED"
    assert not [
        e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"
    ]


@pytest.mark.parametrize("limit", [1, 2, 3])
async def test_lower_limits_stop_before_the_discriminator_arrives(limit):
    # incident_001 gains its cause-specific discriminator only after two
    # evidence rounds; any ceiling below that must abstain rather than
    # continue, which is exactly the trade-off the default of 4 avoids.
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        workflow=WorkflowOptions(evidence_gap_rounds=limit),
    )
    assert state.report.status == "INCONCLUSIVE"
    assert state.report.root_cause is None
    fired = [
        e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"
    ]
    assert len(fired) == 1


async def test_zero_disables_the_guard_entirely():
    # The pre-P0 behaviour must stay reachable so frozen protocols can opt out.
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        workflow=WorkflowOptions(evidence_gap_rounds=0),
    )
    assert state.report.status == "RESOLVED"
    assert state.round_index == 3
    assert not [
        e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"
    ]


async def test_early_abstention_publishes_an_auditable_cost_snapshot():
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        workflow=WorkflowOptions(evidence_gap_rounds=2),
    )
    fired = [
        e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"
    ][0]
    cost = fired.details["cost"]
    assert cost["trigger"] == "no_cause_specific_discriminator"
    assert cost["gap_rounds_limit"] == 2
    assert cost["gap_streak"] >= 2
    for key in (
        "round_index",
        "tool_calls",
        "llm_requests",
        "tokens",
        "elapsed_ms",
        "remaining_requests",
        "remaining_rounds",
        "remaining_tool_calls",
    ):
        assert key in cost
    # The snapshot must describe spent resources, not a prediction of them.
    assert cost["llm_requests"] <= state.budgets.max_llm_calls
    assert cost["tool_calls"] <= state.budgets.max_tool_calls
    assert cost["tokens"] <= state.tokens_used


async def test_guard_never_overrides_the_fixed_schedule():
    # ``fixed`` runs one deterministic batch by design; its early abstention is
    # already decided by the schedule, so the gap guard must not fire there.
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="fixed",
        workflow=WorkflowOptions(evidence_gap_rounds=1, benchmark_rca=True,
                                 database_equivalent_tools=True),
    )
    assert not [
        e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"
    ]


def test_discriminator_predicate_is_the_grounding_one():
    """The guard must reuse grounding, not a second definition of evidence."""
    record = EvidenceRecord.model_validate(
        {
            "evidence_id": "E-1",
            "incident_id": "incident_001",
            "source_type": "configs",
            "source_path": "public/configs/backend-runtime-1.yaml",
            "service": "backend",
            "observed_at": datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc),
            "excerpt": "db_pool_max 20 -> 2 concurrency: 40",
            "metadata": {"change_id": "runtime-1"},
        }
    )
    hypothesis = Hypothesis(
        hypothesis_id="h-1",
        culprit_service="backend",
        failure_mode="backend_pool_config_regression",
        support_ids=["E-1"],
        status="SUPPORTED",
    )
    assert cause_discriminator(hypothesis, record)


async def test_guard_does_not_change_acceptance_semantics():
    """Same board, same conclusion: only the number of rounds differs."""
    strict = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        workflow=WorkflowOptions(evidence_gap_rounds=4),
    )
    disabled = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        workflow=WorkflowOptions(evidence_gap_rounds=0),
    )
    assert strict.report.status == disabled.report.status == "RESOLVED"
    assert strict.report.root_cause == disabled.report.root_cause
    assert strict.report.supporting_evidence_ids == disabled.report.supporting_evidence_ids


async def test_guard_respects_the_round_budget():
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        variant="dynamic",
        budget=Budget(max_rounds=1),
        workflow=WorkflowOptions(evidence_gap_rounds=4),
    )
    assert state.report.status == "INCONCLUSIVE"
    assert state.report.stop_reason
    assert state.round_index <= 1
