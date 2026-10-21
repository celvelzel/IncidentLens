"""Development bridge: serve calls externally; isolation is unverified.

No remote chat API is used. Each structured_call is serialized to a request file
under ``<out>/_bridge/requests`` and the call blocks until the matching response
file appears under ``<out>/_bridge/responses``. An external servicer (an isolated
agent with its own context) reads the request payload and writes the JSON result,
so the model identity in these results is the bridge, not DeepSeek-V4-Flash.

Harness contracts are preserved so budgets and termination detection stay
meaningful: one request permit per served attempt, the stop guard is honored at
entry and while waiting, unsettled permits are reconciled, cancellation carries
usage, and ``model_parameters`` is exposed for the measured wrapper.
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
from incident_lens.evaluation.run_io import append_json, atomic_bytes, atomic_json
from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm.provider import LLMProvider, ProviderError
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.observability import RunJournal
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider

BRIDGE_MODEL_ID = "trae-subagent-bridge-v1"


def _atomic_write(path, text):
    atomic_bytes(path, text.encode("utf-8"))


def request_digest(request):
    return hashlib.sha256(json.dumps(
        request, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def render_dispatch(request, response_path):
    return (
        "# Development bridge; external isolation is NOT verified by this harness\n"
        "Serve one call in a fresh context with no inherited conversation and no tools\n"
        "except reading this request and writing its response. Follow messages exactly.\n"
        "Do not consult repository files, other requests, results, oracles or web pages.\n"
        "No operator hints or manual response edits are permitted. These restrictions\n"
        "are procedural; this file is not an OS sandbox or proof of compliance.\n"
        "Write a JSON envelope with session_id, request_id, request_sha256 copied from\n"
        "this request and content containing the raw JSON output as a STRING to:\n"
        f"{response_path}\n"
        "Use an atomic file rename; one final response per attempt.\n\n```json\n"
        + json.dumps(request, ensure_ascii=False, indent=2) + "\n```\n"
    )


class FileQueueBridgeProvider(LLMProvider):
    """Development-only queue. Request binding is not external-agent isolation."""

    transport_kind = "file_queue"

    def __init__(self, root, model_id=BRIDGE_MODEL_ID, poll_interval=1.0, call_timeout=180.0,
                 structured_repair_retries=1):
        import math
        from uuid import uuid4

        if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
               for x in (poll_interval, call_timeout)):
            raise ValueError("bridge timing must be positive and finite")
        if type(structured_repair_retries) is not int or structured_repair_retries not in (0, 1):
            raise ValueError("bridge structured repair retries must be zero or one")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.session_id = uuid4().hex
        for name in ("requests", "responses", "dispatch", "receipts"):
            path = self.root / name
            path.mkdir()
            setattr(self, name + "_dir", path)
        self.model_id = model_id
        self.temperature = 0.0  # requested value, not an enforced external setting
        self.poll_interval = poll_interval
        self.call_timeout = call_timeout
        self.structured_repair_retries = structured_repair_retries
        self.log_path = self.root / "call_log.jsonl"
        self._counter = {"n": 0}
        self.stop_guard = None
        self.request_reconciler = None
        self.model_parameters = {
            "requested_temperature": 0.0, "temperature_verified": False,
            "model_id": model_id, "model_identity_verified": False,
            "bridge": "file-queue/development-unverified-servicer",
            "call_timeout_seconds": call_timeout, "session_id": self.session_id,
            "isolation_verified": False,
            "structured_repair_retries": structured_repair_retries,
        }

    def _log(self, **record):
        # Logging failures must be visible: never claim an auditable run without a log.
        append_json(self.log_path, dict(
            timestamp_utc=time.time(), monotonic_seconds=time.monotonic(),
            session_id=self.session_id, **record,
        ))

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        from incident_lens.llm.structured_output import output_messages, strict_schema

        self._counter["n"] += 1
        base_id = f"req-{self._counter['n']:04d}"
        schema = strict_schema(output_model)
        messages = output_messages(system_prompt, user_payload, schema)
        usage = dict(
            source="model", model_id=self.model_id, llm_calls=0,
            actual_http_requests=0, bridge_requests=0, logical_structured_calls=1,
            transport_retries=0, repair_requests=0, prompt_tokens=None,
            completion_tokens=None, total_tokens=None, measured_total_tokens=0,
            tokens_complete=False,
        )
        started = time.monotonic()
        try:
            for attempt in range(self.structured_repair_retries + 1):
                if self.stop_guard is not None:
                    self.stop_guard()
                request_id = base_id if attempt == 0 else base_id + "-repair"
                request = dict(
                    session_id=self.session_id, request_id=request_id, role=role,
                    schema_name=output_model.__name__, messages=list(messages),
                    json_schema=schema, requested_temperature=self.temperature,
                )
                request["request_sha256"] = request_digest(request)
                permit = self.request_guard() if self.request_guard is not None else None
                try:
                    usage["llm_calls"] += 1
                    usage["bridge_requests"] += 1
                    usage["repair_requests"] = attempt
                    _atomic_write(self.requests_dir / f"{request_id}.json",
                                  json.dumps(request, ensure_ascii=False))
                    _atomic_write(self.dispatch_dir / f"{request_id}.md", render_dispatch(
                        request, self.responses_dir / f"{request_id}.json",
                    ))
                    self._log(event="REQUEST_WRITTEN", request_id=request_id,
                              timeout_seconds=self.call_timeout,
                              request_sha256=request["request_sha256"], role=role, attempt=attempt)
                    content = await self._await_response(request, usage)
                finally:
                    if self.request_reconciler is not None:
                        self.request_reconciler(permit, None)
                try:
                    result = output_model.model_validate_json(content)
                except ValueError:
                    self._log(event="RESPONSE_INVALID", request_id=request_id)
                    if attempt < self.structured_repair_retries:
                        # Match the legacy real adapter's repair prompt and placement.
                        messages.append({"role": "user", "content":
                            "Return valid JSON matching the supplied schema. One repair only."})
                        continue
                    raise ProviderError("STRUCTURED_OUTPUT_INVALID", usage) from None
                self._log(event="RESPONSE_ACCEPTED", request_id=request_id)
                return result, usage
        except BaseException as exc:
            exc.usage = usage
            raise
        finally:
            usage["elapsed_ms"] = (time.monotonic() - started) * 1000

    async def _await_response(self, request, usage):
        request_id = request["request_id"]
        path = self.responses_dir / f"{request_id}.json"
        deadline = time.monotonic() + self.call_timeout
        next_status = 0.0
        try:
            while True:
                if self.stop_guard is not None:
                    self.stop_guard()
                if time.monotonic() >= deadline:
                    self._log(event="RESPONSE_TIMEOUT", request_id=request_id,
                              timeout_seconds=self.call_timeout)
                    raise ProviderError("BRIDGE_TIMEOUT", usage)
                if time.monotonic() >= next_status:
                    self._log(event="RESPONSE_WAIT", request_id=request_id,
                              remaining_seconds=max(0, deadline - time.monotonic()),
                              request_bytes=(self.requests_dir / f"{request_id}.json").stat().st_size)
                    next_status = time.monotonic() + 30
                if path.exists():
                    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                        raise ProviderError("BRIDGE_RESPONSE_MISMATCH", usage)
                    try:
                        raw = path.read_bytes()
                    except PermissionError:
                        # A scanner may briefly hold the atomic published file.
                        # Preserve the deadline; never silently extend it.
                        await asyncio.sleep(self.poll_interval)
                        continue
                    # A malformed final file fails immediately; no silent editing window.
                    try:
                        envelope = json.loads(raw)
                        if (not isinstance(envelope, dict)
                            or set(envelope) != {"session_id", "request_id", "request_sha256", "content"}
                            or any(envelope[k] != request[k] for k in
                                   ("session_id", "request_id", "request_sha256"))
                            or not isinstance(envelope["content"], str)):
                            raise ValueError("response binding failed")
                    except (ValueError, KeyError, TypeError):
                        raise ProviderError("BRIDGE_RESPONSE_MISMATCH", usage) from None
                    receipt = dict(
                        request=request, response=envelope,
                        response_sha256=hashlib.sha256(raw).hexdigest(),
                        received_at_utc=time.time(), isolation_verified=False,
                    )
                    _atomic_write(self.receipts_dir / f"{request_id}.json",
                                  json.dumps(receipt, ensure_ascii=False))
                    self._log(event="RESPONSE_READ", request_id=request_id,
                              response_sha256=receipt["response_sha256"])
                    return envelope["content"]
                await asyncio.sleep(self.poll_interval)
        except BaseException:
            self._log(event="REQUEST_CLOSED", request_id=request_id)
            raise


async def run_case(args):
    project = Path(__file__).resolve().parents[1]
    load_dotenv(project / ".env", override=False)
    protocol = ExperimentProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8-sig")
    )
    if (protocol.formal or protocol.provider_id != "real"
        or protocol.model_id != BRIDGE_MODEL_ID
        or protocol.blindness_level != "development_visible"):

        raise ValueError("bridge replay is for development pilots only")
    call_timeout = protocol.request_timeout if args.call_timeout is None else args.call_timeout
    if call_timeout != protocol.request_timeout:
        raise ValueError("bridge call timeout must match protocol.request_timeout")
    import yaml

    config_path = getattr(args, "runtime_config", None)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path else {}
    poll_interval = args.poll_interval if args.poll_interval is not None else config.get("poll_interval", 1.0)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    bridge = FileQueueBridgeProvider(
        out / "_bridge", poll_interval=poll_interval, call_timeout=call_timeout,
        structured_repair_retries=config.get("structured_repair_retries", 1),
    )
    provider = MeasuredProvider(bridge)
    evidence = EvidenceProvider(args.dataset / "rca")
    frozen_sources = retest_snapshot(project)
    metadata = {
        "scope": "one-case development bridge; external isolation unverified",
        "incident_id": args.incident,
        "variant": args.variant,
        "protocol": protocol.model_dump(),
        "bridge": {
            "kind": "file-queue/isolated-agent-servicer",
            "request_dir": str(out / "_bridge" / "requests"),
            "response_dir": str(out / "_bridge" / "responses"),
            "dispatch_dir": str(out / "_bridge" / "dispatch"),
            "dispatch_mode": "request-bound-envelope-v2",
            "isolation_verified": False,
            "model_identity_verified": False,
            "effective_call_timeout": bridge.call_timeout,
            "reported_model_id": bridge.model_id,
            "declared_protocol_model_id": protocol.model_id,
            "note": (
                "Development only. No remote chat HTTP is called. Fresh-context/tool "
                "restrictions are procedural and require external session/tool transcripts "
                "to audit; the queue provides no OS sandbox or proof of no contamination. "
                "Model, temperature and token use are unverified. No blind-test claim."
            ),
        },
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=project, text=True
        ).strip(),
        "source_sha256": {
            str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((project / "src").rglob("*.py"))
        },
        "retest_source_sha256": frozen_sources,
        "effective_model_parameters": provider.model_parameters,
        "dataset_revision": evidence.dataset_revision,
        "runtime_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest() if config_path else None,
    }
    atomic_json(out / "scope.json", metadata, exclusive=True)
    args.journal = RunJournal(out / "observability", metadata)
    investigation_started = time.monotonic()
    state = await run_investigation(
        args.incident,
        provider,
        data_root=args.dataset / "rca",
        variant=args.variant,
        budget=Budget(
            max_rounds=protocol.max_rounds,
            max_tool_calls=protocol.max_tool_calls,
            max_llm_calls=protocol.max_llm_calls,
            max_wall_seconds=protocol.max_wall_seconds,
        ),
        workflow=WorkflowOptions(
            benchmark_rca=True,
            database_equivalent_tools=True,
            benchmark_fixed_four=args.variant == "fixed",
        ),
        journal=args.journal,
    )
    elapsed_ms = (time.monotonic() - investigation_started) * 1000
    save_run(state, out, "real", variant=args.variant, elapsed_ms=elapsed_ms)
    raw = state.model_dump(mode="json")
    summary = normalize_termination(raw) | usage_metrics(provider, raw)
    summary["source_drift"] = snapshot_changes(frozen_sources, retest_snapshot(project))
    summary["source_unchanged"] = not summary["source_drift"]
    summary["query_gap_count"] = sum(e.event_type == "TOOL_DATA_GAP" for e in state.events)
    summary["fatal_dispatch"] = any(
        e.event_type == "RUNTIME_ERROR" and e.details.get("stage") == "dispatch"
        for e in state.events
    )
    summary["bridge_model_id"] = bridge.model_id
    summary["bridge_requests"] = sum(c["usage"].get("bridge_requests", 0) for c in provider.calls)
    summary["isolation_verified"] = False
    summary["elapsed_ms"] = elapsed_ms
    summary["observability"] = args.journal.health()
    atomic_json(out / "measured-usage.json", {"schema_version": 1, "calls": provider.calls})
    atomic_json(out / "verification.json", summary, exclusive=True)
    print(json.dumps(summary))


async def run_unlocked(args):
    error = None
    try:
        await run_case(args)
    except BaseException as exc:
        error = exc
        raise
    finally:
        if getattr(args, "journal", None) is not None:
            args.journal.close(error)
            verification = args.out / "verification.json"
            if verification.is_file():
                summary = json.loads(verification.read_bytes())
                summary["observability"] = args.journal.health()
                atomic_json(verification, summary)


async def run(args):
    from incident_lens.incidentbench.experiment import execution_lock

    lease = getattr(args, "lease_directory", None)
    if lease is None:
        return await run_unlocked(args)
    with execution_lock(lease):
        return await run_unlocked(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--incident", default="incident_2001")
    parser.add_argument(
        "--variant",
        choices=("full", "dynamic_no_verifier", "single", "fixed"),
        default="full",
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--lease-directory", type=Path)
    parser.add_argument("--poll-interval", dest="poll_interval", type=float, default=None)
    parser.add_argument("--call-timeout", dest="call_timeout", type=float, default=None)
    asyncio.run(run(parser.parse_args()))
