"""Replay one development pilot case with identical budgets in a fresh directory."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
from incident_lens.evaluation.run_io import atomic_json
from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm.config import provider_options
from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.observability import RunJournal
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


async def run_case(args):
    project = Path(__file__).resolve().parents[1]
    load_dotenv(project / ".env", override=False)
    protocol = ExperimentProtocol.model_validate_json(args.protocol.read_text(encoding="utf-8-sig"))
    endpoint, key, model = (os.getenv(name) for name in (
        "INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY", "INCIDENT_LENS_MODEL",
    ))
    if not all((endpoint, key, model)) or model != protocol.model_id:
        raise ValueError("matching real provider configuration required")
    if protocol.formal or protocol.provider_id != "real":
        raise ValueError("this replay is for real development pilots only")
    if getattr(args, "readiness", None) is not None:
        readiness = json.loads(args.readiness.read_text(encoding="utf-8-sig"))
        if (readiness.get("model_id") != model
            or readiness.get("response_format") != protocol.response_format
            or readiness.get("provider_compatible") is not True):
            raise ValueError("provider readiness must match model and response format")
    args.out.mkdir(parents=True, exist_ok=False)
    evidence = EvidenceProvider(args.dataset / "rca")
    config_path = getattr(args, "runtime_config", None) or project / "configs/system.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if getattr(args, "readiness", None) is not None and readiness.get("thinking") != config.get("thinking"):
        raise ValueError("provider readiness does not match thinking mode")
    provider = MeasuredProvider(RealChatProvider(
        endpoint, key, model, temperature=protocol.temperature,
        structured_repair_retries=config.get("structured_repair_retries", 1),
        recovery=config.get("provider_recovery", {}),
        **provider_options(protocol.response_format, config.get("thinking"), protocol.request_timeout),
    ))
    frozen_sources = retest_snapshot(project)
    metadata = {
        "scope": "one-case development regression; no aggregate accuracy claim",
        "incident_id": args.incident, "variant": args.variant, "protocol": protocol.model_dump(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=project, text=True,
        ).strip(),
        "source_sha256": {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((project / "src").rglob("*.py"))},
        "retest_source_sha256": frozen_sources,
        "effective_model_parameters": provider.model_parameters,
        "dataset_revision": evidence.dataset_revision,
        "runtime_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "dispatch_policy": "collect-siblings; bounded-provider-retry; public-change-discovery; bounded-diff-fetch",
    }
    (args.out / "scope.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    args.journal = RunJournal(args.out / "observability", metadata)
    investigation_started = time.monotonic()
    state = await run_investigation(
        args.incident, provider, data_root=args.dataset / "rca", variant=args.variant,
        budget=Budget(
            max_rounds=protocol.max_rounds, max_tool_calls=protocol.max_tool_calls,
            max_llm_calls=protocol.max_llm_calls, max_wall_seconds=protocol.max_wall_seconds,
        ),
        workflow=WorkflowOptions(benchmark_rca=True, database_equivalent_tools=True,
                                 benchmark_fixed_four=args.variant == "fixed"),
        journal=args.journal,
    )
    elapsed_ms = (time.monotonic() - investigation_started) * 1000
    save_run(state, args.out, "real", variant=args.variant, elapsed_ms=elapsed_ms)
    raw = state.model_dump(mode="json")
    summary = normalize_termination(raw) | usage_metrics(provider, raw)
    (args.out / "measured-usage.json").write_text(
        json.dumps({"schema_version": 1, "calls": provider.calls,
                    "token_usage_by_role": summary["token_usage_by_role"],
                    "token_usage_basis": summary["token_usage_basis"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["source_drift"] = snapshot_changes(frozen_sources, retest_snapshot(project))
    summary["source_unchanged"] = not summary["source_drift"]
    summary["elapsed_ms"] = elapsed_ms
    summary["observability"] = args.journal.health()
    summary["query_gap_count"] = sum(e.event_type == "TOOL_DATA_GAP" for e in state.events)
    summary["fatal_dispatch"] = any(
        e.event_type == "RUNTIME_ERROR" and e.details.get("stage") == "dispatch"
        for e in state.events
    )
    atomic_json(args.out / "verification.json", summary, exclusive=True)
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
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--incident", default="incident_2001")
    parser.add_argument("--variant", choices=("full", "dynamic_no_verifier", "single", "fixed"),
                        default="full")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--lease-directory", type=Path)
    asyncio.run(run(parser.parse_args()))
