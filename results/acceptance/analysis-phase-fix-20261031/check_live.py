"""Bounded post-fix checks of six reconstructed analysis calls, not full reruns."""

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from incident_lens.agents.service import PROMPT_VERSION, analyze
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.security.context import DATABASE_TOOLS

PROJECT = Path.cwd()
OUT = Path(__file__).resolve().parent


async def main():
    load_dotenv(PROJECT / ".env", override=False)
    rows = []
    for slot in ("slot-003", "slot-004", "slot-008", "slot-009", "slot-015", "slot-018"):
        path = PROJECT / "results/v16/wp-d/local-gateway-dev5-20261031/runs" / slot / "attempt-001/trace.json"
        state = json.loads(path.read_text(encoding="utf-8"))["state"]
        failed = next(e for e in reversed(state["events"])
                      if e["event_type"] == "MODEL_FAILURE" and e["role"] == "database")
        task = next(t for t in state["tasks"] if t["task_id"] == failed["task_id"])
        records = {r["evidence_id"]: r for e in state["events"]
                   if e["event_type"] == "TOOL_CALL" and e["task_id"] == task["task_id"]
                   for r in e["details"]["result"]["records"]}
        context = dict(workspace_id=state["workspace_id"], incident_id=state["incident_id"],
                       run_id=state["run_id"], role="database", allowed_tools=list(DATABASE_TOOLS),
                       allowed_evidence_scope=[state["incident_id"]], remaining_tool_calls=38)
        attempts = []

        async def request_hook(request):
            attempts.append({"started_at": datetime.now(timezone.utc).isoformat()})

        async def response_hook(response):
            await response.aread()
            attempts[-1]["http_status"] = response.status_code
            try:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                attempts[-1].update(finish_reason=choice.get("finish_reason"),
                                     content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                                     contains_dsml="DSML" in content)
            except (ValueError, TypeError, IndexError):
                pass

        async with httpx.AsyncClient(timeout=120, event_hooks={"request": [request_hook], "response": [response_hook]}) as client:
            provider = RealChatProvider(os.environ["INCIDENT_LENS_BASE_URL"], os.environ["INCIDENT_LENS_API_KEY"],
                                        "auto/deepseek-v4.1-flash", client=client, thinking="disabled",
                                        response_format_mode="json_schema", recovery={
                                            "enabled": True, "max_transport_retries": 0,
                                            "max_structured_repairs": 1, "max_physical_attempts_per_call": 2,
                                        })
            try:
                value, usage = await analyze(provider, context, task, list(records.values()))
                row = dict(slot=slot, incident=state["incident_id"], task_id=task["task_id"],
                           success=True, usage=usage, result=value.model_dump(mode="json"))
            except ProviderError as exc:
                row = dict(slot=slot, incident=state["incident_id"], task_id=task["task_id"],
                           success=False, error=exc.code, usage=exc.usage)
        row.update(trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), attempts=attempts)
        rows.append(row)
        (OUT / "live-analysis-checks.json").write_text(json.dumps(dict(
            scope="Six reconstructed failed analysis tasks under changed production code; current gateway routing. Not original-response replay or complete investigation acceptance.",
            prompt_version=PROMPT_VERSION, rows=rows), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"slot": slot, "success": row["success"], "requests": len(attempts),
                          "repairs": row["usage"].get("repair_requests", 0)}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
