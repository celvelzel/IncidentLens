"""Read-only benchmark normalization; saved runtime facts remain intact."""

from incident_lens.evaluation.metrics import report_citations
from incident_lens.evaluation.termination import normalize_termination


def normalize(state):
    terminal = normalize_termination(state)
    report = state.get("report") or {}
    technical_ok = bool(
        state.get("report")
        and not state.get("execution_error")
        and not terminal["runtime_failure"]
        and terminal["protocol_valid"] is not False
        and terminal["stop_completion"]
        and report.get("status") != "ERROR"
    )
    citations = report_citations(state.get("report"))
    observed = set()
    for event in state.get("events", []):
        if (
            event.get("event_type") != "TOOL_CALL"
            or event.get("run_id") != state.get("run_id")
            or event.get("incident_id") != state.get("incident_id")
        ):
            continue
        result = event.get("details", {}).get("result", {})
        if result.get("ok") is True:
            for record in result.get("records", []):
                eid = record.get("evidence_id")
                if record.get("incident_id") == state.get("incident_id") and record == state.get(
                    "evidence_index", {}
                ).get(eid):
                    observed.add(eid)
    valid = len(set(citations) & observed)
    return {
        **terminal,
        "citation_count": len(citations),
        "valid_citation_count": valid,
        "citation_existence_validity": valid / len(citations) if citations else None,
        "technical_completion": technical_ok,
        "investigation_completion": technical_ok,
        "resolved": report.get("status") == "RESOLVED",
        "abstained": technical_ok
        and report.get("status") == "INCONCLUSIVE"
        and report.get("root_cause") is None
        and terminal["termination_reason"] != "NO_ALERT",
    }
