# IncidentLens — RESOLVED

Run: `run-d3c32eaa8bb84b9388d89a37fb54d907`

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
Remediation: NOT_STARTED
Workflow: FINISHED
