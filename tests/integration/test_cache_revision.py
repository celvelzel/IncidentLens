import shutil

from incident_lens.cache import CachePolicy, SemanticCacheAdapter
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.tools import EvidenceProvider


async def test_long_lived_cache_refreshes_public_dataset_revision(tmp_path):
    data = tmp_path / "data"
    shutil.copytree("data", data)
    revision = EvidenceProvider(data).dataset_revision
    adapter = SemanticCacheAdapter(
        CachePolicy(mode="semantic"), tmp_path / "cache.sqlite", revision
    )
    await run_investigation("incident_001", MockProvider(), data_root=data, cache=adapter)
    warm = await run_investigation("incident_001", MockProvider(), data_root=data, cache=adapter)
    assert sum(e.event_type == "CACHE_HIT" for e in warm.events) == 4
    unrelated = next((data / "incidents/incident_036/public").glob("*.jsonl"))
    with unrelated.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    assert EvidenceProvider(data).dataset_revision != revision
    changed = await run_investigation("incident_001", MockProvider(), data_root=data, cache=adapter)
    assert not any(e.event_type == "CACHE_HIT" for e in changed.events)
    assert changed.report.status == "RESOLVED"
    assert adapter.dataset_revision == revision  # caller remains safe to share across runs
