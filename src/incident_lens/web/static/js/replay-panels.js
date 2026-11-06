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

export function reviewTimelineHtml(state) {
  return state.events.map((e,i)=>({e,i})).filter(({e})=>e.event_type === 'REVIEW' || e.event_type.includes('FINALIZE') || e.event_type === 'DIAGNOSIS_ACCEPTED').map(({e,i})=>{
    const r=e.details?.review;
    if(!r) return `<div class="replay-review">${jumpButton(i+1,`${e.event_id} · ${e.event_type}`)}${json(e.details)}</div>`;
    const target=state.hypotheses.find(h=>h.hypothesis_id === r.target_hypothesis_id);
    const check = (t,kind) => {
      const completed=state.task_records.some(x=>x.task_id === t.task_id && x.status === 'COMPLETED');
      const assigned=state.events.some(x=>x.event_type === 'DECISION' && x.details?.decision?.assignments?.some(a=>a.task_id === t.task_id));
      return `<li><strong>${esc(kind)} · ${esc(t.role)} · ${esc(t.task_id)}</strong><p>${esc(t.question)}</p><p>${esc(t.reason || '')}</p><span class="text-muted">${completed ? '当前前缀：相同 task_id 已完成' : assigned ? '当前前缀：已调度，未见完成' : '当前前缀：未按此 task_id 调度；不推断检查已完成'}</span></li>`;
    };
    return `<article class="replay-review"><div class="chip-row">${jumpButton(i+1,`${e.event_id} · REVIEW`)}${badge(r.verdict,r.verdict === 'sufficient'?'success':'warning')}</div><p class="mono">${esc(target?.failure_mode || r.target_hypothesis_id)}</p>
      <details><summary>审查理由、证据版本与检查</summary><p>${esc(r.rationale)}</p><dl><dt>Hypothesis SHA256</dt><dd class="mono">${esc(e.details.hypothesis_sha256 || 'not recorded')}</dd><dt>Evidence SHA256</dt><dd class="mono">${esc(e.details.evidence_sha256 || 'not recorded')}</dd></dl>
      ${evidenceChips(r.cited_evidence_ids,state.evidence_index)}<ul>${(r.requested_checks || []).map(t=>check(t,'Blocking')).join('')}${(r.optional_checks || []).map(t=>check(t,'Optional')).join('')}</ul>${r.contradictions?.length ? json(r.contradictions) : ''}</details></article>`;
  }).join('') || empty;
}

export function reliabilityHtml(state) {
  return replayReliability(state).map(({failure,recovery})=>`<div class="replay-reliability"><strong>${esc(failure.details?.error_code || 'MODEL_FAILURE')}</strong> · ${esc(failure.role)} · ${esc(failure.details?.call_id)}
    ${jumpButton(state.events.indexOf(failure)+1,failure.event_id)} → ${recovery ? jumpButton(state.events.indexOf(recovery)+1,`${recovery.event_id} · MODEL_RECOVERED`) : '<span>当前前缀尚无匹配恢复事件</span>'}
    <p class="text-muted">按 call_ids 对应恢复，非相邻事件假设。</p></div>`).join('') || empty;
}
