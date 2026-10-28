# PR validation — 2026-10-28

Publication checks after the best-supported root selection and evidence-board changes:

- `INCIDENT_LENS_OFFLINE_TESTS=1 .venv/bin/python -m pytest tests -q --tb=short`: **1130 passed, 3 skipped**.
- Bundled Node `--test tests/web/*.test.mjs`: **23 passed**.
- `.venv/bin/ruff check src tests scripts`: passed.
- `git diff --check`: passed.

New coverage checks mechanism-free abstention, real counterevidence, residual causal limits, service-owned versus client failure logs, category/scope coverage, leading-review consistency, and strict argument limits. Older tests were aligned to the explicitly authorized best-supported policy; contradictory evidence and stale-review protection remain tested.

No additional live model calls or experiments were performed for PR preparation. The Dev10 live metrics in `dev10-best-supported-20261028.md` identify their earlier frozen snapshot; subsequent publication fixes were checked offline and did not rewrite those results. Mock browser acceptance and Windows execution were not run locally; the repository CI retains those checks.
