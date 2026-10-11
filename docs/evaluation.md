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

All four variants execute the common investigation graph. `single` uses one broad
runtime identity with planning and self-reflection; `fixed` assigns the same three
investigators once; `dynamic_no_verifier` keeps dynamic routing and deterministic
grounding but omits independent review; `full` retains routing and review.
The evaluator creates a fresh provider and budget for every run. It enforces equal
model ID, temperature, budget and public dataset revision across variants and records
the initial public input hash. A change to public data during execution stops the
experiment. Private oracles enter scoring only after the graph has returned.

Caching is explicitly disabled with `cache=None`, regardless of `CACHE_MODE` or
historical cache files. Cold/warm cache performance is a separate experiment.
Defaults are 4 rounds, 12 tools, 16 model requests and 90 seconds per run, temperature
0. CLI options override these bounds and optionally set `--max-tokens`.
Equal upper bounds do not imply equal actual computation; inspect measured usage.
Seed/dev support smoke checks and development. Do not tune prompts using hidden test
results. Mock policy results are offline correctness checks, not model performance.

## Artifacts and metric definitions

- `case-level.csv`: predictions, status, separate scoring fields, measured usage,
  configuration and initial public hashes, errors and stop reason.
- `aggregate.csv`: per-variant numerators and denominators, rates and usage totals.
- `raw-runs.jsonl`: full completed states, external decisions, actual tool results,
  per-call usage, frozen settings and evaluator scoring fields. Recompute using
  `score_completed(record['state'], record['oracle_scoring_fields'])`.
- `error-analysis.md`: denominator summary and cases requiring review.

Root Cause Accuracy requires both culprit service and failure mode to match, only
among identifiable cases. Correct Abstention requires INCONCLUSIVE with no root
cause, only among unidentifiable cases. Misleading Accuracy uses identifiable cases
with oracle-labelled misleading evidence. Execution failures remain incorrect in
their applicable denominator when the oracle is available; unreadable oracles are
explicit evaluation errors and cannot be scored.

Citation Existence Validity counts unique report citations present in the current
incident's shared evidence index and in actual tool-result records from that run.
No citations means an undefined rate. It does not measure semantic support. That
requires manual annotation; unsupported claim rate stays blank and review status
stays `unreviewed` until that work exists.

Model requests include provider repair attempts via the runtime request guard.
Tool calls come from the runtime registry. Failed model calls count structured-call
invocations that raised, and failed tool calls count explicit unsuccessful tool
results; internal repaired attempts are included in request counts but their separate
failure count is unavailable from the provider contract. Latency uses a monotonic
clock around actual graph execution. Unknown tokens and cost are `None` in JSON and
blank in CSV, including mock tokens; no tariff is inferred. Aggregate usage is blank
if any constituent value is unknown. Cost remains unavailable without measured
provider billing. Small synthetic samples cannot establish statistical significance.

## Validation boundary

`python -m pytest tests/evaluation -q` exercises all four actual seed variants,
oracle-after-run ordering, cache bypass, fairness, recomputable metrics, missing
usage, provider failures and missing real configuration. No real-provider accuracy
or cost claim is justified until configured requests are executed and inspected.
