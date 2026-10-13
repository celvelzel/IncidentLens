"""End-to-end scoring of completed, recovered and failed workflows."""
import copy
import json
from pathlib import Path

import pytest

from incident_lens.evaluation.metrics import aggregate, score_completed
from incident_lens.llm import MockProvider, ProviderError
from incident_lens.orchestration.graph import InvestigationRun, run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.tools import EvidenceProvider


class FlakyModel(MockProvider):
    def __init__(self, role="logs", permanent=False):
        self.role = role
        self.permanent = permanent
        self.failed = False
        if role == "remediation":
            self.model_id = "injected-provider-contract"

    async def structured_call(self, *args):
        if self.role == "remediation" and args[0] == self.role:
            raise ProviderError("INJECTED_PLAN_FAILURE", {"llm_calls": 1, "total_tokens": None})
        output, usage = await super().structured_call(*args)
        if args[0] == self.role and (self.permanent or not self.failed) and (
            self.role == "remediation" or args[-1].__name__ == "AnalysisOutput"
        ):
            self.failed = True
            raise ProviderError("INJECTED_CALL_FAILURE", usage)
        return output, usage


def truth(case="incident_001"):
    return json.loads(Path(f"data/incidents/{case}/private/ground_truth.json").read_text())


async def run(provider=None, case="incident_001", **options):
    return await run_investigation(case, provider or MockProvider(),
                                  budget=Budget(max_llm_calls=40, max_tool_calls=24),
                                  workflow=WorkflowOptions(profile="incident_response", **options))


@pytest.mark.parametrize("remediation", [True, False])
async def test_normal_stop_has_consistent_terminal_result_and_credit(remediation):
    state = await run(remediation_enabled=remediation)
    assert state.termination == state.report.termination
    assert state.termination.reason == ("PLAN_READY" if remediation else "DIAGNOSIS_READY")
    kinds = [e.event_type for e in state.events]
    assert "STOP" not in kinds
    assert kinds.count("WORKFLOW_STOP_REQUESTED") == kinds.count("NORMAL_TERMINATION") == 1
    assert kinds.index("DIAGNOSIS_ACCEPTED") < kinds.index("WORKFLOW_STOP_REQUESTED")
    assert kinds.index("NORMAL_TERMINATION") < kinds.index("REPORT")
    score = score_completed(state.model_dump(mode="json"), truth())
    assert score["protocol_valid"] and score["root_cause_correct"] and score["workflow_success"]
    assert score["remediation_success"] is (True if remediation else None)


async def test_failed_model_retry_keeps_costs_and_restores_diagnosis_credit():
    state = await run(FlakyModel())
    score = score_completed(state.model_dump(mode="json"), truth())
    assert score["root_cause_correct"] and score["workflow_success"]
    assert not score["runtime_failure"]
    assert score["recovered_model_failure_count"] == 1
    failure = next(e for e in state.events if e.event_type == "MODEL_FAILURE")
    assert failure.call_id and failure.task_id
    assert failure.details["attempt_id"] and failure.details["stage"] == "diagnosis"
    assert failure.details["llm_calls"] == 1
    assert state.llm_calls_used > 12


async def test_exhausted_specialist_can_be_bypassed_by_accepted_peer_evidence():
    state = await run(FlakyModel(permanent=True), case="incident_037")
    score = score_completed(state.model_dump(mode="json"), truth("incident_037"))
    assert score["root_cause_correct"] and score["workflow_success"]
    assert score["unrecovered_model_failure_count"] == 2
    assert score["recovered_model_failure_count"] == 0
    accepted = next(e for e in state.events if e.event_type == "DIAGNOSIS_ACCEPTED")
    assert len(accepted.details["degraded_call_ids"]) == 2


@pytest.mark.parametrize("provider_failure", [False, True])
async def test_failed_plan_keeps_diagnosis_credit_and_fails_workflow(monkeypatch, provider_failure):
    if not provider_failure:
        async def broken(*args):
            raise RuntimeError("PLAN_GENERATION_FAILED")
        monkeypatch.setattr("incident_lens.agents.remediation.remediate", broken)
    state = await run(FlakyModel("remediation", permanent=True) if provider_failure else None)
    score = score_completed(state.model_dump(mode="json"), truth())
    assert state.termination.reason == "PLAN_FAILED"
    assert state.workflow_status == state.report.workflow_status == "FAILED"
    assert score["root_cause_correct"] and score["diagnosis_match"]
    assert score["remediation_success"] is False and score["workflow_success"] is False
    assert not score["runtime_failure"] and score["protocol_valid"]


async def test_remediation_transport_failure_is_runtime_failure_but_keeps_diagnosis(monkeypatch):
    async def broken(*args):
        raise ProviderError("PROVIDER_TRANSPORT_ERROR", {"llm_calls": 1, "total_tokens": None})
    monkeypatch.setattr("incident_lens.agents.remediation.remediate", broken)
    state = await run()
    score = score_completed(state.model_dump(mode="json"), truth())
    assert state.termination.reason == "UNRECOVERABLE_ERROR"
    assert state.termination.failure_stage == "remediation"
    assert score["protocol_valid"] and score["runtime_failure"] and score["root_cause_correct"]
    assert score["workflow_success"] is False


async def test_evidence_insufficiency_abstains_normally():
    state = await run(case="incident_040")
    score = score_completed(state.model_dump(mode="json"), truth("incident_040"))
    assert state.termination.reason == "INCONCLUSIVE"
    assert score["correct_abstention"] and score["workflow_success"]


async def test_no_alert_uses_monitoring_oracle_not_rca_abstention():
    sample = EvidenceProvider()._records("incident_001", "metrics")[0]
    sample = sample.model_copy(update={"metadata": {"metric_name": "error_rate", "value": 0.001}})
    state = await run(monitor_mode="manual_snapshot", snapshot=[sample])
    oracle = dict(truth(), is_identifiable=False)
    score = score_completed(state.model_dump(mode="json"), oracle)
    assert score["root_cause_correct"] is score["correct_abstention"] is None
    assert score["workflow_success"] is None
    assert score_completed(state.model_dump(mode="json"), dict(
        oracle, monitoring_expected_alert="NO_ALERT"))["workflow_success"] is True
    assert score_completed(state.model_dump(mode="json"), dict(
        oracle, monitoring_expected_alert="ALERT"))["workflow_success"] is False


async def test_stop_timeout_keeps_accepted_diagnosis(monkeypatch):
    investigation = InvestigationRun(MockProvider(), EvidenceProvider(), "incident_001",
                                    limits=Budget(max_llm_calls=40, max_tool_calls=24),
                                    workflow=WorkflowOptions(profile="incident_response"))
    original = investigation.stop_controller.stop

    async def timeout(reason, active=None):
        await original(reason, active)
        request = next(e for e in investigation.state.events
                       if e.event_type == "WORKFLOW_STOP_REQUESTED")
        request.details["required_roles"] = ["logs"]
        investigation.stop_controller.completed = False
        investigation.runtime_event("STOP_TIMEOUT", missing_roles=["logs"], stop_reason=reason)
    monkeypatch.setattr(investigation.stop_controller, "stop", timeout)
    state = await investigation.run()
    score = score_completed(state.model_dump(mode="json"), truth())
    assert state.termination.reason == "STOP_TIMEOUT" and state.workflow_status == "FAILED"
    assert score["protocol_valid"] and score["runtime_failure"]
    assert score["root_cause_correct"] and not score["stop_completion"]
    assert score["workflow_success"] is False


async def test_unknown_reason_and_conflicts_only_keep_raw_match():
    state = (await run()).model_dump(mode="json")
    for source in ["termination", "report"]:
        changed = copy.deepcopy(state)
        if source == "termination":
            changed[source]["reason"] = "UNKNOWN"
        else:
            changed[source]["termination"]["outcome"] = "FAILED"
        score = score_completed(changed, truth())
        assert score["diagnosis_match"] and not score["root_cause_correct"]
        assert not score["protocol_valid"] and not score["workflow_success"]


def test_aggregation_does_not_mix_scoring_versions_or_drop_unknowns():
    base = dict(variant="full", source="mock", split="dev", status="RESOLVED",
                root_cause_correct=True, correct_abstention=None, misleading_correct=None,
                scoring_version="2")
    rows = [dict(base, workflow_success=True), dict(base, workflow_success=False),
            dict(base, workflow_success=None)]
    total = aggregate(rows)[0]
    assert total["workflow_success_denominator"] == 2
    assert total["workflow_success_failures"] == total["workflow_success_unknown"] == 1
    assert total["workflow_success_rate"] == 0.5
    with pytest.raises(ValueError, match="mixed scoring"):
        aggregate([base, dict(base, scoring_version="legacy")])
