"""Replay one development pilot case with identical budgets in a fresh directory."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml
from dotenv import load_dotenv

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
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
    args.out.mkdir(parents=True, exist_ok=False)
    evidence = EvidenceProvider(args.dataset / "rca")
    config = yaml.safe_load((project / "configs/system.yaml").read_text(encoding="utf-8"))
    provider = MeasuredProvider(RealChatProvider(
        endpoint, key, model, temperature=protocol.temperature,
        structured_repair_retries=config.get("structured_repair_retries", 1),
        recovery=config.get("provider_recovery", {}),
        **provider_options(protocol.response_format, None, protocol.request_timeout),
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
        "dispatch_policy": "collect-siblings; bounded-provider-retry; public-change-discovery; bounded-diff-fetch",
    }
    (args.out / "scope.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    args.journal = RunJournal(args.out / "observability", metadata)
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
    save_run(state, args.out, "real", variant=args.variant)
    raw = state.model_dump(mode="json")
    summary = normalize_termination(raw) | usage_metrics(provider, raw)
    summary["source_drift"] = snapshot_changes(frozen_sources, retest_snapshot(project))
    summary["source_unchanged"] = not summary["source_drift"]
    summary["observability"] = args.journal.health()
    summary["query_gap_count"] = sum(e.event_type == "TOOL_DATA_GAP" for e in state.events)
    summary["fatal_dispatch"] = any(
        e.event_type == "RUNTIME_ERROR" and e.details.get("stage") == "dispatch"
        for e in state.events
    )
    (args.out / "verification.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary))


async def run(args):
    error = None
    try:
        await run_case(args)
    except BaseException as exc:
        error = exc
        raise
    finally:
        if getattr(args, "journal", None) is not None:
            args.journal.close(error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--incident", default="incident_2001")
    parser.add_argument("--variant", choices=("full", "dynamic_no_verifier", "single", "fixed"),
                        default="full")
    parser.add_argument("--out", required=True, type=Path)
    asyncio.run(run(parser.parse_args()))
