# WP-B handoff

WORKSTREAM: B
BASE SHA: 50c21e8
DEPENDENCIES: A 7cb9396 + 45275db (cherry-picked locally for validation only).
OWNED/CHANGED: feature_extractors.py, cost_estimator.py, selector.py; test_feature_extraction.py, test_cost_estimation.py, test_selector.py; this handoff.
CONTRACT: frozen caes-v1 DTO and function signatures in contract-freeze.md.

Features are deterministic lexical heuristics, not calibrated information gain. D uses only non-rejected published hypothesis predictions: distinct prediction sets, candidate matches both, and matches at least one contrast token. Shared generic service words alone do not yield D. No failure_mode/root-mode lookup. Negations are retained. U covers published exact requested checks or open-question token coverage. G independently rewards absent role source (.5; 1 with published grounding errors). G predicts possible contribution; it never certifies sufficiency. R is exact completed signature on the same evidence snapshot. Different windows/snapshots are not completed duplicates. Pair diversity uses same role+filters and token Jaccard, preserving opposite negation sets.

Cost fallback is two logical Investigator requests times physical attempt multiplier, two planned tool calls even with one schema. Token and latency remain null; source fixed_fallback. No permit is charged. Selector checks both each task and aggregate selected tasks plus one policy Verifier reserve (physical multiplier for requests, one fetch tool). Lead adapter must use max(existing recovery reserve, policy reserve), not double subtract. Wall <=0 rejection is A's responsibility; latency is unknown and runtime deadline remains authoritative.

Scoring: weighted D/U/G minus R divided by epsilon+request/tool units. B2 uses constant denominator; B3 zeros D weight. B1c preserves input order. CAES selects only positive scores above min_score; duplicate selected work is excluded, stable ties use candidate ID. Zero selection returns NO_USEFUL_ACTION. current_dynamic raises to enforce runtime bypass. No model/tool/provider/oracle/evaluation dependency or execution.

ACTUAL COMMANDS (PowerShell, worktree v15-b):
$env:PYTHONPATH=(Join-Path $PWD 'src')
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m pytest tests/active_investigation -q
Result: 70 passed (25 B tests, 45 A/contracts).
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m ruff check src/incident_lens/orchestration/active_investigation tests/active_investigation
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m ruff format --check src/incident_lens/orchestration/active_investigation tests/active_investigation

Same-pool synthetic fixture proves B1c/B2/B3/B4 select respectively first/expensive/gap/cheap. The fixture injects synthetic dev_aggregate estimates; this is NOT empirical Development calibration. Production fallback costs are uniform, so B2 and B4 can coincide. Future calibrated tables require frozen Dev aggregates; no calibration is claimed here.

Remaining risks: lexical heuristics can miss paraphrases or overvalue superficial contrast, and source categories rely on Lead's projection. Runtime integration, feature-off/shadow equivalence, STOP race, empirical calibration and real provider/research experiments are Lead gates, not proved by these pure-function tests. No shared files were edited. MERGE READINESS: PASS engineering only.
