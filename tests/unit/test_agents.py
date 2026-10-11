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
            output.finding.evidence_ids = ["invented"]
            return output, usage

    with pytest.raises(ProviderError, match="UNOBSERVED_CITATION"):
        await analyze(Bad(), context("logs"), d.assignments[0], [])


@pytest.mark.asyncio
async def test_missing_observations_abstain():
    state = dict(tasks=[dict(role="changes")], hypotheses=[], evidence_index={})
    d, _ = await decide(MockProvider(), state)
    assert d.action == "ABSTAIN"
