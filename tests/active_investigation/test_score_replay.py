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
