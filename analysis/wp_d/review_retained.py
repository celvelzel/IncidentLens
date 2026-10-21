"""Read saved traces only; export completed-run resource and citation inspection.

This is not a scorer and cannot certify semantic support or correctness. It never
imports the runtime, reads an oracle or invokes tools/providers.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def review(batch, out):
    rows, audit, sources = [], [], {}
    for run in sorted(batch.glob("run-*")):
        if not run.is_dir() or not (run / "verification.json").is_file():
            continue
        files = {}
        for name in ("trace.json", "verification.json", "result.json", "scope.json"):
            path = run / name
            files[name] = json.loads(path.read_bytes())
            sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        trace, verification, result, scope = (files[n] for n in
                                             ("trace.json", "verification.json", "result.json", "scope.json"))
        state = trace["state"]
        evidence = state["evidence_index"]
        events = state["events"]
        observed = {}
        for event in events:
            if event["event_type"] == "TOOL_CALL":
                call = event["details"].get("result", {})
                if call.get("ok"):
                    observed.update({record["evidence_id"]: record for record in call.get("records", [])})
        cited = result.get("supporting_evidence_ids", [])
        rows.append({
            "run": run.name, "incident": state["incident_id"], "variant": scope["variant"],
            "status": result["status"], "requests": verification["llm_requests"],
            "repairs": verification["repair_requests"], "tools": state["tool_calls_used"],
            "rounds": state["round_index"], "observed_evidence": len(evidence),
            "reviews": len(state["reviews"]),
            "blocking_review_verdicts": sum(r["verdict"] != "sufficient" for r in state["reviews"]),
            "finalize_rejections": sum(e["event_type"] == "FINALIZE_REJECTED" for e in events),
            "support_reobserved": all(eid in observed for eid in cited),
            "elapsed_ms": trace.get("elapsed_ms"),
        })
        audit.append({"run": run.name, "support": [evidence.get(eid) for eid in cited],
                      "support_missing_observation": [eid for eid in cited if eid not in observed],
                      "rejected": [{"failure_mode": h["failure_mode"],
                                    "contrary_records": [evidence.get(eid) for eid in h["against_ids"]]}
                                   for h in result.get("rejected_hypotheses", [])],
                      "stop_reason": result.get("stop_reason"),
                      "tool_event_counts": dict(Counter(e["details"].get("tool_name") for e in events
                                                        if e["event_type"] == "TOOL_CALL"))})
    totals = defaultdict(Counter)
    for row in rows:
        totals[row["variant"]].update({key: row[key] for key in
                                       ("requests", "repairs", "tools", "rounds", "reviews", "finalize_rejections")})
    out.mkdir(parents=True, exist_ok=False)
    with (out / "per-run.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "inspection.json").write_text(json.dumps({
        "scope": "read-only artifact inspection; selected completed runs only; no semantic scoring",
        "per_variant": dict(totals), "citations": audit, "input_sha256": sources,
        "historical_elapsed_note": "Missing elapsed_ms remains null; operator serving time is not API latency.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    review(options.batch, options.out)
