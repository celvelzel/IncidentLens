from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from incident_lens.orchestration.recovery import (
    BudgetSnapshot,
    RecoveryConfig,
    decide_http_retry,
)


def failure(**changes):
    return SimpleNamespace(
        **(
            {
                "category": "RATE_LIMITED",
                "retryable": True,
                "provider_http_status": 429,
                "retry_after_seconds": None,
            }
            | changes
        )
    )


def test_defaults_and_strict_bounds():
    assert not RecoveryConfig().enabled
    assert RecoveryConfig().reserve_verifier_requests == 0
    for changes in (
        {"max_structured_repairs": 2},
        {"max_physical_attempts_per_call": 0},
        {"initial_backoff_seconds": float("nan")},
        {"enabled": "true"},
        {"retry_http_statuses": [200]},
        {"jitter_mode": "random"},
    ):
        with pytest.raises(ValidationError):
            RecoveryConfig(**changes)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"remaining_request_permits": 0}, "request_budget_exhausted"),
        ({"remaining_wall_seconds": 5.0}, "wall_budget_exhausted"),
        ({"stage_remaining": 0}, "stage_budget_exhausted"),
        ({"remaining_tokens": 0}, "token_budget_exhausted"),
    ],
)
def test_budget_denials(changes, reason):
    snapshot = BudgetSnapshot(
        **({"remaining_request_permits": 2, "remaining_wall_seconds": 20.0} | changes)
    )
    assert (
        decide_http_retry(failure(), snapshot, False, RecoveryConfig(enabled=True)).reason == reason
    )


def test_stop_and_attempt_limits():
    snapshot = BudgetSnapshot(remaining_request_permits=10, remaining_wall_seconds=20.0)
    config = RecoveryConfig(enabled=True)
    assert decide_http_retry(failure(), snapshot, "FROZEN", config).action == "ABORT_STOP"
    assert (
        decide_http_retry(failure(), snapshot, False, config, 2).reason == "transport_retry_limit"
    )
    assert (
        decide_http_retry(failure(), snapshot, False, config, 0, 4).reason
        == "physical_attempt_limit"
    )
    assert (
        decide_http_retry(
            failure(category="DOMAIN_VALIDATION_FAILED"), snapshot, False, config
        ).action
        == "FAIL"
    )
    assert (
        decide_http_retry(failure(), snapshot, False, RecoveryConfig()).reason
        == "recovery_disabled"
    )


def test_retry_after_and_unknown_tokens():
    snapshot = BudgetSnapshot(
        remaining_request_permits=2, remaining_wall_seconds=20.0, tokens_complete=False
    )
    config = RecoveryConfig(enabled=True)
    result = decide_http_retry(failure(retry_after_seconds=10.0), snapshot, False, config)
    assert result.action == "RETRY_HTTP"
    assert result.delay_seconds == 10.0
    assert (
        decide_http_retry(failure(retry_after_seconds=30.0), snapshot, False, config).action
        == "FAIL"
    )
    assert (
        decide_http_retry(failure(retry_after_seconds=float("inf")), snapshot, False, config).action
        == "FAIL"
    )
