/**
 * English i18n catalog for views.js (overview, investigate, run detail,
 * library) and the enum labels that views.js installs at runtime via
 * Object.assign on ROLE_LABEL / SOURCE_TYPE_META / EVENT_KIND.
 *
 * Consumed by the runtime i18n engine, which walks RENDERED text nodes and
 * selected attributes (aria-label/title/placeholder/alt) and applies:
 *   exact -> templates -> fragments -> phrases
 * templates use {} as a non-greedy wildcard over a whitespace-normalised,
 * anchored whole-string match; phrases are literal, longest-first substring
 * replacements; fragments are regex/substitution pairs. Product name
 * IncidentLens, IDs, enum tokens, file paths and already-English text are
 * kept unchanged.
 */

export default {
  exact: {},

  templates: [
    // "共 12 个案例 · 显示 12 个"
    { zh: "共 {} 个案例 · 显示 {} 个", en: "{} of {} cases shown" },
    // kpi foot: "缓存模式 off"
    { zh: "缓存模式 {}", en: "Cache mode {}" },
    // trace row / evidence row aria-labels
    { zh: "查看 {} 的运行详情", en: "View run details for {}" },
    { zh: "查看证据 {}", en: "View evidence {}" },
    // drawer title: "证据 · E-123"
    { zh: "证据 · {}", en: "Evidence · {}" },
  ],

  fragments: [
    // "${n} 轮" (also the "— 轮" placeholder when a trace has no recorded rounds)
    [/([\d—–-]+)\s*轮/g, "$1 rounds"],
    // "${n} 次工具"
    [/([\d—–-]+)\s*次工具/g, "$1 tool calls"],
    // "${n} 次模型请求"
    [/([\d—–-]+)\s*次模型请求/g, "$1 model requests"],
    // "${n} 秒"
    [/([\d—–-]+)\s*秒/g, "$1 s"],
    // "${n} 条记录"
    [/([\d—–-]+)\s*条记录/g, "$1 records"],
    // "${n} 条证据"
    [/([\d—–-]+)\s*条证据/g, "$1 evidence items"],
    // "${n} 服务"
    [/([\d—–-]+)\s*服务/g, "$1 services"],
    // "${n} 个案例" (fallback if the count template does not match)
    [/([\d—–-]+)\s*个案例/g, "$1 cases"],
  ],

  phrases: [
    /* ===================== Runtime enum labels (Object.assign) ===================== */
    ["数据库代理", "Database agent"],
    ["监控代理", "Monitoring agent"],
    ["修复方案代理", "Remediation plan agent"],
    ["数据库", "Database"],
    ["监控判断", "Monitoring decision"],
    ["建议方案就绪", "Advisory plan ready"],
    ["历史停止事件", "Historical stop event"],
    ["停止请求", "Stop request"],
    ["有序结束", "Orderly termination"],
    ["运行失败", "Run failed"],
    ["执行异常", "Execution error"],
    ["停止确认超时", "Stop-confirmation timeout"],
    ["调用失败已恢复", "Call failure recovered"],
    ["调用失败", "Call failed"],
    ["方案生成失败", "Plan generation failed"],
    ["诊断通过门禁", "Diagnosis passed gate"],
    ["停止确认", "Stop confirmation"],
    ["运行时", "Runtime"],

    /* ===================== Overview ===================== */
    ["总览", "Overview"],
    [
      "IncidentLens 是多智能体协作的故障根因调查控制台：协调者分派任务、专家代理在权限边界内取证、验证者交叉核对，最终输出带引用的根因报告 —— 或在证据不足时明确存疑。",
      "IncidentLens is a multi-agent root-cause investigation console: the coordinator dispatches tasks, expert agents gather evidence within their permission boundaries, and the verifier cross-checks the results, ultimately producing a cited root-cause report — or explicitly stating uncertainty when evidence is insufficient.",
    ],
    ["新建调查", "New investigation"],
    ["接受一份结论，需要三件事", "Accepting a conclusion requires three things"],
    ["每个根因都指向本次运行实际观察到的记录，而不是模型的记忆。", "Every root cause points to records actually observed in this run, not to the model's memory."],
    ["日志、指标、变更代理各自只持有只读工具；越权调用被代码拒绝。", "The logs, metrics, and changes agents each hold only read-only tools; out-of-scope calls are rejected in code."],
    ["轮次、工具、请求与时间都有硬上限；证据不足时输出存疑，而不是猜测。", "Rounds, tools, requests, and time all have hard limits; when evidence is insufficient, the output states uncertainty rather than guessing."],
    ["查看系统设计 →", "View system design →"],
    ["档案库概况", "Archive overview"],
    ["最近运行", "Recent runs"],
    ["协调是否值得它的成本？", "Is coordination worth its cost?"],
    ["同一模型、同一批 36 个加固案例、同一预算下，四种架构各跑一次。动态架构用约四成的时间与 token 换到与单代理相同或更好的质量。", "Using the same model, the same set of 36 hardened cases, and the same budget, four architectures each run once. The dynamic architecture trades about 40% of the time and tokens for quality equal to or better than a single agent."],
    ["查看完整评测", "View full evaluation"],
    ["观看一次回放", "Watch a replay"],
    ["设计原则", "Design principles"],
    ["引用或存疑", "Cite or doubt"],
    ["引用", "Citations"],
    ["权限", "Permissions"],
    ["停止", "Stopping"],
    ["结论必须引用确切记录；存在未决问题或竞争性假设时拒绝定论。", "Conclusions must cite exact records; when unresolved questions or competing hypotheses exist, a definitive conclusion is refused."],
    ["权限边界取证", "Evidence gathering within permission boundaries"],
    ["只读工具、角色 ACL、不可变签发上下文与实际查询台账。", "Read-only tools, role ACLs, immutable issuance contexts, and an actual query ledger."],
    ["离线可重放", "Offline replayable"],
    ["已保存痕迹可完整回放，不再调用编排图、工具或模型提供方。", "A saved trace can be fully replayed without calling the orchestration graph, tools, or model providers again."],
    ["解释缓存复用", "Explanation cache reuse"],
    ["精确或保守语义复用，严格命名空间与引用校验。", "Exact or conservative semantic reuse with strict namespace and reference validation."],

    /* ===================== Overview stats ===================== */
    ["事件案例", "Incident cases"],
    ["公开数据集", "Public dataset"],
    ["存档痕迹", "Archived traces"],
    ["results/ 全量", "results/ (full set)"],
    ["已定位根因", "Root cause identified"],
    ["明确存疑", "Clearly inconclusive"],
    ["证据不足时拒绝猜测", "Refuse to guess when evidence is insufficient"],
    ["占比", "of total"],
    ["还没有运行记录", "No runs yet"],
    ["发起一次调查，运行结果会自动归档到 results/ 目录。", "Start an investigation and the run results are automatically archived to the results/ directory."],
    ["加载失败，请稍后重试", "Loading failed, please try again later"],
    ["重试", "Retry"],

    /* ===================== Trace table ===================== */
    ["提供方", "Provider"],
    ["变体", "Variant"],
    ["轮次", "Rounds"],
    ["耗时", "Duration"],
    ["更新时间", "Updated"],
    ["演示", "Demo"],
    ["未知", "Unknown"],
    ["演示回放", "Demo replay"],

    /* ===================== Investigate ===================== */
    ["未选择案例", "No case selected"],
    ["从左侧列表中选择一个事件案例以查看详情。", "Select an incident case from the list on the left to view details."],
    ["选择一个公开事件案例，配置提供方与缓存策略后发起多智能体调查。", "Select a public incident case, configure the provider and cache strategy, then launch a multi-agent investigation."],
    ["暂无可用案例", "No cases available"],
    ["搜索事件 ID、标题或症状…", "Search incident ID, title, or symptoms…"],
    ["当前数据集没有可调查的事件。请确认 data/ 中的公开事件包已加载。", "The current dataset has no investigable incidents. Please confirm that the public incident packages in data/ are loaded."],
    ["没有匹配的案例", "No matching cases"],
    ["换个关键词试试。", "Try a different keyword."],
    ["开始于", "Started at"],
    ["观察到的症状", "Observed symptoms"],
    ["涉及服务", "Affected services"],

    /* ----- Run configuration ----- */
    ["监控模式", "Monitoring mode"],
    ["公开 EvidenceRecord 快照（JSON 数组）", "Public EvidenceRecord snapshot (JSON array)"],
    ["仅粘贴所选事件的公开观测记录。空数组不会触发告警。", "Paste only public observation records for the selected incident. An empty array will not trigger an alert."],
    ["PLAN_ONLY：仅生成建议方案，不执行修复，也不表示服务已恢复。", "PLAN_ONLY: generate an advisory plan only; do not execute remediation, and this does not mean the service has recovered."],
    ["事件响应采用较高预算，为数据库调查、监控和建议方案预留调用。", "Incident response uses a higher budget, reserving calls for database investigation, monitoring, and the advisory plan."],
    ["运行配置", "Run configuration"],
    ["模型提供方", "Model provider"],
    ["Mock · 离线确定性", "Mock · Offline deterministic"],
    ["Real · 真实模型", "Real · Live model"],
    ["Mock 完全离线、可复现；Real 需要 .env 中的端点与密钥配置。", "Mock is fully offline and reproducible; Real requires endpoint and key configuration in .env."],
    ["本地解释缓存", "Local explanation cache"],
    ["off · 关闭", "off · Off"],
    ["exact · 精确复用", "exact · Exact reuse"],
    ["semantic · 语义复用", "semantic · Semantic reuse"],
    ["工作流", "Workflow"],
    ["legacy_rca · 根因调查", "legacy_rca · Root-cause investigation"],
    ["incident_response · 监控、诊断与建议方案", "incident_response · Monitoring, diagnosis, and advisory plan"],
    ["legacy · 沿用事件摘要", "legacy · Use incident summary"],
    ["manual_snapshot · 公开观测快照", "manual_snapshot · Public observation snapshot"],
    ["offline_replay · 按时间回放公开观测", "offline_replay · Replay public observations by time"],
    ["预算上限", "Budget limits"],
    ["发起调查", "Start investigation"],
    ["结构化响应格式", "Structured response format"],
    ["json_schema · 严格模式", "json_schema · Strict mode"],
    ["json_object · JSON 模式", "json_object · JSON mode"],
    ["思考模式", "Thinking mode"],
    ["provider default · 提供方默认", "provider default · Provider default"],
    ["disabled · 禁用", "disabled · Disabled"],
    ["enabled · 启用", "enabled · Enabled"],
    ["请求超时（秒）", "Request timeout (seconds)"],
    ["项目本地的提供方请求设置无效，无法使用 Real 提供方。", "The project-local provider request settings are invalid; the Real provider cannot be used."],
    ["请先选择一个事件案例", "Please select an incident case first"],
    ["提供方请求设置无效，无法运行", "Provider request settings are invalid; cannot run"],
    ["请输入有效的公开 EvidenceRecord JSON 数组。", "Please enter a valid public EvidenceRecord JSON array."],
    ["正在调查公开证据…", "Investigating public evidence…"],
    ["调查完成 ·", "Investigation complete ·"],
    ["调查失败", "Investigation failed"],

    /* ===================== Run detail ===================== */
    ["运行详情", "Run details"],
    ["当前没有可查看的运行", "No run to view right now"],
    ["发起一次新调查，或从痕迹档案库中选择一条已保存的痕迹进行回放。", "Start a new investigation, or select a saved trace from the trace archive to replay."],
    ["浏览档案库", "Browse archive"],
    ["正在加载运行痕迹…", "Loading run trace…"],
    ["无法加载该痕迹", "Unable to load this trace"],
    ["请求失败，请重试。", "Request failed, please try again."],
    ["返回档案库", "Back to archive"],

    /* ----- Replay console ----- */
    ["首步", "First"],
    ["上一步", "Previous"],
    ["播放", "Play"],
    ["暂停", "Pause"],
    ["下一步", "Next"],
    ["末步", "Last"],
    ["速度", "Speed"],
    ["Seek · 保存事件位置", "Seek · Saved event position"],
    ["跳转", "Jump"],
    ["编排视图 · 共享状态与工作流", "Orchestration view · Shared state and workflow"],
    ["演示章节 · 基于事件语义查找", "Demo chapters · Located by event semantics"],
    ["章节名称用于导航；只有跳转后才展示对应历史状态。", "Chapter names are used for navigation; the corresponding historical state is shown only after jumping."],
    ["· 未记录", " · not recorded"],
    ["Communication Timeline · 有序事件导航", "Communication Timeline · Ordered event navigation"],
    ["事件类别", "Event category"],
    ["全部", "All"],
    ["Hypothesis Evolution · 已提交状态变化", "Hypothesis Evolution · Committed state changes"],
    ["Provider Timeout / Recovery · 可靠性事件", "Provider Timeout / Recovery · Reliability events"],
    ["已保存事件", "saved events"],
    ["未播放事件", "event not played"],
    ["执行事件时间：", "Event execution time: "],
    ["原始结构化事件详情", "Raw structured event details"],
    ["DECISION 包含提议；假设面板仅在 MERGE / HYPOTHESIS_RECONCILED 提交后更新。", "DECISION contains proposals; the hypothesis panel updates only after MERGE / HYPOTHESIS_RECONCILED commits."],
    ["此事件没有公开证据引用", "This event has no public evidence references"],
    ["调查开始前", "Before the investigation begins"],
    ["仅已知公开事故摘要；尚未观察工具证据或形成假设。", "Only the public incident summary is known; no tool evidence has been observed and no hypotheses have formed yet."],

    /* ----- Run head / KPIs / tabs ----- */
    ["本次调查刚刚完成", "This investigation just completed"],
    ["—— 以下时间线回放的是刚写入磁盘的痕迹；重新加载页面会得到相同结果。", " — The timeline below replays the trace just written to disk; reloading the page yields the same result."],
    ["MOCK 离线确定性策略", "MOCK offline deterministic strategy"],
    ["—— 以下结果用于演示流水线正确性，不代表真实模型的准确性。", " — The results below demonstrate pipeline correctness and do not represent real-model accuracy."],
    ["调查轮次", "Investigation rounds"],
    ["工具调用", "Tool calls"],
    ["模型请求", "Model requests"],
    ["缓存命中", "Cache hits"],
    ["缓存已关闭", "Cache disabled"],
    ["证据记录", "Evidence records"],
    ["本次运行观察", "Observed in this run"],
    ["运行", "Run"],
    ["模型", "Model"],
    ["缓存", "Cache"],
    ["录制总耗时", "Total recorded time"],
    ["来源指纹", "Source fingerprint"],
    ["完整 Trace / Report 下载在 REPORT 事件后解锁", "Full Trace / Report download unlocks after the REPORT event"],
    ["调查时间线", "Investigation timeline"],
    ["假设看板", "Hypothesis board"],
    ["证据登记", "Evidence registry"],
    ["调查发现", "Investigation findings"],
    ["根因报告", "Root-cause report"],

    /* ----- Timeline ----- */
    ["显示模型请求", "Show model requests"],
    ["没有匹配的事件", "No matching events"],
    ["调整筛选条件后重试。", "Adjust the filters and try again."],
    ["动作 ·", "Action ·"],
    ["判别标准：", "Discrimination criterion: "],
    ["停止原因：", "Stop reason: "],
    ["裁定 ·", "Verdict ·"],
    ["失败 ·", "Failed ·"],
    ["无附加详情", "No additional details"],

    /* ----- Hypotheses ----- */
    ["本次运行未产生假设", "This run produced no hypotheses"],
    ["未决问题", "Open questions"],

    /* ----- Evidence tab ----- */
    ["搜索证据 ID、服务或摘录…", "Search evidence ID, service, or excerpt…"],
    ["搜索证据", "Search evidence"],
    ["按来源筛选", "Filter by source"],
    ["证据 ID", "Evidence ID"],
    ["观察时间", "Observation time"],
    ["没有匹配的证据记录", "No matching evidence records"],

    /* ----- Findings ----- */
    ["尚无调查发现", "No investigation findings yet"],
    ["专家代理完成调查后，发现会汇总到这里。", "After the expert agents complete their investigation, findings are collected here."],
    ["反驳", "Refute"],
    ["中立", "Neutral"],
    ["结论陈述", "Claim"],
    ["关系", "Relation"],
    ["置信", "Confidence"],
    ["引用证据", "Cited evidence"],

    /* ----- Report ----- */
    ["已确定：现有证据最支持", "Determined: best supported by current evidence"],
    ["已确认", "Confirmed"],
    ["较可能（未确认）", "Likely (unconfirmed)"],
    ["证据不足", "Insufficient evidence"],
    ["尚未确认根因；以下保留已调查的解释、观察和关键缺口。", "Root cause not yet confirmed; the explanations investigated, observations, and key gaps are retained below."],
    ["目前没有足够证据支持具体的根因解释。", "There is currently not enough evidence to support a specific root-cause explanation."],
    ["尚未确认根因", "Root cause not yet confirmed"],
    ["责任服务", "Culprit service"],
    ["· 假设", " · Hypothesis"],
    ["待确认的解释", "Provisional explanations"],
    ["按已观察到的机制与来源支持排列，顺序不是正确概率。", "Ordered by observed mechanism and source support; the order is not a probability of correctness."],
    ["尚待解释的反对证据", "Counter-evidence yet to be explained"],
    ["已有观察（归因尚未确认）", "Existing observations (attribution not yet confirmed)"],
    ["结论的证据边界", "Evidentiary boundaries of the conclusion"],
    ["因果链", "Causal chain"],
    ["支持证据", "Supporting evidence"],
    ["已排除假设", "Rejected hypotheses"],
    ["反对证据：", "Counter-evidence: "],
    ["关键缺口", "Key gaps"],
    ["建议下一步", "Suggested next steps"],
    ["以下检查尚未执行，可能需要补采新数据。", "The following checks have not been performed and may require collecting new data."],
    ["可选补充（不阻止作答）", "Optional additions (do not block answering)"],
    ["判断依据", "Basis for judgment"],
    ["停止原因", "Stop reason"],
    ["查看 Markdown 原文", "View raw Markdown"],

    /* ===================== Library ===================== */
    ["痕迹档案库", "Trace archive"],
    ["results/ 目录下所有已保存的调查痕迹。点击任意一条进行离线回放 —— 不再调用编排图、工具或模型。", "All saved investigation traces under the results/ directory. Click any one to replay offline — no orchestration graph, tools, or models are called."],
    ["搜索事件 ID 或运行 ID…", "Search incident ID or run ID…"],
    ["搜索痕迹", "Search traces"],
    ["按提供方筛选", "Filter by provider"],
    ["按状态筛选", "Filter by status"],
    ["全部状态", "All statuses"],
    ["运行错误", "Run error"],
    ["没有匹配的痕迹", "No matching traces"],
    ["档案库为空", "Archive is empty"],
    ["调整搜索或筛选条件。", "Adjust the search or filter conditions."],
    ["通过命令行或新建调查发起一次运行后，痕迹会出现在这里。", "After you start a run from the command line or a new investigation, traces appear here."],

    /* ===================== Attributes (aria-label / placeholder / title) ===================== */
    ["质量成功数（满分 36）", "Quality successes (out of 36)"],
    ["案例选择", "Case selection"],
    ["搜索案例", "Search cases"],
    ["案例列表", "Case list"],
    ["运行详情视图", "Run detail views"],
    ["当前事件详情", "Current event details"],
    ["按角色筛选", "Filter by role"],
    ["未记录对应事件", "did not record the corresponding event"],

    /* ===================== Short shared labels ===================== */
    ["事件", "Incident"],
    ["来源", "Source"],
    ["服务", "Service"],
    ["摘录", "Excerpt"],
    ["成功", "Success"],
    ["支持", "Support"],
    ["反对", "Against"],
  ],
};
