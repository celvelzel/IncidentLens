import json

import pytest

from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.incidentbench.experiment import durable_write, run_order
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm import MockProvider
from incident_lens.llm.provider import LLMProvider, ProviderError


def test_order_seeded_unique_complete():
    protocol = ExperimentProtocol(repeats=2)
    order = run_order(["incident_001", "incident_002"], protocol)
    assert len(order) == len(set(order)) == 16
    assert order == run_order(["incident_001", "incident_002"], protocol)
    assert order != run_order(
        ["incident_001", "incident_002"], protocol.model_copy(update={"run_order_seed": 1})
    )


def test_durable_state_no_overwrite(tmp_path):
    path = tmp_path / "state.json"
    durable_write(path, {"run_id": "r"})
    assert json.loads(path.read_text()) == {"run_id": "r"}
    with pytest.raises(FileExistsError):
        durable_write(path, {"run_id": "other"})


class FailedProvider(LLMProvider):
    async def structured_call(self, *args):
        for _ in range(3):
            self.request_guard()
        raise ProviderError("HTTP_429", {"transport_retries": 1, "repair_requests": 1})


async def test_physical_retries_repairs_unknown_tokens():
    measured = MeasuredProvider(FailedProvider())
    with pytest.raises(ProviderError):
        await measured.structured_call("coordinator", "", {}, None)
    usage = usage_metrics(measured, {"events": []})
    assert usage["actual_http_requests"] == 3
    assert usage["logical_structured_calls"] == 1
    assert usage["transport_retries"] == usage["repair_requests"] == 1
    assert usage["total_tokens"] is None


def build_fixture(tmp_path):
    from incident_lens.incidentbench.builder import build_dataset

    dataset, oracle = tmp_path / "dataset", tmp_path / "labels"
    build_dataset(
        {
            "families": [
                dict(
                    id="fam_001",
                    source_blueprint_id="blueprint_001",
                    near_duplicate_cluster_id="cluster_001",
                    split="seed",
                    started_at="2026-10-01T12:00:00+00:00",
                    mechanism="backend_pool_config_regression",
                    trigger_seconds=10,
                    propagation_seconds=4,
                    demand=120,
                    capacity=100,
                    variants=[
                        dict(id="ordinary", kind="ordinary"),
                        dict(id="missing", kind="missing"),
                    ],
                )
            ]
        },
        dataset,
        oracle,
    )
    return dataset, oracle


async def test_actual_four_graph_runs_durable_before_scoring_fresh_output(tmp_path):
    from incident_lens.incidentbench.experiment import run_experiment

    dataset, oracle = build_fixture(tmp_path)
    out = tmp_path / "runs"
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=30)
    rows = await run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    assert len(rows) == 8
    assert all(r["score_error"] is None and r["label_status"] == "provisional" for r in rows)
    assert all(r["total_tokens"] is None for r in rows)
    raw = [json.loads(line) for line in (out / "raw-runs.jsonl").read_text().splitlines()]
    assert len({r["run_key"] for r in raw}) == 8
    fixed = [r for r in raw if r["variant"] == "fixed_four_equivalent_tools"]
    assert all(
        [t["role"] for t in r["state"]["tasks"]] == ["logs", "metrics", "database", "changes"]
        for r in fixed
    )
    assert all(r["state"]["events"] for r in raw)
    # Reanalysis executes a standalone script, with no provider construction.
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "analyze_incidentbench.py"
    command = [
        sys.executable,
        str(script),
        "--input",
        str(out / "raw-runs.jsonl"),
        "--oracle-root",
        str(oracle),
        "--out",
        str(tmp_path / "analysis"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "analysis" / "aggregate.json").read_text()) == json.loads(
        (out / "aggregate.json").read_text()
    )
    label_path = next(oracle.rglob("benchmark_oracle.json"))
    label_bytes = label_path.read_bytes()
    changed_label = json.loads(label_bytes)
    changed_label["review_version"] = "changed-after-experiment"
    label_path.write_text(json.dumps(changed_label))
    changed = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
    assert changed.returncode != 0 and "oracle label digest mismatch" in changed.stderr
    label_path.write_bytes(label_bytes)
    # Changed raw bytes must be rejected even when the completion files still exist.
    with (out / "raw-runs.jsonl").open("a") as stream:
        stream.write("\n")
    rejected = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
    assert rejected.returncode != 0 and "digest mismatch" in rejected.stderr
    with pytest.raises(FileExistsError):
        await run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)


async def test_graph_exception_keeps_known_failure_denominators(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)

    async def fail(*args, **kwargs):
        raise RuntimeError("private error not exported")

    monkeypatch.setattr(experiment, "run_investigation", fail)
    rows = await experiment.run_experiment(
        dataset,
        "seed",
        MockProvider,
        tmp_path / "failed",
        ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10),
        oracle,
    )
    assert sum(r["identifiable"] is True for r in rows) == 4
    assert all(r["root_cause_correct"] is False for r in rows if r["identifiable"])
    assert all(r["correct_abstention"] is False for r in rows if not r["identifiable"])
    assert all(r["technical_completion"] is False for r in rows)


async def test_formal_fails_closed(tmp_path):
    from incident_lens.incidentbench.experiment import run_experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(formal=True, provider_id="real", model_id="actual-real-model")
    with pytest.raises(ValueError, match="formal experiment"):
        await run_experiment(dataset, "seed", MockProvider, tmp_path / "formal", protocol, oracle)


async def test_development_test_never_loads_oracle_and_empty_split_refuses(tmp_path, monkeypatch):
    from incident_lens.incidentbench.experiment import run_experiment
    from incident_lens.incidentbench.oracle_store import OracleStore

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    with pytest.raises(ValueError, match="empty split"):
        await run_experiment(dataset, "dev", MockProvider, tmp_path / "empty", protocol, oracle)
    index_path = dataset / "public_case_index.json"
    index = json.loads(index_path.read_text())
    for case in index:
        case["split"] = "test"
    index_path.write_text(json.dumps(index))
    (dataset / "rca/splits/test_ids.json").write_bytes(
        (dataset / "rca/splits/seed_ids.json").read_bytes()
    )
    (dataset / "rca/splits/seed_ids.json").write_text("[]")
    from incident_lens.incidentbench.manifest import digest_tree

    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["rca_public_sha256"] = digest_tree(dataset / "rca")
    manifest_path.write_text(json.dumps(manifest))

    def forbidden(*args, **kwargs):
        raise AssertionError("Test label read forbidden")

    monkeypatch.setattr(OracleStore, "load_after_completion", forbidden)
    rows = await run_experiment(
        dataset, "test", MockProvider, tmp_path / "unscored", protocol, oracle
    )
    assert len(rows) == 8
    assert all(
        row["root_cause_correct"] is None and row["label_status"] == "unscored" for row in rows
    )


async def test_post_graph_dataset_drift_durable_then_abort(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)
    original = experiment.run_investigation

    async def drift(*args, **kwargs):
        state = await original(*args, **kwargs)
        (dataset / "coverage.json").write_text("changed during execution")
        return state

    monkeypatch.setattr(experiment, "run_investigation", drift)
    out = tmp_path / "drifted"
    with pytest.raises(ValueError, match="protocol mismatch after Graph"):
        await experiment.run_experiment(
            dataset,
            "seed",
            MockProvider,
            out,
            ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10),
            oracle,
        )
    saved = [json.loads(line) for line in (out / "raw-runs.jsonl").read_text().splitlines()]
    assert len(saved) == 1
    assert saved[0]["state"]["events"]
    assert saved[0]["state"]["execution_error"]["code"] == "PROTOCOL_MISMATCH"
    assert "ABORTED" in (out / "errors.jsonl").read_text()


async def test_public_answer_metadata_refused_before_provider(tmp_path):
    from incident_lens.incidentbench.experiment import run_experiment
    from incident_lens.incidentbench.manifest import digest_tree

    dataset, oracle = build_fixture(tmp_path)
    index_path = dataset / "public_case_index.json"
    index = json.loads(index_path.read_text())
    public = dataset / "rca/incidents" / index[0]["incident_id"] / "public"
    log = public / "logs.jsonl"
    text = log.read_text()
    log.write_text(text.replace("Request completed", "root_cause_code Request completed"))
    index[0]["public_sha256"] = digest_tree(public)
    index_path.write_text(json.dumps(index))
    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["rca_public_sha256"] = digest_tree(dataset / "rca")
    manifest_path.write_text(json.dumps(manifest))

    def forbidden():
        raise AssertionError("provider must not be constructed")

    with pytest.raises(ValueError, match="public benchmark audit"):
        await run_experiment(
            dataset,
            "seed",
            forbidden,
            tmp_path / "runs",
            ExperimentProtocol(model_id=MockProvider.model_id),
            oracle,
        )
    assert not (tmp_path / "runs").exists()
