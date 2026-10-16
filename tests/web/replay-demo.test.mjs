import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {replayPrefix, replayReducer, initialReplay, replayBookmarks, replayWorkflow, replayReliability, evidenceContext, eventCategory} from '../../src/incident_lens/web/static/js/replay.js';
import {metadataHtml,workflowHtml,reviewTimelineHtml,historyHtml} from '../../src/incident_lens/web/static/js/replay-panels.js';
const trace=JSON.parse(readFileSync(new URL('./fixtures/mock-success.json',import.meta.url)));
const event=(event_type,details={},role='coordinator')=>({event_type,details,role,run_id:trace.state.run_id,incident_id:trace.state.incident_id,event_id:`event-${event_type}`});

test('failed model requests count, recovered failures do not erase fatal runtime state',()=>{
 let s=initialReplay(trace);
 s=replayReducer(s,event('MODEL_FAILURE',{llm_calls:1,call_id:'a'}));
 s=replayReducer(s,event('MODEL_FAILURE',{llm_calls:1,call_id:'b'}));
 assert.equal(s.llm_calls_used,2);assert.equal(s.workflow_status,'DEGRADED');
 s=replayReducer(s,event('MODEL_RECOVERED',{call_ids:['a']}));assert.equal(s.workflow_status,'DEGRADED');
 s=replayReducer(s,event('MODEL_RECOVERED',{call_ids:['b']}));assert.equal(s.workflow_status,'RUNNING');
 s=replayReducer(s,event('RUNTIME_FAILURE'));
 s=replayReducer(s,event('MODEL_RECOVERED',{call_ids:['b']}));assert.equal(s.workflow_status,'FAILED');
});

test('investigation rounds exclude finalization decisions and proposals are not committed history',()=>{
 let s=replayReducer(initialReplay(trace),event('DECISION',{decision:{action:'FINALIZE',hypothesis_updates:[{hypothesis_id:'x',status:'REJECTED'}]}}));
 assert.equal(s.round_index,0);assert.deepEqual(s.hypotheses,[]);
 s=replayReducer(s,event('DECISION',{decision:{action:'INVESTIGATE'}}));assert.equal(s.round_index,1);
 s=replayReducer(s,event('HYPOTHESIS_RECONCILED',{hypothesis_updates:[{hypothesis_id:'x',status:'REJECTED'}]}));
 assert.equal(s.hypotheses[0].status,'REJECTED');assert.equal(s.hypothesis_history.length,1);
});

test('semantic bookmarks shift with inserted events and absent chapters remain unavailable',()=>{
 const a=replayBookmarks(trace),modified=structuredClone(trace);
 modified.state.events.unshift(event('UNRELATED'));
 const b=replayBookmarks(modified);
 a.forEach((bookmark,i)=>assert.equal(b[i].position,bookmark.position === null ? null : bookmark.position+1));
 assert.ok(replayBookmarks({state:{events:[]}}).every(b=>b.position === null));
});

test('review requests do not manufacture dispatched roles or completed checks',()=>{
 let s=replayReducer(initialReplay(trace),event('REVIEW',{review:{verdict:'insufficient',optional_checks:[{task_id:'logs-check',role:'logs',question:'Read logs'}]}},'verifier'));
 const w=replayWorkflow(s);assert.ok(w.roles.includes('logs'));assert.equal(w.dispatches.length,0);
 assert.match(workflowHtml(s),/仅审查建议 · 未调度/);
 assert.match(reviewTimelineHtml(s),/未按此 task_id 调度/);
});

test('failure recovery pairs by call_ids across intervening events and never infers adjacency',()=>{
 let s=replayReducer(initialReplay(trace),event('MODEL_FAILURE',{call_id:'a'}));
 s=replayReducer(s,event('TASK_COMPLETED',{task_id:'other'}));
 assert.equal(replayReliability(s)[0].recovery,null);
 s=replayReducer(s,event('MODEL_RECOVERED',{call_ids:['a']}));
 assert.equal(replayReliability(s)[0].recovery.event_type,'MODEL_RECOVERED');
});

test('evidence retains first source agent/time and adds repeated retrievals; report context is prefix-gated',()=>{
 const e=trace.state.events.find(e=>e.event_type==='TOOL_CALL');
 let s=replayReducer(initialReplay(trace),e),id=Object.keys(s.evidence_index)[0];
 const first=structuredClone(s.provenance[id]);
 s=replayReducer(s,{...e,event_id:'later-fetch'});
 const context=evidenceContext(s)[id];
 assert.equal(context.role,e.role);assert.equal(context.event_id,first.event_id);assert.equal(context.observations.length,2);assert.equal(context.report_references,null);
 assert.equal(context.observations[1].event_id,'later-fetch');
});

test('metadata and new panels escape untrusted fields and disclose drift and unknown provenance',()=>{
 const attack='<img src=x onerror=alert(1)>';
 const t=structuredClone(trace);t.provider='unrecorded';t.model_id=attack;
 const html=metadataHtml({trace:t,replay_metadata:{verification:{source_unchanged:false,source_drift:[attack]}}});
 assert.match(html,/PROVIDER UNKNOWN/);assert.match(html,/SOURCE DRIFT/);assert.match(html,/独立最终产物/);assert.ok(!html.includes('<img'));
 const s=initialReplay(trace);s.hypotheses=[{hypothesis_id:'x',failure_mode:attack,status:'OPEN'}];s.hypothesis_history=[];
 assert.ok(!historyHtml(s).includes('<img'));
 assert.equal(eventCategory(event('REVIEW')),'review');
});

test('optional real recorded artifact: every prefix is deterministic, committed, and observation/report gated',{skip:!process.env.WP_C_REAL_TRACE},()=>{
 const t=JSON.parse(readFileSync(process.env.WP_C_REAL_TRACE));const es=t.state.events;
 let priorTime=-Infinity,previous=initialReplay(t);
 for(let n=0;n<=es.length;n++) {
   const s=replayPrefix(t,n);assert.deepEqual(s,previous);
   assert.equal(s.events.filter(e=>e.event_type==='REVIEW').length,es.slice(0,n).filter(e=>e.event_type==='REVIEW').length);
   const observed=new Set(es.slice(0,n).filter(e=>e.event_type==='TOOL_CALL' && e.details.result.ok).flatMap(e=>e.details.result.records.map(r=>r.evidence_id)));
   Object.keys(s.evidence_index).forEach(id=>assert.ok(observed.has(id)));
   if(!es.slice(0,n).some(e=>e.event_type==='REPORT')) assert.equal(s.report,null);
   s.hypothesis_history.forEach(h=>assert.ok(es.slice(0,n).some(e=>e.event_id === h.event_id && ['MERGE','HYPOTHESIS_RECONCILED'].includes(e.event_type))));
   if(n<es.length){const time=Date.parse(es[n].timestamp);assert.ok(time>=priorTime);priorTime=time;previous=replayReducer(previous,es[n]);}
 }
 const s=replayPrefix(t,es.length);
 assert.equal(s.llm_calls_used,t.state.llm_calls_used);assert.equal(s.round_index,t.state.round_index);assert.deepEqual(s.report,t.state.report);
 assert.deepEqual([...s.hypotheses].sort((a,b)=>a.hypothesis_id.localeCompare(b.hypothesis_id)),[...t.state.hypotheses].sort((a,b)=>a.hypothesis_id.localeCompare(b.hypothesis_id)));
 assert.equal(s.findings.length,t.state.findings.length);assert.equal(Object.keys(s.evidence_index).length,Object.keys(t.state.evidence_index).length);
});
