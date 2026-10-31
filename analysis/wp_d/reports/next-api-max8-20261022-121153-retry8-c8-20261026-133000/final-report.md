# Frozen batch retry round 8

All 10 remaining technical-failure slots were retried once with the original
batch concurrency 8, after round 7 failed locally on a process-environment
defect. Frozen model, prompts, budgets and internal recovery were retained.

All 10 attempts failed again on HTTP 429, but the failure mode is materially
different from rounds 1-6: the model channel is **open**, not blocked.

| Slot | New attempt | Failure stage | Logical calls | Physical HTTP | OK (logical) | Tokens |
| --- | --- | --- | --- | --- | --- | --- |
| slot-001 | attempt-009 | dispatch | 4 | 10 | 3 | 8,080 |
| slot-004 | attempt-008 | verify | 11 | 21 | 10 | 53,793 |
| slot-010 | attempt-008 | dispatch | 16 | 27 | 15 | 94,821 |
| slot-020 | attempt-007 | dispatch | 3 | 9 | 1 | 5,003 |
| slot-022 | attempt-007 | dispatch | 3 | 9 | 1 | 5,121 |
| slot-026 | attempt-007 | dispatch | 3 | 9 | 1 | 5,162 |
| slot-028 | attempt-007 | dispatch | 4 | 12 | 3 | 7,842 |
| slot-032 | attempt-007 | dispatch | 4 | 10 | 2 | 8,443 |
| slot-035 | attempt-007 | dispatch | 5 | 13 | 3 | 8,023 |
| slot-039 | attempt-007 | dispatch | 5 | 11 | 3 | 8,972 |

This round: 58 logical calls and 131 physical HTTP requests (retries included).
At logical level 43/58 (74%) eventually returned a usable response; at physical
level the reconstruction of the observability event log (timeline_analysis.py,
matching `verification.json actual_http_requests` exactly) shows **89 of 131
requests (68%) returned 429** (`rate_limit_exceeded`, transport phase,
`http_attempt_index=3`, median elapsed tens of ms). 189,660 measured tokens.
slot-010 ran 16 logical calls with 15 successes; slot-004 reached verify.

## Interpretation

The channel-level hard block observed through 2026-10-24 is gone: a standalone
probe returned 200 (2026-10-26 12:31), and under load 43 of 58 logical calls
eventually succeeded with real token usage. What remains is a short-window burst
limit that trips after sustained parallel traffic. The frozen internal recovery
(2 transport retries, 2 s / 4 s fixed backoff, no jitter) is not long enough
to wait out the window, so the logical call that hits the limit exhausts its
retries and the attempt terminates. Because `stop_on_failure` is set, one
terminated attempt pauses dispatch, then the remaining slots each get their
single attempt and meet the same condition.

The request-level reconstruction (timeline_analysis.py) adds a decisive
measurement for the concurrency question: the peak rolling 60 s request rate
of the whole round was **24 req/min** — under half of the posted 50 RPM account
limit — and **21 of the 89 429 responses arrived with exactly one request in
flight**. 429s continued during the round's final minutes when only one or two
slots remained alive. Our own concurrency and request rate therefore never
reached any rate we know of; the limiting object is the shared per-model
channel ("Channel rate limit reached for model"), not this batch's footprint.

This matches the historical 429 profile (fast 429s, well below the posted
account RPM) and is consistent with the TokenPlan rate-limit scope: all keys
of the account share one quota. It does not prove the exact threshold, window
length, or whether the limit is per-model or account-wide; those fields are
not exposed in the response.

## Round 7 local failure (superseded)

Round 7 produced one attempt per slot that all failed with `InvalidURL` before
any HTTP request: the inherited process environment carried a bracketed
`[::1]` in `NO_PROXY`, which httpx cannot parse (it becomes the invalid mount
`all://*[::1]`). Round 8 sanitizes only that child environment (strip the
brackets; `::1` maps to the valid `all://[::1]`). Proxy routing for the API
host is unchanged. No frozen code or config was modified.

## Selection

No new attempt qualifies for replacement (eligibility requires a completed
run). Final selection remains 4 RESOLVED, 26 INCONCLUSIVE, 10 technical
failures; slot-012 retains attempt-002. Cumulative across all attempts:
1,355 HTTP requests, 7,499,817 measured tokens.

Integrity: all 224 frozen inputs match; batch manifest unchanged
(`98232a6b…` before and after); all 102 historical attempt trees unchanged;
selection valid. No active workers remain. Each target received exactly one
new attempt. Round 8 uses the same worker concurrency as the original batch
(8), so this round is a strictly fair execution-condition comparison for the
slots it covers; the provider-side short-window limit, not the local setup,
ended the attempts.

Observation unrelated to the frozen batch: during the execution window
(2026-10-26 13:41-13:42 Asia/Shanghai) two git-tracked but **non-frozen**
documentation files were modified outside this orchestrator:
`data/README.md` and `data/dataset_manifest.json` (counts/limitations text
about the pre-existing database cohort; the cohort packs themselves date from
2026-10-13). Neither file is among the 224 frozen inputs, the frozen-input
verification reports zero mismatches, and no worker or orchestrator process
of this round writes to them. They are recorded here only for a complete
working-tree picture; the batch integrity statements above are unaffected.

See final-selection.json, retry-manifest.json and retry-supervisor-status.json
for machine-readable evidence, and summarize.py for the per-call tally.
