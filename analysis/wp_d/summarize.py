"""Standalone, stdlib-only artifact reader; never imports IncidentLens runtime."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class Reader:
    def __init__(self):
        self.inputs = {}
        self.errors = []

    def read(self, path):
        if not path.exists():
            return {}
        try:
            data = path.read_bytes()
            value = json.loads(data.decode("utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("expected JSON object")
            self.inputs[str(path)] = hashlib.sha256(data).hexdigest()
            return value
        except (OSError, UnicodeError, ValueError) as exc:
            self.errors.append({"path": str(path), "error_type": type(exc).__name__})
            return {}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest() if value else None


def classify(result, verification):
    if not result or not verification:
        return "incomplete"
    if verification.get("protocol_valid") is False:
        return "protocol_invalid"
    if verification.get("source_unchanged") is False:
        return "source_drift"
    termination = verification.get("termination", {})
    if (verification.get("runtime_failure") is True
            or termination.get("runtime_failure") is True
            or termination.get("outcome") == "FAILED"
            or result.get("workflow_status") == "FAILED"):
        return "runtime_failure"
    if (verification.get("protocol_valid") is not True
            or verification.get("stop_completion") is not True):
        return "unverified_terminal"
    if result.get("status") == "INCONCLUSIVE" and result.get("root_cause") is None:
        return "normal_abstention_candidate"
    if result.get("root_cause") is not None:
        return "diagnosis_candidate"
    return "unverified_terminal"


def summarize(root):
    reader = Reader()
    order = reader.read(root / "run-order.json")
    schedule = order.get("frozen_run_order", [])
    selection = reader.read(root / "final-selection.json")
    replacements = selection.get("replacements", [])
    schedule = [dict(item) for item in schedule]
    excluded = set()
    for replacement in replacements:
        matches = [item for item in schedule if item["slot"] == replacement["slot"]]
        if len(matches) != 1 or matches[0]["out"] != replacement["original_out"]:
            raise ValueError("final selection does not match frozen schedule")
        target = root / replacement["selected_out"]
        if not target.resolve().is_relative_to(root):
            raise ValueError("selected path escapes input root")
        for name in ("scope.json", "result.json", "verification.json"):
            if not (target / name).is_file():
                raise ValueError("selected attempt is incomplete")
        matches[0]["original_out"] = matches[0]["out"]
        matches[0]["out"] = replacement["selected_out"]
        excluded.update(replacement.get("excluded_attempts", []))
    expected = {item["out"]: item for item in schedule}
    if len(expected) != len(schedule) or excluded.intersection(expected):
        raise ValueError("duplicate or excluded selected matrix cell")
    folders = set(expected)
    # Include extra attempts separately; never choose the best attempt per cell.
    for name in ("scope.json", "result.json", "verification.json"):
        folders.update(str(p.parent.relative_to(root)) for p in root.rglob(name)
                       if "observability" not in p.parts)
    rows = []
    for folder in sorted(folders - excluded):
        base = root / folder
        if not base.resolve().is_relative_to(root):
            raise ValueError("schedule path escapes input root")
        item = expected.get(folder, {})
        scope = reader.read(base / "scope.json")
        result = reader.read(base / "result.json")
        verification = reader.read(base / "verification.json")
        trace = reader.read(base / "trace.json")
        state = trace.get("state", {})
        events = state.get("events", [])
        timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
        elapsed = None
        if len(timestamps) >= 2:
            try:
                elapsed = (datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
                           - datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))).total_seconds()
            except ValueError:
                pass
        incident = scope.get("incident_id", result.get("incident_id", item.get("incident_id")))
        variant = scope.get("variant", item.get("variant_cli"))
        mismatches = []
        if item and (incident != item.get("incident_id") or variant != item.get("variant_cli")):
            mismatches.append("schedule_identity_mismatch")
        if result.get("incident_id") and result["incident_id"] != incident:
            mismatches.append("result_identity_mismatch")
        row = {
            "slot": item.get("slot"), "attempt_dir": folder,
            "scheduled_original": bool(item), "incident_id": incident, "variant": variant,
            "frozen_original_dir": item.get("original_out", folder) if item else None,
            "selected_replacement": bool(item.get("original_out")),
            "category": item.get("category"), "run_id": result.get("run_id"),
            "classification": classify(result, verification), "identity_warnings": mismatches,
            "status": result.get("status"), "root_cause": result.get("root_cause"),
            "termination_reason": verification.get("termination_reason"),
            "failure_stage": verification.get("termination", {}).get("failure_stage"),
            "source_unchanged": verification.get("source_unchanged"),
            "protocol_valid": verification.get("protocol_valid"),
            "stop_completion": verification.get("stop_completion"),
            "elapsed_event_seconds": elapsed, "elapsed_basis": "first_to_last_trace_event",
            "protocol_fingerprint": fingerprint(scope.get("protocol")),
            "source_fingerprint": fingerprint(scope.get("retest_source_sha256")),
            "dataset_revision": scope.get("dataset_revision"),
            "prompt_version": trace.get("prompt_version"),
            "model_id": scope.get("protocol", {}).get("model_id"),
            "diagnosis_correct": None, "evidence_supported": None,
            "abstention_appropriate": None, "manual_review": "pending",
        }
        for key in ("actual_http_requests", "logical_structured_calls", "total_tokens",
                    "prompt_tokens", "completion_tokens", "cost_usd", "provider_failures",
                    "task_retries", "repair_requests", "query_gap_count"):
            row[key] = verification.get(key)
        row["tokens_complete"] = row["total_tokens"] is not None
        if mismatches:
            row["classification"] = "identity_mismatch"
        rows.append(row)
    groups = {}
    for variant in sorted({r["variant"] for r in rows if r["variant"]}):
        original = [r for r in rows if r["variant"] == variant and r["scheduled_original"]]
        counts = {}
        for row in original:
            key = row["classification"]
            counts[key] = counts.get(key, 0) + 1
        groups[variant] = {"scheduled_cells": len(original), "classifications": counts}
        for metric in ("actual_http_requests", "total_tokens", "cost_usd", "elapsed_event_seconds"):
            known = [r[metric] for r in original if type(r[metric]) in (int, float)]
            groups[variant][metric] = {"known_sum": sum(known) if known else None,
                                      "known_count": len(known), "unknown_count": len(original)-len(known)}
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_root": str(root), "snapshot_only": True, "expected_cells": len(schedule),
            "rows": rows, "by_variant_original_attempts": groups,
            "selection_basis": "user_authorized_final_selection" if replacements else "frozen_original_attempts",
            "final_selection": selection,
            "by_variant_selected_attempts": groups if replacements else None,
            "comparability": {key: sorted({str(r[key]) for r in rows if r[key] is not None})
                              for key in ("source_fingerprint", "protocol_fingerprint", "dataset_revision", "model_id")},
            "read_errors": reader.errors, "input_sha256": reader.inputs,
            "caveats": ["Development-visible exploratory pilot; no formal accuracy claim.",
                        "T6/T5 pre-gates waived by user; strict G1a remains unclosed.",
                        "Candidates require evaluator/manual evidence review; no oracle read.",
                        "Missing artifacts do not establish whether a process is alive.",
                        "Unknown usage is not zero; extra attempts stay separate unless explicitly excluded.",
                        "With final-selection.json, legacy by_variant_original_attempts contains selected cells; use selection_basis and by_variant_selected_attempts."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.input.resolve(), args.out.resolve()
    report_root = Path(__file__).resolve().parent / "reports"
    if not out.is_relative_to(report_root.resolve()) or out == report_root.resolve():
        parser.error("output must be a new subdirectory of analysis/wp_d/reports")
    if not root.is_dir() or out.is_relative_to(root) or root.is_relative_to(out):
        parser.error("input must exist; output must be a fresh directory separate from input")
    # No partial output until all reads finish; refuse overwrite of any prior report.
    report = summarize(root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "attempts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        rows = report["rows"]
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                 for k, v in row.items()})
    lines = ["# WP-D artifact snapshot", "", *[f"- {c}" for c in report["caveats"]], "",
             "| Attempt | Case | Architecture | Classification | HTTP | Tokens |", "|---|---|---|---|---|---|"]
    for row in report["rows"]:
        values = [row[k] for k in ("attempt_dir", "incident_id", "variant", "classification", "actual_http_requests", "total_tokens")]
        lines.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") if v is not None else "unknown" for v in values) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(report['rows'])} attempt rows to {out}")


if __name__ == "__main__":
    main()
