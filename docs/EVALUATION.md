# Evaluation

This document reports the IncidentLens evaluation as measured in two saved development
batches. It gives the research questions, corpus composition, matched variants, metric
definitions and denominators, the hardened 144-slot results, the earlier 10-case replication,
difficulty-lever and paired comparisons, failure analysis, auxiliary experiments, and the
threats that limit what can be concluded.

Every number here comes from `docs/submission/source_of_truth.md`, which reconciles the
fact sheet with the saved run artifacts. No number in this document is a forecast, an
extrapolation, or a claim about production performance.

## 1. Research questions

The evaluation asks four descriptive questions:

1. **Quality.** Does dynamic specialist selection produce more correct root causes and
   correct abstentions than a strong single agent or a fixed four-role schedule?
2. **Cost.** What latency, request, tool-query and token cost does each architecture incur?
3. **Verification.** Does an independent verifier improve diagnostic quality enough to justify
   its additional cost?
4. **Failure structure.** Where do the architectures fail: wrong causes, over-abstention,
   technical errors, or difficulty-specific blind spots?

The study does not test a causal mechanism for why dynamic selection helps, and it does not
estimate a population effect. It compares four implemented systems on the same development
corpus under a matched protocol.

## 2. Data and composition

### 2.1 Public incident corpus

`data/incidents/` contains 40 synthetic packs, `incident_001`–`incident_040`: 6 seed, 10 dev
and 20 test, plus 4 additive database packs. Each pack contains `incident.json`,
`logs.jsonl`, `metrics.csv`, `changes.jsonl`, `configs.jsonl`, optional `database.jsonl` and a
shared topology. Five packs omit crucial discriminating evidence. All observations are
synthetic. Public metadata carries raw observations only; answer labels live in separate
evaluator oracles.

### 2.2 Hardened benchmark batch

`data/incidentbench_v2_hardened`, encoder lineage `causal-world-v2-hardened`:

| Property | Value |
| --- | --- |
| Cases | 36, `incident_4001`–`incident_4036` |
| Split | All `dev`; seed 0, test 0 |
| Identifiable / intended abstention | 29 / 7 |
| Scenario families | 10 |
| Challenge tags | ordinary 21, missing 7, counterfactual 6, misleading 2 |
| Per-case lever partition | standard 7, boundary 7, competing 7, missing 7, misleading 2, counterfactual pair 6 |
| Label status | `pending`; accepted labels 0 |
| Blindness | `development_visible` |
| Independence | `unreviewed`; independently audited families 0 |
| Oracle review | `annotator_status: pending`, `review_version: candidate-v1`, `reviewer_ids: []` |

The per-case partition sums to 36 and is the basis for the lever table below. Do not use
`manifest.coverage.difficulty_levers` as case counts: it contains overlapping tags
(boundary 14, competing 15, standard 7) and describes tag occurrences, not distinct cases.

Labels are provisional candidate labels, not accepted human annotations. Scoring against them
is therefore provisional. There is no blind or held-out test set; the blind-test protocol
records that formal sealing is blocked.

### 2.3 Earlier batch

`data/incidentbench_v16_dev` contains 10 cases, `incident_3001`–`incident_3010`: 8
identifiable and 2 intended to abstain, across 2 families. It is also development-visible
with pending labels. It is used as a small replication check, not as independent confirmation.

No production, out-of-distribution, monitoring or user cohort was evaluated. The number of
such cohorts is zero.

## 3. Matched variants

| Public name | CLI value | Design |
| --- | --- | --- |
| Single | `single` | One identity with all investigator tools plus evidence fetch; self-review |
| Fixed-4 | `fixed` | One fixed batch of logs, metrics, database and changes specialists |
| **Dynamic** | `dynamic` | Coordinator selects one or two specialists per round; no independent verifier |
| Dynamic (with verifier) | `full` | Dynamic selection plus an independent Verifier review loop |

The historical benchmark condition name `dynamic_no_verifier` and the runtime alias
`no_verifier` both normalize to `dynamic`. The frozen benchmark protocol names remain
`strong_single_equivalent_tools`, `fixed_four_equivalent_tools`, `dynamic_no_verifier` and
`full`. Per-variant behavior and the CLI flags that select it are documented once in the
[Run Guide §4](RUN_GUIDE.md#4-architecture-variants).

Matches held constant across variants:

- the same public incident data and the same public database access where the protocol grants
  equivalent tools;
- the same model and temperature, cache off, one repeat;
- fresh provider objects and fresh budgets for each slot;
- the same fixed protocol settings within a batch;
- the same scoring version and candidate labels.

The variants differ in orchestration and, for `full`, in the presence of an independent
review. They do not differ in access to private oracles; no runtime variant can read one.

## 4. Metrics and denominators

| Metric | Definition | Denominator |
| --- | --- | --- |
| Technical completion | Slot finished and produced a report | All attempted slots (36 or 10) |
| Root correct | Diagnostic service and failure mechanism both match the candidate label | Identifiable runs that completed |
| Correct abstention | `INCONCLUSIVE` with no asserted root cause on an unidentifiable case | Unidentifiable runs that completed |
| Quality success | Root correct or correct abstention; a technical failure is not a success | All attempted slots |
| Average latency | Mean wall-clock seconds | Completed runs only |
| Average requests | Mean logical LLM requests | Completed runs only |
| Average tools | Mean tool queries | Completed runs only |
| Average tokens | Mean reported tokens | Completed runs only |

Two consequences matter:

1. **Technical failure stays in the quality denominator.** A provider or schema failure is
   not excused from the system's success rate. It is also not counted as a wrong answer; it
   is simply not a success.
2. **Resource averages exclude failed slots.** Failed-slot tokens are excluded from the
   averages but included in the batch total. This makes the averages describe completed
   executions, not the full cost of an attempted portfolio.

Citation existence is checked against the observation ledger. It is not a human judgment of
semantic support. No human semantic-support, unsupported-claim or remediation-effectiveness
metric is available.

## 5. Hardened 144-slot results

Batch `full144-hardened-c4-20261101`, model `auto/deepseek-v4.1-flash`, temperature 0, cache
off, 4 jobs, 1 repeat. 36 cases x 4 architectures = 144 slots. Runtime 16,737.6 s
(4 h 38 m 58 s). **136 completed, 8 technical failures, 0 interrupted.** Technical failures
remain in the quality denominator.

| Architecture | Technical | Root correct | Correct abstention | Quality success | Avg latency | Avg requests | Avg tools | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 35/36 | 25/28 | 7/7 | 32/36 (88.9%) | 680.9 s | 17.3 | 14.5 | 245,971 |
| Fixed-4 | 34/36 | 15/27 | 7/7 | 22/36 (61.1%) | 196.3 s | 7.8 | 7.4 | 58,042 |
| **Dynamic** | 33/36 | **27/27** | **6/6** | **33/36 (91.7%)** | 412.9 s | 14.6 | 12.0 | 149,216 |
| Dynamic (with verifier) | 34/36 | 23/27 | 7/7 | 30/36 (83.3%) | 503.8 s | 17.6 | 15.5 | 233,772 |

Resource averages use completed runs only (n = 35 / 34 / 33 / 34). Failed-slot tokens total
921,599 and are excluded from the averages but included in the batch total of 24,376,395
tokens. Quality among completed runs is Dynamic 33/33, Single 32/35, Dynamic (with verifier)
30/34 and Fixed-4 22/34.

### Descriptive differences

These are arithmetic differences on one repeat. No confidence interval, significance test or
variance estimate is available.

- **Dynamic vs Single:** +1 quality success, 39.4% lower latency, 39.3% fewer tokens.
- **Dynamic vs Dynamic (with verifier):** +3 quality successes, 18.0% lower latency, 36.2%
  fewer tokens. The verifier loop cost 56.7% more tokens with no measured quality gain.
- **Fixed-4:** cheapest per completed run, but wrongly abstained on 12 of 27 identifiable
  cases.

Dynamic is the only variant with 7/7 on competing causes and 6/6 on counterfactual pairs.
That pattern is consistent with the design rationale, but it is a descriptive association,
not evidence that dynamic selection caused the difference.

## 6. Earlier 10-case replication

Batch `full40-local-gateway-c4-20261031`, same model and settings, 40 slots, 40/40 completed,
runtime 739.7 s.

| Architecture | Technical | Root correct | Correct abstention | Quality success | Avg latency | Avg requests | Avg tools | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 10/10 | 8/8 | 2/2 | 10/10 | 391.2 s | 17.6 | 15.0 | 257,146 |
| Fixed-4 | 10/10 | 5/8 | 2/2 | 7/10 | 96.9 s | 7.9 | 7.6 | 56,586 |
| **Dynamic** | 10/10 | 8/8 | 2/2 | **10/10** | 233.5 s | 14.0 | 11.8 | 145,035 |
| Dynamic (with verifier) | 10/10 | 8/8 | 2/2 | 10/10 | 438.9 s | 18.8 | 15.9 | 269,832 |

- Dynamic vs Single: identical quality, 40.3% lower latency, 20.5% fewer requests, 21.3%
  fewer tool queries and 43.6% fewer tokens.
- Dynamic vs verifier: identical quality, while the verifier used 88.0% more latency, 34.3%
  more requests, 34.7% more tools and 86.0% more tokens. The verifier needed 12 attempts;
  all-attempt totals are lower bounds.

This batch is small, shares lineage with the hardened corpus and produced a ceiling effect on
quality for three variants. Its value is consistency of the cost ordering, not independent
confirmation. The saved `correctness` strings in this batch are mojibake; analysis uses only
the numeric fields.

## 7. Difficulty levers and paired comparisons

### 7.1 Quality success by lever

Values are quality successes over cases in that lever partition.

| Lever | n | Single | Fixed-4 | Dynamic | Dynamic (with verifier) |
| --- | ---: | ---: | ---: | ---: | ---: |
| competing | 7 | 6 | 4 | **7** | 6 |
| counterfactual pair | 6 | 5 | 3 | **6** | 4 |
| standard | 7 | 6 | 3 | 6 | 6 |
| boundary | 7 | 6 | 4 | 6 | 5 |
| missing | 7 | 7 | 7 | 6 | 7 |
| misleading | 2 | 2 | 1 | 2 | 2 |

Two observations:

- Fixed-4 loses most on competing and counterfactual cases, where a single scheduled sweep
  appears insufficient to distinguish a confusable rival.
- Dynamic is below ceiling on `standard` (6/7), `boundary` (6/7) and `missing` (6/7). Its
  `missing` miss is consistent with the one unidentifiable Dynamic slot that failed
  technically, leaving 6/6 completed correct abstentions; the other two misses are not
  separately attributed by the saved analysis. No Dynamic miss is a wrong cause.

Do not add these cells to infer a different corpus total; the per-case partition is the
source, and the `n` column sums to 36.

### 7.2 Paired per-case quality

| Comparison | Dynamic better | Dynamic worse | Tie |
| --- | ---: | ---: | ---: |
| Dynamic vs Single | 3 | 2 | 31 |
| Dynamic vs Fixed-4 | 12 | 1 | 23 |
| Dynamic vs Dynamic (with verifier) | 5 | 2 | 29 |

Most cases tie. The dynamic advantage is concentrated in cases where fixed scheduling or the
verifier loop changes the outcome. A paired count of 3/2 against Single is too small and too
dependent on one run to support a general superiority claim.

## 8. Ablations and auxiliary experiments

### 8.1 Verifier ablation

The primary ablation is the `full` variant against `dynamic`. On the hardened batch the
verifier variant had 30/36 quality success versus 33/36, while using 56.7% more tokens and
17.6 versus 14.6 average requests; Dynamic was 18.0% faster. On the 10-case batch,
quality was identical while the verifier used 86.0% more tokens. The consistent finding is
that the current review loop adds substantial cost without a measured quality gain in these
corpora. It is a negative result for this implementation, not a claim that independent review
can never help.

### 8.2 Evidence-gap guard replay estimate

The evidence-gap guard was evaluated by replay estimation, not a new measured run. With
threshold 5 on the frozen 10-case batch, the estimate is 44.0% fewer tokens on case 3003,
21.9% fewer on case 3008 and 12.3% fewer across the batch. The default `max_rounds: 4` means
the guard cannot fire under the stock configuration. The guard changes budget allocation; it
never changes gate acceptance. These are estimates from recorded traces and should be
labelled as such.

### 8.3 Cache experiment

The local explanation cache was measured on Mock, on one case. Warm hit rate was 1.0, four
calls were avoided, and the reports were identical. Tokens and cost were null. There is no
real-provider cache experiment. Cache hits do not replace observed evidence: the current run
must still have observed every cited record.

### 8.4 Recovery experiment

Mock fault injection produced task recovery 1.0 with a denominator of 2 per variant. The one
recorded real-provider retest encountered zero failures, so it did not exercise recovery. No
real-provider recovery rate is established.

### 8.5 Statistical analysis

No real-batch confidence interval or significance test exists. The only statistics artifact
is a Mock hardened validation with `status: insufficient_clusters`, `ci95: null`, `p: null`
and one effective cluster. The protocol names a family-clustered paired bootstrap, but it has
not been run on an accepted, independent batch. Cost in USD is null; tokens are measured, not
monetary cost.

## 9. Failure analysis

### 9.1 No wrong root causes

Across all 144 slots, no completed run named a wrong culprit/failure-mode pair. All 19
identifiable misses that completed ended `INCONCLUSIVE` with no asserted culprit. All 27
completed unidentifiable slots abstained correctly. Dynamic's 6/6 is because one of its seven
unidentifiable slots failed technically; the other architectures were 7/7.

The observed failure mode is **over-abstention, not fabrication**. This is the central
trade-off of deterministic grounding: the system prefers a missed diagnosis to an unsupported
one, and the measured cost of that preference is 19 missed identifiable cases.

### 9.2 Technical failures

There were 8 technical failures in 144 slots:

- 6 `STRUCTURED_OUTPUT_INVALID`;
- 2 `FINDING_IDENTITY_MISMATCH`;
- by architecture: Single 1, Fixed-4 2, Dynamic 3, Dynamic (with verifier) 2.

They were not retried and remain in the denominator. They are best described as a
provider/structured-output layer issue rather than an architecture defect, because they occur
across all four architectures and do not track a single orchestration design. That framing is
an interpretation; the raw counts are the evidence.

### 9.3 Fixed-4 over-abstention

Fixed-4's 22/36 quality success is driven by 12 wrong abstentions on 27 identifiable cases.
It is fast and cheap, but a fixed sweep often fails to resolve a competing or counterfactual
case. Its cost advantage should not be read as efficiency without the quality denominator.

## 10. Threats to validity and non-claims

### Internal validity

- **Provisional labels.** All labels are candidate labels with zero accepted annotations and
  zero independently audited families; the reference answer itself has not been accepted by
  an independent reviewer. The full label-metadata legend is in
  [Limitations §3.1](LIMITATIONS.md#31-provisional-development-visible-labels).
- **Synthetic construction.** Cases are generated from causal templates with shared encoder
  lineage. A high score may reflect learning the template family, not diagnostic reasoning.
- **Scoring scope.** Quality success is a binary per-case count. It does not weight incident
  severity, economic impact, time-to-resolution or the usefulness of a partial explanation.
- **Semantic support untested.** Citation existence and provenance are checked; whether a
  cited record actually supports a sentence is not human-evaluated.
- **Technical failures.** Eight slots failed at the provider/schema layer. They remain in the
  quality denominator, but resource averages exclude them, which can make average efficiency
  look better than the full attempted cost.
- **One run per slot.** Temperature 0 reduces but does not eliminate nondeterminism in a
  served model. No repeat-variance estimate exists.

### External validity

- One model, `auto/deepseek-v4.1-flash`, one provider configuration, one synthetic benchmark
  lineage.
- No blind or held-out test, no production telemetry, no out-of-distribution cohort, no human
  on-call users.
- No evidence that results transfer to other models, other incident distributions or real
  observability data.
- No remediation execution or effectiveness measurement; remediation is plan-only.

### Statistical validity

- No confidence interval, significance test, variance estimate or model-sensitivity analysis.
- Paired counts are descriptive. A 3/2 or 12/1 split on a single run is not a population
  effect.
- The family-clustered bootstrap is specified but not available on a real accepted batch; the
  only statistics artifact is Mock and reports insufficient clusters.

### Construct validity

- "Quality success" combines root correctness and correct abstention with equal weight per
  case. A system that abstains more can look better on unidentifiable cases and worse on
  identifiable ones depending on the mix.
- Root correctness requires a diagnostic service and mechanism match. It does not grade the
  quality of the causal chain or the operational usefulness of the recommendation.
- Token averages are reported by the provider; null usage is not imputed.
- USD cost is unavailable, so resource comparisons use tokens, requests and latency as
  proxies.

### Auxiliary-experiment limits

- The cache result is Mock-only, one case, with null token and cost figures.
- The recovery result is a Mock injection with denominator 2 per variant; the real retest had
  no failure to recover.
- The evidence-gap guard result is replay-estimated and cannot fire under the default round
  cap.
- The 10-case batch has a quality ceiling for three variants and mojibake `correctness`
  strings; only numeric fields are used.

### Explicit non-claims

This evaluation does **not** establish:

- that Dynamic is generally superior to Single or to a fixed schedule;
- that multi-agent design is better than a single agent outside this corpus;
- that the verifier is useless in all settings;
- that the system is production-ready, safe for autonomous operation or validated by users;
- that citations are semantically sufficient;
- that remediation is effective;
- that labels are accepted ground truth;
- that results generalize to a blind test, another model or real incidents;
- any dollar cost or return on investment.

## 11. Evidence and reproduction

The primary recorded source for the hardened batch is
`results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json`; the tracked
interpretation and recomputation script are in
`analysis/wp_d/reports/hardened144-20261101/`. The earlier batch source is
`results/v16/wp-d/full40-local-gateway-c4-20261031/final-success-comparison.json`. The
`results/v16/` tree is a local run artifact and may not be present in a fresh clone; the
tracked report is the durable record.

IncidentBench runners also emit `protocol.json`, `protocol.lock.json`, `raw-runs.jsonl`,
`scores.jsonl`, `case-level.csv`, `aggregate.json`, `aggregate.csv`,
`failure-categories.json`, `statistical-analysis.json`, `paired-differences.csv`,
`family-summary.csv`, `citation-review-bundle.jsonl` and `artifact-digests.json`. These are
the audit surface for a rerun. See [IncidentBench](incidentbench/README.md) for the
reproduction workflow and [Run Guide](RUN_GUIDE.md#11-incidentbench-reproduction) for
commands.

The hardened batch used non-default round, tool, logical-request and timeout budgets.
Reproducing the recorded numbers requires the recorded settings and the same provider/model.
A different run is a new result, not a reproduction.
