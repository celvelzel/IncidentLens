# WP-D handoff

Base: 1c95339. Scope: algorithm-spec.md, fairness-protocol.md,
experiment-preregistration.md, dev-results.md, future-work.md and this handoff.
No runtime, old UI, README, graph, schemas, dataset or result files changed.
Authoritative main plan read in full; A/B/C contracts and actual implemented code reviewed.
Existing saved JSON replay fulfills the secondary CLI trace view; no new renderer added.

Public interfaces: CandidateAction/VisibleState/BudgetView/SelectionDecision,
PolicyConfig, ActiveProtocol, workflow_values, saved ACTION_SELECTED replay.
Defaults, lexical D, source G, uniform cost fallback, aggregate feasibility, unknown
usage and six actual code paths are documented. Historical negative smoke is explicitly
source-stale. Preregistration status is BLOCKED_NOT_PREREGISTERED, with no invented hashes.

Actual validation (own worktree PYTHONPATH=src; main .venv Python):

```powershell
$py = 'C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $PWD 'src'
& $py scripts/run_v15_active_eval.py --help
& $py scripts/analyze_v15_active.py --help
& $py scripts/replay_v15_selection.py --help
& $py -m pytest tests/active_investigation/test_score_replay.py tests/active_investigation/test_ablations.py tests/active_investigation/test_experiment_fairness.py -q
& $py scripts/replay_v15_selection.py --trace C:\Develop\python_projects\COMP5584_Agents\IncidentLens\results\v15\active-smoke-20261014\trace.json
git diff --check
```

Three CLI help checks pass. Saved historical replay returns two matching decisions.
Adjacent C tests at D's pinned base: 24 passed, 1 failed in 11.17s. Failure is
test_default_protocol_runs_genuine_graph_all_six: incident_1001.B1c.repeat-0 reports
UNRECOVERABLE_ERROR in retained pytest-523 temporary ledger. This is reported to Lead;
D makes no runtime patch outside ownership. It is not final main acceptance, which
has later integrated fixes. git diff --check passes. No new program files were added,
so no D-owned Python Ruff targets exist. Later final main checks remain Lead-owned.

Remaining Lead work: insert only exact later saved Seed/tight-budget results and final
QA evidence; preserve the negative smoke. Full runtime/release tests are Lead-owned.
Formal research criteria are unmet: independent families, reviewed labels, Dev/Test,
provider readiness, calibration, preregistration and untouched Test evaluation.
MERGE READINESS: PASS scoped documentation; pinned-base adjacent runtime failure requires
Lead's current-source validation. Research BLOCKED.
Followup: inspected latest main source read-only after Lead integration. Updated
resume contract for 67fb9a5, D symmetry rule and final smoke's actual saved termination.
Counts for final smoke are Lead-supplied (7/3 versus 15/9); saved result termination
was directly verified. D pinned-base test result remains historical and unchanged.
