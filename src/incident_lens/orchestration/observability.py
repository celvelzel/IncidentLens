"""Opt-in durable diagnostics. Snapshots are NOT executable resume checkpoints."""

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class RunJournal:
    def __init__(self, root, manifest):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "checkpoints").mkdir()
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.error = None
        self.io_failures = 0
        self.active_io_errors = {}
        self.events_complete = True
        self.sequence = 0
        self.checkpoint_sequence = 0
        self.digest = hashlib.sha256()
        self.offset = 0
        self.status = {
            "schema_version": 1, "pid": os.getpid(), "started_at": now(),
            "lifecycle": "running", "last_progress_at": None,
            "resume_supported": False, "active_requests": {},
            "heartbeat_kind": "in_process_thread_not_external_supervisor",
        }
        self.atomic("run-manifest.json", manifest | self.status)
        self.stream = (self.root / "events-0001.jsonl").open("xb")
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.thread.start()

    def atomic(self, name, value):
        path = self.root / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        for attempt in range(3):
            try:
                payload = value
                if name == "status.json":
                    # A successful replacement clears this target's active
                    # fault. Persist the recovered view, while retaining the
                    # historical degradation count, in that same write.
                    health = self.health()
                    health["active_io_errors"].pop(name, None)
                    payload = dict(value, observability=health)
                with temporary.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, default=str)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except PermissionError as exc:
                if attempt < 2:
                    time.sleep(0.01 * (attempt + 1))
                    continue
                self.io_error(name, exc)
                return False
            except OSError as exc:
                self.io_error(name, exc)
                return False
            self.active_io_errors.pop(name, None)
            if name == "status.json":
                self.status["observability"] = self.health()
            return True

    def io_error(self, target, exc):
        # Diagnostic I/O must not replace the business exception or prevent retries.
        # Keep only safe error metadata, never exception text or request content.
        self.io_failures += 1
        self.error = exc
        self.active_io_errors[target] = {
            "type": type(exc).__name__, "errno": exc.errno,
            "winerror": getattr(exc, "winerror", None),
        }
        self.status["observability"] = self.health()

    def health(self):
        with self.lock:
            return {
                "degraded": self.io_failures > 0,
                "io_failures": self.io_failures,
                "events_complete": self.events_complete,
                "active_io_errors": dict(self.active_io_errors),
            }

    def heartbeat(self):
        while not self.stop.is_set():
            try:
                with self.lock:
                    self.status["heartbeat_at"] = now()
                    self.atomic("status.json", self.status)
            except OSError as exc:
                with self.lock:
                    self.io_error("heartbeat", exc)
            self.stop.wait(10)

    def append(self, kind, details):
        if not self.events_complete:
            return False
        record = {"schema_version": 1, "sequence": self.sequence + 1,
                  "recorded_at": now(), "kind": kind, **details}
        data = (json.dumps(record, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        try:
            written = self.stream.write(data)
            if written != len(data):
                raise OSError("Incomplete diagnostic event write")
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except OSError as exc:
            # A partial write cannot be rolled back safely. Stop the event stream
            # and mark subsequent snapshots incomplete instead of claiming a
            # contiguous, hash-verifiable journal. Business state remains usable.
            self.events_complete = False
            self.io_error("events-0001.jsonl", exc)
            return False
        self.sequence += 1
        self.digest.update(data)
        self.offset += len(data)
        self.status.update(last_event=kind, last_event_at=record["recorded_at"],
                           event_sequence=self.sequence)
        return True

    def event(self, event, run):
        with self.lock:
            self.append(event.event_type, {"event": event.model_dump(mode="json")})
            self.status.update(run_id=run.run_id, round_index=run.state.round_index,
                               physical_requests=run.call_budget.calls,
                               tool_calls=run.registry.call_count,
                               observed_tokens=run.call_budget.tokens,
                               tokens_complete=False)
            if event.event_type in {"MERGE", "DECISION", "REVIEW", "REPORT"}:
                self.status["last_progress_at"] = now()
                checkpoint = {
                    "schema_version": 1, "purpose": "diagnostic_only",
                    "resume_supported": False, "boundary_event": event.event_id,
                    "observability": self.health(),
                    "event_sequence": self.sequence, "event_bytes": self.offset,
                    "event_sha256": self.digest.hexdigest(),
                    "state": run.state.model_dump(mode="json"),
                    "task_records": [r.model_dump(mode="json") for r in run.task_manager.records],
                    "budget": run.call_budget.snapshot().model_dump(mode="json"),
                }
                # Two slots retain the preceding snapshot; status names the
                # committed one only after replacement succeeds.
                self.checkpoint_sequence += 1
                slot = f"checkpoints/slot-{self.checkpoint_sequence % 2}.json"
                if self.atomic(slot, checkpoint):
                    self.status["checkpoint"] = slot
            self.status["observability"] = self.health()
            self.atomic("status.json", self.status)

    def request(self, run, permit):
        with self.lock:
            self.append("REQUEST_DISPATCH_INTENT", {
                "run_id": run.run_id, "permit": asdict(permit),
                "context": run.call_context.get(),
                "note": "intent recording attempted before transport; check events_complete; "
                        "response may remain unknown",
            })
            self.status["last_request_intent_at"] = now()
            self.status["physical_requests"] = run.call_budget.calls
            self.atomic("status.json", self.status)

    def model_activity(self, metadata, active):
        with self.lock:
            self.append("MODEL_WAIT_STARTED" if active else "MODEL_WAIT_ENDED", metadata)
            calls = self.status["active_requests"]
            if active:
                calls[metadata["call_id"]] = metadata | {"started_at": now()}
            else:
                calls.pop(metadata["call_id"], None)
            self.atomic("status.json", self.status)

    def close(self, error=None):
        self.stop.set()
        self.thread.join(timeout=2)
        with self.lock:
            self.status.update(lifecycle="interrupted" if error else "completed",
                               ended_at=now(), error_type=type(error).__name__ if error else None)
            try:
                self.stream.close()
            except OSError as exc:
                self.io_error("events-close", exc)
            # Include close-time diagnostic failures in the final health status.
            self.atomic("status.json", self.status)
