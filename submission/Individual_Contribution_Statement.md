# Individual Contribution Statement

**COMP5584 Large Language Models for Agents — Group Project**

**Group No.: 5** — Topic: *IncidentLens: An Evidence-Driven Multi-Agent System for Software Incident Investigation*

Submission deadline: **23 November 2026, 11:59 PM**. Upload on Canvas by one group member.

---

## Statement

| # | Member name | Student ID | Module(s) / component(s) responsible for | Interaction with other members' modules | Contribution |
| ---: | --- | --- | --- | --- | ---: |
| 1 | YANG Ziting | 25050315G | System evaluation and system integration; system architecture optimisation | Designed the evaluation protocol and the four-architecture matched comparison with the architecture workstream; integrated the agents, gates and web dashboard into a single runnable system; fed architecture-optimisation requirements back to MA Jiyuan's agent-workflow design | % |
| 2 | MA Jiyuan | 25116696G | System architecture; agent workflow development | Defined the LangGraph orchestration graph, coordinator dispatch and role contracts consumed by the evaluation workstream and the specialists' tools; his workflow interfaces are what YANG Ziting's integration and architecture optimisation built on | % |
| 3 | Song Xiaowen | 25058859G |  |  | % |
| 4 | Zhang Boxin | 25054717G |  |  | % |
| 5 | YE Mingxi | 25065994G |  |  | % |
| 6 | WANG Huixuechun | 25064113G |  |  | % |
| | | | | **Total** | **100%** |

### Member 1 — YANG Ziting (25050315G)

- **Modules owned:** system evaluation; system integration; system architecture optimisation.
- **Key deliverables:** the matched four-architecture evaluation (Single / Fixed-4 / Dynamic / Dynamic + verifier) over the 36-case hardened corpus, 144 slots, with scoring and failure analysis (`docs/EVALUATION.md`, `analysis/wp_d/reports/hardened144-20261101/`); end-to-end integration of the orchestration graph, deterministic gates, CLI, web dashboard and tests into one runnable system (`src/incident_lens/`, `pyproject.toml`, `requirements.lock`); architecture-optimisation changes arising from the measured results (budget handling, ablation boundaries).
- **Interfaces provided to / consumed from other members' modules:** consumed MA Jiyuan's agent-workflow interfaces (coordinator decisions, task dispatch, role findings) as the system boundary the evaluation measures; provided the measured per-architecture results that justified the primary-architecture choice and the architecture-optimisation work.
- **Work this member reviewed or integrated:** integrated and regression-tested all members' modules; the full test suite (1,179 passed, 0 failed, 2026-11-02) ran against the integrated tree.

### Member 2 — MA Jiyuan (25116696G)

- **Modules owned:** system architecture; agent workflow development.
- **Key deliverables:** the overall system architecture and the multi-agent workflow (`src/incident_lens/orchestration/`, `src/incident_lens/agents/`): the LangGraph `StateGraph`, the coordinator's INVESTIGATE / FINALIZE / ABSTAIN decisions and bounded dispatch, the specialist agents (logs, metrics/dependencies, database, changes), Merge and FinalizeGate, and the cited-or-abstain contract.
- **Interfaces provided to / consumed from other members' modules:** provided the workflow interfaces — coordinator decisions, task payloads, role findings and gate state — that YANG Ziting's evaluation measures and that system integration wires together; consumed the evaluation's measured results as the feedback loop for architecture optimisation.

### Members 3–6 — descriptions to be completed by the members themselves

Members 3–6 (Song Xiaowen, Zhang Boxin, YE Mingxi, WANG Huixuechun) describe their own
modules, deliverables and interactions in the table above and in their own sections here.

---

## Sign-off

By submitting this statement the group confirms that the descriptions above are accurate and
that each member's stated contribution matches the work delivered.

| Member name | Signature / confirmation | Date |
| --- | --- | --- |
| YANG Ziting |  |  |
| MA Jiyuan |  |  |
| Song Xiaowen |  |  |
| Zhang Boxin |  |  |
| YE Mingxi |  |  |
| WANG Huixuechun |  |  |

---

> **Percentages left blank by design.** The group as a whole agrees on the contribution split;
> only YANG Ziting's and MA Jiyuan's responsibilities were supplied to the document preparer,
> so their rows are filled and every member's percentage is left for the group to agree and
> complete before export to PDF.
