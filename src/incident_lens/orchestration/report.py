"""Deterministic evidence-reference rendering, no provider calls."""

from incident_lens.schemas import RCAReport

from .guards import cause_discriminator, competitor_assessments, grounding_errors


def observed_chain(state, hypothesis):
    """Render observed supporting records, never promote predictions to facts."""
    records = [state.evidence_index[eid] for eid in set(hypothesis.support_ids)]
    return [f"{r.observed_at.isoformat()} [{r.evidence_id}] {r.service}: {r.excerpt}"
            for r in sorted(records, key=lambda r: (r.observed_at, r.evidence_id))]


def populate_assessment(state):
    """Preserve useful work without promoting a tentative cause to a diagnosis.

    This is deterministic rendering of shared observations and assessments. It
    neither calls a model nor changes hypotheses, decisions, gates or scoring.
    """
    report = state.report
    if report.status == "RESOLVED":
        report.assessment_level = "CONFIRMED"
        review = next((r for r in reversed(state.reviews)
                       if r.target_hypothesis_id == report.root_cause.hypothesis_id), None)
        report.optional_questions = list(dict.fromkeys(report.root_cause.optional_questions
            + ([check.question for check in review.optional_checks] if review else [])))
        return

    def observations(h):
        return [state.evidence_index[eid] for eid in set(h.support_ids)
                if eid in state.evidence_index]

    candidates = [h for h in state.hypotheses if h.status != "REJECTED"
                  and any(r.source_type != "topology" for r in observations(h))
                  and set(h.support_ids + h.against_ids).issubset(state.evidence_index)]
    candidates.sort(key=lambda h: (
        -int(any(cause_discriminator(h, r) for r in observations(h))),
        -len({r.source_path for r in observations(h)}),
        bool(h.against_ids), len(h.open_questions), h.hypothesis_id,
    ))
    report.assessment_level = "INSUFFICIENT"
    report.provisional_hypotheses = [h.model_copy(deep=True, update={"status": "OPEN"})
                                     for h in candidates[:3]]
    report.assessment_basis = [
        "Unconfirmed explanations are ordered by observed mechanism support, source diversity, "
        "then unresolved evidence; this is not a probability or an accepted diagnosis."
    ]
    if not candidates:
        report.assessment_basis = ["No non-rejected explanation has observed supporting telemetry."]
        report.next_steps = ["Collect a cause-specific observation before proposing a root cause."]
        return

    leading = candidates[0]
    report.provisional_observations = observed_chain(state, leading)
    review = next((r for r in reversed(state.reviews)
                   if r.target_hypothesis_id == leading.hypothesis_id), None)
    gaps = list(state.open_questions) + list(leading.open_questions)
    if leading.against_ids:
        gaps.append("Resolve observed contrary evidence: " + ", ".join(leading.against_ids))
    competitors = competitor_assessments(state, leading)
    material = [hid for hid, assessment in competitors.items() if assessment["blocking"]]
    if material:
        rivals = [f"{h.culprit_service}/{h.failure_mode}" for h in state.hypotheses
                  if h.hypothesis_id in material]
        gaps.append("Distinguish observed competing explanations: " + ", ".join(rivals))
    if review:
        gaps += list(review.contradictions) + [c.question for c in review.requested_checks]
    errors = grounding_errors(state, leading)
    readable_errors = {
        "Need at least two supporting records from different sources": "The explanation needs supporting observations from two independent sources.",
        "Candidate lacks discriminating predicted observations": "The explanation does not state what would distinguish it from alternatives.",
        "No observed cause-specific discriminator for the candidate": "No observed record yet establishes the proposed failure mechanism.",
        "No supported discriminating investigation": "No completed check has established the proposed mechanism.",
        "Candidate has unresolved questions or contradictory evidence": "Resolve the attribution questions or contrary observations above.",
    }
    gaps += [readable_errors.get(error, error) for error in errors]
    # A likely assessment is still INCONCLUSIVE/root_cause=null. Material gaps,
    # conflicting review or runtime failure never receive this stronger label.
    if (not errors and not state.open_questions and not material
        and (review is None or review.verdict == "sufficient")
        and (review is None or not review.contradictions and not review.requested_checks)
        and not (state.termination and state.termination.runtime_failure)):
        report.assessment_level = "LIKELY"
        report.assessment_basis.append(
            "One candidate has cross-source mechanism support without recorded causal blockers; "
            "the workflow has not accepted a final diagnosis."
        )
    else:
        report.assessment_basis.append("Causal attribution remains insufficient or conflicted.")
    if review and review.verdict != "sufficient":
        gaps.append("Latest review has not accepted the explanation: " + review.rationale)
    if gaps:
        report.unresolved = list(dict.fromkeys(gaps))
    else:
        report.unresolved = ["No specific causal blocker is recorded, but final attribution has not been accepted."]
    report.optional_questions = list(dict.fromkeys(
        leading.optional_questions + ([c.question for c in review.optional_checks] if review else [])))
    checks = list(review.requested_checks) if review else list(state.requested_checks)
    completed = set(state.completed_task_ids)
    steps = [f"{check.question} Discriminator: {check.expected_discriminator}"
             for check in checks if check.task_id not in completed]
    if not steps and report.assessment_level == "LIKELY":
        steps = ["Review the cited observations and record whether they justify attribution. "
                 "Name any remaining blocking gap before collecting more telemetry."]
    if not steps:
        steps = ["Obtain new observations to answer: " + question for question in leading.open_questions]
    if not steps:
        steps = [f"Obtain evidence linking {leading.culprit_service}/{leading.failure_mode} "
                 "to the reported failures and distinguishing material alternatives."]
    report.next_steps = list(dict.fromkeys(steps))[:3]


def render_report(report: RCAReport) -> str:
    title = report.root_cause.failure_mode if report.root_cause else "No confirmed root cause"
    sections = [
        f"# IncidentLens — {report.status}",
        f"Run: `{report.run_id}`",
        f"Incident: `{report.incident_id}`",
        f"## Root cause\n{title}",
    ]
    if report.assessment_level:
        sections.insert(3, "## Evidence assessment\n" + {
            "CONFIRMED": "Confirmed by the investigation workflow",
            "LIKELY": "Likely explanation — NOT confirmed; no accepted root cause",
            "INSUFFICIENT": "Insufficient evidence for a confirmed attribution",
        }[report.assessment_level])
    if report.root_cause:
        sections.append("## Causal chain\n" + "\n".join(f"- {s}" for s in report.causal_chain))
        if report.root_cause.predicted_observations:
            sections.append("## Predictions (not confirmed observations)\n" + "\n".join(
                f"- {s}" for s in report.root_cause.predicted_observations))
        sections.append("## Supporting evidence\n" + "\n".join(
            f"- `{e}`" for e in report.supporting_evidence_ids))
    if report.provisional_hypotheses:
        sections.append("## Leading explanations — NOT confirmed\n" + "\n".join(
            f"- {h.culprit_service}: {h.failure_mode}; observed support: {', '.join(h.support_ids)}"
            + (f"; contrary evidence: {', '.join(h.against_ids)}" if h.against_ids else "")
            for h in report.provisional_hypotheses
        ))
        sections.append("## Observations for leading explanation — attribution unconfirmed\n"
                        + "\n".join("- " + item for item in report.provisional_observations))
    for title, items in (("Assessment basis", report.assessment_basis),
                         ("Unresolved", report.unresolved),
                         ("Suggested next checks — not executed; new telemetry may be required", report.next_steps),
                         ("Optional corroboration — does not block a conclusion", report.optional_questions)):
        if items:
            sections.append("## " + title + "\n" + "\n".join("- " + item for item in items))
    if report.rejected_hypotheses:
        sections.append("## Rejected hypotheses\n" + "\n".join(
            f"- {h.failure_mode}: {h.against_ids}" for h in report.rejected_hypotheses))
    sections.append(f"## Stop reason\n{report.stop_reason}")
    if report.diagnosis_status is not None:
        sections.append(
            f"## Workflow\nDiagnosis: {report.diagnosis_status}\nRemediation: {report.remediation_status}\nWorkflow: {report.workflow_status}"
        )
    if report.remediation_plan:
        plan = report.remediation_plan
        sections.append(
            "## Remediation — PLAN_ONLY\nProposal only; no actions executed and no service recovery confirmed.\n"
            + plan.objective
        )
        for name in (
            "affected_services",
            "actions",
            "preconditions",
            "risks",
            "verification_steps",
            "rollback",
            "evidence_ids",
        ):
            sections.append(
                "### "
                + name.replace("_", " ").title()
                + "\n"
                + "\n".join("- " + v for v in getattr(plan, name))
            )
    if report.termination:
        result = report.termination
        sections.append(
            f"## Termination\nReason: {result.reason}\nOutcome: {result.outcome}"
            f"\nStop completed: {result.stop_completed}\nRuntime failure: {result.runtime_failure}"
            f"\nFailure stage: {result.failure_stage or 'none'}"
        )
    return "\n\n".join(sections) + "\n"
