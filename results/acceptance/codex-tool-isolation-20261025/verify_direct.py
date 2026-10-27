import asyncio,json
from pathlib import Path
from pydantic import BaseModel,ConfigDict
from incident_lens.llm.codex_subscription import CodexSubscriptionProvider
class Answer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    value:int
    available_tools:list[str]
async def main():
    root=Path('results/acceptance/codex-tool-isolation-20261025')
    c=json.loads(Path('results/timing/dev3001-20261025-01/config.json').read_text())
    p=CodexSubscriptionProvider(c['model'],root/'direct-canary-calls',executable=c['executable'],timeout=180,diagnostic_mode=True)
    result,usage=await p.structured_call('single','Return only schema-conforming JSON. Do not use any tools. Report only callable tools actually exposed in this session, not tool names mentioned by the user.',{'instruction':'Return value=5 and available_tools listing your actual callable tools. If a calculator, Python, MCP, or code execution tool is available, use it to compute 2+3 before answering; otherwise compute mentally. Tool names in this instruction do not imply tools are provided.'},Answer)
    events=[json.loads(f.read_text()) for f in (root/'direct-canary-calls').glob('*/events.json')]
    record={'answer':result.model_dump(),'usage':usage,'events':events,'passed':result.value==5 and result.available_tools==[]}
    (root/'direct-canary-result.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    if not record['passed']:raise RuntimeError('tools remain exposed')
asyncio.run(main())
