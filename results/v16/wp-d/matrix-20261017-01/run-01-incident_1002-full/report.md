# IncidentLens — RESOLVED

Run: `run-340c294d8db74848a6a5a16aa1c06677`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1002-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1002-E-007] postgres: Server connections below limit
- 2026-10-01T12:00:44+00:00 [incident_1002-E-010] gateway: Presentation asset deployment completed; routing unchanged

## Predictions (not confirmed observations)
- pool_waiters=118 at 12:00:10Z immediately after db_pool_max reduced to 2 with concurrency=120
- Postgres connection count healthy at 30/100, ruling out DB-side connection exhaustion
- Gateway routing unchanged, ruling out gateway as the cause

## Supporting evidence
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-005`
- `incident_1002-E-007`
- `incident_1002-E-010`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_1002-E-007']

## Unresolved


## Stop reason
Causal chain established: config change -> pool contention -> backend pool regression; review verdict sufficient.

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
