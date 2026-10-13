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
)
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.incidentbench.scorer import aggregate, score_benchmark_run
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
    from incident_lens.incidentbench.oracle_store import OracleStore

    dataset = json.loads(
        (args.input.parent / "experiment-context.json").read_text(encoding="utf-8")
    )["dataset_root"]
    verify_lock(lock, dataset, protocol)
    digests = json.loads((args.input.parent / "artifact-digests.json").read_text(encoding="utf-8"))
    for name, digest in digests.items():
        if hashlib.sha256((args.input.parent / name).read_bytes()).hexdigest() != digest:
            raise ValueError("saved artifact digest mismatch")
    raw = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
    if len({r["run_key"] for r in raw}) != len(raw):
        raise ValueError("duplicate saved run key")
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
    _, _, cases = load_cases(dataset, context["split"])
    metadata_index = {c.incident_id: c.model_dump(mode="json") for c in cases}
    for run in raw:
        state, metadata = run["state"], run["metadata"]
        if (
            metadata != metadata_index[run["incident_id"]]
            or state["incident_id"] != run["incident_id"]
            or state["run_id"] != run["run_id"]
        ):
            raise ValueError("saved run identity/metadata mismatch")
        receipt = state["completion_receipt"]
        saved_state = {k: v for k, v in state.items() if k != "completion_receipt"}
        if hashlib.sha256(canonical(saved_state)).hexdigest() != receipt["sha256"] or Path(
            receipt["path"]
        ).read_bytes() != canonical(saved_state):
            raise ValueError("saved state receipt mismatch")
        # Development Test must remain unscored even in a privileged analysis.
        oracle = (
            OracleStore(args.oracle_root, public_root=dataset).load_after_completion(
                run["incident_id"], state
            )
            if args.oracle_root and metadata["split"] != "test" and state.get("report")
            else None
        )
        row = {
            k: run[k]
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
            **run["usage"],
            **score_benchmark_run(state, oracle),
        )
        if oracle and row.get("oracle_sha256") != original[run["run_key"]].get("oracle_sha256"):
            raise ValueError("oracle label digest mismatch")
        row["score_error"] = original[run["run_key"]].get("score_error")
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
    print(json.dumps({"recomputed_runs": len(rows), "out": str(args.out)}))


if __name__ == "__main__":
    main()
