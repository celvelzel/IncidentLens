"""Saved trace scoring and all evaluator entrypoints share one classification."""

import hashlib
import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import pytest

from incident_lens.evaluation.metrics import score_completed, score_without_oracle
from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path("scripts") / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_rescore_preserves_input_and_all_scores(tmp_path):
    module = script("rescore_eval")
    state = await run_investigation(
        "incident_001",
        MockProvider(),
        budget=Budget(max_llm_calls=32, max_tool_calls=24),
        workflow=WorkflowOptions(profile="incident_response"),
    )
    state = state.model_dump(mode="json")
    oracle = json.loads(Path("data/incidents/incident_001/private/ground_truth.json").read_text())
    source = tmp_path / "input" / "raw-runs.jsonl"
    source.parent.mkdir()
    source.write_text(
        json.dumps(
            dict(
                state=state,
                oracle_scoring_fields=oracle,
                metrics={"variant": "full", "runtime_failure": True},
            )
        )
        + "\n"
    )
    original = source.read_bytes()
    out = tmp_path / "rescored"
    manifest = module.rescore(source, out)
    saved = json.loads((out / "raw-runs.jsonl").read_text())
    assert manifest["input_sha256"] == hashlib.sha256(original).hexdigest()
    assert not manifest["provider_executed"] and manifest["scoring_version"] == "2"
    assert source.read_bytes() == original and saved["state"] == state
    assert saved["historical_metrics"]["runtime_failure"] is True
    for key, value in score_completed(state, oracle).items():
        assert saved["metrics"][key] == value
    with pytest.raises(ValueError, match="new output"):
        module.rescore(source, out)
    with pytest.raises(ValueError, match="separate"):
        module.rescore(source, source.parent)


async def test_v12_saved_scores_equal_direct_scores_and_rescore(tmp_path):
    module = script("run_v12_eval")
    args = Namespace(
        data_root=Path("data"),
        out=tmp_path / "runs",
        split="seed",
        incidents=["incident_001"],
        skip_legacy=True,
        inject_transient_failure=True,
        provider="mock",
        max_rounds=6,
        max_tool_calls=24,
        max_llm_calls=32,
        max_wall_seconds=600,
    )
    rows = await module.evaluate(args, module.TransientFailureMock)
    saved = [json.loads(line) for line in (args.out / "raw-runs.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    for record, row in zip(saved, rows):
        score = score_completed(record["state"], record["oracle_scoring_fields"])
        for key, value in score.items():
            assert row[key] == value
        assert row["failed_calls"] == row["recovered_model_failure_count"] == 1
        assert row["root_cause_correct"] and row["workflow_success"]
    script("rescore_eval").rescore(args.out / "raw-runs.jsonl", tmp_path / "rescored")
    rescored = [
        json.loads(line) for line in (tmp_path / "rescored/raw-runs.jsonl").read_text().splitlines()
    ]
    assert [r["metrics"] for r in rescored] == rows


def test_execution_error_with_oracle_keeps_failure_denominator():
    state = {"incident_id": "case", "events": [], "report": {"status": "ERROR", "root_cause": None}}
    oracle = {"is_identifiable": False, "culprit_service": "api", "failure_mode": "timeout"}
    score = score_completed(state, oracle)
    assert score["runtime_failure"] and score["correct_abstention"] is False
    assert score["workflow_success"] is False
    unknown = score_without_oracle(state)
    assert unknown["runtime_failure"] and unknown["workflow_success"] is False
    assert unknown["root_cause_correct"] is unknown["correct_abstention"] is None


def test_unreadable_oracle_keeps_unknown_quality_and_execution_facts(tmp_path):
    source = tmp_path / "trace.json"
    state = {
        "incident_id": "incident_999",
        "events": [],
        "report": {"status": "ERROR", "root_cause": None},
    }
    source.write_text(json.dumps({"state": state}))
    out = tmp_path / "rescored"
    manifest = script("rescore_eval").rescore(source, out, tmp_path / "missing-data")
    row = json.loads((out / "raw-runs.jsonl").read_text())["metrics"]
    assert manifest["evaluation_errors"] == 1 and row["evaluation_error"]
    assert row["root_cause_correct"] is row["correct_abstention"] is None
    assert row["runtime_failure"] and row["scoring_version"] == "2"
