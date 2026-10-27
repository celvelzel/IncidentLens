# 12 · 关键类与函数速查

按模块分组列出公开类/函数签名（`#` 后为简洁说明或行号）。参数省略号表示其余参数。

## 1. 编排层 `orchestration/`

### 1.1 `graph.py`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `GraphState` | `TypedDict(investigation, local_results, route)` | LangGraph 通道 |
| `InvestigationRun` | `__init__(provider, evidence_provider, incident_id, limits=None, variant="full", workspace_id="incident-lens", run_id=None, cache=None, workflow=None, journal=None)` **L43** | 单次运行的全部状态；内部装配 Registry、CallBudget、TaskManager、StopController |
| `.event` | `(state, event_type, role=None, source="runtime", message="", **details)` **L141** | 追加 trace 事件 |
| `.runtime_event` | `(event_type, **details)` **L159** | 无 state 的运行时事件 |
| `.consume_request` | `()` **L168** | 申请一次物理请求许可 |
| `.model_call` | `async (role, function, *args)` **L187** | 包办理预算 + 失败归一 + 停止快照 |
| `.stage_call` | `async (stage, function, *args)` **L244** | 阶段限额包装（monitoring/remediation） |
| `.monitor` | `async (value)` **L262** | 节点：监控 |
| `.payload` | `(state, role="coordinator", fetched=None)` **L310** | 构造裁剪后的角色 payload |
| `.candidate_assessments` | `(state)` **L399** | 候选的 grounding 评估 |
| `.board_fingerprint` | `(state)` **L417** | 共享板语义指纹（用于审查复用） |
| `.check_signature` | `(check)` **L428** | 请求检查的签名 |
| `.update_usage` | `(state, usage, role)` **L435** | 回写调用/token |
| `.exhausted` | `(state)` **L452** | 预算是否耗尽 |
| `.coordinate` | `async (value)` **L461** | 节点：协调决策 |
| `.investigate` | `async (state, task)` **L695** | 调查者的两阶段（plan → execute → analyze） |
| `.dispatch` | `async (value)` **L815** | 节点：并发/串行派发 |
| `.execute_task` | `async (state, task)` **L876** | 单任务执行与重试 |
| `.recoverable_task_error` | `(exc)` **L913** | 任务错误分类 |
| `.record_recovery` | `(record, stage)` **L928** | 记录恢复 |
| `.wait_for_retry` | `async (state, exc, task_id, stage)` **L976** | 有界退避 |
| `.retry_transient` | `async (state, task_id, role, stage, operation)` **L999** | 通用瞬时重试 |
| `.merge` | `(value)` **L1040** | 节点：合并 |
| `.verify` | `async (value)` **L1111** | 节点：审查 |
| `.finalize` | `(value)` **L1283** | 节点：确定性定稿 |
| `.remediate` | `async (value)` **L1345** | 节点：只生成计划 |
| `.stop` | `async (value)` **L1421** | 节点：统一终止 |
| `.rescue_report` | `(state)` **L1520** | 窄条件救援：全部 runtime 错误均为传输类 + 唯一可定稿候选 + 已有 sufficient 审查 |
| `.report` | `(value)` **L1584** | 节点：报告 + 最终校验 |
| `.compile` | `()` **L1623** | 构建 StateGraph |
| `.run` | `async ()` **L1667** | 执行图并返回 state |
| `run_investigation` | `async (incident_id, provider, data_root=Path("data"), budget=None, variant="full", workspace_id="incident-lens", run_id=None, cache=None, workflow=None, journal=None)` **L1677** | 顶层入口 |

### 1.2 `guards.py`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `review_fingerprint` | `(hypothesis) -> str` | 候选 JSON 的 SHA-256 |
| `evidence_fingerprint` | `(state) -> str` | 证据索引的稳定 SHA-256 |
| `cause_discriminator` | `(hypothesis, record) -> bool` | 7 类故障的保守判别 |
| `grounding_errors` | `(state, hypothesis) -> list[str]` | 引用/来源/判别器/未决问题 |
| `finalize_errors` | `(state, hypothesis, variant="full") -> list[str]` | 定稿总校验 |
| `reviewed_finalization_ready` | `(state, variant="full") -> bool` | 审查是否满足 |

### 1.3 `merge.py`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `merge_results` | `(state, results, registry) -> InvestigationState` | 唯一发布入口 |

### 1.4 `budget.py` / `permits.py` / `runtime.py` / `recovery.py`

| 符号 | 签名/字段 | 说明 |
| --- | --- | --- |
| `BudgetExceeded` | `(RuntimeError)` | 预算异常 |
| `CallBudget` | `consume_request(stage, run_id, logical_call_id)`, `call(fn, *args)`, `record_usage`, `snapshot()` | 物理请求/token/wall 记账 |
| `Permit` | `(logical_call_id, stage, run_id, issued_at, deadline)` | 单次许可 |
| `RequestPermitIssuer` | `issue_*`, `mark_dispatched`, `reconcile`, `snapshot(stage)` | 线程安全许可 |
| `RecoveryConfig` | 见 [07](07-llm-and-cache.md#51-recoveryconfig) | 恢复配置 |
| `RecoveryDecision` | `(action, reason, delay_seconds, ...)` | 恢复决策 |
| `stopped` | `(state) -> bool` | 是否已停止 |
| `decide_http_retry` | `(failure, config, ...)` | 重试判定 |
| `TaskManager` | `assign/start/complete/fail/cancel/stop` | 任务状态机 |
| `StopController` | `guard()`, `stop(reason, callbacks)` | 冻结与 ACK |
| `wait_for_retry` | `async (attempt, base_delay, max_delay, ...)` | 退避等待 |

### 1.5 `observability.py` / `report.py` / `config.py`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `RunJournal` | `append(event)` / `events` | JSONL 逐条写入 |
| `emit_event` | `(state, event_type, ...)` | 统一事件构造 |
| `TraceReader` | `events(...)`, `summary()` | 读取/过滤 trace |
| `observed_chain` | `(state, hypothesis) -> str` | 仅用已观测证据的因果链 |
| `render_report` | `(report) -> str` | 确定性 Markdown |
| `workflow_options` | `(config, *, profile=None, monitor_mode=None, snapshot=None) -> WorkflowOptions` | 配置 → 运行时选项 |

## 2. 角色层 `agents/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `prompt` | `(role) -> str` | 系统 + 角色提示词 |
| `tool_schemas` | `(names) -> dict` | 注入参数 schema |
| `ToolCall` | `(tool_name, args)` | 计划中的工具调用 |
| `InvestigatorPlan` | `(calls: list[ToolCall] ≤ 2)` | 工具计划 |
| `AnalysisOutput` | `(finding, hypotheses, requested_checks ≤ 2)` | 调查结论 |
| `DynamicDecision` | `CoordinatorDecision + assignments ≤ 2` | 动态决策 |
| `ReviewOutput` | `Review` 的生成约束 | sufficient 无阻塞检查 |
| `analysis_schema` | `(records) -> type[AnalysisOutput]` | 引用 ID 限定在实际记录 |
| `decide` | `async (provider, state_payload) -> ...` | 协调 |
| `verify` | `async (provider, state_payload) -> Review + usage` | 审查 |
| `plan_tools` | `async (provider, context, task, public_summary, minimal_facts)` | 规划工具 |
| `analyze` | `async (provider, context, task, records)` | 生成 finding/hypothesis |
| `monitor` | `async (provider, incident_id, records, mode)` | 监控 |
| `validate_alert` | `(alert, incident_id, records)` | 告警校验 |
| `root_cause_version` | `(report) -> str` | 根因 SHA-256 |
| `validate_plan` | `(plan, report, evidence_index)` | 计划校验 |
| `remediate` | `async (provider, report, evidence_index)` | 修复计划 |

## 3. 工具与安全 `tools/` `security/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `TimeWindow` | `(start_ts, end_ts)` + validator | 时间窗 |
| `LogsArgs` / `MetricsArgs` / `ChangesArgs` / `DatabaseArgs` / `FetchArgs` / `ConfigDiffArgs` / `DependenciesArgs` | 见 [06](06-tools-and-security.md#1-工具清单) | 参数模型 |
| `EvidenceProvider` | `list_cases()`, `load_case(id)`, `validate_public()`, `dataset_revision`, `_records(...)` | 公开只读数据 |
| `ScopedClient` | `(context, execute(tool, args))` | 角色受限执行器 |
| `ToolRegistry` | `create_context(...)`, `execute(context, tool, args)`, `observed_ids`, `get_observed_records`, `publish`, `freeze`, `call_count` | 工具中枢 |
| `AgentContext` | `workspace_id, incident_id, run_id, role, allowed_tools, allowed_evidence_scope, remaining_tool_calls` | 不可变上下文 |
| `ContextAuthority` | `issue(...)`, `validate(...)` | 签发与校验 |
| `RoleScopedEvidenceClient` | `Protocol[evidence(...)]` | 依赖注入契约 |
| `query_logs` / `query_metrics` / `get_dependencies` / `query_changes` / `get_config_diff` | `(provider, incident_id, args)` | 只读查询 |
| `get_db_connections` 等 5 个 | 工厂生成的 `(provider, incident_id, args)` | 数据库查询 |

## 4. LLM `llm/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `LLMProvider` | `structured_call(role, system_prompt, user_payload, output_model)` | 抽象接口 |
| `RealChatProvider` | `__init__(endpoint, api_key, model, **options)` **L51** | OpenAI 兼容 |
| `CodexSubscriptionProvider` | `__init__(...)` **L114** | CLI 订阅 |
| `MockProvider` | `model_id="deterministic-public-policy-v1"` **L281** | 确定性 Mock |
| `ProviderError` | `(code)` | 配置/调用错误 |
| `json_payload` | `(value) -> dict/list` | 递归 JSON 化 |
| `output_messages` | `(system_prompt, user_payload, schema)` | 结构化消息 |
| `strict_schema` | `(output_model) -> dict` | 生成 strict JSON Schema |
| `validate_response` | `(data, output_model) -> Model` | 响应校验 |
| `StructuredOutputError` | `(category, phase, ...)` | 输出错误 |
| `repair_message` | `(error) -> str` | 修复指令 |
| `classify_http` | `(status_code, headers=None, sanitized_error_code=None, **ctx) -> FailureInfo` | HTTP 分类 |
| `classify_transport` | `(exc, **ctx) -> FailureInfo` | 传输分类 |
| `compute_backoff` | `(attempt, retry_after, config, rng=None) -> float` | 退避 |
| `provider_options` | `(response_format=None, thinking=None, request_timeout=None) -> dict` | 本地传输选项 |
| `token_value` / `normalize_usage` / `begin_request` / `record_usage` / `refresh_usage` / `aggregate_usage` | usage 记账 | 见 [07](07-llm-and-cache.md) |
| `safe_diagnostic` / `resolve_cli` / `inspect_auth` / `decode_events` | Codex CLI 辅助 | 安全诊断 |

## 5. 缓存 `cache/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `CachePolicy` | `(mode, similarity_threshold, ttl_hours, allowed_task_types)` | 策略 |
| `CacheNamespace` | 见 [07](07-llm-and-cache.md#93-命名空间) | 命名空间 |
| `SemanticCacheAdapter` | `(policy, db_path, dataset_revision, embedder=None)` | 缓存适配器 |
| `.explain` | `async (context, task, records, registry, provider, execute_model_async, emit_callback)` | 查缓存或调用生成；命中结果重绑当前 task/run 身份 |
| `SQLiteCacheStore` | `candidates`, `put`, `record_hit`, `delete`, `close` | 存储 |
| `canonical_tokens` / `safe_equivalent` / `cosine` | 字符串/向量工具 | 语义安全 |
| `FakeEmbedder` / `SentenceTransformerBackend` | `encode(text)` | 嵌入后端 |

## 6. 契约 `schemas/`

| 符号 | 关键字段 |
| --- | --- |
| `StrictModel` | `extra=forbid`, `strict=True`, `validate_assignment=True` |
| `CasePublicInput` | `incident_id`, `title`, `started_at`, `observed_symptoms`, `services` |
| `EvidenceRecord` | 见 [05](05-data-contracts.md#31-evidencerecord) |
| `ToolResult` | `call_id`, `ok`, `records`, `error_code`, `elapsed_ms`, `record_count`, `next_cursor` |
| `InvestigationTask` | `task_id`, `role`, `question`, `allowed_tools`, `filters`, `reason`, `expected_discriminator` |
| `Finding` | `finding_id`, `task_id`, `run_id`, `incident_id`, `role`, `claim`, `evidence_ids`, `relation`, `confidence_qualifier`, `followup_question` |
| `Hypothesis` | `hypothesis_id`, `culprit_service`, `failure_mode`, `support_ids`, `against_ids`, `predicted_observations`, `status`, `open_questions` |
| `Review` | `target_hypothesis_id`, `verdict`, `contradictions`, `requested_checks`, `optional_checks`, `cited_evidence_ids`, `rationale` |
| `CoordinatorDecision` | `action`, `reason`, `assignments`, `hypothesis_updates`, `selected_hypothesis_id`, `stop_reason` |
| `RCAReport` | 见 [05](05-data-contracts.md#51-rcareport) |
| `Budget` | `max_rounds`, `max_tool_calls`, `max_llm_calls`, `max_wall_seconds`, `max_tokens` |
| `InvestigationState` | 见 [05](05-data-contracts.md#61-investigationstate) |
| `TraceEvent` | `event_id`, `run_id`, `incident_id`, `timestamp`, `event_type`, `role`, `task_id`, `call_id`, `evidence_ids`, `message`, `details`, `source`, `elapsed_ms` |
| `StopReason` / `TerminationResult` | 见 [05](05-data-contracts.md#23-stopreason) |
| `IncidentAlert` | `incident_id`, `status`, `summary`, `evidence_ids`, `affected_services` |
| `RemediationPlan` | `objective`, `affected_services`, `actions`, `preconditions`, `risks`, `verification_steps`, `rollback`, `evidence_ids` |
| `TaskRecord` | `task_id`, `attempt_id`, `role`, `attempt`, `status`, `error_code` |
| `StopMessage` | `incident_id`, `run_id`, `stop_reason`, `message_type`, `protocol_version`, `role` |
| `WorkflowOptions` | 见 [05](05-data-contracts.md#7-workflowoptions) |
| `PolicyConfig` | CAES 权重/阈值/上限 |
| `termination_result` | `(reason, failure_stage=None, stop_completed=True) -> TerminationResult` |

## 7. 评估 `evaluation/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `safe_file` | `(root, *parts)` | 拒绝链接/逃逸 |
| `load_split` | `(data_root, split)` | 读取分裂 |
| `load_oracle_after_run` | `(data_root, incident_id, state)` | 运行后加载 oracle |
| `MeasuredProvider` | `(delegate)` | 计量包装 |
| `usage_metrics` | `(provider, state)` | 对账 |
| `evaluate_split` | `async (data_root, split, variants, provider_factory, out, budget=None, provider_name="mock", jobs=1)` | 消融主流程 |
| `score_completed` | `(state, oracle)` | 有 oracle 评分 |
| `score_without_oracle` | `(state)` | 无 oracle 评分 |
| `aggregate` | `(rows)` | 聚合 |
| `citation_metrics` | `(state)` | 引用有效性 |
| `normalize_termination` | `(state)` | 三形态终止归一 |
| `technical_completion` | `(state)` | 技术完成 |
| `aggregate_reliability` | `(rows)` | 可靠性汇总 |
| `atomic_bytes` / `atomic_json` / `append_json` | 原子 IO | 产物安全 |

## 8. IncidentBench `incidentbench/`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `build_dataset` | `(config, out, oracle_root)` | 生成公开包 + oracle |
| `simulate` / `encode` | `(spec, variant)` / `(world, incident_id)` | 世界模型 |
| `validate_dataset` | `(dataset, oracle_root=None)` | 校验 |
| `normalize` | `(state)` | 评分行 |
| `OracleStore` | `(root)` + `read(...)` | 私有标签 |
| `ExperimentProtocol` | 见 [08](08-evaluation-and-benchmark.md#8-incidentbench-实验incidentbenchexperimentpy) | 实验契约 |
| `run_experiment` | `async (dataset, split, provider_factory, out, protocol, oracle_root=None)` | 实验 |
| `score_benchmark_run` | `(state, oracle=None, annotations=None)` | 打分 |
| `aggregate` | `(rows)` | 聚合 |
| `paired_comparison` | `(rows, baseline, metric="root_cause_correct", *, seed=14101, samples=10000)` | 配对 bootstrap |
| `analyze` | `(rows, *, seed=14101, samples=10000)` | 全指标 |
| `prepare_review_bundle` / `merge_reviews` / `review_coverage` | 人工复核 | 引用审查 |
| `evaluate_run` / `summarize` / `validate_completed` / `validate_acceptance` | readiness | 发布门禁 |
| `digest_tree` / `create_lock` / `verify_lock` / `label_commitment` / `seal_dataset` | manifest | 冻结 |

## 9. 接口 `web/` `ui/` `artifacts.py` `cli.py`

| 符号 | 签名 | 说明 |
| --- | --- | --- |
| `main` | `cli.main(argv=None)` | CLI 分发 |
| `save_run` | `(state, output, provider, variant="full", cache_mode="off", elapsed_ms=None)` | 三产物 |
| `validate_metadata` | `(trace)` | 信封校验 |
| `load_replay` | `(path) -> (trace, state)` | 只读重放 |
| `validate_replay_observations` | `(state)` | 观测绑定 |
| `reject_private_fields` | `(value)` | 拒绝评测字段 |
| `web.server.app` | `Starlette(routes=...)` | ASGI 应用 |
| `api_health` / `api_meta` / `api_cases` / `api_run` / `api_traces` / `api_replay` / `api_download` | `async (request)` | 路由处理 |
| `RunRequest` / `ReplayRequest` | Pydantic 请求模型 | 输入校验 |
| `ui.app.main` / `render_state` | `(trace, state)` | Streamlit |

## 10. 常量速查

| 常量 | 值 | 位置 |
| --- | --- | --- |
| `PROMPT_VERSION` | `roles-v12-evidence-reconciliation-v7-task-acl` | `agents/service.py` |
| `MockProvider.model_id` | `deterministic-public-policy-v1` | `llm/mock.py` |
| `PolicyConfig.policy_version` | `caes-v1` | `schemas/active_config.py` |
| 默认预算 | 4 / 12 / 16 / 600s | `configs/system.yaml` |
| 响应预算 | 6 / 24 / 24 / 600s | `configs/incident-response.yaml` |
| 缓存阈值 | 0.95，TTL 24h | `cache/policy.py` |
| 工具超时 | `min(10s, max_wall_seconds)`，默认 5s | `graph.py` → `ToolRegistry(timeout_seconds=...)` |
| 审查 fetch 上限 | 50 条 | `graph.verify` |
| 每轮最多任务 | 2 | `graph.coordinate` |
| Planning 工具调用上限 | 2 | `agents/service.py` |
| 统计默认 seed / samples | 14101 / 10000 | `incidentbench/statistics.py` |
