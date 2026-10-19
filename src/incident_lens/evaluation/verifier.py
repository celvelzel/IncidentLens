"""Observable review effects, not an automated claim of causal benefit or truth."""

from incident_lens.llm.usage import aggregate_usage


def verifier_metrics(state):
    events = state.get("events", [])
    effects = [e.get("details", {}) for e in events if e.get("event_type") == "REVIEW_EFFECT"]
    reviews = [e.get("details", {}).get("review", {}) for e in events
               if e.get("event_type") == "REVIEW"]
    calls = [dict(e.get("details", {}), measurement_source=e.get("source")) for e in events
             if e.get("event_type") in {"LLM_CALL", "MODEL_FAILURE"}
             and e.get("role") in {"verifier", "single"}
             and (e.get("role") == "verifier" or e.get("details", {}).get("stage") == "verify"
                  or e.get("details", {}).get("review_stage") is True)]
    return {
        "review_kind": "independent" if any(e.get("role") == "verifier" for e in events)
        else "self_review" if reviews else "absent",
        "completed_reviews": len(reviews),
        "sufficient_reviews": sum(r.get("verdict") == "sufficient" for r in reviews),
        "blocking_reviews": sum(r.get("verdict") in {"insufficient", "conflicted"} for r in reviews),
        "requested_checks": sum(len(r.get("requested_checks", [])) for r in reviews),
        "optional_checks": sum(len(r.get("optional_checks", [])) for r in reviews),
        "repeated_requested_checks": sum(e.get("repeated_requested_checks", 0) for e in effects),
        "reviews_discharge_gate": sum(e.get("gate_discharged") is True for e in effects),
        "reviews_add_blockers": sum(e.get("added_blockers") is True for e in effects),
        "reused_reviews": sum(e.get("event_type") == "REVIEW_REUSED" for e in events),
        "skipped_reviews": sum(e.get("event_type") == "REVIEW_SKIPPED" for e in events),
        "citation_validation_events": sum(e.get("event_type") == "REVIEW_CITATION_VALIDATION" for e in events),
        "requested_check_followups": [e.get("details", {}) for e in events
                                      if e.get("event_type") == "REVIEW_FOLLOWUP"],
        "followups_with_new_evidence": sum(
            bool(e.get("details", {}).get("new_evidence_ids")) for e in events
            if e.get("event_type") == "REVIEW_FOLLOWUP"
        ),
        "llm_requests": sum(c.get("llm_calls", 0) for c in calls),
        "http_requests": sum(c.get("actual_http_requests", c.get("llm_calls", 0)
                                   if c.get("measurement_source") == "model" else 0) for c in calls),
        "usage": aggregate_usage(calls),
        "effects": effects,
        "benefit_assessment": "pending_manual_or_paired_evaluation",
        "caveat": "Gate changes and new evidence do not establish corrected diagnosis or causal benefit.",
    }
