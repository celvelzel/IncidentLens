"""Provider-reported token accounting. Partial measurements are never estimates."""

TOKEN_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def token_value(value):
    return value if type(value) is int and value >= 0 else None


def normalize_usage(value):
    value = value if isinstance(value, dict) else {}
    result = {key: token_value(value.get(key)) for key in TOKEN_KEYS}
    if result["total_tokens"] is None and all(
        result[key] is not None for key in TOKEN_KEYS[:2]
    ):
        result["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
        result["total_tokens_basis"] = "provider_prompt_plus_completion"
    else:
        result["total_tokens_basis"] = "provider_total" if result["total_tokens"] is not None else "unknown"
    return result


def begin_request(usage):
    usage.setdefault("request_usage", []).append(
        {"http_attempt_index": usage["llm_calls"], **normalize_usage(None)}
    )
    refresh_usage(usage)


def record_usage(usage, reported):
    values = normalize_usage(reported)
    usage["request_usage"][-1].update(values)
    refresh_usage(usage)
    return values["total_tokens"]


def refresh_usage(usage):
    requests = usage["request_usage"]
    for key in TOKEN_KEYS:
        values = [request[key] for request in requests]
        usage[key] = sum(values) if values and all(v is not None for v in values) else None
        usage["measured_" + key] = sum(v for v in values if v is not None)
    usage["tokens_complete"] = bool(requests) and all(
        request["total_tokens"] is not None for request in requests
    )
    usage["requests_with_token_usage"] = sum(r["total_tokens"] is not None for r in requests)
    usage["requests_without_token_usage"] = len(requests) - usage["requests_with_token_usage"]


def aggregate_usage(calls):
    """Aggregate each logical call once, including failed/repaired physical requests."""
    result = {}
    dispatched = [call for call in calls if call.get("llm_calls", 1) > 0]
    for key in TOKEN_KEYS:
        values = [token_value(call.get(key)) for call in dispatched]
        result[key] = sum(values) if values and all(v is not None for v in values) else None
        measured = [token_value(call.get("measured_" + key)) for call in dispatched]
        result["measured_" + key] = sum(
            known if known is not None else value or 0
            for known, value in zip(measured, values)
        )
    known = unknown = 0
    for call in dispatched:
        requests = call.get("request_usage")
        if isinstance(requests, list):
            count = sum(token_value(r.get("total_tokens")) is not None for r in requests)
            known += count
            unknown += max(0, call.get("llm_calls", len(requests)) - count)
        elif token_value(call.get("total_tokens")) is not None and call.get("tokens_complete", True):
            known += call.get("llm_calls", 1)
        else:
            # Old artifacts cannot identify which physical attempts supplied usage.
            unknown += call.get("llm_calls", 1)
    result.update(
        tokens_complete=bool(dispatched) and unknown == 0 and result["total_tokens"] is not None,
        requests_with_token_usage=known,
        requests_without_token_usage=unknown,
        token_usage_basis="provider_reported; measured_* are lower bounds when incomplete",
    )
    if not result["tokens_complete"]:
        result["total_tokens"] = None
    return result
