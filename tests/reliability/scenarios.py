"""Deterministic production-provider fault schedule, shared by tests and CLI."""

import asyncio
import hashlib
import json
import subprocess
import types
from dataclasses import asdict, dataclass

import httpx

from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.permits import RequestPermitIssuer
from incident_lens.schemas import CoordinatorDecision

BASELINE = "3629b0695ed1b78d1bd31121363166558a850940"
VALID = '{"action":"ABSTAIN","reason":"missing","stop_reason":"missing"}'
MODEL = "fixture-model"
PROMPT = "Return the required coordinator decision."
INPUT = {"fixture": "public synthetic reliability input"}


@dataclass(frozen=True)
class Scenario:
    case_id: str
    schedule: tuple
    requests: int = 4
    wall: float = 100.0
    retry_after: str | None = None
    stop: str | None = None
    stage: int | None = None


SCENARIOS = [
    Scenario("F01", (200,)),
    Scenario("F02", (429, 200)),
    Scenario("F03", (429, 200), wall=2.0, retry_after="30"),
    Scenario("F04", (503, 503, 200)),
    Scenario("F05", (401,)),
    Scenario("F06", (400,)),
    Scenario("F07", ("timeout", 200)),
    Scenario("F08", ("invalid", 200)),
    Scenario("F09", ("schema", 200)),
    Scenario("F10", ("invalid", "invalid")),
    Scenario("F13", (429, 200), stop="backoff"),
    Scenario("F14", (200,), stop="inflight"),
    Scenario("F16", ("unknown",)),
    Scenario("F17", ("length", 200)),
    Scenario("F21", (403,)),
    Scenario("F22", (422,)),
    Scenario("F23", (429, 200), requests=1),
    Scenario("F24", (429, 200), stage=1),
    Scenario("F25", (429, "invalid", 200)),
    Scenario("F26", ("invalid", 200), requests=1),
    Scenario("F27", ("schema", 200), stage=1),
    Scenario("F28", ("invalid", 200), requests=2),
    Scenario("F29", (503, 503, "invalid", 200)),
    Scenario("F30", (503, 503, "invalid", "invalid")),
    Scenario("F31", ("invalid", 503, 200)),
    Scenario("F32", ("invalid", 503, 503, 503)),
]


def frozen_provider(root):
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:src/incident_lens/llm/provider.py"], cwd=root
    )
    module = types.ModuleType("incident_lens_frozen_v12_provider")
    exec(compile(source, f"{BASELINE}/provider.py", "exec"), module.__dict__)
    return module.RealChatProvider, source


def envelope(kind):
    content = "not-json" if kind == "invalid" else "{}" if kind == "schema" else VALID
    data = {
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": "length" if kind == "length" else "stop",
            }
        ]
    }
    # These schedules exercise error responses with unknown billing. Separate
    # adapter tests cover error responses that explicitly report valid usage.
    if kind != "unknown" and not (type(kind) is int and kind >= 400):
        data["usage"] = {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}
    return data


async def run_case(scenario, variant, baseline_class):
    """Physical request count comes only from MockTransport dispatches."""
    now = [0.0]
    attempts, events, bodies = [], [], []
    stopped = [False]
    issuer = RequestPermitIssuer(
        max_requests=scenario.requests,
        deadline=scenario.wall,
        clock=lambda: now[0],
        stage_limits={"monitoring": scenario.stage} if scenario.stage is not None else None,
    )
    stage = "monitoring" if scenario.stage is not None else None

    def guard():
        permit = issuer.acquire(stage=stage, stop_token=lambda: stopped[0])
        issuer.mark_dispatched(permit)
        return permit

    def stop_guard():
        if stopped[0]:
            raise asyncio.CancelledError()

    async def sleeper(delay):
        now[0] += delay
        if scenario.stop == "backoff":
            stopped[0] = True
            raise asyncio.CancelledError()

    async def respond(request):
        kind = scenario.schedule[min(len(attempts), len(scenario.schedule) - 1)]
        bodies.append(json.loads(request.content))
        attempts.append(
            dict(
                case_id=scenario.case_id,
                variant=variant,
                event_type="FIXTURE_HTTP_DISPATCH",
                http_attempt_index=len(attempts) + 1,
                injected_outcome=kind,
            )
        )
        if scenario.stop == "inflight":
            stopped[0] = True
            raise asyncio.CancelledError()
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(
            kind if isinstance(kind, int) else 200,
            json=envelope(kind),
            headers={"Retry-After": scenario.retry_after} if scenario.retry_after else {},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        kwargs = dict(
            endpoint="https://fixture.invalid",
            api_key="synthetic",
            model=MODEL,
            client=client,
            timeout=100.0,
            structured_repair_retries=1,
            response_format_mode="json_schema",
        )
        if variant == "R0":
            provider = baseline_class(**kwargs)
        else:
            provider = RealChatProvider(
                **kwargs,
                recovery={"enabled": True, "min_request_time_seconds": 1.0},
                clock=lambda: now[0],
                sleeper=sleeper,
                targeted_structured_repair=variant == "R3",
            )
            if variant in {"R2", "R3"}:
                provider.recovery_snapshot = lambda: issuer.snapshot(stage)
            provider.stop_guard = stop_guard
            provider.request_reconciler = issuer.reconcile
            provider.event_observer = lambda event_type, **details: events.append(
                dict(case_id=scenario.case_id, variant=variant, event_type=event_type, **details)
            )
        provider.request_guard = guard
        completed, code, category, usage = False, None, None, {}
        try:
            _, usage = await provider.structured_call(
                "coordinator", PROMPT, INPUT, CoordinatorDecision
            )
            completed = True
        except asyncio.CancelledError as exc:
            code, category, usage = "CANCELLED", "CANCELLED", getattr(exc, "usage", {})
        except RuntimeError as exc:
            code, usage = getattr(exc, "code", type(exc).__name__), getattr(exc, "usage", {})
            category = getattr(getattr(exc, "failure", None), "category", None)
    total = usage.get("total_tokens")
    # Missing usage on any dispatched attempt prevents a known aggregate bill.
    if not completed and (not usage or not usage.get("tokens_complete", False)):
        total = None
    # A transport retry reuses the same repair message; count only its introduction.
    repairs = sum(
        len(body["messages"]) > len(bodies[index - 1]["messages"])
        for index, body in enumerate(bodies)
        if index > 0
    )
    if variant != "R0":
        assert usage.get("repair_requests", 0) == repairs
        retry_dispatches = sum(
            body["messages"] == bodies[index - 1]["messages"]
            for index, body in enumerate(bodies)
            if index > 0
        )
        assert usage.get("transport_retries", 0) == retry_dispatches
    content_responses = [
        x
        for x in attempts
        if x["injected_outcome"] not in (429, 503, 401, 403, 400, 422, "timeout")
    ]
    row = dict(
        case_id=scenario.case_id,
        variant=variant,
        scope="provider",
        completed=completed,
        actual_http_requests=len(attempts),
        total_tokens=total,
        measured_total_tokens=usage.get("measured_total_tokens", 0),
        tokens_complete=total is not None,
        error_code=code,
        category=category,
        repair_requests=repairs,
        transport_retries=usage.get("transport_retries", 0),
        retryable_fault=scenario.schedule[0] in (429, 503, "timeout"),
        has_content_response=bool(content_responses),
        first_response_valid=bool(content_responses)
        and content_responses[0]["injected_outcome"] in (200, "unknown"),
        simulated_backoff_seconds=now[0],
        stop_reason="CANCELLED" if stopped[0] else None,
        elapsed_ms=usage.get("elapsed_ms"),
        cost=None,
        rca_accuracy=None,
    )
    assert len(attempts) <= scenario.requests
    if scenario.stage is not None:
        assert len(attempts) <= scenario.stage
    assert usage.get("llm_calls", len(attempts)) == len(attempts)
    return row, attempts + events, bodies


def schedule_manifest():
    return [asdict(scenario) for scenario in SCENARIOS]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
