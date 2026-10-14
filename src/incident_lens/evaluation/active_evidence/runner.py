"""Cache-off sequential real Graph runner with durable failure ledgers."""

import asyncio
import hashlib
import time
from pathlib import Path
from uuid import uuid4

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics, write_csv
from incident_lens.incidentbench.experiment import (
    append,
    durable_write,
    execution_lock,
    load_cases,
    run_identity,
    run_order,
    score_saved_raw,
)
from incident_lens.incidentbench.manifest import create_lock, verify_lock
from incident_lens.incidentbench.validator import validate_dataset
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions

from .metrics import selection_events, selection_metrics
from .statistics import analyze
from .variants import ActiveProtocol, workflow_values


async def run_experiment(dataset, split, provider_factory, out, protocol):
    protocol = ActiveProtocol.model_validate(protocol)
    root, public, cases = load_cases(dataset, split)
    if not cases:
        raise ValueError("empty split")
    if split == "test" or protocol.formal:
        raise ValueError("formal/Test research BLOCKED: independent labels and sealing pending")
    if protocol.provider_id != "mock":
        raise ValueError(
            "real empirical gate BLOCKED: provider readiness and reviewed labels pending"
        )
    if not validate_dataset(root)["ok"]:
        raise ValueError("public benchmark audit failed")
    lock = create_lock(root, protocol)
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    with execution_lock(out):
        return await _execute(root, public, cases, split, provider_factory, out, protocol, lock)


async def _execute(root, public, cases, split, factory, out, protocol, lock):
    (out / "states").mkdir()
    experiment_id = str(uuid4())
    context = dict(
        experiment_id=experiment_id,
        dataset_root=str(root),
        split=split,
        evaluation="engineering_no_oracle",
        formal_status="BLOCKED",
    )
    order = run_order([c.incident_id for c in cases], protocol)
    for name, value in (
        ("protocol.json", protocol.model_dump(mode="json")),
        ("manifest.json", lock),
        ("experiment-context.json", context),
        ("run-order.json", order),
    ):
        durable_write(out / name, value)
    metadata = {c.incident_id: c.model_dump(mode="json") for c in cases}
    rows = []
    actions = []
    providers = []
    frozen_parameters = None
    for incident, repeat, variant in order:
        verify_lock(lock, root, protocol)
        key = f"{incident}.{variant}.repeat-{repeat}"
        run_id = run_identity(experiment_id, key)
        append(out / "progress.jsonl", dict(run_key=key, status="STARTED"))
        started = time.monotonic()
        measured = None
        cancelled = False
        try:
            provider = factory()
            if any(provider is p for p in providers):
                raise ValueError("fresh provider required")
            providers.append(provider)
            measured = MeasuredProvider(provider)
            if (
                measured.source != "mock"
                or provider.model_id != protocol.model_id
                or provider.temperature != protocol.temperature
            ):
                raise ValueError("provider protocol mismatch")
            from incident_lens.incidentbench.experiment import canonical

            parameters = canonical(measured.model_parameters)
            if frozen_parameters is None:
                frozen_parameters = parameters
                durable_write(out / "provider-parameters.json", measured.model_parameters)
            elif parameters != frozen_parameters:
                raise ValueError("provider config drift")
            workflow = WorkflowOptions(**workflow_values(variant, protocol.active_evidence_config))
            state = await run_investigation(
                incident,
                measured,
                data_root=public,
                budget=Budget(
                    max_rounds=protocol.max_rounds,
                    max_tool_calls=protocol.max_tool_calls,
                    max_llm_calls=protocol.max_llm_calls,
                    max_wall_seconds=protocol.max_wall_seconds,
                ),
                variant="fixed" if variant == "B0" else "full",
                workspace_id="incidentbench",
                run_id=run_id,
                cache=None,
                workflow=workflow,
            )
            if hasattr(state, "model_dump"):
                state = state.model_dump(mode="json")
            if state.get("incident_id") != incident or state.get("run_id") != run_id:
                raise ValueError("foreign Graph identity")
        except (Exception, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            state = dict(
                incident_id=incident,
                run_id=run_id,
                report=None,
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
        statepath = out / "states" / f"{key}.json"
        durable_write(statepath, state)
        receipt = dict(
            path=str(statepath), sha256=hashlib.sha256(statepath.read_bytes()).hexdigest()
        )
        raw = dict(
            run_key=key,
            incident_id=incident,
            run_id=run_id,
            variant=variant,
            repeat_id=repeat,
            metadata=metadata[incident],
            source="mock",
            latency_ms=(time.monotonic() - started) * 1000,
            usage=usage_metrics(measured, state)
            if measured
            else dict(actual_http_requests=None, total_tokens=None),
            state=dict(state, completion_receipt=receipt),
        )
        append(out / "raw-runs.jsonl", raw)
        row = score_saved_raw(raw, None, root)
        row.update(selection_metrics(state))
        rows.append(row)
        append(out / "scores.jsonl", row)
        for details in selection_events(state):
            append(out / "selection-decisions.jsonl", dict(run_key=key, details=details))
            selected = details["selection"]["selected_candidate_ids"]
            for assessment in details["selection"]["assessments"]:
                actions.append(
                    dict(
                        run_key=key,
                        decision_id=details["selection"]["decision_id"],
                        candidate_id=assessment["candidate_id"],
                        selected=assessment["candidate_id"] in selected,
                        score=assessment.get("score"),
                        eligibility=assessment["eligibility"],
                        reject_reason=assessment.get("reject_reason"),
                        features=assessment.get("features"),
                        coordinator_proposed_tasks=details.get("coordinator_proposed_tasks"),
                        selector_executed_tasks=details.get("selector_executed_tasks"),
                    )
                )
        if row.get("failure_category"):
            append(out / "errors.jsonl", dict(run_key=key, code=row["failure_category"]))
        append(out / "progress.jsonl", dict(run_key=key, status="DURABLE", receipt=receipt))
        if drift or cancelled:
            durable_write(
                out / "experiment-status.json",
                dict(status="partial", attempted=len(rows), planned=len(order)),
            )
            if cancelled:
                raise asyncio.CancelledError("durable cancellation retained")
            raise ValueError("protocol drift; failure retained")
    from incident_lens.incidentbench.scorer import aggregate

    write_csv(out / "case-level.csv", rows)
    summary = aggregate(rows)
    durable_write(out / "aggregate.json", summary)
    write_csv(out / "aggregate.csv", summary)
    write_csv(out / "action-trace.csv", actions)
    from collections import defaultdict

    groups = defaultdict(list)
    for row in rows:
        groups[(row["scenario_family_id"], row["variant"])].append(row)
    write_csv(
        out / "family-slices.csv",
        [
            dict(scenario_family_id=family, **aggregate(group)[0])
            for (family, variant), group in groups.items()
        ],
    )
    from statistics import mean

    paired = []
    for baseline in ("B1", "B1c", "B2", "B3", "B0"):
        for incident in {r["incident_id"] for r in rows}:
            for metric in (
                "root_cause_correct",
                "total_tokens",
                "actual_http_requests",
                "tool_calls",
                "latency_ms",
            ):
                cell = {
                    v: {
                        r["repeat_id"]: r.get(metric)
                        for r in rows
                        if r["incident_id"] == incident and r["variant"] == v
                    }
                    for v in (baseline, "B4")
                }
                matched = [
                    repeat
                    for repeat in set(cell[baseline]) & set(cell["B4"])
                    if cell[baseline][repeat] is not None and cell["B4"][repeat] is not None
                ]
                if matched:
                    paired.append(
                        dict(
                            incident_id=incident,
                            baseline=baseline,
                            metric=metric,
                            matched_repeats=len(matched),
                            difference=mean(cell["B4"][r] - cell[baseline][r] for r in matched),
                        )
                    )
    write_csv(out / "paired-differences.csv", paired)
    durable_write(out / "source-hashes.json", lock)
    durable_write(
        out / "calibration-report.json",
        dict(
            status="NOT_APPLICABLE",
            reason="Seed engineering diagnostics; Dev calibration gate BLOCKED",
        ),
    )
    failures = [r for r in rows if r.get("failure_category")]
    (out / "error-analysis.md").write_text(
        "# Engineering failures\n\n"
        + "\n".join(f"- {r['run_key']}: {r['failure_category']}" for r in failures)
        + "\n\nOracle correctness and semantic review are pending. No empirical improvement claim.\n",
        encoding="utf-8",
    )
    durable_write(
        out / "uncertainty.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    durable_write(
        out / "semantic-review-status.json", dict(status="pending", human_grounded_success=None)
    )
    durable_write(
        out / "experiment-status.json",
        dict(
            status="completed_engineering_only",
            attempted=len(rows),
            planned=len(order),
            research_status="BLOCKED",
            blockers=[
                "reviewed labels pending",
                "Dev/Test empty",
                "real provider empirical gate pending",
            ],
        ),
    )
    for name in ("errors.jsonl", "selection-decisions.jsonl"):
        if not (out / name).exists():
            (out / name).touch()
    durable_write(
        out / "artifact-digests.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.is_file() and p.name != ".execution.lock"
        },
    )
    return rows
