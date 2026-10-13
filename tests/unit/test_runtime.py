import asyncio

import pytest

from incident_lens.orchestration.runtime import RuntimeStoppedError, StopController, TaskManager


def test_attempts_are_bounded_and_unique():
    events = []
    manager = TaskManager(2, lambda event, **data: events.append((event, data)))
    first = manager.assign("logs", "logs")
    manager.start("logs")
    manager.fail("logs", "PROVIDER_ERROR")
    assert manager.can_retry("logs")
    second = manager.assign("logs", "logs")
    assert second.attempt == 2 and first.attempt_id != second.attempt_id
    manager.start("logs")
    manager.fail("logs", "PROVIDER_ERROR")
    assert not manager.can_retry("logs")
    with pytest.raises(ValueError):
        manager.assign("logs", "logs")
    assert len(events) == 6
    assert manager.records[0].status == "FAILED"


def test_transitions_and_independent_success():
    manager = TaskManager()
    manager.assign("logs", "logs")
    with pytest.raises(ValueError):
        manager.complete("logs")
    manager.start("logs")
    manager.fail("logs", "ERROR")
    manager.assign("metrics", "metrics")
    manager.start("metrics")
    manager.complete("metrics")
    with pytest.raises(ValueError):
        manager.fail("metrics", "ERROR")
    snapshot = manager.records
    snapshot[1].status = "FAILED"
    assert manager.records[1].status == "COMPLETED"


def test_task_freeze_allows_cancellation_only():
    manager = TaskManager()
    manager.assign("logs", "logs")
    manager.start("logs")
    manager.stop()
    assert not manager.can_retry("logs")
    for mutation in (lambda: manager.assign("metrics", "metrics"),
                     lambda: manager.start("logs"), lambda: manager.complete("logs"),
                     lambda: manager.fail("logs", "ERROR")):
        with pytest.raises(RuntimeStoppedError):
            mutation()
    assert manager.cancel("logs").status == "CANCELLED"


async def test_stop_ack_and_idempotence():
    events = []
    stop = StopController("incident", "run", lambda event, **data: events.append((event, data)))

    async def cancel():
        assert stop.frozen and stop.stopped
        with pytest.raises(RuntimeStoppedError):
            stop.guard()

    stop.guard()
    await stop.stop("PLAN_READY", {"logs": cancel})
    await stop.stop("UNRECOVERABLE_ERROR", {"metrics": cancel})
    assert [event for event, _ in events] == ["STOP", "STOP_ACK"]
    assert events[1][1]["role"] == "logs"


async def test_hung_and_failed_callbacks_timeout_without_false_ack():
    events = []
    stop = StopController("incident", "run", lambda event, **data: events.append((event, data)),
                          ack_timeout_seconds=0.01)
    released = asyncio.Event()

    async def hung():
        try:
            await released.wait()
        except asyncio.CancelledError:
            await released.wait()  # An uncooperative handler cannot delay STOP.

    async def failed():
        raise RuntimeError("failed cancellation")

    async def declined():
        return False

    await asyncio.wait_for(stop.stop("BUDGET_EXHAUSTED", {
        "logs": hung, "metrics": failed, "changes": declined,
    }), timeout=0.2)
    assert [event for event, _ in events] == ["STOP", "STOP_TIMEOUT"]
    assert events[-1][1]["missing_roles"] == ["changes", "logs", "metrics"]
    released.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert all(event != "STOP_ACK" for event, _ in events)


@pytest.mark.parametrize("value", [0, -1, True, 1.2])
def test_invalid_max_attempts(value):
    with pytest.raises(ValueError):
        TaskManager(value)
