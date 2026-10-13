"""V1.2 controls and rendered plan semantics, without claiming browser validation."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def test_streamlit_response_controls_and_separate_statuses():
    app = AppTest.from_file(Path("src/incident_lens/ui/app.py").resolve(), default_timeout=30).run()
    next(box for box in app.selectbox if box.label == "Workflow profile").set_value(
        "incident_response"
    ).run()
    assert not app.exception
    assert next(box for box in app.selectbox if box.label == "Monitoring mode").value == "legacy"
    app.button[0].click().run()
    assert not app.exception
    report = app.session_state["investigation"].report
    assert report.remediation_status == "PLAN_READY"
    assert app.session_state["investigation"].budgets.max_llm_calls == 24
    assert any(caption.value == "Diagnosis status" for caption in app.caption)
    assert any(caption.value == "Remediation status" for caption in app.caption)
    assert any(caption.value == "Workflow status" for caption in app.caption)
    assert any(caption.value == "Stop confirmation: completed" for caption in app.caption)
    assert report.termination.reason == "PLAN_READY"
    assert any("PLAN_ONLY" in caption.value for caption in app.caption)
    if report.remediation_plan:
        assert report.remediation_plan.execution_mode == "PLAN_ONLY"
        assert any("No remediation was executed" in message.value for message in app.info)


def test_streamlit_bad_snapshot_rejected_before_provider(monkeypatch):
    from incident_lens.llm.mock import MockProvider

    async def forbidden(*args, **kwargs):
        pytest.fail("Malformed snapshot must not call provider")

    monkeypatch.setattr(MockProvider, "structured_call", forbidden)
    app = AppTest.from_file(Path("src/incident_lens/ui/app.py").resolve()).run()
    next(box for box in app.selectbox if box.label == "Workflow profile").set_value(
        "incident_response"
    ).run()
    next(box for box in app.selectbox if box.label == "Monitoring mode").set_value(
        "manual_snapshot"
    ).run()
    app.text_area[0].set_value("{invalid").run()
    app.button[0].click().run()
    assert not app.exception and app.error
    assert "investigation" not in app.session_state


def test_web_plan_component_escapes_untrusted_text_and_keeps_legacy_empty():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node unavailable for ES module rendering check")
    component = Path("src/incident_lens/web/static/js/components.js").resolve().as_uri()
    state = {
        "report": {
            "status": "RESOLVED",
            "diagnosis_status": "RESOLVED",
            "remediation_status": "PLAN_READY",
            "workflow_status": "FINISHED",
            "termination": {
                "reason": "PLAN_READY",
                "outcome": "SUCCESS",
                "stop_completed": True,
                "failure_stage": None,
            },
            "remediation_plan": {
                "objective": "<script>unsafe</script>",
                "affected_services": ["backend"],
                "actions": ["action"],
                "preconditions": ["precondition"],
                "risks": ["risk"],
                "verification_steps": ["verify"],
                "rollback": ["rollback"],
                "evidence_ids": ["e1"],
                "root_cause_version": "version",
            },
        },
        "incident_alert": {
            "status": "ALERT",
            "summary": "alert",
            "affected_services": ["backend"],
            "evidence_ids": ["e1"],
        },
        "task_records": [
            {
                "task_id": "t1",
                "attempt_id": "a1",
                "attempt": 1,
                "role": "database",
                "status": "COMPLETED",
                "error_code": None,
            }
        ],
    }
    script = f"""import {{ workflowReportHtml }} from {json.dumps(component)};
const state = {json.dumps(state)};
const html = workflowReportHtml(state, {{ e1: {{}} }});
if (workflowReportHtml({{ report: {{ status: 'RESOLVED' }} }}) !== '') throw new Error('legacy');
console.log(html);
"""
    result = subprocess.run(
        [node, "--experimental-default-type=module", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "<script>" not in result.stdout and "&lt;script&gt;" in result.stdout
    assert "停止确认：已完成" in result.stdout and "终止结果" in result.stdout
    for expected in ("PLAN_ONLY", "PLAN_READY", "FINISHED", "e1", "a1", "rollback", "precondition"):
        assert expected in result.stdout
