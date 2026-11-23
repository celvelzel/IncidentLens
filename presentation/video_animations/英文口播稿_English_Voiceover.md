# IncidentLens — 10-Minute Course Presentation Video Script (English Voiceover + Heavy Live Demo)

> **Format**: 1080p / 16:9, Total Duration **10:00** (~1,380 spoken English words at a clear, comfortable ~138 wpm, leaving ample visual breathing room for live demos)  
> **Visual Mix**: **4 Live Hands-On Demos (~4 min 55 s)** + **4 ChatGPT HTML5/SVG Animations (~3 min 35 s)** + **Clean Summary / Architecture Slides (~1 min 30 s)**  
> **Color Palette**: PolyU Crimson (`#A02337`) + Slate Dark (`#0F172A`) + Emerald (`#10B981`, verified/resolved) + Amber (`#F59E0B`, abstention) + Red (`#EF4444`, blocked/error)

---

## Master Timeline

| Time | Segment | Visual Format | Core Message |
| --- | --- | --- | --- |
| **00:00–00:50** | 1. Opening Hook & Core Contract | **ChatGPT Animation #1** + Title Card | General LLM agents hallucinate RCA stories; IncidentLens enforces *Cite or Abstain* |
| **00:50–02:10** | 2. Architecture & Four Variants | **ChatGPT Animation #2** | LangGraph dynamic loop, role ACL isolation, deterministic `FinalizeGate`, and 4 benchmarked variants |
| **02:10–03:00** | 3. **Live Demo 1**: Data, ACL & Reliability | **Live Terminal Recording** | `validate-data`, `test_tool_acl.py` isolation proof, 505 unit tests & 110/110 reliability matrix |
| **03:00–04:30** | 4. **Live Demo 2**: Real Cross-Model CLI Run | **Live Terminal Recording** | Live run via OhMyGPT (`tencent/hy4-flash`, thinking disabled) + comparing `incident_4014` (`RESOLVED`) vs `incident_4018` (`INCONCLUSIVE`) |
| **04:30–06:20** | 5. **Live Demo 3**: Web Console Recorded Replay | **Live Browser Recording** (`127.0.0.1:8022`) | Interactive replay of evidence board, click-through citation audit, hypothesis convergence, ACL ledger, stop handshake & intentional abstention |
| **06:20–07:05** | 6. **Live Demo 4**: Audit Protocol & Real Bug Fix | **ChatGPT Animation #3** + **Live Terminal / Code** | Anti-leakage oracle receipt + how we caught and fixed the hidden `leading_review_consistency` bug (8/12 crashes → 0/144 format failures) |
| **07:05–08:55** | 7. Full-Scale & Cross-Model Results | **ChatGPT Animation #4** (Animated Charts) | DeepSeek 144-slot table + `hy4-flash` thinking ON vs OFF (why disabling CoT wins under wall-clock budgets) + `single` 0/5 collapse vs `dynamic` 5/6 + Verifier saving `incident_4035` |
| **08:55–09:35** | 8. Honest Limitations & Future Work | Clean 3-Column Slide | Gate-generator coupling behind 0% false resolution, support-set scoring, OOD logs & on-demand Verifier |
| **09:35–10:00** | 9. Closing Summary | Closing Card | Three core takeaways & thank you |

---

## Shot-by-Shot Script & English Voiceover

### Segment 1: Opening Hook & Core Contract (00:00–00:50)

- **[Visual 00:00–00:35]** Play **ChatGPT Animation #1**: Left side shows a generic LLM agent flooded with noisy alerts, instantly outputting a confident fabricated root cause with red flags (*Hallucinated Citation*, *No Access Boundary*, *Never Abstains*). Right side reveals **IncidentLens** with three glowing guarantees: *Evidence-Backed Citations*, *Read-Only Role ACLs*, and *Explicit Abstention (`INCONCLUSIVE`)*.
- **[Visual 00:35–00:50]** Clean title card: `IncidentLens: Evidence-Driven Multi-Agent Root Cause Analysis & Cross-Model Evaluation`.

> **[Voiceover]**  
> Hi everyone! Today I'm presenting **IncidentLens**, an evidence-driven multi-agent system for software incident root cause analysis.  
> In production postmortems, the most dangerous failure mode isn't failing to find an answer—it's **hallucinating a plausible story**. Generic LLM agents routinely assert confident root causes without valid citations, ignore data access boundaries, and almost never admit when evidence is missing.  
> IncidentLens enforces a much stricter engineering contract: **every claim must cite an actually observed evidence ID**, **every agent operates inside explicit read-only tool permissions**, and **when visible telemetry cannot uniquely identify the root cause, the system must abstain with `INCONCLUSIVE` rather than guess**.  
> Over the next nine minutes, I'll walk through the architecture, show you four live hands-on demos, and share our full-scale, cross-model experimental findings across DeepSeek and Tencent Hunyuan.

---

### Segment 2: Architecture & Four Benchmarked Variants (00:50–02:10)

- **[Visual 00:50–01:40]** Play **ChatGPT Animation #2 (Part 1)**: LangGraph closed loop: Public Incident Summary → `Coordinator` → dynamically dispatches 1–2 specialists (`Logs`, `Metrics`, `Database`, `Changes`, each carrying scoped tool keys) → central `Shared Evidence Board` → deterministic red shield `FinalizeGate` checking 4 rules (≥2 independent sources, cause-specific discriminator, temporally compatible cross-source impact, no unresolved contradiction/competitor) → loops back if gaps remain, or outputs `RESOLVED` / `INCONCLUSIVE`.
- **[Visual 01:40–02:10]** **ChatGPT Animation #2 (Part 2)**: Side-by-side cards of the 4 equivalent-tool architectures: `Single`, `Fixed-4`, `Dynamic` (primary ⭐), and `Full` (`Dynamic + LLM Verifier`).

> **[Voiceover]**  
> Let's look at how IncidentLens works under the hood. It runs as a centralized LangGraph workflow.  
> Starting from a public incident summary, the **Coordinator** inspects the current evidence gaps and remaining budget, then dynamically dispatches one or two specialists per round: **Logs** for error chronology, **Metrics** for capacity and dependencies, **Database** for locks, connections, and slow queries, and **Changes** for recent deployments and config diffs.  
> Two safeguards keep the workflow honest. First, **strict tool ACL isolation**—for example, the Logs agent can never query config diffs. Second, a **deterministic `FinalizeGate`**: final acceptance never relies on an LLM's self-reported confidence. Instead, deterministic code verifies at least two independent sources, a cause-specific discriminator, temporally compatible impact, and zero unresolved contradictions or rival mechanisms.  
> To evaluate whether dynamic multi-agent orchestration actually pays off, we compare four architectures under identical budgets and equivalent tool access: a **Single-agent** baseline, a one-shot **Fixed-4** batch, our primary **Dynamic** architecture, and **Full**, which adds an independent LLM **Verifier** loop.

---

### Segment 3: Live Demo 1 — Data Validation, Permission Isolation & Reliability Suite (02:10–03:00)

- **[Visual — Live Terminal Recording]** (Font 16pt+, dark theme, repo root):
  1. Run `.venv/bin/python -m incident_lens.cli validate-data` → show `"ok": true`.
  2. Run `.venv/bin/pytest tests/isolation/test_tool_acl.py -v` → highlight logs→config denied & immutable `AgentContext` passing.
  3. Run `.venv/bin/pytest tests/unit tests/evaluation tests/reliability tests/isolation -q` (can speed up 2x during dots, pause 2s on `505 passed, 1 skipped`).
  4. Flash output of `run_reliability_eval.py`: `{"cases": 110, "matrix_passed": 110, "matrix_total": 110}`.

> **[Voiceover]**  
> Let's jump straight into our live demonstrations.  
> First, in the terminal, I run `validate-data` to verify that public evidence files follow the strict schema with zero leaked private answer fields.  
> Next, let's verify our security boundary with the isolation test suite. Notice how attempts by a specialist to escalate permissions or call an unauthorized tool—like Logs trying to inspect config diffs—are deterministically blocked at runtime.  
> Running our broader offline regression suite confirms **505 tests passing**, alongside our **110-case provider fault-injection matrix**, which verifies bounded transport retries, atomic request permits, and structured output recovery.

---

### Segment 4: Live Demo 2 — Real Cross-Model Investigation on Terminal (03:00–04:30)

- **[Visual — Live Terminal Recording]** (Split screen or sequential clean runs):
  1. **Live CLI Run with OhMyGPT (`tencent/hy4-flash`, thinking disabled)** (run live or pre-recorded with 2x speed during waiting, pausing on command + final report):
     ```bash
     .venv/bin/python -m incident_lens.cli run \
       --case incident_001 --provider ohmygpt \
       --response-format json_schema --thinking disabled \
       --variant dynamic --out results/demo_video_hy4
     ```
     Show it finish cleanly and open `results/demo_video_hy4/report.md` (highlight `status: RESOLVED`, exact `culprit_service`, `failure_mode`, and real `supporting_evidence_ids`).
  2. **Show real Hardened Dev36 `deepseek-flash` outcomes side by side** (print formatted summary from `results/repro-deepseek-flash-hardened144/states/`):
     - **`incident_4014` (`misleading` lever)**: point out the decoy change placed on the culprit service itself, and show `dynamic` ignoring the decoy and resolving `postgres_lock_contention` in 47s.
     - **`incident_4018` (`missing` lever)**: show `dynamic` executing 12 tool calls across sources, finding no discriminator, and cleanly exiting with `status: INCONCLUSIVE` rather than fabricating a cause.

> **[Voiceover]**  
> Now let's run an actual live investigation—not a mock. Here I invoke the CLI using our newly integrated **OhMyGPT provider** backed by the official OpenAI SDK, calling **Tencent `hy4-flash`** with `json_schema` mode and thinking disabled, under the `dynamic` architecture.  
> *(Let it complete / cut cleanly to `report.md`)*  
> In under a minute, the system finishes cleanly and writes `result.json`, `report.md`, and `trace.json`. Looking at `report.md`, you can see the confirmed culprit service, failure mode, causal chain, and every supporting evidence ID bound directly to actual tool queries.  
> Next, let's look at two hardened benchmark cases we ran on official **DeepSeek `deepseek-flash`**.  
> On **`incident_4014`**, a misleading case where a non-causal change is deliberately injected onto the culprit's own service, `dynamic` doesn't take the bait—it cross-checks database lock waits and logs, and nails `postgres_lock_contention` in 47 seconds.  
> By contrast, on **`incident_4018`**, the critical slow-query discriminator is missing by design. After checking 12 tools across sources, the system refuses to guess and terminates cleanly with **`INCONCLUSIVE`**.

---

### Segment 5: Live Demo 3 — Web Console Recorded Replay (04:30–06:20)

- **[Visual — Live Browser Screen Recording]** (`http://127.0.0.1:8022` launched via `.venv/bin/python -m incident_lens.cli web --port 8022`, browser zoom 115%):
  1. Show the dashboard & **Trace Archive**, explicitly hovering over the **"Recorded Replay — no provider calls"** badge.
  2. **Trace 1 (Resolved Case — e.g., `demo_video_hy4` or `incident_001` / `incident_4014`)**:
     - Click through the **Investigation Timeline**: highlight `DECISION` → `TASK_ASSIGNED` → `TOOL_CALL` → `MERGE` → `DIAGNOSIS_ACCEPTED`.
     - Open the **Hypothesis Board**: show competing hypotheses created, evidence attached (`support_ids` / `against_ids`), and how one candidate wins cleanly.
     - Click a **Citation ID** in the final report: jump directly to the raw observed record in the Evidence Explorer.
     - Scroll to **Stop Protocol & Resource Ledger**: highlight `WORKFLOW_STOP_REQUESTED` → `STOP_ACK` → `NORMAL_TERMINATION`, plus exact HTTP request count, tool count, and token usage.
  3. **Trace 2 (Abstained Case — e.g., `incident_006` or `incident_4018`)**:
     - Switch to the abstained trace in the archive, showing `status: INCONCLUSIVE`, `root_cause: null`, explicit causal gaps, and clean `NORMAL_TERMINATION` (distinct from `RUNTIME_FAILURE`).

> **[Voiceover]**  
> To make every investigation inspectable by human engineers, IncidentLens ships with a local **Web Console**. Here I open the Trace Archive at `localhost:8022`. Notice the banner at the top: **Recorded Replay—zero provider calls**. Every view you're about to see is reconstructed purely from the persisted `trace.json`.  
> Let's inspect a resolved run first. In the timeline panel, we can step through every decision the Coordinator made, which specialist it dispatched, and what exact records came back.  
> Switching to the hypothesis view, you can watch rival explanations compete as new evidence arrives, until only one satisfies `FinalizeGate`.  
> Clicking any citation in the final report traces straight back to the underlying observed log, metric, or config diff—so reviewers can verify grounding in seconds.  
> At the bottom, the audit ledger records the formal two-phase stop handshake—`WORKFLOW_STOP_REQUESTED`, `STOP_ACK`, and `NORMAL_TERMINATION`—alongside exact physical HTTP requests and token counts.  
> Now let's switch to an abstained case. Instead of crashing or guessing, the UI clearly shows `INCONCLUSIVE`, explains which evidence gaps remain open, and distinguishes normal abstention from a runtime error.

---

### Segment 6: Live Demo 4 — Anti-Leakage Evaluation & Real-World Bug Fix (06:20–07:05)

- **[Visual 06:20–06:42]** Play **ChatGPT Animation #3**: Shows the physical wall between `public/` and `local_oracles/`, SHA-256 `Completion Receipt` unlocking offline scoring, and technical failures remaining in the denominator (*Failure-Inclusive*).
- **[Visual 06:42–07:05]** **Live Terminal / Editor Quick Cut**:
  - Highlight the 10-line fix in `src/incident_lens/llm/structured_output.py` (`_SAFE_TYPES` + `_SAFE_REPAIR_HINTS` for `leading_review_consistency` & `task_tool_acl`).
  - Run `.venv/bin/pytest tests/unit/test_structured_output_v13.py -k leading_review -v` → green `PASSED` in 0.1s!
  - Show before/after stat callout: `Single & Full verify crashes: 8/12 → 0/144`.

> **[Voiceover]**  
> Evaluating an agent rigorously is just as hard as building it. IncidentBench physically separates public evidence from private evaluator oracles; labels are only unlocked after a run persists its state and generates a matching SHA-256 completion receipt, and every technical failure stays in the denominator.  
> When we moved our project onto the official DeepSeek API for full-scale testing, we uncovered a critical latent bug: **`Single` and `Full` crashed on 8 out of 12 slots** during verification!  
> Tracing the event logs revealed a subtle hidden bug: `ReviewOutput` enforces a cross-field rule called `leading_review_consistency`, but `structured_output.py` stripped that custom error code into a generic `$: validation_error`, leaving the model completely blind during its one repair attempt.  
> After whitelisting the safe error code, passing an explicit static repair hint, and documenting the invariant in the verifier prompt—verified by this new unit test—**all 9 previously crashed slots recovered 9 out of 9**, and across our subsequent **144-slot full run**, structured output crashes dropped to **literally zero**.

---

### Segment 7: Full-Scale & Cross-Model Experimental Results (07:05–08:55)

- **[Visual 07:05–07:50]** Play **ChatGPT Animation #4 (Scene 1)**: Animated bar chart + Pareto frontier scatter plot for **Official `deepseek-flash` Hardened Dev36 (144 slots = 36 cases × 4 variants)**:
  - **`Dynamic` (⭐ Primary)**: **31/36 (86.1%)** · 113.6k tokens · 56.4s (beats `Single` +6/−3, −42.6% tokens; beats `Full` +6/−2, −39.5% tokens; beats `Fixed-4` +18/−0!)
  - `Single`: 28/36 (77.8%) · 198.0k tokens · 76.5s
  - `Full`: 27/36 (75.0%) · 187.8k tokens · 67.0s (notably **5/6** on `counterfactual_pair`!)
  - `Fixed-4`: 13/36 (36.1%) · 36.5k tokens · 17.3s (23 false abstentions on 29 identifiable cases)
  - Floating badge: **`0 False Resolutions across 137 completed runs`**.
- **[Visual 07:50–08:55]** Play **ChatGPT Animation #4 (Scenes 2 & 3)**:
  - **Scene 2 — `tencent/hy4-flash` Thinking ON vs OFF (24 slots)**: Wall time `48.0 min → 12.6 min` (**3.8× faster**), Technical completion `45.8% → 95.8%` (six 900s timeouts → **0 timeouts**), Quality `7/24 → 13/24`.
  - **Scene 3 — Cross-Model Capability Amplification (`hy4-flash`, thinking disabled)**:
    - `Single`: **1/6 (16.7%)** — **0/5 on identifiable cases**, burning 254k tokens / 174s!
    - `Fixed-4`: **3/6 (50.0%)** · 40k tokens · 28s
    - **`Dynamic` (⭐)**: **5/6 (83.3%)** · **124k tokens (−51%)** · **86s (−51%)**
    - `Full`: **4/6 (66.7%)** · 264k tokens · 146s — **again rescuing `incident_4035` (`counterfactual_pair`)**, replicating the exact same pattern seen on DeepSeek!

> **[Voiceover]**  
> Now let's look at the numbers from our full-scale experiments.  
> On the 36-case hardened benchmark with official **`deepseek-flash`**—144 slots across six difficulty levers—**`Dynamic` finishes first across the board**: **86.1% quality success** (31 out of 36), cutting tokens by **42.6% compared to `Single`** and **39.5% compared to `Full`**, while beating `Fixed-4` 18 to 0 in paired comparisons. Even more remarkably, across all 137 completed runs, there were **zero false resolutions**—whenever the system emitted `RESOLVED`, it was 100% right.  
> To test whether these findings generalize beyond DeepSeek, we ran the same six-lever benchmark on **Tencent `hy4-flash`** via OhMyGPT, both with chain-of-thought thinking enabled and disabled.  
> Here we uncovered a counterintuitive result: **disabling thinking nearly doubled end-to-end success**, cutting runtime from 48 minutes down to 12.6 minutes and lifting completion from 45.8% to **95.8%**. Why? Because multi-agent RCA is a **serial tool-exploration loop**, not a single-shot math puzzle. With thinking enabled, each call took 40 to 70 seconds, causing `Single` and `Full` to exhaust the 900-second wall-clock budget mid-investigation. Disabling thinking let the workflow trade slow internal monologues for fast, iterative evidence gathering—guided externally by `FinalizeGate`.  
> And look at the starkest finding of the entire project: on non-thinking `hy4-flash`, the **monolithic `Single` agent collapsed to 0 out of 5 on identifiable cases**, burning 254,000 tokens per run. Yet **`Dynamic` multi-agent specialization rescued accuracy from 16.7% all the way to 83.3%, while cutting both tokens and latency in half**!  
> Finally, across *both* DeepSeek and `hy4-flash`, the one case `Dynamic` missed—counterfactual pair **`incident_4035`**—was successfully rescued by **`Full`** thanks to the Verifier's targeted follow-up checks.

---

### Segment 8: Honest Limitations & Improvement Roadmap (08:55–09:35)

- **[Visual — Clean 3-Column Reflection Slide]**
  1. **Validity Boundary**: Why *0% false resolution* happens → `FinalizeGate` shares deterministic mechanism rules with the 7 synthetic scenarios; human semantic review is still pending.
  2. **Evaluation Upgrades**: Score against oracle `acceptable_support_sets` automatically; fix `NOT_APPLICABLE` handling in `scorer.py` and re-center `statistics.py` bootstrap on `dynamic`; add OOD unstructured real logs.
  3. **Architecture Next Step**: **On-Demand Verifier (`dynamic_review`)** — stay on cheap `Dynamic` by default, invoke Verifier only when competing/counterfactual ambiguity signals fire.

> **[Voiceover]**  
> To keep our evaluation scientifically honest, we also have to highlight three clear limitations.  
> First, achieving zero false resolutions across both model families owes a great deal to the tight coupling between `FinalizeGate`'s seven hardcoded mechanism rules and our synthetic benchmark scenarios. Testing on out-of-distribution, unstructured production logs is essential to measure true hallucination resistance when hard rules weaken.  
> Second, our automatic scorer currently checks culprit service and failure mode match, even though the oracle already defines acceptable evidence support sets—incorporating support-set coverage and re-centering paired bootstrap statistics onto `Dynamic` are immediate, high-leverage upgrades.  
> Third, our cross-model finding on `incident_4035` points directly to an **on-demand Verifier**: keep `Dynamic` as the fast, economical default, and trigger an independent Verifier only when competing-mechanism or counterfactual signals appear.

---

### Segment 9: Closing Summary (09:35–10:00)

- **[Visual — Clean Closing Card]** Three crisp icon bullets + GitHub repo name (`IncidentLens`) + Thank You.

> **[Voiceover]**  
> To wrap up: IncidentLens demonstrates that combining **scoped multi-agent specialization**, **deterministic grounding gates**, and **failure-inclusive cross-model evaluation** delivers zero-fabrication root cause analysis—not only saving 40% to 50% in tokens on strong models, but dramatically amplifying diagnostic capability on lighter, non-thinking models.  
> Thank you so much for watching, and I'd be happy to take any questions!

---

## Appendix A: Exact Live Demo Commands Checklist

Run from `/Users/songxiaowen/.gemini/antigravity/scratch/IncidentLens`:

```bash
# --- LIVE DEMO 1 (02:10–03:00): Data, Isolation & Reliability ---
.venv/bin/python -m incident_lens.cli validate-data
.venv/bin/pytest tests/isolation/test_tool_acl.py -v
.venv/bin/pytest tests/unit tests/evaluation tests/reliability tests/isolation -q
cat results/offline-reliability-eval/summary.json | head -n 25

# --- LIVE DEMO 2 (03:00–04:30): Real Cross-Model CLI Investigation ---
# Live OhMyGPT hy4-flash (thinking disabled) run:
.venv/bin/python -m incident_lens.cli run \
  --case incident_001 --provider ohmygpt \
  --response-format json_schema --thinking disabled \
  --variant dynamic --out results/demo_video_hy4
cat results/demo_video_hy4/report.md

# Quick side-by-side printout of hardened DeepSeek incident_4014 (RESOLVED) vs incident_4018 (INCONCLUSIVE):
.venv/bin/python -c "
import json
from pathlib import Path
for cid in ('incident_4014', 'incident_4018'):
    st = json.loads(Path(f'results/repro-deepseek-flash-hardened144/states/{cid}.dynamic.json').read_text())
    r = st['report']
    print(f'=== {cid} (dynamic / deepseek-flash) ===')
    print('Status:', r['status'], '| Stop:', r['stop_reason'], '| Tools:', st['tool_calls_used'])
    print('Root Cause:', r.get('root_cause'))
    print('Citations:', r.get('supporting_evidence_ids'))
"

# --- LIVE DEMO 3 (04:30–06:20): Web Console Recorded Replay ---
# Optional: generate one offline abstained trace (incident_006) so both RESOLVED and INCONCLUSIVE are in the archive:
.venv/bin/python -m incident_lens.cli run \
  --case incident_006 --provider mock --cache-mode off \
  --variant dynamic --out results/demo_video_abstain
# Launch Web UI (open http://127.0.0.1:8022 at 115% browser zoom):
.venv/bin/python -m incident_lens.cli web --port 8022

# --- LIVE DEMO 4 (06:20–07:05): Regression Test for Bug Fix ---
.venv/bin/pytest tests/unit/test_structured_output_v13.py -k leading_review -v
```

---

## Appendix B: 4 Ready-to-Paste ChatGPT Animation Prompts (English On-Screen Text)

> **Recording Tip**: Paste each prompt into ChatGPT to generate a **single-file HTML5/SVG/JS animation** (`1920×1080`), open it full-screen in Chrome/Safari, and record with macOS `Shift + Command + 5` for razor-sharp 60fps vector motion graphics with zero AI-video text garbling.

### ChatGPT Animation Prompt #1: Opening Hook — Generic Agent vs IncidentLens (35s)

```text
Create a single-file, self-contained HTML5/SVG/CSS/JS presentation animation (1920x1080 responsive, dark slate background #0F172A, accent colors: crimson #A02337, emerald #10B981, amber #F59E0B, red #EF4444). Include a minimal bottom bar with Play/Pause/Replay and Spacebar toggle. Total auto-play duration: 35 seconds. All on-screen text must be crisp, large English sans-serif (Inter/Arial).

Storyboard:
1. [0-12s] Left card "Generic LLM Agent": noisy alert stream (Gateway 504, DB Timeout, Redis Spike) flows in. Agent immediately outputs a confident fake box: "Root Cause: Primary DB Crash". A red verification scanner sweeps over it and pops up 3 red warning badges: "Fabricated Citation ID", "Unbounded Data Access", "Never Abstains".
2. [12-26s] Smooth transition to Right card "IncidentLens (Evidence-Driven Multi-Agent)": three glowing contract pills animate in sequentially:
   - [Emerald] Cite Observed Evidence Only (Verified Tool Record IDs)
   - [Cyan] Read-Only Role ACL Isolation
   - [Amber] Abstain Explicitly (INCONCLUSIVE when evidence is missing)
3. [26-35s] Side-by-side hold with centered clean title banner: "IncidentLens: Evidence-Driven Multi-Agent Root Cause Analysis".
```

### ChatGPT Animation Prompt #2: Dynamic Architecture & Four Variants (60s)

```text
Create a single-file HTML5/SVG/JS vector animation (1920x1080, dark slate #0F172A, crimson #A02337 highlight, Play/Pause/Replay bar, 60s total, English labels).

Part 1 [0-38s] — Dynamic Closed-Loop Investigation:
- Top node "Public Incident Summary" pulses into "Coordinator".
- Round 1: Coordinator dynamically activates 2 specialist cards with scoped key icons: "Logs (query_logs)" and "Database (locks/connections)", while "Metrics" and "Changes" stay dimmed/idle.
- Glowing evidence packets labeled E-003, E-007 flow into the central "Shared Evidence Board".
- Packet stream enters a bold crimson shield "FinalizeGate (Deterministic)" with 4 animated checkboxes:
  [✓] >= 2 Independent Sources  [✓] Cause-Specific Discriminator  [✓] Temporal Compatibility  [✓] No Unresolved Rival / Contradiction
- Round 1 shows one checkbox amber -> loop returns to Coordinator -> activates "Changes (config_diff)" -> Round 2 passes all 4 green -> outputs "RESOLVED (Grounded Report)".

Part 2 [38-60s] — Four Benchmarked Architectures (4 side-by-side cards):
1. Single: 1 monolithic node tangled with all 4 tool pools.
2. Fixed-4: 4 specialists fire once in parallel, no retry loop ("Cheapest, High False Abstention").
3. Dynamic (PRIMARY ⭐ glowing crimson border): Adaptive 1-2 specialist dispatch + deterministic FinalizeGate.
4. Full (Dynamic + Verifier): Same loop plus an extra purple "Independent LLM Verifier" review node.
```

### ChatGPT Animation Prompt #3: Anti-Leakage Protocol & Hidden Bug Fix (25s)

```text
Create a single-file HTML5/SVG/JS animation (1920x1080, dark slate #0F172A, 25s total, English text, Play/Pause/Replay).

Scene 1 [0-12s] — Anti-Leakage Evaluation:
- Left box "Runtime Sandbox (public/ only)" separated by a glowing barrier "Zero Runtime Access" from Right locked vault "local_oracles/ (Private Ground Truth)".
- Investigation finishes -> persists state.json -> mints a green "SHA-256 Completion Receipt" -> unlocks vault offline -> Evaluator scores run while keeping red "Technical Failures" inside the denominator ("Failure-Inclusive Scoring").

Scene 2 [12-25s] — Hidden Bug Discovery & Fix:
- Split comparison:
  - BEFORE (Red): ReviewOutput raises `leading_review_consistency` -> silenced to `$: validation_error` -> blind repair fails -> 8/12 Single & Full slots crash!
  - AFTER (Emerald): Safe error whitelisted + explicit static repair hint + prompt invariant -> 9/9 crashed slots recover -> 0/144 format crashes on full DeepSeek run!
```

### ChatGPT Animation Prompt #4: Full 144-Slot & Cross-Model Data Visualizations (95s)

```text
Create a single-file HTML5 + SVG animated data dashboard (1920x1080, dark executive research theme #0F172A, PolyU crimson #A02337 for Dynamic, 95s total with keyboard shortcuts 1/2/3 to jump scenes + auto-play, English labels). Use ONLY these exact real experimental numbers:

Scene 1 [0-35s] — Official DeepSeek `deepseek-flash` Hardened Dev36 (144 Slots):
- Animated grouped bar chart + Token-vs-Quality Pareto scatter plot:
  - Dynamic (Primary ⭐): 31/36 (86.1%), 113,645 avg tokens, 56.4s
  - Single: 28/36 (77.8%), 197,986 avg tokens, 76.5s
  - Full (+Verifier): 27/36 (75.0%), 187,781 avg tokens, 67.0s
  - Fixed-4: 13/36 (36.1%), 36,478 avg tokens, 17.3s
- Pop-up callout badges: "0 False Resolutions (0/137)", "-42.6% Tokens vs Single", "-39.5% Tokens vs Full", "Dynamic vs Fixed-4: +18 / -0 paired".

Scene 2 [35-60s] — Tencent `hy4-flash` Thinking ON vs OFF (24 Slots):
- Side-by-side animated gauge & bar transition:
  - Thinking ON (default CoT): 48.0 min wall time | 11/24 (45.8%) completion | 6 wall-clock timeouts (900s) | 7/24 quality
  - Thinking OFF (`thinking: disabled`): 12.6 min wall time (3.8x faster) | 23/24 (95.8%) completion | 0 timeouts | 13/24 quality
- Subtitle note: "Serial multi-round tool loops benefit more from fast exploration than slow per-step CoT."

Scene 3 [60-95s] — Cross-Model Capability Amplification (`hy4-flash`, Thinking OFF):
- Animated bars comparing the 4 variants on 6 representative hardened cases:
  - Single: 1/6 (16.7% — 0/5 on identifiable cases!) | 254k tokens | 174s
  - Fixed-4: 3/6 (50.0%) | 40k tokens | 28s
  - Dynamic (⭐ pulsing highlight): 5/6 (83.3%) | 124k tokens (-51%) | 86s (-51%)
  - Full: 4/6 (66.7%) | 264k tokens | 146s
- Bottom insight callout: "Cross-Model Discovery: On BOTH DeepSeek & hy4-flash, counterfactual case incident_4035 was missed by Dynamic and rescued by Full (Verifier) -> Motivation for On-Demand Verifier."
```
