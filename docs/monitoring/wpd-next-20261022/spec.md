# WP-D next 批次只读监控规范（20261022）

## 1. 目的与边界

对 `results/v16/wp-d` 下的 WP-D 批次（桥接版 + API 版）做**纯只读**进度监控，输出固定格式的中文汇报。

只允许读取与进程查询；**不得**启动/终止/重跑/修复任何调查或批次，**不得** kill 进程，**不得**执行
`scripts/run_wpd_batch.py --execute / --prepare`，**不得**写入任何产物目录
（`batch-state.json`、`supervisor-status.json`、`observability/*`、`batch-events.jsonl` 均不得改写），
**不得**覆盖或删除历史产物，**不得**执行 `analysis/wp_d/serve_bridge_response.py` 或任何替身响应脚本。
桥接待服务请求**只统计数量，不代为回应**（由执行该批次的另一个 agent 负责）。

汇报只陈述观测到的事实：不宣称准确率/可靠率，不宣称「严格公平比较」，未知一律写「未知」。

## 2. 监控对象（动态发现）

| 批次 | 发现方式 | 当前结果 |
|---|---|---|
| 桥接版 | 用户给定目录 `results/v16/wp-d/next-bridge-max4-20261022-092104` | 存在 |
| API 版 | 扫描 `results/v16/wp-d/*/batch-manifest.json`（必要时扩到整个 `results` 树），读取 JSON 的 `plan.mode`，`mode == "api"` 即为 API 版批次目录（通常命名 `next-api-*`） | 尚未出现 |

API 版未出现时，附加只读补充（用于说明其仍处于准备/readiness 阶段）：

1. `results/v16/wp-d` 下最近 1 小时内新建的目录名；
2. 命令行含 `--plan configs/wp_d/api-plan.json` 的 python 进程：
   `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*api-plan*" }`；
3. `local_oracles/wp-d/current-readiness.json` 是否存在（API 计划要求的 readiness 记录）。

## 3. 状态来源（每个批次目录）

| 文件 | 读取字段 |
|---|---|
| `supervisor-status.json` | `state`、`counts`(planned/started/completed/failed/interrupted/active)、`max_concurrency`、`active[]`(slot/incident/variant/worker_pid/worker_elapsed_seconds/heartbeat_utc) |
| `batch-state.json` | `slots.<slot>[]`：`status`(running/completed/failed/interrupted)、`key.incident`、`key.variant`、`exit_code`、`ended_at_utc` |
| `runs/slot-NNN/attempt-*/observability/status.json` | `lifecycle`、`round_index`、`physical_requests`、`tool_calls`、`last_event`、`last_event_at`、`heartbeat_at`、`active_requests`(键数)、`observability.degraded/io_failures/events_complete/active_io_errors` |
| `runs/slot-NNN/attempt-*/_bridge/requests` 与 `_bridge/responses` | 文件数差 = 待服务请求数（只统计） |
| `runs/slot-NNN/attempt-*/verification.json`、`result.json` | `termination_reason`、`outcome`、`protocol_valid`、`source_unchanged`、`source_drift`、`runtime_failure`、`stop_completion`、`status`、`root_cause` |
| `batch-events.jsonl` | 尾部若干行（批次级事件与时间戳） |

读取方式：一次性读取后立即释放句柄（`Get-Content -Raw | ConvertFrom-Json`），不持有文件句柄。
活性判断必须结合 `heartbeat_at` + `active_requests` + `physical_requests` + `last_event` 共同进行，
**不得**仅凭 `lifecycle=running` 或 supervisor `state=batch_running` 断言存活。

## 4. 槽位状态判定口径

- 批次层槽位状态以 `batch-state.json` 的 `status` 为准；`supervisor-status.json` 的 `counts` 需与之交叉核对。
- `run_wpd_batch.py::assess` 判 `completed` 需同时满足 `protocol_valid`、`source_unchanged`、
  `stop_completion`、`runtime_failure=false`、`lifecycle=="completed"`、journal 未 degraded；否则为 `failed`。
- 进程退出码为 0 但 `assess` 判 failed 的槽位，**必须**结合 `verification.json` 的 `source_drift` 列出具体漂移文件，
  归因为「环境/源码漂移」，不得归因为模型能力或运输层超时。

## 5. 结果结论判定口径

按 `analysis/wp_d/summarize.py::classify` 的顺序：

1. `protocol_valid is False` → 协议无效；
2. `source_unchanged is False` → **source_drift**（此时不得判为正常弃权或正确诊断）；
3. `runtime_failure is True` → 运行失败；
4. `protocol_valid`/`stop_completion` 非真 → 终止未验证；
5. `status == "INCONCLUSIVE"` 且 `root_cause is None` → 正常弃权候选；
6. `root_cause` 非空 → 诊断候选。

映射到汇报取值：**正确诊断 / 正常弃权 / 错误弃权 / 运行失败 / 未知**。
候选 ≠ 正确：`diagnosis_correct`、`evidence_supported`、`abstention_appropriate` 留给独立评估/人工复核，
监控过程**不自动读取私有 Oracle**（`local_oracles/incidentbench_v16_dev/rca/incidents/*/private/benchmark_oracle.json`）。

## 6. 汇报格式（每次执行均输出）

桥接版与 API 版各一张表，表头固定：

```
| 批次 | Slot | 案例 | 架构 | 运行情况 | 距上次汇报的新进展 |
```

- API 版无目录时保留表头并写「批次目录尚未出现」+ 上述只读补充。
- 「运行情况」取值：未启动 / 进行中（第 N 轮，物理请求 X，工具 Y，阶段=last_event，心跳=heartbeat_at，活跃请求=active_requests 键数）/ 正常完成（终止原因或 exit_code）/ 运行失败（原因）/ 未知。
- 若该 slot 已有 `verification.json` 或 `result.json`，**另起一行**写结果结论；没有写「未知」。
  不得从报告正文推断结论。
- 「距上次汇报的新进展」：比较本轮与上一轮 `round_index`/`physical_requests`/`tool_calls`，
  写「推进 N 轮 / 请求 +X / 工具 +Y」或「无变化」。
- 活跃 slot 的 `heartbeat_at` 距当前超过 120 秒且 `last_event` 无更新 → 标注「疑似停滞（心跳已过 X 秒）」，
  **但不得因此终止或重启**。
- 表后附一行摘要：批次 state、各项计数、并发上限、待服务桥接请求总数、是否出现异常并注明归因
  （运输层 / 环境 / 代码；Provider 单次超时属正常重试范围；无法归因写「无法归因」），
  并注明本次读取时间与批次最近一次事件时间。

## 7. 验证步骤

1. `supervisor-status.json` 与 `batch-state.json` 的槽位状态与计数交叉一致；
2. 每个 slot 的 `observability/status.json` 可读且 `physical_requests`/`tool_calls` 与 `verification.json`
   的 `llm_requests`/`bridge_requests` 不矛盾；
3. `_bridge/requests` 与 `_bridge/responses` 文件数差 ≥ 0，全批次待服务请求数 = 各 slot 差值之和；
4. `batch-events.jsonl` 尾部 `SLOT_ENDED` 与 `batch-state.json` 的 `ended_at_utc` 一致；
5. API 版发现：全 `results` 树内 `plan.mode` 取值集合已枚举，无遗漏。

## 8. 需人工决策的事项（本规范不代替决策）

- 源码漂移（`configs/wp_d/api-protocol.json`、`configs/wp_d/bridge-protocol.json`、`scripts/run_status.py`
  在批次运行期间被修改）导致 slot-001/002/004 被 `assess` 判 failed：是否在源码冻结后另开目录重跑。
- slot-005 当前有 1 个待服务桥接请求：由执行该批次的 agent 服务，监控方不代为响应。
- API 版 readiness 记录缺失：需先产出 `local_oracles/wp-d/current-readiness.json` 才能进入真实调用。
