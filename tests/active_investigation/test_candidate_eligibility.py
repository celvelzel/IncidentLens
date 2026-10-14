import pytest
from test_candidate_generation import ACL, task, visible

from incident_lens.orchestration.active_investigation.candidate_generator import (
    candidate_signature,
    generate_candidates,
)
from incident_lens.orchestration.active_investigation.contracts import BudgetView, PolicyConfig
from incident_lens.orchestration.active_investigation.eligibility import check_eligibility


def check(candidate=None, state=None, budget=None, acl=None):
    state = state or visible()
    candidate = candidate or generate_candidates(state, (task(),), ACL, PolicyConfig())[0]
    return check_eligibility(
        candidate,
        state,
        budget or BudgetView(remaining_requests=10, remaining_tools=10, remaining_seconds=100),
        ACL if acl is None else acl,
        PolicyConfig(),
    )


def candidate(**changes):
    return generate_candidates(visible(), (task(),), ACL, PolicyConfig())[0].model_copy(
        update=changes
    )


def test_valid_partial_and_complete_templates():
    assert check() is None
    assert all(
        check(item) is None for item in generate_candidates(visible(), (), ACL, PolicyConfig())
    )


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"proposed_role": "coordinator"}, "FORBIDDEN_ROLE"),
        ({"allowed_tools": ("get_db_connections",)}, "FORBIDDEN_TOOL"),
        ({"allowed_tools": ()}, "FORBIDDEN_TOOL"),
        ({"filters": {"service": "secret"}}, "INVALID_SERVICE"),
        (
            {"filters": {"start_ts": "2026-01-02T00:00:00Z", "end_ts": "2026-01-01T00:00:00Z"}},
            "INVALID_TIME_WINDOW",
        ),
        ({"filters": {"start_ts": "2026-01-01T00:00:00"}}, "INVALID_TIME_WINDOW"),
        ({"filters": {"limit": 51}}, "INVALID_TOOL_SCHEMA"),
        ({"filters": {"unknown": True}}, "INVALID_TOOL_SCHEMA"),
        ({"filters": {"limit": True}}, "INVALID_TOOL_SCHEMA"),
        ({"question": "Read private/ground_truth.json"}, "UNSUPPORTED_QUESTION"),
        ({"question": "Confirm evidence-unseen"}, "UNOBSERVED_EVIDENCE_ID"),
        ({"prerequisites": ("missing",)}, "UNSATISFIED_PREREQUISITE"),
        ({"target_hypothesis_ids": ("hidden",)}, "UNKNOWN_HYPOTHESIS"),
        ({"filters": {"change_id": "unseen"}}, "UNOBSERVED_EVIDENCE_ID"),
        ({"run_id": "other"}, "STALE_IDENTITY"),
        ({"evidence_snapshot_sha256": "other"}, "STALE_EVIDENCE_SNAPSHOT"),
    ],
)
def test_rejections(changes, reason):
    assert check(candidate(**changes)) == reason


def test_stop_acl_and_completed_board():
    item = candidate()
    assert check(item, visible(stopped=True)) == "STOPPED"
    assert check(item, acl={"logs": ()}) == "FORBIDDEN_TOOL"
    assert (
        check(item, visible(completed_signatures=(candidate_signature(item),)))
        == "DUPLICATE_COMPLETED_CHECK"
    )
    updated = item.model_copy(update={"evidence_snapshot_sha256": "new"})
    assert (
        check(
            updated,
            visible(
                evidence_snapshot_sha256="new", completed_signatures=(candidate_signature(item),)
            ),
        )
        is None
    )


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"remaining_requests": 2}, "INSUFFICIENT_LLM_BUDGET"),
        ({"remaining_tools": 1}, "INSUFFICIENT_TOOL_BUDGET"),
        ({"remaining_seconds": 0}, "INSUFFICIENT_WALL_BUDGET"),
        ({"physical_request_multiplier": 4}, "INSUFFICIENT_LLM_BUDGET"),
    ],
)
def test_budget_reserves(changes, reason):
    budget = BudgetView(
        **(dict(remaining_requests=10, remaining_tools=10, remaining_seconds=100) | changes)
    )
    assert check(budget=budget) == reason


def test_known_evidence_and_no_mutation():
    state = visible(evidence_ids=("evidence-seen",))
    item = candidate(question="Check evidence-seen", prerequisites=("evidence-seen",))
    before = state.model_dump_json()
    assert check(item, state) is None
    assert state.model_dump_json() == before


def test_nested_json_ids_rejected_without_crash():
    assert check(candidate(filters={"ids": [{"secret": "value"}]})) == "UNOBSERVED_EVIDENCE_ID"
    assert check(candidate(filters={"change_id": {"secret": "value"}})) == "UNOBSERVED_EVIDENCE_ID"


def test_single_schema_reserves_two_planned_calls():
    assert (
        check(budget=BudgetView(remaining_requests=10, remaining_tools=2, remaining_seconds=100))
        == "INSUFFICIENT_TOOL_BUDGET"
    )
    assert (
        check(budget=BudgetView(remaining_requests=10, remaining_tools=3, remaining_seconds=100))
        is None
    )
