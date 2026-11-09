# Palette revision v3 — PolyU-informed colour system

> **Superseded (2026-11-09):** the colour hex values below are historical. The web UI now uses
> the **Meta Astryx** palette — see [`astryx-integration-spec.md`](astryx-integration-spec.md).
> Token names, layout and accessibility rules from this document still apply; only the colour
> values changed (PolyU red removed, Astryx blue accent + teal data scale).

> Scope: colour tokens only. This revision remaps the two-layer colour system in
> `src/incident_lens/web/static/css/tokens.css` to a palette derived from **The Hong Kong
> Polytechnic University** website. It **supersedes the colour hex values in
> `docs/ui/redesign-v2.md` §3** (the token *names*, type/spacing/radius/motion scales and all
> component/layout/a11y rules are unchanged). Everything else in v2 still applies.

## Source

Colours were mined from PolyU's own stylesheet rather than guessed:

- Page: <https://www.polyu.edu.hk/>
- Stylesheet: <https://www.polyu.edu.hk/assets/css/style.css>

Most frequent brand hexes found in that stylesheet:

| Hex | Occurrences | Role on polyu.edu.hk |
|---|---|---|
| `#a02337` | 638 | PolyU primary red (institutional chrome) |
| `#c80f2e` | 275 | Brighter PolyU red (emphasis / hover) |
| `#454545` / `#58595b` / `#717171` | 316 / 149 / 145 | Neutral text greys |
| `#123663` / `#2840a8` / `#0071bb` | 139 / 140 / 138 | Deep-blue → bright-blue family |
| `#2b8054` / `#397e39` | 142 / 140 | Success greens |
| `#b68f16` / `#ecca5f` | 52 / 86 | Gold/yellow accents |
| `#f4f4f4` / `#f8f8f8` / `#d5d5d5` / `#c0bfbf` | 130 / 21 / 53 / 91 | Neutral surfaces & borders |

We keep the product's established **two-layer token model** (raw `--core-*` → semantic
surface/border/text/icon/action/state, light + dark). Only the hex values change. Accent stays a
single interactive blue (PolyU deep blue `#123663`) so status semantics (success/warning/danger)
stay distinct from the institutional red.

## Core palette (Layer 1) — changed values

| Token | v2 (old) | v3 (PolyU) | Note |
|---|---|---|---|
| `--core-red-700` | `#9a0907` | **`#a02337`** | PolyU primary red; 7.5:1 on white |
| `--core-red-300` | `#d0574e` | **`#e08a93`** | dark-theme chrome; 7.3:1 on `#121212` |
| `--core-red-50` | `#f7e9e8` | **`#f8e9ec`** | soft tint |
| `--core-navy-800` | `#003070` | **`#123663`** | PolyU deep blue; interactive accent, 12.1:1 on white |
| `--core-navy-900` | `#00224f` | **`#0d274a`** | hover/pressed |
| `--core-navy-300` | `#86a9e0` | **`#7fb4e6`** | dark-theme accent; 8.5:1 on `#121212` |
| `--core-navy-350` | `#aac6ee` | **`#a7cdf0`** | dark accent-hover |
| `--core-neutral-*` | purple-tinted greys | **true neutral greys** (`#f4f4f4`, `#ededed`, `#d5d5d5`, `#c0c0c0`, `#8f8f8f`, `#6b6b6b`, `#58595b`, `#454545`, `#333333`, `#1f1f1f`, `#121212`, `#0d0d0d`) | removes the faint violet cast; matches PolyU's `#454545/#58595b/#717171` text family |
| `--core-green-600/300` | `#087b4d` / `#3dd68c` | **`#2b8054` / `#4cc38a`** | PolyU green; 4.9:1 / 8.5:1 |
| `--core-amber-700/300` | `#a85f06` / `#f5b93d` | **`#8a6d10` / `#e7c15a`** | PolyU gold; 4.9:1 / 10.9:1 |
| `--core-danger-600/300` | `#d23b3f` / `#f47174` | **`#c62828` / `#f08a86`** | 5.6:1 / 7.8:1 |
| `--core-blue-700/300` | `#1f6fd6` / `#5eb0f6` | **`#1c6bb0` / `#6fb2e8`** | PolyU blue; 5.6:1 / 8.2:1 |

Also updated to stay consistent with the new hexes: every `rgba()` overlay/soft/border/shadow tint
(hover/active, borders, soft state chips, focus/scrim, brand-red-soft, accent-soft) and the favicon /
`<meta name="theme-color">` in `index.html` (now `#a02337`).

## Light theme semantic result

- Ground `#f4f4f4`, surface `#ffffff`, inset `#ededed` (PolyU's neutral surfaces).
- Text: `#333333` (primary, 12.6:1), `#58595b` (secondary, 7.0:1), `#6b6b6b` (tertiary, 4.9:1 on app ground).
- Accent (primary action/focus/link): `#123663`; white text on it = 12.1:1.
- Brand red `#a02337` (chrome/logo rule only, never status).

## Dark theme semantic result

- Ground `#0d0d0d`, surface `#121212`, raised `#1f1f1f`, inset `#0a0a0a` (neutral charcoal, no colour cast).
- Text `#f5f5f5` / `#b3b3b3` / `#8f8f8f`.
- Accent `#7fb4e6` (dark-on-light button text `#0a1420`), brand red `#e08a93`.

## Accessibility (WCAG 2.x) — measured

| Pair | Ratio | Min |
|---|---|---|
| light text-1 `#333333` / white | 12.63 | 4.5 |
| light text-2 `#58595b` / white | 7.01 | 4.5 |
| light text-3 `#6b6b6b` / `#f4f4f4` | 4.85 | 4.5 |
| white / accent `#123663` | 12.11 | 4.5 |
| white / brand red `#a02337` | 7.53 | 4.5 |
| white / success `#2b8054` | 4.86 | 4.5 |
| light warning `#8a6d10` / white | 4.91 | 4.5 |
| light danger `#c62828` / white | 5.62 | 4.5 |
| light info `#1c6bb0` / white | 5.56 | 4.5 |
| dark text-1 `#f5f5f5` / `#121212` | 17.18 | 4.5 |
| dark text-3 `#8f8f8f` / `#121212` | 5.79 | 4.5 |
| dark accent `#7fb4e6` / `#121212` | 8.54 | 4.5 |
| dark success/warning/danger/info / `#121212` | 8.46 / 10.86 / 7.75 / 8.22 | 4.5 |
| border-control `#8a8a8a` / white (UI) | 3.45 | 3.0 |

## Verification

- Real browser (Playwright, Chromium): 6 routes × desktop 1440 / tablet 834 / mobile 390 × light & dark
  → **0 horizontal overflow, 0 page/console errors**. Screenshots: `docs/ui/redesign-v2/palette-*.png`
  plus full set under `results/ui-redesign/palette-v3/`.
- `ruff` ✅; `node --test tests/web/*.test.mjs` 23/23 ✅; `scripts/run_mock_browser.py` ✅
  (selectors/ids/roles/replay/drawer/mobile guard intact).
- Full `pytest` and GitHub "Offline CI" (Node 22) re-run on the PR after this commit.

## Files changed in this revision

- `src/incident_lens/web/static/css/tokens.css` — colour tokens (Layer 1 + both theme Layer 2 blocks).
- `src/incident_lens/web/static/index.html` — favicon + `theme-color` red.
- `docs/ui/palette-v3-polyu.md` (this file) + `docs/ui/redesign-v2/palette-*.png` (screenshots).

No component logic, layout, API, route, permission or data changes.
