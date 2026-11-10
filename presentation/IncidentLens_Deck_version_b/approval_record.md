# Approval and production record

## User-confirmed requirements

- Outline: 21 slides, 15 main and 6 backup.
- Required source image mapping: approved.
- Slide language: English throughout, with no Chinese slide text.
- Visual identity: academic research defense with PolyU red as the primary color, taking palette inspiration from version_a. The user accepted the sample palette.
- Typography correction: Arial throughout slide-authored text. Arial Bold for titles/headings and Arial Regular for supporting text. The user rejected the initial serif title and supplied the MIT Sloan font guidance as the reference.
- Typography scale correction: reduce the overall text scale, especially the footer notes and legend. Target title 28-30 pt, component labels 14-16 pt, supporting text 12-14 pt and footer notes 10-11 pt on the 16:9 canvas. Use plain medium-gray footer text with no oversized bold emphasis. Raster output will be checked visually.
- Backend: built-in `image_gen`, accepted with the disclosed limitation that its exact model version cannot be selected or verified.
- Narration deliverable: a complete English, slide-by-slide verbatim presenter script, with the corresponding talk track in each PPTX slide's speaker notes.
- Execution: single agent, as required by the user's AGENTS.md. No multi-agent authorization has been given.

## Full production authorization

- The user approved the revised sample and instructed completion of the full deck: "可以 就按这个标准干吧，继续做完整套PPT".
- Approved sample: `origin_image/slide_04.png`, retaining the smaller Arial hierarchy and gray footer notes.
- Full-deck image generation, QA, script finalization and PPTX assembly are authorized.
- Single-agent execution remains in force under the user's AGENTS.md. The skill's generic subagent workflow does not override that user instruction. Bundled job scripts record the actual parent agent `/root` as the producer, without claiming subagents were spawned.

## Prepared for review

- `sample_generation.draft.json` records the backend, original generated files, correction pass and selected image hash.
- `speech.md` is the final English verbatim talk track for all 21 slides, embedded in the PPTX notes and included with each thumbnail in `Presentation_Script_version_b.pdf`.

## Completed production

- 21 final slide images: 20 results recorded through the bundled `record_slide_result.py`; approved sample slide 4 retained as accepted.
- All image results used the confirmed built-in backend. No subagents were spawned, following the user's AGENTS.md.
- Every slide was visually reviewed. Typography was tightened on slides 1-3; communication/gate semantics were repaired on slides 6-7; architecture miniatures were replaced with an accurate comparison table on slide 10; measured failure captions were corrected on slide 13; the coordinator tool label was corrected on slide 20.
- The source logo's Chinese line was omitted for the English-only cover. Its emblem and English wordmark remain represented.
- The PPTX has 21 notes sections, each matching its final spoken script exactly. The notes use Arial.
- All 21 embedded image byte streams match the final PNG files. The PPTX package and 16:9 geometry checks passed without findings.
- The slide PDF and illustrated presenter-script PDF each contain 21 pages. All handout speech text is present and within page bounds; every handout page was rendered for QA.

## Production constraints

- Every final slide image comes from the confirmed built-in image backend.
- No programmatic slide drawing or text overlays.
- Required logo, screenshot and result charts retain their source content.
- The final deck is image-based. Its separate script remains directly editable.
- No claim that the built-in backend is GPT-Image-2.6.

## Typography reference

- User-provided page: https://mitsloan.mit.edu/brand-guidelines/fonts
- The page was opened and checked. It specifies Arial for internal communications and PowerPoint presentations.
- Adaptation: use Arial for the user-approved PolyU-red academic visual system. The typography reference does not change the institution or project identity.
