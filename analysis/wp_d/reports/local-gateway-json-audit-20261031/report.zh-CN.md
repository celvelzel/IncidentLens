# 本地网关测试：database 输出非法 JSON 原因审计

日期：2026-10-31（Asia/Shanghai）。本审计没有修改生产代码。新增离线审计脚本、诊断复现脚本及证据文件；真实诊断共 3 次 HTTP 请求：原提示 2 次（首次及一次修复），阶段限定提示 1 次。

## 结论

本批次的六个终止失败全部是 database 在 **AnalysisOutput 分析阶段** 连续两次返回 `INVALID_JSON`。它们没有进入字段 schema 或业务约束校验，并非 database 的 Pydantic schema 特别严格导致字段被拒绝。

对 slot-003 的任务和已取得的公开记录重建请求后，首次和修复请求都复现：HTTP 200、`finish_reason=stop`，但 `choices[0].message.content` 是 DeepSeek DSML 工具调用标记，而非分析 JSON。请求没有注册 API 原生 `tools`，响应也没有结构化 `tool_calls` 字段。内容示例：

```text
<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="get_db_lock_waits">
...
</｜｜DSML｜｜ calls>
```

因此，已证实的直接故障是 **工具调用协议文本进入了预期承载最终 JSON 的 content 字段**。代码严格解析此字段，报错符合当前契约。

最有证据支持的触发机制是：分析阶段沿用带有“使用数据库工具”要求的角色提示，同时输入仍携带可用工具和剩余调用额度。模型把“分析已有工具结果”误当作“继续调用工具”。定向添加阶段限定后，同一任务在同一实际提供商路径下 1 次请求即通过现有动态 schema、身份和引用检查，支持这一解释。这个单样本结果不能保证修复整个批次。

## 统计范围与失败分布

原批次：`results/v16/wp-d/local-gateway-dev5-20261031/`，5 个开发案例、4 种架构。取首次跑齐 20 个槽位时（2026-10-31 15:14:02.838 +08:00）的每槽位最新已结束 attempt。原批次经历过续跑，不能简单取各槽位 attempt-001。调查期间另有聊天启动后续补跑，以下统计不混入这些新 attempt。

20 个槽位：14 completed，6 failed。终止失败如下：

| 槽位 | 案例 | 架构 | 终止调用 |
|---|---|---|---|
| slot-003 | incident_3007 | full | database / AnalysisOutput，首次和修复均 INVALID_JSON |
| slot-004 | incident_3009 | dynamic_no_verifier | 同上 |
| slot-008 | incident_3009 | fixed | 同上 |
| slot-009 | incident_3006 | dynamic_no_verifier | 同上 |
| slot-015 | incident_3010 | fixed | 同上 |
| slot-018 | incident_3010 | dynamic_no_verifier | 同上 |

各角色分析阶段的逻辑调用数（不是物理 HTTP 次数）：

| 角色 | 分析调用 | 需要修复 | 修复成功 | 修复后仍失败 |
|---|---:|---:|---:|---:|
| database | 16 | 13 | 7 | 6 |
| metrics | 21 | 7 | 7 | 0 |
| logs | 14 | 3 | 3 | 0 |
| changes | 3 | 3 | 3 | 0 |

database 的 23 次规划调用没有出现这些格式错误；问题集中在获取记录之后的分析阶段。只有有记录的任务才会调用模型分析；空结果由 runtime 构造数据缺口 finding，因此这些数量不是全部任务数。

全批次共 34 条物理失败事件：database INVALID_JSON 19、metrics 7、logs 3、changes 2、coordinator 1，另有 changes 与 verifier 各 1 次 SCHEMA_VALIDATION_FAILED。34 次失败事件对应 28 个需要修复的逻辑调用，不能当作 34 个独立失败任务。

## 为什么 database 更易触发

1. `src/incident_lens/agents/database.py:3` 的 DATABASE_PROMPT 开头就是“Inspect ... with get_db_connections, get_db_active_sessions, ...”，随后要求查询参数。它同时用于规划和分析。
2. `src/incident_lens/agents/service.py:476` 的 analyze() 继续使用 `prompt(task["role"])`，没有明确声明“工具已执行，此阶段只分析给定 records”。`context` 中仍有 allowed_tools、remaining_tool_calls，`task` 中仍有 allowed_tools 和调查问题。
3. database 通常只取得部分数据库类别记录，其他类别仍未知；角色提示要求进一步区分机制，模型容易试图补查。复现中已经取得 lock_waits 记录，但模型依然输出 get_db_lock_waits、get_db_slow_queries、get_db_health_metrics、get_db_active_sessions 的调用。
4. database 提示虽然要求把后续检查写进 requested_checks，但未把“后续任务建议”和“当前直接调用工具”划清。角色提示还称其为 RequestCheck，实际字段类型是 InvestigationTask，属于次要文案不一致；它不能解释这次语法层 DSML 失败。
5. 其他角色也会生成非法 JSON；其原始响应没有保存在项目 trace 中，不能推断它们也必然是 DSML。database 比较突出的工具导向提示和阶段歧义有源码及复现支持，但本次没有进行各角色的严格随机对照。

## 为什么一次修复仍然非法

`src/incident_lens/llm/structured_output.py:161` 为 INVALID_JSON 生成的修复文本实际为：

```text
Return a new JSON object matching the supplied JSON Schema. One repair only. Response content is not valid JSON.
```

`src/incident_lens/llm/provider.py:596` 仅将上述文本追加为新 user 消息：

```text
system + 原 user payload + 修复 user message
```

没有追加失败的 assistant 输出，也没有告知模型“你刚才输出了 DSML 工具调用；本阶段没有工具可调用；补充检查应写 requested_checks”。原来的工具导向角色提示和带工具权限的上下文全部保留，因此第二次生成仍沿用同一个错误行为。复现直接观察到了这种重复。

原调用温度为 0，但这不意味着请求完全确定；即使有 7 次通用修复成功，也不能认为一次重试必然会修复工具调用与分析输出的阶段冲突。

## 网关和提供商证据

项目配置：本地 `http://127.0.0.1:3425/v1`、模型别名 `auto/deepseek-v4.1-flash`、response_format=json_schema、strict=true、thinking=disabled。

网关的 usage 日志 `C:/Users/RickyMa/.config/magpie/usage.jsonl` 按请求开始时间和 completion_tokens 与项目事件匹配：六个终止失败调用的两次物理请求都由 **workbuddy / deepseek-v4.1-flash** 承接，HTTP 均为 200。匹配字段已保留在 evidence.json，不复制账号信息。路由日志顶层 provider 标签可能与实际执行的 tries/usage provider 不同，不能只看顶层标签。

slot-003 原失败的 route_id 为 1793416545739、1793416545742；本次重建失败为 1793416546776、1793416546778；提示对照成功为 1793416546823。后两组同样由 workbuddy 承接。

复现请求明确发送 json_schema strict=true，但返回 DSML，说明 **这条网关—提供商链路没有兑现请求端预期的硬结构约束**。现有证据不足以区分：网关转换时丢失/改写约束、上游忽略约束，或模型工具模板输出未被正确转换。也不能据此泛化为所有 DeepSeek 端点均有问题。连通性测试只有一个简单 status schema，不能证明复杂角色请求的结构可靠性。

项目原 trace 有意不保存原始 content，因此原六个故障不能逐字还原。对它们可确认的共同事实是阶段、分类、修复次数及实际提供商；DSML 具体形态来自同任务重建请求的两次原始返回，不冒充原响应。

## 诊断对照与建议

重建原 slot-003 的 task、公开 records 和 AgentContext；上下文按源码与 trace 重建，未恢复原始 HTTP 请求。第一次调用使用现有 analyze()；上限两次物理请求、无传输重试，两次均 INVALID_JSON / DSML。

对照只发一次：在角色提示末尾明确 CURRENT PHASE=ANALYZE，工具已执行、当前没有已注册工具、禁止 DSML/XML/Markdown/tool_calls，补充检查只能写入 requested_checks。其余继续使用既有动态 analysis_schema(records)。该请求返回合法 AnalysisOutput，通过全部 Pydantic schema；finding 的 task_id、run_id、incident_id、role 与输入一致，引用是允许的 incident_3007-E-003。对照中 citation_rule 的措辞也有简化，故该实验是定向提示对照，不是严格单变量实验。

建议后续生产修复：

- 分开规划与分析的阶段提示；分析阶段只允许消费 records 和输出分析对象，明确 additional checks 通过 requested_checks 建议。
- 分析输入改用当前阶段需要的身份与记录，减少 remaining_tool_calls 等执行提示；保留必要权限信息时明确其仅为 runtime 元数据。
- 为这种非 JSON 的工具标记输出生成专门修复说明，并在受限的修复上下文中引用上次输出；不得将任意原输出当可信指令，也不要自动执行 DSML。
- 保存脱敏的输出形态诊断（如 DSML/tool-call-like、JSON 错误位置、finish_reason、长度），并用复杂 AnalysisOutput 与 InvestigatorPlan 做提供商能力探测。
- 保持 schema 和引用校验，不通过放宽 JSON/业务契约掩盖错误；原生 tool calling 迁移需要另行设计工具轮次及阶段约束，不能只换 API 名称。

本次未改生产提示/校验器，未发起整批重跑。单次对照通过只说明修复方向有证据，不能声称所有案例已经修好。

## 复核文件

- evidence.json：批次冻结范围、槽位统计、源码 trace SHA256、网关匹配及诊断摘要。
- reproduction-attempts.json / reproduction-outcome.json：本次两次重建请求与返回、结果。
- control-attempts.json / control-outcome.json：一次提示对照请求与返回、结果。
- audit.py：离线统计和脱敏证据提取。
- reproduce.py：有网络请求的诊断脚本；默认最多两次，--analysis-phase-control 模式最多一次。使用当前本地凭证与当前自动路由，勿当作原测试回放。

原始响应文件可能带有上游 reasoning_content；报告仅提取最终 content 中的工具协议标记，不将其作为推理正确性证据。
