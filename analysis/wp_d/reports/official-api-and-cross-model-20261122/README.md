# Official API Fix Validation & Cross-Model Comparison (2026-11-22)

This report documents three follow-up engineering and evaluation updates built on top of the project main branch:

1. **Structured-output diagnostic fix (`39621e5`)**: Whitelisted schema-owned custom validator codes (`leading_review_consistency`, `tool_arguments`, `task_tool_acl`) in `src/incident_lens/llm/structured_output.py`, added static non-leaking repair hints, and stated `ReviewOutput` mutual-exclusion invariants explicitly in `service.verify()` and `prompts/verifier.md`.
2. **Official DeepSeek API full hardened batch (144 slots)**: Executed all 36 `causal-world-v2-hardened` cases × 4 architectures directly against `https://api.deepseek.com/v1` (`deepseek-flash`, `json_object`, `thinking: disabled`, `cache: off`).
3. **Cross-model integration & thinking ablation (OhMyGPT / `tencent/hy4-flash`)**: Integrated OhMyGPT via the official `openai` Python SDK (`--provider ohmygpt`) and evaluated a 6-case representative hardened subset (covering all 6 difficulty levers × 4 architectures = 24 slots) with thinking enabled vs. disabled.

Chinese full report: [report.zh-CN.md](report.zh-CN.md).

## 1. Structured-output fix ablation (Official DeepSeek API)

Running unmodified code directly against the official DeepSeek API (`json_object`) exposed a latent failure mode: `ReviewOutput.leading_review_consistency` was folded into generic `$: validation_error`, causing bounded 1-shot repair to repeat the same violation.

| Stage | Scope | Verify schema crashes | Technical completion | Quality success |
| --- | --- | ---: | ---: | ---: |
| Before fix (`deepseek-chat`) | 6 cases × 4 variants (24 slots) | **8 / 12** (`single` 4/6, `full` 4/6) | 15 / 24 | 10 / 24 |
| After fix retest (`deepseek-chat`) | All 9 previously failed slots | **0 / 8** (7 first-try, 1 repaired) | **9 / 9** | **9 / 9** |
| After fix full (`deepseek-flash`) | Full 36 cases × 4 variants (144 slots) | **0 / 144** (`STRUCTURED_OUTPUT_INVALID = 0`) | **137 / 144 (95.1%)** | — |

## 2. Official DeepSeek API (`deepseek-flash`) — Hardened Dev36 (144 slots)

| Architecture | Technical | Root cause | Abstention | **Quality (of 36)** | False res | False abs | Avg latency | Avg req | Avg tools | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 33/36 | 21/26 | 7/7 | 28/36 (77.8%) | 0 | 5 | 76.5 s | 17.5 | 13.6 | 197,986 |
| Fixed-4 | **36/36** | 6/29 | 7/7 | 13/36 (36.1%) | 0 | 23 | 17.3 s | 7.4 | 7.2 | 36,478 |
| **Dynamic (primary)** | **35/36** | **24/28** | **7/7** | **31/36 (86.1%)** | **0** | **4** | **56.4 s** | **14.8** | **11.1** | **113,645** |
| Full (dynamic + verifier) | 33/36 | 21/27 | 6/6 | 27/36 (75.0%) | 0 | 6 | 67.0 s | 18.5 | 14.6 | 187,781 |

- **Paired per-case quality (`dynamic` vs others)**: vs `single` **+6 / −3 / 27 tie** (−42.6% tokens, −26.3% latency); vs `full` **+6 / −2 / 28 tie** (−39.5% tokens, −15.8% latency); vs `fixed` **+18 / −0 / 18 tie**.
- **Zero false resolutions** across all 137 completed slots. The 7 technical failures were 4 `FINDING_IDENTITY_MISMATCH`, 2 `PROVIDER_TRANSPORT_ERROR`, and 1 `Evidence sufficient@UNRECOVERABLE_ERROR` (0 `STRUCTURED_OUTPUT_INVALID`).
- **Counterfactual lever nuance**: `full` scored **5/6** on `counterfactual_pair` vs `dynamic` 4/6 and `single` 3/6.

## 3. Cross-model & thinking ablation (OhMyGPT / `tencent/hy4-flash`, 24 slots)

Six representative hardened cases spanning all six levers (`incident_4001`, `4007`, `4012`, `4014`, `4018`, `4035`) × 4 variants under `json_schema`:

| Mode | Wall time | Technical completion | 900s timeouts | Quality success | False res |
| --- | ---: | ---: | ---: | ---: | ---: |
| `hy4-flash` thinking ON (default) | 48.0 min | 11 / 24 (45.8%) | 6 (`single` 3, `full` 3) | 7 / 24 (29.2%) | 0 |
| **`hy4-flash` thinking OFF** | **12.6 min (3.8× faster)** | **23 / 24 (95.8%)** | **0** | **13 / 24 (54.2%)** | **0** |

Per-variant breakdown for `hy4-flash` (`thinking: disabled`):

| Architecture | Technical | Root cause | Abstention | **Quality (of 6)** | Avg latency | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 6/6 | 0/5 | 1/1 | 1/6 (16.7%) | 173.8 s | 254,026 |
| Fixed-4 | 6/6 | 2/5 | 1/1 | 3/6 (50.0%) | 28.4 s | 39,809 |
| **Dynamic (primary)** | **6/6** | **4/5** | **1/1** | **5/6 (83.3%)** | **85.6 s** | **123,861** |
| Full (dynamic + verifier) | 5/6 | 3/4 | 1/1 | 4/6 (66.7%) | 146.0 s | 264,436 |

Key cross-model takeaways:
- **Capability amplification on lighter non-thinking models**: While monolithic `single` collapsed to `0/5` on identifiable cases (254k tokens/run), `dynamic` lifted quality from `16.7%` to `83.3%` while cutting both tokens (−51.2%) and latency (−50.7%) in half.
- **Consistent counterfactual signal**: Across both `deepseek-flash` and `hy4-flash` (thinking OFF), `incident_4035` (`counterfactual_pair`) was missed by `dynamic` and rescued by `full`, motivating future on-demand Verifier triggering.

## 4. Evidence boundary

- All runs use development-visible `causal-world-v2-hardened` fixtures (`formal: false`, `blindness_level: development_visible`), provisional candidate labels (`annotator_status: pending`), and one repeat (`repeats = 1`). No significance claim or production accuracy guarantee is made.
- The official `deepseek-flash` 144-slot batch paused after 42 valid slots (41 completed + 1 `FINDING_IDENTITY_MISMATCH`) due to account balance exhaustion (HTTP 402) and resumed the remaining 102 slots under the same fixed code and protocol after top-up.
- The `tencent/hy4-flash` runs cover a 6-case representative subset (24 slots per mode, 48 slots total) rather than all 36 cases, and OhMyGPT selects the upstream provider per request.
- Zero false resolutions depend on deterministic `FinalizeGate` mechanism contracts over the 7 closed-vocabulary synthetic failure modes and do not imply zero misattribution on open-world unstructured incidents.
