# Live-provider 容错修复验收

日期：2026-10-14。原问题记录为 `live-provider-issues.md`，验证和实施方案为 `live-provider-verification-plan.md`。

## 实现范围

- 工具查询未命中：仅明确的未知 service/change_id 返回 NOT_FOUND。必需源文件不可读返回 SOURCE_UNAVAILABLE，源解析错误返回 SOURCE_INVALID；ACL、参数校验、记录上限及工具预算保持原边界。
- 数据缺口：记录 TOOL_DATA_GAP，包含 call_id、工具、过滤条件和时间窗口。全空任务由运行时产生 neutral/unknown Finding，引用与假设为空，不增加分析调用；混合任务继续分析真实记录并附带缺口说明。
- 规划：提供案例可用服务列表，提示词版本更新为 `roles-v12-live-recovery-v1`，使旧缓存不复用变更前的提示词语义。
- 调度：legacy/benchmark/incident_response 共享结果收集策略，默认保留健康兄弟结果；关闭 continue_on_partial_failure 时等待兄弟完成再丢弃批次。运输/结构化输出故障按 max_attempts 有限重试；身份、ACL、协议、源文件和认证错误不进入无差别重试。
- 取消：legacy Provider 保留 CancelledError 及已观察 usage。兼容已包装成 PROVIDER_CANCELLED 的取消；任务记为 CANCELLED，调用携带 cancelled 和取消原因，取消次数与 Provider 故障次数分别计数。
- 预算：asyncio.wait_for 到达全局截止时间后转为明确的 Wall-clock budget exhausted，停止原因为 BUDGET_EXHAUSTED。保留被取消请求携带的 usage；已测量 token 不清零，缺失总量及成本仍为未知。
- 无进展：重复检查同一证据快照以 INCONCLUSIVE 有序退出。已耗尽重试的真实模型失败保持保守失败判断；没有增加任意“忽略未恢复失败”的评分捷径。
- 评分：新观察/批次事件加入冻结后禁止发布集合；维持评分版本 2 的停止、恢复及旧 STOP 无信用规则，未改变答案正确性标准。

责任文件：`tools/errors.py`、`registry.py`、`changes.py`；`agents/service.py`；`orchestration/graph.py`、`budget.py`；`llm/provider.py`；`evaluation/runner.py`、`termination.py`。旧故障注入测试与 `run_v12_eval.py` 改用真实分类代码 PROVIDER_TRANSPORT_ERROR，保留恢复和成本断言。

## 离线验收

最终全套命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
.\.venv\Scripts\python.exe -m ruff check src scripts tests
```

最终结果：**874 passed，3 skipped，250.05 秒**；三个跳过均为 Windows 宿主缺少符号链接权限。Ruff 通过。日志为 `results/acceptance/live-provider-fix-20261014/pytest-final-after-deadline.log` 和 `ruff-final.log`。

新增 `tests/integration/test_live_provider_recovery.py` 覆盖 24 个参数化场景：合法空查询、未知服务、混合工具证据保留、不同 profile/variant、缺口加延迟兄弟、缺口加原生/包装取消、停止与评分、有限重试、安全错误、源文件故障、认证错误、无进展、父级取消和关闭部分容错、原生/可靠运输取消、全局截止时间。

额外截止时间用量检查：第一个响应测得 7 token，第二个 HTTP 请求被总时限取消；两个 HTTP 请求均保留，measured_total_tokens=7、total_tokens 未知，终止原因为 BUDGET_EXHAUSTED。结果保存于 `deadline-partial-usage.json`。

故障注入与重算：

```powershell
.\.venv\Scripts\python.exe scripts/run_v12_eval.py --provider mock --incidents incident_001 incident_037 --out results/acceptance/live-provider-fix-20261014/recovered --skip-legacy --inject-transient-failure
.\.venv\Scripts\python.exe scripts/rescore_eval.py --input results/acceptance/live-provider-fix-20261014/recovered/raw-runs.jsonl --out results/acceptance/live-provider-fix-20261014/rescored
```

四次 Mock 运行每次保留一次失败及明确恢复记录，在线/离线根因、运行时、停止协议、终止原因、恢复次数和完整工作流字段一致；重算零错误、没有执行 Provider。比较结果为 `rescore-consistency.json`。

已执行 21 个 schema 的导出检查；本次没有结构化 schema 变更。导出发现 WorkflowOptions 中既有 CAES 字段尚未进入已跟踪 schema，该无关差异未纳入此次提交。

首轮调试日志及修正前真实复测完整保留：首轮测试有旧故障注入分类不匹配和脚本修改期间的摘要漂移；修正分类并固定源码后，全套通过。预算补修之前的全套为 872 passed、3 skipped；最终以 874/3 日志为准。

## 真实 Provider 回归

使用 COMP `DeepSeek-V4-Flash`，复用原 pilot 的公开数据集、temperature=0、json_schema、request_timeout=180、max_rounds=6、max_tool_calls=24、max_llm_calls=32、max_wall_seconds=600，cache=off。仅运行原故障案例 incident_2001 的 full variant；这是缺陷回归，不是新的两案例四 variant benchmark。源码摘要、基线提交与原协议保存在各新目录的 scope.json，未覆盖原 pilot。

```powershell
.\.venv\Scripts\python.exe scripts/retest_live_provider_fix.py --dataset results/incidentbench/v1/20261013-deepseek-development-pilot/dataset --protocol results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32/pilot-protocol.json --out results/acceptance/live-provider-fix-20261014/real-incident-2001-final
```

首次修正中间版本：22 个真实 HTTP 请求，3 次数据缺口，没有 fatal dispatch；到达 600 秒后发现 coordinate 的 TimeoutError 被误分类为 UNRECOVERABLE_ERROR。该记录保留于 `real-incident-2001/`，已据此补修截止时间路径；它不是最终通过证据。

最终真实复测：**18 个真实 HTTP 请求，4 次数据缺口，INCONCLUSIVE / ABSTAINED 正常结束**。protocol_valid=true、stop_completed=true、runtime_failure=false、fatal_dispatch=false；failed_model_calls、failed_tool_calls、provider_failures 和 cancelled_model_calls 均为 0。prompt_tokens=90,561、completion_tokens=8,113、total_tokens=98,674，用量完整，成本未推算。报告 root_cause=null，不能将正常弃答等同于正确诊断或正确弃答。

最终记录保存至 `real-incident-2001-final/verification.json`；真实模型没有再次选择 inventory，因此原未知服务加兄弟取消的组合由确定性离线回归覆盖。没有评估真实 RCA 正确率，也没有将 development 数据升级为 Frozen Test。完整两案例四 variant 的质量 benchmark 未重跑，本次完成的是原案例的运行时回归。
