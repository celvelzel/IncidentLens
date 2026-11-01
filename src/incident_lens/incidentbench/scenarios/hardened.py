"""Harder discriminative encoders: boundary measurements and same-service rivals.

The frozen ``causal-world-v1`` encoder stays byte-identical so every saved
dataset remains reproducible. This module adds a second, opt-in lineage
(``causal-world-v2-hardened``) whose public observations are harder to read
correctly:

* ``standard`` -- magnitudes clearly over the contract, as in v1, but a rival
  mechanism and a same-service distractor are in play.
* ``boundary`` -- the cause-specific measurement sits exactly on its acceptance
  threshold (``cpu_percent`` 91, ``connection_count`` == ``connection_limit``,
  ``p95_latency_ms`` 3000, ``duration_ms`` 1001/3001), or the intervention's
  magnitude is trivially small (``db_pool_max 20 -> 18``). A reader that reasons
  "pool exhaustion needs a dramatic drop" or "90% CPU is high" instead of
  checking the mechanism contract gets the wrong answer.
* ``competing`` -- a confusable rival mechanism publishes a *symptom* record on
  its own service but never its discriminator, and the late noncausal change
  lands on the culprit's own service rather than on the gateway.

Every rival symptom string is deliberately free of the phrases that
``guards.cause_discriminator`` and the mock classifier treat as a mechanism, so
the rival stays unconfirmable by construction.

These remain deterministic queue/capacity models over synthetic public
observations. They are harder to *discriminate*, not more faithful to
production incidents, and carry no difficulty claim beyond that.
"""

from datetime import timedelta

#: Confusable rival per mechanism. Chosen so the pair shares a service or a
#: symptom signature, never a cause-specific measurement.
RIVALS = {
    "backend_pool_config_regression": "backend_resource_saturation",
    "backend_resource_saturation": "backend_pool_config_regression",
    "postgres_connection_exhaustion": "postgres_slow_query",
    "postgres_lock_contention": "postgres_slow_query",
    "postgres_slow_query": "postgres_connection_exhaustion",
    "redis_unavailable": "payment_external_timeout",
    "payment_external_timeout": "redis_unavailable",
}

#: Service that owns each mechanism, mirroring ``scenarios.world.simulate``.
MECHANISM_SERVICE = {
    "backend_pool_config_regression": "backend",
    "backend_resource_saturation": "backend",
    "postgres_connection_exhaustion": "postgres",
    "postgres_lock_contention": "postgres",
    "postgres_slow_query": "postgres",
    "redis_unavailable": "redis",
    "payment_external_timeout": "payment",
}

#: Rival symptom wording per service. Free of mechanism phrases on purpose.
COMPETING_SYMPTOM = {
    "backend": "Worker threads reporting elevated utilisation",
    "postgres": "Query planner sampling slower than baseline",
    "redis": "Cache lookup latency trending upward",
    "payment": "Upstream call latency trending upward",
}

DIFFICULTIES = ("standard", "boundary", "competing")


def _edge(boundary, near, far):
    """Boundary cases sit on the contract; standard cases sit well beyond it."""
    return near if boundary else far


def encode_hardened(world, incident_id, difficulty="standard"):
    """Encode one harder case; ``difficulty`` selects which levers apply."""
    if difficulty not in DIFFICULTIES:
        raise ValueError("unknown difficulty lever")
    boundary = difficulty == "boundary"
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

    # Every case opens with the same healthy prefix. It is context, never a
    # claim about current health.
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
            # The contract only needs *a* reduction below concurrency. Boundary
            # cases shrink it to one slot so magnitude-based reasoning fails.
            reduced = _edge(boundary, 18, 2)
            observe(
                "configs",
                "backend",
                at,
                f"db_pool_max 20 -> {reduced}; concurrency={world.demand}",
                {"change_id": "runtime-1"},
                "support",
            )
            metric("backend", at, "pool_waiters", max(1, world.demand - reduced), "requests")
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
            # The contract is ``count >= limit``. Boundary cases sit exactly on
            # the cap; standard cases overflow it by the full demand.
            count = _edge(boundary, world.capacity, max(100, world.demand))
            metric("postgres", at, "connections_active", count, "connections", "support")
            observe(
                "database",
                "postgres",
                at,
                "Connection admission held at the server cap"
                if boundary
                else "Connection admission rejected at server cap",
                dict(
                    category="connections",
                    connection_count=count,
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
            # The guard contract only needs ``duration_ms > 0`` plus the category
            # or a blocker, but the *readable* thresholds differ: a lock wait is
            # alarming from 1000ms, a slow query from 3000ms. Boundary cases clear
            # each reading threshold by exactly 1ms.
            duration = _edge(boundary, 1001 if locked else 3001, max(3001, world.delay_ms))
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
                    duration_ms=duration,
                    query_fingerprint="select-shape-7",
                ),
                "support",
            )
            metric("postgres", at, "query_latency_ms", duration, "ms", "support")
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
            # Boundary cases put the rival payment reading one millisecond under
            # its threshold: alarming, not a mechanism.
            metric("payment", at, "p95_latency_ms", _edge(boundary, 2999, 60), "ms", "contradicting")
        elif mode == "payment_external_timeout":
            metric("payment", at, "p95_latency_ms", _edge(boundary, 3000, max(3500, world.delay_ms)),
                   "ms", "support")
            observe("logs", "payment", at, "External request exceeded deadline", role="support")
            metric("redis", at, "availability", 1, "ratio", "contradicting")
        elif mode == "backend_resource_saturation":
            # The contract is ``>= 90``. Boundary cases report 91 percent.
            percent = _edge(boundary, 91, 98)
            metric("backend", at, "cpu_percent", percent, "percent", "support")
            observe(
                "logs",
                "backend",
                at,
                f"CPU worker threads saturated at {percent} percent",
                role="support",
            )
            metric("postgres", at, "connections_active", 30, "connections", "contradicting")
        else:
            # Unknown observations remain a diagnostic challenge, never a supported root.
            metric(world.root_service, at, "clock_offset_ms", world.delay_ms, "ms")

    if mode != "healthy":
        observe("logs", "backend", world.symptom_at, "Request processing exceeded deadline")
        metric("gateway", world.symptom_at, "http_5xx_rate", 0.35, "ratio")
    else:
        metric("gateway", world.symptom_at, "http_5xx_rate", 0, "ratio")
        observe("logs", "backend", world.symptom_at, "Request completed normally")

    rival = RIVALS.get(mode)
    if difficulty == "competing" and rival and not world.missing:
        # Visible rival, never confirmable: a symptom source type on the rival's
        # own service that carries no mechanism measurement for it.
        rival_service = MECHANISM_SERVICE[rival]
        observe("logs", rival_service, world.symptom_at, COMPETING_SYMPTOM[rival_service])

    if world.misleading:
        if difficulty == "competing":
            # A late change on the culprit's own service: far more tempting than
            # a gateway distractor, and still noncausal.
            observe(
                "changes",
                world.root_service,
                world.symptom_at + timedelta(seconds=30),
                "Routine dependency pin refresh completed; runtime limits unchanged",
                {"change_id": "deps-2", "change_type": "deployment"},
                "misleading",
            )
        else:
            observe(
                "changes",
                "gateway",
                world.symptom_at + timedelta(seconds=30),
                "Presentation asset deployment completed; routing unchanged",
                {"change_id": "assets-2", "change_type": "deployment"},
                "misleading",
            )
    return rows, roles
