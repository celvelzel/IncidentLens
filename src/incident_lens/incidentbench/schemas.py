"""Frozen V1 benchmark contracts. Candidate labels are never human acceptance."""

from typing import Literal

from pydantic import Field, model_validator

from incident_lens.schemas.contracts import Identifier, StrictModel, Text

INTERFACE_VERSION = "incidentbench-v1.0"
VARIANTS = (
    "strong_single_equivalent_tools",
    "fixed_four_equivalent_tools",
    "dynamic_no_verifier",
    "full",
)
SUPPORTED_MODES = frozenset(
    {
        "backend_pool_config_regression",
        "postgres_connection_exhaustion",
        "redis_unavailable",
        "payment_external_timeout",
        "backend_resource_saturation",
        "postgres_lock_contention",
        "postgres_slow_query",
    }
)


class BenchmarkRootCause(StrictModel):
    culprit_service: Identifier
    failure_mode: Text
    root_cause_code: Text


class EvidenceSupportSet(StrictModel):
    evidence_ids: list[Identifier] = Field(min_length=1)
    rationale: Text


class BenchmarkOracle(StrictModel):
    incident_id: Identifier
    scenario_family_id: Identifier
    mechanism_id: Text
    counterfactual_pair_id: Identifier | None = None
    is_identifiable: bool
    true_primary_root: BenchmarkRootCause
    acceptable_support_sets: list[EvidenceSupportSet]
    contradicting_evidence_ids: list[Identifier]
    misleading_evidence_ids: list[Identifier]
    required_discriminator_types: list[Text]
    causal_sequence: list[Text]
    identifiability_rationale: Text
    annotator_status: Literal["pending", "adjudicated", "accepted"] = "pending"
    review_version: Text = "candidate-v1"
    cohort: Literal["core", "ood", "monitoring"] = "core"
    reviewer_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def truthful_labels(self):
        if self.cohort == "core" and self.true_primary_root.failure_mode not in SUPPORTED_MODES:
            raise ValueError("unsupported core mechanism")
        if self.is_identifiable != bool(self.acceptable_support_sets):
            raise ValueError("identifiability requires sufficient sets; missing cases have none")
        if self.annotator_status != "pending" and len(set(self.reviewer_ids)) < 2:
            raise ValueError("accepted labels require two independent reviewer identities")
        return self


class BenchmarkCaseMetadata(StrictModel):
    incident_id: Identifier
    split: Literal["seed", "dev", "test"]
    scenario_family_id: Identifier
    scenario_variant_id: Identifier
    challenge_tags: list[Text]
    public_sha256: Text
    source_blueprint_id: Identifier
    near_duplicate_cluster_id: Identifier
    counterfactual_pair_id: Identifier | None = None
    cohort: Literal["core", "ood", "monitoring"] = "core"


class ExperimentProtocol(StrictModel):
    protocol_id: Text = "incidentbench-v1-development"
    benchmark_version: Literal["incidentbench-v1"] = "incidentbench-v1"
    provider_id: Literal["mock", "real"] = "mock"
    model_id: Text = "mock"
    temperature: float = 0.0
    cache_mode: Literal["off"] = "off"
    # WP-D supervisor enforces mode-specific caps: bridge 4, API/subscription 8.
    jobs: int = Field(default=1, ge=1, le=8, strict=True)
    run_order_seed: int = 14100
    repeats: int = Field(default=1, ge=1)
    variants: list[Text] = Field(default_factory=lambda: list(VARIANTS))
    max_rounds: int = Field(default=6, ge=1)
    max_tool_calls: int = Field(default=24, ge=1)
    max_llm_calls: int = Field(default=32, ge=1)
    max_wall_seconds: float = Field(default=600.0, gt=0, allow_inf_nan=False)
    response_format: Literal["json_schema", "json_object"] = "json_schema"
    request_timeout: float = Field(default=180.0, gt=0, allow_inf_nan=False)
    blindness_level: Literal["development_visible", "independent_label_owner"] = (
        "development_visible"
    )
    formal: bool = False
    analysis_seed: int = 14101
    bootstrap_samples: int = Field(default=10000, ge=1)
    analysis_plan: Literal["family_clustered_paired_bootstrap_plus_exact_discordance"] = (
        "family_clustered_paired_bootstrap_plus_exact_discordance"
    )

    @model_validator(mode="after")
    def conditions(self):
        if len(set(self.variants)) != len(self.variants) or set(self.variants) != set(VARIANTS):
            raise ValueError("protocol requires the four equivalent-tool variants")
        if self.formal and (
            self.provider_id != "real" or self.model_id in {"mock", "TO_FILL_BEFORE_FREEZE"}
        ):
            raise ValueError("formal protocol requires a frozen real model")
        return self
