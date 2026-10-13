import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "analyze_eval", Path(__file__).resolve().parents[2] / "scripts/analyze_eval.py"
)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def record():
    evidence = dict(
        evidence_id="e1",
        incident_id="case",
        source_path="public/logs.jsonl",
        excerpt="request timed out",
    )
    return dict(
        metrics=dict(variant="full", root_cause_correct=False),
        state=dict(
            incident_id="case",
            run_id="run",
            round_index=2,
            evidence_index={"e1": evidence},
            report=dict(
                status="RESOLVED",
                root_cause=dict(
                    culprit_service="api", failure_mode="external_timeout", support_ids=["e1"]
                ),
                causal_chain=["external timeout causes API failure"],
                supporting_evidence_ids=["e1", "missing"],
            ),
            events=[
                dict(
                    event_type="DECISION",
                    details=dict(
                        decision=dict(action="INVESTIGATE", assignments=[dict(role="logs")])
                    ),
                ),
                dict(
                    event_type="REVIEW",
                    details=dict(
                        review=dict(verdict="insufficient", requested_checks=[dict(role="metrics")])
                    ),
                ),
                dict(
                    event_type="DECISION",
                    details=dict(
                        decision=dict(action="INVESTIGATE", assignments=[dict(role="metrics")])
                    ),
                ),
                dict(
                    event_type="REVIEW",
                    details=dict(review=dict(verdict="conflicted", requested_checks=[])),
                ),
                dict(event_type="TOOL_CALL", details=dict(result=dict(records=[evidence]))),
            ],
        ),
        oracle_scoring_fields=dict(
            is_identifiable=True,
            culprit_service="api",
            failure_mode="external_timeout",
            misleading_evidence_ids=["decoy"],
        ),
    )


def test_counts_slices_and_actual_citations():
    first = record()
    stopped = copy.deepcopy(first)
    stopped["state"]["events"].append(dict(event_type="STOP"))
    rows, slices, bundle = analysis.analyze([first, stopped])
    assert rows[0]["rounds"] == rows[0]["investigate_decisions"] == 2
    assert rows[0]["replanning_decisions"] == rows[0]["dynamic_role_transitions"] == 1
    assert (
        rows[0]["review_insufficient"]
        == rows[0]["review_conflicted"]
        == rows[0]["requested_checks"]
        == rows[0]["tool_calls"]
        == 1
    )
    assert json.loads(rows[0]["task_roles"]) == ["logs", "metrics"]
    assert slices[0]["n"] == 2
    assert slices[0]["correct"] == slices[0]["runtime_failure"] == 1
    assert slices[0]["correct_rate"] == slices[0]["citation_existence_validity"] == 0.5
    assert bundle["semantic_review_status"] == "awaiting_human"
    review = bundle["runs"][0]
    assert review["missing_cited_evidence_ids"] == ["missing"]
    assert review["cited_evidence"][0]["excerpt"] == "request timed out"
    assert "unsupported_claim_rate" not in review


def test_unidentifiable_abstention_and_slice_separation():
    item = record()
    item["oracle_scoring_fields"].update(is_identifiable=False, misleading_evidence_ids=[])
    item["state"]["report"] = dict(status="INCONCLUSIVE", root_cause=None)
    _, slices, _ = analysis.analyze([record(), item])
    assert len(slices) == 2
    abstain = next(s for s in slices if not s["identifiable"])
    assert abstain["correct_abstention_rate"] == 1
    assert abstain["correct_rate"] is None
    assert abstain["citation_existence_validity"] is None


def test_incomplete_state_rejected_before_oracle_access():
    with pytest.raises(ValueError, match="completed report"):
        analysis.analyze([dict(state=dict(report=None))])


def test_export_preserves_input_and_rejects_existing_output(tmp_path):
    source = tmp_path / "input" / "raw-runs.jsonl"
    source.parent.mkdir()
    original = json.dumps(record()) + "\n"
    source.write_text(original, encoding="utf-8")
    out = tmp_path / "analysis"
    analysis.export(source, out)
    assert source.read_text(encoding="utf-8") == original
    assert {p.name for p in out.iterdir()} == {
        "coordination.csv",
        "mechanism-slices.csv",
        "citation-review.json",
        "coverage.json",
        "followup_examples.json",
        "errors.jsonl",
        "manifest.json",
    }
    with pytest.raises(FileExistsError):
        analysis.export(source, out)
    with pytest.raises(ValueError, match="separate"):
        analysis.export(source, source.parent)


def test_followup_matches_stable_task_and_reports_zero_ordinary():
    item = record()
    events = item["state"]["events"]
    events[1]["event_id"] = "review_1"
    events[2]["event_id"] = "decision_2"
    request = dict(
        task_id="old",
        role="metrics",
        question="check CPU",
        filters={"service": "api"},
        expected_discriminator="CPU spike",
    )
    events[1]["details"]["review"]["requested_checks"] = [request]
    assignment = dict(request, task_id="fresh")
    events[2]["details"]["decision"]["assignments"] = [assignment]
    _, _, bundle = analysis.analyze([item])
    assert bundle["coverage"] == dict(
        mechanisms={"external_timeout": 1}, ordinary=0, misleading=1, complete=1, missing=0
    )
    example = bundle["followup_examples"]["examples"][0]
    assert example["review_event_id"] == "review_1"
    assert example["next_investigate_event_id"] == "decision_2"
    assert example["matched_checks"] == [request]
    assert bundle["followup_examples"]["reviews_with_matched_checks"] == 1
    final_review = bundle["followup_examples"]["examples"][1]
    assert final_review["next_investigate_event_id"] is None
    assert final_review["next_assignments"] == final_review["matched_checks"] == []
    assignment["question"] = "unrelated queue size"
    _, _, bundle = analysis.analyze([item])
    assert bundle["followup_examples"]["examples"][0]["matched_checks"] == []
    assert bundle["followup_examples"]["reviews_with_matched_checks"] == 0


def test_export_preserves_runtime_failure_and_does_not_mark_normal_abstention(tmp_path):
    failed = record()
    failed["state"]["events"].append(
        {"event_type": "STOP", "message": "TIMEOUT", "details": {"stage": "verify"}}
    )
    failed["state"]["report"]["stop_reason"] = "TIMEOUT"
    source = tmp_path / "input" / "raw.jsonl"
    source.parent.mkdir()
    source.write_text(json.dumps(failed) + "\n" + json.dumps(record()) + "\n", encoding="utf-8")
    out = tmp_path / "output"
    analysis.export(source, out)
    errors = [json.loads(line) for line in (out / "errors.jsonl").read_text().splitlines()]
    assert len(errors) == 1 and errors[0]["stop_reason"] == "TIMEOUT"
    assert errors[0]["failure_events"][0]["details"]["stage"] == "verify"
