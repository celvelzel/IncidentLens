# Bridge sub-agent matrix — serving notes

Batch: `results/v16/wp-d/matrix-bridge-subagent-20261019`
Started: 2026-10-19
Protocol: `protocol-bridge.json` (model_id=`trae-subagent-bridge-v1`, all budget params identical to the WP-D frozen matrix)
Dataset: `results/wp-b/pilot-public`
Run order: unchanged copy of `results/v16/wp-d/matrix-20261017-01/run-order.json` (12 slots, serial).

## What this batch is

The WP-D fixed matrix re-run with the **caller model replaced**: instead of the COMP GenAI
DeepSeek endpoint, each model request is answered by an isolated, tool-restricted sub-agent.
`scripts/retest_subagent_bridge.py` serializes each request to `_bridge/requests/req-NNNN.json`
and blocks for `_bridge/responses/req-NNNN.json`; it performs no network I/O
(`actual_http_requests = 0`).

## Serving procedure (per request)

1. Wait for a pending request: `serve_bridge_response.py --bridge-dir <run>/_bridge --watch 90`.
2. Spawn ONE fresh sub-agent per request (context isolation). The sub-agent may use only `Read`
   (the single request file) and `Write` (its raw JSON output). It must not explore, search,
   run commands, or read any other file — in particular no oracle / ground-truth / answer file.
3. The sub-agent's input is exactly the request's `messages` array (system prompt + user payload),
   the same content a real API would see. It returns the strict-schema JSON object.
4. Assemble the envelope verbatim:
   `serve_bridge_response.py --serve-dir <batch>/_serve --requests req-XXXX ...`
   copies `content` byte-for-byte and binds `session_id` / `request_id` / `request_sha256`
   from the request file. No field is repaired, trimmed, or rewritten.

## Known quirks

- A sub-agent may report "(No output)" yet still have written its raw file. Always trust the
  on-disk `_serve/req-XXXX.raw.json`; the helper errors with "missing raw output file" only when
  the file is genuinely absent, in which case re-spawn that request.
- The `Explore` sub-agent type does not honour the JSON-endpoint contract; use `general-purpose`.

## Exact per-request sub-agent prompt template

Spawn one `general-purpose` sub-agent per request, substituting `<REQ>` and `<RAW>`:

```
You are a JSON-only model endpoint. Do exactly this and nothing else.

Step 1: Call the Read tool exactly ONCE, on this single path:
<REQ>

You may NOT use any other tool besides Read and (in step 3) Write. You may NOT explore, grep, glob, or search the repository. You may NOT read any other file. You may NOT run shell commands. You may NOT edit files.

Step 2: That file is a JSON object. Its "messages" array is your complete input. Element 0 is the system prompt, whose text ends with "The required output JSON Schema is:" followed by the JSON Schema. Element 1 is the user payload (a JSON state object).

Step 3: Compute the single JSON object that a strict OpenAI `response_format: json_schema` endpoint would return for exactly those messages: include EVERY property in the schema's "required"; honor "additionalProperties": false; use only allowed enum values; populate arrays/strings meaningfully from the user payload. Then IMMEDIATELY call the Write tool to write ONLY that raw JSON object, no markdown code fences, no extra text, to this exact path:
<RAW>

Step 4: Your final message must be exactly: OK
```

`<REQ>` = `<run>/_bridge/requests/req-NNNN.json`; `<RAW>` = `<batch>/_serve/run-NN/req-NNNN.raw.json`
(per-run serve dir; request ids restart at req-0001 for every run, so never share one _serve dir).

### Chunked serving (requests larger than 64 KB)

A sub-agent's single `Read` tops out at 64 KB. When `--watch` reports a request whose size is
> 64 KB, split it first, then spawn one sub-agent that reads the parts in order:

```
serve_bridge_response.py --bridge-dir <run>/_bridge \
  --prepare <run>/_bridge/requests/req-NNNN.json \
  --prep-dir <batch>/_prepare/run-NN --chunk-kb 40
```

This prints `PART ... bytes=...` lines (each part < 64 KB, compact single-line JSON). Then spawn
one `general-purpose` sub-agent per request with the SAME template as above except step 1/2 read
each `<PREP>/req-NNNN.part-XX.json` ONCE (in order) and step 3 is:

```
Concatenate the part line contents IN ORDER with NO separator and NO added whitespace/newline.
The Read tool prepends a line-number gutter like "1→" — strip it and use only the literal
characters after it. The concatenation is the request's "messages" JSON array. Parse it, then
produce the strict-schema object and Write it (verbatim, no fences) to <RAW>.
```

For a 3-part request, repeat the Read step for part-00, part-01, part-02 before concatenating.
Repair requests (`req-NNNN-repair.json`) are served the same way, with raw path
`<RAW>` = `<batch>/_serve/run-NN/req-NNNN-repair.raw.json`. Never repair content in the parent:
if the helper prints `NOT_JSON`, leave it and wait for the harness's `req-NNNN-repair` request.

## Launch command per slot

```
.venv\Scripts\python.exe -B scripts/retest_subagent_bridge.py \
  --dataset results/wp-b/pilot-public \
  --protocol results/v16/wp-d/matrix-bridge-subagent-20261019/protocol-bridge.json \
  --incident <ID> --variant <VARIANT> \
  --out results/v16/wp-d/matrix-bridge-subagent-20261019/run-NN-<ID>-<VARIANT>-subagent-01
```

## Remaining slots (same frozen order as run-order.json)

- slot 3 incident_1001 fixed
- slot 4 incident_1003 full
- slot 5 incident_1001 dynamic_no_verifier
- slot 6 incident_1002 single
- slot 7 incident_1003 fixed
- slot 8 incident_1001 full
- slot 9 incident_1002 fixed
- slot 10 incident_1003 dynamic_no_verifier
- slot 11 incident_1001 single
- slot 12 incident_1003 single

## Status

- slot 1 incident_1002 full — COMPLETE (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`,
  `protocol_valid=true`, 22 logical calls, 0 HTTP, status=RESOLVED)
- slot 2 incident_1002 dynamic_no_verifier — COMPLETE (`termination=DIAGNOSIS_READY`,
  `outcome=SUCCESS`, `protocol_valid=true`, 15 logical calls, 0 HTTP, status=RESOLVED)
- slot 3 incident_1001 fixed — COMPLETE (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`,
  `protocol_valid=true`, 0 HTTP, status=RESOLVED)
- slot 4 incident_1003 full — COMPLETE at `run-04-incident_1003-full-subagent-01-retest-01`
  (`termination=INCONCLUSIVE`, `outcome=ABSTAINED`, `protocol_valid=true`, 19 llm_requests,
  2 repair_requests, 0 HTTP, `status=INCONCLUSIVE`) = correct abstention for the missing-evidence case.
  The earlier failed original (`failure_stage=coordinate`, 21 calls) was deleted on 2026-10-21 at
  the user's explicit instruction, so only the retained run remains on disk.
- slot 5 incident_1001 dynamic_no_verifier — COMPLETE (`termination=DIAGNOSIS_READY`,
  `outcome=SUCCESS`, `protocol_valid=true`, 16 llm_requests, 0 HTTP, `status=RESOLVED`,
  culprit=backend/backend_pool_config_regression)
- slot 6 incident_1002 single — COMPLETE (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`,
  `protocol_valid=true`, 23 llm_requests, 0 HTTP, `status=RESOLVED`,
  culprit=backend/backend_pool_config_regression; rejected misleading postgres/redis/payment)
- slot 7 incident_1003 fixed — COMPLETE (`termination=INCONCLUSIVE`, `outcome=ABSTAINED`,
  `protocol_valid=true`, 7 llm_requests, 0 HTTP, `status=INCONCLUSIVE`) = correct abstention.
- slot 8 incident_1001 full — COMPLETE (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`,
  `protocol_valid=true`, 26 llm_requests, 0 repair, 0 HTTP, `status=RESOLVED`,
  culprit=backend/backend_pool_config_regression; rejected backend_resource_saturation,
  postgres_connection_exhaustion, payment_external_timeout)
- slot 9 incident_1002 fixed — COMPLETE (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`,
  `protocol_valid=true`, 9 llm_requests, 0 repair, 0 HTTP, `status=RESOLVED`,
  culprit=backend/backend_pool_config_regression; rejected misleading postgres_connection_exhaustion
  and backend_resource_saturation)
- slot 10 incident_1003 dynamic_no_verifier — COMPLETE at
  `run-10-incident_1003-dynamic_no_verifier-subagent-03` (`termination=INCONCLUSIVE`,
  `outcome=ABSTAINED`, `protocol_valid=true`, `runtime_failure=false`, 17 llm_requests,
  0 repair_requests, `actual_http_requests=0`, `query_gap_count=11`,
  `verifier.review_kind=absent`, `bridge_requests=17`). All 17 bridge requests were served `ok`;
  `req-0017` (68 618 B) exceeded the 64 KB single-Read limit and was split with
  `--prepare --chunk-kb 40` into 2 parts. Final decision = ABSTAIN with no assignments,
  `selected_hypothesis_id=null`, and a non-empty stop reason: postgres/redis/payment logs, broad
  change history, and postgres/payment database and metric telemetry all completed with zero
  records, leaving only the generic backend deadline record `incident_1003-E-003` and one 40 ms
  pre-deadline latency sample; no competing mechanism could be rejected with observed contrary
  evidence. That is the expected behaviour for the evidence-insufficient case (incident_1003),
  matching slots 4, 7 and 12.
  Protocol deviation (explicitly authorised): `request_timeout` raised 420 s → 1200 s in
  `protocol-bridge-relaxed.json`; every other parameter is identical to `protocol-bridge.json`.
  Consequently slot 10 is **not** a same-conditions observation — see the caveat below.
  History: this slot failed seven times before the retained run, all in the serving layer
  (one `ROLE_TOOL_PROPOSAL_FORBIDDEN`, three `BRIDGE_TIMEOUT`, one `BUDGET_EXHAUSTED`, and the
  others likewise transport-side). At the user's explicit instruction those failed attempt
  directories and their `_serve` data were deleted on 2026-10-21, so only the successful run is
  kept. This is selective retention: the deleted attempts contained no valid architectural
  observation, but the deletion means the failure trail is no longer reproducible from disk.
- slot 11 incident_1001 single — COMPLETE at `run-11-incident_1001-single-subagent-01-retest-01`
  (`termination=DIAGNOSIS_READY`, `outcome=SUCCESS`, `protocol_valid=true`, 13 llm_requests,
  0 repair, 0 HTTP, `status=RESOLVED`, culprit=backend/backend_pool_config_regression;
  rejected postgres_connection_exhaustion). Served with an added ACL-compliance reminder;
  `isolation_verified=false` is reported for the bridge as a whole (see caveats).
  The earlier failed original (`COORDINATOR_TASK_ACL_INVALID`, 1 llm_request) was deleted on
  2026-10-21 at the user's explicit instruction, so only the retained run remains on disk.
- slot 12 incident_1003 single — COMPLETE (`termination=INCONCLUSIVE`, `outcome=ABSTAINED`,
  `protocol_valid=true`, 16 llm_requests, 0 repair, 0 HTTP, `status=INCONCLUSIVE`) = correct
  abstention for the missing-evidence case. Note: one raw (`req-0003`) was parent-persisted
  verbatim from the sub-agent's returned JSON because the sub-agent printed the object without
  calling Write; no content was repaired or altered (validated against schema before serving).

## Consolidated 12-slot result (after slot-10 attempt 7)

| Outcome | Count | Slots |
|---|---|---|
| RESOLVED (`backend/backend_pool_config_regression`) | 8 | 1, 2, 3, 5, 6, 8, 9, 11 |
| Correct abstention (incident_1003, evidence insufficient) | 4 | 4, 7, 12, 10 |
| FAILED / unmeasured | 0 | — |

**Comparability caveat.** This is a development-set exploratory pilot, not a formal accuracy
measurement. Slot 4 and slot 11 were completed only after a retest, and slot 10 only after seven
attempts (six of which failed in the serving layer) with `request_timeout` relaxed from 420 s to
1200 s. Slots were therefore not all observed under identical conditions; the slot-10 abstention
must not be presented as a first-pass, same-conditions result.
