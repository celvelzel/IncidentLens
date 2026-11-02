# Handoff documents

A handoff document transfers ownership of a workstream: what was built, what was
verified, what remains open, and where the evidence lives. This folder keeps all
of them together so the version archives stay focused on design and results.

## Submission package (course deliverables, 2026-11-02)

The group-facing copies of the presentation and submission materials live in
[submission-package/](submission-package/): the editable deck (`.pptx` + PDF),
all 21 slide renders, the script and Q&A sheet, a copy of the run guide, the
submission checklist and the blank contribution-statement template. Its
[README](submission-package/README.md) also records how to start the demo
website and where its code lives.

## Current project handoff

| Document | Language | Use |
| --- | --- | --- |
| [project-handoff.zh-CN.md](project-handoff.zh-CN.md) | 中文 | Authoritative course-project onboarding guide: status, evidence, runs, report/slides/demo plan, role checklists. Data as of 2026-11-01. |
| [project-handoff.zh-CN.html](project-handoff.zh-CN.html) | 中文 | Companion briefing page with charts, role tabs and a printable checklist. Same numbers as the Markdown. |

## IncidentBench

| Document | Status | Scope |
| --- | --- | --- |
| [incidentbench/workstream-handoffs.md](incidentbench/workstream-handoffs.md) | Reference | Workstream split (A-E + Lead), required handoff evidence, integrated WP status and open research gates. |
| [incidentbench/v16-review-handoff.md](incidentbench/v16-review-handoff.md) | Pending | Human review transfer for the v1.6 Dev corpus. Zero reviews are recorded; reviewer identities are not assigned. |
| [incidentbench/2026-10-14-rca-fix-notes.md](incidentbench/2026-10-14-rca-fix-notes.md) | Historical | RCA fix and retest handoff for the v1 dataset (2026-10-14). Counts describe that run, not current status. |

## CAES v1.5

| Document | Scope |
| --- | --- |
| [v1.5/wp-a-handoff.md](v1.5/wp-a-handoff.md) | Candidate generation and eligibility. |
| [v1.5/wp-b-handoff.md](v1.5/wp-b-handoff.md) | Feature extraction, cost estimation and selection. |
| [v1.5/wp-c-handoff.md](v1.5/wp-c-handoff.md) | Variant runner, metrics, statistics and replay. |
| [v1.5/wp-d-handoff.md](v1.5/wp-d-handoff.md) | Algorithm spec, fairness protocol, preregistration, development results and future work. |

## v1.6 benchmark

| Document | Scope |
| --- | --- |
| [v16/wp-b-experiment-handoff.md](v16/wp-b-experiment-handoff.md) | WP-B to WP-D benchmark handoff: inputs, access boundary, executable commands and owner-approved reference labels. |

## What a handoff must record

- Base commit, branch/worktree and the exact owned write paths.
- What was implemented and which frozen interfaces it matches.
- Commands actually run, with pass/fail/skip counts - not planned commands.
- Evidence paths and source/data hashes, including which artifacts are local-only.
- Review status, open risks and unresolved limits; separate offline technical
  acceptance from scientific effectiveness acceptance.
- A clear `READY FOR LEAD MERGE: YES | NO` (or an equivalent) conclusion.

Link evidence instead of copying it. Keep numbers consistent with the source
report, and update the report rather than the handoff when results change.
