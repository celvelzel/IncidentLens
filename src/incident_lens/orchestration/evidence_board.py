"""Public, observed evidence and query coverage; no oracle or hidden-source reads."""

from incident_lens.tools.database import DATABASE_CATEGORIES


def query_history(state):
    return [
        {
            "task_id": event.task_id,
            "tool_name": event.details["tool_name"],
            "args": event.details.get("args", {}),
            "evidence_ids": [r["evidence_id"] for r in
                             event.details.get("result", {}).get("records", [])],
            "error_code": event.details.get("result", {}).get("error_code"),
            "ok": event.details.get("result", {}).get("ok", False),
            "record_count": len(event.details.get("result", {}).get("records", [])),
            "next_cursor": event.details.get("result", {}).get("next_cursor"),
            "completed": event.task_id in state.completed_task_ids,
        }
        for event in state.events
        if event.event_type == "TOOL_CALL" and "tool_name" in event.details
    ]


def database_coverage(state, history, acl):
    """A category's status refers to its exact recorded scope, never all health."""
    available = {tool for tools in acl.values() for tool in tools}
    services = {record.service for record in state.evidence_index.values()
                if record.source_type == "database"}
    # The database tool schema's documented default is postgres. Other service
    # names require an observed database source, rather than a guessed engine.
    if "postgres" in state.public_summary.services:
        services.add("postgres")
    result = []
    for service in sorted(services):
        for tool, category in DATABASE_CATEGORIES.items():
            if tool not in available:
                continue
            scopes = []
            for query in history:
                if query["tool_name"] != tool or query["args"].get("service", "postgres") != service:
                    continue
                status = "failed" if not query["ok"] else (
                    "partial" if query["next_cursor"] or not query["completed"] else
                    "complete_with_records" if query["record_count"] else "complete_empty")
                scopes.append({"args": query["args"], "status": status,
                               "evidence_ids": query["evidence_ids"],
                               "error_code": query["error_code"]})
            result.append({"service": service, "category": category, "tool_name": tool,
                           "status": "unqueried" if not scopes else "see_scopes",
                           "scopes": scopes})
    return result


def shared_observations(records):
    """Keep metadata needed to join specialists' observations without adding claims."""
    return [record.model_dump(mode="json") for record in
            sorted(records, key=lambda record: (record.observed_at, record.evidence_id))]
