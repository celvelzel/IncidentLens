# Replay Orchestration — UX/UI Redesign Spec (`#replay-workflow`)

> **Task:** `t2` · Orchestration UX spec — staged workflow view for the replay demo
> **Branch:** `ui/ux-redesign-2026-11` (PR #6) · **Presentation layer only**
> **Target module:** `src/incident_lens/web/static/js/replay-panels.js` → `#replay-workflow`
> **New pure module:** `src/incident_lens/web/static/js/orchestration.js`
> **Status:** implemented, verified (2 rounds), reviewed and integrated on PR #6 — see
> [§13 Implementation notes & before/after index](#13-implementation-notes--beforeafter-index).

This document is the single source of truth for the rework of the replay-demo
"agent orchestration & workflow" panel. It is written to be implemented as-is:
information architecture, deterministic trace→view mapping, view-model builder
contracts, CSS class contract, JS export contract, accessibility/interaction/
responsive rules, wireframes, and a P0/P1/P2 build order.

Everything here is derived from the **BEFORE** evidence captured in `t1`:

- Data audit → [`results/ui-redesign/orchestration/data-audit.md`](../../results/ui-redesign/orchestration/data-audit.md)
- DOM/test-hook inventory → [`results/ui-redesign/orchestration/hooks.md`](../../results/ui-redesign/orchestration/hooks.md)
- BEFORE screenshots → [`results/ui-redesign/orchestration/before/`](../../results/ui-redesign/orchestration/before/index.md)
  and [`results/ui-redesign/replay-audit/`](../../results/ui-redesign/replay-audit/)
- Existing code: `replay-panels.js` (`workflowHtml`, `roleDetail`, `reviewTimelineHtml`),
  `views.js` (`mountReplay` ~L591, `drawRun` ~L674), `replay.js` (`replayReducer`,
  `replayWorkflow`, `evidenceContext`, `replayBookmarks`), `app.css` `.replay-*` (~L1171–1380).

---

## 0. TL;DR

Today `#replay-workflow` is a **status list + raw JSON**:

- a one-line legend `Coordinator → 专家任务 → Public Evidence …`,
- a wrapping row of role buttons (`.replay-role`) showing only a status token,
- a flat 2-column grid of "Coordinator → Role / task_id / question" cards (`.replay-dataflow`),
- and, on click, a `.replay-role-detail` that dumps `task_records` and dispatch objects as
  `<pre class="json-block">` (see BEFORE: `rich-verifier-detail.png`, `rich-workflow-last.png`).

It never reads as an *orchestration*: there is no stage progress, no per-round fan-out,
no per-role statistics, no verifier gate, no evidence flow, and no narrative.

This spec replaces the panel with six coordinated views inside the **same**
`#replay-workflow` container:

1. **Stage stepper** — `协调者 → 专家(并行) → 合并证据 → 假设 → 验证审查 → 定案门 → 报告`
   with per-stage count badges and a CURRENT-stage highlight that advances with replay position.
2. **Per-round dispatch swimlane** — Coordinator fan-out to expert task cards grouped by
   investigation round, parallel tasks side-by-side, merge into evidence, verifier gate with
   loop-back to re-dispatch.
3. **Per-role stats + structured drilldown** — dispatches / completed / failed / tool calls /
   evidence produced / findings / duration, with scannable task rows (**no raw `<pre>` JSON**).
4. **Verifier REVIEW-GATE node** — each REVIEW verdict, target hypothesis, cited evidence,
   requested/optional check status, contradictions; the finalize gate honestly reports
   `已定案 / 未触发阻断` (there is no `FINALIZE_REJECTED` in either demo trace).
5. **Evidence-flow view** — `agent → evidence(chips) → finding / hypothesis → report reference`.
6. **Demo-narrative mode** — chaptered narration (one line each) with prev/next key-node control
   that seeks, auto-expands, scrolls and highlights the relevant stage.

The panel moves **directly under the replay controls, open by default**, so orchestration is the
hero of the replay demo. Metadata sinks to a collapsed block at the bottom.

---

## 1. Goals, non-goals, hard invariants

### Goals

- Make the replay read as a real multi-agent orchestration: parallel dispatch, evidence merge,
  hypothesis reconciliation, verifier review gate, finalize gate, report.
- Preserve the product's honesty: every displayed value comes from the **replay prefix**; absent
  data says so; nothing is fabricated (`optional_checks` empty → "未记录可选检查";
  no `FINALIZE_REJECTED` → no fake "blocked" node).
- Degrade gracefully across **both** showcase traces (RICH with verifier, SIMPLE without).
- Retain every CI hook, selector, `data-*` attribute and asserted string.

### Non-goals

- No backend / API / data-structure / route / permission change. No business-logic change.
- No new dependency, framework, build step, webfont, or network request.
- No change to replay playback semantics, `replay.js` reducer, or `api.js`.
- No removal of any existing user flow or tab.

### Hard invariants (must not violate)

**Do NOT edit these files at all:**

`replay.js`, `api.js`, `app.js`, `components.js`, `server.py`,
`tokens.css`, `core.css`, `institutional.css`, `index.html`, `tests/**`.

**Allowed to edit / create (presentation only):**

- `src/incident_lens/web/static/js/orchestration.js` **(new pure module)**;
- `src/incident_lens/web/static/js/replay-panels.js` (`workflowHtml` internals, `roleDetail`,
  helper renderers — exported names & asserted strings preserved);
- `src/incident_lens/web/static/js/views.js` **only** the `mountReplay` template order / `draw()`
  wiring — no routing, data-loading, or state-reducer change;
- `src/incident_lens/web/static/css/app.css` (append `.orch-*` block + small `.replay-*` overrides).

**Preserve every CI test hook** (full matrix in §9):

- `tests/web/browser.cjs`: `.replay-controls button`, `[data-step]`, `#replay-position`,
  `#replay-play`, `#replay-seek`, `#run-tab-panel`, `[data-ev]`, `#drawer*`; mobile 390
  `scrollWidth <= innerWidth`.
- `tests/web/replay-demo.test.mjs`: imports `metadataHtml, workflowHtml, reviewTimelineHtml,
  historyHtml` from `replay-panels.js`; asserts `仅审查建议 · 未调度` in `workflowHtml`, and
  `未按此 task_id 调度` in `reviewTimelineHtml`; asserts metadata strings.
- `tests/web/replay.test.mjs`: pure `replay.js` contracts (untouched).
- `tests/integration/*`: no UI markup contract on the panel.
- `tests/web/browser-real.cjs` is **non-CI and already stale** (references missing `.hero-kicker`,
  see `hooks.md` §9). Keep `.replay-role`, `[data-role]`, `.replay-role-detail`, `#replay-reviews
  article` reachable as cheap insurance, but do not treat it as a blocker.

### Terminology (Chinese-first, small English gloss)

| Concept | UI label (Chinese-first + gloss) |
|---|---|
| Coordinator | 协调者 Coordinator |
| Logs expert | 日志调查员 Logs Agent |
| Metrics expert | 指标调查员 Metrics Agent |
| Database expert | 数据库调查员 Database Agent |
| Changes expert | 变更调查员 Changes Agent |
| Evidence merge | 合并证据 Public Evidence |
| Verifier / review | 验证审查 Verifier |
| Finalize gate | 定案门 FinalizeGate |
| Reporter | 报告者 Reporter |
| Findings | 调查发现 Findings |
| Hypotheses | 假设 Hypotheses |

Use the zh label as the primary text and a `<span class="orch-role-en">` (or `…__gloss`) in
`--text-2xs` / `--text-2` for the English gloss. Do **not** rename raw ids (`data-role="metrics"`
etc.) — only the visible copy changes.

---

## 2. Before → After rationale

**Before** (screenshots: `rich-workflow-last.png`, `rich-workflow-dispatch.png`,
`rich-verifier-detail.png`, `workflow-mobile.png`):

- The panel is a legend + five role pills + a flat two-column task grid. There is no ordering,
  no round grouping, no statistics, no gate, no flow, no narrative.
- Role drilldown dumps raw `JSON.stringify` into `<pre class="json-block">` — unreadable and not
  an orchestration view.
- On mobile the pills and cards stack but the mental model is still "list of stuff".
- The panel also sits *above* the metadata/heading and competes for attention, yet says little.

**After:**

- The **stage stepper** answers "where are we in the workflow?" at a glance and advances as you
  scrub the replay.
- The **swimlane** answers "who was dispatched, in which round, in parallel, and what came back?"
- **Role stats + structured rows** answer "what did each agent actually do?" without JSON.
- The **review gate** makes the verifier loop-back explicit — the demo's key discriminator.
- The **evidence flow** makes provenance legible: agent → evidence → finding/hypothesis → report.
- The **narrative** turns the replay into a 2–3 minute guided story.
- It is now the hero: placed directly under the controls, open, metadata below.

Restraint follows `.design-skills/BRIEF.md` (Operate mode): no gradients, no webfonts, no
emoji/glyph icons, no decorative choreography; 150–250 ms state-driven motion only; flat surfaces,
semantic state colours, `:focus-visible` rings, `prefers-reduced-motion`, 12–16 px radii,
tabular numerals for all counts/durations.

---

## 3. Information architecture & placement

### 3.1 Panel placement (in `mountReplay` template, `views.js`)

New order inside `<section class="card replay-console">`:

1. **Heading block** (badges + title + demo toggle + one-line intro) — rendered by
   `metadataHtml(data, { snapshot: false })`. *(Backward-compatible extension: `metadataHtml(data)`
   with no options keeps emitting the full block, including the metadata `<details>`; the tests
   keep passing.)*
2. `.replay-controls` (unchanged).
3. `.replay-seek` (unchanged).
4. **`<details open>` orchestration panel** — `<summary>编排视图 · 共享状态与工作流</summary>` +
   `<div id="replay-workflow" aria-label="Workflow Overview"></div>`. **Open by default.**
5. `#replay-chapters` (unchanged).
6. Communication Timeline (unchanged).
7. `#replay-selection` (unchanged).
8. `.replay-analysis-grid` (hypotheses + reviews + reliability, unchanged).
9. **Metadata snapshot** — rendered by `metadataHtml(data, { heading: false })`, collapsed.

Rationale: step 4 is directly under the play controls/seek bar; the heavy provenance block sinks to
the bottom. Keep ids identical so `views.js` `draw()` selectors still work (`#replay-demo`,
`#replay-metadata`, `#replay-workflow`, …). `#replay-demo` remains inside the top heading block.

### 3.2 Section order **inside** `#replay-workflow` (rendered by `workflowHtml`)

```
.orch-panel
├─ .orch-toolbar        # provider/round/budget chips + legend + (demo) narrative toggle
├─ .orch-stepper         # (a) stage stepper, one row desktop / vertical mobile
├─ .orch-narrative       # (f) narration line + prev/next (only when bookmarks supplied)
├─ .orch-swimlane        # (b) per-round dispatch swimlane
├─ .orch-role-grid       # (c) per-role stats cards (each card toggle = `.replay-role`)
│  └─ .orch-role-detail  #      structured drilldown for the selected role
├─ .orch-gates           # (d) verifier review-gate node (+ finalize status)
└─ .orch-flow            # (e) evidence flow
```

All sections are stacked, full-width, separated by `--sp-6`; headings use the existing
`.section-title` / `.type-title-3` scale. Each section is its own bordered/tinted surface at
`--radius-lg`; avoid card-in-card beyond one level (`.orch-task-card` inside a lane is one level).

### 3.3 Responsive summary

- **Desktop (≥ 1024):** stepper horizontal; swimlane grid of rounds; role cards 3-up; evidence
  flow 4 columns.
- **Tablet (768–1023):** stepper horizontal that wraps; role cards 2-up; evidence flow 2×2.
- **Mobile (≤ 680, verified at 390):** stepper **vertical**; swimlane single column (rounds stacked,
  parallel tasks stacked but annotated "并行"); role cards 1-up; evidence flow single column with
  directional arrow labels. No horizontal page overflow (see §10).

---

## 4. Data model & deterministic trace→view mapping

**Golden rule:** every builder consumes the **replay prefix state** returned by
`replayPrefix(trace, position)` (the same object `views.js` already builds in `draw()`), never the
final trace state. `bookmarks` (from `replayBookmarks(trace)`) is the only full-trace input allowed,
because chapter navigation is inherently absolute — but a chapter's "reached" flag is recomputed
from `state.events.length`. This preserves the "no final-state backfill" invariant.

### 4.1 Fields used (existing only)

| Source | Fields |
|---|---|
| Events | `event_id, event_type, role, task_id, timestamp, message, details.*` |
| `TASK_ASSIGNED` / `TASK_RUNNING` / `TASK_COMPLETED` / (`TASK_FAILED`) | `details.{task_id, attempt_id, attempt, status, error_code}` |
| `DECISION` | `details.decision.{action, reason, assignments[], hypothesis_updates[], selected_hypothesis_id, stop_reason}`; each assignment: `{task_id, role, question, allowed_tools[], filters, reason, expected_discriminator}` |
| `MERGE` / `HYPOTHESIS_RECONCILED` | `details.{findings[], hypotheses[] \| hypothesis_updates[]}` |
| `REVIEW` | `details.review.{verdict, target_hypothesis_id, contradictions[], requested_checks[], optional_checks[], cited_evidence_ids[], rationale}`; `details.{hypothesis_sha256, evidence_sha256}` |
| `FINALIZE_*` | `event_type === 'FINALIZE_REJECTED'` (absent in both demo traces; must be handled if a future trace adds it) |
| `DIAGNOSIS_ACCEPTED` | `details.{root_cause, supporting_evidence_ids[], degraded_call_ids[]}` |
| `REPORT` | `details.report.{status, root_cause, causal_chain[], supporting_evidence_ids[], rejected_hypotheses[], provisional_hypotheses?, provisional_observations?}` |
| `NORMAL_TERMINATION` / `WORKFLOW_STOP_REQUESTED` | `details.{reason, outcome, stop_completed, runtime_failure, failure_stage}` |
| `TOOL_CALL` | `role, task_id, details.tool_name, details.result.{ok, records[]}`; record: `{evidence_id, source_type, service, source_path, evidence_type, excerpt, metadata, observed_at, incident_id}` (reducer keeps only authorized records) |
| `state.task_records` | final-status snapshots, deduped by `attempt_id`: `{task_id, attempt_id, role, attempt, status, error_code}` |
| `state.findings` | `{finding_id, task_id, role, claim, evidence_ids[], relation, confidence_qualifier, followup_question}` |
| `state.hypotheses` | `{hypothesis_id, culprit_service, failure_mode, support_ids[], against_ids[], predicted_observations[], status, open_questions[]}` |
| `state.evidence_index` | `{evidence_id → record}` (authorized records in prefix) |
| `state.provenance` | `{evidence_id → {event_id, role, timestamp, task_id, call_id, tool, args, observations[]}}` (first observation; plus `findings/hypotheses/report_references` after `views.js` runs `evidenceContext`) |
| `state.round_index` | number of `DECISION.action === 'INVESTIGATE'` seen in prefix (cross-check) |
| `state.budgets` | `{max_rounds, max_tool_calls, max_llm_calls, max_wall_seconds, max_tokens}` |

> `state.roles` is `null` in raw traces; use `state.roles[role]` only as the reducer-derived
> prefix lifecycle token (it is set from `TASK_*` events). Never read `state.tasks`,
> `state.reviews`, `state.decisions` top-level arrays — they are final-state summaries.

### 4.2 Round derivation (deterministic)

```
round = 0
for position, e in events (1-based, in order):
    if e.event_type === 'DECISION' and e.details.decision.action === 'INVESTIGATE':
        round += 1
        for a in e.details.decision.assignments:
            emit TaskCard { round, ...a, decisionEventId: e.event_id, position }
    // FINALIZE decisions do NOT increment round (matches replayReducer L48)
```

- `round_index` reported by the reducer **equals** this derived `round` for every prefix;
  a builder MUST assert-in-dev (not throw) if they differ, and prefer the event-derived value.
- Only `INVESTIGATE` rounds appear in the swimlane. Coordinator-internal tasks (`coordinate-*`) are
  **never** in `DECISION.assignments`, so they never pollute the swimlane; they appear only in
  per-role stats.
- Key every task by `task_id` (+ `attempt_id` where present); **do not** assume contiguous numeric
  suffixes (`check-changes-2`, `check-changes-3` skip `-1`).

**Golden (both traces):** 3 investigation rounds, 4 dispatches (2 + 1 + 1):
R1 logs `check-logs-0` + metrics `check-metrics-0`; R2 changes `check-changes-2`;
R3 changes `check-changes-3`. FINALIZE is a separate non-round decision.

### 4.3 Task lifecycle pairing (for status, timestamp, duration)

For each `(task_id, attempt_id)` build a lifecycle record by scanning events in order:

```
key = task_id + '::' + (attempt_id || '')
lifecycle[key] = { role, task_id, attempt_id, attempt,
                   assignedAt, runningAt, completedAt, failedAt,
                   status: <latest TASK_* status>, errorCode }
```

- `status` = status of the last `TASK_*` event for the key (`ASSIGNED|RUNNING|COMPLETED|FAILED`).
- `durationMs` = `completedAt − assignedAt` when both exist, else `null`.
- Fall back to `state.task_records` only if no `TASK_*` events exist for a record (defensive).
- Lifecycle **counts** must come from events, not just `task_records` (which shows final status
  only). In the demo traces all attempts are 1 and all are `COMPLETED`.

**Golden RICH:** 11 task records — coordinator `coordinate-1..4`, logs `check-logs-0`,
metrics `check-metrics-0`, verifier `verify-1..3`, changes `check-changes-2..3`, all COMPLETED.
**SIMPLE:** 8 — same minus verifier.

### 4.4 Per-role statistics derivation

For each role in
`union(events.role, dispatch.role, review-request.role)`:

| Stat | Derivation |
|---|---|
| `dispatches` | count of `DECISION.assignments` with this role (from §4.2) |
| `tasksAssigned/Running/Completed/Failed` | count of lifecycle keys for the role whose latest `status` matches (from §4.3) |
| `toolCalls` | count of `TOOL_CALL` events with `e.role === role` |
| `evidenceProduced` | count of **unique** evidence ids whose **first** observation role === role (`state.provenance[id].role`, fallback scan of `TOOL_CALL.result.records`) — verifier re-fetches add **0** new ids |
| `findings` | count of `state.findings` with `role === role` |
| `durationMs` | Σ `(completedAt − assignedAt)` over the role's lifecycle keys |

**Golden RICH (full prefix):**

| role | disp | tasks | tools | evidence produced | findings | duration |
|---|---|---|---|---|---|---|
| coordinator | 0 | 4 | 0 | 0 | 0 | ~9 ms |
| logs | 1 | 1 | 1 | 6 | 1 | ~13 ms |
| metrics | 1 | 1 | 2 | 7 | 1 | ~18 ms |
| changes | 2 | 2 | 3 | 2 | 2 | ~19 ms |
| verifier | 0 | 3 | 3 | 0 | 0 | ~10 ms |

Durations are real from timestamps; format with `formatDuration(ms)` (these fixtures are
sub-second → `NN ms`). **SIMPLE** is identical minus verifier.

### 4.5 Evidence → finding → hypothesis → report links

```
evidence (state.evidence_index / provenance)
  → findings      : f.evidence_ids includes id            (state.findings)
  → hypothesis    : id ∈ h.support_ids  → relation 'supports'
                    id ∈ h.against_ids  → relation 'against'   (state.hypotheses)
  → report        : id ∈ report.supporting_evidence_ids      → supporting = true
                    id ∈ provisional_hypotheses[].support_ids | against_ids, or appears in
                    report.provisional_observations → provisional = true
                    causal_chain line containing `[id]` → causalChain.push(line)
```

This mirrors `evidenceContext(state)` (already exported by `replay.js`); builders may call it or
re-implement the same joins over `state`. **Golden:** 15 unique evidence records
(logs 6, metrics 7, changes 1, configs 1); report `supporting_evidence_ids = [C001, D001, M009]`;
`causal_chain` = 3 steps; findings: logs `supports` (6 ids), metrics `supports` (7),
changes `neutral` (C001), changes `supports` (D001, C001).

### 4.6 REVIEW → gate node + loop-back

For each `REVIEW` event (`details.review`):

- `verdict` ∈ `{insufficient, sufficient}` → tone `warning` / `success`; label
  `证据不足 Insufficient` / `证据充分 Sufficient`.
- `target_hypothesis_id` → join `state.hypotheses` for `failure_mode` / `culprit_service`
  (fallback: show raw id).
- `cited_evidence_ids` → evidence chips.
- `requested_checks[]` → blocking checks; `optional_checks[]` → optional checks (may be empty).
  For each check derive a **prefix status**:
  - `completed` if a `TASK_COMPLETED`/`state.task_records` entry with the same `task_id` is
    `COMPLETED` → `当前前缀：相同 task_id 已完成`;
  - `assigned` if a `DECISION.assignments` in the prefix contains `task_id` but no completion →
    `当前前缀：已调度，未见完成`;
  - else `not-dispatched` → `当前前缀：未按此 task_id 调度；不推断检查已完成`
    **(this exact string must survive in `reviewTimelineHtml`, and the same wording is used in the
    gate check rows for consistency).**
- `contradictions[]` → render explicitly (insufficient reviews have 1 each; sufficient has 0 →
  `无矛盾记录`).
- `hypothesis_sha256` / `evidence_sha256` → show as `<dd class="mono">` inside a `<details>`.
- **Loop-back edge:** if `verdict === 'insufficient'` and `requested_checks.length > 0`, find the
  **first round after this REVIEW position** whose assignments include a requested `task_id`; if
  found, `loopBack = { toRound, toPosition, taskIds }`, render an edge
  `验证审查 → 第 N 轮重新调度`. If not found, `loopBack = null`.
  *Golden RICH:* review@25 → round 2 @30 (`check-changes-2`); review@43 → round 3 @48
  (`check-changes-3`).

### 4.7 Finalize-gate status (honest, no fabricated block)

- `diagnosisAccepted` = any `DIAGNOSIS_ACCEPTED` in prefix.
- `blocked` = any `FINALIZE_REJECTED` event in prefix (none in either demo trace).
- `present` = `diagnosisAccepted || any FINALIZE decision`.
- Status text:
  - `blocked` → `已阻断 · FINALIZE_REJECTED` (tone `danger`);
  - else if `present` → `已定案 / 未触发阻断` (tone `neutral`/`success`);
  - else → `待定案` (tone `neutral`).
- Never render a "gate blocked" node from a REVIEW verdict alone; REVIEW `insufficient` is the
  gate signal, not a `FINALIZE_REJECTED`.

### 4.8 Stage derivation (CURRENT advances with replay position)

Stages (fixed order, `index` 0..6):

| id | label | gloss | badge count | reached when |
|---|---|---|---|---|
| `coordinator` | 协调者 | Coordinator | `#DECISION` count | any DECISION |
| `experts` | 专家(并行) | Experts · parallel | `#dispatch assignments` | any assignment **or** non-coordinator TASK_* |
| `evidence` | 合并证据 | Public Evidence | `#unique evidence ids` | any MERGE |
| `hypotheses` | 假设 | Hypotheses | `#state.hypotheses` | any MERGE / HYPOTHESIS_RECONCILED |
| `review` | 验证审查 | Verifier | `#REVIEW` | any REVIEW |
| `finalize` | 定案门 | FinalizeGate | `#DIAGNOSIS_ACCEPTED` (0/1) | DIAGNOSIS_ACCEPTED or FINALIZE decision |
| `report` | 报告 | Report | `#REPORT` (0/1) | any REPORT |

`currentStageId(state)` = walk events **backwards**, take the first event that maps to a stage:

```
REPORT                                        → report
NORMAL_TERMINATION / WORKFLOW_STOP_REQUESTED
  / DIAGNOSIS_ACCEPTED                        → finalize
DECISION(action=FINALIZE)                     → finalize
REVIEW                                        → review
MERGE / HYPOTHESIS_RECONCILED                 → hypotheses
TOOL_CALL                                     → experts
TASK_* (coordinator-internal task_id)         → coordinator
TASK_* (dispatched expert task)               → experts
DECISION(action=INVESTIGATE)                  → coordinator
LLM_CALL / MODEL_* / CACHE_* / other          → (skip, keep scanning)
(no meaningful event — step 0)                → coordinator (state "待开始")
```

Per-stage `state`:
`skipped` if `!available`; else `current` if `id === currentStageId`; else `done` if `reached`;
else `pending`. `review.available = resolveHasVerifier(state, opts)` — **variant-level, not
prefix-only** (§4.8.1); all other stages `available = true`.

#### 4.8.1 Verifier availability is variant-level (implemented rule)

Verifier presence must **not** be inferred from the replay prefix alone. At early positions a
verifier-capable trace has simply not reached its first `REVIEW` yet — that is *pending*, not
*"this variant has no verifier"*. The recorded trace variant is the authoritative capability
signal; the prefix is only corroborating evidence:

```js
// orchestration.js — implemented, exported
const VERIFIER_VARIANTS = {
  full: true, single: false, fixed: false,
  dynamic_no_verifier: false, no_verifier: false,
};
export function variantVerifierCapability(variant) {   // true | false | null (unknown)
  if (variant == null || variant === '') return null;
  return Object.hasOwn(VERIFIER_VARIANTS, variant) ? VERIFIER_VARIANTS[variant] : null;
}
export function prefixHasVerifier(state) {             // any REVIEW or verifier-role event
  return (state.events || []).some(e => e.event_type === 'REVIEW' || e.role === 'verifier');
}
export function resolveHasVerifier(state, opts = {}) { // opts.variant = trace.variant
  if (prefixHasVerifier(state)) return true;           // real prefix REVIEW/verifier overrides variant-no
  const capability = variantVerifierCapability(opts.variant);
  if (capability === true) return true;                // variant says yes → available, stage = pending
  if (capability === false) return false;              // variant says no  → skipped, honest note
  return false;                                        // ambiguous/unknown → fall back to prefix evidence
}
```

Resolution order (do not reorder):

1. **A real prefix `REVIEW` or verifier-role event always wins** — it overrides a variant-no.
   Evidence beats declaration.
2. **Variant says yes** → `review` stage is available even before the first `REVIEW`
   (`state = pending`, normal gloss, gate reads `当前前缀尚无验证审查`).
3. **Variant says no** (`single`/`fixed`/`dynamic_no_verifier`/`no_verifier`) → `review` skipped,
   gloss `该变体无验证者 · 未审查`.
4. **Unknown/absent variant** (`null`, `''`, or a key not in `VERIFIER_VARIANTS`) → falls back to
   prefix evidence, i.e. the same predicate as (1); with no prefix evidence the stage is skipped.

`opts.variant` is threaded from `views.js` (`workflowHtml(state, role, bookmarks, { provider,
variant: data.trace.variant })`). §13.4 records why this deviates from the earlier prefix-only
draft, and the D1 repair round (§13.3) is the defect this rule fixes.

**Golden RICH:** `4 / 4 / 15 / 2 / 3 / 1 / 1`; at last event the CURRENT stage = `报告`.
**Golden SIMPLE:** `4 / 4 / 15 / 2 / 0 / 1 / 1` with `review` **skipped**
(`该变体无验证者 · 未审查`), CURRENT at last = `报告`.
**Golden RICH @ prefix 0–19:** `review` is `pending` (not skipped) with normal gloss and badge
`0 审查`; the gate section reads `当前前缀尚无验证审查` — the variant *does* have a verifier.

### 4.9 Availability / degradation rules (both traces)

1. **RICH** (`mock-success.json`, 71 events, 5 roles, 3 REVIEW, `round_index 3`) → full panel.
2. **SIMPLE** (`demo-simple/trace.json`, 53 events, 4 roles, 0 REVIEW, recorded variant `dynamic`)
   → review stage skipped and review-gate node replaced by a compact note; everything else full.
   `dynamic` is not a key of `VERIFIER_VARIANTS`, so the capability is *unknown* and
   `resolveHasVerifier` falls back to prefix evidence (§4.8.1); the prefix has no
   `REVIEW`/verifier-role event, so the stage is honestly `skipped`.
3. `optional_checks` is empty in both → every check section renders `未记录可选检查`.
4. `contradictions` only on insufficient reviews → sufficient review renders `无矛盾记录`.
5. No `FINALIZE_REJECTED`, and no `backend_resource_saturation` hypothesis → those chapters are
   unavailable; do not hardcode or disable others.
6. `finding.claim` is generic prose → never headline it; lead with `role / task / relation /
   evidence chips / finding_id`.
7. Evidence counts count **unique** ids (15), not verifier re-observations.
8. **Never degrade a variant-capable trace early.** A RICH/`full` trace at prefix 0–19 must keep
   `review` available (`pending`), never `skipped` — the capability is variant-level (§4.8.1), and
   a later `REVIEW` in the same prefix would also override any variant-no. `skipped` is reserved
   for genuinely verifier-less variants (or unknown variants with no prefix evidence at all).

### 4.10 Toolbar & budget chips (deterministic from `state`)

The `.orch-toolbar` shows, all derived from the prefix (never the final trace):

- provider badge: `state` has no provider; use the same `trace.provider` already passed to
  `metadataHtml` (renderer receives it via the existing `data` object or an explicit prop) →
  `MOCK` / `REAL` / `PROVIDER UNKNOWN` (reuse legacy mapping).
- variant gloss: `variantLabel(trace.variant)` (e.g. `Dynamic (with verifier)`, `Dynamic`).
- budget chips: `轮次 {state.round_index} / {state.budgets.max_rounds}`,
  `工具 {state.tool_calls_used} / {state.budgets.max_tool_calls}`,
  `模型请求 {state.llm_calls_used} / {state.budgets.max_llm_calls}` — omit a chip when the
  corresponding max is `null` (e.g. `max_tokens`). Values are prefix-scoped (`tool_calls_used` /
  `llm_calls_used` are already incremented by the reducer).
- when `state.budgets.max_rounds` is present and `round_index === max_rounds`, append a muted
  `已达轮次上限` note (honest, no invented state).

---

## 5. View-model builder contract (`orchestration.js`)

New **pure** module: no DOM, no `window`, no side effects; unit-testable under `node --test`.
All dynamic strings are escaped with `escapeHtml` from `api.js` inside the render helpers.

### 5.1 Exported builders & exact return shapes

```ts
// ---- shared aliases ----
type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';
type StageId = 'coordinator' | 'experts' | 'evidence' | 'hypotheses'
             | 'review' | 'finalize' | 'report';

export function buildStages(state, opts = {}): StageView[];        // opts.variant → resolveHasVerifier (§4.8.1)
export function buildRounds(state): { rounds: RoundView[]; finalize: FinalizeView };
export function buildRoleStats(state): RoleStatView[];
export function buildReviewGates(state, opts = {}): ReviewGateView; // opts.variant → enabled (§4.8.1)
export function buildEvidenceFlow(state): EvidenceFlowView;
export function buildNarrative(state, bookmarks = []): NarrativeView;
```

```ts
interface StageView {
  id: StageId;
  index: number;                 // 0..6
  label: string;                 // "专家(并行)"
  gloss: string;                 // "Experts · parallel"
  count: number;                 // badge number
  countUnit: string;             // "决策"|"任务"|"证据"|"假设"|"审查"|"定案"|"报告"
  reached: boolean;
  available: boolean;            // false only for review w/o verifier (§4.8.1 variant-level rule)
  state: 'done' | 'current' | 'pending' | 'skipped';
  isCurrent: boolean;
  ariaCurrent: 'step' | null;    // 'step' when isCurrent
  firstEventPosition: number|null; // 1-based, for stage click `data-seek`
}
```

```ts
interface RoundView {
  round: number;                 // 1..N
  decisionEventId: string;
  decisionPosition: number;      // 1-based
  timestamp: string;             // ISO
  reason: string;                // decision.reason
  assignments: TaskCardView[];   // 1..n (parallel side-by-side)
}
interface TaskCardView {
  taskId: string;
  role: string;                  // raw id
  roleLabel: string;             // "日志调查员 Logs Agent"
  question: string;
  reason: string;
  allowedTools: string[];
  eventId: string;               // DECISION event id
  position: number;              // DECISION position (fallback jump)
  timestamp: string;             // TASK_ASSIGNED ts if present else DECISION ts
  status: 'ASSIGNED'|'RUNNING'|'COMPLETED'|'FAILED'|'NOT_STARTED';
  statusLabel: string;           // 已调度 / 运行中 / 已完成 / 失败 / 未开始
  statusTone: Tone;
  attemptId: string|null;
  errorCode: string|null;
  jumpPosition: number;          // TASK_ASSIGNED position else DECISION position
  startedAt: string|null;
  completedAt: string|null;
  durationMs: number|null;
}
interface FinalizeView {
  present: boolean;
  decisionEventId: string|null;
  position: number|null;
  selectedHypothesisId: string|null;
  diagnosisAccepted: boolean;
  blocked: boolean;              // true only if FINALIZE_REJECTED present
  statusText: string;            // "已定案 / 未触发阻断" etc.
  statusTone: Tone;
}
```

```ts
interface RoleStatView {
  role: string;
  roleLabel: string;             // "日志调查员 Logs Agent"
  present: boolean;              // role in events / dispatches / review requests
  statusToken: string;           // state.roles[role] or "有已记录动作"
  statusText: string;            // EXACT legacy ternary (see §9): statusToken |
                                 // "已调度 · 尚无执行记录" | "仅审查建议 · 未调度"
  current: boolean;              // data-current (role of latest event)
  stats: {
    dispatches: number;
    tasksAssigned: number; tasksRunning: number;
    tasksCompleted: number; tasksFailed: number;
    toolCalls: number;
    evidenceProduced: number;
    findings: number;
    durationMs: number;
  };
  tasks: TaskRowView[];          // structured rows (no JSON)
  findings: FindingRowView[];
  requestedChecks: CheckRowView[]; // verifier suggestions for this role (incl. not executed)
}
interface TaskRowView {
  taskId: string;
  attemptId: string|null;
  attempt: number;
  status: string;                // COMPLETED | RUNNING | FAILED | ...
  statusLabel: string;           // 已完成 / 运行中 / 失败 / 已调度
  statusTone: Tone;
  question: string;              // dispatch question, or "内部协调任务" for coordinate-*
  resultSummary: string;         // e.g. "supports · 6 条证据" | "neutral · 1 条证据"
                                 //      | "已完成 · 无 finding 提交" | "尚无结果"
  relation: string|null;         // supports | neutral | against | null
  evidenceIds: string[];
  errorCode: string|null;
  jumpPosition: number;
}
interface FindingRowView {
  findingId: string; taskId: string; role: string; relation: string;
  evidenceIds: string[];
}
```

```ts
interface ReviewGateView {
  enabled: boolean;              // resolveHasVerifier(state, opts) — variant-level (§4.8.1)
  summary: { reviewCount: number; insufficient: number; sufficient: number };
  gates: ReviewGateNode[];
  finalize: FinalizeView;
}
interface ReviewGateNode {
  eventId: string; position: number; timestamp: string;
  verdict: 'insufficient' | 'sufficient';
  verdictLabel: string;          // "证据不足 Insufficient" | "证据充分 Sufficient"
  verdictTone: Tone;             // warning | success
  targetHypothesisId: string;
  targetFailureMode: string|null;
  targetCulpritService: string|null;
  rationale: string;
  hypothesisSha256: string|null;
  evidenceSha256: string|null;
  citedEvidenceIds: string[];
  requestedChecks: CheckRowView[];
  optionalChecks: CheckRowView[];
  contradictions: string[];
  loopBack: { toRound: number; toPosition: number; taskIds: string[] } | null;
}
interface CheckRowView {
  taskId: string; role: string; question: string; reason: string;
  kind: 'blocking' | 'optional';
  status: 'completed' | 'assigned' | 'not-dispatched';
  statusLabel: string;           // exact prefix-status strings (§4.6)
}
```

```ts
interface EvidenceFlowView {
  present: boolean;              // any evidence in prefix
  agents: { role: string; roleLabel: string; evidenceIds: string[] }[];
  evidence: {
    id: string; sourceType: string; sourceLabel: string; service: string;
    firstRole: string; firstEventId: string|null; firstTimestamp: string|null;
    findingIds: string[];
    hypothesisRefs: { hypothesisId: string; failureMode: string;
                      relation: 'supports'|'against'; status: string }[];
    report: { supporting: boolean; provisional: boolean; causalChain: string[] };
  }[];
  findings: { findingId: string; taskId: string; role: string;
              relation: string; evidenceIds: string[] }[];
  hypotheses: { hypothesisId: string; failureMode: string; culpritService: string;
                status: string; supportIds: string[]; againstIds: string[] }[];
  report: {
    present: boolean; status: string; rootCauseFailureMode: string|null;
    supportingEvidenceIds: string[]; causalChain: string[];
    rejectedHypothesisIds: string[];
  };
}
```

```ts
interface NarrativeView {
  present: boolean;              // bookmarks.length > 0
  chapters: NarrativeChapter[];
  currentIndex: number;          // last chapter with position <= state.events.length, else -1
}
interface NarrativeChapter {
  id: string;                    // bookmark id
  label: string;                 // bookmark label
  narration: string;             // ONE deterministic line (see §7.6 map)
  position: number|null;         // bookmark position or null
  available: boolean;            // position !== null
  stageId: StageId;              // stage to highlight
  reached: boolean;              // position !== null && position <= state.events.length
}
```

### 5.2 Pure render helpers (return HTML strings)

```ts
export function stagesHtml(state): string;
export function narrativeHtml(state, bookmarks = [], opts = {}): string; // opts.narrativeIndex
export function swimlaneHtml(state): string;
export function roleStatsHtml(state, selectedRole = ''): string;
export function reviewGateHtml(state): string;
export function evidenceFlowHtml(state): string;
export function orchestrationHtml(state, selectedRole = '', bookmarks = [], opts = {}): string;
export function statusBadge(text, tone, icon): string;  // badge + aria-hidden SVG + text
```

All render helpers escape every dynamic value (`escapeHtml`). `orchestrationHtml` composes the
section order of §3.2 and is what `workflowHtml` calls.

### 5.3 DOM binding (lives in `replay-panels.js`, not the pure module)

```ts
// replay-panels.js
export function workflowHtml(state, selectedRole = '', bookmarks = [], opts = {}) {
  return orchestrationHtml(state, selectedRole, bookmarks, opts); // + legacy empty state
}
export function bindWorkflowInteractions(panelEl, ctx): void;
// ctx = { getState, selectedRole, onSelectRole(role), seek(position),
//         narrativeIndex, onNarrativeStep(nextIndex) }
```

`views.js` `draw()` already binds `[data-seek]` (global) and `#replay-workflow [data-role]`
(role toggle). `bindWorkflowInteractions` additionally wires: narrative prev/next buttons,
stage/round/gate `data-seek` jump buttons (they can rely on the global `[data-seek]` binding), and
re-applies the active-chapter highlight (`.is-highlighted`) after each re-render; `aria-current`
stays on the actual current stage and is never reassigned by the demo highlight (§6.6, §13.4). Keep the legacy
`data-role` toggle behavior exactly (aria-pressed toggle, re-draw).

`orchestration.js` **must stay free of DOM calls** so `node --test` can import it directly.

---

## 6. View specifications

### 6.1 (a) Stage stepper — `.orch-stepper`

**Model:** `buildStages(state, opts)` (opts.variant → `resolveHasVerifier`, §4.8.1).

**DOM (desktop horizontal, `<ol>`):**

```html
<nav class="orch-stepper" aria-label="编排阶段">
  <ol class="orch-stepper-track">
    <li class="orch-stepper-item">
      <button type="button" class="orch-stage" data-stage="coordinator"
              data-state="done" data-seek="5">
        <span class="orch-stage__num" aria-hidden="true">1</span>
        <span class="orch-stage__label">协调者</span>
        <span class="orch-stage__gloss">Coordinator</span>
        <span class="orch-stage__badge">4 <span class="orch-badge__unit">决策</span></span>
      </button>
    </li>
    …
    <li class="orch-stepper-item">
      <button type="button" class="orch-stage" data-stage="review" data-state="current"
              aria-current="step" data-seek="25"> … <span class="orch-stage__badge">3 审查</span></button>
    </li>
    <li class="orch-stepper-item">
      <button type="button" class="orch-stage" data-stage="review" data-state="skipped"
              disabled title="该变体无验证者 · 未审查">验证审查
        <span class="orch-stage__gloss">该变体无验证者 · 未审查</span></button>
    </li>
  </ol>
</nav>
```

Rules:

- One `.orch-stage` **button** per stage (inside `.orch-stepper-item <li>`); `data-state` ∈
  `done|current|pending|skipped`; disabled buttons are the only non-focusable case.
- Current stage: `aria-current="step"` **and** `data-state="current"`; visually: accent border +
  accent-soft fill + a small "当前" tag. Colour is never the only signal — current also shows the
  text `当前`.
- Badge: number + unit (`4 决策`, `4 任务`, `15 证据`, `2 假设`, `3 审查`, `1 定案`, `1 报告`);
  zero counts render muted `0`.
- Connector between stages is a CSS `::after` line (not a text glyph); hide it for the vertical
  mobile layout.
- `available === false` → `data-state="skipped"`, badge `—`, gloss text `该变体无验证者 · 未审查`;
  not focusable as a jump (still rendered so the 7-stage story is explicit).
- Stage click (when `firstEventPosition` exists) jumps to the **first event of that stage** via
  `data-seek` (e.g. experts → position 5/6; review → 25; finalize → 67/68; report → 71).
- **Vertical on mobile:** `@media (max-width:680px){ .orch-stepper-track{flex-direction:column} }`;
  connectors become vertical.

### 6.2 (b) Per-round dispatch swimlane — `.orch-swimlane`

**Model:** `buildRounds(state)`.

**Layout:** one `.orch-round` block per INVESTIGATE round (vertical stack). Inside each round:
a header, then a `.orch-lanes` grid where each assignment is a `.orch-task-card` in its own lane —
assignments of the same round sit **side-by-side** (parallel). A coordinator node feeds the lanes,
and a merge node collects them.

```html
<section class="orch-swimlane" aria-label="按轮次调度泳道">
  <article class="orch-round" data-round="1">
    <header class="orch-round__head">
      <span class="orch-round__index">第 1 轮</span>
      <span class="orch-round__reason">Compare symptoms with service health</span>
      <button class="btn btn-sm orch-jump" data-seek="5">跳到决策 · event-5</button>
    </header>
    <div class="orch-lanes">
      <div class="orch-lane">
        <span class="orch-node orch-node--coordinator">协调者 →</span>
        <article class="orch-task-card" data-task-id="check-logs-0" data-role="logs">
          <div class="orch-task-card__head">
            <span class="orch-task-card__role">日志调查员 <span class="orch-role-en">Logs Agent</span></span>
            <span class="orch-status" data-tone="success">…已完成</span>
          </div>
          <code class="orch-task-card__id">check-logs-0</code>
          <p class="orch-task-card__q">Identify error propagation</p>
          <div class="orch-task-card__meta">
            <time>2026-10-15 13:52:44</time>
            <button class="btn btn-sm orch-task-card__jump" data-seek="6">跳到事件</button>
          </div>
        </article>
      </div>
      <div class="orch-lane">…metrics task card (parallel)…</div>
    </div>
    <div class="orch-merge-node">合并证据 → Public Evidence</div>
  </article>
  … rounds 2, 3 …
  <!-- verifier gate + loop-back edges rendered between rounds where applicable -->
</section>
```

Rules:

- Each task card **must show**: role (+ gloss), `task_id`, question, status badge (icon + text +
  tone), timestamp, jump-to-event button. Jump target = first `TASK_ASSIGNED` position for that
  `task_id`, else the DECISION position.
- Parallelism: in R1 the two expert cards share the row; add a small `并行` marker on the round
  header when `assignments.length > 1`.
- **Merge node:** after a round's lanes, a `.orch-merge-node` labelled `合并证据 → Public Evidence`;
  if the round's evidence produced findings, show the finding chips/relation count.
- **Verifier gate node:** a `.orch-gate-node` slot after the round(s) it reviews. For each
  insufficient REVIEW with `loopBack`, render a `.orch-edge--loopback` arrow labelled
  `验证审查 → 第 N 轮重新调度` that is a `data-seek` jump to the re-dispatch DECISION.
- Coordinator-internal `coordinate-*` tasks are **not** lanes; they are summarized in a quiet
  footnote `协调者内部步骤 ×4（计划/综合）`.
- Empty (no assignments) → `.orch-empty` `当前前缀尚无调度 / no dispatch yet`.
- Status badge is `statusBadge(label, tone, icon)` (icon + text, not colour-only).

### 6.3 (c) Per-role stats + structured drilldown — `.orch-role-grid` / `.orch-role-detail`

**Model:** `buildRoleStats(state)`.

**Role card** (one per present role). The card header is a **`.replay-role` button** (preserves the
selector/aria/data-role contract and the asserted status text), followed by a stats grid:

```html
<section class="orch-role-grid" aria-label="角色统计">
  <article class="orch-role-card" data-role-card="logs">
    <button class="replay-role orch-role-toggle" data-role="logs"
            aria-pressed="false" data-current="false">
      <strong>日志调查员 <span class="orch-role-en">Logs Agent</span></strong>
      <span>COMPLETED</span>          <!-- exact legacy statusText ternary -->
    </button>
    <dl class="orch-role-stats">
      <div class="orch-stat"><dt>调度</dt><dd class="orch-stat__value">1</dd></div>
      <div class="orch-stat"><dt>完成 / 失败</dt><dd class="orch-stat__value">1 / 0</dd></div>
      <div class="orch-stat"><dt>工具调用</dt><dd class="orch-stat__value">1</dd></div>
      <div class="orch-stat"><dt>产出证据</dt><dd class="orch-stat__value">6</dd></div>
      <div class="orch-stat"><dt>发现</dt><dd class="orch-stat__value">1</dd></div>
      <div class="orch-stat"><dt>耗时</dt><dd class="orch-stat__value">13 ms</dd></div>
    </dl>
  </article>
  …
</section>
```

**Structured drilldown** `.orch-role-detail` (rendered when `selectedRole` matches; keep the class
name for `browser-real` insurance). **NO `<pre class="json-block">` anywhere.**

```html
<div class="orch-role-detail" data-role-detail="verifier">
  <h3 class="type-title-3">验证审查 · 真实任务与结果</h3>
  <!-- Task rows -->
  <ol class="orch-task-rows">
    <li class="orch-task-row" data-task-id="verify-1">
      <div class="orch-task-row__head">
        <code class="orch-task-row__id">verify-1</code>
        <span class="orch-status" data-tone="success"><span class="orch-status__icon" aria-hidden="true"></span>已完成</span>
      </div>
      <p class="orch-task-row__q">内部协调任务</p>
      <p class="orch-task-row__result">已完成 · 无 finding 提交</p>
      <p class="orch-task-row__error" hidden>error_code: —</p>
      <button class="btn btn-sm" data-seek="7">跳到事件</button>
    </li>
    …
  </ol>
  <!-- Findings for this role (lead with relation + evidence, not claim) -->
  <ul class="orch-finding-rows">
    <li class="orch-finding-row">
      <span class="orch-status" data-tone="info">supports</span>
      <code>finding-…</code> · <code>check-logs-0</code>
      <div class="cite-wrap">…evidence chips…</div>
    </li>
  </ul>
  <!-- Verifier suggestions for this role, structured (not raw array) -->
  <section class="orch-checks">
    <h4>验证审查对该角色的检查建议（含未执行）</h4>
    <ul> … CheckRowView rows with status labels … </ul>
  </section>
</div>
```

Rules:

- Task rows show: status badge, `task_id` (+ `attempt_id · 第 n 次` sub-line when attempt > 1),
  question (or `内部协调任务`), **result summary** (relation + evidence count + finding id reference),
  evidence chips, `error_code` (only when present; otherwise muted `—`).
- Empty tasks → `<p>没有执行记录。审查建议不等于已执行工具查询。</p>` (keep existing copy).
- `reviewOnly` roles (in `reviewWorkflow.roles` only via review requests) get the exact span text
  `仅审查建议 · 未调度` and their drilldown shows suggestions with `未按此 task_id 调度…` status.
- Role toggle preserves legacy behavior: clicking sets/clears `selectedRole` and re-draws.

### 6.4 (d) Verifier REVIEW-GATE node — `.orch-gates`

**Model:** `buildReviewGates(state, opts)`.

`enabled = resolveHasVerifier(state, opts)` — the **variant-level** capability rule of §4.8.1
(`opts.variant` is the recorded trace variant, threaded from `views.js`), never "any REVIEW in the
prefix". Three render states:

1. `!enabled` (genuinely verifier-less variant, e.g. `single`/`fixed`, or an unknown variant with
   no prefix verifier evidence) → compact note only:

```html
<section class="orch-gates orch-gates--skipped" aria-label="验证审查门">
  <p class="orch-empty">该变体无验证者 · 未审查</p>
</section>
```

2. `enabled` but **no `REVIEW` in the current prefix yet** (verifier-capable variant at an early
   replay position) → honest *pending* note + finalize status, never the "no verifier" note:

```html
<section class="orch-gates" aria-label="验证审查门">
  <header class="orch-section-title">验证审查门 Verifier Review Gate <span class="orch-badge">0 审查</span></header>
  <p class="orch-empty">当前前缀尚无验证审查</p>
  <article class="orch-finalize" data-blocked="false">…定案状态…</article>
</section>
```

3. `enabled` **with** `REVIEW` events (RICH from the first review on), render the gate timeline +
   finalize node:

```html
<section class="orch-gates" aria-label="验证审查门">
  <header class="orch-section-title">验证审查门 Verifier Review Gate
    <span class="orch-badge">3 审查 · 2 不足 · 1 充分</span></header>

  <article class="orch-gate" data-verdict="insufficient" data-position="25">
    <header class="orch-gate__head">
      <span class="orch-status" data-tone="warning"><span class="orch-status__icon" aria-hidden="true"></span>证据不足 Insufficient</span>
      <button class="btn btn-sm" data-seek="25">event-25 · REVIEW</button>
    </header>
    <p class="orch-gate__target">目标假设：<span class="mono">backend_pool_config_regression</span>
       <span class="text-muted">(hyp-2354bf4d…)</span></p>
    <p class="orch-gate__rationale">Missing independent causal support or an unresolved contradictory observation</p>
    <div class="cite-wrap">…cited evidence chips (M009, M004)…</div>
    <ul class="orch-checks">
      <li class="orch-check" data-status="assigned">
        <span class="orch-check__kind">阻断检查 Blocking</span>
        <strong>变更调查员 · check-changes-2</strong>
        <p>Check backend pool configuration and its recent change</p>
        <span class="orch-check__status">当前前缀：已调度，未见完成</span>
      </li>
      <li class="orch-check orch-check--optional">可选检查 Optional → 未记录可选检查</li>
    </ul>
    <ul class="orch-contradictions">
      <li class="orch-contradiction">Observed normal database metrics challenge database exhaustion</li>
    </ul>
    <a class="orch-edge--loopback" data-seek="30" href="#">验证审查 → 第 2 轮重新调度 (check-changes-2)</a>
    <details><summary>审查理由与版本哈希</summary>
      <dl><dt>Hypothesis SHA256</dt><dd class="mono">…</dd>
          <dt>Evidence SHA256</dt><dd class="mono">…</dd></dl></details>
  </article>

  … review 2 (insufficient @43) …
  … review 3 (sufficient @62, no contradictions, optional checks "未记录可选检查") …

  <article class="orch-finalize" data-blocked="false">
    <span class="orch-status" data-tone="success">已定案 / 未触发阻断</span>
    <p class="text-muted">DIAGNOSIS_ACCEPTED · event-68 · 根因 backend_pool_config_regression</p>
  </article>
</section>
```

Rules:

- Verdict conveyed by badge + icon + text; tone `warning` (insufficient) / `success` (sufficient).
- Show target hypothesis (failure_mode primary, id muted), rationale, cited evidence chips,
  requested checks (blocking) with prefix status, optional checks (`未记录可选检查` when empty),
  contradictions (`无矛盾记录` when empty), and hashes inside a `<details>`.
- Loop-back edges only for insufficient reviews with a matching later re-dispatch round.
- Finalize node: honest status per §4.7. If a future trace has `FINALIZE_REJECTED`, render
  `已阻断 · FINALIZE_REJECTED` with `data-blocked="true"` and tone `danger`.
- **Never derive availability from the prefix alone** — see §4.8.1. `0 REVIEW` at an early
  position is `pending`, not "该变体无验证者"; only a variant-no (or unknown variant with no
  prefix evidence) may render the skipped note.

### 6.5 (e) Evidence flow — `.orch-flow`

**Model:** `buildEvidenceFlow(state)`. Four columns with directional labels:

```
agent → evidence(chips) → finding / hypothesis → report reference
```

```html
<section class="orch-flow" aria-label="证据流向">
  <header class="orch-section-title">证据流向 Evidence Flow
    <span class="orch-badge">15 证据 · 4 发现 · 2 假设</span></header>
  <div class="orch-flow__grid">
    <div class="orch-flow__col orch-flow__col--agents">
      <h4>来源 Agent</h4>
      <div class="orch-flow__item">
        <span class="orch-role-en">日志调查员 Logs Agent</span>
        <span class="orch-badge">6 证据</span>
      </div> …
    </div>
    <div class="orch-flow__col orch-flow__col--evidence">
      <h4>证据 Evidence</h4>
      <button class="evidence-chip" data-evidence-id="incident_001-M009">M009</button> …
      <!-- grouped by source: 日志/指标/变更/配置; each chip opens the drawer via existing binder -->
    </div>
    <div class="orch-flow__col orch-flow__col--findings">
      <h4>发现 / 假设 Findings · Hypotheses</h4>
      <div class="orch-flow__item">
        <span class="orch-status" data-tone="info">supports</span>
        <code>check-metrics-0</code>
        <div class="cite-wrap">…chips…</div>
      </div>
      <div class="orch-flow__item">
        <span class="orch-badge">postgres_connection_exhaustion</span>
        <span class="orch-status" data-tone="danger">REJECTED</span>
      </div> …
    </div>
    <div class="orch-flow__col orch-flow__col--report">
      <h4>报告引用 Report</h4>
      <p class="mono">backend_pool_config_regression</p>
      <div class="cite-wrap">…supporting chips C001 D001 M009…</div>
      <details><summary>因果链 · causal_chain</summary><ol>…3 lines…</ol></details>
    </div>
  </div>
</section>
```

Rules:

- Evidence chips are the existing `.evidence-chip[data-evidence-id]` buttons so the current
  `bindEvidenceChips` drawer keeps working (no new drawer code).
- Each column can be long; use `max-height` + `overflow:auto` per column on desktop, and stack
  columns on mobile. Never cause page-level horizontal overflow.
- Empty prefix → `.orch-empty` `当前前缀尚无证据`.
- Report not present → `当前前缀尚未生成报告`.
- Relation tones: `supports` info/success, `neutral` neutral, `against` warning/danger;
  hypothesis status uses `REJECTED` danger, `OPEN` info, `SUPPORTED` success.

### 6.6 (f) Demo-narrative mode — `.orch-narrative`

**Model:** `buildNarrative(state, bookmarks)`.

```html
<section class="orch-narrative" aria-label="演示叙事" data-active-index="2">
  <p class="orch-narrative__line" aria-live="polite">
    <span class="orch-chapter-label">第 4 章 · 首次证据不足审查</span>
    验证者判定证据不足，要求补充变更检查。
  </p>
  <div class="orch-narrative__controls">
    <button class="btn btn-sm orch-narrative__prev" type="button">上一关键节点</button>
    <span class="orch-narrative__pos">3 / 6</span>
    <button class="btn btn-sm orch-narrative__next" type="button">下一关键节点</button>
  </div>
  <ol class="orch-chapters">
    <li class="orch-chapter" data-chapter="dispatch" data-position="5" data-stage="experts"
        aria-current="false"><button type="button" data-seek="5">首次调度</button></li>
    …
  </ol>
</section>
```

Deterministic narration map (keyed by bookmark id; chapter label from `replayBookmarks`):

| id | narration (one line) | target stage |
|---|---|---|
| `dispatch` | 协调者把首轮并行任务同时派给日志与指标调查员。 | `experts` |
| `config` | 变更调查员读取配置差异，把 DB_POOL_MAX 从 64 降到 2 的关键证据合并进来。 | `evidence` |
| `insufficient` | 验证者判定证据不足，要求补充变更检查。 | `review` |
| `postgres_connection_exhaustion` | 数据库连接耗尽假设被正常指标证据否决。 | `hypotheses` |
| `backend_resource_saturation` | （该 trace 未记录此竞争假设） | `hypotheses` |
| `gate` | 定案门未触发阻断：本 trace 无 FINALIZE_REJECTED，门禁以 REVIEW 判定表示。 | `finalize` |
| `last-review` | 验证者确认证据充分（sufficient）。 | `review` |
| `report` | 最终报告确认根因 backend_pool_config_regression。 | `report` |
| `(start)` *(synthetic chapter 0)* | 调查开始：只有公开事故摘要，尚无证据。 | `coordinator` |

Rules:

- Chapters come from `replayBookmarks(trace)` (passed by `views.js`). `available = position !== null`;
  unavailable chapters are shown disabled (`title="Trace 未记录对应事件"`, suffix ` · 未记录`) and
  **skipped** by prev/next traversal. For SIMPLE, `insufficient`, `last-review`, `gate`,
  `backend_resource_saturation` are unavailable.
- Exactly **one** narration line is shown at a time; `aria-live="polite"` announces changes.
- Prev/Next: move to previous/next **available** chapter, call `seek(chapter.position)`; disable at
  the ends. Because `seek()` re-renders, the controller stores `narrativeIndex` in the `mountReplay`
  closure and re-applies highlight after each draw.
- **Auto mode** (`#replay-demo` checked, i.e. demo mode): when the replay position lands on/after a
  chapter, `.orch-narrative` auto-updates the visible line, adds `.is-highlighted` to the matching
  `.orch-stage`, expands the relevant `<details>` if collapsed, and calls
  `stageEl.scrollIntoView({ block: 'nearest', behavior: prefersReducedMotion ? 'auto' : 'smooth' })`.
  In non-demo mode the narrative remains manually operable but does **not** auto-scroll.
- **Demo highlight uses `.is-highlighted`, *not* a second `aria-current`** (deliberate,
  a11y-safer — see §13.4). Exactly **one** element in the panel carries `aria-current="step"`: the
  stage matching the replay position (`data-state="current"`), because that is what a screen reader
  should announce as "current". The demo-highlighted stage is marked only with
  `.is-highlighted` (a 2 px accent outline, CSS-only) plus the narration line — two simultaneous
  `aria-current` values would announce conflicting "current" items. The earlier draft of this
  section asked for `aria-current="step"` on the demo-highlighted stage; the implementation
  deliberately does not do that, and §13.4 records the deviation.
  When the demo chapter's target stage *is* the current stage, both marks land on the same
  element (no conflict). Toggling demo off clears `.is-highlighted` only; `aria-current` stays on
  the true current stage.
- `currentIndex` = last chapter with `position <= state.events.length`; before the first, `-1` and
  the line reads `从 0 开始播放，按「下一关键节点」开始演示。`

---

## 7. CSS / class contract

Append a new section to `app.css` (after the existing `.replay-*` block). **All new classes are
namespaced `orch-`** to avoid collisions. Use existing tokens only (`--sp-*`, `--text-*`,
`--radius-*`, `--accent*`, `--success*`, `--warning*`, `--danger*`, `--info*`, `--border*`,
`--bg-*`, `--shadow-*`, `--dur*`, `--ease`). No hard-coded colours, no gradients, no webfonts.

### 7.1 New class names (enumerated)

**Panel / common**
`.orch-panel`, `.orch-toolbar`, `.orch-section`, `.orch-section-title`, `.orch-legend`,
`.orch-badge`, `.orch-badge__unit`, `.orch-status`, `.orch-status__icon`, `.orch-status__text`,
`.orch-role-en`, `.orch-gloss`, `.orch-empty`, `.orch-jump`, `.orch-mono`, `.orch-text-sm`.

**Stepper**
`.orch-stepper`, `.orch-stepper-track`, `.orch-stepper-item`, `.orch-stage`, `.orch-stage__num`, `.orch-stage__label`,
`.orch-stage__gloss`, `.orch-stage__badge`, `.orch-stage__current-tag`,
`.orch-stage[data-state="done|current|pending|skipped"]`, `.orch-stage[aria-current="step"]`.

**Swimlane**
`.orch-swimlane`, `.orch-swimlane-scroll`, `.orch-round`, `.orch-round__head`,
`.orch-round__index`, `.orch-round__reason`, `.orch-lanes`, `.orch-lane`, `.orch-node`,
`.orch-node--coordinator`, `.orch-node--expert`, `.orch-node--merge`, `.orch-task-card`,
`.orch-task-card__head`, `.orch-task-card__role`, `.orch-task-card__id`, `.orch-task-card__q`,
`.orch-task-card__meta`, `.orch-task-card__jump`, `.orch-merge-node`, `.orch-gate-node`,
`.orch-edge`, `.orch-edge--loopback`, `.orch-round__parallel`.

**Role stats / drilldown**
`.orch-role-grid`, `.orch-role-card`, `.orch-role-toggle`, `.orch-role-status`, `.orch-role-stats`,
`.orch-stat`, `.orch-stat__label`, `.orch-stat__value`, `.orch-role-detail`, `.orch-task-rows`,
`.orch-task-row`, `.orch-task-row__head`, `.orch-task-row__id`, `.orch-task-row__status`,
`.orch-task-row__q`, `.orch-task-row__result`, `.orch-task-row__evidence`, `.orch-task-row__error`,
`.orch-finding-rows`, `.orch-finding-row`, `.orch-checks`, `.orch-check`, `.orch-check__kind`,
`.orch-check__status`, `.orch-check--optional`.

**Review gate**
`.orch-gates`, `.orch-gates--skipped`, `.orch-gate`, `.orch-gate[data-verdict="insufficient|sufficient"]`,
`.orch-gate__head`, `.orch-gate__verdict`, `.orch-gate__target`, `.orch-gate__rationale`,
`.orch-gate__meta`, `.orch-contradictions`, `.orch-contradiction`, `.orch-finalize`,
`.orch-finalize[data-blocked="true|false"]`.

**Evidence flow**
`.orch-flow`, `.orch-flow__grid`, `.orch-flow__col`, `.orch-flow__col--agents`,
`.orch-flow__col--evidence`, `.orch-flow__col--findings`, `.orch-flow__col--report`,
`.orch-flow__item`, `.orch-flow__chip`, `.orch-flow__link`, `.orch-flow__group`.

**Narrative**
`.orch-narrative`, `.orch-narrative__line`, `.orch-narrative__controls`, `.orch-narrative__prev`,
`.orch-narrative__next`, `.orch-narrative__pos`, `.orch-chapters`, `.orch-chapter`,
`.orch-chapter[aria-current="true"]`, `.orch-chapter-label`, `.orch-stage.is-highlighted`.

**Legacy review panel (structured cards, `#replay-review-panel`)**
`.replay-review__head`, `.replay-review__chips`, `.replay-review__sub`, `.replay-review__title`,
`.replay-review__kv`, `.replay-review__section`, `.replay-review__label`, `.replay-review__list`,
`.replay-review__hash`, `.replay-review__note`, `.replay-review__raw`,
`.replay-review[data-outcome="accepted|blocked|recorded|unknown"]`. These reuse the existing `.replay-review`
card shell (border/padding), `.kv-list`/`.kv-row`, `.cite-wrap`, `.badge`, `.evidence-chip`,
`.json-block` tokens — no new colour values. `#replay-reviews .evidence-chip` is added to the
existing `@media (pointer: coarse), (max-width: 680px)` 44 px touch-target rule so the new cards
are touch-safe at 390 px.

### 7.2 Existing selectors that must keep working

`#replay-workflow`, `[data-role]`, `.replay-role`, `.replay-role-detail`, `.replay-workflow` (may be
reused as the outer wrapper or kept as an alias on `.orch-panel`), `data-current`, `aria-pressed`,
`data-seek`, `data-bookmark`, `data-evidence-id`, `#replay-reviews article` (one per REVIEW),
`#replay-demo`, `#replay-metadata`, `#replay-position`, `.replay-controls button`, `[data-step]`.

> `#replay-workflow` remains the single mount div; `workflowHtml` returns its inner HTML. The
> `.replay-workflow` CSS rule (currently a flex row of role cards) may be superseded by the
> `.orch-panel` layout, but keep the class token on the outer element if any external CSS relies
> on it. The role buttons themselves stay `.replay-role`.

### 7.3 Status badge contract (icon + text + tone, never colour alone)

`statusBadge(text, tone, icon)` returns:

```html
<span class="orch-status" data-tone="success">
  <span class="orch-status__icon" aria-hidden="true"><svg …/></span>
  <span class="orch-status__text">已完成</span>
</span>
```

Icons (inline SVG, `aria-hidden`): `check` (done/success), `clock` (assigned/pending),
`play` (running), `alert` (failed/insufficient), `shield-check` (sufficient), `dot` (neutral).
Do **not** use emoji or text glyphs as icons (BRIEF ban).

---

## 8. Accessibility, interaction, responsive, motion

### 8.1 Accessibility

- **Status not colour-only:** every status = badge shape + inline SVG icon + text (see §7.3).
- **Current stage:** `aria-current="step"` + `data-state="current"` + visible `当前` tag — exactly
  one such element **inside `#replay-workflow`**. (The 调查时间线 list below the fold carries its own
  `aria-current="step"` on the current-event button — a separate, pre-existing landmark owned by
  `views.js`, which is out of this change set; the panel never duplicates it.) The demo highlight
  is `.is-highlighted` only and never a second `aria-current` (§6.6, §13.4).
- **Keyboard reachable:** stages, task cards and narrative chapters are real `<button>`s (or
  `tabindex="0"` with Enter/Space) — no click-only `<div>`s. Jump buttons are `<button data-seek>`.
- **Focus-visible:** `:focus-visible { outline: 2px solid var(--focus-ring-color); outline-offset:
  2px; }` on every `.orch-*` interactive; never `outline:none` without replacement.
- **Labels:** stepper `<nav aria-label="编排阶段">`; sections `aria-label`; icon-only jumps have
  `aria-label`; decorative icons `aria-hidden="true"`; evidence chips keep their text.
- **Live region:** narration line `aria-live="polite"`; avoid `aria-live` on the whole panel.
- **Headings:** each section `h3` (`.type-title-3`), subsections `h4`; do not skip levels.
- **Reduced motion:** see §8.4.

### 8.2 Interaction

- Role toggle (legacy): click `.replay-role[data-role]` → set/clear `selectedRole` → re-draw.
- Jump-to-event: any `data-seek` button calls `seek(position)` (already globally bound in `draw()`).
- Evidence chip: `data-evidence-id` opens the existing evidence drawer (`bindEvidenceChips`).
- Stage click: `data-seek` to first event of the stage (disabled for skipped/pending-no-position).
- Gate loop-back: `data-seek` to the re-dispatch DECISION.
- Narrative prev/next: move among available chapters; disabled at ends; updates `narrativeIndex`.
- Demo toggle (`#replay-demo`) also turns on narrative auto mode (existing behavior extends to
  auto-expand/scroll/highlight).

### 8.3 Responsive

- Breakpoints (structural): desktop ≥1024, tablet 768–1023, mobile ≤680 (case shell already
  collapses at 860). Verify at **390 × 844**.
- Mobile:
  - `.orch-stepper-track{flex-direction:column}` (vertical stepper; connectors vertical).
  - `.orch-lanes{grid-template-columns:1fr}`; add `并行` marker per round instead of side-by-side.
  - `.orch-role-grid{grid-template-columns:1fr}`.
  - `.orch-flow__grid{grid-template-columns:1fr}` with arrow labels (`↓ 来源`, `↓ 证据` …).
  - `.orch-narrative__controls` full-width stacked buttons.
- **No horizontal overflow at 390:** every flex/grid child gets `min-width:0`; long ids/strings
  wrap (`overflow-wrap:anywhere`); swimlane uses an internal `.orch-swimlane-scroll{overflow-x:auto}`
  only if a lane grid must scroll (never the page). CI asserts
  `document.documentElement.scrollWidth <= innerWidth`.
- **44 px targets** on mobile / `(pointer:coarse)`: exactly these selectors get
  `min-height:44px` — `.orch-stage`, `.orch-role-toggle`, `.orch-task-card__jump`,
  `.orch-narrative button`, `.orch-panel .evidence-chip`, and **`#replay-reviews .evidence-chip`**
  (the legacy review-card chips). The last selector is the fix for a real gap: when the cards
  first shipped, the rule only covered `.orch-panel .evidence-chip`, so the new review-card chips
  measured **32 px** at 390/coarse. The rule was extended to `#replay-reviews .evidence-chip`
  and the chips now measure **44 px** at 390 / `pointer:coarse` (verified in-browser, 0 overflow).
  Evidence chips anywhere else keep their compact legacy sizing — the rule is scoped, not global.

### 8.4 Motion

- 150–250 ms, state-driven only; animate `opacity`/`transform` only; list transition properties
  explicitly (never `transition: all`).
- No page-load choreography, no scroll-reveal.
- `@media (prefers-reduced-motion: reduce) { .orch-panel * { animation: none !important;
  transition: none !important; scroll-behavior: auto !important; } }` and narrative `scrollIntoView`
  uses `behavior:'auto'` when reduced.

---

## 9. JS export contract & test-hook preservation matrix

### 9.1 `replay-panels.js`

- **`workflowHtml(state, selectedRole = '', bookmarks = [], opts = {})` MUST remain exported** —
  `tests/web/replay-demo.test.mjs` imports it. Calling it with the legacy 1–2 args stays valid
  (bookmarks/opts optional). It returns the full inner HTML for `#replay-workflow`.
- **Literal `仅审查建议 · 未调度` MUST still appear in `workflowHtml` output** for the
  "reviewed-but-not-dispatched role" case (a role present only via REVIEW `requested_checks` /
  `optional_checks`, no dispatch, no task events). This is asserted by
  `replay-demo.test.mjs:39`. Implement it exactly as the legacy ternary (§4.4 / §6.3):
  ```
  actual role      → state.roles[role] || '有已记录动作'
  dispatched-only  → '已调度 · 尚无执行记录'
  review-request-only → '仅审查建议 · 未调度'   // ← exact literal
  ```
- **`reviewTimelineHtml(state)` keeps the literal `未按此 task_id 调度`** (in the check status
  `当前前缀：未按此 task_id 调度；不推断检查已完成`), asserted by `replay-demo.test.mjs:40`. It is
  fine to visually restyle it but keep one `<article class="replay-review">` per REVIEW event
  (`#replay-reviews article` count = REVIEW count) and render `DIAGNOSIS_ACCEPTED` as a `<div>`,
  not an `<article>`.
- **Legacy review panel renders structured cards, not raw JSON** (fixes the last remaining raw
  `<pre>` dump). For events in `reviewTimelineHtml` that have no `details.review`:
  - `DIAGNOSIS_ACCEPTED` → 定案门 pass card `<div class="replay-review" data-outcome="accepted">`:
    `badge('诊断已通过','success')` + event id/type + jump; from
    `details.root_cause` show `culprit_service`, `failure_mode` as the headline, `status` badge,
    `support_ids`/`against_ids` as `evidenceChips(...)`, `predicted_observations` and
    `open_questions` as short lists; plus `details.supporting_evidence_ids` chips and a
    `degraded_call_ids` count. The long `hypothesis_id` is truncated in display
    (`hyp-2354bf4d…`) but the full value stays in the `title` attribute — never dropped.
  - `FINALIZE_REJECTED` / `FINALIZE_ACCEPTED` / other `FINALIZE*` → structured summary card
    (action, reason, blocking checks, selected hypothesis / hypothesis+evidence hashes) as
    `kv-row`s; a `candidate_assessments` object is reported as a count and pointed at the two
    places where the full JSON actually lives — the current event's collapsed
    `原始结构化事件详情` in `#replay-selection`, and the event's expanded row in the
    **调查时间线 tab** (`.tl-body` → `timelineBody`). It is deliberately **not** claimed to be in
    the 编排视图 (`reviewGateHtml`/`buildRounds` never render `candidate_assessments`), and not
    claimed to be in the `#replay-events` category list, which renders jump buttons only.
    Only an unrecognisable shape falls back to a **collapsed**
    `<details><summary>原始结构化事件</summary><pre>…</pre></details>` — never the default view.
  - **Every list field is normalised before rendering.** `TraceEvent.details` is
    `dict[str, Any]`, so `support_ids`/`against_ids`/`predicted_observations`/`open_questions`/
    `supporting_evidence_ids`/`degraded_call_ids`/blocking-check sources may legally arrive as a
    scalar (`"incident_001-C001"`) or be absent; `asList(v)` wraps a scalar and treats
    `null`/`''` as empty, so a schema-valid scalar-typed field renders instead of throwing.
    The `diagnosisCard`/`finalizeCard` dispatch — in fact **the whole per-event render** — is
    wrapped in `try/catch` → a collapsed `rawDetails(e)` card for that event only (the REVIEW
    branch keeps its exact markup and strings; the guard simply surrounds it), so an unexpected
    shape degrades to raw JSON instead of throwing out of the `.map()` and blanking
    `#replay-reviews`, `#replay-selection`, `#replay-reliability` and every `[data-seek]` binding
    in `draw()`.
    Evidence-id lists go through `asIdList`, which resolves an id object to its text field
    (`evidence_id`/`id`/…) and **drops entries with no renderable text** (`{}`, `null`, `''`), so a
    chip is never labelled `[object Object]` and never blank (verified: `[{}]`, `[null]`, `['']`
    and `[{a:{b:1}}]` all yield 0 chips, while `[{evidence_id:'incident_001-C001'}]` yields a
    normal chip).
  - Blocking-check sources (`errors` / `blocking_checks` / `checks` / `failed_checks`) are
    normalised and the **first non-empty** one wins, so `errors: []` never masks a populated
    `blocking_checks`. A source that exists but is empty renders `阻断检查 · blocking checks：0 条
    （记录为空）`; the `未记录阻断检查` copy is used only when **no blocking-source field is present
    at all**. The precise invariant is therefore: **the contradiction is prevented only when a
    blocking-source field is PRESENT** — any present source, including an empty `[]`, renders a
    count, so `定案被阻断` + `未记录阻断检查` is unreachable in that case. When **no** blocking
    source is present (`details: {}`), the card legitimately shows `未记录阻断检查` alongside
    `定案被阻断`; that is the honest reading of "this event recorded no blocking checks", and it
    is not a contradiction but a true statement. All 12 real `FINALIZE_REJECTED` events carry
    `errors`, so no live data hits that case.
  - The REVIEW branch keeps its existing `<article class="replay-review">` markup and strings.
- `metadataHtml(data, opts = {})`: default call `metadataHtml(data)` is byte-compatible with today
  and still emits `PROVIDER UNKNOWN`, `SOURCE DRIFT` (when drift), `独立最终产物`. `opts` only
  splits heading vs snapshot for the new placement; defaults preserve all strings.
- `historyHtml`, `reliabilityHtml`, `jumpButton` unchanged exports.
- New: `bindWorkflowInteractions(panelEl, ctx)` (DOM wiring only).

### 9.2 `orchestration.js`

- Exports the six builders + render helpers of §5.1–5.2. Pure: no DOM access.
- May import `escapeHtml`, `formatDuration`, `SOURCE_TYPE_META`, `ROLE_LABEL`, `variantLabel` from
  `api.js`, and `replayWorkflow`, `evidenceContext`, `replayBookmarks` from `replay.js` (imports only;
  those files are not modified). No new third-party dependency.

### 9.3 Test-hook preservation matrix

| Hook | Asserted by | How the redesign preserves it |
|---|---|---|
| `workflowHtml` export | `replay-demo.test.mjs` import | kept exported, same first two params |
| `仅审查建议 · 未调度` | `replay-demo.test.mjs:39` | exact ternary in role status span |
| `未按此 task_id 调度` | `replay-demo.test.mjs:40` | kept in `reviewTimelineHtml` check status |
| `独立最终产物` / `SOURCE DRIFT` / `PROVIDER UNKNOWN` | `replay-demo.test.mjs` (`metadataHtml`) | `metadataHtml` default output unchanged |
| `.replay-controls button`, `[data-step]`, `#replay-play`, `#replay-position`, `#replay-seek` | `browser.cjs` | untouched markup |
| `#run-tab-panel`, `[data-tab]`, `[data-ev]`, `#drawer*` | `browser.cjs` | untouched (`drawRun` shell) |
| 390 px `scrollWidth <= innerWidth` | `browser.cjs` | mobile stacking + `min-width:0` + no page overflow |
| `#replay-workflow [data-role=…]`, `.replay-role`, `.replay-role-detail`, `#replay-reviews article` | `browser-real.cjs` (non-CI, stale) | selectors retained as cheap insurance |
| `historyHtml` / `reviewTimelineHtml` exports | `replay-demo.test.mjs` | retained |

---

## 10. Low-fidelity wireframes

### Desktop (≥1024)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [MOCK] [RECORDED REPLAY]         Investigation Replay         [x] 演示模式      │  ← heading
│ 按保存顺序重建共享状态…                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ [首步][上一步][播放][下一步][末步]  速度 1×   12 / 71 已保存事件                 │  ← controls
│ Seek ──────●────────────────────────────────  Jump [ 12 ] [跳转]               │  ← seek
├──────────────────────────────────────────────────────────────────────────────┤
│ ▸ 编排视图 · 共享状态与工作流                                          (open)    │
│  ┌─ [MOCK][Dynamic (with verifier)] 轮次 3/4 工具 9/12 ──────────────┐        │
│  │ 协调者(4) → 专家(4) → 合并证据(15) → 假设(2) → [验证审查(3)] → 定案门(1) → 报告(1) │  ← stepper
│  │  ▲当前 = aria-current=step（回放位置；#replay-workflow 内唯一）  │        │
│  │  演示模式另加 .is-highlighted 轮廓，不加第二个 aria-current      │        │
│  │ 第 4 章 · 首次证据不足审查：验证者判定证据不足，要求补充变更检查。   [上一][3/6][下一] │  ← narrative
│  ├──────────────────────────────────────────────────────────────────┤        │
│  │ 第 1 轮  Compare symptoms with service health            [跳决策] │        │
│  │ 协调者→ ┌ 日志调查员 Logs Agent ─┐ ┌ 指标调查员 Metrics Agent ─┐   │        │  ← swimlane
│  │        │ check-logs-0  ✓已完成  │ │ check-metrics-0 ✓已完成   │   │        │
│  │        │ Identify error prop…   │ │ Compare dependency health │   │        │
│  │        └ [时间][跳到事件] ──────┘ └ [时间][跳到事件] ─────────┘   │        │
│  │        合并证据 → Public Evidence                                  │        │
│  ├──────────────────────────────────────────────────────────────────┤        │
│  │ 角色统计 Role stats                                               │        │
│  │ ┌日志调查员 1/0/1/6/1/13ms┐ ┌指标调查员┐ ┌变更调查员┐ ┌验证审查┐       │  ← role cards
│  │ │(选中展开)  task rows …  │                                          │        │
│  ├──────────────────────────────────────────────────────────────────┤        │
│  │ 验证审查门 3审查·2不足·1充分                                        │        │  ← gate
│  │ ⚠证据不足 @event-25 目标:backend_pool_config_regression            │        │
│  │   cited M009 M004 · 阻断检查 check-changes-2(已调度未见完成)          │        │
│  │   矛盾: Observed normal database metrics…  ↳ 第2轮重新调度          │        │
│  │ ✓证据充分 @event-62 …            [已定案 / 未触发阻断]               │        │
│  ├──────────────────────────────────────────────────────────────────┤        │
│  │ 证据流向  agent → evidence → finding/hypothesis → report            │        │  ← flow
│  │ Agents │ Evidence chips │ Findings/Hypotheses │ Report refs         │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│  ▸ 演示章节 …   ▸ Communication Timeline …   ▸ Hypothesis …  ▸ Review …      │
│  ▸ 运行来源与限制 · 独立最终产物元数据快照                                   │  ← metadata (sunk)
└──────────────────────────────────────────────────────────────────────────────┘
```

### Mobile (≤680, verified 390)

```
┌─────────────────────────────┐
│ [MOCK][RECORDED]  Investigation Replay  [x]演示│
│ [首步][上一步][播放][下一步][末步]             │
│ Seek ──●──────────── Jump[12][跳转]           │
├─────────────────────────────┤
│ ▾ 编排视图 · 共享状态与工作流    (open)        │
│ ① 协调者 Coordinator  4 决策    │  ← vertical
│ │                            │     stepper
│ ② 专家(并行) Experts  4 任务  ▲当前│
│ │                            │
│ ③ 合并证据 Public Evidence 15  │
│ ④ 假设 Hypotheses 2           │
│ ⑤ 验证审查 Verifier 3          │
│ ⑥ 定案门 FinalizeGate 1        │
│ ⑦ 报告 Report 1               │
│ ─────────────────────────────│
│ 第4章 · 验证者判定证据不足…     │  ← narrative
│ [上一关键节点]  3/6  [下一…]    │
│ ─────────────────────────────│
│ 第 1 轮 (并行)  Compare symptoms│  ← swimlane
│ ┌ 日志调查员 Logs Agent ────┐ │     stacked
│ │ check-logs-0    ✓已完成   │ │
│ │ Identify error propagation│ │
│ │ 13:52:44   [跳到事件]     │ │
│ └───────────────────────────┘ │
│ ┌ 指标调查员 Metrics Agent ─┐ │
│ │ check-metrics-0 ✓已完成   │ │
│ └───────────────────────────┘ │
│ 合并证据 → Public Evidence     │
│ ─────────────────────────────│
│ 角色统计 (1-up cards)          │
│ ┌ 日志调查员 Logs Agent ────┐ │
│ │ 调度1 完成1 工具1 证据6 … │ │
│ │ (展开) task rows …        │ │
│ └───────────────────────────┘ │
│ ─────────────────────────────│
│ 验证审查门 (RICH) / 该变体无验证者·未审查 (SIMPLE)│
│ ⚠ 证据不足 @25 …              │
│ ↳ 第2轮重新调度               │
│ [已定案 / 未触发阻断]          │
│ ─────────────────────────────│
│ 证据流向 (stacked, ↓ arrows)   │
│ 来源 Agent ↓ 证据 ↓ 发现/假设 ↓ 报告│
└─────────────────────────────┘
```

Wireframe conventions (both layouts):

- `▲当前` = the stage whose `aria-current="step"` / `data-state="current"` follows the **replay
  position** — exactly one inside `#replay-workflow` (the separate 调查时间线 list keeps its own
  `aria-current="step"` on the current-event button; `views.js`, unchanged). Demo mode adds a
  separate `.is-highlighted` accent outline to the chapter's target stage; it does **not** move or
  duplicate `aria-current` (§6.6, §13.4).
- The review stage/badge is derived from `resolveHasVerifier(state, opts)` (§4.8.1): RICH
  (`full`) keeps `验证审查` available even at prefix 0–19 (`pending`, `0 审查`, gate note
  `当前前缀尚无验证审查`); only a genuinely verifier-less variant (SIMPLE/unknown with no prefix
  evidence) renders `该变体无验证者 · 未审查`. The wireframe's `[验证审查(3)]` bracket is the RICH
  full-prefix state, not the only valid state.

---

## 11. P0 / P1 / P2 build order

**P0 — must ship (the demo is not an orchestration without these):**
1. Create `orchestration.js` with `buildStages`, `buildRounds`, `buildRoleStats`, `buildReviewGates`
   (+ `statusBadge`, escape-safe render helpers); pure + unit-testable.
2. Rebuild `workflowHtml` composition + `stagesHtml` (stepper with badges/current/vertical mobile).
3. Rebuild `roleStatsHtml` + `roleDetail` as **structured task rows** — delete every
   `<pre class="json-block">` in the panel; preserve `仅审查建议 · 未调度`.
4. `reviewGateHtml` with conditional render + honest finalize status; preserve
   `未按此 task_id 调度` in `reviewTimelineHtml`.
5. Move the panel under the controls, open by default; sink metadata; wire `draw()` to
   `workflowHtml(state, selectedRole, bookmarks)`; keep `[data-seek]`/`[data-role]` working.
6. Accessibility + responsive baseline (badge+icon+text, aria-current, focus-visible, 44 px, no 390
   overflow, reduced motion).

**P1 — recommended:**
7. `swimlaneHtml` per-round dispatch with parallel lanes, merge node, verifier gate node and
   loop-back edges.
8. `buildEvidenceFlow` + `evidenceFlowHtml` (agent → evidence → finding/hypothesis → report),
   reusing `.evidence-chip` drawer.
9. `buildNarrative` + `narrativeHtml` + prev/next control (manual), chapters from `replayBookmarks`,
   skip unavailable chapters.

**P2 — polish:**
10. Narrative auto-expand/auto-scroll/highlight on demo mode + `prefers-reduced-motion` handling.
11. Budget chips (`轮次 3/4 · 工具 9/12`), stage-click jump-to-first-event, subtle transitions.
12. Dark-theme tuning, long-content truncation, microcopy pass (curly quotes, `…`, tabular-nums).

---

## 12. Verification plan (for the implementer)

Run from `IncidentLens-hpc/` with Node 22 (`export PATH=$HOME/.nvm/versions/node/v22.23.4/bin:$PATH`):

1. `npm test` (or `node --experimental-default-type=module --test tests/web/*.test.mjs`) → 23/23
   green; specifically `replay-demo.test.mjs` (workflowHtml/reviewTimelineHtml strings).
2. `python -m ruff check .` → PASS.
3. Integration trio (as in `baseline-tests.md`) → 20 passed.
4. `python scripts/run_mock_browser.py` → PASS (real browser, 1440 + 390, no `/api/run`, no page
   errors, `#replay-workflow` still renders for both fixtures).
5. Manual/Playwright checks:
   - RICH `?path=results/ui-redesign/demo-rich/trace.json`: stepper counts `4/4/15/2/3/1/1`;
     3 gate nodes (2 insufficient → loop-back, 1 sufficient); no `<pre>` inside `#replay-workflow`;
     evidence flow shows 15 chips and report C001/D001/M009.
   - SIMPLE `?path=results/ui-redesign/orchestration/demo-simple/trace.json`: review stage skipped
     with `该变体无验证者 · 未审查`; no gate articles fabricated; all other sections full.
   - Scrub the replay: CURRENT stage advances (coordinator → experts → hypotheses → review → … →
     report) and loops back to experts on insufficient-review re-dispatch.
   - 390 × 844: `document.documentElement.scrollWidth <= innerWidth`; every `.orch-*` button
     ≥44 px; keyboard Tab reaches stages/cards/narrative controls; visible focus ring.
   - `prefers-reduced-motion: reduce`: no scroll animation, no transitions.

### Acceptance checklist (maps to the task contract)

- [x] (a) Horizontal stage stepper `协调者 → 专家(并行) → 合并证据 → 假设 → 验证审查 → 定案门 → 报告`
      with per-stage count badges, CURRENT highlight advancing with replay, vertical on mobile.
- [x] (b) Per-round dispatch swimlane with parallel expert cards (role/task_id/question/status/
      timestamp/jump), merge into evidence, verifier gate → loop-back re-dispatch.
- [x] (c) Per-role stats (dispatches/completed/failed/tool calls/evidence produced/findings/
      duration) + structured drilldown; no raw `<pre>` JSON.
- [x] (d) Verifier REVIEW-GATE node (verdict, target hypothesis, cited evidence, requested/optional
      checks status, contradictions), conditional + honest finalize status.
- [x] (e) Evidence flow `agent → evidence(chips) → finding/hypothesis → report reference`.
- [x] (f) Demo-narrative mode: one narration line per chapter, prev/next control, auto expand/
      scroll/highlight.
- [x] Deterministic mapping from existing fields only; round/count/evidence-link rules specified.
- [x] `orchestration.js` builders named + return shapes pinned.
- [x] CSS class contract + JS export contract pinned; hooks preserved (`仅审查建议 · 未调度`,
      `未按此 task_id 调度`, `#replay-workflow`, `data-role`, `.replay-role`).
- [x] Accessibility/interaction/responsive rules; panel under controls, open by default.
- [x] Hard invariants; no forbidden files touched; no new deps.
- [x] Before/after rationale, ASCII wireframes (desktop + mobile), P0/P1/P2.

---

*End of spec. Implement P0 first; the panel becomes the orchestration hero of the replay demo.*

---

## 13. Implementation notes & before/after index

> Status: **implemented, verified (two rounds), reviewed, and integrated on PR #6**
> (`ui/ux-redesign-2026-11`). Presentation layer only — no backend, API, data-structure,
> route, permission or dependency change.

### 13.1 Files changed

| File | Change |
|---|---|
| `src/incident_lens/web/static/js/orchestration.js` | **New** pure view-model + render helpers (`buildStages`, `buildRounds`, `buildRoleStats`, `buildReviewGates`, `buildEvidenceFlow`, `buildNarrative`, `stagesHtml`, `swimlaneHtml`, `roleStatsHtml`, `reviewGateHtml`, `evidenceFlowHtml`, `narrativeHtml`, `statusBadge`, `orchestrationHtml`, `variantVerifierCapability`, `prefixHasVerifier`, `resolveHasVerifier`). No DOM, no `fetch`, no side effects. |
| `src/incident_lens/web/static/js/replay-panels.js` | `workflowHtml(state, selectedRole, bookmarks?, opts?)` now delegates to `orchestrationHtml` (legacy 2-arg call still valid); `metadataHtml(data, opts?)` split into heading vs sunk snapshot; new `bindWorkflowInteractions(panelEl, ctx)` for narrative prev/next + demo highlight; `reviewTimelineHtml` (legacy `#replay-review-panel`) now renders `DIAGNOSIS_ACCEPTED` / `FINALIZE*` as structured cards instead of a raw `<pre>` JSON dump (REVIEW branch unchanged). |
| `src/incident_lens/web/static/js/views.js` | `mountReplay` mounts `#replay-workflow` under the controls (`<details open id="replay-workflow-panel">`), passes `bookmarks` + provider/variant opts to `workflowHtml`, sinks the metadata snapshot to the panel bottom, and re-renders on demo toggle so the deep link `&demo=1` highlights on first paint. |
| `src/incident_lens/web/static/css/app.css` | +850 lines of `orch-*` styling (stepper, swimlane, role grid, gates, evidence flow, narrative), both themes, 390 px-safe, `prefers-reduced-motion`, focus-visible; plus `.replay-review__*` styling for the structured legacy review cards. |
| `docs/ui/orchestration-redesign.md` | This spec (t2) + §13 implementation notes. |
| `docs/ui/orchestration-redesign/*.png` | Post-repair BEFORE/AFTER composites + per-defect evidence crops. |

### 13.2 Before/after index (desktop 1440 · light unless noted)

| What | BEFORE | AFTER (post-repair) |
|---|---|---|
| Panel at step 0 | `r2-after-before-rich-desktop-light-step0.png` | same pair (left/right) |
| First dispatch (round 1, parallel lanes) | `r2-after-before-rich-desktop-light-dispatch.png` | same pair |
| First insufficient review (loop-back) | `r2-after-before-rich-desktop-light-insufficient.png` | same pair |
| Full prefix — all six deliverables | `r2-after-before-rich-desktop-light-last.png` | same pair |
| Dark theme, full prefix | `r2-after-before-rich-desktop-dark-last.png` | same pair |
| Mobile 390, full prefix | `r2-after-before-rich-mobile-light-last.png` | same pair |
| Verifier role drilldown (structured rows, no JSON) | `r2-after-before-rich-desktop-light-role-verifier.png` | same pair |
| Demo narrative (new; no BEFORE equivalent) | `r2-after-before-rich-desktop-dark-demo-narrative.png` | AFTER only |
| SIMPLE degradation (no verifier, no reviews) | `r2-after-before-simple-desktop-light-insufficient-absent.png`, `…-step0.png`, `…-last.png` | same pairs |
| SIMPLE mobile / dark | `r2-after-before-simple-mobile-light-insufficient-absent.png`, `r2-after-before-simple-desktop-dark-last.png` | same pairs |

Per-defect evidence crops (current bytes): `r2-rich-d1-pos0-panel.png`, `r2-rich-d1-pos19-panel.png`,
`r2-simple-d1-pos0-panel.png` (D1 variant-aware review stage), `r2-d2-demo-initial.png` +
`r2-d2-demo-initial-panel.png` (D2 initial demo highlight), `r2-rich-d3-narrative-start-panel.png` +
`r2-simple-d3-narrative-start-panel.png` (D3 counter + synthetic start chapter),
`r2-d4-relation-labels-panel.png` (D4 relation label icon+text).

Full-resolution BEFORE/AFTER trees, capture scripts and machine-readable reports live under the
gitignored `results/ui-redesign/orchestration/` (`before/`, `after/`, `after-r2/`, `pairs.json`,
`after-r2/r2-report.json`, `verification-report.md`).

### 13.3 Repair round (D1–D4) — what changed

| Id | Defect | Fix |
|---|---|---|
| D1 | RICH at prefix 0–19 labelled the review stage `该变体无验证者 · 未审查` although the variant *does* run a verifier. | Variant-level capability (`VERIFIER_VARIANTS` + `variantVerifierCapability` + `resolveHasVerifier`); a real prefix `REVIEW`/verifier role still overrides variant-no. RICH now shows stage `pending` with normal gloss and the gate reads `当前前缀尚无验证审查`; SIMPLE keeps the honest `该变体无验证者 · 未审查`. |
| D2 | `&demo=1` deep link did not apply the auto-highlight until the next seek. | `mountReplay` enables the toggle and re-renders during mount so `bindWorkflowInteractions` sees demo active on the first paint; toggling off clears `.is-highlighted` without collapsing the panel. |
| D3 | Narrative counter used the total chapter count (8) instead of the navigable ones, and had no start chapter. | Counter counts only available chapters (`1 / 7` at start for RICH, `1 / 4`-style for SIMPLE); synthetic `调查开始前` start chapter at position 0; prev/next clamp to available chapters. |
| D4 | 8 inline relation labels (`supports`/`neutral`) had no icon wrapper. | `relationBadge` now emits icon + text wrapper for every relation label (21/21 in the audit), text assertions unchanged. |

### 13.4 Deliberate design decisions (spec now documents the implemented rule)

These were originally written as "deviations" because the first spec draft specified otherwise. The
spec has since been corrected in place (§4.8.1, §4.9 rule 8, §6.4, §6.6, §10); the decisions
themselves are unchanged and remain deliberate:

1. **Verifier availability is variant-level, not prefix-only.** §4.8/§4.9 previously derived
   verifier presence from the replay prefix. The implemented and now-specified rule is
   `VERIFIER_VARIANTS` + `variantVerifierCapability` + `prefixHasVerifier` +
   `resolveHasVerifier(state, opts)` (§4.8.1), with the recorded trace variant as the authoritative
   capability signal, because a verifier-capable trace has simply not reached its first `REVIEW` at
   early positions ("pending" ≠ "this variant has no verifier"). A real prefix `REVIEW` or
   verifier-role event overrides a variant-no; ambiguous/unknown variants fall back to prefix
   evidence. The D1 repair round (§13.3) is the defect this rule fixes.
2. **`aria-current` stays on the actual current stage only.** §6.6 previously asked for
   `aria-current="step"` on the demo-highlighted stage. The implementation keeps `aria-current` on
   exactly one element **inside `#replay-workflow`** (the stage matching the replay position, which
   is what a screen reader should hear as "current") and marks the demo-highlighted stage with
   `.is-highlighted` instead. The 调查时间线 list below the fold keeps its own pre-existing
   `aria-current="step"` on the current-event button (`views.js`, out of scope), so the page-wide
   count is 2 by design — one per landmark.
   This is an intentional accessibility-safer choice: two simultaneous `aria-current` values would
   announce conflicting "current" items. §6.6 and §8.1 now document this behaviour rather than the
   unimplemented alternative.
3. **The legacy `#replay-review-panel` is structured too.** The earlier implementation left
   `DIAGNOSIS_ACCEPTED`/`FINALIZE*` as raw `<pre>` JSON in the legacy timeline because it sits
   outside `#replay-workflow`. It now renders 定案门/终局 cards (badge + kv rows + evidence chips,
   collapsed raw fallback only for unrecognisable shapes), so no panel in the replay demo dumps raw
   JSON by default.

### 13.5 Verification (current bytes)

Bytes verified: `orchestration.js` `985215e9…` (unchanged), `views.js` `db17d9ba…` (unchanged),
`replay-panels.js` `28fd1ec1…` (was `a8fed41f…` at base HEAD before the structured legacy review
cards + robustness pass), `app.css` `36001fe0…` (was `7305b445…` before the `.replay-review__*`
card styling and the `#replay-reviews` 44 px touch-target rule), on branch
`ui/ux-redesign-2026-11` at base HEAD `fea028a` (the working tree on top of that commit; nothing
is committed by this change set).

| Gate | Result |
|---|---|
| Browser sweep, RICH + SIMPLE × 1440/834/390 × light/dark (`after-r2/r2-report.json`) | 0 page errors, 0 console errors, 0 horizontal overflow; stepper `4/4/15/2/3/1/1` + `aria-current`, 3-round swimlane with gate + 2 loop-backs, 5 role stats, **0 `<pre>` inside `#replay-workflow`**, 15-chip evidence flow with report `C001/D001/M009`, narrative prev/next |
| Review round 5 (F7–F10 doc residuals) | F7: the dangling *The `diagnosisCard`/* clause is completed — it now reads "The `diagnosisCard`/`finalizeCard` dispatch — in fact the whole per-event render — is wrapped in `try/catch`". F8: `asIdList` strengthened to drop non-renderable entries — verified `[{}]`, `[{a:{b:1}}]`, `[null]`, `['']` all yield **0 chips** (no `[object Object]`, no blank chip) while `[{evidence_id:'incident_001-C001'}]` yields a normal chip, so the strong claim is now literally true. F9: the absolute claim is replaced by the true narrower rule — the contradiction is prevented only when a blocking-source field is **present** (any present source, including `[]`, renders a count); when none is present (`details: {}`) the card legitimately shows `未记录阻断检查` alongside `定案被阻断`, which is a true statement rather than a contradiction. No real event hits that case (all 12 `FINALIZE_REJECTED` carry `errors`). F10: the in-box `（回放位置，每页恰好一个）` claim replaced with `（回放位置；#replay-workflow 内唯一）`, ASCII box width preserved at exactly 80 display columns and the inner `│` border columns still align. |
| Review round 4 (t5 re-review fixes) | F2 probe matrix: array/scalar/null/undefined/''/object `support_ids` all render a card (no throw) and the object id is flattened for chips; `predicted_observations`/`open_questions` × string/null/''/object/array all render; hostile getter-throwing `root_cause` **and** `review` shapes degrade to the collapsed raw card instead of aborting `draw()`. Live dashboard with a scalar trace: all four panels populated and 116 `[data-seek]` bound with a working jump. F1 copy names the two locations that actually hold the JSON (`#replay-selection` → 原始结构化事件详情, and the 调查时间线 tab's expanded `.tl-body`), both verified in-browser. F3 `errors` string/object/array all render with a correct count, `errors: []` + populated `blocking_checks` prefers the non-empty source, and a blocked card renders a check count whenever any blocking source is present, so the `定案被阻断` + `未记录阻断检查` pair is unreachable in that case (it is shown only when no blocking-source field exists at all, which is a true statement rather than a contradiction). F4 page-wide `aria-current="step"` = 2 (1 in `#replay-workflow`, 1 in the 调查时间线), stated as such. F5 measured 44 px on `#replay-reviews .evidence-chip` at 390/coarse with 0 overflow; the rule is named selector-by-selector. F6 base HEAD `fea028a` with the correct fea028a blob hashes as "was". `node --test` 23/23, ruff PASS, integration trio 20 passed, mock browser PASS, full `pytest -ra` 1180 passed / 2 skipped. |
| Review round 3 (strict-review findings) | F2 scalar list fields render as 1-item chips (116 `[data-seek]` bound, `#replay-reviews`/`#replay-selection`/`#replay-reliability` all populated, jump works); a throwing shape degrades to the collapsed raw card; F1 copy points at `原始结构化事件详情` which really holds `candidate_assessments`; F3 `errors: "Unknown hypothesis"` renders 1 check with no "none" copy, `errors: []` renders `0 条（记录为空）`, absent source keeps `未记录阻断检查`; F5 `#replay-reviews .evidence-chip` computes `min-height: 44px` and measures 44 px at 390/coarse (overflow 0); F4 page-wide `aria-current="step"` = 2 (1 in `#replay-workflow`, 1 in the 调查时间线) — docs scoped accordingly; F6 base HEAD `fea028a`. `npm test` 23/23, ruff PASS, integration trio 20 passed, mock browser PASS, full `pytest -ra` 1180 passed / 2 skipped. |
| Legacy `#replay-review-panel` (robustness) | Scalar-typed list fields (`support_ids: "incident_001-C001"`) render as a 1-item chip row instead of throwing; a throwing/unexpected shape renders the collapsed raw card for that event only; `errors: "Unknown hypothesis"` renders as one blocking check; `errors: []` renders `0 条（记录为空）`; no `errors`/`checks` field keeps `未记录阻断检查`. Verified with synthetic fixtures (node) — all five cases pass and the panel keeps rendering. |
| Legacy `#replay-review-panel` (structured cards) | `reviewTimelineHtml` renders **no `<pre>` in the default view** (Playwright 1440 light/dark + 390: 0 expanded `<details>`; the only `<pre>`s are the pre-existing collapsed REVIEW contradictions, 2 at full RICH prefix). `DIAGNOSIS_ACCEPTED` → `诊断已通过` card: culprit service `backend`, failure-mode headline `backend_pool_config_regression`, `SUPPORTED` badge, 3 `support_ids` chips + 3 `supporting_evidence_ids` chips + 0 `against_ids`, predicted-observation list, `降级调用 degraded_call_ids：0`, truncated `hyp-2354bf4d…` with the full 68-char id in `title`; `FINALIZE*` → kv summary (action/reason/blocking checks/hashes, `定案被阻断` for REJECTED); raw JSON only inside a collapsed `<details>` for unrecognisable shapes. REVIEW branch strings (`未按此 task_id 调度`) unchanged; `#replay-reviews article` count = REVIEW count. |
| Accessibility probe (`after/a11y-report.json`) | focus-visible 2px, tab order reaches stages/cards/narrative, reduced motion 0 s, status = icon + text (never colour-only) |
| `ruff check src tests scripts` (Node 22) | PASS |
| `npm test` (Node 22) | 23/23 pass |
| Integration trio | 20 passed |
| `scripts/run_mock_browser.py` | PASS — desktop/mobile, playback, prefix report, inspector provenance, saved missing/failure, no runtime errors, no `/api/run` |
| Full `pytest -ra` | 1180 passed, 2 skipped |
| CI test hooks | `仅审查建议 · 未调度` and `未按此 task_id 调度` still emitted; `workflowHtml`/`reviewTimelineHtml` exports unchanged; `#replay-workflow`, `data-role`, `.replay-role`, `#replay-position`, `#run-tab-panel`, `#replay-play`, `#replay-speed`, `[data-step]`, `[data-ev]`, `#drawer*` and tab names intact |

**Environmental flake (not a regression):** `test_failure_accounting[wall_timeout]` failed once while a
Playwright capture was running concurrently (50 ms wall-timeout budget vs a 0.2 s mock sleep — CPU
starvation). It passed on 3 isolated re-runs and 5/5 parametrized runs, and the clean full run is
1180 passed / 2 skipped. No `.py` file is in this change set.

**Known non-blocking items for a future pass:** the narrative chapter list intentionally keeps
unavailable bookmarks visible but disabled (`… · 未记录`) rather than hiding them. (The legacy
`#replay-review-panel` raw-JSON dump is no longer an open item: `DIAGNOSIS_ACCEPTED`/`FINALIZE*`
now render as structured cards — see §6.3 export contract and §13.4 item 3.)
