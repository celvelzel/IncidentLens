# IncidentLens — RESOLVED

Run: `run-c4ce80b8c7e94281b619047ad5783b4a`

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
