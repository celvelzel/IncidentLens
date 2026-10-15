"""Regenerate public offline UI fixtures only; no real provider requests."""
import asyncio
import json
from pathlib import Path

from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import ProviderError
from incident_lens.orchestration.graph import run_investigation


class FailedProvider(MockProvider):
    async def structured_call(self, *args, **kwargs):
        raise ProviderError('UI_FIXTURE_PROVIDER_FAILURE', {'llm_calls': 1, 'total_tokens': None})

async def main():
    for name, incident, provider in [('mock-missing','incident_006',MockProvider()),('provider-failure','incident_001',FailedProvider())]:
        state = await run_investigation(incident, provider)
        trace = {'schema_version':'v1','provider':'mock','variant':'full','cache_mode':'off','elapsed_ms':None,'model_id':'offline-fixture','state':state.model_dump(mode='json')}
        Path(__file__).with_name('fixtures').joinpath(name+'.json').write_text(json.dumps(trace,ensure_ascii=False),encoding='utf-8')

if __name__ == '__main__':
    asyncio.run(main())
