"""Runtime STOP traces remain scored failures, including inconclusive reports."""

import pytest

from incident_lens.evaluation.metrics import aggregate, score_completed


def completed(events, status="INCONCLUSIVE"):
    return {
        "incident_id": "case",
        "events": events,
        "report": {
            "status": status,
            "root_cause": (
                {"culprit_service": "api", "failure_mode": "timeout"}
                if status == "RESOLVED"
                else None
            ),
        },
    }


def oracle(identifiable):
    return {
        "is_identifiable": identifiable,
        "culprit_service": "api",
        "failure_mode": "timeout",
        "misleading_evidence_ids": ["decoy"],
    }


@pytest.mark.parametrize(
    "reason",
    [
        "TimeoutError",
        "Invalid model output",
        "ValidationError",
        "Tool budget exhausted",
    ],
)
@pytest.mark.parametrize("identifiable", [False, True])
def test_stop_failure_retains_denominator(reason, identifiable):
    state = completed([{"event_type": "STOP", "message": reason}])
    score = score_completed(state, oracle(identifiable))
    assert score["runtime_failure"] is True
    assert score["root_cause_correct"] is (False if identifiable else None)
    assert score["correct_abstention"] is (None if identifiable else False)
    assert state["report"]["status"] == "INCONCLUSIVE"
    row = dict(score, variant="full", source="synthetic", split="dev", status="INCONCLUSIVE")
    result = aggregate([row])[0]
    assert result["runtime_failure_runs"] == 1
    assert result["error_runs"] == 0
    assert result["identifiable_denominator"] == int(identifiable)
    assert result["unidentifiable_denominator"] == int(not identifiable)
    assert result["misleading_identifiable_denominator"] == int(identifiable)
    assert result["root_cause_correct"] == result["correct_abstentions"] == 0


def test_explicit_abstain_without_stop_receives_credit():
    score = score_completed(
        completed([{"event_type": "COORDINATE", "details": {"action": "ABSTAIN"}}]), oracle(False)
    )
    assert score["runtime_failure"] is False
    assert score["correct_abstention"] is True
    row = dict(score, variant="full", source="synthetic", split="dev", status="INCONCLUSIVE")
    result = aggregate([row])[0]
    assert result["runtime_failure_runs"] == 0
    assert result["correct_abstention_rate"] == 1


def test_resolved_matching_root_with_stop_receives_no_credit():
    score = score_completed(completed([{"event_type": "STOP"}], "RESOLVED"), oracle(True))
    assert score["runtime_failure"] is True
    assert score["root_cause_correct"] is False
    assert score["misleading_correct"] is False


def test_historical_model_failure_without_stop_receives_no_abstention_credit():
    score = score_completed(completed([{"event_type": "MODEL_FAILURE"}]), oracle(False))
    assert score["runtime_failure"] is True and score["correct_abstention"] is False


async def test_verifier_timeout_emits_stop_and_is_not_correct_abstention():
    from incident_lens.llm import MockProvider, ProviderError
    from incident_lens.orchestration.graph import run_investigation

    class FailedReview(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            if args[-1].__name__ == "Review":
                raise ProviderError("PROVIDER_TIMEOUT", usage)
            return output, usage

    state = await run_investigation("incident_006", FailedReview())
    assert any(e.event_type == "STOP" and e.details.get("stage") == "verify" for e in state.events)
    assert (
        score_completed(state.model_dump(mode="json"), oracle(False))["correct_abstention"] is False
    )
