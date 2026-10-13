"""Paired Seed/Dev pilot with a frozen V1.2 provider and identical budgets."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
import types
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from incident_lens.agents.service import PROMPT_VERSION, ROLE_PROMPTS
from incident_lens.artifacts import save_run
from incident_lens.evaluation.runner import MeasuredProvider, load_split, usage_metrics, write_csv
from incident_lens.llm.config import provider_options
from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.tools import EvidenceProvider

BASE = "3629b0695ed1b78d1bd31121363166558a850940"


class Probe(BaseModel):
    ready: bool


async def run(args):
    load_dotenv()
    args.out.mkdir(parents=True, exist_ok=False)
    options = provider_options(args.response_format, None, args.request_timeout)
    endpoint, key, model = (
        os.getenv(k)
        for k in ("INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY", "INCIDENT_LENS_MODEL")
    )
    manifest = dict(
        baseline_revision=BASE,
        current_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        model=model,
        provider_options=options,
        prompt_version=PROMPT_VERSION,
        jobs=1,
        cache_mode="off",
        split="seed/dev",
        budget=dict(max_llm_calls=16, max_wall_seconds=args.max_wall_seconds),
        dataset_revision=EvidenceProvider("data").dataset_revision,
        note="Descriptive pilot, not frozen-Test generalization or causal RCA improvement.",
    )
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not all((endpoint, key, model)):
        (args.out / "status.json").write_text(
            json.dumps(dict(status="PENDING", reason="provider_configuration_missing"))
        )
        return
    probe = MeasuredProvider(
        RealChatProvider(
            endpoint,
            key,
            model,
            **options,
            structured_repair_retries=0,
            recovery={"enabled": True, "max_transport_retries": 0},
        )
    )
    try:
        _, usage = await probe.structured_call(
            "coordinator", "Return ready=true as JSON.", {}, Probe
        )
        probe_result = dict(status="COMPATIBLE", usage=usage)
    except Exception as exc:
        probe_result = dict(
            status="BLOCKED",
            code=getattr(exc, "code", type(exc).__name__),
            usage=getattr(exc, "usage", {}),
        )
    (args.out / "probe.json").write_text(json.dumps(probe_result, indent=2), encoding="utf-8")
    if probe_result["status"] != "COMPATIBLE":
        (args.out / "status.json").write_text(
            json.dumps(dict(status="BLOCKED", reason="compatibility_probe_failed"))
        )
        print(json.dumps(dict(status="BLOCKED", code=probe_result["code"])))
        return
    source = subprocess.check_output(
        ["git", "show", BASE + ":src/incident_lens/llm/provider.py"], text=True
    )
    frozen = types.ModuleType("v12_pilot_provider")
    exec(compile(source, "frozen-v12-provider.py", "exec"), frozen.__dict__)
    manifest["baseline_provider_sha256"] = hashlib.sha256(source.encode()).hexdigest()
    manifest["current_provider_sha256"] = hashlib.sha256(
        Path("src/incident_lens/llm/provider.py").read_bytes()
    ).hexdigest()
    ids = args.cases or load_split("data", "seed")[:3]
    allowed = set(load_split("data", "seed") + load_split("data", "dev"))
    if len(ids) != len(set(ids)) or any(case not in allowed for case in ids):
        raise ValueError("Pilot accepts unique Seed/Dev IDs only")
    manifest["cases"] = ids
    source_hashes = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path("src/incident_lens").rglob("*.py"))
    }
    manifest["source_hashes"] = source_hashes
    manifest["source_sha256"] = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True).encode()
    ).hexdigest()
    manifest["prompt_sha256"] = hashlib.sha256(
        json.dumps(ROLE_PROMPTS, sort_keys=True).encode()
    ).hexdigest()
    manifest["schema_source_hashes"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path("src/incident_lens/schemas").rglob("*.py"))
    }
    group_configs = {
        "R0": frozen.RealChatProvider(endpoint, key, model, **options).model_parameters,
        "R3": RealChatProvider(
            endpoint, key, model, **options, recovery={"enabled": True}
        ).model_parameters,
    }
    manifest["group_configs"] = group_configs
    manifest["group_config_hashes"] = {
        g: hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()
        for g, c in group_configs.items()
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, attempts = [], []
    for index, case in enumerate(ids):
        for group in ("R0", "R3") if index % 2 == 0 else ("R3", "R0"):
            model_provider = (
                frozen.RealChatProvider(endpoint, key, model, **options)
                if group == "R0"
                else RealChatProvider(endpoint, key, model, **options, recovery={"enabled": True})
            )
            measured = MeasuredProvider(model_provider)
            started = time.monotonic()
            state = await run_investigation(
                case,
                measured,
                data_root="data",
                budget=Budget(max_llm_calls=16, max_wall_seconds=args.max_wall_seconds),
            )
            save_run(state, args.out / group / case, "real", cache_mode="off")
            from incident_lens.evaluation.reliability_metrics import technical_completion

            row = dict(
                group=group,
                incident_id=case,
                status=state.report.status,
                stop_reason=state.report.stop_reason,
                technical_completion=technical_completion(state.model_dump(mode="json")),
                latency_seconds=time.monotonic() - started,
                **usage_metrics(measured, state.model_dump(mode="json")),
            )
            rows.append(row)
            for call in measured.calls:
                for event in call["usage"].get("provider_attempts", []):
                    attempts.append(dict(group=group, incident_id=case, **event))
            write_csv(args.out / "case-level.csv", rows)
            (args.out / "provider-attempts.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in attempts), encoding="utf-8"
            )
            print(json.dumps(row), flush=True)
    aggregates = []
    for group in ("R0", "R3"):
        subset = [r for r in rows if r["group"] == group]
        n = len(subset)
        aggregates.append(
            dict(
                group=group,
                technical_completion_numerator=sum(r["technical_completion"] for r in subset),
                technical_completion_denominator=n,
                actual_requests=sum(r["llm_requests"] for r in subset),
                total_tokens=sum(r["total_tokens"] for r in subset)
                if all(r["total_tokens"] is not None for r in subset)
                else None,
                cost_usd=None,
            )
        )
    write_csv(args.out / "aggregate.csv", aggregates)
    (args.out / "status.json").write_text(
        json.dumps(dict(status="EXECUTED", investigations=len(rows))), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--response-format", choices=["json_schema", "json_object"])
    parser.add_argument("--request-timeout", type=float, default=180)
    parser.add_argument("--max-wall-seconds", type=float, default=180)
    parser.add_argument("--cases", nargs="+")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
