from test_feature_extraction import budget, candidate

from incident_lens.orchestration.active_investigation.cost_estimator import estimate_cost


def test_physical_attempt_bound():
    assert (
        estimate_cost(candidate(), budget(physical_request_multiplier=3)).estimated_model_requests
        == 6
    )


def test_unknown_cost_not_zero():
    cost = estimate_cost(candidate(), budget())
    assert cost.estimated_tokens is None and cost.estimated_latency_ms is None
    assert cost.source == "fixed_fallback" and cost.uncertainty_note


def test_planned_tool_bound():
    assert estimate_cost(candidate(allowed_tools=()), budget()).estimated_tool_calls == 2
    assert (
        estimate_cost(candidate(allowed_tools=("a", "b", "c")), budget()).estimated_tool_calls == 2
    )
