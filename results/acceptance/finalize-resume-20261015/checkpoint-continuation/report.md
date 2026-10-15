> OFFLINE continuation of saved v4 state; no new API calls. Original v4 run remains FAILED.

# IncidentLens — RESOLVED

Run: `run-0c72d8de98e14b37b49a85f63e4133b3`

Incident: `incident_2001`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:10+00:00 [incident_2001-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_2001-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_2001-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:14+00:00 [incident_2001-E-008] backend: Request processing exceeded deadline
- 2026-10-01T12:00:14+00:00 [incident_2001-E-009] gateway: http_5xx_rate=0.35 ratio

## Predictions (not confirmed observations)
- Backend pool_waiters elevated (118) at change time
- Backend log reports request processing exceeded deadline after change
- Gateway http_5xx_rate elevated (0.35) after change

## Supporting evidence
- `incident_2001-E-003`
- `incident_2001-E-004`
- `incident_2001-E-005`
- `incident_2001-E-008`
- `incident_2001-E-009`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_2001-E-007', 'incident_2001-E-004']
- backend_resource_saturation: ['incident_2001-E-003', 'incident_2001-E-004', 'incident_2001-E-008']

## Unresolved


## Stop reason
Causal chain confirmed: backend config change (db_pool_max 20->2, concurrency=120) at 12:00:10Z -> pool_waiters=118 -> backend request timeout (E-008) -> gateway http_5xx_rate=0.35 (E-009). Postgres connection count 30/100 is consistent with backend pool limiting connections rather than postgres exhaustion. No other change records observed in the window.

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
