# V1.6 Investigation Replay — WP-C

Scope: existing run detail (`renderRun`), no backend route or schema changes. Evidence class: OFFLINE_MOCK / ADAPTER_FIXTURE; no real provider requests.

Implemented: pure `replayReducer` / `replayPrefix`; first/previous/play/pause/next/last with 1×/2×/4×; workflow roles and recorded task status; event selector showing actual structured decisions/reviews/findings and evidence; ordered hypothesis status history; prefix-gated existing timeline/hypothesis/evidence/finding/report views. Missing historical fields say `not recorded`. Report Markdown is gated by a recorded REPORT event. Recorded Replay and MOCK/REAL remain visible. Buttons use existing focus styles and semantic controls; controls wrap on narrow screens.

Evidence authorization requires same incident/run successful TOOL_CALL, role/tool ACL, tool/source binding, public-summary service membership and exact final-authorized record equality. Final evidence index alone never grants prefix visibility. Inspector shows escaped excerpt/source plus recorded event/task/call/query provenance. Unknown, future, mismatched and unavailable evidence buttons are disabled. No replay operation calls /api/run, providers or tools. Server remains authoritative for path confinement and private-field rejection.

## Validation

All commands ran from `.worktrees/v16-c`, using MAIN `.venv` with `PYTHONPATH=<worktree>/src` where applicable:

- `node --experimental-default-type=module --test tests/web/replay.test.mjs`: exit 0, 10 passed. Covers saved success/missing/provider-failure fixtures, deterministic stepping, source immutability, absent history, report gating, same incident/run, failed calls, mismatched records, role/tool/source binding, escaped XSS and no execution capability.
- `../../.venv/Scripts/python.exe -m pytest tests/integration/test_web.py -q`: exit 0, 6 passed in 8.28s. Existing API replay/no reexecution/path confinement regression.
- `../../.venv/Scripts/python.exe -m ruff check tests/web`: exit 0.
- `git diff --check`: exit 0 (Windows LF/CRLF advisory only).
- Start `../../.venv/Scripts/python.exe -m uvicorn incident_lens.web.server:app --host 127.0.0.1 --port 8766`; then `node tests/web/browser.cjs`: exit 0. Uses installed bundled Playwright and existing Chromium 1217; environment overrides PLAYWRIGHT_MODULE/CHROMIUM_PATH supported. Verified 1440×1000 desktop and 390×844 mobile, playback and speed, first/next/last, prefix report absence/final presence, provenance drawer, saved missing/failure traces, controls inside viewport, no page errors and zero /api/run requests. API replay response is intercepted with saved fixtures; static SPA is served by actual local server. This is browser fixture evidence, not live model evidence.

Screenshots: [desktop](v16-evidence/desktop.png), [mobile](v16-evidence/mobile.png). Visually inspected mobile screenshot; transitions settle before capture.

Fixtures: mock-success is the unmodified public saved G0 Mock trace from MAIN `results/v16/preflight/m0-20261015-01/mock-positive/trace.json` (JSON whitespace changed only). `tests/web/generate_fixtures.py` captures actual local Mock missing incident_006 and injected provider-error graph runs. No fixture is represented as live provider success.

## Reproducible 2–3 minute demo

1. 0:00–0:25 Open saved Mock success. Point out Recorded Replay, MOCK and source fingerprint `not recorded`. Initial report/evidence/hypotheses are absent. Open report tab to verify no final-state backfill.
2. 0:25–1:10 Play at 4×, pause at the first MERGE. Select recorded DECISION/TOOL_CALL/MERGE events. Inspect the rejected postgres hypothesis and normal database metrics. These are actual recorded findings, not generated dialogue.
3. 1:10–1:50 Step through REVIEW then coordinator DECISION dispatching Changes, configuration diff and subsequent review. Select the event to show role/task/evidence, and open an authorized evidence chip to inspect excerpt and recorded query provenance.
4. 1:50–2:15 Jump to last, open report and confirm backend_pool_config_regression. Jump to first again and verify report disappears. Contrast saved missing incident_006 and injected provider-failure fixtures.
5. 2:15–2:40 Resize to mobile, use keyboard Tab/Enter on controls, pause/play and change speed. State explicitly that playback creates no new requests to /api/run.

## Limits / unmet acceptance

No fresh real-provider success was authorized or obtained, so G3 live-success evidence remains upstream. Browser tested three saved offline fixtures; real API execution and paid-provider reliability are untested. Old traces without observations/hypothesis events intentionally lose unrecoverable historical views. Workflow directions are exposed by actual role/task event selection; no inferred communication arrows or fabricated natural-language messages. Backend path/security integration must be revalidated after Lead cherry-picks. Pure reducer copies prefixes; very large traces beyond these fixtures have not been load-tested.

## Final Lead integration verification
Final Node13passed and backend Web/replay regression included in full950passed3skipped. Actual non-intercepted backend browser checks3saved traces, no/api/run/pageerrors; final settled desktop/mobile screenshots replace initial worker captures in v16-evidence/. Original captures retained under results/v16/integration/20261015-01/worker-*-before-qa.png. Findings now4unique instead of9cumulative duplicates; unchanged hypothesis snapshots do not create false evolution. Final browser receipts/screenshots: results/v16/final-qa/20261015-02/browser-final/. G3 PASS for recorded Mock/fixture engineering only; no real success demo.
