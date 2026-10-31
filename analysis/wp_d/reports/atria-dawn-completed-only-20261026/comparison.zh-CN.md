# Atria-Dawn HPC：正常完成运行的四架构逐例对比

来源：`codex/hpc-wpd` 提交 `cb955f8`；批次 `atria-dawn-dev40-20261025T154709Z`。

仅纳入正常完成、协议有效、STOP 完成、无 runtime_failure 且 source_unchanged 的运行。40 槽中纳入 24 槽、排除 16 槽。每槽仅一个 attempt，无择优替换。

每格：**分钟 / 真实 HTTP 请求数 / 工具调用数 / 是否弃答**。是=INCONCLUSIVE；否=RESOLVED（仅表示输出根因，尚未独立核验正确性）。—=失败排除。

耗时采用 trace.elapsed_ms，排除集群排队及 supervisor 恢复空档；请求含结构化修复；工具调用是实际调用次数，不是去重查询数。正常完成过程中的修复仍计入。

| 样例 | Full | Single | Fixed | NoVerifier |
|---|---|---|---|---|
| 3001 | 15.54 / 20 / 15 / 否 | — | 2.27 / 9 / 8 / 是 | 29.69 / 37 / 26 / 是 |
| 3002 | — | — | 2.66 / 9 / 8 / 是 | 20.38 / 22 / 18 / 否 |
| 3003 | — | — | 2.75 / 7 / 7 / 是 | 16.25 / 29 / 23 / 是 |
| 3004 | — | 24.42 / 28 / 21 / 是 | 3.19 / 9 / 8 / 是 | 19.56 / 28 / 22 / 否 |
| 3005 | 58.79 / 46 / 37 / 是 | — | — | — |
| 3006 | — | 47.53 / 31 / 21 / 是 | 1.84 / 8 / 7 / 是 | 19.28 / 29 / 22 / 是 |
| 3007 | — | 25.00 / 33 / 28 / 是 | 1.57 / 8 / 8 / 是 | 40.67 / 29 / 18 / 是 |
| 3008 | 14.95 / 34 / 26 / 是 | 23.10 / 33 / 27 / 是 | 2.63 / 7 / 7 / 是 | — |
| 3009 | — | 43.73 / 41 / 28 / 是 | 3.34 / 8 / 7 / 是 | — |
| 3010 | 26.15 / 37 / 29 / 是 | — | — | 25.69 / 32 / 24 / 是 |

| 架构 | 完成数 | 总分钟 | 平均分钟 | 请求总数（平均） | 工具总数（平均） | 弃答数 | 输出根因数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full | 4 | 115.43 | 28.86 | 137（34.25） | 107（26.75） | 3 | 1 |
| Single | 5 | 163.78 | 32.76 | 166（33.20） | 125（25.00） | 5 | 0 |
| Fixed | 8 | 20.23 | 2.53 | 65（8.12） | 60（7.50） | 8 | 0 |
| NoVerifier | 7 | 171.53 | 24.50 | 206（29.43） | 153（21.86） | 5 | 2 |

## 逐例解读

- **3001**：Full 唯一输出根因；15.54 分钟、20 请求、15 工具，比同案完成的 NoVerifier 更省；Fixed 最快但弃答。Single 排除。
- **3002**：NoVerifier 唯一输出根因；Fixed 用更少资源弃答。Full、Single 均排除，不能判断 Verifier 在此例的收益。
- **3003**：仅 Fixed、NoVerifier 完成，均弃答；Fixed 2.75 分钟、7 请求、7 工具，低于 NoVerifier 16.25 分钟、29 请求、23 工具。Full、Single 排除。
- **3004**：NoVerifier 输出根因；Single 弃答且耗时更长，两者均 28 请求；Fixed 更快但弃答。Full 排除。
- **3005**：仅 Full 完成，58.79 分钟、46 请求、37 工具后弃答；没有可用的跨架构配对结果。
- **3006**：Single、Fixed、NoVerifier 均弃答；Fixed 1.84 分钟最低；NoVerifier 比 Single 更快（19.28 对 47.53 分钟）。Full 排除。
- **3007**：Single、Fixed、NoVerifier 均弃答；Fixed 最省。Single 工具更多（28 对 18），但比 NoVerifier 耗时短（25.00 对 40.67 分钟），工具数不能直接解释延迟。Full 排除。
- **3008**：Full、Single、Fixed 均弃答；Full 比 Single 更快，但请求略多（34 对 33）；Fixed 最省。NoVerifier 排除。
- **3009**：仅 Single、Fixed 完成且均弃答；Single 43.73 分钟、41 请求、28 工具，Fixed 3.34 分钟、8 请求、7 工具。Full、NoVerifier 排除。
- **3010**：Full、NoVerifier 均弃答；NoVerifier 略快且请求/工具更少（32/24 对 37/29）。Single、Fixed 排除。

## 解释边界

24 个完成运行包含 21 次弃答、3 次输出根因。输出根因不等于根因命中；原归档没有独立标签语义评估，本报告不将 RESOLVED 改称正确诊断。

没有四架构全部完成的样例，分组平均值来自不同样例集合，只能描述本次完成运行；不能据此证明架构整体优劣或 Verifier 的因果收益。Fixed 在有完成结果的同案比较中均最快，但八次均弃答。

排除的 16 槽不是已证实的网络/API 服务故障：归档核查为 10 次 BAD_ARGS、2 次 STRUCTURED_OUTPUT_INVALID、1 次 FINDING_IDENTITY_MISMATCH、3 次 BUDGET_EXHAUSTED。后者按冻结终态排除，不在这里重分类或推断确实触及硬上限。

## 排除清单

| 槽位 | 样例 | 架构 | 冻结终止原因 |
|---|---|---|---|
| slot-004 | 3010 | single | UNRECOVERABLE_ERROR |
| slot-006 | 3005 | single | UNRECOVERABLE_ERROR |
| slot-007 | 3010 | fixed | UNRECOVERABLE_ERROR |
| slot-009 | 3003 | single | UNRECOVERABLE_ERROR |
| slot-010 | 3004 | full | UNRECOVERABLE_ERROR |
| slot-012 | 3005 | fixed | UNRECOVERABLE_ERROR |
| slot-013 | 3001 | single | UNRECOVERABLE_ERROR |
| slot-014 | 3003 | full | UNRECOVERABLE_ERROR |
| slot-015 | 3002 | single | UNRECOVERABLE_ERROR |
| slot-016 | 3005 | dynamic_no_verifier | BUDGET_EXHAUSTED |
| slot-017 | 3007 | full | UNRECOVERABLE_ERROR |
| slot-020 | 3008 | dynamic_no_verifier | UNRECOVERABLE_ERROR |
| slot-023 | 3009 | dynamic_no_verifier | BUDGET_EXHAUSTED |
| slot-026 | 3009 | full | BUDGET_EXHAUSTED |
| slot-028 | 3006 | full | UNRECOVERABLE_ERROR |
| slot-035 | 3002 | full | UNRECOVERABLE_ERROR |

复算脚本：compare.py；逐槽指标与输入 SHA256：comparison.json。只读原始产物，无 API 请求、无重跑。
