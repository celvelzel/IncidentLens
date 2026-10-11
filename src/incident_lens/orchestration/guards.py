"""Deterministic grounding and final acceptance, independent of confidence."""

import re

from incident_lens.schemas import Hypothesis, InvestigationState


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
        return (
            record.source_type == "metrics"
            and name in {"connections_active", "active_connections"}
            and isinstance(value, (int, float))
            and value >= 100
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
    return errors
