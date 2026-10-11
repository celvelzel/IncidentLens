# Live-provider continuation and interruption audit

The resumed task retained all P0–P7 commits, dirty implementation patches,
isolated worktrees, saved failed live attempts and the user's local `.env`.
No global Codex model configuration was changed and no remote push was made.
The first interruption ended tool sessions; completion was verified from retained
artifacts rather than assumed from missing processes.

## Corrections before the held-out run

- `00d8c93`: bounded evaluation concurrency, independent provider and budgets,
  cache off, oracle access after completion, per-completion durable artifacts.
- `5928131`: runtime STOP traces receive no root/abstention credit, remain in
  applicable denominators and are counted separately from outer execution errors.
- `dbc54c5`: saved-trace coordination counts, mechanism/misleading/identifiability
  slices and evidence excerpts for human semantic review.
- `0d24227`: publish every authorized hypothesis citation atomically; reconcile
  current-batch assessments independent of worker order; preserve conflicting
  support/refutation as OPEN; reject reused finding/cause IDs. Mock stops repeated
  discriminating checks with explicit evidence-based abstention. Record prompt,
  schema and source hashes. Expose explicit transport settings in CLI and UI.
- `198f12c`: Verifier exceptions emit STOP with a safe stage/type; legacy
  MODEL_FAILURE events also prevent incorrect abstention credit.

Same-concept identity uses exact `(culprit_service, failure_mode)` within the five
MVP mechanisms. It is not general semantic clustering. Historical counterevidence
is retained; a later SUPPORTED assessment cannot silently erase old contradictions.
This conservative behavior can leave a case unresolved.

## Retained diagnostics

`results/real-compatibility-001` through `007` are actual configured requests,
not accuracy samples or transport fixtures. The seventh completed report was
INCONCLUSIVE after 8 tools and 13 requests, with PROVIDER_TIMEOUT.

`results/real-dev-v6` contains 40 real dev runs with a 180-second wall limit.
All were INCONCLUSIVE (0/9 identifiable correct roots per variant); 13 ended with
ValidationError. Independent reproductions proved a publication defect, but the
failed local analysis outputs were not retained, so those 13 failures cannot all
be individually attributed to it. Original CSVs retain their historical scoring;
`results/acceptance/live-diagnostic-final-scoring` recomputes failure-event-aware slices.
It confirms 36 runtime failures and zero correct abstentions. One old
`incident_007/full TIMEOUT` lacks both failure event types, so historical runtime
failure counts are incomplete; the current Verifier boundary emits STOP.
`results/real-dev-v6-final` is a second diagnostic dev run after publication repair,
at the default 90-second budget, started before final batch-status reconciliation.
Its folder name does not make it the final acceptance experiment.

## Frozen final experiment settings

Implementation snapshot: `198f12c`, prompt `roles-v6`, schema `schema-v1`.
All four variants use the configured `deepseek-v4-flash-0731` model, temperature 0,
explicit JSON-object transport, thinking disabled, 60-second request timeout,
at most one structured repair, 4 rounds, 12 tools, 16 requests and 90 seconds.
Architecture caches are off. `jobs=4` is recorded for every run; shared-endpoint
contention affects latency, so this is not isolated single-request latency evidence.
Unknown usage and billing remain null, with actual request counts retained.

```powershell
python scripts/run_eval.py --split dev --variant all --provider real --jobs 4 --response-format json_object --thinking disabled --request-timeout 60 --out results/acceptance/p5-real-dev
python scripts/run_eval.py --split test --variant all --provider real --jobs 4 --response-format json_object --thinking disabled --request-timeout 60 --out results/acceptance/p5-real-test
```

The held-out run must follow this freeze. Its labels are available only to the
evaluator after each completed investigation; no prompt or implementation tuning
may use its results. Final artifact completion and measured results are recorded
below after execution, not inferred from these commands.

## Explicit review boundaries

Citation existence is automatically checked; semantic support and Unsupported
Claim Rate require human annotation. The exported review bundle remains
`awaiting_human`. Student names and actual contribution ownership, slides, video,
Canvas submission and a learned-embedding experiment are not established by code
generation or synthetic Mock tests.

Final frozen code checks: 214 passed, one Windows symlink-privilege skip;
Ruff lint/format and pip check pass. Independent QA accepted current implementation
after 55 focused tests and in-memory failure reproductions. The skipped symlink
test is supplemented by an actual passing Windows junction denial test.
