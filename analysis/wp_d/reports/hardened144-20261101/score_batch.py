"""Score the frozen 144-slot hardened WP-D batch offline against the evaluator oracle.

Read-only over ``results/v16/wp-d/full144-hardened-c4-20261101``: the batch state and
per-attempt artifacts are never rewritten. The only write is
``final-success-comparison.json`` in the batch directory.

Scoring rule (same contract as the 40-slot local-gateway batch):

* identifiable case -> success requires ``RESOLVED`` with an exact
  ``culprit_service`` **and** ``failure_mode`` match against the oracle;
* unidentifiable case -> success requires a normal ``INCONCLUSIVE`` abstention;
* a technical failure is never scored as a wrong diagnosis: its correctness fields
  stay ``null`` and it counts only in the failure-inclusive denominator.

Labels are provisional: every oracle has ``annotator_status: pending``.

Usage (repository root):

    .venv/Scripts/python.exe analysis/wp_d/reports/hardened144-20261101/score_batch.py
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from incident_lens.incidentbench.scorer import score_benchmark_run
from incident_lens.incidentbench.schemas import BenchmarkOracle
from incident_lens.variants import canonical_name

BATCH = Path("results/v16/wp-d/full144-hardened-c4-20261101")
ORACLE_ROOT = Path("local_oracles/incidentbench_v2_hardened/rca/incidents")
INDEX = Path("data/incidentbench_v2_hardened/public_case_index.json")
OUT = BATCH / "final-success-comparison.json"
ORDER = ("single", "fixed", "dynamic", "full")
LABELS = {
    "single": "Single",
    "fixed": "Fixed-4",
    "dynamic": "Dynamic (primary)",
    "full": "Full (dynamic with verifier)",
}


def load_oracle(incident_id):
    path = ORACLE_ROOT / incident_id / "private" / "benchmark_oracle.json"
    return BenchmarkOracle.model_validate(json.loads(path.read_text(encoding="utf-8")))


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lever_of(scenario_variant_id):
    """``v2_3_boundary`` -> ``boundary``; counterfactual pair members fold together."""
    if not scenario_variant_id:
        return None
    parts = scenario_variant_id.split("_")
    if any(part.startswith("pair") for part in parts):
        return "counterfactual_pair"
    return parts[2] if len(parts) > 2 else None


def build_record(slot, attempt, oracle, meta):
    root = BATCH / attempt["path"]
    state = load_json(root / "trace.json")["state"]
    verification = load_json(root / "verification.json")
    trace = load_json(root / "trace.json")

    scored = score_benchmark_run(state, oracle)
    technical = bool(scored["technical_completion"])
    report = state.get("report") or {}
    prediction = report.get("root_cause")
    if technical:
        root_correct = scored["root_cause_correct"]
        abstention = scored["correct_abstention"]
        quality = bool(root_correct) if oracle.is_identifiable else bool(abstention)
    else:
        # A runtime failure is not evidence of a wrong diagnosis.
        root_correct = None
        abstention = None
        quality = False

    variant = canonical_name(attempt["key"]["variant"])
    truth = oracle.true_primary_root
    return {
        "slot": slot,
        "incident": attempt["key"]["incident"],
        "variant": variant,
        "variant_label": LABELS.get(variant, variant),
        "attempts_until_success": attempt["_attempts"],
        "attempt_path": attempt["path"],
        "elapsed_s": round(trace["elapsed_ms"] / 1000, 3),
        "requests": verification["actual_http_requests"],
        "tools": state.get("tool_calls_used"),
        "tokens": verification["total_tokens"],
        "prompt_tokens": verification["prompt_tokens"],
        "completion_tokens": verification["completion_tokens"],
        "status": scored.get("termination_reason") or report.get("status"),
        "report_status": report.get("status"),
        "termination_outcome": scored.get("termination_outcome"),
        "failure_stage": (verification.get("termination") or {}).get("failure_stage"),
        "failure_cause": None if technical else report.get("stop_reason"),
        "abstained": bool(scored["abstained"]),
        "identifiable": oracle.is_identifiable,
        "root_cause_correct": root_correct,
        "correct_abstention": abstention,
        "technical_completion": technical,
        "quality_success": quality,
        "prediction": None
        if prediction is None
        else {
            "culprit_service": prediction.get("culprit_service"),
            "failure_mode": prediction.get("failure_mode"),
        },
        "truth": {
            "culprit_service": truth.culprit_service,
            "failure_mode": truth.failure_mode,
            "root_cause_code": truth.root_cause_code,
        },
        "oracle_label_status": oracle.annotator_status,
        "scenario_family_id": oracle.scenario_family_id,
        "lever": lever_of(meta.get("scenario_variant_id")),
        "misleading_case": bool(oracle.misleading_evidence_ids),
        "source_unchanged": verification.get("source_unchanged"),
    }


def summarize(group):
    identifiable = [r for r in group if r["identifiable"]]
    unidentifiable = [r for r in group if not r["identifiable"]]
    scored_root = [r for r in identifiable if r["root_cause_correct"] is not None]
    scored_abs = [r for r in unidentifiable if r["correct_abstention"] is not None]
    completed = [r for r in group if r["technical_completion"]]
    return {
        "variant": group[0]["variant"],
        "variant_label": group[0]["variant_label"],
        "n": len(group),
        "technical_completion": len(completed),
        "technical_completion_rate": round(len(completed) / len(group), 4),
        "identifiable": len(identifiable),
        "root_correct": sum(bool(r["root_cause_correct"]) for r in scored_root),
        "root_scored": len(scored_root),
        "root_accuracy_when_completed": round(
            sum(bool(r["root_cause_correct"]) for r in scored_root) / len(scored_root), 4
        )
        if scored_root
        else None,
        "unidentifiable": len(unidentifiable),
        "correct_abstention": sum(bool(r["correct_abstention"]) for r in scored_abs),
        "abstention_scored": len(scored_abs),
        "abstention_rate_when_completed": round(
            sum(bool(r["correct_abstention"]) for r in scored_abs) / len(scored_abs), 4
        )
        if scored_abs
        else None,
        "quality_success": sum(bool(r["quality_success"]) for r in group),
        "quality_success_rate": round(sum(bool(r["quality_success"]) for r in group) / len(group), 4),
        "quality_success_when_completed": round(
            sum(bool(r["quality_success"]) for r in completed) / len(completed), 4
        )
        if completed
        else None,
        "failed": len(group) - len(completed),
        "avg_elapsed_s": round(statistics.mean(r["elapsed_s"] for r in completed), 1)
        if completed
        else None,
        "avg_requests": round(statistics.mean(r["requests"] for r in completed), 1)
        if completed
        else None,
        "avg_tools": round(statistics.mean(r["tools"] for r in completed), 1)
        if completed
        else None,
        "avg_tokens": round(statistics.mean(r["tokens"] for r in completed), 1)
        if completed
        else None,
        "total_tokens_all_attempts": sum(r["tokens"] for r in group),
        "failed_tokens": sum(r["tokens"] for r in group if not r["technical_completion"]),
    }


def main():
    state = load_json(BATCH / "batch-state.json")
    meta = {row["incident_id"]: row for row in load_json(INDEX)}
    records = []
    try:
        for slot, attempts in sorted(state["slots"].items()):
            if not attempts:
                continue
            attempt = dict(attempts[-1], _attempts=len(attempts))
            incident = attempt["key"]["incident"]
            records.append(build_record(slot, attempt, load_oracle(incident), meta.get(incident, {})))
    except Exception as error:  # surface the first broken slot instead of a partial file
        raise SystemExit(f"scoring failed: {error}") from error

    groups = defaultdict(list)
    for record in records:
        groups[record["variant"]].append(record)
    summary = [summarize(groups[name]) for name in ORDER if name in groups]
    levers = {}
    for lever in ("standard", "boundary", "competing", "missing", "misleading", "counterfactual_pair"):
        levers[lever] = {
            name: {
                "n": sum(1 for r in groups[name] if r["lever"] == lever),
                "quality_success": sum(
                    1 for r in groups[name] if r["lever"] == lever and r["quality_success"]
                ),
            }
            for name in ORDER
            if name in groups
        }

    payload = {
        "scope": (
            f"{len(records)}/{state['executions'][-1]['planned_slots']} slots; every attempt "
            "kept, including technical failures; oracle scored offline after batch completion"
        ),
        "batch": str(BATCH),
        "model_id": load_json(BATCH / "runs" / records[0]["slot"] / "attempt-001" / "scope.json")[
            "protocol"
        ]["model_id"],
        "jobs": 4,
        "oracle_label_status": "provisional (benchmark_oracle annotator_status=pending)",
        "correctness_rule": (
            "identifiable: exact culprit_service AND failure_mode; unidentifiable: INCONCLUSIVE "
            "abstention; technical failure: correctness null, quality_success false"
        ),
        "batch_outcome": state["executions"][-1]["outcome"],
        "batch_elapsed_s": round(state["executions"][-1]["elapsed_seconds"], 1),
        "failure_reasons": dict(
            Counter(
                f"{r['status']}@{r['failure_stage']}" for r in records if not r["technical_completion"]
            )
        ),
        "records": records,
        "summary": summary,
        "lever_breakdown": levers,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"wrote {OUT} ({len(records)} records)\n")
    print("| variant | tech | root cause | abstention | quality | latency | requests | tools | tokens |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summary:
        print(
            f"| {row['variant_label']} | {row['technical_completion']}/{row['n']} "
            f"| {row['root_correct']}/{row['root_scored']} "
            f"| {row['correct_abstention']}/{row['abstention_scored']} "
            f"| {row['quality_success']}/{row['n']} "
            f"| {row['avg_elapsed_s']}s | {row['avg_requests']} | {row['avg_tools']} "
            f"| {row['avg_tokens']:,.0f} |"
        )
    print("\nlever breakdown (quality success):")
    for lever, row in levers.items():
        print("  " + lever, {k: f"{v['quality_success']}/{v['n']}" for k, v in row.items()})


if __name__ == "__main__":
    main()
