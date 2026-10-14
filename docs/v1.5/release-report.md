# IncidentLens V1.5 CAES delivery and acceptance

Authority: `docs/plans/IncidentLens_V1.5_CodingAgent_Implementation_Plan.md`, fully read
and executed with its fallback gates. Runtime frozen at local commit `2611182`;
final documentation commit is later, without changing runtime. No push performed.
Overall formal V1.5 research release: **BLOCKED_BY_UPSTREAM**.
Engineering final acceptance: **PASS**, independently verified clean full-r4.

## P0–P7 accounting

| Phase | Delivered evidence | Status |
|---|---|---|
| P0 | full repository/version audit; frozen baseline723pass3skip;110fault checks;80benchmark runs; legacy/response smokes | Engineering PASS |
| P1 | strict CAES DTO/PolicyConfig/WorkflowOptions; schema roundtrip and detached visible projection; contract-freeze.md | Engineering PASS |
| P2 | isolated WP-A/B/C implementations, targeted assertions, lint, local commits and handoffs; WP-D documentation | Engineering PASS |
| P3 | gated Graph integration, default bypass, Shadow fallback, actual selected task execution, unchanged downstream authorities | Engineering PASS |
| P4 | public Seed diagnostics and failures only; Dev is empty, no real compatibility completion or accepted labels | **BLOCKED**, no calibration claimed |
| P5 | six genuine algorithm paths, frozen engineering ledgers, resume/replay/statistics; Test empty/unsealed | **BLOCKED**, no preregistration/Test execution claimed |
| P6 | algorithm/fairness/failure/statistical reports; existing trace JSON/CLI replay exposes decisions without mutating them | Engineering documentation delivered; research inference **BLOCKED** |
| P7 | independent WP-E source/artifact review; clean full suite, lint, fresh wheel installation/active/shadow/replay | Engineering PASS; formal release **BLOCKED** |

No upstream Gate was silently marked complete. T50/T51/T56/T57/T66 formal acceptance
is BLOCKED_BY_UPSTREAM while synthetic/public engineering boundary assertions run.
See coverage-matrix.md for all T01–T68 evidence mappings.

## Workstream delivery / integration

| Workstream | Independent worktree / terminal delivery | Integrated scope |
|---|---|---|
| A | `.worktrees/v15-a`,e506812 | deterministic candidates/eligibility/dedup/cap/runtime ACL; all7cb9396,45275db,e506812 applied |
| B | `.worktrees/v15-b`,76868ff | D/U/G/R/cost/diversity/selector and actual-path ablation tests; Lead adds symmetry/cold-start corrections |
| C | `.worktrees/v15-c`,0a35d25 | genuine graph experiment runner, strict fairness, durable failures/resume, replay/export/statistics; all eight delivery commits integrated |
| D | `.worktrees/v15-d`,f72216f | algorithm/preregistration/fairness/Dev-limit/future/handoff documents; followup alignments applied |
| E | independent read-only reviewer | no implementation ownership; verifies source/permissions/budgets, final traces, receipts/hashes, negative results and wheel isolation |
| Lead | main shared interfaces | schema/config/CLI, LangGraph dispatch, visible projection, STOP/materialization rechecks, common integration/tests, final report |

Worker handoffs: wp-a-handoff.md,wp-b-handoff.md,wp-c-handoff.md,wp-d-handoff.md.
Existing worker worktrees/commits are retained for audit. No unrelated dirty files
were reset, staged or deleted. Original two untracked plan files and results/acceptance/v14
remain untouched; newly observed unrelated `_tmp_pdf/` is also preserved.

## Code changes

Complete repository-relative list: changed-files.txt (against baseline7c48da1).
Core additions: `orchestration/active_investigation/{contracts,candidate_generator,
eligibility,feature_extractors,cost_estimator,selector,policy}.py`; strict additive
`schemas/active_config.py`; gated modifications in graph/config/workflow/CLI;
`evaluation/active_evidence` runner/recovery/replay/metrics/variants/statistics;
three eval/analysis/replay scripts, example YAML,10 new active test modules and docs.
Existing Permit/Budget/ToolRegistry/Verifier/FinalizeGate/TaskManager/Provider business
implementations are not replaced. Existing investigator/merge acceptance is retained.

B1 bypasses CAES; B1c first-eligible, B2 no-cost, B3 no-D, B4 full scorer share hard
feasibility. B0 is actual fixed-four. No extra model/tool call for candidate generation;
cost estimates never charge permits. Actual calls are still runtime-controlled.

## Final checks and evidence

- Frozen baseline:723passed,3skipped,223.55s; logs at results/v15/p0-20261014.
- New active preflight before reserve correction:125passed59.79s; postcorrection graph15passed1.01s; independent affected46passed0.95s.
- Final full-r4: **850passed,3skipped,0failed,328.11s** (log/JUnit results/v15/final-20261014/full-pytest-r4.*); XML853tests,0errors,0failures,3skips independently verified. Skips are OS symlink privileges: ancestor symlink, public symlink and optional database symlink tests.
- Ruff check PASS; Ruff format174files PASS; git diff --check PASS.
- Fresh installed wheel7commands PASS, pip check and old CLI/data/replay included;
  results/v15/final-install-20261014-r2/install-log.json retains exact commands/exits/output.
  Wheel SHA eeded25230eb0cc54444b650760cf5c5bd0a8c545fad191b0c90e08b7595734a.
  Imported from retained environment site-packages outside source cwd.
- Installed Active:INCONCLUSIVE16Mock requests/8tools; Shadow:RESOLVED15/9;
  Active3selection replays match and old/shadow replay invokes no provider.
- Final normal+tight240 executions,247+163 selection replays; independent120receipts,
  score recomputations,23top-level hashes and ordered240progress rows per batch.
  Both offline analysis120 and completed resume120 PASS, no attempted record rerun.
- Final CAES9schema artifact results/v15/final-20261014/caes-contracts.json,
  SHA c1e2518bb84d26eaa69a94cc1a3055852ddeff1c82a6f135f03018c5f03b0e1f.

Exact reproducible commands:

```powershell
.venv/Scripts/python.exe -m pytest -q --junitxml=results/v15/final-20261014/full-pytest-r4.xml
.venv/Scripts/python.exe -m ruff check src tests scripts
.venv/Scripts/python.exe -m ruff format --check src tests scripts
.venv/Scripts/python.exe scripts/verify_install.py --out results/v15/NEW-install
.venv/Scripts/python.exe scripts/run_v15_active_eval.py --dataset data/incidentbench_v1 --split seed --variants B0 B1 B1c B2 B3 B4 --provider mock --out results/v15/NEW-normal
.venv/Scripts/python.exe scripts/run_v15_active_eval.py --dataset data/incidentbench_v1 --split seed --variants B0 B1 B1c B2 B3 B4 --provider mock --protocol results/v15/tight-protocol-20261014.json --out results/v15/NEW-tight
.venv/Scripts/python.exe scripts/analyze_v15_active.py --input results/v15/seed-six-20261014-v3 --out results/v15/NEW-analysis
.venv/Scripts/python.exe results/v15/final-20261014/audit_results.py
```

Use new output paths; existing outputs are intentionally not overwritten. Installed
wheel includes CAES runtime/CLI, while repository evaluation scripts/data/prompts remain
checkout artifacts (not a claimed standalone benchmark distribution).

## Experiments / unresolved issues

Detailed six-group normal/tight tables, denominators, paired differences and statistical
limits: experiment-results.md and results/v15/final-20261014/engineering-summary.json.
Normal B4-B1 means +5.6 requests,+2.65 tools; tight +.85,+.45. Tight63budget failures,
including20/20B4, retained. Results give no savings or efficacy claim. Root correctness,
human grounded success, tokens,dollars and valid family CI are unavailable/null.

Remaining gates: independent accepted labels/human semantic citation review, nonempty
Dev/Test, audited independent source families, dataset sealing and real-provider readiness.
Then P4 calibration/P5 registration/real paired experiments must run without Test tuning.
Engineering limits: lexical D/U/G/R is not calibrated information gain; uniform fallback
costs do not establish action-specific cost prediction; conservative reserves can round
up extra permits; bounded candidate overflow has no individual assessment; scheduler/run
identity can affect ties and fresh-batch outcomes; UI replay dropdown may reset under
concurrent trace additions (unproven cause of full-r3 failure, standalone UI retest PASS).

All failure/superseded attempts remain: old120fourVerifier errors, early failed active
smoke, initial P0 lock drift, full-r1collection errors, full-r2mid-edit lock drift,
full-r3UI mismatch and all63tight failures. qa-review.md records closed issues and the
independent review. No result was fabricated or relabelled to a later source revision.
