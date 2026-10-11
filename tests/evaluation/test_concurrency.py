import asyncio
import csv
import importlib.util
import json
from pathlib import Path

import pytest

from incident_lens.evaluation import VARIANTS, evaluate_split, runner, score_completed
from incident_lens.llm import MockProvider

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_bounded_actual_runs_persist_and_match_serial(tmp_path, monkeypatch):
    serial, serial_totals = await evaluate_split(
        ROOT / "data", "seed", VARIANTS, MockProvider, tmp_path / "serial"
    )
    monkeypatch.setenv("CACHE_MODE", "semantic")
    original = runner.run_investigation
    oracle = runner.load_oracle_after_run
    active = maximum = 0
    finished = set()
    observed_partial_save = []
    delegates = []
    budgets = []
    out = tmp_path / "parallel"

    async def tracked(incident_id, provider, **kwargs):
        nonlocal active, maximum
        assert kwargs["cache"] is None
        delegates.append(provider.delegate)
        budgets.append(kwargs["budget"])
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.005)
        if finished:
            saved = (out / "raw-runs.jsonl").read_text().splitlines()
            with (out / "case-level.csv").open(newline="") as stream:
                saved_csv = list(csv.DictReader(stream))
            assert len(saved) == len(saved_csv) == len(finished)
            observed_partial_save.append(len(saved))
        state = await original(incident_id, provider, **kwargs)
        active -= 1
        finished.add(state.run_id)
        return state

    def after_run(data_root, incident_id, state):
        assert state["run_id"] in finished
        return oracle(data_root, incident_id, state)

    monkeypatch.setattr(runner, "run_investigation", tracked)
    monkeypatch.setattr(runner, "load_oracle_after_run", after_run)
    rows, totals = await evaluate_split(ROOT / "data", "seed", VARIANTS, MockProvider, out, jobs=2)
    assert len(rows) == 24
    assert maximum == 2
    assert observed_partial_save and max(observed_partial_save) < 24
    assert len({id(p) for p in delegates}) == 24
    assert len({id(b) for b in budgets}) == 24
    assert all(not r["execution_error"] and not r["evaluation_error"] for r in rows)
    assert [(r["incident_id"], r["variant"]) for r in rows] == sorted(
        (r["incident_id"], r["variant"]) for r in rows
    )
    ignored = {"latency_ms", "config_sha256", "jobs"}
    assert [{k: v for k, v in r.items() if k not in ignored} for r in rows] == [
        {k: v for k, v in r.items() if k not in ignored} for r in serial
    ]
    assert [{k: v for k, v in r.items() if k != "latency_ms"} for r in totals] == [
        {k: v for k, v in r.items() if k != "latency_ms"} for r in serial_totals
    ]
    raw = [json.loads(line) for line in (out / "raw-runs.jsonl").read_text().splitlines()]
    assert [r["metrics"] for r in raw] == rows
    for record in raw:
        assert record["fairness"]["jobs"] == 2
        scores = score_completed(record["state"], record["oracle_scoring_fields"])
        assert all(record["metrics"][k] == v for k, v in scores.items())
    with (out / "case-level.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 24


@pytest.mark.asyncio
@pytest.mark.parametrize("jobs", [0, 5, -1, True, 1.5, "2"])
async def test_invalid_jobs_rejected(tmp_path, jobs):
    with pytest.raises(ValueError, match="jobs"):
        await evaluate_split(ROOT / "data", "seed", VARIANTS, MockProvider, tmp_path, jobs=jobs)


@pytest.mark.asyncio
async def test_reused_provider_rejected_without_losing_completed_runs(tmp_path):
    shared = MockProvider()
    with pytest.raises(ValueError, match="independent provider"):
        await evaluate_split(ROOT / "data", "seed", VARIANTS, lambda: shared, tmp_path)
    assert len((tmp_path / "raw-runs.jsonl").read_text().splitlines()) == 1
    with (tmp_path / "case-level.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 1


def test_validation_failures_count_without_double_counting():
    measured = runner.MeasuredProvider(MockProvider())
    measured.calls = [{"failed": True, "usage": {}}]
    state = {"events": [{"event_type": "MODEL_FAILURE"}, {"event_type": "MODEL_FAILURE"}]}
    usage = runner.usage_metrics(measured, state)
    assert usage["provider_failures"] == 1
    assert usage["failed_model_calls"] == usage["failed_calls"] == 2


def test_cli_invalid_jobs_before_dotenv(tmp_path):
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "scripts/run_eval.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--out", str(tmp_path), "--jobs", "5"])
    assert exc.value.code == 2


@pytest.mark.asyncio
async def test_cancelled_parallel_calls_count_only_their_own_requests():
    class ConcurrentDelegate:
        model_id = "fixture"
        temperature = 0

        async def structured_call(self, role, *args):
            self.request_guard()
            await asyncio.sleep(0)
            if role == "repair":
                self.request_guard()
            await asyncio.Event().wait()

    measured = runner.MeasuredProvider(ConcurrentDelegate())
    tasks = [
        asyncio.create_task(measured.structured_call(role, "", {}, None))
        for role in ("one", "two", "repair")
    ]
    while measured.actual_requests < 4:
        await asyncio.sleep(0)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    assert sorted(call["usage"]["llm_calls"] for call in measured.calls) == [1, 1, 2]
    assert sum(call["usage"]["llm_calls"] for call in measured.calls) == 4
    assert all(call["failed"] for call in measured.calls)
    assert measured._call_requests.get() == 0
