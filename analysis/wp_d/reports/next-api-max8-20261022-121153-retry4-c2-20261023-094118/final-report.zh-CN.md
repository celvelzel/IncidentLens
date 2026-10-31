# WP-D API 批次第四轮失败槽位补跑报告（并发 2）

- 原始批次：`results/v16/wp-d/next-api-max8-20261022-121153`
- 补跑 ID：`next-api-max8-20261022-121153-retry4-c2-20261023-094118`
- 补跑轮次：第 4 轮
- 补跑窗口：2026-10-23 09:43:53 至 10:01:23（Asia/Shanghai），共 1,050 秒
- 授权范围：全部 10 个仍技术失败的槽位；slot-001 新增 `attempt-005`（父尝试 `attempt-004`），其余 9 个槽位新增 `attempt-004`（父尝试 `attempt-003`）
- 未重跑：slot-012（`attempt-002` 已正常完成）、29 个原正常完成槽位
- 模型与协议：`deepseek-v4.1-flash-1017`，temperature 0，cache off，json_schema，原预算、请求等待、传输重试与结构修复策略不变
- 并发：2（用户 2026-10-23 明确授权由原批次 8 降至 2，已记录在 `retry-manifest.json`）
- 结论：10 个槽位各启动 1 次新调查；全部再次因 HTTP 429 限流技术失败，保留原失败状态；未产生 `attempt-006` 或其他追加尝试

## 1. 冻结边界校验

| 检查项 | 结果 |
| --- | --- |
| batch-manifest 冻结输入 | 224 项全部一致，0 项漂移 |
| batch-manifest SHA-256 | 补跑前后均为 `98232a6bc83d6c2aa16a5e44d3f918b8633419e0c2bd7c76aa52d45a3d50eaf8` |
| 历史 attempt 目录树 | 62 个目录树一致：40 个 `attempt-001`、11 个 `attempt-002`、10 个 `attempt-003`、slot-001 的 `attempt-004`；全部登记产物哈希匹配 |
| 原 attempt 的 scope/trace/result/verification/report/usage | 未覆盖、未删除、未改名、未改写 |
| 新 attempt scope 指纹 | 10/10 与对应父尝试及原始 scope 的 `source_commit`、`retest_source_sha256`、`runtime_config_sha256`、`dataset_revision`、`effective_model_parameters` 一致 |
| 工作区提交 | HEAD `50467d2c0e9376c7a7d401714c68f49edc7184a1`，与原始 scope 的 `source_commit` 一致 |
| 槽位身份与 repeat | 10/10 与 batch-manifest 一致，repeat 均为 0 |
| 执行前既有新 attempt | 9 个槽位无 `attempt-004`；slot-001 的既有 `attempt-004` 作为本轮父尝试，未被改写 |
| 原 worker 存活情况 | 执行前与执行后均无存活 worker |
| 槽位租约 | 10/10 预检可获取，无租约冲突 |
| 并发 | 2，按用户授权覆盖原批次 8；冻结输入与模型参数未变 |
| readiness | 沿用原批次授权；未创建、未伪造 readiness 记录 |
| 新 attempt 数量 | slot-001 恰好 1 个 `attempt-005`，其余 9 个各有 1 个 `attempt-004`；无 `attempt-006` |
| 非目标槽位 | slot-012 及 29 个正常完成槽位均未新增 attempt |
| 最终矩阵 | 40 个槽位，每槽位仅 1 条选定结果 |

## 2. 补跑执行结果

| 槽位 | incident | variant | 原 attempt-001 终止 | 本轮父尝试 | 新 attempt | 新 attempt 终止 | 失败阶段 | HTTP | tokens | 运行秒数 | 最终选择 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| slot-001 | incident_3010 | dynamic_no_verifier | BUDGET_EXHAUSTED / FAILED | attempt-004 / 429 | attempt-005 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 13 | 32,286 | 93 | 保留原失败 |
| slot-004 | incident_3010 | single | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 6 | 12,025 | 40 | 保留原失败 |
| slot-010 | incident_3004 | full | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 19 | 64,529 | 212 | 保留原失败 |
| slot-020 | incident_3008 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 10 | 8,016 | 64 | 保留原失败 |
| slot-022 | incident_3003 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | coordinate | 17 | 28,331 | 180 | 保留原失败 |
| slot-026 | incident_3009 | full | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 7 | 5,072 | 30 | 保留原失败 |
| slot-028 | incident_3006 | full | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 20 | 46,239 | 151 | 保留原失败 |
| slot-032 | incident_3007 | single | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | verify | 27 | 62,438 | 270 | 保留原失败 |
| slot-035 | incident_3002 | full | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | dispatch | 24 | 98,138 | 291 | 保留原失败 |
| slot-039 | incident_3001 | full | UNRECOVERABLE_ERROR / FAILED | attempt-003 / 429 | attempt-004 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | verify | 8 | 15,196 | 62 | 保留原失败 |

- 10 个新 attempt 的 `protocol_valid`、`source_unchanged`、`stop_completion` 均为 true，产物完整；`runtime_failure=true`，不满足替换条件。
- 失败详情均为 `RATE_LIMITED`、HTTP 429、`provider_error_code=rate_limit_exceeded`、`retryable=true`、无 `Retry-After`，在 `http_attempt_index=3` 处耗尽 2 次传输重试（退避 2 秒、4 秒）。
- 失败阶段分布：`dispatch` 6 个（slot-001、004、020、026、028、035）、`coordinate` 2 个（slot-010、022）、`verify` 2 个（slot-032、039）。
- 本轮调查完成度明显高于前几轮：slot-032 已运行 27 次 HTTP、slot-035 24 次、slot-010 19 次、slot-028 20 次，单槽位最长 291 秒；但在最终阶段仍被 429 终止。
- 编排器按原批次 `stop_on_failure` 策略在观察到失败后暂停派发，待活动槽位结束后仅恢复尚未启动的槽位，未重启任何已失败槽位。

## 3. 最终选择结果

选择规则保持不变：原技术失败槽位只有在产物完整、身份与冻结条件匹配、`protocol_valid=true`、`source_unchanged=true`、`stop_completion=true`、`runtime_failure=false` 且正常终止时，才由新 attempt 替换。

- 10 个目标槽位的新 attempt 均为技术失败，不具备替换资格，最终选择保留原 `attempt-001` 失败状态，`selection_reason=original_technical_failure_retained_no_eligible_retry`。
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
| 第 3 轮新增 1 个 attempt（slot-001） | 7 | 5,077 | 4,585 | 492 |
| 第 4 轮新增 10 个 attempt | 151 | 372,270 | 335,245 | 37,025 |
| 全部历史 attempt 合计 | 1,076 | 7,174,704 | 6,628,242 | 546,462 |

第 4 轮 151 次请求中部分未返回 token 用量，`measured_total_tokens` 为不完整的下界；上表按实测值汇总。

## 5. 审计产物

目录：`analysis/wp_d/reports/next-api-max8-20261022-121153-retry4-c2-20261023-094118/`

| 文件 | 用途 |
| --- | --- |
| `retry-manifest.json` | 冻结的第四轮补跑清单：逐槽父尝试与新尝试、输入指纹、并发覆盖说明、readiness 引用 |
| `retry-manifest.sha256` | 补跑清单哈希 |
| `retry-state.json` | 10 个槽位的派发、完成、失败、暂停与恢复状态 |
| `retry-supervisor-status.json` | 补跑结束时的活动槽位与心跳快照 |
| `batch-state.before-retry.json` | 补跑前的 batch-state 快照 |
| `final-selection.json` | 40 槽位逐条选择记录，含 original/selected/candidates、资格检查、产物哈希、usage |
| `final-selection.csv` | 40 槽位选择清单，一行一槽 |
| `final-matrix.csv` | 40 槽位最终选定矩阵 |
| `orchestrator.py` | 本轮分析侧编排脚本，复用现有单案例入口、租约和产物评估逻辑 |

每个新 attempt 目录内另有 `retry-provenance.json`，记录原 attempt、父尝试、slot、incident、variant、repeat、开始时间、输入指纹、状态、退出码、产物哈希及 readiness 引用。

## 6. 限制说明

- 并发由 8 降至 2 是用户明确授权的偏离，冻结输入、模型参数、预算与恢复策略均未修改；本轮结果与原始批次及其他并发条件下的运行不构成严格公平比较。
- 10 个槽位再次因 HTTP 429 限流终止，属于 Provider 运输层限制，不对应模型诊断能力；部分槽位在限流前已完成较多轮次，但仍未形成可验收的最终结果。
- 第 3 轮并发 1 的 slot-001 单槽尝试与第 4 轮并发 2 的 10 槽尝试均在同一个 429 错误码处失败，说明仅降低外部槽位并发不足以规避该限流。
- 未修改 `src`、`scripts`、`configs`、`prompts`、`tests`、依赖、公共数据、Oracle 或原始 batch-manifest；未提交、未推送任何项目代码。
