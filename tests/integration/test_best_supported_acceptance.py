"""Acceptance policy, scoped coverage and strict generation regressions (offline)."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from incident_lens.agents.service import ReviewOutput, plan_tools
from incident_lens.llm.mock import MockProvider
from incident_lens.orchestration.evidence_board import database_coverage
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import cause_discriminator, finalize_errors
from incident_lens.orchestration.report import populate_assessment
from incident_lens.schemas import Review


async def test_accepted_root_keeps_causal_limits_without_inventing_request_links():
    state = await run_investigation("incident_001", MockProvider())
    root = state.report.root_cause
    root.open_questions = ["The exact request/session join is unavailable"]
    state.open_questions = ["The complete recovery timeline is unavailable"]
    populate_assessment(state)
    assert state.report.acceptance_standard == "BEST_SUPPORTED_AVAILABLE"
    assert root.open_questions[0] in state.report.causal_limitations
    assert state.open_questions[0] in state.report.causal_limitations
    assert state.report.status == "RESOLVED"


async def test_best_supported_selection_still_rejects_missing_mechanism_and_counterevidence():
    state = await run_investigation("incident_001", MockProvider())
    root = state.report.root_cause
    symptoms_only = root.model_copy(update={
        "support_ids": [eid for eid in root.support_ids
                        if not cause_discriminator(root, state.evidence_index[eid])],
        "open_questions": [],
    })
    assert "No observed cause-specific discriminator for the candidate" in finalize_errors(
        state, symptoms_only, "single")
    contradicted = root.model_copy(update={"against_ids": [root.support_ids[0]]})
    assert "Candidate has contradictory evidence" in finalize_errors(state, contradicted, "single")


async def test_service_owned_failure_logs_require_independent_corroboration():
    state = await run_investigation("incident_003", MockProvider())
    root = state.report.root_cause
    own_log = next(record for record in state.evidence_index.values()
                   if record.source_type == "logs" and record.service == root.culprit_service)
    assert cause_discriminator(root, own_log)
    only_log = root.model_copy(update={"support_ids": [own_log.evidence_id]})
    assert "Need at least two supporting records from different sources" in finalize_errors(
        state, only_log, "single")
    client_log = own_log.model_copy(update={"service": "backend"})
    assert not cause_discriminator(root, client_log)


def test_database_coverage_does_not_treat_connections_as_lock_or_slow_query_checks():
    state = SimpleNamespace(evidence_index={}, public_summary=SimpleNamespace(services=["postgres"]))
    history = [{"tool_name": "get_db_connections", "args": {"service": "postgres"},
                "ok": True, "completed": True, "record_count": 0,
                "next_cursor": None, "evidence_ids": [], "error_code": None}]
    acl = {"database": ["get_db_connections", "get_db_lock_waits", "get_db_slow_queries"]}
    coverage = {row["category"]: row for row in database_coverage(state, history, acl)}
    assert coverage["connections"]["scopes"][0]["status"] == "complete_empty"
    assert coverage["lock_waits"]["status"] == coverage["slow_queries"]["status"] == "unqueried"
    history[0]["completed"] = False
    coverage = database_coverage(state, history, acl)
    assert coverage[0]["scopes"][0]["status"] == "partial"
    history[0]["ok"] = False
    assert database_coverage(state, history, acl)[0]["scopes"][0]["status"] == "failed"


def test_generation_rejects_conflicting_leading_endorsement_without_breaking_old_traces():
    payload = {"target_hypothesis_id": "candidate", "verdict": "insufficient",
               "likely_hypothesis_supported": True, "likely_blockers": ["Observed rival mechanism"],
               "rationale": "Conflicting assessment", "cited_evidence_ids": ["E1"]}
    with pytest.raises(ValidationError, match="leading_review_consistency"):
        ReviewOutput.model_validate_json(json.dumps(payload))
    assert Review.model_validate_json(json.dumps(payload)).likely_blockers


@pytest.mark.parametrize("limit", [50, 100])
async def test_tool_output_schema_enforces_record_limit_before_dispatch(limit):
    class Planned:
        async def structured_call(self, role, prompt, payload, output_model):
            schema = output_model.model_json_schema()
            args = next(value for value in schema["$defs"].values()
                        if "limit" in value.get("properties", {})
                        and "start_ts" in value["properties"])
            assert args["additionalProperties"] is False
            assert args["properties"]["limit"]["maximum"] == 50
            return output_model.model_validate_json(json.dumps({"calls": [{
                "tool_name": "get_db_lock_waits", "args": {"service": "postgres", "limit": limit,
                "start_ts": "2026-01-01T00:00:00Z", "end_ts": "2026-01-01T01:00:00Z"},
            }]})), {}

    async def plan():
        return await plan_tools(Planned(), {"role": "database", "allowed_tools": ["get_db_lock_waits"]},
                                {"role": "database", "allowed_tools": ["get_db_lock_waits"]},
                                {"services": ["postgres"]}, {})

    if limit == 100:
        with pytest.raises(ValidationError):
            await plan()
    else:
        result, _ = await plan()
        assert result.calls[0].args["limit"] == 50
