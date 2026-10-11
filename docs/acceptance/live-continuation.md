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

Final implementation and analysis checks: 217 passed, one Windows symlink-privilege skip;
Ruff lint/format and pip check pass. Independent QA accepted current implementation
after 55 focused tests and in-memory failure reproductions. The skipped symlink
test is supplemented by an actual passing Windows junction denial test.

## Completed formal dev evidence

All 40 runs completed; independent QA revalidated every state, score, CSV,
aggregate and measured usage field. Four variants have identical initial public
input and stored scoring oracle per case, one frozen configuration, no cache
events, and source digest `37d91b6bb3bd4a2c4f7c3304a05ce096a26b4888c07a1ed3acef007a0f50ce83`.
There were no outer execution/evaluation errors; runtime failures are separate.

| Variant | Correct roots | Correct abstention | Runtime failures |
| --- | --- | --- | --- |
| single | 0/9 | 0/1 | 10/10 |
| fixed | 0/9 | 1/1 | 2/10 |
| dynamic_no_verifier | 0/9 | 0/1 | 10/10 |
| full | 0/9 | 0/1 | 10/10 |

These measured results do not demonstrate usable root-cause accuracy or system
superiority. Causes recorded include 18 Provider timeouts, five ID collisions,
four invalid structured outputs, four request/wall-budget terminations, one
unobserved citation and eight normal fixed-schedule abstentions.

`results/acceptance/p5-real-dev-analysis` contains 40 coordination rows, 24 slices,
32 error records, nine Review examples with seven exact follow-up request matches,
and 40 human-review bundles. Matching requests describes recorded behavior; it
does not prove a causal improvement from the Verifier. Ordinary coverage is zero.
Token/billing totals remain unknown where requests have incomplete usage.

## Completed held-out execution

All 80 runs are saved with the same frozen source and parameters. Each variant
has 0/18 correct roots, 0/2 correct abstentions and 20/20 runtime failures;
outer execution/evaluation errors are zero. There were 144 actual request
attempts, with 42,044 known measured tokens. Full token and billing totals remain
unknown. Independent final artifact audit is recorded in P7.md.

Failure events include 95 PROVIDER_HTTP_ERROR, 27 PROVIDER_TIMEOUT and one
STRUCTURED_OUTPUT_INVALID. Concurrent/cancelled calls mean these event counts
are not a per-run or per-request failure-rate denominator. Execution failures
prevent conclusions about intrinsic model reasoning accuracy. No test labels
were used to change prompts or implementation after the freeze.

Analysis covers 80 coordination rows and 80 pending human review bundles;
ordinary coverage remains zero, misleading 80, identifiable 72, missing 8.

## Post-benchmark availability probes

Three separate bounded requests used benign input or public seed incident_001,
never held-out input. Their JSON files are retained under results/acceptance:
provider-availability.json, provider-full-request-diagnostic.json and
provider-capped-request-diagnostic.json. A tiny request capped at 64 output tokens
returned HTTP 200; the full Coordinator request without an output cap returned
HTTP 429; a full request capped at 2048 returned HTTP 200 but failed schema
validation (2,598 measured tokens). Different request times prevent a causal
claim about the cap. Historical HTTP error events did not record status codes,
so the later 429 cannot establish their individual statuses. These probes are
excluded from the four-variant evaluation. No automatic fallback or credential
rewrite was introduced, and the frozen negative results are retained.

## Post-experiment accounting correction

Independent final QA found two raw per-call request overcounts in held-out
incident_021/fixed and incident_026/fixed. Each run's budget guard and aggregate
correctly report three actual requests, but cancelled sibling-call fallback usage
sums to six because it subtracted a shared counter. Historical records remain
unchanged: do not sum their per-call llm_calls as an actual request total.
Evaluator-only correction `1b0a0e1` uses task-local ContextVar counting to fix the fallback and has a concurrent
cancellation/repair regression. This evaluator-only change follows the frozen
experiments; their recorded source digest and negative scores are retained.
It does not alter investigation decisions, prompts or held-out inputs.
