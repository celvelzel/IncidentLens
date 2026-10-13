import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from incident_lens.llm.errors import FailureInfo, classify_http, classify_transport


@pytest.mark.parametrize(
    "status,category,retryable",
    [
        (429, "RATE_LIMITED", True),
        (408, "TRANSPORT_TIMEOUT", True),
        *[(s, "TRANSIENT_SERVER_ERROR", True) for s in (500, 502, 503, 504)],
        *[(s, "AUTHENTICATION_FAILED", False) for s in (401, 403)],
        *[(s, "INVALID_REQUEST", False) for s in (400, 404, 422, 409)],
        (501, "UNKNOWN_PROVIDER_ERROR", False),
        (200, "UNKNOWN_PROVIDER_ERROR", False),
    ],
)
def test_status_matrix(status, category, retryable):
    result = classify_http(status)
    assert (result.category, result.retryable) == (category, retryable)
    assert result.usage_complete is False


@pytest.mark.parametrize("status", [400, 404, 422])
def test_format_requires_explicit_code(status):
    assert (
        classify_http(status, sanitized_error_code="unsupported_response_format").category
        == "UNSUPPORTED_RESPONSE_FORMAT"
    )
    assert (
        classify_http(status, sanitized_error_code="response_format secret").category
        == "INVALID_REQUEST"
    )


def test_no_sensitive_header_exception_or_unknown_code_leak():
    secret = "Bearer TOP_SECRET"
    result = classify_http(401, {"Authorization": secret, "Other": secret}, secret)
    assert secret not in result.model_dump_json()
    result = classify_transport(httpx.ConnectError(secret))
    assert secret not in result.model_dump_json()
    assert FailureInfo(provider_error_code=secret).provider_error_code is None
    assert (
        FailureInfo(provider_error_code="invalid_api_key").provider_error_code == "invalid_api_key"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("5", 5),
        (" 0 ", 0),
        ("86400", 86400),
        ("86401", None),
        ("-2", None),
        ("NaN", None),
        ("inf", None),
        ("1.5", None),
        ("bad", None),
        ("9" * 129, None),
        (3, None),
        ("9" * 100, None),
        ("Tue, 13 Oct 2026 00:00:10 GMT", 10),
        ("Mon, 12 Oct 2026 00:00:00 GMT", 0),
        ("Tue, 13 Oct 2026 00:00:10", None),
        ("Wed, 14 Oct 2026 00:00:01 GMT", None),
    ],
)
def test_retry_after(value, expected):
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    assert classify_http(429, {"ReTrY-AfTeR": value}, now=now).retry_after_seconds == expected


@pytest.mark.parametrize(
    "exc,category,retryable,phase",
    [
        *[
            (kind("secret"), "TRANSPORT_TIMEOUT", True, "transport")
            for kind in (
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            )
        ],
        (httpx.ConnectError("secret"), "NETWORK_UNAVAILABLE", True, "transport"),
        (httpx.ReadError("secret"), "NETWORK_UNAVAILABLE", True, "transport"),
        (asyncio.CancelledError("secret"), "CANCELLED", False, "cancel"),
        (RuntimeError("secret"), "UNKNOWN_PROVIDER_ERROR", False, "transport"),
    ],
)
def test_transport(exc, category, retryable, phase):
    result = classify_transport(exc, logical_call_id="call_1", http_attempt_index=2, elapsed_ms=4)
    assert (result.category, result.retryable, result.phase) == (category, retryable, phase)
    assert result.logical_call_id == "call_1"
    assert result.http_attempt_index == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"elapsed_ms": float("nan")},
        {"http_attempt_index": -1},
        {"retry_after_seconds": float("inf")},
    ],
)
def test_failure_fields_validate(kwargs):
    with pytest.raises(ValidationError):
        FailureInfo(**kwargs)


def test_legacy_codes_and_untrusted_code_type():
    assert classify_http(400).legacy_code == "STRUCTURED_OUTPUT_COMPATIBILITY_ERROR"
    assert classify_http(429).legacy_code == "PROVIDER_HTTP_ERROR"
    assert classify_http(400, sanitized_error_code={"secret": "value"}).provider_error_code is None
    assert classify_transport(httpx.ReadTimeout("secret")).legacy_code == "PROVIDER_TIMEOUT"
    assert classify_transport(asyncio.CancelledError()).legacy_code == "PROVIDER_CANCELLED"
    assert (
        classify_transport(httpx.ConnectError("secret")).legacy_code == "PROVIDER_TRANSPORT_ERROR"
    )
    assert (
        classify_transport(RuntimeError(), legacy_code="CUSTOM_CODE").legacy_code == "CUSTOM_CODE"
    )
