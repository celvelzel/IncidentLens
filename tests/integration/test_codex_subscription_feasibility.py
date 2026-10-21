"""Offline transport feasibility contracts. Never launch Codex or call a model."""

import json

import pytest

from incident_lens.llm.codex_subscription import (
    CodexSubscriptionProvider,
    account_environment,
    decode_events,
    safe_diagnostic,
)
from incident_lens.llm.provider import ProviderError


def test_api_keys_and_project_credentials_not_inherited(monkeypatch):
    for name in ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "INCIDENT_LENS_API_KEY"]:
        monkeypatch.setenv(name, "synthetic-fixture-only")
    monkeypatch.setenv("HTTPS_PROXY", "http://localhost:1234")
    env = account_environment()
    assert env["HTTPS_PROXY"] == "http://localhost:1234"
    assert not any(name in env for name in ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "INCIDENT_LENS_API_KEY"])


def test_completed_message_has_usage_without_tools():
    stream = b'\n'.join(json.dumps(e).encode() for e in [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
        {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 3}},
    ])
    usage, events = decode_events(stream)
    assert usage["output_tokens"] == 3
    assert events[0]["item_type"] == "agent_message"
    assert all("text" not in event for event in events)


@pytest.mark.parametrize("kind", ["command_execution", "mcp_tool_call", "web_search", "file_change", "error"])
def test_tool_or_error_activity_fails_closed(kind):
    with pytest.raises(ProviderError, match="CODEX_UNEXPECTED_TOOL_ACTIVITY"):
        decode_events(json.dumps({"type": "item.completed", "item": {"type": kind}}).encode())


def test_missing_completion_is_not_success():
    with pytest.raises(ProviderError, match="COMPLETION_MISSING"):
        decode_events(b'{"type":"thread.started"}')


def test_diagnostic_redacts_tokens_and_urls():
    text = safe_diagnostic(b'Bearer synthetic-token-123 sk-test-fixture-only https://example.org/secret?q=test')
    assert "synthetic-token" not in text and "fixture-only" not in text and "example.org" not in text


def test_experiment_rejects_any_model_substitution_before_cli_use(tmp_path):
    with pytest.raises(ValueError, match="pinned to gpt-5.6-luna"):
        CodexSubscriptionProvider("some-other-model", tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


async def test_old_model_receipt_cannot_start_new_model_investigation(tmp_path):
    from argparse import Namespace

    from scripts.run_codex_subscription_case import run

    config = tmp_path / "config.json"
    config.write_text(json.dumps({"model": "gpt-5.6-luna"}), encoding="utf-8")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"model_id": "gpt-5.6-luna", "provider_id": "real"}), encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"status": "FEASIBLE_FOR_CODEX_SUBSCRIPTION_TRANSPORT",
                                  "probes": [{"matched": True, "usage": {"model_id": "unapproved-old-model"}}]}), encoding="utf-8")
    args = Namespace(execute_development_case=True, config=config, protocol=protocol,
                     feasibility=receipt, out=tmp_path / "not-created")
    with pytest.raises(ValueError, match="matching successful"):
        await run(args)
    assert not args.out.exists()
