"""Additive V1.2 contracts; legacy callers need no new configuration."""

from typing import Literal

from pydantic import Field, model_validator

from .contracts import EvidenceRecord, Identifier, StrictModel, Text

StopReason = Literal[
    "PLAN_READY",
    "DIAGNOSIS_READY",
    "INCONCLUSIVE",
    "BUDGET_EXHAUSTED",
    "PLAN_FAILED",
    "UNRECOVERABLE_ERROR",
    "NO_ALERT",
    "STOP_TIMEOUT",
]

PROTOCOL_VERSION = "2"
NORMAL_REASONS = {"PLAN_READY", "DIAGNOSIS_READY", "INCONCLUSIVE", "NO_ALERT", "PLAN_FAILED"}


class TerminationResult(StrictModel):
    protocol_version: Literal["2"]
    reason: StopReason
    outcome: Literal["SUCCESS", "ABSTAINED", "NO_ACTION", "FAILED"]
    failure_stage: (
        Literal[
            "monitoring",
            "coordinate",
            "dispatch",
            "merge",
            "verify",
            "finalize",
            "diagnosis",
            "remediation",
            "stop",
            "runtime",
        ]
        | None
    )
    stop_completed: bool
    runtime_failure: bool

    @model_validator(mode="after")
    def consistent_termination(self):
        expected = {
            "PLAN_READY": "SUCCESS",
            "DIAGNOSIS_READY": "SUCCESS",
            "INCONCLUSIVE": "ABSTAINED",
            "NO_ALERT": "NO_ACTION",
        }.get(self.reason, "FAILED")
        if self.outcome != expected:
            raise ValueError("termination outcome must match reason")
        if self.runtime_failure != (self.reason not in NORMAL_REASONS):
            raise ValueError("runtime_failure must match terminal reason")
        if (self.outcome == "FAILED") != (self.failure_stage is not None):
            raise ValueError("failed outcomes require a failure_stage")
        if self.reason == "STOP_TIMEOUT":
            if self.stop_completed or self.failure_stage != "stop":
                raise ValueError("STOP_TIMEOUT requires incomplete stop at stop stage")
        elif not self.stop_completed:
            raise ValueError("incomplete stop must terminate with STOP_TIMEOUT")
        if self.reason == "PLAN_FAILED" and self.failure_stage != "remediation":
            raise ValueError("PLAN_FAILED requires remediation stage")
        return self


def termination_result(reason: StopReason, failure_stage=None, stop_completed=True):
    """One terminal reason table shared by producers and historical normalization."""
    outcome = {
        "PLAN_READY": "SUCCESS",
        "DIAGNOSIS_READY": "SUCCESS",
        "INCONCLUSIVE": "ABSTAINED",
        "NO_ALERT": "NO_ACTION",
    }.get(reason, "FAILED")
    return TerminationResult(
        protocol_version=PROTOCOL_VERSION,
        reason=reason,
        outcome=outcome,
        failure_stage=(failure_stage or "runtime") if outcome == "FAILED" else None,
        stop_completed=stop_completed,
        runtime_failure=reason not in NORMAL_REASONS,
    )


class IncidentAlert(StrictModel):
    incident_id: Identifier
    status: Literal["ALERT", "NO_ALERT"]
    summary: Text
    evidence_ids: list[Identifier] = Field(default_factory=list)
    affected_services: list[Identifier] = Field(default_factory=list)


class RemediationPlan(StrictModel):
    incident_id: Identifier
    run_id: Identifier
    root_cause_version: Identifier
    execution_mode: Literal["PLAN_ONLY"] = "PLAN_ONLY"
    objective: Text
    affected_services: list[Identifier] = Field(min_length=1)
    actions: list[Text] = Field(min_length=1)
    preconditions: list[Text] = Field(min_length=1)
    risks: list[Text] = Field(min_length=1)
    verification_steps: list[Text] = Field(min_length=1)
    rollback: list[Text] = Field(min_length=1)
    evidence_ids: list[Identifier] = Field(min_length=1)


class TaskRecord(StrictModel):
    task_id: Identifier
    attempt_id: Identifier
    role: str
    attempt: int = Field(ge=1)
    status: Literal["ASSIGNED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    error_code: str | None = None


class StopMessage(StrictModel):
    incident_id: Identifier
    run_id: Identifier
    stop_reason: StopReason
    message_type: Literal["WORKFLOW_STOP_REQUESTED", "STOP_ACK"] = "WORKFLOW_STOP_REQUESTED"
    protocol_version: Literal["2"] = PROTOCOL_VERSION
    role: str = "coordinator"


class WorkflowOptions(StrictModel):
    profile: Literal["legacy_rca", "incident_response"] = "legacy_rca"
    communication_mode: Literal["centralized"] = "centralized"
    monitor_mode: Literal["legacy", "manual_snapshot", "offline_replay"] = "legacy"
    database_enabled: bool = True
    database_equivalent_tools: bool = False
    remediation_enabled: bool = True
    execution_mode: Literal["plan_only"] = "plan_only"
    max_attempts: int = Field(default=2, ge=1, le=10)
    continue_on_partial_failure: bool = True
    ack_timeout_seconds: float = Field(default=5.0, gt=0)
    monitoring_max_calls: int = Field(default=1, ge=0)
    remediation_max_calls: int = Field(default=2, ge=0)
    snapshot: list[EvidenceRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def profile_semantics(self):
        if self.profile == "legacy_rca" and self.monitor_mode != "legacy":
            raise ValueError("monitoring requires incident_response profile")
        return self
