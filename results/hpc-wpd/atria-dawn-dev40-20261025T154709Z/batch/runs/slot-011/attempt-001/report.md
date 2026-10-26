# IncidentLens — RESOLVED

Run: `run-c0af0f1df71f44d5aec97b40581eba3d`

Incident: `incident_3002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-11T09:00:00+00:00 [incident_3002-E-001] backend: request_latency_ms=40 ms
- 2026-10-11T09:00:00+00:00 [incident_3002-T-backend] backend: backend depends on: postgres, redis, payment
- 2026-10-11T09:00:27+00:00 [incident_3002-E-003] backend: Runtime settings deployment applied
- 2026-10-11T09:00:27+00:00 [incident_3002-E-004] backend: db_pool_max 20 -> 2; concurrency=155
- 2026-10-11T09:00:27+00:00 [incident_3002-E-005] backend: pool_waiters=153 requests
- 2026-10-11T09:00:27+00:00 [incident_3002-E-007] postgres: Server connections below limit
- 2026-10-11T09:00:36+00:00 [incident_3002-E-008] backend: Request processing exceeded deadline

## Predictions (not confirmed observations)
- Backend metrics after 09:00:27Z show db connection checkout/wait latency rising while pool size is capped at 2.
- Backend request latency and errors increase under concurrency near 155, consistent with pool starvation rather than an external dependency timeout.
- Postgres connections remain well below the 100-connection limit (observed 30) while backend pool_waiters spikes, because the bottleneck is the backend's reduced pool cap.
- Backend logs contain pool acquisition timeout or connection wait errors after 09:00:27Z rather than postgres too_many_clients, redis connection failure, or payment timeout signatures.

## Supporting evidence
- `incident_3002-E-001`
- `incident_3002-E-003`
- `incident_3002-E-004`
- `incident_3002-E-005`
- `incident_3002-E-007`
- `incident_3002-E-008`
- `incident_3002-T-backend`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_3002-E-004', 'incident_3002-E-007']
- backend_pool_config_regression: ['incident_3002-E-010']
- postgres_connection_exhaustion: ['incident_3002-E-007']
- postgres_slow_query: ['incident_3002-E-004']
- redis_unavailable: ['incident_3002-E-004']
- payment_external_timeout: ['incident_3002-E-004']
- backend_resource_saturation: ['incident_3002-E-004']
- postgres_lock_contention: ['incident_3002-E-004']

## Unresolved


## Stop reason
Finalized backend_pool_config_regression on backend: runtime-1 reduced db_pool_max from 20 to 2 at 09:00:27Z, followed by pool_waiters=153 at concurrency 155 and latency degradation, with postgres capacity observed healthy at 30/100 and no observed dependency-side or resource-saturation discriminator.

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
