"""HTTP fixture compatibility is distinct from a live provider experiment."""

import json

import httpx

from incident_lens.agents.service import AnalysisOutput, DynamicDecision, InvestigatorPlan
from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import CoordinatorDecision, Review


async def test_real_adapter_full_graph_with_structured_http_fixture():
    outputs = {
        m.__name__: m
        for m in (AnalysisOutput, InvestigatorPlan, CoordinatorDecision, DynamicDecision, Review)
    }
    captured = []

    async def respond(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        captured.append(payload)
        output = outputs[body["response_format"]["json_schema"]["name"]]
        role = payload.get("context", {}).get(
            "role", "verifier" if output is Review else "coordinator"
        )
        result, _ = await MockProvider().structured_call(
            role, body["messages"][0]["content"], payload, output
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": result.model_dump_json()}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider(
            "https://fixture.invalid/v1", "fixture-secret", "fixture", client=client
        )
        state = await run_investigation("incident_001", provider)
    assert state.report.status == "RESOLVED"
    assert state.llm_calls_used == len(captured) == 15
    assert state.tokens_used == 75
    assert next(e for e in state.events if e.event_type == "REPORT").details["tokens_complete"]
    assert all(e.source == "model" for e in state.events if e.event_type == "LLM_CALL")

    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()

    assert all(
        not {"ground_truth", "oracle_scoring_fields", "is_identifiable"}.intersection(keys(payload))
        for payload in captured
    )
    assert "fixture-secret" not in state.model_dump_json()
