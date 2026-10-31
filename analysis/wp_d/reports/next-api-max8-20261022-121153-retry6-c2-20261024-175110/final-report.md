# Frozen batch retry round 6

All 10 remaining technical-failure slots were retried once with external concurrency 2. Frozen model, prompts, budgets and internal recovery were retained. All 10 failed again; no new attempt qualifies for replacement.

| Slot | New attempt | Failure stage | HTTP status | HTTP requests | Measured tokens |
| --- | --- | --- | --- | --- | --- |
| slot-001 | attempt-007 | dispatch | 429 | 9 | 5,063 |
| slot-004 | attempt-006 | dispatch | 429 | 8 | 8,482 |
| slot-010 | attempt-006 | dispatch | 429 | 9 | 11,200 |
| slot-020 | attempt-006 | dispatch | 429 | 10 | 8,008 |
| slot-022 | attempt-006 | coordinate | 429 | 3 | 0 |
| slot-026 | attempt-006 | coordinate | 429 | 3 | 0 |
| slot-028 | attempt-006 | dispatch | 429 | 7 | 5,071 |
| slot-032 | attempt-006 | coordinate | 429 | 4 | 4,947 |
| slot-035 | attempt-006 | coordinate | 429 | 3 | 0 |
| slot-039 | attempt-006 | coordinate | 429 | 3 | 0 |

This round: 59 HTTP requests; 42,771 measured tokens (incomplete lower bound).
Final selection remains 4 RESOLVED, 26 INCONCLUSIVE, 10 technical failures. slot-012 retains attempt-002.

Integrity: all 224 frozen inputs match; batch manifest unchanged; all 82 historical attempt trees unchanged. No active workers remain according to terminal supervisor status. Each target received exactly one new attempt. No source/configuration edits were made.

Provider failures remain HTTP 429 / rate_limit_exceeded. Historical logs do not preserve the response message; this round alone cannot prove the precise provider-side limiting threshold. The earlier independent diagnostic returned Channel rate limit reached for model; it is supporting context, not a newly captured error body for these attempts.

External concurrency 2 differs from original concurrency 8; this is not a strictly identical execution-condition comparison.

See final-selection.json, retry-manifest.json and retry-supervisor-status.json for machine-readable evidence.
