"""Analysis consumes observations; tools remain under runtime control."""

import copy
import json

import httpx
import pytest

from incident_lens.agents.service import analyze, plan_tools
from incident_lens.llm.provider import ProviderError, RealChatProvider


def inputs(role="database", single=False):
    tool = {
        "database": "get_db_lock_waits", "logs": "query_logs",
        "metrics": "query_metrics", "changes": "query_changes",
    }[role]
    context = dict(workspace_id="test", incident_id="incident-1", run_id="run-1",
                   role="single" if single else role, allowed_tools=[tool],
                   allowed_evidence_scope=["incident-1"], remaining_tool_calls=38)
    task = dict(task_id="task-1", role=role, question="Check the observed mechanism",
                allowed_tools=[tool], filters={}, reason="Distinguish causes",
                expected_discriminator="Measured cause versus unknown behavior")
    records = [dict(evidence_id="E-1", incident_id="incident-1", source_type=role,
                    service="postgres", observed_at="2026-10-12T09:00:46Z",
                    source_path="public/database.jsonl", excerpt="Observed transaction lock wait",
                    metadata={"duration_ms": 7700})]
    return context, task, records


def valid_analysis(payload):
    return json.dumps(dict(
        finding=dict(finding_id="finding-1", task_id=payload["task"]["task_id"],
                     run_id=payload["context"]["run_id"],
                     incident_id=payload["context"]["incident_id"], role=payload["task"]["role"],
                     claim="Observed lock wait; attribution remains uncertain", evidence_ids=["E-1"],
                     relation="neutral", confidence_qualifier="weak", followup_question=None),
        hypotheses=[], requested_checks=[],
    ))


def envelope(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}}


@pytest.mark.parametrize("role", ["database", "logs", "metrics", "changes"])
@pytest.mark.parametrize("single", [False, True])
async def test_analysis_has_no_execution_authority_and_preserves_task_scope(role, single):
    context, task, records = inputs(role, single)
    before = copy.deepcopy((context, task, records))
    bodies = []

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        payload = json.loads(body["messages"][1]["content"])
        assert payload["phase"] == "analysis"
        assert payload["context"] == {k: context[k] for k in (
            "workspace_id", "incident_id", "run_id", "role")}
        assert payload["task"] == task  # Future checks keep the same permissions.
        assert payload["records"] == records
        assert "No callable tools are registered" in body["messages"][0]["content"]
        assert "CURRENT PHASE: ANALYZE" in body["messages"][0]["content"]
        assert "tools" not in body
        return httpx.Response(200, json=envelope(valid_analysis(payload)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "k", "m", client=client,
                                    recovery={"enabled": True})
        result, usage = await analyze(provider, context, task, records)
    assert (context, task, records) == before
    assert result.finding.role == task["role"]
    assert result.finding.evidence_ids == ["E-1"]
    assert usage["actual_http_requests"] == len(bodies) == 1


async def test_planning_still_has_authority_and_typed_tool_arguments():
    context, task, _ = inputs()

    def respond(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        assert payload["context"]["remaining_tool_calls"] == 38
        assert payload["effective_allowed_tools"] == ["get_db_lock_waits"]
        assert "get_db_lock_waits" in payload["tool_argument_schemas"]
        return httpx.Response(200, json=envelope(json.dumps({"calls": [{
            "tool_name": "get_db_lock_waits", "args": {
                "service": "postgres", "start_ts": "2026-10-12T08:30:00Z",
                "end_ts": "2026-10-12T10:00:00Z", "limit": 50,
            },
        }]})))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "k", "m", client=client,
                                    recovery={"enabled": True})
        plan, usage = await plan_tools(provider, context, task, {"services": ["postgres"]}, {})
    assert plan.calls[0].tool_name == "get_db_lock_waits"
    assert usage["actual_http_requests"] == 1


@pytest.mark.parametrize("recover", [True, False])
async def test_dsml_repair_is_targeted_bounded_and_never_replays_untrusted_content(recover):
    context, task, records = inputs()
    bodies, events = [], []
    dsml = '<｜｜DSML｜｜ calls>\ninvoke name="SECRET_TOOL">SECRET_INPUT'

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        payload = json.loads(body["messages"][1]["content"])
        if len(bodies) == 2:
            feedback = body["messages"][-1]["content"]
            assert "No callable tools are registered" in feedback
            assert "requested_checks" in feedback
            assert "tool_call_markup" in feedback
            assert "SECRET" not in json.dumps(body)
            assert body["response_format"] == bodies[0]["response_format"]
        return httpx.Response(200, json=envelope(
            valid_analysis(payload) if recover and len(bodies) == 2 else dsml))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "k", "m", client=client,
                                    recovery={"enabled": True})
        provider.event_observer = lambda kind, **details: events.append(dict(kind=kind, **details))
        if recover:
            result, usage = await analyze(provider, context, task, records)
            assert result.finding.evidence_ids == ["E-1"]
        else:
            with pytest.raises(ProviderError, match="STRUCTURED_OUTPUT_INVALID") as caught:
                await analyze(provider, context, task, records)
            usage = caught.value.usage
            assert caught.value.failure.category == "INVALID_JSON"
    assert len(bodies) == usage["actual_http_requests"] == 2
    assert usage["repair_requests"] == 1
    assert usage["transport_retries"] == 0
    assert usage["total_tokens"] == 6
    assert "SECRET" not in json.dumps(events)
    failures = [e for e in events if e["kind"] == "PROVIDER_FAILURE_CLASSIFIED"]
    assert all("tool_call_markup" in e["validation_summary"] for e in failures)


async def test_analysis_still_rejects_unobserved_citations_after_one_repair():
    context, task, records = inputs()

    def respond(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        invalid = json.loads(valid_analysis(payload))
        invalid["finding"]["evidence_ids"] = ["FABRICATED"]
        return httpx.Response(200, json=envelope(json.dumps(invalid)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "k", "m", client=client,
                                    recovery={"enabled": True})
        with pytest.raises(ProviderError, match="STRUCTURED_OUTPUT_INVALID") as caught:
            await analyze(provider, context, task, records)
    assert caught.value.failure.category == "SCHEMA_VALIDATION_FAILED"
    assert caught.value.usage["actual_http_requests"] == 2
