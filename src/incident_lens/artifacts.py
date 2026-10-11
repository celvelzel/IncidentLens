"""Validated public artifact writing and offline replay."""

import json
from pathlib import Path

from incident_lens.orchestration.report import render_report
from incident_lens.schemas import InvestigationState


def save_run(state, output, provider, variant="full", cache_mode="off", elapsed_ms=None):
    state = InvestigationState.model_validate_json(state.model_dump_json())
    if state.report is None:
        raise ValueError("Cannot save an unfinished run")
    validate_metadata(
        {"schema_version": "v1", "provider": provider, "variant": variant, "cache_mode": cache_mode}
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    trace = {
        "schema_version": "v1",
        "provider": provider,
        "variant": variant,
        "cache_mode": cache_mode,
        "elapsed_ms": elapsed_ms,
        "state": state.model_dump(mode="json"),
    }
    calls = [e for e in state.events if e.event_type in {"LLM_CALL", "MODEL_FAILURE"}]
    trace["model_id"] = calls[0].details.get("model_id") if calls else None
    trace["prompt_version"] = next(
        (e.details.get("prompt_version") for e in calls if e.details.get("prompt_version")), None
    )
    (output / "trace.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "result.json").write_text(
        state.report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(render_report(state.report), encoding="utf-8")
    return trace


def validate_metadata(trace):
    if not isinstance(trace, dict) or trace.get("schema_version") != "v1":
        raise ValueError("Unsupported trace schema")
    allowed = {
        "schema_version",
        "provider",
        "variant",
        "cache_mode",
        "elapsed_ms",
        "state",
        "model_id",
        "prompt_version",
    }
    if set(trace) - allowed:
        raise ValueError("Unexpected trace envelope fields")
    if trace.get("provider") not in ("mock", "real"):
        raise ValueError("Invalid trace provider")
    if trace.get("variant") not in ("full", "single", "fixed", "dynamic_no_verifier"):
        raise ValueError("Invalid trace variant")
    if trace.get("cache_mode") not in ("off", "exact", "semantic"):
        raise ValueError("Invalid trace cache mode")


def load_replay(path):
    trace = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    validate_metadata(trace)
    reject_private_fields(trace)
    if not isinstance(trace.get("state"), dict):
        raise ValueError("Invalid trace state")
    state = InvestigationState.model_validate_json(json.dumps(trace["state"]))
    if state.report is None:
        raise ValueError("Trace has no completed report")
    return trace, state


def reject_private_fields(value):
    """Reject evaluator-only objects in externally edited public replay input."""
    if isinstance(value, dict):
        if {"ground_truth", "oracle_scoring_fields", "is_identifiable"}.intersection(value):
            raise ValueError("Evaluator-only fields cannot enter replay")
        for child in value.values():
            reject_private_fields(child)
    elif isinstance(value, list):
        for child in value:
            reject_private_fields(child)
