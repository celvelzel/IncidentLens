# IncidentLens — Q&A Preparation

**Use with:** `presentation/Presentation_Script.md`, `presentation/IncidentLens_Final.pptx`
**Rule:** every answer here is traceable to `docs/submission/source_of_truth.md`. If a
question falls outside this document, say so and give the bounded answer — do not improvise a
number.

Three answer shapes are used throughout:

- **State the measurement.** Give the number, its denominator, and the batch.
- **State the boundary.** Say what the number does not establish, in one sentence.
- **State what would settle it.** Name the experiment that would change the conclusion.

An answer that admits a limit in one sentence scores better than an answer that overclaims and
is caught.

---

## 1. The ten most likely questions

### Q1. "You report no wrong root causes. Isn't that just because your labels are easy?"

**Short answer.** Partly, and we say so. The corpus has 7 competing-cause cases, 6
counterfactual pairs and 7 boundary cases, and the labels are provisional candidate labels
written by the generator authoring team — `annotator_status: pending`, `accepted_labels = 0`,
`independent_audited_families = 0`.

**Detail.** The zero is measured across 144 attempted slots with 136 completed runs. It means
no completed run asserted a culprit/failure-mode pair that disagreed with the candidate
label. It does not mean the system would be safe on arbitrary incidents: the failure vocabulary
is seven modes, each with a deterministic discriminator, so the gates operate in a closed
world. `docs/LIMITATIONS.md` §2.2 and §3.1 state this directly.

**Do not say:** "hallucination-free", "proves grounding works", "the labels are correct".

---

### Q2. "Why is Dynamic only 33/36? Single gets 32/36 with one failure."

**Short answer.** 33/36 is *quality success over all 36 slots*, and a technical failure is
never counted as a success. Dynamic had 3 technical failures; among runs that completed,
Dynamic was 33/33.

**Detail.** The denominators are deliberately different:
`technical completion` 33/36; `root cause` 27/27 on identifiable completed runs;
`abstention` 6/6 on unidentifiable completed runs; `quality` 33/36 over all 36.
Single: 35/36, 25/28, 7/7, 32/36. Fixed-4: 34/36, 15/27, 7/7, 22/36.
Dynamic (with verifier): 34/36, 23/27, 7/7, 30/36.
All four columns are in `analysis/wp_d/reports/hardened144-20261101/README.md`.

**Follow-up if pressed:** "If you prefer a single failure-inclusive number, it is 33/36
against 32/36 — a one-case difference, which is why we lead with the root-correct figure and
report cost separately."

---

### Q3. "One model, one repeat. How do you know this isn't noise?"

**Short answer.** We do not. Every difference is descriptive arithmetic on one run with
`auto/deepseek-v4.1-flash`, temperature 0, one repeat, and we make no significance claim.

**Detail.** The paired per-case split is 3 wins / 2 losses / 31 ties against Single, and
5/2/29 against the verifier. Ties dominate because most cases are solvable by every
architecture. The protocol names a family-clustered paired bootstrap, but the only statistics
artifact is a Mock validation with `status: insufficient_clusters`, `ci95: null`, `p: null`,
one effective cluster. There is no confidence interval on the real batch.

**What would settle it:** multiple models, repeated runs, and the pre-declared clustered
bootstrap on an accepted independent batch.

---

### Q4. "Isn't 39% fewer tokens just because Dynamic makes fewer calls by design?"

**Short answer.** Yes — that is the intended effect, and the claim is exactly that: with
dynamic selection, the same corpus is solved with fewer model requests and tool queries.

**Detail.** Per completed run, Dynamic averages 14.6 requests, 12.0 tool calls and 149,216
tokens, against Single's 17.3 / 14.5 / 245,971 and the verifier variant's 17.6 / 15.5 /
233,772. Fixed-4 is cheaper still (7.8 / 7.4 / 58,042) but abstains wrongly on 12 of 27
identifiable cases. The interesting result is that the cheaper dynamic schedule also has
higher measured quality than the more expensive verifier schedule.

**Caveat to add:** averages cover completed runs only; failed-slot tokens (921,599) are
excluded from averages but included in the 24,376,395 batch total.

---

### Q5. "The verifier made things worse. Why keep it at all?"

**Short answer.** Because it is a negative ablation, and we report it as one. On the hardened
batch the verifier loop cost 56.7% more tokens with no measured quality gain; on the earlier
10-case batch it cost 86.0% more tokens with identical 10/10 quality.

**Detail.** Dynamic (with verifier) was 30/36 quality vs Dynamic's 33/36, with 503.8 s vs
412.9 s and 233,772 vs 149,216 tokens. "No measured gain" is not "verifiers never help" — the
implementation and review protocol are ours, and a stronger review protocol might change the
result. We keep the variant so the ablation is reproducible, not because we recommend it.

---

### Q6. "Your guard saves 44% tokens — why isn't that in the headline?"

**Short answer.** Because it is a **replay estimate**, not a measured run, and it cannot fire
in the stock configuration.

**Detail.** Threshold 5 on the frozen 10-case batch gives −44.0% on `incident_3003`, −21.9%
on `incident_3008`, and −12.3% across the batch. The default budget is `max_rounds: 4`, and
the guard only triggers beyond that, so under default settings it never fires. It changes
budget allocation, never gate acceptance. Reporting it as a runtime saving would be wrong.

---

### Q7. "How is this different from one agent with all the tools?"

**Short answer.** Scoped access plus gap-driven allocation, not agent count. Single gets the
union of all investigator tools and plans for itself; here each role can call only its
source's tools, and the coordinator chooses which gap to close next.

**Detail.** Enforced by `ROLE_TOOL_ACL`, a frozen `AgentContext`, an actual-query ledger, and
Merge's identity/task/role validation. Measured effect on the hardened batch: +1 quality
success, −39.4% latency, −39.3% tokens versus Single. On the lever table, Dynamic is the only
variant at 7/7 competing causes and 6/6 counterfactual pairs.

**Honest boundary:** the study does not isolate *why* dynamic selection helps; it is a
matched comparison of implemented systems, not a causal identification.

---

### Q8. "Can an agent cheat — read the answer key, or widen its own tools?"

**Short answer.** Not by design, and the controls are tested. The provider reads six fixed
filenames under `public/` plus the topology file; private oracles are never loaded at runtime;
`AgentContext` is frozen and validates that `allowed_tools` cannot elevate the role; replay is
confined to `results/**/trace.json`.

**Detail.** Tests cover junction/symlink refusal, path traversal, unknown filenames, ACL denial
for every role, forced context mutation detection, foreign-context crossing, and one prompt
injection test that checks injected instructions remain data, cannot widen tool access, and
are not echoed into events.

**Boundary:** that injection test is a unit-level control, not a red-team benchmark. Prompt
injection within an authorized scope is not eliminated (`docs/LIMITATIONS.md` §2.5).

---

### Q9. "Why not just fine-tune or use a bigger model?"

**Short answer.** That changes the model, not the acceptance contract. The problem we target
is that a fluent answer with no record-level support must not be accepted, whatever the model.

**Detail.** The gates check citations, source diversity, an observed mechanism discriminator
and temporal compatibility in code. A bigger model would raise the prior on plausible
narratives without changing what the gate accepts. A model-sensitivity study is a listed
next step, not a claim.

---

### Q10. "What happens in production, with real telemetry?"

**Short answer.** We did not test it. This is a research/teaching prototype over synthetic
packs with read-only tools; it does not integrate with Prometheus, Grafana, PostgreSQL or an
incident-management system, and it does not execute remediation.

**Detail.** Remediation is `PLAN_ONLY`: it proposes actions, preconditions, risks, verification
and rollback, and never executes them. Real-provider runs send public evidence to an external
endpoint, so the demo uses Mock. Production readiness, real-incident accuracy, USD cost and
latency under load are all `UNVERIFIED`.

---

## 2. Rapid-fire answers

| Question | One-line answer |
| --- | --- |
| Why 36 cases? | The hardened corpus is 36 cases, 29 identifiable / 7 intended to abstain, 10 families — enough for a matched four-way comparison, small enough to inspect every failure. |
| Why four architectures? | To separate two design claims: dynamic selection vs a fixed schedule (Fixed-4), and coordination vs no roles (Single); the verifier is the ablation. |
| How does the loop stop? | Three coordinator terminals — `INVESTIGATE`, `FINALIZE`, `ABSTAIN` — plus a unified shutdown with a `TerminationResult`; budgets are 4 rounds, 12 tool calls, 16 model requests, 600 s. |
| What is `BEST_SUPPORTED_AVAILABLE`? | The strongest accepted state; deliberately weaker than proof, and it still requires citations and a discriminator. |
| What is `RESOLVED` vs `INCONCLUSIVE`? | `RESOLVED` requires a supported root cause with evidence and a causal chain; `INCONCLUSIVE` asserts no root cause and may carry up to three cited `OPEN` provisional hypotheses. |
| Why 8 technical failures? | Six `STRUCTURED_OUTPUT_INVALID`, two `FINDING_IDENTITY_MISMATCH`; a provider/structured-output layer issue, not retried, retained in the denominator. |
| Did you retry failures? | No — by batch plan they stay in the quality denominator, which is why quality is 33/36 rather than 33/33. |
| Is the demo live or replay? | Both, and labelled: a live Mock run, then a recorded replay that calls no graph, tool or provider. |
| Does the site use real data? | Real saved traces from real runs of the system over synthetic incident packs; no fabricated screenshots. |
| Can we run it? | Yes — `validate-data`, `run --provider mock`, `replay`, then `web`. No API key needed for Mock. |
| Cost in dollars? | `null` — not computed. Tokens and requests are measured proxies. |
| Why is the UI Chinese? | It is a demo surface for a Chinese-speaking team; the documentation and deck are English. It is not an accessible production console. |
| Is there a license? | No license file is declared yet; reuse rights are unresolved until the group adds one. |
| Did PolyU endorse this? | No. It is a course submission; the PolyU name and logo appear only in the course deck, not on the website. |

---

## 3. Questions you should decline to answer as asked

| If asked… | Do not… | Say instead |
| --- | --- | --- |
| "Which architecture is best overall?" | Rank them as a verdict | "Dynamic had the highest measured quality in this development batch at the lowest cost of the dynamic family; Fixed-4 is cheapest and pays in recall." |
| "What is the accuracy?" | Give one percentage | "Quality success 33/36; root correctness 27/27 among completed identifiable runs — they are different denominators." |
| "How much did this cost?" | Estimate USD | "Not measured. Tokens and requests are recorded; USD cost is null." |
| "Does it work on our incidents?" | Say yes | "Untested. It reads a fixed public-file schema and a seven-mode vocabulary." |
| "Who did what?" | Guess roles | "The Individual Contribution Statement is completed by the group; we do not assert contributions here." |
| "Can it fix the incident?" | Say it remediates | "It produces a PLAN_ONLY proposal; nothing is executed." |
| "Is 39% a real saving?" | Call it significant | "A descriptive difference on one run, one model, one repeat." |

---

## 4. Demo-failure answers

If the live run stalls or the provider errors, say the sentence below and switch to the
recorded trace. Do not debug on stage.

> "The live run is not responding, so I will show the recorded replay of the same
> investigation — the graph, tools and provider are not called; this is state rebuilt from
> the saved event log."

If the browser fails entirely, use the PDF and `presentation/assets/demo_console.png`, and say:

> "This is a captured frame from the running console, not a mock-up. I can show the trace
> file and the replay command afterwards."

If asked why the demo uses Mock:

> "Mock is offline and deterministic, so the demo is reproducible on any machine without a
> key. The real-provider path is the same runtime with a different adapter; the measured
> batches used a real model."

---

## 5. Numbers to have memorised

**Source:** `docs/EVALUATION.md` §5–6 and `analysis/wp_d/reports/hardened144-20261101/`. These
are the numbers you may be asked to defend; do not quote any figure you cannot trace there.

| Item | Value |
| --- | --- |
| Slots attempted / completed | 144 / 136 |
| Technical failures | 8 (Single 1, Fixed-4 2, Dynamic 3, verifier 2) |
| Dynamic | 33/36 quality · 27/27 root · 6/6 abstain · 412.9 s · 14.6 req · 12.0 tools · 149,216 tok |
| Single | 32/36 · 25/28 · 7/7 · 680.9 s · 17.3 · 14.5 · 245,971 |
| Fixed-4 | 22/36 · 15/27 · 7/7 · 196.3 s · 7.8 · 7.4 · 58,042 |
| Verifier | 30/36 · 23/27 · 7/7 · 503.8 s · 17.6 · 15.5 · 233,772 |
| Dynamic vs Single | +1 quality, −39.4% latency, −39.3% tokens |
| Dynamic vs Verifier | +3 quality, −18.0% latency, −36.2% tokens; verifier +56.7% tokens |
| Paired (W/L/T) | Single 3/2/31 · Fixed 12/1/23 · Verifier 5/2/29 |
| Wrong root causes | 0 of 144 |
| Identifiable misses | 19, all `INCONCLUSIVE` (Fixed-4 12, Verifier 4, Single 3, Dynamic 0) |
| Guard replay estimate | −44.0% (3003), −21.9% (3008), −12.3% (10-case batch), threshold 5 |
| Tests | 1,179 passed, 3 skipped, 0 failed; 2026-11-02; 381 s |
| Corpus | 40 public packs; hardened 36 cases, 29/7, 10 families |
| Budgets | 4 rounds, 12 tool calls, 16 LLM requests, 600 s |
| Batch runtime | 16,737.6 s (4 h 38 m 58 s); 24,376,395 tokens |

---

## 6. Rehearsal: run this as a mock Q&A

Assign one person to ask, one to answer, one to time. Two minutes per question.

1. "Your zero-wrong-cause result — how much is the closed vocabulary?"
2. "Why does Dynamic have more technical failures than Single?"
3. "Which single number should we remember?"
4. "What would you do next with two more weeks?"
5. "Why should we believe the cost comparison if averages exclude failures?"
6. "Show me one citation and prove it came from this run."
7. "What is the weakest part of this project?"

For question 7, the answer is over-abstention: 19 identifiable cases across the four
architectures ended `INCONCLUSIVE`, and an operator may read repeated abstentions as a broken
tool. That is the honest weak point, and it is measured.
