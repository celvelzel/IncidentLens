import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderReport } from '../../src/incident_lens/web/static/js/views.js';
import { evidenceContext } from '../../src/incident_lens/web/static/js/replay.js';
import { evidenceDrawerHtml } from '../../src/incident_lens/web/static/js/components.js';

test('tentative explanations remain visibly unconfirmed, with gaps and next checks', () => {
  const panel = { innerHTML: '', querySelectorAll: () => [] };
  const attack = '<img src=x onerror=alert(1)>';
  renderReport(panel, {
    evidence_index: { E1: {} },
    report: {
      status: 'INCONCLUSIVE', root_cause: null, assessment_level: 'LIKELY',
      provisional_hypotheses: [{ culprit_service: 'backend', failure_mode: 'pool', support_ids: ['E1'] }],
      provisional_observations: [attack], unresolved: ['Need origin evidence'],
      next_steps: ['Inspect origin logs'], optional_questions: ['Longer baseline'],
      assessment_basis: ['Observed mechanism, attribution pending'], stop_reason: 'Pending',
    },
  }, '');
  assert.match(panel.innerHTML, /较可能（未确认）/);
  assert.match(panel.innerHTML, /待确认的解释/);
  assert.match(panel.innerHTML, /关键缺口/);
  assert.match(panel.innerHTML, /建议下一步/);
  assert.match(panel.innerHTML, /可选补充（不阻止作答）/);
  assert.doesNotMatch(panel.innerHTML, /<img/);
  assert.match(panel.innerHTML, /&lt;img/);
  assert.match(panel.innerHTML, /data-evidence-id="E1"/);
});

test('provisional citations are distinguished from accepted root support in the inspector', () => {
  const record = { evidence_id: 'E1', service: 'backend', source_type: 'logs', metadata: {}, excerpt: 'observed' };
  const state = { evidence_index: { E1: record }, provenance: {}, findings: [], hypotheses: [],
    report: { supporting_evidence_ids: [], provisional_hypotheses: [{ support_ids: ['E1'] }],
      provisional_observations: ['[E1] observed'] } };
  const observation = evidenceContext(state).E1;
  assert.equal(observation.report_references.supporting, false);
  assert.equal(observation.report_references.provisional, true);
  const html = evidenceDrawerHtml(record, observation);
  assert.match(html, /用于待确认解释，尚未支持最终诊断/);
  state.report = null;
  assert.equal(evidenceContext(state).E1.report_references, null);
});
