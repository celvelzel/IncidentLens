"""A scoring-resource error must survive replay without inventing answer quality."""

import json
import os
import subprocess
import sys
from pathlib import Path

from test_experiment_fairness import build_fixture

from incident_lens.incidentbench import experiment
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm import MockProvider


async def test_replay_preserves_invalid_oracle_errors_and_failure_denominators(
    tmp_path, monkeypatch
):
    dataset, oracle = build_fixture(tmp_path)
    for path in oracle.rglob("benchmark_oracle.json"):
        path.write_text("invalid candidate label", encoding="utf-8")

    async def failed_graph(*args, **kwargs):
        raise RuntimeError("synthetic graph failure")

    monkeypatch.setattr(experiment, "run_investigation", failed_graph)
    runs = tmp_path / "runs"
    rows = await experiment.run_experiment(
        dataset,
        "seed",
        MockProvider,
        runs,
        ExperimentProtocol(model_id=MockProvider.model_id, bootstrap_samples=10),
        oracle,
    )
    assert len(rows) == 8 and all(row["score_error"] == "PermissionError" for row in rows)
    assert all(
        row["root_cause_correct"] is None and not row["technical_completion"] for row in rows
    )
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/analyze_incidentbench.py"),
            "--input",
            str(runs / "raw-runs.jsonl"),
            "--oracle-root",
            str(oracle),
            "--out",
            str(tmp_path / "analysis"),
        ],
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((runs / "aggregate.json").read_bytes()) == json.loads(
        (tmp_path / "analysis/aggregate.json").read_bytes()
    )
