"""Measure the guard's observed peak gap streak across the mock incidents.

The frozen WP-D batch is a capped-budget workload; the unit tests run a
much larger budget where the coordinator takes more rounds. A default
threshold must clear the peak of *every* identifiable run it can see, so this
probe reports the smallest limit at which the guard never fires per case.
"""

import asyncio
from pathlib import Path

from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions

CASES = sorted(p.name for p in Path("data/incidents").iterdir() if (p / "public").is_dir())
BIG = dict(
    budget=Budget(max_llm_calls=40, max_tool_calls=24),
    workflow=WorkflowOptions(profile="incident_response", remediation_enabled=True),
)


def fired(state):
    return [e for e in state.events if e.event_type == "INVESTIGATION_EVIDENCE_EXHAUSTED"]


async def peak(case):
    for limit in range(1, 12):
        options = BIG["workflow"].model_copy(update={"evidence_gap_rounds": limit})
        state = await run_investigation(
            case, MockProvider(), budget=BIG["budget"], workflow=options
        )
        if not fired(state):
            return limit - 1, state.report.status, state.round_index
    return 11, state.report.status, state.round_index


async def main():
    worst = 0
    for case in CASES:
        found, status, rounds = await peak(case)
        worst = max(worst, found)
        print(f"{case}: peak_streak={found} status={status} rounds={rounds}")
    print(f"\nmax peak across {len(CASES)} mock cases: {worst}")
    print("A default at or below this value would abstain on an identifiable run.")


if __name__ == "__main__":
    asyncio.run(main())
