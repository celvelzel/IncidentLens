"""Offline transport feasibility contracts. Never launch Codex or call a model."""

import json
from pathlib import Path

import pytest

from incident_lens.llm.codex_subscription import (
    CodexSubscriptionProvider,
    account_environment,
    decode_events,
    safe_diagnostic,
    subscription_command,
)
from incident_lens.llm.provider import ProviderError


def test_api_keys_and_project_credentials_not_inherited(monkeypatch):
    for name in ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "INCIDENT_LENS_API_KEY"]:
        monkeypatch.setenv(name, "synthetic-fixture-only")
    monkeypatch.setenv("HTTPS_PROXY", "http://localhost:1234")
    env = account_environment()
    assert env["HTTPS_PROXY"] == "http://localhost:1234"
    assert not any(name in env for name in ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "INCIDENT_LENS_API_KEY"])


def test_desktop_tool_transport_not_inherited_but_security_and_login_are_preserved(monkeypatch):
    removed = ["CODEX_APP_TOOLS_PIPE_PATH", "CODEX_SESSION_ID", "CODEX_TOOL_CALL_ID",
               "CODEX_TASK_WORKSPACE_VERIFYING_IDENTITY", "BROWSER_USE_ACCESS_VERIFYING_IDENTITY"]
    for name in removed:
        monkeypatch.setenv(name, "fixture-host-transport")
    preserved = {"CODEX_HOME": "/fixture/login", "CODEX_SANDBOX": "seatbelt",
                 "CODEX_SANDBOX_NETWORK_DISABLED": "1", "HTTPS_PROXY": "http://localhost:1234"}
    for name, value in preserved.items():
        monkeypatch.setenv(name, value)
    env = account_environment()
    assert not any(name in env for name in removed)
    assert all(env[name] == value for name, value in preserved.items())


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


@pytest.mark.parametrize("tool_event", [False, True, "remote_error"])
async def test_transport_disables_tool_providers_and_still_rejects_tool_events(
    tmp_path, monkeypatch, tool_event,
):
    """Exercise actual launch arguments and audit, without a remote model call."""
    from pydantic import BaseModel

    from incident_lens.llm import codex_subscription as transport

    class Answer(BaseModel):
        value: int

    monkeypatch.setattr(transport, "resolve_cli", lambda executable: "fixture-codex")
    monkeypatch.setattr(transport, "inspect_auth", lambda executable: {"auth_method": "chatgpt"})
    monkeypatch.setattr(transport, "write_inference_catalog",
                        lambda executable, model, path: path.write_text('{"models": []}'))
    monkeypatch.setenv("HTTPS_PROXY", "http://localhost:1234")
    monkeypatch.setenv("INCIDENT_LENS_API_KEY", "fixture-secret")
    launches = []

    class Process:
        returncode = 0

        async def communicate(self, payload):
            if tool_event == "remote_error":
                return (b'{"type":"turn.failed","error":{"message":"Bearer fixture-secret https://example.org/private"}}', b"")
            item = {"type": "mcp_tool_call" if tool_event else "agent_message"}
            events = [{"type": "item.completed", "item": item},
                      {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 3}}]
            return b"\n".join(json.dumps(e).encode() for e in events), b""

    async def launch(*command, **kwargs):
        launches.append(command)
        assert Path(kwargs["cwd"]) != tmp_path
        assert kwargs["env"]["HTTPS_PROXY"] == "http://localhost:1234"
        assert "INCIDENT_LENS_API_KEY" not in kwargs["env"]
        disabled = {command[i + 1] for i, arg in enumerate(command) if arg == "--disable"}
        assert {"code_mode_host", "code_mode", "shell_tool", "apps", "plugins"} <= disabled
        configs = dict(command[i + 1].split("=", 1)
                       for i, arg in enumerate(command) if arg == "--config")
        assert configs["mcp_servers"] == "{}"
        assert configs["agents.enabled"] == "false"
        assert Path(json.loads(configs["model_catalog_json"])).is_file()
        assert "--ignore-user-config" in command and "--ephemeral" in command
        Path(command[command.index("--output-last-message") + 1]).write_text('{"value": 5}')
        return Process()

    monkeypatch.setattr(transport.asyncio, "create_subprocess_exec", launch)
    provider = CodexSubscriptionProvider("gpt-5.6-luna", tmp_path / "calls", diagnostic_mode=True)
    if tool_event == "remote_error":
        with pytest.raises(ProviderError, match="CODEX_REMOTE_TURN_FAILED"):
            await provider.structured_call("single", "Return JSON only", {}, Answer)
        diagnostic = next((tmp_path / "calls").glob("*/startup-diagnostic.json")).read_text()
        assert "fixture-secret" not in diagnostic and "example.org" not in diagnostic
        assert "turn.failed" in diagnostic
    elif tool_event:
        with pytest.raises(ProviderError, match="CODEX_UNEXPECTED_TOOL_ACTIVITY"):
            await provider.structured_call("single", "Return JSON only", {}, Answer)
        failure = next((tmp_path / "calls").glob("*/failure.json"))
        assert json.loads(failure.read_text())["unexpected_item_type"] == "mcp_tool_call"
    else:
        answer, _ = await provider.structured_call("single", "Return JSON only", {}, Answer)
        assert answer.value == 5
    assert len(launches) == 1


def test_command_preserves_paths_with_spaces_as_single_arguments(tmp_path):
    directory = tmp_path / "output with spaces"
    command = subscription_command("codex path", "gpt-5.6-luna", directory, "low", directory / "catalog.json")
    assert command[0] == "codex path"
    assert command[command.index("--output-schema") + 1] == str(directory / "output-schema.json")
    assert command[-1] == "-"


def test_catalog_preserves_model_and_prompts_but_removes_code_mode_only(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from incident_lens.llm import codex_subscription as transport
    entry = {"slug": "gpt-5.6-luna", "tool_mode": "code_mode_only", "node_repl_disabled": False,
             "base_instructions": "fixture-original", "model_messages": {"fixture": "unchanged"},
             "context_window": 272000}
    def run(command, **kwargs):
        assert command == ["fixture-codex", "debug", "models", "--bundled"]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"models": [entry]}).encode())
    monkeypatch.setattr(transport.subprocess, "run", run)
    path = tmp_path / "catalog.json"
    transport.write_inference_catalog("fixture-codex", "gpt-5.6-luna", path)
    assert json.loads(path.read_text()) == {
        "models": [dict(entry, tool_mode="direct", node_repl_disabled=True)]}
    with pytest.raises(ProviderError, match="CATALOG_UNAVAILABLE"):
        transport.write_inference_catalog("fixture-codex", "missing-model", tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()
