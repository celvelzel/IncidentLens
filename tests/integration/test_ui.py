import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_mock_run_and_labeled_replay(monkeypatch):
    app = AppTest.from_file(Path("src/incident_lens/ui/app.py").resolve(), default_timeout=30).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    state = app.session_state["investigation"]
    assert state.report.status == "RESOLVED"
    before = state.model_dump_json()
    trace_before = json.dumps(app.session_state["trace"], sort_keys=True)
    assert any("MOCK" in message.value for message in app.info)
    for button in app.get("download_button"):
        button.click().run()
        assert not app.exception
        assert app.session_state["investigation"].model_dump_json() == before
        assert json.dumps(app.session_state["trace"], sort_keys=True) == trace_before

    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not execute graph or provider")

    import incident_lens.orchestration.graph as graph
    from incident_lens.llm.mock import MockProvider
    from incident_lens.llm.provider import RealChatProvider

    monkeypatch.setattr(MockProvider, "structured_call", forbidden)
    monkeypatch.setattr(RealChatProvider, "structured_call", forbidden)
    monkeypatch.setattr(graph, "run_investigation", forbidden)
    app.radio[0].set_value("Recorded Replay").run()
    saved = Path("results/ui") / state.run_id / "trace.json"
    next(box for box in app.selectbox if box.label == "Saved trace").set_value(
        saved.resolve()
    ).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["recorded"] is True
    assert any("Recorded Replay" in caption.value for caption in app.caption)
    assert app.session_state["investigation"].model_dump_json() == before
    assert all(
        "private" not in record.source_path
        for record in app.session_state["investigation"].evidence_index.values()
    )


def test_ui_source_has_no_oracle_loader():
    source = Path("src/incident_lens/ui/app.py").read_text(encoding="utf-8")
    assert "ground_truth" not in source
