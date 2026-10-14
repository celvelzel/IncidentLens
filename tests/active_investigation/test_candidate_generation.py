from datetime import datetime, timezone

from incident_lens.orchestration.active_investigation.candidate_generator import (
    candidate_signature,
    generate_candidates,
)
from incident_lens.orchestration.active_investigation.contracts import PolicyConfig, VisibleState
from incident_lens.schemas import InvestigationTask
from incident_lens.schemas.contracts import CasePublicInput

ACL = {"logs": ("query_logs",), "metrics": ("get_dependencies",), "changes": ("query_changes",)}


def visible(**changes):
    values = dict(
        run_id="r",
        incident_id="i",
        decision_id="d",
        evidence_snapshot_sha256="board",
        public_summary=CasePublicInput(
            incident_id="i",
            title="Failure",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            observed_symptoms=["errors"],
            services=["backend"],
        ),
    )
    return VisibleState(**(values | changes))


def task(**changes):
    return InvestigationTask(
        **(
            dict(
                task_id="t",
                role="logs",
                question="Check errors",
                allowed_tools=["query_logs"],
                filters={"service": "backend"},
                reason="investigate",
                expected_discriminator="Error onset distinguishes propagation",
            )
            | changes
        )
    )


def test_three_origins_and_replay():
    state = visible(requested_checks=(task(task_id="review", question="Check retries"),))
    result = generate_candidates(state, (task(),), ACL, PolicyConfig())
    assert {c.origin for c in result} == {
        "coordinator_proposal",
        "verifier_requested_check",
        "public_task_template",
    }
    assert result == generate_candidates(state, (task(),), ACL, PolicyConfig())
    proposal = next(c for c in result if c.origin == "coordinator_proposal")
    assert proposal.filters == task().filters
    assert proposal.existing_task_id == "t"
    assert proposal.expected_discriminator == task().expected_discriminator


def test_cold_start_public_acl_and_window():
    result = generate_candidates(visible(), (), ACL, PolicyConfig())
    assert len(result) == 3
    assert all(c.proposed_role != "database" for c in result)
    logs = next(c for c in result if c.proposed_role == "logs")
    assert logs.filters["start_ts"] == "2025-12-31T23:45:00+00:00"
    assert logs.filters["end_ts"] == "2026-01-01T00:15:00+00:00"


def test_dedup_request_precedence_and_cap():
    result = generate_candidates(
        visible(requested_checks=(task(task_id="review"),)),
        (task(),),
        ACL,
        PolicyConfig(candidate_pool_limit=1),
    )
    assert len(result) == 1
    assert result[0].origin == "verifier_requested_check"
    assert result[0].existing_task_id == "review"


def test_semantic_changes_not_merged():
    tasks = (
        task(),
        task(task_id="t2", question="Do not check errors"),
        task(task_id="t3", filters={"service": "backend", "start_ts": "2026-01-01T00:00:00Z"}),
    )
    result = generate_candidates(visible(), tasks, ACL, PolicyConfig())
    assert len({candidate_signature(c) for c in result if c.origin == "coordinator_proposal"}) == 3
    first = result[0]
    assert candidate_signature(first) == candidate_signature(
        first.model_copy(update={"candidate_id": "other", "decision_id": "other"})
    )
    assert candidate_signature(first) != candidate_signature(
        first.model_copy(update={"evidence_snapshot_sha256": "new"})
    )


def test_stop_empty_no_private_io(monkeypatch):
    import builtins

    def forbidden(*args, **kwargs):
        raise AssertionError("Candidate generation cannot open files")

    monkeypatch.setattr(builtins, "open", forbidden)
    assert generate_candidates(visible(stopped=True), (), ACL, PolicyConfig()) == ()
    assert generate_candidates(visible(), (), ACL, PolicyConfig())


def test_deterministic_service_order_and_no_mutation():
    state = visible()
    original = state.model_dump_json()
    generate_candidates(state, (task(),), ACL, PolicyConfig())
    assert state.model_dump_json() == original
    assert generate_candidates(state, (), {}, PolicyConfig()) == ()
