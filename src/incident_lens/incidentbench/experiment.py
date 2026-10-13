"""Sequential, locked, failure-preserving execution of the existing Graph."""

import asyncio
import csv
import hashlib
import io
import json
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics, write_csv
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions

from .schemas import BenchmarkCaseMetadata, ExperimentProtocol
from .scorer import aggregate, score_benchmark_run


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def run_identity(experiment_id, key):
    return "bench-" + hashlib.sha256(f"{experiment_id}:{key}".encode()).hexdigest()[:24]


@contextmanager
def execution_lock(out):
    """OS-backed lock survives process death without a stale-lock deletion step."""
    from .oracle_store import safe_path

    safe_path(out)
    lock_path = out / ".execution.lock"
    if lock_path.exists() or lock_path.is_symlink():
        if not safe_path(lock_path).is_file():
            raise PermissionError("execution lock must be a regular file")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("experiment already active; concurrent resume refused") from None
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError("experiment already active; concurrent resume refused") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


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


def read_json(path):
    from .oracle_store import safe_path

    return json.loads(safe_path(path).read_bytes())


def read_jsonl(path):
    from .oracle_store import safe_path

    if not Path(path).exists():
        return []
    raw = safe_path(path).read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("partial JSONL line; retained unchanged for explicit audit")
    return [json.loads(line) for line in raw.splitlines()]


def write_json_preserving(path, value):
    if Path(path).exists():
        if read_json(path) != value:
            raise ValueError("existing derived artifact mismatch")
    else:
        durable_write(path, value)


def write_csv_preserving(path, rows):
    if Path(path).exists():
        from .oracle_store import safe_path

        existing_bytes = safe_path(path).read_bytes()
        headers = next(csv.reader(io.StringIO(existing_bytes.decode("utf-8"))), [])
        fields = list(dict.fromkeys(k for r in rows for k in r))
        if set(headers) != set(fields) or len(headers) != len(fields):
            raise ValueError("existing derived CSV field mismatch")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        if existing_bytes != stream.getvalue().encode("utf-8"):
            raise ValueError("existing derived CSV mismatch")
    else:
        write_csv(path, rows)


def score_saved_raw(raw, oracle_root, root):
    from .oracle_store import OracleStore

    state, metadata = raw["state"], raw["metadata"]
    oracle, score_error = None, None
    if (
        oracle_root
        and metadata["split"] != "test"
        and state.get("report")
        and (state.get("execution_error") or {}).get("code") != "PROTOCOL_MISMATCH"
    ):
        try:
            oracle = OracleStore(oracle_root, public_root=root).load_after_completion(
                raw["incident_id"], state
            )
        except Exception as exc:
            score_error = getattr(exc, "code", type(exc).__name__)
    row = {
        k: raw[k]
        for k in (
            "run_key",
            "incident_id",
            "run_id",
            "variant",
            "repeat_id",
            "source",
            "latency_ms",
        )
    }
    row.update(
        scenario_family_id=metadata["scenario_family_id"],
        source_blueprint_id=metadata["source_blueprint_id"],
        near_duplicate_cluster_id=metadata["near_duplicate_cluster_id"],
        counterfactual_pair_id=metadata["counterfactual_pair_id"],
        independence_status="unreviewed",
        cohort=metadata["cohort"],
        **raw["usage"],
        **score_benchmark_run(state, oracle),
    )
    row["score_error"] = score_error
    row["failure_category"] = (
        (
            (state.get("execution_error") or {}).get("code")
            or row.get("termination_reason")
            or "UNKNOWN"
        )
        if not row["technical_completion"]
        else None
    )
    return row


def recover_resume(out, root, protocol, context, order, metadata, oracle_root):
    """Recover evaluator work only; never repeat an already STARTED attempt."""
    from .manifest import verify_lock
    from .oracle_store import safe_path

    out = safe_path(out)
    safe_path(out / "states")
    verify_lock(read_json(out / "protocol.lock.json"), root, protocol)
    if read_json(out / "manifest-lock.json") != read_json(out / "protocol.lock.json"):
        raise ValueError("resume manifest lock mismatch")
    if (
        read_json(out / "protocol.json") != protocol.model_dump(mode="json")
        or read_json(out / "experiment-context.json") != context
    ):
        raise ValueError("resume protocol/evaluator context mismatch")
    if read_json(out / "run-order.json") != [list(x) for x in order]:
        raise ValueError("resume run order mismatch")
    final = (out / "artifact-digests.json").exists()
    if final:
        for name, digest in read_json(out / "artifact-digests.json").items():
            if (
                name
                not in {
                    "raw-runs.jsonl",
                    "scores.jsonl",
                    "protocol.json",
                    "experiment-context.json",
                }
                or hashlib.sha256(safe_path(out / name).read_bytes()).hexdigest() != digest
            ):
                raise ValueError("resume artifact digest mismatch")
    progress = read_jsonl(out / "progress.jsonl")
    raw_rows = read_jsonl(out / "raw-runs.jsonl")
    score_rows = read_jsonl(out / "scores.jsonl")
    expected = {}
    for incident, repeat, variant in order:
        key = f"{incident}.{variant}.repeat-{repeat}"
        expected[key] = (
            incident,
            repeat,
            variant,
            run_identity(context["experiment_id"], key),
        )
    started, durable = {}, {}
    for event in progress:
        key = event.get("run_key")
        if key not in expected or event.get("run_id") != expected[key][3]:
            raise ValueError("resume foreign progress key")
        if event["status"] == "STARTED":
            if key in started:
                raise ValueError("resume duplicate STARTED attempt")
            started[key] = event
        elif event["status"] == "DURABLE":
            if key not in started or key in durable:
                raise ValueError("resume invalid durable progress")
            durable[key] = event
        else:
            raise ValueError("resume unknown progress status")
    if list(started) != list(expected)[: len(started)]:
        raise ValueError("resume progress must be a prefix of locked run order")
    raws, scores = {}, {}
    for raw in raw_rows:
        key = raw["run_key"]
        if key not in started or key in raws:
            raise ValueError("resume duplicate/foreign raw run")
        incident, repeat, variant, run_id = expected[key]
        if (raw["incident_id"], raw["repeat_id"], raw["variant"], raw["run_id"]) != (
            incident,
            repeat,
            variant,
            run_id,
        ) or raw["metadata"] != metadata[incident].model_dump(mode="json"):
            raise ValueError("resume raw identity/metadata mismatch")
        state = raw["state"]
        receipt = state["completion_receipt"]
        path = out / "states" / f"{key}.json"
        saved = {k: v for k, v in state.items() if k != "completion_receipt"}
        if (
            safe_path(receipt["path"]) != safe_path(path)
            or canonical(saved) != safe_path(path).read_bytes()
            or hashlib.sha256(canonical(saved)).hexdigest() != receipt["sha256"]
            or saved.get("incident_id") != incident
            or saved.get("run_id") != run_id
        ):
            raise ValueError("resume completion receipt mismatch")
        if key in durable and durable[key]["receipt"] != receipt:
            raise ValueError("resume progress receipt mismatch")
        raws[key] = raw
    for row in score_rows:
        if row["run_key"] not in raws or row["run_key"] in scores:
            raise ValueError("resume duplicate/foreign score key")
        scores[row["run_key"]] = row
    if list(raws) != list(started)[: len(raws)] or list(scores) != list(raws)[: len(scores)]:
        raise ValueError("resume raw/score order mismatch")
    if final and len(raws) != len(order):
        raise ValueError("sealed experiment missing completed keys")
    if set(durable) - set(raws):
        raise ValueError("resume durable progress without raw record")
    for key, row in scores.items():
        if row != score_saved_raw(raws[key], oracle_root, root):
            raise ValueError("resume score/oracle mismatch")
    parameter_path = out / "provider-parameters.json"
    if (
        parameter_path.exists()
        and read_json(out / "provider-parameters.sha256.json")
        != hashlib.sha256(safe_path(parameter_path).read_bytes()).hexdigest()
    ):
        raise ValueError("resume provider parameter digest mismatch")
    for key in started:
        incident, repeat, variant, run_id = expected[key]
        if key not in raws:
            path = out / "states" / f"{key}.json"
            if path.exists():
                state = read_json(safe_path(path))
                if state.get("incident_id") != incident or state.get("run_id") != run_id:
                    raise ValueError("resume orphan state identity mismatch")
            else:
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
                    execution_error={"code": "INTERRUPTED"},
                )
                durable_write(path, state)
            receipt = {
                "path": str(path),
                "sha256": hashlib.sha256(safe_path(path).read_bytes()).hexdigest(),
            }
            usage = {
                k: None
                for k in (
                    "actual_http_requests",
                    "llm_requests",
                    "logical_structured_calls",
                    "task_retries",
                    "transport_retries",
                    "repair_requests",
                    "failed_calls",
                    "provider_failures",
                    "failed_model_calls",
                    "failed_tool_calls",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "cost_usd",
                )
            }
            raw = dict(
                run_key=key,
                incident_id=incident,
                run_id=run_id,
                variant=variant,
                repeat_id=repeat,
                metadata=metadata[incident].model_dump(mode="json"),
                source="mock",
                latency_ms=None,
                usage=usage,
                state=dict(state, completion_receipt=receipt),
            )
            append(out / "raw-runs.jsonl", raw)
            append(
                out / "errors.jsonl",
                {"run_key": key, "code": "INTERRUPTED_USAGE_UNKNOWN", "status": "RETAINED"},
            )
            raws[key] = raw
        if key not in durable:
            append(
                out / "progress.jsonl",
                {
                    "run_key": key,
                    "run_id": run_id,
                    "status": "DURABLE",
                    "receipt": raws[key]["state"]["completion_receipt"],
                },
            )
        recomputed = score_saved_raw(raws[key], oracle_root, root)
        if key in scores:
            if scores[key] != recomputed:
                raise ValueError("resume score/oracle mismatch")
            # Canonical JSON sorts nested dictionaries; restore scorer insertion
            # order so their CSV representation matches the original export.
            scores[key] = recomputed
        else:
            append(out / "scores.jsonl", recomputed)
            scores[key] = recomputed
    frozen = canonical(read_json(parameter_path)) if parameter_path.exists() else None
    return list(scores.values()), [r["state"] for r in raws.values()], set(raws), frozen


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
    from .oracle_store import safe_path

    dataset = safe_path(dataset)
    return (dataset.parent, dataset) if dataset.name == "rca" else (dataset, dataset / "rca")


def load_cases(dataset, split):
    from .oracle_store import safe_path

    if split not in {"seed", "dev", "test"}:
        raise ValueError("unknown split")
    root, public = dataset_paths(dataset)
    index = json.loads(safe_path(root / "public_case_index.json").read_text(encoding="utf-8"))
    if isinstance(index, dict):
        index = index.get("cases", index.get("items", []))
    cases = [BenchmarkCaseMetadata.model_validate(c) for c in index]
    ids = json.loads(safe_path(public / "splits" / f"{split}_ids.json").read_text(encoding="utf-8"))
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
    dataset,
    split,
    provider_factory,
    out,
    protocol,
    oracle_root=None,
    *,
    protocol_lock=None,
    resume=False,
):
    """Run or explicitly resume; serialize all writers before touching ledgers."""
    from .manifest import verify_lock
    from .oracle_store import safe_path
    from .validator import validate_dataset

    protocol = (
        protocol
        if isinstance(protocol, ExperimentProtocol)
        else ExperimentProtocol.model_validate(protocol)
    )
    root, _, cases = load_cases(dataset, split)
    if not cases:
        raise ValueError("empty split")
    if not validate_dataset(root)["ok"]:
        raise ValueError("public benchmark audit failed before execution")
    if protocol.formal:
        raise ValueError(
            "formal experiment requires independently accepted labels and verified sealing; pending"
        )
    if protocol_lock is not None:
        verify_lock(protocol_lock, root, protocol)
    out = Path(out).absolute()
    if resume:
        out = safe_path(out)
        if protocol.provider_id != "mock":
            raise ValueError("resume currently supports offline mock execution only")
    else:
        out.mkdir(parents=True, exist_ok=False)
    with execution_lock(out):
        return await _run_experiment(
            dataset,
            split,
            provider_factory,
            out,
            protocol,
            oracle_root,
            protocol_lock=protocol_lock,
            resume=resume,
        )


async def _run_experiment(
    dataset,
    split,
    provider_factory,
    out,
    protocol,
    oracle_root=None,
    *,
    protocol_lock=None,
    resume=False,
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
    order = run_order([c.incident_id for c in cases], protocol)
    metadata = {c.incident_id: c for c in cases}
    context = {
        "dataset_root": str(root),
        "split": split,
        "oracle_root_path_commitment": hashlib.sha256(
            os.path.normcase(str(Path(oracle_root).resolve())).encode()
        ).hexdigest()
        if oracle_root
        else None,
        "resume_policy": "retain_interrupted_then_continue_unstarted_offline",
    }
    if resume:
        from .oracle_store import safe_path

        experiment_id = read_json(safe_path(out / "experiment-context.json"))["experiment_id"]
        if str(UUID(experiment_id)) != experiment_id:
            raise ValueError("resume invalid experiment identity")
    else:
        experiment_id = str(uuid4())
    context["experiment_id"] = experiment_id
    if resume:
        if protocol.provider_id != "mock":
            raise ValueError("resume currently supports offline mock execution only")
        rows, review_states, completed, frozen_parameters = recover_resume(
            out, root, protocol, context, order, metadata, oracle_root
        )
        if len(completed) == len(order) and (out / "artifact-digests.json").exists():
            if read_json(out / "aggregate.json") != aggregate(rows):
                raise ValueError("completed aggregate mismatch")
            finalize_experiment(out, rows, review_states, split, cases, protocol)
            return rows
    else:
        (out / "states").mkdir()
        durable_write(out / "protocol.lock.json", lock)
        durable_write(out / "manifest-lock.json", lock)
        durable_write(out / "experiment-context.json", context)
        durable_write(out / "protocol.json", protocol.model_dump(mode="json"))
        durable_write(out / "run-order.json", order)
        rows, frozen_parameters, review_states, completed = [], None, [], set()
    used_providers = []
    for position, (incident, repeat, variant) in enumerate(order):
        key = f"{incident}.{variant}.repeat-{repeat}"
        if key in completed:
            continue
        try:
            verify_lock(lock, root, protocol)
        except ValueError:
            append(
                out / "errors.jsonl",
                {"status": "ABORTED", "code": "PROTOCOL_MISMATCH", "position": position},
            )
            raise
        run_id = run_identity(experiment_id, key)
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
            durable_write(
                out / "provider-parameters.sha256.json",
                hashlib.sha256(current_parameters).hexdigest(),
            )
            frozen_parameters = current_parameters
        elif current_parameters != frozen_parameters:
            raise ValueError("provider recovery/config drift")
        append(out / "progress.jsonl", dict(run_key=key, run_id=run_id, status="STARTED"))
        started = time.monotonic()
        cancelled = False
        try:
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
        row["failure_category"] = (
            (
                (state.get("execution_error") or {}).get("code")
                or row.get("termination_reason")
                or "UNKNOWN"
            )
            if not row["technical_completion"]
            else None
        )
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
    finalize_experiment(out, rows, review_states, split, cases, protocol)
    return rows


def finalize_experiment(out, rows, review_states, split, cases, protocol):
    """Write missing derived outputs; preserve and verify existing ones on recovery."""
    write_csv_preserving(out / "case-level.csv", rows)
    write_json_preserving(out / "aggregate.json", aggregate(rows))
    write_csv_preserving(out / "aggregate.csv", aggregate(rows))
    from collections import Counter

    from .statistics import analyze

    write_json_preserving(
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
    write_json_preserving(
        out / "failure-categories.json",
        dict(Counter(r["failure_category"] for r in rows if not r["technical_completion"])),
    )
    write_json_preserving(
        out / "review-coverage.json",
        {"reviewed_claims": 0, "human_support_rate": None, "status": "pending"},
    )
    write_json_preserving(
        out / "statistical-analysis.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    from .citation_review import prepare_review_bundle

    bundle = prepare_review_bundle(review_states)
    bundle_path = out / "citation-review-bundle.jsonl"
    expected_bundle = [bundle] if isinstance(bundle, dict) else bundle
    if bundle_path.exists():
        existing = read_jsonl(bundle_path)
        if existing != expected_bundle[: len(existing)]:
            raise ValueError("existing review bundle mismatch")
    else:
        existing = []
    for claim in expected_bundle[len(existing) :]:
        append(bundle_path, claim)
    write_json_preserving(
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
    reproducibility = (
        f"Python: {sys.version}\nExecutable: {sys.executable}\n"
        "Run uses saved source/config/environment lock, cache off, jobs=1.\n"
        "Formal runner pending; no human review claimed.\n"
    )
    if (out / "reproducibility.txt").exists():
        from .oracle_store import safe_path

        if safe_path(out / "reproducibility.txt").read_text(encoding="utf-8") != reproducibility:
            raise ValueError("existing reproducibility artifact mismatch")
    else:
        with (out / "reproducibility.txt").open("x", encoding="utf-8") as stream:
            stream.write(reproducibility)


def export_paired(out, rows, protocol):
    from .statistics import analyze

    analyses = analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples)
    summaries = [
        dict(baseline=a["baseline"], scenario_family_id=family, difference=value)
        for a in analyses
        for family, value in a.get("family_differences", {}).items()
    ]
    write_csv_preserving(out / "family-summary.csv", summaries)
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
    write_csv_preserving(out / "paired-differences.csv", differences)
