"""Immutable authority descriptor; issuance is enforced by the runtime."""

from pydantic import ConfigDict, Field, model_validator

from incident_lens.schemas import Identifier, Role, StrictModel

DATABASE_TOOLS = (
    "get_db_connections",
    "get_db_active_sessions",
    "get_db_lock_waits",
    "get_db_slow_queries",
    "get_db_health_metrics",
)
ROLE_TOOL_ACL: dict[str, tuple[str, ...]] = {
    "database": DATABASE_TOOLS,
    "coordinator": (),
    "monitoring": (),
    "remediation": (),
    "logs": ("query_logs",),
    "metrics": ("query_metrics", "get_dependencies"),
    "changes": ("query_changes", "get_config_diff"),
    "verifier": ("fetch_evidence_by_ids",),
    "reporter": ("fetch_evidence_by_ids",),
    "single": (
        "query_logs",
        "query_metrics",
        "get_dependencies",
        "query_changes",
        "get_config_diff",
        "fetch_evidence_by_ids",
    ),
}


class AgentContext(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id: Identifier
    incident_id: Identifier
    run_id: Identifier
    role: Role
    allowed_tools: tuple[str, ...] = ()
    allowed_evidence_scope: tuple[Identifier, ...] = ()
    remaining_tool_calls: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def role_authority(self):
        ceiling = ROLE_TOOL_ACL[self.role] + (
            DATABASE_TOOLS if self.role in ("metrics", "single") else ()
        )
        if not set(self.allowed_tools).issubset(ceiling):
            raise ValueError("allowed_tools cannot elevate role authority")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed_tools cannot contain duplicates")
        return self
