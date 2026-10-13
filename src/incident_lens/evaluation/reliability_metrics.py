"""Reliability summaries with explicit denominators and unknown usage."""


def aggregate_reliability(rows):
    """Only provider rows are ablations; runtime checks are separate evidence."""
    result = []
    for variant in sorted({r["variant"] for r in rows if r["scope"] == "provider"}):
        cases = [r for r in rows if r["scope"] == "provider" and r["variant"] == variant]
        eligible = [r for r in cases if r["retryable_fault"]]
        repaired = [r for r in cases if r["repair_requests"]]
        responding = [r for r in cases if r["has_content_response"]]
        metrics = {
            "logical_call_success_rate": (sum(r["completed"] for r in cases), len(cases)),
            "retry_recovery_rate": (sum(r["completed"] for r in eligible), len(eligible)),
            "structured_repair_success_rate": (
                sum(r["completed"] for r in repaired),
                len(repaired),
            ),
            "structured_validity_after": (sum(r["completed"] for r in responding), len(responding)),
            "structured_validity_before": (
                sum(r["first_response_valid"] for r in responding),
                len(responding),
            ),
        }
        for name, (numerator, denominator) in metrics.items():
            result.append(
                dict(
                    variant=variant,
                    metric=name,
                    numerator=numerator,
                    denominator=denominator,
                    sample_count=len(cases),
                    value=numerator / denominator if denominator else None,
                )
            )
        for name, value in {
            "actual_http_requests": sum(r["actual_http_requests"] for r in cases),
            "measured_total_tokens": sum(r["measured_total_tokens"] for r in cases),
            "total_tokens": (
                sum(r["total_tokens"] for r in cases)
                if all(r["total_tokens"] is not None for r in cases)
                else None
            ),
        }.items():
            result.append(
                dict(
                    variant=variant,
                    metric=name,
                    numerator=value,
                    denominator=None,
                    sample_count=len(cases),
                    value=value,
                )
            )
    return result


def technical_completion(state):
    """Return technical terminal completion without consulting answer truth."""
    from .termination import normalize_termination

    if hasattr(state, "model_dump"):
        state = state.model_dump(mode="json")
    terminal = normalize_termination(state)
    report = state.get("report") or {}
    if (
        terminal["runtime_failure"]
        or terminal["protocol_valid"] is False
        or report.get("status") == "ERROR"
    ):
        return False
    if terminal["termination_source"] == "legacy":
        return report.get("status") in {"RESOLVED", "INCONCLUSIVE"}
    return terminal["termination_outcome"] in {"SUCCESS", "ABSTAINED", "NO_ACTION"}
