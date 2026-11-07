import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { replayPrefix, replayReducer, initialReplay, replayBookmarks, evidenceContext } from '../../src/incident_lens/web/static/js/replay.js';
import { evidenceDrawerHtml, evidenceChips, bindEvidenceChips } from '../../src/incident_lens/web/static/js/components.js';
import { buildEvidenceFlow } from '../../src/incident_lens/web/static/js/orchestration.js';
import { renderReport } from '../../src/incident_lens/web/static/js/views.js';
const trace = JSON.parse(readFileSync(new URL('./fixtures/mock-success.json',import.meta.url)));
const events = trace.state.events;

test('scalar hypothesis updates remain navigable and replayable',()=>{
  const hypothesis={hypothesis_id:'h1',failure_mode:'postgres_connection_exhaustion',status:'REJECTED'};
  const event={event_type:'MERGE',event_id:'merge',run_id:trace.state.run_id,incident_id:trace.state.incident_id,details:{hypotheses:hypothesis}};
  const scalar=structuredClone(trace);
  scalar.state.events=[event];
  assert.equal(replayBookmarks(scalar).find(b=>b.id==='postgres_connection_exhaustion').position,1);
  assert.deepEqual(replayPrefix(scalar,1).hypotheses,[hypothesis]);
  const decision={...event,event_type:'DECISION',details:{decision:{hypothesis_updates:hypothesis,reason:'recorded'}}};
  scalar.state.events=[decision,event];
  assert.equal(replayPrefix(scalar,2).hypothesis_history[0].reason,'recorded');
  event.details.hypotheses=[null,42,hypothesis];
  assert.equal(replayPrefix(scalar,2).hypotheses.length,1);
  assert.equal(replayBookmarks(scalar).find(b=>b.id==='postgres_connection_exhaustion').position,2);
});

test('evidence context ignores non-text report entries and keeps recorded references',()=>{
  const state={evidence_index:{E1:{}},provenance:{},findings:[],hypotheses:[],report:{
    provisional_hypotheses:[null,{support_ids:'E1'}], causal_chain:[42,null,'cause [E1]'],
    provisional_observations:{unexpected:'shape'},
  }};
  const refs=evidenceContext(state).E1.report_references;
  assert.equal(refs.provisional,true);
  assert.deepEqual(refs.causal_chain,['cause [E1]']);
  assert.deepEqual(refs.provisional_observations,[]);
  state.report.causal_chain=42;
  assert.deepEqual(evidenceContext(state).E1.report_references.causal_chain,[]);
  state.events=[];
  assert.deepEqual(buildEvidenceFlow(state).evidence[0].report.causalChain,[]);
  const panel={innerHTML:'',querySelectorAll:()=>[]};
  state.report={status:'INSUFFICIENT',causal_chain:'cause [E1]',provisional_observations:'observation [E1]'};
  renderReport(panel,state,'');
  assert.match(panel.innerHTML,/cause \[E1\]/);
  assert.match(panel.innerHTML,/observation \[E1\]/);
  state.report.causal_chain=42;
  assert.doesNotThrow(()=>renderReport(panel,state,''));
});

test('inherited object properties never authorize evidence chips or drawer access',()=>{
  const html=evidenceChips(['constructor','toString','__proto__'],{});
  assert.equal((html.match(/disabled/g)||[]).length,3);
  let handler;
  const chip={dataset:{evidenceId:'constructor'},addEventListener:(type,fn)=>{handler=fn;}};
  globalThis.document={createElement:()=>({style:{},remove(){}}),
    getElementById:()=>({appendChild(){}})};
  // A click must stop at unavailable handling, never try to render a Function as evidence.
  bindEvidenceChips({querySelectorAll:()=>[chip]},{});
  const originalTimeout=globalThis.setTimeout;
  try { globalThis.setTimeout=()=>0; assert.doesNotThrow(()=>handler()); }
  finally { globalThis.setTimeout=originalTimeout; }
  delete globalThis.document;
});
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
test('model failure without a recorded terminal outcome remains usable and degraded',()=>{
  const failed=structuredClone(trace); failed.state.events=[{event_type:'MODEL_FAILURE',run_id:trace.state.run_id,incident_id:trace.state.incident_id,details:{error_code:'fixture_provider_timeout'}}];
  const s=replayPrefix(failed,1); assert.equal(s.report,null); assert.equal(s.workflow_status,'DEGRADED');
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

test('actual cumulative multi-MERGE findings remain unique and match saved final findings',()=>{
  assert.ok(events.filter(e=>e.event_type==='MERGE').length>1);
  const final=replayPrefix(trace,events.length);
  assert.equal(final.findings.length,4);
  assert.equal(new Set(final.findings.map(f=>f.finding_id)).size,4);
  assert.deepEqual(final.findings,trace.state.findings);
});
test('unchanged hypothesis snapshots do not become additional evolution changes',()=>{
  const merge=events.find(e=>e.event_type==='MERGE');
  const first=replayReducer(initialReplay(trace),merge);
  const repeated=replayReducer(first,{...merge,event_id:'duplicate-snapshot'});
  assert.deepEqual(repeated.hypothesis_history,first.hypothesis_history);
  const changed=structuredClone(merge);
  changed.event_id='changed-snapshot';
  changed.details.hypotheses[0].support_ids.push('changed-support');
  const next=replayReducer(repeated,changed);
  assert.equal(next.hypothesis_history.length,first.hypothesis_history.length+1);
  assert.equal(next.hypothesis_history.at(-1).event_id,'changed-snapshot');
});
