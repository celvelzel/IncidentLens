# IncidentLens — RESOLVED

Run: `run-0bd36799c8fc47cdb6ff263ffa596005`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_1002-T-backend] backend: backend depends on: postgres, redis, payment
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1002-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1002-E-007] postgres: Server connections below limit
- 2026-10-01T12:00:14+00:00 [incident_1002-E-008] backend: Request processing exceeded deadline
- 2026-10-01T12:00:44+00:00 [incident_1002-E-010] gateway: Presentation asset deployment completed; routing unchanged

## Predictions (not confirmed observations)
- The runtime-1 backend config diff reduces db_pool_max from 20 to 2 while concurrency=120, applied at 2026-10-01T12:00:10Z (incident_1002-E-004), logged as a runtime settings deployment (incident_1002-E-003).
- Connection-pool queueing pool_waiters=118 appears at the same 2026-10-01T12:00:10Z timestamp, close to concurrency minus the reduced pool size (incident_1002-E-005).
- The backend 'Request processing exceeded deadline' error follows the config change at 2026-10-01T12:00:14Z (incident_1002-E-008).
- Postgres stays below its connection limit at 30 of 100 (incident_1002-E-007), because the pool is shrunk application-side rather than the datastore being saturated.
- Payment and redis emit no ERROR/CRITICAL records and no payment latency or error deviation over 2026-10-01T11:30:00Z-12:30:00Z, so no external dependency stall is observed.

## Supporting evidence
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-005`
- `incident_1002-E-007`
- `incident_1002-E-008`
- `incident_1002-E-010`
- `incident_1002-T-backend`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_1002-E-007']
- payment_external_timeout: ['incident_1002-T-payment']

## Unresolved


## Stop reason
Finalizing backend_pool_config_regression for service backend: the runtime-1 configuration change reduced db_pool_max from 20 to 2 under concurrency=120 at 2026-10-01T12:00:10Z (incident_1002-E-004), connection-pool queueing pool_waiters=118 appeared at the same timestamp (incident_1002-E-005), and the backend 'Request processing exceeded deadline' symptom followed at 2026-10-01T12:00:14Z (incident_1002-E-008); postgres remained at 30 of 100 connections (incident_1002-E-007) and payment/redis showed no error or latency signal, so the queueing originates in the application connection pool rather than the datastore or an external dependency.

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
