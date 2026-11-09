/**
 * English i18n catalog for components.js (badges, empty states, skeletons,
 * toasts, drawer, evidence detail, workflow report).
 *
 * Consumed by the runtime i18n engine, which walks RENDERED text nodes and
 * selected attributes (aria-label/title/placeholder/alt) and applies:
 *   exact -> templates -> fragments -> phrases
 * templates use {} as a non-greedy wildcard over a whitespace-normalised,
 * anchored whole-string match; phrases are literal, longest-first substring
 * replacements; fragments are regex/substitution pairs.
 */

export default {
  exact: {
    "无": "None",
  },

  templates: [
    { zh: "证据 {} 未在本次运行索引中", en: "Evidence {} is not in this run's index" },
    { zh: "证据 · {}", en: "Evidence · {}" },
  ],

  fragments: [
    // task attempt number: "… · 第 2 次"
    [/第\s*([\d—–-]+)\s*次/g, "attempt $1"],
  ],

  phrases: [
    // Skeletons / loading
    ["加载中…", "Loading…"],

    // Evidence detail drawer
    ["Evidence ID（原始 ID）", "Evidence ID (original ID)"],
    ["证据观察时间（事故时间）", "Evidence observation time (incident time)"],
    ["来源文件", "Source file"],
    ["首次来源 Agent", "First source Agent"],
    ["查询执行时间", "Query execution time"],
    ["来源工具 / 事件", "Source tool / event"],
    ["已记录查询 / Task / Call", "Recorded queries / Tasks / Calls"],
    ["关联 Finding / Hypothesis", "Related Findings / Hypotheses"],
    ["报告引用", "Report references"],
    ["原始摘录", "Original excerpt"],
    [
      "来源 Agent、查询执行时间、Findings / Hypotheses 关系与报告引用仅来自当前回放前缀。无法获得的原始证据不补造。",
      "The source Agent, query execution time, Findings / Hypotheses relationships, and report references come only from the current replay prefix. Original evidence that is unavailable is not fabricated.",
    ],
    ["最终报告支持证据", "Supporting evidence in the final report"],
    ["用于待确认解释，尚未支持最终诊断", "Used for a provisional explanation; does not yet support a final diagnosis"],
    ["未列为最终报告支持证据", "Not listed as supporting evidence in the final report"],
    ["当前前缀没有关联 Finding。", "No associated Finding in the current prefix."],
    ["当前前缀尚未生成报告。", "No report generated in the current prefix."],

    // Workflow report
    ["事件响应工作流", "Incident response workflow"],
    ["诊断状态", "Diagnosis status"],
    ["方案状态", "Plan status"],
    ["工作流状态", "Workflow status"],
    ["终止结果", "Termination result"],
    ["停止确认：", "Stop confirmation: "],
    ["已完成", "Completed"],
    ["未完成", "Not completed"],
    ["· 失败阶段：", " · Failure stage: "],
    ["监控告警 ·", "Monitoring alert ·"],
    ["PLAN_ONLY · 仅生成建议方案", "PLAN_ONLY · Advisory plan only"],
    [
      "方案尚未执行；诊断完成和方案就绪不表示服务已恢复。变更前需操作人员确认。",
      "The plan has not been executed; a completed diagnosis and a ready plan do not mean the service has recovered. Operator confirmation is required before any change.",
    ],
    ["方案引用证据", "Plan evidence references"],
    ["根因版本", "Root cause version"],
    ["任务与重试记录 ·", "Tasks and retries ·"],
    ["任务 / 尝试", "Task / Attempt"],
    ["建议动作", "Recommended actions"],
    ["执行前提", "Preconditions"],
    ["验证步骤", "Verification steps"],
    ["回滚", "Rollback"],

    // Short labels (own text nodes / table headers / list titles)
    ["角色", "Role"],
    ["状态", "Status"],
    ["错误", "Error"],
    ["风险", "Risks"],
  ],
};
