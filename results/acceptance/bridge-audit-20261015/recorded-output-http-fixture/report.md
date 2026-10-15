# IncidentLens — RESOLVED

Run: `run-21c5db5c6b9d4e399345ba8caa1a3f39`

Incident: `incident_2001`

## Root cause
backend_pool_config_regression

## Causal chain
- 2026-10-01T12:00:00+00:00 [incident_2001-T-backend] backend: backend depends on: postgres, redis, payment
- 2026-10-01T12:00:00+00:00 [incident_2001-T-gateway] gateway: gateway depends on: backend
- 2026-10-01T12:00:10+00:00 [incident_2001-E-003] backend: Runtime settings deployment applied
- 2026-10-01T12:00:10+00:00 [incident_2001-E-004] backend: db_pool_max 20 -> 2; concurrency=120
- 2026-10-01T12:00:10+00:00 [incident_2001-E-005] backend: pool_waiters=118 requests
- 2026-10-01T12:00:14+00:00 [incident_2001-E-009] gateway: http_5xx_rate=0.35 ratio

## Predictions (not confirmed observations)
- Backend error-rate increase correlated with the reduced db_pool_max=2
- Database connection-pool wait or acquisition timeout errors from backend
- Elevated backend request latency beginning at or after 2026-10-01T12:00:10Z
- a backend connection-pool configuration change precedes the pool_waiters rise
- backend pool_waiters stays elevated while request_latency_ms rises after 12:00:10Z

## Supporting evidence
- `incident_2001-E-003`
- `incident_2001-E-004`
- `incident_2001-E-005`
- `incident_2001-E-009`
- `incident_2001-T-backend`
- `incident_2001-T-gateway`

## Rejected hypotheses
- backend_resource_saturation: ['incident_2001-E-004']

## Unresolved


## Stop reason
backend_pool_config_regression confirmed with a sufficient review and no contradictions. The retrieved runtime-1 diff (incident_2001-E-004) lowered backend db_pool_max 20->2 with concurrency=120 at 2026-10-01T12:00:10Z; the configured service then shows the matching pool_waiters=118 symptom at 2026-10-01T12:00:10Z (incident_2001-E-005), and the only diverging node, downstream gateway http_5xx_rate=0.35 at 2026-10-01T12:00:14Z (incident_2001-E-009), sits along the observed edges gateway -> backend -> {postgres, redis, payment} (incident_2001-T-gateway, incident_2001-T-backend). Two independent source types (configs/changes and metrics) supply the mechanism, the matching service symptom and the downstream effect in causal order; the pre-change 40 ms latency baseline (incident_2001-E-001) is baseline chronology, not a contradiction, and the competing backend_resource_saturation account is displaced by the observed configuration change.

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
