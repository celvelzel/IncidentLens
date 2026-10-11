"""Analyze saved completed evaluation traces without executing investigations."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from incident_lens.evaluation.metrics import report_citations, score_completed


def analyze(records):
    coordination, reviews = [], []
    slices = defaultdict(list)
    for record in records:
        state = record["state"]
        if not isinstance(state.get("report"), dict):
            raise ValueError("analysis requires a completed report before oracle access")
        oracle = record["oracle_scoring_fields"]
        if not isinstance(oracle, dict):
            raise ValueError("completed run has no stored scoring oracle")
        score = score_completed(state, oracle)
        metrics = record["metrics"]
        identity = dict(incident_id=state["incident_id"], run_id=state.get("run_id"), variant=metrics["variant"])
        events = state.get("events", [])
        decisions = [e.get("details", {}).get("decision", {}) for e in events if e.get("event_type") == "DECISION"]
        investigations = [d for d in decisions if d.get("action") == "INVESTIGATE"]
        role_sets = [tuple(sorted(set(t["role"] for t in d.get("assignments", [])))) for d in investigations]
        review_events = [e.get("details", {}).get("review", {}) for e in events if e.get("event_type") == "REVIEW"]
        coordination.append(dict(
            **identity, rounds=state.get("round_index", len(investigations)),
            investigate_decisions=len(investigations), replanning_decisions=max(0, len(investigations) - 1),
            task_roles=json.dumps([t["role"] for d in investigations for t in d.get("assignments", [])]),
            tool_calls=sum(e.get("event_type") == "TOOL_CALL" for e in events),
            review_insufficient=sum(r.get("verdict") == "insufficient" for r in review_events),
            review_conflicted=sum(r.get("verdict") == "conflicted" for r in review_events),
            requested_checks=sum(len(r.get("requested_checks", [])) for r in review_events),
            dynamic_role_transitions=sum(a != b for a, b in zip(role_sets, role_sets[1:])),
        ))
        key = metrics["variant"], oracle["failure_mode"], score["misleading_case"], score["identifiable"]
        slices[key].append(score)
        cited = set(report_citations(state["report"]))
        evidence = {}
        for event in events:
            if event.get("event_type") != "TOOL_CALL":
                continue
            for item in event.get("details", {}).get("result", {}).get("records", []):
                if item.get("evidence_id") in cited and item.get("incident_id") == state["incident_id"]:
                    evidence[item["evidence_id"]] = {k: item.get(k) for k in ("evidence_id", "source_path", "excerpt")}
        report = state["report"]
        reviews.append(dict(**identity, semantic_review_status="awaiting_human",
            root_cause=report.get("root_cause"), causal_chain=report.get("causal_chain", []),
            rejected_hypotheses=report.get("rejected_hypotheses", []), unresolved=report.get("unresolved", []),
            supporting_evidence_ids=report.get("supporting_evidence_ids", []),
            cited_evidence=[evidence[eid] for eid in sorted(evidence)],
            missing_cited_evidence_ids=sorted(cited - evidence.keys())))
    rows = []
    for (variant, mode, misleading, identifiable), scores in sorted(slices.items()):
        n = len(scores)
        citations = sum(s["citation_count"] for s in scores)
        valid = sum(s["valid_citation_count"] for s in scores)
        correct = sum(s["root_cause_correct"] is True for s in scores)
        abstain = sum(s["correct_abstention"] is True for s in scores)
        failures = sum(s["runtime_failure"] for s in scores)
        rows.append(dict(variant=variant, failure_mode=mode, misleading=misleading, identifiable=identifiable,
            n=n, correct=correct, correct_rate=correct / n if identifiable else None,
            abstain=abstain, correct_abstention_rate=abstain / n if not identifiable else None,
            runtime_failure=failures, runtime_failure_rate=failures / n,
            citation_count=citations, valid_citation_count=valid,
            citation_existence_validity=valid / citations if citations else None))
    return coordination, rows, dict(evidence_label="Synthetic incident traces; no human semantic annotation",
        semantic_review_status="awaiting_human", runs=reviews)


def export(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out == source.parent or source.is_relative_to(out):
        raise ValueError("output must be separate from input")
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("input contains no completed runs")
    coordination, slices, reviews = analyze(records)
    out.mkdir(parents=True, exist_ok=False)
    for name, rows in (("coordination.csv", coordination), ("mechanism-slices.csv", slices)):
        with (out / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (out / "citation-review.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    export(args.input, args.out)
