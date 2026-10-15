"""Bounded same-input HTTP probes; not an end-to-end or model-ranking experiment."""

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from incident_lens.agents.service import REVIEW_SCHEMA, DynamicDecision, analysis_schema
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
from incident_lens.evaluation.runner import MeasuredProvider, usage_metrics
from incident_lens.llm.config import provider_options
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.llm.structured_output import output_messages, strict_schema


async def run(args):
    project = Path(__file__).resolve().parents[1]
    load_dotenv(project / ".env", override=False)
    endpoint, key, model = (os.getenv(name) for name in (
        "INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY", "INCIDENT_LENS_MODEL"))
    if not all((endpoint, key, model)):
        raise ValueError("real provider configuration required")
    args.out.mkdir(parents=True, exist_ok=False)
    frozen = retest_snapshot(project)
    summary = {"scope": "same saved inputs, HTTP only, no workflow execution or accuracy claim",
               "source_sha256": frozen, "model_id": model, "timeout": args.timeout,
               "structured_repairs": 0, "results": []}
    for request_id in args.requests:
        if not request_id.startswith("req-") or not request_id[4:].isdigit():
            raise ValueError("invalid request id")
        path = args.bridge / "_bridge" / "requests" / (request_id + ".json")
        raw = path.read_bytes()
        request = json.loads(raw)
        payload = request["user_payload"]
        base = {"DynamicDecision": DynamicDecision, "Review": REVIEW_SCHEMA}.get(request["schema_name"])
        if request["schema_name"] == "AnalysisOutput":
            base = analysis_schema(payload["records"])
        if base is None:
            raise ValueError("unsupported probe schema")

        # Preserve the original per-call dynamic schema, including citation enums.
        class SavedSchema:
            @staticmethod
            def model_json_schema():
                return copy.deepcopy(request["json_schema"])

            @staticmethod
            def model_validate_json(content):
                return base.model_validate_json(content)

        SavedSchema.__name__ = request["schema_name"]
        provider = MeasuredProvider(RealChatProvider(
            endpoint, key, model, temperature=0, structured_repair_retries=0,
            **provider_options("json_schema", None, args.timeout),
        ))
        wire = {"messages": output_messages(request["system_prompt"], payload, strict_schema(SavedSchema)),
                "schema": strict_schema(SavedSchema)}
        (args.out / (request_id + ".input.json")).write_text(json.dumps(wire, indent=2), encoding="utf-8")
        item = {"request_id": request_id, "role": request["role"],
                "original_request_sha256": hashlib.sha256(raw).hexdigest(),
                "status": "pending", "bridge_response": json.loads(
                    (args.bridge / "_bridge" / "responses" / (request_id + ".json")).read_text())}
        try:
            result, _ = await provider.structured_call(request["role"], request["system_prompt"], payload, SavedSchema)
            item.update(status="valid", api_response=result.model_dump(mode="json"))
        except ProviderError as exc:
            item.update(status="failed", error_code=exc.code)
        item["usage"] = usage_metrics(provider, {"events": []})
        item["elapsed_ms"] = sum(c["usage"].get("elapsed_ms", 0) for c in provider.calls)
        summary["results"].append(item)
        summary["source_drift"] = snapshot_changes(frozen, retest_snapshot(project))
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({k: item[k] for k in ("request_id", "status", "usage")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--requests", nargs="+", default=["req-0001", "req-0011", "req-0012"])
    parser.add_argument("--timeout", type=float, default=180)
    asyncio.run(run(parser.parse_args()))
