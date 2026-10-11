# IncidentLens — RESOLVED

Run: `run-987fb3ff05024497ae59d73c36e8ae55`

Incident: `incident_001`

## Root cause
backend_pool_config_regression

## Causal chain
- Reduced backend pool capacity causes local acquisition contention
- Acquisition deadlines fail while database capacity remains available

## Supporting evidence
- `incident_001-C001`
- `incident_001-D001`
- `incident_001-M009`

## Rejected hypotheses
- postgres_connection_exhaustion: ['incident_001-M004']

## Unresolved


## Stop reason
Evidence sufficient
