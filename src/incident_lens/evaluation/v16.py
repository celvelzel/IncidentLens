"""Failure-inclusive V16 companion metrics; never reinterpret legacy match scores."""

import json
from collections import Counter
from pathlib import Path


def quality_row(row):
    """Consume completion-gated scorer output, never load evaluator labels here."""
    labelled = row.get("identifiable") is not None
    identifiable = row.get("identifiable")
    reviewed = row.get("human_grounded_success")
    return {
        "run_key": row["run_key"],
        "variant": row["variant"],
        "incident_id": row["incident_id"],
        "technical_completion": bool(row["technical_completion"]),
        "runtime_failure": bool(row.get("runtime_failure")),
        "budget_exhausted": row.get("termination_reason") == "BUDGET_EXHAUSTED",
        "mechanism_service_match": row.get("root_cause_correct"),
        "semantic_supported_root_cause_correct": reviewed if identifiable else None,
        "false_resolution": (
            bool(row.get("resolved") and (not identifiable or not row["root_cause_correct"]))
            if labelled else None
        ),
        "identifiable": identifiable,
        "correct_abstention": row.get("correct_abstention"),
        "citation_existence_validity": row.get("citation_existence_validity"),
        "citation_semantic_support": row.get("human_support_rate"),
        "failure_category": row.get("failure_category"),
    }


def rate(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return {"numerator": sum(values), "denominator": len(values),
            "rate": sum(values) / len(values) if values else None}


def summarize(rows):
    output = []
    for variant in sorted({r["variant"] for r in rows}):
        group = [r for r in rows if r["variant"] == variant]
        item = {"variant": variant, "attempted_n": len(group)}
        for field, name in (
            ("technical_completion", "technical_completion_rate"),
            ("runtime_failure", "runtime_failure_rate"),
            ("budget_exhausted", "budget_exhausted_rate"),
            ("mechanism_service_match", "mechanism_service_match_rate"),
            ("correct_abstention", "correct_abstention_rate"),
            ("false_resolution", "false_resolution_rate"),
        ):
            item[name] = rate(group, field)
        # Partial review cannot silently replace the all-attempt primary denominator.
        diagnosed = [r for r in group if r["identifiable"] is True]
        reviewed = [r for r in diagnosed
                    if r["semantic_supported_root_cause_correct"] is not None]
        item["root_cause_correct_rate"] = {
            "numerator": sum(r["semantic_supported_root_cause_correct"] for r in reviewed)
            if diagnosed and len(reviewed) == len(diagnosed) else None,
            "denominator": len(diagnosed),
            "reviewed_n": len(reviewed),
            "rate": rate(reviewed, "semantic_supported_root_cause_correct")["rate"]
            if diagnosed and len(reviewed) == len(diagnosed) else None,
        }
        for identifiable, name in ((True, "identifiable"), (False, "missing")):
            item[f"false_resolution_{name}_rate"] = rate(
                [r for r in group if r["identifiable"] is identifiable], "false_resolution")
        item["failure_counts"] = dict(Counter(
            r["failure_category"] or "UNKNOWN" for r in group
            if not r["technical_completion"]))
        output.append(item)
    return output


def write_companion(out, scores):
    """Write separate artifacts so historical score files keep their exact meaning."""
    rows = [quality_row(row) for row in scores]
    payload = {
        "schema": "v16-evaluation-v1", "rows": rows, "aggregate": summarize(rows),
        "independence_status": "not_established", "ci95": None, "p_value": None,
        "evidence_level": "OFFLINE_MOCK" if all(r.get("source") == "mock" for r in scores)
        else "LIVE_DEVELOPMENT",
        "limitations": [
            "Historical root_cause_correct is service/mechanism match only.",
            "Semantic quality stays null without complete human review.",
            "False resolution uses labelled mechanism match, not semantic review.",
            "Source lineage independence is unreviewed; descriptive results only.",
        ],
    }
    path = Path(out) / "v16-metrics.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
    return payload
