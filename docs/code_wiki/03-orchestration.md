# 03 · 编排层：工作流、预算与确定性 Gate

核心文件：[`orchestration/graph.py`](../../src/incident_lens/orchestration/graph.py)（`InvestigationRun`，L42；`run_investigation`，L1677）。

## 1. `InvestigationRun` 构造与运行时组件

`InvestigationRun.__init__`（L43）一次性装配本次运行的全部组件：

| 组件 | 类型 | 作用 |
| --- | --- | --- |
| `provider` | `LLMProvider` | 真实 / Mock / Codex Provider |
| `variant` | `full \| single \| fixed \| dynamic_no_verifier` | 消融变体 |
| `workflow` | `WorkflowOptions` | profile、监控模式、修复开关、最大尝试次数 |
| `limits` | `Budget` | 轮数 / 工具 / LLM / wall / token |
| `call_budget` | `CallBudget` | 物理请求、token、失败记录、停止快照 |
| `registry` | `ToolRegistry` | ACL、工具执行、查询账本 |
| `task_manager` | `TaskManager` | 任务状态机（ASSIGNED→RUNNING→COMPLETED/FAILED/CANCELLED） |
| `stop_controller` | `StopController` | 冻结 + 取消 + ACK 超时 |
| `signatures` | set | 已执行任务签名，用于检测"无进展循环" |
| `completed_scopes` | dict | 已成功执行且结果为空的变化查询范围 → 证据指纹 |
| `failed_finalizations` | set | 已失败的 `(候选, 证据指纹, 错误集合)`，防止同错反复重试 |
| `remediation_versions` | set | 已生成计划的根因版本，避免重复调用 |

`GraphState` 是 LangGraph 的 TypedDict，含三个键：`investigation: InvestigationState`、`local_results: list`、`route: str`。所有节点返回 `{"investigation": ..., "route": ...}`（dispatch 额外返回 `local_results`）。

## 2. 节点逐一说明

### 2.1 `monitor`（L262）

- 仅 `incident_response` profile 可用。
- 输入：`state.public_summary`、`workflow.snapshot`（`manual_snapshot` / `offline_replay`）。
- 输出 `IncidentAlert`（`ALERT` / `NO_ALERT`），写入 `state.incident_alert`，并发 `INCIDENT_ALERT` 事件。
- `NO_ALERT` → `stop`（`StopReason.NO_ALERT`，outcome `NO_ACTION`）；`ALERT` → `coordinate`。
- `monitor_mode == "legacy"` 时直接路由到 `coordinate`，不调用模型。
- 受 `workflow.monitoring_max_calls` 与独立的 stage 预算限制。

### 2.2 `coordinate`（L461）

协调器（`agents.service.decide`）输出 `CoordinatorDecision`，动作只有三种：

| action | 约束 | 路由 |
| --- | --- | --- |
| `INVESTIGATE` | 必须有 `assignments`，不能有 `selected_hypothesis_id` / `stop_reason`；每轮最多 2 个任务 | `dispatch` |
| `FINALIZE` | 必须选一个候选；若本轮同时修正了假设（`changed`）且为 `full`，先转 `verify` 刷新审查 | `verify` / `finalize` |
| `ABSTAIN` | 必须有 `stop_reason`，无任务 | `report`（编译时映射到 `stop`） |

确定性保护：

1. **轮次/工具/LLM 预检**：`round_index >= max_rounds`、`registry.call_count >= max_tool_calls` 直接抛错 → `RUNTIME_ERROR`。
2. **LLM 预算预留**：`reserve = 1 + (full|single)`，`affordable = (remaining - reserve) // 2`；任务数超出则截断并记录 `INVESTIGATION_BUDGET_RESERVED`。保证至少留一次协调 + 一次审查。
3. **无进展检测**：任务签名（role/allowed_tools/filters/expected_discriminator）+ 当前共享板指纹相同 → `INVESTIGATION_NO_PROGRESS` → `INCONCLUSIVE`。
4. **空变化范围检测**：若所有任务都是已成功、空结果、无 cursor 的 `query_changes` 且共享板未变 → 直接 `INCONCLUSIVE`。
5. **任务 ID 新鲜性**：新任务 ID 不得与 `state.tasks` 重复，否则运行时错误。
6. **fixed 变体**：首轮自动生成 logs+metrics+changes（benchmark 下 +database）；之后不再调查，只在无障碍候选中定稿或弃权。benchmark 模式下若协调器仍想调查，会改写为 `ABSTAIN`。

### 2.3 `dispatch`（L815）与 `execute_task`（L876）

- `full` / `fixed`：为每个任务 `asyncio.create_task`，再 `asyncio.gather(..., return_exceptions=True)` 并发执行；`single`：按顺序串行。
- 每个任务：
  1. `task_manager.assign/start` 记录 attempt；
  2. 用 `payload(state, role, fetched=...)` 构造最小上下文；
  3. 调 `investigate` 得到 `InvestigatorOutput`（本地 `Finding` / `Hypothesis`）；
  4. 工具调用经 `registry.execute(context, ...)`，每次发 `TOOL_CALL` 事件；
  5. 返回 `(context, task, analysis)`，**不写共享状态**。
- 任务异常按 `recoverable_task_error` 分类：可恢复 → `wait_for_retry`（指数退避，受剩余 wall clock 约束）；不可恢复 → 记录 `TASK_FAILED`。`continue_on_partial_failure` 允许部分任务失败后继续合并。

### 2.4 `merge`（L1040）→ [`merge.py`](../../src/incident_lens/orchestration/merge.py)

`merge_results(state, local_results, registry)` 做四类校验后才发布：

1. **身份**：`run_id` / `incident_id` / `task_id` / `role` 与当前 state 和任务一致；
2. **任务**：`task.task_id` 必须已存在于 `state.tasks`；
3. **证据**：finding 的 `evidence_ids` 必须是该 worker 实际观测过的；hypothesis 的 `support/against` 可引用本 worker 新观测，也可复用**上一轮已发布**的共享证据；
4. **ID 冲突**：finding / hypothesis ID 重复且内容不同视为不可恢复错误；同一 `(culprit_service, failure_mode)` 复用同一假设 ID。

Merge 还负责：

- 把本 worker 新查询到的证据写入 `evidence_index`；
- 在**状态整体校验通过后**调用 `registry.publish(context, ids)`，才真正把证据加入共享可见集（顺序刻意放在校验之后，避免半发布）；
- 对齐 Verifier 先前 `requested_checks`：若本轮任务完成了指定检查，发 `REVIEW_FOLLOWUP`，记录新证据 ID；
- 对"精确空变化查询"记录 `completed_scopes[scope] = evidence_fingerprint(state)`；
- 发 `MERGE` 事件（完整 findings/hypotheses 快照）。

路由：`full` / `single` → `verify`；其他 → `coordinate`。

### 2.5 `verify`（L1111）

- 无候选 → `REVIEW_SKIPPED` → `coordinate`。
- **审查复用**：`board_fingerprint(state)` 未变且最近审查针对同一候选 → `REVIEW_REUSED`，若 `reviewed_finalization_ready` 则 `finalize`，否则 `coordinate`。
- **先 fetch 再审查**：Verifier 只能用 `fetch_evidence_by_ids` 读取共享证据（最多 50 条），payload 仅包含本次实际返回的记录。这样"未查询证据"不会进入审查上下文。
- 输出 `Review`：`sufficient` / `insufficient` / `conflicted`，可带 `requested_checks`（必须执行）与 `optional_checks`。
- `REVIEW` 事件写入两个指纹：`hypothesis_sha256` 与 `evidence_sha256`。后续任何候选或证据变化都会让该审查失效。

### 2.6 `finalize`（L1283）

纯同步、无模型调用：

1. 取 `state.decisions[-1].selected_hypothesis_id`；
2. 计算 `finalize_errors(state, candidate, variant)`；
3. 追加预算审计：LLM 调用数、token、wall clock；
4. 有错误：
   - 发 `FINALIZE_REJECTED`（errors + 全部候选评估）；
   - 若 `(候选, 证据指纹, 错误集合)` 未重复、轮次未耗尽且预算未耗尽 → 回 `coordinate` 继续调查；
   - 否则写 `state.stop_reason` 并终止。
5. 通过：
   - 候选置为 `SUPPORTED`；
   - 构造 `RCAReport(status="RESOLVED")`，`causal_chain = observed_chain(state, candidate)`（只使用已观测证据）；
   - `rejected_hypotheses` 收集所有 `REJECTED`；
   - 发 `DIAGNOSIS_ACCEPTED`，并列出诊断阶段失败但已恢复的 call_id（降级记录）。
6. 路由：`incident_response` 且有报告 → `remediate`；否则 `stop`。

### 2.7 `remediate`（L1345）

- 仅 `incident_response` 且 `remediation_enabled=True`。
- 以 `root_cause_version(report)` 去重；同一根因版本只生成一次计划。
- 生成 `RemediationPlan`（`execution_mode="PLAN_ONLY"`），`validate_plan` 校验：引用的证据必须属于 RCA 的 `supporting_evidence_ids`，动作/前置条件/风险/验证/回滚均非空。
- 成功 → `remediation_status="PLAN_READY"`；失败 → `PLAN_FAILED`（预算原因映射为 `PLAN_FAILED` 或 `BUDGET_EXHAUSTED`）。
- 绝不执行任何变更。

### 2.8 `stop`（L1421）

所有终态的唯一出口：

```text
state.workflow_status = "STOPPING"
reason = 由 report/termination 推导（见下表）
task_manager.stop() + registry.freeze()      # 冻结，拒绝新工具/新任务
取消 active_workers 与 active_model_calls（按角色分组）
对仍有 ASSIGNED/RUNNING 记录的任务补 CANCELLED
stop_controller.stop(reason, callbacks)      # 发送 STOP、等待 ACK
若 ACK 超时 → STOP_TIMEOUT / failure_stage="stop"
写 state.task_records / state.termination / workflow_status
发 NORMAL_TERMINATION 或 RUNTIME_FAILURE
```

终止原因推导优先级（自上而下）：

1. 存在 `RUNTIME_ERROR` → `BUDGET_EXHAUSTED`（消息含 budget）或 `UNRECOVERABLE_ERROR`；
2. `remediation_status == PLAN_READY` → `PLAN_READY`；
3. `PLAN_FAILED` → 预算耗尽则 `BUDGET_EXHAUSTED`，否则 `PLAN_FAILED`；
4. `report.status == RESOLVED` → `DIAGNOSIS_READY`；
5. 消息含 budget → `BUDGET_EXHAUSTED`；
6. 正常弃权 / 拒绝定稿 / 明确无证据 → `INCONCLUSIVE`；
7. 否则 `UNRECOVERABLE_ERROR`。
8. 特例：若判定为 `INCONCLUSIVE` 但存在未恢复的 Provider 失败（且不是取消），升级为 `UNRECOVERABLE_ERROR`。

### 2.9 `report`（L1584）

- 若 `state.report is None`，先尝试 `rescue_report`（L1520）。这不是通用兜底，而是**窄条件救援**：
  - 存在至少一个 `RUNTIME_ERROR`，且**全部**都是传输类错误；
  - 最近一次决策不是 `ABSTAIN`，且 `stop_reason` 不是预算原因；
  - 恰好存在 1 个通过 `finalize_errors` 的候选；
  - 该候选此前已有 `REVIEW` 且 verdict 为 `sufficient`。
  - 满足时生成 `RESOLVED` 报告，事件标记 `rescued=True`，仅用于"审查已完成、随后传输失败"的场景。
- 若仍无报告，生成 `INCONCLUSIVE` 报告，包含：
  - `unresolved`：优先未决问题，其次最近一次 `FINALIZE_REJECTED` 的错误，最后默认"需要额外判别证据"；
  - 已拒绝的候选；
  - 终止原因、workflow/termination 状态（响应型 profile 下 `diagnosis_status=INCONCLUSIVE`、`remediation_status=SKIPPED`）。
- 回写 `tool_calls_used` / `llm_calls_used` / `tokens_used`。
- 发 `REPORT` 事件（含 `tokens_complete`）。
- 最后再执行一次 `InvestigationState.model_validate_json(state.model_dump_json())`，保证引用完整性。
- 返回 `END`。

## 3. 图构建（L1623）

```python
nodes = ["monitor", "coordinate", "dispatch", "merge", "verify",
         "finalize", "remediate", "stop", "report"]
for name in nodes:
    graph.add_node(name, getattr(self, name))
graph.add_edge(START, "monitor" if response_profile else "coordinate")
for name in nodes[:-2]:            # monitor ... remediate
    graph.add_conditional_edges(
        name,
        lambda value: "stop" if value["route"] == "report" else value["route"],
        {...},
    )
graph.add_edge("stop", "report")
graph.add_edge("report", END)
```

路由使用内联 lambda 而非命名方法：任意节点的 `route` 直接作为下一节点名；`"report"` 统一映射到 `"stop"`（因此 `stop → report → END` 永远执行）。

## 4. 预算系统

### 4.1 `CallBudget`（[`budget.py`](../../src/incident_lens/orchestration/budget.py)）

- `consume_request(stage, run_id, logical_call_id)`：先检查 token 上限，再向 `RequestPermitIssuer` 申请 permit，`calls += 1`。
- `call(function, *args)`：包一层 `asyncio.wait_for(..., remaining_seconds)`；超时且确实到 deadline → 转为 `BudgetExceeded`，保留子调用的 usage。
- 失败也记账：`usage` 与 `failures` 都记录，未知 token 记为 `tokens_complete=False`。
- `attempts = usage.llm_calls`：Provider 内部的重试/修复次数会折算成额外调用，若总调用超限则抛 `Structured repair exhausted LLM budget`。
- `snapshot()` 返回剩余请求/token/秒数，供 trace 与 Web 展示。

### 4.2 `RequestPermitIssuer`（[`permits.py`](../../src/incident_lens/orchestration/permits.py)）

- 线程安全，签发 `RequestPermit(logical_call_id, stage, run_id, issued_at, deadline)`。
- 支持 stage 限额（monitoring / remediation），以及 `reserve_verifier_requests`。
- `mark_dispatched` 与 `reconcile(permit, total_tokens)` 用于把"逻辑调用"与"物理请求"对齐。
- `snapshot(stage)` 输出 `BudgetSnapshot`。

## 5. 任务运行时（[`runtime.py`](../../src/incident_lens/orchestration/runtime.py)）

| 类 / 函数 | 职责 |
| --- | --- |
| `TaskManager` | `assign / start / complete / fail / cancel / stop`；生成 `TaskRecord`，保证 attempt 单调 |
| `StopController` | `guard()` 在 stopped/frozen 时抛 `CancelledError`；`stop(reason, callbacks)` 发 STOP、等待 ACK、设置 `completed` |
| `wait_for_retry` | 指数退避（`base_delay * 2**attempt`，上限 `max_delay`），受剩余 wall clock 限制 |
| `active_workers` | task_id → asyncio Task，STOP 时统一取消 |

## 6. 恢复策略（[`recovery.py`](../../src/incident_lens/orchestration/recovery.py)）

`RecoveryPolicy` 把错误分为：

| 类别 | 例子 | 动作 |
| --- | --- | --- |
| 认证 / 配置 | 401、缺失 API key | 立即失败，不重试 |
| 结构化输出 | JSON 不合法 / schema 不匹配 | Provider 内 1 次修复；仍失败则失败 |
| 速率限制 | 429 / `Retry-After` | 有界重试，遵守 Retry-After |
| 传输瞬时 | 超时、连接重置、5xx | 指数退避重试 |
| 预算 | `BudgetExceeded` | 立即终止 |
| 取消 | `CancelledError` | 不重试，记录为取消而非失败 |

`RecoveryAction` 枚举与 `classify_failure` 是唯一判定入口，避免各处自定义重试逻辑。

## 7. CAES（可选）

[`orchestration/active_investigation/`](../../src/incident_lens/orchestration/active_investigation/) 实现 Cost-Aware Evidence Selection：

1. `candidate_generator` 生成候选任务（角色 × 服务 × 证据域）；
2. `feature_extractors` 计算新颖性、相关性、判别潜力；
3. `cost_estimator` 估算 token/工具/时延；
4. `eligibility` 过滤越权或不可执行候选；
5. `selector` 在预算内选 top-k；
6. `policy.apply_policy` 用 `legacy` / `caes` 策略替换协调器提案。

约束：

- 只有 `variant == "full"` 允许启用；
- `shadow_caes=True` 时只记录 `ACTION_POLICY_FALLBACK`，不改变真实路由；
- 任何 CAES 内部异常在影子模式下必须被吞掉并记录，不影响主流程。

## 8. 观测与 trace（[`observability.py`](../../src/incident_lens/orchestration/observability.py)）

事件类型（`event_type`）包括：

`NODE_START` / `NODE_END`、`AGENT_REQUEST` / `AGENT_RESPONSE`、`MODEL_CALL` / `MODEL_FAILURE`、`TOOL_CALL`、`TASK_ASSIGNED` / `TASK_STARTED` / `TASK_COMPLETED` / `TASK_FAILED` / `TASK_CANCELLED`、`DECISION`、`HYPOTHESIS_RECONCILED`、`MERGE`、`REVIEW` / `REVIEW_SKIPPED` / `REVIEW_REUSED` / `REVIEW_FOLLOWUP`、`FINALIZE_REJECTED` / `DIAGNOSIS_ACCEPTED`、`REMEDIATION_PLAN` / `REMEDIATION_FAILED`、`STOP_REQUESTED` / `STOP_ACK`、`NORMAL_TERMINATION` / `RUNTIME_FAILURE`、`REPORT`。

`TraceWriter` 逐条追加 JSONL；`TraceReader` 支持按类型/角色/任务过滤，并生成 `TraceSummary`（供 Web 列表与 replay）。

## 9. 报告渲染（[`report.py`](../../src/incident_lens/orchestration/report.py)）

`render_report(state) -> str` 是纯函数，输出 Markdown：

1. 标题、run/incident、状态、终止原因；
2. 事故摘要与症状；
3. 根因（若 `RESOLVED`）：服务、失败模式、因果链、支持证据（含 excerpt 与路径）；
4. 已拒绝假设；
5. 修复计划（若存在）；
6. 未解决项；
7. 预算用量与终止结果；
8. 证据索引附录。

不调用任何模型，保证同一 state 渲染结果完全一致。

## 10. 修改工作流时的检查清单

- [ ] 新节点必须绑定 `self.state = state`（runtime 事件依赖它）。
- [ ] 新路由必须在 `compile()` 的条件边映射中登记。
- [ ] 新状态字段必须加入 `InvestigationState`，并考虑 `consistent_provenance` 引用校验。
- [ ] 新事件类型必须能被 `TraceReader`/前端安全忽略。
- [ ] 任何新的模型调用必须走 `model_call` / `stage_call`，否则不计预算与 trace。
- [ ] 任何新的工具调用必须经 `registry.execute`，否则绕过 ACL 与账本。
- [ ] 终态必须经过 `stop`，不得直接返回 `END`。
