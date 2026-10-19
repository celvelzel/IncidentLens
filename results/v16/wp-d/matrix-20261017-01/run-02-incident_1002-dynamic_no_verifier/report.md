# IncidentLens — RESOLVED

Run: `run-7da18ec9d8ce4039af6c720f65252ec9`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_1002-E-001] backend: request_latency_ms=40 ms
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1002-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1002-E-007] postgres: Server connections below limit

## Predictions (not confirmed observations)
- Backend pool_waiters=118 at 12:00:10Z while postgres connections=30 (well below limit 100)
- Config diff shows db_pool_max 20->2 and concurrency=120 at 12:00:10Z
- Postgres connection_count remains well below connection_limit throughout the available data
- No error_rate/p99/request_count metrics are available in the data to directly observe a latency/error spike

## Supporting evidence
- `incident_1002-E-001`
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-005`
- `incident_1002-E-007`

## Rejected hypotheses


## Unresolved


## Stop reason
Causal support established: config diff shows db_pool_max 20->2 with concurrency=120, pool_waiters=118 at 12:00:10Z exactly matches the reduced pool capacity, and postgres connections remain low (30/100), ruling out database-side exhaustion.

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
