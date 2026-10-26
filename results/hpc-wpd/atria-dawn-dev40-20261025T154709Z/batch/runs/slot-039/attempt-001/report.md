# IncidentLens — RESOLVED

Run: `run-17687fbc00f345428325069b59ada915`

Incident: `incident_3001`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-11T09:00:27+00:00 [incident_3001-E-003] backend: Runtime settings deployment applied
- 2026-10-11T09:00:27+00:00 [incident_3001-E-004] backend: db_pool_max 20 -> 2; concurrency=155
- 2026-10-11T09:00:27+00:00 [incident_3001-E-005] backend: pool_waiters=153 requests
- 2026-10-11T09:00:27+00:00 [incident_3001-E-007] postgres: Server connections below limit
- 2026-10-11T09:00:36+00:00 [incident_3001-E-008] backend: Request processing exceeded deadline

## Predictions (not confirmed observations)
- A backend config change reducing db_pool_max precedes queue buildup.
- pool_waiters rises to approximately concurrency minus db_pool_max after the change.
- Request deadline warnings first appear only after the config deployment.
- Postgres connections remain well below max_connections during the waiter spike.

## Supporting evidence
- `incident_3001-E-003`
- `incident_3001-E-004`
- `incident_3001-E-005`
- `incident_3001-E-007`
- `incident_3001-E-008`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_3001-E-005', 'incident_3001-E-007']
- backend_resource_saturation: ['incident_3001-E-003', 'incident_3001-E-004']

## Unresolved


## Stop reason
Causal support and chronology are established from two independent source types (changes/config and backend metrics) plus corroborating log chronology and postgres connection state; competing hypotheses are contradicted or lack any observed cause discriminator, and the most recent review verdict is sufficient with no remaining blocking checks.

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
