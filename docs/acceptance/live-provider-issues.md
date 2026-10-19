# Live-provider known issues — real-model run findings

Current iteration overview: [RCA retest iteration](rca-retest-iteration-20261015.md).
The entries below retain historical run observations; old source line numbers and
suite counts describe their recorded versions. ISSUE-6 includes the later fix.

Recorded 2026-10-14 during the first real-model evaluation of V1.4 on the COMP
On-Premises GenAI Platform (`DeepSeek-V4-Flash`, endpoint
`https://genai.comp.polyu.edu.hk/api/v1`). These issues are runtime error-handling
defects in the dispatch layer, first exposed by real-model runs; the original offline mock
acceptance suite (723 passed) did not cover them. **Fix implemented 2026-10-14.**
Validation and remaining real-provider limits are recorded in
[the fix acceptance report](live-provider-fix-acceptance.md).

The original trace is retained below as historical evidence. Verification corrected
three interpretations: `inventory` is outside the case's service list (a valid empty
query already returns `ok=true`); one worker failure alone triggers the legacy batch
abort; and the ninth request was cancelled with unknown usage, so this was not a
9/9 successful-request run. The defect is reproducible with offline fault injection.

## ISSUE-1: Tool `NOT_FOUND` (unknown service) cascades into whole-investigation `UNRECOVERABLE_ERROR`

**Severity: High** — aborts otherwise healthy investigations; blocks reliable
real-provider evaluation.

### Symptom

A task whose evidence tool returns `NOT_FOUND` (the queried service does not exist
in this case) fails that task. This failure cancels a sibling call in the
same parallel batch (observed: a model call recorded as
`PROVIDER_CANCELLED`), and the dispatch layer escalates to
`UNRECOVERABLE_ERROR` and terminates the entire investigation with no RCA report,
even though rounds and LLM budget remain.

### Observed evidence

Run `incident_2001.full.repeat-0` (batch budget32), state file:
`results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/runs/states/incident_2001.full.repeat-0.json`

- Round 1 healthy: gateway 5xx evidence (`incident_2001-E-009`, `http_5xx_rate=0.35`)
  and config-deployment evidence (`E-003`) found; Verifier review completed;
  hypothesis direction plausible (`backend_pool_config_regression`).
- Round 2 parallel batch:
  - `t3_metrics_inventory`: `query_metrics(inventory)` -> `NOT_FOUND` (0 records)
    -> task FAILED (`Tool failed: NOT_FOUND`).
  - `t2_metrics_payment`: model call elapsed 12.3s then `PROVIDER_CANCELLED`
    -> task FAILED.
- Escalation: `WORKFLOW_STOP_REQUESTED` at stage `dispatch`, reason
  `UNRECOVERABLE_ERROR`; report `INCONCLUSIVE`, `root_cause: null`.
- Budget spent 9/32 LLM calls — this is NOT budget exhaustion.
- The readiness probe succeeded. Eight requests completed; the cancelled ninth
  request has `tokens_complete: false` and unknown total usage. The trace does not
  establish its server-side completion or billing status.

Scoring record: `runs/scores.jsonl` ->
`failure_category: UNRECOVERABLE_ERROR`, `diagnosis_failure: true`, llm_requests 9.

### Root-cause chain (pre-fix code)

1. `src/incident_lens/tools/registry.py:205,209` — empty/missing service data is
   returned as `error_code: "NOT_FOUND"` with `ok: false`.
2. `src/incident_lens/orchestration/graph.py:507-508` — any tool result with
   `ok: false` raises `RuntimeError("Tool failed: ...")`, turning a benign data
   gap into a hard task failure with no re-planning signal.
3. Parallel sibling failures plus un-recovered model failures
   (`graph.py:898-903`, `evaluation/termination.py:215`) upgrade the stop reason
   to `UNRECOVERABLE_ERROR` and abort the whole run.

### Why mock acceptance missed it

The original mock acceptance cases did not produce the `NOT_FOUND` + concurrent model-cancellation
combination. Deterministic offline dispatch injection can reproduce this class of defect;
which `results/acceptance/v14/final/phase-acceptance.json` records as
`P6: REAL_EVAL_PENDING` / `real_provider_requests: 0`.

### Expected behavior (fix requirements)

1. `NOT_FOUND` / empty-record tool results must be **task-level tolerable outcomes**,
   not hard failures: the task should complete with an explicit "no data for this
   service/window" observation so the Coordinator can re-plan (choose another
   service or evidence type). Tool ACL and record caps stay unchanged.
2. A sibling task failure must not cancel healthy in-flight siblings by default;
   if cancellation is kept as a budget-saving policy, it must be configurable and
   must never itself escalate to `UNRECOVERABLE_ERROR` when budget and rounds
   remain.
3. `UNRECOVERABLE_ERROR` should be reserved for genuinely unrecoverable conditions
   (protocol violation, repeated provider transport failure). Data gaps and single
   task failures should yield continued investigation or a clean `INCONCLUSIVE`
   abstention, never a runtime crash path.
4. Any new failure taxonomy must keep the v1.2 stop-protocol invariants: STOP
   traces get no root/abstention credit; measured usage remains complete where
   observed.

### Acceptance checks for the fix

- Unit test: tool `NOT_FOUND` yields a task completion with a no-data observation
  (no `RuntimeError`).
- Integration test: parallel batch with one `NOT_FOUND` tool result + one cancelled
  model call completes the investigation (continued rounds or clean
  `INCONCLUSIVE`), and scoring records no `UNRECOVERABLE_ERROR`.
- Re-run `incident_2001.full` on COMP `DeepSeek-V4-Flash` under
  `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/`
  protocol and confirm the crash path is gone.
- Full pytest suite stays green (baseline 2026-10-14: 849 passed, 1 flaky
  contention failure in `test_experiment_fairness.py` that passes in isolation).

## ISSUE-2 (observation, lower severity): `PROVIDER_CANCELLED` on in-flight model calls when a sibling task fails

Observed in both real batches (budget16 run1, budget32 run1): an in-flight model
call (~12s) is cancelled and recorded as `PROVIDER_CANCELLED` with
`tokens_complete: false` and `measured_total_tokens: 0`. This is the dispatch
layer cancelling siblings on batch failure, not a platform/network fault. If
ISSUE-1 is fixed and sibling cancellation is retained, the cancelled-call usage
accounting (server-side generation and billing are unknown without usage) should be
documented in the failure accounting contract. Same fix batch as ISSUE-1.

## ISSUE-3: Verify-stage `PROVIDER_TIMEOUT` is fatal while identical diagnosis-stage timeout recovers

**Severity: High** — aborts an otherwise complete investigation at the final step;
blocks reliable real-provider evaluation on high-latency endpoints.

Recorded 2026-10-15 during the retest of the 2026-10-14 RCA fix batch on the new
provider endpoint (`deepseek-v4-flash-0731`,
`https://discovery-api.intern-ai.org.cn/v1`). **Fix implemented 2026-10-15.**

### Symptom

Run `run-255c309b55f3467c946a408943313b45` (`incident_2001`, variant `full`),
state: `results/incidentbench/v1/user-retest-reconciliation/full/`.

- All worker tasks, merge, and a first Verifier review (`insufficient` + two
  blocking `requested_checks`, contract-correct) completed; E-003/E-004 fetched;
  postgres competitor rejected via E-007. 14/32 LLM calls used.
- 16:52 a diagnosis-stage metrics call timed out at 182.3s
  (`request_timeout: 180`) -> `PROVIDER_TIMEOUT` -> task retry `attempt-3`
  succeeded (`MODEL_RECOVERED`).
- 17:00 the final verify-stage call also exceeded 180s -> `PROVIDER_TIMEOUT` ->
  `RUNTIME_ERROR` stage `verify` -> `UNRECOVERABLE_ERROR`, report `INCONCLUSIVE`.
- `repair_requests: 0` — the `strict_schema` shim eliminated the earlier
  `STRUCTURED_OUTPUT_INVALID`; this failure is purely transport latency.

### Root-cause chain

1. `src/incident_lens/llm/provider.py:203-204` — `httpx.TimeoutException` raises
   `ProviderError("PROVIDER_TIMEOUT")` immediately; the retry loop at :186 only
   re-enters on schema-repair, so timeouts get no transport-level retry.
2. `src/incident_lens/orchestration/graph.py:854-863` — `verify()` catches every
   exception, sets `stop_reason`, emits `RUNTIME_ERROR`, routes to `report`;
   unlike diagnosis-stage tasks (retried per-attempt), the verify call has no
   retry wrapper, so one transient timeout terminates the run.
3. Termination normalization records `UNRECOVERABLE_ERROR` with
   `runtime_failure: true`, although budget (18 LLM calls) and rounds remained.

### Expected behavior (fix requirements)

1. Transient `PROVIDER_TIMEOUT` / `PROVIDER_TRANSPORT_ERROR` at the verify stage
   must get a bounded retry (task-level or transport-level), consistent with the
   diagnosis stage; only repeated failure may escalate.
2. Single transient verify failure should degrade to continued investigation or
   clean abstention, never a runtime crash, per the ISSUE-1 taxonomy.
3. Keep stop-protocol invariants: usage accounting for the timed-out call stays
   `tokens_complete: false`.

### Fix applied

`graph.py` `verify()` now routes the review through the same bounded per-attempt
retry as a diagnosis task (task id `verify-<round>`, `task_manager.assign/start/
fail/can_retry`), retrying only `recoverable_task_error` codes and still failing
closed on protocol violations, exhausted budget, or STOP. `verify()` also binds
`self.state` — it was the one node that never did, so runtime task-transition
events were emitted against a stale state object and the review's task records
were missing from the trace; the termination protocol then reported
`task snapshots conflict with transition events`.

Validation: new regression test
`tests/reliability/test_fault_matrix.py::test_verify_stage_transient_fault_retries_instead_of_aborting`
(a single verify-stage timeout now retries, emits `MODEL_RECOVERED` with stage
`verify`, and finishes without a runtime failure). Full suite green:
880 passed, 3 skipped.

## ISSUE-4 (environment, not a code defect): accumulated endpoint stalls exhaust the wall-clock budget

**Severity: Medium** — not a defect; a resource-envelope mismatch between the new
slow endpoint and the 900s `max_wall_seconds` chosen for the older endpoint.

Recorded 2026-10-15 on the retest that validated the ISSUE-3 fix.

### Symptom

Run `run-b7f3bab13b3c46dbb11674e45cfb7825` (`incident_2001`, variant `full`),
state: `results/incidentbench/v1/user-retest-reconciliation/full/`.

- Termination `BUDGET_EXHAUSTED` / `FAILED`, `failure_stage: verify`,
  `runtime_failure: true`, `protocol_valid: true`, `stop_completed: true`.
- 22/32 LLM calls, `repair_requests: 0`.
- `task_retries: 3`, `recovered_model_failure_count: 3`,
  `unrecovered_model_failure_count: 0` — **the ISSUE-3 fix worked**: three
  diagnosis-stage `PROVIDER_TIMEOUT`s (182.3s, 182.3s, 182.9s) each retried at
  `attempt-2` and all recovered (`MODEL_RECOVERED` ×3).
- `verify-1` (20.9s) and `verify-2` (30.1s) completed normally.
- `verify-3` started 01:01:54, and at 01:02:40 the in-flight call (46.2s elapsed)
  raised `BudgetExceeded` -> `RUNTIME_ERROR` stage `verify` ->
  `WORKFLOW_STOP_REQUESTED`. The first recorded event at 00:48:02 follows a 21.4s coordinator call;
  inferred execution start is about 00:47:40.7, so the 900s deadline is
  01:02:40.7. Event timestamps are not run-start timestamps.

### Root-cause chain

1. The endpoint (`https://discovery-api.intern-ai.org.cn/v1`) has a high latency
   baseline: successful structured calls in this run ranged 3.9s–131.7s, with
   several at 50–90s.
2. Three client-observed request timeouts hit the 180s `request_timeout`;
   their server-side cause is not established by these logs. Two ran in parallel
   (`model-call-4`/`model-call-5`), the third serial (`model-call-19`), so the
   stalls alone consumed ~365s of the 900s wall clock (~41%) before any work
   completed. All three were recovered by retry — the cost is wall time, not
   correctness.
3. The wall budget spans the whole run, so cumulative stalls plus the high
   baseline latency exceeded 900s. `verify-3` began with ~46s left and the stop
   guard fired mid-call; `graph.py` `verify()` correctly did **not** retry an
   exhausted budget (`self.exhausted(state)` guard) and failed closed.
4. Classification is stage-independent, so this is not a verify-specific defect:
   `schemas/workflow.py:85` sets `runtime_failure = reason not in NORMAL_REASONS`,
   and `BUDGET_EXHAUSTED` is outside `NORMAL_REASONS`; a diagnosis-stage wall
   exhaustion classifies identically. No code change is warranted.

### Resolution (operational)

The 900s envelope was sized for the previous endpoint's latency profile. Remedy
is to raise `max_wall_seconds` for the new endpoint (see
`pilot-protocol-retest-v3.json`, wall 1800) while keeping `request_timeout: 180`
— a 131.7s successful call shows legitimate calls already approach the timeout,
so lowering it would truncate valid work.

## ISSUE-5: Same gap as ISSUE-3 at the `coordinate` stage — a single first-call timeout aborts the run

**Severity: High** — the coordinator is the very first model call of every run, so
this makes the whole run a single point of failure on a stalling endpoint.

Recorded 2026-10-15, in the wall-1800 retest (`pilot-protocol-retest-v3.json`).
**Fix implemented 2026-10-15.**

### Symptom

Run `run-21fe3a81b079449e9f60a67b1322cf85` (`incident_2001`, variant `full`),
state: `results/incidentbench/v1/user-retest-reconciliation/full/`.

- `model-call-1` (role `coordinator`, stage `coordinate`) stalled 182.5s ->
  `PROVIDER_TIMEOUT` -> `RUNTIME_ERROR` stage `coordinate` ->
  `WORKFLOW_STOP_REQUESTED` reason `UNRECOVERABLE_ERROR`.
- `llm_requests: 1`, `failed_calls: 1`, `recovered_model_failure_count: 0`,
  `unrecovered_model_failure_count: 1`, `protocol_valid: true`.
- The run died with approximately 1617.5s of the 1800s wall clock and 31/32 LLM calls untouched — this
  was not a budget problem, and wall 1800 did not help.

### Root-cause chain

1. The endpoint stalls regularly (`request_timeout: 180`); legitimate successful
   calls reach 50–130s, so stalls are indistinguishable from slow success until
   the timeout fires.
2. `src/incident_lens/orchestration/graph.py` `coordinate()` called `model_call`
   directly with no retry wrapper. `verify()` had the same gap until the ISSUE-3
   fix; `coordinate()` was left untouched by that fix, so it kept the identical
   failure path.
3. The exception propagated to the node's catch-all, which emits `RUNTIME_ERROR`
   and stops the workflow. Per the ISSUE-1 taxonomy only **repeated** transport
   failure may be unrecoverable; a single transient stall terminating a run is a
   harness robustness defect.

### Fix applied

- `graph.py`: new shared `retry_transient` (bounded per-attempt retry via
  `task_manager.assign/start/fail/can_retry`, `exhausted(state)` guard,
  `record_recovery`, binds `self.state` — the ISSUE-3 trap) plus
  `stage_retryable_error`, which restricts stage re-issue to transport-class
  codes (`PROVIDER_TIMEOUT`, `PROVIDER_TRANSPORT_ERROR`) on top of the shared
  recoverability rule. The adapter already bounds structured-repair and
  HTTP-status handling internally, so re-driving those at stage level would
  double-count requests and break the accounting invariants.
- Wired into `coordinate()` (both `decide` sites, task id `coordinate-<round>`)
  and `monitor()` (`monitor-1`). `verify()` keeps its own loop; diagnosis tasks
  keep `execute_task`'s loop; `merge()` has no model call; `remediate()` keeps
  its existing bounded loop.
- Fail-closed behavior preserved: protocol violations (e.g. the coordinator's
  at-most-two-assignments rule), `PROVIDER_CANCELLED`, STOP, and exhausted budget
  are never retried.

Validation: new regression test
`tests/reliability/test_fault_matrix.py::test_coordinate_stage_transient_fault_retries_instead_of_aborting`
(a single coordinator-call timeout now retries, emits `MODEL_RECOVERED` with
stage `coordinate`, and finishes without a runtime failure). Full suite green:
881 passed, 3 skipped.

## ISSUE-6: Redundant coordinate after refreshed FINALIZE review exposes delivery to two request timeouts

**Severity: High for real-provider acceptance** — the model reaches the correct
root cause and the Verifier accepts it, but a stalled transport call at the next
coordinate stage terminates the run before the report is emitted.

### Symptom (2026-10-15 wall3600/req300 development retest)

Run `run-0c72d8de98e14b37b49a85f63e4133b3` (`incident_2001`, variant `full`,
protocol `...budget32-wall3600-req300-retest-v4`, endpoint
`https://discovery-api.intern-ai.org.cn/v1`, model `deepseek-v4-flash-0731`):

- Investigation converged correctly: hypothesis
  `backend_pool_config_regression` (backend, `db_pool_max 20->2`,
  `concurrency=120` at 12:00:10Z, `pool_waiters=118`) reached status
  `SUPPORTED` with evidence `E-003/004/005/008/009`; competing hypotheses
  `postgres_connection_exhaustion` and `backend_resource_saturation` were
  rejected against explicit evidence. The Coordinator decided `FINALIZE` at
  04:06:57Z and the Verifier judged `sufficient` at 04:05:09Z and again at
  04:08:00Z after the FINALIZE hypothesis updates invalidated the first review.
- The follow-up coordinate call (`coordinate-5`) timed out at ~302s
  (`PROVIDER_TIMEOUT`) on attempt-17 and again on attempt-18. Both task
  attempts were consumed, so the dispatch layer escalated to
  `UNRECOVERABLE_ERROR` (failure stage `coordinate`) and the run ended
  `INCONCLUSIVE` at 04:18:04Z — wall spent 2955/3600s, LLM budget 25/32.

### Observed evidence

- Run dir: `results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/full`
  (`trace.json`, `result.json`, `verification.json`, `failed-calls.json`).
- All 5 model failures are the same signature: elapsed 301.9-302.8s against
  the 300s client deadline, error code `PROVIDER_TIMEOUT`, unknown token usage
  (endpoint returns no usage fields). Two hit `diagnosis`
  (`task_metrics_backend_2001`, both remained unrecovered), one hit
  `verify` (`verify-2`, recovered), two hit `coordinate-5` (both lost -> stop).
- The same preflight probe (`verifier-preflight/attempt1`, saved `req-0006`
  Review input, 300s cap) also stalled at 302s and succeeded on the immediate
  retry (`attempt2`, 15353 tokens) — the endpoint intermittently stalls at the
  deadline rather than rejecting fast.

### Root-cause chain (v4 code before finalization fix)

1. `src/incident_lens/llm/provider.py:195-196` — any `httpx.TimeoutException`
   maps to `PROVIDER_TIMEOUT`; when the endpoint stalls, the only bound is the
   per-request deadline (300s here). A stall therefore always costs the full
   deadline and one task attempt.
2. Runtime retry (ISSUE-3 fix) works as designed: `graph.py` `retry_transient`
   gave `coordinate-5` two attempts (attempt-17/18). With `max_attempts=2`, two
   consecutive stalls exhaust the task.
3. `evaluation/termination.py` — exhausted task attempts plus
   `unrecovered_model_failure_count: 4` upgrade the stop reason to
   `UNRECOVERABLE_ERROR`, even though rounds/budget remained and the Verifier
   had accepted the supported hypothesis.

### Fix and validation

The original v4 remains a failed real-provider run. Its client-side errors establish
transport timeouts, not the exact location or cause of the stalled requests.
The event trace also reveals a workflow defect: event-97 already decided FINALIZE,
event-98 updated hypotheses, and the necessary refreshed review at event-104 passed
all existing finalization guards. Returning to another coordinate call was redundant.

Full mode now routes an eligible refreshed review directly to the deterministic
finalizer, preserving the existing FINALIZE decision, fresh-review requirement,
evidence/competition guards, STOP rules and budget audits. It does not convert a
failed API call into success or increase retry limits. The new event is
FINALIZE_RESUMED_AFTER_REVIEW.

Fault-injection and guard tests pass; saved v4 event-104 state also completes the
production finalization path with zero new API calls. The latter is an offline
forensic continuation, not a new complete live investigation. The saved final suite
result is 914 passed, 3 skipped. Details and artifacts:
[finalization acceptance](finalize-resume-20261015.md).

## ISSUE-7: Verifier `cited_evidence_ids` mismatch on a completed review is a fatal `RuntimeError`, not a retryable/repairable defect

### Symptom (2026-10-17 t6-real-2, incident_2002 negative retest)

Run `results/v16/t6-closure/20261016-static-01/t6-real-2/` ended `UNRECOVERABLE_ERROR / FAILED`
at the verify stage with `stop_reason: "Verifier cited unshared evidence"`, after
5 rounds, 24 LLM calls and 21 tool calls. Two `logs_backend_2002_011` diagnosis
calls had already burned two `PROVIDER_TIMEOUT` attempts (~423s each). This is a
third, distinct failure mode from the historical loop and transport cases:
the model completed a full review call and only the evidence citation check failed.

### Observed evidence

- event-129 `fetch_evidence_by_ids` returned exactly 4 records:
  `incident_2002-E-004`, `incident_2002-E-001`, `incident_2002-T-backend`, `incident_2002-T-gateway`.
- event-133 `LLM_CALL` for the review **succeeded** (29,244 tokens, 89s,
  `tokens_complete: true`) — the model produced a well-formed review.
- event-134 `RUNTIME_ERROR` `RuntimeError("Verifier cited unshared evidence")`,
  stage `verify`, `transport_error: false`. The run died despite the review call
  itself succeeding.

### Root-cause chain (current code)

1. `graph.py` `verify()` (~L980-988) fetches shared evidence through the verifier
   ACL with `{"ids": list(state.evidence_index)[:50]}` — all 4 public IDs were fetched.
2. The review model call succeeds; then `graph.py` (~L1040-1043) hard-checks
   `review.cited_evidence_ids ⊆ {record.evidence_id for record in result.records}`
   and raises a bare `RuntimeError` on any mismatch.
3. The raised error escapes the `while True` retry loop because the citation check
   sits **outside** the try/except that wraps `self.model_call(...)` — it is neither
   retried nor repaired, and is not an evidence/competition guard that would justify
   failing closed on a protocol violation.
4. `evaluation/termination.py` records the exception as
   `UNRECOVERABLE_ERROR / FAILED` (`diagnosis_failure: true`), even though the
   underlying diagnosis was on track to abstain normally.

The citation check enforces a content constraint on model output (which IDs the
model chose to cite) — the same class of defect as a schema violation, which the
structured-output pipeline repairs rather than kills the run for. Treating it as
`RuntimeError` converts one plausible model slip into whole-investigation failure.

### Expected behavior (fix requirements)

- A citation mismatch on a completed review must be handled like a structured
  repairable defect (targeted repair/retry within existing bounded retry budget),
  or degrade gracefully (e.g. drop the unshared citations and record a warning),
  never raise an unguarded `RuntimeError`.
- Protocol-borne guards (evidence/competition/finalization) keep fail-closed semantics;
  model-cited metadata mismatches do not.

### Related run conditions (not the root cause)

- Two `PROVIDER_TIMEOUT` calls on `logs_backend_2002_011` consumed the task's
  2-attempt budget (ISSUE-4 class endpoint stall) but did not terminate the run.
- `result.json` shows `root_cause: null` / `INCONCLUSIVE` — no fabricated root cause.

### Post-fix retest (2026-10-17 t6-real-3, incident_2002)

The ISSUE-7 fix (dynamic `Literal` citation binding + `ProviderError` repair path +
empty-changes-scope guard) held under live load: zero `REVIEW_CITATION_VALIDATION`
violations, zero fabricated root cause, investigation progressed through 3 review
cycles requesting genuinely discriminating checks instead of looping. The run still
ended `UNRECOVERABLE_ERROR / FAILED` (`failure_stage: coordinate`), but purely from
the ISSUE-4 endpoint stall class: `coordinate-4` consumed both task attempts on
two consecutive `PROVIDER_TIMEOUT` calls (~423s each; events 138/145), then
`RUNTIME_ERROR` at event 148. `result.json` `stop_reason: PROVIDER_TIMEOUT`.
No code defect remains in this failure chain; a healthy endpoint is required for
the negative-case abstention acceptance.

## References

- Real readiness probe (healthy): `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/readiness.json`
- Pilot scope/protocol: `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/pilot-scope.json`
- Earlier budget16 batch (retained for budget-sensitivity comparison):
  `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot/runs/`
- Stop-protocol invariants: `docs/acceptance/stop-protocol-v2.md`
- ISSUE-6 run (wall3600/req300 retest, converged then transport-timeout failure):
  `results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/`
  (`freeze/manifest.json`, `verifier-preflight/`, `full/`)
