# V1.3 reliability evaluation protocol

This offline experiment measures provider reliability, request accounting and guard preservation. It does not measure live provider quality, RCA accuracy, billing savings, or multi-agent reasoning quality.

Run from the checkout root in the project Python environment with `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/reliability -q
python scripts/run_reliability_eval.py --out results/v13-eval/NEW-EXPERIMENT-ID
```

The CLI refuses an existing output directory. No real API is contacted. Runtime guard checks execute selected existing pytest assertions and preserve their logs/JUnit XML; their unmeasured HTTP, token and completion values are NULL.

## Frozen paired groups

R0 dynamically compiles the original provider source from commit `9e209218a9d0ce128d955897b1abfb3070afb4d9`, in an isolated module. Its source and SHA-256 are exported. R0 never calls the current provider's disabled path. R1 uses the production enabled recovery path and generic repair, with a hard request/stage/deadline permit guard but no recovery snapshot. R2 adds the shared budget snapshot. R3 adds targeted repair. All groups share model, schema, initial prompt/input, response format, temperature, hard request/time/stage limits and per-case response schedule. At most one repair and four physical requests are configured; two transport retries are allowed.

R1 still has production fallback deadline/physical-cap logic and hard guards. It cannot be described as completely budget-unaware. R2 adds information for retry feasibility before sleeping. R0 retains its historical envelope/truncation semantics; F17 records that behavior without treating it as correct V1.3 truncation validation. R0's generic repair and R1/R2 generic repair are retained. Targeted and generic prompts receive the same scripted corrected response, so this matrix cannot establish an incremental targeted-prompt efficacy benefit.

## Cases and evidence

| ID | Actual injected condition / executed guard assertion |
|---|---|
| F01 | Valid 200, one dispatch |
| F02 | 429 then valid 200 |
| F03 | Retry-After 30 seconds exceeds two-second deadline |
| F04 | 503, 503, valid 200 |
| F05 / F21 | 401 / 403, no retry |
| F06 / F22 | Unknown-code 400 / 422, no fallback |
| F07 | ReadTimeout then valid 200, aggregate usage unknown |
| F08 | Invalid JSON then corrected response |
| F09 | Missing schema fields then corrected response |
| F10 | Invalid JSON twice, bounded failure |
| F11 | Existing forged-citation cache integrity/domain guard test |
| F12 | Two concurrent production HTTP calls race for the final permit |
| F13 | Cancellation during provider backoff, no second POST |
| F14 | Cancellation raised while MockTransport handles an in-flight POST |
| F15 | Existing production stage-context concurrency and shared whole-task permit tests |
| F16 | Valid output with all usage fields missing |
| F17 | Valid-looking response with finish_reason=length |
| F18 | Existing actual incident-response PLAN_READY/DIAGNOSIS_READY normal-stop scoring |
| F19 | Existing actual insufficient-evidence incident_040 INCONCLUSIVE scoring |
| F20 | Existing cold/warm legacy graph cache/grounding and normal monitoring workflow |
| F23 | 429 with one total permit |
| F24 | 429 with one monitoring-stage permit |
| F25 | Transport retry followed by schema repair |

F11/F12/F15/F18/F19/F20 are runtime assertion evidence, evaluated once against the current runtime. They are excluded from the R0–R3 provider ablation and do not imply frozen-runtime compatibility was rerun. F14 proves cancellation accounting and no further dispatch at the adapter boundary; full frozen-state isolation remains covered by the existing runtime regression suite. Each matrix row links expected and observed completion/dispatch counts or the exact executed test nodes. A passing matrix includes expected failures; it is not a 100% technical completion rate.

## Metrics and artifacts

`case-level.csv` is the authoritative measured provider row set. `provider-attempts.jsonl` includes actual MockTransport dispatch events and sanitized production observer events, never request bodies, headers, response payloads or secrets. R0 has dispatch evidence but no new V1.3 observer events. `aggregate.csv` exports each rate with numerator, denominator and sample count. Logical completion is valid final Pydantic output; no investigation completion rate is inferred from these calls. Retry recovery denominator is cases whose first injected fault is retryable. Structured validity before/after uses cases with a content-bearing response; before means the first content-bearing response, which may follow an HTTP retry. Structured repair effectiveness uses cases that actually dispatch a repair request. Runtime normal-stop and evidence-insufficiency scoring assertions distinguish technical failure from semantic abstention without introducing RCA aggregate claims.

Known measured token sums are lower bounds. Any unmeasured dispatched attempt keeps total_tokens NULL even if a later response supplies usage. No cost is inferred. Injected clock backoff is recorded separately; host elapsed time in frozen R0 and fake-clock elapsed time in R1–R3 must not be compared as latency measurements. There are no significance claims.

`manifest.json` records current revision/dirty state, baseline revision/source hash, current provider source hash, prompt/schema/dataset/protocol hashes. `protocol.json` contains the complete public synthetic schedule and runtime test nodes. The export also contains `baseline-provider.py`, `fault-matrix.csv`, `error-analysis.md`, reproduction `README.md` and actual runtime assertion logs/XML. Recompute aggregates only from provider-scope rows. All outputs are new, gitignored experiment artifacts.

Live compatibility and paired Seed/Dev experiments remain a separate Lead phase. They must preserve model, input/prompt/schema/config hashes, budgets, jobs, response mode and cache setting, alternate R0/R3 execution order, and report unknown usage as NULL. Offline fixture outcomes cannot substitute for live evidence.
`F26/F27` deny an unissued JSON/schema repair at final global/stage permits; `F28` permits a repair using the final second request; `F29/F30` exercise the four-attempt bound across two HTTP retries and one repair. Actual dispatch-derived counts are checked against production retry/repair usage counters, including zero for denied requests. The oracle-free `technical_completion` helper uses existing termination normalization so explicitly recovered model failures do not invalidate a normal terminal run.
