"""Monotonic wall clock and actual provider request accounting."""

import asyncio
import time


class BudgetExceeded(RuntimeError):
    pass


class CallBudget:
    def __init__(self, limits):
        self.limits = limits
        self.started = time.monotonic()
        self.calls = 0
        self.tokens = 0
        self.usage = []
        self.guarded_provider = False

    def consume_request(self):
        if self.calls >= self.limits.max_llm_calls or not self.remaining_seconds():
            raise BudgetExceeded("LLM or wall-clock budget exhausted")
        if self.limits.max_tokens is not None and self.tokens >= self.limits.max_tokens:
            raise BudgetExceeded("Token budget exhausted")
        self.calls += 1

    def remaining_seconds(self):
        return max(0.0, self.limits.max_wall_seconds - (time.monotonic() - self.started))

    async def call(self, function, *args):
        if self.calls >= self.limits.max_llm_calls or not self.remaining_seconds():
            raise BudgetExceeded("LLM or wall-clock budget exhausted")
        if self.limits.max_tokens is not None and self.tokens >= self.limits.max_tokens:
            raise BudgetExceeded("Token budget exhausted")
        if not self.guarded_provider:
            self.consume_request()
        result, usage = await asyncio.wait_for(function(*args), timeout=self.remaining_seconds())
        attempts = usage.get("llm_calls", usage.get("request_count", 1))
        if not self.guarded_provider:
            self.calls += max(0, attempts - 1)
        if self.calls > self.limits.max_llm_calls:
            raise BudgetExceeded("Structured repair exhausted LLM budget")
        total = usage.get("total_tokens")
        if total is not None:
            self.tokens += total
        self.usage.append(usage)
        return result, usage
