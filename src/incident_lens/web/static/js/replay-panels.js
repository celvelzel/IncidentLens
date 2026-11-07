import { escapeHtml as esc, variantLabel } from './api.js';
import { badge, evidenceChips } from './components.js';
import { replayWorkflow, replayReliability } from './replay.js';
import { orchestrationHtml, buildNarrative } from './orchestration.js';

const json = value => `<pre class="json-block">${esc(JSON.stringify(value, null, 2))}</pre>`;
const empty = '<p class="text-muted">当前前缀尚无记录 / not recorded</p>';
export const jumpButton = (position, label, extra = '') => `<button class="btn btn-sm" data-seek="${position}" ${extra}>${esc(label)}</button>`;

/**
 * Replay metadata block. Backward compatible: `metadataHtml(data)` emits the full
 * heading + provenance snapshot exactly as before. `opts` lets the redesigned
 * mount split the heading (under the controls) from the sunk metadata snapshot.
 *   opts.snapshot === false → heading block only (badges/title/demo toggle/intro/drift)
 *   opts.heading  === false → metadata `<details>` snapshot only
 */
export function metadataHtml(data, opts = {}) {
  const { heading = true, snapshot = true } = opts;
  const t = data.trace, s = t.state || {}, m = data.replay_metadata || {}, v = m.verification || {}, p = m.protocol || {};
  const label = t.provider === 'real' ? 'REAL LLM' : t.provider === 'mock' ? 'MOCK' : 'PROVIDER UNKNOWN';
  const models = [...new Set((s.events || []).map(e => e.details?.model_id).filter(Boolean))];
  const headHtml = heading ? `<div class="replay-heading"><div><div class="chip-row replay-badges">${badge(label, t.provider === 'real' ? 'info' : t.provider === 'mock' ? 'accent' : 'warning')}${badge('RECORDED REPLAY', 'neutral')}</div><h2 class="section-title type-title-2">Investigation Replay</h2></div><label class="chip chip-toggle"><input type="checkbox" id="replay-demo"> 演示模式</label></div>
    <p class="text-secondary">按保存顺序重建共享状态。选择章节会跳到对应事件；不会重新调用模型或工具。</p>
    ${v.source_unchanged === false ? '<p class="replay-provenance" data-drift="true"><strong>SOURCE DRIFT · 已保存来源检查发现变化；本录制不代表冻结正式实验。</strong></p>' : ''}` : '';
  const snapshotHtml = snapshot ? `<details id="replay-metadata"><summary>运行来源与限制 · 独立最终产物元数据快照</summary>
      <p class="text-muted">以下是整个已录制运行的元数据，不表示当前播放位置已知的调查结论。来源一致性为内部校验，非签名认证。</p>
      <dl class="replay-metadata-grid">
      ${Object.entries({Incident:s.incident_id,Variant:variantLabel(t.variant),Model:t.model_id || models.join(', ') || 'not recorded',
        'Recorded events':s.events?.length ?? 0,'Recorded requests (including failures)':(s.events || []).filter(e => ['LLM_CALL','MODEL_FAILURE'].includes(e.event_type)).reduce((n,e)=>n+(e.details?.llm_calls ?? 1),0),
        'Protocol ID':p.protocol_id || 'not recorded','Protocol valid (saved verification)':v.protocol_valid ?? 'not recorded',
        'Source commit':m.source_commit || 'not recorded','Dataset revision':m.dataset_revision || 'not recorded',
        'Elapsed / tokens / cost':`${t.elapsed_ms ?? 'unknown'} ms / ${v.total_tokens ?? 'unknown'} tokens / ${v.cost_usd ?? 'unknown'} USD`,
        'Run scope':m.scope || 'not recorded'}).map(([k,val])=>`<div><dt>${esc(k)}</dt><dd>${esc(String(val))}</dd></div>`).join('')}
      </dl><h3>有效预算（Trace） / Protocol（已保存）</h3>${json({budget:s.budgets || {},protocol:p})}
      <div class="replay-provenance" data-drift="${v.source_unchanged === false ? 'true' : 'unknown'}"><strong>${v.source_unchanged === false ? 'SOURCE DRIFT · 非冻结正式实验' : v.source_unchanged === true ? 'Saved source check: unchanged' : 'Source drift: not recorded'}</strong>
      <p>${esc(v.source_unchanged === false ? '运行期间记录的源码指纹发生变化；可展示真实开发调查过程，不能视为完全冻结的正式实验。' : '仅显示产物记录的来源检查，不推断当前源码与录制时一致。')}</p>${v.source_drift?.length ? json(v.source_drift) : ''}</div>
      ${m.warnings?.length ? json(m.warnings) : ''}
    </details>` : '';
  return headHtml + snapshotHtml;
}

/**
 * #replay-workflow inner HTML. Legacy call `workflowHtml(state, selectedRole)` stays
 * valid — bookmarks/opts are optional. Rendering lives in orchestration.js.
 */
export function workflowHtml(state, selectedRole = '', bookmarks = [], opts = {}) {
  return orchestrationHtml(state, selectedRole, bookmarks, opts);
}

/**
 * DOM wiring for the orchestration panel. Role toggling and generic [data-seek]
 * jumps are bound by views.js `draw()`; this adds narrative prev/next and the
 * demo-mode auto highlight/scroll.
 */
export function bindWorkflowInteractions(panelEl, ctx = {}) {
  if (!panelEl) return;
  const seek = typeof ctx.seek === 'function' ? ctx.seek : () => {};
  const state = typeof ctx.getState === 'function' ? ctx.getState() : ctx.state || { events: [] };
  const bookmarks = ctx.bookmarks || [];
  let model = null;
  try { model = buildNarrative(state, bookmarks); } catch { model = null; }
  if (model) {
    const ch = model.chapters;
    const cur = typeof ctx.narrativeIndex === 'number' ? ctx.narrativeIndex : model.currentIndex;
    const avail = ch.map((c, i) => ({ c, i })).filter(o => o.c.available);
    const posInAvail = avail.findIndex(o => o.i === cur);
    const prev = posInAvail > 0 ? avail[posInAvail - 1] : null;
    const next = posInAvail < 0 ? avail[0] || null : posInAvail < avail.length - 1 ? avail[posInAvail + 1] : null;
    const prevBtn = panelEl.querySelector('[data-narrative-prev]');
    const nextBtn = panelEl.querySelector('[data-narrative-next]');
    if (prevBtn) { prevBtn.disabled = !prev; prevBtn.onclick = () => { if (prev) seek(prev.c.position); }; }
    if (nextBtn) { nextBtn.disabled = !next; nextBtn.onclick = () => { if (next) seek(next.c.position); }; }
  }
  const demo = typeof ctx.demo === 'function' ? ctx.demo() : !!ctx.demo;
  const nar = panelEl.querySelector('.orch-narrative');
  if (demo && nar && nar.dataset.activeStage) {
    const stageEl = panelEl.querySelector(`.orch-stage[data-stage="${nar.dataset.activeStage}"]`);
    if (stageEl) {
      stageEl.classList.add('is-highlighted');
      const reduce = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      try { stageEl.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' }); } catch { /* ignore */ }
    }
  }
}

export function historyHtml(state) {
  return state.hypotheses.map(h=>`<article class="replay-hypothesis"><h3>${esc(h.failure_mode)} ${badge(h.status,h.status === 'REJECTED' ? 'danger' : h.status === 'SUPPORTED' ? 'success' : 'neutral')}</h3>
    ${state.hypothesis_history.filter(x=>x.hypothesis_id === h.hypothesis_id).map(x=>`<details><summary>${esc(x.timestamp || '')} · ${jumpButton(state.events.findIndex(e=>e.event_id === x.event_id)+1,`${x.previous_status || '首次提出'} → ${x.status}`)}</summary>
      <p>${esc(x.reason || '此事件没有独立理由字段；参见原始结构化事件。')}</p><p>支持</p>${evidenceChips(x.support_ids,state.evidence_index)}<p>反对</p>${evidenceChips(x.against_ids,state.evidence_index)}<p>未决问题</p>${json(x.open_questions || [])}</details>`).join('')}
    <details><summary>相关 Coordinator / Verifier 事件</summary>${state.events.map((e,i)=>({e,i})).filter(({e})=>e.details?.review?.target_hypothesis_id === h.hypothesis_id || e.details?.decision?.selected_hypothesis_id === h.hypothesis_id).map(({e,i})=>jumpButton(i+1,`${e.event_id} · ${e.event_type}`)).join('') || empty}</details></article>`).join('') || empty;
}

/* ---------- legacy review panel: structured finalize / diagnosis cards ---------- */
// The panel below `#replay-workflow` is the legacy timeline. It must read as
// structured review-gate cards too (same design language as orchestration.js:
// badges + kv rows + evidence chips), never as a raw `<pre>` JSON dump. Only an
// unrecognisable event shape falls back to collapsed raw JSON.
const shortId = (value, keep = 12) => {
  const s = String(value ?? '');
  return s ? `${s.slice(0, keep)}…` : '';
};
// `TraceEvent.details` is `dict[str, Any]` on the wire (schemas/contracts.py), so a
// "list" field may legally arrive as a scalar (string/number/object) or be absent.
// Normalise BEFORE `.map`: array → as-is; non-empty string/scalar/object → [v];
// null/undefined/'' → []. A schema-valid but scalar-typed field must never throw
// and blank the whole panel (it previously aborted draw() at the `.map` below).
const asList = (v) => (Array.isArray(v) ? v : v == null || v === '' ? [] : [v]);
const itemText = (x) => {
  if (typeof x === 'string') return x;
  if (x && typeof x === 'object') {
    const keys = ['claim', 'message', 'question', 'reason', 'summary', 'code', 'label'];
    const hit = keys.find(k => typeof x[k] === 'string');
    if (hit) return x[hit];
    const pairs = Object.entries(x).filter(([, v]) => typeof v === 'string' || typeof v === 'number');
    if (pairs.length) return pairs.map(([k, v]) => `${k}: ${v}`).join(' · ');
  }
  return String(x ?? '');
};
// Evidence chips need renderable scalar ids. A details field typed `Any` may carry
// an object id (`{ evidence_id: … }`) or an unusable entry (`{}`, `null`, `''`).
// Flatten an id object that carries a text field to its text; DROP anything with no
// renderable text, so a chip is never labelled `[object Object]` and never blank.
const ID_TEXT_KEYS = ['evidence_id', 'evidenceId', 'id', 'claim', 'message', 'question',
  'reason', 'summary', 'code', 'label', 'name'];
const asIdList = (v) => asList(v)
  .map((x) => {
    if (typeof x === 'string') return x.trim();
    if (typeof x === 'number' || typeof x === 'boolean') return String(x);
    if (x && typeof x === 'object') {
      const hit = ID_TEXT_KEYS.find((k) => typeof x[k] === 'string' && x[k].trim());
      if (hit) return x[hit].trim();
    }
    return null; // no renderable text → drop the entry rather than emit a blank chip
  })
  .filter(Boolean);
const listHtml = (items, emptyText = '无记录') => {
  const list = asList(items);
  return list.length
    ? `<ul class="replay-review__list">${list.map(x => `<li>${esc(itemText(x))}</li>`).join('')}</ul>`
    : `<p class="text-muted">${esc(emptyText)}</p>`;
};
const rawDetails = (e) => {
  let body;
  try {
    body = JSON.stringify(e.details ?? {}, null, 2);
  } catch {
    body = '[unserialisable event details]';
  }
  return `<details class="replay-review__raw"><summary>原始结构化事件</summary><pre class="json-block">${esc(body)}</pre></details>`;
};
const reviewHead = (e, i, chipHtml) => `<header class="replay-review__head"><div class="chip-row replay-review__chips">${jumpButton(i + 1, `${e.event_id} · ${e.event_type}`)}${chipHtml}</div><p class="replay-review__sub text-muted">${esc(e.event_type)}${e.role ? ` · ${esc(e.role)}` : ''}${e.timestamp ? ` · ${esc(e.timestamp)}` : ''}</p></header>`;

/** DIAGNOSIS_ACCEPTED → 定案门 pass card (culprit service, failure mode headline, evidence chips). */
function diagnosisCard(e, i, state) {
  const d = e.details || {};
  const rc = d.root_cause;
  if (!rc || typeof rc !== 'object') {
    return `<div class="replay-review" data-outcome="unknown">${reviewHead(e, i, badge('未识别事件结构', 'neutral'))}<p class="text-muted">该事件没有可识别的定案字段；展开查看原始结构。</p>${rawDetails(e)}</div>`;
  }
  const evidenceIndex = state.evidence_index || {};
  const support = asIdList(rc.support_ids);
  const against = asIdList(rc.against_ids);
  const predicted = asList(rc.predicted_observations);
  const openQuestions = asList(rc.open_questions);
  const supporting = asIdList(d.supporting_evidence_ids);
  const degraded = asList(d.degraded_call_ids);
  const statusTone = rc.status === 'SUPPORTED' ? 'success' : rc.status === 'REJECTED' ? 'danger' : 'neutral';
  return `<div class="replay-review" data-outcome="accepted">${reviewHead(e, i, badge('诊断已通过', 'success'))}
    <p class="replay-review__title">${esc(rc.failure_mode || 'not recorded')}</p>
    <dl class="kv-list replay-review__kv">
      <div class="kv-row"><dt>根因服务 culprit_service</dt><dd class="mono">${esc(rc.culprit_service || 'not recorded')}</dd></div>
      <div class="kv-row"><dt>假设状态 status</dt><dd>${rc.status ? badge(rc.status, statusTone) : '<span class="text-muted">not recorded</span>'}</dd></div>
      <div class="kv-row"><dt>Hypothesis ID</dt><dd><span class="mono replay-review__hash" title="${esc(rc.hypothesis_id || '')}">${esc(shortId(rc.hypothesis_id))}</span></dd></div>
    </dl>
    <section class="replay-review__section"><p class="replay-review__label">支持证据 · support_ids <span class="text-muted">${support.length}</span></p><div class="cite-wrap">${evidenceChips(support, evidenceIndex)}</div></section>
    <section class="replay-review__section"><p class="replay-review__label">反对证据 · against_ids <span class="text-muted">${against.length}</span></p><div class="cite-wrap">${evidenceChips(against, evidenceIndex)}</div></section>
    <section class="replay-review__section"><p class="replay-review__label">预测观察 · predicted_observations</p>${listHtml(predicted, '无预测观察记录')}</section>
    <section class="replay-review__section"><p class="replay-review__label">未决问题 · open_questions</p>${listHtml(openQuestions, '无未决问题记录')}</section>
    <section class="replay-review__section"><p class="replay-review__label">报告支持证据 · supporting_evidence_ids <span class="text-muted">${supporting.length}</span></p><div class="cite-wrap">${evidenceChips(supporting, evidenceIndex)}</div></section>
    <p class="replay-review__note text-muted">降级调用 degraded_call_ids：${degraded.length}${degraded.length ? ` · ${degraded.map(x => esc(String(x))).join(', ')}` : ' · 无'}</p>
  </div>`;
}

/** FINALIZE_ACCEPTED / FINALIZE_REJECTED / other FINALIZE* → structured summary card. */
function finalizeCard(e, i) {
  const d = e.details || {};
  const dec = d.decision || {};
  const blocked = e.event_type === 'FINALIZE_REJECTED' || /REJECTED/.test(e.event_type) || d.blocked === true;
  const accepted = !blocked && (/ACCEPTED/.test(e.event_type) || e.event_type === 'FINALIZE');
  const action = dec.action || d.action || null;
  const reason = dec.reason || d.reason || dec.stop_reason || d.stop_reason || null;
  // Blocking-check sources may be a list, a single scalar string, or a single
  // object (details is dict[str, Any]); treat a scalar as one check rather than
  // claiming "none". Prefer the first source that actually HAS content, so
  // `errors: []` never masks a populated `blocking_checks`.
  const blockingSources = ['errors', 'blocking_checks', 'checks', 'failed_checks']
    .map((key) => d[key])
    .filter((value) => value != null);
  const checks = blockingSources.map(asList).find((list) => list.length > 0) || [];
  const hadBlockingSource = blockingSources.length > 0;
  const selected = d.selected_hypothesis_id || dec.selected_hypothesis_id || null;
  const hypHash = d.hypothesis_sha256 || null;
  const evHash = d.evidence_sha256 || null;
  const assessments = d.candidate_assessments && typeof d.candidate_assessments === 'object'
    ? Object.keys(d.candidate_assessments).length : 0;
  const recognizable = blocked || accepted || action || reason || checks.length || selected || hypHash || evHash;
  if (!recognizable) {
    return `<div class="replay-review" data-outcome="unknown">${reviewHead(e, i, badge('未识别事件结构', 'neutral'))}<p class="text-muted">该事件没有可识别的定案字段；展开查看原始结构。</p>${rawDetails(e)}</div>`;
  }
  const verdictBadge = blocked ? badge('定案被阻断', 'danger') : accepted ? badge('定案通过', 'success') : badge(e.event_type, 'neutral');
  const headline = action ? `动作 · ${action}` : e.event_type;
  return `<div class="replay-review" data-outcome="${blocked ? 'blocked' : accepted ? 'accepted' : 'recorded'}">${reviewHead(e, i, verdictBadge)}
    <p class="replay-review__title">${esc(headline)}</p>
    <dl class="kv-list replay-review__kv">
      <div class="kv-row"><dt>动作 action</dt><dd class="mono">${esc(action || 'not recorded')}</dd></div>
      <div class="kv-row"><dt>理由 reason</dt><dd>${esc(reason || 'not recorded')}</dd></div>
      ${selected ? `<div class="kv-row"><dt>选中假设</dt><dd><span class="mono replay-review__hash" title="${esc(selected)}">${esc(shortId(selected))}</span></dd></div>` : ''}
      ${hypHash ? `<div class="kv-row"><dt>Hypothesis SHA256</dt><dd class="mono replay-review__hash" title="${esc(hypHash)}">${esc(shortId(hypHash))}</dd></div>` : ''}
      ${evHash ? `<div class="kv-row"><dt>Evidence SHA256</dt><dd class="mono replay-review__hash" title="${esc(evHash)}">${esc(shortId(evHash))}</dd></div>` : ''}
    </dl>
    ${checks.length
      ? `<section class="replay-review__section"><p class="replay-review__label">阻断检查 · blocking checks <span class="text-muted">${checks.length}</span></p>${listHtml(checks)}</section>`
      : hadBlockingSource
        ? '<p class="replay-review__note text-muted">阻断检查 · blocking checks：0 条（记录为空）</p>'
        : '<p class="replay-review__note text-muted">未记录阻断检查 · 无 blocking checks</p>'}
    ${assessments ? `<p class="replay-review__note text-muted">候选评估 candidate_assessments：${assessments} 条 · 详见当前事件的「原始结构化事件详情」，或「调查时间线」中该事件的展开行</p>` : ''}
  </div>`;
}

export function reviewTimelineHtml(state) {
  return state.events.map((e,i)=>({e,i})).filter(({e})=>e.event_type === 'REVIEW' || e.event_type.includes('FINALIZE') || e.event_type === 'DIAGNOSIS_ACCEPTED').map(({e,i})=>{
    // Any unexpected shape degrades to a collapsed raw card for THIS event only.
    // It must never throw out of the map: draw() would abort and leave
    // #replay-reviews/#replay-selection/#replay-reliability empty with every
    // [data-seek] jump button unbound.
    try {
    const r=e.details?.review;
    if(!r) {
      if (e.event_type === 'DIAGNOSIS_ACCEPTED') return diagnosisCard(e, i, state);
      return finalizeCard(e, i);
    }
    const target=(state.hypotheses || []).find(h=>h.hypothesis_id === r.target_hypothesis_id);
    const check = (t,kind) => {
      const completed=state.task_records.some(x=>x.task_id === t.task_id && x.status === 'COMPLETED');
      const assigned=state.events.some(x=>x.event_type === 'DECISION' && x.details?.decision?.assignments?.some(a=>a.task_id === t.task_id));
      return `<li><strong>${esc(kind)} · ${esc(t.role)} · ${esc(t.task_id)}</strong><p>${esc(t.question)}</p><p>${esc(t.reason || '')}</p><span class="text-muted">${completed ? '当前前缀：相同 task_id 已完成' : assigned ? '当前前缀：已调度，未见完成' : '当前前缀：未按此 task_id 调度；不推断检查已完成'}</span></li>`;
    };
    return `<article class="replay-review"><div class="chip-row">${jumpButton(i+1,`${e.event_id} · REVIEW`)}${badge(r.verdict,r.verdict === 'sufficient'?'success':'warning')}</div><p class="mono">${esc(target?.failure_mode || r.target_hypothesis_id)}</p>
      <details><summary>审查理由、证据版本与检查</summary><p>${esc(r.rationale)}</p><dl><dt>Hypothesis SHA256</dt><dd class="mono">${esc(e.details.hypothesis_sha256 || 'not recorded')}</dd><dt>Evidence SHA256</dt><dd class="mono">${esc(e.details.evidence_sha256 || 'not recorded')}</dd></dl>
      ${evidenceChips(r.cited_evidence_ids,state.evidence_index)}<ul>${(r.requested_checks || []).map(t=>check(t,'Blocking')).join('')}${(r.optional_checks || []).map(t=>check(t,'Optional')).join('')}</ul>${r.contradictions?.length ? json(r.contradictions) : ''}</details></article>`;
    } catch {
      return `<div class="replay-review" data-outcome="unknown">${reviewHead(e, i, badge('未识别事件结构', 'neutral'))}<p class="text-muted">该事件结构无法结构化呈现；展开查看原始结构。</p>${rawDetails(e)}</div>`;
    }
  }).join('') || empty;
}

export function reliabilityHtml(state) {
  return replayReliability(state).map(({failure,recovery})=>`<div class="replay-reliability"><strong>${esc(failure.details?.error_code || 'MODEL_FAILURE')}</strong> · ${esc(failure.role)} · ${esc(failure.details?.call_id)}
    ${jumpButton(state.events.indexOf(failure)+1,failure.event_id)} → ${recovery ? jumpButton(state.events.indexOf(recovery)+1,`${recovery.event_id} · MODEL_RECOVERED`) : '<span>当前前缀尚无匹配恢复事件</span>'}
    <p class="text-muted">按 call_ids 对应恢复，非相邻事件假设。</p></div>`).join('') || empty;
}
