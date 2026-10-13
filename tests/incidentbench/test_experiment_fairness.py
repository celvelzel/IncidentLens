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


class SimulatedCrash(BaseException):
    pass


async def test_resume_last_raw_before_score_requires_zero_graph_calls(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    out = tmp_path / "last-score-partial"
    original_append = experiment.append
    scores = 0

    def crash_last_score(path, value):
        nonlocal scores
        if path.name == "scores.jsonl":
            scores += 1
            if scores == 8:
                raise SimulatedCrash()
        original_append(path, value)

    monkeypatch.setattr(experiment, "append", crash_last_score)
    with pytest.raises(SimulatedCrash):
        await experiment.run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    before = (out / "raw-runs.jsonl").read_bytes()
    monkeypatch.setattr(experiment, "append", original_append)

    def forbidden():
        raise AssertionError("post-durable recovery must make zero provider/Graph calls")

    rows = await experiment.run_experiment(
        dataset, "seed", forbidden, out, protocol, oracle, resume=True
    )
    assert len(rows) == 8
    assert (out / "raw-runs.jsonl").read_bytes() == before


async def test_resume_raw_before_score_no_completed_graph_reexecution(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    out = tmp_path / "raw-partial"
    real_append, real_graph = experiment.append, experiment.run_investigation
    executed = []

    async def tracked(*args, **kwargs):
        executed.append(kwargs["run_id"])
        return await real_graph(*args, **kwargs)

    def crash_before_score(path, value):
        if path.name == "scores.jsonl":
            raise SimulatedCrash()
        real_append(path, value)

    monkeypatch.setattr(experiment, "run_investigation", tracked)
    monkeypatch.setattr(experiment, "append", crash_before_score)
    with pytest.raises(SimulatedCrash):
        await experiment.run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    initial_raw = (out / "raw-runs.jsonl").read_bytes()
    completed_id = executed[0]
    monkeypatch.setattr(experiment, "append", real_append)
    rows = await experiment.run_experiment(
        dataset, "seed", MockProvider, out, protocol, oracle, resume=True
    )
    assert len(rows) == 8 and len(executed) == 8
    assert executed.count(completed_id) == 1
    assert (out / "raw-runs.jsonl").read_bytes().startswith(initial_raw)
    before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    def forbidden_factory():
        raise AssertionError("completed resume must construct no provider")

    assert (
        await experiment.run_experiment(
            dataset, "seed", forbidden_factory, out, protocol, oracle, resume=True
        )
        == rows
    )
    assert before == {
        p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError, match="lock drift"):
        await experiment.run_experiment(
            dataset,
            "seed",
            forbidden_factory,
            out,
            protocol.model_copy(update={"run_order_seed": 99}),
            oracle,
            resume=True,
        )


async def test_resume_started_without_state_retains_failure_unknown_usage(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    out = tmp_path / "started-partial"
    real_append = experiment.append

    def crash_after_started(path, value):
        real_append(path, value)
        if path.name == "progress.jsonl" and value.get("status") == "STARTED":
            raise SimulatedCrash()

    monkeypatch.setattr(experiment, "append", crash_after_started)
    with pytest.raises(SimulatedCrash):
        await experiment.run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    monkeypatch.setattr(experiment, "append", real_append)
    factory_calls = []

    def factory():
        factory_calls.append(True)
        return MockProvider()

    rows = await experiment.run_experiment(
        dataset, "seed", factory, out, protocol, oracle, resume=True
    )
    assert len(rows) == 8 and len(factory_calls) == 7
    assert rows[0]["technical_completion"] is False
    assert rows[0]["actual_http_requests"] is None
    assert rows[0]["total_tokens"] is None and rows[0]["latency_ms"] is None
    assert all(
        rows[0][field] is None
        for field in (
            "llm_requests",
            "logical_structured_calls",
            "task_retries",
            "transport_retries",
            "repair_requests",
            "failed_calls",
            "provider_failures",
            "failed_model_calls",
            "failed_tool_calls",
            "prompt_tokens",
            "completion_tokens",
            "cost_usd",
        )
    )
    raw = [json.loads(line) for line in (out / "raw-runs.jsonl").read_text().splitlines()]
    assert raw[0]["state"]["execution_error"]["code"] == "INTERRUPTED"
    assert rows[0]["failure_category"] == "INTERRUPTED"
    assert len({r["run_key"] for r in raw}) == 8


async def test_resume_receipt_tamper_and_existing_output_refuse(tmp_path, monkeypatch):
    from incident_lens.incidentbench import experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    out = tmp_path / "tampered-partial"
    real_append = experiment.append

    def crash_before_score(path, value):
        if path.name == "scores.jsonl":
            raise SimulatedCrash()
        real_append(path, value)

    monkeypatch.setattr(experiment, "append", crash_before_score)
    with pytest.raises(SimulatedCrash):
        await experiment.run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    monkeypatch.setattr(experiment, "append", real_append)

    def forbidden():
        raise AssertionError("tampered resume must not execute")

    with pytest.raises(FileExistsError):
        await experiment.run_experiment(dataset, "seed", forbidden, out, protocol, oracle)
    state_path = next((out / "states").glob("*.json"))
    state_path.write_text("{}")
    with pytest.raises(ValueError, match="receipt mismatch"):
        await experiment.run_experiment(
            dataset, "seed", forbidden, out, protocol, oracle, resume=True
        )


@pytest.mark.parametrize("artifact", ["case-level.csv", "reproducibility.txt", "coverage.json"])
async def test_completed_resume_rejects_derived_tamper(tmp_path, artifact):
    from incident_lens.incidentbench.experiment import run_experiment

    dataset, oracle = build_fixture(tmp_path)
    protocol = ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10)
    out = tmp_path / "complete"
    await run_experiment(dataset, "seed", MockProvider, out, protocol, oracle)
    path = out / artifact
    path.write_bytes(path.read_bytes() + b" ")
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    def forbidden():
        raise AssertionError("tampered completed resume must not construct a provider")

    # Whitespace alone preserves JSON meaning, so change its value as well.
    if artifact.endswith(".json"):
        value = json.loads(path.read_bytes())
        value["run_n"] += 1
        path.write_text(json.dumps(value))
        before[path.relative_to(out)] = path.read_bytes()
    with pytest.raises(ValueError, match="mismatch"):
        await run_experiment(dataset, "seed", forbidden, out, protocol, oracle, resume=True)
    assert before == {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}


def test_execution_lock_refuses_concurrent_process_and_nonfile(tmp_path):
    import os
    import subprocess
    import sys

    from incident_lens.incidentbench.experiment import execution_lock

    code = (
        "from pathlib import Path; import sys; "
        "from incident_lens.incidentbench.experiment import execution_lock; "
        "manager = execution_lock(Path(sys.argv[1])); manager.__enter__(); manager.__exit__(None,None,None)"
    )
    with execution_lock(tmp_path):
        result = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        assert result.returncode != 0 and "concurrent resume refused" in result.stderr
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    (tmp_path / ".execution.lock").unlink()
    (tmp_path / ".execution.lock").mkdir()
    with pytest.raises(PermissionError, match="regular file"):
        with execution_lock(tmp_path):
            pytest.fail("directory lock accepted")


def test_partial_jsonl_retained_without_truncation(tmp_path):
    from incident_lens.incidentbench.experiment import read_jsonl

    path = tmp_path / "progress.jsonl"
    raw = b'{"status":"STARTED"}\n{"status":'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="partial JSONL"):
        read_jsonl(path)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("surface", ["dataset", "lock"])
def test_link_paths_refused_before_resolve(tmp_path, surface):
    import os
    import subprocess

    from incident_lens.incidentbench.experiment import dataset_paths, execution_lock

    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    link = output / (".execution.lock" if surface == "lock" else "dataset")
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(
            PermissionError, match="unsafe evaluator path|evaluator resource unavailable"
        ):
            if surface == "dataset":
                dataset_paths(link)
            else:
                with execution_lock(output):
                    pytest.fail("linked lock accepted")
        assert list(target.iterdir()) == []
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
