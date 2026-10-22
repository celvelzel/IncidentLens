"""Explicit development-case worker, also dispatched by the subscription batch.

Uses official Codex subscription transport. It is distinct from Platform API and
file-queue bridge runs. This entry point has not been exercised on an incident.
"""

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
from incident_lens.evaluation.run_io import atomic_json
from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.incidentbench.experiment import execution_lock
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm.codex_subscription import CodexSubscriptionProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.observability import RunJournal
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


async def run(args):
    if not args.execute_development_case:
        raise ValueError("No investigation started: explicitly pass --execute-development-case later")
    config = json.loads(args.config.read_bytes())
    protocol = ExperimentProtocol.model_validate_json(args.protocol.read_bytes())
    if (protocol.formal or protocol.provider_id != "real"
        or protocol.blindness_level != "development_visible" or protocol.model_id != config["model"]):
        raise ValueError("matching development subscription protocol required")
    receipt = json.loads(args.feasibility.read_bytes())
    if (receipt.get("status") != "FEASIBLE_FOR_CODEX_SUBSCRIPTION_TRANSPORT"
        or not receipt.get("probes")
        or any(p.get("matched") is not True or p.get("usage", {}).get("model_id") != config["model"]
               for p in receipt["probes"])):
        raise ValueError("matching successful synthetic feasibility receipt required")
    public = args.dataset / "rca"
    if any(path.name == "private" for path in public.rglob("*")):
        raise ValueError("runtime dataset must contain public observations only")
    project = Path(__file__).resolve().parents[1]
    before = retest_snapshot(project)
    args.out.mkdir(parents=True, exist_ok=False)
    journal = None
    error = None
    try:
        delegate = CodexSubscriptionProvider(config["model"], args.out / "codex-calls",
                                             executable=config["executable"],
                                             timeout=protocol.request_timeout,
                                             reasoning_effort=config["reasoning_effort"])
        provider = MeasuredProvider(delegate)
        metadata = {
            "scope": "remote_codex_subscription_development; not Platform API or blind-test evidence",
            "incident_id": args.incident, "variant": args.variant,
            "protocol": protocol.model_dump(mode="json"),
            "effective_model_parameters": delegate.model_parameters,
            "source_sha256": before,
            "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
            "feasibility_sha256": hashlib.sha256(args.feasibility.read_bytes()).hexdigest(),
            "dataset_revision": EvidenceProvider(public).dataset_revision,
        }
        atomic_json(args.out / "scope.json", metadata, exclusive=True)
        journal = RunJournal(args.out / "observability", metadata)
        started = time.monotonic()
        state = await run_investigation(
            args.incident, provider, data_root=public, variant=args.variant,
            budget=Budget(max_rounds=protocol.max_rounds, max_tool_calls=protocol.max_tool_calls,
                          max_llm_calls=protocol.max_llm_calls, max_wall_seconds=protocol.max_wall_seconds),
            workflow=WorkflowOptions(benchmark_rca=True, database_equivalent_tools=True,
                                     benchmark_fixed_four=args.variant == "fixed"), journal=journal,
        )
        elapsed = (time.monotonic() - started) * 1000
        save_run(state, args.out, "real", variant=args.variant, elapsed_ms=elapsed)
        raw = state.model_dump(mode="json")
        summary = normalize_termination(raw) | usage_metrics(provider, raw)
        changes = snapshot_changes(before, retest_snapshot(project))
        summary.update(source_drift=changes, source_unchanged=not changes, elapsed_ms=elapsed,
                       transport="official_codex_exec", billing_mode="chatgpt_codex_subscription",
                       underlying_http_requests=None, platform_api_verified=False,
                       temperature_verified=False, g1a_acceptance_claim=False,
                       codex_invocations=sum(c["usage"].get("codex_invocations", 0) for c in provider.calls))
        atomic_json(args.out / "measured-usage.json", {"calls": provider.calls})
        atomic_json(args.out / "verification.json", summary, exclusive=True)
    except BaseException as exc:
        error = exc
        raise
    finally:
        if journal is not None:
            journal.close(error)
            path = args.out / "verification.json"
            if path.is_file():
                summary = json.loads(path.read_bytes())
                summary["observability"] = journal.health()
                atomic_json(path, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/wp_d/codex-subscription.json"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--feasibility", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--incident", required=True)
    parser.add_argument("--variant", choices=("single", "fixed", "dynamic_no_verifier", "full"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lease-directory", type=Path)
    parser.add_argument("--execute-development-case", action="store_true")
    args = parser.parse_args()
    lease = args.lease_directory or args.out.parent / (args.out.name + ".lease")
    lease.mkdir(parents=True, exist_ok=True)
    with execution_lock(lease):
        asyncio.run(run(args))
