"""Probe what a guard stop would actually save on a mock run.

A cost guard must only fire when it *saves* a round. If the streak has already
consumed the whole round budget, stopping early changes the verdict and saves
nothing, which is pure loss. This probe prints the state at every coordinate
decision so the rule can be derived from measurements.
"""

import asyncio
from pathlib import Path
import sys

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions


async def main(case, max_rounds):
    from incident_lens.tools import EvidenceProvider

    run = InvestigationRun(
        MockProvider(),
        EvidenceProvider(Path("data")),
        case,
        Budget(max_rounds=max_rounds, max_llm_calls=40, max_tool_calls=24),
        "dynamic",
        # 10 keeps the streak counting while never firing, so the trace shows
        # what the guard would have seen without the guard acting.
        workflow=WorkflowOptions(profile="incident_response", evidence_gap_rounds=10),
    )
    original = run.record_evidence_gap

    def traced(state):
        fired = original(state)
        decisive = bool(run.discriminator_candidates(state))
        print(
            f"  round_index={state.round_index} streak={run.evidence_gap_streak} "
            f"decisive={decisive} "
            f"remaining_rounds={max(0, run.limits.max_rounds - state.round_index)} "
            f"remaining_llm={run.limits.max_llm_calls - run.call_budget.calls} "
            f"tokens={run.call_budget.tokens}"
        )
        return fired

    run.record_evidence_gap = traced
    state = await run.run()
    print(
        f"{case} max_rounds={max_rounds}: status={state.report.status} "
        f"rounds={state.round_index} peak={run.evidence_gap_peak}"
    )
    return run.evidence_gap_peak


if __name__ == "__main__":
    case = sys.argv[1] if len(sys.argv) > 1 else "incident_001"
    for rounds in (4, 8):
        asyncio.run(main(case, rounds))
