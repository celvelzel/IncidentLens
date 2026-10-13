import asyncio

import pytest

from incident_lens.agents.remediation import remediate, root_cause_version, validate_plan
from incident_lens.llm import MockProvider, ProviderError
from incident_lens.schemas.contracts import RCAReport


def report():
    return RCAReport(
        run_id="run",
        incident_id="case",
        status="RESOLVED",
        stop_reason="accepted",
        causal_chain=["resource saturation causes errors"],
        supporting_evidence_ids=["e1"],
        root_cause=dict(
            hypothesis_id="h1",
            culprit_service="backend",
            failure_mode="backend_resource_saturation",
            status="SUPPORTED",
            support_ids=["e1"],
        ),
    )


def evidence():
    return {
        "e1": dict(
            evidence_id="e1",
            incident_id="case",
            source_type="metrics",
            service="backend",
            observed_at="2026-01-01T00:00:00Z",
            source_path="public/metrics.csv",
            excerpt="CPU 99 percent",
        )
    }


@pytest.mark.asyncio
async def test_plan_is_conditioned_complete_and_mock_labeled():
    plan, usage = await remediate(MockProvider(), report(), evidence())
    assert plan.execution_mode == "PLAN_ONLY" and "admission control" in plan.actions[0]
    assert all((plan.preconditions, plan.risks, plan.verification_steps, plan.rollback))
    assert plan.evidence_ids == ["e1"] and usage["source"] == "mock"
    assert len(plan.root_cause_version) == 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,code",
    [
        ("incident_id", "other", "IDENTITY"),
        ("run_id", "other", "IDENTITY"),
        ("root_cause_version", "old", "IDENTITY"),
        ("evidence_ids", ["other"], "CITATION"),
        ("affected_services", ["redis"], "SERVICE"),
    ],
)
async def test_plan_validation(field, value, code):
    plan, _ = await remediate(MockProvider(), report(), evidence())
    with pytest.raises(ProviderError, match=code):
        validate_plan(plan.model_copy(update={field: value}), report(), evidence())


@pytest.mark.asyncio
async def test_inconclusive_and_unobserved_refused():
    inconclusive = RCAReport(
        run_id="run", incident_id="case", status="INCONCLUSIVE", stop_reason="missing"
    )
    with pytest.raises(ProviderError, match="NOT_RESOLVED"):
        await remediate(MockProvider(), inconclusive, evidence())
    with pytest.raises(ProviderError, match="UNOBSERVED"):
        await remediate(MockProvider(), report(), {})


def test_root_version_tracks_contents():
    first = report()
    second = report()
    second.root_cause.failure_mode = "redis_unavailable"
    assert root_cause_version(first) != root_cause_version(second)


@pytest.mark.asyncio
async def test_real_path_and_timeout_owned_by_caller():
    plan, _ = await remediate(MockProvider(), report(), evidence())

    class Provider:
        model_id = "fixture-real-path"

        async def structured_call(self, role, prompt, payload, model):
            assert role == "remediation" and set(payload["evidence_index"]) == {"e1"}
            return plan, {"llm_calls": 1}

    assert (await remediate(Provider(), report(), evidence()))[1]["llm_calls"] == 1

    class Slow(Provider):
        async def structured_call(self, *args):
            await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(remediate(Slow(), report(), evidence()), 0.01)
