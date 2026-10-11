"""Strict public contracts for IncidentLens orchestration."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
]
Text = Annotated[str, StringConstraints(min_length=1)]
Role = Literal["coordinator", "logs", "metrics", "changes", "verifier", "reporter", "single"]
SpecialistRole = Literal["logs", "metrics", "changes"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


def timezone_required(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone is required")
    return value


class CasePublicInput(StrictModel):
    incident_id: Identifier
    title: Text
    started_at: datetime
    observed_symptoms: list[Text]
    services: list[Identifier]
    _timezone = field_validator("started_at")(timezone_required)


class EvidenceRecord(StrictModel):
    evidence_id: Identifier
    incident_id: Identifier
    source_type: Literal["logs", "metrics", "changes", "configs", "topology"]
    service: Identifier
    observed_at: datetime
    source_path: Text
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    _timezone = field_validator("observed_at")(timezone_required)

    @field_validator("source_path")
    @classmethod
    def public_relative_path(cls, value: str) -> str:
        parts = value.split("/")
        if (
            "\\" in value
            or ":" in value
            or value.startswith("/")
            or any(p in ("", ".", "..") for p in parts)
        ):
            raise ValueError("source_path must be a normalized public relative path")
        if any(
            p.lower() in ("private", "hidden", "ground_truth", "ground-truth", "secrets", ".git")
            or p.startswith(".")
            for p in parts
        ):
            raise ValueError("source_path cannot reference private data")
        if not value.startswith("public/") and value != "topology/services.yaml":
            raise ValueError("source_path must reference public/ or topology/services.yaml")
        return value


class ToolResult(StrictModel):
    call_id: Identifier
    ok: bool
    records: list[EvidenceRecord] = Field(default_factory=list)
    error_code: str | None = None
    elapsed_ms: float = Field(default=0.0, ge=0)
    record_count: int = Field(default=0, ge=0)
    next_cursor: str | None = None

    @model_validator(mode="after")
    def consistent_result(self):
        if self.record_count != len(self.records):
            raise ValueError("record_count must match records")
        if self.ok == (self.error_code is not None):
            raise ValueError("successful results have no error_code; failures require one")
        if not self.ok and (self.records or self.next_cursor is not None):
            raise ValueError("failed results cannot contain records or next_cursor")
        return self


class InvestigationTask(StrictModel):
    task_id: Identifier
    role: SpecialistRole
    question: Text
    allowed_tools: list[Text]
    filters: dict[str, Any] = Field(default_factory=dict)
    reason: Text
    expected_discriminator: Text


class Finding(StrictModel):
    finding_id: Identifier
    task_id: Identifier
    run_id: Identifier
    incident_id: Identifier
    role: SpecialistRole
    claim: Text
    evidence_ids: list[Identifier]
    relation: Literal["supports", "refutes", "neutral"]
    confidence_qualifier: Literal["supported", "weak", "unknown"]
    followup_question: str | None = None


class Hypothesis(StrictModel):
    hypothesis_id: Identifier
    culprit_service: Identifier
    failure_mode: Text
    support_ids: list[Identifier] = Field(default_factory=list)
    against_ids: list[Identifier] = Field(default_factory=list)
    predicted_observations: list[Text] = Field(default_factory=list)
    status: Literal["OPEN", "SUPPORTED", "REJECTED"] = "OPEN"
    open_questions: list[Text] = Field(default_factory=list)


class Review(StrictModel):
    target_hypothesis_id: Identifier
    verdict: Literal["sufficient", "insufficient", "conflicted"]
    contradictions: list[Text] = Field(default_factory=list)
    requested_checks: list[InvestigationTask] = Field(default_factory=list)
    cited_evidence_ids: list[Identifier] = Field(default_factory=list)
    rationale: Text


class CoordinatorDecision(StrictModel):
    action: Literal["INVESTIGATE", "FINALIZE", "ABSTAIN"]
    reason: Text
    assignments: list[InvestigationTask] = Field(default_factory=list)
    selected_hypothesis_id: Identifier | None = None
    stop_reason: str | None = None

    @model_validator(mode="after")
    def action_semantics(self):
        if self.action == "INVESTIGATE":
            if (
                not self.assignments
                or self.selected_hypothesis_id is not None
                or self.stop_reason is not None
            ):
                raise ValueError(
                    "INVESTIGATE requires assignments and no final selection or stop reason"
                )
        elif self.assignments or not self.stop_reason:
            raise ValueError("terminal decisions require stop_reason and no assignments")
        elif (self.action == "FINALIZE") != (self.selected_hypothesis_id is not None):
            raise ValueError("only FINALIZE requires selected_hypothesis_id")
        return self


class RCAReport(StrictModel):
    run_id: Identifier
    incident_id: Identifier
    status: Literal["RESOLVED", "INCONCLUSIVE", "ERROR"]
    root_cause: Hypothesis | None = None
    causal_chain: list[Text] = Field(default_factory=list)
    supporting_evidence_ids: list[Identifier] = Field(default_factory=list)
    rejected_hypotheses: list[Hypothesis] = Field(default_factory=list)
    unresolved: list[Text] = Field(default_factory=list)
    stop_reason: Text

    @model_validator(mode="after")
    def resolution_semantics(self):
        if self.status == "RESOLVED":
            if (
                self.root_cause is None
                or self.root_cause.status != "SUPPORTED"
                or not self.supporting_evidence_ids
                or not self.causal_chain
            ):
                raise ValueError(
                    "RESOLVED requires a supported root cause, evidence and causal chain"
                )
        elif self.root_cause is not None:
            raise ValueError("non-resolved reports cannot assert a root cause")
        if any(h.status != "REJECTED" for h in self.rejected_hypotheses):
            raise ValueError("rejected_hypotheses must have REJECTED status")
        return self


class Budget(StrictModel):
    max_rounds: int = Field(default=4, ge=1)
    max_tool_calls: int = Field(default=12, ge=0)
    max_llm_calls: int = Field(default=16, ge=0)
    max_wall_seconds: float = Field(default=90.0, gt=0)
    max_tokens: int | None = Field(default=None, ge=1)


class TraceEvent(StrictModel):
    event_id: Identifier
    run_id: Identifier
    incident_id: Identifier
    timestamp: datetime
    event_type: Identifier
    role: Role | None = None
    task_id: Identifier | None = None
    call_id: Identifier | None = None
    evidence_ids: list[Identifier] = Field(default_factory=list)
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    source: Literal["model", "cache", "mock", "runtime"] | None = None
    elapsed_ms: float | None = Field(default=None, ge=0)
    _timezone = field_validator("timestamp")(timezone_required)


class InvestigationState(StrictModel):
    workspace_id: Identifier
    incident_id: Identifier
    run_id: Identifier
    public_summary: CasePublicInput
    budgets: Budget = Field(default_factory=Budget)
    round_index: int = Field(default=0, ge=0)
    findings: list[Finding] = Field(default_factory=list)
    evidence_index: dict[str, EvidenceRecord] = Field(default_factory=dict)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    tasks: list[InvestigationTask] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    decisions: list[CoordinatorDecision] = Field(default_factory=list)
    events: list[TraceEvent] = Field(default_factory=list)
    report: RCAReport | None = None
    stop_reason: str | None = None
    open_questions: list[Text] = Field(default_factory=list)
    requested_checks: list[InvestigationTask] = Field(default_factory=list)
    completed_task_ids: list[Identifier] = Field(default_factory=list)
    tool_calls_used: int = Field(default=0, ge=0)
    llm_calls_used: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def consistent_provenance(self):
        if self.public_summary.incident_id != self.incident_id:
            raise ValueError("public_summary incident_id must match state")
        for key, record in self.evidence_index.items():
            if key != record.evidence_id or record.incident_id != self.incident_id:
                raise ValueError("evidence_index keys and incident_id must match state")
        for item in [
            *self.findings,
            *self.events,
            *([self.report] if self.report is not None else []),
        ]:
            if item.run_id != self.run_id or item.incident_id != self.incident_id:
                raise ValueError("nested run_id and incident_id must match state")
        task_ids = {task.task_id for task in self.tasks}
        tasks_by_id = {task.task_id: task for task in self.tasks}
        if any(finding.task_id not in task_ids for finding in self.findings):
            raise ValueError("finding task_id must reference a state task")
        if any(finding.role != tasks_by_id[finding.task_id].role for finding in self.findings):
            raise ValueError("finding role must match its assigned task")
        if not set(self.completed_task_ids).issubset(task_ids):
            raise ValueError("completed_task_ids must reference state tasks")
        if len(task_ids) != len(self.tasks):
            raise ValueError("task IDs must be unique")
        if len({f.finding_id for f in self.findings}) != len(self.findings):
            raise ValueError("finding IDs must be unique")
        cited_ids = [eid for f in self.findings for eid in f.evidence_ids]
        cited_ids += [eid for h in self.hypotheses for eid in h.support_ids + h.against_ids]
        cited_ids += [eid for r in self.reviews for eid in r.cited_evidence_ids]
        if self.report is not None:
            cited_ids += self.report.supporting_evidence_ids
            cited_ids += [
                eid
                for h in self.report.rejected_hypotheses
                for eid in h.support_ids + h.against_ids
            ]
            if self.report.root_cause is not None:
                cited_ids += self.report.root_cause.support_ids + self.report.root_cause.against_ids
        if not set(cited_ids).issubset(self.evidence_index):
            raise ValueError("all shared citations must exist in current incident evidence_index")
        return self


Budgets = Budget
