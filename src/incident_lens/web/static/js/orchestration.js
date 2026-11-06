/**
 * IncidentLens replay orchestration — pure view-model + render helpers.
 *
 * Everything here is derived ONLY from the replay-prefix `state` produced by
 * replay.js (`replayPrefix(trace, position)`). No DOM, no window, no fetch,
 * no side effects — so the builders are directly importable under `node --test`.
 *
 * The render helpers return HTML strings (dynamic values are escaped with
 * `escapeHtml`). DOM wiring lives in replay-panels.js (`bindWorkflowInteractions`).
 */
import { escapeHtml as esc, formatDuration, SOURCE_TYPE_META, ROLE_LABEL, variantLabel } from './api.js';
import { replayWorkflow } from './replay.js';

/* ------------------------------------------------------------------ *
 * Labels & tones
 * ------------------------------------------------------------------ */

const ROLE_GLOSS = {
  coordinator: ['协调者', 'Coordinator'],
  logs: ['日志调查员', 'Logs Agent'],
  metrics: ['指标调查员', 'Metrics Agent'],
  database: ['数据库调查员', 'Database Agent'],
  changes: ['变更调查员', 'Changes Agent'],
  verifier: ['验证审查', 'Verifier'],
  reporter: ['报告者', 'Reporter'],
  single: ['单体代理', 'Single Agent'],
};

const roleZh = (role) => {
  const g = ROLE_GLOSS[role];
  return g ? g[0] : ROLE_LABEL[role] || role || '运行时';
};
const roleEn = (role) => {
  const g = ROLE_GLOSS[role];
  return g ? g[1] : '';
};
const roleLabel = (role) => {
  const en = roleEn(role);
  return en ? `${roleZh(role)} ${en}` : roleZh(role);
};

const TASK_STATUS = {
  ASSIGNED: { label: '已调度', tone: 'info', icon: 'clock' },
  RUNNING: { label: '运行中', tone: 'info', icon: 'play' },
  COMPLETED: { label: '已完成', tone: 'success', icon: 'check' },
  FAILED: { label: '失败', tone: 'danger', icon: 'alert' },
  NOT_STARTED: { label: '未开始', tone: 'neutral', icon: 'dot' },
};

const ICON_SVG = {
  check:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.2 8.4l3 3 6.6-6.8"/></svg>',
  clock:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="5.4"/><path d="M8 4.8V8l2.3 1.4"/></svg>',
  play:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M5.2 3.6l7 4.4-7 4.4z"/></svg>',
  alert:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2.2l6 10.6H2z"/><path d="M8 6.2v3"/><circle cx="8" cy="11.1" r="0.5"/></svg>',
  shield:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2l5 1.9v4.2c0 3-2.2 4.8-5 6-2.8-1.2-5-3-5-6V3.9z"/><path d="M5.6 8l1.8 1.8 3.1-3.3"/></svg>',
  dot:
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="8" cy="8" r="3.2"/></svg>',
};
const TONE_ICON = { success: 'check', warning: 'alert', danger: 'alert', info: 'dot', neutral: 'dot' };

/** Status badge = shape + inline SVG icon + text (never colour alone). */
export function statusBadge(text, tone = 'neutral', icon) {
  const name = icon || TONE_ICON[tone] || 'dot';
  return `<span class="orch-status" data-tone="${esc(tone)}"><span class="orch-status__icon" aria-hidden="true">${
    ICON_SVG[name] || ICON_SVG.dot
  }</span><span class="orch-status__text">${esc(text)}</span></span>`;
}

const shortEvidenceId = (id) => String(id ?? '').split('-').pop();

/** Relation label as a status badge (icon + text + tone), consistent with statusBadge. */
function relationBadge(relation) {
  const rel = relation || 'neutral';
  const tone = rel === 'supports' ? 'info' : rel === 'against' ? 'warning' : 'neutral';
  return statusBadge(rel, tone);
}

function chips(ids, evidenceIndex) {
  if (!ids || !ids.length) return '<span class="text-muted">无</span>';
  return ids
    .map((id) => {
      const known = evidenceIndex && Object.hasOwn(evidenceIndex, id);
      return `<button type="button" class="evidence-chip" data-evidence-id="${esc(id)}"${
        known ? '' : ' disabled title="unavailable in this prefix"'
      }>${esc(id)}</button>`;
    })
    .join('');
}

/* ------------------------------------------------------------------ *
 * Lifecycle / prefix helpers
 * ------------------------------------------------------------------ */

function taskIdOf(e) {
  return e.task_id || e.details?.task_id || null;
}

function buildLifecycle(state) {
  const events = state.events || [];
  const records = [];
  const byKey = {};
  events.forEach((e, i) => {
    if (!e.event_type || !e.event_type.startsWith('TASK_')) return;
    const d = e.details || {};
    const taskId = taskIdOf(e);
    if (!taskId) return;
    const attemptId = d.attempt_id || null;
    const key = `${taskId}::${attemptId || ''}`;
    let r = byKey[key];
    if (!r) {
      r = {
        task_id: taskId, attempt_id: attemptId, attempt: d.attempt || 1, role: e.role || null,
        status: null, errorCode: null, assignedAt: null, runningAt: null, completedAt: null, failedAt: null,
        assignedPos: null, runningPos: null, completedPos: null, failedPos: null, durationMs: null,
      };
      byKey[key] = r;
      records.push(r);
    }
    if (e.role) r.role = e.role;
    if (d.attempt) r.attempt = d.attempt;
    const status = d.status || e.event_type.slice(5);
    r.status = status;
    if (status === 'ASSIGNED') { r.assignedAt = e.timestamp; r.assignedPos = i + 1; }
    else if (status === 'RUNNING') { r.runningAt = e.timestamp; r.runningPos = i + 1; }
    else if (status === 'COMPLETED') { r.completedAt = e.timestamp; r.completedPos = i + 1; }
    else if (status === 'FAILED') { r.failedAt = e.timestamp; r.failedPos = i + 1; }
    if (d.error_code != null) r.errorCode = d.error_code;
  });
  records.forEach((r) => {
    if (r.completedAt && r.assignedAt) {
      const a = Date.parse(r.assignedAt), c = Date.parse(r.completedAt);
      r.durationMs = Number.isFinite(a) && Number.isFinite(c) ? c - a : null;
    }
  });
  const byTask = {};
  records.forEach((r) => { (byTask[r.task_id] = byTask[r.task_id] || []).push(r); });
  return { records, byTask };
}

function buildFinalize(state) {
  const events = state.events || [];
  const finIdx = events.findIndex((e) => e.event_type === 'DECISION' && e.details?.decision?.action === 'FINALIZE');
  const diagIdx = events.findIndex((e) => e.event_type === 'DIAGNOSIS_ACCEPTED');
  const blocked = events.some((e) => e.event_type === 'FINALIZE_REJECTED');
  const fin = finIdx >= 0 ? events[finIdx] : null;
  const diag = diagIdx >= 0 ? events[diagIdx] : null;
  const present = !!diag || !!fin;
  const selectedHypothesisId =
    fin?.details?.decision?.selected_hypothesis_id || diag?.details?.root_cause?.hypothesis_id || null;
  const statusText = blocked ? '已阻断 · FINALIZE_REJECTED' : present ? '已定案 / 未触发阻断' : '待定案';
  const statusTone = blocked ? 'danger' : present ? 'success' : 'neutral';
  return {
    present,
    decisionEventId: fin?.event_id || diag?.event_id || null,
    position: finIdx >= 0 ? finIdx + 1 : diagIdx >= 0 ? diagIdx + 1 : null,
    selectedHypothesisId,
    diagnosisAccepted: !!diag,
    blocked,
    statusText,
    statusTone,
  };
}

function currentStageId(state) {
  const events = state.events || [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const e = events[i];
    const d = e.details || {};
    const et = e.event_type;
    if (et === 'REPORT') return 'report';
    if (['NORMAL_TERMINATION', 'WORKFLOW_STOP_REQUESTED', 'DIAGNOSIS_ACCEPTED'].includes(et)) return 'finalize';
    if (et === 'DECISION' && d.decision?.action === 'FINALIZE') return 'finalize';
    if (et === 'REVIEW') return 'review';
    if (['MERGE', 'HYPOTHESIS_RECONCILED'].includes(et)) return 'hypotheses';
    if (et === 'TOOL_CALL') return 'experts';
    if (et.startsWith('TASK_')) {
      const tid = taskIdOf(e) || '';
      return tid.startsWith('coordinate-') ? 'coordinator' : 'experts';
    }
    if (et === 'DECISION' && d.decision?.action === 'INVESTIGATE') return 'coordinator';
  }
  return 'coordinator';
}

/* ------------------------------------------------------------------ *
 * Variant-level verifier capability
 *
 * Availability must not be inferred from the replay prefix alone: at early
 * positions a verifier-capable trace has simply not reached its first REVIEW,
 * which is "pending", not "this variant has no verifier". The recorded trace
 * variant is the authoritative capability signal; ambiguous/unknown variants
 * fall back to prefix evidence.
 * ------------------------------------------------------------------ */

const VERIFIER_VARIANTS = {
  full: true,
  single: false,
  fixed: false,
  dynamic_no_verifier: false,
  no_verifier: false,
};

export function variantVerifierCapability(variant) {
  if (variant == null || variant === '') return null;
  return Object.hasOwn(VERIFIER_VARIANTS, variant) ? VERIFIER_VARIANTS[variant] : null;
}

/** True when the prefix has already produced verifier evidence (REVIEW / verifier role). */
export function prefixHasVerifier(state) {
  const events = state.events || [];
  return events.some((e) => e.event_type === 'REVIEW' || e.role === 'verifier');
}

/**
 * Verifier availability for this trace:
 * - an actual REVIEW in the prefix is direct evidence → always available
 * - variant says yes  → available even before the first REVIEW (stage = pending)
 * - variant says no   → not available
 * - ambiguous/unknown → fall back to prefix evidence (verifier-role events)
 */
export function resolveHasVerifier(state, opts = {}) {
  if (prefixHasVerifier(state)) return true;
  const capability = variantVerifierCapability(opts.variant);
  if (capability === true) return true;
  if (capability === false) return false;
  return false;
}

/* ------------------------------------------------------------------ *
 * Builders
 * ------------------------------------------------------------------ */

export function buildStages(state, opts = {}) {
  const events = state.events || [];
  const decisions = events.filter((e) => e.event_type === 'DECISION');
  const assignments = decisions.flatMap((e) => e.details?.decision?.assignments || []);
  const reviewEvents = events.filter((e) => e.event_type === 'REVIEW');
  const hasVerifier = resolveHasVerifier(state, opts);
  const diagAccepted = events.some((e) => e.event_type === 'DIAGNOSIS_ACCEPTED');
  const hasFinalizeDecision = events.some((e) => e.event_type === 'DECISION' && e.details?.decision?.action === 'FINALIZE');
  const reportEvents = events.filter((e) => e.event_type === 'REPORT');
  const uniqueEvidence = Object.keys(state.evidence_index || {}).length;
  const current = currentStageId(state);
  const pos = (pred) => {
    const i = events.findIndex(pred);
    return i < 0 ? null : i + 1;
  };
  const expertTask = (e) => e.event_type.startsWith('TASK_') && e.role && e.role !== 'coordinator' && !(taskIdOf(e) || '').startsWith('coordinate-');

  const defs = [
    {
      id: 'coordinator', label: '协调者', gloss: 'Coordinator', unit: '决策',
      count: decisions.length, reached: decisions.length > 0,
      first: pos((e) => e.event_type === 'DECISION'),
    },
    {
      id: 'experts', label: '专家(并行)', gloss: 'Experts · parallel', unit: '任务',
      count: assignments.length, reached: assignments.length > 0 || events.some(expertTask),
      first: pos(expertTask) ?? pos((e) => e.event_type === 'DECISION' && e.details?.decision?.action === 'INVESTIGATE'),
    },
    {
      id: 'evidence', label: '合并证据', gloss: 'Public Evidence', unit: '证据',
      count: uniqueEvidence, reached: events.some((e) => e.event_type === 'MERGE'),
      first: pos((e) => e.event_type === 'MERGE'),
    },
    {
      id: 'hypotheses', label: '假设', gloss: 'Hypotheses', unit: '假设',
      count: (state.hypotheses || []).length,
      reached: events.some((e) => ['MERGE', 'HYPOTHESIS_RECONCILED'].includes(e.event_type)),
      first: pos((e) => ['MERGE', 'HYPOTHESIS_RECONCILED'].includes(e.event_type)),
    },
    {
      id: 'review', label: '验证审查', gloss: 'Verifier', unit: '审查',
      count: reviewEvents.length, reached: reviewEvents.length > 0,
      first: reviewEvents.length ? events.findIndex((e) => e === reviewEvents[0]) + 1 : null,
    },
    {
      id: 'finalize', label: '定案门', gloss: 'FinalizeGate', unit: '定案',
      count: diagAccepted ? 1 : 0, reached: diagAccepted || hasFinalizeDecision,
      first: pos((e) => e.event_type === 'DECISION' && e.details?.decision?.action === 'FINALIZE') ?? pos((e) => e.event_type === 'DIAGNOSIS_ACCEPTED'),
    },
    {
      id: 'report', label: '报告', gloss: 'Report', unit: '报告',
      count: reportEvents.length, reached: reportEvents.length > 0,
      first: pos((e) => e.event_type === 'REPORT'),
    },
  ];

  return defs.map((d, index) => {
    const available = d.id === 'review' ? hasVerifier : true;
    const stateName = !available ? 'skipped' : d.id === current ? 'current' : d.reached ? 'done' : 'pending';
    return {
      id: d.id,
      index,
      label: d.label,
      gloss: available ? d.gloss : '该变体无验证者 · 未审查',
      count: d.count,
      countUnit: d.unit,
      reached: d.reached,
      available,
      state: stateName,
      isCurrent: stateName === 'current',
      ariaCurrent: stateName === 'current' ? 'step' : null,
      firstEventPosition: d.first ?? null,
    };
  });
}

export function buildRounds(state) {
  const events = state.events || [];
  const { byTask } = buildLifecycle(state);
  const rounds = [];
  let round = 0;
  events.forEach((e, i) => {
    const d = e.details || {};
    if (!(e.event_type === 'DECISION' && d.decision?.action === 'INVESTIGATE')) return;
    round += 1;
    const assignments = (d.decision.assignments || []).map((a) => {
      const recs = (byTask[a.task_id] || []).slice().sort((x, y) => (x.assignedPos || 0) - (y.assignedPos || 0));
      const r = recs[recs.length - 1] || null;
      const status = r?.status || 'NOT_STARTED';
      const meta = TASK_STATUS[status] || TASK_STATUS.NOT_STARTED;
      return {
        taskId: a.task_id,
        role: a.role,
        roleLabel: roleLabel(a.role),
        question: a.question || '',
        reason: a.reason || '',
        allowedTools: a.allowed_tools || [],
        eventId: e.event_id,
        position: i + 1,
        timestamp: r?.assignedAt || e.timestamp,
        status,
        statusLabel: meta.label,
        statusTone: meta.tone,
        attemptId: r?.attempt_id || null,
        errorCode: r?.errorCode || null,
        jumpPosition: r?.assignedPos || r?.runningPos || i + 1,
        startedAt: r?.assignedAt || null,
        completedAt: r?.completedAt || null,
        durationMs: r?.durationMs ?? null,
      };
    });
    rounds.push({
      round,
      decisionEventId: e.event_id,
      decisionPosition: i + 1,
      timestamp: e.timestamp,
      reason: d.decision.reason || '',
      assignments,
    });
  });
  return { rounds, finalize: buildFinalize(state) };
}

function prefixCheckStatus(state, taskId) {
  const completed =
    (state.task_records || []).some((x) => x.task_id === taskId && x.status === 'COMPLETED') ||
    (state.events || []).some((e) => e.event_type === 'TASK_COMPLETED' && taskIdOf(e) === taskId);
  const assigned = (state.events || []).some(
    (e) => e.event_type === 'DECISION' && (e.details?.decision?.assignments || []).some((a) => a.task_id === taskId),
  );
  if (completed) return { status: 'completed', statusLabel: '当前前缀：相同 task_id 已完成' };
  if (assigned) return { status: 'assigned', statusLabel: '当前前缀：已调度，未见完成' };
  return { status: 'not-dispatched', statusLabel: '当前前缀：未按此 task_id 调度；不推断检查已完成' };
}

function checkRow(state, t, kind) {
  const cs = prefixCheckStatus(state, t.task_id);
  const k = String(kind || '').includes('optional') ? 'optional' : 'blocking';
  return {
    taskId: t.task_id,
    role: t.role,
    question: t.question || '',
    reason: t.reason || '',
    kind: k,
    status: cs.status,
    statusLabel: cs.statusLabel,
  };
}

function buildTaskRows(state, role, roleRecords) {
  const events = state.events || [];
  const dispatchQ = {};
  const dispatchPos = {};
  events.forEach((e, i) => {
    if (e.event_type !== 'DECISION') return;
    (e.details?.decision?.assignments || []).forEach((a) => {
      if (dispatchQ[a.task_id] === undefined) dispatchQ[a.task_id] = a.question;
      if (dispatchPos[a.task_id] === undefined) dispatchPos[a.task_id] = i + 1;
    });
  });
  const findingByTask = {};
  (state.findings || []).forEach((f) => { if (f.task_id && findingByTask[f.task_id] === undefined) findingByTask[f.task_id] = f; });
  const order = (r) => r.assignedPos || r.runningPos || r.completedPos || r.failedPos || 9999;
  return roleRecords
    .slice()
    .sort((a, b) => order(a) - order(b))
    .map((r) => {
      const status = r.status || 'NOT_STARTED';
      const meta = TASK_STATUS[status] || TASK_STATUS.NOT_STARTED;
      const f = findingByTask[r.task_id];
      let resultSummary = '尚无结果';
      if (status === 'COMPLETED') resultSummary = f ? `${f.relation} · ${(f.evidence_ids || []).length} 条证据` : '已完成 · 无 finding 提交';
      else if (status === 'FAILED') resultSummary = '失败';
      return {
        taskId: r.task_id,
        attemptId: r.attempt_id || null,
        attempt: r.attempt || 1,
        status,
        statusLabel: meta.label,
        statusTone: meta.tone,
        question: dispatchQ[r.task_id] || '内部协调任务',
        resultSummary,
        relation: f ? f.relation : null,
        evidenceIds: f ? f.evidence_ids || [] : [],
        errorCode: r.errorCode || null,
        jumpPosition: r.assignedPos || r.runningPos || r.completedPos || r.failedPos || dispatchPos[r.task_id] || 1,
      };
    });
}

export function buildRoleStats(state) {
  const events = state.events || [];
  const { dispatches, requests, roles } = replayWorkflow(state);
  const { records } = buildLifecycle(state);
  const rolesMap = state.roles || {};

  const evidenceByRole = {};
  Object.keys(state.evidence_index || {}).forEach((id) => {
    let role = state.provenance?.[id]?.role;
    if (!role) {
      for (const e of events) {
        if (e.event_type === 'TOOL_CALL' && (e.details?.result?.records || []).some((r) => r.evidence_id === id)) { role = e.role; break; }
      }
    }
    if (role) (evidenceByRole[role] = evidenceByRole[role] || []).push(id);
  });

  const lastRole = events.length ? events[events.length - 1].role || null : null;

  return roles.map((role) => {
    let roleRecords = records.filter((r) => r.role === role);
    if (!roleRecords.length) {
      roleRecords = (state.task_records || [])
        .filter((t) => t.role === role)
        .map((t) => ({
          task_id: t.task_id, attempt_id: t.attempt_id, attempt: t.attempt || 1, role: t.role,
          status: t.status, errorCode: t.error_code, durationMs: null,
          assignedPos: null, runningPos: null, completedPos: null, failedPos: null,
        }));
    }
    const cnt = { assigned: 0, running: 0, completed: 0, failed: 0 };
    roleRecords.forEach((r) => {
      if (r.status === 'ASSIGNED') cnt.assigned += 1;
      else if (r.status === 'RUNNING') cnt.running += 1;
      else if (r.status === 'COMPLETED') cnt.completed += 1;
      else if (r.status === 'FAILED') cnt.failed += 1;
    });
    const actual = events.some((e) => e.role === role);
    const dispatched = dispatches.some((t) => t.role === role);
    const statusText = actual ? rolesMap[role] || '有已记录动作' : dispatched ? '已调度 · 尚无执行记录' : '仅审查建议 · 未调度';
    const findings = (state.findings || []).filter((f) => f.role === role);
    return {
      role,
      roleLabel: roleLabel(role),
      present: true,
      statusToken: statusText,
      statusText,
      current: lastRole === role,
      stats: {
        dispatches: dispatches.filter((t) => t.role === role).length,
        tasksAssigned: cnt.assigned,
        tasksRunning: cnt.running,
        tasksCompleted: cnt.completed,
        tasksFailed: cnt.failed,
        toolCalls: events.filter((e) => e.event_type === 'TOOL_CALL' && e.role === role).length,
        evidenceProduced: (evidenceByRole[role] || []).length,
        findings: findings.length,
        durationMs: roleRecords.reduce((n, r) => n + (r.durationMs || 0), 0),
      },
      tasks: buildTaskRows(state, role, roleRecords),
      findings: findings.map((f) => ({ findingId: f.finding_id, taskId: f.task_id, role: f.role, relation: f.relation, evidenceIds: f.evidence_ids || [] })),
      requestedChecks: requests.filter((t) => t.role === role).map((t) => checkRow(state, t, t.kind)),
    };
  });
}

export function buildReviewGates(state, opts = {}) {
  const events = state.events || [];
  const reviewEvents = events.map((e, i) => ({ e, i })).filter(({ e }) => e.event_type === 'REVIEW');
  const hasVerifier = resolveHasVerifier(state, opts);
  const rounds = [];
  let r = 0;
  events.forEach((e, i) => {
    if (e.event_type === 'DECISION' && e.details?.decision?.action === 'INVESTIGATE') {
      r += 1;
      rounds.push({ round: r, position: i + 1, taskIds: (e.details.decision.assignments || []).map((a) => a.task_id) });
    }
  });

  const gates = reviewEvents.map(({ e, i }) => {
    const rv = e.details?.review || {};
    const verdict = rv.verdict === 'sufficient' ? 'sufficient' : 'insufficient';
    const target = (state.hypotheses || []).find((h) => h.hypothesis_id === rv.target_hypothesis_id);
    let loopBack = null;
    if (verdict === 'insufficient' && (rv.requested_checks || []).length) {
      const reqIds = (rv.requested_checks || []).map((t) => t.task_id);
      const next = rounds
        .filter((rr) => rr.position > i + 1 && rr.taskIds.some((id) => reqIds.includes(id)))
        .sort((a, b) => a.position - b.position)[0];
      if (next) loopBack = { toRound: next.round, toPosition: next.position, taskIds: reqIds.filter((id) => next.taskIds.includes(id)) };
    }
    return {
      eventId: e.event_id,
      position: i + 1,
      timestamp: e.timestamp,
      verdict,
      verdictLabel: verdict === 'sufficient' ? '证据充分 Sufficient' : '证据不足 Insufficient',
      verdictTone: verdict === 'sufficient' ? 'success' : 'warning',
      targetHypothesisId: rv.target_hypothesis_id || '',
      targetFailureMode: target?.failure_mode || null,
      targetCulpritService: target?.culprit_service || null,
      rationale: rv.rationale || '',
      hypothesisSha256: e.details?.hypothesis_sha256 || null,
      evidenceSha256: e.details?.evidence_sha256 || null,
      citedEvidenceIds: rv.cited_evidence_ids || [],
      requestedChecks: (rv.requested_checks || []).map((t) => checkRow(state, t, 'blocking')),
      optionalChecks: (rv.optional_checks || []).map((t) => checkRow(state, t, 'optional')),
      contradictions: rv.contradictions || [],
      loopBack,
    };
  });
  return {
    enabled: hasVerifier,
    summary: {
      reviewCount: gates.length,
      insufficient: gates.filter((g) => g.verdict === 'insufficient').length,
      sufficient: gates.filter((g) => g.verdict === 'sufficient').length,
    },
    gates,
    finalize: buildFinalize(state),
  };
}

export function buildEvidenceFlow(state) {
  const events = state.events || [];
  const ids = Object.keys(state.evidence_index || {});
  const report = state.report || null;
  const findings = state.findings || [];
  const hypotheses = state.hypotheses || [];
  const agentsMap = {};

  const evidence = ids.map((id) => {
    const rec = state.evidence_index[id] || {};
    const prov = state.provenance?.[id] || {};
    let firstRole = prov.role;
    if (!firstRole) {
      for (const e of events) {
        if (e.event_type === 'TOOL_CALL' && (e.details?.result?.records || []).some((x) => x.evidence_id === id)) { firstRole = e.role; break; }
      }
    }
    if (firstRole) (agentsMap[firstRole] = agentsMap[firstRole] || []).push(id);
    const sourceType = rec.source_type || '';
    return {
      id,
      sourceType,
      sourceLabel: SOURCE_TYPE_META[sourceType]?.label || sourceType || 'other',
      service: rec.service || '',
      firstRole: firstRole || '',
      firstEventId: prov.event_id || null,
      firstTimestamp: prov.timestamp || null,
      findingIds: findings.filter((f) => (f.evidence_ids || []).includes(id)).map((f) => f.finding_id),
      hypothesisRefs: hypotheses
        .filter((h) => (h.support_ids || []).includes(id) || (h.against_ids || []).includes(id))
        .map((h) => ({
          hypothesisId: h.hypothesis_id,
          failureMode: h.failure_mode,
          relation: (h.against_ids || []).includes(id) ? 'against' : 'supports',
          status: h.status,
        })),
      report: {
        supporting: !!(report && (report.supporting_evidence_ids || []).includes(id)),
        provisional: !!(report && (report.provisional_hypotheses || []).some((h) => (h.support_ids || []).includes(id) || (h.against_ids || []).includes(id))),
        causalChain: report ? (report.causal_chain || []).filter((line) => line.includes(`[${id}]`)) : [],
      },
    };
  });

  const agents = Object.keys(agentsMap).map((role) => ({ role, roleLabel: roleLabel(role), evidenceIds: agentsMap[role] }));
  return {
    present: ids.length > 0,
    agents,
    evidence,
    findings: findings.map((f) => ({ findingId: f.finding_id, taskId: f.task_id, role: f.role, relation: f.relation, evidenceIds: f.evidence_ids || [] })),
    hypotheses: hypotheses.map((h) => ({
      hypothesisId: h.hypothesis_id, failureMode: h.failure_mode, culpritService: h.culprit_service,
      status: h.status, supportIds: h.support_ids || [], againstIds: h.against_ids || [],
    })),
    report: report
      ? {
          present: true,
          status: report.status || '',
          rootCauseFailureMode: report.root_cause?.failure_mode || null,
          supportingEvidenceIds: report.supporting_evidence_ids || [],
          causalChain: report.causal_chain || [],
          rejectedHypothesisIds: (report.rejected_hypotheses || []).map((h) => h.hypothesis_id),
        }
      : { present: false, status: '', rootCauseFailureMode: null, supportingEvidenceIds: [], causalChain: [], rejectedHypothesisIds: [] },
  };
}

const NARRATION = {
  dispatch: { text: '协调者把首轮并行任务同时派给日志与指标调查员。', stage: 'experts' },
  config: { text: '变更调查员读取配置差异，把 DB_POOL_MAX 从 64 降到 2 的关键证据合并进来。', stage: 'evidence' },
  insufficient: { text: '验证者判定证据不足，要求补充变更检查。', stage: 'review' },
  postgres_connection_exhaustion: { text: '数据库连接耗尽假设被正常指标证据否决。', stage: 'hypotheses' },
  backend_resource_saturation: { text: '（该 trace 未记录此竞争假设）', stage: 'hypotheses' },
  gate: { text: '定案门未触发阻断：本 trace 无 FINALIZE_REJECTED，门禁以 REVIEW 判定表示。', stage: 'finalize' },
  'last-review': { text: '验证者确认证据充分（sufficient）。', stage: 'review' },
  report: { text: '最终报告确认根因 backend_pool_config_regression。', stage: 'report' },
};

/** Synthetic chapter 0 — the demo can start before the first recorded event. */
const START_CHAPTER = {
  id: 'start',
  label: '调查开始前',
  narration: '调查开始：只有公开事故摘要，尚无证据。',
  stageId: 'coordinator',
  position: 0,
};

export function buildNarrative(state, bookmarks = []) {
  const len = (state.events || []).length;
  const chapters = [START_CHAPTER, ...(bookmarks || []).map((b) => {
    const map = NARRATION[b.id] || { text: b.label, stage: 'coordinator' };
    const position = b.position ?? null;
    return {
      id: b.id,
      label: b.label,
      narration: map.text,
      position,
      available: position !== null,
      stageId: map.stage,
      reached: position !== null && position <= len,
    };
  })];
  let navIndex = 0;
  const numbered = chapters.map((c) => ({
    ...c,
    available: c.available !== false,
    chapter: c.available === false ? null : (navIndex += 1),
  }));
  let currentIndex = -1;
  let best = -Infinity;
  numbered.forEach((c, i) => {
    if (c.available && c.position <= len && c.position >= best) { best = c.position; currentIndex = i; }
  });
  return { present: (bookmarks || []).length > 0, chapters: numbered, currentIndex };
}

/* ------------------------------------------------------------------ *
 * Render helpers
 * ------------------------------------------------------------------ */

function providerLabel(p) {
  return p === 'real' ? 'REAL' : p === 'mock' ? 'MOCK' : 'PROVIDER UNKNOWN';
}

function toolbarHtml(state, opts = {}) {
  const b = state.budgets || {};
  const chipsList = [];
  if (b.max_rounds != null) chipsList.push(`轮次 ${state.round_index ?? 0} / ${b.max_rounds}`);
  if (b.max_tool_calls != null) chipsList.push(`工具 ${state.tool_calls_used ?? 0} / ${b.max_tool_calls}`);
  if (b.max_llm_calls != null) chipsList.push(`模型请求 ${state.llm_calls_used ?? 0} / ${b.max_llm_calls}`);
  const atLimit = b.max_rounds != null && state.round_index === b.max_rounds;
  return `<div class="orch-toolbar"><span class="orch-badge orch-badge--provider">${esc(providerLabel(opts.provider))}</span><span class="orch-badge">${esc(variantLabel(opts.variant))}</span>${chipsList
    .map((c) => `<span class="orch-badge orch-badge--budget">${esc(c)}</span>`)
    .join('')}${atLimit ? '<span class="orch-badge orch-badge--muted">已达轮次上限</span>' : ''}<span class="orch-legend">只从回放前缀派生 · presentation only</span></div>`;
}

export function stagesHtml(state, opts = {}) {
  const stages = buildStages(state, opts);
  const items = stages
    .map((s) => {
      const num = `<span class="orch-stage__num" aria-hidden="true">${s.index + 1}</span>`;
      if (!s.available) {
        return `<li class="orch-stepper-item"><button type="button" class="orch-stage" data-stage="${s.id}" data-state="skipped" disabled title="该变体无验证者 · 未审查">${num}<span class="orch-stage__label">${esc(s.label)}</span><span class="orch-stage__gloss">${esc(s.gloss)}</span><span class="orch-stage__badge">—</span></button></li>`;
      }
      const cur = s.isCurrent ? ' aria-current="step"' : '';
      const seek = s.firstEventPosition != null ? ` data-seek="${s.firstEventPosition}"` : ' disabled title="当前前缀尚无对应事件"';
      const tag = s.isCurrent ? '<span class="orch-stage__current-tag">当前</span>' : '';
      const badge = s.count > 0 ? `${s.count} <span class="orch-badge__unit">${esc(s.countUnit)}</span>` : '0';
      return `<li class="orch-stepper-item"><button type="button" class="orch-stage" data-stage="${s.id}" data-state="${s.state}"${cur}${seek}>${num}<span class="orch-stage__label">${esc(s.label)}</span><span class="orch-stage__gloss">${esc(s.gloss)}</span><span class="orch-stage__badge">${badge}</span>${tag}</button></li>`;
    })
    .join('');
  return `<nav class="orch-stepper" aria-label="编排阶段"><ol class="orch-stepper-track">${items}</ol></nav>`;
}

export function narrativeHtml(state, bookmarks = [], opts = {}) {
  const model = buildNarrative(state, bookmarks);
  if (!model.present) return '';
  const ch = model.chapters;
  const cur = model.currentIndex;
  const avail = ch.map((c, i) => ({ c, i })).filter((o) => o.c.available);
  const posInAvail = avail.findIndex((o) => o.i === cur);
  const prev = posInAvail > 0 ? avail[posInAvail - 1] : null;
  const next = posInAvail < 0 ? avail[0] || null : posInAvail < avail.length - 1 ? avail[posInAvail + 1] : null;
  const current = cur >= 0 ? ch[cur] : null;
  // One deterministic narration line at a time, prefixed with its chapter number.
  const line = current
    ? `<span class="orch-chapter-label">第 ${current.chapter} 章 · ${esc(current.label)}</span> ${esc(current.narration)}`
    : esc('从 0 开始播放，按「下一关键节点」开始演示。');
  const stageId = current ? current.stageId : 'coordinator';
  // Counter counts only NAVIGABLE (available) chapters, not unavailable bookmarks.
  const posLabel = `${posInAvail >= 0 ? posInAvail + 1 : 0} / ${avail.length}`;
  const chapterItems = ch
    .map((c, i) => {
      const currentTag = `aria-current="${i === cur ? 'true' : 'false'}"`;
      if (!c.available) {
        return `<li class="orch-chapter orch-chapter--unavailable" data-chapter="${esc(c.id)}" data-stage="${esc(c.stageId)}" aria-current="false"><button type="button" class="btn btn-sm" disabled title="Trace 未记录对应事件">${esc(c.label)} · 未记录</button></li>`;
      }
      return `<li class="orch-chapter" data-chapter="${esc(c.id)}" data-position="${c.position}" data-stage="${esc(c.stageId)}" ${currentTag}><button type="button" class="btn btn-sm" data-seek="${c.position}">${esc(c.label)}</button></li>`;
    })
    .join('');
  return `<section class="orch-narrative" aria-label="演示叙事" data-active-index="${cur}" data-active-stage="${esc(stageId)}">
    <p class="orch-narrative__line" aria-live="polite">${line}</p>
    <div class="orch-narrative__controls">
      <button class="btn btn-sm orch-narrative__prev" type="button" data-narrative-prev${prev ? '' : ' disabled'}>上一关键节点</button>
      <span class="orch-narrative__pos">${esc(posLabel)}</span>
      <button class="btn btn-sm orch-narrative__next" type="button" data-narrative-next${next ? '' : ' disabled'}>下一关键节点</button>
    </div>
    <ol class="orch-chapters">${chapterItems}</ol>
  </section>`;
}

export function swimlaneHtml(state, opts = {}) {
  const { rounds } = buildRounds(state);
  const events = state.events || [];
  const coordCompleted = events.filter((e) => e.event_type === 'TASK_COMPLETED' && (taskIdOf(e) || '').startsWith('coordinate-')).length;
  if (!rounds.length) {
    return `<section class="orch-swimlane" aria-label="按轮次调度泳道"><p class="orch-empty">当前前缀尚无调度 / no dispatch yet</p></section>`;
  }
  const findingByTask = {};
  (state.findings || []).forEach((f) => { if (f.task_id && findingByTask[f.task_id] === undefined) findingByTask[f.task_id] = f; });

  const roundsHtml = rounds
    .map((r) => {
      const parallel = r.assignments.length > 1;
      const lanes = r.assignments
        .map((a) => {
          const meta = TASK_STATUS[a.status] || TASK_STATUS.NOT_STARTED;
          const f = findingByTask[a.taskId];
          return `<div class="orch-lane"><article class="orch-task-card" data-task-id="${esc(a.taskId)}" data-task-role="${esc(a.role)}">
          <div class="orch-task-card__head"><span class="orch-task-card__role">${esc(roleZh(a.role))} <span class="orch-role-en">${esc(roleEn(a.role))}</span></span>${statusBadge(a.statusLabel, a.statusTone, meta.icon)}</div>
          <code class="orch-task-card__id">${esc(a.taskId)}</code>
          <p class="orch-task-card__q">${esc(a.question)}</p>
          <div class="orch-task-card__meta"><time>${esc(a.timestamp || '')}</time><button class="btn btn-sm orch-task-card__jump" data-seek="${a.jumpPosition}">跳到事件</button></div>
          ${f ? `<div class="cite-wrap">${chips(f.evidence_ids, state.evidence_index)}</div>` : ''}
        </article></div>`;
        })
        .join('');
      const mergeChips = r.assignments.map((a) => findingByTask[a.taskId]).filter(Boolean);
      const mergeSummary = mergeChips
        .map((f) => `${relationBadge(f.relation)} <span class="orch-badge">${(f.evidence_ids || []).length} 证据</span>`)
        .join('');
      return `<article class="orch-round" data-round="${r.round}">
        <header class="orch-round__head"><span class="orch-round__index">第 ${r.round} 轮</span>${parallel ? '<span class="orch-round__parallel">并行</span>' : ''}<span class="orch-round__reason">${esc(r.reason)}</span><button class="btn btn-sm orch-jump" data-seek="${r.decisionPosition}">跳到决策 · ${esc(r.decisionEventId)}</button></header>
        <div class="orch-lanes"><div class="orch-lane orch-lane--coord"><span class="orch-node orch-node--coordinator">协调者 →</span></div>${lanes}</div>
        <div class="orch-merge-node"><span class="orch-node orch-node--merge">合并证据 → Public Evidence</span>${mergeSummary}</div>
      </article>`;
    })
    .join('');

  const gates = buildReviewGates(state, opts);
  const gateNode = gates.enabled
    ? `<div class="orch-gate-node"><span class="orch-node orch-node--expert">验证审查 Verifier</span>${gates.gates
        .map((g) => statusBadge(g.verdictLabel, g.verdictTone))
        .join('')}${gates.gates
        .filter((g) => g.loopBack)
        .map((g) => `<button type="button" class="orch-edge--loopback" data-seek="${g.loopBack.toPosition}">验证审查 → 第 ${g.loopBack.toRound} 轮重新调度 (${esc(g.loopBack.taskIds.join(', '))})</button>`)
        .join('')}</div>`
    : '';
  const footnote = coordCompleted ? `<p class="orch-footnote text-muted">协调者内部步骤 ×${coordCompleted}（计划/综合）</p>` : '';
  return `<section class="orch-swimlane" aria-label="按轮次调度泳道">${roundsHtml}${gateNode}${footnote}</section>`;
}

function roleDetailHtml(state, model, role) {
  if (!model) return '';
  const tasks = model.tasks || [];
  const tasksHtml = tasks.length
    ? `<ol class="orch-task-rows">${tasks
        .map((t) => {
          const meta = TASK_STATUS[t.status] || TASK_STATUS.NOT_STARTED;
          return `<li class="orch-task-row" data-task-id="${esc(t.taskId)}">
        <div class="orch-task-row__head"><code class="orch-task-row__id">${esc(t.taskId)}</code>${statusBadge(t.statusLabel, t.statusTone, meta.icon)}${t.attempt > 1 ? `<span class="text-muted">· 第 ${t.attempt} 次</span>` : ''}</div>
        <p class="orch-task-row__q">${esc(t.question)}</p>
        <p class="orch-task-row__result">${esc(t.resultSummary)}</p>
        ${t.evidenceIds.length ? `<div class="orch-task-row__evidence cite-wrap">${chips(t.evidenceIds, state.evidence_index)}</div>` : ''}
        <p class="orch-task-row__error"${t.errorCode ? '' : ' hidden'}>error_code: ${esc(t.errorCode || '—')}</p>
        <button class="btn btn-sm" data-seek="${t.jumpPosition}">跳到事件</button>
      </li>`;
        })
        .join('')}</ol>`
    : `<p>没有执行记录。审查建议不等于已执行工具查询。</p>`;
  const findingsHtml =
    model.findings && model.findings.length
      ? `<ul class="orch-finding-rows">${model.findings
          .map((f) => `<li class="orch-finding-row">${relationBadge(f.relation)} <code>${esc(f.findingId)}</code> · <code>${esc(f.taskId)}</code><div class="cite-wrap">${chips(f.evidenceIds, state.evidence_index)}</div></li>`)
          .join('')}</ul>`
      : '';
  const checksHtml =
    model.requestedChecks && model.requestedChecks.length
      ? `<section class="orch-checks"><h4>验证审查对该角色的检查建议（含未执行）</h4><ul>${model.requestedChecks
          .map((c) => `<li class="orch-check${c.kind === 'optional' ? ' orch-check--optional' : ''}" data-status="${c.status}"><span class="orch-check__kind">${c.kind === 'optional' ? '可选检查 Optional' : '阻断检查 Blocking'}</span> <strong>${esc(roleZh(c.role))} · ${esc(c.taskId)}</strong><p>${esc(c.question)}</p><span class="orch-check__status">${esc(c.statusLabel)}</span></li>`)
          .join('')}</ul></section>`
      : '';
  return `<div class="replay-role-detail orch-role-detail" data-role-detail="${esc(role)}"><h3 class="type-title-3">${esc(roleZh(role))} · 真实任务与结果</h3>${tasksHtml}${findingsHtml}${checksHtml}</div>`;
}

export function roleStatsHtml(state, selectedRole = '') {
  const roles = buildRoleStats(state);
  if (!roles.length) {
    return `<section class="orch-role-grid" aria-label="角色统计"><p class="orch-empty">当前前缀尚无角色记录</p></section>`;
  }
  const cards = roles
    .map((r) => {
      const pressed = selectedRole === r.role;
      return `<article class="orch-role-card" data-role-card="${esc(r.role)}">
        <button class="replay-role orch-role-toggle" data-role="${esc(r.role)}" aria-pressed="${pressed}" data-current="${r.current}"><strong>${esc(roleZh(r.role))} <span class="orch-role-en">${esc(roleEn(r.role))}</span></strong><span class="orch-role-status">${esc(r.statusText)}</span></button>
        <dl class="orch-role-stats">
          <div class="orch-stat"><dt>调度</dt><dd class="orch-stat__value">${r.stats.dispatches}</dd></div>
          <div class="orch-stat"><dt>完成 / 失败</dt><dd class="orch-stat__value">${r.stats.tasksCompleted} / ${r.stats.tasksFailed}</dd></div>
          <div class="orch-stat"><dt>工具调用</dt><dd class="orch-stat__value">${r.stats.toolCalls}</dd></div>
          <div class="orch-stat"><dt>产出证据</dt><dd class="orch-stat__value">${r.stats.evidenceProduced}</dd></div>
          <div class="orch-stat"><dt>发现</dt><dd class="orch-stat__value">${r.stats.findings}</dd></div>
          <div class="orch-stat"><dt>耗时</dt><dd class="orch-stat__value">${esc(formatDuration(r.stats.durationMs))}</dd></div>
        </dl>
      </article>`;
    })
    .join('');
  const detail = selectedRole ? roleDetailHtml(state, roles.find((r) => r.role === selectedRole), selectedRole) : '';
  return `<section class="orch-role-grid" aria-label="角色统计">${cards}</section>${detail}`;
}

function checkLi(c) {
  return `<li class="orch-check${c.kind === 'optional' ? ' orch-check--optional' : ''}" data-status="${c.status}"><span class="orch-check__kind">${c.kind === 'optional' ? '可选检查 Optional' : '阻断检查 Blocking'}</span> <strong>${esc(roleZh(c.role))} · ${esc(c.taskId)}</strong><p>${esc(c.question)}</p><span class="orch-check__status">${esc(c.statusLabel)}</span></li>`;
}

export function reviewGateHtml(state, opts = {}) {
  const model = buildReviewGates(state, opts);
  if (!model.enabled) {
    // Genuinely verifier-less variant (e.g. Single/Fixed or a no-verifier Dynamic).
    return `<section class="orch-gates orch-gates--skipped" aria-label="验证审查门"><p class="orch-empty">该变体无验证者 · 未审查</p></section>`;
  }
  if (!model.gates.length) {
    // Verifier-capable variant whose replay prefix has not reached the first REVIEW yet:
    // this is PENDING, never "该变体无验证者".
    const f0 = model.finalize;
    const finNote0 = !f0.present ? '尚未定案' : `${f0.diagnosisAccepted ? 'DIAGNOSIS_ACCEPTED' : 'FINALIZE'} · ${f0.statusText}`;
    return `<section class="orch-gates" aria-label="验证审查门"><header class="orch-section-title">验证审查门 Verifier Review Gate <span class="orch-badge">0 审查</span></header><p class="orch-empty">当前前缀尚无验证审查</p><article class="orch-finalize" data-blocked="${f0.blocked}">${statusBadge(f0.statusText, f0.statusTone, f0.blocked ? 'alert' : 'shield')}<p class="text-muted">${esc(finNote0)}</p></article></section>`;
  }
  const s = model.summary;
  const gatesHtml = model.gates
    .map((g) => {
      const blocking = g.requestedChecks.map(checkLi).join('');
      const optional = g.optionalChecks.length
        ? g.optionalChecks.map(checkLi).join('')
        : '<li class="orch-check orch-check--optional">可选检查 Optional → 未记录可选检查</li>';
      const contradictions = g.contradictions.length
        ? `<ul class="orch-contradictions">${g.contradictions.map((c) => `<li class="orch-contradiction">${esc(c)}</li>`).join('')}</ul>`
        : '<p class="text-muted">无矛盾记录</p>';
      const loop = g.loopBack
        ? `<button type="button" class="orch-edge--loopback" data-seek="${g.loopBack.toPosition}">验证审查 → 第 ${g.loopBack.toRound} 轮重新调度 (${esc(g.loopBack.taskIds.join(', '))})</button>`
        : '';
      return `<article class="orch-gate" data-verdict="${g.verdict}" data-position="${g.position}">
        <header class="orch-gate__head">${statusBadge(g.verdictLabel, g.verdictTone)}<button class="btn btn-sm" data-seek="${g.position}">${esc(g.eventId)} · REVIEW</button></header>
        <p class="orch-gate__target">目标假设：<span class="mono">${esc(g.targetFailureMode || g.targetHypothesisId || 'not recorded')}</span>${g.targetHypothesisId ? ` <span class="text-muted">(${esc(String(g.targetHypothesisId).slice(0, 13))}…)</span>` : ''}</p>
        <p class="orch-gate__rationale">${esc(g.rationale)}</p>
        <div class="cite-wrap">${chips(g.citedEvidenceIds, state.evidence_index)}</div>
        <ul class="orch-checks">${blocking}${optional}</ul>
        ${contradictions}
        ${loop}
        <details><summary>审查理由与版本哈希</summary><dl><dt>Hypothesis SHA256</dt><dd class="mono">${esc(g.hypothesisSha256 || 'not recorded')}</dd><dt>Evidence SHA256</dt><dd class="mono">${esc(g.evidenceSha256 || 'not recorded')}</dd></dl></details>
      </article>`;
    })
    .join('');
  const f = model.finalize;
  const rootCause = f.selectedHypothesisId
    ? (state.hypotheses || []).find((h) => h.hypothesis_id === f.selectedHypothesisId)?.failure_mode || f.selectedHypothesisId
    : '—';
  const finNote = !f.present
    ? '尚未定案'
    : `${f.diagnosisAccepted ? 'DIAGNOSIS_ACCEPTED' : 'FINALIZE'}${f.decisionEventId ? ` · ${esc(f.decisionEventId)}` : ''} · 根因 ${esc(rootCause)}`;
  const finHtml = `<article class="orch-finalize" data-blocked="${f.blocked}">${statusBadge(f.statusText, f.statusTone, f.blocked ? 'alert' : 'shield')}<p class="text-muted">${finNote}</p></article>`;
  return `<section class="orch-gates" aria-label="验证审查门"><header class="orch-section-title">验证审查门 Verifier Review Gate <span class="orch-badge">${s.reviewCount} 审查 · ${s.insufficient} 不足 · ${s.sufficient} 充分</span></header>${gatesHtml}${finHtml}</section>`;
}

export function evidenceFlowHtml(state) {
  const model = buildEvidenceFlow(state);
  if (!model.present) {
    return `<section class="orch-flow" aria-label="证据流向"><p class="orch-empty">当前前缀尚无证据</p></section>`;
  }
  const groups = {};
  model.evidence.forEach((ev) => { (groups[ev.sourceLabel] = groups[ev.sourceLabel] || []).push(ev); });
  const agentsHtml =
    model.agents.map((a) => `<div class="orch-flow__item"><span>${esc(a.roleLabel)}</span><span class="orch-badge">${a.evidenceIds.length} 证据</span></div>`).join('') ||
    '<p class="orch-empty">—</p>';
  const evidenceHtml = Object.keys(groups)
    .map((label) => `<div class="orch-flow__group"><h5>${esc(label)}</h5>${groups[label]
      .map((ev) => `<button type="button" class="evidence-chip" data-evidence-id="${esc(ev.id)}">${esc(shortEvidenceId(ev.id))}</button>`)
      .join('')}</div>`)
    .join('');
  const findingsHtml =
    model.findings.map((f) => `<div class="orch-flow__item">${relationBadge(f.relation)} <code>${esc(f.taskId)}</code><div class="cite-wrap">${chips(f.evidenceIds, state.evidence_index)}</div></div>`).join('') ||
    '<p class="orch-empty">当前前缀尚无发现</p>';
  const hypothesesHtml = model.hypotheses
    .map((h) => `<div class="orch-flow__item"><span class="orch-badge">${esc(h.failureMode)}</span>${statusBadge(h.status, h.status === 'REJECTED' ? 'danger' : h.status === 'SUPPORTED' ? 'success' : 'info')}</div>`)
    .join('');
  const reportHtml = model.report.present
    ? `<p class="orch-mono">${esc(model.report.rootCauseFailureMode || '—')}</p><div class="cite-wrap">${chips(model.report.supportingEvidenceIds, state.evidence_index)}</div>${
        model.report.causalChain.length
          ? `<details><summary>因果链 · causal_chain</summary><ol>${model.report.causalChain.map((l) => `<li>${esc(l)}</li>`).join('')}</ol></details>`
          : ''
      }`
    : '<p class="orch-empty">当前前缀尚未生成报告</p>';
  return `<section class="orch-flow" aria-label="证据流向"><header class="orch-section-title">证据流向 Evidence Flow <span class="orch-badge">${model.evidence.length} 证据 · ${model.findings.length} 发现 · ${model.hypotheses.length} 假设</span></header><div class="orch-flow__grid">
    <div class="orch-flow__col orch-flow__col--agents"><h4>来源 Agent</h4>${agentsHtml}</div>
    <div class="orch-flow__col orch-flow__col--evidence"><h4>证据 Evidence</h4>${evidenceHtml}</div>
    <div class="orch-flow__col orch-flow__col--findings"><h4>发现 / 假设 Findings · Hypotheses</h4>${findingsHtml}${hypothesesHtml}</div>
    <div class="orch-flow__col orch-flow__col--report"><h4>报告引用 Report</h4>${reportHtml}</div>
  </div></section>`;
}

export function orchestrationHtml(state, selectedRole = '', bookmarks = [], opts = {}) {
  return `<div class="orch-panel">
    ${toolbarHtml(state, opts)}
    ${stagesHtml(state, opts)}
    ${narrativeHtml(state, bookmarks, opts)}
    ${swimlaneHtml(state, opts)}
    ${roleStatsHtml(state, selectedRole)}
    ${reviewGateHtml(state, opts)}
    ${evidenceFlowHtml(state)}
  </div>`;
}
