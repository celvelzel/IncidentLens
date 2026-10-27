# 06 · 工具与安全边界

相关代码：[`tools/`](../../src/incident_lens/tools)、[`security/`](../../src/incident_lens/security)。

## 1. 工具清单

| 工具名 | 参数模型 | 主要参数 | 证据域 | 说明 |
| --- | --- | --- | --- | --- |
| `query_logs` | `LogsArgs` | `service`, `start_ts`, `end_ts`, `severity?`, `contains?`, `limit<=50` | logs | 按时间窗查询公开日志 |
| `query_metrics` | `MetricsArgs` | `service`, `metric_names<=50`, `start_ts`, `end_ts` | metrics | 指标序列；空列表表示全部指标 |
| `get_dependencies` | `DependenciesArgs` | `service?` | topology | 服务依赖拓扑 |
| `query_changes` | `ChangesArgs` | `service?`, `start_ts?`, `end_ts?`, `change_type?` | changes | 变更记录 |
| `get_config_diff` | `ConfigDiffArgs` | `change_id` | configs | 配置 diff；ID 来自变更记录 `metadata.change_id` |
| `get_db_connections` | `DatabaseArgs` | `service="postgres"`, `limit<=50`, `start_ts`, `end_ts` | database | 连接数 / 上限 |
| `get_db_active_sessions` | 同上 | 同上 | database | 活动会话与状态 |
| `get_db_lock_waits` | 同上 | 同上 | database | 锁等待与 `blocked_by` |
| `get_db_slow_queries` | 同上 | 同上 | database | 慢查询与 `duration_ms` |
| `get_db_health_metrics` | 同上 | 同上 | database | 健康指标 |
| `fetch_evidence_by_ids` | `FetchArgs` | `ids: 1..50` | 共享板 | 仅返回已发布证据（或 single 自己的账本） |

参数不变量：

- `TimeWindow` 要求 `start_ts <= end_ts`，且都能解析为带时区时间。
- `limit` 一律 1..50，超过部分返回 `next_cursor`（当前实现以字符串上限表示还有更多）。
- `change_type ∈ {deployment, config, maintenance, scaling}`。
- `severity ∈ {DEBUG, INFO, WARN, ERROR, CRITICAL}`。

## 2. 权限矩阵（`ROLE_TOOL_ACL`）

| 角色 | 允许工具 |
| --- | --- |
| `coordinator` | 无 |
| `monitoring` | 无 |
| `remediation` | 无 |
| `logs` | `query_logs` |
| `metrics` | `query_metrics`, `get_dependencies`（benchmark 等价模式下 + 5 个 DB 工具） |
| `database` | 5 个 `get_db_*` |
| `changes` | `query_changes`, `get_config_diff` |
| `verifier` | `fetch_evidence_by_ids` |
| `reporter` | `fetch_evidence_by_ids` |
| `single` | logs/metrics/deps/changes/config diff/fetch（等价模式下 + 5 个 DB 工具） |

**ACL 是上限，不是默认值**：`InvestigationTask.allowed_tools` 只能从角色 ACL 中收窄，`AgentContext.role_authority` 会拒绝任何越权或重复项。

## 3. 安全对象

### 3.1 `AgentContext`（不可变）

```python
class AgentContext(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id, incident_id, run_id, role
    allowed_tools: tuple[str, ...]
    allowed_evidence_scope: tuple[Identifier, ...]
    remaining_tool_calls: int
```

- `frozen=True`：签发后无法修改。
- `role_authority` 校验 `allowed_tools ⊆ ROLE_TOOL_ACL[role] (+ DB tools for metrics/single)`。
- `remaining_tool_calls` 在签发时快照，用于提示与二次校验。

### 3.2 `ContextAuthority`（[`security/authorization.py`](../../src/incident_lens/security/authorization.py)）

- `issue(role, remaining, tools)`：记录 `id(context) -> token`，返回 context。
- `validate(context, tool_name=None)`：检查 context 由本 registry 签发（对象身份必须是同一实例）、内容 JSON 与签发时逐字节一致（防替换/篡改），并检查工具在 ACL 内。
- `_issued` 以 `id(context)` 为键，同时保存 context 引用与签发时的 `model_dump_json()`；由于 `frozen=True` 且内容比对，伪造或修改后的 context 无法通过校验。

### 3.3 `ScopedClient`

`ToolRegistry.client(context)` 返回 `ScopedClient`，只暴露 `context` 与 `execute(tool, args)`，避免把 registry 本体交给 Agent。`RoleScopedEvidenceClient` 是结构化 Protocol，用于依赖注入与测试。

## 4. 执行流程（`ToolRegistry.execute`，L142）

```text
1. 生成 call_id = "call-" + uuid4
2. 检查 registry 未 frozen（两次：入口与扣预算前）
3. authority.validate(context, tool_name)
4. tool_name 必须存在于 ARGUMENT_MODELS
5. args 必须是 dict
6. ARGUMENT_MODELS[tool].model_validate(args)
7. 若带 service，必须属于该 case 的服务集合
8. 原子扣减工具预算：达到上限 → error = BUDGET_EXCEEDED
9. 执行：
   - fetch_evidence_by_ids：只读 shared（single 额外读自己的账本），引用必须可见
   - 其他：单线程 `ThreadPoolExecutor` + `future.result(timeout=self._timeout_seconds)`
     （registry 默认 5s；运行时传入 `min(10s, max_wall_seconds)`）
10. 截断到 limit，设置 next_cursor
11. 未冻结时把记录写入该 context 的 observed ledger
12. 任何异常 → 映射 error_code（不抛给调用方）
13. 追加脱敏事件（不记录原始参数/证据文本/异常文本）
```

### 4.1 错误码

| error_code | 触发条件 |
| --- | --- |
| `FORBIDDEN` | 上下文无效、工具越权、未共享证据、registry 已冻结 |
| `BAD_ARGS` | 参数校验失败（类型、窗口、limit、枚举） |
| `NOT_FOUND` | 服务不存在 |
| `SOURCE_INVALID` | 数据源记录无法解析 |
| `TIMEOUT` | 工具执行超过 `timeout_seconds` |
| `SOURCE_UNAVAILABLE` | 文件系统/IO 错误 |
| `BUDGET_EXCEEDED` | 工具调用数达到上限 |

失败结果必须 `records=[]`、`next_cursor=None`（`ToolResult` 不变量强制）。

## 5. 查询账本（observed ledger）

- 每个 context 一个 `dict[evidence_id, EvidenceRecord]`。
- **只有实际执行成功的查询记录才进入账本**；超时任务即使后来完成也不会写账本（`executor.shutdown(wait=False, cancel_futures=True)` + 冻结检查）。
- `publish(context, ids)` 要求 `ids ⊆ ledger`，否则 `PermissionError`；发布只做深拷贝到 `_shared`。
- `fetch_evidence_by_ids` 对 verifier/reporter 只能看 `_shared`；对 `single` 额外可看自己的 ledger，但不能看其他任务的。
- 这条链路保证："说的必须是自己查过的，审查的必须是已公开的"。

## 6. 证据加载与路径安全（[`tools/provider.py`](../../src/incident_lens/tools/provider.py)）

`EvidenceProvider` 只暴露公开证据，不提供任何私有 oracle 接口。

### 6.1 根目录

- 根目录先 `absolute()`，拒绝 symlink/junction（Windows reparse point）。
- `resolve(strict=True)` 后必须是目录。

### 6.2 固定白名单

```python
PUBLIC_FILES = {incident.json, logs.jsonl, metrics.csv,
                changes.jsonl, configs.jsonl, database.jsonl}
CASE_ID = ^incident_[0-9]{3,}$
```

`_public_path(incident_id, filename)` 要求 incident_id 匹配 `CASE_ID`、filename 在白名单中，再走 `_safe_path("incidents", incident_id, "public", filename)`。

### 6.3 `_safe_path`

逐段拒绝：

- `""`、`.`、`..`；
- 包含 `/`、`\`、`:` 的段；
- 任何 symlink / junction；
- 最终 `resolve()` 必须 `is_relative_to(root)`。

这防止 `../private/oracle.json`、符号链接逃逸、Windows 盘符/ADS 等路径攻击。

### 6.4 元数据白名单

`METADATA_FIELDS` 限定每类证据可暴露的字段：

- database：`category`、`metric_name`、`value`、`unit`、连接/池、`session_id`、`state`、`wait_event`、`blocked_by`、`duration_ms`、`query_fingerprint`、`health_status`；
- logs：`severity`、`request_id`、`origin`；
- changes：`change_id`、`change_type`；
- configs：`change_id`；
- metrics：`metric_name`、`value`、`unit`。

`ANSWER_FIELDS`（`root_cause_code`、`culprit_service`、`failure_mode`、`decisive_evidence_ids`、`misleading_evidence_ids`、`is_identifiable`、`generator_seed`）**永远不会**进入公开 evidence。

## 7. 冻结与 STOP 的交互

`stop` 节点按顺序：

1. `task_manager.stop()`；
2. `registry.freeze()`；
3. 取消在途 worker 与模型调用；
4. 补记 `CANCELLED`；
5. `stop_controller.stop()`。

冻结后：

- 新 `create_context` 抛 `PermissionError`；
- `execute` 返回 `FORBIDDEN`；
- `publish` 抛 `PermissionError`；
- 已在执行中的只读任务即使完成也不会写账本。

## 8. 数据泄漏防线（多层）

| 层 | 机制 |
| --- | --- |
| 路径 | `EvidenceProvider._safe_path` + 固定文件名白名单 |
| 记录 | `EvidenceRecord.source_path` 只能是 `public/` 或 `topology/services.yaml` |
| 字段 | `METADATA_FIELDS` 白名单，`ANSWER_FIELDS` 永不公开 |
| 工具 | ACL + 参数模型 + 服务白名单 |
| 引用 | 执行账本 + 发布校验 + `fetch_evidence_by_ids` 可见性 |
| 状态 | `consistent_provenance` 引用闭包 |
| 评测 | `private/oracle` 与公开包物理分离，评测器单独读取 |

## 9. 新增工具的检查清单

- [ ] 在 `tools/arguments.py` 定义参数模型并注册到 `ARGUMENT_MODELS`。
- [ ] 在 `tools/registry.py` 的 `HANDLERS` 中注册实现。
- [ ] 在 `security/context.py` 的 `ROLE_TOOL_ACL` 中只授予必要角色。
- [ ] 确保实现只读、无副作用、不访问 `private/`。
- [ ] 在 `tools/provider.py` 中新增数据加载时遵循白名单与 `_safe_path`。
- [ ] 增加 ACL、路径逃逸、超时、预算、错误码测试。
