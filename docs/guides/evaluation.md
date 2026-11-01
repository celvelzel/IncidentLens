# Evaluation

Run from the repository root with the installed Python environment:

```powershell
python scripts/run_eval.py --split seed --variant all --provider mock --out results/eval-seed
python scripts/run_eval.py --split dev --variant all --provider mock --out results/eval-dev
python scripts/run_eval.py --split test --variant all --provider real --out results/eval-test
```

The real command requires `INCIDENT_LENS_BASE_URL`, `INCIDENT_LENS_API_KEY`, and
`INCIDENT_LENS_MODEL` from the environment or `.env`. Missing configuration fails
explicitly before execution; there is no mock fallback. Credentials are never
included in evaluation artifacts. Choose a fresh output directory for each experiment;
running again replaces the previous experiment artifacts.

## Comparisons and frozen settings

All four variants execute the common investigation graph. `dynamic` is the primary
architecture and the runtime default: dynamic routing with deterministic grounding and
no independent review. `full` is its ablation control — displayed as *dynamic (with
verifier)* — and retains the Verifier review. `single` uses one broad runtime identity
with planning and self-reflection, and `fixed` assigns the same three investigators once.

The name `dynamic_no_verifier` appears in saved WP-D protocols, traces and result rows.
It is a frozen historical alias of `dynamic`: the runtime resolves it on input and never
writes it for a new run. IncidentBench condition names (`strong_single_equivalent_tools`,
`fixed_four_equivalent_tools`, `dynamic_no_verifier`, `full`) are also frozen, because
saved `protocol.json` files must keep validating.

The evaluator creates a fresh provider and budget for every run. It enforces equal
model ID, temperature, budget and public dataset revision across variants and records
the initial public input hash. A change to public data during execution stops the
experiment. Private oracles enter scoring only after the graph has returned.

Caching is explicitly disabled with `cache=None`, regardless of `CACHE_MODE` or
historical cache files. Cold/warm cache performance is a separate experiment.
Defaults are 4 rounds, 12 tools, 16 model requests and 90 seconds per run, temperature
0. CLI options override these bounds and optionally set `--max-tokens`.
`--jobs` defaults to 1 and accepts integers 1 through 4. It bounds concurrently
executing runs with an asyncio semaphore; each case/variant has its own provider,
budget and public data reader. Jobs is recorded in raw fairness settings and CSV.
Concurrency can affect wall-clock latency and provider rate limits; compare accuracy
and usage with identical jobs settings for real experiments.
Equal upper bounds do not imply equal actual computation; inspect measured usage.
Seed/dev support smoke checks and development. Do not tune prompts using hidden test
results. Mock policy results are offline correctness checks, not model performance.

## Evidence-gap cost guard

`WorkflowOptions.evidence_gap_rounds` (default 5, `0` disables) stops an investigation
that has made no discriminative progress. Each round the run asks whether *any*
candidate gained a `cause_discriminator`; if none did, a streak counter increments,
and any decisive observation resets it. At the threshold the run writes
`stop_reason="INCONCLUSIVE"`, emits `INVESTIGATION_EVIDENCE_EXHAUSTED` with a cost
snapshot, and routes to `report`. It is a budget decision only: `FinalizeGate`,
`grounding_errors` and `BEST_SUPPORTED_AVAILABLE` are untouched, so it cannot convert
a resolvable case into a scored abstention. The `fixed` variant does not arm it.

The default is measured, not chosen by feel. Replaying the same predicate over the
frozen WP-D traces gives a largest non-unidentifiable streak of 3 for `single`,
`dynamic` and `full`; the mock suite at an uncapped round budget peaks at 4. A threshold
of 4 is therefore the first false-positive-free value and 5 keeps one round of margin.
Note that the default `configs/system.yaml` sets `max_rounds: 4`, so the guard cannot
reach 5 under that configuration — the round cap fires first. Raising `max_rounds` or
lowering `evidence_gap_rounds` changes which mechanism ends the run, and lowering it
reintroduces the false positive seen at 3 (`incident_3005`).

Replay estimates for `dynamic` at threshold 5: `incident_3003` 268,375 → 150,355
tokens (−44.0%), `incident_3008` 274,794 → 214,669 (−21.9%), batch −12.3%. These are
replays over the frozen 10-case batch, not a new measured run, and the batch contains
no case whose decisive evidence arrives late.

## Artifacts and metric definitions

- `case-level.csv`: predictions, status, separate scoring fields, measured usage,
  configuration and initial public hashes, errors and stop reason.
- `aggregate.csv`: per-variant numerators and denominators, rates and usage totals.
- `raw-runs.jsonl`: full completed states, external decisions, actual tool results,
  per-call usage, frozen settings and evaluator scoring fields. Both raw JSONL and
  case-level CSV are saved after every completed run, including on partial failure.
  Successful final artifacts are sorted by incident ID and variant; interrupted
  raw JSONL retains completion order. Recompute using
  `score_completed(record['state'], record['oracle_scoring_fields'])`.
- `error-analysis.md`: denominator summary and cases requiring review.

Root Cause Accuracy requires both culprit service and failure mode to match, only
among identifiable cases. Correct Abstention requires INCONCLUSIVE with no root
cause, only among unidentifiable cases. Misleading Accuracy uses identifiable cases
with oracle-labelled misleading evidence. Execution failures remain incorrect in
their applicable denominator when the oracle is available; unreadable oracles are
explicit evaluation errors and cannot be scored.

Scoring version `2` reads the complete trace through one termination classifier.
New runs emit `WORKFLOW_STOP_REQUESTED`, actual `STOP_ACK` events, then exactly one
`NORMAL_TERMINATION` or terminal `RUNTIME_FAILURE`. State and report carry the same
strict `termination` result (protocol version `2`). Normal termination describes
orderly shutdown, including a business failure such as `PLAN_FAILED`.

`MODEL_FAILURE` is a failed call, not an automatic run failure. Explicit recovery
links failed call IDs to the completed task attempt; accepted diagnoses can also
record failed specialist calls safely bypassed by sufficient peer evidence. All
failed calls, requests and measured tokens remain in cost/accounting statistics.
A matching `DIAGNOSIS_ACCEPTED` checkpoint is required for new resolved traces.

`root_cause_correct` credits accepted matching diagnoses without an unrecovered
fatal diagnosis-stage error. `diagnosis_match` reports raw matching independently.
`remediation_success` is applicable only when a plan was attempted; `PLAN_FAILED`
keeps diagnosis credit but fails remediation and `workflow_success`. Shutdown
failure after accepted diagnosis likewise keeps diagnosis credit but fails
`stop_completion` and workflow success. Budgets and unrecoverable errors are
runtime failures, never evidence-based abstentions.

`NO_ALERT` is excluded from RCA and correct-abstention denominators. Monitoring
requires an explicit evaluator-only `monitoring_expected_alert` (ALERT/NO_ALERT);
without it monitoring accuracy and no-alert workflow success remain unknown.
Normal `INCONCLUSIVE` succeeds only for an unidentifiable oracle. Unreadable
oracles are evaluation errors with unknown answer quality; known execution failures
remain recorded. Each layered aggregate exports successes, failures, applicable
denominator, unknown count and rate. Mixed scoring versions are rejected.

Historical non-structured STOP and unexplained MODEL_FAILURE remain conservative
failures. Structured historical STOP accepts only known reasons and consistent
reports. Unknown/missing/conflicting terminal data cannot earn shutdown, workflow
or abstention credit. Raw events are never removed or rewritten. Recompute into a
new directory using `scripts/rescore_eval.py --input <raw-runs.jsonl-or-trace.json>
--out <new-directory>`; outputs record scoring version and input SHA-256. Saved
oracle fields are preferred; dataset truth is read only after a completed report
exists. Original score rows are retained as `historical_metrics`.

Citation Existence Validity counts unique report citations present in the current
incident's shared evidence index and in actual tool-result records from that run.
No citations means an undefined rate. It does not measure semantic support. That
requires manual annotation; unsupported claim rate stays blank and review status
stays `unreviewed` until that work exists.

Model requests include provider repair attempts via the runtime request guard.
Tool calls come from the runtime registry. `provider_failures` counts structured-call
invocations that raised. `failed_model_calls` is the maximum of provider failures
and runtime `MODEL_FAILURE` events, so schema and role validation failures are
counted without counting the same provider exception twice. `failed_calls` adds
explicit unsuccessful tool results to failed model calls. Internal repaired attempts
are included in request counts but their separate failure count is unavailable from the provider contract. Latency uses a monotonic
clock around actual graph execution. Unknown tokens and cost are `None` in JSON and
blank in CSV, including mock tokens; no tariff is inferred. Aggregate usage is blank
if any constituent value is unknown. Cost remains unavailable without measured
provider billing. Small synthetic samples cannot establish statistical significance.

## Validation boundary

`python -m pytest tests/evaluation -q` exercises all four actual seed variants,
oracle-after-run ordering, cache bypass, fairness, recomputable metrics, missing
usage, provider failures and missing real configuration. No real-provider accuracy
or cost claim is justified until configured requests are executed and inspected.
