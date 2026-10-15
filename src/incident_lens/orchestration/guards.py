"""Deterministic grounding and final acceptance, independent of confidence."""

import hashlib
import json
import re

from incident_lens.schemas import Hypothesis, InvestigationState


def review_fingerprint(hypothesis):
    return hashlib.sha256(
        json.dumps(hypothesis.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


def evidence_fingerprint(state):
    return hashlib.sha256(
        json.dumps(
            {k: v.model_dump(mode="json") for k, v in sorted(state.evidence_index.items())},
            sort_keys=True,
        ).encode()
    ).hexdigest()


def cause_discriminator(hypothesis, record):
    """Conservative V1 evidence checks for the five fixed incident mechanisms.

    These are acceptance checks over public measurements, not an oracle.
    They establish a cause-specific observation, not guaranteed RCA correctness.
    """
    text = record.excerpt.lower()
    name = str(record.metadata.get("metric_name", "")).lower()
    value = record.metadata.get("value")
    mode = hypothesis.failure_mode.lower()
    if record.service != hypothesis.culprit_service:
        return False
    if mode == "backend_pool_config_regression":
        return (
            record.source_type == "configs"
            and bool(re.search(r"db_pool_max.{0,30}(?:->|to)\s*2\b", text))
            and "concurrency" in text
        )
    if mode == "postgres_connection_exhaustion":
        if record.source_type == "database":
            return (
                record.metadata.get("category") == "connections"
                and record.metadata.get("connection_limit", 0) > 0
                and record.metadata.get("connection_count", 0)
                >= record.metadata["connection_limit"]
            )
        return (
            record.source_type == "metrics"
            and name in {"connections_active", "active_connections"}
            and isinstance(value, (int, float))
            and value >= 100
        )
    if mode in ("postgres_lock_contention", "postgres_slow_query"):
        return (
            record.source_type == "database"
            and isinstance(record.metadata.get("duration_ms"), (int, float))
            and record.metadata["duration_ms"] >= 3000
            and (
                bool(record.metadata.get("blocked_by"))
                if mode == "postgres_lock_contention"
                else record.metadata.get("category") == "slow_queries"
            )
        )
    if mode == "redis_unavailable":
        return record.source_type == "metrics" and name == "availability" and value == 0
    if mode == "payment_external_timeout":
        return (
            record.source_type == "metrics"
            and "latency" in name
            and isinstance(value, (int, float))
            and value >= 3000
        )
    if mode == "backend_resource_saturation":
        return (
            record.source_type == "metrics"
            and name in {"cpu_percent", "thread_utilization"}
            and isinstance(value, (int, float))
            and value >= 90
        )
    return False


def grounding_errors(state: InvestigationState, hypothesis: Hypothesis) -> list[str]:
    errors = []
    if hypothesis.status == "REJECTED":
        errors.append("Rejected hypothesis cannot be finalized")
    refs = hypothesis.support_ids + hypothesis.against_ids
    if not set(refs).issubset(state.evidence_index):
        return ["Candidate cites unobserved evidence"]
    records = [state.evidence_index[eid] for eid in set(hypothesis.support_ids)]
    if len(records) < 2 or len({r.source_path for r in records}) < 2:
        errors.append("Need at least two supporting records from different sources")
    if not hypothesis.predicted_observations:
        errors.append("Candidate lacks discriminating predicted observations")
    if not any(cause_discriminator(hypothesis, r) for r in records):
        errors.append("No observed cause-specific discriminator for the candidate")
    completed = {f.task_id for f in state.findings if f.confidence_qualifier == "supported"}
    if not any(t.task_id in completed and t.expected_discriminator for t in state.tasks):
        errors.append("No supported discriminating investigation")
    if hypothesis.open_questions or hypothesis.against_ids:
        errors.append("Candidate has unresolved questions or contradictory evidence")
    return errors


def finalize_errors(state: InvestigationState, hypothesis: Hypothesis, variant="full") -> list[str]:
    errors = grounding_errors(state, hypothesis)
    if state.open_questions:
        errors.append("Unresolved shared questions prevent finalization")
    if any(
        h.hypothesis_id != hypothesis.hypothesis_id
        and h.status != "REJECTED"
        and (h.support_ids or h.open_questions)
        for h in state.hypotheses
    ):
        errors.append("Competing hypothesis remains unresolved")
    if variant == "full":
        review = next(
            (
                r
                for r in reversed(state.reviews)
                if r.target_hypothesis_id == hypothesis.hypothesis_id
            ),
            None,
        )
        if review is None or review.verdict != "sufficient":
            errors.append("Independent verifier has not accepted the candidate")
        elif review.contradictions or review.requested_checks:
            errors.append("Verifier still requests checks or reports contradictions")
        elif not review.cited_evidence_ids:
            errors.append("Verifier did not cite observed evidence")
        else:
            event = next(
                (
                    e
                    for e in reversed(state.events)
                    if e.event_type == "REVIEW"
                    and e.details.get("review", {}).get("target_hypothesis_id")
                    == hypothesis.hypothesis_id
                ),
                None,
            )
            if (
                event is None
                or event.details.get("hypothesis_sha256") != review_fingerprint(hypothesis)
                or event.details.get("evidence_sha256") != evidence_fingerprint(state)
            ):
                errors.append("Verifier review does not match current candidate/evidence snapshot")
    return errors


def reviewed_finalization_ready(state: InvestigationState, variant="full") -> bool:
    """A refreshed review can discharge an existing FINALIZE, never create one."""
    if (variant != "full" or not state.decisions or not state.reviews
        or state.report is not None or state.termination is not None
        or state.workflow_status != "RUNNING"):
        return False
    decision, review = state.decisions[-1], state.reviews[-1]
    if decision.action != "FINALIZE" or review.target_hypothesis_id != decision.selected_hypothesis_id:
        return False
    candidate = next(
        (h for h in state.hypotheses if h.hypothesis_id == decision.selected_hypothesis_id), None
    )
    return candidate is not None and not finalize_errors(state, candidate, variant)
