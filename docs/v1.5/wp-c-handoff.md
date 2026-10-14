# WP-C handoff

Base: 50c21e8. Contract: CAES caes-v1 frozen DTOs and Lead WorkflowOptions fields.

Owned changes: evaluation/active_evidence/{variants,runner,metrics,statistics,replay}.py,
package init, scripts/{run_v15_active_eval,analyze_v15_active,replay_v15_selection}.py,
tests/active_investigation/test_{ablations,experiment_fairness,score_replay}.py.

Validation: main .venv Python, own-worktree PYTHONPATH=src. pytest on the three owned
test files: 20 passed. Ruff check and format scoped to owned files pass after formatting.
CLI --help validated separately. No real Graph CAES claim before Lead A/B/shared integration.

Interfaces: ActiveProtocol, workflow_values, run_experiment(dataset, split, factory, out,
protocol), analyze(rows), replay_selection(ACTION_SELECTED.details). B0 uses benchmark
fixed-four Graph variant fixed; B1 full current_dynamic bypass; B1c/B2/B3/B4 full with
first_eligible/active_no_cost/active_no_discrimination/active_evidence respectively.

Runner uses existing MeasuredProvider, usage_metrics, saved-state scoring with Oracle=None,
public dataset validation and source/prompt/config/dependency locks verified per run.
Cache off, jobs 1, matched budget and equivalent DB ACL, no monitoring/remediation.
Durable raw/errors/progress ledger and exact-state receipt retain runtime failures/cancellation.
Every provider must be fresh and model/temperature/recovery consistent. Saved selectors replay
via pure select_candidates using saved public state/candidates/budget/config/ACL.

Formal/Test and real empirical gates fail closed. Empty Dev/Test fail before provider creation.
Seed output is engineering-only; correctness and human grounded success remain null without
reviewed evaluator labels. Unknown usage stays null. Source-linked clusters use V1.4 union;
one independent cluster yields null CI with explicit reason. Duplicate repeats rejected.

Remaining: Lead must execute actual six-group Seed Graph E2E after selector integration and
saved trace replay; no real provider or private Oracle/Test label access was performed.
Resume is intentionally unsupported (new unique output only); interrupted durable ledgers
remain audit artifacts, and completion analysis refuses incomplete schedules. Formal protocols
need future independent sealing/label owner authorization before enabling research.

Example: python scripts/run_v15_active_eval.py --dataset data/incidentbench_v1 --split seed
--variants B0 B1 B1c B2 B3 B4 --provider mock --out results/v15/UNIQUE
Analysis: python scripts/analyze_v15_active.py --input results/v15/UNIQUE --out results/v15/ANALYSIS
Replay: python scripts/replay_v15_selection.py --trace SAVED_TRACE.json

Follow-up: replay validates saved datetime DTOs in JSON mode; added aggregate/paired/action/family/error/calibration/source artifacts. --resume explicitly refuses without modifying partial artifacts. CLI protocol settings are preserved unless an explicit override is supplied. 20 tests and owned Ruff checks pass.
