# WPD bridge max4 批次归档说明

日期：2026-10-22（Asia/Shanghai）。原批次：`results/v16/wp-d/next-bridge-max4-20261022-092104`。

归档备注：**由于其他 agent 误操作而导致代码漂移，冻结失效。实验失败，但各槽位的运行记录仍有参考价值。** “其他 agent 误操作”为项目负责人确认的事故归因；产物自身能够证明文件漂移，不能单独识别操作者。

原始实验文件不修改、不删除，不把 failed 改写为 completed。原始文件的逐字节副本及 SHA256 清单保存在 `results/acceptance/wpd-bridge-max4-20261022-archive/`。

## 已核查事实

- 计划 40 槽位，并发 4；启动 5，completed 1，failed 4，未启动 35，interrupted 0。
- 09:21:32 开始，10:53:42 以 `batch_paused_after_failure` 结束；失败后停止派发，让在途槽位结束。
- 5 个调查退出码均为 0、protocol_valid=true、stop_completion=true、runtime_failure=false。
- 槽位 001、002、004、005 的 source_unchanged=false；漂移文件为 `configs/wp_d/api-protocol.json`、`configs/wp_d/bridge-protocol.json`、`scripts/run_status.py`。槽位 003 没有检测到漂移。
- 检查时 35 项登记产物 SHA256 与 batch-state 一致；84 次请求均有响应及接受记录，身份绑定未发现不一致。这不证明外部上下文隔离。

| 槽位 | 案例 | 架构 | 耗时（分钟） | 请求 | 调查结论 | 冻结校验 |
|---|---|---|---:|---:|---|---|
| 001 | incident_3010 | dynamic_no_verifier | 54.99 | 18 | INCONCLUSIVE / ABSTAINED | 失败 |
| 002 | incident_3004 | dynamic_no_verifier | 60.00 | 19 | INCONCLUSIVE / ABSTAINED | 失败 |
| 003 | incident_3008 | fixed | 11.44 | 7 | INCONCLUSIVE / ABSTAINED | 通过 |
| 004 | incident_3010 | single | 80.02 | 17 | RESOLVED / postgres_slow_query | 失败 |
| 005 | incident_3008 | full | 80.44 | 23 | INCONCLUSIVE / ABSTAINED | 失败 |

## 研究价值和限制

可以分析证据获取、竞争假设阻塞、弃答、Verifier 检查开销、桥接请求延迟。3010 的 single 与 dynamic_no_verifier 产生不同结论；3008 缺失证据场景中，full 比 fixed 请求更多、耗时更长，仍然弃答。这些是探索性观察，不证明架构优劣；SUCCESS 也不等于独立真值评分正确。

5 次调查平均约 57.38 分钟；按持续 4 并发线性外推，40 槽位约 9.56 小时，排期参考 10–12 小时。样本少且覆盖不均，这不是置信区间，也不是新 8 并发配置的实测估计。

本批次本来就是 formal=false、development_visible；模型身份、外部隔离和 Token 成本未验证。不能作为完整 40 槽位正式对比结果，也不应当把冻结失效计为模型调用失败或根因识别错误。

## 后续配置

恢复状态脚本的冻结前功能，桥接/API 并发均调整为 8；API 模型为 deepseek-v4.1-flash-1017。新配置需要新批次重新冻结，不能用旧批次清单直接续跑。本次归档、提交和清理不启动任何正式测试。
