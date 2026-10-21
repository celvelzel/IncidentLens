"""Official Codex CLI transport using its existing ChatGPT login.

This is a real remote Codex service invocation, NOT the Platform Chat Completions
API. No OAuth token is extracted or sent to an undocumented endpoint. Each call
uses a fresh ephemeral session, an isolated working directory and disabled tools.
Actual HTTP attempts, subscription credit debits and temperature are unobserved.
"""

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from incident_lens.evaluation.run_io import append_json, atomic_bytes, atomic_json
from incident_lens.llm.provider import LLMProvider, ProviderError, json_payload
from incident_lens.llm.structured_output import strict_schema

REQUIRED_MODEL = "gpt-5.6-luna"

DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "shell_snapshot", "multi_agent", "multi_agent_v2",
    "apps", "plugins", "hooks", "computer_use", "browser_use", "browser_use_external",
    "in_app_browser", "image_generation", "view_image", "sleep_tool", "skill_search",
    "goals", "workspace_dependencies", "code_mode", "code_mode_only", "unbounded_connection_retries",
)


def safe_diagnostic(payload):
    """Bounded redacted local CLI startup diagnostics, never auth cache data."""
    text = payload.decode("utf-8", errors="replace")[:8192]
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", text)
    text = re.sub(r"\b(?:sk-|sess-|ghp_|github_pat_)[A-Za-z0-9_.-]+", "[REDACTED]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_.-]{20,}", "[REDACTED]", text)
    text = re.sub(r"https?://[^\s\"']+", "[URL]", text)
    return text


def account_environment():
    """Keep official cached login/proxy configuration, remove API-key fallbacks."""
    excluded = {
        "OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID",
        "OPENAI_PROJECT_ID", "CODEX_ACCESS_TOKEN", "CODEX_THREAD_ID",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    }
    # Never pass the IncidentLens endpoint credentials into another process.
    return {key: value for key, value in os.environ.items()
            if key not in excluded and not key.startswith("INCIDENT_LENS_")}


def resolve_cli(executable="codex.exe"):
    result = shutil.which(str(executable))
    if result is None:
        raise ProviderError("CODEX_CLI_NOT_INSTALLED")
    path = Path(result).resolve()
    if os.name == "nt" and path.suffix.lower() != ".exe":
        raise ProviderError("CODEX_NATIVE_EXECUTABLE_REQUIRED")
    return str(path)


def inspect_auth(executable):
    """Read only the documented login-status command, never the auth cache."""
    try:
        result = subprocess.run([executable, "login", "status"], env=account_environment(),
                                capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ProviderError("CODEX_AUTH_STATUS_UNAVAILABLE") from None
    text = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    if result.returncode != 0 or "Logged in using ChatGPT" not in text:
        raise ProviderError("CODEX_CHATGPT_LOGIN_REQUIRED")
    return {"auth_method": "chatgpt", "verified_by": "codex login status",
            "account_identity_read": False, "credential_cache_read": False}


def decode_events(payload):
    """Accept only schema output without tool use and a completed turn."""
    events = []
    for line in payload.splitlines():
        if line.strip():
            try:
                event = json.loads(line)
            except (ValueError, RecursionError):
                raise ProviderError("CODEX_EVENT_STREAM_INVALID") from None
            if not isinstance(event, dict):
                raise ProviderError("CODEX_EVENT_STREAM_INVALID")
            events.append(event)
    for event in events:
        if event.get("type", "").startswith("item."):
            kind = event.get("item", {}).get("type")
            if kind not in {"agent_message", "reasoning"}:
                error = ProviderError("CODEX_UNEXPECTED_TOOL_ACTIVITY")
                error.unexpected_item_type = re.sub(r"[^A-Za-z0-9_.-]", "?", str(kind))[:80]
                if kind == "error":
                    error.cli_warning = safe_diagnostic(json.dumps(event.get("item", {})).encode())
                raise error
        if event.get("type") in {"turn.failed", "error"}:
            raise ProviderError("CODEX_REMOTE_TURN_FAILED")
    completed = [event for event in events if event.get("type") == "turn.completed"]
    if len(completed) != 1:
        raise ProviderError("CODEX_TURN_COMPLETION_MISSING")
    # Do not persist reasoning summaries or arbitrary server error text.
    safe = [{"type": event.get("type"), "item_type": event.get("item", {}).get("type")}
            for event in events]
    return completed[0].get("usage", {}), safe


class CodexSubscriptionProvider(LLMProvider):
    transport_kind = "codex_cli"

    def __init__(self, model, artifacts, executable="codex.exe", timeout=180.0,
                 reasoning_effort="low", diagnostic_mode=False):
        if (not isinstance(model, str) or not model or model.startswith("-")
            or type(timeout) not in (float, int) or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("explicit model and positive finite timeout required")
        if model != REQUIRED_MODEL:
            raise ValueError("This experiment is pinned to gpt-5.6-luna; model substitution is forbidden")
        if reasoning_effort not in {"low", "medium", "high", "xhigh", "max", "ultra"}:
            raise ValueError("unsupported reasoning effort")
        self.executable = resolve_cli(executable)
        self.model_id = model
        self.temperature = 0.0  # requested convention only; CLI does not expose temperature
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.diagnostic_mode = diagnostic_mode
        self.artifacts = Path(artifacts)
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.stop_guard = None
        self.request_reconciler = None
        self.model_parameters = {
            "transport": "official_codex_exec", "billing_mode": "chatgpt_codex_subscription",
            "requested_model": model, "model_identity_verified": False,
            "temperature_verified": False, "reasoning_effort": reasoning_effort,
            "fresh_ephemeral_session_per_call": True, "request_timeout_seconds": timeout,
            "tools_requested_disabled": list(DISABLED_FEATURES),
            "tool_event_audit": "reject_non_message_items",
            "os_level_oracle_isolation_verified": False,
            "platform_api_equivalent": False, "underlying_http_attempts": None,
            "automatic_provider_fallback": False,
        }

    async def _terminate(self, process):
        if process.returncode is not None:
            return
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/PID", str(process.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            process.kill()
        await process.wait()

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        call_id = "codex-" + uuid4().hex
        directory = self.artifacts / call_id
        directory.mkdir()
        usage = {"source": "model", "model_id": self.model_id, "llm_calls": 0,
                 "logical_structured_calls": 1, "codex_invocations": 0,
                 "actual_http_requests": 0, "underlying_http_requests": None,
                 "transport_retries": 0, "repair_requests": 0,
                 "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                 "measured_total_tokens": 0, "tokens_complete": False,
                 "token_usage_basis": "codex_turn_report; underlying HTTP accounting unavailable",
                 "billing_mode": "chatgpt_codex_subscription", "cost_usd": None}
        permit = None
        admitted = False
        observed_total = None
        process = None
        communication = None
        started = time.monotonic()
        try:
            if self.stop_guard is not None:
                self.stop_guard()
            auth = await asyncio.to_thread(inspect_auth, self.executable)
            atomic_json(directory / "auth-status.json", auth)
            schema = strict_schema(output_model)
            atomic_json(directory / "output-schema.json", schema)
            # The CLI reads this as its base instructions, rather than inheriting
            # coding instructions or project AGENTS.md. No repository is mounted.
            atomic_bytes(directory / "instructions.txt", system_prompt.encode("utf-8"))
            payload = json.dumps(json_payload(user_payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
            atomic_json(directory / "request.json", {"call_id": call_id, "role": role,
                        "payload_sha256": hashlib.sha256(payload).hexdigest(),
                        "system_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
                        "parameters": self.model_parameters})
            with tempfile.TemporaryDirectory(prefix="incidentlens-codex-") as temporary:
                command = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                           "--skip-git-repo-check", "--sandbox", "read-only", "--json",
                           "--color", "never", "--model", self.model_id,
                           "--output-schema", str((directory / "output-schema.json").resolve()),
                           "--output-last-message", str((directory / "output.json").resolve())]
                overrides = {
                    "model_provider": "openai", "forced_login_method": "chatgpt",
                    "approval_policy": "never", "project_doc_max_bytes": 0,
                    "web_search": "disabled", "model_reasoning_effort": self.reasoning_effort,
                    "hide_agent_reasoning": True, "model_reasoning_summary": "none",
                    "model_instructions_file": str((directory / "instructions.txt").resolve()),
                }
                for key, value in overrides.items():
                    command += ["--config", key + "=" + json.dumps(value)]
                for feature in DISABLED_FEATURES:
                    command += ["--disable", feature]
                command.append("-")
                if self.stop_guard is not None:
                    self.stop_guard()
                permit = self.request_guard() if self.request_guard is not None else None
                admitted = True
                usage.update(llm_calls=1, codex_invocations=1)
                append_json(directory / "lifecycle.jsonl", {"event": "INVOCATION_INTENT",
                            "time_utc": time.time(), "timeout_seconds": self.timeout})
                process = await asyncio.create_subprocess_exec(
                    *command, cwd=temporary, env=account_environment(),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                communication = asyncio.create_task(process.communicate(payload))
                deadline = time.monotonic() + self.timeout
                while not communication.done():
                    if self.stop_guard is not None:
                        self.stop_guard()
                    if time.monotonic() >= deadline:
                        raise ProviderError("CODEX_REQUEST_TIMEOUT", usage)
                    await asyncio.wait({communication}, timeout=0.25)
                stdout, stderr = communication.result()
                # Raw stderr is not retained; synthetic feasibility may opt in
                # to bounded redacted diagnostics through a separate CLI check.
                atomic_json(directory / "process.json", {"exit_code": process.returncode,
                            "stderr_bytes": len(stderr), "stderr_sha256": hashlib.sha256(stderr).hexdigest()})
                if process.returncode != 0:
                    # Do not store arbitrary remote response errors. Startup
                    # errors (no JSON event stream) are local CLI diagnostics.
                    if self.diagnostic_mode:
                        errors = []
                        for line in stdout.splitlines():
                            try:
                                entry = json.loads(line)
                            except ValueError:
                                continue
                            if entry.get("type") in {"error", "turn.failed"}:
                                errors.append(safe_diagnostic(json.dumps(entry).encode()))
                        atomic_json(directory / "startup-diagnostic.json", {
                            "scope": "synthetic probe only", "redacted_text": safe_diagnostic(stderr),
                            "redacted_errors": errors[:5]})
                    unavailable = b"not supported when using Codex with a ChatGPT account"
                    if unavailable in stdout or unavailable in stderr:
                        raise ProviderError("CODEX_MODEL_NOT_AVAILABLE_FOR_CHATGPT", usage)
                    raise ProviderError("CODEX_PROCESS_FAILED", usage)
                reported, safe_events = decode_events(stdout)
                atomic_json(directory / "events.json", safe_events)
                atomic_json(directory / "reported-usage.json", reported)
                input_tokens = reported.get("input_tokens")
                output_tokens = reported.get("output_tokens")
                if all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens)):
                    observed_total = input_tokens + output_tokens
                    usage.update(codex_reported_prompt_tokens=input_tokens,
                                 codex_reported_completion_tokens=output_tokens,
                                 codex_reported_total_tokens=observed_total,
                                 cached_input_tokens=reported.get("cached_input_tokens"))
                    # Keep generic tokens conservative: CLI internal retry and
                    # hidden request coverage cannot be established from one turn.
                    usage.update(measured_prompt_tokens=input_tokens,
                                 measured_completion_tokens=output_tokens,
                                 measured_total_tokens=observed_total)
                    if self.token_observer is not None:
                        self.token_observer(observed_total)
                try:
                    result = output_model.model_validate_json((directory / "output.json").read_bytes())
                except (OSError, ValueError):
                    raise ProviderError("CODEX_STRUCTURED_OUTPUT_INVALID", usage) from None
                return result, usage
        except BaseException as exc:
            if process is not None and process.returncode is None:
                await self._terminate(process)
            if communication is not None and not communication.done():
                await asyncio.gather(communication, return_exceptions=True)
            exc.usage = usage
            # Original provider failures remain classified; no silent API fallback.
            atomic_json(directory / "failure.json", {"error_type": type(exc).__name__,
                        "code": exc.code if isinstance(exc, ProviderError) else "LOCAL_ERROR",
                        "unexpected_item_type": getattr(exc, "unexpected_item_type", None),
                        "cli_warning": getattr(exc, "cli_warning", None) if self.diagnostic_mode else None,
                        "remote_result_may_be_unknown": admitted})
            raise
        finally:
            usage["elapsed_ms"] = (time.monotonic() - started) * 1000
            if admitted and self.request_reconciler is not None:
                self.request_reconciler(permit, observed_total)
            atomic_json(directory / "usage.json", usage)
