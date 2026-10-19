"""Offline reproduction: a reader denying delete-sharing interrupts journal status replacement."""
import ctypes
import json
from pathlib import Path
from types import SimpleNamespace
from ctypes import wintypes
from incident_lens.orchestration.observability import RunJournal
from incident_lens.orchestration.runtime import TaskManager

out=Path(__file__).resolve().parent
journal=RunJournal(out/'journal-reproduction',{'purpose':'offline fault reproduction'})
run=SimpleNamespace(run_id='offline-reproduction',state=SimpleNamespace(round_index=1),call_budget=SimpleNamespace(calls=0,tokens=0),registry=SimpleNamespace(call_count=0))
def emit(kind,**details):
 event=SimpleNamespace(event_type=kind,model_dump=lambda **kw:{'event_type':kind,'details':details})
 journal.event(event,run)
manager=TaskManager(2,emit)
manager.assign('coordinate-4','single');manager.start('coordinate-4')
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CreateFileW.restype=wintypes.HANDLE
k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
handle=k.CreateFileW(str((journal.root/'status.json').resolve()),0x80000000,1,None,3,0,None)
assert handle!=ctypes.c_void_p(-1).value,ctypes.get_last_error()
try:
 try:manager.fail('coordinate-4','PROVIDER_TIMEOUT')
 except PermissionError as exc:
  result={'reproduced':True,'exception':type(exc).__name__,'winerror':exc.winerror,'task_record_status':manager.records[-1].status,'can_retry':manager.can_retry('coordinate-4'),'note':'TASK_FAILED is persisted before status.json replacement raises. Exception escapes fail() before retry logic. This reproduces a candidate mechanism, not proof of the actual file holder in slot12.'}
 else:raise AssertionError('expected Windows sharing violation')
finally:
 k.CloseHandle(handle);journal.close()
(out/'permission-reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
