"""Map additive nested YAML options to the deterministic workflow contract."""

from incident_lens.schemas.workflow import WorkflowOptions


def workflow_options(config, *, profile=None, monitor_mode=None, snapshot=None):
    from incident_lens.orchestration.active_investigation.contracts import PolicyConfig

    investigation = config.get("investigation", {})
    if not isinstance(investigation, dict) or set(investigation) - {
        "selection_policy",
        "shadow_enabled",
        "active_evidence",
    }:
        raise ValueError("invalid investigation configuration")
    workflow = config.get("workflow", {})
    monitor = config.get("monitor", {})
    remediation = config.get("remediation", {})
    runtime = config.get("task_runtime", {})
    stop = config.get("stop", {})
    communication = config.get("communication", {})
    database = config.get("database_agent", {})
    return WorkflowOptions(
        selection_policy=investigation.get("selection_policy", "current_dynamic"),
        shadow_caes=investigation.get("shadow_enabled", False),
        active_evidence_config=PolicyConfig.model_validate(
            investigation.get("active_evidence", {})
        ),
        profile=profile or workflow.get("profile", "legacy_rca"),
        communication_mode=communication.get("mode", "centralized"),
        monitor_mode=monitor_mode
        or (monitor.get("mode", "legacy") if monitor.get("enabled", False) else "legacy"),
        snapshot=snapshot or [],
        database_enabled=database.get("enabled", True),
        database_equivalent_tools=database.get("equivalent_tools", False),
        remediation_enabled=remediation.get("enabled", True),
        execution_mode=remediation.get("execution_mode", "plan_only"),
        max_attempts=runtime.get("max_attempts", 2),
        continue_on_partial_failure=runtime.get("continue_on_partial_failure", True),
        ack_timeout_seconds=stop.get("ack_timeout_seconds", 5.0),
        monitoring_max_calls=monitor.get("max_calls", 1),
        remediation_max_calls=remediation.get("max_calls", 2),
    )
