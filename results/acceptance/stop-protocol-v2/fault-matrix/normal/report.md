# IncidentLens — RESOLVED

Run: `run-325785ba477642c59177c58469812510`

Incident: `incident_001`

## Root cause
backend_pool_config_regression

## Causal chain
- Acquisition deadlines fail while database capacity remains available
- Reduced backend pool capacity causes local acquisition contention

## Supporting evidence
- `incident_001-C001`
- `incident_001-D001`
- `incident_001-M009`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_001-M004']

## Unresolved


## Stop reason
Evidence sufficient

## Workflow
Diagnosis: RESOLVED
Remediation: PLAN_READY
Workflow: FINISHED

## Remediation — PLAN_ONLY
Proposal only; no actions executed and no service recovery confirmed.
Mitigate backend_pool_config_regression in backend after operator approval.

### Affected Services
- backend

### Actions
- If the deployed pool configuration differs from the approved baseline and database capacity permits, restore the approved pool configuration on one canary instance.

### Preconditions
- Operator approval, current causal measurements, approved baseline, and a tested rollback are required.

### Risks
- Configuration changes can shift load to dependencies or interrupt requests; assess capacity and consistency first.

### Verification Steps
- Compare the cited causal signal, service error rate, latency and downstream health against the pre-change baseline during the canary window.

### Rollback
- If health deteriorates or the causal signal fails to recover, stop rollout and restore the captured approved configuration or routing state.

### Evidence Ids
- incident_001-C001
- incident_001-D001
- incident_001-M009
