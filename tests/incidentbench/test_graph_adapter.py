import pytest

from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions


async def test_fixed_four_is_explicit_and_legacy_fixed_unchanged():
    legacy = await run_investigation("incident_037", MockProvider(), variant="fixed")
    benchmark = await run_investigation(
        "incident_037",
        MockProvider(),
        variant="fixed",
        budget=Budget(max_tool_calls=24, max_llm_calls=32),
        workflow=WorkflowOptions(
            database_equivalent_tools=True, benchmark_rca=True, benchmark_fixed_four=True
        ),
    )
    assert [t.role for t in legacy.tasks] == ["logs", "metrics", "changes"]
    assert [t.role for t in benchmark.tasks] == ["logs", "metrics", "database", "changes"]
    assert any(e.event_type == "TOOL_CALL" and e.role == "database" for e in benchmark.events)
    assert benchmark.report is not None
    assert not any(e.event_type in {"INCIDENT_ALERT", "REMEDIATION_PLAN"} for e in benchmark.events)


def test_benchmark_opt_in_requires_equivalent_tools():
    with pytest.raises(ValueError):
        WorkflowOptions(benchmark_rca=True)
