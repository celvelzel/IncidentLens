import json
import subprocess
import sys

import pytest

from incident_lens.cli import CONTRACTS


def test_installed_cli_and_schema_export(tmp_path):
    version = subprocess.run(
        [sys.executable, "-m", "incident_lens.cli", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert version.stdout.strip() == "IncidentLens 1.6.1"
    subprocess.run(
        [sys.executable, "-m", "incident_lens.cli", "export-schemas", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(list(tmp_path.glob("*.json"))) == len(CONTRACTS)
    for model in CONTRACTS:
        assert (
            json.loads((tmp_path / f"{model.__name__}.json").read_text())
            == model.model_json_schema()
        )


def test_default_yaml_cache_off_is_a_string_and_runs_offline(tmp_path, monkeypatch):
    from pathlib import Path

    import dotenv
    import yaml

    from incident_lens.cli import main

    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.delenv("CACHE_MODE", raising=False)
    assert yaml.safe_load(Path("configs/system.yaml").read_text())["cache_mode"] == "off"
    assert (
        main(["run", "--case", "incident_001", "--provider", "mock", "--out", str(tmp_path)]) == 0
    )
    assert json.loads((tmp_path / "result.json").read_text())["status"] == "RESOLVED"


@pytest.mark.parametrize("retries", [0, 1])
def test_cli_passes_configured_repair_limit(tmp_path, monkeypatch, retries):
    import dotenv

    import incident_lens.llm.provider as providers
    from incident_lens.cli import main
    from incident_lens.llm.mock import MockProvider

    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.delenv("CACHE_MODE", raising=False)
    captured = []

    def fixture_provider(*args, **kwargs):
        captured.append(kwargs["structured_repair_retries"])
        return MockProvider()

    monkeypatch.setattr(providers, "RealChatProvider", fixture_provider)
    config = tmp_path / "system.yaml"
    config.write_text(f'structured_repair_retries: {retries}\ncache_mode: "off"\n')
    assert (
        main(
            [
                "run",
                "--case",
                "incident_001",
                "--provider",
                "real",
                "--config",
                str(config),
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    assert captured == [retries]
