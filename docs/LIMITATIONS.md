# Limitations

IncidentLens is a course research prototype over synthetic incident data. This document states
what it does not establish, where the implementation is narrow, and what evidence would be
required to change the conclusions. It is intentionally more specific than a generic
"future work" section.

The project is a COMP5584 course submission and is not an official PolyU product. The PolyU
name and logo belong to the course presentation context and must not be presented as
endorsement or used on a public product site.

## 1. How to read the claims

The project uses five evidence labels:

| Label | Meaning |
| --- | --- |
| **VERIFIED** | Checked in the source, contracts or command behavior |
| **MEASURED** | Produced by a recorded run with saved artifacts |
| **INTERPRETATION** | A reasoned reading of the measurements, not a causal proof |
| **PROPOSED** | A future direction or design option that is not implemented as a measured capability |
| **UNVERIFIED** | Not established by the current evidence |

The 144-slot and 10-case results are MEASURED. Statements about why Dynamic outperformed
another variant are INTERPRETATION. Claims about production reliability, user value,
statistical significance or general superiority are UNVERIFIED and are not made.

## 2. Technical limitations

### 2.1 Synthetic, read-only, single-incident scope

- All 40 public packs and all benchmark cases are synthetic. No production telemetry,
  observability integration, customer incident or on-call workflow was used.
- The runtime reads only a fixed set of public files for one incident at a time. It does not
  aggregate across incidents, maintain a service graph over time, or ingest streaming data.
- Tools are read-only. The system cannot restart a service, change a pool, roll back a
  deployment or execute a runbook.
- Remediation is `PLAN_ONLY`, capped at two proposals in the response profile. A proposal is
  not an action and has not been evaluated for operational effectiveness.

### 2.2 Fixed failure vocabulary and discriminators

The analysis schema constrains seven failure modes:

1. `backend_pool_config_regression`
2. `postgres_connection_exhaustion`
3. `redis_unavailable`
4. `payment_external_timeout`
5. `backend_resource_saturation`
6. `postgres_lock_contention`
7. `postgres_slow_query`

Each has a deterministic discriminator in the guard layer. A real incident outside this
vocabulary, or one whose mechanism is not expressible in these measurements, will be rejected
even if a human would recognize the cause. The implemented discriminator vocabulary is listed
in [Architecture §6](ARCHITECTURE.md#6-finalizegate).

This is a direct source of over-abstention. The measured zero-wrong-cause result is therefore
partly a statement about a closed world, not evidence that the system is safe on arbitrary
incidents.

### 2.3 Provenance is not semantic support

The runtime proves that a cited record exists, was observed by the right agent in the right
task, and passed structural validation. It does not prove that the record semantically
supports the attached sentence. No human semantic-support, unsupported-claim or
citation-relevance evaluation was performed.

A citation can be real and still be insufficient, misleading or incomplete. The deterministic
gates reduce this risk with source-diversity and mechanism checks, but they do not eliminate
it.

### 2.4 Deterministic gates can be gamed by vocabulary, not understanding

The gates check observable patterns. A generated or adversarially constructed incident that
places the expected discriminator in the public evidence can pass the gate without the system
understanding the incident. Conversely, a genuine incident that lacks the exact pattern is
rejected. The evaluation measures behavior on a synthetic generator that shares templates and
lineage; it does not establish robustness to distribution shift or adversarial evidence.

### 2.5 Prompt injection and untrusted evidence

Incident evidence is untrusted text. Role-scoped read-only tools and a public-file allowlist
reduce the impact of injected instructions, but they do not eliminate prompt-injection risk.
An agent could still be influenced by content in a log line or configuration value within its
authorized scope. One isolation test checks that an injected instruction remains data, cannot
widen tool access and is not echoed into events, but that is a unit-level control, not a
dedicated prompt-injection benchmark or red-team evaluation. This is an INTERPRETATION of the
security posture, not a measured guarantee.

### 2.6 Recovery and caching are not established on real providers

- Recovery was tested with injected Mock faults: task recovery 1.0 with a denominator of 2
  per variant. The one recorded real-provider retest encountered zero failures, so recovery
  was not exercised.
- The cache was measured on Mock, one case: warm hit rate 1.0, four calls avoided, identical
  reports, tokens and cost null. There is no real-provider cache experiment.
- The evidence-gap guard's token reduction is replay-estimated, not a new measured run:
  threshold 5 gives 44.0% fewer tokens on case 3003, 21.9% on case 3008 and 12.3% across the
  frozen 10-case batch. The default `max_rounds: 4` means it cannot fire under stock
  configuration, and it changes budget allocation, never gate acceptance.

These mechanisms should not be described as production reliability features.

### 2.7 Replay and portability limits

- Replay reconstructs a saved trace; it does not re-execute the graph. A replay cannot reveal
  a bug that depends on a different provider response or live tool state.
- The web replay surface is confined to `results/**/trace.json`. Companion metadata is bound
  by identity, and mismatched companions are not shown; this is a safety property, but it
  also means a trace moved without its companions loses context.
- IncidentBench artifacts contain absolute local context paths. Portability to a moved
  checkout requires a relocation protocol that is not implemented.
- The bundled dashboard's evaluation view is a static, hard-coded snapshot of one recorded
  batch, not a live feed, and its UI text is Chinese. It is a demo surface, not an accessible
  production console.

### 2.8 Operational and packaging gaps

- No license file is currently declared. Reuse rights are therefore unclear until the group
  adds one.
- Member names, IDs and individual contributions are unavailable in this checkout. No
  attribution is invented. The individual contribution statement remains for the group to
  complete.
- A deck export is present at `presentation/IncidentLens_Final.pptx` with a PDF and rendered
  slides, but its delivery date, room and approval are not recorded here, and no demo video is
  present. A video must not be claimed until it is recorded and verified.
- The submission archive is built and size-checked as the last step of the submission
  checklist; this document does not record its contents.

## 3. Empirical limitations

### 3.1 Provisional, development-visible labels

The hardened corpus has 36 cases, 29 identifiable and 7 intended to abstain, across 10
families. Its metadata is:

- `label_status: pending`;
- `accepted_labels = 0`;
- `blindness_level: development_visible`;
- `independence_status: unreviewed`;
- `independent_audited_families = 0`;
- every oracle has `annotator_status: pending`, `review_version: candidate-v1` and
  `reviewer_ids: []`.

The labels are candidate labels, not accepted human ground truth. Scoring against them is
provisional. There is no blind or held-out test; the blind-test protocol records that formal
sealing is blocked, and the number of production, out-of-distribution or monitoring cohorts
is zero.

The earlier 10-case batch is also development-visible with pending labels across 2 families.
It is a replication check, not independent confirmation.

### 3.2 One model, one repeat, no significance test

The recorded batches used `auto/deepseek-v4.1-flash`, temperature 0, cache off, one repeat.
There is no repeat-variance estimate, no multi-model sensitivity analysis, no confidence
interval and no significance test on a real accepted batch.

The only statistics artifact is a Mock hardened validation with
`status: insufficient_clusters`, `ci95: null`, `p: null` and one effective cluster. The
protocol names a family-clustered paired bootstrap, but it has not been run on an accepted
independent batch.

All reported differences are descriptive arithmetic on one run. A paired split of 3/2 against
Single, or 5/2 against the verifier, is not a population effect.

### 3.3 Small corpus and shared lineage

The hardened corpus has 36 cases; the earlier batch has 10. Both are generated from causal
templates with shared encoder lineage. Four source groups share development encoder lineage.
A high score may reflect the generator family rather than diagnostic reasoning that transfers
to real incidents.

The 10-case batch has a ceiling effect: three variants achieved 10/10 quality. Ceiling effects
reduce the ability to discriminate architectures and make cost differences more informative
than quality differences.

### 3.4 Technical failures and denominator effects

Eight of 144 slots failed technically: six `STRUCTURED_OUTPUT_INVALID` (five provider
responses with no string content, one truncated output invalid after repair) and two
`FINDING_IDENTITY_MISMATCH`, spread across all four architectures (Single 1, Fixed-4 2,
Dynamic 3, Dynamic with verifier 2). They were not retried and remain in the quality
denominator.

Resource averages use completed runs only. Failed-slot tokens (921,599) are excluded from the
averages but included in the batch total of 24,376,395 tokens. This means average latency,
requests, tools and tokens describe successful executions, not the full cost of an attempted
portfolio. A variant with more failures can appear more efficient per completed run.

Root-correct and abstention denominators are completion-dependent. Dynamic's 27/27 root
correct is out of 27 completed identifiable runs, not 28; one identifiable Dynamic slot
failed technically. Dynamic's 6/6 abstention is because one of its seven unidentifiable slots
failed technically. These denominators are correct for completed-run accuracy, but they do
not mean the failed slot would have succeeded.

### 3.5 Binary quality and missing cost measures

Quality success is a binary per-case count of correct root cause or correct abstention. It
does not weight severity, business impact, time-to-resolution, partial credit or the
usefulness of a likely explanation. A system that abstains more can score differently
depending on the identifiable/unidentifiable mix.

No USD cost was computed (`null`). Token, request, tool and latency counts are proxies, not
monetary or operational cost. Provider pricing, retries, infrastructure and human review time
are outside the measurement.

No human evaluation of semantic support, unsupported claims, citation semantics or
remediation effectiveness was performed. Those metrics remain null.

## 4. The over-abstention problem

The central empirical weakness is over-abstention, not fabrication.

Across 144 slots, no completed run named a wrong culprit/failure-mode pair. All 19
identifiable misses that completed ended `INCONCLUSIVE` with no asserted culprit. All 27
completed unidentifiable slots abstained correctly. Fixed-4 wrongly abstained on 12 of 27
identifiable cases. Dynamic is below ceiling on `standard`, `boundary` and `missing`, each at
6/7. The `missing` miss is consistent with the technical failure in an unidentifiable slot;
the other two are not separately attributed in the saved analysis. None is a wrong cause.

This is a real trade-off:

- **Benefit:** the system avoids unsupported root causes in the measured corpus.
- **Cost:** it misses 19 identifiable cases across the four architectures and is especially
  weak on a fixed schedule.
- **Risk:** an operator may see repeated `INCONCLUSIVE` results as a broken tool and stop
  using it, or may over-trust the cases where it does resolve.

The correct claim is "no wrong root causes in these development batches, with substantial
over-abstention", not "hallucination-free" or "reliable". The evaluation does not establish
that the abstention rate is acceptable for any operational setting.

## 5. Ethical and societal considerations

### 5.1 Synthetic data and privacy

The public corpus is synthetic and contains no real customer data. This avoids consent and
privacy risk in the study, but it also means no claim can be made about handling sensitive
production logs. Extending the system to real telemetry would require a privacy review,
redaction, retention policy and data-processing agreement.

Real-provider runs send public evidence to an external model endpoint. The demo therefore uses
Mock. If a real provider is used, the operator must confirm that the evidence is safe to
disclose and that provider logging terms are acceptable. No credential belongs in the
repository.

### 5.2 Automation bias and unsafe trust

A cited, confident-looking report can encourage automation bias. The interface distinguishes
`RESOLVED` from `INCONCLUSIVE`, and a likely explanation is not a confirmed root cause, but
there is no user study showing that operators interpret these states correctly. The system
must not be presented as an autonomous authority or as a replacement for incident command.

Remediation is a proposal. A wrong proposal could still influence an operator to take a
harmful action. No remediation effectiveness or safety evaluation was performed.

### 5.3 False abstention as a hidden failure

Over-abstention is safer than fabrication but not harmless. In an outage, a tool that
repeatedly says "insufficient evidence" can delay mitigation or erode trust. The measured
cost is reported rather than hidden, and the system does not claim operational fitness.

### 5.4 Attribution, endorsement and intellectual property

- No license is declared, so reuse rights are unresolved.
- Group member names and contributions are not asserted; the contribution statement must be
  completed by the group.
- The PolyU name and logo must not imply official endorsement or appear on a public product
  site. Their use is limited to the course presentation context.
- Third-party datasets, fonts, images or code used in the presentation require their own
  attribution; this document does not certify the deck.

## 6. Scope and non-goals

IncidentLens does not:

- execute remediation or modify production state;
- integrate with Prometheus, Grafana, PostgreSQL, cloud APIs or an incident-management tool;
- ingest streaming telemetry or handle multiple concurrent incidents;
- learn from feedback, retain cross-run memory or update its prompts from outcomes;
- perform root-cause analysis outside the seven-mode vocabulary;
- provide a multi-tenant, authenticated or hardened web service;
- replace human incident commanders or on-call engineers;
- establish causal superiority of multi-agent over single-agent design.

These are scope decisions. They should not be described as pending features that already
work.

## 7. What would change the conclusions

The following evidence would materially strengthen, weaken or overturn the current reading:

| Evidence | What it would establish |
| --- | --- |
| Accepted labels from independent annotators | Whether the candidate labels are correct and whether scoring is trustworthy |
| A sealed blind or held-out corpus | Whether results transfer beyond development-visible cases |
| Multiple models and repeated runs | Whether the architecture differences exceed model and run variance |
| Pre-declared clustered bootstrap on a real batch | Confidence intervals and a defensible significance claim |
| Production or out-of-distribution telemetry | External validity beyond synthetic templates |
| Human semantic-support and citation review | Whether real citations actually support the claims |
| USD and operational cost accounting | Whether the efficiency differences matter economically |
| Real-provider cache and fault-recovery experiments | Whether those mechanisms work under real transport failures |
| A verifier redesign with a stronger review protocol | Whether the negative ablation is specific to this implementation |
| A prompt-injection and adversarial-evidence benchmark | Whether role scoping is sufficient under hostile content |
| A usability study with on-call engineers | Whether abstention states and evidence panels are understood and useful |

Until several of these exist, the strongest defensible statement is:

> On a 36-case synthetic development corpus, with candidate labels, one model and one repeat,
> Dynamic achieved 33/36 quality success and 27/27 root correctness among completed
> identifiable runs; no completed run named a wrong root cause; the dominant error was
> over-abstention; and the independent verifier added substantial token cost without a
> measured quality gain.

Every clause in that sentence is bounded. Do not remove the boundaries when summarizing it.
