# WP-D 后续修复：调用可靠性、调查收敛、Verifier 观测与 Token 用量

日期：2026-10-19。修复实施于独立工作树；合入后项目目录为 `C:\Develop\python_projects\COMP5584_Agents\IncidentLens`。

## 范围与状态

用户授权修复 P0、两个 P1、P2 中的 Verifier 收益衡量，以及 WP-D Token 统计。
初始修复阶段仅做静态检查。用户随后明确授权离线测试、合并和工作树清理；最终完整套件 **1033 passed, 3 skipped**。
三项跳过均为 Windows 符号链接权限限制。未进行真实模型调用、连通性请求或真实补跑。
最终验收记录见 `wpd-repair-offline-20261019.md` 及 `results/acceptance/wp-d-repair-offline-20261019/validation.json`。
保留工作区已有改动，不修改旧矩阵、final-selection、原始日志或已冻结的历史结果。

## 已定位的问题与修改

### P0：错误分类与有界恢复

- legacy Provider 的超时、网络错误和所有 HTTP 错误都携带安全的 FailureInfo；仅记录类型、状态、白名单错误代码、Retry-After、请求耗时等，不保留响应正文或凭据。
- ProviderError、MeasuredProvider、CallBudget、MODEL_FAILURE、RUNTIME_ERROR 和 verification 之间保留分类，避免最终只剩 PROVIDER_HTTP_ERROR。
- coordinate 阶段可对明确可恢复 HTTP 错误重试；diagnosis/verify 同样使用有界退避和 Retry-After，等待计入原 wall budget。仍受 max_attempts、请求许可、STOP 和总预算约束。
- 显式 insufficient_quota 判为 QUOTA_EXHAUSTED，不把它作为短暂限流重试；认证和无效请求不重试。
- provider_recovery=true 的内部恢复结束后，业务层不再重复一轮同类恢复。默认 provider_recovery 开关及原预算未改。
- 未诊断真实 HTTP 故障根因，需先取得新分类日志再判断服务端、网络或配置问题。

### P1：错误弃答与调查效率

- slot 5 旧轨迹存在相同故障机制的长句变体，导致不同 hypothesis ID 作为竞争者互相阻断。新分析输出将 failure_mode 约束为现有 taxonomy 的精确枚举，解释保留在 finding/prediction 中。历史 trace 不重写。
- slot 9 旧轨迹中 FINALIZE_REJECTED 的错误写入 open_questions，形成“共享问题未解决”的自我阻断。门槛错误现在仅保留在事件和 last_finalization_feedback，不再变成业务问题。
- 协调器收到每个候选的具体门槛错误、竞争假设 ID、原因区分证据 ID，明确要求对所有竞争者做有据的更新。没有自动删除竞争者、没有把无数据当健康、没有放宽最终证据门槛。
- 循环和失败最终化指纹包含证据内容、假设评估及真实问题，避免仅因证据 ID 没变就忽略有效评估更新。
- 提供剩余请求/轮次/工具和最低调查成本；动态调度为最终决策及复核预留调用，必要时推迟第二个任务，并显式记录执行/推迟列表。预算不足终止仍是运行失败，不伪装成正确弃答。
- 提示词明确：已成功完成的宽范围查询不能仅因未试过更窄的窗口或关键词就再次查询。此策略不自动推断部分页、失败查询或无结构过滤器等价。

### P2：Verifier 的收益可衡量

- 复核目标约束为已有假设；存在 FINALIZE 选择时约束为该目标。
- 无候选时跳过复核；证据、假设与问题均未变且目标一致时复用已有复核。任何相关快照变化都要求重新复核。
- REVIEW_EFFECT 记录复核前后门槛、阻断检查、矛盾、重复检查数量及快照，REVIEW_FOLLOWUP 保守匹配后续实际工具调用并记录新公开证据 ID。
- verification 的 verifier 字段区分独立复核与 single 自我复核，汇总调用数、实测 Token、接受/阻断/复用次数及后续取证。
- 门槛解除与新增证据不等于纠正了错误诊断。benefit_assessment 保持 pending_manual_or_paired_evaluation，需人工/配对实验判断正确性收益。
- 旧 trace 未记录的新事件无法追溯补造；历史 single 的成功自我复核用量若无 stage 标记也无法精确拆分。

### Token：完整总量与已知用量分开

- 新增 llm/usage.py：每个已派发物理请求有 request_usage；失败、取消、输出修复的请求均保留。
- 记录 measured_prompt_tokens / measured_completion_tokens / measured_total_tokens 下界，以及已知/未知请求数、角色用量。不完整时 total_tokens 仍为 null。
- 提供方只给 prompt_tokens 和 completion_tokens 时可精确相加，并标注 provider_prompt_plus_completion；不使用字符数或 tokenizer 猜测。
- reliable 和 legacy 使用一致计数；失败响应若包含合法 usage 也保留。不重复累计 prompt cache 或 reasoning 等 total 内部子项。
- 新 WP-D 补跑额外保存 measured-usage.json；verification 及常规评测聚合显示完整性和下界。
- analysis/wp_d/summarize.py 升为 schema_version=2，旧 trace 只读恢复已有数字，按 call_id 去重，记录恢复来源；旧 mixed-attempt 覆盖数量是保守口径。

## 旧矩阵恢复结果

在原仓库矩阵上只读生成 `analysis/wp_d/reports/token-recovery-20261019/`，选定口径仍是 12 项，slot 5 仍用第三次结果。
合计已知用量至少 **2,067,532 Token**；仅 slot 7 完整，为 38,632 Token。
slot 5 已知下界为 660,845 Token，slot 4 为 364,998 Token；这不是完整成本，不能与完整用量混称。
slot 12 下界为 0，表示没有收到任何用量测量，不表示该请求在提供方未消耗 Token。
该报告不改变案例是否通过，也不弥补缺失的提供方计费记录。

## 主要文件

- src/incident_lens/llm/{provider,errors,usage}.py
- src/incident_lens/orchestration/{graph,budget}.py
- src/incident_lens/agents/service.py（prompt version 更新为 roles-v12-evidence-reconciliation-v6）
- src/incident_lens/evaluation/{runner,metrics,verifier}.py
- scripts/retest_live_provider_fix.py
- analysis/wp_d/{summarize.py,README.md}
- tests/integration/test_wpd_repair_accounting.py（已编写、未运行）

## 验证边界

这次包含真实调查策略与提示词变化，不能沿用上一轮“仅诊断日志修复”的比较说明。
后续运行需重新冻结并记录源码、提示词、配置和数据指纹。旧矩阵保留为历史探索结果；
新结果单独报告。不能把跨版本选择性补跑声称为已验证的严格公平比较。
验证交接见 `wpd-repair-validation-prompt-20261019.md`。

## 离线验收中的补充修复

- 嵌套 Token / Verifier 指标写 CSV 时统一使用排序的 JSON，保证保存、重载、resume 的字节一致性。
- HTTP 故障注入明确区分有合法 usage 与未返回 usage 两类；分别验证完整总量和未知下界，不删除未知值断言。
- 复核边界断言按 review_event_id 追踪实际 REVIEW，允许中间出现纯观测的 REVIEW_EFFECT，仍禁止额外模型调用或决策。
- runner 的离线测试替身补齐新的用量契约，并验证 measured-usage.json 真实写出。
