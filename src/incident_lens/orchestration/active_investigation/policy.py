"""Runtime adapter: detached visible projections, never an evidence provider."""

from copy import deepcopy
from time import perf_counter

from incident_lens.schemas.contracts import CoordinatorDecision, InvestigationTask
from incident_lens.security.context import DATABASE_TOOLS, ROLE_TOOL_ACL

from .contracts import BudgetView, CandidateAction, PolicyConfig, VisibleState, digest


def role_acl(workflow):
    acl = {role: tuple(ROLE_TOOL_ACL[role]) for role in ("logs", "metrics", "changes")}
    if (
        workflow.profile == "incident_response" or workflow.benchmark_rca
    ) and workflow.database_enabled:
        acl["database"] = tuple(DATABASE_TOOLS)
    if workflow.database_equivalent_tools:
        acl["metrics"] += tuple(DATABASE_TOOLS)
    return acl


def visible_projection(run, state):
    from incident_lens.orchestration.guards import evidence_fingerprint, finalize_errors

    completed = []
    mapping = getattr(run, "caes_task_signatures", {})
    terminal = {
        r.task_id
        for r in run.task_manager.records
        if r.status in {"COMPLETED", "FAILED", "CANCELLED"}
    }
    for tid in terminal:
        if tid in mapping:
            completed.append(mapping[tid])
    published = dict(
        run_id=state.run_id,
        incident_id=state.incident_id,
        decision_id=f"caes-{state.round_index + 1}",
        public_summary=state.public_summary.model_dump(mode="json"),
        hypotheses=[h.model_dump(mode="json") for h in state.hypotheses],
        requested_checks=[t.model_dump(mode="json") for t in state.requested_checks],
        open_questions=tuple(state.open_questions),
        evidence_ids=tuple(sorted(state.evidence_index)),
        observed_change_ids=tuple(
            sorted(
                {
                    str(r.metadata["change_id"])
                    for r in state.evidence_index.values()
                    if r.source_type in {"changes", "configs"}
                    and isinstance(r.metadata.get("change_id"), str)
                }
            )
        ),
        evidence_sources=tuple(sorted({r.source_type for r in state.evidence_index.values()})),
        completed_signatures=tuple(sorted(set(completed))),
        grounding_errors=tuple(
            sorted(
                {
                    error
                    for h in state.hypotheses
                    for error in finalize_errors(state, h, run.variant)
                }
            )
        ),
        stopped=run.stop_controller.stopped or state.workflow_status != "RUNNING",
    )
    board = evidence_fingerprint(state)
    # completed signatures embed a prior snapshot; exclude them from the hash to
    # avoid making the act of completion alone falsely look like new evidence.
    snapshot = digest(
        {k: v for k, v in published.items() if k not in {"decision_id", "completed_signatures"}}
        | {"board": board}
    )
    published["evidence_snapshot_sha256"] = snapshot
    # Reviewer/hypothesis wording can change while the actual queried board is
    # unchanged. Rebind completed semantic actions to today's full snapshot.
    from .candidate_generator import candidate_signature

    boards = getattr(run, "caes_task_boards", {})
    for task in state.tasks:
        if task.task_id in terminal and boards.get(task.task_id) == board:
            completed.append(
                candidate_signature(
                    CandidateAction(
                        candidate_id="completed",
                        decision_id=published["decision_id"],
                        incident_id=state.incident_id,
                        run_id=state.run_id,
                        evidence_snapshot_sha256=snapshot,
                        origin="coordinator_proposal",
                        proposed_role=task.role,
                        question=task.question,
                        expected_discriminator=task.expected_discriminator,
                        filters=deepcopy(task.filters),
                        allowed_tools=tuple(task.allowed_tools),
                    )
                )
            )
    published["completed_signatures"] = tuple(sorted(set(completed)))
    return VisibleState.model_validate_json(__import__("json").dumps(published))


def budget_projection(run):
    snapshot = run.call_budget.snapshot()
    provider = getattr(run.provider, "delegate", run.provider)
    recovery = getattr(provider, "recovery", None)
    multiplier = (
        recovery.max_physical_attempts_per_call
        if recovery and recovery.enabled
        else 1 + int(getattr(provider, "structured_repair_retries", 0))
    )
    return BudgetView(
        remaining_requests=snapshot.remaining_request_permits,
        remaining_tools=max(0, run.limits.max_tool_calls - run.registry.call_count),
        remaining_seconds=run.call_budget.remaining_seconds(),
        remaining_tokens=snapshot.remaining_tokens,
        physical_request_multiplier=max(1, multiplier),
    )


def apply_policy(run, state, proposal):
    from .candidate_generator import candidate_signature, generate_candidates
    from .eligibility import check_eligibility
    from .selector import select_candidates

    run.stop_controller.guard()
    visible = visible_projection(run, state)
    budget = budget_projection(run)
    acl = role_acl(run.workflow)
    config = run.workflow.active_evidence_config
    recovery = getattr(getattr(run.provider, "delegate", run.provider), "recovery", None)
    if recovery and recovery.enabled:
        config = PolicyConfig.model_validate(
            config.model_dump()
            | {
                "reserve_verifier_requests": max(
                    config.reserve_verifier_requests, recovery.reserve_verifier_requests
                ),
            }
        )
    started = perf_counter()
    candidates = generate_candidates(visible, tuple(proposal.assignments), acl, config)
    policy = (
        "active_evidence"
        if run.workflow.selection_policy == "current_dynamic"
        else run.workflow.selection_policy
    )
    selection = select_candidates(candidates, visible, budget, acl, config, policy)
    elapsed = (perf_counter() - started) * 1000
    run.stop_controller.guard()
    if (
        selection.decision_id != visible.decision_id
        or selection.evidence_snapshot_sha256 != visible.evidence_snapshot_sha256
        or selection.budget_snapshot_digest != digest(budget.model_dump(mode="json"))
    ):
        raise RuntimeError("STALE_SELECTION_DECISION")
    if visible_projection(run, state).evidence_snapshot_sha256 != visible.evidence_snapshot_sha256:
        raise RuntimeError("STALE_EVIDENCE_SNAPSHOT")
    latest = budget_projection(run)
    from .cost_estimator import estimate_cost

    selected_candidates = [
        c for c in candidates if c.candidate_id in selection.selected_candidate_ids
    ]
    requests = sum(estimate_cost(c, latest).estimated_model_requests for c in selected_candidates)
    tools = sum(estimate_cost(c, latest).estimated_tool_calls for c in selected_candidates)
    if (
        requests + config.reserve_verifier_requests * latest.physical_request_multiplier
        > latest.remaining_requests
        or tools + config.reserve_verifier_tools > latest.remaining_tools
        or latest.remaining_seconds <= 0
        or latest.remaining_tokens == 0
    ):
        # A zero-selection decision is already a safe stop even at exhausted budgets.
        if selected_candidates:
            raise RuntimeError("CAES_MATERIALIZATION_BUDGET_CHANGED")
    tasks = []
    signatures = {}
    by_id = {c.candidate_id: c for c in candidates}
    if len(by_id) != len(candidates):
        raise RuntimeError("DUPLICATE_CANDIDATE_ID")
    for index, cid in enumerate(selection.selected_candidate_ids):
        candidate = by_id[cid]
        if check_eligibility(candidate, visible, budget_projection(run), acl, config):
            raise RuntimeError("CAES_MATERIALIZATION_REJECTED")
        task = InvestigationTask(
            task_id=f"caes-{digest(state.run_id)[:12]}-{state.round_index + 1}-{index + 1}",
            role=candidate.proposed_role,
            question=candidate.question,
            allowed_tools=list(candidate.allowed_tools),
            filters=deepcopy(candidate.filters),
            reason=f"{config.policy_version}: {candidate.origin}",
            expected_discriminator=candidate.expected_discriminator,
        )
        if task.task_id in {t.task_id for t in state.tasks}:
            raise RuntimeError("CAES_TASK_ID_COLLISION")
        tasks.append(task)
        signatures[task.task_id] = candidate_signature(candidate)
    # No mutable DTO or selector result is published as evidence.
    details = dict(
        visible=visible.model_dump(mode="json"),
        candidates=[c.model_dump(mode="json") for c in candidates],
        budget=budget.model_dump(mode="json"),
        config=config.model_dump(mode="json"),
        role_acl={r: list(t) for r, t in acl.items()},
        selection=selection.model_dump(mode="json"),
        coordinator_proposed_tasks=[t.model_dump(mode="json") for t in proposal.assignments],
        selector_executed_tasks=[]
        if run.workflow.shadow_caes
        else [t.model_dump(mode="json") for t in tasks],
        shadow=run.workflow.shadow_caes,
        candidate_generation_calls=0,
        generation_elapsed_ms=elapsed,
    )
    run.event(
        state,
        "CANDIDATES_GENERATED",
        candidate_ids=[c.candidate_id for c in candidates],
        candidate_generation_calls=0,
        generation_elapsed_ms=elapsed,
    )
    run.event(state, "ACTION_SELECTED", **details)
    if run.workflow.shadow_caes:
        return proposal
    if not tasks:
        return CoordinatorDecision(
            action="ABSTAIN", reason="NO_USEFUL_ACTION", stop_reason="NO_USEFUL_ACTION"
        )
    run.caes_task_signatures = getattr(run, "caes_task_signatures", {}) | signatures
    from incident_lens.orchestration.guards import evidence_fingerprint

    run.caes_task_boards = getattr(run, "caes_task_boards", {}) | {
        task.task_id: evidence_fingerprint(state) for task in tasks
    }
    return CoordinatorDecision(action="INVESTIGATE", reason=proposal.reason, assignments=tasks)
