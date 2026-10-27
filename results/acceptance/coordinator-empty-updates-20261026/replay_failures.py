"""Offline replay of saved outputs; no provider, tools, Oracle or network."""
import asyncio,hashlib,json
from pathlib import Path
from pydantic import ValidationError
from incident_lens.agents.service import decide
from incident_lens.security.context import ROLE_TOOL_ACL
BASE=Path('results/timing/dev3002-3005-20261026-01/batch')
async def main():
    results=[]
    for slot in ['slot-001','slot-004','slot-005','slot-008']:
        root=BASE/'runs'/slot/'attempt-001';state=json.loads((root/'trace.json').read_text())['state'];assert state['hypotheses']==[]
        calls=[]
        for f in (root/'codex-calls').glob('*/request.json'):
            request=json.loads(f.read_text());output=f.parent/'output.json'
            if request['role'] in ['coordinator','single'] and output.exists() and 'hypothesis_updates' in json.loads(output.read_text()):
                calls.append((f.stat().st_mtime,output))
        output=max(calls,key=lambda c:c[0])[1]
        class Replay:
            async def structured_call(self,role,system,payload,schema):
                assert schema.model_json_schema()['properties']['hypothesis_updates']['maxItems']==0
                return schema.model_validate_json(output.read_bytes()),{}
        try:
            await decide(Replay(),dict(state,benchmark_rca=True,role_tool_acl=ROLE_TOOL_ACL))
        except ValidationError as exc:
            errors=exc.errors(include_input=False,include_context=False,include_url=False)
            assert any(e['loc']==('hypothesis_updates',) and e['type']=='too_long' for e in errors)
            results.append({'slot':slot,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'rejected_at_schema':True,'runtime_or_tools_executed':False})
        else:raise AssertionError('Saved invalid update was accepted')
    print(json.dumps(results))
    Path('results/acceptance/coordinator-empty-updates-20261026/replay-results.json').write_text(json.dumps(results,indent=2)+'\n')
asyncio.run(main())
