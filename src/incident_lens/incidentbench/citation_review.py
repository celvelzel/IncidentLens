"""Anonymous pending claim exports and explicit human review provenance."""

import hashlib
from collections import defaultdict

from .oracle_store import canonical

LABELS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "NOT_APPLICABLE"}


def prepare_review_bundle(states):
    bundle = []
    for state in states:
        report = state.get("report") or {}
        observed = {}
        for event in state.get("events", []):
            if (
                event.get("event_type") != "TOOL_CALL"
                or event.get("run_id") != state.get("run_id")
                or event.get("incident_id") != state.get("incident_id")
            ):
                continue
            result = event.get("details", {}).get("result", {})
            if result.get("ok") is not True:
                continue
            for record in result.get("records", []):
                if record.get("incident_id") == state.get("incident_id") and record == state.get(
                    "evidence_index", {}
                ).get(record.get("evidence_id")):
                    observed[record["evidence_id"]] = record
        claims = []
        root = report.get("root_cause")
        if root:
            claims.append(
                (
                    "root_cause",
                    root.get(
                        "description",
                        str(
                            {
                                k: v
                                for k, v in root.items()
                                if k in {"culprit_service", "failure_mode", "root_cause_code"}
                            }
                        ),
                    ),
                    report.get("supporting_evidence_ids", report.get("citations", [])),
                )
            )
        for step in report.get("causal_chain", []):
            claims.append(
                (
                    "causal_step",
                    str(step),
                    report.get("supporting_evidence_ids", report.get("citations", [])),
                )
            )
        for number, (kind, text, citations) in enumerate(claims):
            key = hashlib.sha256(canonical([state.get("run_id"), number])).hexdigest()[:24]
            ids = [c if isinstance(c, str) else c.get("evidence_id") for c in citations]
            bundle.append(
                {
                    "claim_id": key,
                    "claim_type": kind,
                    "claim_text": text,
                    "citation_ids": ids,
                    "evidence": [observed[i] for i in ids if i in observed],
                    "unobserved_citation_ids": [i for i in ids if i not in observed],
                    "review_label": None,
                    "reviewer_id": None,
                    "annotation_status": "pending",
                }
            )
    return sorted(bundle, key=lambda row: row["claim_id"])


def merge_reviews(bundle, records, adjudications=None):
    """Never convert missing or conflicting reviews into a semantic label."""
    known = {row["claim_id"] for row in bundle}
    grouped = defaultdict(dict)
    for record in records:
        claim = record.get("claim_id")
        reviewer = record.get("reviewer_id")
        if (
            claim not in known
            or not reviewer
            or record.get("review_label") not in LABELS
            or not record.get("rationale")
            or record.get("source") != "human"
            or not record.get("reviewed_at")
        ):
            raise ValueError("invalid human review record")
        if reviewer in grouped[claim] and grouped[claim][reviewer] != record:
            raise ValueError("conflicting duplicate reviewer record")
        grouped[claim][reviewer] = record
    adjudications = adjudications or []
    decisions = {}
    for item in adjudications:
        if item["claim_id"] in decisions or item["claim_id"] not in known:
            raise ValueError("duplicate or unknown adjudication")
        if (
            item.get("source") != "human"
            or not item.get("rationale")
            or not item.get("reviewed_at")
        ):
            raise ValueError("invalid adjudication provenance")
        decisions[item["claim_id"]] = item
    results = []
    for claim in sorted(known):
        raw = list(grouped[claim].values())
        labels = {r["review_label"] for r in raw}
        label = None
        status = "pending"
        if len(raw) >= 2 and len(labels) == 1:
            label, status = raw[0]["review_label"], "final"
        elif len(raw) >= 2 and claim in decisions:
            decision = decisions[claim]
            if (
                decision.get("reviewer_id") in grouped[claim]
                or decision.get("review_label") not in LABELS
            ):
                raise ValueError("adjudication requires independent reviewer")
            label, status = decision["review_label"], "adjudicated"
        results.append(
            {
                "claim_id": claim,
                "review_label": label,
                "annotation_status": status,
                "raw_reviews": raw,
                "adjudication": decisions.get(claim),
            }
        )
    return results


def review_coverage(bundle, merged):
    expected = {row["claim_id"] for row in bundle}
    completed = {
        row["claim_id"]: row
        for row in merged
        if row["claim_id"] in expected and row["annotation_status"] in {"final", "adjudicated"}
    }
    factual = [row for row in completed.values() if row["review_label"] != "NOT_APPLICABLE"]
    pairs = [
        row
        for row in merged
        if row["claim_id"] in expected and len(row.get("raw_reviews", [])) >= 2
    ]
    unique_pairs = {row["claim_id"]: row for row in pairs}
    agreeing = sum(
        len({r["review_label"] for r in row["raw_reviews"]}) == 1 for row in unique_pairs.values()
    )
    return {
        "double_reviewed_claims": len(unique_pairs),
        "disagreements": len(unique_pairs) - agreeing,
        "observed_agreement": agreeing / len(unique_pairs) if unique_pairs else None,
        "total_claims": len(expected),
        "reviewed_claims": len(completed),
        "coverage": len(completed) / len(expected) if expected else None,
        "human_support_rate": sum(r["review_label"] == "SUPPORTED" for r in factual) / len(factual)
        if factual
        else None,
        "unsupported_claim_rate": sum(
            r["review_label"] in {"CONTRADICTED", "INSUFFICIENT"} for r in factual
        )
        / len(factual)
        if factual
        else None,
    }


def validate_truth_reviews(oracle, document):
    records = document.get("reviews", [])
    reviewers = set()
    expected = {
        k: v
        for k, v in oracle.items()
        if k not in {"reviewer_ids", "annotator_status", "review_version"}
    }
    labels = []
    for record in records:
        if (
            record.get("source") != "human"
            or not record.get("reviewed_at")
            or not record.get("rationale")
            or not record.get("reviewer_id")
            or record.get("incident_id") != oracle["incident_id"]
        ):
            raise ValueError("invalid truth review provenance")
        if record["reviewer_id"] in reviewers:
            raise ValueError("duplicate truth reviewer")
        reviewers.add(record["reviewer_id"])
        labels.append(record.get("labels"))
    if len(reviewers) < 2 or not set(oracle.get("reviewer_ids", [])).issubset(reviewers):
        raise ValueError("truth review requires two raw independent records")
    if all(label == expected for label in labels):
        return True
    adjudication = document.get("adjudication") or {}
    if (
        adjudication.get("source") != "human"
        or not adjudication.get("rationale")
        or not adjudication.get("reviewed_at")
        or not adjudication.get("reviewer_id")
        or adjudication["reviewer_id"] in reviewers
        or adjudication.get("labels") != expected
    ):
        raise ValueError("truth disagreement requires authentic adjudication")
    return True
