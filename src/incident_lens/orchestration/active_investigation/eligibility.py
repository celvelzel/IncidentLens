"""Pure hard feasibility checks; runtime dispatch remains authoritative."""

import re
from datetime import datetime

from pydantic import TypeAdapter, ValidationError

from incident_lens.tools.arguments import ARGUMENT_MODELS

from .candidate_generator import candidate_signature
from .contracts import BudgetView, CandidateAction, PolicyConfig, VisibleState, digest


def check_eligibility(
    candidate: CandidateAction,
    visible: VisibleState,
    budget: BudgetView,
    role_acl: dict[str, tuple[str, ...]],
    config: PolicyConfig,
) -> str | None:
    if visible.stopped:
        return "STOPPED"
    if (candidate.run_id, candidate.incident_id, candidate.decision_id) != (
        visible.run_id,
        visible.incident_id,
        visible.decision_id,
    ):
        return "STALE_IDENTITY"
    if candidate.evidence_snapshot_sha256 != visible.evidence_snapshot_sha256:
        return "STALE_EVIDENCE_SNAPSHOT"
    if (
        candidate.proposed_role not in ("logs", "metrics", "database", "changes")
        or candidate.proposed_role not in role_acl
    ):
        return "FORBIDDEN_ROLE"
    if not candidate.allowed_tools or any(
        tool not in role_acl[candidate.proposed_role] or tool not in ARGUMENT_MODELS
        for tool in candidate.allowed_tools
    ):
        return "FORBIDDEN_TOOL"
    try:
        digest(candidate.filters)
    except (ValueError, TypeError):
        return "INVALID_TOOL_SCHEMA"
    text = " ".join(
        (candidate.question, candidate.expected_discriminator, str(candidate.filters))
    ).lower()
    if any(
        marker in text
        for marker in (
            "private/",
            "private\\",
            "ground_truth",
            "ground-truth",
            "oraclestore",
            "scenario_family",
            "oracle",
            "test_label",
        )
    ):
        return "UNSUPPORTED_QUESTION"
    if not candidate.question.strip() or not candidate.expected_discriminator.strip():
        return "UNSUPPORTED_QUESTION"
    observed = set(visible.evidence_ids)
    mentioned = set(re.findall(r"\b(?:evidence|ev|e)[_-][A-Za-z0-9_.-]+", text, re.IGNORECASE))
    if not mentioned.issubset({eid.lower() for eid in observed}):
        return "UNOBSERVED_EVIDENCE_ID"
    if not set(candidate.prerequisites).issubset(observed):
        return "UNSATISFIED_PREREQUISITE"
    if not set(candidate.target_hypothesis_ids).issubset(
        {h.hypothesis_id for h in visible.hypotheses}
    ):
        return "UNKNOWN_HYPOTHESIS"
    if "ids" in candidate.filters and (
        not isinstance(candidate.filters["ids"], list)
        or any(not isinstance(eid, str) or eid not in observed for eid in candidate.filters["ids"])
    ):
        return "UNOBSERVED_EVIDENCE_ID"
    if "change_id" in candidate.filters and (
        not isinstance(candidate.filters["change_id"], str)
        or candidate.filters["change_id"] not in visible.observed_change_ids
    ):
        return "UNOBSERVED_EVIDENCE_ID"
    if (
        candidate.filters.get("service") is not None
        and candidate.filters["service"] not in visible.public_summary.services
    ):
        return "INVALID_SERVICE"
    times = {}
    try:
        for field in ("start_ts", "end_ts"):
            if candidate.filters.get(field) is not None:
                value = candidate.filters[field]
                if not isinstance(value, str):
                    return "INVALID_TIME_WINDOW"
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    return "INVALID_TIME_WINDOW"
                times[field] = parsed
        if len(times) == 2 and times["start_ts"] > times["end_ts"]:
            return "INVALID_TIME_WINDOW"
    except (ValueError, TypeError):
        return "INVALID_TIME_WINDOW"
    # Task filters are partial planning hints. Validate every supplied field against
    # at least one allowed existing tool schema, without inventing required args.
    valid = False
    tool_filters = dict(candidate.filters)
    if "database_internal" in tool_filters:
        if not isinstance(tool_filters.pop("database_internal"), bool):
            return "INVALID_TOOL_SCHEMA"
    for tool in candidate.allowed_tools:
        fields = ARGUMENT_MODELS[tool].model_fields
        if not set(tool_filters).issubset(fields):
            continue
        try:
            for name, value in tool_filters.items():
                field = fields[name]
                adapter = TypeAdapter(field.rebuild_annotation())
                adapter.validate_python(times.get(name, value), strict=True)
            valid = True
        except (ValidationError, ValueError, TypeError):
            continue
    if not valid:
        return "INVALID_TOOL_SCHEMA"
    if candidate_signature(candidate) in visible.completed_signatures:
        return "DUPLICATE_COMPLETED_CHECK"
    if (
        budget.remaining_requests
        < (2 + config.reserve_verifier_requests) * budget.physical_request_multiplier
    ):
        return "INSUFFICIENT_LLM_BUDGET"
    # One allowed tool schema can be invoked twice by the Investigator plan.
    # Reserve the fixed conservative plan cap, not the number of tool names.
    if budget.remaining_tools < 2 + config.reserve_verifier_tools:
        return "INSUFFICIENT_TOOL_BUDGET"
    if budget.remaining_seconds <= 0:
        return "INSUFFICIENT_WALL_BUDGET"
    return None
