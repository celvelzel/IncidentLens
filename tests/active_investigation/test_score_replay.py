import asyncio
import sys
from types import SimpleNamespace

import pytest

from incident_lens.evaluation.active_evidence import runner
from incident_lens.evaluation.active_evidence.replay import replay_selection
from incident_lens.evaluation.active_evidence.variants import ActiveProtocol


@pytest.mark.parametrize(
    "split,formal,provider",
    [("test", False, "mock"), ("seed", True, "mock"), ("seed", False, "real")],
)
def test_research_gates_before_provider(tmp_path, monkeypatch, split, formal, provider):
    monkeypatch.setattr(
        runner, "load_cases", lambda *a: (tmp_path, tmp_path, [SimpleNamespace(incident_id="i")])
    )

    def forbidden():
        raise AssertionError("provider must not be constructed")

    with pytest.raises(ValueError, match="BLOCKED"):
        asyncio.run(
            runner.run_experiment(
                tmp_path,
                split,
                forbidden,
                tmp_path / "out",
                ActiveProtocol(formal=formal, provider_id=provider),
            )
        )
    assert not (tmp_path / "out").exists()


def test_empty_split_before_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "load_cases", lambda *a: (tmp_path, tmp_path, []))
    with pytest.raises(ValueError, match="empty split"):
        asyncio.run(
            runner.run_experiment(tmp_path, "dev", lambda: None, tmp_path / "out", ActiveProtocol())
        )


def test_invalid_replay_does_not_import_selector(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "incident_lens.orchestration.active_investigation.selector", None
    )
    with pytest.raises(ValueError):
        replay_selection({"visible": {"private_oracle": "forbidden"}})


@pytest.mark.parametrize("envelope", ["list", "state", "artifact"])
def test_replay_cli_normal_envelopes(tmp_path, monkeypatch, capsys, envelope):
    import importlib.util
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "replay_v15_selection.py"
    spec = importlib.util.spec_from_file_location("replay_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    events = [
        {"event_type": "ACTION_SELECTED", "details": {"decision": "one"}},
        {"event_type": "STOP", "details": {}},
    ]
    value = events if envelope == "list" else {"events": events}
    if envelope == "artifact":
        value = {"state": value, "metadata": {"source": "mock"}}
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps(value))
    monkeypatch.setattr(cli, "replay_selection", lambda details: {"match": True, **details})
    monkeypatch.setattr(sys, "argv", ["replay_v15_selection.py", "--trace", str(trace)])
    cli.main()
    assert json.loads(capsys.readouterr().out) == [{"match": True, "decision": "one"}]


@pytest.fixture
def real_case(monkeypatch):
    from pathlib import Path

    dataset = Path(__file__).resolve().parents[2] / "data" / "incidentbench_v1"
    root, public, cases = runner.load_cases(dataset, "seed")
    monkeypatch.setattr(runner, "load_cases", lambda *args: (root, public, cases[:1]))
    return dataset


async def test_completed_resume_no_provider_and_exact_bytes(tmp_path, real_case):
    from incident_lens.llm import MockProvider

    protocol = ActiveProtocol(variants=["B1", "B4"])
    out = tmp_path / "out"
    first = await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    def forbidden():
        raise AssertionError("completed resume must not construct a provider")

    second = await runner.run_experiment(real_case, "seed", forbidden, out, protocol, resume=True)
    assert first == second
    assert before == {
        p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }


async def test_cancelled_durable_not_rerun(tmp_path, real_case, monkeypatch):
    import json

    from incident_lens.llm import MockProvider

    protocol = ActiveProtocol(variants=["B1", "B4"])
    out = tmp_path / "out"
    graph = runner.run_investigation

    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(runner, "run_investigation", cancel)
    with pytest.raises(asyncio.CancelledError):
        await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    raw_before = (out / "raw-runs.jsonl").read_bytes()
    calls = []

    async def counted(*args, **kwargs):
        calls.append(kwargs["run_id"])
        return await graph(*args, **kwargs)

    monkeypatch.setattr(runner, "run_investigation", counted)
    rows = await runner.run_experiment(real_case, "seed", MockProvider, out, protocol, resume=True)
    assert len(calls) == 1 and len(rows) == 2
    assert (out / "raw-runs.jsonl").read_bytes().startswith(raw_before)
    first = json.loads(raw_before.splitlines()[0])
    assert first["run_id"] not in calls
    assert rows[0]["technical_completion"] is False


async def test_started_orphan_retained_unknown_without_provider_rerun(
    tmp_path, real_case, monkeypatch
):
    import json

    from incident_lens.llm import MockProvider

    protocol = ActiveProtocol(variants=["B1", "B4"])
    out = tmp_path / "out"
    original_append = runner.append

    class ProcessDeath(BaseException):
        pass

    def crash(path, value):
        original_append(path, value)
        if value.get("status") == "STARTED":
            raise ProcessDeath()

    monkeypatch.setattr(runner, "append", crash)
    with pytest.raises(ProcessDeath):
        await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    monkeypatch.setattr(runner, "append", original_append)
    calls = []

    def factory():
        calls.append(1)
        return MockProvider()

    rows = await runner.run_experiment(real_case, "seed", factory, out, protocol, resume=True)
    raw = [json.loads(line) for line in (out / "raw-runs.jsonl").read_text().splitlines()]
    assert len(calls) == 1 and len(rows) == 2
    assert raw[0]["usage"]["total_tokens"] is None
    assert raw[0]["usage"]["actual_http_requests"] is None
    assert raw[0]["state"]["execution_error"]["code"] == "INTERRUPTED"


async def test_resume_refuses_partial_jsonl_unchanged(tmp_path, real_case):
    from incident_lens.llm import MockProvider

    out = tmp_path / "out"
    protocol = ActiveProtocol(variants=["B1"])
    await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    path = out / "raw-runs.jsonl"
    path.write_bytes(path.read_bytes() + b'{"partial":')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        await runner.run_experiment(
            real_case, "seed", lambda: pytest.fail("provider called"), out, protocol, resume=True
        )
    assert path.read_bytes() == before


@pytest.mark.parametrize("tamper", ["protocol", "manifest", "state", "progress", "raw_source"])
async def test_resume_rejects_drift_and_foreign_ledgers(tmp_path, real_case, tamper):
    import json

    from incident_lens.llm import MockProvider

    out = tmp_path / "out"
    protocol = ActiveProtocol(variants=["B1"])
    await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    # Exercise prefix checks without relying only on the completed aggregate digest.
    (out / "artifact-digests.json").unlink()
    if tamper == "protocol":
        protocol = ActiveProtocol(variants=["B1"], max_rounds=5)
    elif tamper == "manifest":
        path = out / "manifest.json"
        value = json.loads(path.read_bytes())
        value["source_sha256"] = "bad"
        path.write_text(json.dumps(value))
    elif tamper == "state":
        path = next((out / "states").iterdir())
        value = json.loads(path.read_bytes())
        value["run_id"] = "foreign"
        path.write_text(json.dumps(value))
    elif tamper == "progress":
        path = out / "progress.jsonl"
        values = [json.loads(line) for line in path.read_text().splitlines()]
        values[0]["run_id"] = "foreign"
        path.write_text("".join(json.dumps(v) + "\n" for v in values))
    else:
        path = out / "raw-runs.jsonl"
        values = [json.loads(line) for line in path.read_text().splitlines()]
        values[0]["source"] = "model"
        path.write_text("".join(json.dumps(v) + "\n" for v in values))
    before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        await runner.run_experiment(
            real_case, "seed", lambda: pytest.fail("provider called"), out, protocol, resume=True
        )
    assert before == {
        p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }


async def test_saved_raw_missing_score_and_durable_progress_recovered(tmp_path, real_case):
    import json

    from incident_lens.llm import MockProvider

    out = tmp_path / "out"
    protocol = ActiveProtocol(variants=["B4"])
    await runner.run_experiment(real_case, "seed", MockProvider, out, protocol)
    (out / "artifact-digests.json").unlink()
    (out / "scores.jsonl").write_bytes(b"")
    progress = json.loads((out / "progress.jsonl").read_bytes().splitlines()[0])
    (out / "progress.jsonl").write_text(json.dumps(progress) + "\n")
    original = (out / "raw-runs.jsonl").read_bytes()

    def forbidden():
        raise AssertionError("saved raw must never rerun")

    rows = await runner.run_experiment(real_case, "seed", forbidden, out, protocol, resume=True)
    assert len(rows) == 1 and rows[0]["technical_completion"]
    assert (out / "raw-runs.jsonl").read_bytes() == original
    assert len((out / "progress.jsonl").read_bytes().splitlines()) == 2
    assert len((out / "scores.jsonl").read_bytes().splitlines()) == 1
