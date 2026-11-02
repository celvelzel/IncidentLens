# Documentation map

`docs/` separates current guidance from frozen contracts, benchmark records and version
archives. Start with the task, not the folder.

The current submission set is the seven documents linked under "Current submission
documents" plus this map. Older deep guides remain valid as implementation references unless
they conflict with the current code or `docs/submission/source_of_truth.md`. When a conflict
exists, the current implementation and the fact sheet win; the older document should be read
as history and the disagreement reported rather than silently copied.

## Start here

| I need to... | Read |
| --- | --- |
| understand the project at a glance | [../README.md](../README.md) |
| install, run, replay or package the system | [RUN_GUIDE.md](RUN_GUIDE.md) |
| understand the graph, state, gates and security | [ARCHITECTURE.md](ARCHITECTURE.md) |
| understand roles, coordination and hypothesis lifecycle | [AGENT_DESIGN.md](AGENT_DESIGN.md) |
| inspect the measurements, denominators and validity threats | [EVALUATION.md](EVALUATION.md) |
| record or deliver an 8-10 minute demo | [DEMO_GUIDE.md](DEMO_GUIDE.md) |
| see what the project does not establish | [LIMITATIONS.md](LIMITATIONS.md) |
| take over the course submission (deck, script, demo website, checklist) | [handoff/](handoff/) — see [handoff/submission-package/README.md](handoff/submission-package/README.md) (中文) |
| run or configure the system with the older deep guide | [guides/readme-guide.md](guides/readme-guide.md) · [中文](guides/readme-guide.zh-CN.md) |
| understand the architecture module by module | [code_wiki/README.md](code_wiki/README.md) |
| record a demo using the older guide | [guides/demo.md](guides/demo.md) |
| evaluate variants and score a run with the older guide | [guides/evaluation.md](guides/evaluation.md) |
| work on IncidentBench | [incidentbench/README.md](incidentbench/README.md) |
| review what was accepted and rejected | [acceptance/](acceptance/) |
| plan the next iteration | [guides/optimization-roadmap.zh-CN.md](guides/optimization-roadmap.zh-CN.md) (中文) |
| check the rubric mapping or the authoritative fact sheet | [submission/](submission/) |
| rehearse the talk or prepare for Q&A | [../presentation/Presentation_Script.md](../presentation/Presentation_Script.md) · [QA_Preparation.md](../presentation/QA_Preparation.md) |
| assemble the submission archive | [../submission/SUBMISSION_CHECKLIST.md](../submission/SUBMISSION_CHECKLIST.md) |

## Current submission documents

| Document | Purpose |
| --- | --- |
| [../README.md](../README.md) | Front door: problem, contract, quick start, architecture summary, results, limitations, documentation map |
| [RUN_GUIDE.md](RUN_GUIDE.md) | Prerequisites, installation, Mock workflow, variants, replay, dashboard, real provider, budgets, artifacts, tests, troubleshooting, packaging |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System context, LangGraph nodes and routing, state and contracts, deterministic Merge and FinalizeGate, provenance, recovery, replay, extension points |
| [AGENT_DESIGN.md](AGENT_DESIGN.md) | Role catalog and ACL, coordinator policy, assignment limits, hypothesis lifecycle, merge reconciliation, verifier ablation, stop protocol, failure taxonomy, trade-offs |
| [EVALUATION.md](EVALUATION.md) | Research questions, corpus, matched variants, metrics, hardened 144-slot results, 10-case replication, levers, paired results, ablations, validity, non-claims |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | 8-10 minute plan for dashboard and CLI, setup checklist, click path, provenance and abstention moments, fallbacks, recording checklist |
| [LIMITATIONS.md](LIMITATIONS.md) | Technical, empirical, ethical and scope limits; over-abstention; what would change the conclusions |

## Layout

| Path | Contents | Notes |
| --- | --- | --- |
| `RUN_GUIDE.md`, `ARCHITECTURE.md`, `AGENT_DESIGN.md`, `EVALUATION.md`, `DEMO_GUIDE.md`, `LIMITATIONS.md` | Current submission documents | First-class entry points; older deep guides below remain discoverable |
| `submission/` | Authoritative submission facts and rubric mapping | [source_of_truth.md](submission/source_of_truth.md) wins conflicts with older docs; [rubric_alignment.md](submission/rubric_alignment.md) maps criteria to artifacts |
| `../presentation/` | Final deck, PDF, renders, script, Q&A and the build script | `IncidentLens_Deck.pptx` is the editable source; `build_deck.py` regenerates it |
| `../submission/` | Contribution statement template and submission checklist | The statement is blank by design; the group completes it |
| `project_guidelines/` | Course brief | `COMP5584_project_guidelines.pdf`; assessment weights are summarized in the rubric alignment |
| `handoff/` | Ownership-transfer documents | Index: [handoff/README.md](handoff/README.md). Current onboarding, IncidentBench handoffs and per-version (v1.5/v1.6) handoffs. |
| `guides/` | Task-oriented guides | Operations, demo, evaluation, analysis, cache, offline CI and the roadmap. |
| `reference/` | Frozen contracts and planning references | Investigation protocol, phase ownership, contribution matrix and the v1.2 interface freeze (historical; later freezes live in the version folders). Some frozen values are older than the current implementation; check `source_of_truth.md`. |
| `code_wiki/` | Deep developer reference | Architecture, module map, orchestration, contracts, tools, LLM/cache, evaluation, interfaces, testing and symbol index. |
| `contracts/` | Exported Pydantic JSON schemas | Regenerate with `python -m incident_lens.cli export-schemas`. |
| `incidentbench/` | Benchmark protocol and dataset records | Scenarios, fairness, audits, release reports and the v1.6 dataset records. |
| `evaluation/` | v1.6 evaluation protocol and Stage 0 evidence | See also [EVALUATION.md](EVALUATION.md) and the older [guides/evaluation.md](guides/evaluation.md). |
| `acceptance/` | Dated acceptance evidence | P0-P7 and version gates, with JSON companions where applicable. |
| `plans/` | Implementation plans | Historical plans, including `plans/v16/`. |
| `monitoring/` | Dated read-only monitoring specs | One subfolder per monitored batch. |
| `source/` | Original Notion design/plan snapshots | Imported 2026-10-11. |
| `ui/` | UI replay notes and screenshots | Evidence images under `ui/v16-evidence/`. |
| `v1.3/`, `v1.5/`, `v16/` | Per-version design, contracts, QA and results | Handoff documents live in `handoff/<version>/`. |

## Conventions

- Current submission documents live at the top level of `docs/`; task guides live in
  `guides/`, frozen contracts in `reference/`, and dated evidence in the version and
  acceptance folders.
- `docs/submission/source_of_truth.md` is the authoritative fact sheet for version, results,
  labels and known conflicts. It takes precedence over older prose when the two disagree.
- Handoff documents go in `handoff/`. Name current ones `<scope>-handoff.md` and
  dated historical ones `<YYYY-MM-DD>-<slug>.md`.
- Version archives and acceptance records are append-only. New work should not
  rewrite their evidence.
- `results/` and `analysis/` sit outside `docs/`: `results/` holds run evidence,
  `analysis/` holds WP-D reports and recomputation scripts.
- Relative links are used throughout; when a page moves, update its inbound
  links rather than leaving redirects.
