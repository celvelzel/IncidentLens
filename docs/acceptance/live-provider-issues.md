# Live-provider known issues — real-model run findings

Recorded 2026-10-14 during the first real-model evaluation of V1.4 on the COMP
On-Premises GenAI Platform (`DeepSeek-V4-Flash`, endpoint
`https://genai.comp.polyu.edu.hk/api/v1`). These issues are runtime error-handling
defects in the dispatch layer, exposed only by real-model runs; the offline mock
acceptance suite (723 passed) does not reproduce them. **PENDING FIX — not yet fixed.**

## ISSUE-1: Tool `NOT_FOUND` (empty service data) cascades into whole-investigation `UNRECOVERABLE_ERROR`

**Severity: High** — aborts otherwise healthy investigations; blocks reliable
real-provider evaluation.

### Symptom

A task whose evidence tool returns `NOT_FOUND` (the queried service simply has no
data in this case, a normal data gap) fails that task. When a sibling task in the
same parallel batch also fails (observed: a model call cancelled as
`PROVIDER_CANCELLED`), the dispatch layer escalates to
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
- Provider transport was healthy all run (9/9 requests returned normal structured
  output; `tokens_complete: true` before the cancellation).

Scoring record: `runs/scores.jsonl` ->
`failure_category: UNRECOVERABLE_ERROR`, `diagnosis_failure: true`, llm_requests 9.

### Root-cause chain (code)

1. `src/incident_lens/tools/registry.py:205,209` — empty/missing service data is
   returned as `error_code: "NOT_FOUND"` with `ok: false`.
2. `src/incident_lens/orchestration/graph.py:507-508` — any tool result with
   `ok: false` raises `RuntimeError("Tool failed: ...")`, turning a benign data
   gap into a hard task failure with no re-planning signal.
3. Parallel sibling failures plus un-recovered model failures
   (`graph.py:898-903`, `evaluation/termination.py:215`) upgrade the stop reason
   to `UNRECOVERABLE_ERROR` and abort the whole run.

### Why mock acceptance missed it

The mock provider/tools do not produce the `NOT_FOUND` + concurrent model-cancellation
combination. This class of defect is only observable in real-model dispatch runs,
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
accounting (tokens already streamed server-side are uncounted) should be
documented in the failure accounting contract. Same fix batch as ISSUE-1.

## References

- Real readiness probe (healthy): `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/readiness.json`
- Pilot scope/protocol: `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/pilot-scope.json`
- Earlier budget16 batch (retained for budget-sensitivity comparison):
  `results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot/runs/`
- Stop-protocol invariants: `docs/acceptance/stop-protocol-v2.md`
