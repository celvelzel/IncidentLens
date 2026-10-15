"""Offline forensic continuation only; not a production resume entrypoint."""
import asyncio
import hashlib
import json
import time
from pathlib import Path

from incident_lens.artifacts import save_run
from incident_lens.evaluation.retest_provenance import retest_snapshot
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.llm.provider import LLMProvider
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.orchestration.guards import reviewed_finalization_ready
from incident_lens.schemas import Budget, InvestigationState
from incident_lens.schemas.workflow import TaskRecord, WorkflowOptions
from incident_lens.tools import EvidenceProvider

SOURCE = Path("results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/full/trace.json")

class NoCalls(LLMProvider):
    async def structured_call(self, *args):
        raise AssertionError("No new model call permitted")

async def main():
    original = SOURCE.read_bytes()
    data = json.loads(original)["state"]
    cutoff = next(i for i, e in enumerate(data["events"]) if e["event_id"] == "event-104")
    prefix = data["events"][:cutoff + 1]
    data.update(events=prefix, report=None, termination=None, workflow_status="RUNNING", stop_reason=None)
    records = {}
    for event in prefix:
        if event["event_type"] in {"TASK_ASSIGNED", "TASK_RUNNING", "TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED"}:
            record = event["details"] | {"role": event["role"]}
            records[record["attempt_id"]] = record
    data["task_records"] = list(records.values())
    data["llm_calls_used"] = 23
    state = InvestigationState.model_validate_json(json.dumps(data))
    runtime = InvestigationRun(NoCalls(), EvidenceProvider(
        "results/incidentbench/v1/20261013-deepseek-development-pilot/dataset/rca"),
        "incident_2001", limits=Budget.model_validate_json(json.dumps(data["budgets"])),
        run_id=state.run_id, workflow=WorkflowOptions(benchmark_rca=True, database_equivalent_tools=True))
    runtime.state = state
    # Hydrate the forensic fixture from recorded task transitions; no real worker is resumed.
    runtime.task_manager._records = [TaskRecord.model_validate_json(json.dumps(r)) for r in records.values()]
    runtime.task_manager._latest = {r.task_id: r for r in runtime.task_manager._records}
    runtime.call_budget.calls = 23
    runtime.call_budget.usage = [e.details for e in state.events if e.event_type in {"LLM_CALL", "MODEL_FAILURE"}]
    first = next(e for e in state.events if e.event_type == "LLM_CALL")
    elapsed = (state.events[-1].timestamp - first.timestamp).total_seconds() + first.details["elapsed_ms"] / 1000
    runtime.call_budget.started = time.monotonic() - elapsed
    assert reviewed_finalization_ready(state)
    runtime.event(state, "FINALIZE_RESUMED_AFTER_REVIEW", selected_hypothesis_id=state.decisions[-1].selected_hypothesis_id,
                  review_event_id="event-104", decision_index=len(state.decisions)-1)
    result = runtime.finalize({"investigation": state})
    assert result["route"] == "report" and state.report.status == "RESOLVED"
    await runtime.stop(result)
    final = runtime.report({"investigation": state})["investigation"]
    out = Path(__file__).parent / "checkpoint-continuation"
    out.mkdir(exist_ok=False)
    save_run(final, out, "real")
    report_path = out / "report.md"
    report_path.write_text("> OFFLINE continuation of saved v4 state; no new API calls. Original v4 run remains FAILED.\n\n" + report_path.read_text(encoding="utf-8"), encoding="utf-8")
    verification = normalize_termination(final.model_dump(mode="json"))
    verification.update(scope="OFFLINE continuation from real v4 event-104; not a new real API run",
        new_http_requests=0, source_trace_sha256=hashlib.sha256(original).hexdigest(), source_checkpoint="event-104",
        source_unchanged=SOURCE.read_bytes()==original, source_sha256=retest_snapshot(Path.cwd()),
        checkpoint_events_unchanged=final.model_dump(mode="json")["events"][:len(prefix)]==prefix,
        historical_requests_before_checkpoint=23)
    (out / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in verification.items() if k!="source_sha256"}))

asyncio.run(main())
