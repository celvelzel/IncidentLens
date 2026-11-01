# Implementation dependencies and ownership

P0 is the frozen-contract gate. Lead owns packaging, schemas, security context,
graph, merge, budget, CLI and integration. Data & Tools owns data, tools,
authorization and dataset scripts. Agent Implementation owns agents, llm,
prompts and local explanation cache adapters. Evaluation owns baselines,
metrics and benchmark scripts. UI owns Streamlit views and replay presentation.
Independent QA is read-only and reviews gates before release.

P0 -> P1 public datasets/RBAC -> P2 provider/roles -> P3 dynamic graph -> P4 CLI/E2E.
P4 -> P5 baselines/cache experiments -> P6 trace UI -> P7 independent acceptance.
Data and Agent implementation can work independently against frozen contracts;
parallel writes must use isolated Git worktrees. Evaluation/UI integration
waits for the actual backend artifacts. At most three coding workers are live.

No runtime module may read private ground truth. Baseline comparisons disable
cache. Semantic caching is limited to the three local explanation task types.
Real provider results require real calls and are never substituted by Mock.
Human contribution assignments in the source specification are proposed;
generated code is not evidence of those students' personal contributions.

## Frozen task packets for subsequent phases

| Phase / owner | Write scope | Required predecessor / gate |
| --- | --- | --- |
| P1 Data & Tools | data/**, tools/**, security/authorization.py, scoped_client implementation, scripts/generate_cases.py, validate_dataset.py, tests/isolation/** | P0 schemas; five seed packs, neutral IDs, evaluator-only oracle, 10+ ACL tests, runtime-issued identities, role/run query ledger, max 50 records |
| P2 Agent Implementation | llm/**, agents/**, prompts/**, tests/unit/test_provider* and test_agents* | P0 types + P1 tools; five structured roles, real provider explicit configuration, one JSON repair, ID validation, offline Mock |
| P3 Lead / Integrator | orchestration/**, integration tests | P1/P2; compiled StateGraph, dynamic dispatch, single Merge publisher, independent challenge changes next task, bounded budgets, missing-data abstention |
| P4 Lead + Agent cache owner | cli.py, cache/{semantic,store,embeddings}.py, scripts/run_demo.py, tests/cache/** | P3; mock E2E artifacts/replay, real mode no silent fallback, SQLite WAL cache with exact namespace and post-hit grounding |
| P5 Evaluation | evaluation/**, scripts/run_eval.py, evaluation tests | P4; strong single/fixed/no-verifier/full actually executed, cache off, private oracle read only after completed run, measured denominators/costs, separate cold/warm cache experiment |
| P6 UI | ui/**, docs/demo.md, UI tests | P4/P5 backend; Streamlit timeline/hypothesis/report, labeled replay, permission and cache events, no duplicated graph logic |
| P7 Independent QA + file owners | reviewer read-only; owners fix within original scopes | All predecessors; security/cache/failure/concurrency tests, fresh install, complete docs and honest evidence limitations |

### Runtime integration contracts to enforce

Data worker implements `ToolRegistry.execute(context, tool_name, args) ->
ToolResult` with immutable contexts issued by its server-owned factory; the
factory's issuer ledger must reject forged/replaced contexts, foreign runs and
foreign incidents. `RoleScopedEvidenceClient.execute` exposes no filesystem
handle. Runtime owns `observed_ids` by role/run and `shared_ids` by run.
Grounding validator must check actual-query ledger, not only matching strings.

Agent worker implements `async structured_call(role, system_prompt,
user_payload, output_model) -> (validated_model, usage_metadata)`. Context is
constructed by runtime and never accepted from LLM JSON. Worker has no shared
state mutation capability; it returns task-local structured outputs only.
Identity fields are stamped and checked by runtime. Investigator context
contains its assignment, minimal shared facts and its own returned evidence.

Lead exposes a single backend `run_investigation` service to CLI/evaluation/UI;
only LangGraph drives the actual core loop. Source roots and private files are
not passed to Coordinator/Provider. Merge validates identity/task/provenance
before publishing. Provider timeout and every retry consume recorded budgets.
Standalone replay reconstructs recorded state without provider calls.

Each worker packet must name exact predecessor revision, allowed write scope,
tests, return files/commands/results and uncertainties. Workers cannot spawn
other workers. At most three workers run; parallel writers use isolated Git
worktrees and the Lead integrates/retests each patch. UI never precedes P3.

Real-model experimentation is contingent on explicit endpoint/model credentials
and successful structured output compatibility; absent credentials produce a
reported limitation, never fabricated baseline metrics. Hidden test data is
frozen separately and must not be used for prompt tuning.
