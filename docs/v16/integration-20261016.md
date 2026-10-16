# V1.6 main integration — 2026-10-16

## Delivered

- G1a transport rescue and one-shot changes discovery: 1533040.
- WP-B: merged codex/wp-b-finalization through f775f32; frozen owner-accepted development corpus, evaluation isolation and handoff.
- WP-C: merged codex/wp-c-real-replay through 2a9a63f; recorded real T5 replay, metadata and evidence views.
- T5 checklist accepted by explicit user instruction; source drift remains disclosed. T6 deferred by user; all prior failed attempts retained. G1a overall/frozen-source research acceptance remains incomplete.

## Combined-tree checks

No full suite or paid calls rerun. Existing worker full-suite receipts remain branch-specific.

- `.venv/Scripts/python.exe -m pytest -q tests/integration/test_rescue_finalization.py tests/unit/test_agents.py tests/integration/test_web_replay_metadata.py tests/integration/test_wp_b_download_isolation.py tests/incidentbench/test_wp_b_finalization.py tests/incidentbench/test_wp_b_evaluation.py`: 54 passed in 51.86s, exit 0.
- `node --experimental-default-type=module --test tests/web/replay.test.mjs tests/web/replay-demo.test.mjs`: 20 passed, 1 optional real-trace test skipped, exit 0. Then set WP_C_REAL_TRACE to the retained T5 trace and reran replay-demo.test.mjs: 8 passed, 0 skipped, exit 0, covering that optional case.
- `.venv/Scripts/python.exe -m ruff check src scripts tests`: all checks passed, exit 0.
- No new integrated browser validation; prior WP-C actual-browser receipts retained in its acceptance record.

## Preservation and next steps

All existing worktrees and branches retained because ignored/private/raw evidence is not transferred by Git merges. No results, credentials or private Oracle files staged. User V1.6 plan/start documents preserved and included for repository traceability. No push or version tag created. This is a V1.6 engineering integration, not full research acceptance; package version was not changed.

Next: deferred T6 and frozen-source positive acceptance when resumed; then bounded explicitly budgeted WP-D development pilot. Formal independent/blind review and G1b reliability remain separate pending work.
