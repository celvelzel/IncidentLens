"""Recompute saved raw states without calling any provider or Graph."""

import argparse
import hashlib
import json
from pathlib import Path

from incident_lens.evaluation.runner import write_csv
from incident_lens.incidentbench.experiment import (
    canonical,
    durable_write,
    export_paired,
    load_cases,
    run_identity,
    run_order,
    score_saved_raw,
)
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.incidentbench.scorer import aggregate
from incident_lens.incidentbench.statistics import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--oracle-root", type=Path)
    args = parser.parse_args()
    protocol = ExperimentProtocol.model_validate_json(
        (args.input.parent / "protocol.json").read_bytes()
    )
    lock = json.loads((args.input.parent / "protocol.lock.json").read_text(encoding="utf-8"))
    from incident_lens.incidentbench.manifest import verify_lock
    from incident_lens.incidentbench.oracle_store import safe_path

    dataset = json.loads(
        (args.input.parent / "experiment-context.json").read_text(encoding="utf-8")
    )["dataset_root"]
    verify_lock(lock, dataset, protocol)
    digests = json.loads((args.input.parent / "artifact-digests.json").read_text(encoding="utf-8"))
    expected_files = {"raw-runs.jsonl", "scores.jsonl", "protocol.json", "experiment-context.json"}
    if set(digests) != expected_files:
        raise ValueError("saved artifact digest contract mismatch")
    if hashlib.sha256(safe_path(args.input).read_bytes()).hexdigest() != digests["raw-runs.jsonl"]:
        raise ValueError(
            "analysis input digest mismatch: must match the complete hashed raw ledger"
        )
    for name, digest in digests.items():
        if hashlib.sha256(safe_path(args.input.parent / name).read_bytes()).hexdigest() != digest:
            raise ValueError("saved artifact digest mismatch")
    raw = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
    if len({r["run_key"] for r in raw}) != len(raw):
        raise ValueError("duplicate saved run key")
    order = json.loads(safe_path(args.input.parent / "run-order.json").read_bytes())
    expected_keys = [f"{incident}.{variant}.repeat-{repeat}" for incident, repeat, variant in order]
    if [run["run_key"] for run in raw] != expected_keys:
        raise ValueError("analysis requires every attempted key in the locked run order")
    rows = []
    original = {
        r["run_key"]: r
        for r in [
            json.loads(line)
            for line in (args.input.parent / "scores.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
    }
    context = json.loads(
        (args.input.parent / "experiment-context.json").read_text(encoding="utf-8")
    )
    if set(original) != set(expected_keys):
        raise ValueError("saved score keys must match the complete raw ledger")
    _, _, cases = load_cases(dataset, context["split"])
    if order != [list(item) for item in run_order([case.incident_id for case in cases], protocol)]:
        raise ValueError("saved run order differs from the frozen seeded schedule")
    metadata_index = {c.incident_id: c.model_dump(mode="json") for c in cases}
    for run in raw:
        state, metadata = run["state"], run["metadata"]
        if (
            metadata != metadata_index[run["incident_id"]]
            or state["incident_id"] != run["incident_id"]
            or state["run_id"] != run["run_id"]
            or run["run_id"] != run_identity(context["experiment_id"], run["run_key"])
        ):
            raise ValueError("saved run identity/metadata mismatch")
        receipt = state["completion_receipt"]
        saved_state = {k: v for k, v in state.items() if k != "completion_receipt"}
        expected_state = safe_path(args.input.parent / "states" / f"{run['run_key']}.json")
        if safe_path(receipt["path"]) != expected_state or (
            hashlib.sha256(canonical(saved_state)).hexdigest() != receipt["sha256"]
            or expected_state.read_bytes() != canonical(saved_state)
        ):
            raise ValueError("saved state receipt mismatch")
        # The same completion-gated evaluator path preserves oracle errors and
        # blocks development Test labels without ever constructing a provider.
        row = score_saved_raw(run, args.oracle_root, dataset)
        original_digest = original[run["run_key"]].get("oracle_sha256")
        if (
            args.oracle_root
            and original_digest is not None
            and row.get("oracle_sha256") != original_digest
        ):
            raise ValueError("oracle label digest mismatch")
        rows.append(row)
    args.out.mkdir(parents=True, exist_ok=False)
    write_csv(args.out / "case-level.csv", rows)
    durable_write(args.out / "aggregate.json", aggregate(rows))
    write_csv(args.out / "aggregate.csv", aggregate(rows))
    durable_write(
        args.out / "statistical-analysis.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    export_paired(args.out, rows, protocol)
    from incident_lens.evaluation.v16 import write_companion

    write_companion(args.out, rows)
    durable_write(args.out / "score-recomputation.json", {
        "attempted_n": len(rows),
        "exact_scores_equal": rows == list(original.values()),
        "oracle_supplied": args.oracle_root is not None,
    })
    print(json.dumps({"recomputed_runs": len(rows), "out": str(args.out)}))


if __name__ == "__main__":
    main()
