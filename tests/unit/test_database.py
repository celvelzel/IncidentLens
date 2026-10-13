import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest

from incident_lens.agents.service import AnalysisOutput
from incident_lens.cache import CachePolicy, SemanticCacheAdapter
from incident_lens.schemas import Finding, InvestigationTask
from incident_lens.security.context import DATABASE_TOOLS
from incident_lens.tools import EvidenceProvider, ToolRegistry


def setup(role="database", *, equivalent=False, incident="incident_037", root="data"):
    provider = EvidenceProvider(root)
    registry = ToolRegistry(
        provider, "test", incident, "run-db", database_equivalent_tools=equivalent
    )
    context = registry.create_context(role)
    case = provider.load_case(incident)
    args = {
        "service": "postgres",
        "start_ts": (case.started_at - timedelta(minutes=10)).isoformat(),
        "end_ts": (case.started_at + timedelta(minutes=10)).isoformat(),
    }
    return provider, registry, context, args


@pytest.mark.parametrize(
    "role", ["logs", "metrics", "changes", "single", "coordinator", "verifier", "reporter"]
)
def test_database_acl_denied_by_default(role):
    _, registry, context, args = setup(role)
    assert registry.execute(context, "get_db_connections", args).error_code == "FORBIDDEN"
    assert registry.call_count == 0


@pytest.mark.parametrize("role", ["metrics", "single"])
def test_equivalent_tools_explicitly_enabled(role):
    _, registry, context, args = setup(role, equivalent=True)
    result = registry.execute(context, "get_db_connections", args)
    assert result.ok and result.records[0].metadata["connection_count"] == 100


def test_database_category_windows_budget_and_publish():
    _, registry, context, args = setup(incident="incident_039")
    records = []
    for name in DATABASE_TOOLS:
        result = registry.execute(context, name, args)
        assert result.ok
        records += result.records
    assert {r.metadata["category"] for r in records} == {
        "connections",
        "lock_waits",
        "slow_queries",
    }
    assert registry.call_count == 5
    registry.publish(context, [r.evidence_id for r in records])
    with pytest.raises(PermissionError):
        registry.publish(context, ["guessed-id"])
    assert registry.execute(context, "query_logs", args).error_code == "FORBIDDEN"
    assert (
        registry.execute(
            context, "get_db_connections", {**args, "sql": "DROP TABLE users"}
        ).error_code
        == "BAD_ARGS"
    )
    assert (
        registry.execute(
            context, "get_db_connections", {**args, "end_ts": args["start_ts"]}
        ).records
        == []
    )


def test_registry_freeze_blocks_inflight_ledger_and_new_authority(monkeypatch):
    from incident_lens.tools.registry import HANDLERS

    provider, registry, context, args = setup()
    started, release = Event(), Event()

    def delayed(*_):
        started.set()
        assert release.wait(3)
        return provider._records("incident_037", "database")

    monkeypatch.setitem(HANDLERS, "get_db_connections", delayed)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(registry.execute, context, "get_db_connections", args)
        assert started.wait(3)
        registry.freeze()
        release.set()
        assert future.result().error_code == "FORBIDDEN"
    assert registry.observed_ids(context) == set()
    assert registry.execute(context, "get_db_connections", args).error_code == "FORBIDDEN"
    with pytest.raises(PermissionError):
        registry.create_context("database")
    with pytest.raises(PermissionError):
        registry.publish(context, [])


def test_missing_database_is_optional_and_unsafe_path_is_not(tmp_path):
    shutil.copytree("data/incidents/incident_001", tmp_path / "incidents/incident_001")
    shutil.copytree("data/topology", tmp_path / "topology")
    provider = EvidenceProvider(tmp_path)
    assert provider._records("incident_001", "database") == []
    path = tmp_path / "incidents/incident_001/public/database.jsonl"
    path.mkdir()
    with pytest.raises(OSError):
        provider._records("incident_001", "database")


def test_optional_database_symlink_rejected(tmp_path):
    shutil.copytree("data/incidents/incident_037", tmp_path / "incidents/incident_037")
    path = tmp_path / "incidents/incident_037/public/database.jsonl"
    path.unlink()
    try:
        path.symlink_to(tmp_path / "missing-private-target")
    except OSError:
        pytest.skip("host does not permit symlink creation")
    with pytest.raises(PermissionError):
        EvidenceProvider(tmp_path)._records("incident_037", "database")


@pytest.mark.parametrize(
    "incident,category,value",
    [
        ("incident_037", "connections", 100),
        ("incident_038", "connections", 12),
        ("incident_039", "lock_waits", 45000),
        ("incident_040", "connections", None),
    ],
)
def test_four_database_scenarios(incident, category, value):
    _, registry, context, args = setup(incident=incident)
    name = "get_db_" + category
    result = registry.execute(context, name, args)
    assert result.ok
    if value is None:
        assert result.records == []
    else:
        assert (
            result.records[0].metadata.get(
                "connection_count", result.records[0].metadata.get("duration_ms")
            )
            == value
        )


@pytest.mark.parametrize(
    "mutation", ["source", "path", "incident", "service", "metadata", "category"]
)
def test_database_provenance_and_answer_metadata_rejected(tmp_path, mutation):
    shutil.copytree("data/incidents/incident_037", tmp_path / "incidents/incident_037")
    path = tmp_path / "incidents/incident_037/public/database.jsonl"
    record = json.loads(path.read_text().splitlines()[0])
    if mutation == "metadata":
        record["metadata"]["failure_mode"] = "oracle_answer"
    elif mutation == "category":
        record["metadata"]["category"] = "sql_execute"
    else:
        key = {
            "source": "source_type",
            "path": "source_path",
            "incident": "incident_id",
            "service": "service",
        }[mutation]
        record[key] = {
            "source": "logs",
            "path": "private/ground_truth.json",
            "incident": "incident_038",
            "service": "unknown",
        }[mutation]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        EvidenceProvider(tmp_path)._records("incident_037", "database")


def test_database_cache_namespace_authorization_and_snapshot(tmp_path):
    provider, registry, context, args = setup()
    records = registry.execute(context, "get_db_connections", args).records
    task = InvestigationTask(
        task_id="task-db",
        role="database",
        question="Inspect connections",
        allowed_tools=["get_db_connections"],
        reason="Check capacity",
        expected_discriminator="Measured capacity",
    )
    cache = SemanticCacheAdapter(CachePolicy(mode="exact"), tmp_path / "cache.db", "dataset-test")
    assert cache._authorize(context, task, records, registry) == {records[0].evidence_id}
    model = type("Model", (), {"model_id": "test", "temperature": 0})()
    namespace = cache.namespace(context, task, records, model)
    assert namespace.agent_role == "database"
    assert namespace.task_type == "interpret_database_window"
    modified = records[0].model_copy(deep=True)
    modified.metadata["connection_count"] = 1
    with pytest.raises(PermissionError):
        cache._authorize(context, task, [modified], registry)
    assert (
        cache.namespace(context, task, [modified], model).evidence_snapshot_sha256
        != namespace.evidence_snapshot_sha256
    )
    assert provider.validate_public() == []


async def test_database_cache_hit_and_incident_partition(tmp_path):
    _, registry, context, args = setup()
    records = registry.execute(context, "get_db_connections", args).records
    task = InvestigationTask(
        task_id="task-db",
        role="database",
        question="Inspect connections",
        allowed_tools=["get_db_connections"],
        reason="Check capacity",
        expected_discriminator="Measured capacity",
    )
    cache = SemanticCacheAdapter(CachePolicy(mode="exact"), tmp_path / "cache.db", "dataset-test")
    model = type("Model", (), {"model_id": "test", "temperature": 0})()
    calls = []

    async def execute():
        calls.append(1)
        return AnalysisOutput(
            finding=Finding(
                finding_id="finding-db",
                task_id=task.task_id,
                run_id=context.run_id,
                incident_id=context.incident_id,
                role="database",
                claim="Connections reach measured capacity",
                evidence_ids=[records[0].evidence_id],
                relation="supports",
                confidence_qualifier="supported",
            ),
            hypotheses=[],
        )

    events = []
    for _ in range(2):
        await cache.explain(
            context,
            task,
            records,
            registry,
            model,
            execute,
            lambda kind, **details: events.append(kind),
        )
    assert calls == [1] and events == ["CACHE_MISS", "CACHE_HIT"]
    _, other_registry, other_context, other_args = setup(incident="incident_038")
    other_records = other_registry.execute(other_context, "get_db_connections", other_args).records
    assert cache.namespace(context, task, records, model) != cache.namespace(
        other_context, task, other_records, model
    )
