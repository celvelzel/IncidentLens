"""Explainable lexical heuristics over published observations only."""

import re
from itertools import combinations

from .candidate_generator import candidate_signature
from .contracts import CandidateAction, CandidateFeatures, CostEstimate, VisibleState

_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "check", "whether", "observed"}


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _STOP


def same_check(candidate, task):
    return (
        candidate.proposed_role == task.role
        and candidate.filters == task.filters
        and tokens(candidate.question) == tokens(task.question)
        and tokens(candidate.expected_discriminator) == tokens(task.expected_discriminator)
    )


def extract_features(
    candidate: CandidateAction, visible: VisibleState, cost: CostEstimate
) -> CandidateFeatures:
    observable = tokens(candidate.question + " " + candidate.expected_discriminator)
    hypotheses = [
        h
        for h in visible.hypotheses
        if h.status != "REJECTED"
        and (
            not candidate.target_hypothesis_ids
            or h.hypothesis_id in candidate.target_hypothesis_ids
        )
    ]
    pairs = list(combinations(hypotheses, 2))
    distinct = 0
    for left, right in pairs:
        lp = {frozenset(tokens(p)) for p in left.predicted_observations if tokens(p)}
        rp = {frozenset(tokens(p)) for p in right.predicted_observations if tokens(p)}
        # Different published predictions must share an observable with this action.
        if (
            lp
            and rp
            and lp != rp
            and observable & (set().union(*lp) ^ set().union(*rp))
            and any(observable & (set(p) - set(visible.public_summary.services)) for p in lp)
            and any(observable & (set(p) - set(visible.public_summary.services)) for p in rp)
        ):
            distinct += 1
    discrimination = distinct / len(pairs) if pairs else 0.0
    requested = any(same_check(candidate, task) for task in visible.requested_checks)
    questions = list(visible.open_questions) + [q for h in hypotheses for q in h.open_questions]
    gap = (
        1.0
        if requested
        else max(
            (len(observable & tokens(q)) / max(1, len(tokens(q))) for q in questions), default=0.0
        )
    )
    # Missing source is independent of predicted-observation discrimination.
    missing_source = candidate.proposed_role not in visible.evidence_sources
    gate = 0.5 if missing_source else 0.0
    if missing_source and visible.grounding_errors:
        gate = 1.0
    repeated = candidate_signature(candidate) in visible.completed_signatures
    return CandidateFeatures(
        discrimination=discrimination,
        gap_coverage=gap,
        gate_contribution=gate,
        redundancy=1.0 if repeated else 0.0,
        cost=cost,
        explanations=(
            f"distinct observable prediction pairs={distinct}/{len(pairs)}",
            f"published requested check={requested}; gap={gap:.3f}",
            f"missing source={missing_source}; grounding gaps={len(visible.grounding_errors)}",
            f"completed identical snapshot check={repeated}",
        ),
    )
