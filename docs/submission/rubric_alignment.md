# Rubric Alignment Matrix

**Source:** `docs/project_guidelines/COMP5584_project_guidelines.pdf` (3 pages).
Total: **100%**. This matrix maps each criterion to evidence and to the final artifacts.
**Deck map (21 slides):** 1 title · 2–3 Problem · 4–7 Design · 8–9 System · 10–13
Evaluation · 14–15 Discussion · 16–21 Backup. Slide numbers below refer to
`presentation/IncidentLens_Final.pptx`; update them if the deck is reordered.

| Rubric category | Weight | What the assessor is looking for | Evidence in IncidentLens | Documents | Slides | Demo cue |
| --- | ---: | --- | --- | --- | ---: | --- |
| **1. Problem Formulation & Motivation** | 15% | A clear, significant problem; precise scope; why multi-agent LLM design is appropriate; testable objectives | Incident RCA requires cross-source evidence and calibrated abstention; generic LLM agents over-claim. The project defines a cited-or-abstain contract and four matched architectures. Scope is synthetic, read-only incidents. | `README.md` §"Why this project"; `docs/ARCHITECTURE.md` §1; `docs/LIMITATIONS.md` §1 | 2–3 | Show an `INCONCLUSIVE` report and ask "why not guess?" |
| **2. Multi-Agent System Design** | 30% | Role decomposition; coordination; communication; state; failure handling; justified design choices | 1 coordinator + 4 specialists + verifier ablation + deterministic merge/finalize + remediation + monitoring; LangGraph state machine; max 2 tasks/round; role ACL; stable hypothesis IDs; partial-failure handling; unified stop. | `docs/ARCHITECTURE.md`; `docs/AGENT_DESIGN.md`; `docs/reference/protocol.md` | 4–7 | Open **System** and **Run → Workflow**; click a specialist |
| **3. Technical Implementation & Functionality** | 25% | Working system; code quality; reproducibility; tests; actual demo | 40 public packs; mock and real providers; CLI + web; replay without re-execution; 1,179 tests passed, 3 skipped, 0 failed (2026-11-02, 450 s); strict Pydantic contracts; retry and stop protocol; no secrets in repo. | `README.md`; `docs/RUN_GUIDE.md`; `docs/ARCHITECTURE.md` §5–8 | 8–9 | Run `incident_001` live (Mock), then replay it; show trace and evidence drawer |
| **4. Analysis & Innovation** | 15% | Measurement; insight; comparison; honest limitations; novelty | Matched 4-architecture benchmark; 144 slots; quality/cost metrics; difficulty levers; zero wrong root causes; verifier ablation; deterministic grounding gates; replay-estimated guard analysis with explicit boundary. | `docs/EVALUATION.md`; `analysis/wp_d/reports/hardened144-20261101/README.md`; `docs/incidentbench/README.md` | 10–14 (backup 17–19) | **Evaluation** page: 33/36 vs 32/36, 27/27 root correct, token/latency comparison |
| **5. Presentation & Submission Quality** | 15% | Clear narrative; visual quality; timing; Q&A; complete, consistent package | PolyU-aligned deck and site; 9–10 min script; six-speaker allocation; Q&A with limitations; blank contribution template; checklist; consistency audit; reproducible package. | `presentation/Presentation_Script.md`; `presentation/QA_Preparation.md`; `docs/submission/`; `submission/` | all | Coherent red/navy design across deck and site; rehearsed hand-offs |

## Criterion-level evidence checklist

### 1. Problem Formulation & Motivation (15%)

- [x] Concrete incident classes: pool regression, PostgreSQL exhaustion/locks/slow queries,
  Redis outage, payment timeout, resource saturation (7 failure modes).
- [x] Why evidence cross-checking matters: at least two sources, mechanism, temporal order.
- [x] Why multi-agent: role-scoped evidence access and dynamic allocation; not "more agents
  is better".
- [x] Testable objective: cited-or-abstain; quality success, technical completion, cost.
- [x] Explicit non-goals: no production changes, no execution, no real telemetry.
- [x] Scope boundary: synthetic development corpus, provisional labels.

### 2. Multi-Agent System Design (30%)

- [x] Roles, responsibilities and tool ACL table (`README.md`, `docs/AGENT_DESIGN.md`).
- [x] Coordination protocol: `INVESTIGATE` / `FINALIZE` / `ABSTAIN`; max 2 tasks; replan.
- [x] Shared state and communication: typed `InvestigationState`; shared evidence board;
  findings; hypothesis reconciliation; review fingerprints.
- [x] Deterministic control: Merge and FinalizeGate do not depend on model confidence.
- [x] Failure handling: partial batch failure, task retry, structured-output repair,
  budget exhaustion, unified stop.
- [x] Design justification and ablation: Single, Fixed-4, Dynamic, Dynamic (with verifier).
- [x] Security: immutable context, actual-query ledger, public allowlist, replay confinement.

### 3. Technical Implementation & Functionality (25%)

- [x] End-to-end runnable CLI and web dashboard; offline Mock; real provider adapter.
- [x] Reproducible install (`requirements.lock`, editable install, `.env.example`).
- [x] Strict schemas and validation; no private-oracle reads at runtime.
- [x] Tests across unit, integration, isolation, reliability, evaluation, IncidentBench.
- [x] Saved artifacts and offline replay/rescore.
- [x] Website demonstrates real traces, not mock screenshots: live Mock run, recorded
  replay, evidence provenance, hypothesis board, gate timeline, evaluation table.
- [x] UI labels Live vs Recorded Replay and Mock vs Real.
- [x] No secrets, `.venv`, caches or demo video in the submission archive.

**Verified:** full suite run on 2026-11-02 against this tree — `1179 passed, 3 skipped in
450.01s`, exit 0 (`analysis/submission/pytest-20261102.log`). Re-run after any change to source, tests,
configuration or web assets.

### 4. Analysis & Innovation (15%)

- [x] Matched comparison: same model, temperature, public data, tools, budget, cache off.
- [x] Denominators: technical failure stays in the quality denominator; root correctness
  only on identifiable completed runs; abstention only on unidentifiable completed runs.
- [x] Quality and cost: quality success, root correct, abstention, latency, requests,
  tools, tokens.
- [x] Difficulty levers: competing causes, counterfactual pairs, boundary, missing,
  misleading.
- [x] Negative result reported: verifier added cost without measured quality gain.
- [x] Failure analysis: 8 technical failures; 19 over-abstentions; zero wrong root causes.
- [x] Boundaries: no blind test, pending labels, one model/repeat, no significance test,
  replay-estimated guard, mock-only cache/recovery.

### 5. Presentation & Submission Quality (15%)

- [x] 16:9 editable deck, PolyU-aligned visual system, speaker notes.
- [x] Every slide rendered and visually inspected (record inspection log).
- [x] PDF export (if WPS export succeeds).
- [x] English script with Chinese notes, timings, transitions, demo cues.
- [x] Six-speaker allocation without inventing contributions.
- [x] Q&A preparation with correct, bounded answers.
- [x] Blank Individual Contribution Statement template.
- [x] Submission checklist and cross-artifact consistency audit.
- [ ] Final package organized and size-checked. (The archive is built and verified at
  submission time; see `submission/SUBMISSION_CHECKLIST.md` §9.)

## Presentation-specific rubric (if separately assessed)

| Criterion | How the deck addresses it | Slide(s) |
| --- | --- | --- |
| Clear research question | "Can a coordinated multi-agent system investigate incidents with cited evidence and calibrated abstention at acceptable cost?" | 3 |
| Methodology | IncidentBench, matched variants, metrics, denominators | 10, 17 |
| Results | Quality table, cost table, lever table, zero wrong causes | 11–13, 18 |
| Critical analysis | Verifier negative result, over-abstention, boundaries | 12–15, 19 |
| Visual communication | One idea per slide, PolyU rail, consistent charts, readable sizes | all |
| Timing | 9–10 min main track; backup slides for Q&A | script |
| Speaker coordination | Six hand-offs with explicit cues | script |

## Known gaps and how they are disclosed

| Gap | Where disclosed | Why it is acceptable |
| --- | --- | --- |
| No blind test | Slide 14; `docs/LIMITATIONS.md`; Q&A | Stated as a development-visible study, not a blind claim |
| Provisional labels | Slide 10/14; evaluation page | Prevents overstating ground truth |
| One model, one repeat | Slide 12/14 | Differences described, not tested for significance |
| Over-abstention | Slide 13–14 | Presented as the observed failure mode, with counts |
| No production users | Slide 14 | Scope is a research/teaching prototype |
| Member contributions unknown | Contribution template blank | Integrity constraint; group completes it |

## Submission artifacts map

| Artifact | Path | Owner action |
| --- | --- | --- |
| Source code + instructions | repository root, `README.md`, `docs/RUN_GUIDE.md` | verify fresh clone install |
| Demo video (≤10 min) | **not produced here** | group records using `docs/DEMO_GUIDE.md` |
| Slides | `presentation/IncidentLens_Final.pptx` + `.pdf` | review, add names if desired |
| Individual Contribution Statement | `submission/Individual_Contribution_Statement_TEMPLATE.md` | each member completes |
| Submission checklist | `submission/SUBMISSION_CHECKLIST.md` | tick before zipping |
| Consistency audit | `docs/submission/consistency_check.md` | re-run after any edit |
| Rubric alignment | this file | use as rehearsal checklist |
