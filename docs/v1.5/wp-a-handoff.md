# WP-A handoff

Base SHA: 50c21e897f5261d2232704d3ccdf0a531a8e299f. Frozen caes-v1 contracts unchanged.
Owned/changed files: candidate_generator.py, eligibility.py in src/incident_lens/orchestration/active_investigation; tests/active_investigation/test_candidate_generation.py and test_candidate_eligibility.py; this handoff.

Functions: generate_candidates, candidate_signature, check_eligibility match frozen interfaces.
Three origins, deterministic candidate IDs, public service templates, snapshot-bound canonical signatures and explicit runtime ACL. Requested checks win duplicate conflicts and cap precedence; Coordinator order is otherwise preserved for first_eligible. No filesystem/provider/tool calls or mechanism lookup.

Example replay: visible run=r, incident=i, decision=d, snapshot=board with public backend start 2026-01-01T00:00Z and one logs proposal produces proposal plus logs/metrics/changes templates under the test ACL. Repeating generate_candidates yields exactly equal DTOs. Completion signatures bind board; changed board/window allows another check.

Filters are partial planning hints, matching the existing InvestigationTask contract. Supplied fields must satisfy one allowed existing tool schema; missing required tool arguments are left to actual plan/ToolRegistry validation. Templates supply complete args; time-bearing templates use public started_at +/-15 minutes. Dependency topology template has no time schema. Database templates exist only when runtime ACL includes database tools; all public services are eligible, with actual data availability checked at execution.

Commands (worktree root; main virtualenv only):
```powershell
$env:PYTHONPATH=(Join-Path $PWD src)
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m pytest tests/active_investigation -q
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m ruff check src/incident_lens/orchestration/active_investigation/candidate_generator.py src/incident_lens/orchestration/active_investigation/eligibility.py tests/active_investigation/test_candidate_generation.py tests/active_investigation/test_candidate_eligibility.py
& C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe -m ruff format --check src/incident_lens/orchestration/active_investigation/candidate_generator.py src/incident_lens/orchestration/active_investigation/eligibility.py tests/active_investigation/test_candidate_generation.py tests/active_investigation/test_candidate_eligibility.py
```

Expected final result: 43 passed (30 owned tests plus 13 contracts), no failures/skips; Ruff check/format pass. Actual command output reported in commit handoff.

Limits: text evidence-reference detection covers conventional evidence-/ev-/e- or underscore identifiers; arbitrary free-text references cannot be exhaustively identified. Explicit prerequisites/filter IDs are fully checked. Private markers are conservative rejection guards, not a semantic security classifier. Public window and cost are uncalibrated heuristics. Wall check only excludes zero remainder because no calibrated latency exists. Request reserve includes physical multiplier; runtime is final permit/deadline authority and must combine recovery reserve using max, not additive. Runtime task identity creation, STOP recheck, trace and aggregate selection budgets remain Lead/B ownership. Formal Dev/Frozen research remains blocked upstream; no quality/cost improvement claims.

Merge readiness: PASS for scoped pure-module engineering; runtime integration pending Lead.

Followup: templates now round-robin legal roles before advancing sorted services, preventing the pool cap from excluding database/changes when multiple services exist. Coordinator/request source priority is preserved. Eligibility reserves two planned tool invocations even for one tool schema, because the plan may invoke the same tool twice. Followup validation: 45 active tests pass; scoped Ruff check and format pass.
