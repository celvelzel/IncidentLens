"""Inventory the retained twelve executions without inventing decision snapshots."""

import hashlib
import json
from pathlib import Path

from incident_lens.prompts.resolver import canonical


def audit_retained(root, out):
    root = Path(root)
    manifest = root / "analysis/wp_d/reports/retained-trace-review-20261021/inspection.json"
    inspection = json.loads(manifest.read_text(encoding="utf-8"))
    rows, worksheet = [], []
    for recorded, expected_hash in inspection["input_sha256"].items():
        if not recorded.endswith("trace.json"):
            continue
        path = root.joinpath(*recorded.replace("\\", "/").split("/"))
        entry = {"path": path.relative_to(root).as_posix(), "available": path.is_file(),
                 "expected_sha256": expected_hash, "exact_predecision_input": False}
        if path.is_file():
            raw = path.read_bytes()
            entry["actual_sha256"] = hashlib.sha256(raw).hexdigest()
            entry["hash_matches"] = entry["actual_sha256"] == expected_hash
            if not entry["hash_matches"]:
                raise ValueError("retained artifact changed")
            state = json.loads(raw)["state"]
            entry.update(incident_id=state["incident_id"], findings=len(state["findings"]),
                         reviews=len(state["reviews"]))
            for hypothesis in state["hypotheses"]:
                if not hypothesis["against_ids"]:
                    continue
                worksheet.append({"trace": entry["path"], "hypothesis": hypothesis,
                                  "contrary_records": [state["evidence_index"].get(eid)
                                                       for eid in hypothesis["against_ids"]],
                                  "annotation_status": "pending_human_review",
                                  "error_owner": "unknown", "prompt_fixable": "unknown",
                                  "note": "Final board may include coordinator reconciliation; "
                                  "do not attribute an error to Analysis or Verifier from this alone."})
        rows.append(entry)
    target = Path(out)
    target.mkdir(parents=True, exist_ok=False)
    report = {"source": str(manifest.relative_to(root)), "executions": rows,
              "available_traces": sum(r["available"] for r in rows),
              "usable_training_snapshots": 0,
              "decision": "GO for engineering prototype; NO-GO for quality or deployment claims",
              "limitations": ["No historical final state is relabeled as pre-decision input.",
                              "Missing retained files remain missing; no replacement trace selected.",
                              "Existing six-of-eight review is exploratory, not adjudicated gold."]}
    (target / "audit.json").write_text(canonical(report) + "\n", encoding="utf-8")
    (target / "review-worksheet.jsonl").write_text("".join(canonical(r) + "\n" for r in worksheet),
                                                  encoding="utf-8")
    return report
