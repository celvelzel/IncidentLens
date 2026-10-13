"""Server-issued context identity checks for the read-only runtime boundary."""

from threading import RLock

from incident_lens.security.context import ROLE_TOOL_ACL, AgentContext


class ContextAuthority:
    def __init__(self, workspace_id: str, incident_id: str, run_id: str):
        self.workspace_id = workspace_id
        self.incident_id = incident_id
        self.run_id = run_id
        self._issued: dict[int, tuple[AgentContext, str]] = {}
        self._lock = RLock()

    def issue(self, role: str, remaining_tool_calls: int, allowed_tools=None) -> AgentContext:
        if role not in ROLE_TOOL_ACL:
            raise ValueError("unknown role")
        context = AgentContext(
            workspace_id=self.workspace_id,
            incident_id=self.incident_id,
            run_id=self.run_id,
            role=role,
            allowed_tools=ROLE_TOOL_ACL[role] if allowed_tools is None else allowed_tools,
            allowed_evidence_scope=(self.incident_id,),
            remaining_tool_calls=remaining_tool_calls,
        )
        with self._lock:
            self._issued[id(context)] = (context, context.model_dump_json())
        return context

    def validate(self, context: AgentContext, tool_name: str | None = None) -> None:
        with self._lock:
            issued = self._issued.get(id(context))
            if issued is None or issued[0] is not context:
                raise PermissionError("context was not issued by this registry")
            if context.model_dump_json() != issued[1]:
                raise PermissionError("issued context has been modified")
            if tool_name is not None and tool_name not in context.allowed_tools:
                raise PermissionError("tool is outside role ACL")
