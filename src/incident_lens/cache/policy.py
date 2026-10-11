from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from incident_lens.schemas import Identifier, Role, StrictModel

CacheTaskType = Literal["summarize_log_slice", "interpret_metric_window", "summarize_change_diff"]
CACHE_TASK_ALLOWLIST = ("summarize_log_slice", "interpret_metric_window", "summarize_change_diff")
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CachePolicy(StrictModel):
    mode: Literal["off", "exact", "semantic"] = "off"
    similarity_threshold: float = Field(default=0.95, ge=0.95, le=1.0)
    ttl_hours: float = Field(default=24.0, gt=0)
    allowed_task_types: tuple[CacheTaskType, ...] = CACHE_TASK_ALLOWLIST


class CacheNamespace(StrictModel):
    workspace_id: Identifier
    incident_id: Identifier
    agent_role: Role
    task_type: CacheTaskType
    evidence_snapshot_sha256: Sha256
    dataset_revision: Identifier
    prompt_version: Identifier
    model_id: Identifier
    model_parameters_hash: Sha256
    output_schema_version: Identifier
    tool_acl_version: Identifier
