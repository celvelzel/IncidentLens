# IncidentLens — Verified Source of Truth

**Purpose.** This is the single fact base for the README, submission documents, slides,
speaker script, Q&A and website copy. Every public claim about the project should trace to
this file. Evidence labels:

- **VERIFIED** — read directly from the implementation, contracts or dataset.
- **MEASURED** — taken from a saved result artifact, with its denominator and boundary.
- **INTERPRETATION** — a reasoned reading of measured evidence; never phrased as proof.
- **PROPOSED** — designed but not implemented or not evaluated.
- **UNVERIFIED** — unavailable, not run, or not safe to claim.

Last fact-base review: **2026-11-02**. Project version `1.6.1`.
Course: **COMP5584 Large Language Models for Agents**, The Hong Kong Polytechnic University,
2026/27 Semester 1. Submission deadline from the official guidelines:
**23 November 2026, 11:59 PM**. Recommended archive name in the guidelines:
`COMP5584+GroupProject+Group5.zip`. The deck uses **Group 5**; member names are deliberately
not invented and must be added by the group.

> The reference PowerPoint supplied by the user is a **design reference only**. It is a
> different course's deck (COMP5434, Group 9). None of its project facts, member names,
> results or claims belong to IncidentLens.

---

## 1. What the system is

**VERIFIED.** IncidentLens is an evidence-driven multi-agent system for software incident
investigation and root-cause analysis (RCA). It reads only public, read-only incident
evidence (logs, metrics, database observations, changes, configs, topology), coordinates
specialist agents, and produces either a cited root-cause report or an explicit
`INCONCLUSIVE` abstention. An optional response workflow adds public-snapshot monitoring
and a remediation **proposal**. No production change is executed.

The system is a research/teaching prototype over synthetic incident packs. It is **not** a
production incident platform, has no live production integrations, and has not been
validated by on-call engineers.

**Core contract (VERIFIED).**

1. A conclusion must cite records that the run actually observed.
2. A candidate root cause must have at least two supporting records from different source
   paths, an observed cause-specific discriminator, and temporally compatible cross-source
   corroboration.
3. If those conditions are not met, the run abstains rather than guessing.
4. Merge and FinalizeGate are deterministic; model confidence cannot override them.
5. Every role has a fixed, read-only tool allowlist.

---

## 2. Canonical names and terminology

| Concept | Public name to use | Internal value | Notes |
| --- | --- | --- | --- |
| Primary architecture | **Dynamic** | `dynamic` | Dynamic specialist selection; no independent verifier |
| Verifier ablation | **Dynamic (with verifier)** | `full` | Adds the Verifier review loop |
| Fixed baseline | **Fixed-4** | `fixed` | One fixed logs/metrics/database/changes batch |
| Single baseline | **Single** | `single` | One agent with all investigator tools |
| Legacy alias | — | `dynamic_no_verifier` | Frozen benchmark/trace name; normalizes to `dynamic`; never written for new runs |
| Benchmark lineage | **causal-world-v2-hardened** | same | 36 development cases |
| Earlier lineage | **causal-world-v16** (dev) | same | 10 development cases |
| Benchmark | **IncidentBench** | same | Evaluator-only labels, matched-tool variants |

Use "**root cause**" only for a `RESOLVED` report. For an `INCONCLUSIVE` report with a
leading explanation, use "**provisional / likely explanation — not confirmed**".
Use "**remediation proposal**", never "remediation" as if executed.
Use "**recorded replay**" only for a saved trace loaded without re-execution.

---

## 3. Agent roles and orchestration (VERIFIED)

Implementation: `src/incident_lens/orchestration/graph.py`, `agents/service.py`,
`orchestration/guards.py`, `security/context.py`, `schemas/contracts.py`.

| Role | Responsibility | Tool authority |
| --- | --- | --- |
| Monitoring (`monitoring`) | Detect anomalies in a public snapshot/replay; emit `ALERT` or `NO_ALERT` | none |
| Coordinator (`coordinator`) | Choose `INVESTIGATE` / `FINALIZE` / `ABSTAIN`; assign at most 2 tasks per round; replan from evidence gaps and budget | none |
| Logs investigator (`logs`) | Reconstruct error chronology and propagation | `query_logs` |
| Metrics & dependency investigator (`metrics`) | Inspect service health, capacity and dependency scope | `query_metrics`, `get_dependencies`; database tools only where equivalent-tool configuration grants them |
| Database investigator (`database`) | Analyse connections, sessions, locks and slow queries | `get_db_connections`, `get_db_active_sessions`, `get_db_lock_waits`, `get_db_slow_queries`, `get_db_health_metrics` |
| Changes investigator (`changes`) | Compare deployments/config changes with onset | `query_changes`, `get_config_diff` |
| Verifier / skeptic (`verifier`) | Challenge a candidate using already-published evidence; request concrete checks | `fetch_evidence_by_ids` |
| Remediation (`remediation`) | Produce a `PLAN_ONLY` proposal after an accepted RCA | none |
| Reporter (`reporter`) | Deterministic report rendering | `fetch_evidence_by_ids` |
| Single baseline (`single`) | One agent performs planning, investigation and self-reflection | all investigator tools + evidence fetch |

**Workflow.** LangGraph `StateGraph` with nodes:
`monitor → coordinate → dispatch (1–2 concurrent specialists) → merge → [verify] →
finalize → remediate → stop → report`. `merge` and `finalize` are deterministic.
`full` inserts `verify`; `dynamic` does not. Terminal paths from every phase pass through
a unified shutdown (`stop`) with a `TerminationResult`.

**Coordinator decisions.** `INVESTIGATE` requires assignments and forbids a selected
hypothesis or stop reason; `FINALIZE` requires a selected hypothesis; `ABSTAIN` may nominate
an unconfirmed leading explanation (`proposed_hypothesis_id`) but never asserts a root cause.
Maximum 2 assignments per round. A repeated task signature is suppressed; a completed scope
is not reassigned.

**Budgets.** Defaults from `Budget`: 4 rounds, 12 tool calls, 16 LLM calls, 600 s.
`CallBudget` counts physical requests, retries and structured repairs. Budget exhaustion is
a runtime failure (`BUDGET_EXHAUSTED`). Ordinary evidence insufficiency is `INCONCLUSIVE`,
not a runtime failure.

**Bounded recovery.** Task-level retry with backoff and stage budgets; atomic request
permits; one targeted structured-output repair; classified transport failures. Retry
accounting is explicit in events. Recovery behavior was tested with injected mock faults;
real-provider recovery of a failed request was **not** measured (the one recorded real
retest had no failure to recover).

---

## 4. Evidence discipline and security (VERIFIED)

- **Read-only provider.** `EvidenceProvider` reads only six fixed filenames under
  `data/incidents/<id>/public/` plus `topology/services.yaml`; it rejects symlinks,
  junctions, path traversal, unknown files and private paths. `validate_public()` never
  reads private oracles.
- **Role ACL.** `ROLE_TOOL_ACL` fixes each role's ceiling. `AgentContext` is frozen and
  validates that `allowed_tools` cannot elevate the role.
- **Observation ledger.** A worker may cite only evidence it actually queried. Merge
  validates worker identity, task role and observed IDs before publishing shared evidence.
- **Shared evidence board.** Merge is the only publisher of findings and shared evidence;
  hypothesis IDs are stable per `(culprit_service, failure_mode)` concept, and conflicting
  current assessments keep a hypothesis `OPEN`.
- **Deterministic grounding.** `grounding_errors()` requires ≥2 support records from ≥2
  source paths, an observed `cause_discriminator` for the failure mode, and temporally
  compatible cross-source impact/corroboration; any `against_ids` blocks selection.
- **Competing hypotheses.** An alternative blocks only if it has an observed competing
  mechanism or unobserved citations; generic symptoms do not get veto power, and absence of
  telemetry never proves an alternative false.
- **Verifier binding (full only).** Finalization requires a review whose citations match
  fetched evidence, plus a `REVIEW` event fingerprint bound to the current candidate and
  evidence snapshot. The verifier is an ablation, not the primary architecture.
- **Cited-or-abstain.** `RCAReport` enforces `RESOLVED` ⇒ supported root cause + evidence +
  causal chain; `INCONCLUSIVE` ⇒ no root cause; `LIKELY` ⇒ `INCONCLUSIVE` + provisional
  hypotheses (max 3, `OPEN`, cited).
- **Replay safety.** Web replay accepts only a `trace.json` inside `results/`, loads it via
  `load_replay` without calling graph/tools/provider, and binds companion metadata
  (result/scope/verification) by identity; unsafe or mismatched companions are not shown.

---

## 5. Failure-mode taxonomy (VERIFIED)

Seven labels are constrained in the analysis schema:

1. `backend_pool_config_regression`
2. `postgres_connection_exhaustion`
3. `redis_unavailable`
4. `payment_external_timeout`
5. `backend_resource_saturation`
6. `postgres_lock_contention`
7. `postgres_slow_query`

Each has a deterministic discriminator in `guards.cause_discriminator()` (for example, a
pool decrease paired with higher concurrency; connections at the configured limit;
`connection refused`/availability 0; payment latency ≥ 3000 ms; CPU/thread utilisation ≥ 90;
locks with `blocked_by`; slow-query category). These are **acceptance checks over public
measurements**, not an oracle and not proof of causal correctness.

---

## 6. Data and benchmark (VERIFIED)

### 6.1 Public incident corpus

`data/incidents/` contains **40 synthetic packs** (`incident_001`–`incident_040`):
6 seed, 10 dev, 20 test, plus 4 additive database packs. Each public pack has
`incident.json`, `logs.jsonl`, `metrics.csv`, `changes.jsonl`, `configs.jsonl`,
optional `database.jsonl`, and shared `topology/services.yaml`. Five packs omit crucial
discriminating evidence. All observations are synthetic. Public metadata carries only raw
observation fields; answer labels live in separate evaluator oracles.

### 6.2 IncidentBench hardened batch

`data/incidentbench_v2_hardened`, encoder lineage `causal-world-v2-hardened`:

- **36 cases**, `incident_4001`–`incident_4036`; all split `dev` (seed 0, test 0).
- **29 identifiable / 7 intended to abstain**; **10 scenario families**.
- Challenge tags: ordinary 21, missing 7, counterfactual 6, misleading 2.
- Per-case lever partition used in the result analysis: standard 7, boundary 7, competing 7,
  missing 7, misleading 2, counterfactual pair 6.
- `label_status = pending`, `accepted_labels = 0`, `blindness_level =
  development_visible`, `independence_status = unreviewed`,
  `independent_audited_families = 0`.
- Every oracle has `annotator_status: pending`, `review_version: candidate-v1`,
  `reviewer_ids: []`. Labels are provisional candidate labels, not accepted human labels.
- **Caution:** `manifest.coverage.difficulty_levers` (boundary 14, competing 15, standard 7)
  counts overlapping tags and does not match the per-case partition. Do not present
  14/15/7 as case counts.

### 6.3 Earlier batch

`data/incidentbench_v16_dev`: **10 cases** (`incident_3001`–`incident_3010`), 8 identifiable
/ 2 abstaining, 2 families, dev-only, labels pending, development-visible.

No blind or held-out test set exists. `docs/incidentbench/blind-test-protocol.md` states
formal sealing is blocked. No production, OOD or monitoring cohort was evaluated
(cohorts = 0).

---

## 7. Measured results

### 7.1 Hardened 144-slot batch (MEASURED)

Batch `full144-hardened-c4-20261101`, `auto/deepseek-v4.1-flash`, temperature 0,
cache off, 4 jobs, 1 repeat, 36 cases × 4 architectures = 144 slots.
Runtime 16,737.6 s (4 h 38 m 58 s). **136 completed, 8 technical failures, 0 interrupted.**
Source: `results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json`;
interpretation: `analysis/wp_d/reports/hardened144-20261101/README.md`.

| Architecture | Technical | Root correct | Correct abstention | Quality success | Avg latency | Avg requests | Avg tools | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 35/36 | 25/28 | 7/7 | 32/36 (88.9%) | 680.9 s | 17.3 | 14.5 | 245,971 |
| Fixed-4 | 34/36 | 15/27 | 7/7 | 22/36 (61.1%) | 196.3 s | 7.8 | 7.4 | 58,042 |
| **Dynamic (primary)** | 33/36 | **27/27** | **6/6** | **33/36 (91.7%)** | 412.9 s | 14.6 | 12.0 | 149,216 |
| Dynamic (with verifier) | 34/36 | 23/27 | 7/7 | 30/36 (83.3%) | 503.8 s | 17.6 | 15.5 | 233,772 |

Resource averages use **completed runs only** (n = 35 / 34 / 33 / 34). Failed-slot tokens
(921,599) are excluded from averages but included in the batch total of **24,376,395
tokens**. Quality among completed runs: Dynamic 33/33, Single 32/35, Verifier 30/34,
Fixed 22/34.

**Differences (descriptive, one repeat, no significance test):** Dynamic vs Single:
+1 quality success, −39.4% latency, −39.3% tokens. Dynamic vs Dynamic (with verifier):
+3 quality successes, −18.0% latency, −36.2% tokens; the verifier loop cost **56.7% more
tokens** with no measured quality gain. Fixed-4 is cheapest but wrongly abstained on 12 of
27 identifiable cases.

**Paired per-case quality (Dynamic better / worse / tie):** vs Single 3/2/31;
vs Fixed 12/1/23; vs Dynamic (with verifier) 5/2/29.

**Difficulty levers (quality success, n per architecture as shown):**

| Lever | Single | Fixed-4 | Dynamic | Dynamic (with verifier) |
| --- | ---: | ---: | ---: | ---: |
| competing (n=7) | 6/7 | 4/7 | **7/7** | 6/7 |
| counterfactual pair (n=6) | 5/6 | 3/6 | **6/6** | 4/6 |
| standard (n=7) | 6/7 | 3/7 | 6/7 | 6/7 |
| boundary (n=7) | 6/7 | 4/7 | 6/7 | 5/7 |
| missing (n=7) | 7/7 | 7/7 | 6/7 | 7/7 |
| misleading (n=2) | 2/2 | 1/2 | 2/2 | 2/2 |

**No wrong root causes.** Across 144 slots, all 19 identifiable misses that completed ended
`INCONCLUSIVE` with no asserted culprit; none named a wrong culprit/failure-mode pair.
All 27 completed unidentifiable slots correctly abstained (Dynamic 6/6 because one
unidentifiable Dynamic slot failed technically; the other architectures 7/7). The observed
failure mode is **over-abstention, not fabrication**.

**Technical failures (8/144):** 6 `STRUCTURED_OUTPUT_INVALID` (five provider responses
with no string content, one truncated output invalid after its one repair) + 2
`FINDING_IDENTITY_MISMATCH`; by architecture Single 1, Fixed 2, Dynamic 3,
Dynamic (with verifier) 2. They were not retried and remain in the denominator. Described
as a provider/structured-output layer issue, not evidence of an architecture defect.

### 7.2 Earlier 10-case batch (MEASURED)

Batch `full40-local-gateway-c4-20261031`, same model/settings, 40 slots, 40/40 completed
over three executions (3,104.9 s for 39/40, an interrupted resume, then 739.7 s for 40/40).
Source:
`results/v16/wp-d/full40-local-gateway-c4-20261031/final-success-comparison.json`.

| Architecture | Technical | Root correct | Correct abstention | Quality success | Avg latency | Avg requests | Avg tools | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 10/10 | 8/8 | 2/2 | 10/10 | 391.2 s | 17.6 | 15.0 | 257,146 |
| Fixed-4 | 10/10 | 5/8 | 2/2 | 7/10 | 96.9 s | 7.9 | 7.6 | 56,586 |
| **Dynamic** | 10/10 | 8/8 | 2/2 | **10/10** | 233.5 s | 14.0 | 11.8 | 145,035 |
| Dynamic (with verifier) | 10/10 | 8/8 | 2/2 | 10/10 | 438.9 s | 18.8 | 15.9 | 269,832 |

Dynamic vs Single: same 10/10 quality, −40.3% latency, −20.5% requests, −21.3% tool
queries, −43.6% tokens. Dynamic vs verifier: same quality, verifier +88.0% latency,
+34.3% requests, +34.7% tools, +86.0% tokens. The verifier needed 12 attempts; all-attempt
totals are lower bounds. The saved `correctness` strings in this batch are mojibake; use
only the numeric fields.

### 7.3 What the evaluation does **not** establish (UNVERIFIED)

- No blind/held-out test; labels are provisional and unreviewed; one model, one repeat.
- No confidence interval, significance test, variance or model-sensitivity estimate.
  The protocol names a family-clustered paired bootstrap, but no real-batch
  `statistical-analysis.json` exists. The only statistics artifact is a **mock** hardened
  validation with `status: insufficient_clusters`, `ci95: null`, `p = null`, 1 effective
  cluster.
- No USD cost (null); tokens are measured, cost is not.
- No human evaluation of semantic support, unsupported claims, citation semantics or
  remediation effectiveness.
- No real-provider cache experiment (cache measured on mock, one case: warm hit rate 1.0,
  4 calls avoided, identical reports, tokens/cost null).
- No real-provider recovery experiment (mock injected fault, task recovery 1.0 with
  denominator 2 per variant; the real retest had zero failures to recover).
- The evidence-gap guard's token reduction is **replay-estimated**, not a new measured run:
  threshold 5 on the frozen 10-case batch gives −44.0% on 3003, −21.9% on 3008, −12.3%
  across the batch. The default `max_rounds: 4` means the guard cannot fire under the
  stock configuration; it changes budget, never gate acceptance.
- The synthetic corpus does not establish production generalization. Variants share causal
  templates and encoder lineage; `accepted_labels = 0`, `independent_audited_families = 0`.

---

## 8. Implementation and reproducibility (VERIFIED)

- Python ≥3.11; verified on Windows with Python 3.13. Package version 1.6.1.
- Declared runtime: `langgraph==1.2.14`, `pydantic==2.14.0`, `PyYAML`, `httpx`,
  `python-dotenv`, `numpy`, `starlette==1.7.0`, `uvicorn`, `streamlit==1.65.0`.
- Console entry point `incident-lens`; CLI also runs as `python -m incident_lens.cli`.
- Offline mode: `--provider mock` uses a deterministic mock over supplied public evidence;
  no API key or model weights.
- Real mode needs `INCIDENT_LENS_BASE_URL`, `INCIDENT_LENS_API_KEY`,
  `INCIDENT_LENS_MODEL`; `.env.example` contains blanks only. Never commit `.env`.
- Artifacts: `trace.json`, `result.json`, `report.md`, optional `scope.json` and
  `verification.json`. `replay` validates saved state without graph/tool/provider calls.
- Web: Starlette static SPA on `127.0.0.1:8022`; routes `/api/health`, `/api/meta`,
  `/api/cases`, `/api/run` (POST), `/api/traces`, `/api/replay` (POST), `/api/download`.
  Live runs write `results/ui/<run_id>/`; replay is confined to `results/**/trace.json`.
  The web API's `WorkflowOptions` supports the response workflow; the dashboard runs the
  default dynamic architecture.
- Tests: 88 Python test files; `pytest --collect-only -q` reports **1182 tests collected**.
  Full suite run on 2026-11-02 against this tree: `1179 passed, 3 skipped in 450.01s`,
  exit 0 (`results/pytest-current.log`). Re-run after any change to source, tests,
  configuration or web assets.
- Web acceptance: Playwright scripts in `tests/web/` (real HTTP, no route interception).

---

## 9. Design rationale (INTERPRETATION, not proof)

- **Dynamic selection** is motivated by the cost of uniform investigation: a fixed batch
  asks every specialist even when one source can discriminate. Measured evidence is
  consistent with this (higher quality and lower cost than Single; much higher quality than
  Fixed-4), but the study cannot isolate the causal mechanism from model behaviour.
- **Deterministic gates** are motivated by the untrustworthiness of model self-confidence.
  The code enforces citations, source diversity, mechanism and competitor checks regardless
  of stated confidence. This is a design contract, not an empirical claim that gates are
  optimal.
- **The verifier is retained as an ablation**, not the default. On both measured batches it
  added cost without a measured quality gain. That is "no gain observed in these batches",
  not proof that verifiers never help.
- **Abstention is a feature.** All observed errors were over-abstention; this is safer than
  confident fabrication but reduces coverage. The project reports it as a limitation.
- **Plan-only remediation** is deliberate: the system proposes actions, preconditions,
  risks, verification and rollback but never executes them.

---

## 10. Proposed extensions (PROPOSED; not implemented/evaluated)

- A sealed, independently labelled blind test and human semantic-support audit.
- Multi-model and repeated-run variance analysis with the pre-declared clustered bootstrap.
- A real-provider cache study and real-provider fault-recovery study.
- An executed evidence-gap guard experiment (not replay estimation).
- Production-like telemetry adapters, OOD/monitoring cohorts and on-call usability studies.
- Optional human-in-the-loop approval before any remediation execution (execution is
  currently out of scope).
- Richer causal modelling (request-level linkage) to reduce over-abstention.

Do not present any of these as delivered.

---

## 11. Unavailable information and integrity rules

**UNVERIFIED / unavailable.**

- Member names, student IDs, individual contributions and percentages. The Individual
  Contribution Statement must remain blank; no roles or shares may be inferred.
- Demo video: not recorded or edited by this work.
- Presentation date, room and assessor preferences.
- Production performance, real incident accuracy, cost in USD, latency under real load.
- Official PolyU endorsement. The project is a course submission, not an institutional
  product. The PolyU logo is used only in the course deck, following the supplied course
  template; it must not appear on the public project website.

**Claim ledger.**

| Do not write | Write instead |
| --- | --- |
| "proves dynamic is best" | "Dynamic had the highest measured quality in this development batch" |
| "eliminates hallucination" | "enforces cited-or-abstain and produced no wrong root cause in 144 measured slots" |
| "verifier improves accuracy" | "the verifier showed no measured quality gain and cost more in both batches" |
| "44% token saving" (as measured runtime) | "replay-estimated −44.0% on incident_3003 under threshold 5" |
| "blind test" / "held-out test" | "development-visible batch with provisional candidate labels" |
| "production-ready" | "research/teaching prototype over synthetic incidents" |
| "all tests pass" (before a fresh run) | report the exact fresh test result and date |
| "real-time production monitoring" | "optional public-snapshot monitoring profile" |
| "automatically remediates" | "produces a PLAN_ONLY remediation proposal" |
| "state-of-the-art" | no comparative SOTA claim was measured |

**Visual identity.** PolyU red `#9A0907`, navy `#003070`, light grey `#E8E9EF`, mid grey
`#A6A6A6`, white; serif display titles (Georgia / Times New Roman), sans body (Calibri /
Segoe UI). The deck follows the supplied PolyU course template's section rail and header
logo; the website borrows the palette and typographic contrast but uses its own wordmark and
does not imply endorsement.
