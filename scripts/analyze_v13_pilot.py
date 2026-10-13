"""Reconcile a saved pilot without new provider calls or oracle reads."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

from incident_lens.evaluation.reliability_metrics import technical_completion
from incident_lens.evaluation.runner import write_csv


def analyze(source, out):
    rows = list(csv.DictReader((source / "case-level.csv").open(encoding="utf-8")))
    out.mkdir(parents=True, exist_ok=False)
    corrected, details = [], []
    for row in rows:
        state = json.loads(
            (source / row["group"] / row["incident_id"] / "trace.json").read_text(encoding="utf-8")
        )["state"]
        calls = [e for e in state["events"] if e["event_type"] in {"LLM_CALL", "MODEL_FAILURE"}]
        successful = [e for e in calls if e["event_type"] == "LLM_CALL"]

        def repairs(event):
            data = event["details"]
            return data.get(
                "repair_requests",
                max(0, data.get("llm_calls", 0) - 1) if row["group"] == "R0" else 0,
            )

        measured = sum(e["details"].get("measured_total_tokens", 0) for e in calls)
        counts = sum(e["details"].get("llm_calls", 0) for e in calls)
        assert counts == int(row["llm_requests"]), "Trace/physical-count mismatch"
        classifications = Counter(
            e["details"].get("category", "UNKNOWN")
            for e in state["events"]
            if e["event_type"] == "PROVIDER_FAILURE_CLASSIFIED"
        )
        repaired = [e for e in calls if repairs(e)]
        invalid_categories = {"INVALID_JSON", "SCHEMA_VALIDATION_FAILED", "RESPONSE_TRUNCATED"}
        responding = len(successful) + sum(
            e["event_type"] != "LLM_CALL"
            and (
                repairs(e) or e["details"].get("failure", {}).get("category") in invalid_categories
            )
            for e in calls
        )
        info = dict(
            group=row["group"],
            incident_id=row["incident_id"],
            logical_call_success_numerator=len(successful),
            logical_call_success_denominator=len(calls),
            repaired_call_count=len(repaired),
            repaired_call_success=sum(e["event_type"] == "LLM_CALL" for e in repaired),
            structured_validity_before_numerator=sum(not repairs(e) for e in successful),
            structured_validity_after_numerator=len(successful),
            structured_validity_denominator=responding,
            failure_categories=dict(classifications),
            measured_total_tokens_lower_bound=measured,
            actual_request_count=counts,
            logical_call_count=len(calls),
            repair_requests=sum(repairs(e) for e in calls),
            repair_count_method="source-established legacy single-repair inference"
            if row["group"] == "R0"
            else "dispatch usage",
            technical_completion=technical_completion(state),
            rca_accuracy=None,
            correct_abstention=None,
        )
        details.append(info)
        updated = dict(
            row,
            repair_requests=info["repair_requests"],
            logical_structured_calls=len(calls),
            technical_completion=info["technical_completion"],
            measured_total_tokens_lower_bound=measured,
        )
        updated = {k: None if v == "" else v for k, v in updated.items()}
        corrected.append(updated)
    write_csv(out / "case-level-reconciled.csv", corrected)
    summaries = []
    for group in ("R0", "R3"):
        selected = [r for r in corrected if r["group"] == group]
        diagnostics = [d for d in details if d["group"] == group]
        latency = sorted(float(r["latency_seconds"]) for r in selected)
        n = len(selected)
        summaries.append(
            dict(
                group=group,
                sample_count=n,
                technical_completion_numerator=sum(r["technical_completion"] for r in selected),
                technical_completion_denominator=n,
                actual_http_requests=sum(int(r["llm_requests"]) for r in selected),
                measured_total_tokens_lower_bound=sum(
                    d["measured_total_tokens_lower_bound"] for d in diagnostics
                ),
                total_tokens=sum(int(r["total_tokens"]) for r in selected)
                if all(r["total_tokens"] is not None for r in selected)
                else None,
                logical_success_numerator=sum(
                    d["logical_call_success_numerator"] for d in diagnostics
                ),
                logical_success_denominator=sum(
                    d["logical_call_success_denominator"] for d in diagnostics
                ),
                repair_success_numerator=sum(d["repaired_call_success"] for d in diagnostics),
                repair_success_denominator=sum(d["repaired_call_count"] for d in diagnostics),
                latency_p50_seconds=median(latency) if n else None,
                latency_p95_seconds=latency[math.ceil(0.95 * n) - 1] if n else None,
                cost_usd=None,
                rca_accuracy=None,
                correct_abstention=None,
            )
        )
    write_csv(out / "aggregate-reconciled.csv", summaries)
    (out / "diagnostics.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    (out / "README.md").write_text(
        "# Pilot reconciliation\n\nNo new model calls or oracle reads. Original CSV/trace preserved. R0 lacks repair_requests; original CSV's default zero is corrected from frozen legacy single-repair behavior (physical attempts minus first request). New counters are dispatch-derived. Counts reconcile to saved LLM_CALL/MODEL_FAILURE usage. Provider-schema success is separate from terminal technical completion and domain/RCA correctness. Measured tokens are lower bounds; blank totals remain unknown. Full-source hashes were post-launch observations; see source manifest. Small descriptive sample, no improvement claim.\n",
        encoding="utf-8",
    )
    print(json.dumps(summaries))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.source, args.out)


if __name__ == "__main__":
    main()
