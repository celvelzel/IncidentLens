"""Exercise semantic correction through a fake CLI; never call a remote model."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from incident_lens.agents.service import decide
from incident_lens.llm import codex_subscription as transport
from incident_lens.llm.provider import ProviderError


@pytest.fixture
def fake_cli(monkeypatch):
    outputs, launches, payloads = [], [], []
    monkeypatch.setattr(transport, "resolve_cli", lambda executable: "fixture-codex")
    monkeypatch.setattr(transport, "inspect_auth", lambda executable: {"auth_method": "chatgpt"})
    monkeypatch.setattr(transport, "write_inference_catalog",
                        lambda executable, model, path: path.write_text('{"models": []}'))

    class Process:
        returncode = 0

        async def communicate(self, payload):
            payloads.append(json.loads(payload))
            events = [{"type": "item.completed", "item": {"type": "agent_message"}},
                      {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 3}}]
            return b"\n".join(json.dumps(e).encode() for e in events), b""

    async def launch(*command, **kwargs):
        launches.append(command)
        output = outputs.pop(0)
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(output))
        return Process()

    monkeypatch.setattr(transport.asyncio, "create_subprocess_exec", launch)
    return outputs, launches, payloads


def decision(role="logs", tool="query_metrics"):
    return {"action": "INVESTIGATE", "reason": "fixture discovery", "assignments": [{
        "task_id": "fixture-task", "role": role, "question": "Inspect public telemetry",
        "allowed_tools": [tool], "filters": {}, "reason": "fixture",
        "expected_discriminator": "observed mechanism",
    }], "hypothesis_updates": [], "selected_hypothesis_id": None, "stop_reason": None}


async def test_acl_mistake_corrected_once_before_dispatch_and_accounted(tmp_path, fake_cli):
    outputs, launches, payloads = fake_cli
    outputs.extend([decision(), decision("metrics")])
    provider = transport.CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls")
    permits, tokens, events = [], [], []
    provider.request_guard = lambda: permits.append(len(permits) + 1) or permits[-1]
    provider.token_observer = tokens.append
    reconciled = []
    provider.request_reconciler = lambda permit, total: reconciled.append((permit, total))
    provider.event_observer = lambda kind, **details: events.append((kind, details))
    acl = {"logs": ["query_logs"], "metrics": ["query_metrics"]}
    result, usage = await decide(provider, {"role_tool_acl": acl, "hypotheses": []})
    assert result.assignments[0].role == "metrics"
    assert len(launches) == len(permits) == 2 and tokens == [5, 5]
    assert reconciled == [(1, 5), (2, 5)]
    assert usage["llm_calls"] == usage["codex_invocations"] == 2
    assert usage["repair_requests"] == 1 and usage["logical_structured_calls"] == 1
    assert usage["measured_total_tokens"] == 10 and usage["total_tokens"] is None
    assert usage["codex_reported_total_tokens"] == 10
    correction = payloads[1]["output_correction"]
    assert "role_tool_acl" in correction["validation_feedback"][0]["description"]
    assert payloads[1]["original_input"]["role_tool_acl"] == acl
    assert json.loads(correction["previous_invalid_output"])["assignments"][0]["role"] == "logs"
    assert events[0][0] == "STRUCTURED_REPAIR"
    assert len(list((tmp_path / "calls").glob("*/failure.json"))) == 1
    assert len(json.loads(next((tmp_path / "calls/_logical_calls").glob("*.json")).read_text())["attempts"]) == 2


async def test_repeated_acl_error_stops_after_two_requests(tmp_path, fake_cli):
    outputs, launches, _ = fake_cli
    outputs.extend([decision(), decision()])
    provider = transport.CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls")
    with pytest.raises(ProviderError, match="CODEX_STRUCTURED_OUTPUT_INVALID") as caught:
        await decide(provider, {"role_tool_acl": {"logs": ["query_logs"]}})
    assert len(launches) == 2
    assert caught.value.usage["llm_calls"] == 2
    assert caught.value.usage["repair_requests"] == 1
    assert caught.value.usage["measured_total_tokens"] == 10


async def test_repair_respects_request_budget_and_retains_first_usage(tmp_path, fake_cli):
    outputs, launches, _ = fake_cli
    outputs.extend([decision(), decision("metrics")])
    provider = transport.CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls")
    admissions = 0

    def guard():
        nonlocal admissions
        admissions += 1
        if admissions > 1:
            raise ProviderError("REQUEST_BUDGET_EXCEEDED")
        return admissions

    provider.request_guard = guard
    with pytest.raises(ProviderError, match="REQUEST_BUDGET_EXCEEDED") as caught:
        await decide(provider, {"role_tool_acl": {"logs": ["query_logs"], "metrics": ["query_metrics"]}})
    assert len(launches) == 1
    assert caught.value.usage["llm_calls"] == 1
    assert caught.value.usage["repair_requests"] == 0
    assert caught.value.usage["measured_total_tokens"] == 5


async def test_invalid_output_can_opt_out_of_correction(tmp_path, fake_cli):
    outputs, launches, _ = fake_cli
    outputs.append(decision())
    provider = transport.CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls", structured_repair_retries=0)
    with pytest.raises(ProviderError, match="CODEX_STRUCTURED_OUTPUT_INVALID"):
        await decide(provider, {"role_tool_acl": {"logs": ["query_logs"]}})
    assert len(launches) == 1


async def test_validator_secret_is_not_copied_into_repair_feedback(tmp_path, fake_cli):
    from pydantic import model_validator

    class Answer(BaseModel):
        value: int

        @model_validator(mode="after")
        def reject(self):
            if self.value < 0:
                raise ValueError("Bearer synthetic-validator-secret https://private.invalid")
            return self

    outputs, _, payloads = fake_cli
    outputs.extend([{"value": -1}, {"value": 1}])
    provider = transport.CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls")
    result, _ = await provider.structured_call("single", "fixture", {}, Answer)
    assert result.value == 1
    assert "synthetic-validator-secret" not in json.dumps(payloads)
