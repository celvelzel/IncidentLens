"""Actual offline CLI reproduction with disclosed development-only inputs."""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from test_generation import development_config

ROOT = Path(__file__).resolve().parents[2]


def cli(script, *args, success=True):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if success:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout + result.stderr
    return result


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_fresh_cli_build_validate_mock_recompute_and_refuse_overwrite(tmp_path):
    config = development_config()
    config["families"] = config["families"][:1]
    config["families"][0]["variants"] = [
        v for v in config["families"][0]["variants"] if v["kind"] in ("ordinary", "missing")
    ]
    spec = tmp_path / "development.json"
    spec.write_text(json.dumps(config), encoding="utf-8")
    dataset, labels = tmp_path / "dataset", tmp_path / "labels"
    build_args = ("--config", spec, "--out", dataset, "--oracle-root", labels)
    coverage = json.loads(cli("build_incidentbench.py", *build_args).stdout)
    assert coverage["total_cases"] == 2 and coverage["accepted_labels"] == 0
    for mode in ("public", "privileged"):
        args = ["--dataset", dataset, "--mode", mode]
        if mode == "privileged":
            args += ["--oracle-root", labels]
        assert json.loads(cli("validate_incidentbench.py", *args).stdout)["ok"]
    before = snapshot(dataset)
    cli("build_incidentbench.py", *build_args, success=False)
    assert snapshot(dataset) == before

    runs = tmp_path / "runs"
    run_args = (
        "--dataset",
        dataset,
        "--split",
        "seed",
        "--variant",
        "all",
        "--provider",
        "mock",
        "--cache-mode",
        "off",
        "--jobs",
        "1",
        "--oracle-root",
        labels,
        "--out",
        runs,
    )
    assert json.loads(cli("run_incidentbench.py", *run_args).stdout)["runs"] == 8
    raw = [json.loads(line) for line in (runs / "raw-runs.jsonl").read_text().splitlines()]
    scores = [json.loads(line) for line in (runs / "scores.jsonl").read_text().splitlines()]
    assert len({r["run_key"] for r in raw}) == 8
    assert all(r["source"] == "mock" and r["state"]["completion_receipt"] for r in raw)
    identifiable = [r for r in scores if r["root_cause_correct"] is not None]
    assert len(identifiable) == 4
    assert next(r for r in identifiable if r["variant"] == "full")["root_cause_correct"]
    assert all(r["technical_completion"] for r in scores)
    assert sum(r["correct_abstention"] is True for r in scores) == 4
    assert all(r["human_support_rate"] is None for r in scores)
    assert all(r["human_grounded_success"] is None for r in scores)
    saved = snapshot(runs)
    cli("run_incidentbench.py", *run_args, success=False)
    assert snapshot(runs) == saved

    analysis = tmp_path / "analysis"
    analyze_args = ("--input", runs / "raw-runs.jsonl", "--oracle-root", labels, "--out", analysis)
    assert json.loads(cli("analyze_incidentbench.py", *analyze_args).stdout)["recomputed_runs"] == 8
    with (runs / "case-level.csv").open(newline="", encoding="utf-8") as handle:
        original = list(csv.DictReader(handle))
    with (analysis / "case-level.csv").open(newline="", encoding="utf-8") as handle:
        recomputed = list(csv.DictReader(handle))
    assert original == recomputed
    assert (runs / "aggregate.json").read_bytes() == (analysis / "aggregate.json").read_bytes()
    assert snapshot(runs) == saved
    saved_analysis = snapshot(analysis)
    cli("analyze_incidentbench.py", *analyze_args, success=False)
    assert snapshot(analysis) == saved_analysis
