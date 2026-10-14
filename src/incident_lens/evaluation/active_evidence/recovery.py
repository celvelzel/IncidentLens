"""Strict Mock-only prefix recovery, adapted from IncidentBench durable recovery."""

import hashlib
from pathlib import Path

from incident_lens.incidentbench.experiment import (
    append,
    canonical,
    durable_write,
    read_json,
    read_jsonl,
    run_identity,
    score_saved_raw,
)

from .metrics import selection_events, selection_metrics


def score_raw(raw, oracle_root, root):
    if oracle_root is not None:
        raise ValueError("CAES resume never accesses an oracle")
    row = score_saved_raw(raw, None, root)
    row.update(selection_metrics(raw["state"]))
    return row


def recover_resume(out, root, protocol, context, order, metadata, oracle_root):
    """Recover evaluator work only; never repeat an already STARTED attempt."""
    from incident_lens.incidentbench.manifest import verify_lock
    from incident_lens.incidentbench.oracle_store import safe_path

    out = safe_path(out)
    safe_path(out / "states")
    verify_lock(read_json(out / "manifest.json"), root, protocol)
    if (
        read_json(out / "protocol.json") != protocol.model_dump(mode="json")
        or read_json(out / "experiment-context.json") != context
    ):
        raise ValueError("resume protocol/evaluator context mismatch")
    if read_json(out / "run-order.json") != [list(x) for x in order]:
        raise ValueError("resume run order mismatch")
    final = (out / "artifact-digests.json").exists()
    if final:
        digests = read_json(out / "artifact-digests.json")
        expected_files = {
            p.name
            for p in out.iterdir()
            if p.is_file() and p.name not in {".execution.lock", "artifact-digests.json"}
        }
        if set(digests) != expected_files:
            raise ValueError("resume artifact digest file set mismatch")
        for name, expected_digest in digests.items():
            if (
                Path(name).name != name
                or hashlib.sha256(safe_path(out / name).read_bytes()).hexdigest() != expected_digest
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
        ) or raw["metadata"] != metadata[incident]:
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
        if row != score_raw(raws[key], oracle_root, root):
            raise ValueError("resume score/oracle mismatch")
    parameter_path = out / "provider-parameters.json"
    if (
        parameter_path.exists()
        and read_json(out / "provider-parameters.sha256.json")
        != hashlib.sha256(safe_path(parameter_path).read_bytes()).hexdigest()
    ):
        raise ValueError("resume provider parameter digest mismatch")
    # Serial execution permits a single unfinished attempt at the tail only.
    if set(started) - set(durable) not in (set(), {list(started)[-1]} if started else set()):
        raise ValueError("resume ambiguous unfinished prefix")
    expected_state_files = {f"{key}.json" for key in started}
    if {p.name for p in (out / "states").iterdir()} - expected_state_files:
        raise ValueError("resume foreign state files")
    # Validate all existing supplemental ledgers before any recovery writes.
    selection_expected = [
        dict(run_key=key, details=d)
        for key, raw in raws.items()
        for d in selection_events(raw["state"])
    ]
    selection_saved = read_jsonl(out / "selection-decisions.jsonl")
    if selection_saved != selection_expected[: len(selection_saved)]:
        raise ValueError("resume selection ledger mismatch")
    errors = read_jsonl(out / "errors.jsonl")
    for error in errors:
        if error.get("run_key") not in started:
            raise ValueError("resume foreign error record")
        if error.get("code") not in {
            "INTERRUPTED_USAGE_UNKNOWN",
            (scores.get(error["run_key"]) or {}).get("failure_category"),
        }:
            raise ValueError("resume error code mismatch")
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
                metadata=metadata[incident],
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
        recomputed = score_raw(raws[key], oracle_root, root)
        if key in scores:
            if scores[key] != recomputed:
                raise ValueError("resume score/oracle mismatch")
            # Canonical JSON sorts nested dictionaries; restore scorer insertion
            # order so their CSV representation matches the original export.
            scores[key] = recomputed
        else:
            append(out / "scores.jsonl", recomputed)
            scores[key] = recomputed
    for detail in selection_expected[len(selection_saved) :]:
        append(out / "selection-decisions.jsonl", detail)
    for key, row in scores.items():
        if row.get("failure_category") and not any(e.get("run_key") == key for e in errors):
            append(out / "errors.jsonl", dict(run_key=key, code=row["failure_category"]))
    frozen = canonical(read_json(parameter_path)) if parameter_path.exists() else None
    return list(scores.values()), [r["state"] for r in raws.values()], set(raws), frozen
