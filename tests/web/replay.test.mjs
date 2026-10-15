import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { replayPrefix, replayReducer, initialReplay } from '../../src/incident_lens/web/static/js/replay.js';
import { evidenceDrawerHtml, evidenceChips } from '../../src/incident_lens/web/static/js/components.js';
const trace = JSON.parse(readFileSync(new URL('./fixtures/mock-success.json',import.meta.url)));
const events = trace.state.events;
test('saved Mock success: report and observations follow saved prefix only',()=>{
  const zero=replayPrefix(trace,0); assert.equal(zero.report,null); assert.deepEqual(zero.hypotheses,[]); assert.deepEqual(zero.evidence_index,{});
  const reportIndex=events.findIndex(e=>e.event_type==='REPORT');
  assert.equal(replayPrefix(trace,reportIndex).report,null);
  assert.deepEqual(replayPrefix(trace,reportIndex+1).report,trace.state.report);
  const toolIndex=events.findIndex(e=>e.event_type==='TOOL_CALL');
  assert.equal(Object.keys(replayPrefix(trace,toolIndex).evidence_index).length,0);
  assert.ok(Object.keys(replayPrefix(trace,toolIndex+1).evidence_index).length>0);
});
test('deterministic stepping equals jumping and leaves source immutable',()=>{
  const before=JSON.stringify(trace);
  assert.deepEqual(events.reduce(replayReducer,initialReplay(trace)),replayPrefix(trace,events.length));
  assert.deepEqual(replayPrefix(trace,events.length),replayPrefix(trace,events.length));
  assert.equal(JSON.stringify(trace),before);
});
test('old missing history never backfills final report, hypotheses, observations',()=>{
  const old=structuredClone(trace); delete old.state.events;
  const s=replayPrefix(old,999); assert.equal(s.report,null); assert.deepEqual(s.hypotheses,[]); assert.deepEqual(s.evidence_index,{});
});
test('failed provider trace without report remains usable and failed',()=>{
  const failed=structuredClone(trace); failed.state.events=[{event_type:'MODEL_FAILURE',run_id:trace.state.run_id,incident_id:trace.state.incident_id,details:{error_code:'fixture_provider_timeout'}}];
  const s=replayPrefix(failed,1); assert.equal(s.report,null); assert.equal(s.workflow_status,'FAILED');
});
test('final index alone, failed calls, wrong incident/run/role and mismatched records never authorize evidence',()=>{
  const event=events.find(e=>e.event_type==='TOOL_CALL');
  for(const change of [e=>e.run_id='other',e=>e.incident_id='other',e=>e.role='coordinator',e=>e.details.result.ok=false,e=>e.details.result.records.forEach(r=>r.excerpt='tampered'),e=>e.details.result.records.forEach(r=>r.incident_id='other')]) {
    const e=structuredClone(event); change(e); const s=replayReducer(initialReplay(trace),e); assert.equal(Object.keys(s.evidence_index).length,0);
  }
});
test('hypothesis changes are event-derived ordered history',()=>{
  const merge=events.findIndex(e=>e.event_type==='MERGE');
  assert.deepEqual(replayPrefix(trace,merge).hypotheses,[]);
  assert.ok(replayPrefix(trace,merge+1).hypothesis_history.length>0);
});
test('evidence inspector escapes XSS including provenance and unavailable ids',()=>{
  const attack='<img src=x onerror=alert(1)>';
  const html=evidenceDrawerHtml({excerpt:attack,metadata:{[attack]:attack},source_path:attack},{args:attack});
  assert.ok(!html.includes('<img')); assert.ok(html.includes('&lt;img'));
  const chip=evidenceChips([attack],{}); assert.ok(chip.includes('disabled')); assert.ok(!chip.includes('<img'));
});
test('replay reducer has no provider, tool or network execution capability',()=>{
  const code=readFileSync(new URL('../../src/incident_lens/web/static/js/replay.js',import.meta.url),'utf8');
  assert.doesNotMatch(code,/fetch\(|runInvestigation|\/api\/run/);
});

test('forged tool/source binding is rejected even if final index agrees',()=>{
  const forged=structuredClone(trace);
  const e=forged.state.events.find(e=>e.event_type==='TOOL_CALL');
  e.role='logs'; e.details.tool_name='query_logs';
  e.details.result.records.forEach(r=>{r.source_type='database'; forged.state.evidence_index[r.evidence_id]=structuredClone(r);});
  assert.equal(Object.keys(replayReducer(initialReplay(forged),e).evidence_index).length,0);
});
test('saved missing and provider-failure fixtures replay without report backfill',()=>{
  for(const name of ['mock-missing','provider-failure']) {
    const fixture=JSON.parse(readFileSync(new URL(`./fixtures/${name}.json`,import.meta.url)));
    assert.equal(replayPrefix(fixture,0).report,null);
    const s=replayPrefix(fixture,fixture.state.events.length);
    assert.deepEqual(s.report,fixture.state.report);
    assert.equal(s.report.root_cause,null);
  }
});
