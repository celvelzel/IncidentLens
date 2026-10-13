"""Sequential, locked, failure-preserving execution of the existing Graph."""

import asyncio
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics, write_csv
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions

from .schemas import BenchmarkCaseMetadata, ExperimentProtocol
from .scorer import aggregate, score_benchmark_run


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def durable_write(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def append(path, value):
    with Path(path).open("ab") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_order(cases, protocol):
    order = [
        (case, repeat, variant)
        for case in cases
        for repeat in range(protocol.repeats)
        for variant in protocol.variants
    ]
    random.Random(protocol.run_order_seed).shuffle(order)
    return order


def dataset_paths(dataset):
    dataset = Path(dataset).resolve(strict=True)
    return (dataset.parent, dataset) if dataset.name == "rca" else (dataset, dataset / "rca")


def load_cases(dataset, split):
    if split not in {"seed", "dev", "test"}:
        raise ValueError("unknown split")
    root, public = dataset_paths(dataset)
    index = json.loads((root / "public_case_index.json").read_text(encoding="utf-8"))
    if isinstance(index, dict):
        index = index.get("cases", index.get("items", []))
    cases = [BenchmarkCaseMetadata.model_validate(c) for c in index]
    ids = json.loads((public / "splits" / f"{split}_ids.json").read_text(encoding="utf-8"))
    selected = [c for c in cases if c.incident_id in ids]
    if (
        len(set(ids)) != len(ids)
        or set(ids) != {c.incident_id for c in selected}
        or len(selected) != len(ids)
    ):
        raise ValueError("split/index mismatch or duplicate cases")
    if any(c.split != split for c in selected):
        raise ValueError("split metadata mismatch")
    return root, public, sorted(selected, key=lambda c: c.incident_id)


async def run_experiment(
    dataset, split, provider_factory, out, protocol, oracle_root=None, *, protocol_lock=None
):
    """Development Test is always unscored. Formal runs require external sealing."""
    from .manifest import create_lock, verify_lock
    from .oracle_store import OracleStore

    protocol = (
        protocol
        if isinstance(protocol, ExperimentProtocol)
        else ExperimentProtocol.model_validate(protocol)
    )
    root, public, cases = load_cases(dataset, split)
    from .validator import validate_dataset

    audit = validate_dataset(root)
    if not audit["ok"]:
        raise ValueError("public benchmark audit failed")
    if not cases:
        raise ValueError("empty split")
    if protocol.formal:
        # No human label acceptance exists in this delivery. Fail closed rather than
        # allowing an arbitrary caller-provided lock to assert formal readiness.
        raise ValueError(
            "formal experiment requires independently accepted labels and verified sealing; pending"
        )
    lock = create_lock(root, protocol)
    if protocol_lock is not None:
        verify_lock(protocol_lock, root, protocol)
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    (out / "states").mkdir()
    durable_write(out / "protocol.lock.json", lock)
    durable_write(out / "manifest-lock.json", lock)
    durable_write(out / "experiment-context.json", {"dataset_root": str(root), "split": split})
    durable_write(out / "protocol.json", protocol.model_dump(mode="json"))
    order = run_order([c.incident_id for c in cases], protocol)
    durable_write(out / "run-order.json", order)
    metadata = {c.incident_id: c for c in cases}
    rows, used_providers, frozen_parameters, review_states = [], [], None, []
    for position, (incident, repeat, variant) in enumerate(order):
        try:
            verify_lock(lock, root, protocol)
        except ValueError:
            append(
                out / "errors.jsonl",
                {"status": "ABORTED", "code": "PROTOCOL_MISMATCH", "position": position},
            )
            raise
        key = f"{incident}.{variant}.repeat-{repeat}"
        run_id = "bench-" + hashlib.sha256(key.encode()).hexdigest()[:24]
        append(out / "progress.jsonl", dict(run_key=key, run_id=run_id, status="STARTED"))
        started = time.monotonic()
        measured = None
        cancelled = False
        try:
            provider = provider_factory()
            if any(provider is p for p in used_providers):
                raise ValueError("provider_factory must return a fresh provider")
            used_providers.append(provider)
            measured = MeasuredProvider(provider)
            expected_source = "mock" if protocol.provider_id == "mock" else "model"
            if (
                measured.source != expected_source
                or provider.model_id != protocol.model_id
                or provider.temperature != protocol.temperature
            ):
                raise ValueError("provider/model/temperature protocol mismatch")
            current_parameters = canonical(measured.model_parameters)
            if frozen_parameters is None:
                durable_write(out / "provider-parameters.json", measured.model_parameters)
                frozen_parameters = current_parameters
            elif current_parameters != frozen_parameters:
                raise ValueError("provider recovery/config drift")
            budget = Budget(
                max_rounds=protocol.max_rounds,
                max_tool_calls=protocol.max_tool_calls,
                max_llm_calls=protocol.max_llm_calls,
                max_wall_seconds=protocol.max_wall_seconds,
            )
            workflow = WorkflowOptions(
                database_equivalent_tools=True,
                benchmark_rca=True,
                benchmark_fixed_four=variant == "fixed_four_equivalent_tools",
            )
            state = await run_investigation(
                incident,
                measured,
                data_root=public,
                budget=budget,
                variant={
                    "strong_single_equivalent_tools": "single",
                    "fixed_four_equivalent_tools": "fixed",
                }.get(variant, variant),
                workspace_id="incidentbench",
                run_id=run_id,
                cache=None,
                workflow=workflow,
            )
            if hasattr(state, "model_dump"):
                state = state.model_dump(mode="json")
            if state.get("incident_id") != incident or state.get("run_id") != run_id:
                raise ValueError("Graph returned foreign run")
        except (Exception, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            state = dict(
                incident_id=incident,
                run_id=run_id,
                report=dict(
                    incident_id=incident,
                    run_id=run_id,
                    status="ERROR",
                    stop_reason="UNRECOVERABLE_ERROR",
                    workflow_status="FAILED",
                ),
                events=[],
                evidence_index={},
                workflow_status="FAILED",
                stop_reason="UNRECOVERABLE_ERROR",
                execution_error={"code": getattr(exc, "code", type(exc).__name__)},
            )
        drift = False
        try:
            verify_lock(lock, root, protocol)
        except ValueError:
            drift = True
            state["execution_error"] = {"code": "PROTOCOL_MISMATCH"}
        latency = (time.monotonic() - started) * 1000
        path = out / "states" / f"{key}.json"
        durable_write(path, state)
        # Append the raw state before loading an oracle. Receipt is bound to exact
        # saved bytes and run identities, and is never supplied to the Graph.
        receipt = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        state_with_receipt = dict(state, completion_receipt=receipt)
        usage = (
            usage_metrics(measured, state)
            if measured
            else dict(actual_http_requests=0, total_tokens=None)
        )
        raw = dict(
            run_key=key,
            incident_id=incident,
            run_id=run_id,
            variant=variant,
            repeat_id=repeat,
            metadata=metadata[incident].model_dump(mode="json"),
            source="mock" if protocol.provider_id == "mock" else "model",
            latency_ms=latency,
            usage=usage,
            state=state_with_receipt,
        )
        append(out / "raw-runs.jsonl", raw)
        review_states.append(state)
        append(
            out / "progress.jsonl",
            dict(run_key=key, run_id=run_id, status="DURABLE", receipt=receipt),
        )
        oracle, score_error = None, None
        if (
            oracle_root is not None
            and split != "test"
            and state.get("report") is not None
            and not drift
        ):
            try:
                oracle = OracleStore(oracle_root, public_root=root).load_after_completion(
                    incident, state_with_receipt
                )
            except Exception as exc:
                score_error = getattr(exc, "code", type(exc).__name__)
        row = dict(
            run_key=key,
            incident_id=incident,
            run_id=run_id,
            variant=variant,
            repeat_id=repeat,
            scenario_family_id=metadata[incident].scenario_family_id,
            source_blueprint_id=metadata[incident].source_blueprint_id,
            near_duplicate_cluster_id=metadata[incident].near_duplicate_cluster_id,
            counterfactual_pair_id=metadata[incident].counterfactual_pair_id,
            independence_status="unreviewed",
            cohort=metadata[incident].cohort,
            source=raw["source"],
            latency_ms=latency,
            **usage,
            **score_benchmark_run(state, oracle),
        )
        row["score_error"] = score_error
        if state.get("execution_error") or score_error:
            append(
                out / "errors.jsonl",
                dict(
                    run_key=key,
                    execution_error=state.get("execution_error"),
                    score_error=score_error,
                ),
            )
        append(out / "scores.jsonl", row)
        rows.append(row)
        if cancelled:
            append(out / "errors.jsonl", {"status": "ABORTED", "run_key": key, "code": "CANCELLED"})
            raise asyncio.CancelledError("durable cancellation retained")
        if drift:
            append(
                out / "errors.jsonl",
                {"status": "ABORTED", "run_key": key, "code": "PROTOCOL_MISMATCH"},
            )
            raise ValueError("protocol mismatch after Graph; durable run retained")
    write_csv(out / "case-level.csv", rows)
    durable_write(out / "aggregate.json", aggregate(rows))
    write_csv(out / "aggregate.csv", aggregate(rows))
    from collections import Counter

    from .statistics import analyze

    durable_write(
        out / "coverage.json",
        {
            "split": split,
            "case_n": len(cases),
            "run_n": len(rows),
            "families": dict(Counter(c.scenario_family_id for c in cases)),
            "cohorts": {
                k: sum(c.cohort == k for c in cases) for k in ("core", "ood", "monitoring")
            },
        },
    )
    durable_write(
        out / "failure-categories.json",
        dict(Counter(r["termination_reason"] for r in rows if not r["technical_completion"])),
    )
    durable_write(
        out / "review-coverage.json",
        {"reviewed_claims": 0, "human_support_rate": None, "status": "pending"},
    )
    durable_write(
        out / "statistical-analysis.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    from .citation_review import prepare_review_bundle

    bundle = prepare_review_bundle(review_states)
    if isinstance(bundle, dict):
        append(out / "citation-review-bundle.jsonl", bundle)
    else:
        for claim in bundle:
            append(out / "citation-review-bundle.jsonl", claim)
    durable_write(
        out / "artifact-digests.json",
        {
            name: hashlib.sha256((out / name).read_bytes()).hexdigest()
            for name in (
                "raw-runs.jsonl",
                "scores.jsonl",
                "protocol.json",
                "experiment-context.json",
            )
        },
    )
    export_paired(out, rows, protocol)
    # Empty streams document the absence of errors/reviews instead of invented records.
    for filename in ("errors.jsonl", "citation-review-bundle.jsonl"):
        if not (out / filename).exists():
            (out / filename).touch()
    (out / "reproducibility.txt").write_text(
        f"Python: {sys.version}\nExecutable: {sys.executable}\n"
        "Run uses saved source/config/environment lock, cache off, jobs=1.\n"
        "Formal runner pending; no human review claimed.\n",
        encoding="utf-8",
    )
    return rows


def export_paired(out, rows, protocol):
    from .statistics import analyze

    analyses = analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples)
    summaries = [
        dict(baseline=a["baseline"], scenario_family_id=family, difference=value)
        for a in analyses
        for family, value in a.get("family_differences", {}).items()
    ]
    write_csv(out / "family-summary.csv", summaries)
    from collections import defaultdict
    from statistics import mean

    cells = defaultdict(dict)
    for row in rows:
        if row.get("cohort", "core") == "core" and row.get("root_cause_correct") is not None:
            cells[row["incident_id"]].setdefault(row["variant"], []).append(
                row["root_cause_correct"]
            )
    differences = [
        dict(incident_id=case, baseline=baseline, difference=mean(pair["full"]) - mean(values))
        for case, pair in cells.items()
        for baseline, values in pair.items()
        if baseline != "full" and "full" in pair
    ]
    write_csv(out / "paired-differences.csv", differences)
