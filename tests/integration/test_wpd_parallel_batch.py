"""Offline supervisor tests: no provider, credentials, or model calls."""

import json
from argparse import Namespace

import pytest

from incident_lens.incidentbench.schemas import ExperimentProtocol
from scripts import run_wpd_batch as batch


@pytest.mark.parametrize("mode,cap", [("bridge", 4), ("api", 8), ("subscription", 8)])
def test_mode_caps(mode, cap):
    for jobs in range(1, cap + 1):
        assert batch.validate_concurrency(mode, jobs) == jobs
    for jobs in [0, cap + 1, True, 1.5, "2"]:
        with pytest.raises(ValueError):
            batch.validate_concurrency(mode, jobs)


@pytest.mark.parametrize("jobs", [True, "4", 2.5, 0, 9])
def test_protocol_rejects_invalid_jobs(jobs):
    with pytest.raises(ValueError):
        ExperimentProtocol(jobs=jobs)


def harness(tmp_path, monkeypatch, mode, cap, fail=False, stop=False):
    (tmp_path / "batch-state.json").write_text('{"slots": {}}')
    order = [{"incident": f"incident_{i}", "variant": "full", "repeat": 0}
             for i in range(cap + 3)]
    manifest = {"plan": {"mode": mode, "dataset": "data", "protocol": "p.json",
                         "runtime_config": "r.yaml", "subscription_config": "s.json",
                         "feasibility": "receipt.json"}, "order": order,
                "protocol": {"max_wall_seconds": 100, "jobs": cap}, "max_concurrency": cap}
    clock = [0]
    processes = []
    peak = [0]

    class Process:
        def __init__(self, command, **kwargs):
            self.number = len(processes)
            self.pid = 100 + self.number
            # First lane finishes later, exercising out-of-order completion.
            self.end = clock[0] + (3 if self.number == 0 else 1)
            self.code = 1 if fail and self.number == 1 else 0
            self.command = command
            processes.append(self)
            peak[0] = max(peak[0], sum(p.poll() is None for p in processes))

        def poll(self):
            return self.code if clock[0] >= self.end else None

    def sleep(seconds):
        clock[0] += 1
        if stop:
            (tmp_path / "STOP_REQUESTED").touch()

    monkeypatch.setattr(batch.subprocess, "Popen", Process)
    monkeypatch.setattr(batch.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(batch.time, "sleep", sleep)
    monkeypatch.setattr(batch, "frozen_inputs", lambda *a: manifest)
    monkeypatch.setattr(batch, "assess", lambda *a: "completed")
    monkeypatch.setattr(batch, "artifact_hashes", lambda *a: {n: "hash" for n in batch.OUTPUT_FILES})
    monkeypatch.setattr(batch, "digest", lambda *a: "hash")
    monkeypatch.setattr(batch, "stop_child", lambda p: setattr(p, "end", clock[0]))
    args = Namespace(out=tmp_path, plan=tmp_path / "plan.json", readiness=tmp_path / "ready.json",
                     resume=False, retry_failed=False, retry_interrupted=False)
    return args, manifest, processes, peak


@pytest.mark.parametrize("mode,cap", [("bridge", 4), ("api", 8), ("subscription", 8)])
def test_parallel_pool_out_of_order_and_resume(tmp_path, monkeypatch, mode, cap):
    args, manifest, processes, peak = harness(tmp_path, monkeypatch, mode, cap)
    assert batch.execute(args, manifest) == 0
    assert peak[0] == cap
    assert len(processes) == cap + 3
    commands = [p.command for p in processes]
    assert len({c[c.index("--out") + 1] for c in commands}) == cap + 3
    assert all(("--readiness" in c) == (mode == "api") for c in commands)
    if mode == "subscription":
        assert all("--execute-development-case" in c and "--feasibility" in c for c in commands)
        assert all("--runtime-config" not in c for c in commands)
        assert all(c[3].endswith("run_codex_subscription_case.py") for c in commands)
        assert len({c[c.index("--lease-directory") + 1] for c in commands}) == cap + 3
    events = [json.loads(line) for line in (tmp_path / "batch-events.jsonl").read_text().splitlines()]
    ended = [e["slot"] for e in events if e["event"] == "SLOT_ENDED"]
    assert ended.index("slot-002") < ended.index("slot-001")
    args.resume = True
    assert batch.execute(args, manifest) == 0
    assert len(processes) == cap + 3  # Completed receipts never start another worker.


@pytest.mark.parametrize("mode,cap", [("bridge", 4), ("api", 8), ("subscription", 8)])
def test_failure_drains_siblings_without_dispatch(tmp_path, monkeypatch, mode, cap):
    args, manifest, processes, peak = harness(tmp_path, monkeypatch, mode, cap, fail=True)
    assert batch.execute(args, manifest) == 1
    assert len(processes) == cap
    state = json.loads((tmp_path / "batch-state.json").read_text())
    assert state["slots"]["slot-001"][-1]["status"] == "completed"
    assert state["slots"]["slot-002"][-1]["status"] == "failed"


def test_stop_records_every_active_worker(tmp_path, monkeypatch):
    args, manifest, processes, peak = harness(tmp_path, monkeypatch, "api", 8, stop=True)
    monkeypatch.setattr(batch, "assess", lambda *a: (_ for _ in ()).throw(ValueError("no output")))
    assert batch.execute(args, manifest) == 130
    assert len(processes) == 8
    state = json.loads((tmp_path / "batch-state.json").read_text())
    assert all(a[-1]["status"] == "interrupted" for a in state["slots"].values())
    status = json.loads((tmp_path / "supervisor-status.json").read_text())
    assert status["active"] == []


def test_input_drift_stops_active_workers_before_next_dispatch(tmp_path, monkeypatch):
    args, manifest, processes, peak = harness(tmp_path, monkeypatch, "api", 8)
    checks = [0]

    def frozen(*unused):
        checks[0] += 1
        return manifest if checks[0] <= 2 else {}

    monkeypatch.setattr(batch, "frozen_inputs", frozen)
    with pytest.raises(ValueError, match="input drift"):
        batch.execute(args, manifest)
    assert len(processes) == 2
    assert all(p.poll() is not None for p in processes)
    status = json.loads((tmp_path / "supervisor-status.json").read_text())
    assert status["state"] == "batch_stopped"
    assert status["active"] == []


def test_frozen_concurrency_must_match_protocol(tmp_path, monkeypatch):
    args, manifest, processes, peak = harness(tmp_path, monkeypatch, "api", 8)
    manifest["protocol"]["jobs"] = 4
    with pytest.raises(ValueError, match="does not match"):
        batch.execute(args, manifest)
    assert not processes
