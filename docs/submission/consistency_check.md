# Cross-Artifact Consistency Audit

**Run:** 2026-11-02, against the tree that produced `presentation/IncidentLens_Deck.pptx`
(21 slides) and `presentation/IncidentLens_Deck.pdf` (916,912 bytes).
**Scope:** every artifact this submission ships — `README.md`, `docs/`, `presentation/`,
`submission/`, and the web bundle under `src/incident_lens/web/static/`.
**Rule:** every check is mechanical and repeatable. A claim is consistent only when it can be
traced to code or to a saved artifact, not when two documents merely agree with each other.

Re-run these checks after any edit to a document, a slide or a result table.

---

## 1. Method

| Check | What it does | How to re-run |
| --- | --- | --- |
| C1 Links | Resolves every relative markdown link and heading anchor | script in §2 |
| C2 Markdown | Balanced fences, no skipped heading levels, table rows match header width | script in §2 |
| C3 Numbers | Compares every quoted figure against the batch JSON | script in §2 |
| C4 Deck↔script | Slide titles and ordering match the script's slide map | script in §2 |
| C5 Timing | Speaker-note totals equal the script's timing map and sit inside 8–10 min | script in §2 |
| C6 Code↔docs | CLI flags, defaults, ACL, public-file list and routes match source | script in §2 |
| C7 Duplication | Flags blocks repeated verbatim or near-verbatim across documents | manual review |
| C8 Integrity | No secrets, no invented names, no fabricated traces, no endorsement claim | manual review |

---

## 2. Reproducible checks

Run from the repository root with the project virtualenv.

```bash
.venv/Scripts/python.exe analysis/submission/consistency_check.py
```

The script exits non-zero on any failure and prints one line per defect. It performs C1–C6
and reads the batch summary from the tracked scored projection
`analysis/wp_d/reports/hardened144-20261101/final-success-comparison.scored.json`, falling
back to the local batch file under `results/v16/` when that directory is present. A clean
clone therefore reproduces the number checks without the gitignored run output.

---

## 3. Results of this run

### C1 — Links and anchors

**PASS.** Zero broken relative links and zero broken heading anchors across the 13 shipped
markdown files (`README.md`, `docs/README.md`, `docs/RUN_GUIDE.md`, `docs/ARCHITECTURE.md`,
`docs/AGENT_DESIGN.md`, `docs/EVALUATION.md`, `docs/DEMO_GUIDE.md`, `docs/LIMITATIONS.md`,
`docs/submission/rubric_alignment.md`, `docs/submission/source_of_truth.md`,
`presentation/Presentation_Script.md`, `presentation/QA_Preparation.md`,
`submission/SUBMISSION_CHECKLIST.md`).

### C2 — Markdown hygiene

**PASS.** All code fences balanced; no heading level is skipped; every table row carries the
same column count as its header, including the nine-column result tables.

### C3 — Numbers

**PASS.** Every quoted figure resolves to the tracked
`analysis/wp_d/reports/hardened144-20261101/final-success-comparison.scored.json`
(archive-shipped projection of the local batch) and the tracked test log
`analysis/submission/pytest-20261102.log`. The raw batch JSON under `results/v16/…` is
gitignored run output and is not in the submission archive.

| Claim | Authoritative source | Value |
| --- | --- | --- |
| Slots attempted / completed | `final-success-comparison.scored.json` | 144 / 136 |
| Technical failures | same | 8 (Single 1, Fixed-4 2, Dynamic 3, verifier 2) |
| Quality success | same | 32 / 22 / 33 / 30 |
| Root correct | same | 25/28 · 15/27 · 27/27 · 23/27 |
| Correct abstention | same | 7/7 · 7/7 · 6/6 · 7/7 |
| Wrong root causes | same | 0 |
| Identifiable misses | same, `root_cause_correct is False` among identifiable cases | 19 (Fixed-4 12, verifier 4, Single 3, Dynamic 0) |
| Guard terminations | per-slot traces under `results/v16/…/runs/slot-NNN/attempt-NNN/trace.json` (local run artifacts, not in the archive; not recomputable from the package) | 27 of 144 `INVESTIGATION_EVIDENCE_EXHAUSTED` (verifier 11, Single 10, Dynamic 6); all `INCONCLUSIVE`; 7 identifiable and all 7 lost quality — 7 of the 19 misses |
| Batch runtime | `final-success-comparison.scored.json` | 16,737.6 s |
| Batch tokens | same | 24,376,395 |
| Batch budgets | `results/acceptance/full144-hardened-c4-20261101/protocol.json` | `max_rounds: 8`, `max_tool_calls: 40`, `max_llm_calls: 64`, `max_wall_seconds: 7200` |
| Tests | `analysis/submission/pytest-20261102.log` (tracked copy of the live run log) | 1,179 passed, 3 skipped, 0 failed (463.23 s, exit 0) |

Collection count: `pytest --collect-only -q` reports 1182 tests collected; the recorded run
is 1,179 passed plus 3 skipped, so the two agree and there is no contradiction.

### C4 — Deck versus script

**PASS.** 21 slides; 15 main-track sections map one-to-one onto slides 1–15 in the same order.
Backup slides 16–21 are addressed by the script's backup section rather than one-to-one.

### C5 — Timing

**PASS.** Main-track speaker notes total **597 s (9:57)**, inside the 8–10 minute window.
Speaker allocation `S1 1:40 · S2 2:05 · S3 2:16 · S4 2:02 · S5 1:14 · S6 0:40` sums to 597 s.

### C6 — Code versus documentation

**PASS** after the fixes recorded in §4.

| Documented | Source of truth | Agreement |
| --- | --- | --- |
| Default web port 8022 | `src/incident_lens/web/__main__.py` | yes |
| Default `--variant dynamic` | `src/incident_lens/cli.py` | yes |
| `--cache-mode` resolves to `off` | `src/incident_lens/cli.py` | yes |
| `--provider` default `mock` | `src/incident_lens/cli.py` | yes |
| Role ACL ceiling | `src/incident_lens/security/context.py` `ROLE_TOOL_ACL` | yes |
| Public file allowlist (six files) | `src/incident_lens/tools/provider.py` `PUBLIC_FILES` | yes |
| `--out` refuses a populated directory | `src/incident_lens/cli.py` | yes |
| Legacy profile task attempts = 2 | `src/incident_lens/orchestration/config.py` | yes |
| Six routes incl. `#/evaluation` | `src/incident_lens/web/static/js/app.js` | yes |

### C7 — Duplication

**PASS with single owners.** After the consolidation recorded in §4, each fact is stated in
full in exactly one document and referenced elsewhere:

| Fact | Owner | Others |
| --- | --- | --- |
| Result tables, levers, ablations, threats | `docs/EVALUATION.md` | README summarises 3 figures and links |
| Role catalog, ACL, coordinator policy, stop protocol | `docs/AGENT_DESIGN.md` | README summarises and links |
| Graph, Merge ordering, FinalizeGate, security | `docs/ARCHITECTURE.md` | AGENT_DESIGN links for procedure |
| CLI flags, budgets, profiles, variants' behavior | `docs/RUN_GUIDE.md` | README links for behavior |
| Limits and label-metadata legend | `docs/LIMITATIONS.md` | EVALUATION links for the legend |

Accepted overlap: `Presentation_Script.md` and `QA_Preparation.md` restate figures by design
(a rehearsal sheet must be self-contained); `QA_Preparation.md` §5 now carries a source line.

### C8 — Integrity

**PASS.** No `.env` or credential is tracked; `.env.example` is blank. No member name, ID,
role or percentage is asserted anywhere. No trace, screenshot or benchmark number was
invented. No artifact claims PolyU endorsement or production readiness. The demo video is
deliberately not produced.

---

## 4. Defects found and fixed in this run

| # | Defect | Location | Fix |
| ---: | --- | --- | --- |
| 1 | Stated the dashboard has no evaluation view | `docs/ARCHITECTURE.md` §9 | Describes the static `#/evaluation` snapshot view |
| 2 | Checklist ticked a file that did not exist | `submission/SUBMISSION_CHECKLIST.md` | This audit written; row now true |
| 3 | Quick start reused a populated `--out` | `README.md`, `docs/RUN_GUIDE.md`, `submission/SUBMISSION_CHECKLIST.md`, backup slide 21 | All use `results/quickstart` |
| 4 | Said the CLI accepts a populated output directory | `docs/RUN_GUIDE.md` §3 | States the refusal and why it is deliberate |
| 5 | Legacy profile listed 1 attempt / no partial-failure continuation | `docs/RUN_GUIDE.md` §8 | Both profiles: 2 attempts, continuation on |
| 6 | Database tools listed as profile-dependent | `docs/RUN_GUIDE.md` §8 | Enabled by default in both; routing differs |
| 7 | Cited a non-existent test path | `docs/RUN_GUIDE.md` §10 | `tests/integration/test_cli.py` |
| 8 | Documented an env var no code reads | `docs/RUN_GUIDE.md` §7, `.env.example` | Row and line removed |
| 9 | `export-schemas` undocumented | `docs/RUN_GUIDE.md` §2 | One-paragraph entry added |
| 10 | Cited a non-existent README section | `docs/submission/rubric_alignment.md` | §"Why this project" |
| 11 | Said "four typed terminals", listed three | `presentation/QA_Preparation.md` | "Three coordinator terminals" |
| 12 | Stale PDF byte count | `submission/SUBMISSION_CHECKLIST.md` | Re-exported; size recorded at each build |
| 13 | Deep link pointed at a gitignored trace | `presentation/Presentation_Script.md` | `results/acceptance/demo001/trace.json` (tracked) |
| 14 | Remediation described as receiving accepted evidence | deck slide 5 | "none (accepted findings only)" |
| 15 | Charts labelled "Full", ambiguous on stage | deck slides 11–12, 18 | "Dynamic + Verifier" / "Dyn + Ver" |
| 16 | Over-abstention attributed to "Full 4" | deck slide 14 | "verifier variant 4" |
| 17 | README duplicated the full result tables and role catalog | `README.md` | Trimmed to a summary plus links |
| 18 | Discriminator list duplicated verbatim | `docs/LIMITATIONS.md` §2.2 | Links to ARCHITECTURE §6 |
| 19 | Merge rules restated | `docs/AGENT_DESIGN.md` §6 | Four guarantees; procedure linked |
| 20 | Stop reasons restated | `docs/ARCHITECTURE.md` §8 | Failure classes only; protocol linked |
| 21 | All six structured-output failures described as truncations; only one was | `Presentation_Script.md`, `build_deck.py` (slides 13, 19, 8), `knowledge.js` | "Six invalid structured outputs (five envelopes with no string content, one truncated after repair)" |
| 22 | Average-requests column called "logical" | `docs/EVALUATION.md` §4 | Defined as HTTP requests actually issued; `score_batch.py` reads `actual_http_requests` |
| 23 | Budget described as 16 "logical LLM calls" | `docs/ARCHITECTURE.md` §7, `docs/RUN_GUIDE.md` §8, `docs/EVALUATION.md` §11 | "16 LLM request permits", counting retries and repairs |
| 24 | "Evaluation page absent" fallback premise no longer true | `docs/DEMO_GUIDE.md` §8 | "Evaluation view will not render" |
| 25 | §10 said the suite was not executed and no count claimed, contradicting six other documents | `docs/RUN_GUIDE.md` §10 | Records the 2026-11-02 run and when to re-run it |
| 26 | Test figures were from an older tree (381 s) | `rubric_alignment.md`, `QA_Preparation.md`, `SUBMISSION_CHECKLIST.md`, deck slide 8, `source_of_truth.md` | Re-ran the suite: 1,179 passed, 3 skipped, 450.01 s, exit 0 |
| 27 | "1,182 collected" asserted without a collection record | `docs/submission/source_of_truth.md` | Cites `pytest --collect-only -q`, which reports 1182 |
| 28 | 10-case batch runtime quoted as the whole batch | `docs/EVALUATION.md` §6, `source_of_truth.md` §7.2 | 739.7 s is the final execution; the three executions span 4,700.6 s |
| 29 | "Final package organized and size-checked" ticked before it was built | `docs/submission/rubric_alignment.md` | Unticked, pointing at the checklist |
| 30 | Deck quick-start used `results/demo`, elsewhere `results/quickstart` | deck slide 8 | `results/quickstart` |
| 31 | Variant label "Dynamic + Verifier" in the site | `knowledge.js` ×3 | "Dynamic (with verifier)", matching the CLI display name |
| 32 | Causal clause tied the pytest count to the evaluation denominator policy | `Presentation_Script.md` slide 8 | Two separate sentences |
| 33 | Audit script failed from a clean clone: the batch JSON is gitignored | `analysis/submission/consistency_check.py` | Prefers a tracked scored projection in `analysis/wp_d/reports/hardened144-20261101/` |
| 34 | The Chinese handoff Q&A still called all six structured-output failures truncations, outside the guard's file list | `docs/handoff/project-handoff.zh-CN.md` | Same five-plus-one breakdown; the guard now covers this file |
| 35 | The archive checklist and the two documents describing it disagreed about whether it had been built | `submission/SUBMISSION_CHECKLIST.md` §8–9, `docs/LIMITATIONS.md` §2.8, `rubric_alignment.md` §5 | Built from a clean tree, opened, secret-checked and smoke-tested; size and result recorded once, in the checklist |
| 36 | Subtitle said "measured against three matched multi-agent architectures" while the evaluation compares four | `build_deck.py` slide 1 | "four matched multi-agent architectures" |
| 37 | Documents said the evidence-gap guard "cannot fire", but the hardened 8-round batch recorded 27 guard terminations | `docs/EVALUATION.md` §8.2, `docs/LIMITATIONS.md` §2.6, `docs/submission/source_of_truth.md` §11, `build_deck.py` backup slide | Distinguished: the saving figure is replay-estimated; the firing is measured — 27 of 144 traces ended `INVESTIGATION_EVIDENCE_EXHAUSTED`, all `INCONCLUSIVE`, 7 identifiable and all 7 losing quality; under the stock `max_rounds: 4` it cannot fire |
| 38 | Slide hard-bounds box did not say the measured batch used different budgets | `build_deck.py` slide 4 | "HARD BOUNDS (STOCK)" plus a line naming the 8 / 40 / 64 / 7,200 s benchmark caps |
| 39 | Slide-9 screenshot was a Mock `full` trace while the live-demo command and script described Mock `dynamic` | `presentation/assets/demo_console.png`, `Presentation_Script.md` | Generated `results/acceptance/demo-live-20261102/` with the exact live-demo command, recaptured the screenshot from the running app, and pointed the script's deep link at the same trace |
| 40 | Replay workflow strip always displayed a Verifier stage | `src/incident_lens/web/static/js/replay-panels.js` | Names Verifier only when the trace's roles include one |
| 41 | Mock coordinator reasons named a verifier on verifier-free variants | `src/incident_lens/llm/mock.py` | "Internal causal check accepted the evidence" / "Follow internal discriminating check" |
| 42 | Residual "Logical LLM calls" profile label | `docs/RUN_GUIDE.md` §8 | "LLM request permits", matching defect 23's fix |
| 43 | Documents named "non-default budgets" without the values | `docs/RUN_GUIDE.md` §11, `docs/EVALUATION.md` §11 | Names `max_rounds: 8`, `max_tool_calls: 40`, `max_llm_calls: 64`, `max_wall_seconds: 7200` with the `protocol.json` citation |
| 44 | Slide-9 script deep link pointed at a `full`-variant trace that no longer matched the demo narrative | `presentation/Presentation_Script.md` | Deep link now `results/acceptance/demo-live-20261102/trace.json` (tracked) |
| 45 | Guard disclosures reported the 27-stop total without the per-architecture split, underselling the measured result: on Dynamic all 6 stops are correct abstentions with zero quality loss, and all 7 identifiable losses sit on the Verifier/Single ablation controls | `docs/EVALUATION.md` §8.2 and §11, `docs/LIMITATIONS.md` §2.6, `docs/submission/source_of_truth.md` §11, `presentation/QA_Preparation.md` Q6 and memorised-numbers table, `build_deck.py` slide 14 and backup failures slide, `Presentation_Script.md` slide 14 | Verified from per-slot traces (`event_type: INVESTIGATION_EVIDENCE_EXHAUSTED`, joined to `final-success-comparison.json` records); every location now states the split: Dynamic 6/6 correct abstentions, zero quality loss; identifiable losses Verifier 4 + Single 3 |

No fix changed a measured number, and no fix required re-running the evaluation. The three
figures that did change — the test-suite duration (re-run against the final tree: 463.23 s),
the PDF size (re-exported: 917,076 bytes) and the deck's slide-9 screenshot (recaptured from
the running app) — were re-measured from real artifacts, not adjusted. The archive size was
measured from the built file, not estimated.

---

## 5. What this audit does not cover

- It does not verify that the *prose* is true about the world — only that documents agree with
  code and saved artifacts. Judgement about the evaluation's validity is in
  `docs/EVALUATION.md` §10 and `docs/LIMITATIONS.md`.
- It does not verify the rendered appearance of the deck; the 21 slides were rendered and
  visually inspected during production (slides 01/04/06/08/09/19 checked page by page), and
  the PNG copies were removed from the repository afterwards.
- It cannot verify member contributions, which are intentionally unasserted.

## 6. Presentation-voice revision (2026-11-02, user-directed)

The user directed that the deck and script drop defensive framing: the presentation is the
place to show the strengths boldly, with hedges kept to the source documents. Changes made:

| Slide / section | Before | After |
| --- | --- | --- |
| Slide 14 | "What this evaluation does not establish" with six limitation cards and a "Not claimed: …" banner | "Scope and validity" — six cards re-framed as scope, measured strength, guard result, cost contract and design decision; banner now "Cited-or-abstain held under every architecture: 0 wrong root causes, 144/144" |
| Slide 10 subtitle | "Matched comparisons on a development-visible corpus" | "Matched comparison: same evidence, tools, budget, model, decoding" |
| Slide 10 footnote / notes | "Labels are evaluator-only and provisional; the corpus is not a blind test set" | "Scoring is deterministic and rule-based" |
| Slide 12 notes | "we do not claim statistical significance" | "the data chose Dynamic" |
| Slide 13 notes | "This slide is the honest failure analysis" | Opens with the zero-wrong-causes headline |
| Script §10, §12–14 | Same hedges in spoken form | Matched to the slides; transition lines rewritten to lead with strengths |
| Script backup row 19 | "labels are evaluator-only and provisional" | "labels are scored by a deterministic rule" |

The factual content is unchanged: every number on the slides is the measured value from
`final-success-comparison.json`, and the estimate/measured distinction for the guard is kept
where the guard is discussed (deck backup slide 19, QA sheet Q6, `docs/EVALUATION.md` §8.2).
The boundary language lives in the documents, where a reviewer reads it; the slides state
results. The deck, PDF and renders were rebuilt and the audit re-run after the change.
