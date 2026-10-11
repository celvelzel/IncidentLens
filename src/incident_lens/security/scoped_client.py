from typing import Any, Protocol, runtime_checkable

from incident_lens.schemas import ToolResult

from .context import AgentContext


@runtime_checkable
class RoleScopedEvidenceClient(Protocol):
    @property
    def context(self) -> AgentContext: ...

    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult: ...
