"""Read-only aggregation of batch next-api-max8-20261022-121153 (40 slots, 4 variants).

Reads only frozen artifacts under the batch directory:
  batch-manifest.json, batch-state.json, and per-attempt
  scope.json / observability-status.json / result.json / measured-usage.json.

No network, no project runtime import, no writes outside this report directory.
Outputs: aggregate.json, per-slot.csv, summary.zh-CN.md
"""

import csv
import hashlib
import json
import os
from datetime import datetime, timezone

BATCH = os.path.join(
    "results", "v16", "wp-d", "next-api-max8-20261022-121153"
)
OUT = os.path.dirname(os.path.abspath(__file__))

VARIANT_LABEL = {
    "single": "Single（强单代理）",
    "fixed": "Fixed（固定四代理）",
    "dynamic_no_verifier": "NoVerifier（动态无验证）",
    "full": "Full（完整动态）",
}
VARIANT_ORDER = ["full", "single", "fixed", "dynamic_no_verifier"]


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_attempt(slot_dir, attempt_rel):
    """Extract metrics of one attempt. Returns None if artifacts are missing."""
    path = os.path.join(slot_dir, attempt_rel)
    scope_p = os.path.join(path, "scope.json")
    status_p = os.path.join(path, "observability", "status.json")
    result_p = os.path.join(path, "result.json")
    usage_p = os.path.join(path, "measured-usage.json")
    if not os.path.isfile(scope_p):
        return None
    rec = {
        "path": attempt_rel,
        "variant": None,
        "incident": None,
        "lifecycle": None,
        "started_at": None,
        "ended_at": None,
        "elapsed_sec": None,
        "physical_requests": None,
        "tool_calls": None,
        "observed_tokens": None,
        "tokens_complete": None,
        "error_type": None,
        "result_status": None,
        "termination_reason": None,
        "runtime_failure": None,
        "workflow_status": None,
        "stop_reason": None,
        "usage": {
            "logical_calls": 0,
            "http_requests": 0,
            "transport_retries": 0,
            "repair_requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            # complete-calls-only: strict lower bound (tokens_complete=true)
            "measured_total_tokens": 0,
            # all-calls: includes partial usage recorded on incomplete calls;
            # equals status.json observed_tokens (basis of the earlier review)
            "observed_total_tokens": 0,
            "calls_with_usage": 0,
            "calls_without_usage": 0,
        },
        "files": {},
    }
    scope = load_json(scope_p)
    rec["variant"] = scope.get("variant")
    rec["incident"] = scope.get("incident_id")
    rec["files"]["scope.json"] = sha256_file(scope_p)

    if os.path.isfile(status_p):
        st = load_json(status_p)
        rec["lifecycle"] = st.get("lifecycle")
        rec["started_at"] = st.get("started_at")
        rec["ended_at"] = st.get("ended_at")
        rec["physical_requests"] = st.get("physical_requests")
        rec["tool_calls"] = st.get("tool_calls")
        rec["observed_tokens"] = st.get("observed_tokens")
        rec["tokens_complete"] = st.get("tokens_complete")
        rec["error_type"] = st.get("error_type")
        if rec["started_at"] and rec["ended_at"]:
            fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
            try:
                s = datetime.strptime(rec["started_at"], fmt)
                e = datetime.strptime(rec["ended_at"], fmt)
                rec["elapsed_sec"] = round((e - s).total_seconds(), 1)
            except (ValueError, TypeError):
                rec["elapsed_sec"] = None
        rec["files"]["observability/status.json"] = sha256_file(status_p)

    if os.path.isfile(result_p):
        res = load_json(result_p)
        rec["result_status"] = res.get("status")
        term = res.get("termination") or {}
        rec["termination_reason"] = term.get("reason")
        rec["runtime_failure"] = term.get("runtime_failure")
        rec["workflow_status"] = res.get("workflow_status")
        rec["stop_reason"] = res.get("stop_reason")
        rec["files"]["result.json"] = sha256_file(result_p)

    if os.path.isfile(usage_p):
        usage = load_json(usage_p)
        u = rec["usage"]
        for call in usage.get("calls", []):
            measure = call.get("usage") or {}
            u["logical_calls"] += 1
            u["http_requests"] += measure.get("actual_http_requests", 0) or 0
            u["transport_retries"] += measure.get("transport_retries", 0) or 0
            u["repair_requests"] += measure.get("repair_requests", 0) or 0
            u["observed_total_tokens"] += (
                measure.get("measured_total_tokens") or 0
            )
            if measure.get("tokens_complete"):
                u["calls_with_usage"] += 1
                u["prompt_tokens"] += measure.get("measured_prompt_tokens") or 0
                u["completion_tokens"] += (
                    measure.get("measured_completion_tokens") or 0
                )
                u["measured_total_tokens"] += (
                    measure.get("measured_total_tokens") or 0
                )
            else:
                u["calls_without_usage"] += 1
        rec["files"]["measured-usage.json"] = sha256_file(usage_p)
    return rec


def classify(rec):
    """normal_completion | technical_failure | unknown"""
    if rec["lifecycle"] is None or rec["result_status"] is None:
        return "unknown"
    if rec["lifecycle"] != "completed":
        return "technical_failure"
    if rec["runtime_failure"] or rec["workflow_status"] == "FAILED":
        return "technical_failure"
    return "normal_completion"


def fmt_minutes(sec):
    if sec is None:
        return "n/a"
    return f"{sec / 60.0:.2f}"


def main():
    manifest = load_json(os.path.join(BATCH, "batch-manifest.json"))
    state = load_json(os.path.join(BATCH, "batch-state.json"))

    order = manifest["order"]  # 40 planned slots
    runs_root = os.path.join(BATCH, "runs")

    per_slot = {}
    all_attempts = []
    for idx, planned in enumerate(order, start=1):
        slot_id = f"slot-{idx:03d}"
        slot_dir = os.path.join(runs_root, slot_id)
        attempts = state["slots"].get(slot_id, [])
        recs = []
        for att in attempts:
            rec = read_attempt(slot_dir, os.path.basename(att["path"]))
            if rec is None:
                continue
            rec["slot"] = slot_id
            rec["batch_status"] = att.get("status")
            rec["retry_of"] = att.get("retry_of")
            rec["retry_reason"] = att.get("retry_reason")
            rec["class"] = classify(rec)
            recs.append(rec)
            all_attempts.append(rec)
        # selection: a normal-completion attempt replaces the original; the
        # original attempt-001 stays representative when every retry failed.
        selected = None
        for rec in recs:
            if rec["class"] == "normal_completion":
                selected = rec
                break
        if selected is None and recs:
            selected = recs[0]
        per_slot[slot_id] = {
            "incident": planned["incident"],
            "variant": planned["variant"],
            "planned_repeat": planned["repeat"],
            "n_attempts": len(recs),
            "selected": selected,
            "attempts": recs,
        }

    # ---- aggregate by variant over SELECTED attempts ----
    by_variant = {}
    for variant in VARIANT_ORDER:
        slots = [
            (sid, sd)
            for sid, sd in per_slot.items()
            if sd["variant"] == variant
        ]
        sel = [sd["selected"] for _, sd in slots if sd["selected"]]
        normal = [r for r in sel if r["class"] == "normal_completion"]
        failed = [r for r in sel if r["class"] != "normal_completion"]
        resolved = [r for r in normal if r["result_status"] == "RESOLVED"]
        inconclusive = [
            r for r in normal if r["result_status"] == "INCONCLUSIVE"
        ]
        elapsed = [r["elapsed_sec"] for r in sel if r["elapsed_sec"] is not None]
        reqs = [r["physical_requests"] for r in sel if r["physical_requests"] is not None]
        tools = [r["tool_calls"] for r in sel if r["tool_calls"] is not None]
        tokens_obs = [r["usage"]["observed_total_tokens"] for r in sel]
        tokens_comp = [r["usage"]["measured_total_tokens"] for r in sel]
        by_variant[variant] = {
            "label": VARIANT_LABEL[variant],
            "planned_slots": len(slots),
            "normal_completions": len(normal),
            "technical_failures": len(failed),
            "resolved": len(resolved),
            "abstentions": len(inconclusive),
            "elapsed_sec_total": round(sum(elapsed), 1) if elapsed else None,
            "elapsed_sec_mean": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
            "elapsed_sec_min": min(elapsed) if elapsed else None,
            "elapsed_sec_max": max(elapsed) if elapsed else None,
            "physical_requests_total": sum(reqs),
            "tool_calls_total": sum(tools),
            "tokens_total_observed": sum(tokens_obs),
            "tokens_total_complete_only": sum(tokens_comp),
            "mean_requests_per_slot": round(sum(reqs) / len(reqs), 2) if reqs else None,
            "mean_tools_per_slot": round(sum(tools) / len(tools), 2) if tools else None,
            "mean_tokens_per_slot": round(sum(tokens_obs) / len(tokens_obs)) if tokens_obs else None,
            "mean_minutes_per_slot": (
                round((sum(elapsed) / len(elapsed)) / 60.0, 2) if elapsed else None
            ),
            "elapsed_detail_seconds": elapsed,
            "requests_detail": reqs,
            "tools_detail": tools,
            "tokens_detail": tokens_obs,
        }

    # ---- aggregate over ALL attempts (full retry ledger) ----
    ledger = {}
    for variant in VARIANT_ORDER:
        recs = [r for r in all_attempts if r["variant"] == variant]
        ledger[variant] = {
            "label": VARIANT_LABEL[variant],
            "n_attempts": len(recs),
            "http_requests": sum(r["usage"]["http_requests"] for r in recs),
            "logical_calls": sum(r["usage"]["logical_calls"] for r in recs),
            "transport_retries": sum(r["usage"]["transport_retries"] for r in recs),
            "repair_requests": sum(r["usage"]["repair_requests"] for r in recs),
            "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in recs),
            "completion_tokens": sum(r["usage"]["completion_tokens"] for r in recs),
            "measured_total_tokens": sum(
                r["usage"]["measured_total_tokens"] for r in recs
            ),
            "observed_total_tokens": sum(
                r["usage"]["observed_total_tokens"] for r in recs
            ),
            "calls_with_usage": sum(r["usage"]["calls_with_usage"] for r in recs),
            "calls_without_usage": sum(r["usage"]["calls_without_usage"] for r in recs),
        }
    ledger_total = {
        "n_attempts": len(all_attempts),
        "http_requests": sum(v["http_requests"] for v in ledger.values()),
        "logical_calls": sum(v["logical_calls"] for v in ledger.values()),
        "transport_retries": sum(v["transport_retries"] for v in ledger.values()),
        "repair_requests": sum(v["repair_requests"] for v in ledger.values()),
        "prompt_tokens": sum(v["prompt_tokens"] for v in ledger.values()),
        "completion_tokens": sum(v["completion_tokens"] for v in ledger.values()),
        "measured_total_tokens": sum(v["measured_total_tokens"] for v in ledger.values()),
        "observed_total_tokens": sum(v["observed_total_tokens"] for v in ledger.values()),
        "calls_with_usage": sum(v["calls_with_usage"] for v in ledger.values()),
        "calls_without_usage": sum(v["calls_without_usage"] for v in ledger.values()),
    }

    # selected-attempt totals
    sel_all = [sd["selected"] for sd in per_slot.values() if sd["selected"]]
    selected_total = {
        "n_slots": len(sel_all),
        "http_requests": sum(r["usage"]["http_requests"] for r in sel_all),
        "physical_requests_status_field": sum(
            r["physical_requests"] or 0 for r in sel_all
        ),
        "tool_calls": sum(r["tool_calls"] or 0 for r in sel_all),
        "measured_total_tokens": sum(
            r["usage"]["measured_total_tokens"] for r in sel_all
        ),
        "observed_total_tokens": sum(
            r["usage"]["observed_total_tokens"] for r in sel_all
        ),
        "elapsed_sec_total": round(
            sum(r["elapsed_sec"] or 0 for r in sel_all), 1
        ),
    }

    out = {
        "batch": "next-api-max8-20261022-121153",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "planned_slots": len(order),
        "supervisor_status": load_json(
            os.path.join(BATCH, "supervisor-status.json")
        ),
        "selection_rule": (
            "每个槽位优先取第一个正常完成的 attempt（仅 slot-012 由补跑 attempt-002 替换）；"
            "全部 attempt 均技术失败的槽位保留原始 attempt-001 作为代表。"
        ),
        "by_variant_selected": by_variant,
        "by_variant_all_attempts_ledger": ledger,
        "ledger_total": ledger_total,
        "selected_total": selected_total,
        "slots": {
            sid: {
                "incident": sd["incident"],
                "variant": sd["variant"],
                "n_attempts": sd["n_attempts"],
                "selected_attempt": sd["selected"]["path"],
                "selected_class": sd["selected"]["class"],
                "selected_status": sd["selected"]["result_status"],
                "selected_termination": sd["selected"]["termination_reason"],
                "selected_elapsed_sec": sd["selected"]["elapsed_sec"],
                "selected_physical_requests": sd["selected"]["physical_requests"],
                "selected_tool_calls": sd["selected"]["tool_calls"],
                "selected_tokens_observed": sd["selected"]["usage"]["observed_total_tokens"],
                "selected_tokens_complete_only": sd["selected"]["usage"]["measured_total_tokens"],
                "attempt_classes": [r["class"] for r in sd["attempts"]],
            }
            for sid, sd in per_slot.items()
        },
    }

    with open(os.path.join(OUT, "aggregate.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "per-slot.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "slot", "incident", "variant", "n_attempts",
                "selected_attempt", "class", "result_status",
                "termination_reason", "elapsed_sec", "physical_requests",
                "tool_calls", "tokens_observed", "tokens_complete_only",
                "http_requests_usage", "logical_calls",
                "calls_with_usage", "calls_without_usage",
            ]
        )
        for sid in sorted(per_slot):
            sd = per_slot[sid]
            r = sd["selected"]
            writer.writerow(
                [
                    sid, sd["incident"], sd["variant"], sd["n_attempts"],
                    r["path"], r["class"], r["result_status"],
                    r["termination_reason"], r["elapsed_sec"],
                    r["physical_requests"], r["tool_calls"],
                    r["usage"]["observed_total_tokens"],
                    r["usage"]["measured_total_tokens"],
                    r["usage"]["http_requests"], r["usage"]["logical_calls"],
                    r["usage"]["calls_with_usage"], r["usage"]["calls_without_usage"],
                ]
            )

    # ---- console digest ----
    print("=== SELECTED attempts per variant ===")
    for v in VARIANT_ORDER:
        d = by_variant[v]
        print(
            f"{v:20s} slots={d['planned_slots']} ok={d['normal_completions']} "
            f"fail={d['technical_failures']} resolved={d['resolved']} "
            f"abstain={d['abstentions']} reqs={d['physical_requests_total']} "
            f"tools={d['tool_calls_total']} tokens_obs={d['tokens_total_observed']} "
            f"tokens_comp={d['tokens_total_complete_only']} "
            f"mean_min={d['mean_minutes_per_slot']}"
        )
    print("selected_total:", selected_total)
    print("=== ALL attempts ledger ===")
    for v in VARIANT_ORDER:
        d = ledger[v]
        print(
            f"{v:20s} attempts={d['n_attempts']} http={d['http_requests']} "
            f"logical={d['logical_calls']} retries={d['transport_retries']} "
            f"repairs={d['repair_requests']} tokens_obs={d['observed_total_tokens']} "
            f"with_usage={d['calls_with_usage']} without={d['calls_without_usage']}"
        )
    print("ledger_total:", ledger_total)


if __name__ == "__main__":
    main()
