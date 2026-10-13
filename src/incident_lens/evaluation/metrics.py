"""Recomputable scores; citation existence is distinct from semantic support."""

VARIANTS = ("single", "fixed", "dynamic_no_verifier", "full")


def report_citations(report):
    if not report:
        return []
    ids = list(report.get("supporting_evidence_ids", []))
    for hypothesis in [report.get("root_cause"), *report.get("rejected_hypotheses", [])]:
        if hypothesis:
            ids.extend(hypothesis.get("support_ids", []))
            ids.extend(hypothesis.get("against_ids", []))
    return sorted(set(ids))


def score_completed(state, oracle):
    """The caller must finish execution before supplying the evaluator-only oracle."""
    report = state.get("report")
    if report is None:
        raise ValueError("evaluation requires a completed report")
    identifiable = oracle["is_identifiable"]
    if not isinstance(identifiable, bool):
        raise ValueError("oracle identifiability must be boolean")
    root = report.get("root_cause")
    runtime_failure = any(
        event.get("event_type") in {"MODEL_FAILURE", "RUNTIME_ERROR"}
        or (
            event.get("event_type") == "STOP"
            and (
                event.get("details", {}).get("message_type") != "STOP"
                or event.get("details", {}).get("stop_reason")
                in {"BUDGET_EXHAUSTED", "UNRECOVERABLE_ERROR"}
            )
        )
        for event in state.get("events", [])
    )
    correct = bool(
        not runtime_failure
        and report["status"] == "RESOLVED"
        and root
        and root["culprit_service"] == oracle["culprit_service"]
        and root["failure_mode"] == oracle["failure_mode"]
    )
    abstained = not runtime_failure and report["status"] == "INCONCLUSIVE" and root is None
    citations = report_citations(report)
    index = state.get("evidence_index", {})
    observed = {
        record["evidence_id"]
        for event in state.get("events", [])
        if event["event_type"] == "TOOL_CALL"
        for record in event.get("details", {}).get("result", {}).get("records", [])
        if record.get("incident_id") == state["incident_id"]
    }
    valid = [
        eid
        for eid in citations
        if eid in index
        and eid in observed
        and index[eid].get("incident_id") == state["incident_id"]
    ]
    misleading = bool(oracle.get("misleading_evidence_ids"))
    return dict(
        identifiable=identifiable,
        runtime_failure=runtime_failure,
        root_cause_correct=correct if identifiable else None,
        correct_abstention=abstained if not identifiable else None,
        misleading_case=misleading,
        misleading_correct=correct if misleading and identifiable else None,
        misleading_decoy_observed=bool(set(oracle.get("misleading_evidence_ids", [])) & set(index)),
        citation_count=len(citations),
        valid_citation_count=len(valid),
        citation_existence_validity=len(valid) / len(citations) if citations else None,
        unsupported_claim_rate=None,
        semantic_review_status="unreviewed",
    )


def aggregate(rows):
    result = []
    for variant in VARIANTS:
        group = [r for r in rows if r["variant"] == variant]
        if not group:
            continue

        def ratio(key):
            values = [r[key] for r in group if r.get(key) is not None]
            return sum(values), len(values), sum(values) / len(values) if values else None

        accuracy_n, accuracy_d, accuracy = ratio("root_cause_correct")
        abstention_n, abstention_d, abstention = ratio("correct_abstention")
        misleading_n, misleading_d, misleading = ratio("misleading_correct")
        citations = sum(r.get("citation_count", 0) for r in group)
        valid = sum(r.get("valid_citation_count", 0) for r in group)

        def measured_sum(key):
            values = [r.get(key) for r in group]
            return sum(values) if all(v is not None for v in values) else None

        result.append(
            dict(
                variant=variant,
                source=group[0]["source"],
                split=group[0]["split"],
                runs=len(group),
                error_runs=sum(r["status"] == "ERROR" for r in group),
                runtime_failure_runs=sum(bool(r.get("runtime_failure", False)) for r in group),
                resolved_runs=sum(r["status"] == "RESOLVED" for r in group),
                inconclusive_runs=sum(r["status"] == "INCONCLUSIVE" for r in group),
                root_cause_correct=accuracy_n,
                identifiable_denominator=accuracy_d,
                root_cause_accuracy=accuracy,
                correct_abstentions=abstention_n,
                unidentifiable_denominator=abstention_d,
                correct_abstention_rate=abstention,
                misleading_correct=misleading_n,
                misleading_identifiable_denominator=misleading_d,
                misleading_accuracy=misleading,
                valid_citations=valid,
                citation_denominator=citations,
                citation_existence_validity=valid / citations if citations else None,
                tool_calls=measured_sum("tool_calls"),
                llm_requests=measured_sum("llm_requests"),
                total_tokens=measured_sum("total_tokens"),
                cost_usd=measured_sum("cost_usd"),
                failed_calls=measured_sum("failed_calls"),
                latency_ms=measured_sum("latency_ms"),
                unsupported_claim_rate=None,
                semantic_review_status="unreviewed",
                cache_mode="off",
            )
        )
    return result
