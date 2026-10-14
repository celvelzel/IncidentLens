"""Validate saved public selection snapshots without providers or tools."""

from incident_lens.orchestration.active_investigation.contracts import (
    BudgetView,
    CandidateAction,
    PolicyConfig,
    SelectionDecision,
    VisibleState,
    digest,
)


def replay_selection(details):
    visible = VisibleState.model_validate(details["visible"])
    candidates = tuple(CandidateAction.model_validate(c) for c in details["candidates"])
    budget = BudgetView.model_validate(details["budget"])
    config = PolicyConfig.model_validate(details["config"])
    saved = SelectionDecision.model_validate(details["selection"])
    from incident_lens.orchestration.active_investigation.selector import select_candidates

    computed = select_candidates(
        candidates,
        visible,
        budget,
        {k: tuple(v) for k, v in details["role_acl"].items()},
        config,
        saved.policy,
    )
    if computed.model_dump(mode="json") != saved.model_dump(mode="json"):
        raise ValueError("selection replay mismatch")
    return dict(
        decision_id=saved.decision_id,
        match=True,
        selection_sha256=digest(saved.model_dump(mode="json")),
    )
