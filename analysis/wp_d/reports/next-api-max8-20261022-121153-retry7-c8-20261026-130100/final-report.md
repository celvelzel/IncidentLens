# Frozen batch retry round 7

All 10 remaining technical-failure slots were retried once with the original
batch concurrency 8, after an independent probe returned 200 from the frozen
endpoint and model on 2026-10-26. Frozen model, prompts, budgets and internal
recovery were retained.

All 10 attempts failed **before any HTTP request was sent**. This was a local
environment defect, not a provider decision.

| Slot | New attempt | Failure cause | HTTP requests | Tokens |
| --- | --- | --- | --- | --- |
| slot-001 | attempt-008 | InvalidURL (local) | 0 | 0 |
| slot-004 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-010 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-020 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-022 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-026 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-028 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-032 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-035 | attempt-007 | InvalidURL (local) | 0 | 0 |
| slot-039 | attempt-007 | InvalidURL (local) | 0 | 0 |

Cause: the process environment inherited by the workers carried a bracketed
`[::1]` entry in `NO_PROXY`. httpx maps each NO_PROXY entry to a proxy-mount
pattern; the bracketed form is classified as a plain hostname and becomes
`all://*[::1]`, whose URL parse fails with `Invalid port: ':1]'` atclient
construction. Observability confirms `TASK_FAILED error_code=InvalidURL` at
the first coordinator call of every attempt, with `actual_http_requests: 0`.

No provider budget was consumed (0 HTTP, 0 tokens). No frozen input changed;
224 frozen inputs verified, batch manifest unchanged, all historical attempt
trees unchanged. These round-7 attempts remain recorded as failed attempts in
the batch state and are treated as history by later rounds.

This round carries no provider signal. Its lesson is procedural: before
dispatching workers, the child environment must be sanitized so `::1` (no
brackets) is used, which maps to the valid `all://[::1]` no-proxy pattern.
Routing for the API host is unaffected because the API host is not in
NO_PROXY. See round 8 for the retry with that fix applied.
