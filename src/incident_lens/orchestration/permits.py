"""Atomic request reservation and per-stage accounting."""

import math
import threading
import time
from dataclasses import dataclass, replace
from uuid import uuid4

from incident_lens.orchestration.budget import BudgetExceeded
from incident_lens.orchestration.recovery import BudgetSnapshot, stopped


@dataclass(frozen=True)
class Permit:
    permit_id: str
    run_id: str
    logical_call_id: str
    stage: str | None
    state: str = "reserved"


class RequestPermitIssuer:
    def __init__(
        self, max_requests, deadline, max_tokens=None, stage_limits=None, clock=time.monotonic
    ):
        if type(max_requests) is not int or max_requests < 0:
            raise ValueError("max_requests must be a nonnegative integer")
        for value in [max_tokens, *(stage_limits or {}).values()]:
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("limits must be nonnegative integers")
        if not math.isfinite(deadline):
            raise ValueError("deadline must be finite")
        self.max_requests = max_requests
        self.deadline = deadline
        self.max_tokens = max_tokens
        self.stage_limits = dict(stage_limits or {})
        self.clock = clock
        self._lock = threading.Lock()
        self._permits = {}
        self._requests = 0
        self._stages = {}
        self._tokens = 0
        self._tokens_complete = True

    def acquire(self, run_id="", logical_call_id="", stage=None, stop_token=None):
        with self._lock:
            if stopped(stop_token):
                raise BudgetExceeded("stop_requested")
            if self.clock() >= self.deadline:
                raise BudgetExceeded("wall_budget_exhausted")
            if self._requests >= self.max_requests:
                raise BudgetExceeded("request_budget_exhausted")
            if self.max_tokens is not None and self._tokens >= self.max_tokens:
                raise BudgetExceeded("token_budget_exhausted")
            if (
                stage in self.stage_limits
                and self._stages.get(stage, 0) >= self.stage_limits[stage]
            ):
                raise BudgetExceeded("stage_budget_exhausted")
            permit = Permit(uuid4().hex, run_id, logical_call_id, stage)
            self._permits[permit.permit_id] = permit
            self._requests += 1
            self._stages[stage] = self._stages.get(stage, 0) + 1
            return permit

    @staticmethod
    def _id(permit_id):
        return permit_id.permit_id if isinstance(permit_id, Permit) else permit_id

    def mark_dispatched(self, permit_id):
        with self._lock:
            key = self._id(permit_id)
            permit = self._permits[key]
            if permit.state == "reserved":
                self._permits[key] = replace(permit, state="dispatched")
            elif permit.state == "released":
                raise ValueError("released permit cannot be dispatched")

    def release_if_not_dispatched(self, permit_id):
        with self._lock:
            key = self._id(permit_id)
            permit = self._permits[key]
            if permit.state != "reserved":
                return False
            self._permits[key] = replace(permit, state="released")
            self._requests -= 1
            self._stages[permit.stage] -= 1
            return True

    def reconcile(self, permit_id, token_usage_or_unknown):
        with self._lock:
            key = self._id(permit_id)
            permit = self._permits[key]
            if permit.state == "reconciled":
                return
            if permit.state != "dispatched":
                raise ValueError("only dispatched permits can be reconciled")
            usage = token_usage_or_unknown
            if isinstance(usage, dict):
                usage = usage.get("total_tokens") if usage.get("tokens_complete", True) else None
            if usage is not None and (type(usage) is not int or usage < 0):
                raise ValueError("token usage must be a nonnegative integer or unknown")
            if usage is None:
                self._tokens_complete = False
            else:
                self._tokens += usage
            self._permits[key] = replace(permit, state="reconciled")

    def snapshot(self, stage=None):
        with self._lock:
            return BudgetSnapshot(
                remaining_request_permits=max(0, self.max_requests - self._requests),
                remaining_wall_seconds=max(0.0, float(self.deadline - self.clock())),
                remaining_tokens=(
                    None if self.max_tokens is None else max(0, self.max_tokens - self._tokens)
                ),
                tokens_complete=self._tokens_complete
                and not any(p.state == "dispatched" for p in self._permits.values()),
                stage_remaining=(
                    None
                    if stage not in self.stage_limits
                    else max(0, self.stage_limits[stage] - self._stages.get(stage, 0))
                ),
            )
