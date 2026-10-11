"""Only publisher of investigator findings and shared evidence."""

from incident_lens.schemas import InvestigationState


def merge_results(state: InvestigationState, results: list, registry) -> InvestigationState:
    payload = state.model_dump(mode="json")
    tasks = {t.task_id: t for t in state.tasks}
    known = {f.finding_id for f in state.findings}
    hypotheses = {h.hypothesis_id: h.model_dump(mode="json") for h in state.hypotheses}
    for context, task, analysis in results:
        finding = analysis.finding
        if (finding.run_id, finding.incident_id, finding.task_id, finding.role) != (
            state.run_id,
            state.incident_id,
            task.task_id,
            task.role,
        ) or task.task_id not in tasks:
            raise ValueError("Rejected worker identity/task mismatch")
        authorized = registry.observed_ids(context)
        all_refs = set(finding.evidence_ids)
        for h in analysis.hypotheses:
            all_refs.update(h.support_ids + h.against_ids)
        # Workers may combine already published observations, but cannot introduce
        # another role's unshared evidence or unqueried IDs.
        if not set(finding.evidence_ids).issubset(authorized):
            raise ValueError("Finding cites evidence not observed by this worker")
        if not all_refs.issubset(authorized | set(state.evidence_index)):
            raise ValueError("Hypothesis cites unpublished or unobserved evidence")
        registry.publish(context, list(finding.evidence_ids))
        for record in registry.get_observed_records(context):
            if record.evidence_id in finding.evidence_ids:
                payload["evidence_index"][record.evidence_id] = record.model_dump(mode="json")
        if finding.finding_id not in known:
            payload["findings"].append(finding.model_dump(mode="json"))
            known.add(finding.finding_id)
        if task.task_id not in payload["completed_task_ids"]:
            payload["completed_task_ids"].append(task.task_id)
        for h in analysis.hypotheses:
            updated = h.model_dump(mode="json")
            previous = hypotheses.get(h.hypothesis_id)
            if previous:
                updated["support_ids"] = sorted(set(previous["support_ids"] + h.support_ids))
                updated["against_ids"] = sorted(set(previous["against_ids"] + h.against_ids))
            hypotheses[h.hypothesis_id] = updated
    payload["hypotheses"] = list(hypotheses.values())
    # This final validation is performed atomically, before a new graph snapshot.
    return InvestigationState.model_validate_json(__import__("json").dumps(payload))
