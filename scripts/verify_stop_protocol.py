"""Retained Mock/fault-injection acceptance traces for stopping and layered scores."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from incident_lens.artifacts import save_run
from incident_lens.evaluation.metrics import score_completed
from incident_lens.evaluation.runner import load_oracle_after_run, write_csv
from incident_lens.llm import MockProvider, ProviderError
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.orchestration.runtime import StopController
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


class FailedPlanRun(InvestigationRun):
    async def model_call(self, role, function, *args):
        if role == "remediation":
            async def failed(*unused):
                raise ProviderError("INJECTED_PLAN_FAILURE",
                                    {"source": "mock", "llm_calls": 1, "total_tokens": 0})
            function = failed
        return await super().model_call(role, function, *args)


class DeclinedStop(StopController):
    async def stop(self, reason, active=None):
        async def declined():
            return False
        await super().stop(reason, dict(active or {}, reporter=declined))


async def verify(out, data_root=Path("data")):
    out = Path(out)
    if out.exists():
        raise ValueError("use a new acceptance directory")
    rows = []
    for name in ("normal", "plan-failed", "stop-failed", "budget-exhausted", "no-alert"):
        options = WorkflowOptions(profile="incident_response")
        evidence = EvidenceProvider(data_root)
        if name == "no-alert":
            record = evidence._records("incident_001", "metrics")[0].model_copy(update={
                "metadata": {"metric_name": "error_rate", "value": 0.001}})
            options = options.model_copy(update={"monitor_mode": "manual_snapshot",
                                                 "snapshot": [record]})
        run = (FailedPlanRun if name == "plan-failed" else InvestigationRun)(
            MockProvider(), evidence, "incident_001", workflow=options,
            limits=Budget(max_llm_calls=0 if name == "budget-exhausted" else 40,
                          max_tool_calls=24),
        )
        if name == "stop-failed":
            run.stop_controller = DeclinedStop("incident_001", run.run_id, run.runtime_event, 0.01)
        started = time.monotonic()
        completed = await run.run()
        elapsed_ms = (time.monotonic() - started) * 1000
        state = completed.model_dump(mode="json")
        oracle = load_oracle_after_run(data_root, "incident_001", state)
        if name == "no-alert":
            oracle = dict(oracle, monitoring_expected_alert="NO_ALERT")
        score = score_completed(state, oracle)
        expected_root = None if name == "no-alert" else name != "budget-exhausted"
        assert score["protocol_valid"], score["protocol_errors"]
        assert score["root_cause_correct"] is expected_root
        assert score["workflow_success"] is (name in {"normal", "no-alert"})
        path = out / name
        save_run(completed, path, "mock", "full", "off", elapsed_ms)
        (path / "scoring.json").write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
        rows.append(dict(scenario=name, incident_id="incident_001", variant="full",
                         source="mock", split="acceptance", status=completed.report.status,
                         failure_injection=name not in {"normal", "no-alert"}, **score))
    write_csv(out / "case-level.csv", rows)
    (out / "README.md").write_text(
        "# Stop protocol acceptance\n\nMock and explicitly injected faults only; no real provider "
        "or operational remediation executed. stop-failed injects a declined cancellation callback "
        "through the actual StopController ACK protocol. Each folder retains the full trace and "
        "scoring result. PLAN_ONLY is a proposal, not service recovery.\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps({"provider": "mock", "runs": len(asyncio.run(verify(args.out, args.data_root)))}))
