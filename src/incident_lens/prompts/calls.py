"""One optional observation hook around the existing structured provider boundary."""

from time import perf_counter
from uuid import uuid4

from incident_lens.llm.provider import json_payload
from incident_lens.prompts.resolver import digest, resolver_for


async def structured_call(provider, stage, role, baseline, payload, schema):
    resolver = resolver_for(provider)
    system = resolver.resolve(stage, baseline)
    metadata = resolver.metadata()
    metadata["effective_prompt_sha256"] = digest(system)
    observer = getattr(provider, "snapshot_observer", None)
    call_id = uuid4().hex
    started = perf_counter()
    if observer is not None and stage in {"analysis", "verify"}:
        observer({"phase": "request", "snapshot_id": call_id, "stage": stage, "role": role,
                  "payload": json_payload(payload), "system_prompt": system,
                  "schema": schema.model_json_schema(), "prompt_metadata": metadata})
    try:
        result, usage = await provider.structured_call(role, system, payload, schema)
    except BaseException as exc:
        if observer is not None and stage in {"analysis", "verify"}:
            observer({"phase": "failure", "snapshot_id": call_id,
                      "error_type": type(exc).__name__, "usage": getattr(exc, "usage", {}),
                      "elapsed_ms": (perf_counter() - started) * 1000})
        raise
    if observer is not None and stage in {"analysis", "verify"}:
        observer({"phase": "result", "snapshot_id": call_id,
                  "output": result.model_dump(mode="json"), "usage": usage,
                  "elapsed_ms": (perf_counter() - started) * 1000})
    return result, dict(usage, **metadata)
