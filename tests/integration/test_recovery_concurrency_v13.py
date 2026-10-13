import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from incident_lens.orchestration.budget import BudgetExceeded
from incident_lens.orchestration.permits import RequestPermitIssuer


def issuer(**changes):
    return RequestPermitIssuer(
        **({"max_requests": 1, "deadline": 100.0, "clock": lambda: 0.0} | changes)
    )


def test_atomic_last_permit():
    for _ in range(20):
        budget = issuer()
        barrier = Barrier(8)

        def acquire(index):
            barrier.wait()
            try:
                return budget.acquire(logical_call_id=str(index))
            except BudgetExceeded:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            permits = [p for p in pool.map(acquire, range(8)) if p]
        assert len(permits) == 1
        assert budget.snapshot().remaining_request_permits == 0


def test_release_dispatch_reconcile_and_unknown_usage():
    budget = issuer(max_requests=2, max_tokens=10)
    first = budget.acquire()
    assert budget.release_if_not_dispatched(first)
    assert not budget.release_if_not_dispatched(first)
    with pytest.raises(ValueError):
        budget.mark_dispatched(first)
    second = budget.acquire()
    budget.mark_dispatched(second)
    assert not budget.release_if_not_dispatched(second)
    budget.reconcile(second, None)
    budget.reconcile(second, 9)
    assert not budget.snapshot().tokens_complete
    assert budget.snapshot().remaining_tokens == 10
    third = budget.acquire()
    budget.mark_dispatched(third)
    budget.reconcile(third, 10)
    assert budget.snapshot().remaining_tokens == 0
    with pytest.raises(BudgetExceeded):
        budget.acquire()


def test_global_denial_does_not_debit_stage_and_stage_does_not_debit_global():
    budget = issuer(stage_limits={"monitoring": 1, "repair": 1})
    permit = budget.acquire(stage="monitoring")
    with pytest.raises(BudgetExceeded):
        budget.acquire(stage="repair")
    assert budget.snapshot("repair").stage_remaining == 1
    assert budget.release_if_not_dispatched(permit)
    permit = budget.acquire(stage="repair")
    budget.mark_dispatched(permit)
    assert budget.snapshot("monitoring").stage_remaining == 1
    budget = issuer(max_requests=3, stage_limits={"monitoring": 0})
    with pytest.raises(BudgetExceeded):
        budget.acquire(stage="monitoring")
    assert budget.snapshot().remaining_request_permits == 3


async def test_stop_during_backoff_cancels_second_dispatch():
    budget = issuer(max_requests=2)
    stop = False
    sleeping = asyncio.Event()
    never = asyncio.Event()

    async def request():
        permit = budget.acquire(stop_token=lambda: stop)
        budget.mark_dispatched(permit)
        budget.reconcile(permit, None)
        sleeping.set()
        await never.wait()  # injectable backoff sleeper
        budget.acquire(stop_token=lambda: stop)

    task = asyncio.create_task(request())
    await sleeping.wait()
    stop = True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(BudgetExceeded, match="stop_requested"):
        budget.acquire(stop_token=lambda: stop)
    assert budget.snapshot().remaining_request_permits == 1


def test_deadline_and_dispatched_timeout_remains_charged():
    now = [0.0]
    budget = issuer(max_requests=2, clock=lambda: now[0])
    permit = budget.acquire()
    budget.mark_dispatched(permit)
    budget.reconcile(permit, None)
    now[0] = 100.0
    with pytest.raises(BudgetExceeded, match="wall_budget"):
        budget.acquire()
    assert budget.snapshot().remaining_request_permits == 1


def test_known_tokens_block_next_request_and_usage_is_idempotent():
    budget = issuer(max_requests=5, max_tokens=4)
    permit = budget.acquire()
    budget.mark_dispatched(permit)
    assert not budget.snapshot().tokens_complete
    budget.reconcile(permit, {"total_tokens": 4})
    budget.reconcile(permit, 4)
    assert budget.snapshot().tokens_complete
    assert budget.snapshot().remaining_request_permits == 4
    with pytest.raises(BudgetExceeded, match="token_budget"):
        budget.acquire()


def test_task_retries_share_global_permits_and_unique_identity():
    budget = issuer(max_requests=3)
    permits = []
    for task_attempt in range(2):
        for transport_attempt in range(2):
            try:
                permit = budget.acquire(logical_call_id=f"task-{task_attempt}")
            except BudgetExceeded:
                continue
            permits.append(permit)
            budget.mark_dispatched(permit)
            budget.reconcile(permit, None)
    assert len(permits) == len({p.permit_id for p in permits}) == 3
    assert budget.snapshot().remaining_request_permits == 0
