# IncidentLens — RESOLVED

Run: `run-81b83f87c7e5466682f1ffc2d9280778`

Incident: `incident_1001`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:10+00:00 [incident_1001-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1001-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1001-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1001-E-007] postgres: Server connections below limit

## Predictions (not confirmed observations)
- backend pool_waiters increase after 2026-10-01T12:00:10Z once db_pool_max is reduced to 2
- backend pool_waiters stays elevated while postgres active sessions remain low, matching a backend-side pool configuration regression
- backend pooling saturates at the reduced ceiling of 2 concurrent connections while concurrency=120 demand is unmet
- postgres lock waits and slow-query counts show no coincident spike
- postgres server connections remain well below connection_limit (e.g. ~30 of 100) across the window rather than approaching the limit
- postgres-side connection usage remains below its own limit while backend pool_waiters are elevated

## Supporting evidence
- `incident_1001-E-003`
- `incident_1001-E-004`
- `incident_1001-E-005`
- `incident_1001-E-007`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_1001-E-007']

## Unresolved


## Stop reason
Finalized on hyp-2354bf4d3f473cedacf9117199ff63a5928dab8fb231824dd4f90ea588ae234e (backend_pool_config_regression): latest review verdict 'sufficient' with no contradictions or requested checks; observed in-window config mechanism incident_1001-E-003 plus cause discriminator incident_1001-E-004 (db_pool_max 20 -> 2; concurrency=120) supported by the coincident pool_waiters=118 symptom (incident_1001-E-005) across changes/configs and metrics, with the competing postgres_connection_exhaustion hypothesis refuted by incident_1001-E-007 and the stale headroom open question resolved.

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
