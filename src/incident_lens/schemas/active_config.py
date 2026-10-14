"""Dependency-free CAES configuration contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PolicyName = Literal[
    "current_dynamic",
    "active_evidence",
    "active_no_cost",
    "active_no_discrimination",
    "first_eligible",
]


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    policy_version: Literal["caes-v1"] = "caes-v1"
    candidate_pool_limit: int = Field(default=6, ge=1, le=20)
    max_selected_tasks: int = Field(default=2, ge=1, le=2)
    discrimination_weight: float = Field(default=0.4, ge=0, le=1)
    gap_weight: float = Field(default=0.3, ge=0, le=1)
    gate_weight: float = Field(default=0.3, ge=0, le=1)
    redundancy_weight: float = Field(default=0.3, ge=0, le=1)
    diversity_penalty: float = Field(default=0.15, ge=0, le=1)
    redundancy_hard_limit: float = Field(default=0.95, ge=0, le=1)
    request_weight: float = Field(default=1.0, gt=0)
    tool_weight: float = Field(default=0.25, ge=0)
    epsilon: float = Field(default=0.01, gt=0)
    min_score: float = 0.0
    reserve_verifier_requests: int = Field(default=1, ge=1)
    reserve_verifier_tools: int = Field(default=1, ge=1)
