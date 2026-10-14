"""Deterministic candidates from published tasks and bounded public templates."""

from datetime import timedelta

from incident_lens.schemas import InvestigationTask

from .contracts import BudgetView, CandidateAction, PolicyConfig, VisibleState, digest


def candidate_signature(candidate: CandidateAction) -> str:
    """Semantic identity, excluding local/runtime task IDs and source origin."""
    return digest(
        {
            "role": candidate.proposed_role,
            "question": " ".join(candidate.question.split()),
            "discriminator": " ".join(candidate.expected_discriminator.split()),
            "filters": candidate.filters,
            "tools": sorted(set(candidate.allowed_tools)),
            "targets": sorted(set(candidate.target_hypothesis_ids)),
            "prerequisites": sorted(set(candidate.prerequisites)),
            "snapshot": candidate.evidence_snapshot_sha256,
        }
    )


def generate_candidates(
    visible: VisibleState,
    proposals: tuple[InvestigationTask, ...],
    role_acl: dict[str, tuple[str, ...]],
    config: PolicyConfig,
) -> tuple[CandidateAction, ...]:
    if visible.stopped:
        return ()
    candidates = []

    def add(origin, role, question, discriminator, filters, tools, task_id=None):
        item = CandidateAction(
            candidate_id="pending",
            decision_id=visible.decision_id,
            incident_id=visible.incident_id,
            run_id=visible.run_id,
            evidence_snapshot_sha256=visible.evidence_snapshot_sha256,
            origin=origin,
            proposed_role=role,
            question=question,
            expected_discriminator=discriminator,
            filters=filters,
            allowed_tools=tuple(tools),
            existing_task_id=task_id,
        )
        signature = candidate_signature(item)
        item = item.model_copy(
            update={
                "candidate_id": "ca-"
                + digest({"decision": visible.decision_id, "signature": signature})[:24]
            }
        )
        candidates.append(item)

    # Preserve proposal order for first_eligible; duplicate requests take precedence.
    for origin, tasks in (
        ("coordinator_proposal", proposals),
        ("verifier_requested_check", visible.requested_checks),
    ):
        for task in tasks:
            add(
                origin,
                task.role,
                task.question,
                task.expected_discriminator,
                task.filters,
                task.allowed_tools,
                task.task_id,
            )
    start = (visible.public_summary.started_at - timedelta(minutes=15)).isoformat()
    end = (visible.public_summary.started_at + timedelta(minutes=15)).isoformat()
    templates = (
        (
            "logs",
            "query_logs",
            "Check error onset and retry propagation",
            "Error timing and propagation differ across services",
        ),
        (
            "metrics",
            "get_dependencies",
            "Check service dependency health",
            "Dependency relationships identify upstream versus downstream exposure",
        ),
        (
            "database",
            "get_db_connections",
            "Check connection capacity and active usage",
            "Observed connection usage distinguishes capacity pressure from normal operation",
        ),
        (
            "changes",
            "query_changes",
            "Check deployments and configuration changes",
            "Change timing distinguishes recent changes from unchanged configuration",
        ),
    )
    # Round-robin roles before advancing services, so the pool cap cannot let
    # one role's service expansion crowd out other legal investigations.
    for service in sorted(set(visible.public_summary.services)):
        for role, tool, question, discriminator in templates:
            if tool not in role_acl.get(role, ()):
                continue
            filters = {"service": service}
            if tool != "get_dependencies":
                filters.update(start_ts=start, end_ts=end)
            add(
                "public_task_template",
                role,
                f"{question} for {service}",
                discriminator,
                filters,
                role_acl[role],
            )
    unique = {}
    priorities = {
        "verifier_requested_check": 0,
        "coordinator_proposal": 1,
        "public_task_template": 2,
    }
    for item in candidates:
        signature = candidate_signature(item)
        if (
            signature not in unique
            or priorities[item.origin] < priorities[unique[signature].origin]
        ):
            unique[signature] = item
    # Invalid requests must not crowd executable work out of the bounded pool.
    # Local import avoids a module cycle: eligibility uses the public signature.
    from .eligibility import check_eligibility

    validation_budget = BudgetView(
        remaining_requests=10**9, remaining_tools=10**9, remaining_seconds=10**9
    )

    def priority(item):
        invalid = check_eligibility(item, visible, validation_budget, role_acl, config) is not None
        legal_priority = {
            "coordinator_proposal": 0,
            "verifier_requested_check": 1,
            "public_task_template": 2,
        }
        return (invalid, legal_priority[item.origin])

    ordered = sorted(unique.values(), key=priority)
    return tuple(ordered[: config.candidate_pool_limit])
