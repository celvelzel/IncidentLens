"""Run exactly four authorized post-fix cells, serially, with source/data locks."""
import ctypes
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[4]
ROOT=PROJECT/'results/v16/wp-d/matrix-20261017-01'
OUT=Path(__file__).resolve().parent
SLOTS=[(4,'incident_1003','full'),(8,'incident_1001','full'),(11,'incident_1001','single'),(12,'incident_1003','single')]
def write(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def snapshot():
 paths=[p for d in ('src','scripts','configs','prompts','data') for p in (PROJECT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[PROJECT/'pyproject.toml',ROOT/'protocol.json']
 return {str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def stamp():return datetime.now(timezone.utc).isoformat()

def main():
 assert PROJECT.joinpath('pyproject.toml').is_file(),PROJECT
 frozen=snapshot();write(OUT/'frozen-inputs.json',frozen)
 state={'started_at':stamp(),'phase':'starting','cells':[],'standby_prevention':False}
 write(OUT/'batch-status.json',state)
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.SetThreadExecutionState.argtypes=[ctypes.c_uint];kernel.SetThreadExecutionState.restype=ctypes.c_uint
 if not kernel.SetThreadExecutionState(0x80000003):raise OSError('Cannot acquire system/display execution request')
 state['standby_prevention']=True
 print('Automatic standby prevention acquired; four serial runs authorized.',flush=True)
 child=None
 try:
  for slot,incident,variant in SLOTS:
   assert snapshot()==frozen,'Frozen inputs changed; no additional provider calls allowed'
   old=f'run-{slot:02}-{incident}-{variant}'
   name=old+'-postfix-01'; dest=ROOT/name
   assert not dest.exists(),f'Output already exists: {name}'
   cell={'slot':slot,'incident':incident,'variant':variant,'out':name,'started_at':stamp(),'phase':'running'}
   state['cells'].append(cell);state['phase']='running';write(OUT/'batch-status.json',state)
   command=[sys.executable,'-B',str(PROJECT/'scripts/retest_live_provider_fix.py'),'--dataset',str(PROJECT/'results/wp-b/pilot-public'),'--protocol',str(ROOT/'protocol.json'),'--incident',incident,'--variant',variant,'--out',str(dest)]
   print(f'START slot {slot}: {name}',flush=True)
   with (OUT/f'slot-{slot:02}.out.log').open('w',encoding='utf-8') as stdout,(OUT/f'slot-{slot:02}.err.log').open('w',encoding='utf-8') as stderr:
    child=subprocess.Popen(command,cwd=PROJECT,stdout=stdout,stderr=stderr)
    cell['pid']=child.pid;write(OUT/'batch-status.json',state)
    while child.poll() is None:
     time.sleep(30)
     journal=dest/'observability/status.json'
     if journal.exists():
      try:
       status=json.loads(journal.read_text(encoding='utf-8'))
       cell['progress']={k:status.get(k) for k in ('round_index','physical_requests','tool_calls','last_event','heartbeat_at')}
      except (OSError,ValueError):pass
     write(OUT/'batch-status.json',state)
     print(json.dumps({'slot':slot,'progress':cell.get('progress',{})}),flush=True)
   cell['returncode']=child.returncode;cell['ended_at']=stamp();child=None
   assert snapshot()==frozen,'Frozen inputs changed during investigation'
   if cell['returncode'] or not all((dest/n).is_file() for n in ('scope.json','result.json','verification.json')):
    cell['phase']='artifact_failure';write(OUT/'batch-status.json',state);raise RuntimeError(f'Slot {slot} runner failed; preserved outputs, no automatic retry')
   verification=json.loads((dest/'verification.json').read_text(encoding='utf-8'))
   assert verification['source_unchanged'] and verification['protocol_valid'],'Invalid source or terminal protocol'
   cell.update(phase='completed',termination=verification['termination_reason'],outcome=verification['termination_outcome'],runtime_failure=verification['runtime_failure'])
   selection=json.loads((ROOT/'final-selection.json').read_text(encoding='utf-8'))
   selection['replacements']=[r for r in selection['replacements'] if r['slot']!=slot]
   selection['replacements'].append({'slot':slot,'original_out':old,'selected_out':name,'excluded_attempts':[old],'reason':'User-authorized post-fix rerun; old runtime failure excluded; mixed-version exploratory comparison only'})
   write(ROOT/'final-selection.json',selection)
   write(OUT/'batch-status.json',state)
   print('DONE '+json.dumps(cell),flush=True)
  state['phase']='completed';state['ended_at']=stamp();state['frozen_inputs_unchanged']=snapshot()==frozen;write(OUT/'batch-status.json',state)
  subprocess.run([sys.executable,'-B',str(PROJECT/'analysis/wp_d/summarize.py'),str(ROOT),'--out',str(PROJECT/'analysis/wp_d/reports/postfix-final-matrix-20261018')],cwd=PROJECT,check=True)
 except BaseException as exc:
  state.update(phase='failed',error_type=type(exc).__name__,ended_at=stamp());write(OUT/'batch-status.json',state)
  raise
 finally:
  if child is not None and child.poll() is None:child.terminate();child.wait(timeout=30)
  kernel.SetThreadExecutionState(0x80000000)
  state['standby_prevention']=False;write(OUT/'batch-status.json',state)
  print('Standby execution request released.',flush=True)

if __name__=='__main__':main()
