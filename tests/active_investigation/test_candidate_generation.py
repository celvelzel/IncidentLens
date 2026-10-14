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


def test_multi_service_cap_preserves_role_diversity():
    state = visible()
    summary = state.public_summary.model_copy(
        update={"services": ["backend", "frontend", "postgres", "worker"]}
    )
    state = state.model_copy(update={"public_summary": summary})
    acl = ACL | {"database": ("get_db_connections",)}
    proposals = (task(), task(task_id="second", question="Check timeout onset"))
    result = generate_candidates(state, proposals, acl, PolicyConfig())
    assert len(result) == 6
    assert [item.existing_task_id for item in result[:2]] == ["t", "second"]
    assert len({item.proposed_role for item in result}) == 4
    assert [item.proposed_role for item in result[2:]] == ["logs", "metrics", "database", "changes"]
    assert result == generate_candidates(state, proposals, acl, PolicyConfig())


def test_templates_use_full_explicit_runtime_acl():
    acl = ACL | {
        "metrics": ("query_metrics", "get_dependencies"),
        "database": ("get_db_connections", "get_db_lock_waits"),
    }
    result = generate_candidates(visible(), (), acl, PolicyConfig())
    assert all(item.allowed_tools == acl[item.proposed_role] for item in result)
    assert next(item for item in result if item.proposed_role == "metrics").filters == {
        "service": "backend"
    }


def test_invalid_requested_checks_cannot_starve_proposal():
    checks = tuple(
        task(
            task_id=f"db{i}",
            role="database",
            allowed_tools=["get_db_connections"],
            question=f"Check database {i}",
        )
        for i in range(6)
    )
    result = generate_candidates(visible(requested_checks=checks), (task(),), ACL, PolicyConfig())
    assert len(result) == 6
    assert result[0].origin == "coordinator_proposal"
    assert result[0].existing_task_id == "t"
    assert len([item for item in result if item.origin == "public_task_template"]) == 3
    assert len([item for item in result if item.origin == "verifier_requested_check"]) == 2
