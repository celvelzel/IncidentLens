# Frozen contracts v1

The project uses Pydantic v2 `extra=forbid`, strict Python validation, and
`model_validate_json` for JSON input. Use JSON parsing for ISO timestamps and
tuple fields; Python constructors require actual timezone-aware datetimes and
tuples. Exported machine-readable contracts are in `docs/contracts/`.

ASSIGNMENT -> FINDING / EVIDENCE REF -> REVIEW -> DECISION.
InvestigationTask carries role, permitted tool declarations, filters, reason
and expected discriminator. Finding carries runtime-stamped run/incident/task
identity and evidence IDs. Worker results cannot directly publish shared state.
The implemented MergeNode validates the complete batch, tasks, actual role/run
queries and evidence origin before publication. Schema validation checks IDs,
provenance and references; the runtime ledger supplies actual-query proof.
Neither layer alone proves semantic support.

| Role | Executable tool allowlist |
| --- | --- |
| coordinator | none |
| logs | query_logs |
| metrics | query_metrics, get_dependencies |
| changes | query_changes, get_config_diff |
| verifier/reporter | fetch_evidence_by_ids, shared records only |
| single | dedicated baseline identity with union of the six tools |

Reporter is a deterministic formatter, not an extra LLM. AgentContext is a
frozen authority descriptor. P1 must issue contexts at runtime and match them
against a server-owned ledger; accepting a caller-created equal-valued context
is not adequate role authentication. The server owns the total run budget.

Read-only signatures:

```python
query_logs(service, start_ts, end_ts, severity=None, contains=None, limit=50)
query_metrics(service, metric_names, start_ts, end_ts)
get_dependencies(service=None)
query_changes(service=None, start_ts=None, end_ts=None, change_type=None)
get_config_diff(change_id)
fetch_evidence_by_ids(ids)
RoleScopedEvidenceClient.execute(tool_name, args) -> ToolResult
```

P1 arguments must be independently validated with Pydantic. ToolResult has
call_id/ok/records/error_code/elapsed_ms/record_count/next_cursor; failures have
no records. Maximum return size is 50, applied by the runtime, with stable IDs.
Required runtime errors: FORBIDDEN, BAD_ARGS, NOT_FOUND, TIMEOUT, BUDGET_EXCEEDED.
Private truth is available exclusively to dataset generation/evaluation.

Final report statuses: RESOLVED / INCONCLUSIVE / ERROR. A RESOLVED schema alone
does not certify correctness. Full-system FinalizeGate requires two distinct
source records, a discriminating check, valid currently observed citations,
sufficient verifier review and no outstanding critical contradiction.
Single and no-verifier experiments retain the same grounding/discrimination
requirements with explicit self-reflection/deterministic acceptance gates;
they cannot invent an independent verifier verdict.

CachePolicy allows summarize_log_slice, interpret_metric_window and
summarize_change_diff only. Lookup order is authorize -> snapshot -> strict
namespace -> similarity -> TTL/schema/current-role observation grounding.
CacheNamespace intentionally excludes run_id: reuse still requires the current
run to have actually observed every cited record. Namespace includes workspace,
incident, role, task, evidence SHA256, dataset revision, prompt version, model
identifier/parameters SHA256, schema version and ACL version. Coordinator,
Verifier and report are uncached. Fake embeddings are test fixtures only.

Default Budget: 4 rounds, 12 tools, 16 LLM calls, 90 seconds, optional token cap.
P2 structured repair is bounded to one retry; usage counts include retries.
TraceEvent stores public decisions/usage summaries, never hidden reasoning or
secrets; runtime sanitization remains a P2/P3 obligation.
