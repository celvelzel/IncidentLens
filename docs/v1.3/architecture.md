# V1.3 architecture
Existing LangGraph, AgentService domain guards, TaskManager and StopController remain. RealChatProvider composes error taxonomy, bounded transport recovery and safe syntax/schema validation. Request permits are authorized by a per-run budget and immutable task-local stage. Logical calls, HTTP attempts, repairs and whole-task retries remain separate. Replay diagnostics add safe events only.
P0 baseline artifacts: results/v13-baseline/20261013-local. Worktree snapshot includes local uncommitted STOP v2 changes without altering original index or HEAD.

## Integrated modules

- `llm/errors.py`: exact safe error codes, taxonomy and Retry-After parsing.
- `llm/transport_retry.py`: pure bounded exponential backoff and injectable jitter.
- `orchestration/recovery.py`: validated flag/configuration, immutable snapshots and decisions.
- `orchestration/permits.py`: global/stage atomic reservation, dispatch, release and reconciliation.
- `llm/structured_output.py`: safe syntax/schema/truncation diagnostics and targeted correction.
- `llm/capabilities.py`: explicit immutable capability declaration.
- Lead integrates existing provider, CallBudget, graph, CLI and measurement wrapper.
- `evaluation/reliability_metrics.py`: denominator-preserving offline metrics and terminal technical completion.

No new runtime agents, tools, remediation writes, private oracle inputs, benchmark datasets or V1.4/V1.5 behavior were introduced. Proposal identity binding was deferred; the existing evidence gates stay authoritative.
