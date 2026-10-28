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
    """Observed mechanism checks over public measurements and source categories.

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
        change = re.search(r"db_pool_max\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:->|to)\s*(\d+(?:\.\d+)?)", text)
        concurrency = re.search(r"concurrency\s*[:=]\s*(\d+(?:\.\d+)?)", text)
        return bool(record.source_type == "configs" and change and concurrency
                    and 0 < float(change[2]) < float(change[1])
                    and float(concurrency[1]) > float(change[2]))
    if mode == "postgres_connection_exhaustion":
        if record.source_type == "logs":
            return any(phrase in text for phrase in (
                "remaining connection slots are reserved", "too many connections",
                "connection rejected at max_connections",
            ))
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
            and isinstance(record.metadata.get("connection_limit"), (int, float))
            and record.metadata["connection_limit"] > 0
            and value >= record.metadata["connection_limit"]
        )
    if mode in ("postgres_lock_contention", "postgres_slow_query"):
        return (
            record.source_type == "database"
            and isinstance(record.metadata.get("duration_ms"), (int, float))
            and record.metadata["duration_ms"] > 0
            and (
                bool(record.metadata.get("blocked_by"))
                if mode == "postgres_lock_contention"
                else record.metadata.get("category") == "slow_queries"
            )
        )
    if mode == "redis_unavailable":
        if record.source_type == "logs":
            return "connection refused" in text or "cache unavailable" in text
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
    mechanisms = [r for r in records if cause_discriminator(hypothesis, r)]
    if not mechanisms:
        errors.append("No observed cause-specific discriminator for the candidate")
    elif not any(
        r.source_type in {"logs", "metrics"}
        and any(r.source_path != mechanism.source_path and r.observed_at >= mechanism.observed_at
                for mechanism in mechanisms)
        for r in records
    ):
        errors.append("No temporally compatible cross-source impact or corroboration")
    # Questions remain visible as limitations, not an automatic veto. Actual
    # counterevidence and observed competing mechanisms still block selection.
    if hypothesis.against_ids:
        errors.append("Candidate has contradictory evidence")
    return errors


def competitor_assessments(state: InvestigationState, hypothesis: Hypothesis) -> dict:
    """Retain untested alternatives without giving generic symptoms veto power.

    An alternative needs an observed mechanism discriminator to block. No rival
    is marked rejected here. Unobserved citations stay blocking as an integrity
    failure; absence of telemetry never proves an alternative false.
    """
    assessments = {}
    for other in state.hypotheses:
        if other.hypothesis_id == hypothesis.hypothesis_id or other.status == "REJECTED":
            continue
        missing = sorted(set(other.support_ids + other.against_ids) - set(state.evidence_index))
        matches = [eid for eid in other.support_ids if eid in state.evidence_index
                   and cause_discriminator(other, state.evidence_index[eid])]
        assessments[other.hypothesis_id] = {
            "blocking": bool(missing or matches),
            "reason": "unobserved_citations" if missing else
                      "observed_competing_mechanism" if matches else "no_observed_competing_mechanism",
            "cause_discriminator_ids": matches,
            "missing_evidence_ids": missing,
        }
    return assessments


def finalize_errors(state: InvestigationState, hypothesis: Hypothesis, variant="full") -> list[str]:
    errors = grounding_errors(state, hypothesis)
    if any(a["blocking"] for a in competitor_assessments(state, hypothesis).values()):
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
        if review is None or not (review.verdict == "sufficient" or review.likely_hypothesis_supported):
            errors.append("Independent verifier has not accepted the candidate")
        elif review.contradictions or review.likely_blockers or review.verdict == "conflicted":
            errors.append("Verifier reports a contradiction or competing-mechanism blocker")
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


def likely_assessment_errors(state, hypothesis, variant="full"):
    """Weaker attribution is explicit and never promoted to a confirmed diagnosis."""
    errors = [error for error in grounding_errors(state, hypothesis)
              if error != "Candidate has unresolved questions or contradictory evidence"]
    if hypothesis.against_ids:
        errors.append("Observed contrary evidence prevents a leading prediction")
    if any(a["blocking"] for a in competitor_assessments(state, hypothesis).values()):
        errors.append("Observed competing mechanism remains unresolved")
    records = [state.evidence_index[eid] for eid in hypothesis.support_ids if eid in state.evidence_index]
    mechanisms = [r for r in records if cause_discriminator(hypothesis, r)]
    if not mechanisms or not any(
        r.source_type in {"logs", "metrics"}
        and any(r.source_path != mechanism.source_path and r.observed_at >= mechanism.observed_at
                for mechanism in mechanisms) for r in records
    ):
        errors.append("Leading prediction lacks temporally compatible cross-source corroboration")
    review = next((r for r in reversed(state.reviews)
                   if r.target_hypothesis_id == hypothesis.hypothesis_id), None)
    if review and (review.contradictions or review.verdict == "conflicted" or review.likely_blockers):
        errors.append("Review records a contradiction or material leading-prediction blocker")
    if variant == "full":
        if review is None or not review.likely_hypothesis_supported or not review.cited_evidence_ids:
            errors.append("Independent review has not endorsed a leading explanation")
        else:
            event = next((e for e in reversed(state.events)
                          if e.event_type == "REVIEW"
                          and e.details.get("review", {}).get("target_hypothesis_id")
                          == hypothesis.hypothesis_id), None)
            if (event is None or event.details.get("hypothesis_sha256") != review_fingerprint(hypothesis)
                or event.details.get("evidence_sha256") != evidence_fingerprint(state)):
                errors.append("Leading review does not match the current candidate/evidence snapshot")
    return errors
