"""Pure backoff calculation; budgets and cancellation belong to the runtime."""

import math
import random


def compute_backoff(attempt, retry_after, config, rng=None):
    """Return the delay for a zero-based retry index.

    The configured cap applies to exponential delay, never to server Retry-After.
    Full/seeded jitter uses the supplied Random-compatible generator when provided.
    """
    if type(attempt) is not int or attempt < 0:
        raise ValueError("attempt must be a nonnegative integer")
    initial = config.initial_backoff_seconds
    cap = config.max_backoff_seconds
    for value in (initial, cap):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError("backoff settings must be nonnegative and finite")
    if retry_after is not None and (
        isinstance(retry_after, bool) or not math.isfinite(retry_after) or retry_after < 0
    ):
        raise ValueError("retry_after must be nonnegative and finite")
    mode = config.jitter_mode
    if mode not in ("none", "full", "seeded"):
        raise ValueError("unsupported jitter mode")
    # Avoid integer/float overflow even for arbitrarily large retry indices.
    if initial == 0 or cap == 0:
        delay = 0.0
    elif initial >= cap or attempt >= math.log2(cap) - math.log2(initial):
        delay = float(cap)
    else:
        delay = math.ldexp(initial, attempt)
    if mode != "none":
        if mode == "seeded" and rng is None:
            raise ValueError("seeded jitter requires an injected rng")
        delay = (rng or random).uniform(0, delay)
    return max(delay, retry_after or 0.0)
