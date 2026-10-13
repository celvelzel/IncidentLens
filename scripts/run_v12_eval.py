"""Cache-off paired V1.2 evaluation, with unchanged four legacy schedules."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from incident_lens.agents.monitoring import validate_alert
from incident_lens.agents.remediation import validate_plan
from incident_lens.agents.service import PROMPT_VERSION
from incident_lens.evaluation.metrics import (
    VARIANTS,
    aggregate,
    score_completed,
    score_without_oracle,
)
from incident_lens.evaluation.runner import (
    MeasuredProvider,
    digest,
    load_oracle_after_run,
    load_split,
    usage_metrics,
    write_csv,
)
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.llm import MockProvider, ProviderError, RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


class TransientFailureMock(MockProvider):
    """One charged first-attempt analysis failure per independent evaluation run."""

    def __init__(self):
        # Per-call provider copies must share the single per-run injection flag.
        self._injection = {"injected": False}

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        result, usage = await super().structured_call(
            role, system_prompt, user_payload, output_model
        )
        if (
            role == "logs"
            and output_model.__name__ == "AnalysisOutput"
            and not self._injection["injected"]
        ):
            self._injection["injected"] = True
            raise ProviderError("INJECTED_TRANSIENT_ANALYSIS_FAILURE", usage)
        return result, usage


def workflow_metrics(completed, snapshot=()):
    """Assess contract validity separately from diagnosis correctness and semantic quality."""
    state = completed.model_dump(mode="json")
    report = completed.report
    plan_valid = None
    if report.remediation_plan is not None:
        try:
            validate_plan(report.remediation_plan, report, completed.evidence_index)
            plan_valid = report.status == "RESOLVED"
        except (ProviderError, ValueError):
            plan_valid = False
    events = completed.events
    terminal = normalize_termination(state)
    stop_valid = terminal["protocol_valid"]
    records = completed.task_records
    stop_completion = terminal["stop_completion"]
    retries = [r for r in records if r.attempt > 1]
    recovered_tasks = {r.task_id for r in retries if r.status == "COMPLETED"}
    failed_tasks = {r.task_id for r in records if r.status == "FAILED"}
    alert_valid = None
    if completed.incident_alert is not None:
        try:
            validate_alert(completed.incident_alert, completed.incident_id, snapshot)
            alert_valid = True
        except (ProviderError, ValueError):
            alert_valid = False
    return {
        "monitoring_alert": completed.incident_alert.status if completed.incident_alert else None,
        "monitoring_contract_valid": alert_valid,
        "monitoring_accuracy": None,
        "remediation_status": report.remediation_status,
        "remediation_contract_valid": plan_valid,
        "stop_contract_valid": stop_valid,
        "stop_completion": stop_completion,
        "stop_timeout_count": sum(e.event_type == "STOP_TIMEOUT" for e in events),
        "stop_ack_count": sum(e.event_type == "STOP_ACK" for e in events),
        "failed_task_count": len(failed_tasks),
        "retried_attempt_count": len(retries),
        "recovered_task_count": len(recovered_tasks),
        "task_recovery_rate": len(recovered_tasks) / len(failed_tasks) if failed_tasks else None,
        "diagnosis_status": report.diagnosis_status or report.status,
        "workflow_status": report.workflow_status,
        "serialized_state": state,
    }


async def evaluate(args, factory):
    data_root, out = args.data_root, args.out
    public = EvidenceProvider(data_root)
    revision = public.dataset_revision
    package_root = Path(__file__).resolve().parents[1] / "src" / "incident_lens"
    source_sha256 = digest(
        {
            str(p.relative_to(package_root)): digest(p.read_text(encoding="utf-8"))
            for p in sorted(package_root.rglob("*.py"))
        }
    )
    ids = args.incidents or load_split(data_root, args.split)
    if len(ids) != len(set(ids)):
        raise ValueError("incident IDs must be unique")
    budget = Budget(
        max_rounds=args.max_rounds,
        max_tool_calls=args.max_tool_calls,
        max_llm_calls=args.max_llm_calls,
        max_wall_seconds=args.max_wall_seconds,
    )
    modes = [("v12_database_enabled", "full", True), ("v12_database_disabled", "full", False)]
    if not args.skip_legacy:
        modes += [("legacy_" + variant, variant, None) for variant in VARIANTS]
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    # Reset this run's output before incrementally appending completed runs.
    (out / "raw-runs.jsonl").write_text("", encoding="utf-8")
    for incident_id in ids:
        initial = public.load_case(incident_id).model_dump(mode="json")
        snapshot = public._records(incident_id, "metrics") + public._records(incident_id, "logs")
        for label, variant, enabled in modes:
            delegate = factory()
            provider = MeasuredProvider(delegate)
            if (args.provider == "mock") != (provider.source == "mock"):
                raise ValueError("requested provider does not match actual provider")
            workflow = (
                WorkflowOptions()
                if enabled is None
                else WorkflowOptions(
                    profile="incident_response",
                    monitor_mode="manual_snapshot",
                    snapshot=snapshot,
                    database_enabled=enabled,
                    database_equivalent_tools=True,
                )
            )
            config = {
                "scenario": "transient_failure" if args.inject_transient_failure else "normal",
                "provider": args.provider,
                "source": provider.source,
                "model_id": provider.model_id,
                "temperature": provider.temperature,
                "model_parameters": provider.model_parameters,
                "prompt_version": PROMPT_VERSION,
                "schema_version": "v1.2",
                "source_sha256": source_sha256,
                "budget": budget.model_dump(mode="json"),
                "cache_mode": "off",
                "dataset_revision": revision,
                "communication_mode": "centralized",
                "database_tools_available_to_metrics": enabled is not None,
                "workflow": workflow.model_dump(mode="json", exclude={"snapshot"}),
            }
            started = time.monotonic()
            execution_error = evaluation_error = None
            try:
                completed = await run_investigation(
                    incident_id,
                    provider,
                    data_root=data_root,
                    budget=budget.model_copy(deep=True),
                    variant=variant,
                    cache=None,
                    workflow=workflow,
                )
                extra = workflow_metrics(completed, snapshot)
                state = extra.pop("serialized_state")
            except Exception as exc:
                execution_error = type(exc).__name__
                state = {
                    "incident_id": incident_id,
                    "events": [],
                    "evidence_index": {},
                    "report": {
                        "status": "ERROR",
                        "root_cause": None,
                        "stop_reason": execution_error,
                    },
                }
                extra = {
                    "stop_contract_valid": False,
                    "stop_completion": False,
                    "monitoring_accuracy": None,
                }
            elapsed = (time.monotonic() - started) * 1000
            if public.dataset_revision != revision:
                raise ValueError("public dataset changed during evaluation")
            # Oracle is read only after graph execution has returned a completed report.
            oracle_split = oracle = None
            try:
                oracle = load_oracle_after_run(data_root, incident_id, state)
                oracle_split = oracle.get("split")
                scores = score_completed(state, oracle)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                evaluation_error = type(exc).__name__
                scores = score_without_oracle(state)
            row = {
                "incident_id": incident_id,
                "variant": label,
                "split": "explicit_incidents" if args.incidents else args.split,
                "oracle_split": oracle_split,
                "scenario": config["scenario"],
                "provider": args.provider,
                "source": provider.source,
                "model_id": provider.model_id,
                "cache_mode": "off",
                "config_sha256": digest(config),
                "initial_public_sha256": digest(initial),
                "dataset_revision": revision,
                "status": state["report"]["status"],
                "latency_ms": elapsed,
                "tool_calls": state.get("tool_calls_used"),
                "execution_error": execution_error,
                "evaluation_error": evaluation_error,
                **extra,
                **scores,
                **usage_metrics(provider, state),
            }
            rows.append(row)
            with (out / "raw-runs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "metrics": row,
                            "fairness": config,
                            "state": state,
                            "oracle_scoring_fields": oracle,
                            "measured_calls": provider.calls,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            write_csv(out / "case-level.csv", rows)
    totals = []
    for label, _, _ in modes:
        group = [r for r in rows if r["variant"] == label]
        normalized = [dict(r, variant="full") for r in group]
        summary = aggregate(normalized)[0]
        summary["variant"] = label
        for field in (
            "remediation_contract_valid",
            "stop_contract_valid",
            "task_recovery_rate",
            "diagnosis_match",
            "stop_completion",
        ):
            values = [r[field] for r in group if r.get(field) is not None]
            summary[field] = sum(values) / len(values) if values else None
            summary[field + "_denominator"] = len(values)
        summary["stop_completion_rate"] = summary["stop_completion"]
        summary["monitoring_accuracy"] = summary["monitoring_accuracy_rate"]
        totals.append(summary)
    write_csv(out / "aggregate.csv", totals)
    (out / "README.md").write_text(
        "# V1.2 paired evaluation\n\n"
        f"Actual provider: {args.provider}; cache disabled; source: {provider.source}.\n\n"
        "Enabled and disabled specialist arms share database tool availability for metrics, "
        "public input, provider parameters and global budgets. Four legacy schedules use their "
        "original profile. Full raw traces are retained. Private truth is evaluator-only.\n\n"
        "Mock results are deterministic smoke evidence, not real-model effectiveness evidence. "
        "Citation validity measures observed reference existence. Unsupported semantic claims "
        "remain unreviewed; no unsupported-claim score or cost is invented. Remediation validity "
        "checks identity, diagnosis version, accepted citations and PLAN_ONLY contracts, "
        "not operational effectiveness. Recovery is measured only when failures actually occur.\n\n"
        "diagnosis_match compares an accepted resolved cause with evaluator-only truth independently "
        "of final execution quality. Scoring version 2 credits accepted diagnoses after explicit "
        "recovery; remediation and stop failures are scored separately. Transient-failure scenarios "
        "inject one charged mock logs analysis "
        "failure per run; scenario is recorded in raw fairness data and case-level rows.\n",
        encoding="utf-8",
    )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--split", choices=("seed", "dev", "test"), default="seed")
    parser.add_argument("--incidents", nargs="+")
    parser.add_argument("--provider", choices=("mock", "real"), default="mock")
    parser.add_argument("--skip-legacy", action="store_true")
    parser.add_argument(
        "--inject-transient-failure",
        action="store_true",
        help="Mock-only charged analysis failure to measure actual retry recovery",
    )
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--max-tool-calls", type=int, default=24)
    parser.add_argument("--max-llm-calls", type=int, default=32)
    parser.add_argument("--max-wall-seconds", type=float, default=600)
    args = parser.parse_args(argv)
    try:
        if args.inject_transient_failure and args.provider != "mock":
            raise ValueError("failure injection is mock-only")
        if args.provider == "real":
            load_dotenv()
            from incident_lens.llm.config import provider_options

            config = provider_options()
            endpoint = os.getenv("INCIDENT_LENS_BASE_URL", "")
            key = os.getenv("INCIDENT_LENS_API_KEY", "")
            model = os.getenv("INCIDENT_LENS_MODEL", "")
            RealChatProvider(endpoint, key, model, **config)

            def factory():
                return RealChatProvider(endpoint, key, model, temperature=0, **config)
        else:
            factory = TransientFailureMock if args.inject_transient_failure else MockProvider
        rows = asyncio.run(evaluate(args, factory))
    except (ProviderError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"error": exc.code if isinstance(exc, ProviderError) else type(exc).__name__}
            )
        )
        return 2
    print(json.dumps({"provider": args.provider, "runs": len(rows), "cache_mode": "off"}))
    return int(any(r["execution_error"] or r["evaluation_error"] for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
