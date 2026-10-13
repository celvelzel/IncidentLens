# P0 repository audit

Baseline: 5f2cb2a2bbe1a07469c12e667a3f25ea6a2d1cc1, main; remote main verified equal via git ls-remote. Only pre-existing untracked file: V1.4 implementation plan. No pull/rebase/reset.

Actual tests: 637 passed, 2 skipped (host symlink privilege), 100.22s. Ruff passed; validate-data ok. Legacy seed 24 actual Mock graph runs, four variants. V1.2 incident_037 response RESOLVED, 7 tools, 12 model calls. Logs: results/acceptance/v14/p0.

V1.3 engineering merged. Historical live pilot 0/3 technical completion in each group, minimal json_schema capability established only. Real efficacy unproven; formal V1.4 requires readiness and review gates.

EvidenceProvider accepts only incident.json/logs.jsonl/metrics.csv/changes.jsonl/configs.jsonl and optional database.jsonl, IDs incident_[0-9]{3,}; topology/services.yaml. Metadata allowlists remain unchanged. Private oracle currently legacy post-run loader; new OracleStore stays evaluator-only. Supported core mechanisms: backend pool config, postgres connections, redis availability, payment timeout, backend saturation, postgres locks/slow query; discriminator guard unchanged.

Default legacy_rca; database enabled, equivalent tools opt-in. Legacy fixed has three experts. Single equivalent DB is available; fixed_four requires explicit additive workflow option. Normal STOP vs runtime failure uses evaluation/termination.py; citation validity requires observed TOOL_CALL records. Unknown tokens/cost stay null; MeasuredProvider counts physical attempts.

Human reviewers not yet confirmed. All generated labels remain pending; no Frozen Core accepted, no strict blind claim. Legacy source/data hashes in baseline-hashes.json.
