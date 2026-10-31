"""Evaluate persisted Dev40 artifacts without providers or runtime execution.

Writes new report artifacts here and receipt-bound evaluator copies under
local_oracles. Original experiment inputs and outputs remain read-only.
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from incident_lens.incidentbench.manifest import digest_tree
from incident_lens.incidentbench.oracle_store import OracleStore
from incident_lens.incidentbench.scorer import score_benchmark_run

BATCH = ROOT / "results/v16/wp-d/next-api-max8-20261022-121153"
OUT = Path(__file__).resolve().parent
PRIVATE = ROOT / "local_oracles/wp-d/next-api-max8-20261022-121153-review"
VARIANTS = ["full", "single", "fixed", "dynamic_no_verifier"]


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    PRIVATE.mkdir(parents=True, exist_ok=False)
    manifest = read(BATCH / "batch-manifest.json")
    batch_state = read(BATCH / "batch-state.json")
    status = read(BATCH / "supervisor-status.json")
    assert status["state"] == "batch_finished_with_errors" and not status["active"]
    assert len(manifest["order"]) == len(batch_state["slots"]) == 40
    assert all(len(ats) == 1 for ats in batch_state["slots"].values())
    source_before = {p: sha(ROOT / p) if (ROOT / p).is_file() else None
                     for p in manifest["hashes"]}
    drift = [p for p, expected in manifest["hashes"].items() if source_before[p] != expected]
    assert not drift, drift
    freeze = read(ROOT / "docs/incidentbench/wp-b-project-accepted-freeze.json")
    oracle_root = ROOT / "local_oracles/incidentbench_v16_dev"
    public_root = ROOT / manifest["plan"]["dataset"]
    assert digest_tree(oracle_root) == freeze["datasets"]["dev"]["oracle_sha256"]
    assert digest_tree(public_root) == freeze["datasets"]["dev"]["public_sha256"]
    store = OracleStore(oracle_root, public_root)
    inputs = {str(BATCH / n): sha(BATCH / n) for n in
              ["batch-manifest.json", "batch-state.json", "supervisor-status.json"]}
    rows, details, private_scores = [], [], []
    identities, params = set(), set()
    artifact_n = 0
    for index, expected in enumerate(manifest["order"], 1):
        slot = f"slot-{index:03}"
        at = batch_state["slots"][slot][0]
        assert at["key"] == expected
        directory = BATCH / at["path"]
        for name, digest in at["artifacts"].items():
            path = directory / name
            assert sha(path) == digest, path
            inputs[str(path)] = digest
            artifact_n += 1
        scope = read(directory / "scope.json")
        trace = read(directory / "trace.json")
        state = trace["state"]
        result = read(directory / "result.json")
        verification = read(directory / "verification.json")
        assert scope["incident_id"] == expected["incident"] == result["incident_id"]
        assert scope["variant"] == expected["variant"] == trace["variant"]
        assert state["report"] == result
        assert scope["protocol"] == manifest["protocol"]
        identities.add((scope["source_commit"], scope["runtime_config_sha256"], trace["model_id"],
                        scope["dataset_revision"], trace.get("prompt_version")))
        params.add(json.dumps(scope["effective_model_parameters"], sort_keys=True))
        # Persist an exact evaluator copy first; OracleStore validates its receipt.
        state_path = PRIVATE / f"{slot}-completed-state.json"
        write(state_path, state)
        completed = dict(state, completion_receipt={"path": str(state_path), "sha256": sha(state_path)})
        oracle = store.load_after_completion(expected["incident"], completed)
        score = score_benchmark_run(state, oracle)
        assert score["technical_completion"] == (at["status"] == "completed")
        correct = score["root_cause_correct"] if oracle.is_identifiable else score["correct_abstention"]
        row = {
            "slot": slot, "incident": expected["incident"], "variant": expected["variant"],
            "attempt": at["path"], "technical_status": at["status"],
            "identifiable": oracle.is_identifiable, "report_status": result["status"],
            "root_match": score["root_cause_correct"], "correct_abstention": score["correct_abstention"],
            "task_correct": bool(correct), "termination_reason": verification["termination_reason"],
            "http_requests": verification["actual_http_requests"],
            "logical_calls": verification["logical_structured_calls"],
            "transport_retries": verification["transport_retries"],
            "repairs": verification["repair_requests"], "tools": state["tool_calls_used"],
            "rounds": state["round_index"], "elapsed_minutes": verification["elapsed_ms"] / 60000,
            "measured_tokens": verification["measured_total_tokens"],
            "tokens_complete": verification["tokens_complete"],
            "requests_with_usage": verification["requests_with_token_usage"],
            "requests_without_usage": verification["requests_without_token_usage"],
            "citations": score["citation_count"], "valid_citations": score["valid_citation_count"],
            "reviews": len(state["reviews"]),
            "independent_reviews": verification["verifier"]["completed_reviews"]
                if verification["verifier"]["review_kind"] == "independent" else 0,
            "source_unchanged": verification["source_unchanged"],
            "protocol_valid": verification["protocol_valid"],
            "observability_healthy": not verification["observability"]["degraded"],
        }
        rows.append(row)
        private_scores.append(dict(slot=slot, oracle=oracle.model_dump(mode="json"), score=score))
        observed = state["evidence_index"]
        details.append({"slot": slot, "incident": expected["incident"], "variant": expected["variant"],
                        "result": result,
                        "support_records": [observed.get(e) for e in result["supporting_evidence_ids"]],
                        "rejected_hypotheses": [{"hypothesis": h, "against_records":
                            [observed.get(e) for e in h["against_ids"]]}
                            for h in result["rejected_hypotheses"]],
                        "verifier": verification["verifier"],
                        "provider_failure_details": verification["provider_failure_details"],
                        "runtime_errors": [e for e in state["events"] if e["event_type"] == "RUNTIME_ERROR"],
                        "last_decision": state["decisions"][-1] if state["decisions"] else None,
                        "budget": state["budgets"],
                        "stop_completed": verification["stop_completion"]})
    assert len(identities) == len(params) == 1
    sums = ["http_requests", "logical_calls", "transport_retries", "repairs", "tools", "rounds",
            "measured_tokens", "requests_with_usage", "requests_without_usage", "citations", "valid_citations",
            "reviews", "independent_reviews"]

    def aggregate(group):
        ok = [r for r in group if r["technical_status"] == "completed"]
        identifiable = [r for r in group if r["identifiable"]]
        ok_identifiable = [r for r in ok if r["identifiable"]]
        unidentifiable = [r for r in group if not r["identifiable"]]
        return {
            "planned": len(group), "completed": len(ok), "failed": len(group) - len(ok),
            "resolved": sum(r["report_status"] == "RESOLVED" for r in ok),
            "abstained": sum(r["report_status"] == "INCONCLUSIVE" for r in ok),
            "root_matches": sum(r["root_match"] is True for r in group),
            "identifiable_n": len(identifiable), "completed_identifiable_n": len(ok_identifiable),
            "correct_abstentions": sum(r["correct_abstention"] is True for r in group),
            "unidentifiable_n": len(unidentifiable),
            "unnecessary_abstentions": sum(r["identifiable"] and r["report_status"] == "INCONCLUSIVE" for r in ok),
            "task_correct": sum(r["task_correct"] for r in group),
            "totals_all_attempts": {k: sum(r[k] for r in group) for k in sums},
            "totals_completed_only": {k: sum(r[k] for r in ok) for k in sums},
            "mean_minutes_all": mean(r["elapsed_minutes"] for r in group),
            "median_minutes_all": median(r["elapsed_minutes"] for r in group),
            "complete_usage_runs": sum(r["tokens_complete"] for r in group),
            "total_tokens": sum(r["measured_tokens"] for r in group) if all(r["tokens_complete"] for r in group) else None,
            "cost_usd": None,
        }

    paired = {}
    for other in VARIANTS[1:]:
        by_full = {r["incident"]: r for r in rows if r["variant"] == "full"}
        by_other = {r["incident"]: r for r in rows if r["variant"] == other}
        common = [i for i in by_full if by_full[i]["technical_status"] == by_other[i]["technical_status"] == "completed"]
        paired[other] = {"common_completed_cases": common,
            "full_task_correct": sum(by_full[i]["task_correct"] for i in common),
            "other_task_correct": sum(by_other[i]["task_correct"] for i in common),
            "full_requests": sum(by_full[i]["http_requests"] for i in common),
            "other_requests": sum(by_other[i]["http_requests"] for i in common),
            "full_tools": sum(by_full[i]["tools"] for i in common),
            "other_tools": sum(by_other[i]["tools"] for i in common)}
    executions = batch_state["executions"]
    as_local = lambda x: datetime.fromtimestamp(x, timezone(timedelta(hours=8))).isoformat()
    audit = {"artifact_hashes_verified": artifact_n, "frozen_files_verified": len(source_before),
             "current_frozen_source_drift": drift,
             "source_unchanged_all_runs": all(r["source_unchanged"] for r in rows),
             "protocol_valid_all_runs": all(r["protocol_valid"] for r in rows),
             "observability_healthy_all_runs": all(r["observability_healthy"] for r in rows),
             "single_source_model_dataset_runtime_prompt_identity": list(identities)[0],
             "oracle_tree_matches_owner_acceptance": True,
             "public_tree_matches_owner_acceptance": True,
             "source_files_unchanged_by_analysis": all(sha(ROOT / p) == digest for p, digest in source_before.items()),
             "read_inputs_unchanged_by_analysis": all(sha(Path(p)) == digest for p, digest in inputs.items())}
    assert audit["source_files_unchanged_by_analysis"] and audit["read_inputs_unchanged_by_analysis"]
    summary = {"batch": str(BATCH), "scope": "development_visible, formal=false; descriptive reference agreement, no human grounding certification",
        "status": status, "protocol": manifest["protocol"], "external": manifest["external"],
        "started_at_shanghai": as_local(executions[0]["started_at_utc"]),
        "ended_at_shanghai": as_local(executions[-1]["ended_at_utc"]),
        "elapsed_minutes_including_pauses": (executions[-1]["ended_at_utc"] - executions[0]["started_at_utc"]) / 60,
        "execution_minutes_excluding_pauses": sum(e["elapsed_seconds"] for e in executions) / 60,
        "execution_count": len(executions), "totals": aggregate(rows),
        "by_variant": {v: aggregate([r for r in rows if r["variant"] == v]) for v in VARIANTS},
        "paired_completed_only": paired, "integrity": audit,
        "failure_categories": dict(Counter(d["provider_failure_details"][-1]["category"]
                if d["provider_failure_details"] else "SAVED_BUDGET_EXHAUSTED_REQUIRES_REVIEW"
                for d, r in zip(details, rows) if r["technical_status"] != "completed")),
        "human_semantic_review": None, "human_grounded_success": None,
        "input_sha256": inputs}
    write(PRIVATE / "reference-scores.json", private_scores)
    write(OUT / "summary.json", summary)
    write(OUT / "trace-inspection.json", details)
    with (OUT / "per-slot.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k not in ["input_sha256", "protocol", "status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
