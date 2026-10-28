# Best-supported root selection: Dev10 validation

On 2026-10-28 the frozen current code ran all synthetic development incidents 3001–3010 with four variants once each. Requests used gpt-5.6-luna / low through the official Codex subscription CLI, four concurrent slots, 8 rounds, 64 model calls, 40 tool calls and 7200 seconds per run. No failed run was replaced or earlier best result spliced into this batch.

| Variant | Correct decisions | Identifiable roots | Correct abstentions | Mean seconds | Model calls | Tool calls | Token lower bound |
|---|---:|---:|---:|---:|---:|---:|---:|
| Single | 10/10 | 8/8 | 2/2 | 122.7 | 152 | 102 | 1,275,909 |
| Fixed | 7/10 | 5/8 | 2/2 | 26.7 | 76 | 73 | 380,291 |
| Dynamic without verifier | 10/10 | 8/8 | 2/2 | 93.9 | 141 | 104 | 954,862 |
| Full | 10/10 | 8/8 | 2/2 | 100.5 | 153 | 113 | 1,123,906 |

All 40 runs completed normally. Incidents 3003 and 3008 correctly remained inconclusive in every variant. Fixed abstained on identifiable incidents 3005, 3006 and 3007. The complete batch took 897.6 seconds, 522 model calls, 392 tool calls, three correction requests and 3,734,968 observed tokens as a lower bound. Complete underlying HTTP usage and subscription charges are unknown.

`RESOLVED` now means selecting the most reasonable cause supported by available observations; it does not assert direct proof of every causal link. Residual causal limits are retained. Consequently improved acceptance versus the old strict policy is not proof of improved reasoning or additional evidence. Full tied Single and no-verifier accuracy here; these results do not establish a multi-agent advantage.

All selected labels were evaluated only after every run terminated and 240 raw artifacts were hash-locked. Labels are provisional and these cases were already known to the developer, so this is development evidence rather than a blind held-out evaluation. No Test label contents were read. Raw calls, local paths, model catalogs and oracle contents remain local; the adjacent JSON records portable per-run metrics, protocol and original artifact hashes.

Local full artifacts: `results/timing/dev3001-3010-20261028-best-supported-01/`. This directory is intentionally ignored and is not required to run offline tests. No live model calls are performed by CI.


Publication regression follow-up: before opening the PR, offline regressions exposed two additional compatibility gaps. The deterministic Mock planner now consults the observed dependency and completed query scopes rather than repeating an empty source. Mechanism checks recognize explicit service-owned capacity/availability failure logs and compare corroborating source pairs correctly when more than one source describes a mechanism. These changes were verified offline, after the frozen live batch above; no new live calls were made and none of its results were rewritten. The original batch manifest hash in the adjacent JSON identifies the exact evaluated snapshot.
