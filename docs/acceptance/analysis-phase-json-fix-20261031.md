# Analysis phase JSON repair — 2026-10-31

The local-gateway development batch exposed a protocol error: database analysis
sometimes returned DeepSeek DSML tool-call markup in `message.content` instead of
the required `AnalysisOutput` JSON. The planning prompt was also used after tools
had already run, while analysis context still advertised tool permissions and a
remaining execution budget. A generic JSON retry could repeat that mistake.

The user explicitly authorized lifting the source freeze for this fix, followed
by a separate commit and push. Existing experiment manifests and recorded results
remain evidence of their original source snapshots; this change does not revise
them or claim a new complete four-architecture evaluation.

## Changed behavior

- Analysis now has an explicit phase contract and role-specific interpretation
  guidance, separate from instructions for planning tool calls. Additional work is
  represented as `requested_checks` for later coordinator scheduling.
- The analysis request retains runtime identity, the original task scope and
  fetched records, while omitting execution authority and remaining tool-call
  budget from its context. Planning still receives its original permissions and
  typed tool argument schemas.
- A non-JSON response starting with a recognized DSML delimiter remains
  `INVALID_JSON`, with a safe `tool_call_markup` shape diagnostic. Targeted repair
  explains the phase/protocol mistake without replaying untrusted output, tool
  names or arguments. This uses the existing recovery-enabled provider path and
  keeps the existing one-repair/request-budget limits.
- The prompt version is advanced to isolate semantic-cache entries generated
  under the old prompts. JSON, citation and identity validation are preserved;
  tool markup is neither accepted as an analysis nor executed.

## Validation

Targeted offline checks: **120 passed, 1 skipped**, covering structured-output
validation, the production provider recovery path, database behavior, all four
specialist roles under specialist/single identities, planning authority, repair
success/exhaustion, sensitive-output non-disclosure, and fabricated-citation
rejection. Ruff (`src tests scripts`) and whitespace checks passed.

Full offline regression: **1146 passed, 3 skipped** in 431.26 seconds with
`PYTHONUTF8=1`, `PYTHON_DOTENV_DISABLED=1`, and
`INCIDENT_LENS_OFFLINE_TESTS=1`. All three skips concern unavailable Windows
symlink privileges. The command was
`python -m pytest -q -ra --junitxml=results/acceptance/analysis-phase-fix-20261031/pytest.xml`.

The live checks reconstruct the six originally failed analysis tasks and public
records. They exercise the changed production `analyze()` function through the
current local gateway, with at most two HTTP requests per task and no transport
retry. They do not run planners, execute tools, or evaluate complete diagnoses.
All **6/6** tasks passed through the changed production analysis boundary on their
first response: **6 HTTP requests, 0 repairs**, HTTP 200 and `finish_reason=stop`
throughout. Gateway usage records matched each request to
`workbuddy / deepseek-v4.1-flash`. The existing dynamic citation schema and
post-generation identity checks ran for every result. This is output-contract
verification, not independent validation of diagnosis correctness or a complete
investigation acceptance result.

The adjacent JSON contains the sanitized per-task receipt and source hashes.
Detailed local receipts are in
`results/acceptance/analysis-phase-fix-20261031/`; only a sanitized validation
summary is intended for publication.
