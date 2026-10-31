"""Per-case 4-architecture comparison over normally-completed runs only.

Scope: batch next-api-max8-20261022-121153. A slot enters the analysis set only
when its selected attempt is a NORMAL COMPLETION (lifecycle=completed and no
runtime failure). Slots not completed due to network / API-provider /
output-protocol technical failures are excluded from the comparison and only
listed with their failure reason.

Read-only: frozen batch artifacts only; writes stay inside this report dir.
Outputs: per-case.csv, per-case.json, summary.zh-CN.md data block (stdout).
"""

import csv
import json
import os
from datetime import datetime, timezone

BATCH = os.path.join(
    "results", "v16", "wp-d", "next-api-max8-20261022-121153"
)
OUT = os.path.dirname(os.path.abspath(__file__))

VARIANT_ORDER = ["full", "single", "fixed", "dynamic_no_verifier"]
VARIANT_SHORT = {
    "full": "Full",
    "single": "Single",
    "fixed": "Fixed",
    "dynamic_no_verifier": "NoVerifier",
}

# termination reason -> human-readable exclusion cause (zh-CN)
REASON_ZH = {
    "UNRECOVERABLE_ERROR": "不可恢复错误（补跑证实为 API 通道 429 限流类传输失败）",
    "RATE_LIMITED": "HTTP 429 限流",
    "SCHEMA_VALIDATION_FAILED": "结构化输出 schema 校验失败",
    "BUDGET_EXHAUSTED": "保存为预算耗尽（终止分类异常，非实际上限）",
    "PROVIDER_TRANSPORT_ERROR": "提供商传输错误",
    "UNKNOWN_PROVIDER_ERROR": "未知提供商错误",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_attempt(slot_dir, attempt_rel):
    path = os.path.join(slot_dir, attempt_rel)
    scope = load_json(os.path.join(path, "scope.json"))
    rec = {
        "path": attempt_rel,
        "variant": scope.get("variant"),
        "incident": scope.get("incident_id"),
        "elapsed_sec": None,
        "physical_requests": None,
        "tool_calls": None,
        "result_status": None,
        "termination_reason": None,
        "runtime_failure": None,
        "workflow_status": None,
        "lifecycle": None,
        "stop_reason": None,
    }
    stp = os.path.join(path, "observability", "status.json")
    if os.path.isfile(stp):
        st = load_json(stp)
        rec["lifecycle"] = st.get("lifecycle")
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
        try:
            s = datetime.strptime(st["started_at"], fmt)
            e = datetime.strptime(st["ended_at"], fmt)
            rec["elapsed_sec"] = round((e - s).total_seconds(), 1)
        except (KeyError, ValueError, TypeError):
            rec["elapsed_sec"] = None
        rec["physical_requests"] = st.get("physical_requests")
        rec["tool_calls"] = st.get("tool_calls")
    rsp = os.path.join(path, "result.json")
    if os.path.isfile(rsp):
        res = load_json(rsp)
        rec["result_status"] = res.get("status")
        term = res.get("termination") or {}
        rec["termination_reason"] = term.get("reason")
        rec["runtime_failure"] = term.get("runtime_failure")
        rec["workflow_status"] = res.get("workflow_status")
        rec["stop_reason"] = res.get("stop_reason")
    return rec


def classify(rec):
    if rec["lifecycle"] != "completed" or rec["result_status"] is None:
        return "technical_failure"
    if rec["runtime_failure"] or rec["workflow_status"] == "FAILED":
        return "technical_failure"
    return "normal_completion"


def main():
    manifest = load_json(os.path.join(BATCH, "batch-manifest.json"))
    state = load_json(os.path.join(BATCH, "batch-state.json"))
    order = manifest["order"]
    runs_root = os.path.join(BATCH, "runs")

    # selected attempt per slot (first normal completion, else original)
    selected = {}
    for idx in range(1, len(order) + 1):
        slot_id = f"slot-{idx:03d}"
        slot_dir = os.path.join(runs_root, slot_id)
        recs = []
        for att in state["slots"].get(slot_id, []):
            rec = read_attempt(slot_dir, os.path.basename(att["path"]))
            rec["slot"] = slot_id
            rec["class"] = classify(rec)
            recs.append(rec)
        pick = next((r for r in recs if r["class"] == "normal_completion"), None)
        if pick is None:
            pick = next((r for r in recs if r["path"] == "attempt-001"), None)
        if pick is None and recs:
            pick = recs[0]
        selected[slot_id] = pick

    # analysis set: only normally-completed selected runs
    completed = {
        sid: rec for sid, rec in selected.items()
        if rec["class"] == "normal_completion"
    }
    excluded = {
        sid: rec for sid, rec in selected.items()
        if rec["class"] != "normal_completion"
    }

    # per incident x variant grid
    cases = {}
    for sid, rec in selected.items():
        incident = rec["incident"]
        cases.setdefault(incident, {})[rec["variant"]] = {
            "slot": sid,
            "class": rec["class"],
            "elapsed_sec": rec["elapsed_sec"],
            "physical_requests": rec["physical_requests"],
            "tool_calls": rec["tool_calls"],
            "result_status": rec["result_status"],
            "termination_reason": rec["termination_reason"],
            "selected_attempt": rec["path"],
        }

    out = {
        "batch": "next-api-max8-20261022-121153",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_set": "selected attempts that are normal completions only",
        "n_completed": len(completed),
        "n_excluded": len(excluded),
        "per_case": cases,
    }
    with open(os.path.join(OUT, "per-case.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "per-case.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "incident", "variant", "slot", "selected_attempt", "class",
                "elapsed_sec", "elapsed_min", "physical_requests",
                "tool_calls", "result_status", "abstained", "termination_reason",
            ]
        )
        for incident in sorted(cases):
            for v in VARIANT_ORDER:
                if v not in cases[incident]:
                    continue
                c = cases[incident][v]
                writer.writerow(
                    [
                        incident, v, c["slot"], c["selected_attempt"],
                        c["class"], c["elapsed_sec"],
                        round((c["elapsed_sec"] or 0) / 60.0, 2),
                        c["physical_requests"], c["tool_calls"],
                        c["result_status"],
                        "yes" if c["result_status"] == "INCONCLUSIVE" else "no",
                        c["termination_reason"],
                    ]
                )

    # console digest
    print(f"completed slots: {len(completed)}  excluded: {len(excluded)}")
    print("excluded slots:", sorted(excluded))
    print()
    hdr = f"{'case':10s} " + " ".join(f"{VARIANT_SHORT[v]:>22s}" for v in VARIANT_ORDER)
    print(hdr)
    for incident in sorted(cases):
        cells = []
        for v in VARIANT_ORDER:
            c = cases[incident].get(v)
            if c is None:
                cells.append(f"{'missing':>22s}")
            elif c["class"] != "normal_completion":
                cells.append(f"{'EXCLUDED':>22s}")
            else:
                abst = "弃答" if c["result_status"] == "INCONCLUSIVE" else "出根因"
                cells.append(
                    f"{c['elapsed_sec']/60:6.1f}m {c['physical_requests']:3d}rq "
                    f"{c['tool_calls']:2d}t {abst:>4s}"
                )
        print(f"{incident:10s} " + " ".join(cells))


if __name__ == "__main__":
    main()
