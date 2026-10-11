import json
import subprocess
import sys

from incident_lens.cli import CONTRACTS


def test_installed_cli_and_schema_export(tmp_path):
    version = subprocess.run(
        [sys.executable, "-m", "incident_lens.cli", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert version.stdout.strip() == "IncidentLens 0.1.0"
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
