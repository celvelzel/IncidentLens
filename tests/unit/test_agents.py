import pytest

from incident_lens.agents import analyze, decide, plan_tools, verify
from incident_lens.llm import MockProvider, ProviderError


def context(role):
    return dict(
        role=role,
        run_id="run",
        incident_id="opaque",
        allowed_tools={
            "logs": ["query_logs"],
            "metrics": ["query_metrics", "get_dependencies"],
            "changes": ["query_changes", "get_config_diff"],
        }[role],
    )


def record(eid, source, excerpt, service="backend", metadata=None):
    return dict(
        evidence_id=eid,
        incident_id="opaque",
        source_type=source,
        service=service,
        source_path="public/" + source + ".jsonl",
        excerpt=excerpt,
        metadata=metadata or {},
    )


@pytest.mark.asyncio
async def test_five_roles_dynamic_challenge_and_config_followup():
    p = MockProvider()
    state = dict(incident_id="opaque", tasks=[], hypotheses=[], findings=[], evidence_index={})
    decision, _ = await decide(p, state)
    summary = dict(started_at="2026-01-01T00:00:00Z", observed_symptoms=["API errors"])
    for task in decision.assignments:
        plan, _ = await plan_tools(p, context(task.role), task, summary, [])
        assert 0 < len(plan.calls) <= 2
        rs = (
            [record("log", "logs", "DB connection acquire timeout")]
            if task.role == "logs"
            else [record("metric", "metrics", "connections normal", "postgres")]
        )
        output, _ = await analyze(p, context(task.role), task, rs)
        state["hypotheses"].extend(h.model_dump() for h in output.hypotheses)
        state["findings"].append(output.finding.model_dump())
        state["evidence_index"].update({r["evidence_id"]: r for r in rs})
    state["tasks"] = [t.model_dump() for t in decision.assignments]
    review, _ = await verify(p, state)
    assert review.verdict == "insufficient" and review.requested_checks[0].role == "changes"
    state["requested_checks"] = [t.model_dump() for t in review.requested_checks]
    decision, _ = await decide(p, state)
    assert decision.assignments[0].role == "changes"
    change_task = decision.assignments[0]
    output, _ = await analyze(
        p,
        context("changes"),
        change_task,
        [record("diff", "configs", "DB_POOL_MAX reduced from 20 to 2")],
    )
    assert output.hypotheses[0].failure_mode == "backend_pool_config_regression"
    plan, _ = await plan_tools(
        p,
        context("changes"),
        change_task,
        summary,
        [record("change", "changes", "configuration updated", metadata={"change_id": "c1"})],
    )
    assert plan.calls[0].tool_name == "get_config_diff"


@pytest.mark.asyncio
async def test_role_and_citation_checks():
    p = MockProvider()
    d, _ = await decide(p, {})
    with pytest.raises(ProviderError, match="ROLE_IDENTITY_MISMATCH"):
        await plan_tools(p, context("changes"), d.assignments[0], {}, [])

    class Bad(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            output = output.model_copy(
                update={"finding": output.finding.model_copy(update={"evidence_ids": ["invented"]})}
            )
            return output, usage

    with pytest.raises(ProviderError, match="UNOBSERVED_CITATION"):
        await analyze(Bad(), context("logs"), d.assignments[0], [])


@pytest.mark.asyncio
async def test_missing_observations_abstain():
    state = dict(tasks=[dict(role="changes")], hypotheses=[], evidence_index={})
    d, _ = await decide(MockProvider(), state)
    assert d.action == "ABSTAIN"


@pytest.mark.asyncio
async def test_real_citation_schema_repairs_once_and_counts_requests():
    import json

    import httpx

    from incident_lens.llm import RealChatProvider

    task = (await decide(MockProvider(), {}))[0].assignments[0]
    records = [record("observed", "logs", "DB connection acquire timeout")]
    output, _ = await analyze(MockProvider(), context("logs"), task, records)
    good = output.model_dump(mode="json")
    bad = json.loads(json.dumps(good))
    bad["finding"]["evidence_ids"] = ["unqueried"]
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(bad if len(requests) == 1 else good)}}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealChatProvider("https://example.invalid", "secret", "test", client=client)
        result, usage = await analyze(provider, context("logs"), task, records)
    assert result.finding.evidence_ids == ["observed"]
    assert usage["llm_calls"] == 2 and usage["total_tokens"] == 24
    assert (
        requests[0]["response_format"]["json_schema"]["schema"]["$defs"]["ObservedFinding"][
            "properties"
        ]["evidence_ids"]["items"]["const"]
        == "observed"
    )


def test_citation_schema_rejects_unobserved_hypothesis_and_empty_records():
    from pydantic import ValidationError

    from incident_lens.agents.service import analysis_schema

    schema = analysis_schema([record("observed", "logs", "timeout")])
    hypothesis = schema.model_fields["hypotheses"].annotation.__args__[0]
    with pytest.raises(ValidationError):
        hypothesis.model_validate_json(
            '{"hypothesis_id":"h","culprit_service":"backend","failure_mode":"backend_pool_config_regression","support_ids":["unqueried"]}'
        )
    empty_finding = analysis_schema([]).model_fields["finding"].annotation
    assert empty_finding.model_json_schema()["properties"]["evidence_ids"]["maxItems"] == 0


@pytest.mark.asyncio
async def test_hypothesis_ids_follow_cause_not_model_local_ids():
    task = (await decide(MockProvider(), {}))[0].assignments[0]

    class LocalIDs(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            for h in output.hypotheses:
                h.hypothesis_id = "hyp-1"
            return output, usage

    first, _ = await analyze(
        LocalIDs(),
        context("logs"),
        task,
        [record("a", "logs", "Redis connection refused", "redis")],
    )
    second, _ = await analyze(
        LocalIDs(), context("logs"), task, [record("b", "logs", "payment timed out", "payment")]
    )
    repeat, _ = await analyze(
        LocalIDs(), context("logs"), task, [record("c", "logs", "Redis unavailable", "redis")]
    )
    assert first.hypotheses and second.hypotheses and repeat.hypotheses
    assert first.hypotheses[0].hypothesis_id != second.hypotheses[0].hypothesis_id
    assert first.hypotheses[0].hypothesis_id == repeat.hypotheses[0].hypothesis_id


@pytest.mark.asyncio
async def test_reused_coordinator_task_ids_are_allocated_fresh():
    from incident_lens.agents.service import DynamicDecision

    initial, _ = await decide(MockProvider(), {})
    payload = initial.model_dump(mode="json")
    payload["assignments"] = [dict(payload["assignments"][0]), dict(payload["assignments"][0])]

    class Reused(MockProvider):
        async def structured_call(self, *args):
            return DynamicDecision.model_validate_json(__import__("json").dumps(payload)), {}

    old = [initial.assignments[0].model_dump(mode="json")]
    result, _ = await decide(Reused(), {"tasks": old})
    ids = [t.task_id for t in result.assignments]
    assert len(ids) == len(set(ids))
    assert old[0]["task_id"] not in ids


@pytest.mark.asyncio
async def test_finding_ids_bind_observation_and_task_instead_of_model_label():
    task = (await decide(MockProvider(), {}))[0].assignments[0]

    class LocalID(MockProvider):
        async def structured_call(self, *args):
            output, usage = await super().structured_call(*args)
            output.finding.finding_id = "F1"
            return output, usage

    records = [record("a", "logs", "Redis connection refused", "redis")]
    first, _ = await analyze(LocalID(), context("logs"), task, records)
    repeat, _ = await analyze(LocalID(), context("logs"), task, records)
    other, _ = await analyze(LocalID(), context("logs"),
                             task.model_copy(update={"task_id": "next-round"}), records)
    assert first.finding.finding_id == repeat.finding.finding_id
    assert first.finding.finding_id != other.finding.finding_id
    assert other.finding.task_id == "next-round"


def test_optional_review_checks_do_not_become_acceptance_blockers():
    from pydantic import ValidationError

    from incident_lens.agents.service import ReviewOutput

    data = dict(target_hypothesis_id="h", verdict="sufficient", rationale="Causal evidence complete")
    accepted = ReviewOutput(**data, optional_checks=[])
    assert accepted.requested_checks == []
    with pytest.raises(ValidationError, match="sufficient requires"):
        ReviewOutput(**data, contradictions=["Material contradiction"])


@pytest.mark.asyncio
async def test_reconciliation_rejects_unobserved_ids_and_changed_cause():
    from incident_lens.schemas import Hypothesis

    old = Hypothesis(hypothesis_id="h", culprit_service="backend",
                     failure_mode="backend_pool_config_regression")
    initial = (await decide(MockProvider(), {}))[0]
    for changes in ({"support_ids": ["unobserved"]}, {"culprit_service": "gateway"}):
        class InvalidUpdate(MockProvider):
            async def structured_call(self, *args):
                return initial.model_copy(update={
                    "hypothesis_updates": [old.model_copy(update=changes)]
                }), {}

        with pytest.raises(ProviderError, match="COORDINATOR_HYPOTHESIS_UPDATE_INVALID"):
            await decide(InvalidUpdate(), dict(benchmark_rca=True,
                         hypotheses=[old.model_dump()], evidence_catalog={"observed": {}}))


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", ["single", "full", "dynamic_no_verifier", "fixed"])
@pytest.mark.parametrize("benchmark_rca", [False, True])
async def test_no_existing_hypotheses_forbids_updates_in_provider_schema(variant, benchmark_rca):
    from pydantic import ValidationError

    from incident_lens.llm.structured_output import strict_schema
    from incident_lens.schemas import Hypothesis

    initial, _ = await decide(MockProvider(), {})
    good = initial.model_dump(mode="json")
    bad = dict(good, hypothesis_updates=[Hypothesis(
        hypothesis_id="H1", culprit_service="backend", failure_mode="fixture-cause",
    ).model_dump(mode="json")])

    class CheckSchema:
        async def structured_call(self, role, system, payload, schema):
            assert strict_schema(schema)["properties"]["hypothesis_updates"]["maxItems"] == 0
            assert "hypothesis_updates must be an empty array []" in system
            with pytest.raises(ValidationError, match="hypothesis_updates"):
                schema.model_validate(bad)
            return schema.model_validate(good), {}

    result, _ = await decide(CheckSchema(), dict(
        variant=variant, benchmark_rca=benchmark_rca, hypotheses=[], evidence_index={},
    ))
    assert result.action == "INVESTIGATE" and result.assignments
    assert result.hypothesis_updates == []


@pytest.mark.asyncio
async def test_empty_board_invalid_updates_repair_before_runtime_guard():
    import json

    import httpx

    from incident_lens.llm import RealChatProvider
    from incident_lens.schemas import Hypothesis

    good = (await decide(MockProvider(), {}))[0].model_dump(mode="json")
    bad = dict(good, hypothesis_updates=[Hypothesis(
        hypothesis_id="H1", culprit_service="backend", failure_mode="fixture-cause",
    ).model_dump(mode="json")])
    requests = []

    async def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(bad if len(requests) == 1 else good)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = RealChatProvider("https://fixture.invalid", "fixture-secret", "fixture", client=client)
        result, usage = await decide(provider, dict(benchmark_rca=True, hypotheses=[]))
    assert result.action == "INVESTIGATE" and result.hypothesis_updates == []
    assert len(requests) == usage["llm_calls"] == 2
    assert usage["total_tokens"] == 24
    assert requests[0]["response_format"]["json_schema"]["schema"]["properties"]["hypothesis_updates"]["maxItems"] == 0


@pytest.mark.asyncio
async def test_registered_hypotheses_can_still_be_reconciled():
    from incident_lens.schemas import Hypothesis

    old = Hypothesis(hypothesis_id="known", culprit_service="backend", failure_mode="fixture-cause")
    initial = (await decide(MockProvider(), {}))[0]
    revised = old.model_copy(update={"status": "SUPPORTED", "support_ids": ["observed"]})

    class UpdateExisting:
        async def structured_call(self, role, system, payload, schema):
            return schema.model_validate(dict(initial.model_dump(mode="json"),
                                               hypothesis_updates=[revised.model_dump(mode="json")])), {}

    result, _ = await decide(UpdateExisting(), dict(
        benchmark_rca=True, hypotheses=[old.model_dump()], evidence_catalog={"observed": {}},
    ))
    assert result.hypothesis_updates[0].model_dump() == revised.model_dump()


@pytest.mark.asyncio
async def test_bypassing_empty_board_schema_still_fails_closed():
    from incident_lens.schemas import Hypothesis

    initial = (await decide(MockProvider(), {}))[0]

    class BypassSchema:
        async def structured_call(self, *args):
            return initial.model_copy(update={"hypothesis_updates": [Hypothesis(
                hypothesis_id="H1", culprit_service="backend", failure_mode="fixture-cause",
            )]}), {}

    with pytest.raises(ProviderError, match="COORDINATOR_HYPOTHESIS_UPDATE_INVALID"):
        await decide(BypassSchema(), dict(benchmark_rca=True, hypotheses=[]))


@pytest.mark.asyncio
async def test_tool_planning_uses_observed_metadata_and_discovers_unknown_metrics():
    from incident_lens.agents.service import InvestigatorPlan

    class Planned(MockProvider):
        def __init__(self, calls):
            self.calls = calls

        async def structured_call(self, *args):
            return InvestigatorPlan.model_validate_json(
                __import__("json").dumps({"calls": self.calls})
            ), {}

    initial, _ = await decide(MockProvider(), {})
    change_task = initial.assignments[0].model_copy(
        update={"role": "changes", "allowed_tools": ["get_config_diff"]}
    )
    facts = {
        "evidence_index": {
            "change-evidence": record(
                "change-evidence", "changes", "deployed", metadata={"change_id": "actual-change"}
            )
        }
    }
    plan, _ = await plan_tools(
        Planned([{"tool_name": "get_config_diff", "args": {"change_id": "change-evidence"}}]),
        context("changes"),
        change_task,
        {},
        facts,
    )
    assert plan.calls[0].args["change_id"] == "actual-change"
    metrics_task = initial.assignments[0].model_copy(
        update={"role": "metrics", "allowed_tools": ["query_metrics"]}
    )
    plan, _ = await plan_tools(
        Planned(
            [
                {
                    "tool_name": "query_metrics",
                    "args": {
                        "service": "backend",
                        "metric_names": ["invented_metric"],
                        "start_ts": "2026-01-01T00:00:00Z",
                        "end_ts": "2026-01-01T01:00:00Z",
                    },
                }
            ]
        ),
        context("metrics"),
        metrics_task,
        {},
        facts,
    )
    assert plan.calls[0].args["metric_names"] == []
    assert plan.calls[0].args["service"] == "backend"

    proposed = [{"tool_name": "query_changes", "args": {
        "service": "backend", "start_ts": "2026-01-01T00:00:00Z",
        "end_ts": "2026-01-01T00:00:00Z", "change_type": "config",
    }}]
    change_task = change_task.model_copy(update={"allowed_tools": ["query_changes"]})
    discovery, _ = await plan_tools(
        Planned(proposed), context("changes"), change_task, {},
        {"benchmark_discovery": True, "evidence_index": {}},
    )
    assert discovery.calls[0].args == {"service": "backend"}
    # With an empty changes source, only the one-shot discovery query may drop the
    # window; later queries must keep it so a decisive NO_DATA stays observable.
    rerun, _ = await plan_tools(
        Planned(proposed), context("changes"), change_task, {},
        {"benchmark_discovery": True, "changes_discovery_done": True, "evidence_index": {}},
    )
    assert rerun.calls[0].args == proposed[0]["args"]
    narrowed, _ = await plan_tools(
        Planned(proposed), context("changes"), change_task, {},
        dict(facts, benchmark_discovery=True),
    )
    assert narrowed.calls[0].args == proposed[0]["args"]
    legacy, _ = await plan_tools(
        Planned(proposed), context("changes"), change_task, {}, {"evidence_index": {}},
    )
    assert legacy.calls[0].args == proposed[0]["args"]
    log_task = change_task.model_copy(update={"role": "logs", "allowed_tools": ["query_logs"]})
    log_args = {"service": "backend", "start_ts": "2026-01-01T00:00:00Z",
                "end_ts": "2026-01-01T01:00:00Z", "severity": "ERROR", "contains": "timeout"}
    discovered, _ = await plan_tools(
        Planned([{"tool_name": "query_logs", "args": log_args}]), context("logs"),
        log_task, {}, {"benchmark_discovery": True, "evidence_index": {}},
    )
    assert discovered.calls[0].args == {k: v for k, v in log_args.items()
                                      if k not in {"severity", "contains"}}
