"""Safe, machine-readable provider failure classification without response bodies."""

import asyncio
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

FailureCategory = Literal[
    "RATE_LIMITED",
    "TRANSIENT_SERVER_ERROR",
    "TRANSPORT_TIMEOUT",
    "NETWORK_UNAVAILABLE",
    "AUTHENTICATION_FAILED",
    "INVALID_REQUEST",
    "UNSUPPORTED_RESPONSE_FORMAT",
    "INVALID_JSON",
    "SCHEMA_VALIDATION_FAILED",
    "DOMAIN_VALIDATION_FAILED",
    "RESPONSE_TRUNCATED",
    "CANCELLED",
    "REQUEST_BUDGET_EXHAUSTED",
    "WALL_BUDGET_EXHAUSTED",
    "TOKEN_BUDGET_EXHAUSTED",
    "UNKNOWN_PROVIDER_ERROR",
]

# Only exact, reviewed protocol codes may survive into diagnostics.
SAFE_ERROR_CODES = frozenset(
    {
        "unsupported_response_format",
        "response_format_not_supported",
        "invalid_response_format",
        "rate_limit_exceeded",
        "insufficient_quota",
        "invalid_api_key",
        "invalid_request_error",
        "model_not_found",
    }
)
FORMAT_ERROR_CODES = frozenset(
    {
        "unsupported_response_format",
        "response_format_not_supported",
        "invalid_response_format",
    }
)
MAX_RETRY_AFTER_SECONDS = 86400.0


class FailureInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    category: FailureCategory = "UNKNOWN_PROVIDER_ERROR"
    legacy_code: str = "PROVIDER_HTTP_ERROR"
    provider_http_status: int | None = Field(default=None, ge=100, le=599)
    provider_error_code: str | None = None
    retryable: bool = False
    retry_after_seconds: float | None = Field(default=None, ge=0, le=MAX_RETRY_AFTER_SECONDS)
    phase: Literal["transport", "syntax", "schema", "domain", "budget", "cancel"] = "transport"
    logical_call_id: str = ""
    http_attempt_index: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0, ge=0)
    usage_complete: bool = False

    @field_validator("provider_error_code", mode="before")
    @classmethod
    def safe_code(cls, value):
        return value if isinstance(value, str) and value in SAFE_ERROR_CODES else None


def _retry_after(headers, now=None):
    if not headers:
        return None
    value = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if not isinstance(value, str) or len(value) > 128:
        return None
    value = value.strip()
    try:
        if value.isascii() and value.isdigit():
            seconds = float(value)
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            seconds = max(0.0, (date - (now or datetime.now(timezone.utc))).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None
    return seconds if math.isfinite(seconds) and 0 <= seconds <= MAX_RETRY_AFTER_SECONDS else None


def classify_http(status_code, headers=None, sanitized_error_code=None, **context):
    """Classify status and allowlisted metadata; never inspect a response body.

    ``now`` optionally supplies an aware UTC datetime for deterministic HTTP-date tests.
    Other context values are the runtime-owned FailureInfo timing/identity fields.
    """
    now = context.pop("now", None)
    code = (
        sanitized_error_code
        if isinstance(sanitized_error_code, str) and sanitized_error_code in SAFE_ERROR_CODES
        else None
    )
    category, retryable = "UNKNOWN_PROVIDER_ERROR", False
    if status_code == 429:
        category, retryable = "RATE_LIMITED", True
    elif status_code == 408:
        category, retryable = "TRANSPORT_TIMEOUT", True
    elif status_code in (500, 502, 503, 504):
        category, retryable = "TRANSIENT_SERVER_ERROR", True
    elif status_code in (401, 403):
        category = "AUTHENTICATION_FAILED"
    elif 400 <= status_code < 500:
        category = "INVALID_REQUEST"
        if status_code in (400, 404, 422) and code in FORMAT_ERROR_CODES:
            category = "UNSUPPORTED_RESPONSE_FORMAT"
    context.setdefault(
        "legacy_code",
        "STRUCTURED_OUTPUT_COMPATIBILITY_ERROR"
        if status_code in (400, 404, 422)
        else "PROVIDER_HTTP_ERROR",
    )
    return FailureInfo(
        **context,
        category=category,
        retryable=retryable,
        provider_http_status=status_code,
        provider_error_code=code,
        retry_after_seconds=_retry_after(headers, now),
    )


def classify_transport(exc, **context):
    """Inspect exception types only. Cancellation remains the caller's to propagate."""
    category, retryable, phase = "UNKNOWN_PROVIDER_ERROR", False, "transport"
    if isinstance(exc, asyncio.CancelledError):
        category, phase = "CANCELLED", "cancel"
    elif isinstance(exc, httpx.TimeoutException):
        category, retryable = "TRANSPORT_TIMEOUT", True
    elif isinstance(exc, httpx.NetworkError):
        category, retryable = "NETWORK_UNAVAILABLE", True
    context.setdefault(
        "legacy_code",
        "PROVIDER_CANCELLED"
        if phase == "cancel"
        else (
            "PROVIDER_TIMEOUT" if category == "TRANSPORT_TIMEOUT" else "PROVIDER_TRANSPORT_ERROR"
        ),
    )
    return FailureInfo(**context, category=category, retryable=retryable, phase=phase)
