# IncidentLens

IncidentLens: An Evidence-Driven Multi-Agent System for Software Incident Investigation.

Python 3.11+; offline synthetic evidence; role-scoped read-only tools; LangGraph
dynamic investigation; structured evidence references; independent verifier;
bounded investigation and explicit abstention. Reporter is deterministic.

## Install (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m incident_lens.cli --version
.venv\Scripts\python.exe -m incident_lens.cli check-environment
```

P0 delivers contracts, packaging, immutable context types and schema tests.
The CLI currently checks the environment and exports frozen JSON Schemas.
Investigation commands are added after the P1 evidence boundary and P3 graph
gates. Mock will work without credentials; real provider execution must require
explicit credentials and cannot silently fall back to Mock.

## Contracts and security

`src/incident_lens/schemas/` is the sole Pydantic JSON boundary. Frozen role ACLs
and contexts live in `security/context.py`; `security/scoped_client.py` defines
the read-only client interface. P0 types do not implement server identity
issuance or actual data access control; those are P1 requirements. Runtime
investigators cannot access private evaluation truth. No shell or arbitrary
filesystem tools are allowed. This is application isolation, not an OS sandbox.

`cache/policy.py` permits caching only local explanation tasks. Coordinator
routing, verifier verdicts and final reports are never cacheable. Namespace
includes identity, evidence digest, dataset, model/parameters, prompt, schema
and ACL versions. Baseline architecture experiments always run with cache off.

## Documents

See `docs/source/` for the complete source design/implementation snapshots;
`docs/phase-plan.md` for dependencies and file ownership; `docs/protocol.md`
for frozen interfaces and `docs/acceptance/` for actual phase evidence.
The Notion contributor matrix is a proposed assignment, not proof of human
ownership. Tests and Mock demonstrations are not real LLM accuracy results.
