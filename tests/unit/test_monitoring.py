import asyncio

import pytest

from incident_lens.agents.monitoring import monitor
from incident_lens.llm import MockProvider, ProviderError
from incident_lens.schemas.workflow import IncidentAlert


def observation(eid="e1", value=2, minute=0):
    return dict(
        evidence_id=eid,
        incident_id="case",
        source_type="metrics",
        service="backend",
        observed_at=f"2026-01-01T00:{minute:02d}:00Z",
        source_path="public/metrics.csv",
        excerpt="health measurement",
        metadata={"metric_name": "cpu_percent", "value": value},
    )


@pytest.mark.asyncio
async def test_normal_and_empty_no_alert():
    for records in ([], [observation()]):
        alert, usage = await monitor(MockProvider(), "case", records, "manual_snapshot")
        assert alert.status == "NO_ALERT" and not alert.affected_services
        assert usage["source"] == "mock"


@pytest.mark.asyncio
async def test_replay_stops_before_future_record():
    alert, usage = await monitor(
        MockProvider(),
        "case",
        [observation("future", 99, 2), observation("first", 95, 1), observation()],
        "offline_replay",
    )
    assert alert.evidence_ids == ["first"] and usage["observed_records"] == 2
    assert alert.affected_services == ["backend"]


class Provider:
    model_id = "fixture-real-path"

    def __init__(self, **changes):
        self.changes = changes
        self.payloads = []

    async def structured_call(self, role, prompt, payload, model):
        assert role == "monitoring"
        self.payloads.append(payload)
        return IncidentAlert(
            **(
                dict(
                    incident_id="case",
                    status="ALERT",
                    summary="anomaly",
                    evidence_ids=["e1"],
                    affected_services=["backend"],
                )
                | self.changes
            )
        ), {"llm_calls": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,code",
    [
        ({"incident_id": "other"}, "IDENTITY"),
        ({"evidence_ids": ["future"]}, "CITATION"),
        ({"affected_services": ["redis"]}, "SERVICE"),
    ],
)
async def test_real_output_boundaries(changes, code):
    with pytest.raises(ProviderError, match=code):
        await monitor(Provider(**changes), "case", [observation()], "manual_snapshot")


@pytest.mark.asyncio
async def test_input_identity():
    with pytest.raises(ProviderError, match="INPUT_IDENTITY"):
        await monitor(MockProvider(), "other", [observation()], "manual_snapshot")


@pytest.mark.asyncio
async def test_real_replay_only_supplies_prefix():
    provider = Provider()
    await monitor(provider, "case", [observation(), observation("future", 99, 1)], "offline_replay")
    assert [r["evidence_id"] for r in provider.payloads[0]["records"]] == ["e1"]


@pytest.mark.asyncio
async def test_timeout_is_caller_owned():
    class Slow(Provider):
        async def structured_call(self, *args):
            await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(monitor(Slow(), "case", [observation()], "manual_snapshot"), 0.01)


@pytest.mark.asyncio
async def test_replay_failure_retains_prior_usage():
    class Failing(Provider):
        async def structured_call(self, role, prompt, payload, model):
            self.payloads.append(payload)
            if len(self.payloads) > 1:
                raise ProviderError("REQUEST_BUDGET_EXCEEDED", {"llm_calls": 0, "total_tokens": 0})
            return IncidentAlert(incident_id="case", status="NO_ALERT", summary="normal"), {
                "llm_calls": 1,
                "total_tokens": 10,
            }

    with pytest.raises(ProviderError) as error:
        await monitor(
            Failing(), "case", [observation(), observation("next", 99, 1)], "offline_replay"
        )
    assert error.value.usage["llm_calls"] == 1
    assert error.value.usage["total_tokens"] == 10
