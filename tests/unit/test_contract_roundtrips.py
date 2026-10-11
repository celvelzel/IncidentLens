from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from incident_lens.schemas import (
    CasePublicInput,
    CoordinatorDecision,
    EvidenceRecord,
    Finding,
    Hypothesis,
    InvestigationState,
    InvestigationTask,
    RCAReport,
    Review,
    TraceEvent,
)


def objects():
    now = datetime.now(timezone.utc)
    case = CasePublicInput(
        incident_id="i1",
        title="Failure",
        started_at=now,
        observed_symptoms=["500 errors"],
        services=["backend"],
    )
    record = EvidenceRecord(
        evidence_id="i1-log-1",
        incident_id="i1",
        source_type="logs",
        service="backend",
        observed_at=now,
        source_path="public/logs.jsonl",
        excerpt="timeout",
    )
    task = InvestigationTask(
        task_id="t1",
        role="logs",
        question="When did errors begin?",
        allowed_tools=["query_logs"],
        reason="timeline",
        expected_discriminator="error onset",
    )
    finding = Finding(
        finding_id="f1",
        task_id="t1",
        run_id="r1",
        incident_id="i1",
        role="logs",
        claim="Timeout observed",
        evidence_ids=[record.evidence_id],
        relation="supports",
        confidence_qualifier="weak",
    )
    hypothesis = Hypothesis(
        hypothesis_id="h1",
        culprit_service="backend",
        failure_mode="unknown",
        support_ids=[record.evidence_id],
    )
    review = Review(
        target_hypothesis_id="h1",
        verdict="insufficient",
        requested_checks=[task],
        cited_evidence_ids=[record.evidence_id],
        rationale="Need metrics",
    )
    event = TraceEvent(
        event_id="event1",
        run_id="r1",
        incident_id="i1",
        timestamp=now,
        event_type="ASSIGNMENT",
        source="runtime",
        task_id="t1",
    )
    decision = CoordinatorDecision(action="INVESTIGATE", reason="timeline", assignments=[task])
    state = InvestigationState(
        workspace_id="w1",
        incident_id="i1",
        run_id="r1",
        public_summary=case,
        tasks=[task],
        findings=[finding],
        hypotheses=[hypothesis],
        reviews=[review],
        events=[event],
        decisions=[decision],
        evidence_index={record.evidence_id: record},
    )
    return [record, task, finding, hypothesis, review, event, decision, state]


@pytest.mark.parametrize("index", range(8))
def test_all_message_types_json_roundtrip(index):
    value = objects()[index]
    assert type(value).model_validate_json(value.model_dump_json()) == value


def test_state_rejects_unobserved_citation_and_duplicate_tasks():
    state = objects()[-1]
    for changes in ({"evidence_index": {}}, {"tasks": state.tasks * 2}):
        with pytest.raises(ValidationError):
            InvestigationState(**(state.model_dump() | changes))


def test_state_rejects_wrong_worker_role():
    state = objects()[-1]
    wrong = state.findings[0].model_copy(update={"role": "changes"})
    with pytest.raises(ValidationError):
        InvestigationState(**(state.model_dump() | {"findings": [wrong]}))


def test_state_rejects_unobserved_rejected_hypothesis_citation():
    state = objects()[-1]
    rejected = Hypothesis(
        hypothesis_id="rejected",
        culprit_service="backend",
        failure_mode="unknown",
        status="REJECTED",
        against_ids=["fabricated"],
    )
    report = RCAReport(
        run_id="r1",
        incident_id="i1",
        status="INCONCLUSIVE",
        rejected_hypotheses=[rejected],
        stop_reason="missing evidence",
    )
    with pytest.raises(ValidationError):
        InvestigationState(**(state.model_dump() | {"report": report}))
