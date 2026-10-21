"""At most two synthetic remote Codex calls; never run an incident benchmark."""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from incident_lens.agents.service import plan_tools
from incident_lens.evaluation.run_io import atomic_json
from incident_lens.llm.codex_subscription import (
    CodexSubscriptionProvider,
    inspect_auth,
    resolve_cli,
)


class ProbeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    marker: str
    value: int


async def probe(args):
    config = json.loads(args.config.read_bytes())
    executable = resolve_cli(config["executable"])
    auth = await asyncio.to_thread(inspect_auth, executable)
    args.out.mkdir(parents=True, exist_ok=False)
    result = {"scope": "synthetic subscription feasibility only; not API Platform or G1a",
              "auth": auth, "formal_test_started": False, "incident_investigations": 0,
              "attempted_codex_invocations": 0, "probes": [], "status": "AUTH_CONFIRMED_ONLY",
              "platform_api_quota_shared": False}
    atomic_json(args.out / "feasibility.json", result)
    if not args.run_feasibility:
        print(json.dumps(result))
        return
    provider = CodexSubscriptionProvider(
        config["model"], args.out / "calls", executable=executable,
        timeout=config["feasibility_timeout_seconds"], reasoning_effort=config["reasoning_effort"],
        diagnostic_mode=True,
    )
    try:
        result["attempted_codex_invocations"] += 1
        answer, usage = await provider.structured_call(
            "coordinator", "Return only the schema-conforming JSON answer. Do not use tools.",
            {"instruction": "Return marker=subscription-feasibility and value equal to 2+3."}, ProbeAnswer,
        )
        matched = answer.marker == "subscription-feasibility" and answer.value == 5
        result["probes"].append({"name": "structured_json", "matched": matched,
                                "answer": answer.model_dump(), "usage": usage})
        if not matched:
            raise ValueError("synthetic structured-output answer mismatch")
        result["attempted_codex_invocations"] += 1
        plan, usage = await plan_tools(
            provider,
            {"role": "metrics", "allowed_tools": ["query_metrics", "get_dependencies"]},
            {"task_id": "probe-metrics", "role": "metrics", "allowed_tools": ["query_metrics"],
             "question": "Propose one query_metrics call for synthetic-backend, with metric_names=[], "
                         "start_ts=2026-10-21T00:00:00Z and end_ts=2026-10-21T00:01:00Z."},
            {"services": ["synthetic-backend"], "incident_id": "synthetic-feasibility"}, {},
        )
        matched = len(plan.calls) == 1 and plan.calls[0].tool_name == "query_metrics"
        result["probes"].append({"name": "task_acl_schema", "matched": matched,
                                "plan": plan.model_dump(), "usage": usage,
                                "proposed_tools_executed": False})
        if not matched:
            raise ValueError("synthetic task-tool plan mismatch")
        result["status"] = "FEASIBLE_FOR_CODEX_SUBSCRIPTION_TRANSPORT"
    except BaseException as exc:
        result["status"] = "FEASIBILITY_FAILED"
        result["error_type"] = type(exc).__name__
        result["error_code"] = getattr(exc, "code", "LOCAL_VALIDATION_ERROR")
        raise
    finally:
        atomic_json(args.out / "feasibility.json", result)
        print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/wp_d/codex-subscription.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-feasibility", action="store_true")
    asyncio.run(probe(parser.parse_args()))
