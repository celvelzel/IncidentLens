# IncidentLens 运行与配置指南

**简体中文** | [English](readme-guide.md)

本文承接原中文 README 中的运行与配置细节。README 保留项目概览和常用入口，本页集中说明成本感知证据选择、运行机制与预算、模型提供方与配置、证据与权限、本地解释缓存。

## 成本感知证据选择（CAES）

CAES 位于 `full` 动态调查的 Coordinator 返回 `INVESTIGATE` 之后、任务实际执行之前。它不会绕过 `FINALIZE`、`ABSTAIN`、Verifier 或 FinalizeGate，也不会读取私有 Oracle。候选生成和评分不调用模型或工具。

| 策略 | 实际行为 |
| --- | --- |
| `current_dynamic` | 默认策略；执行 Coordinator 原任务，绕过 CAES。 |
| `first_eligible` | 按候选生成顺序选择满足约束的任务。 |
| `active_no_cost` | 排名去掉请求和工具成本分母，硬预算仍有效。 |
| `active_no_discrimination` | 去掉区分性权重，保留缺口覆盖、门控贡献、冗余和成本。 |
| `active_evidence` | 使用区分性、缺口覆盖、门控贡献、冗余和成本形成完整启发式排序。 |

CandidateGenerator 从 Coordinator 提案、公开 Verifier 补查和公共角色模板构造候选，默认最多保留 6 个。ActionScorer 使用公开假说之间的区分性、开放问题覆盖、缺失证据来源、重复签名、预计请求和工具调用计算价值。Selector 默认最多选择 2 个可执行任务；没有有用任务时返回 `NO_USEFUL_ACTION`，使运行时安全弃权而不是空转。

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

默认配置中的权重是开发起点，不是校准后的研究参数。评分是启发式估计，不是信息增益概率；成本为统一回退值时，`active_no_cost` 与完整 CAES 的排序可能相同。冷启动没有可用区分性，只能使用公开角色优先顺序。物理重试乘数、Verifier 预留、STOP、墙钟和 token 预算始终优先于选择分数。

`--shadow-caes` 记录完整建议，但实际执行 Coordinator 原任务，适合观察而不改变控制流。显式策略、Shadow 和重放选项要求 `--variant full`。观测失败时回退原提案。完整配置见 [CAES 示例](../configs/active-investigation.example.yaml)，算法和实验边界见 [CAES 算法](v1.5/algorithm-spec.md) 与 [公平实验协议](v1.5/fairness-protocol.md)。

```powershell
# 记录建议，但不采用建议执行。
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --cache-mode off --shadow-caes --out results/caes-shadow

# 显式启用完整 CAES。
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --cache-mode off --selection-policy active_evidence --out results/caes-active

# 重放已保存的选择，不调用模型或工具。
.venv\Scripts\python.exe scripts/replay_v15_selection.py --trace results/caes-active/trace.json
```

## 运行机制与预算

所有角色运行在同一个 LangGraph `StateGraph` 中，通信由中央运行时负责。调查者返回局部结果，Merge 先按签发任务身份、角色、实际查询账本和证据来源校验批次，再把结果发布到共享证据板。Coordinator 只能看到已发布状态；Verifier 只能获取授权共享记录；FinalizeGate 拒绝被否决的候选、未解决阻塞、竞争假设和缺失的因果支撑。

TaskManager 限制单任务尝试次数；StopController 冻结任务和工具、取消在途工作并等待停止确认。Reporter 是确定性组件，Merge、Verifier、FinalizeGate 和 Reporter 都不是额外 LLM Agent。树形 Agent 通信不受支持。

| 配置 | 工作流 | 轮次 | 工具调用 | 模型请求 | 总时限 |
| --- | --- | ---: | ---: | ---: | ---: |
| [system.yaml](../configs/system.yaml)（默认） | `legacy_rca` | 4 | 12 | 16 | 600 秒 |
| [incident-response.yaml](../configs/incident-response.yaml) | `incident_response` | 6 | 24 | 24 | 600 秒 |

事件响应配置额外限制 Monitoring 8 次调用、Remediation 2 次调用、单任务 2 次尝试和 5 秒停止确认等待。阶段预算共享全局上限；JSON 修复、传输重试和物理请求都计入实际请求用量。CLI 参数覆盖配置文件。

`--max-tokens` 是请求开始前的上限检查。已计量用量达到上限后不再发出新请求，但正在进行的一次响应可能超过上限。缺少 Provider usage 时，Token 和成本保持未知，不按零值计。墙钟、轮次、请求、工具或 Token 预算耗尽属于运行时失败；正常证据不足则应以 `INCONCLUSIVE` 结束，不能混同。

根因状态、修复状态和工作流状态分别记录：

- 根因：`RESOLVED`、`INCONCLUSIVE`；旧报告契约还允许 `ERROR`。
- 修复：`NOT_STARTED`、`PLAN_READY`、`PLAN_FAILED`、`SKIPPED`。
- 工作流：`RUNNING`、`STOPPING`、`FINISHED`、`FAILED`。

`PLAN_READY` 只表示修复建议已生成，不表示生产服务恢复。完整停止与评分契约见 [排查协议](protocol.md)。

## 模型提供方与配置

将 [`.env.example`](../.env.example) 复制为项目本地 `.env`。真实模式必须显式提供以下配置：

| 环境变量 | 含义 |
| --- | --- |
| `INCIDENT_LENS_PROVIDER` | `mock` 或 `real` |
| `INCIDENT_LENS_BASE_URL` | OpenAI 兼容 Chat Completions 基础 URL 或完整端点 |
| `INCIDENT_LENS_API_KEY` | 本地密钥；不得提交、导出或写入结果 |
| `INCIDENT_LENS_MODEL` | Provider 接受的模型标识 |
| `INCIDENT_LENS_RESPONSE_FORMAT` | `json_schema` 或 `json_object` |
| `INCIDENT_LENS_THINKING` | 可选；`enabled` 或 `disabled` |
| `INCIDENT_LENS_REQUEST_TIMEOUT` | 单次请求超时秒数，默认 180 |

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider real --out results/real001
```

默认 `json_schema` 模式要求服务端支持严格 JSON Schema。端点只支持 JSON object mode 时，显式使用 `--response-format json_object`。两种模式都使用同一份本地 Pydantic 契约校验响应。配置优先级为 CLI `--response-format`、环境变量、启用后的 recovery 能力配置。不会自动切换响应格式、模型或 Provider。

配置缺失、端点不兼容、鉴权失败、限流、超时和传输错误都显式分类。`real` 永不静默回退到 Mock。HTTP fixture 测试只证明适配器行为，不证明某个在线端点兼容。Mock 是公开证据上的确定性策略，不读取私有标签，也不按事件 ID 查找答案；其结果不能代表真实模型质量或架构优越性。

### Provider 故障恢复

`provider_recovery.enabled` 默认 `false`，保持旧路径的至多一次结构化修复。显式启用后，运行时在请求、墙钟和阶段预算内分类并重试瞬态 HTTP/网络故障，并在预算允许时至多执行一次定向语法或 Schema 修复。每次实际发送，包括传输重试和修复，都消耗物理请求 permit。STOP 会取消退避；Domain、引用和最终化门禁继续由业务层控制。

```yaml
provider_recovery:
  enabled: true
  format_capability: json_object
  max_transport_retries: 2
  max_structured_repairs: 1
  max_physical_attempts_per_call: 4
  min_request_time_seconds: 5.0
```

恢复策略不会把缺失 usage 填成零，也不会把 Provider 失败改写为证据弃权。诊断事件只保存安全失败类别和尝试标识。旧 trace 仍可读取。详细错误分类、恢复判定和 usage 记账见 [LLM 与缓存实现](code_wiki/07-llm-and-cache.md)。

真实可靠性实验会产生 Provider 费用，必须使用新的输出目录。确定性故障注入和独立真实预检分别执行：

```powershell
.venv\Scripts\python.exe scripts/run_reliability_eval.py --out results/v13-eval/NEW-ID
.venv\Scripts\python.exe scripts/run_v13_pilot.py --out results/v13-eval/NEW-PILOT --response-format json_schema
.venv\Scripts\python.exe scripts/analyze_v13_pilot.py --source results/v13-eval/NEW-PILOT --out results/v13-eval/NEW-ANALYSIS
```

离线故障恢复不证明真实 RCA 正确率或定向修复质量。相关契约见 [运行时契约](v1.3/contracts.md) 与 [评测协议](v1.3/evaluation_protocol.md)。

## 证据与权限

数据集包含原有 6 个 Seed、10 个 Dev、20 个留出合成用例，以及独立 [数据库用例集](../data/splits/database_ids.json) 中的 `incident_037`–`incident_040`，共 40 个案例。原有划分保持冻结；新增案例覆盖连接耗尽、应用连接池误配置、锁竞争、慢查询和证据不足。合成模板不是独立采集的生产基准，证据不足案例要求正常弃权。数据范围见 [数据说明](../data/README.md)。

所有业务工具只读：

| 证据域 | 工具 |
| --- | --- |
| Logs | `query_logs` |
| Metrics / Dependencies | `query_metrics`、`get_dependencies` |
| Changes / Config | `query_changes`、`get_config_diff` |
| Database | `get_db_connections`、`get_db_active_sessions`、`get_db_lock_waits`、`get_db_slow_queries`、`get_db_health_metrics` |
| Shared evidence | `fetch_evidence_by_ids` |

ToolRegistry 以角色 ACL 为上限；`InvestigationTask.allowed_tools` 只能进一步收窄。公平架构比较可显式启用 `database_equivalent_tools`，让 Metrics 和 Single 获得等价数据库访问。服务端签发不可变 `AgentContext`，绑定角色、工作区、事件、运行和剩余工具预算。

工具成功返回的记录进入该 context 的 observed ledger。Merge 发布和 Verifier 获取共享证据时，只能引用实际观察并已发布到当前运行的记录。公共文件采用固定文件名白名单，拒绝私有真值、路径穿越、符号链接和 Windows junction。证据摘录始终按不可信数据提示模型；应用层隔离不等同于操作系统级 Python 沙箱。

新增工具必须同时维护参数 Schema、只读实现、角色 ACL、路径白名单和越权/预算/超时测试。完整权限矩阵与查询账本见 [工具与安全边界](code_wiki/06-tools-and-security.md)。

## 本地解释缓存

缓存默认关闭，架构对比必须强制 `cache=None`。仅以下四类调查者的局部解释可复用：

- `summarize_log_slice`
- `interpret_metric_window`
- `summarize_change_diff`
- `interpret_database_window`

Monitoring、Coordinator 路由、Verifier 审核、修复方案、FinalizeGate、报告和工具查询始终正常执行。缓存命中前，本次运行必须已经真实查询当前证据；命中结果只能引用该次证据快照中的记录，并在 Merge 前重绑 finding、task 和 run 身份。

| 模式 | 行为 |
| --- | --- |
| `off` | 不查、不写。 |
| `exact` | 归一化题目精确匹配。 |
| `semantic` | 本地嵌入余弦相似度加保守文本等价检查。 |

```powershell
$env:CACHE_MODE = 'semantic'
$env:CACHE_SIMILARITY_THRESHOLD = '0.95'
$env:CACHE_TTL_HOURS = '24'
$env:CACHE_EMBEDDING_MODEL = 'fake'
$env:CACHE_DB_PATH = 'results/cache.sqlite'
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --out results/cache-demo
```

命名空间必须精确匹配工作区、事件、角色、任务类型、证据快照哈希、数据集修订、Prompt 版本、模型 ID、模型参数哈希、输出 Schema 和 ACL 版本。任务签名还排除可变的 task ID 与 question，但保留 filters 和预期区分项。过期、损坏、引用不匹配或响应摘要不一致的条目会失效。

`FakeEmbedder` 是离线测试辅助工具，不是学习得到的语义模型。可选 `SentenceTransformerBackend` 只加载显式安装的本地权重，CI 不下载模型。相似度高但仍涉及否定、数值、比较或方向变化时，保守安全检查会拒绝复用。

缓存收益必须单独测量；架构比较不能开启缓存。Mock 结果只证明离线行为，图、工具和嵌入都计入延迟，不能用本地 Mock 时间推断真实 Provider 的节省。实现与失效规则见 [缓存设计](cache.md)。

```powershell
.venv\Scripts\python.exe scripts/run_cache_eval.py --provider mock --out results/cache-experiment
```

## 相关文档

- [运行与配置指南（英文）](readme-guide.md)
- [排查协议](protocol.md)
- [CAES 算法](v1.5/algorithm-spec.md)
- [CAES 公平实验协议](v1.5/fairness-protocol.md)
- [工具与安全边界](code_wiki/06-tools-and-security.md)
- [LLM 与缓存实现](code_wiki/07-llm-and-cache.md)
- [缓存设计](cache.md)
- [数据说明](../data/README.md)
- [IncidentBench 测试指南](incidentbench/README.md)
