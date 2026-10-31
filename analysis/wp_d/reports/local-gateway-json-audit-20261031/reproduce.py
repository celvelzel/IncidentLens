"""Bounded diagnostic reconstruction of one failed analysis; no investigation rerun."""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

from incident_lens.agents.service import analyze, analysis_schema, prompt, FAILURE_MODES
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.security.context import DATABASE_TOOLS

PROJECT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def main():
    control = "--analysis-phase-control" in sys.argv
    prefix = "control-" if control else "reproduction-"
    load_dotenv(PROJECT / ".env", override=False)
    trace = json.loads((PROJECT / "results/v16/wp-d/local-gateway-dev5-20261031/runs/slot-003/attempt-001/trace.json").read_text(encoding="utf-8"))
    state = trace["state"]
    task = next(t for t in state["tasks"] if t["role"] == "database")
    events = state["events"]
    records = {r["evidence_id"]: r for e in events
               if e["event_type"] == "TOOL_CALL" and e.get("task_id") == task["task_id"]
               for r in e["details"]["result"]["records"]}
    running = next(i for i, e in enumerate(events) if e["event_type"] == "TASK_RUNNING" and e.get("task_id") == task["task_id"])
    context = dict(workspace_id=state["workspace_id"], incident_id=state["incident_id"],
                   run_id=state["run_id"], role="database", allowed_tools=list(DATABASE_TOOLS),
                   allowed_evidence_scope=[state["incident_id"]],
                   remaining_tool_calls=40-sum(e["event_type"] == "TOOL_CALL" for e in events[:running]))
    runtime = yaml.safe_load((PROJECT / "configs/wp_d/api-runtime.yaml").read_text(encoding="utf-8"))
    recovery = dict(runtime["provider_recovery"], max_transport_retries=0,
                    max_physical_attempts_per_call=2)
    attempts = []

    async def request_hook(request):
        attempts.append({"started_at": datetime.now(timezone.utc).isoformat(),
                         "request": json.loads(request.content)})
        write(prefix + "attempts.json", attempts)

    async def response_hook(response):
        await response.aread()
        attempts[-1]["status"] = response.status_code
        try:
            attempts[-1]["response"] = response.json()
        except ValueError:
            attempts[-1]["response_text"] = response.text
        write(prefix + "attempts.json", attempts)

    async with httpx.AsyncClient(timeout=120, event_hooks={"request": [request_hook], "response": [response_hook]}) as client:
        provider = RealChatProvider(os.environ["INCIDENT_LENS_BASE_URL"],
                                    os.environ["INCIDENT_LENS_API_KEY"],
                                    "auto/deepseek-v4.1-flash", client=client,
                                    response_format_mode="json_schema", thinking="disabled",
                                    structured_repair_retries=0 if control else 1,
                                    recovery=recovery)
        try:
            if control:
                result, usage = await provider.structured_call(
                    "database", prompt("database") +
                    "\nCURRENT PHASE: ANALYZE ALREADY-FETCHED RECORDS ONLY. "
                    "The runtime has already executed the tools. No callable tools are registered "
                    "in this request. The context's permissions and remaining_tool_calls describe "
                    "runtime authority, not permission to call tools in this response. "
                    "Do not call tools or output DSML, XML, Markdown fences, or tool_calls. "
                    "Return exactly one AnalysisOutput JSON object containing finding, hypotheses, "
                    "and requested_checks. Use only the supplied records as evidence. "
                    "Represent any additional investigation as requested_checks tasks for the "
                    "coordinator to schedule later. Never perform those checks in this response.",
                    dict(context=context, task=task, records=list(records.values()),
                         failure_mode_taxonomy=FAILURE_MODES, allowed_evidence_ids=sorted(records),
                         citation_rule="Copy IDs exactly from records; all citations must be observed."),
                    analysis_schema(list(records.values())),
                )
            else:
                result, usage = await analyze(provider, context, task, list(records.values()))
            outcome = {"success": True, "usage": usage, "result": result.model_dump(mode="json")}
        except ProviderError as exc:
            outcome = {"success": False, "error": exc.code, "usage": exc.usage}
    outcome["scope"] = "Reconstructed slot-003 analysis, original task/public records; context reconstructed; current auto routing, at most 2 HTTP requests. Not original response recovery."
    write(prefix + "outcome.json", outcome)
    print(json.dumps({"success": outcome["success"], "requests": len(attempts), "error": outcome.get("error")}))


if __name__ == "__main__":
    asyncio.run(main())
