"""Rescore saved traces into a new directory, without running a provider."""

import argparse
import hashlib
import json
from pathlib import Path

from incident_lens.evaluation.metrics import aggregate, score_completed, score_without_oracle
from incident_lens.evaluation.runner import load_oracle_after_run, write_csv
from incident_lens.evaluation.termination import SCORING_VERSION


def rescore(source, out, data_root=Path("data")):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out == source.parent or source.is_relative_to(out):
        raise ValueError("output must be separate from input")
    if out.exists():
        raise ValueError("use a new output directory; historical results are preserved")
    contents = source.read_bytes()
    if source.suffix == ".jsonl":
        records = [
            json.loads(line) for line in contents.decode("utf-8").splitlines() if line.strip()
        ]
    else:
        records = [json.loads(contents)]
    if not records:
        raise ValueError("input contains no completed traces")
    rescored, rows = [], []
    for record in records:
        state = record["state"]
        if not isinstance(state.get("report"), dict):
            raise ValueError("rescore requires a completed report before oracle access")
        old = record.get("metrics", {})
        oracle = record.get("oracle_scoring_fields")
        error = None
        try:
            if oracle is None:
                oracle = load_oracle_after_run(data_root, state["incident_id"], state)
            score = score_completed(state, oracle)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            error = type(exc).__name__
            score = score_without_oracle(state)
        row = dict(
            old,
            incident_id=state["incident_id"],
            variant=old.get("variant", record.get("variant", "full")),
            source=old.get("source", record.get("provider", "saved")),
            split=old.get("split", "saved"),
            status=state["report"]["status"],
            evaluation_error=error,
            **score,
        )
        rows.append(row)
        rescored.append(
            dict(record, metrics=row, historical_metrics=old, oracle_scoring_fields=oracle)
        )
    out.mkdir(parents=True, exist_ok=False)
    (out / "raw-runs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rescored), encoding="utf-8"
    )
    write_csv(out / "case-level.csv", rows)
    summaries = []
    for variant in sorted({r["variant"] for r in rows}):
        group = [dict(r, variant="full") for r in rows if r["variant"] == variant]
        summaries.append(dict(aggregate(group)[0], variant=variant))
    write_csv(out / "aggregate.csv", summaries)
    manifest = dict(
        scoring_version=SCORING_VERSION,
        input_path=str(source),
        input_sha256=hashlib.sha256(contents).hexdigest(),
        runs=len(rows),
        evaluation_errors=sum(bool(r["evaluation_error"]) for r in rows),
        provider_executed=False,
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    manifest = rescore(args.input, args.out, args.data_root)
    print(json.dumps(manifest))
    raise SystemExit(2 if manifest["evaluation_errors"] else 0)
