# WP-D HPC 40 槽位实验报告：Atria-Dawn

- 运行 ID：`atria-dawn-dev40-20261025T154709Z`
- 执行日期：2026-10-25/26（UTC 2026-10-25T16:03 起至 2026-10-26T10:22 止，含集群排队空档）
- 入口：`hpc/run_wpd.py`（分支 `codex/hpc-wpd`，提交 `1c6b9e6`，工作区全程干净）
- 结果目录：`results/hpc-wpd/atria-dawn-dev40-20261025T154709Z/`

本报告与旧的 deepseek 批次相互独立：新模型 + HPC 环境是独立实验条件，不构成严格受控的模型因果比较，不预设任何优劣结论。

## 1. 模型与关键参数

| 项目 | 值 |
|---|---|
| 服务商 / 端点 | Intern InkStone，`https://discovery-api.intern-ai.org.cn/v1` |
| 模型（API ID） | **`Atria-Dawn`** |
| readiness 验证 | 计算节点同网络环境真实探测：1 次真实 HTTP 请求、88 token，`provider_compatible: true` |
| 采样 / 缓存 | `temperature: 0.0`，`cache_mode: off` |
| 响应格式 / 思考 | `response_format: json_schema`，`thinking: disabled` |
| 单调查预算 | `max_rounds: 8`、`max_tool_calls: 40`、`max_llm_calls: 64`、`max_wall_seconds: 7200`、`request_timeout: 1200` |
| 内部韧性（冻结配置） | `structured_repair_retries: 1`、传输重试 `max_transport_retries: 2`、`max_physical_attempts_per_call: 4`、退避 2s→20s（jitter none） |
| 批次设计 | Dev10（incident_3001–3010）× 4 变体（`single` / `fixed` / `dynamic_no_verifier` / `full`）× repeat 0，共 40 槽 |
| 随机顺序种子 | `run_order_seed: 14100` |
| 外部槽位并发 | 2（`jobs: 2`；dispatch 内部可并行，故并发 2 ≠ HTTP 并发 2） |
| 失败停机 | `stop_on_failure: true`（任一槽位技术失败即暂停派发，活动槽结束后退出） |
| 分析参数（未执行） | `analysis_seed: 14101`、`bootstrap_samples: 10000`（分析需既有评估流程，不在本次 runtime 内） |
| 运行环境 | Python 3.12.11（73 个锁定依赖）、提交 `1c6b9e6`、Slurm 单节点单 supervisor、无 GPU（h07q1 初始、h07q2 恢复链） |

## 2. 总体结果

- **40/40 槽位全部终态**：`BATCH_FINISHED` 正常收尾；supervisor 共执行 12 次（初始 1 次 + 授权恢复 11 次）。
- **24 槽完成**：3 个 `DIAGNOSIS_READY/SUCCESS` + 21 个 `INCONCLUSIVE/ABSTAINED`。
- **16 槽技术失败**：详见第 4 节分类。
- 全部失败均为 Atria-Dawn **输出可靠性问题**，非服务商/环境故障：零 429 限流、零未恢复传输失败、零 provider 故障。

## 3. 四组结果矩阵（每变体 10 槽）

| 变体 | SUCCESS | INCONCLUSIVE | 技术失败 | 完成率 |
|---|---|---|---|---|
| dynamic_no_verifier | 2 | 5 | 3（1 UNRECOVERABLE + 2 BUDGET_EXHAUSTED） | 7/10 |
| single | 0 | 5 | 5（全部 BAD_ARGS） | 5/10 |
| fixed | 0 | 8 | 2（BAD_ARGS） | 8/10 |
| full | 1 | 3 | 6（5 UNRECOVERABLE + 1 BUDGET_EXHAUSTED） | 4/10 |

SUCCESS 槽位：slot-002（incident_3004 / dynamic_no_verifier）、slot-011（incident_3002 / dynamic_no_verifier）、slot-039（incident_3001 / full）。

## 4. 失败分类（脱敏错误码，16 例）

| 失败原因 / 阶段 | 数量 | 槽位 |
|---|---|---|
| `UNRECOVERABLE_ERROR` @ dispatch — `Tool failed: BAD_ARGS` | 10 | 004, 006, 007, 012, 013, 014, 015, 017, 020, 028 |
| `UNRECOVERABLE_ERROR` @ coordinate — `STRUCTURED_OUTPUT_INVALID` | 2 | 009, 035 |
| `UNRECOVERABLE_ERROR` @ dispatch — `FINDING_IDENTITY_MISMATCH` | 1 | 010 |
| `BUDGET_EXHAUSTED` @ runtime | 3 | 016, 023, 026 |

机制定位（代码级）：工具参数模型为 `StrictModel`（`src/incident_lens/tools/arguments.py`），禁止额外字段；Atria-Dawn 在 `query_metrics` / `get_dependencies` 等调用中混入 `limit` / `tool_name` 等禁用字段 → 参数校验 `BAD_ARGS`；结构化响应经 1 次内部修复仍不合规 → `STRUCTURED_OUTPUT_INVALID`；`FINDING_IDENTITY_MISMATCH` 为证据身份校验不匹配；`BUDGET_EXHAUSTED` 为预算内未收敛（单调查未达结论，属预算耗尽型失败）。

失败集中在需要模型自由组织工具调用的变体（`single` / `full`）；`fixed` 变体因固定日程大部分完成。

## 5. 请求与 token 实测量

- **909 次真实 HTTP 请求**（全部为真实服务商调用，无 mock）。
- **9,105,902 token 实测**：prompt 8,381,973 + completion 723,929。
- **未知量如实披露**：slots 018 / 023 / 029 / 032 / 033 / 034 各有 1 次请求（合计 6/909）未返回用量；这些槽的 `measured_total_tokens` 为**实测下界**，不可估算成完整费用。

## 6. 冻结与完整性校验

- 全 40 槽：`protocol_valid: true`、`source_unchanged: true`（零 source drift）、`stop_completion: true`；失败槽 `runtime_failure: true` 为模型行为，协议本身无错（`protocol_errors` 均为空）。
- 终检 `run_wpd.py probe`：`validate()`（干净工作区 + 提交 `1c6b9e6` 一致 + session 哈希一致）通过后拒绝覆盖 readiness——**冻结输入全程未改动**。
- 恢复流程仅为继续未跑槽位（`resume` 跳过已完成与失败槽位）；失败槽按授权保留、未重试；未改模型 / 协议 / 预算 / 思考参数；全程零重复 supervisor 并发。
- 语义正确性仍需既有评估流程与独立标签（本报告不含 local_oracles 或人工核验）。

## 7. Slurm 作业履历

| 作业 | 分区 | 模式 | 时长 | 备注 |
|---|---|---|---|---|
| 139658 | h07q1 | 初始 run | 41m20s | slot-001–005 |
| 139677/139678 | h07q1 | resume | —（排队后取消） | h07q1 无回填窗口（整节点高优先级作业阻塞） |
| 139683 → 139725 | h07q2 | resume 链 | 12m56s–1h27m20s | 每失败暂停后自动恢复一次 |

全部作业 exit code 1 皆因 `stop_on_failure` 设计性暂停；末位 `batch_finished_with_errors` 为最终结果（16 槽技术失败已计入）。

## 8. 入库产物清单

- `results/hpc-wpd/atria-dawn-dev40-20261025T154709Z/session.json`、`readiness.json`、`summary.json`、`inputs/`（冻结协议 / 计划 / runtime）
- `batch/batch-manifest.json`（40 槽顺序）、`batch-state.json`（逐槽状态）、`batch-events.jsonl`、`supervisor-status.json`
- 每槽 `report.md`、`verification.json`、`result.json`、`scope.json`、`trace.json`、`measured-usage.json`
- **未入库**：每槽 `observability/` 原始事件流（约 48MB）与 Slurm 日志——仅保留在运行节点磁盘，需要时另行归档。

## 9. 复现与后续

- 复现入口：`bash hpc/sync.sh <新 checkout>` → 依 `docs/hpc-wpd-guide.zh-CN.md` 第 2–4 节执行（本批次已占用 `results/hpc-wpd`，新代码版本需另建 checkout）。
- 后续可选：补跑 16 个失败槽位需另行授权并制定逐槽尝试清单（本入口未开放自动重试）；正式分析需独立标签与既有评估流程。
