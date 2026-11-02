# Individual Contribution Statement

**COMP5584 Large Language Models for Agents — Group Project**

Submission deadline: **23 November 2026, 11:59 PM**. Upload on Canvas by one group member.

---

## Instructions (delete this section before submitting)

1. Fill one row per group member. Add or remove rows to match the actual group size.
2. Describe the **module(s) or component(s)** the member was responsible for, and how that
   work **interacts with or contributes to** other members' modules. The course guidelines
   ask for both parts; a bare list of tasks is not enough.
3. Percentages must sum to **100%** across the group. Use the same granularity for everyone.
4. Contributions are individual grades' evidence. Members who made no substantive
   contribution receive no marks, so describe what was actually delivered, not intentions.
5. Keep this file as `Individual_Contribution_Statement.pdf` in the submission archive.
6. Nothing in this template is pre-filled: the group completes it from its own records.

---

## Statement

| # | Member name | Student ID | Module(s) / component(s) responsible for | Interaction with other members' modules | Contribution |
| ---: | --- | --- | --- | --- | ---: |
| 1 |  |  |  |  |  % |
| 2 |  |  |  |  |  % |
| 3 |  |  |  |  |  % |
| 4 |  |  |  |  |  % |
| 5 |  |  |  |  |  % |
| 6 |  |  |  |  |  % |
| | | | | **Total** | **100%** |

### Member 1 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

### Member 2 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

### Member 3 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

### Member 4 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

### Member 5 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

### Member 6 — detailed description

- **Modules owned:**

- **Key deliverables (with file paths or commits if available):**

- **Interfaces provided to / consumed from other modules:**

- **Work this member reviewed or integrated:**

---

## Sign-off

By submitting this statement the group confirms that the descriptions above are accurate and
that each member's stated contribution matches the work delivered.

| Member name | Signature / confirmation | Date |
| --- | --- | --- |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

---

## Module map (for reference, not a claim about who did what)

The project decomposes into modules that map onto the course rubric's "Multi-Agent System
Design" and "Technical Implementation" criteria. Use this list only as a vocabulary when
writing the rows above; do not copy it as an allocation.

| Area | Where it lives | What it covers |
| --- | --- | --- |
| Orchestration graph and state | `src/incident_lens/orchestration/` | LangGraph nodes, routing, budget, stop protocol |
| Deterministic gates | `src/incident_lens/orchestration/guards.py` | Grounding, competitor and verifier checks |
| Contracts and schemas | `src/incident_lens/schemas/` | Typed state, findings, reports, workflow options |
| Agent services and roles | `src/incident_lens/agents/` | Coordinator, specialists, verifier, remediation |
| Tools and evidence provider | `src/incident_lens/tools/` | Read-only public-file access, query tools |
| Security and isolation | `src/incident_lens/security/` | Role ACL, immutable context, observation ledger |
| LLM providers and cache | `src/incident_lens/llm/` | Mock and real adapters, structured-output repair |
| Evaluation and benchmark | `src/incident_lens/evaluation/`, `src/incident_lens/incidentbench/`, `analysis/` | Batch runner, scoring, hardened report |
| CLI | `src/incident_lens/cli.py` | run, replay, validate-data, web, list-cases |
| Web dashboard | `src/incident_lens/web/` | Starlette API, SPA views, replay console |
| Tests | `tests/` | Unit, integration, isolation, reliability, evaluation, web |
| Documentation and presentation | `docs/`, `presentation/`, `submission/` | Guides, architecture, evaluation, deck, script, QA |
