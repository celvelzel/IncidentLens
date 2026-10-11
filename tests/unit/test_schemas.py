from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from incident_lens.cache.policy import CacheNamespace, CachePolicy
from incident_lens.schemas import (
    Budget,
    CasePublicInput,
    CoordinatorDecision,
    EvidenceRecord,
    Finding,
    Hypothesis,
    InvestigationState,
    InvestigationTask,
    RCAReport,
    ToolResult,
)
from incident_lens.security.context import AgentContext


def case():
    return CasePublicInput(
        incident_id="inc-1",
        title="Latency",
        started_at=datetime.now(timezone.utc),
        observed_symptoms=["slow"],
        services=["api"],
    )


def evidence(**changes):
    data = dict(
        evidence_id="e-1",
        incident_id="inc-1",
        source_type="logs",
        service="api",
        observed_at=datetime.now(timezone.utc),
        source_path="public/logs/api.jsonl",
        excerpt="timeout",
    )
    return EvidenceRecord(**(data | changes))


def test_json_roundtrip_and_extra_forbid():
    value = case()
    assert CasePublicInput.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        CasePublicInput(**(value.model_dump() | {"secret": "bad"}))


@pytest.mark.parametrize("invalid", ["bad/id", "", "../secret", "a b"])
def test_invalid_identifiers(invalid):
    with pytest.raises(ValidationError):
        evidence(evidence_id=invalid)


def test_timezone_and_strict_types():
    with pytest.raises(ValidationError):
        evidence(observed_at=datetime.now())
    with pytest.raises(ValidationError):
        Budget(max_rounds="4")


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../truth.json",
        "public/../truth",
        "C:/secret",
        "public\\logs",
        "private/truth.json",
        ".hidden/data",
        "public//logs",
        "ground_truth.json",
        "logs/data.json",
    ],
)
def test_invalid_public_paths(path):
    with pytest.raises(ValidationError):
        evidence(source_path=path)


def test_tool_result_counts_and_errors():
    record = evidence()
    good = ToolResult(call_id="call-1", ok=True, records=[record], record_count=1)
    assert ToolResult.model_validate_json(good.model_dump_json()) == good
    for changes in ({"record_count": 0}, {"elapsed_ms": -1.0}, {"error_code": "ERR"}):
        with pytest.raises(ValidationError):
            ToolResult(**(good.model_dump() | changes))
    with pytest.raises(ValidationError):
        ToolResult(call_id="call-2", ok=False)


def test_decision_semantics():
    task = InvestigationTask(
        task_id="t-1",
        role="logs",
        question="What changed?",
        allowed_tools=["query_logs"],
        reason="investigate",
        expected_discriminator="timeout",
    )
    CoordinatorDecision(action="INVESTIGATE", reason="need evidence", assignments=[task])
    CoordinatorDecision(
        action="FINALIZE", reason="verified", selected_hypothesis_id="h-1", stop_reason="verified"
    )
    CoordinatorDecision(action="ABSTAIN", reason="budget", stop_reason="budget")
    for data in (
        dict(action="INVESTIGATE", reason="empty"),
        dict(action="FINALIZE", reason="missing", stop_reason="done"),
        dict(action="ABSTAIN", reason="bad", stop_reason="done", selected_hypothesis_id="h-1"),
    ):
        with pytest.raises(ValidationError):
            CoordinatorDecision(**data)


def test_report_constraints():
    hypothesis = Hypothesis(
        hypothesis_id="h-1", culprit_service="api", failure_mode="timeout", status="SUPPORTED"
    )
    report = RCAReport(
        run_id="run-1",
        incident_id="inc-1",
        status="RESOLVED",
        root_cause=hypothesis,
        causal_chain=["timeout causes latency"],
        supporting_evidence_ids=["e-1"],
        stop_reason="verified",
    )
    assert RCAReport.model_validate_json(report.model_dump_json()) == report
    with pytest.raises(ValidationError):
        RCAReport(**(report.model_dump() | {"supporting_evidence_ids": []}))
    with pytest.raises(ValidationError):
        RCAReport(**(report.model_dump() | {"status": "INCONCLUSIVE"}))


def test_context_immutable_and_cannot_elevate():
    context = AgentContext(
        workspace_id="w",
        incident_id="inc-1",
        run_id="run-1",
        role="logs",
        allowed_tools=("query_logs",),
        allowed_evidence_scope=("e-1",),
        remaining_tool_calls=2,
    )
    with pytest.raises(ValidationError):
        context.role = "single"
    with pytest.raises(ValidationError):
        AgentContext(**(context.model_dump() | {"allowed_tools": ("query_changes",)}))
    with pytest.raises(ValidationError):
        AgentContext(**(context.model_dump() | {"allowed_evidence_scope": ["e-1"]}))
    assert AgentContext.model_validate_json(context.model_dump_json()) == context


def test_independent_state_defaults_and_cache_allowlist():
    first = InvestigationState(
        workspace_id="w", incident_id="inc-1", run_id="run-1", public_summary=case()
    )
    second = InvestigationState(
        workspace_id="w", incident_id="inc-1", run_id="run-2", public_summary=case()
    )
    first.hypotheses.append(
        Hypothesis(hypothesis_id="h", culprit_service="api", failure_mode="timeout")
    )
    assert second.hypotheses == []
    assert first.budgets == Budget()
    with pytest.raises(ValidationError):
        CachePolicy(allowed_task_types=("root_cause",))
    with pytest.raises(ValidationError):
        CachePolicy(similarity_threshold=0.94)
    namespace = CacheNamespace(
        workspace_id="w",
        incident_id="inc-1",
        agent_role="logs",
        task_type="summarize_log_slice",
        evidence_snapshot_sha256="a" * 64,
        dataset_revision="v1",
        prompt_version="v1",
        model_id="fixture",
        model_parameters_hash="b" * 64,
        output_schema_version="v1",
        tool_acl_version="v1",
    )
    assert CacheNamespace.model_validate_json(namespace.model_dump_json()) == namespace


def test_state_rejects_foreign_provenance():
    base = dict(workspace_id="w", incident_id="inc-1", run_id="run-1", public_summary=case())
    for updates in (
        {"incident_id": "other"},
        {"evidence_index": {"e-1": evidence(incident_id="other")}},
        {"evidence_index": {"wrong-key": evidence()}},
        {"tool_calls_used": -1},
        {"completed_task_ids": ["missing"]},
    ):
        with pytest.raises(ValidationError):
            InvestigationState(**(base | updates))
    finding = Finding(
        finding_id="f-1",
        task_id="t-1",
        run_id="foreign",
        incident_id="inc-1",
        role="logs",
        claim="timeout",
        evidence_ids=["e-1"],
        relation="supports",
        confidence_qualifier="supported",
    )
    with pytest.raises(ValidationError):
        InvestigationState(**(base | {"findings": [finding]}))
    with pytest.raises(ValidationError):
        Finding(**(finding.model_dump() | {"confidence_qualifier": "certain"}))
