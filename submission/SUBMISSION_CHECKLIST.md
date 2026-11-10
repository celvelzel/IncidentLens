# Submission Checklist — COMP5584 Group Project

**Deadline:** 23 November 2026, 11:59 PM (Canvas).
**Archive name:** `COMP5584+GroupProject+Group5.zip` (use the group's actual ID).
**Uploader:** one member on behalf of the group.
**Status legend:** `[x]` verified in this checkout · `[ ]` group action still required.

---

## 1. Course requirements (from the official guidelines)

| # | Requirement | Where | Status |
| ---: | --- | --- | --- |
| 1 | System source code with instructions for running it | repository root, `README.md`, `docs/RUN_GUIDE.md` | [x] |
| 2 | Demo video, ≤ 10 minutes, whole workflow + representative examples | **not produced here**; plan in `docs/DEMO_GUIDE.md` | [ ] group records |
| 3 | Presentation slides | `presentation/IncidentLens_Deck_version_b/IncidentLens_Deck_version_b.pptx` (+ PDFs) | [x] |
| 4 | Individual Contribution Statement | `submission/Individual_Contribution_Statement.md` | [x] members 1–2 filled; percentages and members 3–6 still [ ] group completes |
| 5 | Slides cover: problem & motivation, multi-agent design, implementation, demo & results | slides 2–15 | [x] |

> The demo video is the one item this work deliberately does not produce. Record it from the
> running system using `docs/DEMO_GUIDE.md`; do not substitute slides or a screen recording of
> a replay for the live workflow without labelling it.

---

## 2. Current deck checks (version_b)

- [x] 21 English slides, 16:9 (10 x 5.625 in), image-based PPTX.
- [x] 15 main slides + 6 backup slides. All final images visually inspected.
- [x] Slides PDF and illustrated English script PDF each contain 21 pages.
- [x] All 21 speaker-note sections exactly match the English verbatim script.
- [x] Title slide retains Group 5 and all six names/student IDs.
- [x] Arial styling, PolyU red and smaller gray annotations follow the approved sample.
- [x] PPTX package and geometry validation passed; image bytes match final PNGs.
- [ ] Group opens the PPTX on the venue machine and rehearses with the actual demo.

Individual slide objects are not editable in version_b. Notes and `speech.md` remain editable. The former editable deck is archived in `presentation/version_a/`.

---

## 3. Script and Q&A checks

- [x] `presentation/IncidentLens_Deck_version_b/speech.md` — English verbatim script for all 21 slides, with transitions, demo cues and six suggested speaker blocks.
- [ ] Group measures the version_b rehearsal time; the old 9:57 version_a allocation is historical.
- [x] `presentation/QA_Preparation.md` — 10 likely questions, rapid-fire table, declined
      questions, demo-failure answers, memorised numbers, mock Q&A drill.
- [ ] Group assigns speakers to the six blocks (allocation is by slide, not a claim about who
      built what).
- [ ] Full timed rehearsal, twice, including one deliberate demo failure.

---

## 4. Documentation checks

- [x] `README.md` — problem, contract, architecture, roles, results, boundaries, run commands.
- [x] `docs/RUN_GUIDE.md` — install, commands, variants, replay, dashboard, real provider,
      budgets, artifacts, tests, troubleshooting, packaging.
- [x] `docs/ARCHITECTURE.md` — graph, state, gates, security, recovery, replay.
- [x] `docs/AGENT_DESIGN.md` — role catalog, ACL, coordination policy, hypothesis lifecycle.
- [x] `docs/EVALUATION.md` — questions, corpus, metrics, denominators, results, threats.
- [x] `docs/DEMO_GUIDE.md` — 8–10 minute demo plan, fallbacks, recording checklist.
- [x] `docs/LIMITATIONS.md` — technical, empirical, ethical and scope limits.
- [x] `docs/README.md` — documentation map updated.
- [x] `docs/submission/source_of_truth.md` — single fact base with evidence labels.
- [x] `docs/submission/rubric_alignment.md` — rubric map to evidence, documents, slides.
- [x] `docs/submission/consistency_check.md` — cross-artifact audit.
- [ ] Group reads `docs/LIMITATIONS.md` before Q&A; it is the defensive spine.

---

## 5. Code and repository checks

- [x] No `.env` committed; only `.env.example` with blank values.
- [x] No API keys, tokens or private endpoints in tracked files.
- [x] `.venv/`, `__pycache__/`, `.pytest_cache/`, build output and `results/` bulk are ignored.
- [x] `requirements.lock` present for reproducible install.
- [x] Mock provider needs no key and produces deterministic output.
- [x] Full test suite: `1179 passed, 3 skipped, 0 failed` on 2026-11-02 (463.23 s, exit 0),
  re-run against the final tree.
- [x] Replay confined to `results/**/trace.json`; companion metadata bound by identity.
- [ ] Re-run the suite if the tree changes after 2026-11-02 and update
      `docs/submission/source_of_truth.md` with the new result.
- [ ] Decide on a license before publishing the repository publicly.

**Fresh-clone sanity check** (do this once before zipping):

```bash
git clone <repo> /tmp/incidentlens-check
cd /tmp/incidentlens-check
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m incident_lens.cli validate-data
.venv/bin/python -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/quickstart
.venv/bin/python -m incident_lens.cli replay --trace results/quickstart/trace.json
```

---

## 6. Website checks (if the site is shown or submitted)

- [x] Live vs recorded replay labelled in the UI (`Live run · saved trace` / `Recorded Replay`).
- [x] Mock vs real labelled (`MOCK` / `REAL`).
- [x] Evidence drawer shows source file, source tool/event, query time, raw excerpt.
- [x] Hypothesis board and FinalizeGate timeline present.
- [x] Evaluation view marked as a recorded batch, not live.
- [x] Responsive layout and keyboard-accessible navigation.
- [ ] Confirm the site is served from the same commit that is submitted.
- [ ] No PolyU logo or endorsement claim on the public site.

---

## 7. Numbers to verify immediately before submitting

| Claim | Authoritative value | Where |
| --- | --- | --- |
| Slots attempted / completed | 144 / 136 | `analysis/wp_d/reports/hardened144-20261101/final-success-comparison.scored.json` |
| Technical failures | 8 (1 / 2 / 3 / 2 by architecture) | same |
| Dynamic quality / root / abstain | 33/36 · 27/27 · 6/6 | same |
| Wrong root causes | 0 of 144 | same |
| Identifiable misses | 19, all `INCONCLUSIVE` (Fixed-4 12, Verifier 4, Single 3, Dynamic 0) | same |
| Tests | 1,179 passed, 3 skipped, 0 failed | `analysis/submission/pytest-20261102.log` |
| Corpus | 40 public packs; 36 hardened cases (29/7), 10 families | `data/`, `docs/submission/source_of_truth.md` |

Recompute the batch table with:

```bash
.venv/bin/python analysis/submission/consistency_check.py
```

> Boundary: the tracked, archive-shipped authority for these numbers is the scored
> projection above (144 records). The raw batch JSON
> `results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json` is local
> run output (gitignored, `.gitignore:12`) and is not part of the submission archive;
> `analysis/wp_d/reports/hardened144-20261101/score_batch.py` can regenerate it only
> against the retained batch directory plus evaluator-only oracles, which are deliberately
> not shipped.

---

## 8. Packaging

Exclude from the archive:

- `.venv/`, `node_modules/`, `build/`, `dist/`, `*.egg-info/`
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- `.env` (any variant), local credentials, `local_oracles/`
- `results/` bulk run output (keep the summary tables and the tracked acceptance artifacts if
  the archive needs evidence; the hardened batch summary is small)
- any recorded demo video from the source archive if the video is uploaded separately

Include:

- source tree, `pyproject.toml`, `requirements.lock`, `.env.example`
- `README.md`, `docs/` (current guides; archives may be trimmed)
- `data/incidentbench_v2_hardened/` and `data/incidents/` if the archive size allows —
  otherwise document how to regenerate them
- `presentation/IncidentLens_Deck_version_b/IncidentLens_Deck_version_b.pptx`, slides PDF, `Presentation_Script_version_b.pdf`, `speech.md`
- `submission/Individual_Contribution_Statement.pdf` (filled by the group)
- `analysis/wp_d/reports/hardened144-20261101/` summary and scoring script

Suggested archive check:

```bash
zip -r "COMP5584+GroupProject+Group5.zip" . -x ".venv/*" "results/*" ".git/*" "*.pyc"
```

Then confirm the archive opens, contains no `.env`, and is under the Canvas upload limit.
Report the final size in the group's submission note.

**Build record (2026-11-02):**

| Property | Value |
| --- | --- |
| File | `COMP5584+GroupProject+Group5.zip` at the repository root (ignored by git, not committed) |
| Source | `git archive HEAD` from a clean `main` working tree, so only tracked files are included |
| Size | about 22 MB compressed, 74.3 MB uncompressed, 3,418 files — well under a typical Canvas limit, but confirm the course setting |
| Integrity | archive opens; per-entry CRC check passes; extraction yields all 3,418 files |
| Secrets | only `.env.example`, whose values are blank; no `.env`, key, token, `.venv`, `__pycache__`, cache, `.sqlite` or `local_oracles/` |
| Smoke test on the extracted copy | `validate-data` returns `ok`; `incident_001` Mock Dynamic ends `RESOLVED`; `incident_006` ends `INCONCLUSIVE`; `replay` reads the saved trace; `analysis/submission/consistency_check.py` prints `PASS` |

The archive is rebuilt after the group adds the completed Individual Contribution Statement and
any member names to slide 1, so the delivered file will not be byte-identical to this build.
Re-measure the size at that point.

---

## 9. Final ten minutes

- [ ] Deck and PDF open on the presentation machine.
- [ ] Console running; recorded trace tab preloaded.
- [ ] Contribution statement filled, signed, exported to PDF.
- [x] Archive built from a clean tree, opened once, size checked (see §8 build record).
- [ ] Archive rebuilt after the contribution statement and slide-1 names are added.
- [ ] One member has the Canvas submission page open and logged in.
- [ ] Everyone knows which speaker block they take and which backup slide they own.
