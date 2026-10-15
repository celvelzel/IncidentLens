# V1.6 ownership and dependency record

Lead owns integration, docs/v16, server.py, schemas, configs and shared contracts. Existing untracked docs/plans/v16 belongs to user; retain unchanged. No worker may delegate, overwrite another worker, change guards to manufacture success, or run paid API calls.

| Packet | Worktree / branch | Write scope |
|---|---|---|
| WP-A | .worktrees/v16-a / codex/v16-a | agents/, orchestration/, llm/, tests/integration/test_v16_e2e*, tests/reliability/test_v16*, scripts/v16_e2e_preflight.py, docs/acceptance/v16-* |
| WP-B | .worktrees/v16-b / codex/v16-b | incidentbench/builder.py, scenarios/, family_split.py, validator.py, tests/incidentbench/test_generation_v16*, docs/incidentbench/v16-*, new dev public data; private candidate oracle only ignored local_oracles/ |
| WP-C | .worktrees/v16-c / codex/v16-c | web/static/, tests/web/, docs/ui/v16-* |
| WP-D | .worktrees/v16-d / codex/v16-d | evaluation/ (excluding termination.py unless RFC), scripts/v16_eval*, scripts/run_incidentbench.py, scripts/analyze_incidentbench.py, tests/evaluation/test_v16*, docs/evaluation/v16-* |
| WP-E | read-only integrated checkout | QA findings returned to Lead; no business edits |

Max 3 workers: A/B/C first, D when slot opens; E independently audits integrated implementation. This is bounded concurrency, not five simultaneous workers. G0 precedes implementation. A/B contracts frozen before D preparation; G1a+G2a+explicit budget precede real pilot, G2b precedes formal research claims. Shared-file changes require Lead RFC. Workers commit only owned files; Lead reviews commits and cherry-picks serially. Never bulk-stage private data/results/user plans.

Lead shared-boundary ownership extension: artifacts.py, cli.py, tests/integration/test_v16_artifact_boundaries.py (no worker overlap). Contract1.1 is additive validation; workers notified. No JSON schema/interface migration.

## Actual scheduling / integration history
E read-only baseline audit ran while G0 suite executed; no implementation began before G0. A/B/C ran truly concurrently in separate worktrees. A/B completion freed slots for D and independent E follow-up. C delivered isolated correction after E found cumulative snapshots. D remained frozen through80attempts/reanalysis. Lead integrated commits serially, verified exact data bytes and independently ran UI/API/tests. Max3workers was respected; no worker delegated.
A:be4491d ->bf434c5; B:6e651fd ->a75a75c plus exact-byte restorationde092ed; C:a9fe275 ->62a93ef and a36deba ->a9b387e; D:0e361dc ->0af1292. Lead final boundary/eval fixes5695203,c69ac16. E independent read-only findings and resolutions documented in qa-release-report.md. Worktrees and all raw/private evidence retained; no archive/removal.
