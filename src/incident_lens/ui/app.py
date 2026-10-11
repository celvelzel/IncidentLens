"""Minimal offline investigation dashboard; never reads evaluation truth."""

import asyncio
import json
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from incident_lens.artifacts import load_replay, save_run
from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.report import render_report
from incident_lens.security.context import ROLE_TOOL_ACL
from incident_lens.tools import EvidenceProvider

ROOT = Path(__file__).resolve().parents[3]


def render_state(trace, state):
    replay = st.session_state.get("recorded", False)
    st.caption(
        "Recorded Replay · immutable saved trace"
        if replay
        else "Completed investigation · actual backend execution"
    )
    if trace["provider"] == "mock":
        st.info(
            "MOCK · offline deterministic policy. These results are a demonstration, not real-model accuracy."
        )
    metrics = st.columns(5)
    metrics[0].caption("Outcome")
    metrics[0].write(state.report.status)
    metrics[1].metric("Rounds", state.round_index)
    metrics[2].metric("Tool calls", f"{state.tool_calls_used} / {state.budgets.max_tool_calls}")
    metrics[3].metric("Model requests", f"{state.llm_calls_used} / {state.budgets.max_llm_calls}")
    hits = sum(e.event_type == "CACHE_HIT" for e in state.events)
    metrics[4].metric("Cache hits", hits)
    st.caption(
        f"{state.incident_id} · {state.run_id} · {trace.get('model_id', 'unknown model')} · cache={trace.get('cache_mode', 'off')}"
    )
    timeline, board = st.columns([3, 2])
    with timeline:
        st.subheader("Investigation timeline")
        roles = ["All"] + sorted({e.role for e in state.events if e.role})
        selected = st.selectbox("Filter by role", roles)
        for event in state.events:
            if selected != "All" and event.role != selected:
                continue
            if event.event_type == "LLM_CALL":
                continue
            label = f"{event.event_id} · {event.role or 'runtime'} · {event.event_type}"
            details = event.details
            if event.event_type == "TOOL_CALL":
                result = details.get("result", {})
                label += f" · {details.get('tool_name', 'tool')} · {result.get('record_count', 0)} records"
            with st.expander(label, expanded=event.event_type in {"DECISION", "REVIEW"}):
                if event.message:
                    st.write(event.message)
                if "decision" in details:
                    decision = details["decision"]
                    st.write(f"Action: {decision['action']}")
                    for task in decision.get("assignments", []):
                        st.write(f"{task['role']}: {task['question']}")
                        st.caption("Discriminator: " + task["expected_discriminator"])
                elif "review" in details:
                    review = details["review"]
                    st.write(f"Verdict: {review['verdict']}")
                    st.write(review["rationale"])
                    for contradiction in review.get("contradictions", []):
                        st.warning(contradiction)
                    for check in review.get("requested_checks", []):
                        st.write("Requested check: " + check["question"])
                elif event.event_type == "TOOL_CALL":
                    st.json(details.get("result", {}))
                else:
                    st.json(details)
    with board:
        st.subheader("Hypothesis board")
        for hypothesis in state.hypotheses:
            status = (
                "SUPPORTED"
                if state.report.root_cause
                and state.report.root_cause.hypothesis_id == hypothesis.hypothesis_id
                else hypothesis.status
            )
            with st.container(border=True):
                st.write(f"{status} · {hypothesis.culprit_service}")
                st.write(hypothesis.failure_mode)
                st.caption("Support: " + (", ".join(hypothesis.support_ids) or "none"))
                st.caption("Against: " + (", ".join(hypothesis.against_ids) or "none"))
        with st.expander("Role and tool permissions"):
            st.dataframe(
                [
                    {"role": role, "allowed_tools": ", ".join(tools) or "none"}
                    for role, tools in ROLE_TOOL_ACL.items()
                ],
                hide_index=True,
            )
        with st.expander("Observed evidence registry"):
            st.dataframe(
                [
                    {
                        "ID": record.evidence_id,
                        "service": record.service,
                        "source": record.source_path,
                        "time": record.observed_at.isoformat(),
                    }
                    for record in state.evidence_index.values()
                ],
                hide_index=True,
            )
    st.divider()
    st.subheader("Root cause report")
    st.markdown(render_report(state.report))
    st.download_button(
        "Download trace",
        json.dumps(trace, indent=2, ensure_ascii=False),
        file_name="trace.json",
        mime="application/json",
    )
    st.download_button(
        "Download report", render_report(state.report), file_name="report.md", mime="text/markdown"
    )


def main():
    st.set_page_config(page_title="IncidentLens", layout="wide")
    st.title("IncidentLens")
    st.caption("Evidence-driven software incident investigation")
    load_dotenv(ROOT / ".env")
    provider = EvidenceProvider(ROOT / "data")
    with st.sidebar:
        st.header("Investigation")
        mode = st.radio("Mode", ["Run investigation", "Recorded Replay"])
        if mode == "Run investigation":
            cases = provider.list_cases()
            incident = st.selectbox("Incident", [c.incident_id for c in cases])
            llm = st.selectbox("Provider", ["mock", "real"])
            cache_mode = st.selectbox("Local explanation cache", ["off", "semantic", "exact"])
            st.caption("Limits: 4 rounds · 12 tools · 16 model requests · 90 seconds")
            if st.button("Run investigation", type="primary"):
                try:
                    model = (
                        MockProvider()
                        if llm == "mock"
                        else RealChatProvider(
                            os.getenv("INCIDENT_LENS_BASE_URL"),
                            os.getenv("INCIDENT_LENS_API_KEY"),
                            os.getenv("INCIDENT_LENS_MODEL"),
                        )
                    )
                    cache = None
                    if cache_mode != "off":
                        from incident_lens.cache.policy import CachePolicy
                        from incident_lens.cache.semantic import SemanticCacheAdapter

                        cache = SemanticCacheAdapter(
                            CachePolicy(mode=cache_mode),
                            ROOT / "results/ui-cache.sqlite",
                            provider.dataset_revision,
                        )
                    with st.spinner("Investigating public evidence..."):
                        started = time.monotonic()
                        state = asyncio.run(
                            run_investigation(incident, model, ROOT / "data", cache=cache)
                        )
                        trace = save_run(
                            state,
                            ROOT / "results/ui" / state.run_id,
                            llm,
                            cache_mode=cache_mode,
                            elapsed_ms=(time.monotonic() - started) * 1000,
                        )
                    st.session_state["trace"] = trace
                    st.session_state["investigation"] = state
                    st.session_state["recorded"] = False
                except ProviderError as exc:
                    st.error(exc.code)
                except (ValueError, OSError) as exc:
                    st.error(f"{type(exc).__name__}: configuration or data error")
        else:
            traces = sorted((ROOT / "results").glob("**/trace.json"))
            if traces:
                path = st.selectbox(
                    "Saved trace", traces, format_func=lambda p: str(p.relative_to(ROOT))
                )
                if st.button("Load recorded trace", type="primary"):
                    try:
                        trace, state = load_replay(path)
                        st.session_state.update(trace=trace, investigation=state, recorded=True)
                    except (ValueError, OSError, KeyError):
                        st.error("Invalid recorded trace")
            else:
                st.info("Run a case with the CLI or this dashboard to create a trace.")
    if "investigation" in st.session_state:
        render_state(st.session_state["trace"], st.session_state["investigation"])
    else:
        st.info("Choose an incident and run the investigation, or load a recorded trace.")
        st.markdown(
            "Coordinator → Role-scoped tools → Validated merge → Verifier → Replan or report"
        )


if __name__ == "__main__":
    main()
