/** Pure recorded-prefix projection. Final state supplies identity and authorization only. */
const dbTools = ['get_db_connections','get_db_active_sessions','get_db_lock_waits','get_db_slow_queries','get_db_health_metrics'];
const roleTools = { logs:['query_logs'], metrics:['query_metrics','get_dependencies',...dbTools], database:dbTools, changes:['query_changes','get_config_diff'], verifier:['fetch_evidence_by_ids'], reporter:['fetch_evidence_by_ids'], single:['query_logs','query_metrics','get_dependencies','query_changes','get_config_diff','fetch_evidence_by_ids',...dbTools] };
const toolSources = { query_logs:['logs'], query_metrics:['metrics'], get_dependencies:['topology'], query_changes:['changes'], get_config_diff:['configs'], ...Object.fromEntries(dbTools.map(t => [t,['database']])) };
const sourceAllowed = (tool, source) => tool === 'fetch_evidence_by_ids' ? ['logs','metrics','topology','changes','configs','database'].includes(source) : (toolSources[tool] || []).includes(source);
const clone = value => JSON.parse(JSON.stringify(value));
const equal = (a, b) => {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false;
  const keys = Object.keys(a).sort();
  return JSON.stringify(keys) === JSON.stringify(Object.keys(b).sort()) && keys.every(k => equal(a[k], b[k]));
};
export function initialReplay(trace) {
  const s = trace.state || {};
  return { incident_id: s.incident_id, run_id: s.run_id, authorized: clone(s.evidence_index || {}), services: clone(s.public_summary?.services || []),
    events: [], evidence_index: {}, provenance: {}, hypotheses: [], hypothesis_history: [], findings: [],
    task_records: [], report: null, round_index: 0, tool_calls_used: 0, llm_calls_used: 0,
    public_summary: clone(s.public_summary || {}),
    budgets: clone(s.budgets || {}), workflow_status: 'not recorded', roles: {} };
}
export function replayReducer(previous, raw) {
  const s = clone(previous);
  if (raw.run_id !== s.run_id || raw.incident_id !== s.incident_id) return s;
  const e = clone(raw), d = e.details || {};
  if (e.event_type === 'TOOL_CALL') {
    s.tool_calls_used++;
    const result = d.result || {};
    const records = result.ok === true && (roleTools[e.role] || []).includes(d.tool_name) && Array.isArray(result.records) ? result.records.filter(r =>
      r.incident_id === s.incident_id && sourceAllowed(d.tool_name, r.source_type) && s.services.includes(r.service) && Object.hasOwn(s.authorized, r.evidence_id) && equal(r, s.authorized[r.evidence_id])) : [];
    for (const record of records) {
      s.evidence_index[record.evidence_id] = record;
      const observation = { event_id: e.event_id, role: e.role, timestamp: e.timestamp,
        task_id: e.task_id || d.task_id, call_id: e.call_id || result.call_id,
        tool: d.tool_name, args: d.args || d.arguments || null };
      const prior = s.provenance[record.evidence_id];
      s.provenance[record.evidence_id] = prior ? { ...prior, observations: [...prior.observations, observation] }
        : { ...observation, observations: [observation] };
    }
    e.details = { ...d, result: { ...result, records, record_count: records.length } };
  }
  if (['LLM_CALL','MODEL_FAILURE'].includes(e.event_type)) s.llm_calls_used += d.llm_calls ?? 1;
  if (e.event_type.startsWith('TASK_')) {
    const task = { ...d, role: e.role, task_id: e.task_id || d.task_id };
    s.task_records = s.task_records.filter(t => t.attempt_id !== task.attempt_id);
    s.task_records.push(task);
    s.roles[e.role || 'runtime'] = d.status || e.event_type.slice(5);
  }
  if (e.event_type === 'DECISION' && d.decision?.action === 'INVESTIGATE') s.round_index++;
  const updates = ['MERGE','HYPOTHESIS_RECONCILED'].includes(e.event_type) ? d.hypotheses || d.hypothesis_updates || [] : [];
  for (const h of updates) {
    const prior = s.hypotheses.find(old => old.hypothesis_id === h.hypothesis_id);
    s.hypotheses = s.hypotheses.filter(old => old.hypothesis_id !== h.hypothesis_id);
    s.hypotheses.push(clone(h));
    const decision = s.events.findLast(old => old.event_type === 'DECISION' && old.details?.decision?.hypothesis_updates?.some(update => equal(update,h)));
    if (!equal(prior, h)) s.hypothesis_history.push({ event_id: e.event_id, timestamp: e.timestamp,
      previous_status: prior?.status || null, reason: decision?.details?.decision?.reason || null,
      decision_event_id: decision?.event_id || null, ...clone(h) });
  }
  if (Array.isArray(d.findings)) {
    for (const finding of d.findings) {
      if (finding.run_id !== s.run_id || finding.incident_id !== s.incident_id || !finding.finding_id) continue;
      const index = s.findings.findIndex(old => old.finding_id === finding.finding_id);
      if (index < 0) s.findings.push(clone(finding));
      else s.findings[index] = clone(finding);
    }
  }
  if (e.event_type === 'REPORT' && d.report) { s.report = clone(d.report); s.roles.report = 'COMPLETED'; }
  if (['RUNTIME_FAILURE','RUNTIME_ERROR','STOP_TIMEOUT'].includes(e.event_type)) s.workflow_status = 'FAILED';
  if (e.event_type === 'MODEL_FAILURE' && !['FAILED','FINISHED'].includes(s.workflow_status)) s.workflow_status = 'DEGRADED';
  if (e.event_type === 'MODEL_RECOVERED' && !['FAILED','FINISHED'].includes(s.workflow_status)) {
    const recovered = new Set([...s.events,e].filter(x => x.event_type === 'MODEL_RECOVERED').flatMap(x => x.details?.call_ids || []));
    s.workflow_status = s.events.some(x => x.event_type === 'MODEL_FAILURE' && !recovered.has(x.details?.call_id)) ? 'DEGRADED' : 'RUNNING';
  }
  if (e.event_type === 'NORMAL_TERMINATION') { s.workflow_status = d.outcome === 'FAILED' ? 'FAILED' : 'FINISHED'; s.termination = clone(d); }
  if (e.event_type === 'DIAGNOSIS_ACCEPTED') s.roles.finalize = 'COMPLETED';
  if (d.termination) s.termination = clone(d.termination);
  if (d.alert) s.incident_alert = clone(d.alert);
  if (d.workflow_status) s.workflow_status = d.workflow_status;
  s.events.push(e);
  return s;
}
export function replayPrefix(trace, count) {
  return (trace.state?.events || []).slice(0, Math.max(0, count)).reduce(replayReducer, initialReplay(trace));
}

export function eventCategory(e) {
  if (e.event_type === 'DECISION') return 'dispatch';
  if (e.event_type === 'REVIEW') return 'review';
  if (e.event_type === 'TOOL_CALL') return 'evidence';
  if (e.event_type === 'MERGE') return 'findings';
  if (e.event_type.includes('HYPOTHESIS')) return 'hypothesis';
  if (e.event_type.startsWith('MODEL_') || e.event_type.includes('RETRY')) return 'reliability';
  if (e.event_type.includes('FINALIZE') || ['DIAGNOSIS_ACCEPTED','REPORT'].includes(e.event_type)) return 'finalization';
  if (e.event_type.includes('TERMINATION') || e.event_type.includes('STOP')) return 'termination';
  if (e.event_type.startsWith('TASK_')) return 'task';
  return 'other';
}

/** Bookmark labels are navigation only, not historical assertions. Never embed event indices. */
export function replayBookmarks(trace) {
  const events = trace.state?.events || [];
  const find = fn => { const index = events.findIndex(fn); return index < 0 ? null : index + 1; };
  const lastReview = events.findLastIndex(e => e.event_type === 'REVIEW');
  const updates = e => ['MERGE','HYPOTHESIS_RECONCILED'].includes(e.event_type) ? e.details?.hypotheses || e.details?.hypothesis_updates || [] : [];
  return [
    { id:'dispatch', label:'首次调度', position:find(e => e.event_type === 'DECISION' && e.details?.decision?.assignments?.length) },
    { id:'config', label:'配置变更证据', position:find(e => e.event_type === 'TOOL_CALL' && e.details?.tool_name === 'get_config_diff' && e.details?.result?.ok === true && e.details.result.records?.length) },
    { id:'insufficient', label:'首次证据不足审查', position:find(e => e.event_type === 'REVIEW' && e.details?.review?.verdict === 'insufficient') },
    ...['postgres_connection_exhaustion','backend_resource_saturation'].map(mode => ({ id:mode, label:`竞争假设 · ${mode}`, position:find(e => updates(e).some(h => h.failure_mode === mode && h.status === 'REJECTED')) })),
    { id:'gate', label:'首次 FinalizeGate 阻断', position:find(e => e.event_type === 'FINALIZE_REJECTED') },
    { id:'last-review', label:'最终审查', position:lastReview < 0 ? null : lastReview + 1 },
    { id:'report', label:'最终报告', position:find(e => e.event_type === 'REPORT' && e.details?.report) },
  ];
}

/** Shared-state paths recorded in the prefix; requests are not dispatches. */
export function replayWorkflow(state) {
  const dispatches = state.events.filter(e => e.event_type === 'DECISION').flatMap(e =>
    (e.details.decision?.assignments || []).map(task => ({ ...task, event_id:e.event_id })));
  const requests = state.events.filter(e => e.event_type === 'REVIEW').flatMap(e =>
    ['requested_checks','optional_checks'].flatMap(kind => (e.details.review?.[kind] || []).map(t => ({...t, kind, event_id:e.event_id}))));
  const roles = [...new Set([...state.events.map(e => e.role).filter(Boolean), ...dispatches.map(t=>t.role), ...requests.map(t => t.role)])];
  return { dispatches, requests, roles };
}

export function replayReliability(state) {
  return state.events.filter(e => e.event_type === 'MODEL_FAILURE').map(failure => ({ failure,
    recovery:state.events.find(e => e.event_type === 'MODEL_RECOVERED' && e.details?.call_ids?.includes(failure.details?.call_id)) || null }));
}

/** Context always comes from the current prefix, including report references. */
export function evidenceContext(state) {
  return Object.fromEntries(Object.keys(state.evidence_index).map(id => [id, {
    ...state.provenance[id],
    findings:state.findings.filter(f => f.evidence_ids?.includes(id)).map(f => ({finding_id:f.finding_id,role:f.role,relation:f.relation,claim:f.claim})),
    hypotheses:state.hypotheses.filter(h => h.support_ids?.includes(id) || h.against_ids?.includes(id)).map(h => ({failure_mode:h.failure_mode,status:h.status,relation:h.against_ids?.includes(id)?'against':'supports'})),
    report_references:state.report ? { supporting:state.report.supporting_evidence_ids?.includes(id) || false,
      provisional:(state.report.provisional_hypotheses || []).some(h => h.support_ids?.includes(id) || h.against_ids?.includes(id)),
      causal_chain:(state.report.causal_chain || []).filter(line => line.includes(`[${id}]`)),
      provisional_observations:(state.report.provisional_observations || []).filter(line => line.includes(`[${id}]`)) } : null,
  }]));
}
