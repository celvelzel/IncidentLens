# T6 closure and WP-D pilot — 2026-10-16

This record supersedes the earlier instruction to defer T6. The owner authorized
the historical model `deepseek-v4-flash-0731`, no overall budget cap, and the
existing accepted Seed pilot `incident_1001/1002/1003`. These are development
cases, not the separate Dev split or an independent held-out test.

## Historical failure attribution

Machine-readable evidence, original trace paths and hashes:
`results/v16/t6-closure/20261016-static-01/historical-t6-audit.json`.

| Attempt | Measured calls / tools | Observed termination | Interpretation |
|---|---:|---|---|
| g1a-20261015-01 / incident-2002-full | 35 / 27 | Round budget exhausted | No model failures; repeated empty changes checks |
| g1a-20261016-02 / incident-2002-full-attempt1-transport-failed | 12 / 7 | PROVIDER_TIMEOUT | Four model timeouts; transport failure |
| g1a-20261016-02 / incident-2002-full | 26 / 15 | Wall-clock budget exhausted | Eight timeouts plus final budget cancellation; mixed failure |

The old changes loop repeatedly treated omitted time bounds as an invalid query.
The tool actually searches the complete supplied pack when bounds are omitted.
A successful broad empty query establishes missing records within that pack,
not a healthy system. Reworded questions evaded the exact task-text loop guard.
Repeated tool calls after a model analysis timeout are retries and must not be
classified as successful completed checks.

## Reviewed repair

- Prompts explain broad-query semantics and when evidence gaps warrant abstention.
- Shared query history exposes success, returned count, pagination and task
  completion alongside the actual executed arguments.
- A conservative guard detects repeated completed empty Changes scopes with
  matching effective arguments and unchanged public evidence. It requires
  successful merge publication and complete, successful empty tool results.
- Existing public change IDs preserve access to configuration diffs; single mode
  is excluded because its tool ACL is wider than task-level permissions.
- Novel scopes, failed/unpublished work, partial results, and existing budget or
  provider failures are not converted to correct abstention. Metric/log loops
  receive clearer history and instructions; this guard is deliberately narrower.

An independent reviewer reproduced and required a fix for an early false
abstention when an unread config diff was available. Final review PASS; 72
independent related tests passed. Coordinator final focused regression: 60 passed.
Ruff and diff whitespace checks passed. These are offline engineering evidence.

The first full suite ran during the final repair: 1004 passed, 3 skipped, 1
protocol-lock failure. Source changed while that experiment test was running;
its durable lock correctly rejected the drift. Keep `pytest.log` and rerun on
the frozen source (`pytest-frozen.log`); do not report the first run as green.

## Frozen real execution

Artifact root: `results/v16/t6-closure/20261016-static-01/`.
`source-freeze.json`, `source.patch`, `review-acceptance.json` and
`frozen-checkout/` bind the reviewed uncommitted patch to HEAD `73282911`.
The snapshot, rather than HEAD alone, identifies the executed version.

`approved-live-plan.json` records authorization. `protocol.json` freezes all
four architectures at temperature 0, json_schema, cache off, jobs 1, one repeat,
48 physical HTTP permits, 32 tools, 8 rounds, 5400 investigation seconds and
420 seconds per request. The request ceiling includes repair/retry dispatches.
No global Token or money cap was requested. Actual unit price/cost is unknown;
incomplete token usage must remain unknown, not zero.

The fourteen investigations imply at most 672 admitted investigation requests
and 21 investigation-hours, excluding the separately counted readiness probe,
setup and evaluation. These are arithmetic ceilings, not runtime predictions.
No automatic new investigation retries or architecture/model substitutions.

Fresh readiness probe: compatible, one request, 195 measured tokens, about 4.1 s;
`readiness.json` retains the complete measured result. No retry was enabled.

Execution order: frozen-source regression; fresh T6; fresh T5 on identical
source; audit normal termination/STOP, provenance and public causal support;
then and only then the twelve pilot investigations. A failure blocks downstream
real experiments and remains in the evidence ledger. Pilot runtime omits the
Oracle root; scoring occurs later in a separate evaluator process. Public and
privileged validations of the selected existing pilot both passed.

The earlier draft and alternate Dev subset remain preserved but unused. They
are preparation artifacts, not authorized executions or new experimental results.

## Live outcomes

Frozen full suite: **1007 passed, 3 skipped**, 280.67 s, exit 0;
`pytest-frozen.log` and `pytest-frozen.exit`. Skips are Windows symlink privileges.
The separately repeated fairness module passed all 20 tests in 72.78 s;
`fairness-final.log`. Source hashes and pilot lock were verified unchanged.

T6 started at the fresh `t6-real/` output. G1a and G4 have not been promoted.
Final outcomes and exact validation logs will be appended after execution.
