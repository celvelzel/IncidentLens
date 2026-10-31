"""Stdlib-only inspection. No runtime imports, providers, tests or original writes."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BATCH = ROOT / "results/v16/wp-d/next-api-max8-20261022-121153"
EARLIER = ROOT / "analysis/wp_d/reports/next-api-max8-20261022-121153-review"
SCORES = ROOT / "local_oracles/wp-d/next-api-max8-20261022-121153-review/reference-scores.json"


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, obj):
    with (OUT / name).open("w", encoding="utf-8") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def snapshot():
    paths = {SCORES}
    for directory in [BATCH, EARLIER, *[ROOT / p for p in ("src", "scripts", "configs", "prompts", "data")]]:
        paths.update(p for p in directory.rglob("*") if p.is_file())
    paths.update(ROOT / p for p in read(BATCH / "batch-manifest.json")["hashes"])
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def main():
    before = snapshot()
    manifest = read(BATCH / "batch-manifest.json")
    assert all(before[p.replace("\\", "/")] == h for p, h in manifest["hashes"].items())
    scores = {x["slot"]: x for x in read(SCORES)}
    public_metrics = {}
    for case in (ROOT / "data/incidentbench_v16_dev/rca/incidents").iterdir():
        with (case / "public/metrics.csv").open(encoding="utf-8", newline="") as stream:
            public_metrics[case.name] = list(csv.DictReader(stream))
    previous_rows = {x["slot"]: x for x in csv.DictReader((EARLIER / "per-slot.csv").open(encoding="utf-8-sig"))}
    detailed, rows = [], []
    for slot, prev in sorted(previous_rows.items()):
        path = BATCH / prev["attempt"]
        state = read(path / "trace.json")["state"]
        verification = read(path / "verification.json")
        result = read(path / "result.json")
        events = state["events"]
        observed, tools = set(), []
        seen_calls = Counter()
        for event in events:
            if event["event_type"] != "TOOL_CALL":
                continue
            details = event["details"]
            returned = details.get("result", {})
            ids = [r["evidence_id"] for r in returned.get("records", [])] if returned.get("ok") else []
            call_key = json.dumps([details.get("tool_name"), details.get("args")], sort_keys=True)
            if isinstance(details.get("args"), dict):
                seen_calls[call_key] += 1
            new_ids = sorted(set(ids) - observed)
            tools.append({"event_id": event["event_id"], "role": event.get("role"),
                "task_id": details.get("task_id"), "tool": details.get("tool_name"),
                "args": details.get("args"), "ok": returned.get("ok"), "record_ids": ids,
                "new_evidence_ids": new_ids, "exact_query_occurrence":
                    seen_calls[call_key] if isinstance(details.get("args"), dict) else None})
            observed.update(ids)
        oracle = scores[slot]["oracle"]
        target_key = oracle["true_primary_root"]
        target = [h for h in state["hypotheses"] if
                  (h["culprit_service"], h["failure_mode"]) ==
                  (target_key["culprit_service"], target_key["failure_mode"])]
        target_ids = {h["hypothesis_id"] for h in target}
        # Read already receipt-gated evaluator output; never open new oracle files.
        acceptable = [set(x["evidence_ids"]) for x in oracle["acceptable_support_sets"]]
        support_complete = any(s.issubset(observed) for s in acceptable) if acceptable else None
        reference_missing = sorted(set().union(*acceptable) - observed) if acceptable else []
        target_assessments = []
        for event in events:
            details = event["details"]
            assessments = details.get("candidate_assessments", {})
            matched = {h: value for h, value in assessments.items() if h in target_ids}
            if matched:
                target_assessments.append({"event_id": event["event_id"],
                    "type": event["event_type"], "assessments": matched,
                    "errors": details.get("errors", [])})
        final_errors = sorted({err for x in target_assessments[-1:] for a in x["assessments"].values()
                               for err in a.get("finalize_errors", [])})
        target_state = [{k: h[k] for k in ["hypothesis_id", "status", "support_ids", "against_ids", "open_questions"]}
                        for h in target]
        failures = [{"event_id": e["event_id"], "type": e["event_type"], "details": e["details"]}
                    for e in events if e["event_type"] in
                    ["RUNTIME_ERROR", "MODEL_FAILURE", "PROVIDER_FAILURE_CLASSIFIED", "PROVIDER_RETRY_DENIED",
                     "BUDGET_RETRY_DENIED", "STRUCTURED_REPAIR", "PROVIDER_RETRY_SCHEDULED"]]
        reviews = [{"event_id": e["event_id"], "type": e["event_type"], "details": e["details"]}
                   for e in events if e["event_type"] in ["REVIEW", "REVIEW_EFFECT", "REVIEW_FOLLOWUP"]]
        metrics = public_metrics[state["incident_id"]]
        missing_metrics = [r for r in metrics if r["evidence_id"] not in observed]
        comparable = any(e["event_type"] == "FINALIZE_REJECTED" for e in events)
        category = ("resolved_control" if result["status"] == "RESOLVED" else
                    "technical_failure" if prev["technical_status"] == "failed" else
                    "appropriate_missing_evidence_abstention" if not oracle["is_identifiable"] else
                    "identifiable_support_observed_but_abstained" if support_complete else
                    "identifiable_support_not_fully_retrieved")
        row = {"slot": slot, "incident": prev["incident"], "variant": prev["variant"],
            "technical_status": prev["technical_status"], "termination": verification["termination_reason"],
            "category": category, "reference_support_observed": support_complete,
            "target_present": bool(target), "target_status": ";".join(h["status"] for h in target),
            "final_gate_errors": "; ".join(final_errors), "finalize_rejected": comparable,
            "tools": len(tools), "zero_new_evidence_tool_calls": sum(not t["new_evidence_ids"] for t in tools),
            "exact_repeat_tool_calls": sum((t["exact_query_occurrence"] or 0) > 1 for t in tools),
            "postgres_metrics_queries": sum(t["tool"] == "query_metrics" and t["args"].get("service") == "postgres" for t in tools),
            "public_metric_records_not_observed": len(missing_metrics),
            "reviews": len(state["reviews"]), "stop_reason": result["stop_reason"]}
        rows.append(row)
        detailed.append({"summary": row, "last_decision": state["decisions"][-1] if state["decisions"] else None,
            "target_state": target_state, "target_gate_history": target_assessments,
            "all_hypotheses": state["hypotheses"], "tools": tools,
            "failure_events": failures, "reviews": reviews, "verification_verifier": verification["verifier"],
            "missing_public_metrics": missing_metrics,
            "reference_support_missing_count": len(reference_missing),
            "budgets": state["budgets"], "rounds": state["round_index"],
            "llm_requests": verification["actual_http_requests"], "elapsed_ms": verification["elapsed_ms"],
            "runtime_error_n": sum(e["event_type"] == "RUNTIME_ERROR" for e in events)})
    after = snapshot()
    assert before == after, "Protected inputs changed during audit"
    counts = dict(Counter(r["category"] for r in rows))
    assert counts["technical_failure"] == 11
    assert counts["appropriate_missing_evidence_abstention"] == 6
    assert counts["resolved_control"] == 4
    assert sum(v for k, v in counts.items() if k.startswith("identifiable_")) == 19
    write("protected-inputs-before.json", before)
    write("evidence-audit.json", detailed)
    summary = {"batch": str(BATCH), "category_counts": counts,
        "protected_file_count": len(before), "protected_inputs_unchanged": before == after,
        "frozen_input_count": len(manifest["hashes"]),
        "all_frozen_inputs_match_batch_manifest": True,
        "runtime_calls": 0, "provider_calls": 0, "original_writes": 0,
        "reference_basis": "Previously receipt-gated evaluator output; owner-accepted development references, not independent truth.",
        "repeated_tools_all": sum(r["exact_repeat_tool_calls"] for r in rows),
        "zero_new_evidence_tool_calls_all": sum(r["zero_new_evidence_tool_calls"] for r in rows),
        "tools_all": sum(r["tools"] for r in rows),
        "unresolved_with_finalize_rejection": [r["slot"] for r in rows if r["finalize_rejected"] and r["category"] != "resolved_control"]}
    write("audit-summary.json", summary)
    with (OUT / "per-slot-causes.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for row in rows:
        print(row["slot"], row["incident"][-4:], row["variant"], row["category"],
              'support', row["reference_support_observed"], 'gate', row["final_gate_errors"],
              'repeat/zero/new',row["exact_repeat_tool_calls"], row["zero_new_evidence_tool_calls"], row["tools"])


if __name__ == "__main__":
    main()
