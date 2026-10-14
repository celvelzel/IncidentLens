"""Conservative physical-request fallback; never charges runtime permits."""

from .contracts import BudgetView, CandidateAction, CostEstimate


def estimate_cost(candidate: CandidateAction, budget: BudgetView) -> CostEstimate:
    return CostEstimate(
        estimated_model_requests=2 * budget.physical_request_multiplier,
        estimated_tool_calls=2,
        source="fixed_fallback",
        uncertainty_note="Two logical Investigator requests with configured physical attempt bound; tokens and latency uncalibrated.",
    )
