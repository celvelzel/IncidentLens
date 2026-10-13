# IncidentLens — RESOLVED

Run: `run-33e11999fe924776ada425a948e0e577`

Incident: `incident_037`

## Root cause
postgres_connection_exhaustion

## Causal chain
- Database sessions reach server connection capacity
- New database sessions are rejected and backend requests fail

## Supporting evidence
- `incident_037-DB001`
- `incident_037-L002`
- `incident_037-M004`
- `incident_037-M009`

## Rejected hypotheses


## Unresolved


## Stop reason
Evidence sufficient

## Workflow
Diagnosis: RESOLVED
Remediation: PLAN_READY
Workflow: FINISHED

## Remediation — PLAN_ONLY
Proposal only; no actions executed and no service recovery confirmed.
Mitigate postgres_connection_exhaustion in postgres after operator approval.

### Affected Services
- postgres

### Actions
- If active sessions and connection limits confirm exhaustion, reduce incoming concurrency on a canary and review idle sessions with the database owner before any termination.

### Preconditions
- Operator approval, current causal measurements, approved baseline, and a tested rollback are required.

### Risks
- Configuration changes can shift load to dependencies or interrupt requests; assess capacity and consistency first.

### Verification Steps
- Compare the cited causal signal, service error rate, latency and downstream health against the pre-change baseline during the canary window.

### Rollback
- If health deteriorates or the causal signal fails to recover, stop rollout and restore the captured approved configuration or routing state.

### Evidence Ids
- incident_037-DB001
- incident_037-L002
- incident_037-M004
- incident_037-M009
