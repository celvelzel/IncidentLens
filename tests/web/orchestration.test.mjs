import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildNarrative, buildReviewGates } from '../../src/incident_lens/web/static/js/orchestration.js';

test('finalization follows the latest proposal and gate outcome in the prefix', () => {
  const decision = (id, hypothesis) => ({ event_id: id, event_type: 'DECISION', details: { decision: { action: 'FINALIZE', selected_hypothesis_id: hypothesis } } });
  const rejected = { event_id: 'reject', event_type: 'FINALIZE_REJECTED', details: { selected_hypothesis_id: 'old' } };
  const accepted = { event_id: 'accept', event_type: 'DIAGNOSIS_ACCEPTED', details: { root_cause: { hypothesis_id: 'new' } } };
  const events = [decision('first', 'old'), rejected, decision('second', 'new'), accepted];
  const get = n => buildReviewGates({ events: events.slice(0, n) }, { variant: 'full' }).finalize;
  assert.match(get(1).statusText, /等待门禁/);
  assert.equal(get(1).diagnosisAccepted, false);
  assert.equal(get(2).blocked, true);
  assert.equal(get(3).blocked, false);
  assert.equal(get(3).selectedHypothesisId, 'new');
  assert.equal(get(4).diagnosisAccepted, true);
  assert.equal(get(4).blocked, false);
  assert.equal(get(4).selectedHypothesisId, 'new');
  assert.equal(get(4).decisionEventId, 'accept');
});

test('narration does not invent case-specific conclusions for arbitrary traces', () => {
  const bookmarks = ['dispatch', 'config', 'insufficient', 'backend_resource_saturation', 'gate', 'last-review', 'report']
    .map((id, index) => ({ id, label: id, position: index + 1 }));
  const chapters = buildNarrative({ events: Array(7).fill({}) }, bookmarks).chapters;
  const gate = chapters.find(c => c.id === 'gate').narration;
  assert.match(gate, /阻断/);
  assert.doesNotMatch(gate, /未触发|无 FINALIZE_REJECTED/);
  assert.doesNotMatch(chapters.find(c => c.id === 'report').narration, /backend_pool_config_regression|确认根因/);
  assert.doesNotMatch(chapters.find(c => c.id === 'last-review').narration, /充分/);
  assert.doesNotMatch(chapters.find(c => c.id === 'backend_resource_saturation').narration, /未记录/);
});
