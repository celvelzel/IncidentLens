"""Deterministic evidence-reference rendering, no provider calls."""

from incident_lens.schemas import RCAReport


def render_report(report: RCAReport) -> str:
    title = report.root_cause.failure_mode if report.root_cause else "No supported root cause"
    sections = [
        f"# IncidentLens — {report.status}",
        f"Run: `{report.run_id}`",
        f"Incident: `{report.incident_id}`",
        f"## Root cause\n{title}",
        "## Causal chain\n" + "\n".join(f"- {s}" for s in report.causal_chain),
        "## Supporting evidence\n" + "\n".join(f"- `{e}`" for e in report.supporting_evidence_ids),
        "## Rejected hypotheses\n"
        + "\n".join(f"- {h.failure_mode}: {h.against_ids}" for h in report.rejected_hypotheses),
        "## Unresolved\n" + "\n".join(f"- {s}" for s in report.unresolved),
        f"## Stop reason\n{report.stop_reason}",
    ]
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
