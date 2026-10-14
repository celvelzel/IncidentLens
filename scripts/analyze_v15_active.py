"""Recompute complete hashed saved ledgers without provider or oracle access."""

import argparse
import hashlib
import json
from pathlib import Path

from incident_lens.evaluation.active_evidence.metrics import selection_metrics
from incident_lens.evaluation.active_evidence.statistics import analyze
from incident_lens.evaluation.active_evidence.variants import ActiveProtocol
from incident_lens.evaluation.runner import write_csv
from incident_lens.incidentbench.experiment import durable_write, read_jsonl, score_saved_raw


def analyze_saved(folder):
    digests = json.loads((folder / "artifact-digests.json").read_bytes())
    for name, expected in digests.items():
        if (
            Path(name).name != name
            or hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("artifact hash mismatch")
    raw = read_jsonl(folder / "raw-runs.jsonl")
    order = json.loads((folder / "run-order.json").read_bytes())
    expected = [f"{i}.{v}.repeat-{r}" for i, r, v in order]
    if [r["run_key"] for r in raw] != expected:
        raise ValueError("incomplete or duplicate ledger")
    context = json.loads((folder / "experiment-context.json").read_bytes())
    rows = []
    for r in raw:
        state = r["state"]
        receipt = state["completion_receipt"]
        path = folder / "states" / f"{r['run_key']}.json"
        saved = json.loads(path.read_bytes())
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"] or saved != {
            k: v for k, v in state.items() if k != "completion_receipt"
        }:
            raise ValueError("state receipt mismatch")
        row = score_saved_raw(r, None, context["dataset_root"])
        row.update(selection_metrics(state))
        rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    rows = analyze_saved(a.input)
    protocol = ActiveProtocol.model_validate_json((a.input / "protocol.json").read_bytes())
    a.out.mkdir(parents=True, exist_ok=False)
    write_csv(a.out / "case-level.csv", rows)
    durable_write(
        a.out / "uncertainty.json",
        analyze(rows, seed=protocol.analysis_seed, samples=protocol.bootstrap_samples),
    )
    print(json.dumps(dict(recomputed_runs=len(rows))))


if __name__ == "__main__":
    main()
