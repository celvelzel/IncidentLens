"""Pure, bounded recovery policy; no provider or runtime side effects."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecoveryConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)
    enabled: bool = False
    max_transport_retries: int = Field(default=2, ge=0, le=100)
    max_structured_repairs: int = Field(default=1, ge=0, le=1)
    max_physical_attempts_per_call: int = Field(default=4, ge=1, le=1000)
    initial_backoff_seconds: float = Field(default=0.5, ge=0, le=3600)
    max_backoff_seconds: float = Field(default=4.0, ge=0, le=3600)
    jitter_mode: Literal["none", "seeded", "full"] = "none"
    retry_http_statuses: list[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504], max_length=100
    )
    reserve_verifier_requests: int = Field(default=0, ge=0, le=1000)
    min_request_time_seconds: float = Field(default=5.0, ge=0, le=86400)
    safety_margin_seconds: float = Field(default=0.0, ge=0, le=3600)
    format_capability: Literal["json_object", "json_schema"] = "json_object"

    @model_validator(mode="after")
    def bounded_statuses(self):
        if any(status < 400 or status > 599 for status in self.retry_http_statuses):
            raise ValueError("retry HTTP statuses must be between 400 and 599")
        if self.initial_backoff_seconds > self.max_backoff_seconds:
            raise ValueError("initial backoff must not exceed maximum")
        return self


class BudgetSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)
    remaining_request_permits: int = Field(ge=0)
    remaining_wall_seconds: float = Field(ge=0)
    remaining_tokens: int | None = Field(default=None, ge=0)
    tokens_complete: bool = True
    stage_remaining: int | None = Field(default=None, ge=0)


class RecoveryDecision(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)
    action: Literal["RETRY_HTTP", "REPAIR_OUTPUT", "FAIL", "ABORT_STOP"]
    reason: str
    delay_seconds: float = Field(default=0.0, ge=0)
    remaining_request_permits: int = Field(ge=0)
    remaining_wall_seconds: float = Field(ge=0)


def stopped(state):
    """Accept a boolean/callback or the runtime's explicit STOP state."""
    if callable(state):
        state = state()
    if isinstance(state, bool):
        return state
    return getattr(state, "value", state) in {"STOPPING", "FROZEN", "STOPPED", "CANCELLED"}


def decide_http_retry(
    failure, snapshot, stop_state, config, transport_retry_count=0, physical_attempt_count=0
):
    def decision(action, reason, delay=0.0):
        return RecoveryDecision(
            action=action,
            reason=reason,
            delay_seconds=delay,
            remaining_request_permits=snapshot.remaining_request_permits,
            remaining_wall_seconds=snapshot.remaining_wall_seconds,
        )

    if stopped(stop_state) or getattr(failure, "category", None) == "CANCELLED":
        return decision("ABORT_STOP", "stop_requested")
    if not config.enabled:
        return decision("FAIL", "recovery_disabled")
    category = getattr(failure, "category", None)
    if category not in {
        "RATE_LIMITED",
        "TRANSIENT_SERVER_ERROR",
        "TRANSPORT_TIMEOUT",
        "NETWORK_UNAVAILABLE",
    } or not getattr(failure, "retryable", False):
        return decision("FAIL", "non_retryable_failure")
    status = getattr(failure, "provider_http_status", None)
    if status is not None and status not in config.retry_http_statuses:
        return decision("FAIL", "http_status_not_enabled")
    if transport_retry_count < 0 or physical_attempt_count < 0:
        return decision("FAIL", "invalid_attempt_count")
    if transport_retry_count >= config.max_transport_retries:
        return decision("FAIL", "transport_retry_limit")
    if physical_attempt_count >= config.max_physical_attempts_per_call:
        return decision("FAIL", "physical_attempt_limit")
    if snapshot.remaining_request_permits <= config.reserve_verifier_requests:
        return decision("FAIL", "request_budget_exhausted")
    if snapshot.stage_remaining is not None and snapshot.stage_remaining <= 0:
        return decision("FAIL", "stage_budget_exhausted")
    if snapshot.remaining_tokens is not None and snapshot.remaining_tokens <= 0:
        return decision("FAIL", "token_budget_exhausted")
    delay = min(
        config.max_backoff_seconds,
        config.initial_backoff_seconds * 2 ** min(transport_retry_count, 100),
    )
    retry_after = getattr(failure, "retry_after_seconds", None)
    if retry_after is not None:
        import math

        if not math.isfinite(retry_after) or retry_after < 0:
            return decision("FAIL", "invalid_retry_after")
        delay = max(delay, retry_after)
    if (
        delay + config.min_request_time_seconds + config.safety_margin_seconds
        > snapshot.remaining_wall_seconds
    ):
        return decision("FAIL", "wall_budget_exhausted")
    return decision("RETRY_HTTP", "transient_failure", delay)
