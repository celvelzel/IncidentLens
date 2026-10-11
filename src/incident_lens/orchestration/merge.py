"""Only publisher of investigator findings and shared evidence."""

from incident_lens.schemas import InvestigationState


def merge_results(state: InvestigationState, results: list, registry) -> InvestigationState:
    payload = state.model_dump(mode="json")
    tasks = {t.task_id: t for t in state.tasks}
    known = {f.finding_id: f.model_dump(mode="json") for f in state.findings}
    hypotheses = {h.hypothesis_id: h.model_dump(mode="json") for h in state.hypotheses}
    concept_ids = {(h.culprit_service, h.failure_mode): h.hypothesis_id for h in state.hypotheses}
    assessments = {}
    publications = []
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
        publication_ids = all_refs & authorized
        publications.append((context, sorted(publication_ids)))
        for record in registry.get_observed_records(context):
            if record.evidence_id in publication_ids:
                payload["evidence_index"][record.evidence_id] = record.model_dump(mode="json")
        if finding.finding_id not in known:
            payload["findings"].append(finding.model_dump(mode="json"))
            known[finding.finding_id] = finding.model_dump(mode="json")
        elif known[finding.finding_id] != finding.model_dump(mode="json"):
            raise ValueError("Finding ID reused for a different observation/task")
        if task.task_id not in payload["completed_task_ids"]:
            payload["completed_task_ids"].append(task.task_id)
        for h in analysis.hypotheses:
            updated = h.model_dump(mode="json")
            concept = (h.culprit_service, h.failure_mode)
            assessments.setdefault(concept, []).append(h)
            prior_id = hypotheses.get(h.hypothesis_id)
            if prior_id and (prior_id["culprit_service"], prior_id["failure_mode"]) != concept:
                raise ValueError("Hypothesis ID reused for a different cause")
            stable_id = concept_ids.setdefault(concept, h.hypothesis_id)
            previous = hypotheses.get(stable_id)
            if previous and (previous["culprit_service"], previous["failure_mode"]) != concept:
                raise ValueError("Hypothesis ID reused for a different cause")
            updated["hypothesis_id"] = stable_id
            if previous:
                updated["support_ids"] = sorted(set(previous["support_ids"] + h.support_ids))
                updated["against_ids"] = sorted(set(previous["against_ids"] + h.against_ids))
            hypotheses[stable_id] = updated
    for concept, batch in assessments.items():
        combined = hypotheses[concept_ids[concept]]

        def grounded_status(h):
            if h.status == "SUPPORTED" and not h.support_ids:
                return "OPEN"
            if h.status == "REJECTED" and not h.against_ids:
                return "OPEN"
            return h.status

        statuses = {grounded_status(h) for h in batch}
        if {"SUPPORTED", "REJECTED"}.issubset(statuses):
            combined["status"] = "OPEN"
            combined["open_questions"] = sorted(
                {q for h in batch for q in h.open_questions}
                | {"Conflicting current assessments require a discriminating check"}
            )
        else:
            status = (
                "REJECTED"
                if "REJECTED" in statuses
                else "SUPPORTED"
                if "SUPPORTED" in statuses
                else "OPEN"
            )
            combined["status"] = status
            combined["open_questions"] = sorted(
                {q for h in batch if grounded_status(h) == status for q in h.open_questions}
            )
        combined["predicted_observations"] = sorted(
            {observation for h in batch for observation in h.predicted_observations}
        )
    payload["hypotheses"] = list(hypotheses.values())
    # This final validation is performed atomically, before a new graph snapshot.
    validated = InvestigationState.model_validate_json(__import__("json").dumps(payload))
    for context, ids in publications:
        registry.publish(context, ids)
    return validated
