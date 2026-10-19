"""Offline regressions for the post-WP-D repair; no live endpoint is used."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from incident_lens.agents.service import FAILURE_MODES, analysis_schema
from incident_lens.evaluation.runner import MeasuredProvider, csv_rows, usage_metrics
from incident_lens.evaluation.verifier import verifier_metrics
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.llm.usage import aggregate_usage, begin_request, normalize_usage, record_usage
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.schemas import Budget


class Output(BaseModel):
    answer: str


def rescue_fixture():
    path = Path(__file__).with_name("test_rescue_finalization.py")
    spec = importlib.util.spec_from_file_location("wpd_rescue_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def envelope(content, usage=None):
    return {"choices": [{"message": {"content": content}}], "usage": usage}


def test_mixed_physical_usage_retains_measurements_and_unknowns():
    usage = {"llm_calls": 1}
    begin_request(usage)
    record_usage(usage, {"prompt_tokens": 10, "completion_tokens": 5})
    usage["llm_calls"] += 1
    begin_request(usage)  # A dispatched timeout has unknowable usage.
    totals = aggregate_usage([usage, {"llm_calls": 1, "total_tokens": 7}])
    assert totals["total_tokens"] is None
    assert totals["measured_total_tokens"] == 22
    assert totals["measured_prompt_tokens"] == 10
    assert totals["requests_with_token_usage"] == 2
    assert totals["requests_without_token_usage"] == 1
    assert not totals["tokens_complete"]


@pytest.mark.parametrize("reported,expected", [
    ({"prompt_tokens": 0, "completion_tokens": 0}, 0),
    ({"prompt_tokens": 4, "completion_tokens": 3}, 7),
    ({"prompt_tokens": True, "completion_tokens": 3}, None),
    ({"prompt_tokens": -1, "completion_tokens": 3}, None),
    ({}, None),
])
def test_only_valid_provider_measurements_are_summed(reported, expected):
    assert normalize_usage(reported)["total_tokens"] == expected


def test_nested_metrics_csv_is_stable_after_sorted_json_resume():
    row = {"verifier": {"z": [1, {"b": 2, "a": 3}], "a": False}}
    restored = json.loads(json.dumps(row, sort_keys=True))
    assert csv_rows([row]) == csv_rows([restored])
    assert json.loads(csv_rows([row])[0]["verifier"]) == row["verifier"]


@pytest.mark.parametrize("status", [429, 503])
async def test_reliable_error_without_usage_keeps_unknown_total(status):
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(status, json={"error": {"code": "rate_limit_exceeded"}})
        return httpx.Response(200, json=envelope('{"answer":"ok"}', {"total_tokens": 7}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "k", "m", client=client,
                                    recovery={"enabled": True, "initial_backoff_seconds": 0.0})
        _, usage = await provider.structured_call("verifier", "", {}, Output)
    assert len(requests) == 2 and usage["total_tokens"] is None
    assert usage["measured_total_tokens"] == 7 and not usage["tokens_complete"]
    assert usage["requests_with_token_usage"] == usage["requests_without_token_usage"] == 1


async def test_repair_then_timeout_keeps_first_response_usage():
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 2:
            raise httpx.ReadTimeout("sensitive transport detail")
        return httpx.Response(200, json=envelope("invalid", {"total_tokens": 9}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        measured = MeasuredProvider(RealChatProvider("https://fixture.invalid", "secret", "m", client=client))
        with pytest.raises(ProviderError) as error:
            await measured.structured_call("changes", "", {}, Output)
    result = usage_metrics(measured, {"events": []})
    assert result["total_tokens"] is None and result["measured_total_tokens"] == 9
    assert result["requests_with_token_usage"] == result["requests_without_token_usage"] == 1
    assert result["token_usage_by_role"]["changes"]["measured_total_tokens"] == 9
    assert error.value.failure.category == "TRANSPORT_TIMEOUT"
    assert "sensitive" not in json.dumps(result)


@pytest.mark.parametrize("status,code,category,retryable", [
    (401, "invalid_api_key", "AUTHENTICATION_FAILED", False),
    (429, "insufficient_quota", "QUOTA_EXHAUSTED", False),
    (429, "rate_limit_exceeded", "RATE_LIMITED", True),
    (503, None, "TRANSIENT_SERVER_ERROR", True),
])
async def test_legacy_http_error_keeps_safe_failure_metadata(status, code, category, retryable):
    def respond(request):
        return httpx.Response(status, headers={"Retry-After": "2"}, json={
            "error": {"code": code, "message": "NEVER_LOG_THIS"},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "secret", "m", client=client)
        with pytest.raises(ProviderError) as error:
            await provider.structured_call("coordinator", "", {}, Output)
    details = error.value.usage["failure"]
    assert details["category"] == category and details["retryable"] is retryable
    assert details["provider_http_status"] == status
    assert details["retry_after_seconds"] == 2
    assert "NEVER_LOG_THIS" not in json.dumps(details)


async def test_coordinate_retries_transient_http_once_without_losing_usage():
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=envelope(json.dumps({
            "action": "ABSTAIN", "reason": "Missing causal evidence", "assignments": [],
            "hypothesis_updates": [], "selected_hypothesis_id": None,
            "stop_reason": "Missing discriminating evidence",
        }), {"prompt_tokens": 4, "completion_tokens": 3}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = MeasuredProvider(RealChatProvider("https://fixture.invalid", "k", "m", client=client))
        state = await run_investigation("incident_001", provider, budget=Budget())
    metrics = usage_metrics(provider, state.model_dump(mode="json"))
    assert len(requests) == metrics["actual_http_requests"] == 2
    assert metrics["task_retries"] == 1
    assert metrics["measured_total_tokens"] == 7 and metrics["total_tokens"] is None
    assert any(e.event_type == "TASK_RETRY_SCHEDULED" for e in state.events)
    failure = next(e for e in state.events if e.event_type == "MODEL_FAILURE")
    assert failure.details["failure"]["provider_http_status"] == 503


async def test_reliable_retry_exhaustion_does_not_multiply_task_retries():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = MeasuredProvider(RealChatProvider(
            "https://fixture.invalid", "k", "m", client=client,
            recovery={"enabled": True, "max_transport_retries": 1,
                      "max_physical_attempts_per_call": 2, "initial_backoff_seconds": 0.0},
        ))
        state = await run_investigation("incident_001", provider, budget=Budget())
    metrics = usage_metrics(provider, state.model_dump(mode="json"))
    assert len(requests) == 2 and metrics["task_retries"] == 0
    assert metrics["transport_retries"] == 1
    assert state.termination.runtime_failure


def test_generation_requires_exact_failure_mode_labels():
    model = analysis_schema([]).model_fields["hypotheses"].annotation.__args__[0]
    fields = dict(hypothesis_id="h1", culprit_service="backend", failure_mode=FAILURE_MODES[0])
    assert model(**fields).failure_mode == FAILURE_MODES[0]
    with pytest.raises(ValidationError):
        model(**dict(fields, failure_mode=FAILURE_MODES[0] + ": explanatory prose"))


def test_finalization_feedback_does_not_create_shared_causal_questions():
    fixture = rescue_fixture()
    run = fixture.fake_run()
    state, _, _ = fixture.build_state(with_errors=False)
    state.reviews = []
    run.limits = Budget()
    run.failed_finalizations = set()
    run.call_budget.remaining_seconds = lambda: 100.0
    run.exhausted = lambda state: None
    before = list(state.open_questions)
    run.finalize({"investigation": state})
    assert state.open_questions == before
    rejected = next(e for e in state.events if e.event_type == "FINALIZE_REJECTED")
    assert rejected.details["errors"]
    assert rejected.details["selected_hypothesis_id"] == state.hypotheses[0].hypothesis_id


def test_board_changes_when_assessment_changes_without_new_evidence():
    state, _, _ = rescue_fixture().build_state(with_errors=False)
    first = InvestigationRun.board_fingerprint(state)
    state.hypotheses[0].open_questions = ["A material causal gap"]
    assert InvestigationRun.board_fingerprint(state) != first


def test_verifier_effects_are_observations_not_claims_of_benefit():
    metrics = verifier_metrics({"events": [
        {"event_type": "REVIEW", "role": "verifier", "details": {"review": {
            "verdict": "sufficient", "requested_checks": [], "optional_checks": [],
        }}},
        {"event_type": "REVIEW_EFFECT", "details": {"gate_discharged": True}},
        {"event_type": "REVIEW_FOLLOWUP", "details": {"new_evidence_ids": ["e1"]}},
        {"event_type": "LLM_CALL", "role": "verifier", "source": "model", "details": {
            "llm_calls": 1, "total_tokens": 17,
        }},
    ]})
    assert metrics["reviews_discharge_gate"] == metrics["followups_with_new_evidence"] == 1
    assert metrics["http_requests"] == 1 and metrics["usage"]["total_tokens"] == 17
    assert metrics["benefit_assessment"] == "pending_manual_or_paired_evaluation"


def test_old_wpd_artifacts_recover_lower_bound_without_inventing_total():
    path = Path(__file__).resolve().parents[2] / "analysis/wp_d/summarize.py"
    spec = importlib.util.spec_from_file_location("wpd_summary_repair", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verification = {"actual_http_requests": 3, "total_tokens": None}
    events = [
        {"event_type": "LLM_CALL", "details": {"llm_calls": 1, "total_tokens": 11}},
        {"event_type": "MODEL_FAILURE", "details": {
            "llm_calls": 2, "total_tokens": None, "measured_total_tokens": 5,
            "tokens_complete": False,
        }},
    ]
    recovered = module.token_accounting(verification, events)
    assert recovered["total_tokens"] is None
    assert recovered["measured_total_tokens"] == 16 and not recovered["tokens_complete"]
