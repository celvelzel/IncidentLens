"""CAES v1 frozen DTOs. Only published information crosses this boundary."""

import hashlib
import json
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from incident_lens.schemas.active_config import PolicyConfig as PolicyConfig
from incident_lens.schemas.active_config import PolicyName
from incident_lens.schemas.contracts import (
    CasePublicInput,
    Hypothesis,
    Identifier,
    InvestigationTask,
    SpecialistRole,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VisibleState(DTO):
    run_id: Identifier
    incident_id: Identifier
    decision_id: Identifier
    evidence_snapshot_sha256: str
    public_summary: CasePublicInput
    hypotheses: tuple[Hypothesis, ...] = ()
    requested_checks: tuple[InvestigationTask, ...] = ()
    open_questions: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_sources: tuple[str, ...] = ()
    observed_change_ids: tuple[str, ...] = ()
    completed_signatures: tuple[str, ...] = ()
    grounding_errors: tuple[str, ...] = ()
    stopped: bool = False

    @field_validator("public_summary", "hypotheses", "requested_checks", mode="after")
    @classmethod
    def detach_published_models(cls, value):
        return deepcopy(value)


class BudgetView(DTO):
    remaining_requests: int = Field(ge=0)
    remaining_tools: int = Field(ge=0)
    remaining_seconds: float = Field(ge=0)
    remaining_tokens: int | None = Field(default=None, ge=0)
    physical_request_multiplier: int = Field(default=1, ge=1)


class CandidateAction(DTO):
    candidate_id: Identifier
    decision_id: Identifier
    incident_id: Identifier
    run_id: Identifier
    evidence_snapshot_sha256: str
    origin: Literal["coordinator_proposal", "verifier_requested_check", "public_task_template"]
    proposed_role: SpecialistRole
    question: str = Field(min_length=1)
    expected_discriminator: str = Field(min_length=1)
    filters: dict[str, JsonValue] = Field(default_factory=dict)
    allowed_tools: tuple[str, ...]
    existing_task_id: str | None = None
    target_hypothesis_ids: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()

    @field_validator("filters")
    @classmethod
    def json_filters(cls, value):
        digest(value)
        return deepcopy(value)


class CostEstimate(DTO):
    estimated_model_requests: int = Field(ge=1)
    estimated_tool_calls: int = Field(ge=1)
    estimated_tokens: int | None = Field(default=None, ge=0)
    estimated_latency_ms: float | None = Field(default=None, ge=0)
    source: Literal["dev_aggregate", "fixed_fallback", "not_calibrated"] = "fixed_fallback"
    uncertainty_note: str | None = None


class CandidateFeatures(DTO):
    discrimination: float = Field(ge=0, le=1)
    gap_coverage: float = Field(ge=0, le=1)
    gate_contribution: float = Field(ge=0, le=1)
    redundancy: float = Field(ge=0, le=1)
    cost: CostEstimate
    explanations: tuple[str, ...] = ()


class CandidateAssessment(DTO):
    candidate_id: Identifier
    eligibility: Literal["ELIGIBLE", "REJECTED"]
    reject_reason: str | None = None
    features: CandidateFeatures | None = None
    score: float | None = None
    rank: int | None = None


class SelectionDecision(DTO):
    decision_id: Identifier
    policy: PolicyName
    policy_version: Literal["caes-v1"]
    evidence_snapshot_sha256: str
    selected_candidate_ids: tuple[str, ...]
    assessments: tuple[CandidateAssessment, ...]
    budget_snapshot_digest: str
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def selected_are_eligible(self):
        selected = self.selected_candidate_ids
        if len(selected) > 2 or len(set(selected)) != len(selected):
            raise ValueError("selection requires at most two unique candidates")
        assessments = {a.candidate_id: a for a in self.assessments}
        if len(assessments) != len(self.assessments):
            raise ValueError("assessment IDs must be unique")
        if any(
            cid not in assessments or assessments[cid].eligibility != "ELIGIBLE" for cid in selected
        ):
            raise ValueError("selected candidates must have eligible assessments")
        return self
