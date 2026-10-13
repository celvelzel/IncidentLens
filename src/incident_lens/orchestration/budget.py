"""Monotonic wall clock and actual provider request accounting."""

import asyncio
import time


class BudgetExceeded(RuntimeError):
    pass


class CallBudget:
    def __init__(self, limits, stage_limits=None):
        self.limits = limits
        self.started = time.monotonic()
        self.calls = 0
        self.tokens = 0
        self.usage = []
        self.failures = []
        self.guarded_provider = False
        self.observed_tokens = False
        from incident_lens.orchestration.permits import RequestPermitIssuer

        self.permits = RequestPermitIssuer(
            limits.max_llm_calls,
            self.started + limits.max_wall_seconds,
            limits.max_tokens,
            stage_limits=stage_limits,
        )

    def observe_tokens(self, total):
        self.tokens += total

    def consume_request(self, *, stage=None, run_id="", logical_call_id=""):
        if self.limits.max_tokens is not None and self.tokens >= self.limits.max_tokens:
            raise BudgetExceeded("Token budget exhausted")
        permit = self.permits.acquire(stage=stage, run_id=run_id, logical_call_id=logical_call_id)
        self.permits.mark_dispatched(permit)
        self.calls += 1
        return permit

    def reconcile_request(self, permit, total):
        if permit is not None:
            self.permits.reconcile(permit, total)

    def snapshot(self, stage=None):
        snapshot = self.permits.snapshot(stage)
        # Token observers also cover legacy adapters that do not reconcile permits.
        if self.limits.max_tokens is not None:
            snapshot = snapshot.model_copy(
                update={"remaining_tokens": max(0, self.limits.max_tokens - self.tokens)}
            )
        return snapshot

    def remaining_seconds(self):
        return max(0.0, self.limits.max_wall_seconds - (time.monotonic() - self.started))

    async def call(self, function, *args, metadata=None):
        if self.calls >= self.limits.max_llm_calls or not self.remaining_seconds():
            raise BudgetExceeded("LLM or wall-clock budget exhausted")
        if self.limits.max_tokens is not None and self.tokens >= self.limits.max_tokens:
            raise BudgetExceeded("Token budget exhausted")
        if not self.guarded_provider:
            self.consume_request()
        try:
            result, usage = await asyncio.wait_for(
                function(*args), timeout=self.remaining_seconds()
            )
        except BaseException as exc:
            usage = getattr(exc, "usage", None)
            if usage:
                self.usage.append(dict(usage))
                self.failures.append(
                    dict(usage)
                    | {"error_code": getattr(exc, "code", type(exc).__name__), "failed": True}
                    | (metadata or {})
                )
                if not self.observed_tokens:
                    self.tokens += (
                        usage.get("measured_total_tokens", usage.get("total_tokens")) or 0
                    )
            elif self.calls:
                unknown = {
                    "source": "model",
                    "llm_calls": 1,
                    "total_tokens": None,
                    "tokens_complete": False,
                    "error_code": type(exc).__name__,
                    "failed": True,
                    **(metadata or {}),
                }
                self.usage.append(unknown)
                self.failures.append(unknown)
            raise
        attempts = usage.get("llm_calls", usage.get("request_count", 1))
        if not self.guarded_provider:
            self.calls += max(0, attempts - 1)
        if self.calls > self.limits.max_llm_calls:
            raise BudgetExceeded("Structured repair exhausted LLM budget")
        total = usage.get("measured_total_tokens", usage.get("total_tokens"))
        if total is not None and not self.observed_tokens:
            self.tokens += total
        self.usage.append(usage)
        return result, usage
