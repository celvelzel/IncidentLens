# Documentation map

`docs/` separates current guidance from frozen contracts, benchmark records and
version archives. Start with the task, not the folder.

## Start here

| I need to... | Read |
| --- | --- |
| take over the course project (testing, report, slides, demo, presentation) | [handoff/project-handoff.zh-CN.md](handoff/project-handoff.zh-CN.md) (中文) or the [HTML briefing](handoff/project-handoff.zh-CN.html) |
| run or configure the system | [guides/readme-guide.md](guides/readme-guide.md) · [中文](guides/readme-guide.zh-CN.md) |
| understand the architecture | [code_wiki/README.md](code_wiki/README.md) |
| record a demo | [guides/demo.md](guides/demo.md) |
| evaluate variants and score a run | [guides/evaluation.md](guides/evaluation.md) |
| work on IncidentBench | [incidentbench/README.md](incidentbench/README.md) |
| review what was accepted and rejected | [acceptance/](acceptance/) |
| plan the next iteration | [guides/optimization-roadmap.zh-CN.md](guides/optimization-roadmap.zh-CN.md) (中文) |

## Layout

| Path | Contents | Notes |
| --- | --- | --- |
| `handoff/` | Ownership-transfer documents | Index: [handoff/README.md](handoff/README.md). Current onboarding, IncidentBench handoffs and per-version (v1.5/v1.6) handoffs. |
| `guides/` | Task-oriented guides | Operations, demo, evaluation, analysis, cache, offline CI and the roadmap. |
| `reference/` | Frozen contracts and planning references | Investigation protocol, phase ownership, contribution matrix and the v1.2 interface freeze (historical; later freezes live in the version folders). |
| `code_wiki/` | Deep developer reference | Architecture, module map, orchestration, contracts, tools, LLM/cache, evaluation, interfaces, testing and symbol index. |
| `contracts/` | Exported Pydantic JSON schemas | Regenerate with `python -m incident_lens.cli export-schemas`. |
| `incidentbench/` | Benchmark protocol and dataset records | Scenarios, fairness, audits, release reports and the v1.6 dataset records. |
| `evaluation/` | v1.6 evaluation protocol and Stage 0 evidence | See also [guides/evaluation.md](guides/evaluation.md). |
| `acceptance/` | Dated acceptance evidence | P0-P7 and version gates, with JSON companions where applicable. |
| `plans/` | Implementation plans | Historical plans, including `plans/v16/`. |
| `monitoring/` | Dated read-only monitoring specs | One subfolder per monitored batch. |
| `source/` | Original Notion design/plan snapshots | Imported 2026-10-11. |
| `ui/` | UI replay notes and screenshots | Evidence images under `ui/v16-evidence/`. |
| `v1.3/`, `v1.5/`, `v16/` | Per-version design, contracts, QA and results | Handoff documents live in `handoff/<version>/`. |

## Conventions

- Handoff documents go in `handoff/`. Name current ones `<scope>-handoff.md` and
  dated historical ones `<YYYY-MM-DD>-<slug>.md`.
- Version archives and acceptance records are append-only. New work should not
  rewrite their evidence.
- `results/` and `analysis/` sit outside `docs/`: `results/` holds run evidence,
  `analysis/` holds WP-D reports and recomputation scripts.
- Relative links are used throughout; when a page moves, update its inbound
  links rather than leaving redirects.
