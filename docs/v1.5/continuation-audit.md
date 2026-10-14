# Continuation audit — 2026-10-14

User explicitly required resuming all interrupted work without skipping gates.
Resumed main HEAD was 9ab8f9d; only the same three pre-existing untracked items
remained (two plan files and results/acceptance/v14). No Python process remained.

Actual worker worktrees and scoped changes were reconciled against main history:

| WP | Worker terminal commit | Integrated delivery |
|---|---|---|
| A | e506812 | Candidate generation/eligibility/tests; 7cb9396,45275db,e506812 all applied |
| B | 76868ff | Feature/cost/selector/tests; later Lead symmetry fix 8754d4d retained |
| C | 0a35d25 | Runner/analysis/replay/resume/tests; all eight scoped worker commits applied |
| D | f72216f | Six documentation files and source-alignment followup applied |
| E | read-only | Previous P7 turn failed on account usage limit; explicitly resumed, not counted as acceptance |

Completed overnight: results/v15/seed-six-20261014-frozen contains 120 unique raw
records, 120 scores, 120 unique run IDs, and 120 STARTED plus 120 DURABLE records.
Six groups each have 20 runs. Four verifier BAD_ARGS errors remain in denominators.
Independent QA verified 23 top-level hashes, all saved scores, all 192 selections,
protocol/source/public-data lock, and progress order. Offline analysis completed;
explicit completed resume returned 120 records without re-executing completed runs.

The independent review found measured tool counters absent from score rows. That
Medium issue is a real defect, not completion: metrics now takes actual
state.tool_calls_used with unknown/null fallback. A new regression checks it.
Old artifact directories are preserved. A new uniquely named source-frozen run
must follow; old results are not represented as using the fix.

The four Verifier errors had empty published Boards. The runtime/Verifier gates
remain unchanged. A specification-required conservative cold-start tie rule now
prefers Logs/Metrics for equal scores while hypotheses are absent, with D still 0;
it uses public role semantics, not Oracle/family labels or inspected test answers.
The change is separately committed and hash-frozen before a new experiment.

Outstanding work at this checkpoint: new preflight/full suite, fresh experiment
and tight-budget comparison, independent recheck of fixes, fresh install/active
wheel smoke, final coverage/changed-files/phase/QA/results reports. None are
claimed completed by this checkpoint. P4/P5 scientific gates remain BLOCKED:
Dev/Test empty, no accepted labels/human semantic review, no audited independent
families, no formal sealing or confirmed real-provider completion.
