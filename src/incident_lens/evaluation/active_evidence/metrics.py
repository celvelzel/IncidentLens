"""Selection diagnostics from actual runtime events; estimates stay separate."""


def selection_events(state):
    return [
        event["details"]
        for event in state.get("events", [])
        if event.get("event_type") == "ACTION_SELECTED"
    ]


def selection_metrics(state):
    decisions = selection_events(state)
    assessments = [a for d in decisions for a in d["selection"]["assessments"]]
    return dict(
        tool_calls=state.get("tool_calls_used"),
        selection_rounds=len(decisions),
        candidate_pool_size=sum(len(d["candidates"]) for d in decisions),
        eligible_candidates=sum(a["eligibility"] == "ELIGIBLE" for a in assessments),
        selected_tasks=sum(len(d["selection"]["selected_candidate_ids"]) for d in decisions),
        candidate_generation_calls=sum(d.get("candidate_generation_calls", 0) for d in decisions),
        human_grounded_success=None,
        human_review_coverage=0,
    )
