"""Deterministic CAES ranking with aggregate feasibility and no execution."""

from .contracts import CandidateAssessment, SelectionDecision, digest
from .cost_estimator import estimate_cost
from .eligibility import check_eligibility
from .feature_extractors import extract_features, tokens


def overlap(left, right):
    if left.proposed_role != right.proposed_role or left.filters != right.filters:
        return 0.0
    lt = tokens(left.question + " " + left.expected_discriminator)
    rt = tokens(right.question + " " + right.expected_discriminator)
    if (lt & {"no", "not", "without"}) != (rt & {"no", "not", "without"}):
        return 0.0
    return len(lt & rt) / max(1, len(lt | rt))


def select_candidates(candidates, visible, budget, role_acl, config, policy):
    if policy == "current_dynamic":
        raise ValueError("current_dynamic must bypass CAES")
    if policy not in {
        "first_eligible",
        "active_evidence",
        "active_no_cost",
        "active_no_discrimination",
    }:
        raise ValueError("unsupported CAES policy")
    assessments = []
    entries = []
    for index, candidate in enumerate(candidates):
        reason = (
            "STOPPED"
            if visible.stopped
            else check_eligibility(candidate, visible, budget, role_acl, config)
        )
        cost = estimate_cost(candidate, budget)
        if (
            reason is None
            and cost.estimated_model_requests
            + (config.reserve_verifier_requests * budget.physical_request_multiplier)
            > budget.remaining_requests
        ):
            reason = "INSUFFICIENT_LLM_BUDGET"
        if (
            reason is None
            and cost.estimated_tool_calls + config.reserve_verifier_tools > budget.remaining_tools
        ):
            reason = "INSUFFICIENT_TOOL_BUDGET"
        if reason:
            assessments.append(
                CandidateAssessment(
                    candidate_id=candidate.candidate_id,
                    eligibility="REJECTED",
                    reject_reason=reason,
                )
            )
            continue
        feature = extract_features(candidate, visible, cost)
        value = (
            (0 if policy == "active_no_discrimination" else config.discrimination_weight)
            * feature.discrimination
            + config.gap_weight * feature.gap_coverage
            + config.gate_weight * feature.gate_contribution
            - config.redundancy_weight * feature.redundancy
        )
        denominator = (
            1.0
            if policy == "active_no_cost"
            else config.epsilon
            + config.request_weight * cost.estimated_model_requests
            + config.tool_weight * cost.estimated_tool_calls
        )
        score = value / denominator
        entries.append((candidate, feature, score, index))
        assessments.append(
            CandidateAssessment(
                candidate_id=candidate.candidate_id,
                eligibility="ELIGIBLE",
                features=feature,
                score=score,
            )
        )
    ordered = sorted(
        entries,
        key=(lambda e: e[3])
        if policy == "first_eligible"
        else (lambda e: (-e[2], e[0].candidate_id)),
    )
    ranks = {e[0].candidate_id: i + 1 for i, e in enumerate(ordered)}
    selected = []
    requests = tools = 0
    for candidate, feature, score, _ in ordered:
        if len(selected) >= config.max_selected_tasks:
            break
        similarity = max((overlap(candidate, prior) for prior in selected), default=0.0)
        if similarity >= config.redundancy_hard_limit:
            continue
        if policy != "first_eligible" and (
            score <= max(0.0, config.min_score)
            or score - config.diversity_penalty * similarity <= max(0.0, config.min_score)
        ):
            continue
        cost = feature.cost
        if (
            requests
            + cost.estimated_model_requests
            + (config.reserve_verifier_requests * budget.physical_request_multiplier)
            > budget.remaining_requests
            or tools + cost.estimated_tool_calls + config.reserve_verifier_tools
            > budget.remaining_tools
        ):
            continue
        selected.append(candidate)
        requests += cost.estimated_model_requests
        tools += cost.estimated_tool_calls
    return SelectionDecision(
        decision_id=visible.decision_id,
        policy=policy,
        policy_version=config.policy_version,
        evidence_snapshot_sha256=visible.evidence_snapshot_sha256,
        selected_candidate_ids=tuple(c.candidate_id for c in selected),
        assessments=tuple(
            a.model_copy(update={"rank": ranks.get(a.candidate_id)}) for a in assessments
        ),
        budget_snapshot_digest=digest(budget.model_dump(mode="json")),
        fallback_reason=None if selected else "NO_USEFUL_ACTION",
    )
