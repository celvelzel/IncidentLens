# CAES engineering experiments — actual observations

Final runtime commit: `2611182`. Authority: V1.5 CodingAgent Implementation Plan.
This is unsealed public Seed/Mock evaluation, **not P4 Dev calibration or P5 Frozen Test**.
The exact frozen source hash is
`c15ff679a5e1ecfb696da04c6118a0c798722ac43027917dd82bf80abea0f56a`.
Manifest/protocol/source/config/prompt/dependency/public-data hashes are saved with each batch.
No runtime or analysis reads Frozen Test Oracle; correctness/human support metrics are null.

Final batches: `results/v15/seed-six-20261014-v3` and
`results/v15/seed-tight-20261014-v3`, 120 genuine Graph runs each, six groups ×20 cases.
No cache, one job, same provider/model/tool ACL/recovery and budgets within each batch.
Normal limits: 32 requests,24 tools,6 rounds,600 seconds. Tight:12 requests,8 tools,4 rounds,
600 seconds. Both repeat1, run-order seed15100, analysis seed15101,10000 bootstrap samples.
Limits are maximum allowances, not extra CAES calls. The final batches are never selectively
rerun: completed-resume returned120 each and independently verified preserved record bytes.

## Normal budget

| Group / actual path | Technical completion /20 | Runtime failures | Resolved reports | Mean logical/model requests | Mean tools |
|---|---:|---:|---:|---:|---:|
| B0 actual fixed-four |20|0|4|8.00|6.00|
| B1 original dynamic (CAES bypass)|20|0|7|12.20|7.10|
| B1c common candidates, first eligible|20|0|4|15.70|8.85|
| B2 CAES without cost denominator|20|0|2|17.80|9.80|
| B3 CAES without discrimination weight|20|0|2|17.80|9.85|
| B4 full CAES|20|0|1|17.80|9.75|

Resolved is a workflow outcome; it is **not verified correctness**. Technical completion
includes orderly inconclusive/abstained investigation. Existence-valid citations alone
do not prove semantic grounding. No accuracy or correct-abstention rate can be computed.

## Tight budget

| Group | Technical completion /20 | BUDGET_EXHAUSTED failures | Resolved reports | Mean requests | Mean tools |
|---|---:|---:|---:|---:|---:|
| B0 |20|0|4|8.00|6.00|
| B1 |17|3|4|11.15|6.50|
| B1c |20|0|4|11.00|6.35|
| B2 |0|20|0|12.00|6.85|
| B3 |0|20|0|12.00|6.85|
| B4 |0|20|0|12.00|6.95|

All63 failures are retained in raw/scores/errors/progress and denominators. Runtime
permits enforce the limit; selection reserve alone does not guarantee sufficient calls
for all later Coordinator/Verifier rounds. This is an observed algorithm limitation,
not evidence of safe completion or improved budget efficiency. No guard was weakened.

## Mechanisms and statistical limits

Normal247 and tight163 ACTION_SELECTED events replay exactly without model/tool execution.
244/247 normal and160/163 tight rounds have at least2 eligible retained candidates.
Actual executed role/question/filter sequences differ between B4 and B1c in20/20 paired
cases; B4 vs B2 and B3 differ in3/20 each. These compare complete executed sequences,
not isolated ranking decisions on identical per-round histories. The shared-pool synthetic
regression proves B1c/B2/B3/B4 genuinely distinct algorithms on controlled inputs.
Uniform fallback costs often make no-cost/full initial rankings equal; synthetic injected
costs demonstrate control flow, not Dev calibration or measured production cost estimates.

Primary B4-B1 paired mean cost difference: normal **+5.60 model requests,+2.65 tools**;
tight **+0.85 requests,+0.45 tools**. B4-B1c: normal+2.10 requests,+0.90 tools;
tight+1.00 requests,+0.60 tools. There is no cost-saving claim. HTTP attempts are0
because the provider is Mock; model requests are actual Mock structured calls, not HTTP
requests. Tokens, dollar cost and quality remain null, never substituted with zero.

Public Seed has20 cases but one unreviewed linked source cluster (four declared family
names do not establish independence). Primary cluster CI is null with an explicit reason;
no p-value, significance or generalization claim is justified. `uncertainty.json` preserves
pair counts/missingness and descriptive differences. Latency is measured locally during
engineering verification; concurrent test/install CPU activity and scheduler ordering
preclude performance inference. IDs include run identity, and concurrent specialist
completion can affect histories/ties; a fresh batch need not reproduce every outcome.
Saved-snapshot replay is exact. Source revisions/batch differences are not causal evidence.

## Preserved failed / superseded runs

`seed-six-20261014-frozen` (old source9ab8f9d):120 runs, four Verifier
`fetch_evidence_by_ids` BAD_ARGS failures: incident1019/B3,1013/B2,1015/B2,1016/B3.
These had empty published Boards. Conservative public cold-start priorities were fixed
atcee3987; none of these raw failures were deleted or overwritten. The old scores lack
the measured tool field (raw state retains counters); the corrected metrics are separately
versioned. Historical192 decisions were independently replayed with the historical selector.

`seed-six-20261014-v2` and `seed-tight-20261014-v2` belong tocee3987, before the
Recovery physical/logical reserve fix. Each has120 real Mock executions, offline analysis,
completed-resume and hash checks. They are preserved, not relabelled as2611182 results.
Other P0/live-tree lock-drift failures and early active ROLE_TOOL_PROPOSAL_FORBIDDEN smoke
remain saved. Final full-suite initial collection and mid-edit hash-drift failures remain
in their original logs; the final clean rerun has a unique filename.

Reproduction commands are in fairness-protocol.md. Final engineering summaries and
all410 selection replays are reproducible with
`python results/v15/final-20261014/audit_results.py`; saved score/receipt/hash recomputation
uses `scripts/analyze_v15_active.py` into a new output directory. No Oracle is passed.
