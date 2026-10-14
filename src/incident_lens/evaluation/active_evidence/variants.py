"""Exact mappings to existing Graph behavior, never label-only ablations."""

from typing import Literal

from pydantic import Field, model_validator

from incident_lens.orchestration.active_investigation.contracts import PolicyConfig
from incident_lens.schemas.contracts import StrictModel

VARIANTS = {
    "B0": "current_dynamic",
    "B1": "current_dynamic",
    "B1c": "first_eligible",
    "B2": "active_no_cost",
    "B3": "active_no_discrimination",
    "B4": "active_evidence",
}


class ActiveProtocol(StrictModel):
    protocol_id: str = "caes-v1-seed-diagnostic"
    provider_id: Literal["mock", "real"] = "mock"
    model_id: str = "deterministic-public-policy-v1"
    temperature: float = 0.0
    cache_mode: Literal["off"] = "off"
    jobs: Literal[1] = 1
    variants: list[str] = Field(default_factory=lambda: list(VARIANTS))
    repeats: int = Field(default=1, ge=1)
    run_order_seed: int = 15100
    analysis_seed: int = 15101
    bootstrap_samples: int = Field(default=10000, ge=1)
    max_rounds: int = Field(default=6, ge=1)
    max_tool_calls: int = Field(default=24, ge=1)
    max_llm_calls: int = Field(default=32, ge=1)
    max_wall_seconds: float = Field(default=600, gt=0)
    formal: bool = False
    active_evidence_config: PolicyConfig = Field(default_factory=PolicyConfig)

    @model_validator(mode="after")
    def valid_variants(self):
        if (
            not self.variants
            or len(set(self.variants)) != len(self.variants)
            or set(self.variants) - set(VARIANTS)
        ):
            raise ValueError("unknown, empty or duplicate CAES variants")
        return self


def workflow_values(variant, config):
    if variant not in VARIANTS:
        raise ValueError("unknown policy variant")
    return dict(
        profile="legacy_rca",
        database_enabled=True,
        database_equivalent_tools=True,
        benchmark_rca=True,
        benchmark_fixed_four=variant == "B0",
        remediation_enabled=False,
        selection_policy=VARIANTS[variant],
        shadow_caes=False,
        active_evidence_config=config,
    )
