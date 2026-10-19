# IncidentLens — RESOLVED

Run: `run-7d980b48a2444a66b23f55d6934633c9`

Incident: `incident_1002`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:10+00:00 [incident_1002-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_1002-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:14+00:00 [incident_1002-E-008] backend: Request processing exceeded deadline

## Predictions (not confirmed observations)
- Backend deadline errors appear from 2026-10-01T12:00:14Z, approximately four seconds after the runtime-1 configuration change, consistent with connection-pool starvation.
- If the pool regression is causal, backend pool acquisition wait/queue metrics rise while upstream datastore latency stays flat.
- The change_id runtime-1 config diff shows db_pool_max reduced from 20 to 2 and concurrency=120 at 2026-10-01T12:00:10Z.

## Supporting evidence
- `incident_1002-E-003`
- `incident_1002-E-004`
- `incident_1002-E-008`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_1002-E-007']

## Unresolved


## Stop reason
Finalize backend_pool_config_regression on the backend service: incident_1002-E-003 (runtime-1 configuration change applied 2026-10-01T12:00:10Z) and incident_1002-E-004 (config diff, db_pool_max 20 -> 2 with concurrency=120) show the deployment reduced the backend database connection-pool size, and incident_1002-E-008 (backend 'Request processing exceeded deadline' at 2026-10-01T12:00:14Z) records the matching downstream symptom four seconds later; the competing postgres_lock_contention candidate is unsupported with all of its first-party discriminating scopes exhausted empty, and the REJECTED postgres_connection_exhaustion candidate is refuted by incident_1002-E-007 (connection_count 30 against connection_limit 100).

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
