# IncidentLens — RESOLVED

Run: `run-d0fa200903a54603b2a15a644dbce502`

Incident: `incident_1001`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_1001-E-001] backend: request_latency_ms=40 ms
- 2026-10-01T12:00:10+00:00 [incident_1001-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1001-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_1001-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:10+00:00 [incident_1001-E-007] postgres: Server connections below limit

## Predictions (not confirmed observations)
- Backend pool_waiters stay elevated (118 requests at 2026-10-01T12:00:10Z) while postgres connection_count remains far below its connection_limit of 100.
- Backend request latency exceeds its deadline and propagates to the downstream gateway http_5xx_rate once the reduced db_pool_max of 2 can no longer service concurrency 120.
- The degradation onset coincides with the runtime-1 change at 2026-10-01T12:00:10Z that reduced db_pool_max from 20 to 2 while concurrency stayed at 120.

## Supporting evidence
- `incident_1001-E-001`
- `incident_1001-E-003`
- `incident_1001-E-004`
- `incident_1001-E-005`
- `incident_1001-E-007`

## Rejected hypotheses
- backend_resource_saturation: ['incident_1001-E-004']
- postgres_connection_exhaustion: ['incident_1001-E-004', 'incident_1001-E-007', 'incident_1001-E-009']
- postgres_connection_exhaustion: ['incident_1001-E-006', 'incident_1001-E-007']

## Unresolved


## Stop reason
Causal support for backend_pool_config_regression is complete and consistent: the observed runtime-1 change (incident_1001-E-003) reduces db_pool_max from 20 to 2 while concurrency stays 120 (incident_1001-E-004), backend pool_waiters reaches 118 at the change timestamp (incident_1001-E-005) with backend latency onset preceding the downstream gateway 5xx (incident_1001-E-001, incident_1001-E-009), and postgres stays well below its connection limit (incident_1001-E-006, incident_1001-E-007) so the bound is application-side. The competing postgres_connection_exhaustion and backend_resource_saturation explanations are rejected against observed contrary evidence, and no unqueried source remains for a further discriminating check.

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
