"""Ablations execute real production adapters, never synthetic outcome rows."""

import importlib.util
import sys
from pathlib import Path

import pytest

from incident_lens.evaluation.reliability_metrics import aggregate_reliability

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "reliability_eval", ROOT / "scripts/run_reliability_eval.py"
)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


@pytest.fixture(scope="module")
def baseline():
    return runner.fixtures.frozen_provider(ROOT)[0]


@pytest.mark.parametrize("scenario", runner.fixtures.SCENARIOS, ids=lambda s: s.case_id)
@pytest.mark.parametrize("variant", ["R0", "R1", "R2", "R3"])
async def test_paired_faults(scenario, variant, baseline):
    row, events, bodies = await runner.fixtures.run_case(scenario, variant, baseline)
    assert runner.expected(row, scenario, variant)
    assert row["actual_http_requests"] == len(bodies)
    assert sum(e["event_type"] == "FIXTURE_HTTP_DISPATCH" for e in events) == len(bodies)
    if scenario.case_id in {"F02", "F04", "F07", "F16", "F14"}:
        assert row["total_tokens"] is None
    if scenario.case_id == "F09" and variant == "R3":
        assert (
            bodies[-1]["messages"][-1]["content"]
            != "Return valid JSON matching the supplied schema. One repair only."
        )
    assert all(body["response_format"]["type"] == "json_schema" for body in bodies)
    assert all(body["model"] == runner.fixtures.MODEL for body in bodies)
    if variant != "R0":
        first_fault = {
            "F02": "RATE_LIMITED",
            "F03": "RATE_LIMITED",
            "F04": "TRANSIENT_SERVER_ERROR",
            "F05": "AUTHENTICATION_FAILED",
            "F06": "INVALID_REQUEST",
            "F07": "TRANSPORT_TIMEOUT",
            "F08": "INVALID_JSON",
            "F09": "SCHEMA_VALIDATION_FAILED",
            "F10": "INVALID_JSON",
            "F17": "RESPONSE_TRUNCATED",
            "F21": "AUTHENTICATION_FAILED",
            "F22": "INVALID_REQUEST",
        }.get(scenario.case_id)
        if first_fault:
            classified = [
                event["category"]
                for event in events
                if event["event_type"] == "PROVIDER_FAILURE_CLASSIFIED"
            ]
            assert classified[0] == first_fault
    if scenario.case_id in {"F31", "F32"}:
        assert row["repair_requests"] == 1
        assert row["total_tokens"] is None
        if variant != "R0":
            assert row["transport_retries"] == (1 if scenario.case_id == "F31" else 2)
            assert sum(event["event_type"] == "STRUCTURED_REPAIR" for event in events) == 1
    safe = str(events)
    assert "Authorization" not in safe and "synthetic" not in safe


def test_unknown_aggregate_and_denominators():
    row = dict(
        scope="provider",
        variant="R3",
        completed=True,
        retryable_fault=True,
        repair_requests=1,
        has_content_response=True,
        first_response_valid=False,
        actual_http_requests=2,
        measured_total_tokens=3,
        total_tokens=None,
    )
    summary = {r["metric"]: r for r in aggregate_reliability([row])}
    assert summary["total_tokens"]["value"] is None
    assert summary["logical_call_success_rate"]["numerator"] == 1
    assert summary["logical_call_success_rate"]["denominator"] == 1
    assert summary["structured_validity_before"]["value"] == 0


async def test_technical_completion_preserves_recovered_and_normal_stops():
    from incident_lens.evaluation.reliability_metrics import technical_completion
    from incident_lens.llm import MockProvider, ProviderError
    from incident_lens.orchestration.graph import run_investigation
    from incident_lens.schemas import Budget
    from incident_lens.schemas.workflow import WorkflowOptions

    class Flaky(MockProvider):
        failed = False

        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[0] == "logs" and args[-1].__name__ == "AnalysisOutput" and not self.failed:
                self.failed = True
                raise ProviderError("INJECTED_CALL_FAILURE", usage)
            return output, usage

    state = await run_investigation(
        "incident_001",
        Flaky(),
        budget=Budget(max_llm_calls=40, max_tool_calls=24),
        workflow=WorkflowOptions(profile="incident_response"),
    )
    assert any(event.event_type == "MODEL_FAILURE" for event in state.events)
    assert any(event.event_type == "MODEL_RECOVERED" for event in state.events)
    assert technical_completion(state)
    broken = state.model_dump(mode="json")
    broken["report"]["termination"]["outcome"] = "FAILED"
    assert not technical_completion(broken)
    incomplete = {"events": [], "report": None}
    assert not technical_completion(incomplete)
    assert technical_completion({"events": [], "report": {"status": "RESOLVED"}})
    assert not technical_completion(
        {"events": [{"event_type": "MODEL_FAILURE"}], "report": {"status": "INCONCLUSIVE"}}
    )
    abstained = await run_investigation(
        "incident_040",
        MockProvider(),
        budget=Budget(max_llm_calls=40, max_tool_calls=24),
        workflow=WorkflowOptions(profile="incident_response"),
    )
    assert technical_completion(abstained)
