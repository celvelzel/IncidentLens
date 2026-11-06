# IncidentLens Console — Design Requirements & System Spec (v2)

**Task:** `t2` — design requirements & system spec for the IncidentLens web console redesign.
**Branch:** `ui/ux-redesign-2026-11` (off `origin/main` @ `424a4ae`). **Never merged by this work.**
**Surface:** the vanilla-JS SPA served by `src/incident_lens/web/` (routes `#/`, `#/investigate`,
`#/run?path=…`, `#/library`, `#/system`, `#/evaluation`).
**Mode:** **Operate** (impeccable). This is an evidence-driven incident *console* for a category-fluent
SRE; success is "trust it in seconds", not persuasion.
**Status:** implementation-ready. Two implementers (impl-core, impl-pages) can build in parallel on
disjoint files using only this document. Section 8 is the ownership/split contract; every token,
class name, helper API and preserved test hook an implementer needs is enumerated there and in §3–§7.

This document is **synthesis-based**. It resolves every finding in
`results/ui-redesign/audit.md` and every "before" screenshot in `results/ui-redesign/before/`
against the staged design skills under `.design-skills/`. Where a skill rule conflicts with the
Chinese-language Operate reality and the brand, the brief (`../.design-skills/BRIEF.md`) and product
reality win — every such override is recorded in §1.

**Reading order for implementers:** §1 (why) → §2 (don't break) → §3 (tokens) → §4 (components) →
§5 (pages) → §6 (responsive) → §7 (a11y) → §8 (your file list + migration maps) → §9 (how it is judged).

---

## Table of contents

0. [How to use / parallel ownership map](#0-how-to-use--parallel-ownership-map)
1. [Skill synthesis & decision log (ADOPTED vs DROPPED)](#1-skill-synthesis--decision-log-adopted-vs-dropped)
2. [Hard invariants (business + test coupling)](#2-hard-invariants-business--test-coupling)
3. [Design tokens (the closed system)](#3-design-tokens-the-closed-system)
4. [Component contracts & full state matrix](#4-component-contracts--full-state-matrix)
5. [Page-by-page layout & visual hierarchy](#5-page-by-page-layout--visual-hierarchy)
6. [Structural responsive plan](#6-structural-responsive-plan)
7. [Accessibility & interaction spec](#7-accessibility--interaction-spec)
8. [Implementation split, file ownership & migration maps](#8-implementation-split-file-ownership--migration-maps)
9. [Verification & acceptance checklist](#9-verification--acceptance-checklist)
- [Appendix A — Exact preserved test hooks](#appendix-a--exact-preserved-test-hooks)
- [Appendix B — Full CSS custom-property index](#appendix-b--full-css-custom-property-index)

---

## 0. How to use / parallel ownership map

The implementation is split across two disjoint file sets so two people can work simultaneously
without merge conflicts. **Anything a side consumes from the other side is a fixed contract in this
document — do not improvise names, tokens, or helper signatures.**

| Side | Owns (may edit) | Must NOT edit |
|---|---|---|
| **impl-core** | `src/incident_lens/web/static/css/tokens.css`, `…/css/core.css`, `…/static/index.html`, `…/static/js/components.js` | app.css, institutional.css, views.js, knowledge.js, replay-panels.js, app.js, api.js, replay.js, anything under `tests/` |
| **impl-pages** | `src/incident_lens/web/static/css/app.css`, `…/css/institutional.css`, `…/js/views.js`, `…/js/knowledge.js`, `…/js/replay-panels.js` | tokens.css, core.css, index.html, components.js, app.js, api.js, replay.js, anything under `tests/` |
| **integration (stage after both land)** | `…/js/app.js` only for the view-level error boundary (§7.7) and any final cross-file wiring | business logic in server.py/api.js/replay.js |

**Shared contract surfaces** (both sides touch different files but must agree):

1. **Design tokens** (§3): impl-core *writes* them in `tokens.css`; impl-pages *reads* them in
   app.css/institutional.css. Token names in §3 are law.
2. **Component primitives** (§4): impl-core *writes* `.btn/.input/.select/.card/.table/.tabs/.badge/
   .toast/.drawer/.empty/.skeleton/.kpi/.alert/.chip/.segmented` in `core.css`; impl-pages *emits the
   class names* in views.js/knowledge.js/replay-panels.js. Class names + state attributes in §4 are law.
3. **JS helpers** (§4.16): impl-core *writes* `badge/emptyState/skeleton*/loadingBlock/toast/openDrawer/
   evidenceChips/…` in `components.js`; impl-pages *calls* them. Signatures + returned class names in
   §4.16 are law.
4. **Shell DOM** (§4.12): impl-core writes `index.html`; impl-pages styles `.app-shell/.sidebar/.topbar/
   .nav-item/.brand-*/.menu-btn/.scrim` in app.css. The shell class contract in §4.12 is law. `app.js`
   selects these exact nodes and is **not edited** by either side — the ids/classes it queries must survive.

**Golden rule:** if you think you need a new CSS custom property or a new component class, it must
already appear in §3 or §4; if it does not, use an existing token/class. Do not invent ad-hoc values.
(Where this spec says "map X→Y", that is a deliberate decision, not a suggestion.)

---

## 1. Skill synthesis & decision log (ADOPTED vs DROPPED)

### 1.1 What this product is, and the mode decision

IncidentLens is an **Operate** surface: an evidence-driven incident investigation console. A
category-fluent operator must read *state, evidence, and next action* in seconds. Per
`impeccable` **Operate** mode and `impeccable/craft-floor.md`, ambition here shows as **precision and
restraint**, not spectacle; familiar patterns earn their place; the tool disappears into the task.

The "before" screenshots confirm the diagnosis in `results/ui-redesign/audit.md`: a marketing/editorial
layer (hero with radial gradient, serif display, eyebrow kickers, numbered stage rails, "three equal
cards") was bolted onto an operator console and now fights the mode. The redesign **subtracts the
spectacle**, it does not repaint the brand. The incumbent palette and the two-layer token *structure*
are an asset and are kept.

### 1.2 Skill-by-skill synthesis

| Skill (file) | What we ADOPT | What we DROP / override (and why) |
|---|---|---|
| **impeccable — `SKILL.md`** | Modes; "Operate ambition = precision + restraint"; refinement-preserves vs redesign-replaces semantics (this is a *refinement/redesign inside the incumbent identity*, not a new visual world — keep product truth, content, function, brand); verify by looking at the rendered result at ship sizes; craft-floor is a floor not a ceiling. | Nothing material. |
| **impeccable — `mode-operate.md`** | The world lends only **type, palette, density, one signature move**; navigation and controls stay standard web components. State-first comps; realistic data; state colours only where they carry meaning. | *No* "world costume" (terminal bezel, ruled ledger paper): the signature move here is **restrained institutional chrome + evidence/citation treatment**, not a themed interface language. |
| **impeccable — `craft-floor.md`** | Contrast floors (4.5:1 body/placeholder, 3:1 large/UI parts); **soft offset shadows, no zero-offset glow halos**; spacing rhythm (more above a heading than below); balanced headings; typography floor; **theme browser surfaces** (selection, caret, scrollbar, focus ring, underline offset, tabular numerals); full state set; copy names problem+recovery. **Bans we enforce:** eyebrow/kicker above a heading (absolute ban); gradient text; glass/blur as decoration; single-side `border-left/right` >1px on cards/callouts; hard offset shadows; numbered section markers *unless the sequence itself carries information*; system display face as an own-world display voice; glyph/emoji as icons. | **Override — "source and self-host a display face":** dropped. The corpus is largely Chinese and offline/browser CI **aborts cross-origin requests**; we use one refined **system CJK sans stack** and tune scale/weight/tracking instead (BRIEF §Typography). **Override — "system display face is a failure":** in an Operate Chinese console the system CJK sans *is* the correct face; there is no own-world display voice to source. |
| **impeccable — `redesign-existing-projects.SKILL.md`** | The full **audit axes** (typography, color/surfaces, layout, interactivity/states, content, component patterns, code quality) and the **fix-priority order** (font/scale → color/surface cleanup → states → layout/spacing → motion → components → loading/empty/error → copy → type polish). "Work with the existing stack; do not migrate frameworks." "Never invent a design value." | **DROP its Design Values as literal values:** Geist/Manrope/Poppins webfonts (→ system CJK sans), the **hero-heading text gradient** (→ no gradients at all), **scroll-reveal choreography** (→ Operate: no page-load reveals), pure-black dark ramp. All of these are overridden by the BRIEF and Operate mode. |
| **landing-page-design.SKILL.md** | The **type scale table, spacing table, corner-radius + nested-radius formula, named text styles (Heading/Title/Body/Button/Caption), copy rules (`…`, curly quotes, no orphaned words via `text-wrap`), and the full state set**. The 390px "no horizontal overflow, buttons keep their text inside" check is adopted as a hard gate. | **DROP the entire landing-page *structure*:** hero-with-CTA-above-the-fold, benefits/how-it-works/FAQ/final-CTA order, the **mandatory tagline word-reveal section**, scroll reveals, floating glass nav, gradient hero heading, webfonts. Wrong mode for Operate; BRIEF explicitly defers them. The *visual system* (Part B) is adopted minus gradients/webfonts. |
| **anthropic-frontend-design.SKILL.md** | One family (not display+body pairing); **numbering only when content is genuinely a sequence** (→ System design pipeline keeps step order; Overview/Evaluation decorative numbering removed); no eyebrow/kickers; no single-accented-word headlines; structural devices must encode real information; active-voice copy; restraint ("remove one accessory"); the **slop-list used as an anti-reference** (no cream+terracotta, no dark+acid-green, no SaaS-card kit, no `A · B · C` meta strings). | DROP "hero is the first thing / open with the most characteristic thing" — wrong mode; in Operate the shell + current state lead. |
| **vercel-web-interface-guidelines** (command + skill) | Accessibility: `aria-label` on icon-only buttons, decorative icons `aria-hidden="true"`, `aria-live` for toasts, semantic HTML, headings hierarchy, skip link. Focus: **`:focus-visible`, never `outline:none` without replacement**. Animation: **never `transition: all`; list properties; animate transform/opacity; respect reduced-motion**. Typography: `…`, curly quotes, NBSP for units, **`tabular-nums` on number columns, `text-wrap: balance/pretty`**. Content handling: **`min-w-0` on flex children, truncate/line-clamp, handle empty**. Touch: **`overscroll-behavior: contain`**, 44px targets, `touch-action: manipulation`. Dark mode: `color-scheme`, native `<select>` explicit `background-color`/`color`. Locale: `Intl.*` (already used — keep). | **Override "Title Case for headings/buttons"**: BRIEF specifies **sentence case** and the UI is Chinese; Title Case does not apply to CJK. Use sentence case where Latin string fragments appear. |
| **figma-designer.SKILL.md** | The **two-layer token structure and naming discipline** (Core palette → Color System aliases; groups Border/Surface/Action/Text/Icon/Overlay), the **spacing scale**, **radius scale + nested-radius formula**, the **Heading/Title/Body/Button/Caption text-style groups on a fixed scale**, interactive-component **state variants**, 44px touch targets, contrast floors, "borders all around or not at all", "one typeface, no italics, no weights above bold", "hero/lead capped width, no eyebrow by default". | **DROP all Figma tooling and its artifacts** (variables UI, modes, components, Foundations frames). **DROP** the hero-text gradient exception, Geist Mono for data, Phosphor/Solar/Iconamoon icon *libraries* (we keep the existing authored inline-SVG icon set at one stroke weight), and Figma's "5 types × 5 states = 25 variants" combinatorial requirement (kept as a *conceptual* state matrix, not literal component variants). |

### 1.3 Concrete decisions (the log the acceptance asks for)

| # | Decision | ADOPTED | DROPPED | Why |
|---|---|---|---|---|
| D1 | Surface mode | **Operate** (task-first console) | Landing-page structure (hero, FAQ, testimonials, tagline word-reveal, scroll reveals) | Operators are in a task; spectacle erodes "trust in seconds". BRIEF §What-this-product-is. |
| D2 | Typography families | **One** refined system CJK sans stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif` | Two families (serif display + sans body); any webfont | Chinese corpus; offline/browser CI aborts cross-origin → a Latin webfont barely helps and breaks tests. Serif Chinese fallbacks (Songti/SimSun) render inconsistently and read as marketing. |
| D3 | Type sizing | **Fixed rem scale, closed step list** (~1.125–1.2 product ratio), named styles | `clamp()` / fluid type; off-scale px (9.5/10.5/11/13.5/15/17/22/26/30/34/35/38) | Users view at consistent DPI in a console; a fluid h1 looks worse in a sidebar. Operate/SKILL: fixed rem scale. |
| D4 | Weights | 400 / 500 / 550 / 600 / 650 / 700 (cap at **bold = 700**) | 720, 750, 800, 900, italics | "No weights above bold", no italics (craft-floor, redesign). |
| D5 | Brand identity | **Keep brand red `#9a0907`** and **navy `#003070`** (dark: `#d0574e` / `#86a9e0`); light theme **default** (projectors), dark first-class | Generic dark + acid-green "AI" palette; purple/blue gradient; SaaS-card kit | Institutional/editorial identity is the product. BRIEF §Color; anthropic slop-list. |
| D6 | Color model | **Two layers:** raw `--core-*` palette → semantic surface/border/text/icon/action/state tokens | Single flat token blob; role-named-by-color tokens | figma-designer token structure; enables a rebrand by editing only Layer 1. |
| D7 | Accent discipline | **One interactive accent** (navy/blue) for primary action, current selection, state; **brand red** for institutional chrome/identity only | Accent as decoration; red as a status color | Operate color rules; brief. |
| D8 | Surfaces | **Flat** surfaces; depth = tinted soft **offset** shadows; a second neutral layer for sidebar/toolbar/panel | Background gradients (overview hero radial, report hero linear), gradient text, glow halos | craft-floor bans; audit §1.2/§1.13. |
| D9 | Borders | **All around or none**; full 1px borders; row dividers = 1px hairline | Single-side accent stripes (`border-left:4px` hero, `3px` decision/finding/plan-only/provenance, `border-top:2px` invariant) | craft-floor ban; audit §1.7. |
| D10 | Numbered rails | Keep numbering **only where the sequence is real information** (System design pipeline step order, Gates order) restyled as compact neutral step labels | Decorative numbered kickers (`.pipeline-stage::before` on Overview dead CSS; `.stage-n`/`.gate-n` as brand-red display; Evaluation `row-tag` display) | anthropic: numbering only for real sequences; craft-floor "unless the sequence carries information". |
| D11 | Motion | **150–250 ms** state-driven transitions; `--ease: cubic-bezier(0.22,1,0.36,1)`; animate transform/opacity; explicit property lists; `prefers-reduced-motion` path | Page-load choreography, section stagger, scroll reveals, `transition: all`, `ease`/`linear` defaults | Operate: users in flow; craft-floor motion floor; vercel animation rules. |
| D12 | Loading | **Layout-shaped skeletons** (table/list/KPI/run-shaped); inline status text | Centered spinners in content; generic grey bars of arbitrary height | Operate/SKILL: skeleton states; audit §3.1. |
| D13 | Empty / error | Composed **getting-started** empty states; inline, specific errors naming problem + next step | Blank panels; `window.alert()`; wrong "no match" copy for a truly empty dataset | redesign/landing B9; audit §3.2/§3.3. |
| D14 | Responsive | **Structural** (collapse sidebar → drawer; responsive tables; breakpoint columns); verify **390** | Fluid type as the responsive strategy; hiding core functionality on mobile | Operate layout; adapt.md; landing B10 (390). |
| D15 | Icons | Existing **authored inline SVG**, one stroke weight, `aria-hidden="true"` when decorative; icon-only buttons get `aria-label` | Icon glyphs/emoji; library swap; material symbols | craft-floor "no glyph icons"; vercel a11y. |
| D16 | Dependencies | **None new.** Vanilla CSS + existing ES modules only | Any runtime dep, JS framework, CSS preprocessor, build step, webfont loader | Hard invariant (BRIEF team contract). |
| D17 | Theme surfaces | Theme selection, caret, scrollbar, focus ring, underline offset, tabular numerals from the palette | Browser-default selection/caret/scrollbar (leave to default) | craft-floor "browser surfaces". |
| D18 | Focus ring | `:focus-visible` **outline ring** (2px, 2px offset) that does **not** reset `border-radius` | Global `box-shadow` ring that also sets `border-radius: var(--radius-sm)` on every element | Audit §4.3 — the global `border-radius` reshapes pills/chips. |
| D19 | Copy language | Sentence case, active voice, specific labels/errors; keep all product strings; `…` not `...`; curly quotes; NBSP for units | Title Case (does not apply to CJK); filler marketing words | BRIEF copy; vercel/landing. |
| D20 | Scope of change | **CSS-first**; minimal, event/state-safe markup changes only. No business-logic/API/route/permission/data changes. | Any behavioural refactor, new route, new API, data-shape change, `tests/` edit | Hard invariant. |

---

## 2. Hard invariants (business + test coupling)

These are **non-negotiable**. Violating any of them fails the task even if it looks better.

### 2.1 Business / behavioural invariants

- **No changes** to business logic, HTTP API, database, data structures, route behaviour, or
  permissions. `src/incident_lens/web/server.py`, `static/js/api.js`, `static/js/replay.js` and the
  hash-router in `static/js/app.js` must remain **functionally identical**. Do not add/remove routes,
  query params, fetch calls, or state semantics.
- **No feature removal; no change to user flows or operation semantics.** Every screen keeps its
  content and actions. You may restructure *presentation*; you may not remove a field, action, or
  piece of information.
- **CSS-first.** Prefer CSS. Markup changes are allowed only when they are *event/state-safe*: adding
  wrapper classes/containers for layout or replacing a non-semantic container with a semantic one,
  **without** changing ids that JS queries, `data-*` that handlers read, ARIA wiring, or behaviour.
- **No new dependencies. No changes under `tests/`.**

### 2.2 Test coupling — preserve every asserted hook

These are read from `tests/web/browser.cjs` (run in CI via `scripts/run_mock_browser.py`),
`tests/integration/test_v12_ui.py`, and `tests/web/*.test.mjs`. **Appendix A is the exhaustive list.**
Highlights that constrain markup:

- **CI browser run (`browser.cjs`, 1440×1000 then 390×844):**
  - `#replay-position` exists and updates; at 390×844 `document.documentElement.scrollWidth <= window.innerWidth`
    **and** every `.replay-controls button` has `getBoundingClientRect().right <= window.innerWidth`.
  - Tabs are found by accessible role/name: `根因报告`, `证据登记`, `调查时间线` — keep them as
    `role="tab"` buttons with those names.
  - `#run-tab-panel` innerText contains `not recorded` (empty-report state) and, at last step,
    `backend_pool_config_regression`; `#drawer-body` contains `已记录查询`; `#replay-play` text toggles
    `播放`/`暂停`; `[data-step=next|first|last]`, `#replay-speed`, `#drawer`, `#drawer-close`, `[data-ev]`
    work as today.
- **`test_v12_ui.py`** shells out to `workflowReportHtml()` and asserts it emits `停止确认：已完成`,
  `终止结果`, `PLAN_ONLY`, `PLAN_READY`, `FINISHED`, the evidence id `e1`, the attempt id `a1`, the plan
  texts (`rollback`, `precondition`), escapes `<script>` as `&lt;script&gt;`, and returns **exactly `''`**
  for `{report:{status:'RESOLVED'}}` (legacy empty). Class names `report-section`, `workflow-result`,
  `workflow-status-grid`, `workflow-plan-grid`, `workflow-plan-section`, `plan-only-note` are load-bearing
  (the test checks text, not classes — but keep them stable to avoid drift).
- **`provisional-report.test.mjs`** asserts `renderReport()` output contains `较可能（未确认）`,
  `待确认的解释`, `关键缺口`, `建议下一步`, `可选补充（不阻止作答）`, `data-evidence-id="E1"`, escapes
  `<img>`; and `evidenceDrawerHtml()` contains `用于待确认解释，尚未支持最终诊断`.
- **`replay-demo.test.mjs`** asserts `metadataHtml()` contains `PROVIDER UNKNOWN`, `SOURCE DRIFT`,
  `独立最终产物`, escapes `<img>`; `workflowHtml()` contains `仅审查建议 · 未调度`;
  `reviewTimelineHtml()` contains `未按此 task_id 调度`.
- **`replay.test.mjs`** asserts `evidenceChips()`/`evidenceDrawerHtml()` escaping and disabled behaviour.

> **Note on `tests/web/browser-real.cjs`:** this is a **v16 offline acceptance script, not part of CI**
> (CI runs only `browser.cjs`, `pytest`, `ruff`). It is *not* in the preservation set named by the
> contract. It currently reads `.hero-kicker` text on the run-detail replay heading. Since we remove the
> marketing eyebrow `.hero-kicker`, that script would need its selector updated if it is ever run — but
> `tests/` must not be edited, so treat it as out of scope and do not preserve `.hero-kicker` for its
> sake. (If a stage later needs it, the *run-detail* provider string can be exposed as a status badge;
> never reintroduce a heading eyebrow.) See §5.3 and Appendix A.4.

---

## 3. Design tokens (the closed system)

impl-core writes these into `tokens.css`. Everything below is a **closed list**: implementers may only
use these names and values. Root font size is `16px` (`html { font-size: 16px }`) so `rem` is exact.

### 3.1 Two-layer color model

**Layer 1 — raw core palette (`--core-*`).** Theme-independent raw hexes. Brand and neutrals are the
institutional identity; state palettes are semantic. Implementers **never** use `--core-*` directly in
components — only Layer 2 aliases. (Rule from figma-designer: "Bind designs to Color System tokens only,
never to Core Colors directly.")

| Group | Token | Hex | Notes |
|---|---|---|---|
| Brand red | `--core-red-700` | `#9a0907` | PolyU brand red (light chrome). 8.7:1 on white. |
| Brand red (dark) | `--core-red-300` | `#d0574e` | brand red for dark chrome. 4.7:1 on `#0e0e13`. |
| Brand red soft | `--core-red-50` | `#f7e9e8` | tinted wash for light chrome rules. |
| Navy | `--core-navy-800` | `#003070` | brand navy = light interactive accent. 12.7:1 on white. |
| Navy strong | `--core-navy-900` | `#00224f` | hover/pressed. |
| Navy (dark) | `--core-navy-300` | `#86a9e0` | dark interactive accent. 8.0:1 on `#0e0e13`. |
| Navy light | `--core-navy-350` | `#aac6ee` | dark accent-hover. |
| Neutral | `--core-neutral-0` | `#ffffff` | |
| | `--core-neutral-25` | `#f7f7f9` | light secondary panel |
| | `--core-neutral-50` | `#f6f6f8` | light app ground |
| | `--core-neutral-75` | `#f1f1f4` | light inset |
| | `--core-neutral-100` | `#e8e9ef` | light dividers / brand-light |
| | `--core-neutral-200` | `#d5d5dd` | |
| | `--core-neutral-300` | `#b9b9c2` | |
| | `--core-neutral-400` | `#90909d` | dark text-3 |
| | `--core-neutral-450` | `#80808b` | |
| | `--core-neutral-500` | `#666673` | light text-3 (5.7:1) |
| | `--core-neutral-600` | `#4c4c57` | light text-2 (8.5:1) |
| | `--core-neutral-700` | `#2b2b33` | |
| | `--core-neutral-800` | `#1f1f27` | |
| | `--core-neutral-850` | `#17171e` | light text-1 / dark overlay |
| | `--core-neutral-900` | `#131318` | dark raised |
| | `--core-neutral-950` | `#0e0e13` | dark surface |
| | `--core-neutral-1000` | `#0b0b0f` | dark inset |
| | `--core-neutral-1050` | `#09090c` | dark app ground |
| Green (success) | `--core-green-600` / `--core-green-300` | `#087b4d` / `#3dd68c` | light / dark; 5.3:1 / 10.3:1 |
| Amber (warning) | `--core-amber-700` / `--core-amber-300` | `#a85f06` / `#f5b93d` | light / dark; **4.9:1** / 10.9:1 |
| Red (danger) | `--core-danger-600` / `--core-danger-300` | `#d23b3f` / `#f47174` | light / dark; 4.7:1 / 6.8:1 |
| Blue (info) | `--core-blue-700` / `--core-blue-300` | `#1f6fd6` / `#5eb0f6` | light / dark; 4.9:1 / 8.3:1 |

> **Deliberate change vs. baseline:** light `--warning` moves `#b26a08` → **`#a85f06`**, because the
> old value is only **4.24:1** on white (fails 4.5:1 for the small badge/caption text it colours).
> `#a85f06` is 4.88:1 on white and 4.52:1 on `#f6f6f8`. Dark warning `#f5b93d` passes (10.9:1).

**Layer 2 — semantic tokens (Light + Dark).** Every value is an *alias* of a core shade. Components bind
only to these. The table is the single source of truth; contrast is measured against the surface it sits
on (`--bg-surface` unless noted).

**Surface (role: background / panel / state)**

| Token | Light (alias → hex) | Dark (alias → hex) |
|---|---|---|
| `--bg-app` | neutral-50 `#f6f6f8` | neutral-1050 `#09090c` |
| `--bg-surface` | neutral-0 `#ffffff` | neutral-950 `#0e0e13` |
| `--bg-raised` | neutral-0 `#ffffff` | neutral-900 `#131318` |
| `--bg-overlay` | neutral-0 `#ffffff` | `#17171e` |
| `--bg-inset` | neutral-75 `#f1f1f4` | neutral-1000 `#0b0b0f` |
| `--bg-hover` | `rgba(23,23,30,0.045)` | `rgba(255,255,255,0.045)` |
| `--bg-active` | `rgba(23,23,30,0.08)` | `rgba(255,255,255,0.08)` |
| `--surface-2` | neutral-25 `#f7f7f9` | `#121217` |
| `--bg-scrim` | `rgba(9,9,12,0.44)` | `rgba(0,0,0,0.62)` |

> `--surface-2` **fixes the undefined token** used by `.plan-only-note` (`app.css:1008`). It is a subtle
> secondary panel, one step off `--bg-surface`; it must not be used as a text background for body copy.
> (Dark `--bg-overlay` and `--surface-2` are the only surface hexes not on the neutral ramp; keep them.)

**Border (role: separators / control boundaries)**

| Token | Light | Dark | Contrast / use |
|---|---|---|---|
| `--border-subtle` | `rgba(23,23,30,0.07)` | `rgba(255,255,255,0.06)` | decorative row/panel separators (no ratio requirement) |
| `--border` | `rgba(23,23,30,0.12)` | `rgba(255,255,255,0.10)` | default card/table borders (decorative) |
| `--border-strong` | `rgba(23,23,30,0.22)` | `rgba(255,255,255,0.18)` | hover/emphasis |
| `--border-control` | `#8a8a96` | `#6f6f7a` | **form-control / checkbox / radio boundary ≥3:1** (3.4:1 on white; 3.9:1 on `#0e0e13`) |

**Text (role: type colour)**

| Token | Light | Dark | Contrast |
|---|---|---|---|
| `--text-1` | neutral-850 `#17171e` | `#f2f2f5` | 17.8:1 / 17.2:1 |
| `--text-2` | neutral-600 `#4c4c57` | `#a3a3af` | 8.5:1 / 7.7:1 |
| `--text-3` | neutral-500 `#666673` | neutral-400 `#90909d` | 5.7:1 / 6.1:1 (caption ≥12px only) |
| `--text-inverse` | `#ffffff` | `#09090c` | on `--accent` (12.7:1 / 8.0:1) |
| `--text-link` | `--accent` | `--accent` | 12.7:1 / 8.0:1 |

**Icon (role: icons / glyph strokes)** — separate from text so icon scopes are explicit.

| Token | Light | Dark |
|---|---|---|
| `--icon-1` | `#17171e` | `#f2f2f5` |
| `--icon-2` | `#4c4c57` | `#a3a3af` |
| `--icon-3` | `#666673` | `#90909d` |

**Action (role: interactive fills/labels)** — aliases of the accent + brand systems.

| Token | Light | Dark |
|---|---|---|
| `--accent` (= `--action-primary`) | navy-800 `#003070` | navy-300 `#86a9e0` |
| `--accent-strong` (= `-hover`) | navy-900 `#00224f` | navy-350 `#aac6ee` |
| `--accent-active` (= `-pressed`) | `#001b3f` | `#c3d7f5` |
| `--accent-contrast` | `#ffffff` | `#06101f` |
| `--accent-soft` | `rgba(0,48,112,0.07)` | `rgba(134,169,224,0.14)` |
| `--accent-border` | `rgba(0,48,112,0.26)` | `rgba(134,169,224,0.36)` |
| `--action-disabled-bg` | `rgba(23,23,30,0.05)` | `rgba(255,255,255,0.06)` |
| `--action-disabled-text` | `#8a8a96` | `#6f6f7a` |
| `--brand-red` (chrome only) | `#9a0907` | `#d0574e` |
| `--brand-red-soft` | `rgba(154,9,7,0.07)` | `rgba(208,87,78,0.14)` |
| `--brand-navy` | `#003070` | `#86a9e0` |
| `--brand-light` | `#e8e9ef` | `#22232a` |

**State (role: semantic feedback)** — each has base + soft + border; base must pass 4.5:1 as text.

| Token | Light | Dark | Base contrast |
|---|---|---|---|
| `--success` | green-600 `#087b4d` | green-300 `#3dd68c` | 5.3 / 10.3 |
| `--success-soft` | `rgba(8,123,77,0.10)` | `rgba(61,214,140,0.12)` | |
| `--success-border` | `rgba(8,123,77,0.30)` | `rgba(61,214,140,0.32)` | |
| `--warning` | amber-700 `#a85f06` | amber-300 `#f5b93d` | 4.9 / 10.9 |
| `--warning-soft` | `rgba(168,95,6,0.10)` | `rgba(245,185,61,0.12)` | |
| `--warning-border` | `rgba(168,95,6,0.30)` | `rgba(245,185,61,0.32)` | |
| `--danger` | danger-600 `#d23b3f` | danger-300 `#f47174` | 4.7 / 6.8 |
| `--danger-soft` | `rgba(210,59,63,0.09)` | `rgba(244,113,116,0.12)` | |
| `--danger-border` | `rgba(210,59,63,0.30)` | `rgba(244,113,116,0.34)` | |
| `--info` | blue-700 `#1f6fd6` | blue-300 `#5eb0f6` | 4.9 / 8.3 |
| `--info-soft` | `rgba(31,111,214,0.09)` | `rgba(94,176,246,0.12)` | |
| `--info-border` | `rgba(31,111,214,0.30)` | `rgba(94,176,246,0.32)` | |
| `--neutral-soft` | `rgba(76,76,87,0.09)` | `rgba(163,163,175,0.12)` | |
| `--neutral-border` | `rgba(76,76,87,0.26)` | `rgba(163,163,175,0.30)` | |

**Misc surfaces:** `--code-bg` (light `rgba(23,23,30,0.05)`, dark `rgba(255,255,255,0.05)`),
`--scroll-thumb` (light `rgba(23,23,30,0.18)`, dark `rgba(255,255,255,0.14)`),
`--selection-bg` (= `--accent-soft`), `--caret-color` (= `--accent`),
`--focus-ring-color` (= `--accent`).

### 3.2 Type scale — fixed rem, closed step list

Root `16px`. **No `clamp()`, no off-scale px.** Off-scale values snap down to the nearest step (with a
12px legibility floor). `--text-*` names are retained for compatibility but are redefined on the closed
scale below.

| Token | rem | px | Paired line-height | Typical use |
|---|---|---|---|---|
| `--text-2xs` | 0.75rem | 12 | 1.4 | Caption micro / badges / captions (was 9.5–11.5px) |
| `--text-xs` | 0.8125rem | 13 | 1.45 | Caption / meta |
| `--text-sm` | 0.875rem | 14 | 1.55 | Body small / table cells / button-sm |
| `--text-base` | 0.9375rem | 15 | 1.6 | Body (default) |
| `--text-md` | 1rem | 16 | 1.6 | Body large / title-3 / button-md |
| `--text-lg` | 1.125rem | 18 | 1.5 | Title-2 / card title |
| `--text-xl` | 1.25rem | 20 | 1.45 | Title-1 / heading-6 |
| `--text-2xl` | 1.5rem | 24 | 1.35 | Heading-5 |
| `--text-3xl` | 1.75rem | 28 | 1.25 | Heading-4 |
| `--text-4xl` | 2rem | 32 | 1.2 | Heading-3 |
| `--text-5xl` | 2.5rem | 40 | 1.1 | Heading-1/2 (page titles) |

**Line-height tokens:** `--leading-tight: 1.2`, `--leading-snug: 1.4`, `--leading-normal: 1.6`,
`--leading-relaxed: 1.75`.
**Tracking tokens:** `--tracking-tight: -0.02em` (large headings only, never below `-0.04em`),
`--tracking-normal: 0`, `--tracking-wide: 0.02em` (Latin micro-labels only — **never on CJK**).

**Named styles** (define once as reusable classes in `core.css`; named styles are the single source of
truth — do not restate loose size+weight on elements):

| Named style class | Scale step | Weight | Use |
|---|---|---|---|
| `.type-heading-1` | `--text-5xl` 40 | 700 | Page hero/lead (overview/system/evaluation H1) |
| `.type-heading-2` | `--text-4xl` 32 | 700 | Standard page title |
| `.type-heading-3` | `--text-3xl` 28 | 700 | Large section |
| `.type-heading-4` | `--text-2xl` 24 | 650 | Section |
| `.type-title-1` | `--text-xl` 20 | 650 | Card title (large) |
| `.type-title-2` | `--text-lg` 18 | 600 | Section title |
| `.type-title-3` | `--text-md` 16 | 600 | Card title / nav item |
| `.type-body-1` | `--text-base` 15 | 550 | Lead body |
| `.type-body-2` | `--text-base` 15 | 400 | Body |
| `.type-body-3` | `--text-sm` 14 | 400 | Dense body / table |
| `.type-button-lg` | `--text-md` 16 | 600 | Big buttons |
| `.type-button-md` | `--text-base` 15 | 600 | Default buttons |
| `.type-button-sm` | `--text-sm` 14 | 600 | Small buttons/tabs |
| `.type-caption-1` | `--text-xs` 13 | 550 | Meta / labels |
| `.type-caption-2` | `--text-2xs` 12 | 500 | Badges / fine print |

All named styles set `font-family: var(--font-sans)`, `text-wrap` per §7, and use `--leading-*`. Body
copy measure is `65–75ch` (tables may run wider).

**Off-scale → token mapping (mandatory; every hardcoded px below must snap):**

| Baseline px | Token |
|---|---|
| 9.5, 10.5, 11, 11.5 | `--text-2xs` (12) |
| 12.5, 13 | `--text-xs` (13) |
| 13.5 | `--text-sm` (14) |
| 14, 15 | `--text-base` (15) |
| 16, 17 | `--text-md` (16) |
| 18 | `--text-lg` (18) |
| 20, 22 | `--text-xl` (20) |
| 24, 26 | `--text-2xl` (24) |
| 28, 30 | `--text-3xl` (28) |
| 32, 34, 35, 38 | `--text-4xl` (32) |
| 40 | `--text-5xl` (40) |

**Class → named-style mapping for existing page classes (impl-pages):**

| Existing class | Map to | Notes |
|---|---|---|
| `.page-title` | `.type-heading-2` | Remove serif + clamp + weight 700 only |
| `.hero-title` | (removed — hero retired, §5.1) | — |
| `.section-title` | `.type-title-2` (18/600) | Not 15px; more space above than below |
| `.card-title` | `.type-title-3` | |
| `.card-subtitle` | `.type-caption-1` | |
| `.field-label` | `.type-body-3` weight 600 | |
| `.field-hint` | `.type-caption-2` | ≥12px |
| `.kpi-label` | `.type-caption-2` | **remove uppercase + letter-spacing** (CJK) |
| `.kpi-value` | numeric display: 24–32, 700, `tabular-nums` | tone only via state tokens |
| `.stat-value`, `.bound-value` | numeric display: 32/700 `tabular-nums` | no serif |
| `.run-head h1` | `.type-heading-3` but keep `--font-mono` for the id | id stays mono |
| `.badge` | `.type-caption-2` | |
| `.tab` | `.type-button-sm` | |
| `.btn` / `.btn-sm` / `.btn-lg` | `.type-button-md` / `-sm` / `-lg` | |
| `.empty-title` | `.type-title-3` | |
| `.empty-desc` | `.type-body-3` | |
| `.report-section h3` | `.type-title-3` | **remove uppercase + letter-spacing** |

### 3.3 Spacing scale (closed, 4px grid)

| Token | Value | Token | Value |
|---|---|---|---|
| `--sp-0` | 0 | `--sp-6` | 24px |
| `--sp-0-5` | 2px | `--sp-8` | 32px |
| `--sp-1` | 4px | `--sp-10` | 40px |
| `--sp-2` | 8px | `--sp-12` | 48px |
| `--sp-3` | 12px | `--sp-14` | 56px |
| `--sp-4` | 16px | `--sp-16` | 64px |
| `--sp-5` | 20px | | |

**Ad-hoc → token mapping (every magic number must snap):** 2→`--sp-0-5`; 5→`--sp-1` (4);
6→`--sp-2` (8); 7→`--sp-2` (8); 9→`--sp-2` (8); 10→`--sp-3` (12); 11→`--sp-3` (12); 14→`--sp-4` (16);
18→`--sp-4` (16); 22→`--sp-6` (24); 26→`--sp-6` (24); 28→`--sp-8` (32); 30→`--sp-8` (32);
34→`--sp-10` (40); 44→`--sp-10`/`--sp-12`. Layout invariants: **more space above a heading than below**
(e.g. `--sp-8` above, `--sp-3` below); tight groups use `--sp-2`–`--sp-3`, generous separation `--sp-6`+.

**Fixed layout tokens:** `--sidebar-width: 232px`, `--topbar-height: 56px`, `--content-max: 1280px`,
`--content-pad: var(--sp-6)`, `--content-pad-compact: var(--sp-4)`, `--measure: 70ch`,
`--prose-max: 720px`.

### 3.4 Radius scale + nested-radius formula

| Token | Value |
|---|---|
| `--radius-xs` | 4px |
| `--radius-sm` | 6px |
| `--radius` (alias `--radius-md`) | 8px |
| `--radius-lg` | 12px |
| `--radius-xl` | 16px |
| `--radius-2xl` | 24px |
| `--radius-full` | 999px |

**Nested radius formula:** when a shape sits inside another and the gap is **< 32px**,
`inner = outer − gap`; apply only if the result is **> 2px**, else leave the inner shape unchanged.
Examples: outer 16 + 8 gap → inner 8 (`--radius`); outer 12 + 8 gap → inner 4 (`--radius-xs`);
outer 12 + 16 gap → −4 (do not apply). Card radii stay **12–16px**; pills/full radius only for small
controls (badges, chips, small toggles) — **not** for cards or buttons.

### 3.5 Elevation / shadow system

Depth = **tinted, soft, offset** shadows (no zero-offset glow halos). One light direction (top-down).

| Token | Light | Dark |
|---|---|---|
| `--shadow-xs` | `0 1px 2px rgba(23,23,30,0.05)` | `0 1px 2px rgba(0,0,0,0.35)` |
| `--shadow-sm` | `0 1px 3px rgba(23,23,30,0.07), 0 1px 2px rgba(23,23,30,0.05)` | `0 1px 3px rgba(0,0,0,0.45)` |
| `--shadow-md` | `0 4px 12px rgba(23,23,30,0.09)` | `0 6px 20px rgba(0,0,0,0.5)` |
| `--shadow-lg` | `0 12px 32px rgba(23,23,30,0.14)` | `0 16px 48px rgba(0,0,0,0.6)` |
| `--shadow-overlay` | `0 16px 48px rgba(23,23,30,0.20)` | `0 24px 64px rgba(0,0,0,0.7)` |

Rule: declare elevation **once** — a 1px border **or** a shadow, not both on the same box (no "ghost
card"). **Status dots** use a solid fill + optional 1px `--border-subtle` ring, **never**
`box-shadow: 0 0 8px` glow (fix audit §1.13 / `app.css:122,128`).

### 3.6 Motion durations + easing

| Token | Value | Use |
|---|---|---|
| `--dur-fast` | 150ms | color/opacity feedback (hover, focus) |
| `--dur` | 200ms | default state change, tab/selection, border |
| `--dur-slow` | 250ms | transform/lift, skeleton none |
| `--dur-overlay` | 260ms | drawer/modal/toast entrance |
| `--ease` | `cubic-bezier(0.22, 1, 0.36, 1)` | standard deceleration ("confident arrival") |
| `--ease-exit` | `cubic-bezier(0.4, 0, 1, 1)` | exits (faster than entrance) |

Rules (from vercel/animate/Operate): animate **transform/opacity only**; **list properties explicitly,
never `transition: all`**; no page-load choreography; no scroll reveals; `prefers-reduced-motion`
reduces movement to opacity/instant (§7.9). Existing `var(--dur-fast)`, `var(--dur)`, `var(--dur-slow)`,
`var(--ease)` names are retained so existing declarations keep working.

### 3.7 Z-index scale

| Token | Value | Layer |
|---|---|---|
| `--z-base` | 0 | content |
| `--z-sticky` | 40 | topbar |
| `--z-scrim` | 55 | mobile nav scrim |
| `--z-sidebar` | 60 | sidebar / mobile drawer nav |
| `--z-overlay-backdrop` | 90 | drawer backdrop |
| `--z-overlay` | 100 | drawer / modal |
| `--z-toast` | 120 | toasts |
| `--z-skip-link` | 200 | skip link |

### 3.8 Focus ring tokens

| Token | Value |
|---|---|
| `--focus-ring-width` | 2px |
| `--focus-ring-offset` | 2px |
| `--focus-ring-color` | `var(--accent)` |

`:focus-visible { outline: var(--focus-ring-width) solid var(--focus-ring-color); outline-offset:
var(--focus-ring-offset); }` — **do not** set `border-radius` here (fixes audit §4.3). For controls on
colored fills, use a 2px `--accent-contrast` inner + `--accent` outer ring (see §7.2).

---

## 4. Component contracts & full state matrix

impl-core writes these primitives in `core.css`; impl-pages emits the class names. **Each component
ships its full state set** — default / hover / focus-visible / active / disabled, plus loading / empty /
error where it holds data. State is conveyed by class or ARIA attribute (not color alone — pair with
icon/label/weight). Transitions list properties explicitly and use `--dur-*` / `--ease`.

### 4.1 Buttons

Classes: `.btn` (base), `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`, `.btn-lg`,
`.icon-btn`. Icon-only buttons **must** have `aria-label`; nested decorative `<svg aria-hidden="true">`.

| State | Selector | Visual spec |
|---|---|---|
| default | `.btn` | bg `--bg-raised`, 1px `--border`, text `--text-1`, radius `--radius`, padding 8×14 (`--sp-2 var(--sp-3)`+), weight 600 |
| hover | `.btn:hover` | bg `--bg-hover`, border `--border-strong` |
| focus-visible | `.btn:focus-visible` | outline ring §3.8 (keeps radius) |
| active | `.btn:active` | `transform: translateY(1px)` |
| disabled | `.btn:disabled` | `opacity:.55`, `cursor:not-allowed`, no transform |
| loading | `.btn[aria-busy="true"]` / disabled + `.spinner` | spinner 14px + text unchanged; `aria-busy="true"` |
| primary | `.btn-primary` | bg `--accent`, text `--accent-contrast`, no border; hover `--accent-strong`; active `--accent-active`; disabled `--action-disabled-bg`/`--action-disabled-text` |
| danger | `.btn-danger` | text `--danger`, bg `--danger-soft`, border `--danger-border` |
| ghost | `.btn-ghost` | transparent, text `--text-2`; hover bg `--bg-hover` text `--text-1` |
| icon-btn | `.icon-btn` | 30×30 desktop, **≥44×44 on coarse pointers/≤860**; radius `--radius-sm`; color `--icon-3`; hover bg `--bg-hover` color `--icon-1` |

Touch targets: all buttons reach **44×44** effective hit area at ≤860 (increase padding or min-height
`44px`); never shrink tap area below the visible mark.

### 4.2 Inputs / selects / textarea

Classes: `.input`, `.select`, `.field`, `.field-label`, `.field-hint`, `.input-with-icon`.

| State | Spec |
|---|---|
| default | bg `--bg-inset`, 1px `--border-control`, text `--text-1`, radius `--radius`, padding 8×12 |
| placeholder | `--text-3`, ends with `…` when illustrative |
| hover | border `--border-strong` |
| focus | border `--accent` + ring `0 0 0 3px var(--accent-soft)` **or** outline ring §3.8 |
| hover+focus | keep focus treatment |
| disabled | bg `--action-disabled-bg`, text `--action-disabled-text`, cursor not-allowed |
| error | border `--danger`, `aria-invalid="true"`, inline `.field-error` text `--danger` |
| filled | normal |
| select | explicit `background-color: var(--bg-inset)` + `color: var(--text-1)`; **arrow tokenised** — arrow stroke must be `--icon-3` via currentColor mask/SVG, **not** hardcoded `%23888` (fix audit §4.4); padding-right 32 |
| textarea | `resize: vertical`, `min-height` from token; `.workflow-snapshot` keeps `width:100%` |

`.field-error` message sits immediately after the field, names the problem + next step, `role="alert"`
where async. `#snapshot-error` behaviour unchanged (logic).

### 4.3 Cards / panels

Classes: `.card`, `.card-flush`, `.card-header`, `.card-title`, `.card-subtitle`, `.card-body`, and
`.panel` (alias for a bordered secondary panel = `.card` with `--surface-2`/`--bg-surface`).

- default: bg `--bg-surface`, 1px `--border-subtle`, radius `--radius-lg`, padding `--sp-5`.
- hover: only if interactive — border `--border`.
- focus-visible: ring (only when the card is a link/button container).
- **No nested cards** (card-in-card). Reduce card-in-card: use `.card-flush` + inner `.divider`/rows,
  not a card inside a card. **No single-side borders.**
- Respect nested radius: children inset by `--sp-4`/`--sp-5` from a 12px card → inner ≤ 4px.

### 4.4 Tables (`.table`, `table.data`)

Classes: `.table-wrap`, `table.data`, `.cell-main`, `.cell-sub`, `.is-clickable`, `.num`, and
responsive helpers `.table--stack` / `.col-priority-*` (§6.3).

| State | Spec |
|---|---|
| default | `table.data` width 100%, font `--text-sm`; header bg `--bg-inset`, `--text-3`, weight 600, **sentence case** headers; rows separated by `--border-subtle` |
| **numerals** | `font-variant-numeric: tabular-nums` on **all** numeric cells (`.num`, round/耗时/时间/tokens/cost/counts) — fix audit §2 |
| hover | row bg `--bg-hover` |
| focus-visible | focusable row/cell link gets ring; **do not** put `role="link"`/`role="button"` on `<tr>` — put a real `<a>`/`<button>` in a cell (fix audit §4.2) |
| selected | `aria-current`/`.is-selected` → bg `--accent-soft`, full 1px `--accent-border` (not left stripe) |
| empty | `.empty` state inside the wrapper (never an empty table body) |
| loading | `.skeleton-table` shaped like header + N rows |
| error | inline `.alert-danger` above/inside the wrapper |

`.table-wrap { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }` and its grid/flex
parent must be `min-width: 0` (§6.1) so tables scroll **locally** and never push the page wider.

### 4.5 Tabs

Classes: `.tabs`, `.tab`, `.tab .count`, `.tab-panel`. Roles: `role="tablist"` / `role="tab"`
(`aria-selected`, `aria-controls`, `tabindex` roving — keep existing keyboard model in views.js).

| State | Spec |
|---|---|
| default | text `--text-3`, weight 600, `--text-sm`, bottom 1px `--border` on `.tabs` |
| hover | text `--text-1` |
| selected | text `--text-1`, 2px `--accent` underline (`::after`, bottom −1px, radius 2) |
| focus-visible | ring on the tab (keeps radius) |
| disabled | text `--action-disabled-text` |
| `.count` | `--text-2xs`, bg `--bg-active`, `tabular-nums` |

At ≤680 tabs scroll horizontally **inside** `.tabs` (`overflow-x:auto`) — page must not overflow
(confirms the current mobile run-detail behaviour; keep it).

### 4.6 Badges / status pills

Classes: `.badge`, `.badge-success|warning|danger|info|accent`, `.badge-outline`, `.badge .dot`.

- default: radius `--radius-full`, 1px `--neutral-border`, bg `--neutral-soft`, text `--text-2`,
  `--text-2xs`, weight 600, padding 2×8. **No uppercase / no letter-spacing** (CJK).
- state variants: text/bg/border from `--<state>` / `--<state>-soft` / `--<state>-border`.
- dot: 6px, `currentColor`, no glow.
- hover: none (non-interactive) unless `.badge` is a button (then hover bg).
- **Always pair color with the text label** (never color-only meaning) — the badge already carries a
  label; keep it.

### 4.7 Toast

Classes: `.toast-region`, `.toast`, `.toast-success|error|info`, `.toast-msg`. `#toast-region` keeps
`role="status" aria-live="polite"`.

- default: bg `--bg-overlay`, 1px `--border`, `--shadow-overlay`, radius `--radius-lg`, padding 12×14.
- entrance: `.toast` `toast-in var(--dur-overlay) var(--ease)` (transform/opacity only).
- states: success/error/info colour the icon; `.toast-msg` text `--text-1`. No exclamation marks.
- auto-dismiss keeps existing timing (logic in components.js); fade via `opacity 240ms` (explicit).
- stacking: bottom-right, `max-width: min(380px, calc(100vw - 40px))`, `overscroll-behavior: contain`.

### 4.8 Drawer / modal

Classes: `.drawer-backdrop`, `.drawer`, `.drawer-header`, `.drawer-title`, `.drawer-body`. Keep
`role="dialog" aria-modal="true" aria-labelledby="drawer-title"`, focus trap, Escape and `inert` shell
(behaviour in components.js — keep).

- default: bg `--bg-overlay`, 1px left `--border` **allowed on the overlay edge** (this is a panel edge,
  not a card accent stripe), `--shadow-overlay`, width `min(520px, 94vw)`.
- entrance: `drawer-in var(--dur-overlay) var(--ease)`; backdrop `fade-in`.
- **`overscroll-behavior: contain`** on `.drawer-body` (and modal body) so scroll does not chain.
- focus-visible inside: ring; on open focus `#drawer-close`; on close restore focus (existing).
- mobile: width `min(520px, 100vw)`; `max-height: 100dvh`.

### 4.9 Sidebar + topbar + mobile nav (shell)

See §4.12 for the class/DOM contract and §6.2 for responsive behaviour. States: `.nav-item` default
(text `--text-2`), hover (`--bg-hover`, `--text-1`), current (`aria-current="page"` → bg `--accent-soft`,
text `--accent`, plus a **full** current treatment; the old 3px brand-red left bar is removed and
replaced with the accent-tinted pill), focus-visible ring. `.menu-btn` 34×34 desktop-hidden, **44×44**
at ≤860. `.theme-toggle` same states as `.nav-item`. Sidebar footer status dot: solid `--success` /
`--danger` **without glow**.

### 4.10 Skeleton loaders

Classes: `.skeleton`, `.skeleton-table`, `.skeleton-row`, `.skeleton-kpi`, `.skeleton-block`,
`.skeleton-panel`. Shimmer uses `--bg-hover`→`--bg-active` (allowed loading affordance), respects
reduced-motion (static tint instead of shimmer).

- **Layout-shaped**: `.skeleton-table` renders a header row + N body rows in a grid matching
  `table.data` column proportions; `.skeleton-kpi` renders N KPI-sized blocks; `.skeleton-panel` matches
  the run-detail shape (header + KPI strip + tab bar + rows). Generic arbitrary-height bars are not
  acceptable as content loading (fix audit §3.1).
- `aria-busy="true"` on the container; `role="status"` + visually-hidden "加载中…" text.

### 4.11 Empty state

Classes: `.empty`, `.empty-icon`, `.empty-title`, `.empty-desc`, `.empty-actions`.

- composed getting-started: icon in `.empty-icon` (46px, `--bg-hover` tile, 1px `--border-subtle`),
  `.empty-title` (`--text-2`), `.empty-desc` (`--text-3`, max 420px), 1–2 actions.
- **Two distinct copies** where data can be empty vs filtered-empty (investigate — §5.2).

### 4.12 KPI / stat cards

Classes: `.kpi-grid`, `.kpi`, `.kpi-label`, `.kpi-value`, `.kpi-foot`, `.kpi-bar`, and the stat variants
`.stat-band`, `.stat`, `.stat-value`, `.stat-label`, `.stat-note`, `.stat-strip`.

- `.kpi`: bg `--bg-surface`, 1px `--border-subtle`, radius `--radius-lg`, padding `--sp-4`,
  `min-width:0`.
- `.kpi-label`: `--text-2xs`, **no uppercase / no letter-spacing**, `--text-3`.
- `.kpi-value`: `--text-2xl`–`--text-4xl`, weight 700, `tabular-nums`, `line-height:1.1`; tone via
  state token only.
- `.kpi-bar` track `--bg-active`, fill `--accent`, `width` transition `--dur-slow` (transform-safe:
  use `transform: scaleX()` or accept width transition — if width, keep it short; preferred: animate
  `transform`).
- `.stat-band` / `.stat-strip`: 4 → 2 → 1 columns; dividers are 1px `--border-subtle` full-height via
  border-right (this is a data-cell divider, acceptable) or gap; no glow.

### 4.13 Alerts / callouts (`.alert`)

Classes: `.alert`, `.alert-info|warning|danger|success`, `.alert-msg`. Full 1px border (state
`--<state>-border`), bg `--<state>-soft`, text `--text-1` in `.alert-msg`, icon state-coloured. **Never**
a single-side stripe. The `.plan-only-note` and `.replay-provenance` become variants of `.alert` /
`.note` (full border) — see §8.3.

### 4.14 Chips / segmented (`.chip`, `.segmented`)

`.chip`: radius full, 1px `--border`, text `--text-2`, `--text-sm`; hover `--border-strong`/`--text-1`;
pressed `aria-pressed="true"` → bg `--accent-soft`, border `--accent-border`, text `--accent`;
**transition lists properties explicitly** (remove `transition: all` — fix audit §1.12). `.segmented`
button pressed state = bg `--bg-raised` + `--shadow-sm`.

### 4.15 Misc primitives

`.divider` (1px `--border-subtle`), `.tag-id` (mono, `--code-bg`, `--border-subtle`, `--radius-sm`),
`.evidence-chip` (mono `--text-2xs`, `--accent` on `--accent-soft`, 1px `--accent-border`, hover
`--accent-border` bg), `.kv-list/.kv-row` (dt `--text-3` 600, dd `--text-1`, `word-break`), `.json-block`
(mono `--text-2xs`, `--bg-inset`, 1px `--border-subtle`, `--radius`, scroll, `max-height`), `.mono`.

### 4.16 JS helper API (impl-core `components.js`) — signatures are law

| Helper | Signature | Output contract |
|---|---|---|
| `badge(text, tone='neutral', withDot=false)` | unchanged | `<span class="badge [badge-<tone>]">…` |
| `emptyState({title, desc='', actionHtml='', icon=null})` | **add optional `icon`** | `.empty` block; default magnifier icon |
| `skeletonRows(count=4, height=44)` | retained | generic bars — **must not be used for table/list content anymore** |
| `skeletonTable(rows=6, cols=8)` | **new** | `.skeleton-table` with header + `rows` body rows shaped like `table.data` |
| `skeletonList(count=6)` | **new** | `.skeleton-list` of case-item-shaped rows |
| `skeletonKpi(count=4)` | **new** | `.skeleton-kpi` blocks |
| `loadingBlock(text='加载中…')` | retained | **run-detail-shaped** `.skeleton-panel` (not a centered spinner); `role="status"` + text |
| `toast(message, type='info', timeout=4200)` | unchanged | `.toast.toast-<type>`, aria-live region |
| `openDrawer/closeDrawer/initDrawer` | unchanged | focus trap/escape/inert preserved |
| `evidenceDrawerHtml(record, observation=null)` | unchanged | must keep `用于待确认解释，尚未支持最终诊断` string |
| `bindEvidenceChips/evidenceChips(ids, index, {emptyText})` | unchanged | disabled handling + escaping |
| `workflowReportHtml(state, evidenceIndex={})` | unchanged | must keep all test_v12 strings/classes |

impl-pages **must** switch callsites: overview `#overview-stats` → `skeletonKpi(4)`; `#recent-runs` →
`skeletonTable(4, 8)`; investigate `#case-list` → `skeletonList(6)`; library `#lib-table` →
`skeletonTable(6, 8)`; run detail → `loadingBlock()` (redefined). This requires impl-core to land the
new helpers before/with impl-pages; both are on the same branch, and the callsites degrade gracefully
because `skeletonRows` still exists.

### 4.17 Shell DOM contract (`index.html` = impl-core; shell CSS = impl-pages)

`app.js` and `components.js` query these exact selectors and **must keep working**:
`#sidebar`, `#scrim`, `#menu-btn`, `#theme-toggle`, `#topbar-title`, `#main`, `#drawer`,
`#drawer-backdrop`, `#drawer-close`, `#drawer-body`, `#drawer-title`, `#toast-region`, `.skip-link`,
`.main-area`, `.app-shell`, `[data-nav]`, `#sidebar-meta`, `#sidebar-meta-text`.

`index.html` keeps: `<a class="skip-link" href="#main">跳到主要内容</a>`; `<html lang="zh-CN"
data-theme="light">`; `<meta name="color-scheme" content="light dark">`; `<meta name="theme-color">`;
the four stylesheet links in order tokens → core → app → institutional (**order matters**). The shell
markup may be re-classed for layout, but the id/class set above is frozen. `.app-shell`,
`.main-area`, `.sidebar`, `.topbar`, `.nav-item`, `.brand-mark`, `.brand-text`, `.brand-rule`,
`.sidebar-nav`, `.sidebar-footer`, `.sidebar-meta`, `.theme-toggle`, `.menu-btn`, `.scrim` are styled by
app.css (impl-pages). Cross-file rule: **`.app-shell` is a CSS grid `var(--sidebar-width) 1fr`** on
desktop and **`1fr`** at ≤860.

---

## 5. Page-by-page layout & visual hierarchy

Shared rules for all pages: **left-aligned hierarchy**; page head = title (`--type-heading-2`) + one
sentence purpose (`--type-body-2`, `--text-3`, max `--prose-max`) + primary action at the right of the
title row where it exists; **more space above a section heading than below** (`--sp-8` top / `--sp-3`
bottom); **aligned baselines** across side-by-side cards; **CTA rows bottom-aligned**; **no eyebrows /
kickers**; **no serif**; **no clamp**; **no background gradients**; **no single-side stripes**; break the
"three equal cards" default; reduce card-in-card. Content width capped at `--content-max` (1280) centred,
`--content-pad` gutters.

### 5.1 Overview (`#/`, `renderOverview`) — desktop / tablet / mobile

**Current problems:** radial-gradient hero + `.hero-kicker` "EVIDENCE-DRIVEN RCA CONSOLE" + serif
`.hero-title` + `clamp()` + weight 750; `.eyebrow` "RECORDED BATCH · 2026-11-01" on the result teaser;
`.feature-grid` three/four equal cards; **the `.stack` grid makes the page 860px wide at 834/390**
(capture-report: `scrollWidth=860` at `innerWidth` 834 and 390).

**Target structure (top → bottom):**

1. **Page head** (`.overview-head`): H1 `总览` + one line purpose + primary `新建调查` (page-level; the
   topbar also has one — keep both consistent). *Remove the marketing hero entirely.* Fold the "接受一份
   结论，需要三件事" content into a compact **contract panel** below the page head — a single `.card`
   with three `.contract-row` definition rows (`引用 / 权限 / 停止`), each `strong` label + sentence. No
   kicker, no gradient, no serif, no left stripe; full 1px `--border` (or borderless on `--surface-2`).
2. **档案库概况 — KPI stat strip** (`.stat-strip` 4-up): 事件案例 / 存档痕迹 / 已定位根因 / 明确存疑.
   Values `tabular-nums`; tone via `--success`/`--warning`. 4→2→1 columns (§6.4).
3. **最近运行 — recent runs table** (`.card.card-flush` + `.table-wrap` + `table.data` + `.skeleton-table`
   while loading). **This is the section that must stop overflowing** — see §6.1. 8 columns; on mobile
   use column priority (§6.3): keep 事件/状态/演示; 提供方/变体/轮次/耗时/更新时间 collapse into the
   `.cell-sub` line or hide.
4. **评测 teaser** (`.result-teaser`): remove `.eyebrow`; title `协调是否值得它的成本？`
   (`--type-title-1`); sentence; two actions (primary `查看完整评测`, secondary `观看一次回放`); right
   side the `.mini-rows` quality bars — restyle as a compact bar list with `tabular-nums` values.
   Layout: `minmax(0,1fr) minmax(280px, .72fr)` desktop → 1 col ≤1080.
5. **设计原则** (`.principle-list`): replace `.feature-grid` equal cards with a **single bordered list**
   or **2-up asymmetric** items (`引用或存疑 / 权限边界取证 / 离线可重放 / 解释缓存复用`), each item an
   icon (`--icon-3`, `aria-hidden`) + title + one sentence. No 4-equal-card grid; no card-in-card.

**Hierarchy:** H1 → section titles (Title-2) → table/stat values (numeric display) → body. The visual
lead is the **KPI strip + recent runs** (operational state), not a hero. All `--min-w-0` on grid/flex
children. Remove `.hero`, `.hero-kicker`, `.hero-title`, `.hero-desc`, `.hero-split`, `.pipeline`,
`.pipeline-stage`, `.feature-grid`/`.feature` from the page (or repurpose `.feature` as list row).

**Desktop (≥1280):** content 1280 max; KPI 4-up; teaser 2-col; principles 2-up/rows.
**Tablet (861–1024):** KPI 2-up; teaser stacked; principles 1-col/2-up; table local scroll.
**Compact (≤860, incl. 834 and 390):** hamburger shell; KPI 2-up (390: 2-up or 1-up), teaser stacked,
principles 1-col, table column priority; **zero horizontal page overflow**.

### 5.2 Investigate (`#/investigate`, `renderInvestigate`)

**Current:** two-pane master-detail (7fr case list / 5fr detail+config); case items use
`box-shadow: inset 2px 0 0` left stripe for selection; empty-data copy wrong; error hole.

**Target:**
- Page head `新建调查` + purpose. Then `.investigate-grid` = `minmax(0,1fr)` case list card +
  `minmax(320px, 380px)` right column (detail card + run-config card). Desktop 2-col, ≤1080 stack
  (list then detail then config), ≤860 single column with list `max-height` capped and internal scroll.
- **Case list**: `.case-item` as `<button aria-pressed>` (keep), but selected state = `--accent-soft`
  bg + **full 1px `--accent-border`** + weight 600 (remove the left inset stripe); hover `--bg-hover`;
  focus ring. Show `id` mono, service count badge, symptom line-clamp 2. `.skeleton-list` while loading.
- **Case detail**: tag-id + started badge, title (Title-3), symptom list, service badges. Unselected →
  `.empty` "未选择案例 / 从左侧列表中选择一个事件案例以查看详情。"
- **Run config**: `.card` with provider `.segmented` (keep `data-provider`, `aria-pressed`), cache
  select, workflow select, conditional monitor/snapshot fields, budget badges, run button
  (`#run-btn`, `.btn-primary.btn-lg`, width 100%). Keep **all ids** (`#cache-mode`, `#workflow-profile`,
  `#monitor-mode`, `#snapshot-field`, `#monitor-snapshot`, `#snapshot-error`, `#real-options`,
  `#req-timeout`, `#resp-format`, `#thinking-mode`, `#run-btn`) — logic depends on them.
- **Empty copy fix:** distinguish **dataset empty** (`cases.length === 0` → getting-started: title
  `暂无可用案例`, desc "当前数据集没有可调查的事件。请确认 data/ 中的公开事件包已加载。") from
  **filter no-match** (`没有匹配的案例 / 换个关键词试试。`). (Fix audit §3.2.)
- **Error fix:** if `getMeta()`/`getCases()` fails, render the inline `.alert-danger` (problem + next
  step + a `重试` button that re-invokes `renderInvestigate(root)`) into **both** `#case-list` **and**
  `#run-config` so the right pane is not a permanent hole. (Fix audit §3.3; event-safe, no API change.)
- **A11y:** search input has `aria-label`; case list `role="group" aria-label="案例列表"` (keep).

**Desktop:** 2-col. **Tablet 861–1024:** 2-col if ≥980 else stacked. **≤860:** single column, case list
capped ~50vh with internal scroll; config below; no page overflow.

### 5.3 Run detail (`#/run`, `renderRun` → `mountReplay` / `drawRun`)

**Current:** run-head cluster; KPI budget bars; tabbed panels (时间线/假设/证据/发现/报告); replay
controls; centred spinner on load (`loadingBlock`); `.hero-kicker` "REAL LLM / RECORDED REPLAY" in the
replay heading; timeline uses per-kind coloured dots.

**Target:**
- **Loading:** replace centered spinner with run-detail-shaped `.skeleton-panel` (`loadingBlock`), with
  `role="status"` text `正在加载运行痕迹…` (keep the string used in views.js:555).
- **Run head** (`.run-head`): H1 = incident id (mono, `--type-heading-3`), status/ workflow/provider/
  live badges; meta row (`.run-head-meta`) with `tabular-nums` for run id/model/variant/cache/耗时/来源
  指纹; download actions right. Fit at 390: wrap, actions drop below (`.run-head` `flex-wrap`, column
  ≤560).
- **KPI budget strip**: `.kpi-grid` (轮次/工具/模型请求/缓存命中/证据记录) with `.kpi-bar`
  (used/max) — `tabular-nums`, width/transform transition `--dur-slow`.
- **Tabs**: keep `#run-tabs`, `role="tablist"`, tab names 调查时间线/假设看板/证据登记/调查发现/根因报告
  and `.count`; roving tabindex + Arrow/Home/End keyboard (keep existing JS). Tabs scroll horizontally
  inside `.tabs` at ≤680.
- **Timeline** (`.timeline`, `.tl-event`, `.tl-head`, `.tl-body`, `.tl-chevron`): keep collapse behaviour
  and `data-kind` dots, but recolour dots from state tokens (decision `--accent`, review `--warning`,
  tool `--info`, merge/report `--success`, cache `--text-3`), no glow. Event body uses `.assign-item`
  (panel, not card-in-card), `.json-block`, `.chip-row`, `.cite-wrap`, `.tag-id`.
- **Hypotheses / Evidence / Findings / Report** panels: use `.hypo-card` (panel; `data-status` SUPPORTED
  → `--success-border`, REJECTED → dim + `--danger` label, not opacity only), evidence `table.data`
  (accessible rows, `.evidence-excerpt` line-clamp 1), findings table (numeric/`cite-wrap`), report
  uses the **new report components** (§5.3.1). Keep every text string the tests assert.
- **Replay heading**: **remove `.hero-kicker`**. Replace the provider/source line with a **badge row**
  (e.g. `MOCK`/`REAL LLM` badge + `RECORDED REPLAY` badge). Keep the `Investigation Replay` heading
  (`.section-title`). (browser-real.cjs is non-CI — see §2.2 note; do not preserve `.hero-kicker`.)
- **Replay controls** (`.replay-controls`): 首步/上一步/播放/下一步/末步 + speed select +
  `#replay-position` (`aria-live`). **Must wrap and keep every button's right edge ≤ viewport at 390**
  (CI asserts this). Buttons min-height 40–44, `white-space: normal` at ≤540 (keep existing). `#replay-play`
  text toggles 播放/暂停 (keep). `#replay-speed` select themed.
- **Progress bar `style="width:${pct}%"`** → move to a CSS custom property (`--pct`) set inline, width
  via `width: calc(var(--pct) * 1%)` or `transform: scaleX`, so inline magic styles are removed.

**Tablet/mobile:** run head stacks; KPI 2-up→1-up; tabs scroll; tables local scroll; replay controls
wrap; **390 must have `scrollWidth <= innerWidth`**.

#### 5.3.1 Report presentation (`.report-hero`, `.report-section`, `.causal-chain`)

- `.report-hero`: **remove the three `linear-gradient` backgrounds** (`app.css:789-791`); use flat
  `--bg-surface` + 1px state border (`--success-border`/`--warning-border`/`--danger-border`) and a state
  badge. Title `.report-hero-title` (`--type-title-1`), sub in `--text-2`. No gradient.
- `.report-section` headings: `--type-title-3`, **sentence case, no uppercase/letter-spacing** (fix
  `app.css:860-867`). Sections separated by `--border-subtle`; more space above than below.
- `.causal-chain`: keep ordered list; counter bubble uses `--accent-soft`/`--accent-border`/`--accent`
  (or state), connector `--border`. This is a genuine sequence → numbering allowed, but restyle neutral
  and smaller (not a display kicker).
- Provisional explanations / gaps / next steps / optional / assessment basis: use `.assign-item` panels
  + `.symptom-list`; **keep the exact strings** `待确认的解释`, `关键缺口`, `建议下一步`,
  `可选补充（不阻止作答）`, `较可能（未确认）`, `用于待确认解释，尚未支持最终诊断`.
- `workflowReportHtml` output: keep `.report-section.workflow-result`, `.workflow-status-grid`,
  `.workflow-plan-grid`, `.workflow-plan-section`, `.plan-only-note`; `.plan-only-note` becomes a
  full-bordered `.alert.alert-info` (no `border-left`, bg `--surface-2` now defined).

### 5.4 Library (`#/library`, `renderLibrary`)

**Current:** `.page-title` serif; toolbar (search + provider chips + status select); `.card-flush` table;
good empty state; table clipped on mobile (local scroll works — `scrollWidth` stays 390).

**Target:** page head `痕迹档案库` + purpose (`--type-body-2`, no serif); `.library-toolbar` (search
`max-width:360px`, filter chips + status select; `flex:1 min-width:0`); `.card.card-flush` +
`.skeleton-table` while loading + `table.data`; keep `traceTable` columns but apply responsive column
priority (§6.3) and descriptive empty states (`档案库为空` vs `没有匹配的痕迹`). Row click/`data-demo-link`
unchanged. Table local scroll with sticky first column at ≤680. **No page overflow.**

### 5.5 System design (`#/system`, `renderSystem`)

**Current:** `.page-head--rule` + `.eyebrow` "System design" + serif `.page-title`; `.stage-track` with
`.stage-n` brand-red numbers and a 2px top rule per stage; `.decision-grid` 3 equal cards; `.bound-strip`;
`.acl-table`; `.gate-list` with `.gate-n`; `.invariant-grid` 4 equal; `.next-band`.

**Target:**
- Page head: H1 `四个角色，一套可审计的契约` (`--type-heading-1` or `-2`), purpose; **remove `.eyebrow`**,
  remove serif, keep `.page-head` spacing (the red rule `.brand-rule` is *identity chrome* allowed in
  the sidebar brand only; the 46×3 red rule under page head is removed as decoration).
- **Pipeline** (`.stage-track`): genuine ordered sequence → **keep numbers as compact neutral step
  labels** (`1 · Monitor` … `7 · Report`, mono `--text-2xs`, `--text-3`), **not** brand-red display
  kickers. Remove the per-stage 2px top rule; use a single connector line / subtle step markers. This
  explicitly nuances "remove numbered rails": numbering stays because the content is a real sequence
  (anthropic rule), but it is restyled as content, not decoration. Optional stages: dashed marker +
  `可选` badge.
- **Coordinator decisions** (`.decision-grid`): break the 3-equal-card default → a **single bordered
  panel** with three `.decision-row`s separated by `--border-subtle` dividers, each with a state badge
  (`INVESTIGATE` info / `FINALIZE` success / `ABSTAIN` warning), rule, detail. (No card-in-card.)
- **Hard bounds** (`.bound-strip`): 4-up stat cells (4→2→1), values `tabular-nums`, no serif.
- **ACL matrix** (`.acl-table`): keep semantic `<th scope="row">`; sentence-case strip headers; check
  icons `aria-hidden` with `aria-label` on the cell; local scroll + sticky first column at mobile.
- **Gates** (`.gate-list`): keep numbering (`01`…) because it is an ordered gate list, but restyle
  `.gate-n` as compact mono `--text-3` (not brand-red 12px), and use a proper `dl`/row rhythm.
- **Invariants** (`.invariant-grid`): 4→2→1; use bordered panels (full 1px `--border-subtle`,
  `--bg-inset`) — **remove the `border-top: 2px solid brand-navy` stripe** (single-side border ban).
- **Next band** (`.next-band`): keep, restyle to `.alert`-like full-border accent panel.

### 5.6 Evaluation (`#/evaluation`, `renderEvaluation`)

**Current:** `.eyebrow` "Evaluation · recorded batch" + serif `.page-title`; `.stat-band` 4 numbers in
serif clamp; `.eval-table`; `.tradeoff-grid` 2 chart cards; `.finding-grid` 3 equal; `.lever-table` heat
cells; `.boundary-card` with left stripe; all inside sections.

**Target:**
- Page head: H1 `协调是否值得它的成本？`, purpose, `.run-tags` badges (RECORDED BATCH / date / model /
  cache) — **remove `.eyebrow`** and serif; badges are sentence-case labels (module name stays as-is in
  the badge only where it is a proper noun/identifier; do not uppercase CJK).
- `.stat-band`: 4 stat cells, `tabular-nums`, values `--text-4xl` (no serif clamp), 4→2→1.
- `.eval-table`: `tabular-nums` on all numeric columns (`.num`), aligned right/centre, `.row-tag`
  "PRIMARY" becomes a `.badge-accent` **not** an uppercase letter-spaced glyph label; `is-primary` row
  uses `--brand-red-soft` tint (brand as row emphasis is allowed here — it marks the recommended arm) or
  `--accent-soft`; local scroll + sticky first column.
- `.tradeoff-grid`: 2 chart cards (stack ≤1080); `.hbar` rows with `tabular-nums` labels; bars from
  `--accent`/`--brand-red`/muted; **remove 3-equal `.finding-grid`** → a 1-column `.finding-list` (or
  2-up) of bordered `.finding` panels (full border, no left stripe).
- `.lever-table` heat cells: keep the two-band ink logic (light band dark ink / dark band white ink so
  no cell lands in the mid-tone fail zone), `font-variant-numeric: tabular-nums`; first column sticky on
  mobile; heat uses `--brand-red` tint via `color-mix` (identity data emphasis is permitted; it is
  data, not chrome). Keep `heat()` logic in knowledge.js but ensure contrast.
- `.boundary-card`: full 1px `--border` (remove `border-left` stripe), `--bg-inset`, definition list;
  `.boundary-source` mono `--text-3`; `code` chips.

---

## 6. Structural responsive plan

Responsive is **structural**, not fluid type. Breakpoints (deliberate, reconciled with the shell's
existing 860 collapse):

| Name | Range | Shell | Notes |
|---|---|---|---|
| Desktop | `≥1280px` | sidebar visible (232px) | full 2-col layouts, 4-up stats |
| Wide | `1025–1279px` | sidebar visible | same as desktop, content caps at 1280 |
| Tablet | `861–1024px` | sidebar visible | 2-col where fits; stats 2-up; tables local-scroll |
| Compact | `≤860px` | **drawer nav** (hamburger + scrim, existing) | single column; **834 is in this band** — design must look intentional (hamburger, 1-col), while 1024 uses tablet layout |
| Phone | `≤560px` | drawer nav | stats 1–2-up, controls wrap, 44px targets |
| Verification | **390px** | drawer nav | **hard gate: no horizontal overflow** |

Implementation notes:
- `@media (max-width: 860px)` = shell collapse (keep existing app.js `matchMedia("(max-width:860px)")`
  contract). `@media (max-width: 1080px)` = investigate/teaser/tradeoff collapse. `@media (max-width: 640px)`
  = compacter paddings, stage grids 1-col.
- `@media (pointer: coarse)` (and `≤860`) = 44px touch targets, no hover-only affordances.
- `@media (prefers-reduced-motion: reduce)` = kill movement (keep opacity/state) — §7.9.

### 6.1 The blocker fix — `.stack` / grid overflow (Overview 834/390)

**Root cause (measured):** `.stack { display:grid }` (`app.css:262`) creates an implicit `auto` track
whose `min-content` is the widest child (the 8-column 最近运行 table, min-content ≈ 844px);
`.table-wrap { overflow-x:auto }` cannot shrink the grid track, so the whole page stretches to 860px
(capture-report).

**Mandatory fix (impl-pages):**
```css
.stack { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-5); }
/* every grid/flex child that can contain wide content */
.stack > *, .content > *, .investigate-grid > *, .card, section { min-width: 0; }
.table-wrap { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }
```
Plus `.app-shell { min-width: 0 }`, `.main-area { min-width: 0 }` (already present). Add a **guard
test** in the QA pass: at 834 and 390, `document.documentElement.scrollWidth === innerWidth` for every
route. Do **not** hide the overflow with `overflow-x: clip` as the primary fix; fix the track/grid.

### 6.2 Sidebar collapse / mobile nav (shell)

- `≥861`: `.app-shell` grid `var(--sidebar-width) 1fr`; sidebar sticky, full height; `.menu-btn` hidden.
- `≤860`: `.app-shell` `1fr`; sidebar `position: fixed; left:0; width: var(--sidebar-width);
  transform: translateX(-105%)`; `.sidebar.is-open { transform: none }`; `.menu-btn { display: grid }`;
  `.scrim` shown when open; `mainArea.inert = true` (existing app.js). Focus loop + Escape (existing).
  Ensure sidebar width ≤ `min(86vw, var(--sidebar-width))` so it never exceeds 390.

### 6.3 Responsive tables — column priority (not blind horizontal scroll)

For wide data tables, prefer **column priority** over "scroll everything":

- Desktop: all columns.
- Tablet (861–1024): keep primary columns; move low-priority values into the primary cell's
  `.cell-sub` line (e.g. run-id under incident id; variant/rounds under status).
- Compact/phone (≤860): show a **card-row** presentation — either `.table--stack` (each `<tr>`
  becomes a bordered block; `<td>` gets `::before` label from `data-label`) **or** keep `table.data`
  but wrap in `.table-wrap` with **sticky first column** and hide columns marked `.col-priority-3`.
- Column priority classes: `.col-priority-1` (always), `.col-priority-2` (hide ≤560 into `.cell-sub`),
  `.col-priority-3` (hide ≤860). Content must remain reachable (via `.cell-sub`/detail view), never
  silently dropped.

`traceTable` (used by overview + library) is shared markup in views.js: apply priorities there
(事件/状态/演示 stay; 提供方/变体/轮次/耗时/更新时间 fold). This is a markup change in impl-pages only.

### 6.4 Per-page responsive summary

| Page | Desktop ≥1280 | Tablet 861–1024 | Compact ≤860 / phone 390 |
|---|---|---|---|
| Overview | 1col flow, KPI 4-up, teaser 2-col, principles 2-up | KPI 2-up, teaser stack, principles 1-col | KPI 2→1-up, all stack, table column-priority; **0 overflow** |
| Investigate | 2-col (list / detail+config) | 2-col if ≥980 else stack | 1-col, list internal scroll, config below |
| Run detail | full tabs, KPI 5-up | KPI 3→2-up, tabs scroll | KPI 2→1-up, tabs scroll, replay controls wrap, **0 overflow** |
| Library | full table | primary + `.cell-sub` | stacked/sticky-col, local scroll |
| System | stage-track 7-up, 4-up stats/grids | 4-up stage wrap, 2-up grids | stage 1-col, stats 2→1-up, ACL local scroll |
| Evaluation | 4-up stat, 2 chart cards, tables | 2-up stat, chart stack, local scroll | 2→1-up stat, tables local scroll, findings 1-col |

---

## 7. Accessibility & interaction spec

### 7.1 Contrast targets

- Body & placeholder text ≥ **4.5:1**; large text (≥24px, or ≥18px bold) and **UI parts** (icons,
  control borders, focus rings) ≥ **3:1**. Values in §3.1 are measured; do not regress them.
- `--brand-red` on white is 8.7:1 but **must not be used for small body copy on non-white tints**; it is
  chrome/identity (rules, logo, heat-data) only. Use state tokens for status text.
- Never rely on color alone: badges carry text; state rows carry a label/icon/weight change.

### 7.2 Focus-visible

- Every interactive element has a visible ring via `:focus-visible` outline (§3.8). **Never**
  `outline:none` without a replacement. **Do not** set `border-radius` on `:focus-visible` (the global
  rule that reshapes pills is removed — fix audit §4.3).
- Compound controls (segmented, tablist, chip group) use `:focus-within` where appropriate.
- Sticky topbar/sidebar/overlay must not cover the focused element (`scroll-margin-top:
  var(--topbar-height)` on focus targets / section anchors).

### 7.3 Keyboard & tab order

- Logical DOM order = visual order. Skip link (`跳到主要内容`) first; it focuses `#main`.
- Tablist: roving tabindex, ArrowLeft/Right/Home/End (keep existing views.js keyboard model).
- Drawer/modal: focus trap, Escape closes, focus restores (keep components.js behaviour).
- Mobile nav: focus loop + Escape (keep app.js).
- **Do not** put `role="link"`/`role="button"` on `<tr>` (fix audit §4.2). Put a real `<a>`/`<button>`
  in a cell (e.g. the 演示回放 link already exists; extend the primary cell to be a real link, or keep
  the row `tabindex="0"` **without** overriding the row role — acceptable: `tabindex="0"` +
  `aria-label` on `tr`, no `role=`). Row click handler in `bindTraceRows` stays.

### 7.4 Data typography

- `font-variant-numeric: tabular-nums` on **all** numeric/data columns and values: table `.num`
  (轮次/耗时/时间/tokens/成本/计数), `.kpi-value`, `.stat-value`, `.bound-value`, `.bar-label`,
  evaluation heat cells, replay position. (Fix audit §2.)
- Numeric columns right-aligned (`.num`); units via NBSP (`600&nbsp;s`, `10&nbsp;MB`).
- `Intl.NumberFormat`/`Intl.DateTimeFormat` already used in api.js — keep.

### 7.5 Text wrapping & truncation

- `text-wrap: balance` on headings (H1–H4, section titles) and short centred blocks;
  `text-wrap: pretty` on body/copy. No orphaned single words. (Fix audit §2.)
- **`min-width: 0`** on every flex/grid child that can hold long text (brand text, table cells, cards,
  grid sections). Truncate/line-clamp with `overflow:hidden; text-overflow:ellipsis; white-space:nowrap`
  or `-webkit-line-clamp` where content can be long (case symptoms, evidence excerpt, drawer title,
  topbar title, brand small). Handle empty strings (don't render empty shaded boxes).
- Body measure 65–75ch (`--measure`); prose `--prose-max`.

### 7.6 aria-live & announcements

- Toast region keeps `role="status" aria-live="polite"` (`#toast-region`).
- Replay position `#replay-position` keeps `aria-live="polite"`.
- Loading regions: `role="status"` with visually-hidden "加载中…". Skeleton containers `aria-busy="true"`.
- Async form errors: `role="alert"` / `aria-invalid` (keep `#snapshot-error` behaviour).

### 7.7 Errors & view-level boundary

- Inline, specific errors naming problem + next step, never `window.alert()`. Reuse `.alert-danger`
  (`failedBanner` stays in views.js; may be re-styled).
- **View-level error boundary presentation** (spec; small **app.js** edit in integration stage, §0):
  wrap `await rendering` in `route()` in `try/catch`; on throw render into `#main` a `.card` with
  `.empty`-style error: title `页面加载失败`, desc `渲染时出现错误，请重试或返回总览。`, actions
  `重试`（re-run `route()`）and `返回总览` (`#/`). This is presentation-only; no business logic change.
  If integration prefers not to touch app.js, each view's own async catch (already present in most) must
  at minimum render a `.alert-danger` rather than leaving `#main` blank.

### 7.8 Touch, overscroll, safe areas

- 44×44 minimum touch targets at ≤860 / coarse pointers (`.icon-btn`, `.btn-sm`, `.chip`, case rows).
- `overscroll-behavior: contain` on `.drawer-body`, modal bodies, `.table-wrap`, `.case-list`,
  `.replay-event-list`, `.json-block` scroll areas (overlays must escape `overflow` ancestors and not
  chain scroll).
- `touch-action: manipulation` on interactive controls; intentional `-webkit-tap-highlight-color`.
- Safe areas: `.topbar` / `.content` respect `env(safe-area-inset-*)` where full-bleed.
- Native `<select>`: explicit `background-color: var(--bg-inset)` and `color: var(--text-1)` for Windows
  dark mode; `color-scheme` set per theme (already via `[data-theme]`).

### 7.9 Reduced motion

`@media (prefers-reduced-motion: reduce)` sets `animation-duration: .01ms`, `animation-iteration-count:
1`, `transition-duration: .01ms` (keep existing) **and** disables skeleton shimmer and drawer slide
(instant opacity). Feedback (color/opacity/state) remains legible.

### 7.10 Decorative icons

Every decorative inline `<svg>` gets `aria-hidden="true"` (audit §4.1 lists ~26 currently missing).
Icon-only buttons get `aria-label`. Meaningful icons (status, check/deny cells) get `aria-label` or a
real text label; never rely on glyph alone.

### 7.11 Browser surfaces (craft floor)

Theme from the palette: `::selection { background: var(--selection-bg); }`, `caret-color:
var(--caret-color)`, custom scrollbar (`--scroll-thumb`), `text-decoration` underline offset on links,
`::marker` for lists, tabular numerals. Focus ring themed (§7.2).

---

## 8. Implementation split, file ownership & migration maps

### 8.1 impl-core — `tokens.css`, `core.css`, `index.html`, `components.js`

1. **tokens.css** — rewrite to the two-layer model in §3. Keep the `:root` + `[data-theme="dark"]` +
   `[data-theme="light"]` structure. Add `html { font-size: 16px }`-equivalent root scale. Add
   `--surface-2`, `--border-control`, `--icon-1/2/3`, `--action-*` aliases, `--z-*`, `--focus-ring-*`,
   `--shadow-xs`, `--dur-overlay`, `--ease-exit`, `--selection-bg`, `--caret-color`, `--measure`,
   `--prose-max`, `--content-pad[-compact]`. **Remove `--font-serif`** (and ensure no remaining
   reference — impl-pages removes its uses). Redefine `--text-*` to the closed rem scale. Adjust light
   `--warning` to `#a85f06`. Keep `--brand-red/--brand-navy/--brand-light` identity values. Keep
   `--radius`, `--radius-lg`, etc. names; add `--radius-xs/-md/-2xl`.
2. **core.css** — rewrite primitives to §4: buttons (incl. 44px touch targets, `.spinner`), badges,
   cards, tables (tabular-nums, no `role` styling dependence), forms (tokenised select arrow via
   `currentColor`/mask, `--border-control`), segmented, chips (**remove `transition: all`**), tabs,
   empty, skeleton system (`.skeleton-table/.skeleton-list/.skeleton-kpi/.skeleton-panel`), toast,
   drawer, alert, kv, evidence-chip, json-block, dividers, misc; named type-style utilities (§3.2);
   focus-visible **outline** ring (no border-radius reset); selection/caret/scrollbar theming.
   **Delete** the `:focus-visible { border-radius }` rule. Add `.type-*` classes.
3. **index.html** — keep ids/classes in §4.17; refine shell markup for layout (allowed: add wrapper
   classes, container elements) **without** changing ids/`data-nav`/aria wiring/`lang`/meta/stylesheet
   order/`skip-link`. Remove nothing that `app.js` queries. Keep all 4 stylesheet links in order.
4. **components.js** — implement the helper API in §4.16 (new skeleton helpers, redefined
   `loadingBlock`), theme nothing else; **preserve** `workflowReportHtml`, `evidenceDrawerHtml`,
   `badge`, `emptyState` output strings/classes, `toast`, drawer behaviour. Update class names only
   where §4 requires; never change exported function names.

### 8.2 impl-pages — `app.css`, `institutional.css`, `views.js`, `knowledge.js`, `replay-panels.js`

1. **app.css** — shell layout (§4.17/§6.2); page scaffolding (`.page-head/.page-title/.section-title/
   .stack`); responsive breakpoints (§6); the **`.stack`/min-width:0 overflow fix (§6.1)**; overview,
   investigate, run-detail, library page classes; replay console classes. **Remove** all
   `font-family: var(--font-serif)`, `clamp()`, weights 720/750, background gradients, single-side
   borders, glow `box-shadow`, `transition: all`, and the dead `.pipeline` block. Convert inline-style
   hacks (`.replay-*`, `.plan-only-note`, `.replay-provenance`) to token-driven classes.
2. **institutional.css** — either **fold into app.css and delete** the duplicate `.hero/.page-title/
   .hero-kicker/.hero-title/.hero-desc` definitions, **or** keep the file but strip those duplicates and
   all serif/clamp/eyebrow/uppercase-CJK/single-side-stripe rules. **Single source of truth:** the
   final cascade must define each of `.hero*`/`.page-title` **once** (recommended: delete the hero
   block entirely; define `.page-title` once). Keep `.visually-hidden`, `.alert-success`,
   `.brand-rule` (sidebar identity), ACL/gate/invariant/eval page classes (restyled per §5.5/§5.6) only
   if they stay; otherwise move their restyled equivalents into app.css and delete institutional.css
   from `index.html` (**coordinate with impl-core**: removing a `<link>` is an index.html edit owned by
   impl-core — file a handoff note; simplest is to keep the file and empty it of duplicates).
3. **views.js** — overview restructure (§5.1): remove `.hero*`/eyebrow/serif classes; new contract
   panel, principle list, teaser sans-eyebrow; switch skeletons to new helpers; investigate empty/error
   fixes; run detail: remove `.hero-kicker`, report/teardown restyle, progress `--pct`, accessible rows;
   library column priority. **Preserve all ids/`data-*`/strings in Appendix A.**
4. **knowledge.js** — system/evaluation: remove eyebrow/serif/clamp/uppercase-CJK; restyle stage/gate/
   decision/invariant/finding/stat/tables per §5.5–5.6; keep all data and `data-tone` semantics; keep
   `heat()` logic but ensure tabular-nums + contrast.
5. **replay-panels.js** — remove `.hero-kicker` in `metadataHtml`; keep `PROVIDER UNKNOWN`/`SOURCE
   DRIFT`/`独立最终产物` strings and escaping; restyle `replay-role`/`replay-review`/`replay-reliability`
   panels (full borders, no stripes); keep all `data-*`/ids and exact copy asserted by tests.

### 8.3 Inline-style migration map (impl-pages)

| Location (baseline) | Inline style | Replace with |
|---|---|---|
| `views.js` several | `margin-bottom:6px` / `:8px` | class `.mb-2` (maps `--sp-2`) or gap on parent |
| `views.js` | `margin-bottom:var(--sp-5)` etc. | utility `.stack` gap / `.mt-*` classes |
| `views.js` `input-with-icon` wrappers | `flex:1;max-width:340/360px` | `.search-field` (max-width token) |
| `views.js` findings claim | `max-width:380px;font-weight:450` | `.cell-claim` class (`--text-base` 400) |
| `views.js` `#case-list` column header | `flex-direction:column;...gap:10px` | `.case-list-head` class |
| `views.js` progress bars | `style="width:88.9%"` | `--pct` custom property + CSS |
| `views.js` hero actions etc. | `style="margin-top:var(--sp-4)"` | utility `.mt-4` |
| `components.js` skeleton | `height:${height}px;margin-bottom:10px` | new skeleton helpers/classes |
| `knowledge.js` bars | `width:${pct}%` | `--pct` custom property (keep aria-hidden) |
| `views.js` report hero | `flex:1;min-width:220px` | `.report-hero-main` class |
| `views.js` `.evidence-toolbar` margin hack | `margin:calc(-1 * var(--sp-5))...` | `.card-flush .evidence-toolbar` class |

Utility classes to add (core.css): `.mt-2/.mt-3/.mt-4/.mt-6`, `.mb-2/.mb-3/.mb-4/.mb-5`,
`.m-0`, `.w-full`, `.search-field`, `.cell-claim`, `.report-hero-main`, `.case-list-head`,
`.num`, `.col-priority-1/2/3`, `.table--stack`, `.mb-0`.

### 8.4 Dead / duplicate CSS to remove (impl-pages)

- Overview `.hero`, `.hero-kicker`, `.hero-title`, `.hero-desc`, `.hero-split` (both app.css **and**
  institutional.css copies — define at most one, or none).
- `.pipeline`, `.pipeline-stage`, `.pipeline-stage::before/::after` (dead on Overview).
- `.eyebrow`, `.stage-n`, `.gate-n`, `.row-tag` display styling, `.brand-rule` under page head.
- `.page-title` duplicate serif rule (institutional.css) — single definition only.
- `.report-hero[data-status]` gradient backgrounds.
- `.sidebar-meta .dot { box-shadow: 0 0 8px }` glow.
- `.chip { transition: all }`.
- `.select` hardcoded `stroke='%23888'` arrow.
- Single-side borders on `.decision-card`, `.finding`, `.invariant`, `.plan-only-note`,
  `.replay-provenance`, `.boundary-card`, `.hero`.

### 8.5 Token naming reconciliation (baseline → v2)

Existing `--text-*` names retained with new rem values; `--bg-*`, `--border-*`, `--text-1/2/3`,
`--accent*`, `--success/warning/danger/info/neutral*`, `--radius*`, `--sp-*`, `--dur*`, `--ease`,
`--shadow-*`, `--sidebar-width`, `--topbar-height`, `--content-max` are all **retained**. New/added:
`--core-*`, `--surface-2`, `--border-control`, `--icon-1/2/3`, `--action-*`, `--z-*`,
`--focus-ring-*`, `--shadow-xs`, `--shadow-overlay`, `--dur-overlay`, `--ease-exit`, `--selection-bg`,
`--caret-color`, `--measure`, `--prose-max`, `--content-pad[-compact]`, `--radius-xs/-md/-2xl`,
`--sp-0/-0-5/-12/-16`, `--text-2xs`, `--text-4xl/-5xl`, `--leading-*`, `--tracking-*`. Removed:
`--font-serif`.

---

## 9. Verification & acceptance checklist

Every item must be **evidenced in a real browser** (Playwright is installed) plus the existing CI.

### 9.1 Maps 1:1 to the audit's prioritised opportunities

| # | Audit finding | Where resolved | How verified |
|---|---|---|---|
| 1 | Overview horizontal overflow at 834/390 | §6.1 (`.stack` `minmax(0,1fr)` + `min-width:0`) | measure `scrollWidth===innerWidth` at 834/390 on `#/` |
| 2 | Landing-page grammar (eyebrows, gradients, numbered rails, 3 equal cards, serif, clamp, weights 720/750, uppercase CJK, single-side stripes) | §5 each page, §8.4 | grep-style review + screenshots |
| 3 | CSS drift / undefined `--surface-2` / `transition:all` / select arrow / glow / duplicates / inline magic | §3.1, §8.3–8.5 | grep for removed patterns; token existence |
| 4 | Generic skeletons / centered spinner / investigate empty+error copy / no view error boundary | §4.10, §4.16, §5.2, §7.7 | screenshots of loading/empty/error; read copy |
| 5 | Data typography `tabular-nums`, text-wrap, min-w-0 | §3.2, §7.4, §7.5 | computed styles; long-copy screenshots |
| 6 | A11y: aria-hidden SVGs, no role on tr, focus radius, select arrow, 44px targets | §4, §7 | axe-style manual checks + browser focus/tab |
| 7 | Responsive structural plan across pages | §6 | 1440 / 834 / 390 screenshots per route, light+dark |

### 9.2 Acceptance criteria (the contract)

- [ ] **All staged skills read & synthesized** — §1 decision log with ADOPTED vs DROPPED and reasons.
- [ ] **Concrete tokens**: two-layer color model (both themes, hex + contrast), fixed-rem closed type
  scale with named styles, closed spacing scale, radius + nested formula, elevation, motion, z-index —
  exact CSS custom-property names (§3, Appendix B).
- [ ] **Every shared component with full state set** — buttons, inputs/selects, cards/panels, tables,
  tabs, badges/status pills, toast, drawer/modal, sidebar+topbar+mobile nav, skeleton, empty state,
  KPI/stat cards (§4).
- [ ] **Page-by-page layout + hierarchy** for overview, investigate, run detail, library, system design,
  evaluation across desktop ≥1280 / tablet 768–1024 / mobile ≤860 checked at 390, with **structural**
  responsive plan (sidebar collapse, responsive tables, breakpoint columns) (§5–6).
- [ ] **A11y + interaction spec**: contrast, focus-visible, keyboard/tab order, tabular-nums, text-wrap,
  min-w-0, aria-live, skip link, reduced-motion, overscroll containment (§7).
- [ ] **Hard invariants stated**: no business/API/route/permission/data changes; preserve every
  id/role/`data-*`/string asserted by `tests/web/browser.cjs`, `tests/integration/test_v12_ui.py`,
  `tests/web/*.test.mjs`; CSS-first minimal markup; no new deps; no `tests/` edits (§2, Appendix A).
- [ ] **Detailed enough for two parallel implementers on disjoint files** — §8 ownership + migration +
  contract surfaces.

### 9.3 Must-pass gates before the redesign is "done" (downstream stages)

1. `python -m ruff check src tests scripts` → PASS.
2. `python -m pytest -ra` → the baseline is 1179 passed / 1 pre-existing env failure
   (`test_v12_ui.py` shells out with Node-24-removed `--experimental-default-type=module`) / 2 skipped.
   On CI (Node 22) that test passes. **No new failures.**
3. `npm test` (Node 22 CI) → `tests/web/*.test.mjs` 23/23 pass.
4. `python scripts/run_mock_browser.py` (`browser.cjs`) → PASS desktop+mobile, no runtime errors, no
   `/api/run`.
5. Real-browser visual pass at 1440 / 834 / 390, light+dark, all six routes + loading/empty/error/
   drawer/toast states: **no horizontal overflow at 390 on any route**, focus rings visible, 44px
   targets, tabular numerals aligned, no eyebrow/serif/gradient/stripe regressions.
6. Diff review: no edits under `tests/`, `server.py`, `api.js`, `replay.js`; no new dependencies.

---

## Appendix A — Exact preserved test hooks

### A.1 `tests/web/browser.cjs` (CI, via `scripts/run_mock_browser.py`)

IDs: `#replay-position`, `#run-tab-panel`, `#replay-play`, `#replay-speed`, `#drawer`,
`#drawer-body`, `#drawer-close`, `#replay-seek`(range, exists), `#replay-jump`. Tabs by role/name:
`根因报告`, `证据登记`, `调查时间线`. Selectors: `[data-step=next|first|last]`, `[data-ev]`,
`#drawer:not([hidden])`. Strings: `not recorded`, `backend_pool_config_regression`, `已记录查询`,
`播放`/`暂停`. Layout gate: at `390×844`, `document.documentElement.scrollWidth <= window.innerWidth`
and `.replay-controls button` all `right <= innerWidth`. Fixtures `mock-missing`/`provider-failure`
reload to `#/run?path=fixture` and need non-empty `#run-tab-panel`.

### A.2 `tests/integration/test_v12_ui.py`

`workflowReportHtml(state, index)` must contain: `停止确认：已完成`, `终止结果`, `PLAN_ONLY`,
`PLAN_READY`, `FINISHED`, `e1`, `a1`, `rollback`, `precondition`; escape `<script>`→`&lt;script&gt;`;
and `workflowReportHtml({report:{status:'RESOLVED'}}) === ''`. (Also the Streamlit `ui/app.py` tests are
untouched — do not modify `src/incident_lens/ui/`.)

### A.3 `tests/web/*.test.mjs`

- `provisional-report.test.mjs`: `renderReport` contains `较可能（未确认）`, `待确认的解释`,
  `关键缺口`, `建议下一步`, `可选补充（不阻止作答）`, `data-evidence-id="E1"`, escapes `<img>`;
  `evidenceDrawerHtml` contains `用于待确认解释，尚未支持最终诊断`.
- `replay-demo.test.mjs`: `metadataHtml` contains `PROVIDER UNKNOWN`, `SOURCE DRIFT`, `独立最终产物`,
  escapes `<img>`; `workflowHtml` contains `仅审查建议 · 未调度`; `reviewTimelineHtml` contains
  `未按此 task_id 调度`.
- `replay.test.mjs`: `evidenceChips`/`evidenceDrawerHtml` escaping + disabled for inherited keys.

### A.4 Non-CI reference (`tests/web/browser-real.cjs`) — do NOT preserve `.hero-kicker`

References `.hero-kicker` (run-detail replay heading, `REAL LLM`/`MOCK`), `#replay-metadata`,
`#replay-reviews`, `#replay-history`, `#replay-workflow`, `#replay-selection`, `#replay-category`,
`#replay-events`, `#replay-demo`, `data-bookmark`, `[data-role]`, `data-evidence-id`, `#theme-toggle`.
Out of scope per the contract; do not reintroduce eyebrows. If ever run, its `.hero-kicker` selector
must be updated (a `tests/` edit, not ours). Keep the underlying provider label reachable as a badge.

### A.5 Data attributes & ids that JS reads (must survive)

`data-nav`, `data-theme`, `data-trace-path`, `data-demo-link`, `data-ev`, `data-evidence-id`, `data-role`,
`data-case`, `data-provider`, `data-source`, `data-tab`, `data-step`, `data-seek`, `data-bookmark`,
`data-kind`, `data-open`, `data-status`, `data-tone`, `data-current`, `data-drift`, `data-pressed`→
`aria-pressed`. Shell ids in §4.17; run/replay ids in views.js/replay markup; investigate run-config ids
in §5.2. Every one must remain queryable exactly as today.

---

## Appendix B — Full CSS custom-property index

**Layer 1 (core):** `--core-red-700`, `--core-red-300`, `--core-red-50`, `--core-navy-800`,
`--core-navy-900`, `--core-navy-300`, `--core-navy-350`, `--core-neutral-0/25/50/75/100/200/300/400/450/
500/600/700/800/850/900/950/1000/1050`, `--core-green-600/300`, `--core-amber-700/300`,
`--core-danger-600/300`, `--core-blue-700/300`.

**Layer 2 (semantic):** `--bg-app`, `--bg-surface`, `--bg-raised`, `--bg-overlay`, `--bg-inset`,
`--bg-hover`, `--bg-active`, `--bg-scrim`, `--surface-2`; `--border-subtle`, `--border`,
`--border-strong`, `--border-control`; `--text-1`, `--text-2`, `--text-3`, `--text-inverse`,
`--text-link`; `--icon-1`, `--icon-2`, `--icon-3`; `--accent`, `--accent-strong`, `--accent-active`,
`--accent-contrast`, `--accent-soft`, `--accent-border`, `--action-primary`, `--action-hover`,
`--action-pressed`, `--action-disabled-bg`, `--action-disabled-text`; `--brand-red`,
`--brand-red-soft`, `--brand-navy`, `--brand-light`; `--success`, `--success-soft`, `--success-border`,
`--warning`, `--warning-soft`, `--warning-border`, `--danger`, `--danger-soft`, `--danger-border`,
`--info`, `--info-soft`, `--info-border`, `--neutral-soft`, `--neutral-border`; `--code-bg`,
`--scroll-thumb`, `--selection-bg`, `--caret-color`.

**Typography:** `--font-sans`, `--font-mono`; `--text-2xs`, `--text-xs`, `--text-sm`, `--text-base`,
`--text-md`, `--text-lg`, `--text-xl`, `--text-2xl`, `--text-3xl`, `--text-4xl`, `--text-5xl`;
`--leading-tight`, `--leading-snug`, `--leading-normal`, `--leading-relaxed`; `--tracking-tight`,
`--tracking-normal`, `--tracking-wide`.

**Spacing:** `--sp-0`, `--sp-0-5`, `--sp-1`, `--sp-2`, `--sp-3`, `--sp-4`, `--sp-5`, `--sp-6`, `--sp-8`,
`--sp-10`, `--sp-12`, `--sp-14`, `--sp-16`.

**Radius:** `--radius-xs`, `--radius-sm`, `--radius`, `--radius-md`, `--radius-lg`, `--radius-xl`,
`--radius-2xl`, `--radius-full`.

**Elevation:** `--shadow-xs`, `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-overlay`.

**Motion:** `--dur-fast`, `--dur`, `--dur-slow`, `--dur-overlay`, `--ease`, `--ease-exit`.

**Z-index:** `--z-base`, `--z-sticky`, `--z-scrim`, `--z-sidebar`, `--z-overlay-backdrop`,
`--z-overlay`, `--z-toast`, `--z-skip-link`.

**Focus / layout:** `--focus-ring-width`, `--focus-ring-offset`, `--focus-ring-color`,
`--sidebar-width`, `--topbar-height`, `--content-max`, `--content-pad`, `--content-pad-compact`,
`--measure`, `--prose-max`.

**Named type-style classes:** `.type-heading-1..4`, `.type-title-1..3`, `.type-body-1..3`,
`.type-button-lg/md/sm`, `.type-caption-1/2`.

**Utility classes:** `.mt-2/3/4/6`, `.mb-2/3/4/5`, `.mt-0`, `.m-0`, `.w-full`, `.search-field`,
`.cell-claim`, `.report-hero-main`, `.case-list-head`, `.num`, `.col-priority-1/2/3`, `.table--stack`,
`.mono`, `.visually-hidden`, `.text-muted`, `.text-secondary`.

---

*End of spec. This document is the contract for `t2`; downstream implementation must not require any
further design decision. If a genuine gap is found, record it in the task output rather than inventing a
value.*
