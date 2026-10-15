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
      s.provenance[record.evidence_id] = { event_id: e.event_id, task_id: e.task_id || d.task_id,
        call_id: e.call_id || result.call_id, tool: d.tool_name, args: d.args || d.arguments || null };
    }
    e.details = { ...d, result: { ...result, records, record_count: records.length } };
  }
  if (e.event_type === 'LLM_CALL') s.llm_calls_used += d.llm_calls || 1;
  if (e.event_type.startsWith('TASK_')) {
    const task = { ...d, role: e.role, task_id: e.task_id || d.task_id };
    s.task_records = s.task_records.filter(t => t.attempt_id !== task.attempt_id);
    s.task_records.push(task);
    s.roles[e.role || 'runtime'] = d.status || e.event_type.slice(5);
  }
  if (e.event_type === 'DECISION') s.round_index++;
  const updates = d.hypotheses || d.hypothesis_updates || d.decision?.hypothesis_updates || [];
  for (const h of updates) {
    s.hypotheses = s.hypotheses.filter(old => old.hypothesis_id !== h.hypothesis_id);
    s.hypotheses.push(clone(h));
    s.hypothesis_history.push({ event_id: e.event_id, ...clone(h) });
  }
  if (Array.isArray(d.findings)) s.findings.push(...clone(d.findings).filter(f => f.run_id === s.run_id && f.incident_id === s.incident_id));
  if (e.event_type === 'REPORT' && d.report) { s.report = clone(d.report); s.roles.report = 'COMPLETED'; }
  if (['RUNTIME_FAILURE','RUNTIME_ERROR','MODEL_FAILURE','TASK_FAILED','STOP_TIMEOUT'].includes(e.event_type)) s.workflow_status = 'FAILED';
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
