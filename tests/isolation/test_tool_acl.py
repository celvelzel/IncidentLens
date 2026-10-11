import importlib.util
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from time import sleep

import pytest

from incident_lens.security.context import ROLE_TOOL_ACL, AgentContext
from incident_lens.tools import EvidenceProvider, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction boundary")
def test_public_junction_is_refused(tmp_path):
    root = tmp_path / "data"
    private = root / "incidents/incident_001/private"
    private.mkdir(parents=True)
    public = private.parent / "public"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(public), str(private)], capture_output=True
    )
    if result.returncode:
        pytest.skip("host does not permit creating a junction")
    try:
        provider = EvidenceProvider(root)
        with pytest.raises(PermissionError):
            provider.load_case("incident_001")
    finally:
        public.rmdir()


def test_timeout_deadline_does_not_publish_late_results(provider, monkeypatch):
    registry = ToolRegistry(provider, "w", "incident_001", "r", timeout_seconds=0.01)
    context = registry.create_context("logs")
    original = provider._records

    def slow(*args):
        sleep(0.06)
        return original(*args)

    monkeypatch.setattr(provider, "_records", slow)
    result = registry.execute(context, "query_logs", log_args(provider))
    assert result.error_code == "TIMEOUT"
    sleep(0.1)
    assert registry.observed_ids(context) == set()
    assert registry.shared_records() == {}


@pytest.fixture
def provider():
    return EvidenceProvider(ROOT / "data")


@pytest.fixture
def registry(provider):
    return ToolRegistry(provider, "workspace", "incident_001", "run-1", max_tool_calls=50)


def log_args(provider, **updates):
    start = provider.load_case("incident_001").started_at
    return (
        dict(
            service="backend",
            start_ts=(start - timedelta(minutes=10)).isoformat(),
            end_ts=(start + timedelta(minutes=15)).isoformat(),
        )
        | updates
    )


def test_issued_context_positive_query_and_stable_ids(registry, provider):
    context = registry.create_context("logs")
    first = registry.execute(context, "query_logs", log_args(provider))
    second = registry.client(context).execute("query_logs", log_args(provider))
    assert first.ok and first.record_count > 0
    assert [item.evidence_id for item in first.records] == [
        item.evidence_id for item in second.records
    ]
    assert registry.observed_ids(context) == {item.evidence_id for item in first.records}
    assert all(item.source_path == "public/logs.jsonl" for item in first.records)


@pytest.mark.parametrize("role", list(ROLE_TOOL_ACL))
def test_every_role_denies_tools_outside_acl(registry, provider, role):
    context = registry.create_context(role)
    for tool in ROLE_TOOL_ACL["single"]:
        if tool not in ROLE_TOOL_ACL[role]:
            result = registry.execute(context, tool, log_args(provider))
            assert result.error_code == "FORBIDDEN" and result.records == []
    assert registry.call_count == 0


def test_equal_clone_and_model_construct_are_not_issued(registry, provider):
    issued = registry.create_context("logs")
    clone = AgentContext.model_validate_json(issued.model_dump_json())
    assert issued == clone and issued is not clone
    forged = AgentContext.model_construct(**issued.model_dump())
    for spoof in (clone, forged, issued.model_copy(update={"role": "single"})):
        assert registry.execute(spoof, "query_logs", log_args(provider)).error_code == "FORBIDDEN"
        with pytest.raises(PermissionError):
            registry.observed_ids(spoof)


def test_forced_context_mutation_is_detected(registry, provider):
    context = registry.create_context("logs")
    object.__setattr__(context, "allowed_tools", ROLE_TOOL_ACL["single"])
    assert registry.execute(context, "query_changes", {}).error_code == "FORBIDDEN"
    assert registry.execute(context, "query_logs", log_args(provider)).error_code == "FORBIDDEN"


@pytest.mark.parametrize(
    "workspace,incident,run",
    [
        ("other", "incident_001", "run-1"),
        ("workspace", "incident_002", "run-1"),
        ("workspace", "incident_001", "other-run"),
    ],
)
def test_foreign_contexts_cannot_cross_registry_boundary(
    provider, registry, workspace, incident, run
):
    foreign = ToolRegistry(provider, workspace, incident, run).create_context("logs")
    assert registry.execute(foreign, "query_logs", log_args(provider)).error_code == "FORBIDDEN"


@pytest.mark.parametrize(
    "updates",
    [
        {"path": "../private/ground_truth.json"},
        {"incident_id": "incident_002"},
        {"service": "../private"},
        {"limit": 51},
        {"limit": "5"},
        {"start_ts": "2026-10-01T00:00:00"},
        {"start_ts": "not-a-time"},
        {"severity": "IGNORE_ACL"},
    ],
)
def test_bad_arguments_do_not_read_files(registry, provider, updates):
    context = registry.create_context("logs")
    assert (
        registry.execute(context, "query_logs", log_args(provider, **updates)).error_code
        == "BAD_ARGS"
    )
    assert registry.observed_ids(context) == set()


def test_inverted_window_and_unknown_service(registry, provider):
    context = registry.create_context("logs")
    args = log_args(provider)
    assert (
        registry.execute(
            context, "query_logs", args | {"end_ts": args["start_ts"], "start_ts": args["end_ts"]}
        ).error_code
        == "BAD_ARGS"
    )
    assert (
        registry.execute(context, "query_logs", args | {"service": "not-present"}).error_code
        == "NOT_FOUND"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "ground_truth.json",
        "../private/ground_truth.json",
        "/etc/passwd",
        "logs.jsonl/../incident.json",
    ],
)
def test_provider_fixed_filename_allowlist(provider, filename):
    with pytest.raises(PermissionError):
        provider._public_path("incident_001", filename)
    with pytest.raises(PermissionError):
        provider.load_case("../incident_001")
    with pytest.raises(PermissionError):
        provider._records("incident_001", "private")


def test_public_symlink_is_refused(tmp_path):
    root = tmp_path / "data"
    shutil.copytree(ROOT / "data", root)
    target = root / "incidents/incident_001/public/logs.jsonl"
    target.unlink()
    try:
        target.symlink_to(root / "incidents/incident_001/private/ground_truth.json")
    except OSError:
        pytest.skip("host does not permit creating symlinks")
    provider = EvidenceProvider(root)
    with pytest.raises(PermissionError):
        provider._records("incident_001", "logs")


def test_private_oracle_never_loaded_and_not_part_of_revision(tmp_path):
    root = tmp_path / "data"
    shutil.copytree(ROOT / "data", root)
    provider = EvidenceProvider(root)
    before = provider.dataset_revision
    for path in root.glob("incidents/*/private/ground_truth.json"):
        path.write_text("PRIVATE_SENTINEL_INVALID_JSON", encoding="utf-8")
    assert provider.dataset_revision == before
    assert provider.validate_public() == []
    registry = ToolRegistry(provider, "w", "incident_001", "r")
    result = registry.execute(registry.create_context("single"), "query_logs", log_args(provider))
    assert result.ok and "PRIVATE_SENTINEL" not in result.model_dump_json()


def test_publish_requires_queried_ids_and_shared_fetch(registry, provider):
    logs = registry.create_context("logs")
    changes = registry.create_context("changes")
    verifier = registry.create_context("verifier")
    result = registry.execute(logs, "query_logs", log_args(provider, limit=1))
    evidence_id = result.records[0].evidence_id
    assert (
        registry.execute(verifier, "fetch_evidence_by_ids", {"ids": [evidence_id]}).error_code
        == "FORBIDDEN"
    )
    for ids in ([evidence_id], ["incident_002-L001"], ["invented"]):
        with pytest.raises(PermissionError):
            registry.publish(changes, ids)
    registry.publish(logs, [evidence_id])
    fetched = registry.execute(verifier, "fetch_evidence_by_ids", {"ids": [evidence_id]})
    assert fetched.ok and fetched.records == result.records
    assert (
        registry.execute(
            verifier, "fetch_evidence_by_ids", {"ids": [evidence_id, "unseen"]}
        ).error_code
        == "FORBIDDEN"
    )


def test_ledger_and_shared_records_are_defensive_copies(registry, provider):
    context = registry.create_context("logs")
    result = registry.execute(context, "query_logs", log_args(provider, limit=1))
    original = result.records[0].excerpt
    evidence_id = result.records[0].evidence_id
    result.records[0].excerpt = "forged caller edit"
    assert registry.get_observed_records(context)[0].excerpt == original
    registry.publish(context, [evidence_id])
    copy = registry.shared_records()
    copy[evidence_id].excerpt = "forged shared edit"
    assert registry.shared_records()[evidence_id].excerpt == original


def test_only_returned_records_enter_ledger_and_record_cap(registry, provider):
    context = registry.create_context("logs")
    result = registry.execute(context, "query_logs", log_args(provider, limit=1))
    assert result.record_count == 1 and result.next_cursor == "1"
    assert len(registry.observed_ids(context)) == 1
    other = next(
        record
        for record in provider._records("incident_001", "logs")
        if record.evidence_id not in registry.observed_ids(context)
    )
    with pytest.raises(PermissionError):
        registry.publish(context, [other.evidence_id])


def test_single_can_fetch_own_observations_without_publication(registry, provider):
    single = registry.create_context("single")
    evidence_id = (
        registry.execute(single, "query_logs", log_args(provider, limit=1)).records[0].evidence_id
    )
    assert registry.execute(single, "fetch_evidence_by_ids", {"ids": [evidence_id]}).ok
    assert registry.shared_records() == {}


def test_parallel_global_budget_is_atomic(provider):
    registry = ToolRegistry(provider, "w", "incident_001", "r", max_tool_calls=3)
    contexts = [registry.create_context("logs") for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(
            executor.map(
                lambda context: registry.execute(context, "query_logs", log_args(provider)),
                contexts,
            )
        )
    assert sum(result.ok for result in results) == 3
    assert sum(result.error_code == "BUDGET_EXCEEDED" for result in results) == 9
    assert registry.call_count == 3


def test_parallel_incidents_do_not_share_ledgers(provider):
    registries = [
        ToolRegistry(provider, "w", incident, f"run-{index}")
        for index, incident in enumerate(("incident_001", "incident_002"))
    ]
    contexts = [registry.create_context("single") for registry in registries]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda pair: pair[0].execute(pair[1], "query_changes", {}),
                zip(registries, contexts),
            )
        )
    for index, result in enumerate(results):
        assert result.ok and all(
            record.incident_id == f"incident_{index + 1:03d}" for record in result.records
        )
        ids = [record.evidence_id for record in result.records]
        registries[index].publish(contexts[index], ids)
        assert (
            registries[1 - index].execute(contexts[index], "query_changes", {}).error_code
            == "FORBIDDEN"
        )
    assert set(registries[0].shared_records()).isdisjoint(registries[1].shared_records())


def test_prompt_injection_remains_data_and_events_do_not_echo_payload(registry, provider):
    logs = registry.create_context("logs")
    result = registry.execute(
        logs, "query_logs", log_args(provider, contains="override permissions")
    )
    assert result.ok and len(result.records) == 1
    assert "read private/ground_truth.json" in result.records[0].excerpt
    assert (
        registry.execute(logs, "get_config_diff", {"change_id": "change-1-01"}).error_code
        == "FORBIDDEN"
    )
    assert "override permissions" not in json.dumps(registry.events)
    assert registry.shared_records() == {}


def test_timeout_returns_safe_error_and_spends_budget(registry, provider, monkeypatch):
    context = registry.create_context("logs")

    def timeout(*args):
        raise TimeoutError("secret-file-detail")

    monkeypatch.setattr(provider, "_records", timeout)
    result = registry.execute(context, "query_logs", log_args(provider))
    assert result.error_code == "TIMEOUT" and result.records == []
    assert registry.call_count == 1
    assert "secret-file-detail" not in json.dumps(registry.events)


def test_metrics_configs_and_dependencies_positive(registry, provider):
    metrics = registry.create_context("metrics")
    args = log_args(provider) | {"metric_names": []}
    result = registry.execute(metrics, "query_metrics", args | {"service": "postgres"})
    assert result.ok and {record.metadata["metric_name"] for record in result.records} >= {
        "cpu_percent",
        "connections_active",
        "max_connections",
    }
    topology = registry.execute(metrics, "get_dependencies", {"service": "backend"})
    assert topology.records[0].metadata["dependencies"] == ["postgres", "redis", "payment"]
    changes = registry.create_context("changes")
    diff = registry.execute(changes, "get_config_diff", {"change_id": "change-1-01"})
    assert diff.ok and "DB_POOL_MAX: 64 -> 2" in diff.records[0].excerpt
    assert (
        registry.execute(changes, "get_config_diff", {"change_id": "missing"}).error_code
        == "NOT_FOUND"
    )


def test_dataset_validator_and_revision(provider, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "dataset_validator", ROOT / "scripts/validate_dataset.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate_dataset(ROOT / "data") == []
    root = tmp_path / "data"
    shutil.copytree(ROOT / "data", root)
    copy = EvidenceProvider(root)
    before = copy.dataset_revision
    path = root / "incidents/incident_001/public/logs.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace("pool wait queue", "local wait queue"),
        encoding="utf-8",
    )
    assert copy.dataset_revision != before
    oracle = root / "incidents/incident_001/private/ground_truth.json"
    truth = json.loads(oracle.read_text(encoding="utf-8"))
    truth["decisive_evidence_ids"] = ["invented"]
    oracle.write_text(json.dumps(truth), encoding="utf-8")
    assert any("invalid oracle evidence" in item for item in module.validate_dataset(root))
