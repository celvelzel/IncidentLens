"""Rescue finalization: a verified diagnosis must survive pure transport failure."""

from datetime import datetime, timezone
from types import SimpleNamespace

from incident_lens.evaluation.termination import accepted_diagnosis, normalize_termination
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.orchestration.guards import (
    evidence_fingerprint,
    finalize_errors,
    review_fingerprint,
)
from incident_lens.schemas import (
    Budget,
    CasePublicInput,
    CoordinatorDecision,
    EvidenceRecord,
    Finding,
    Hypothesis,
    InvestigationState,
    InvestigationTask,
    Review,
    TraceEvent,
)
from incident_lens.schemas.workflow import termination_result

NOW = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)
RUN_ID = "run-rescue-1"
INCIDENT_ID = "incident_001"


def transport_errors(stage="coordinate", count=2):
    return [
        {"message": "TIMEOUT", "stage": stage, "error_code": "PROVIDER_TIMEOUT", "transport_error": True}
        for _ in range(count)
    ]


def evidence_index():
    return {
        "ev-config": EvidenceRecord(
            evidence_id="ev-config",
            incident_id=INCIDENT_ID,
            source_type="configs",
            service="backend",
            observed_at=NOW,
            source_path="public/configs/pool.yaml",
            excerpt="db_pool_max: 8 -> 2; concurrency=7",
        ),
        "ev-change": EvidenceRecord(
            evidence_id="ev-change",
            incident_id=INCIDENT_ID,
            source_type="changes",
            service="backend",
            observed_at=NOW,
            source_path="public/changes/1.yaml",
            excerpt="Reduced backend pool capacity",
            metadata={"change_id": "chg-1"},
        ),
        "ev-metric": EvidenceRecord(
            evidence_id="ev-metric",
            incident_id=INCIDENT_ID,
            source_type="metrics",
            service="backend",
            observed_at=NOW,
            source_path="public/metrics/pool.yaml",
            excerpt="pool_waiters elevated",
            metadata={"metric_name": "pool_waiters", "value": 5},
        ),
    }


def fake_run():
    run = InvestigationRun.__new__(InvestigationRun)
    run.journal = None
    run.variant = "full"
    run.response_profile = False
    run.registry = SimpleNamespace(call_count=0)
    run.call_budget = SimpleNamespace(calls=0, tokens=0, usage=[])
    run.task_manager = SimpleNamespace(records=[])
    return run


def build_state(
    error_details=None,
    verdict="sufficient",
    action="FINALIZE",
    stop_reason="TIMEOUT",
    termination_reason="UNRECOVERABLE_ERROR",
    with_errors=True,
):
    index = evidence_index()
    candidate = Hypothesis(
        hypothesis_id="hyp-backend-pool",
        culprit_service="backend",
        failure_mode="backend_pool_config_regression",
        support_ids=list(index),
        predicted_observations=[
            "Reduced backend pool capacity causes local acquisition contention"
        ],
        status="OPEN",
    )
    rejected = Hypothesis(
        hypothesis_id="hyp-redis",
        culprit_service="redis",
        failure_mode="redis_unavailable",
        predicted_observations=["Cache availability fails"],
        status="REJECTED",
    )
    task = InvestigationTask(
        task_id="t-check",
        role="metrics",
        question="Measure backend pool capacity",
        allowed_tools=["query_metrics"],
        reason="Resolve the causal gap",
        expected_discriminator="Compare pool capacity with database capacity",
    )
    finding = Finding(
        finding_id="f-check",
        task_id="t-check",
        run_id=RUN_ID,
        incident_id=INCIDENT_ID,
        role="metrics",
        claim="Observed backend pool saturation",
        evidence_ids=["ev-metric"],
        relation="supports",
        confidence_qualifier="supported",
    )
    review = Review(
        target_hypothesis_id=candidate.hypothesis_id,
        verdict=verdict,
        cited_evidence_ids=list(index),
        rationale="Independent sources and a cause discriminator support the candidate",
    )
    decision = CoordinatorDecision(
        action=action,
        reason="Verifier accepted causal evidence"
        if action == "FINALIZE"
        else "Observed evidence lacks sufficient causal support",
        selected_hypothesis_id=candidate.hypothesis_id if action == "FINALIZE" else None,
        stop_reason="Evidence sufficient" if action == "FINALIZE" else "Missing discriminating evidence",
    )
    termination = termination_result(
        "INCONCLUSIVE" if action == "ABSTAIN" and not with_errors else termination_reason,
        failure_stage="coordinate" if with_errors else None,
    )
    state = InvestigationState(
        workspace_id="incident-lens",
        incident_id=INCIDENT_ID,
        run_id=RUN_ID,
        public_summary=CasePublicInput(
            incident_id=INCIDENT_ID,
            title="Backend error spike",
            started_at=NOW,
            observed_symptoms=["checkout errors"],
            services=["backend", "postgres"],
        ),
        budgets=Budget(),
        findings=[finding],
        evidence_index=index,
        hypotheses=[candidate, rejected],
        tasks=[task],
        reviews=[review],
        decisions=[decision],
        events=[],
        stop_reason=stop_reason,
        workflow_status="FAILED" if with_errors else "FINISHED",
        termination=termination,
    )

    def add(event_type, details, role=None):
        state.events.append(
            TraceEvent(
                event_id=f"event-{len(state.events) + 1}",
                run_id=RUN_ID,
                incident_id=INCIDENT_ID,
                timestamp=NOW,
                event_type=event_type,
                role=role,
                details=details,
                source="runtime",
            )
        )

    add(
        "REVIEW",
        {
            "review": review.model_dump(mode="json"),
            "hypothesis_sha256": review_fingerprint(candidate),
            "evidence_sha256": evidence_fingerprint(SimpleNamespace(evidence_index=index)),
        },
        role="verifier",
    )
    if with_errors:
        for details in error_details if error_details is not None else transport_errors():
            add("RUNTIME_ERROR", dict(details))
    request = {
        "incident_id": INCIDENT_ID,
        "run_id": RUN_ID,
        "stop_reason": termination.reason,
        "message_type": "WORKFLOW_STOP_REQUESTED",
        "protocol_version": "2",
        "required_roles": ["coordinator"],
        "stage": "coordinate",
    }
    add("WORKFLOW_STOP_REQUESTED", request, role="coordinator")
    add("STOP_ACK", {**request, "message_type": "STOP_ACK"}, role="coordinator")
    add(
        "RUNTIME_FAILURE" if termination.runtime_failure else "NORMAL_TERMINATION",
        termination.model_dump(mode="json"),
    )
    review_event_id = state.events[0].event_id
    return state, candidate, review_event_id


def completed(state):
    return fake_run().report({"investigation": state})["investigation"]


async def test_rescue_emits_resolved_report_with_rescued_acceptance():
    state, candidate, review_event_id = build_state()
    result = completed(state)
    assert result.report.status == "RESOLVED"
    assert result.report.root_cause.hypothesis_id == candidate.hypothesis_id
    assert result.report.root_cause.status == "SUPPORTED"
    accepted = next(e for e in result.events if e.event_type == "DIAGNOSIS_ACCEPTED")
    assert accepted.details["rescued"] is True
    assert accepted.details["rescue_review_event_id"] == review_event_id
    assert accepted.details["root_cause"] == result.report.root_cause.model_dump(mode="json")
    assert accepted.details["supporting_evidence_ids"] == result.report.supporting_evidence_ids
    assert result.report.stop_reason == "Evidence sufficient"


async def test_missing_sufficient_review_blocks_rescue():
    state, _, _ = build_state(verdict="insufficient")
    run = fake_run()
    assert run.rescue_report(state) is None
    result = run.report({"investigation": state})["investigation"]
    assert result.report.status == "INCONCLUSIVE"
    assert result.report.root_cause is None
    assert not any(e.event_type == "DIAGNOSIS_ACCEPTED" for e in result.events)


async def test_non_transport_runtime_error_blocks_rescue():
    state, _, _ = build_state(
        error_details=[
            {
                "message": "TIMEOUT",
                "stage": "coordinate",
                "error_code": "PROVIDER_TIMEOUT",
                "transport_error": True,
            },
            {
                "message": "STRUCTURED_OUTPUT_INVALID",
                "stage": "coordinate",
                "error_code": "STRUCTURED_OUTPUT_INVALID",
                "transport_error": False,
            },
        ]
    )
    run = fake_run()
    assert run.rescue_report(state) is None
    result = run.report({"investigation": state})["investigation"]
    assert result.report.status == "INCONCLUSIVE"
    assert not any(e.event_type == "DIAGNOSIS_ACCEPTED" for e in result.events)


async def test_rescued_termination_keeps_honest_runtime_accounting():
    state, _, review_event_id = build_state()
    result = completed(state)
    terminal = normalize_termination(result.model_dump(mode="json"))
    assert terminal["protocol_valid"] is True
    assert terminal["termination_reason"] == "UNRECOVERABLE_ERROR"
    assert terminal["runtime_failure"] is True
    assert terminal["diagnosis_failure"] is False
    assert accepted_diagnosis(result.model_dump(mode="json")) is True
    forged = result.model_dump(mode="json")
    accepted = next(
        e for e in forged["events"] if e.get("event_type") == "DIAGNOSIS_ACCEPTED"
    )
    accepted["details"]["rescue_review_event_id"] = "event-forged"
    assert accepted_diagnosis(forged) is False
    assert review_event_id in {e["event_id"] for e in forged["events"]}


async def test_abstain_and_budget_states_are_not_rescued():
    abstain, _, _ = build_state(action="ABSTAIN", with_errors=False)
    run = fake_run()
    assert run.rescue_report(abstain) is None
    result = run.report({"investigation": abstain})["investigation"]
    assert result.report.status == "INCONCLUSIVE"
    terminal = normalize_termination(result.model_dump(mode="json"))
    assert terminal["termination_reason"] == "INCONCLUSIVE"
    assert terminal["diagnosis_failure"] is False
    assert accepted_diagnosis(result.model_dump(mode="json")) is False

    abstain_error, _, _ = build_state(action="ABSTAIN")
    assert fake_run().rescue_report(abstain_error) is None

    budget, _, _ = build_state(
        stop_reason="LLM call budget exhausted", termination_reason="BUDGET_EXHAUSTED"
    )
    assert fake_run().rescue_report(budget) is None


async def test_rescue_requires_unique_finalizable_hypothesis():
    state, candidate, _ = build_state()
    competitor = state.hypotheses[1].model_copy(
        update={
            "status": "OPEN",
            "culprit_service": "backend",
            "failure_mode": "backend_pool_config_regression",
            "support_ids": list(candidate.support_ids),
            "open_questions": [],
        }
    )
    state.hypotheses[1] = competitor
    assert finalize_errors(state, candidate, "full") != []
    assert finalize_errors(state, competitor, "full") != []
    assert fake_run().rescue_report(state) is None
