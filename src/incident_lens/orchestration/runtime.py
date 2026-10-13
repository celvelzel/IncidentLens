"""Deterministic task attempts and bounded centralized STOP coordination."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from incident_lens.schemas.workflow import StopMessage, StopReason, TaskRecord


class RuntimeStoppedError(RuntimeError):
    """A mutation was attempted after the runtime froze."""


class TaskManager:
    def __init__(self, max_attempts: int = 2, emit: Callable[..., Any] | None = None):
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self.max_attempts = max_attempts
        self.emit = emit or (lambda *args, **kwargs: None)
        self._records: list[TaskRecord] = []
        self._latest: dict[str, TaskRecord] = {}
        self.stopped = False

    @property
    def records(self) -> list[TaskRecord]:
        return [record.model_copy(deep=True) for record in self._records]

    def stop(self) -> None:
        self.stopped = True

    def _guard(self) -> None:
        if self.stopped:
            raise RuntimeStoppedError("task manager is stopped")

    def assign(self, task_id: str, role: str) -> TaskRecord:
        self._guard()
        previous = self._latest.get(task_id)
        if previous is not None and not self.can_retry(task_id):
            raise ValueError(f"task {task_id} cannot be assigned again")
        if previous is not None and role != previous.role:
            raise ValueError("retry cannot change task role")
        attempt = previous.attempt + 1 if previous else 1
        # Sequence suffix keeps identifiers bounded even for 128-character task IDs.
        record = TaskRecord(
            task_id=task_id,
            role=role,
            attempt=attempt,
            attempt_id=f"attempt-{len(self._records) + 1}",
            status="ASSIGNED",
        )
        self._records.append(record)
        self._latest[task_id] = record
        self.emit("TASK_ASSIGNED", **record.model_dump())
        return record.model_copy(deep=True)

    def can_retry(self, task_id: str) -> bool:
        record = self._latest.get(task_id)
        return bool(
            not self.stopped
            and record
            and record.status == "FAILED"
            and record.attempt < self.max_attempts
        )

    def _transition(
        self, task_id: str, status: str, allowed: set[str], error_code: str | None = None
    ) -> TaskRecord:
        if status != "CANCELLED":
            self._guard()
        record = self._latest[task_id]
        if record.status not in allowed:
            raise ValueError(f"invalid task transition {record.status} -> {status}")
        record.status = status
        record.error_code = error_code
        self.emit(f"TASK_{status}", **record.model_dump())
        return record.model_copy(deep=True)

    def start(self, task_id: str) -> TaskRecord:
        return self._transition(task_id, "RUNNING", {"ASSIGNED"})

    def complete(self, task_id: str) -> TaskRecord:
        return self._transition(task_id, "COMPLETED", {"RUNNING"})

    def fail(self, task_id: str, error_code: str) -> TaskRecord:
        return self._transition(task_id, "FAILED", {"RUNNING"}, error_code)

    def cancel(self, task_id: str) -> TaskRecord:
        return self._transition(task_id, "CANCELLED", {"ASSIGNED", "RUNNING"})


class StopController:
    def __init__(
        self,
        incident_id: str,
        run_id: str,
        emit: Callable[..., Any] | None = None,
        ack_timeout_seconds: float = 5.0,
    ):
        if not 0 < ack_timeout_seconds < float("inf"):
            raise ValueError("ack_timeout_seconds must be positive and finite")
        self.incident_id = incident_id
        self.run_id = run_id
        self.emit = emit or (lambda *args, **kwargs: None)
        self.ack_timeout_seconds = ack_timeout_seconds
        self.stopped = False
        self.frozen = False
        self.completed = False
        self.missing_roles: list[str] = []
        self.reason: StopReason | None = None

    def guard(self) -> None:
        if self.frozen:
            raise RuntimeStoppedError("runtime is frozen after STOP")

    async def stop(
        self, reason: StopReason, active: Mapping[str, Callable[[], Awaitable[Any]]] | None = None
    ) -> None:
        if self.stopped:
            return
        message = StopMessage(incident_id=self.incident_id, run_id=self.run_id, stop_reason=reason)
        self.stopped = self.frozen = True
        self.reason = reason
        callbacks = dict(active or {})
        self.emit(
            "WORKFLOW_STOP_REQUESTED", **message.model_dump(), required_roles=sorted(callbacks)
        )
        acknowledged: set[str] = set()
        accepting = True

        async def acknowledge(role: str, callback: Callable[[], Awaitable[Any]]) -> None:
            try:
                result = await callback()
            except (Exception, asyncio.CancelledError):
                return
            if accepting and result is not False:
                acknowledged.add(role)
                ack = message.model_copy(update={"message_type": "STOP_ACK", "role": role})
                self.emit("STOP_ACK", **ack.model_dump())

        tasks = [
            asyncio.create_task(acknowledge(role, callback)) for role, callback in callbacks.items()
        ]
        try:
            if tasks:
                await asyncio.wait(tasks, timeout=self.ack_timeout_seconds)
        finally:
            accepting = False
            for task in tasks:
                if not task.done():
                    task.cancel()
        missing = sorted(set(callbacks) - acknowledged)
        self.missing_roles = missing
        self.completed = not missing
        if missing:
            self.emit(
                "STOP_TIMEOUT",
                incident_id=self.incident_id,
                run_id=self.run_id,
                stop_reason=reason,
                missing_roles=missing,
            )
