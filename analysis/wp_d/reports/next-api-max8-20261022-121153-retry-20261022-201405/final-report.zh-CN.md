# WP-D API 批次失败槽位补跑与最终选择报告

- 原始批次：`results/v16/wp-d/next-api-max8-20261022-121153`
- 补跑 ID：`next-api-max8-20261022-121153-retry-20261022-201405`
- 补跑窗口：2026-10-22 20:28:30 至 20:30:59（Asia/Shanghai），共 149 秒
- 授权范围：slot-001、004、010、012、020、022、026、028、032、035、039，共 11 个原始 failed 槽位
- 模型与协议：`deepseek-v4.1-flash-1017`，temperature 0，cache off，json_schema，原预算、请求等待、传输重试与结构修复策略不变
- 结论：11 个槽位各启动 1 次新调查；slot-012 正常完成并被选为最终结果，其余 10 个槽位的新调查再次技术失败，保留原失败状态

## 1. 冻结边界校验

| 检查项 | 结果 |
| --- | --- |
| batch-manifest 冻结输入 | 224 项全部一致，0 项漂移 |
| batch-manifest SHA-256 | 补跑前后均为 `98232a6bc83d6c2aa16a5e44d3f918b8633419e0c2bd7c76aa52d45a3d50eaf8` |
| 原 attempt 目录树 | 40/40 槽位一致，280 个原产物哈希全部匹配 |
| 原 attempt 的 scope/trace/result/verification/report/usage | 未覆盖、未删除、未改名、未改写 |
| 新 attempt scope | 11/11 与原 attempt 的 scope JSON 完全一致 |
| 槽位身份与 repeat | 11/11 与 batch-manifest 一致，repeat 均为 0 |
| 执行前既有补跑 | 未发现任何他人补跑的新 attempt 目录，无需纳入 |
| 原 worker 存活情况 | 40 个记录 PID 均不存活 |
| 槽位租约 | 11/11 预检可获取，无租约冲突 |
| 并发 | 8，与原批次一致，未降低 |
| readiness | 沿用原批次 `readiness_skipped=true` / `USER_DIRECTIVE_20261022` 授权；未创建、未伪造 readiness 记录，详见 `readiness-audit.json` |
| 新 attempt 数量 | 每槽位恰好 1 个 `attempt-002`，无 `attempt-003` |
| 非补跑槽位 | 29 个槽位均未新增 attempt |
| batch-state 原记录 | 29 个非补跑槽位记录完全不变；11 个补跑槽位的原 attempt 记录完全不变 |
| 最终矩阵 | 40 个槽位，每槽位仅 1 条选定结果；40 个 selected run_id 互不重复 |

## 2. 补跑执行结果

| 槽位 | incident | variant | 原 attempt 终止 | 新 attempt | 新 attempt 终止 | runtime_failure | HTTP | tokens | 最终选择 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| slot-001 | incident_3010 | dynamic_no_verifier | BUDGET_EXHAUSTED / FAILED | runs/slot-001/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-004 | incident_3010 | single | UNRECOVERABLE_ERROR / FAILED | runs/slot-004/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-010 | incident_3004 | full | UNRECOVERABLE_ERROR / FAILED | runs/slot-010/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-012 | incident_3005 | fixed | BUDGET_EXHAUSTED / FAILED | runs/slot-012/attempt-002 | INCONCLUSIVE / ABSTAINED | false | 11 | 29,137 | 新结果替换 |
| slot-020 | incident_3008 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | runs/slot-020/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-022 | incident_3003 | dynamic_no_verifier | UNRECOVERABLE_ERROR / FAILED | runs/slot-022/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-026 | incident_3009 | full | UNRECOVERABLE_ERROR / FAILED | runs/slot-026/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-028 | incident_3006 | full | UNRECOVERABLE_ERROR / FAILED | runs/slot-028/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-032 | incident_3007 | single | UNRECOVERABLE_ERROR / FAILED | runs/slot-032/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-035 | incident_3002 | full | UNRECOVERABLE_ERROR / FAILED | runs/slot-035/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |
| slot-039 | incident_3001 | full | UNRECOVERABLE_ERROR / FAILED | runs/slot-039/attempt-002 | UNRECOVERABLE_ERROR / RATE_LIMITED(429) | true | 3 | 0 | 保留原失败 |

补跑过程中观察到 1 次失败暂停。首批 8 个槽位中 7 个因 HTTP 429 失败，slot-012 正常完成；待活动槽位全部结束后，编排器记录 1 次暂停，并仅恢复派发尚未启动的 slot-032、035、039，未重启任何已失败槽位。该行为沿用原批次记录中的失败暂停与恢复策略。

## 3. 最终选择结果

选择规则：原技术失败槽位只有在以下条件全部满足时才由新 attempt 替换：

- 产物完整
- 身份与冻结条件匹配
- `protocol_valid=true`
- `source_unchanged=true`
- `stop_completion=true`
- `runtime_failure=false`
- 正常终止，结果为 RESOLVED 或 INCONCLUSIVE

按此规则：

- 29 个原正常完成槽位继续采用原结果，未重跑。
- slot-012 的原技术失败由 `runs/slot-012/attempt-002` 替换。该新 attempt 为正常 INCONCLUSIVE / ABSTAINED，`runtime_failure=false`，全部资格检查通过。
- 其余 10 个槽位的新 attempt 再次技术失败（HTTP 429 `RATE_LIMITED`），不具备替换资格，保留原失败状态；新增失败 attempt 已单独记录，不计入正常完成分母。
- 最终 40 个槽位：4 个 RESOLVED、26 个 INCONCLUSIVE、10 个技术失败；正常完成 30 个，技术失败 10 个。

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
| 新增 11 个 attempt | 41 | 29,137 | 24,841 | 4,296 |
| 全部历史 attempt 合计 | 857 | 6,764,366 | 6,258,527 | 505,839 |

## 5. 审计产物

目录：`analysis/wp_d/reports/next-api-max8-20261022-121153-retry-20261022-201405/`

| 文件 | 用途 |
| --- | --- |
| `retry-manifest.json` | 冻结的补跑清单：槽位、incident、variant、repeat、原 attempt、输入指纹、readiness 引用 |
| `retry-manifest.sha256` | 补跑清单哈希，执行前校验 |
| `retry-state.json` | 11 个槽位的派发、完成、失败、暂停与恢复状态 |
| `retry-supervisor-status.json` | 补跑结束时的活动槽位与心跳快照 |
| `batch-state.before-retry.json` | 补跑前的 batch-state 快照，用于审计原记录未变 |
| `readiness-audit.json` | 原批次 readiness 跳过授权与 endpoint 指纹的只读审计副本 |
| `final-selection.json` | 40 槽位逐条选择记录，含 original/selected/candidates、资格检查、产物哈希、usage |
| `final-selection.csv` | 40 槽位选择清单，一行一槽 |
| `final-matrix.csv` | 40 槽位最终选定矩阵 |
| `orchestrator.py` | 本次补跑的分析侧编排脚本，复用现有单案例入口、租约和产物评估逻辑 |

每个新增 attempt 目录内另有 `retry-provenance.json`，记录原 attempt、父尝试、slot、incident、variant、repeat、开始与结束时间、输入指纹、状态、退出码、产物哈希及 readiness 引用。

## 6. 限制说明

- 10 个槽位的新调查在 3 次 HTTP 请求内即收到 429 限流并终止，属于运输层/Provider 限流失败，不构成对模型诊断能力的证据。
- slot-001、slot-012 的原始 `BUDGET_EXHAUSTED` 分类与停止理由未被修改；slot-001 的新尝试因 429 失败，slot-012 的新尝试正常完成。
- 这 10 个槽位在原矩阵中仍为技术失败，未被转换为 INCONCLUSIVE；原失败 attempt 的全部产物保持不变。
- slot-012 的替换依据是事先声明的技术失败替换规则，而非诊断质量筛选；其最终结果为正常弃权。
- 未修改 `src`、`scripts`、`configs`、`prompts`、`tests`、依赖、公共数据、Oracle 或原始 batch-manifest；未提交、未推送任何项目代码。
