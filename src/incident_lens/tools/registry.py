"""Role-scoped execution, query ledger, publication and shared tool budget."""

import math
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from time import perf_counter
from uuid import uuid4

from pydantic import ValidationError

from incident_lens.schemas import ToolResult
from incident_lens.security.authorization import ContextAuthority
from incident_lens.security.context import AgentContext

from .arguments import ARGUMENT_MODELS
from .changes import get_config_diff, query_changes
from .logs import query_logs
from .metrics import get_dependencies, query_metrics
from .provider import EvidenceProvider

HANDLERS = {
    "query_logs": query_logs,
    "query_metrics": query_metrics,
    "get_dependencies": get_dependencies,
    "query_changes": query_changes,
    "get_config_diff": get_config_diff,
}


class ScopedClient:
    def __init__(self, registry, context):
        self._registry = registry
        self._context = context

    @property
    def context(self) -> AgentContext:
        return self._context

    def execute(self, tool_name: str, args: dict) -> ToolResult:
        return self._registry.execute(self._context, tool_name, args)


class ToolRegistry:
    def __init__(
        self,
        provider: EvidenceProvider,
        workspace_id: str,
        incident_id: str,
        run_id: str,
        max_tool_calls: int = 12,
        timeout_seconds: float = 5.0,
    ):
        if (
            isinstance(max_tool_calls, bool)
            or not isinstance(max_tool_calls, int)
            or max_tool_calls < 0
        ):
            raise ValueError("max_tool_calls must be a nonnegative integer")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        self._provider = provider
        self._case = provider.load_case(incident_id)
        self._authority = ContextAuthority(workspace_id, incident_id, run_id)
        self._max_tool_calls = max_tool_calls
        self._timeout_seconds = timeout_seconds
        self._call_count = 0
        self._observed: dict[int, dict] = {}
        self._shared: dict = {}
        self._events: list[dict] = []
        self._lock = RLock()

    def create_context(self, role: str) -> AgentContext:
        with self._lock:
            context = self._authority.issue(role, max(0, self._max_tool_calls - self._call_count))
            self._observed[id(context)] = {}
            return context

    def client(self, context: AgentContext) -> ScopedClient:
        self._authority.validate(context)
        return ScopedClient(self, context)

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._call_count

    @property
    def events(self) -> list[dict]:
        with self._lock:
            return deepcopy(self._events)

    def observed_ids(self, context: AgentContext) -> set[str]:
        with self._lock:
            self._authority.validate(context)
            return set(self._observed[id(context)])

    def get_observed_records(self, context: AgentContext) -> list:
        with self._lock:
            self._authority.validate(context)
            return deepcopy(list(self._observed[id(context)].values()))

    def publish(self, context: AgentContext, ids: list[str]) -> None:
        with self._lock:
            self._authority.validate(context)
            ledger = self._observed[id(context)]
            if not set(ids).issubset(ledger):
                raise PermissionError("publication requires actually queried evidence")
            self._shared.update({eid: deepcopy(ledger[eid]) for eid in ids})

    def shared_records(self) -> dict:
        with self._lock:
            return deepcopy(self._shared)

    def execute(self, context: AgentContext, tool_name: str, args: dict) -> ToolResult:
        started = perf_counter()
        call_id = f"call-{uuid4().hex}"
        records = []
        error = None
        cursor = None
        try:
            if not isinstance(tool_name, str):
                raise PermissionError("tool_name must be a known string")
            self._authority.validate(context, tool_name)
            if tool_name not in ARGUMENT_MODELS:
                raise PermissionError("unknown tool")
            if not isinstance(args, dict):
                raise ValueError("tool arguments must be an object")
            parsed = ARGUMENT_MODELS[tool_name].model_validate(args)
            if (
                getattr(parsed, "service", None) is not None
                and parsed.service not in self._case.services
            ):
                raise FileNotFoundError("service does not exist")
            with self._lock:
                if self._call_count >= self._max_tool_calls:
                    error = "BUDGET_EXCEEDED"
                else:
                    self._call_count += 1
            if error is None:
                if tool_name == "fetch_evidence_by_ids":
                    with self._lock:
                        visible = dict(self._shared)
                        if context.role == "single":
                            visible.update(self._observed[id(context)])
                        if not set(parsed.ids).issubset(visible):
                            raise PermissionError("evidence has not been shared")
                        records = [deepcopy(visible[eid]) for eid in dict.fromkeys(parsed.ids)]
                else:
                    # Timed-out read-only work cannot publish or change the registry ledger.
                    executor = ThreadPoolExecutor(max_workers=1)
                    future = executor.submit(
                        HANDLERS[tool_name], self._provider, self._case.incident_id, parsed
                    )
                    try:
                        records = future.result(timeout=self._timeout_seconds)
                    finally:
                        executor.shutdown(wait=False, cancel_futures=True)
                limit = getattr(parsed, "limit", 50)
                if len(records) > limit:
                    cursor = str(limit)
                records = records[:limit]
                with self._lock:
                    self._observed[id(context)].update(
                        {record.evidence_id: deepcopy(record) for record in records}
                    )
        except PermissionError:
            error = "FORBIDDEN"
        except (ValidationError, ValueError, TypeError):
            error = "BAD_ARGS"
        except (FileNotFoundError, KeyError):
            error = "NOT_FOUND"
        except TimeoutError:
            error = "TIMEOUT"
        except OSError:
            error = "NOT_FOUND"
        elapsed_ms = (perf_counter() - started) * 1000
        result = ToolResult(
            call_id=call_id,
            ok=error is None,
            records=records if error is None else [],
            record_count=len(records) if error is None else 0,
            error_code=error,
            elapsed_ms=elapsed_ms,
            next_cursor=cursor if error is None else None,
        )
        with self._lock:
            # Neither caller arguments nor raw evidence/exception text enters the trace.
            self._events.append(
                {
                    "call_id": call_id,
                    "tool_name": tool_name
                    if isinstance(tool_name, str) and tool_name in ARGUMENT_MODELS
                    else "unknown",
                    "ok": result.ok,
                    "error_code": error,
                    "record_count": result.record_count,
                    "evidence_ids": [record.evidence_id for record in result.records],
                    "elapsed_ms": elapsed_ms,
                }
            )
        return result
