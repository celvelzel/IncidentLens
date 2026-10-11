import json
from concurrent.futures import ThreadPoolExecutor
from time import time

import pytest

from incident_lens.agents.service import analyze
from incident_lens.cache import CachePolicy, FakeEmbedder, SemanticCacheAdapter
from incident_lens.cache.embeddings import cosine
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import InvestigationTask
from incident_lens.tools import EvidenceProvider, ToolRegistry


def setup_local(tmp_path, *, role="logs", run="run-one", incident="incident_001", workspace="test"):
    registry = ToolRegistry(EvidenceProvider("data"), workspace, incident, run)
    context = registry.create_context(role)
    tools = {"logs": ["query_logs"], "metrics": ["query_metrics"], "changes": ["query_changes"]}
    args = {
        "service": "backend",
        "start_ts": "2000-01-01T00:00:00Z",
        "end_ts": "9999-12-31T00:00:00Z",
    }
    if role == "metrics":
        args["metric_names"] = []
    result = registry.execute(context, tools[role][0], args)
    assert result.ok and result.records
    task = InvestigationTask(
        task_id="task-one",
        role=role,
        question="Summarize database errors",
        allowed_tools=tools[role],
        reason="Local explanation",
        expected_discriminator="Compare cause",
    )
    cache = SemanticCacheAdapter(CachePolicy(mode="semantic"), tmp_path / "cache.db", "dataset-v1")
    return cache, registry, context, task, result.records, MockProvider()


async def explain(bundle, *, task=None, records=None, context=None):
    cache, registry, original_context, original_task, original_records, provider = bundle
    context, task, records = (
        context or original_context,
        task or original_task,
        original_records if records is None else records,
    )
    calls, events = [], []

    async def execute():
        calls.append(True)
        return (await analyze(provider, context, task, records))[0]

    output = await cache.explain(
        context,
        task,
        records,
        registry,
        provider,
        execute,
        lambda kind, **details: events.append((kind, details)),
    )
    return output, len(calls), events


async def test_paraphrase_hit_and_current_run_rebinding(tmp_path):
    bundle = setup_local(tmp_path)
    original, calls, _ = await explain(bundle)
    assert calls == 1
    fresh = setup_local(tmp_path, run="run-two")
    task = fresh[3].model_copy(update={"task_id": "task-two", "question": "Explain db failures"})
    output, calls, events = await explain(fresh, task=task)
    assert calls == 0 and output.finding.run_id == "run-two"
    assert output.finding.task_id == "task-two" and output.finding.finding_id == "finding-task-two"
    assert output.finding.claim == original.finding.claim
    hit = events[-1][1]
    assert events[-1][0] == "CACHE_HIT" and hit["cache_similarity"] >= 0.95
    assert hit["llm_calls_avoided"] == 1 and hit["cache_lookup_ms"] >= 0
    assert hit["evidence_snapshot_sha256"] and hit["cache_namespace_digest"]
    assert fresh[1].call_count == 1  # The new run actually queried tools first.


@pytest.mark.parametrize(
    "field",
    list(
        __import__(
            "incident_lens.cache.policy", fromlist=["CacheNamespace"]
        ).CacheNamespace.model_fields
    ),
)
async def test_every_namespace_field_partitions(tmp_path, field):
    bundle = setup_local(tmp_path)
    await explain(bundle)
    cache = bundle[0]
    original_namespace = cache.namespace

    def altered(*args):
        ns = original_namespace(*args)
        value = {"agent_role": "single", "task_type": "interpret_metric_window"}.get(
            field,
            "f" * 64 if field.endswith("sha256") or field.endswith("_hash") else "different-v2",
        )
        return ns.model_copy(update={field: value})

    cache.namespace = altered
    _, calls, events = await explain(bundle)
    assert calls == 1 and events[-1][0] == "CACHE_MISS"


@pytest.mark.parametrize(
    "question",
    [
        "Summarize database errors not",
        "Summarize redis errors",
        "Summarize database errors > 2",
        "Summarize database successes",
    ],
)
async def test_opposites_and_near_wrong_queries_rejected(tmp_path, question):
    bundle = setup_local(tmp_path)
    await explain(bundle)
    task = bundle[3].model_copy(update={"question": question})
    _, calls, events = await explain(bundle, task=task)
    assert calls == 1 and all(kind != "CACHE_HIT" for kind, _ in events)


@pytest.mark.parametrize("mutation", ["expiry", "future", "schema", "citation", "identity"])
async def test_corruption_and_ttl_invalidate(tmp_path, mutation):
    bundle = setup_local(tmp_path)
    await explain(bundle)
    with bundle[0].store.connection() as db:
        if mutation in ("expiry", "future"):
            db.execute(
                "UPDATE explanations SET created_at=?",
                (time() + 100 if mutation == "future" else 0,),
            )
        else:
            payload = json.loads(db.execute("SELECT response_json FROM explanations").fetchone()[0])
            if mutation == "schema":
                payload["unexpected"] = True
            elif mutation == "citation":
                payload["finding"]["evidence_ids"] = ["fabricated"]
            else:
                payload["finding"]["run_id"] = "spoofed-run"
            db.execute("UPDATE explanations SET response_json=?", (json.dumps(payload),))
    _, calls, events = await explain(bundle)
    assert calls == 1 and events[0][0] == "INVALIDATED"


async def test_input_authority_exact_content_and_role_boundaries(tmp_path):
    bundle = setup_local(tmp_path)
    await explain(bundle)
    forged = bundle[2].model_copy()
    with pytest.raises(PermissionError):
        await explain(bundle, context=forged)
    modified = bundle[4][0].model_copy(update={"excerpt": "invented"})
    with pytest.raises(PermissionError):
        await explain(bundle, records=[modified])
    unqueried = setup_local(tmp_path)[1].create_context("logs")
    with pytest.raises(PermissionError):
        await explain(bundle, context=unqueried)
    wrong_task = bundle[3].model_copy(update={"role": "changes"})
    with pytest.raises(PermissionError):
        await explain(bundle, task=wrong_task)
    with pytest.raises(PermissionError):
        await explain(bundle, context=bundle[1].create_context("verifier"))


@pytest.mark.parametrize("mode", ["off", "exact"])
async def test_off_and_exact_modes(tmp_path, mode):
    bundle = setup_local(tmp_path)
    bundle[0].policy.mode = mode
    await explain(bundle)
    _, calls, _ = await explain(bundle)
    assert calls == (1 if mode == "off" else 0)
    _, calls, _ = await explain(
        bundle, task=bundle[3].model_copy(update={"question": "Explain db failures"})
    )
    assert calls == 1


async def test_empty_evidence_not_cached(tmp_path):
    bundle = setup_local(tmp_path)
    await explain(bundle, records=[])
    _, calls, events = await explain(bundle, records=[])
    assert calls == 1 and events[-1][1]["cache_invalidation_reason"] == "empty_evidence"


def test_atomic_concurrent_store_and_hits(tmp_path):
    from incident_lens.cache.store import SQLiteCacheStore

    def write(number):
        store = SQLiteCacheStore(tmp_path / "concurrent.db")
        store.put(
            cache_key=str(number),
            namespace_digest="ns",
            namespace_json="{}",
            task_signature="task",
            question="q",
            exact_question="q",
            embedding_backend="fake",
            vector=[1.0],
            response_json=json.dumps({"number": number}),
            ttl_seconds=3600,
        )
        for _ in range(5):
            store.record_hit(str(number))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(32)))
    store = SQLiteCacheStore(tmp_path / "concurrent.db")
    rows = store.candidates("ns", "task")
    assert len(rows) == 32 and all(row["hit_count"] == 5 for row in rows)
    assert {json.loads(row["response_json"])["number"] for row in rows} == set(range(32))
    with store.connection() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


async def test_actual_cold_warm_graph_calls_and_grounding(tmp_path):
    cache = SemanticCacheAdapter(CachePolicy(mode="semantic"), tmp_path / "graph.db", "dataset-v1")
    cold = await run_investigation("incident_001", MockProvider(), cache=cache)
    warm = await run_investigation("incident_001", MockProvider(), cache=cache)
    assert cold.report.status == warm.report.status == "RESOLVED"
    assert cold.report.root_cause.failure_mode == warm.report.root_cause.failure_mode
    hits = [event for event in warm.events if event.event_type == "CACHE_HIT"]
    assert hits and all(event.source == "cache" for event in hits)
    assert warm.llm_calls_used == cold.llm_calls_used - len(hits)
    assert warm.tool_calls_used == cold.tool_calls_used
    assert all(f.run_id == warm.run_id for f in warm.findings)
    assert set(warm.report.supporting_evidence_ids).issubset(warm.evidence_index)
    assert all(event.role not in ("coordinator", "verifier", "reporter") for event in hits)


def test_fake_embedder_synonyms_are_offline():
    embedder = FakeEmbedder()
    assert cosine(
        embedder.embed("Summarize database errors"), embedder.embed("Explain db failures")
    ) == pytest.approx(1)


@pytest.mark.parametrize(
    "change",
    [
        "workspace",
        "incident",
        "role",
        "snapshot",
        "dataset",
        "prompt",
        "model",
        "parameters",
        "schema",
        "acl",
        "filter",
    ],
)
async def test_real_inputs_partition_cache(tmp_path, change):
    bundle = setup_local(tmp_path)
    await explain(bundle)
    fresh = setup_local(
        tmp_path,
        workspace="different" if change == "workspace" else "test",
        incident="incident_002" if change == "incident" else "incident_001",
        role="metrics" if change == "role" else "logs",
    )
    cache = fresh[0]
    task, records = fresh[3], fresh[4]
    attributes = {
        "dataset": "dataset_revision",
        "prompt": "prompt_version",
        "schema": "output_schema_version",
        "acl": "tool_acl_version",
    }
    if change in attributes:
        setattr(cache, attributes[change], "different-v2")
    elif change == "model":
        fresh[5].model_id = "different-model"
    elif change == "parameters":
        fresh[5].temperature = 0.5
    elif change == "snapshot":
        records = records[:1]
        assert len(fresh[4]) > 1
    elif change == "filter":
        task = task.model_copy(update={"filters": {"service": "backend"}})
    _, calls, events = await explain(fresh, task=task, records=records)
    assert calls == 1 and all(kind != "CACHE_HIT" for kind, _ in events)


async def test_forged_citation_rejected_even_with_matching_integrity_digest(tmp_path):
    import hashlib

    bundle = setup_local(tmp_path)
    await explain(bundle)
    with bundle[0].store.connection() as db:
        row = db.execute("SELECT response_json FROM explanations").fetchone()
        payload = json.loads(row[0])
        payload["finding"]["evidence_ids"] = ["fabricated"]
        response = json.dumps(payload)
        db.execute(
            "UPDATE explanations SET response_json=?,response_sha256=?",
            (response, hashlib.sha256(response.encode()).hexdigest()),
        )
    _, calls, events = await explain(bundle)
    assert calls == 1 and events[0][0] == "INVALIDATED"


async def test_fresh_identity_spoof_cannot_be_stored(tmp_path):
    bundle = setup_local(tmp_path)
    cache, registry, context, task, records, provider = bundle

    async def spoof():
        output = (await analyze(provider, context, task, records))[0]
        output.finding.run_id = "spoofed-run"
        return output

    with pytest.raises(ValueError, match="identity mismatch"):
        await cache.explain(context, task, records, registry, provider, spoof, lambda *a, **k: None)
    with cache.store.connection() as db:
        assert db.execute("SELECT count(*) FROM explanations").fetchone()[0] == 0


async def test_single_identity_cannot_import_another_task_roles_unpublished_records(tmp_path):
    bundle = setup_local(tmp_path)
    cache, registry, _, task, _, provider = bundle
    context = registry.create_context("single")
    result = registry.execute(context, "query_changes", {"service": "backend"})
    assert result.ok and result.records

    async def should_not_execute():
        raise AssertionError("unauthorized explanation executed")

    with pytest.raises(PermissionError, match="local task role"):
        await cache.explain(
            context,
            task,
            result.records,
            registry,
            provider,
            should_not_execute,
            lambda *a, **k: None,
        )


async def test_contradictions_rejected_even_with_maximal_embedding_similarity(tmp_path):
    import numpy as np

    class ConstantEmbedder:
        backend_id = "constant-test-only"

        def embed(self, question):
            return np.array([1.0])

    bundle = setup_local(tmp_path)
    bundle[0].embedder = ConstantEmbedder()
    await explain(bundle, task=bundle[3].model_copy(update={"question": "Is database healthy?"}))
    _, calls, events = await explain(
        bundle, task=bundle[3].model_copy(update={"question": "Is database unhealthy?"})
    )
    assert calls == 1 and events[-1][1]["cache_invalidation_reason"] == "safety_guard"


@pytest.mark.parametrize(
    "left,right",
    [
        ("db causes redis failures", "redis causes db failures"),
        ("not db but redis", "db but not redis"),
        ("db > redis", "redis > db"),
    ],
)
def test_order_reversal_never_equivalent(left, right):
    from incident_lens.cache.embeddings import safe_equivalent

    assert not safe_equivalent(left, right)


def test_extreme_vectors_fail_closed():
    assert cosine([1e308], [1e308]) == 0.0
    assert cosine([float("nan")], [1]) == 0.0
