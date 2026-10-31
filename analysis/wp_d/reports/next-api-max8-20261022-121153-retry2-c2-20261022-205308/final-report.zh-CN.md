# WP-D API 批次第二轮失败槽位补跑报告（并发 2）

- 原始批次：`results/v16/wp-d/next-api-max8-20261022-121153`
- 补跑 ID：`next-api-max8-20261022-121153-retry2-c2-20261022-205308`
- 补跑轮次：第 2 轮（新尝试为 `attempt-003`，父尝试为 `attempt-002`）
- 补跑窗口：2026-10-22 21:05:49 至 21:08:54（Asia/Shanghai），共 105 秒
- 授权范围：首轮补跑后仍技术失败的 10 个槽位：slot-001、004、010、020、022、026、028、032、035、039
- 未重跑：slot-012（首轮 `attempt-002` 已正常完成）、29 个原正常完成槽位
- 模型与协议：`deepseek-v4.1-flash-1017`，temperature 0，cache off，json_schema，原预算、请求等待、传输重试与结构修复策略不变
- 并发：2（用户明确授权由原批次 8 降至 2，已在 `retry-manifest.json` 中记录）
- 结论：10 个槽位各启动 1 次 `attempt-003`；全部再次因 HTTP 429 限流技术失败，保留原失败状态；未产生 `attempt-004`

## 1. 冻结边界校验

| 检查项 | 结果 |
| --- | --- |
| batch-manifest 冻结输入 | 224 项全部一致，0 项漂移 |
| batch-manifest SHA-256 | 补跑前后均为 `98232a6bc83d6c2aa16a5e44d3f918b8633419e0c2bd7c76aa52d45a3d50eaf8` |
| 历史 attempt 目录树 | 50 个目录树一致：40 个 `attempt-001` + 10 个 `attempt-002`，全部登记产物哈希匹配 |
| 原 attempt 的 scope/trace/result/verification/report/usage | 未覆盖、未删除、未改名、未改写 |
| 新 attempt scope 指纹 | 10/10 与对应 `attempt-002` 及原始 scope 的 `source_commit`、`retest_source_sha256`、`runtime_config_sha256`、`dataset_revision`、`effective_model_parameters` 一致 |
| 工作区提交 | HEAD `50467d2c0e9376c7a7d401714c68f49edc7184a1`，与原始 scope 的 `source_commit` 一致 |
| 槽位身份与 repeat | 10/10 与 batch-manifest 一致，repeat 均为 0 |
| 执行前既有新 attempt | 未发现任何 `attempt-003` 目录，无他人补跑 |
| 原 worker 存活情况 | 无记录中的存活 worker |
| 槽位租约 | 10/10 预检可获取，无租约冲突 |
| 并发 | 2，按用户授权覆盖原批次 8；冻结输入与模型参数未变 |
| readiness | 沿用原批次授权；未创建、未伪造 readiness 记录 |
| 新 attempt 数量 | 每槽位恰好 1 个 `attempt-003`，无 `attempt-004` |
| 非目标槽位 | slot-012 及 29 个正常完成槽位均未新增 attempt |
| 最终矩阵 | 40 个槽位，每槽位仅 1 条选定结果 |

## 2. 补跑执行结果

`attempt-002` 为本轮 10 个槽位的父尝试，均为首轮补跑的技术失败尝试。

| 槽位 | incident | variant | 原 attempt-001 终止 | attempt-002 终止 | attempt-003 终止 | 失败阶段 | HTTP | tokens | 最终选择 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| slot-001 | incident_3010 | dynamic_no_verifier | BUDGET_EXHAUSTED / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 9 | 5,083 | 保留原失败 |
| slot-004 | incident_3010 | single | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 9 | 4,981 | 保留原失败 |
| slot-010 | incident_3004 | full | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 7 | 5,075 | 保留原失败 |
| slot-020 | incident_3008 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 7 | 5,077 | 保留原失败 |
| slot-022 | incident_3003 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 3 | 0 | 保留原失败 |
| slot-026 | incident_3009 | full | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 3 | 0 | 保留原失败 |
| slot-028 | incident_3006 | full | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 8 | 7,861 | 保留原失败 |
| slot-032 | incident_3007 | single | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 9 | 4,914 | 保留原失败 |
| slot-035 | incident_3002 | full | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 3 | 0 | 保留原失败 |
| slot-039 | incident_3001 | full | UNRECOVERABLE_ERROR / FAILED | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 3 | 0 | 保留原失败 |

- 10 个 `attempt-003` 的 `protocol_valid`、`source_unchanged`、`stop_completion` 均为 true，产物完整；`runtime_failure=true`，不满足替换条件。
- 失败详情均为 `RATE_LIMITED`、HTTP 429、`provider_error_code=rate_limit_exceeded`、`retryable=true`、无 `Retry-After`，在 `http_attempt_index=3` 处耗尽 2 次传输重试（退避 2 秒、4 秒）。
- 6 个槽位在 `dispatch` 阶段失败，失败前已成功完成 1–6 次请求（slot-001、004、010、020、028、032）；4 个槽位在 `coordinate` 阶段失败（slot-022、026、035、039）。
- 按并发 2 每批派发两个槽位，批次开始时间分别为 21:05:49、21:07:00、21:07:34/35、21:07:49、21:08:40；单槽位运行时长 14–70 秒。
- 未发生暂停恢复：所有槽位按序派发，前序槽位结束后派发下一对。

## 3. 最终选择结果

选择规则保持不变：原技术失败槽位只有在产物完整、身份与冻结条件匹配、`protocol_valid=true`、`source_unchanged=true`、`stop_completion=true`、`runtime_failure=false` 且正常终止时，才由新 attempt 替换。

- 10 个目标槽位的 `attempt-003` 均为技术失败，不具备替换资格，最终选择保留原 `attempt-001` 失败状态，`selection_reason=original_technical_failure_retained_no_eligible_retry`。
- `slot-012` 继续采用首轮 `runs/slot-012/attempt-002`（INCONCLUSIVE / ABSTAINED，`runtime_failure=false`），本轮未重跑。
- 29 个原正常完成槽位继续采用原结果，未重跑。
- 最终 40 个槽位：4 个 RESOLVED、26 个 INCONCLUSIVE、10 个技术失败；正常完成 30 个。

| variant | 槽位数 | selected RESOLVED | selected INCONCLUSIVE | selected 技术失败 | 替换数 |
| --- | --- | --- | --- | --- | --- |
| full | 10 | 1 | 4 | 5 | 0 |
| dynamic_no_verifier | 10 | 1 | 6 | 3 | 0 |
| single | 10 | 2 | 6 | 2 | 0 |
| fixed | 10 | 0 | 10 | 0 | 1 |
| 合计 | 40 | 4 | 26 | 10 | 1 |

本报告仅陈述观测到的运行结果与选择结果，不据此宣称准确率、可靠率或严格公平比较。

## 4. 资源消耗

| 范围 | HTTP 请求 | total tokens | prompt tokens | completion tokens |
| --- | --- | --- | --- | --- |
| 原 40 个 attempt | 816 | 6,735,229 | 6,233,686 | 501,543 |
| 第 1 轮新增 11 个 attempt | 41 | 29,137 | 24,841 | 4,296 |
| 第 2 轮新增 10 个 attempt | 61 | 32,991 | 29,885 | 3,106 |
| 全部历史 attempt 合计 | 918 | 6,797,357 | 6,288,412 | 508,945 |

`attempt-003` 的 61 次请求中有 53 次未返回 token 用量，`measured_total_tokens` 为不完整的下界；上表按实测值汇总。

## 5. 审计产物

目录：`analysis/wp_d/reports/next-api-max8-20261022-121153-retry2-c2-20261022-205308/`

| 文件 | 用途 |
| --- | --- |
| `retry-manifest.json` | 冻结的第二轮补跑清单：槽位、incident、variant、repeat、父尝试、输入指纹、并发覆盖说明、readiness 引用 |
| `retry-manifest.sha256` | 补跑清单哈希 |
| `retry-state.json` | 10 个槽位的派发、完成、失败状态与 preflight 记录 |
| `retry-supervisor-status.json` | 补跑结束时的活动槽位与心跳快照 |
| `final-selection.json` | 40 槽位逐条选择记录，含 original/selected/candidates、资格检查、产物哈希、usage |
| `final-selection.csv` | 40 槽位选择清单，一行一槽 |
| `final-matrix.csv` | 40 槽位最终选定矩阵 |
| `orchestrator.py` | 本轮补跑的分析侧编排脚本，复用现有单案例入口、租约和产物评估逻辑 |

每个 `attempt-003` 目录内另有 `retry-provenance.json`，记录原 attempt、父尝试、slot、incident、variant、repeat、开始时间、输入指纹、状态、退出码、产物哈希及 readiness 引用。

## 6. 限制说明

- 并发由 8 降至 2 是用户明确授权的偏离，冻结输入、模型参数、预算与恢复策略均未修改；因此本轮结果与原始批次及其他并发条件下的运行不构成严格公平比较。
- 10 个槽位的 `attempt-003` 均因 HTTP 429 限流在运输层终止，属于 Provider 限流而非模型诊断能力证据；部分槽位在限流前已完成若干请求，同样不构成完整调查结果。
- 现有恢复策略只允许 3 次物理尝试、退避上限 20 秒；Provider 限流窗口长于该窗口时，降低并发仍可能无法完成调查。本次未修改该策略。
- 未修改 `src`、`scripts`、`configs`、`prompts`、`tests`、依赖、公共数据、Oracle 或原始 batch-manifest；未提交、未推送任何项目代码。
