/**
 * English catalog — replay.js (recorded-prefix projection) + replay-panels.js
 * (replay metadata / history / review timeline / reliability panels).
 *
 * Owned by content-replay. Consumed by the DOM i18n engine (../i18n.js).
 * Format: { exact:{}, templates:[{zh,en}], fragments:[[/re/g,'repl']], phrases:[['中文','English']] }.
 */

export default {
  exact: {},

  templates: [
    { zh: '动作 · {}', en: 'Action · {}' },
    {
      zh: '候选评估 candidate_assessments：{} 条 · 详见当前事件的「原始结构化事件详情」，或「调查时间线」中该事件的展开行',
      en: 'Candidate assessments candidate_assessments: {} items · see the current event’s “raw structured event details”, or the expanded row for this event in the “investigation timeline”',
    },
  ],

  fragments: [],

  phrases: [
    /* ---- replay.js bookmark labels ---- */
    ['首次证据不足审查', 'First insufficient-evidence review'],
    ['首次 FinalizeGate 阻断', 'First FinalizeGate block'],
    ['配置变更证据', 'Config-change evidence'],
    ['首次调度', 'First dispatch'],
    ['最终审查', 'Final review'],
    ['最终报告', 'Final report'],
    ['竞争假设', 'Competing hypothesis'],

    /* ---- replay-panels.js : metadata block ---- */
    ['当前前缀尚无记录 / not recorded', 'No records in the current prefix / not recorded'],
    ['SOURCE DRIFT · 已保存来源检查发现变化；本录制不代表冻结正式实验。', 'SOURCE DRIFT · Saved source check found changes; this recording does not represent a frozen formal experiment.'],
    ['SOURCE DRIFT · 非冻结正式实验', 'SOURCE DRIFT · not a frozen formal experiment'],
    ['运行来源与限制 · 独立最终产物元数据快照', 'Run provenance and limits · standalone final-artifact metadata snapshot'],
    ['以下是整个已录制运行的元数据，不表示当前播放位置已知的调查结论。来源一致性为内部校验，非签名认证。', 'Below is metadata for the entire recorded run; it does not represent the investigation conclusion known at the current playback position. Source consistency is an internal check, not signature authentication.'],
    ['按保存顺序重建共享状态。选择章节会跳到对应事件；不会重新调用模型或工具。', 'Rebuild shared state in saved order. Selecting a chapter jumps to the corresponding event; it does not re-invoke models or tools.'],
    ['有效预算（Trace） / Protocol（已保存）', 'Effective budget (Trace) / Protocol (saved)'],
    ['运行期间记录的源码指纹发生变化；可展示真实开发调查过程，不能视为完全冻结的正式实验。', 'The source fingerprint recorded during the run changed; this can show a real development investigation process and must not be treated as a fully frozen formal experiment.'],
    ['仅显示产物记录的来源检查，不推断当前源码与录制时一致。', 'Only shows the artifact-recorded source check; does not infer that current source matches the recording.'],
    ['演示模式', 'Demo mode'],

    /* ---- replay-panels.js : workflow fallback ---- */
    ['编排视图暂不可用：当前事件结构无法解析。请使用「Communication Timeline」浏览事件。', 'Orchestration view temporarily unavailable: the current event structure could not be parsed. Please use “Communication Timeline” to browse events.'],

    /* ---- replay-panels.js : history ---- */
    ['此事件没有独立理由字段；参见原始结构化事件。', 'This event has no standalone reason field; see the raw structured event.'],
    ['相关 Coordinator / Verifier 事件', 'Related Coordinator / Verifier events'],
    ['首次提出', 'First proposed'],
    ['未决问题 · open_questions', 'Open questions · open_questions'],
    ['未决问题', 'Open questions'],
    ['支持', 'Support'],
    ['反对', 'Against'],
    ['无记录', 'No records'],

    /* ---- replay-panels.js : review cards ---- */
    ['原始结构化事件详情', 'Raw structured event details'],
    ['原始结构化事件', 'Raw structured event'],
    ['未识别事件结构', 'Unrecognized event structure'],
    ['该事件没有可识别的定案字段；展开查看原始结构。', 'This event has no recognizable finalize fields; expand to view the raw structure.'],
    ['该事件结构无法结构化呈现；展开查看原始结构。', 'This event structure cannot be presented structurally; expand to view the raw structure.'],
    ['诊断已通过', 'Diagnosis accepted'],
    ['根因服务 culprit_service', 'Root-cause service culprit_service'],
    ['假设状态 status', 'Hypothesis status'],
    ['报告支持证据 · supporting_evidence_ids', 'Report supporting evidence · supporting_evidence_ids'],
    ['支持证据 · support_ids', 'Supporting evidence · support_ids'],
    ['反对证据 · against_ids', 'Against evidence · against_ids'],
    ['预测观察 · predicted_observations', 'Predicted observations · predicted_observations'],
    ['无预测观察记录', 'No predicted observation records'],
    ['无未决问题记录', 'No open-question records'],
    ['降级调用 degraded_call_ids：', 'Degraded calls degraded_call_ids: '],
    ['· 无', '· none'],
    ['定案被阻断', 'Finalization blocked'],
    ['定案通过', 'Finalization passed'],
    ['动作 action', 'Action action'],
    ['理由 reason', 'Reason reason'],
    ['选中假设', 'Selected hypothesis'],
    ['阻断检查 · blocking checks：0 条（记录为空）', 'Blocking checks · blocking checks: 0 items (record empty)'],
    ['阻断检查 · blocking checks', 'Blocking checks · blocking checks'],
    ['未记录阻断检查 · 无 blocking checks', 'No blocking checks recorded · no blocking checks'],
    ['审查理由、证据版本与检查', 'Review rationale, evidence versions, and checks'],

    /* ---- replay-panels.js : request/check status (shared with orchestration) ---- */
    ['当前前缀：相同 task_id 已完成', 'Current prefix: same task_id already completed'],
    ['当前前缀：已调度，未见完成', 'Current prefix: dispatched, not yet completed'],
    ['当前前缀：未按此 task_id 调度；不推断检查已完成', 'Current prefix: not dispatched under this task_id; not inferring the check completed'],

    /* ---- replay-panels.js : reliability ---- */
    ['当前前缀尚无匹配恢复事件', 'No matching recovery event in the current prefix'],
    ['按 call_ids 对应恢复，非相邻事件假设。', 'Recovery matched by call_ids, not an adjacent-event assumption.'],
  ],
};
