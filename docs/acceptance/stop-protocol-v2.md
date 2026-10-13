# 停止协议与分层评测验收

## 实现结果

新运行使用协议版本 `2`：`WORKFLOW_STOP_REQUESTED` → 必要角色的实际 `STOP_ACK` → 一次 `NORMAL_TERMINATION` 或 `RUNTIME_FAILURE` → `REPORT`。没有活动工作时不制造 ACK。state/report 保存一致的 `TerminationResult`，明确 reason、outcome、failure_stage、stop_completed 和 runtime_failure。

`NORMAL_TERMINATION` 表示有序结束，包括 `PLAN_FAILED` 这样的业务失败。禁用修复时的已确认诊断使用 `DIAGNOSIS_READY`。预算耗尽、不可恢复执行异常和停止超时使用失败结果；停止超时不能伪装成完成。修复阶段的运输/超时故障与方案内容失败分别归类，但均保留已经确认的诊断。

评分版本 `2` 分开记录诊断、方案、停止协议和完整工作流。`MODEL_FAILURE` 保存 stage/call_id/task_id/attempt_id；恢复记录必须明确关联失败调用及完成的 task attempt。已通过门禁的诊断可记录被充分同伴证据替代的失败专家调用。失败调用与成本统计不会被删除。

正常证据不足仅在 oracle 确实不可识别时获得弃答信用。`NO_ALERT` 不进入 RCA/弃答分母；监控准确率依赖独立 `monitoring_expected_alert`，缺失时为未知。缺少 oracle 时仍保留执行、协议与方案事实，不生成答案正确率。

## 修改位置与兼容

- 契约：`schemas/workflow.py`、`schemas/contracts.py`、CLI 导出与 `docs/contracts/`；新增 TerminationResult，保留历史 state/report 可选字段。
- 运行时：`orchestration/runtime.py`、`graph.py`、`budget.py`、`report.py`；实际停止确认、冻结后禁止结果发布、诊断门禁记录、调用失败关联及分层失败结果。
- 评分：`evaluation/termination.py` 集中分类，`metrics.py` 分层计分和聚合；普通评测 runner、V1.2 评测、分析与离线重算调用相同入口，V1.2 不再删除 STOP 事件后评分。
- 消费者：Web 时间线与报告组件、Streamlit 状态区、英文/中文 README、评测说明和接口冻结说明；保留历史 STOP 展示，分别展示诊断、方案与工作流结果。
- 测试：新增终止分类、端到端评分与重算/入口一致性测试，迁移停止事件断言，增加 UI 终止结果断言。

历史非结构化 STOP、无法解释的 MODEL_FAILURE 保持保守失败判定。历史结构化 STOP 仅接受明确原因且报告一致的运行。新协议核对事件顺序、身份、ACK、任务快照与状态、最终结果、报告及诊断门禁记录；未知字段、缺失终止字段、冲突和冻结后的发布不能获得成功信用。原始 trace 不修改，聚合拒绝混用评分版本。

共享工作区内正在增加 Provider 恢复和请求许可能力；本次保留这些修改，并使用任务上下文关联调用与许可。故障注入标志跨 Provider 副本共享，确保每次验收运行只注入一次 transient failure。

## 可复现验证

从项目根目录在 PowerShell 执行，产物目录必须为新目录：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
.\.venv\Scripts\python.exe -m ruff check src scripts tests
.\.venv\Scripts\python.exe -m incident_lens.cli export-schemas
.\.venv\Scripts\python.exe scripts/run_v12_eval.py --provider mock --incidents incident_001 incident_037 incident_040 --out results/acceptance/stop-protocol-check/normal --skip-legacy
.\.venv\Scripts\python.exe scripts/run_v12_eval.py --provider mock --incidents incident_001 incident_037 --out results/acceptance/stop-protocol-check/recovered --skip-legacy --inject-transient-failure
.\.venv\Scripts\python.exe scripts/verify_stop_protocol.py --out results/acceptance/stop-protocol-check/fault-matrix
.\.venv\Scripts\python.exe scripts/rescore_eval.py --input results/acceptance/stop-protocol-check/recovered/raw-runs.jsonl --out results/acceptance/stop-protocol-check/rescored
.\.venv\Scripts\python.exe scripts/analyze_eval.py --input results/acceptance/stop-protocol-check/recovered/raw-runs.jsonl --out results/acceptance/stop-protocol-check/analysis
```

保留产物位于 `results/acceptance/stop-protocol-v2/`。`final/normal` 为 6 次配对 Mock 运行；`final/recovered` 为 4 次各注入一次模型调用失败的配对运行；`final/fault-matrix` 为 5 次正常/方案失败/停止失败/预算耗尽/无告警运行。方案与停止失败都保留正确根因分数并使完整工作流失败。恢复场景保留 1 次失败调用统计，同时获得诊断和工作流信用。

| 场景 | 根因信用 | 方案成功 | 停止完成 | 完整工作流成功 |
|---|---|---|---|---|
| 根因与方案正确，正常停止 | True | True | True | True |
| 首次模型调用失败，重试恢复 | True | True | True | True |
| 方案生成失败 | True | False | True | False |
| 停止确认失败 | True | True | False | False |
| 诊断前预算耗尽 | False | 不适用 | True | False |
| 不可识别案例正常弃答 | 不适用 | 不适用 | True | True |
| NO_ALERT，有独立监控真值 | 不适用 | 不适用 | True | 按监控真值计分 |

`historical-score-comparison.json` 对同一个旧 database-resolved trace 使用本地历史提交 `00ae458` 的真实评分函数与新评分函数比较：runtime_failure 从 True 变为 False，root_cause_correct 从 False 变为 True。文件记录输入 SHA-256 和历史源提交；没有执行模型。

`final/rescored` 与 `historical-rescored` 保留新评分、历史指标和输入摘要；`final/analysis` 保留分层汇总及失败导出。新评分不修改原始事件或原评分文件。离线重算有 oracle 读取错误时退出码为 2，并保留错误行及未知正确率。

最终全套日志为 `pytest-final-after-review.log`、`ruff-final-after-review.log`；早期检查日志也保留。`verification.json` 汇总最终结果、当前源码摘要和保存产物的重算一致性。

最终检查结果：**516 passed，2 skipped**，耗时 74.44 秒；Ruff 与 `git diff --check` 均通过。全套结果包含共享工作区中的 Provider 恢复扩展测试，并非全部由本次修改新增。

## 验证边界

全部新增运行证据为 Mock、故障注入或已保存 trace 的离线重算。没有真实付费模型调用、实际修复执行、服务恢复确认、提交或推送。UI 验证使用 Streamlit AppTest 与 JavaScript 组件渲染测试，不宣称完成浏览器视觉验收。两个符号链接测试依赖宿主允许创建符号链接；跳过原因见完整日志。
