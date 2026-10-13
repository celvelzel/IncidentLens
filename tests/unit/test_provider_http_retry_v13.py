import random
from types import SimpleNamespace

import httpx
import pytest

from incident_lens.llm.errors import classify_http, classify_transport
from incident_lens.llm.transport_retry import compute_backoff


def config(**kwargs):
    return SimpleNamespace(
        **(
            {"initial_backoff_seconds": 0.5, "max_backoff_seconds": 4.0, "jitter_mode": "none"}
            | kwargs
        )
    )


def test_exponential_sequence_cap_and_server_floor():
    assert [compute_backoff(i, None, config()) for i in range(5)] == [0.5, 1, 2, 4, 4]
    assert compute_backoff(10**100, None, config()) == 4
    assert compute_backoff(0, 20, config()) == 20
    assert compute_backoff(0, None, config(initial_backoff_seconds=8)) == 4
    assert compute_backoff(0, None, config(initial_backoff_seconds=0)) == 0
    assert compute_backoff(0, None, config(max_backoff_seconds=0)) == 0


@pytest.mark.parametrize("mode", ["full", "seeded"])
def test_jitter_is_deterministic_and_preserves_server_floor(mode):
    assert compute_backoff(1, None, config(jitter_mode=mode), random.Random(7)) == random.Random(
        7
    ).uniform(0, 1)
    assert compute_backoff(1, 9, config(jitter_mode=mode), random.Random(7)) == 9


@pytest.mark.parametrize(
    "attempt,delay,settings",
    [
        (-1, None, {}),
        (True, None, {}),
        (1.0, None, {}),
        (0, -1, {}),
        (0, float("inf"), {}),
        (0, True, {}),
        (0, None, {"initial_backoff_seconds": -1}),
        (0, None, {"max_backoff_seconds": float("nan")}),
        (0, None, {"initial_backoff_seconds": True}),
        (0, None, {"jitter_mode": "unknown"}),
        (0, None, {"jitter_mode": "seeded"}),
    ],
)
def test_invalid_inputs(attempt, delay, settings):
    with pytest.raises(ValueError):
        compute_backoff(attempt, delay, config(**settings))


def test_full_jitter_without_rng():
    assert 0 <= compute_backoff(0, None, config(jitter_mode="full")) <= 0.5


@pytest.mark.parametrize(
    "sequence,max_retries,remaining_wall,expected",
    [
        ([200], 2, 30, 1),
        ([429, 200], 2, 30, 2),
        ([503, 503, 200], 2, 30, 3),
        ([503, 503, 200], 1, 30, 2),
        ([401, 200], 2, 30, 1),
        ([403, 200], 2, 30, 1),
        ([400, 200], 2, 30, 1),
        ([422, 200], 2, 30, 1),
        ([429, 200], 2, 1, 1),
        (["timeout", 200], 2, 30, 2),
    ],
)
async def test_mock_transport_records_real_post_attempts(
    sequence, max_retries, remaining_wall, expected
):
    attempts, delays = [], []

    def handle(request):
        assert request.method == "POST"
        outcome = sequence[len(attempts)]
        attempts.append(request.method)
        if outcome == "timeout":
            raise httpx.ReadTimeout("sensitive message", request=request)
        return httpx.Response(outcome, headers={"Retry-After": "2"} if outcome == 429 else {})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        for index in range(max_retries + 1):
            try:
                response = await client.post("https://fixture.invalid/chat", json={})
                if response.status_code == 200:
                    break
                failure = classify_http(response.status_code, response.headers)
            except httpx.TransportError as exc:
                failure = classify_transport(exc)
            if not failure.retryable or index == max_retries:
                break
            delay = compute_backoff(index, failure.retry_after_seconds, config())
            if delay + 1 > remaining_wall:
                break
            delays.append(delay)
            remaining_wall -= delay
    assert len(attempts) == expected
    assert len(delays) == expected - 1
