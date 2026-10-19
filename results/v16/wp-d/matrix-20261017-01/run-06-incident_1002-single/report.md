# IncidentLens — RESOLVED

Run: `run-ceb5a18d4fd44ac1ad458faf71d8bfd9`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_1002-E-001] backend: request_latency_ms=40 ms
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1002-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1002-E-007] postgres: Server connections below limit
- 2026-10-01T12:00:14+00:00 [incident_1002-E-008] backend: Request processing exceeded deadline
- 2026-10-01T12:00:14+00:00 [incident_1002-E-009] gateway: http_5xx_rate=0.35 ratio

## Predictions (not confirmed observations)
- Backend pool_waiters=118 at 12:00:10Z coincident with db_pool_max reduction to 2
- Backend request deadline exceeded at 12:00:14Z
- Gateway http_5xx_rate=0.35 at 12:00:14Z
- Postgres connection_count=30/100 at 12:00:10Z, below limit

## Supporting evidence
- `incident_1002-E-001`
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-005`
- `incident_1002-E-007`
- `incident_1002-E-008`
- `incident_1002-E-009`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_1002-E-007']

## Unresolved


## Stop reason
Causal mechanism confirmed: backend pool config regression (db_pool_max 20->2) at 12:00:10Z caused pool_waiters=118 and downstream gateway 5xx; Postgres connection exhaustion refuted by E-007; sufficient review.

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
