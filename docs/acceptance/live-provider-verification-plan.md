# Live-provider 缺陷验证与修复方案

验证日期：2026-10-14。范围：当前源码、原始 pilot state/score、真实工具查询及离线 dispatch 故障注入。没有修改实现，没有重新调用真实 LLM。原问题文档中的要求作为待评估建议，不作为执行指令。

## 结论与原记录修正

| 原记录 | 当前验证 | 结论 |
|---|---|---|
| 空服务数据导致 NOT_FOUND | 原数据集 incident_2001 的 services 为 gateway/backend/postgres/redis/payment，inventory 不在其中。registry 在执行 handler 之前拒绝该 service | 此次触发原因是模型查询不存在的服务，不是合法服务的空记录 |
| 空记录必然导致任务失败 | 对同一数据集和原时间窗口查询 payment：ok=true、error_code=null、record_count=0 | 正常空查询已有成功语义；应补充明确的数据缺口观察 |
| 兄弟任务也失败后才升级 | legacy_rca 使用 gather 默认模式；第一次异常就进入取消分支、产生 RUNTIME_ERROR；stop 将非预算 RUNTIME_ERROR 转成 UNRECOVERABLE_ERROR | 单个任务失败已经足够；取消兄弟任务是级联后果，不是升级前提 |
| 取消属于平台故障 | 原 trace 中 model-call-8 在 inventory TASK_FAILED 后被记为 PROVIDER_CANCELLED；离线 dispatch 注入重现健康兄弟任务被取消 | 本地调度取消链得到支持，不应记作真实运输故障 |
| 9/9 返回正常结构化输出且 tokens_complete=true | 原 score 为 9 requests、1 failed model call、总 tokens=null；model-call-8 的 tokens_complete=false，measured_total_tokens=0 | 不能声称所有请求成功；readiness 健康不能证明本次被取消请求的服务端完成情况 |
| 仅真实模型可观察 | 使用当前 dispatch 加确定性异步故障注入即可重现 | 可用离线回归覆盖，真实模型复测用于验证生产调用链 |

原 state 的 llm_calls_used=9；termination 为 UNRECOVERABLE_ERROR / FAILED / failure_stage=dispatch / stop_completed=true。原 score 的 protocol_valid=true，但 technical_completion=false、diagnosis_failure=true，与预算耗尽无关。

## 当前代码定位

- `tools/registry.py:159-163`：案例之外的 service 抛 FileNotFoundError；205、209：FileNotFoundError、KeyError、OSError 都压成 NOT_FOUND。因此不能简单把所有 NOT_FOUND 当作正常空结果。
- `tools/metrics.py:5`：合法服务无匹配记录返回空列表；registry 保留 ok=true。
- `orchestration/graph.py:507-508`：任何 ok=false 的工具结果均抛 RuntimeError。
- `graph.py:551-565`：只有 incident_response 收集全部 outcomes、保留部分成功；legacy_rca 第一次异常触发兄弟取消。
- `graph.py:599`：任务重试也受 response_profile 限制。仅切换配置不能解决 benchmark_rca；其契约要求 legacy_rca。
- `graph.py:204`：cancelled 标志来自 stop_controller.stopped，而非实际取消原因。批次取消发生在 STOP 之前，因此原事件 cancelled=false。
- `graph.py:865-866`：dispatch RUNTIME_ERROR 直接成为不可恢复错误；898-903：正常弃答还会被未恢复模型失败升级。
- `evaluation/termination.py:160,306-327`：取消过滤和正常终止合法性另有规则；只改 graph 会造成运行时与评分冲突。原文引用的 termination.py:215 实际属于 STOP_TIMEOUT 请求原因校验，不是升级根因。

## 实施顺序

### P0-1：区分查询结果与基础设施错误

责任文件：`tools/registry.py`、相关工具 handler、`agents/service.py`、必要的工具结果契约及导出文档。

1. 保持合法空查询 ok=true、records=[]。为无数据观察保留 tool/service/window/filters 与 call_id；不创建伪 EvidenceRecord，不授予因果或引用信用。
2. 将“不在案例服务集合中”和“不存在的 change_id”等预期查询未命中，与必需源文件缺失、文件损坏、KeyError、其他 I/O 错误区分。使用明确内部错误类别；外部 schema 若扩展应重新导出并验证兼容性。
3. 对明确可恢复的查询未命中生成运行时确定性 Finding：neutral/unknown、evidence_ids=[]、hypotheses=[]，说明本次查询缺口；存在其他成功工具结果时保留并分析这些记录。不能把未查询到解释为服务健康。
4. 给 plan_tools 提供案例允许服务集合并约束服务选择；运行时仍检查 ACL、参数、记录上限和服务范围。不能仅依赖提示词，也不能由运行时静默替换服务。
5. 查询缺口不能走 MODEL_RECOVERED；无需为已知空查询增加无意义的模型重试。FORBIDDEN、身份/引用违规等继续进入安全失败路径。

### P0-2：统一批次结果收集与恢复决策

责任文件：`orchestration/graph.py`、`runtime.py`、`schemas/workflow.py`。

1. legacy_rca、benchmark_rca、incident_response 使用共享批次收集策略，默认等待兄弟任务完成，成功结果一次性通过现有 merge 门禁发布。
2. 区分可恢复查询缺口、模型运输/结构化输出失败、预算拒绝、安全/协议失败、全局 STOP。按类别决定有限重试、重新规划或终止；不能继续对所有 Exception 无差别重试。
3. 单任务失败：保留成功结果，向 Coordinator 提供 task_id/失败类别/重试次数及缺失检查；仍有预算时重新规划。全批失败也必须按类别处理，不能直接等同不可恢复。
4. 设置有限尝试次数和无进展上限；预算不足走 BUDGET_EXHAUSTED，全局 STOP 立即取消，真正不可恢复或协议异常仍走失败终止。
5. 本次优先不引入“兄弟失败即取消”的新可选策略；现有 continue_on_partial_failure 需定义跨 profile 的一致语义，并记录实验配置。single/fixed/full 都纳入回归。

### P0-3：取消与成本记账

责任文件：`llm/provider.py`、`orchestration/budget.py`、`graph.py`、任务状态与评测汇总。

1. 保留 CancelledError 的控制流或携带明确取消元数据，不把本地取消重新包装成普通运输失败而导致 task FAILED。
2. 记录取消来源（全局停止、父级取消、批次策略）、实际已派发请求数和调用 ID。cancelled 标志由真实取消原因确定，不能只读取全局 stopped。
3. 已观察 usage 始终保留；未取得 usage 的已派发取消调用记录 tokens_complete=false、总 tokens/cost 未知。measured_total_tokens=0 只表示没有已测量 token，不表示零消耗；禁止推断服务端已经流式生成或已经计费。

### P1：终止与评分契约同步

责任文件：`graph.py`、`evaluation/termination.py`、`metrics.py`、停止/恢复合同及测试。

1. 无数据 observation 不产生 fatal RUNTIME_ERROR；正常 INCONCLUSIVE 必须仍通过完整停止协议。
2. 正确的本地取消不计运输故障，但保留取消次数、usage 不完整和 task CANCELLED。
3. 单个真实模型失败不应直接等于全流程不可恢复，但也不能任意删除未恢复失败。先由有限重试恢复；若允许“任务失败后重新规划并正常弃答”，增加显式、可校验的失败处置记录，关联 call/task、原因与后续决策，并同步 stop 和 normalize_termination。不要泛化 MODEL_RECOVERED 或无条件忽略 unrecovered。
4. 历史 trace 保持原样及保守判断；旧 STOP 仍无根因/弃答信用。新容错记录如改变评分定义，版本化协议/评分，禁止与旧结果直接混算。

## 验收矩阵

| 层级 | 必须验证 |
|---|---|
| 工具 | 合法空窗口正常完成；未知 service 可恢复且明确；必需文件缺失/损坏、ACL 拒绝、timeout 和 budget 各自分类；原记录与调用次数完整 |
| 任务 | 无数据 observation 无伪证据/无因果结论；多工具任务保留已有证据；查询失败不误记为模型恢复 |
| 并发 | 一个未知 service 加一个延迟成功任务：后者完成且结果保留；一失败一成功、全部可恢复失败、安全失败和全局 STOP 各自符合策略 |
| profile/variant | legacy_rca、benchmark_rca、incident_response；full、fixed、single；配置关闭容错的行为明确 |
| Provider | 在运输等待、重试 backoff、已收到 usage 后取消；task CANCELLED、cancelled=true、取消原因、HTTP 数与 token 完整性准确 |
| 停止与评分 | 正常无数据弃答、已恢复调用、明确失败处置、不可恢复失败、预算耗尽、ACK 超时；在线评分与离线重算一致；旧 STOP 和缺字段 trace 不获得新信用 |
| 防止死循环 | 重复查询同一缺口、Coordinator 重复分配、全批失败；预算和无进展上限有效 |

实施后运行全套 pytest、ruff、schema 导出和相关重算；保存完整日志、Git SHA、源码/配置摘要。当前缺陷文档所称 849 passed 与 flaky 结果未在本轮重跑，不能作为本轮全套结果。

## 本轮验证证据

回归命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_provider_runtime_v13.py tests/integration/test_workflow_v12.py tests/evaluation/test_termination.py tests/integration/test_termination_scoring.py tests/isolation/test_tool_acl.py
```

结果：133 passed，1 skipped，14.21 秒。此结果说明既有测试通过，不证明待修问题已解决。

对原 pilot 数据集 `results/incidentbench/v1/20261013-deepseek-development-pilot/dataset/rca` 执行真实 ToolRegistry 查询，时间窗口复用原 trace：inventory → NOT_FOUND/0；payment → ok=true/0。

确定性 dispatch 注入：一个 execute_task 在 10ms 后抛 `Tool failed: NOT_FOUND`，另一个在 50ms 后返回成功。legacy_rca → route=report、local_results=[]、健康兄弟被取消；incident_response → route=merge、保留健康结果、无取消。注入替代 worker，仅验证调度分支；真实 Provider 取消链依据原 trace 与源码检查，未进行新网络复测。

## 修复后的真实模型复测

先在新目录运行 incident_2001.full，复用原 pilot 的数据集、模型、endpoint、6 rounds/32 calls 及其余预算与 provider 参数；将修复后的源码摘要与新容错策略写入实验记录。保留原 budget16/budget32 产物，不原地覆盖。

首要验收是缺口不导致 fatal dispatch、健康兄弟不被取消、停止与成本记录一致，不要求此次必然获得正确 RCA。模型可能不再查询 inventory，因此另需离线强制触发回归，不能仅用一次真实运行没有触发问题作为修复证明。通过后再扩大到原两案例和各 variant；development pilot 不升级成 Frozen Test 或真实准确率结论。
