import csv
import importlib.util
import json
from pathlib import Path

import pytest

from incident_lens.evaluation import VARIANTS, aggregate, evaluate_split, runner, score_completed
from incident_lens.llm import MockProvider, ProviderError
from incident_lens.schemas import Budget

ROOT = Path(__file__).resolve().parents[2]


def scored_state(status="RESOLVED", mode="correct"):
    return {
        "incident_id": "incident_001",
        "report": {
            "status": status,
            "root_cause": {
                "culprit_service": "backend",
                "failure_mode": mode,
                "support_ids": ["seen", "unseen", "foreign"],
            }
            if status == "RESOLVED"
            else None,
        },
        "evidence_index": {
            "seen": {"incident_id": "incident_001"},
            "unseen": {"incident_id": "incident_001"},
            "foreign": {"incident_id": "incident_002"},
        },
        "events": [
            {
                "event_type": "TOOL_CALL",
                "details": {
                    "result": {"records": [{"evidence_id": "seen", "incident_id": "incident_001"}]}
                },
            }
        ],
    }


def test_metrics_recompute_service_and_failure_mode_and_observed_citations():
    oracle = dict(
        is_identifiable=True,
        culprit_service="backend",
        failure_mode="correct",
        misleading_evidence_ids=["seen"],
    )
    score = score_completed(scored_state(mode="wrong"), oracle)
    assert score["root_cause_correct"] is False
    assert score["misleading_correct"] is False
    assert score["valid_citation_count"] == 1
    assert score["citation_count"] == 3
    assert score["citation_existence_validity"] == pytest.approx(1 / 3)
    assert score["unsupported_claim_rate"] is None
    assert score["semantic_review_status"] == "unreviewed"
    abstention = score_completed(scored_state("INCONCLUSIVE"), {**oracle, "is_identifiable": False})
    assert abstention["correct_abstention"] is True
    assert abstention["root_cause_correct"] is None
    rows = [
        {**score, "variant": "full", "source": "mock", "split": "seed", "status": "RESOLVED"},
        {
            **abstention,
            "variant": "full",
            "source": "mock",
            "split": "seed",
            "status": "INCONCLUSIVE",
        },
    ]
    total = aggregate(rows)[0]
    assert total["identifiable_denominator"] == 1
    assert total["unidentifiable_denominator"] == 1
    assert total["correct_abstention_rate"] == 1
    assert total["total_tokens"] is None


@pytest.mark.asyncio
async def test_actual_all_seed_variants_fairness_oracle_after_run_and_cache_off(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CACHE_MODE", "semantic")
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "historical-hot.sqlite"))
    (tmp_path / "historical-hot.sqlite").write_bytes(b"existing hot cache")
    original_run = runner.run_investigation
    original_oracle = runner.load_oracle_after_run
    finished = []
    made = []
    settings = []

    async def tracked_run(incident_id, provider, **kwargs):
        assert kwargs["cache"] is None
        assert isinstance(provider.delegate, MockProvider)
        settings.append((provider.model_id, provider.temperature, kwargs["budget"].model_dump()))
        state = await original_run(incident_id, provider, **kwargs)
        assert state.report is not None
        finished.append((incident_id, state.run_id))
        return state

    def tracked_oracle(data_root, incident_id, state):
        assert finished[-1] == (incident_id, state["run_id"])
        return original_oracle(data_root, incident_id, state)

    def factory():
        instance = MockProvider()
        made.append(instance)
        return instance

    monkeypatch.setattr(runner, "run_investigation", tracked_run)
    monkeypatch.setattr(runner, "load_oracle_after_run", tracked_oracle)
    rows, totals = await evaluate_split(ROOT / "data", "seed", VARIANTS, factory, tmp_path)
    ids = runner.load_split(ROOT / "data", "seed")
    assert len(rows) == len(ids) * 4 == len(made)
    assert len({id(p) for p in made}) == len(made)
    assert all(setting == settings[0] for setting in settings)
    assert len({row["config_sha256"] for row in rows}) == 1
    for incident_id in ids:
        case_rows = [row for row in rows if row["incident_id"] == incident_id]
        assert len({row["initial_public_sha256"] for row in case_rows}) == 1
    assert all(not r["execution_error"] and not r["evaluation_error"] for r in rows)
    assert all(r["llm_requests"] > 0 and r["tool_calls"] > 0 for r in rows)
    assert all(r["citation_existence_validity"] in (None, 1) for r in rows)
    raw = [json.loads(line) for line in (tmp_path / "raw-runs.jsonl").read_text().splitlines()]
    assert len(raw) == len(rows)
    for run in raw:
        recomputed = score_completed(run["state"], run["oracle_scoring_fields"])
        assert all(run["metrics"][k] == v for k, v in recomputed.items())
        assert run["metrics"]["llm_requests"] == run["state"]["llm_calls_used"]
    full = next(t for t in totals if t["variant"] == "full")
    assert full["root_cause_correct"] == full["identifiable_denominator"] == 5
    assert full["correct_abstentions"] == full["unidentifiable_denominator"] == 1
    with (tmp_path / "case-level.csv").open(newline="") as stream:
        serialized = list(csv.DictReader(stream))
    assert all(
        r["cost_usd"] == r["total_tokens"] == r["unsupported_claim_rate"] == "" for r in serialized
    )


@pytest.mark.asyncio
async def test_failed_actual_requests_remain_measured_and_scored(tmp_path):
    class FailingProvider(MockProvider):
        async def structured_call(self, *args, **kwargs):
            self.request_guard()
            raise ProviderError("PROVIDER_TIMEOUT", {"total_tokens": None})

    rows, totals = await evaluate_split(
        ROOT / "data", "seed", ("full",), FailingProvider, tmp_path, budget=Budget()
    )
    assert all(r["llm_requests"] > 0 and r["failed_model_calls"] > 0 for r in rows)
    assert all(r["total_tokens"] is None for r in rows)
    assert totals[0]["identifiable_denominator"] == 5
    assert totals[0]["root_cause_accuracy"] == 0


def test_real_missing_credentials_fails_before_execution(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "scripts/run_eval.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    for name in ("INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY", "INCIDENT_LENS_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "MockProvider", lambda: pytest.fail("real fell back to mock"))
    assert cli.main(["--provider", "real", "--out", str(tmp_path / "out")]) == 2
    assert json.loads(capsys.readouterr().out) == {"error": "PROVIDER_CONFIGURATION_REQUIRED"}
    assert not (tmp_path / "out").exists()
