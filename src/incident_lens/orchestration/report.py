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
    return "\n\n".join(sections) + "\n"
