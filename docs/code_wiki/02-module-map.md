# 02 · 模块地图

## 1. 仓库目录结构

```text
incidentlens/
├── src/incident_lens/          # 主包（约 14.5k 行 Python）
│   ├── orchestration/          # LangGraph 工作流、预算、Gate、Merge、恢复、CAES
│   ├── agents/                 # 角色实现与提示词绑定
│   ├── tools/                  # 只读工具实现 + 注册表 + 证据加载
│   ├── security/               # AgentContext 签发、ACL、scoped client
│   ├── llm/                    # Provider 抽象、HTTP/Codex 实现、结构化输出
│   ├── cache/                  # 语义缓存（SQLite + 嵌入）
│   ├── schemas/                # Pydantic 契约与状态机
│   ├── evaluation/             # 消融评估、指标、终止协议、active evidence
│   ├── incidentbench/          # IncidentBench 数据集构建/校验/实验/打分
│   ├── web/                    # Starlette API + 原生 JS SPA
│   ├── ui/                     # 可选 Streamlit 界面
│   ├── artifacts.py            # result/report/trace 读写与 replay
│   └── cli.py                  # 命令行入口
├── configs/                    # system / incident-response / agents / model / protocol
├── prompts/                    # 6 个角色提示词的静态镜像（人工审阅用，运行时以 agents/service.py 为准）
├── data/                       # 40 个事故案例 + 拓扑 + splits + IncidentBench 数据
├── docs/                       # 设计文档、协议、阶段计划、本 Wiki
├── tests/                      # 单元 / 集成 / 评估 / 基准 / 前端测试
├── scripts/                    # 评估、数据生成、验收、审计脚本
├── analysis/wp_d/              # 历史实验快照与审计报告（数据，不是运行时依赖）
├── results/                    # 运行产物与缓存（git 忽略内容）
├── .github/workflows/          # CI（ruff + pytest + Playwright）
├── pyproject.toml              # 依赖、可选依赖、脚本入口、pytest 配置
├── requirements.lock           # CI 使用的冻结依赖
└── package.json                # 仅用于前端测试（Playwright），非运行时依赖
```

> 注意：`prompts/*.md` 与 `agents/service.py` 中的 `SYSTEM_PROMPT` / `ROLE_PROMPTS` 内容重复，两者需要手工同步；运行时**只读** `service.py`。

## 2. 包级职责

| 包 / 文件 | 行数量级 | 职责 | 对外关键符号 |
| --- | --- | --- | --- |
| `orchestration/graph.py` | 1705 | 工作流全部节点、状态转换、`run_investigation` | `InvestigationRun`, `run_investigation`, `WorkflowOptions` |
| `orchestration/guards.py` | 167 | Grounding / Finalize 确定性验收、因果判别器、指纹 | `grounding_errors`, `finalize_errors`, `review_fingerprint`, `evidence_fingerprint`, `cause_discriminator` |
| `orchestration/merge.py` | 101 | 校验调查结果身份/引用/ID 后发布 | `merge_results` |
| `orchestration/budget.py` | 109 | 轮数/工具/LLM/wall/token 预算与快照 | `CallBudget`, `BudgetExhausted` |
| `orchestration/permits.py` | 124 | 逻辑调用 → 物理请求许可、恢复预算 | `RequestPermitIssuer`, `RequestPermit` |
| `orchestration/runtime.py` | 161 | 任务并发、取消、STOP 冻结、重试等待 | `TaskManager`, `StopController`, `wait_for_retry` |
| `orchestration/recovery.py` | 138 | 失败分类与恢复决策 | `RecoveryAction`, `RecoveryPolicy`, `classify_failure` |
| `orchestration/config.py` | 178 | YAML 加载、预算推导、数据根解析 | `load_config`, `load_environment`, `BudgetLimits` |
| `orchestration/observability.py` | 194 | 统一事件流（NODE/AGENT/TASK/TOOL_CALL/STOP…） | `emit_event`, `TraceWriter`, `TraceReader` |
| `orchestration/report.py` | 128 | 确定性 Markdown 报告渲染 | `render_report` |
| `orchestration/active_investigation/` | ~1100 | CAES：候选生成、成本估计、特征、资格、策略、选择 | `select_task_candidates`, `CaesPolicy` |
| `agents/service.py` | 400 | 协调/调查/审查/定稿/修复的提示词与 I/O 绑定 | `CoordinatorService`, `VerifierService`, `FinalizerService`, `RemediationService` |
| `agents/monitoring.py` | 136 | 监控告警识别、快照/回放 | `MonitoringService` |
| `agents/remediation.py` | 141 | 修复计划生成、风险分级 | `RemediationService` |
| `agents/database.py` | 76 | 数据库域提示与证据选择 | `DatabaseAgent` |
| `tools/registry.py` | 241 | 工具执行、ACL、参数校验、账本、共享 fetch | `ToolRegistry`, `ToolResult` |
| `tools/provider.py` | 242 | 从 `data/` 加载公开证据，路径白名单 | `LocalEvidenceProvider` |
| `tools/arguments.py` | 92 | 各工具参数模型 | `LogsArgs`, `MetricsArgs`, `ChangesArgs`, `FetchArgs`, `DatabaseArgs` |
| `tools/logs.py` / `metrics.py` / `changes.py` / `database.py` | 各 ~100-250 | 具体只读查询实现 | `query`, `query_metrics`, `query_changes`, `query_database` |
| `security/context.py` | 33 | 角色枚举与 `ROLE_TOOL_ACL` | `AgentContext`, `ROLE_TOOL_ACL`, `DATABASE_TOOLS` |
| `security/authorization.py` | 40 | 签发与校验 context | `ContextAuthority` |
| `security/scoped_client.py` | ~90 | 只读证据的 scoped 视图 | `ScopedEvidenceClient` |
| `llm/provider.py` | 623 | Provider 接口、HTTP 实现、重试/修复 | `LLMProvider`, `RealChatProvider`, `ProviderError` |
| `llm/mock.py` | 586 | 确定性 Mock 策略 | `MockProvider` |
| `llm/structured_output.py` | 168 | 单一结构化提示、schema 校验、修复指令 | `build_structured_prompt`, `validate_output`, `StructuredOutputError` |
| `llm/errors.py` | 159 | HTTP/传输错误分类 | `FailureInfo`, `classify_http_error`, `classify_exception` |
| `llm/capabilities.py` | ~80 | 模型能力 profile | `CapabilityProfile` |
| `llm/transport_retry.py` | ~40 | 指数退避 + jitter | `compute_backoff`, `decide_http_retry` |
| `llm/usage.py` | ~80 | token usage 归一/记录/聚合 | `usage_from_response`, `record_usage` |
| `llm/codex_subscription.py` | 296 | Codex CLI 订阅接入 | `CodexSubscriptionProvider` |
| `cache/semantic.py` | 264 | 命名空间、命中校验、事件 | `SemanticCache`, `build_namespace` |
| `cache/store.py` | 120 | SQLite 持久化 | `CacheStore` |
| `cache/embeddings.py` | 128 | 分词、等价性、嵌入后端、余弦 | `tokenize`, `cosine`, `HashingEmbedder`, `SentenceTransformerBackend` |
| `cache/policy.py` | 40 | 模式、阈值、TTL | `CachePolicy`, `CacheMode` |
| `schemas/contracts.py` | 328 | **全部核心模型**：证据/任务/分析/审查/决策/报告/预算/状态/事件 | `StrictModel`, `EvidenceRecord`, `InvestigationTask`, `Finding`, `Hypothesis`, `Review`, `CoordinatorDecision`, `RCAReport`, `InvestigationState`, `TraceEvent` |
| `schemas/workflow.py` | 162 | 工作流增量契约（V1.2/v2）：终止、告警、计划、任务记录、`WorkflowOptions` | `StopReason`, `TerminationResult`, `IncidentAlert`, `RemediationPlan`, `TaskRecord`, `StopMessage`, `WorkflowOptions` |
| `schemas/active_config.py` | 57 | CAES 配置（独立于 contracts，避免循环依赖） | `PolicyConfig`, `PolicyName` |
| `schemas/incident.py` | 3 | 兼容性 re-export | `CasePublicInput` |
| `schemas/evidence.py` | 3 | 兼容性 re-export | `EvidenceRecord`, `ToolResult` |
| `schemas/state.py` | 3 | 兼容性 re-export | `Budget`, `Budgets`, `InvestigationState`, `TraceEvent` |
| `schemas/report.py` | 3 | 兼容性 re-export | `RCAReport` |
| `schemas/agent_io.py` | 3 | 兼容性 re-export | `CoordinatorDecision`, `Finding`, `Hypothesis`, `InvestigationTask`, `Review` |
| `evaluation/*` | ~2600 | 评估、指标、终止校验、v16、可靠性 | `run_evaluation`, `score_completed`, `aggregate` |
| `incidentbench/*` | ~4000 | 基准构建、校验、实验、打分、统计 | `build_dataset`, `validate_dataset`, `run_experiment`, `score_state` |
| `web/server.py` | 385 | HTTP API + 静态服务 | `app`, `api_run`, `api_replay` |
| `ui/app.py` | 340 | Streamlit 面板 | `main` |
| `artifacts.py` | 133 | 产物保存/加载/重放 | `save_run`, `load_replay`, `load_trace` |
| `cli.py` | 299 | 7 个子命令 | `main` |

## 3. 子包内部结构

### `orchestration/active_investigation/`（CAES）

| 文件 | 作用 |
| --- | --- |
| `contracts.py` | `TaskCandidate`, `CandidateScore`, `SelectionDecision`, `CaesConfig` |
| `candidate_generator.py` | 按角色枚举可选任务（服务 × 证据域） |
| `feature_extractors.py` | 从证据提取新颖性、相关性、期望信息增益特征 |
| `cost_estimator.py` | 估算 token/工具调用/时延成本 |
| `eligibility.py` | 过滤非法或越权候选 |
| `policy.py` | `legacy` / `caes` 选择策略、影子模式 |
| `selector.py` | 打分、去重、预算内选择，产出 `SelectionDecision` |

### `evaluation/active_evidence/`

| 文件 | 作用 |
| --- | --- |
| `variants.py` | 主动证据实验变体 → `WorkflowOptions` 映射 |
| `runner.py` | 实验执行、断点续跑、锁 |
| `metrics.py` | 主动证据专属指标（覆盖率、信息增益、成本） |
| `recovery.py` | 中断实验的恢复状态 |
| `replay.py` | 从 trace 复算 |
| `statistics.py` | bootstrap / 配对检验 |

### `incidentbench/`

| 文件 | 作用 |
| --- | --- |
| `builder.py` | 从世界模型生成案例、公开/私有分层 |
| `scenarios/world.py` | 7 类故障的世界模型/证据生成器 |
| `validator.py` | 数据完整性、泄漏、可解性校验 |
| `normalizer.py` | 证据文本归一化 |
| `manifest.py` | 数据集清单与哈希 |
| `oracle_store.py` | 受保护的 oracle 读写（与 public 分离） |
| `experiment.py` | 4 条件实验执行 |
| `schemas.py` | `ExperimentProtocol` 等实验契约 |
| `scorer.py` | 状态 → 指标 |
| `readiness.py` | 正式实验门禁 |
| `citation_review.py` | 引用人工复核 |
| `family_split.py` | 按故障族分层切分 |
| `statistics.py` | 统计检验与置信区间 |

## 4. 模块之间的调用关系（简化）

```text
cli.py ──► orchestration.config / orchestration.graph ──► agents ──► llm
  │                    │                                   │
  │                    ├──► tools.registry ──► tools.provider ──► data/
  │                    ├──► security.authorization / context
  │                    ├──► orchestration.budget / permits / runtime
  │                    ├──► orchestration.merge / guards / report
  │                    └──► orchestration.observability ──► schemas.state
  ├──► artifacts（产物、replay）
  └──► web.server ──► orchestration.graph / artifacts

evaluation ──► orchestration.graph / schemas / artifacts（只读消费）
incidentbench ──► evaluation / schemas / orchestration（实验驱动）
```

更细的依赖方向与禁止反向依赖见 [11-dependency-map.md](11-dependency-map.md)。

## 5. 测试与文档布局

| 目录 | 内容 |
| --- | --- |
| `tests/unit/` | 模型、工具、缓存、LLM、预算、Gate 的细粒度测试（14 个文件） |
| `tests/integration/` | 端到端工作流、CLI、Web API、并发/STOP、恢复、产物边界（29 个文件） |
| `tests/evaluation/` | 指标、终止校验、消融、可靠性（7 个文件） |
| `tests/incidentbench/` | 数据集构建/校验/打分/统计/实验（16 个文件） |
| `tests/active_investigation/` | CAES 候选、特征、选择、影子模式（10 个文件） |
| `tests/reliability/` | 真实 Provider 恢复与账本 fixtures（3 个文件） |
| `tests/isolation/` | 路径逃逸、数据泄漏隔离 |
| `tests/cache/` | 缓存命名空间、失效、投毒防护 |
| `tests/web/` | JS 单测（`*.test.mjs`）与 Playwright 浏览器验收（`browser.cjs`） |
| `tests/conftest.py` | `INCIDENT_LENS_OFFLINE_TESTS=1` 时阻断非本机网络 |
| `docs/` | 架构、协议、缓存、评估、UI、验收与阶段计划（`docs/plans/`、`docs/incidentbench/`） |
| `docs/contracts/` | `export-schemas` 生成的 JSON Schema |

## 6. 代码风格与约定

- 所有公开模型继承 `StrictModel`（`extra="forbid"`），禁止隐式字段。
- 枚举值使用大写常量字符串；JSON 序列化统一 `model_dump(mode="json")`。
- 时间统一 UTC ISO-8601；trace 事件带单调递增 `seq`。
- 工具实现无状态、只读，错误通过 `ToolResult.ok/error_code` 表达，不抛业务异常。
- 运行时禁止 `print`，日志走 `logging`；trace 用 `observability.emit_event`。
