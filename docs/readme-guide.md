# IncidentLens Operations and Configuration Guide

[简体中文](readme-guide.zh-CN.md) | **English**

This guide contains the operational detail moved out of the English README. The README keeps the project overview and common entry points; this page documents cost-aware evidence selection, runtime and budgets, providers, evidence permissions, and the local explanation cache.

## Cost-Aware Evidence Selection (CAES)

CAES runs in the `full` variant after the Coordinator returns `INVESTIGATE` and before selected tasks execute. It does not bypass `FINALIZE`, `ABSTAIN`, the Verifier, or FinalizeGate, and it never reads the private Oracle. Candidate generation and scoring make no model or tool call.

| Policy | Behavior |
| --- | --- |
| `current_dynamic` | Default; execute the Coordinator's original assignments and bypass CAES. |
| `first_eligible` | Select feasible candidates in generator order. |
| `active_no_cost` | Remove the request/tool cost denominator; hard budgets still apply. |
| `active_no_discrimination` | Remove the discrimination weight while retaining gaps, gate contribution, redundancy, and cost. |
| `active_evidence` | Rank with discrimination, gap coverage, gate contribution, redundancy, and cost. |

CandidateGenerator combines Coordinator proposals, published Verifier checks, and public role templates, with a default pool limit of six. ActionScorer estimates discrimination between published hypotheses, open-question coverage, missing evidence sources, repeated signatures, planned requests, and tool calls. The Selector chooses at most two feasible tasks. With no useful action it returns `NO_USEFUL_ACTION`, allowing a safe abstention instead of an empty loop.

```yaml
investigation:
  selection_policy: active_evidence
  shadow_enabled: false
  active_evidence:
    policy_version: caes-v1
    candidate_pool_limit: 6
    max_selected_tasks: 2
    discrimination_weight: 0.4
    gap_weight: 0.3
    gate_weight: 0.3
    redundancy_weight: 0.3
    request_weight: 1.0
    tool_weight: 0.25
    reserve_verifier_requests: 1
    reserve_verifier_tools: 1
```

The weights in the default example are development starting values, not calibrated research parameters. The score is a heuristic, not calibrated information gain or a probability of success. Uniform fallback costs can make `active_no_cost` and full CAES rank candidates identically. Cold start has no usable discrimination and falls back to a public role order. Physical retry multipliers, Verifier reserves, STOP, wall-clock limits, and token budgets take precedence over a selection score.

`--shadow-caes` records recommendations while executing the Coordinator assignments. Explicit policies, Shadow, and replay require `--variant full`. Observation failures fall back to the original proposal. See the [CAES example configuration](../configs/active-investigation.example.yaml), [algorithm](v1.5/algorithm-spec.md), and [fairness protocol](v1.5/fairness-protocol.md).

```powershell
# Record recommendations without changing execution.
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --cache-mode off --shadow-caes --out results/caes-shadow

# Enable full CAES explicitly.
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --cache-mode off --selection-policy active_evidence --out results/caes-active

# Replay saved selection without model or tool calls.
.venv\Scripts\python.exe scripts/replay_v15_selection.py --trace results/caes-active/trace.json
```

## Runtime and budgets

All roles execute in one LangGraph `StateGraph` with centralized runtime coordination. Investigators return local results. Merge validates task identity, role, actual-query ledger, and evidence provenance before publishing to the shared evidence board. The Coordinator receives published state; the Verifier fetches only authorized shared records; FinalizeGate rejects rejected candidates, unresolved blockers, competing hypotheses, and missing causal support.

TaskManager bounds task attempts. StopController freezes tasks and tools, cancels in-flight work, and waits for acknowledgements. Reporter is deterministic. Merge, Verifier, FinalizeGate, and Reporter are runtime components, not additional LLM agents. Tree-shaped agent communication is unsupported.

| Configuration | Workflow | Rounds | Tool calls | Model requests | Total time |
| --- | --- | ---: | ---: | ---: | ---: |
| [system.yaml](../configs/system.yaml) (default) | `legacy_rca` | 4 | 12 | 16 | 600 seconds |
| [incident-response.yaml](../configs/incident-response.yaml) | `incident_response` | 6 | 24 | 24 | 600 seconds |

The response configuration also limits Monitoring to eight calls, Remediation to two calls, each task to two attempts, and stop acknowledgement to five seconds. Phase budgets share global limits. JSON repair, transport retries, and physical requests count toward actual request usage. CLI flags override configuration.

`--max-tokens` checks the limit before starting another request. After measured usage reaches the cap, no new request starts, but an in-flight response may exceed it. Missing provider usage remains unknown rather than being recorded as zero. Exhausting wall-clock, round, request, tool, or token budgets is a runtime failure; ordinary evidence insufficiency should end as `INCONCLUSIVE`.

Diagnosis, remediation, and workflow states are separate:

- Diagnosis: `RESOLVED`, `INCONCLUSIVE`; the legacy report contract also permits `ERROR`.
- Remediation: `NOT_STARTED`, `PLAN_READY`, `PLAN_FAILED`, `SKIPPED`.
- Workflow: `RUNNING`, `STOPPING`, `FINISHED`, `FAILED`.

`PLAN_READY` means a proposal exists, not that a production service recovered. See the [investigation protocol](protocol.md) for stop and scoring contracts.

## Providers and configuration

Copy [`.env.example`](../.env.example) to a project-local `.env`. Real mode requires explicit configuration:

| Variable | Meaning |
| --- | --- |
| `INCIDENT_LENS_PROVIDER` | `mock` or `real` |
| `INCIDENT_LENS_BASE_URL` | OpenAI-compatible Chat Completions base URL or full endpoint |
| `INCIDENT_LENS_API_KEY` | Local secret; never export, commit, or include in artifacts |
| `INCIDENT_LENS_MODEL` | Provider model identifier |
| `INCIDENT_LENS_RESPONSE_FORMAT` | `json_schema` or `json_object` |
| `INCIDENT_LENS_THINKING` | Optional; `enabled` or `disabled` |
| `INCIDENT_LENS_REQUEST_TIMEOUT` | Per-request timeout in seconds; default 180 |

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider real --out results/real001
```

The default `json_schema` mode requires server support for strict JSON Schema. For a JSON-object endpoint, select `--response-format json_object` explicitly. Both modes validate against the same local Pydantic contract. Format precedence is CLI `--response-format`, then environment, then the enabled recovery capability setting. The runtime never automatically changes format, model, or provider.

Missing configuration, incompatible endpoints, authentication failures, rate limits, timeouts, and transport errors are classified explicitly. `real` never falls back silently to Mock. HTTP fixture tests validate adapter behavior, not online endpoint compatibility. Mock is a deterministic policy over public evidence; it never reads private labels or looks up answers by incident ID. Its output does not establish real-model quality or architectural superiority.

### Provider recovery

`provider_recovery.enabled` defaults to `false`, retaining the legacy path with at most one structured repair. When explicitly enabled, the runtime classifies and retries transient HTTP/network failures within request, wall-clock, and stage budgets, and performs at most one targeted syntax or schema repair. Every physical dispatch, including a transport retry or repair, consumes a request permit. STOP cancels backoff; domain, citation, and finalization guards remain authoritative.

```yaml
provider_recovery:
  enabled: true
  format_capability: json_object
  max_transport_retries: 2
  max_structured_repairs: 1
  max_physical_attempts_per_call: 4
  min_request_time_seconds: 5.0
```

Recovery never converts missing usage to zero or rewrites a provider failure as evidence-based abstention. Diagnostic events retain safe failure categories and attempt identifiers. Older traces remain readable. See [LLM and cache internals](code_wiki/07-llm-and-cache.md) for failure classification, recovery decisions, and usage accounting.

Real reliability experiments can incur provider charges and require fresh output directories. Deterministic fault injection and separately recorded real compatibility pilots are:

```powershell
.venv\Scripts\python.exe scripts/run_reliability_eval.py --out results/v13-eval/NEW-ID
.venv\Scripts\python.exe scripts/run_v13_pilot.py --out results/v13-eval/NEW-PILOT --response-format json_schema
.venv\Scripts\python.exe scripts/analyze_v13_pilot.py --source results/v13-eval/NEW-PILOT --out results/v13-eval/NEW-ANALYSIS
```

Offline fault recovery does not establish live RCA accuracy or targeted-repair quality. See [runtime contracts](v1.3/contracts.md) and the [evaluation protocol](v1.3/evaluation_protocol.md).

## Evidence and permissions

The dataset contains the original 6 Seed, 10 Dev, and 20 held-out synthetic cases, plus `incident_037`–`incident_040` in a separate [database set](../data/splits/database_ids.json), for 40 cases total. Existing splits remain frozen. Added cases cover connection exhaustion, application pool misconfiguration, lock contention, slow queries, and insufficient evidence. Synthetic templates are not an independently collected production benchmark; missing-evidence cases require a normal abstention. See [data documentation](../data/README.md).

All business tools are read-only:

| Evidence domain | Tools |
| --- | --- |
| Logs | `query_logs` |
| Metrics / Dependencies | `query_metrics`, `get_dependencies` |
| Changes / Config | `query_changes`, `get_config_diff` |
| Database | `get_db_connections`, `get_db_active_sessions`, `get_db_lock_waits`, `get_db_slow_queries`, `get_db_health_metrics` |
| Shared evidence | `fetch_evidence_by_ids` |

ToolRegistry treats the role ACL as an upper bound. `InvestigationTask.allowed_tools` can narrow it further. Fair architecture comparisons may explicitly enable `database_equivalent_tools` for equivalent Metrics and Single database access. The server issues immutable `AgentContext` objects that bind role, workspace, incident, run, and remaining tool budget.

Successful tool results enter that context's observed ledger. Merge publication and Verifier access can reference only records actually observed in the current run and then published. Public files use a fixed filename allowlist that rejects private truth, traversal, symlinks, and Windows junctions. Evidence excerpts are treated as untrusted data. Application isolation is not an operating-system Python sandbox.

New tools require coordinated updates to argument schemas, read-only implementations, role ACLs, path allowlists, and tests for authorization, budgets, and timeouts. See [tools and security boundaries](code_wiki/06-tools-and-security.md).

## Local explanation cache

The cache is off by default. Architecture comparisons must force `cache=None`. Only local explanations from these investigator task types are reusable:

- `summarize_log_slice`
- `interpret_metric_window`
- `summarize_change_diff`
- `interpret_database_window`

Monitoring, Coordinator routing, Verifier review, remediation, FinalizeGate, reports, and tool queries always execute. Before a hit, the current run must have actually queried the current evidence. A hit may cite only records in that evidence snapshot, and finding, task, and run identities are rebound before Merge.

| Mode | Behavior |
| --- | --- |
| `off` | Neither read nor write. |
| `exact` | Normalized exact question match. |
| `semantic` | Local embedding cosine plus conservative textual equivalence. |

```powershell
$env:CACHE_MODE = 'semantic'
$env:CACHE_SIMILARITY_THRESHOLD = '0.95'
$env:CACHE_TTL_HOURS = '24'
$env:CACHE_EMBEDDING_MODEL = 'fake'
$env:CACHE_DB_PATH = 'results/cache.sqlite'
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --out results/cache-demo
```

Namespaces require an exact match on workspace, incident, role, task type, evidence snapshot hash, dataset revision, prompt version, model ID, model parameter hash, output schema, and ACL version. The task signature excludes the mutable task ID and question but retains filters and expected discriminators. Expired, malformed, citation-invalid, or digest-mismatched entries are invalidated.

`FakeEmbedder` is an offline test aid, not a learned semantic model. Optional `SentenceTransformerBackend` loads only explicitly installed local weights; CI never downloads model weights. Even when cosine similarity is high, negation, number, comparison, or direction changes can reject reuse.

Measure cache benefits separately; architecture comparisons cannot enable the cache. Mock output establishes offline behavior only. Graph, tools, and embedding all contribute to latency, so local Mock timing cannot predict real-provider savings. See [cache design](cache.md) for implementation and invalidation rules.

```powershell
.venv\Scripts\python.exe scripts/run_cache_eval.py --provider mock --out results/cache-experiment
```

## Related documentation

- [Chinese operations guide](readme-guide.zh-CN.md)
- [Investigation protocol](protocol.md)
- [CAES algorithm](v1.5/algorithm-spec.md)
- [CAES fairness protocol](v1.5/fairness-protocol.md)
- [Tools and security boundaries](code_wiki/06-tools-and-security.md)
- [LLM and cache internals](code_wiki/07-llm-and-cache.md)
- [Cache design](cache.md)
- [Data documentation](../data/README.md)
- [IncidentBench test guide](incidentbench/README.md)
