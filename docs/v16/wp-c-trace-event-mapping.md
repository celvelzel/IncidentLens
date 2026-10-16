# WP-C：T5 Trace 与事件映射

核对源：原仓库 `results/v16/live-e2e/g1a-20261015-01/incident-2001-full/` 的 `trace.json`、`result.json`、`report.md`、`scope.json`、`verification.json`，以及父目录 `protocol-retest-v5-generous.json`。本地浏览器使用上述五个公开 companion 的逐字节副本 `results/v16/wp-c-real-replay/t5/`，未复制 private oracle。Trace SHA256：`c6f998eed2232eb2401e11c8b3b7ade4ea99af72b54e602826f038b79d2fd74d`。

录制：`incident_2001` / `run-801a52cff3a5491aaf5df79b8f543614`，REAL `deepseek-v4-flash-0731`，full / cache off。核实 103 个事件、12 次工具调用、21 次逻辑与物理请求（18 `LLM_CALL` + 3 `MODEL_FAILURE`）、2 个 INVESTIGATE 轮次、5 次 Coordinator 决策、4 个最终 Finding、7 条公开证据。elapsed / token / cost 为 null。下文数字用于描述这份已核对档案，UI 不硬编码这些计数或索引。

## Schema → 展示

| 原始事件 | T5 数量 | 展示与状态投影 |
|---|---:|---|
| TASK_ASSIGNED / RUNNING / COMPLETED / FAILED | 16 / 16 / 13 / 3 | 同 attempt 的实际状态；不生成对话 |
| DECISION | 5 | assignments / 原始 reason / expected discriminator；hypothesis updates 为提议 |
| TOOL_CALL | 12 | 合法成功记录首次成为可见证据；查询参数与原始 ID 保留 |
| MERGE | 2 | Finding 去重发布、Hypothesis 已提交快照 |
| HYPOTHESIS_RECONCILED | 2 | 已提交假设变化；重复快照不产生重复历史 |
| REVIEW | 4 | verdict、rationale、对象、两个版本哈希、blocking / optional checks、引用 |
| LLM_CALL / MODEL_FAILURE | 18 / 3 | 请求计数包括失败；错误与恢复另列 |
| MODEL_RECOVERED | 3 | 通过 call_ids 对应失败，非相邻推断 |
| FINALIZE_REJECTED | 1 | 展示原始阻断理由，不把 sufficient 当作通过 Gate |
| FINALIZE_RESUMED_AFTER_REVIEW | 1 | 原始 review_event_id / selected hypothesis / decision index |
| DIAGNOSIS_ACCEPTED | 1 | 已接受诊断及真实引用 |
| WORKFLOW_STOP_REQUESTED / NORMAL_TERMINATION / REPORT | 1 / 1 / 1 | 停止握手、终止原因/结果；REPORT 才解锁最终报告 |

## 因果过程与已提交假设

| 事件 | 真实内容与解释界限 |
|---|---|
| 5 | 初次派 Metrics / Changes，原始 reason 为查基线与变更 |
| 11 / 12 | 公开 change / config 证据；`db_pool_max 20 → 2; concurrency=120` |
| 28 MERGE | `backend_resource_saturation` 与 `backend_pool_config_regression` 首次 OPEN |
| 39 REVIEW | insufficient；现有变更与 Gateway 症状尚不足以确认因果 |
| 44 | 真正执行的后续任务为 Backend metrics 与 PostgreSQL connections；不是所有审查建议都执行 |
| 50 / 52 | PostgreSQL 30/100 连接、Backend pool_waiters=118 等证据；累计可见证据达到 7 条 |
| 57 MERGE | PostgreSQL exhaustion 首次出现时已是 REJECTED；没有记录 OPEN→REJECTED 跃迁，不补造 |
| 68 / 69 | FINALIZE 提议后提交 pool 与 resource saturation 为 SUPPORTED；PostgreSQL 保持 REJECTED |
| 80 / 81 | 再次 FINALIZE 被 Gate 拒绝：`Competing hypothesis remains unresolved` |
| 91 / 92 | Coordinator 明确区分饱和症状与配置根因；resource saturation 提议后提交 REJECTED，反证 E-003 / E-004 |
| 98 / 99 / 100 | 最终 REVIEW，恢复 finalize，DIAGNOSIS_ACCEPTED |
| 101 / 102 / 103 | STOP，DIAGNOSIS_READY / SUCCESS / stop_completed，最终 REPORT |

数据库故障不是预设正确答案；Trace 中最初一项 pool 假设预测连接数靠近 2，数据库实际 30/100 是区分 PostgreSQL 连接耗尽的证据。最终记录的解释结合 config、118 waiters、Gateway 症状与拓扑；它不是一次 Oracle 准确率评测。

## 四次审查与版本

| REVIEW | verdict | blocking / optional | Hypothesis hash 前缀 | Evidence hash 前缀 |
|---|---|---:|---|---|
| 39 | insufficient | 4 / 2 | d9961f6247d8 | dc133a2182fe |
| 63 | sufficient | 0 / 6 | 见 UI 原始哈希 | fca485660598 |
| 75 | sufficient | 0 / 6 | 见 UI 原始哈希 | fca485660598 |
| 98 | sufficient | 0 / 4 | e1e2b93ea24f | fca485660598 |

第 39 次事件要求 Gateway latency、Backend metrics、其他服务变更隔离及完整 diff；optional 是 PostgreSQL connections 与 Backend logs。后续只按实际 task_id 标记已调度/已完成，不把相似任务或已存在证据自动说成“随后完成”。后续 rationale 明确将部分缺失项目降为 corroboration，并引用早已存在的 change/diff 查询；UI 保留原文与各版本，避免将四轮压缩为一句“审查好评”。第 81 个事件说明独立 Gate 还会阻止 unresolved competing hypothesis。

## Timeout 与来源

三个 PROVIDER_TIMEOUT 通过 call ID 对应恢复：18→27（changes / model-call-4）、32→37（verifier / model-call-8）、84→89（coordinator / model-call-19）。中间有任务重试及其他事件，不能画成相邻的即时恢复。未匹配恢复只显示“当前前缀尚无匹配恢复”，不提前读取后续结论。

scope 记录 source commit `31b4f4031576649282cac5c2f36b70f4a2643dda`、protocol `incidentbench-v1-comp-deepseek-v4-flash-two-case-g1a-live-e2e-generous-retest-v5`；预算 8 rounds / 32 tools / 48 requests / 5400 s，单请求 420 s，development_visible / formal=false。verification 为 protocol_valid=true，但 source_unchanged=false，漂移文件为 `src/incident_lens/orchestration/graph.py`。这只支持有来源限制的真实开发录制展示。
