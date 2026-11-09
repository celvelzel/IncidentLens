/**
 * English catalog — orchestration.js (replay orchestration view-model + render helpers).
 *
 * Owned by content-replay. Consumed by the DOM i18n engine (../i18n.js).
 * Format: { exact:{}, templates:[{zh,en}], fragments:[[/re/g,'repl']], phrases:[['中文','English']] }.
 *
 * NOTE: orchestration.js renders several BILINGUAL strings in source (role labels like
 * "协调者 Coordinator", section headings like "验证审查门 Verifier Review Gate", verdict
 * labels like "证据充分 Sufficient"). The full bilingual phrase is listed FIRST so the
 * longest-first phrase matcher maps it to English-only and never yields "Coordinator
 * Coordinator"; shorter single-word entries follow for standalone occurrences.
 */

export default {
  exact: {
    // Full bilingual role labels (single text nodes, e.g. evidence-flow agent rows).
    '协调者 Coordinator': 'Coordinator',
    '日志调查员 Logs Agent': 'Logs Agent',
    '指标调查员 Metrics Agent': 'Metrics Agent',
    '数据库调查员 Database Agent': 'Database Agent',
    '变更调查员 Changes Agent': 'Changes Agent',
    '验证审查 Verifier': 'Verifier',
    '报告者 Reporter': 'Reporter',
    '单体代理 Single Agent': 'Single Agent',
    // Full bilingual section headings / verdict labels (single text nodes).
    '验证审查门 Verifier Review Gate': 'Verifier Review Gate',
    '证据流向 Evidence Flow': 'Evidence Flow',
    '证据充分 Sufficient': 'Sufficient',
    '证据不足 Insufficient': 'Insufficient',
    '合并证据 → Public Evidence': 'Merged Evidence → Public Evidence',
  },

  templates: [
    { zh: '轮次 {} / {}', en: 'Rounds {} / {}' },
    { zh: '工具 {} / {}', en: 'Tools {} / {}' },
    { zh: '模型请求 {} / {}', en: 'Model calls {} / {}' },
    { zh: '第 {} 轮', en: 'Round {}' },
  ],

  fragments: [
    // Numeric unit patterns (counts interpolated before a unit word / before "条证据").
    [/(\d+)\s*条证据/g, '$1 evidence'],
    [/(\d+)\s*证据/g, '$1 evidence'],
    [/(\d+)\s*发现/g, '$1 findings'],
    [/(\d+)\s*假设/g, '$1 hypotheses'],
    [/(\d+)\s*审查/g, '$1 reviews'],
    [/(\d+)\s*不足/g, '$1 insufficient'],
    [/(\d+)\s*充分/g, '$1 sufficient'],
    // Ordinal patterns embedded in larger sentences.
    [/第\s*(\d+)\s*轮重新调度/g, 'Round $1 re-dispatch'],
    [/第\s*(\d+)\s*轮/g, 'Round $1'],
    [/第\s*(\d+)\s*次/g, 'attempt $1'],
    [/第\s*(\d+)\s*章/g, 'Chapter $1'],
  ],

  phrases: [
    /* ---- Full bilingual strings (longest-first wins before short forms) ---- */
    ['验证审查门 Verifier Review Gate', 'Verifier Review Gate'],
    ['证据流向 Evidence Flow', 'Evidence Flow'],
    ['证据充分 Sufficient', 'Sufficient'],
    ['证据不足 Insufficient', 'Insufficient'],
    ['验证审查 Verifier', 'Verifier'],
    ['合并证据 → Public Evidence', 'Merged Evidence → Public Evidence'],
    ['协调者 Coordinator', 'Coordinator'],
    ['日志调查员 Logs Agent', 'Logs Agent'],
    ['指标调查员 Metrics Agent', 'Metrics Agent'],
    ['数据库调查员 Database Agent', 'Database Agent'],
    ['变更调查员 Changes Agent', 'Changes Agent'],
    ['报告者 Reporter', 'Reporter'],
    ['单体代理 Single Agent', 'Single Agent'],

    /* ---- Roles (standalone words) ---- */
    ['协调者', 'Coordinator'],
    ['日志调查员', 'Logs Agent'],
    ['指标调查员', 'Metrics Agent'],
    ['数据库调查员', 'Database Agent'],
    ['变更调查员', 'Changes Agent'],
    ['验证审查', 'Verifier'],
    ['报告者', 'Reporter'],
    ['单体代理', 'Single Agent'],
    ['运行时', 'Runtime'],

    /* ---- Task statuses ---- */
    ['已调度 · 尚无执行记录', 'Dispatched · no execution record yet'],
    ['当前前缀：相同 task_id 已完成', 'Current prefix: same task_id already completed'],
    ['当前前缀：已调度，未见完成', 'Current prefix: dispatched, not yet completed'],
    ['当前前缀：未按此 task_id 调度；不推断检查已完成', 'Current prefix: not dispatched under this task_id; not inferring the check completed'],
    ['已完成 · 无 finding 提交', 'Completed · no finding submitted'],
    ['尚无结果', 'No result yet'],
    ['已调度', 'Assigned'],
    ['运行中', 'Running'],
    ['已完成', 'Completed'],
    ['失败', 'Failed'],
    ['未开始', 'Not Started'],
    ['有已记录动作', 'Has recorded actions'],
    ['仅审查建议 · 未调度', 'Review suggestion only · not dispatched'],
    ['内部协调任务', 'Internal coordination task'],

    /* ---- Stage names / glosses / units ---- */
    ['专家(并行)', 'Experts (parallel)'],
    ['合并证据', 'Merged Evidence'],
    ['定案门', 'Finalize Gate'],
    ['假设', 'Hypotheses'],
    ['报告', 'Report'],
    ['决策', 'decisions'],
    ['任务', 'tasks'],
    ['证据', 'evidence'],
    ['审查', 'reviews'],
    ['定案', 'finalize'],
    ['发现', 'Findings'],

    /* ---- Finalize / prefix status notes ---- */
    ['待定案', 'Pending finalization'],
    ['定案提议 · 等待门禁', 'Finalize proposed · awaiting gate'],
    ['已阻断 · FINALIZE_REJECTED', 'Blocked · FINALIZE_REJECTED'],
    ['诊断已通过 · DIAGNOSIS_ACCEPTED', 'Diagnosis accepted · DIAGNOSIS_ACCEPTED'],
    ['尚未定案', 'Not yet finalized'],
    ['已接受假设', 'Accepted hypothesis'],
    ['所选假设', 'Selected hypothesis'],
    ['无矛盾记录', 'No contradictions recorded'],

    /* ---- Stages / narrative ---- */
    ['该变体无验证者 · 未审查', 'This variant has no verifier · not reviewed'],
    ['当前前缀尚无对应事件', 'No corresponding event in the current prefix'],
    ['Trace 未记录对应事件', 'Trace did not record the corresponding event'],
    ['当前前缀尚无验证审查', 'No verifier review in the current prefix'],
    ['当前前缀尚无角色记录', 'No role records in the current prefix'],
    ['当前前缀尚无证据', 'No evidence in the current prefix'],
    ['当前前缀尚无发现', 'No findings in the current prefix'],
    ['当前前缀尚未生成报告', 'No report generated in the current prefix yet'],
    ['当前前缀尚无调度 / no dispatch yet', 'No dispatch in the current prefix / no dispatch yet'],
    ['编排阶段', 'Orchestration stages'],
    ['演示叙事', 'Demo narrative'],
    ['按轮次调度泳道', 'Round dispatch swimlane'],
    ['角色统计', 'Role statistics'],
    ['验证审查门', 'Verifier Review Gate'],
    ['证据流向', 'Evidence Flow'],
    ['上一关键节点', 'Previous key node'],
    ['下一关键节点', 'Next key node'],
    ['跳到事件', 'Jump to event'],
    ['跳到决策', 'Jump to decision'],
    ['当前', 'Current'],
    ['并行', 'Parallel'],
    ['已达轮次上限', 'Round limit reached'],
    ['只从回放前缀派生 · presentation only', 'Derived from replay prefix only · presentation only'],
    ['从 0 开始播放，按「下一关键节点」开始演示。', 'Start playing from 0; press “Next key node” to begin the demo.'],

    /* ---- Narrative chapters ---- */
    ['查看首次调度的任务。', 'View the first dispatched task.'],
    ['查看配置差异查询返回的证据。', 'View the evidence returned by the config-diff query.'],
    ['查看首次证据不足的审查。', 'View the first insufficient-evidence review.'],
    ['查看该竞争假设被排除的记录。', 'View the record where this competing hypothesis was ruled out.'],
    ['查看定案门阻断的记录。', 'View the record where the finalize gate was blocked.'],
    ['查看最后一次验证审查的结果。', 'View the result of the last verifier review.'],
    ['查看最终报告及其记录的结论。', 'View the final report and its recorded conclusion.'],
    ['调查开始前', 'Before the investigation'],
    ['调查开始：只有公开事故摘要，尚无证据。', 'Investigation start: only the public incident summary, no evidence yet.'],

    /* ---- Swimlane / roles detail ---- */
    ['协调者内部步骤', 'Coordinator internal steps'],
    ['（计划/综合）', ' (planning/synthesis)'],
    ['重新调度', 're-dispatch'],
    ['真实任务与结果', 'Real tasks and results'],
    ['没有执行记录。审查建议不等于已执行工具查询。', 'No execution record. Review suggestions are not the same as executed tool queries.'],
    ['验证审查对该角色的检查建议（含未执行）', 'Verifier check suggestions for this role (including unexecuted)'],
    ['可选检查 Optional → 未记录可选检查', 'Optional check → no optional check recorded'],
    ['可选检查 Optional', 'Optional check'],
    ['阻断检查 Blocking', 'Blocking check'],
    ['未记录可选检查', 'no optional check recorded'],
    ['可选检查', 'Optional check'],
    ['阻断检查', 'Blocking check'],

    /* ---- Stats ---- */
    ['完成 / 失败', 'Completed / Failed'],
    ['工具调用', 'Tool calls'],
    ['产出证据', 'Evidence produced'],
    ['调度', 'Dispatches'],
    ['耗时', 'Duration'],

    /* ---- Review gate ---- */
    ['目标假设：', 'Target hypothesis: '],
    ['审查理由与版本哈希', 'Review rationale and version hashes'],

    /* ---- Evidence flow ---- */
    ['来源 Agent', 'Source Agent'],
    ['证据 Evidence', 'Evidence'],
    ['发现 / 假设 Findings · Hypotheses', 'Findings / Hypotheses'],
    ['报告引用 Report', 'Report references'],
    ['因果链 · causal_chain', 'Causal chain · causal_chain'],

    /* ---- Misc ---- */
    ['无', 'None'],
    ['未记录', 'not recorded'],
  ],
};
