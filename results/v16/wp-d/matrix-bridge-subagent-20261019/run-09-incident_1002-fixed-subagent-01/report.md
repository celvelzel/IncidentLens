# IncidentLens — RESOLVED

Run: `run-364d388e50a84e5e9ce060bb43f68761`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_1002-T-gateway] gateway: gateway depends on: backend
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:14+00:00 [incident_1002-E-008] backend: Request processing exceeded deadline
- 2026-10-01T12:00:14+00:00 [incident_1002-E-009] gateway: http_5xx_rate=0.35 ratio

## Predictions (not confirmed observations)
- Backend connection pool saturation metrics (active connections near db_pool_max=2) coincident with the runtime-1 application timestamp 2026-10-01T12:00:10Z
- Backend errors indicating pool wait/timeouts under concurrency=120 while pool max is only 2
- Gateway layer shows downstream backend errors rather than its own routing or presentation failures
- application pool_limit or pool_in_use saturated while postgres connection_count remains well below connection_limit
- config diff showing a reduced pool size or changed pool timeout near the incident window
- connection acquisition timeouts reported by the backend while database capacity is healthy

## Supporting evidence
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-008`
- `incident_1002-E-009`
- `incident_1002-T-gateway`

## Rejected hypotheses
- backend_resource_saturation: ['incident_1002-E-004']
- postgres_connection_exhaustion: ['incident_1002-E-007']

## Unresolved


## Stop reason
Backend runtime-1 configuration change applied at 2026-10-01T12:00:10Z reduced db_pool_max from 20 to 2 under concurrency=120 (incident_1002-E-003, incident_1002-E-004), and the backend then exceeded its processing deadline at 12:00:14Z (incident_1002-E-008) with the gateway http_5xx_rate rising to 0.35 at 12:00:14Z (incident_1002-E-009), a coherent causal chronology for backend_pool_config_regression. Postgres connection capacity remained healthy (incident_1002-E-007), no resource-saturation discriminator was observed for the generic competitor, and the completed scopes leave no further discriminating check, so the decision is to finalize on the config-regression hypothesis.

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
