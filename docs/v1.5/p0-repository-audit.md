# P0 repository audit — 2026-10-14

Baseline main HEAD: `7c48da1`. Existing untracked V1.4 Review Bridge plan,
V1.5 authoritative plan and results/acceptance/v14 retained; no reset/push.
Full plan read, multi-agent skill/policies read; independent read-only QA verified gates.

Frozen baseline `.worktrees/v15-p0` at 7c48da1:
full pytest **723 passed, 3 skipped**, 223.55s. Symlink skips are host limitations.
Logs/JUnit: results/v15/p0-20261014/baseline-pytest.{log,xml}.
Ruff lint PASS, format 145 files PASS. Old data validation PASS.
Legacy incident_001 RESOLVED: 15 Mock calls/9 tools; response incident_037 RESOLVED:
12 Mock calls/7 tools. Reliability fault matrix 110/110.
V1.4 frozen-source smoke ran **80 Mock Graph investigations**, no Oracle supplied.
All commands/logs/results retained under results/v15/p0-20261014.

Failed attempts retained: initial live-tree pytest 722 passed/1 failed/3 skipped,
and first benchmark smoke raised benchmark lock drift because Lead added contracts
during hash-locked execution. These are orchestration mistakes, not silently discarded
passes. A second test invocation from parent cwd was interrupted during collection;
final baseline rerun used frozen-worktree cwd and PYTHONPATH. No source mutation during
subsequent final acceptance runs is allowed.

V1.3: code/reliability engineering present. Historical real pilot R0/R3 0/3 completion
each, unknown aggregate token costs; no evidence of positive RCA/provider efficacy.
V1.4 actual module maps to src/incident_lens/incidentbench; data root is
data/incidentbench_v1 (not proposed rca/ subfolder). Public validation PASS.
Seed/Dev/Test **20/0/0**, pending labels, 0 accepted labels, 0 audited independent
families, unsealed development_visible. Actual fixed-four exists. Formal runner
fail-closed. P4 Dev calibration, P5 Frozen Test and real inferential claims **BLOCKED**.
CAES contracts/engineering/Seed Mock diagnostics proceed under specification fallback.

Interfaces inspected: graph.coordinate INVES­TIGATE before DECISION publication,
typed InvestigationTask and requested_checks, CallBudget/permit/recovery, ToolRegistry
workflow-specific ACL, TaskManager/StopController, Verifier/FinalizeGate and existing
benchmark experiment/manifest/usage helpers. Lead owns shared integration. P1 contract
50c21e8 has 13 meaningful tests and detached published object projections; worker
base is that commit. A/B/C isolated worktrees have disjoint ownership.

Risks: no scientific independence/human semantic review; external Provider completion
unproven; heuristic cost not calibration; DTO nested containers shallow-frozen but
deep-isolated and digest checked before dispatch; STOP and combined budget must be
rechecked. No Frozen Test Oracle inspected or supplied to algorithm development.
