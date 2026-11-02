# Hardened 36-case × 4-architecture comparison (2026-11-01)

Full-size development batch over the `causal-world-v2-hardened` encoder lineage
(36 Dev cases: 29 identifiable, 7 abstaining), four architectures, four jobs,
one repeat, 144 slots. Batch `full144-hardened-c4-20261101` ran on
`auto/deepseek-v4.1-flash` through the local gateway in 4 h 39 min
(136 completed, 8 technical failures, 0 interrupted).

Chinese report: [report.zh-CN.md](report.zh-CN.md).

## Result

Denominators follow the IncidentBench contract: technical completion over all 36
slots; root-cause correctness only on identifiable cases that completed;
correct abstention only on unidentifiable cases that completed; quality success
over 36, so a technical failure is never counted as a success.

| Architecture | Technical | Root cause | Abstention | Quality | Latency | Requests | Tools | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 35/36 | 25/28 | 7/7 | 32/36 | 680.9 s | 17.3 | 14.5 | 245,971 |
| Fixed-4 | 34/36 | 15/27 | 7/7 | 22/36 | 196.3 s | 7.8 | 7.4 | 58,042 |
| **Dynamic (primary)** | 33/36 | **27/27** | 6/6 | **33/36** | 412.9 s | 14.6 | 12.0 | 149,216 |
| Full (dynamic with verifier) | 34/36 | 23/27 | 7/7 | 30/36 | 503.8 s | 17.6 | 15.5 | 233,772 |

Quality among technically completed runs: Dynamic 33/33, Single 32/35,
Full 30/34, Fixed 22/34.

## What the numbers support

- **No wrong root causes anywhere.** All 19 identifiable misses ended in
  `INCONCLUSIVE`; no run named a wrong `culprit_service`/`failure_mode`, and all
  seven unidentifiable cases were correctly abstained in every completed run.
  The observed failure mode is over-abstention, not fabrication.
- **`dynamic` is the strongest and the cheapest of the dynamic family.** Against
  `single`: +1 quality, −39.4% latency, −39.3% tokens. Against `full`: +3 quality,
  −18.0% latency, −36.2% tokens. The Verifier loop produced no measurable quality
  gain on this hardened set and cost 56.7% more tokens than `dynamic`.
- **`fixed` is cheapest and pays in recall**: 58k tokens and 196 s per run, but it
  wrongly abstained on 12 of 27 identifiable cases.
- **Difficulty levers separate the architectures.** `dynamic` is the only variant
  at 7/7 on competing causes and 6/6 on counterfactual pairs; `fixed` drops to
  3/7 on standard and 3/6 on pairs.

Paired per-case results (dynamic right / other right / tie): vs single 3/2/31,
vs fixed 12/1/23, vs full 5/2/29.

## Technical failures (8/144)

Six `STRUCTURED_OUTPUT_INVALID` (five provider responses carrying no string content,
one truncated output that stayed invalid after its one repair) and two
`FINDING_IDENTITY_MISMATCH`, spread over all four variants (single 1, fixed 2, dynamic 3,
full 2) — a provider/structured-output
layer issue rather than an architecture defect. Per the batch plan they were not
retried and remain in the denominator; they account for 0.92 M of the 24.4 M tokens
spent.

## Evidence boundary

- Not a blind test: the protocol is `formal: false`, `blindness_level: development_visible`.
- Oracle labels are provisional (`annotator_status: pending`).
- One repeat, one model, 36 cases: every difference above is descriptive; no
  significance claim is made.
- Source inputs were frozen for the whole batch (144/144 slots `source_unchanged: true`);
  that check covers repository inputs, not gateway-side routing.
- Quality is failure-inclusive over 36; conditional accuracy among completed runs
  is reported separately so the two are never conflated.

## Reproduce

```bash
.venv/Scripts/python.exe analysis/wp_d/reports/hardened144-20261101/score_batch.py
```

The script is read-only over `results/v16/wp-d/full144-hardened-c4-20261101` and rewrites
`final-success-comparison.json` there from the per-slot `trace.json`,
`verification.json` and the evaluator oracle.
