"""Failure-inclusive causal scoring, separate from human semantic review."""

import hashlib
import json
from collections import Counter
from statistics import mean

from .normalizer import normalize
from .schemas import BenchmarkOracle


def score_benchmark_run(state, oracle=None, annotations=None):
    result = normalize(state)
    result.update(
        scoring_version="incidentbench-v1.0",
        label_status="unscored",
        identifiable=None,
        root_cause_correct=None,
        correct_abstention=None,
        misleading_correct=None,
        misleading_case=None,
        human_support_rate=None,
        unsupported_claim_rate=None,
        human_grounded_success=None,
        human_review_coverage=None,
        semantic_review_status="unreviewed",
    )
    if oracle is not None:
        oracle = (
            oracle
            if isinstance(oracle, BenchmarkOracle)
            else BenchmarkOracle.model_validate(oracle)
        )
        if oracle.incident_id != state["incident_id"]:
            raise ValueError("oracle incident mismatch")
        root = (state.get("report") or {}).get("root_cause") or {}
        correct = bool(
            result["technical_completion"]
            and result["resolved"]
            and root.get("culprit_service") == oracle.true_primary_root.culprit_service
            and root.get("failure_mode") == oracle.true_primary_root.failure_mode
        )
        result.update(
            label_status="provisional"
            if oracle.annotator_status == "pending"
            else oracle.annotator_status,
            oracle_sha256=hashlib.sha256(
                json.dumps(
                    oracle.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            oracle_review_version=oracle.review_version,
            identifiable=oracle.is_identifiable,
            root_cause_correct=correct if oracle.is_identifiable else None,
            correct_abstention=result["abstained"] if not oracle.is_identifiable else None,
            misleading_case=bool(oracle.misleading_evidence_ids),
            misleading_correct=correct
            if oracle.is_identifiable and oracle.misleading_evidence_ids
            else None,
        )
    if annotations is not None:
        from .citation_review import merge_reviews, prepare_review_bundle, review_coverage

        bundle = annotations["bundle"]
        if bundle != prepare_review_bundle([state]):
            raise ValueError(
                "review bundle must exactly cover this run's key claims and observed evidence"
            )
        merged = merge_reviews(bundle, annotations["records"], annotations.get("adjudications"))
        coverage = review_coverage(bundle, merged)
        factual = [
            r
            for r in merged
            if r["annotation_status"] in {"final", "adjudicated"}
            and r["review_label"] != "NOT_APPLICABLE"
        ]
        result.update(
            human_factual_claim_n=len(factual),
            human_supported_claim_n=sum(r["review_label"] == "SUPPORTED" for r in factual),
            human_unsupported_claim_n=sum(
                r["review_label"] in {"CONTRADICTED", "INSUFFICIENT"} for r in factual
            ),
        )
        result.update(
            human_support_rate=coverage["human_support_rate"],
            unsupported_claim_rate=coverage["unsupported_claim_rate"],
            human_review_coverage=coverage["coverage"],
            semantic_review_status="reviewed" if coverage["reviewed_claims"] else "unreviewed",
        )
        if coverage["coverage"] == 1 and result["identifiable"]:
            result["human_grounded_success"] = bool(
                result["root_cause_correct"]
                and all(r["review_label"] == "SUPPORTED" for r in merged)
            )
    return result


def aggregate(rows):
    """Core denominators include technical failures; nulls never become zero."""
    output = []
    for variant in sorted({r["variant"] for r in rows}):
        group = [r for r in rows if r["variant"] == variant and r.get("cohort", "core") == "core"]

        def rate(key):
            values = [r[key] for r in group if r.get(key) is not None]
            return {
                "numerator": sum(values),
                "denominator": len(values),
                "rate": mean(values) if values else None,
            }

        item = {
            "variant": variant,
            "tested_n": len(group),
            "label_status_counts": dict(Counter(r.get("label_status", "unscored") for r in group)),
            "failure_counts": dict(
                Counter(
                    r.get("failure_category") or r.get("termination_reason") or "UNKNOWN"
                    for r in group
                    if not r.get("technical_completion")
                )
            ),
        }
        for key, name in (
            ("technical_completion", "investigation_completion_rate"),
            ("root_cause_correct", "root_cause_accuracy"),
            ("correct_abstention", "correct_abstention_rate"),
            ("misleading_correct", "misleading_accuracy"),
        ):
            item[name] = rate(key)
        cited = sum(r.get("citation_count", 0) for r in group)
        item["citation_existence_validity"] = (
            sum(r.get("valid_citation_count", 0) for r in group) / cited if cited else None
        )
        attempts = [r.get("actual_http_requests") for r in group]
        item["total_http_attempts"] = (
            sum(attempts) if all(v is not None for v in attempts) else None
        )
        item["request_count_completeness"] = (
            sum(v is not None for v in attempts) / len(group) if group else None
        )
        item["known_http_attempts_lower_bound"] = sum(v for v in attempts if v is not None)
        item["token_completeness"] = (
            sum(r.get("total_tokens") is not None for r in group) / len(group) if group else None
        )
        item["total_tokens"] = (
            sum(r["total_tokens"] for r in group)
            if group and all(r.get("total_tokens") is not None for r in group)
            else None
        )
        item["latency_ms"] = (
            mean(r["latency_ms"] for r in group)
            if group and all(r.get("latency_ms") is not None for r in group)
            else None
        )
        item.update(
            human_support_rate=None, unsupported_claim_rate=None, human_grounded_success_rate=None
        )
        for metric in ("human_support_rate", "unsupported_claim_rate", "human_grounded_success"):
            reviewed = [r[metric] for r in group if r.get(metric) is not None]
            item[
                metric if metric != "human_grounded_success" else "human_grounded_success_rate"
            ] = mean(reviewed) if reviewed else None
        item["human_audited_run_n"] = sum(
            r.get("human_grounded_success") is not None for r in group
        )
        factual_n = sum(r.get("human_factual_claim_n", 0) for r in group)
        item["human_support_rate"] = (
            sum(r.get("human_supported_claim_n", 0) for r in group) / factual_n
            if factual_n
            else None
        )
        item["unsupported_claim_rate"] = (
            sum(r.get("human_unsupported_claim_n", 0) for r in group) / factual_n
            if factual_n
            else None
        )
        output.append(item)
    return output
