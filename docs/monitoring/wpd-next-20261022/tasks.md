# WP-D next 批次只读监控任务清单（20261022）

执行规范见同目录 `spec.md`。每轮监控按下列顺序执行，全部为只读操作。

## T1 批次发现

- [x] T1.1 扫描 `results/v16/wp-d/*/batch-manifest.json`，读取 `plan.mode`
- [x] T1.2 桥接版目录固定为 `results/v16/wp-d/next-bridge-max4-20261022-092104`
- [x] T1.3 API 版：未找到 `mode == "api"` 目录 → 记「API 版批次目录尚未出现」
- [x] T1.4 API 版补充证据：`results/v16/wp-d` 近 1 小时新建目录、`--plan configs/wp_d/api-plan.json` 进程、`local_oracles/wp-d/current-readiness.json` 存在性

## T2 桥接版状态采集

- [x] T2.1 `supervisor-status.json`：state / counts / max_concurrency / active[]
- [x] T2.2 `batch-state.json`：逐 slot status、key.incident、key.variant、exit_code、ended_at_utc
- [x] T2.3 逐 slot `observability/status.json`：lifecycle、round_index、physical_requests、tool_calls、last_event、last_event_at、heartbeat_at、active_requests 键数、degraded/io_failures/events_complete/active_io_errors
- [x] T2.4 逐 slot `_bridge/requests` 与 `_bridge/responses` 文件数差（只统计）
- [x] T2.5 逐 slot `verification.json` / `result.json` 存在性与关键字段
- [x] T2.6 `batch-events.jsonl` 尾部事件与时间戳

## T3 交叉校验

- [x] T3.1 supervisor `counts` 与 `batch-state.json` 槽位状态一致
- [x] T3.2 `physical_requests` 与 `verification.json` 的 `llm_requests`/`bridge_requests` 不矛盾
- [x] T3.3 `SLOT_ENDED` 事件时间与 `ended_at_utc` 一致
- [x] T3.4 failed 槽位的 `source_drift` 具体文件已列出并归因（环境/源码漂移）

## T4 汇报输出

- [x] T4.1 桥接版表：逐 slot「运行情况」+「结果结论」两行
- [x] T4.2 API 版表：保留表头，写「批次目录尚未出现」+ 只读补充
- [x] T4.3 「距上次汇报的新进展」按 round/phys/tool 差值计算
- [x] T4.4 摘要行：state、计数、并发上限、待服务请求总数、异常归因、本次读取时间、批次最近事件时间

## 后续轮次

- [ ] T5 下一轮监控：重做一致性快照，比较 round/phys/tool 增量，检查 slot-005 心跳与待服务请求数
- [ ] T6 批次状态变化时（slot-005 结束、批次恢复或失败）重算 counts 与摘要行
