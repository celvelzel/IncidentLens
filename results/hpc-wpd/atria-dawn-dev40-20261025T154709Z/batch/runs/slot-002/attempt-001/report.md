# IncidentLens — RESOLVED

Run: `run-0cbaf5a7435b46969b9d09360ad20c08`

Incident: `incident_3004`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-11T09:00:00+00:00 [incident_3004-E-001] backend: request_latency_ms=40 ms
- 2026-10-11T09:00:27+00:00 [incident_3004-E-003] backend: Runtime settings deployment applied
- 2026-10-11T09:00:27+00:00 [incident_3004-E-004] backend: db_pool_max 20 -> 2; concurrency=155
- 2026-10-11T09:00:27+00:00 [incident_3004-E-005] backend: pool_waiters=153 requests
- 2026-10-11T09:00:27+00:00 [incident_3004-E-007] postgres: Server connections below limit
- 2026-10-11T09:00:36+00:00 [incident_3004-E-008] backend: Request processing exceeded deadline

## Predictions (not confirmed observations)
- runtime-1 lowers backend db_pool_max from 20 to 2 at 09:00:27Z while concurrency remains 155, preceding the latency rise and 153 pool waiters.
- Backend latency is normal at 09:00:00Z and degrades only after the pool cap change.
- Postgres remains at 30/100 connections with no connection-limit, lock-wait, slow-query, or health degradation.
- Backend, postgres, redis, and payment logs contain no cause-specific dependency or resource error; only a generic request deadline appears.

## Supporting evidence
- `incident_3004-E-001`
- `incident_3004-E-003`
- `incident_3004-E-004`
- `incident_3004-E-005`
- `incident_3004-E-007`
- `incident_3004-E-008`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_3004-E-004', 'incident_3004-E-007']
- backend_resource_saturation: ['incident_3004-E-004', 'incident_3004-E-008']
- postgres_connection_exhaustion: ['incident_3004-E-007']
- postgres_lock_contention: ['incident_3004-E-007']
- postgres_slow_query: ['incident_3004-E-007']
- payment_external_timeout: ['incident_3004-E-004']

## Unresolved


## Stop reason
Causal support is sufficient for backend_pool_config_regression: the runtime-1 db_pool_max 20 to 2 reduction at 09:00:27Z precedes the latency rise and 153 pool waiters, postgres retains spare capacity, and all completed dependency log/database/metric scopes contain no competing cause-specific evidence.

## Workflow
Diagnosis: RESOLVED
Remediation: NOT_STARTED
Workflow: FINISHED

## Termination
Reason: DIAGNOSIS_READY
Outcome: SUCCESS
Stop completed: True
Runtime failure: False
Failure stage: none
