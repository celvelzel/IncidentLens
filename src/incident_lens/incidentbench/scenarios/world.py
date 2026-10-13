"""Resource interventions -> dependency propagation -> independently encoded observations.

Private inputs choose timelines, workloads, mechanisms and observation placement. No
incident/family identifier is used to infer an answer. These are deliberately small
deterministic queue/capacity models, not production system fidelity claims.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class World:
    mechanism: str
    root_service: str
    started_at: datetime
    trigger_at: datetime
    symptom_at: datetime
    demand: int
    capacity: int
    delay_ms: int
    missing: bool
    misleading: bool


def simulate(spec: dict, variant: dict) -> World:
    start = datetime.fromisoformat(spec["started_at"])
    if start.utcoffset() is None:
        raise ValueError("scenario time must have timezone")
    mechanism = variant.get("mechanism", spec["mechanism"])
    demand = int(variant.get("demand", spec.get("demand", 120)))
    capacity = int(variant.get("capacity", spec.get("capacity", 100)))
    if capacity <= 0 or demand <= 0:
        raise ValueError("positive workload and capacity required")
    trigger = start + timedelta(seconds=int(spec.get("trigger_seconds", 10)))
    lag = int(spec.get("propagation_seconds", 5))
    if lag <= 0:
        raise ValueError("symptoms must follow intervention")
    service = {
        "backend_pool_config_regression": "backend",
        "backend_resource_saturation": "backend",
        "postgres_connection_exhaustion": "postgres",
        "postgres_lock_contention": "postgres",
        "postgres_slow_query": "postgres",
        "redis_unavailable": "redis",
        "payment_external_timeout": "payment",
        "healthy": "backend",
    }.get(mechanism, spec.get("root_service", "backend"))
    if mechanism in {"postgres_connection_exhaustion", "backend_resource_saturation"}:
        if demand < capacity:
            raise ValueError("capacity intervention does not produce overload")
    return World(
        mechanism,
        service,
        start,
        trigger,
        trigger + timedelta(seconds=lag),
        demand,
        capacity,
        max(3500, (demand - capacity + 1) * 100),
        variant["kind"] == "missing",
        variant["kind"] == "misleading",
    )


def encode(world: World, incident_id: str) -> tuple[list[dict], dict]:
    """Encode world measurements with provenance; retain candidate roles privately."""
    rows, roles = [], {"support": [], "contradicting": [], "misleading": []}

    def observe(source, service, at, excerpt, metadata=None, role=None):
        row = dict(
            evidence_id=f"{incident_id}-E-{len(rows) + 1:03d}",
            incident_id=incident_id,
            source_type=source,
            service=service,
            observed_at=at.isoformat(),
            source_path=f"public/{source}.jsonl",
            excerpt=excerpt,
            metadata=metadata or {},
        )
        if source == "metrics":
            row["source_path"] = "public/metrics.csv"
        rows.append(row)
        if role:
            roles[role].append(row["evidence_id"])
        return row

    def metric(service, at, name, value, unit, role=None):
        observe(
            "metrics",
            service,
            at,
            f"{name}={value} {unit}",
            dict(metric_name=name, value=value, unit=unit),
            role,
        )

    # Every case has a healthy prefix. It is context, never asserted as current health.
    metric("backend", world.started_at, "request_latency_ms", 40, "ms")
    observe("logs", "gateway", world.started_at, "Request completed with HTTP 200")
    mode, at = world.mechanism, world.trigger_at
    if not world.missing and mode != "healthy":
        if mode == "backend_pool_config_regression":
            observe(
                "changes",
                "backend",
                at,
                "Runtime settings deployment applied",
                {"change_id": "runtime-1", "change_type": "configuration"},
                "support",
            )
            observe(
                "configs",
                "backend",
                at,
                f"db_pool_max 20 -> 2; concurrency={world.demand}",
                {"change_id": "runtime-1"},
                "support",
            )
            metric("backend", at, "pool_waiters", max(1, world.demand - 2), "requests")
            metric("postgres", at, "connections_active", 30, "connections", "contradicting")
            observe(
                "database",
                "postgres",
                at,
                "Server connections below limit",
                dict(category="connections", connection_count=30, connection_limit=100),
                "contradicting",
            )
        elif mode == "postgres_connection_exhaustion":
            metric(
                "postgres",
                at,
                "connections_active",
                max(100, world.demand),
                "connections",
                "support",
            )
            observe(
                "database",
                "postgres",
                at,
                "Connection admission rejected at server cap",
                dict(
                    category="connections",
                    connection_count=world.demand,
                    connection_limit=world.capacity,
                ),
                "support",
            )
            observe(
                "configs",
                "backend",
                at,
                "db_pool_max remains 20; concurrency=120",
                {"change_id": "baseline-1"},
                "contradicting",
            )
        elif mode in {"postgres_lock_contention", "postgres_slow_query"}:
            locked = mode == "postgres_lock_contention"
            observe(
                "database",
                "postgres",
                at,
                "Session waiting on transaction lock" if locked else "Query execution sampled",
                dict(
                    category="lock_waits" if locked else "slow_queries",
                    session_id="session-9",
                    blocked_by="session-2" if locked else "",
                    wait_event="transaction_lock" if locked else "CPU",
                    duration_ms=world.delay_ms,
                    query_fingerprint="select-shape-7",
                ),
                "support",
            )
            metric("postgres", at, "query_latency_ms", world.delay_ms, "ms", "support")
            observe(
                "database",
                "postgres",
                at,
                "Connections healthy below server cap",
                dict(category="connections", connection_count=30, connection_limit=100),
                "contradicting",
            )
        elif mode == "redis_unavailable":
            metric("redis", at, "availability", 0, "ratio", "support")
            observe("logs", "redis", at, "Listener connection refused", role="support")
            metric("payment", at, "p95_latency_ms", 60, "ms", "contradicting")
        elif mode == "payment_external_timeout":
            metric("payment", at, "p95_latency_ms", world.delay_ms, "ms", "support")
            observe("logs", "payment", at, "External request exceeded deadline", role="support")
            metric("redis", at, "availability", 1, "ratio", "contradicting")
        elif mode == "backend_resource_saturation":
            metric("backend", at, "cpu_percent", 98, "percent", "support")
            observe(
                "logs", "backend", at, "CPU worker threads saturated at 98 percent", role="support"
            )
            metric("postgres", at, "connections_active", 30, "connections", "contradicting")
        else:
            # Unknown observations remain a diagnostic challenge, not a supported root.
            metric(world.root_service, at, "clock_offset_ms", world.delay_ms, "ms")
    if mode != "healthy":
        observe("logs", "backend", world.symptom_at, "Request processing exceeded deadline")
        metric("gateway", world.symptom_at, "http_5xx_rate", 0.35, "ratio")
    else:
        metric("gateway", world.symptom_at, "http_5xx_rate", 0, "ratio")
        observe("logs", "backend", world.symptom_at, "Request completed normally")
    if world.misleading:
        # Late, noncausal deployment follows the symptom rather than causing it.
        observe(
            "changes",
            "gateway",
            world.symptom_at + timedelta(seconds=30),
            "Presentation asset deployment completed; routing unchanged",
            {"change_id": "assets-2", "change_type": "deployment"},
            "misleading",
        )
    return rows, roles
