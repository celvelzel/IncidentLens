"""Cache-off sequential real Graph runner with durable failure ledgers."""

import asyncio
import hashlib
import time
from pathlib import Path
from uuid import UUID, uuid4

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.incidentbench.experiment import (
    append,
    durable_write,
    execution_lock,
    load_cases,
    read_json,
    run_identity,
    run_order,
    score_saved_raw,
    write_csv_preserving,
    write_json_preserving,
)
from incident_lens.incidentbench.manifest import create_lock, verify_lock
from incident_lens.incidentbench.validator import validate_dataset
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions

from .metrics import selection_events, selection_metrics
from .statistics import analyze
from .variants import ActiveProtocol, workflow_values


async def run_experiment(dataset, split, provider_factory, out, protocol, *, resume=False):
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
    if resume:
        from incident_lens.incidentbench.oracle_store import safe_path

        out = safe_path(out)
        if not out.is_dir():
            raise ValueError("resume requires existing output")
    else:
        out.mkdir(parents=True, exist_ok=False)
    with execution_lock(out):
        return await _execute(
            root, public, cases, split, provider_factory, out, protocol, lock, resume=resume
        )


def action_rows(key, details):
    selected = details["selection"]["selected_candidate_ids"]
    return [
        dict(
            run_key=key,
            decision_id=details["selection"]["decision_id"],
            candidate_id=a["candidate_id"],
            selected=a["candidate_id"] in selected,
            score=a.get("score"),
            eligibility=a["eligibility"],
            reject_reason=a.get("reject_reason"),
            features=a.get("features"),
            coordinator_proposed_tasks=details.get("coordinator_proposed_tasks"),
            selector_executed_tasks=details.get("selector_executed_tasks"),
        )
        for a in details["selection"]["assessments"]
    ]


async def _execute(root, public, cases, split, factory, out, protocol, lock, *, resume=False):
    experiment_id = (
        read_json(out / "experiment-context.json")["experiment_id"] if resume else str(uuid4())
    )
    if str(UUID(experiment_id)) != experiment_id:
        raise ValueError("invalid experiment UUID")
    context = dict(
        experiment_id=experiment_id,
        dataset_root=str(root),
        split=split,
        evaluation="engineering_no_oracle",
        formal_status="BLOCKED",
    )
    order = run_order([c.incident_id for c in cases], protocol)
    metadata = {c.incident_id: c.model_dump(mode="json") for c in cases}
    if resume:
        from .recovery import recover_resume

        rows, states, completed, frozen_parameters = recover_resume(
            out, root, protocol, context, order, metadata, None
        )
        actions = [
            action
            for row, state in zip(rows, states)
            for details in selection_events(state)
            for action in action_rows(row["run_key"], details)
        ]
    else:
        (out / "states").mkdir()
        for name, value in (
            ("protocol.json", protocol.model_dump(mode="json")),
            ("manifest.json", lock),
            ("experiment-context.json", context),
            ("run-order.json", order),
        ):
            durable_write(out / name, value)
        rows, actions, completed, frozen_parameters = [], [], set(), None
    providers = []
    for incident, repeat, variant in order:
        key = f"{incident}.{variant}.repeat-{repeat}"
        if key in completed:
            continue
        verify_lock(lock, root, protocol)
        run_id = run_identity(experiment_id, key)
        append(out / "progress.jsonl", dict(run_key=key, run_id=run_id, status="STARTED"))
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
                durable_write(
                    out / "provider-parameters.sha256.json", hashlib.sha256(parameters).hexdigest()
                )
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
            actions.extend(action_rows(key, details))
        if row.get("failure_category"):
            append(out / "errors.jsonl", dict(run_key=key, code=row["failure_category"]))
        append(
            out / "progress.jsonl",
            dict(run_key=key, run_id=run_id, status="DURABLE", receipt=receipt),
        )
        if drift or cancelled:
            durable_write(
                out / "checkpoint-status.json",
                dict(status="partial", attempted=len(rows), planned=len(order)),
            )
            if cancelled:
                raise asyncio.CancelledError("durable cancellation retained")
            raise ValueError("protocol drift; failure retained")
    from incident_lens.incidentbench.scorer import aggregate

    write_csv_preserving(out / "case-level.csv", rows)
    summary = aggregate(rows)
    write_json_preserving(out / "aggregate.json", summary)
    write_csv_preserving(out / "aggregate.csv", summary)
    write_csv_preserving(out / "action-trace.csv", actions)
    from collections import defaultdict

    groups = defaultdict(list)
    for row in rows:
        groups[(row["scenario_family_id"], row["variant"])].append(row)
    write_csv_preserving(
        out / "family-slices.csv",
        [
            dict(scenario_family_id=family, **aggregate(group)[0])
            for (family, variant), group in groups.items()
        ],
    )
    from statistics import mean

    paired = []
    for baseline in ("B1", "B1c", "B2", "B3", "B0"):
        for incident in sorted({r["incident_id"] for r in rows}):
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
                    for repeat in sorted(set(cell[baseline]) & set(cell["B4"]))
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
    write_csv_preserving(out / "paired-differences.csv", paired)
    write_json_preserving(out / "source-hashes.json", lock)
    write_json_preserving(
        out / "calibration-report.json",
        dict(
            status="NOT_APPLICABLE",
            reason="Seed engineering diagnostics; Dev calibration gate BLOCKED",
        ),
    )
    failures = [r for r in rows if r.get("failure_category")]
    error_text = (
        "# Engineering failures\n\n"
        + "\n".join(f"- {r['run_key']}: {r['failure_category']}" for r in failures)
        + "\n\nOracle correctness and semantic review are pending. No empirical improvement claim.\n"
    )
    error_path = out / "error-analysis.md"
    if error_path.exists():
        if error_path.read_bytes() != error_text.encode("utf-8"):
            raise ValueError("existing error analysis mismatch")
    else:
        with error_path.open("xb") as stream:
            stream.write(error_text.encode("utf-8"))
    write_json_preserving(
        out / "uncertainty.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    write_json_preserving(
        out / "semantic-review-status.json", dict(status="pending", human_grounded_success=None)
    )
    write_json_preserving(
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
    write_json_preserving(
        out / "artifact-digests.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.is_file() and p.name not in {".execution.lock", "artifact-digests.json"}
        },
    )
    return rows
