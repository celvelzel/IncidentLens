# Demo Guide

This is an 8-10 minute demonstration plan for IncidentLens using the bundled dashboard and
the CLI. It is written so the demo can run live from a fresh installation or fall back to a
saved recorded replay without changing the story.

No demo video is claimed to exist. If the group records one, use the checklist at the end.

## 1. Demo objectives

By the end of the demo, the audience should understand four things:

1. IncidentLens produces a **cited** root cause, not a free-form narrative.
2. The deterministic gates can say **`INCONCLUSIVE`**, and that is a designed outcome.
3. The evidence registry shows **where each claim came from** and that the run observed it.
4. The four-architecture comparison is a measured study with an explicit evidence boundary,
   including a negative verifier result.

The demo should not try to show every command, every schema or every failure mode. Pick one
ordinary case, one abstention case, one provenance moment and one results table.

## 2. Before the demo

### 2.1 Environment

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m incident_lens.cli validate-data
.venv\Scripts\python.exe -m incident_lens.cli list-cases
```

Do not use a real API key for the live demo. Mock is deterministic, offline and sufficient to
show the contract. If a real provider is used, keep `.env` off screen and never display the
key.

### 2.2 Pre-run and verify the two cases

Run these before the audience arrives, into fresh directories:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/demo-live
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_006 --provider mock --variant dynamic --cache-mode off --out results/demo-abs
```

Confirm the outcomes before relying on them:

- `results/demo-live/report.md` should present a resolved root cause with citations.
- `results/demo-abs/report.md` should be `INCONCLUSIVE` with no asserted root cause.

If `incident_006` does not abstain in your environment, inspect the report and choose another
known missing-evidence case. Do not claim an abstention path you have not verified.

### 2.3 Start the dashboard

```powershell
.venv\Scripts\python.exe -m incident_lens.cli web --port 8767
```

Open `http://127.0.0.1:8767` and check the health endpoint at
`http://127.0.0.1:8767/api/health`. Confirm the trace library sees the pre-run artifacts.

### 2.4 Checklist

- [ ] Virtual environment installed and `validate-data` passes.
- [ ] Live and abstention runs completed and inspected.
- [ ] Dashboard running on a known port.
- [ ] Browser at 100% zoom or larger; terminal font at least 16 pt.
- [ ] Notifications, chat, email and password managers closed.
- [ ] No `.env`, key, token or personal path visible in a terminal or browser tab.
- [ ] Tabs pre-opened: dashboard overview, trace library, `docs/EVALUATION.md`, and the
      saved hardened report.
- [ ] Backup terminal ready for CLI replay.
- [ ] Recording tested if the session is being recorded.

## 3. Timing plan

| Time | Segment | What is on screen | Key message |
| ---: | --- | --- | --- |
| 0:00-0:40 | Framing | Title and one-sentence contract | The problem is not writing a plausible story; it is deciding when a story is supported |
| 0:40-1:30 | Architecture | README architecture diagram or a slide | Specialists investigate; deterministic components accept |
| 1:30-2:20 | Live run | Terminal running `incident_001` with Mock | The system runs end to end offline and produces three artifacts |
| 2:20-4:10 | Run detail | Dashboard timeline and hypothesis board | Dynamic selection, tasks, merge and finalization are visible |
| 4:10-5:10 | Provenance | Evidence registry and a cited record | Every claim traces to an observed record |
| 5:10-6:10 | Abstention | `incident_006` report or replay | Missing evidence produces `INCONCLUSIVE`, not a guess |
| 6:10-7:00 | Replay | `Recorded Replay` of the saved trace | The demo is reproducible without the provider |
| 7:00-8:20 | Evaluation | `docs/EVALUATION.md` hardened table | 33/36 quality, 27/27 root correct, zero wrong causes, verifier cost |
| 8:20-9:20 | Limitations | Limitation bullets | Development-visible labels, one model, one repeat; over-abstention |
| 9:20-10:00 | Close | Contract and docs map | What exists, what is not claimed, where to inspect |

If the audience is technical, spend more time on provenance and gates. If it is mixed, keep
the architecture segment to one diagram and spend more time on the abstention contrast.

## 4. Segment notes

### 4.1 Framing (0:00-0:40)

Say:

- "IncidentLens investigates a synthetic software incident over logs, metrics, database
  observations and changes."
- "The contract is cited-or-abstain: every conclusion must cite records observed in this run,
  or the result is `INCONCLUSIVE`."
- "The interesting design question is not whether an LLM can write a root-cause paragraph.
  It is whether we can constrain when that paragraph is allowed to be accepted."

Do not open with benchmark numbers. Establish the contract first; the numbers later are
evidence about how it behaves.

### 4.2 Architecture (0:40-1:30)

Show the README diagram or one slide with the graph. Point to:

- coordinator selects one or two specialists per round;
- Merge is the only publisher of shared evidence;
- FinalizeGate is deterministic and reads no model confidence;
- the verifier variant is optional, not the primary architecture.

Say: "Dynamic is the default. The verifier is an ablation, and it did not pay for itself in
the measured batch. We report that."

Avoid walking every node. The audience needs the proposal/acceptance split, not a full graph
lecture.

### 4.3 Live run (1:30-2:20)

In the terminal, run a fresh directory so nothing is overwritten:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/demo-stage
```

While it runs, say:

- "Mock is deterministic over the public evidence. It is not a language model and it does not
  estimate real diagnostic accuracy."
- "The run writes `trace.json`, `result.json` and `report.md`."
- "The trace is what makes replay possible."

If the run takes longer than expected, do not debug on stage. Let it finish or switch to the
pre-run artifact and explain that the saved run is the same contract.

### 4.4 Run detail (2:20-4:10)

In the dashboard, open the completed `incident_001` run. The navigation is in Chinese; use
these labels and gloss them for the audience:

| UI label | English gloss | What to show |
| --- | --- | --- |
| 总览 | Overview | Case and run inventory |
| 新建调查 | New investigation | Mock provider choice |
| 痕迹档案库 | Trace library | Saved runs and replays |
| 运行详情 | Run detail | Timeline, hypotheses, evidence, findings, report |
| 调查时间线 | Investigation timeline | Coordinator, dispatch, merge, finalize events |
| 假设看板 | Hypothesis board | Candidate explanations and status |
| 证据登记 | Evidence registry | Observed records and citations |
| 调查发现 | Findings | Role findings after merge |
| 根因报告 | Root-cause report | Final status and citations |

Click path:

1. Open `运行详情`.
2. On `调查时间线`, point out the coordinator decision, the one or two specialist tasks, the
   merge event and the finalization event.
3. On `假设看板`, show that hypotheses accumulate on a concept and that conflicting
   assessments stay open rather than being silently overwritten.
4. Do not click every tab. The point is that the process is inspectable, not that the UI has
   many panels.

Say: "The agents propose. Merge publishes. FinalizeGate accepts. The timeline shows those as
separate steps, which is why we can audit a conclusion."

### 4.5 Evidence provenance (4:10-5:10)

Open `证据登记` and select a cited record. Show:

- the record ID used in the report;
- its source path and timestamp;
- the run and incident identity;
- the task or role that observed it.

Say: "The citation is not just a string in the report. The runtime ledger records that this
worker queried this record in this task. Merge validates that before publication."

Then add the honest boundary: "This proves the record was observed and is cited. It does not
prove by itself that the sentence is a semantically complete explanation. We do not claim a
human semantic-support evaluation."

This is the strongest technical moment of the demo. Do not rush it.

### 4.6 Abstention (5:10-6:10)

Open the pre-run `incident_006` result, either in the dashboard or by showing its
`report.md`. Confirm the status is `INCONCLUSIVE` and that no root cause is asserted.

Say:

- "Five of the forty public packs omit a discriminating record."
- "Here the system cannot satisfy the cross-source and mechanism checks, so it abstains."
- "In the hardened batch, no completed run named a wrong root cause. The dominant error was
  over-abstention: 19 identifiable cases ended inconclusive."
- "That is a real cost. We do not present abstention as free."

Do not say the system "refused to hallucinate" as a marketing line. State the measured
behaviour: no wrong causes in these batches, at the cost of missed diagnoses.

### 4.7 Recorded replay (6:10-7:00)

If the live run is healthy, you can still show replay as a reproducibility feature. From the
CLI:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli replay --trace results/demo-live/trace.json
```

Or open the trace library and select a run labelled `Recorded Replay`.

Say: "Replay loads the saved trace without calling the graph, tools or provider. That is why
the demo does not depend on the model staying available."

Do not present a replayed trace as a live execution. The UI label is deliberate.

### 4.8 Evaluation moment (7:00-8:20)

Show one results table, not all of them:

| Architecture | Quality success | Root correct | Avg latency | Avg tokens |
| --- | ---: | ---: | ---: | ---: |
| Single | 32/36 | 25/28 | 680.9 s | 245,971 |
| Fixed-4 | 22/36 | 15/27 | 196.3 s | 58,042 |
| **Dynamic** | **33/36** | **27/27** | 412.9 s | 149,216 |
| Dynamic (with verifier) | 30/36 | 23/27 | 503.8 s | 233,772 |

Say:

- "This is the hardened 36-case development batch, four architectures, 144 slots. 136
  completed; eight technical failures remain in the quality denominator."
- "Dynamic had 33/36 quality success and 27/27 root correctness. Fixed-4 was cheaper but
  wrongly abstained on 12 of 27 identifiable cases."
- "The verifier variant used 56.7% more tokens than Dynamic with no measured quality gain.
  That is a negative result for this ablation."

Then state the boundary before anyone asks:

- "These labels are provisional and development-visible. There is no blind test, one model,
  one repeat, no confidence interval and no significance test. These are descriptive
  differences, not proof of general superiority."

The bundled dashboard has an evaluation view at `#/evaluation`. It is a static snapshot of
the recorded hardened batch, hard-coded in `src/incident_lens/web/static/js/knowledge.js` and
labelled `RECORDED BATCH` — not a live feed. Confirm it matches the table above before
showing it, and pair it with `docs/EVALUATION.md` or the tracked hardened report for the full
denominators and boundaries.

### 4.9 Limitations and close (8:20-10:00)

Show four limitations, not a wall of text:

- synthetic corpus with provisional candidate labels and zero accepted annotations;
- one model, one repeat, no blind test and no significance test;
- over-abstention: 19 identifiable misses, all `INCONCLUSIVE`;
- auxiliary cache and recovery evidence is Mock-only; the guard result is replay-estimated.

Close with the contract and the documentation map:

- "Dynamic is the primary architecture; the verifier is an ablation."
- "The system either cites observed evidence and passes deterministic gates, or it abstains."
- "The evaluation is a development-visible comparison, not a production claim. The README,
  Run Guide, Architecture, Agent Design, Evaluation and Limitations documents give the full
  boundary."

## 5. Fallbacks

| Failure | Fallback |
| --- | --- |
| Live run is slow | Stop waiting; open the pre-run `results/demo-live` and say it is a saved run |
| Provider or network error | Switch to Mock; never debug credentials on stage |
| Dashboard will not start | Use CLI replay and open `report.md` in the editor |
| Case data missing | Run `validate-data` and `list-cases`; use a case that exists |
| No abstention case | Use `docs/EVALUATION.md` and explain the five missing-evidence packs, without showing an unverified report |
| Evaluation view will not render | Open `docs/EVALUATION.md` or the tracked hardened report |
| Time is short | Cut the architecture segment and the replay segment; keep provenance and abstention |

A recorded replay is the primary fallback because it requires no provider, no network and no
live model. Keep at least one saved trace with a resolved result and one with an abstention.
The repository also contains tracked acceptance traces you can use if your own pre-runs are
missing:

- `results/acceptance/demo001/trace.json` — Mock, `full`, `incident_001`, `RESOLVED`;
- `results/acceptance/demo006/trace.json` — Mock, `full`, `incident_006`, `INCONCLUSIVE`;
- `results/acceptance/baselines/dynamic_no_verifier/trace.json` — Mock, frozen dynamic alias,
  `incident_001`, `RESOLVED`.

Use these as recorded replays, not as live evidence, and check that they still match the
current tree before relying on them.

## 6. Recording checklist

If the group records a video:

- [ ] 16:9, 1080p or higher, 30 fps, cursor visible.
- [ ] Length between 8 and 10 minutes; hard stop before 10:00.
- [ ] Audio checked with a 10-second test; no clipping, fan noise or notification sounds.
- [ ] Terminal and browser fonts large enough to read on a laptop.
- [ ] No `.env`, API key, token, email, personal path or unrelated browser tab on screen.
- [ ] Every claim matches the current documentation, especially the 144-slot numbers and the
      evidence boundary.
- [ ] The abstention case is verified before recording; do not stage an unverified failure.
- [ ] Replay is labelled as replay; live execution is labelled as live.
- [ ] The video does not claim a blind test, accepted labels, production use or an executed
      remediation.
- [ ] File named consistently with the submission package; keep it out of the source archive
      unless the course instructions require it.
- [ ] Playback tested end to end after export.

A video is not required by this guide, and this repository does not contain one.
