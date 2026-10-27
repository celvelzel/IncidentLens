# 05 · 数据契约与状态机

所有运行时对象都是 Pydantic v2 `StrictModel`：`extra="forbid"`、`strict=True`、`validate_assignment=True`。**任何字段拼写错误或类型漂移都会立刻失败**，这是系统可审计性的基础。

核心定义全部在 [`schemas/contracts.py`](../../src/incident_lens/schemas/contracts.py) 与 [`schemas/workflow.py`](../../src/incident_lens/schemas/workflow.py)；其余 `schemas/*.py` 只是兼容性 re-export。

## 1. 基础类型

```python
Identifier = str  # 1..128, ^[A-Za-z0-9][A-Za-z0-9_.-]*$
Text = str        # min_length=1
```

`timezone_required` 强制所有 `datetime` 带时区（UTC）。

## 2. 角色与枚举

### 2.1 `Role`

`coordinator`、`logs`、`metrics`、`database`、`changes`、`verifier`、`reporter`、`single`、`monitoring`、`remediation`

### 2.2 `SpecialistRole`

`logs`、`metrics`、`database`、`changes`

### 2.3 `StopReason`

| 值 | outcome | 含义 |
| --- | --- | --- |
| `PLAN_READY` | SUCCESS | RCA 已解析且修复计划已生成 |
| `DIAGNOSIS_READY` | SUCCESS | RCA 已解析，无修复阶段 |
| `INCONCLUSIVE` | ABSTAINED | 证据不足，显式弃权 |
| `NO_ALERT` | NO_ACTION | 监控未发现异常 |
| `PLAN_FAILED` | FAILED | 诊断成功但修复计划失败 |
| `BUDGET_EXHAUSTED` | FAILED | 预算耗尽 |
| `UNRECOVERABLE_ERROR` | FAILED | 不可恢复运行时错误 |
| `STOP_TIMEOUT` | FAILED | STOP/ACK 未在超时内完成 |

`NORMAL_REASONS = {PLAN_READY, DIAGNOSIS_READY, INCONCLUSIVE, NO_ALERT, PLAN_FAILED}`；其余 `runtime_failure=True`。

### 2.4 其他状态枚举

| 模型 | 字段 | 值 |
| --- | --- | --- |
| `Hypothesis` | `status` | `OPEN` / `SUPPORTED` / `REJECTED` |
| `Finding` | `relation` | `supports` / `refutes` / `neutral` |
| `Finding` | `confidence_qualifier` | `supported` / `weak` / `unknown` |
| `Review` | `verdict` | `sufficient` / `insufficient` / `conflicted` |
| `CoordinatorDecision` | `action` | `INVESTIGATE` / `FINALIZE` / `ABSTAIN` |
| `RCAReport` | `status` | `RESOLVED` / `INCONCLUSIVE` / `ERROR` |
| `RCAReport` | `diagnosis_status` | `RESOLVED` / `INCONCLUSIVE` / `None` |
| `RCAReport` | `remediation_status` | `NOT_STARTED` / `PLAN_READY` / `PLAN_FAILED` / `SKIPPED` |
| `RCAReport` / `InvestigationState` | `workflow_status` | `RUNNING` / `STOPPING` / `FINISHED` / `FAILED` |
| `InvestigationState` | `stop_reason` | `str \| None`（最终由 `StopReason` 收口） |
| `TaskRecord` | `status` | `ASSIGNED` / `RUNNING` / `COMPLETED` / `FAILED` / `CANCELLED` |
| `IncidentAlert` | `status` | `ALERT` / `NO_ALERT` |
| `TerminationResult` | `outcome` | `SUCCESS` / `ABSTAINED` / `NO_ACTION` / `FAILED` |
| `TerminationResult` | `failure_stage` | `monitoring` / `coordinate` / `dispatch` / `merge` / `verify` / `finalize` / `diagnosis` / `remediation` / `stop` / `runtime` |

## 3. 证据模型

### 3.1 `EvidenceRecord`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `evidence_id` | Identifier | 全局唯一引用 ID |
| `incident_id` | Identifier | 所属事故 |
| `source_type` | `logs \| metrics \| changes \| configs \| topology \| database` | 证据域 |
| `service` | Identifier | 关联服务 |
| `observed_at` | datetime | 必须带时区 |
| `source_path` | str | **只能是 `public/...` 或 `topology/services.yaml`** |
| `excerpt` | str | 公开摘录 |
| `metadata` | dict | 结构化字段（`metric_name`、`value`、`change_id`、`connection_limit`…） |

`public_relative_path` 校验拒绝：

- 反斜杠、冒号、绝对路径、空段、`.`、`..`；
- `private`、`hidden`、`ground_truth`、`ground-truth`、`secrets`、`.git`、任何以 `.` 开头的段；
- 不以 `public/` 开头且不是 `topology/services.yaml` 的路径。

这是**数据泄漏防线**：即使上层被注入，也无法构造指向私有 oracle 的证据记录。

### 3.2 `ToolResult`

```python
call_id: Identifier
ok: bool
records: list[EvidenceRecord]
error_code: str | None
elapsed_ms: float
record_count: int
next_cursor: str | None
```

不变量（`consistent_result`）：

- `record_count == len(records)`；
- `ok == True` 时 `error_code is None`，`ok == False` 时必须非空；
- 失败结果不得带 records 或 cursor。

## 4. 调查模型

### 4.1 `InvestigationTask`

| 字段 | 含义 |
| --- | --- |
| `task_id` | 每轮必须新鲜 |
| `role` | 必须是 `SpecialistRole` |
| `question` | 调查问题 |
| `allowed_tools` | 只能是该角色 ACL 的子集 |
| `filters` | 结构化过滤（用于空查询范围检测） |
| `reason` | 为什么派这个任务 |
| `expected_discriminator` | 预期能区分什么 |

### 4.2 `Finding`

`finding_id`、`task_id`、`run_id`、`incident_id`、`role`、`claim`、`evidence_ids`、`relation`、`confidence_qualifier`、`followup_question`。

### 4.3 `Hypothesis`

`hypothesis_id`、`culprit_service`、`failure_mode`、`support_ids`、`against_ids`、`predicted_observations`、`status`、`open_questions`。

### 4.4 `Review`

`target_hypothesis_id`、`verdict`、`contradictions`、`requested_checks`、`optional_checks`、`cited_evidence_ids`、`rationale`。

`ReviewOutput`（生成侧）额外约束：`sufficient` 时不得有 `requested_checks` 或 `contradictions`。

### 4.5 `CoordinatorDecision`

| action | 允许字段 | 禁止字段 |
| --- | --- | --- |
| `INVESTIGATE` | 非空 `assignments` | `selected_hypothesis_id`、`stop_reason` |
| `FINALIZE` | 非空 `stop_reason`、`selected_hypothesis_id` | `assignments` |
| `ABSTAIN` | 非空 `stop_reason` | `assignments`、`selected_hypothesis_id` |

## 5. 报告模型

### 5.1 `RCAReport`

| 字段 | 说明 |
| --- | --- |
| `status` | RESOLVED / INCONCLUSIVE / ERROR |
| `root_cause` | `Hypothesis \| None` |
| `causal_chain` | `list[str]`，每条一个已观测证据的 `时间 [id] 服务: 摘录` |
| `supporting_evidence_ids` | 已接受证据 |
| `rejected_hypotheses` | 必须全部 `REJECTED` |
| `unresolved` | 未解决问题 |
| `stop_reason` | 终止原因文本 |
| `diagnosis_status` | 与 status 同步 |
| `remediation_status` | 修复计划状态 |
| `workflow_status` | 工作流状态 |
| `remediation_plan` | `RemediationPlan \| None` |
| `termination` | `TerminationResult \| None` |

`resolution_semantics` 强制：

1. `diagnosis_status` 必须与 `status` 一致；
2. `PLAN_READY ⇔ remediation_plan is not None`；
3. 有修复计划 ⇒ `status == RESOLVED`、run/incident 一致、计划证据 ⊆ 支持证据；
4. `RESOLVED` ⇒ 根因存在且 `SUPPORTED`、有支持证据、有因果链；
5. 非 `RESOLVED` ⇒ 不得有根因；
6. `rejected_hypotheses` 必须全部 `REJECTED`。

### 5.2 `RemediationPlan`

`incident_id`、`run_id`、`root_cause_version`、`execution_mode`（固定 `PLAN_ONLY`）、`objective`、`affected_services`、`actions`、`preconditions`、`risks`、`verification_steps`、`rollback`、`evidence_ids`。除前三个外全部 `min_length=1`。

### 5.3 `TerminationResult`

`consistent_termination` 强制：

- `outcome` 必须匹配 reason 表；
- `runtime_failure ⇔ reason ∉ NORMAL_REASONS`；
- `FAILED ⇔ failure_stage is not None`；
- `STOP_TIMEOUT` ⇒ `stop_completed=False` 且 stage=`stop`；
- 非 `STOP_TIMEOUT` ⇒ `stop_completed=True`；
- `PLAN_FAILED` ⇒ stage=`remediation`。

## 6. 状态模型

### 6.1 `InvestigationState`

| 分组 | 字段 |
| --- | --- |
| 身份 | `workspace_id`, `incident_id`, `run_id`, `public_summary` |
| 预算/进度 | `budgets`, `round_index`, `tool_calls_used`, `llm_calls_used`, `tokens_used` |
| 共享板 | `findings`, `evidence_index`, `hypotheses`, `tasks`, `reviews`, `decisions` |
| 问题/完成 | `open_questions`, `requested_checks`, `completed_task_ids` |
| 端点阶段 | `incident_alert`, `task_records`, `report` |
| 终止 | `stop_reason`, `workflow_status`, `termination` |
| 事件 | `events: list[TraceEvent]` |

### 6.2 `consistent_provenance`（关键不变量）

状态每次校验都会检查：

1. `public_summary.incident_id == state.incident_id`；
2. `evidence_index` 的 key 必须等于 `record.evidence_id`，且 `record.incident_id` 一致；
3. 所有 finding / event / report 的 `run_id`、`incident_id` 与状态一致；
4. 每个 finding 的 `task_id` 必须存在于 `tasks`，且 `role` 与任务一致；
5. `completed_task_ids ⊆ task_ids`；
6. 任务 ID、finding ID 均唯一；
7. **所有引用闭包**（findings、hypotheses 的 support/against、reviews 的 cited、report 的支持证据、修复计划证据、被拒假设引用、根因引用）必须 ⊆ `evidence_index`。

第 7 条是整个系统"不可引用未观测证据"的最终防线，`report` 节点结束前会再跑一次完整校验。

### 6.3 `TraceEvent`

`event_id`、`run_id`、`incident_id`、`timestamp`、`event_type`、`role`、`task_id`、`call_id`、`evidence_ids`、`message`、`details`、`source`（`model` / `cache` / `mock` / `runtime`）、`elapsed_ms`。

## 7. `WorkflowOptions`

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `selection_policy` | `current_dynamic` | CAES 策略名 |
| `shadow_caes` | `False` | 只观测不改变路由 |
| `active_evidence_config` | `PolicyConfig()` | CAES 权重/阈值 |
| `profile` | `legacy_rca` | 或 `incident_response` |
| `communication_mode` | `centralized` | 仅支持集中式 |
| `monitor_mode` | `legacy` | 或 `manual_snapshot` / `offline_replay` |
| `database_enabled` | `True` | 是否允许 database 角色 |
| `database_equivalent_tools` | `False` | benchmark 等价工具 |
| `benchmark_rca` | `False` | 基准模式 |
| `benchmark_fixed_four` | `False` | fixed 变体加 database |
| `remediation_enabled` | `True` | 是否进入 remediate |
| `execution_mode` | `plan_only` | 固定 |
| `max_attempts` | 2 | task/stage 重试上限 |
| `continue_on_partial_failure` | True | 部分任务失败后继续 |
| `ack_timeout_seconds` | 5.0 | STOP ACK 超时 |
| `monitoring_max_calls` | 1 | 监控阶段调用上限 |
| `remediation_max_calls` | 2 | 修复阶段上限 |
| `snapshot` | `[]` | 手动快照/回放证据 |

`profile_semantics` 校验：

- `benchmark_fixed_four` ⇒ `benchmark_rca`；
- `benchmark_rca` ⇒ `legacy_rca` + `database_enabled` + `database_equivalent_tools`；
- `legacy_rca` ⇒ `monitor_mode == "legacy"`。

## 8. `PolicyConfig`（CAES）

`policy_version="caes-v1"`，`candidate_pool_limit=6`，`max_selected_tasks=2`，权重：

`discrimination_weight=0.4`、`gap_weight=0.3`、`gate_weight=0.3`、`redundancy_weight=0.3`、`diversity_penalty=0.15`、`redundancy_hard_limit=0.95`、`request_weight=1.0`、`tool_weight=0.25`、`epsilon=0.01`、`min_score=0.0`、`reserve_verifier_requests=1`、`reserve_verifier_tools=1`。

## 9. 序列化约定

- 对外 JSON 一律 `model_dump(mode="json")` / `model_validate_json`。
- trace、result、report 中的时间均为 UTC ISO-8601。
- 枚举使用字符串字面量，不使用 Python Enum，便于 JSON Schema 与跨语言消费。
- `export-schemas` 生成 `docs/contracts/*.json`，用于外部集成与协议冻结。

## 10. 修改契约的兼容性规则

| 变更 | 是否安全 |
| --- | --- |
| 给 `StrictModel` 加**可选**字段（有默认值） | 需要更新 schema 快照与测试 |
| 加无默认值字段 | 破坏旧 trace，禁止 |
| 改枚举值 | 破坏旧产物，必须升 `PROTOCOL_VERSION` |
| 放宽校验 | 需同步更新安全测试与文档 |
| 删除字段 | 禁止，除非主版本升级并提供迁移 |
