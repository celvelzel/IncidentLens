"""Validated public artifact writing and offline replay."""

import json
from pathlib import Path

from incident_lens.orchestration.report import render_report
from incident_lens.schemas import InvestigationState, ToolResult
from incident_lens.security.context import DATABASE_TOOLS, ROLE_TOOL_ACL


def save_run(state, output, provider, variant="full", cache_mode="off", elapsed_ms=None):
    state = InvestigationState.model_validate_json(state.model_dump_json())
    if state.report is None:
        raise ValueError("Cannot save an unfinished run")
    validate_metadata(
        {"schema_version": "v1", "provider": provider, "variant": variant, "cache_mode": cache_mode}
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() or (output / name).is_symlink()
           for name in ("trace.json", "result.json", "report.md")):
        raise FileExistsError("Run artifacts already exist; use a fresh output")
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
    for name, content in (
        ("trace.json", json.dumps(trace, indent=2, ensure_ascii=False) + "\n"),
        ("result.json", state.report.model_dump_json(indent=2) + "\n"),
        ("report.md", render_report(state.report)),
    ):
        with (output / name).open("x", encoding="utf-8") as stream:
            stream.write(content)
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
    validate_replay_observations(state)
    return trace, state


def validate_replay_observations(state):
    """Bind published evidence to recorded successful, role-authorized observations.

    This checks internal consistency, not authenticity of an externally edited trace.
    Older traces lacking observations cannot authorize an evidence inspector.
    """
    observed = {}
    for event in state.events:
        if event.event_type != "TOOL_CALL":
            continue
        allowed = ROLE_TOOL_ACL.get(event.role, ()) + (
            DATABASE_TOOLS if event.role in {"metrics", "single"} else ()
        )
        result = ToolResult.model_validate_json(json.dumps(event.details.get("result")))
        if not result.ok:
            continue
        if event.details.get("tool_name") not in allowed:
            raise ValueError("Replay tool observation violates role authority")
        for record in result.records:
            if (record.incident_id != state.incident_id
                    or record.service not in state.public_summary.services):
                raise ValueError("Replay observation has foreign evidence")
            if record.evidence_id in observed and observed[record.evidence_id] != record:
                raise ValueError("Replay observation content changed")
            observed[record.evidence_id] = record
    if any(observed.get(eid) != record for eid, record in state.evidence_index.items()):
        raise ValueError("Replay evidence lacks matching successful observation")


def reject_private_fields(value):
    """Reject evaluator-only objects in externally edited public replay input."""
    if isinstance(value, dict):
        if {
            "ground_truth", "oracle_scoring_fields", "is_identifiable", "benchmark_oracle",
            "true_primary_root", "acceptable_support_sets", "contradicting_evidence_ids",
            "misleading_evidence_ids", "required_discriminator_types",
            "identifiability_rationale", "annotator_status", "reviewer_ids",
        }.intersection(value):
            raise ValueError("Evaluator-only fields cannot enter replay")
        for child in value.values():
            reject_private_fields(child)
    elif isinstance(value, list):
        for child in value:
            reject_private_fields(child)
