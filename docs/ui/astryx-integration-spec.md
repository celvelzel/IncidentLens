# Astryx Frontend Integration Spec

Goal: improve the IncidentLens dashboard (vanilla-JS SPA served by `incident_lens.web`) using
**Meta's Astryx design system** (`@astryxdesign/core` 0.7.11) — its color palette, radii,
shadows, motion, and component conventions — without changing application logic or the
information architecture.

> **Status: shipped (2026-11-09).** This document is the current authority for the web UI's
> visual language. It **supersedes** the colour hex values in
> [`palette-v3-polyu.md`](palette-v3-polyu.md) and the colour section (§3) of
> [`redesign-v2.md`](redesign-v2.md); token names, layout and a11y rules from those documents
> still apply.

## Final applied design (round 2)

The first integration kept PolyU red for the brand mark and the evaluation page. Round 2
removed red entirely in favour of one harmonious Astryx palette:

- **Theme / interactive accent:** Astryx blue `--color-accent` (`#0064E0` light / `#0171E3`
  dark). Replaces the PolyU-red brand colour everywhere (brand mark, sidebar rule, favicon,
  `theme-color`, "PRIMARY" row tint, Dynamic bars). One accent across buttons, links, focus and
  data emphasis.
- **Evaluation heatmap (`难度杠杆下的表现`):** 5-band sequential **Astryx data-teal**
  (`--color-data-teal-1..5`), text ink per band chosen for ≥4.5:1 contrast
  (band ratios ≈ 13.10 / 9.53 / 5.75 / 4.96 / 5.39). No red.
- **Primary architecture column:** the `Dynamic` column header is accent-coloured + `700`;
  its body cells are `700` while the other three columns are `600` (`col-dynamic`).
- **Unified columns:** the four architecture columns share equal widths
  (`table-layout: fixed`; first column 22 %, each architecture column 19.5 %).
- **No application logic, routes or Chinese copy changed.** Example verifier:
  `tests/web/browser.cjs`.

## What is already vendored

- `src/incident_lens/web/static/css/astryx.css`
  = the pre-compiled Astryx core CSS (`package/dist/astryx.css`). It defines the full Astryx
  design-token set as CSS custom properties on `:root` (`--color-*`, `--font-size-*`,
  `--text-heading-*`, `--spacing-*`, `--radius-*`, `--shadow-*`, `--duration-*`, `--ease-*`,
  `--size-element-*`, ...). It uses `light-dark()` so it follows `color-scheme`.
  It contains **no global element selectors** (only hashed atomic classes), so importing it is
  conflict-free.
- `astryx.css` has NO `color-scheme` of its own: the existing `tokens.css` already sets
  `color-scheme: light` on `:root,[data-theme="light"]` and `dark` on `[data-theme="dark"]`,
  which is exactly what `light-dark()` needs. Keep that.

## Wiring (index.html)

Load Astryx first, then the app tokens, then component layers, then the new bridge last:

```html
<link rel="stylesheet" href="css/astryx.css">
<link rel="stylesheet" href="css/tokens.css">
<link rel="stylesheet" href="css/core.css">
<link rel="stylesheet" href="css/app.css">
<link rel="stylesheet" href="css/institutional.css">
<link rel="stylesheet" href="css/astryx-bridge.css">
```

Keep `<html lang="zh-CN" data-theme="light">`. No new attributes are required (the app's
`data-theme` drives `light-dark()`).

## Token bridge (rewrite the Layer-2 semantic blocks of tokens.css)

Keep the `--core-*` raw palette and the scale sections, but re-point the semantic Layer-2
tokens at Astryx tokens so every existing component inherits the new system. Recommended map
(app token ← Astryx token):

| app token | Astryx token |
|---|---|
| `--bg-app` | `var(--color-background-body)` |
| `--bg-surface` | `var(--color-background-surface)` |
| `--bg-raised` | `var(--color-background-card)` |
| `--bg-overlay` | `var(--color-background-popover)` |
| `--bg-inset` | `var(--color-background-muted)` |
| `--surface-2` | `var(--color-background-card)` |
| `--bg-hover` | `var(--color-overlay-hover)` |
| `--bg-active` | `var(--color-overlay-pressed)` |
| `--border-subtle` / `--border` | `var(--color-border)` |
| `--border-strong` / `--border-control` | `var(--color-border-emphasized)` |
| `--text-1` | `var(--color-text-primary)` |
| `--text-2` | `var(--color-text-secondary)` |
| `--text-3` | `var(--color-text-disabled)` |
| `--text-inverse` | `var(--color-on-accent)` |
| `--text-link` | `var(--color-text-accent)` |
| `--icon-1/2/3` | `var(--color-icon-primary/secondary/disabled)` |
| `--accent` / `--action-primary` | `var(--color-accent)` |
| `--accent-strong` / `--action-hover` | `var(--color-accent-strong, var(--color-accent))` |
| `--accent-active` | `color-mix(in srgb, var(--color-accent) 86%, #000)` |
| `--accent-contrast` | `var(--color-on-accent)` |
| `--accent-soft` | `var(--color-accent-muted)` |
| `--accent-border` | `var(--color-border-emphasized)` |
| `--success` / `--success-soft` / `--success-border` | `var(--color-success)` / `var(--color-success-muted)` / `var(--color-background-green)` |
| `--warning*` | `var(--color-warning)` / `var(--color-warning-muted)` / `var(--color-background-yellow)` |
| `--danger*` | `var(--color-error)` / `var(--color-error-muted)` / `var(--color-background-red)` |
| `--info*` | `var(--color-info)` / `var(--color-info-muted)` / `var(--color-background-blue)` |
| `--neutral-soft` / `--neutral-border` | `var(--color-background-gray)` / `var(--color-border-gray)` |
| `--shadow-xs` / `--shadow-sm` | `var(--shadow-low)` |
| `--shadow-md` | `var(--shadow-med)` |
| `--shadow-lg` / `--shadow-overlay` | `var(--shadow-high)` |
| `--radius-xs` / `--radius-sm` | `var(--radius-inner)` |
| `--radius` / `--radius-md` | `var(--radius-element)` |
| `--radius-lg` | `var(--radius-container)` |
| `--radius-xl` / `--radius-2xl` | `var(--radius-page)` |
| `--radius-full` | `var(--radius-full)` |
| `--dur-fast` / `--dur` | `var(--duration-fast)` |
| `--dur-slow` / `--dur-overlay` | `var(--duration-medium)` |
| `--ease` | `var(--ease-standard)` |
| `--ease-exit` | `var(--ease-exit)` |
| `--focus-ring-color` | `var(--color-accent)` |

Notes:
- Astryx accent (light) is `#0064E0` blue and (dark) `#0171E3` — one accent for interaction
  **and** brand identity. The PolyU red has been removed entirely: `--brand-red` /
  `--brand-red-soft` now alias `--color-accent` / `--color-accent-muted` (brand mark, sidebar
  rule, favicon, `theme-color`, evaluation emphasis all use the Astryx accent).
- Keep the existing CJK-tuned `--text-*` font sizes (14–40px) rather than shrinking to Astryx
  px scale; only adopt Astryx font weights (`--font-weight-medium/semibold`), families
  (`--font-family-*`), radii, colors, shadows, motion.
- Disabled text: prefer `var(--color-text-disabled)`.

## Component bridge (new file `astryx-bridge.css`, loaded last)

Restyle these toward Astryx conventions using Astryx tokens. Keep class names; do not change
markup or JS unless strictly required (a tiny class tweak is acceptable if documented).

- **Buttons** `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.btn-sm/.btn-lg`:
  height `var(--size-element-md)` (sm → `--size-element-sm`, lg → `--size-element-lg`),
  radius `calc(var(--radius-element) - var(--spacing-1))`, `font-weight: var(--font-weight-medium)`,
  inline padding `var(--spacing-3)`, gap `var(--spacing-1-5)`. Primary: bg `--color-accent`,
  color `--color-on-accent`; hover `color-mix(in srgb, var(--color-accent) 90%, #000)`;
  ghost/secondary: transparent bg, `border: 1px solid var(--color-border)`, hover
  `var(--color-overlay-hover)`. Smooth `transition: background var(--duration-fast) var(--ease-standard)`.
- **Badges/pills** `.badge*`, `.chip`, `.evidence-chip`, `.segmented`: radius `--radius-full`,
  padding `var(--spacing-0-5) var(--spacing-2)`, `font-size: var(--font-size-sm)`,
  bg `*-muted` + color `--color-text-*`. Active chip/segment: accent bg + on-accent text.
- **Cards/panels** `.card`, `.panel`, `.orch-panel`, `.boundary-card`, `.chart-card`:
  bg `--color-background-surface`, `border: 1px solid var(--color-border)`,
  radius `var(--radius-container)`, `box-shadow: var(--shadow-low)`, padding `var(--spacing-4)`.
  `.card-header` title `font-weight: var(--font-weight-semibold)`.
- **Inputs/selects** `.input`, `.select`, `.search-field`: height `--size-element-md`,
  radius `--radius-element`, border `var(--color-border-emphasized)`, inline padding
  `var(--spacing-3)`, bg `--color-background-surface`; focus → `--focus-ring-*`.
- **Tabs** `.tabs`, `.tab`: active tab 2px bottom indicator `var(--color-accent)`,
  inactive text `--color-text-secondary`, hover `--color-overlay-hover`, radius top
  `--radius-inner`.
- **Nav** `.nav-item`: radius `--radius-element`; hover bg `--color-overlay-hover`;
  `[aria-current="page"]` bg `--color-accent-muted`, text/icon `--color-accent`, `font-weight: var(--font-weight-medium)`.
- **Table** `.table-wrap table` (and `.eval-table`, `.acl-table`, `.lever-table`): header bg
  `--color-background-muted`, color `--color-text-secondary`, `font-size: var(--font-size-sm)`,
  weight medium; row border-bottom `1px solid var(--color-border)`; row hover
  `var(--color-overlay-hover)`; cell padding `var(--spacing-2) var(--spacing-3)`.
- **KPI/stat** `.kpi`, `.stat`: value `font-size: var(--font-size-2xl)` weight semibold,
  label `--color-text-secondary`; keep accent color for the positive/primary stat.
- **Topbar/sidebar** `.topbar`: bg `color-mix(in srgb, var(--color-background-surface) 88%, transparent)` +
  `backdrop-filter: blur(8px)`, border-bottom `1px solid var(--color-border)`. `.sidebar`:
  bg `--color-background-surface`, border-right `1px solid var(--color-border)`.
- **Overlays** `.drawer`, `.toast`, `.drawer-backdrop`: radius `--radius-container` (drawer),
  shadow `--shadow-high`, backdrop `--color-overlay`.
- **Focus**: one rule — `:where(.btn,.input,.select,.nav-item,.tab,.chip,.icon-btn,[tabindex]):focus-visible`
  → `outline: var(--focus-ring-width) solid var(--focus-ring-color); outline-offset: var(--focus-ring-offset)`.

## Guardrails

- Do **not** change DOM structure, JS behaviour, routes, API, or Chinese copy.
- Do **not** touch `astryx.css` (vendored, generated).
- Verify both `data-theme="light"` and `data-theme="dark"`, desktop 1440px and mobile 390px,
  on all six routes: `#/`, `#/investigate`, `#/library`, `#/run?path=...`, `#/system`, `#/evaluation`.
- Zero console errors. No horizontal overflow on mobile.
