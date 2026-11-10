# IncidentLens version_b

Completed English COMP5584 Group 5 presentation: **21 slides, 15 main + 6 Q&A backup**.

## Deliverables

| File | Use |
| --- | --- |
| [IncidentLens_Deck_version_b.pptx](IncidentLens_Deck_version_b.pptx) | 16:9 presentation, with the corresponding complete English talk track in every slide's speaker notes |
| [IncidentLens_Deck_version_b.pdf](IncidentLens_Deck_version_b.pdf) | Slides-only PDF for viewing or presenting |
| [Presentation_Script_version_b.pdf](Presentation_Script_version_b.pdf) | One slide thumbnail and its verbatim English script per page, ready for rehearsal |
| [speech.md](speech.md) | Editable English script, with one `Slide N` heading per slide |

In PowerPoint, open the Notes pane or Presenter View to read the talk track for the current slide. Slides 16-21 support questions and do not belong to the timed main talk. S1-S6 are suggested speaking blocks, not claims about members' implementation contributions.

## Visual standard

- User-approved PolyU red `#9A0907`, white and restrained navy.
- Arial styling throughout authored slide text, with smaller gray footer notes and legends.
- Typography reference supplied by the user: [MIT Sloan font guidelines](https://mitsloan.mit.edu/brand-guidelines/fonts).
- All visible presentation content is English. The logo uses the supplied emblem and English wordmark, with its Chinese line omitted for this language requirement.

## Format and editability

This is the image-based deck requested through `codex-ppt`. Each slide is one complete generated image. Individual slide text boxes, chart bars and diagram shapes are not separately editable. The English script is editable in `speech.md`, and notes are editable in PowerPoint. Raster slide images have no embedded font-family or point-size metadata.

The confirmed backend was the built-in image tool. Its exact model version is not exposed, a limitation explicitly accepted by the user. All 20 non-sample results were recorded with the bundled `record_slide_result.py`; slide 4 is the accepted sample. Production was performed by the parent agent under the user's single-agent AGENTS.md instruction.

## Source and evidence

- Official requirements: `../../docs/project_guidelines/COMP5584_project_guidelines.pdf`.
- Project facts: `../../docs/submission/source_of_truth.md`, `../../docs/ARCHITECTURE.md`, `../../docs/AGENT_DESIGN.md`.
- Measured results: `../../results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json`.
- This work rechecked saved result counts. It did not run new model experiments or a new full application test suite.
- Study boundaries remain visible: synthetic development cases, provisional labels, one model and one repeat, descriptive comparisons.

## Production and validation records

- [outline.md](outline.md): final outline and source-image mapping.
- [deck_spec.json](deck_spec.json): content and visual brief.
- [origin_image/](origin_image/): 21 final generated PNGs.
- [prompts/](prompts/): saved per-slide image jobs.
- [slide_jobs.json](slide_jobs.json): 20 recorded results and one accepted sample.
- [slide_run_state.json](slide_run_state.json): run-state history.
- [approval_record.md](approval_record.md): approvals, corrections and production boundaries.
- [qa_report.json](qa_report.json): final structural, image and script validation summary.

All 21 slides were visually inspected. Embedded PPTX image bytes match the final PNGs, all 21 notes sections match the English script, and package/geometry validators passed. Both PDFs contain 21 pages. Every handout page was rendered and all script text checked for completeness and page bounds. These checks do not claim native PowerPoint execution was tested.

The previous editable presentation is preserved in [version_a](../version_a/README.md).

## Recheck the shipped artifacts

From the repository root, with project dependencies installed:

```powershell
.venv/Scripts/python.exe presentation/IncidentLens_Deck_version_b/verify_artifacts.py
.venv/Scripts/python.exe analysis/submission/consistency_check.py
```

The first command verifies version_b images, notes, page counts and hashes without accessing local generation paths or calling a provider. The second includes historical version_a timing/deck checks and current documentation links; it does not establish a timed rehearsal of version_b. Both commands passed when preparing this update. QA contact sheets and rejected draft images are excluded from Git; final PNGs and generation records are included.
