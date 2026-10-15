# V1.6 offline E2E preparation

WP-A, baseline `62ec53475f4f4c71b9e1cccf33532763c90156f2`, branch `codex/v16-a`.
Evidence: UNIT / OFFLINE_MOCK; zero real provider requests. G1a/G1b remain
BLOCKED_AWAITING_USER. No semantic review or live success is certified.

`scripts/v16_e2e_preflight.py` reads public development inputs and saved artifacts,
hashes public files/protocol/current source, recomputes the existing termination
evaluator, compares saved result/trace, and prepares argument arrays for the existing
`retest_live_provider_fix.py`. It does not load `.env`, credentials, private labels,
instantiate a provider, probe endpoints, or execute prepared commands. Output must
be a new directory; input failure exits 1 and records a failure receipt. Exit 0
means input preparation completed, **not G1 acceptance**. Every historical artifact
stays in the report, including missing/malformed/failed artifacts.

Technical screening requires measured HTTP requests, no declared bridge/continuation,
matching current source lock, complete valid STOP, consistent nonempty reports and
the expected incident/status/termination. Even a matching real envelope cannot
authenticate its execution origin or prove semantic correctness, so `live_verified`
and `g1_accepted` always remain false. Fixture and continuation metadata can only
exclude evidence; they cannot authenticate live execution. Unknown semantic support
remains null. A fresh approved run needs independent execution-provenance and human
or trusted development-oracle review before Lead accepts G1.

Verified local inputs (relative to MAIN repository):

- Dataset: `results/incidentbench/v1/20261013-deepseek-development-pilot/dataset`.
  Both `rca/incidents/incident_2001/public` and `incident_2002/public` exist.
- Protocol: `results/incidentbench/v1/user-retest-reconciliation/pilot-protocol-retest-v4.json`.
  Real development-visible, deepseek-v4-flash-0731, JSON Schema, cache off,
  request timeout 300s, 32 LLM calls, 24 tools, 6 rounds, 3600s wall.
  These are historical protocol limits, not current user approval.
- Saved real v4 `.../real-v4-wall3600-req300/full` is a technical failure
  (`UNRECOVERABLE_ERROR`) and differs from current source. It remains failed.
- `results/acceptance/finalize-resume-20261015/checkpoint-continuation` lacks
  the runner's scope receipt and cannot qualify as a new live run.

Run from the worktree with MAIN's interpreter and isolated imports:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& ../../.venv/Scripts/python.exe scripts/v16_e2e_preflight.py --dataset ../../results/incidentbench/v1/20261013-deepseek-development-pilot/dataset --protocol ../../results/incidentbench/v1/user-retest-reconciliation/pilot-protocol-retest-v4.json --positive-artifact ../../results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/full --positive-artifact ../../results/acceptance/finalize-resume-20261015/checkpoint-continuation --out results/v16/wp-a/NEW-UNIQUE-DIRECTORY
```

The receipt contains prepared positive/negative `commands_argv_NOT_EXECUTED`.
Replace their output placeholder with fresh unique paths after explicit approval
specifies model/config and total request/token/cost/wall limits. Configuration
matching and proxy/schema/timeout compatibility are unverified; check them only
within the authorized live budget. Correct RCA and justified abstention still need
semantic evidence review. Unknown dollar cost stays unknown.

Validation on 2026-10-15, raw root in this worktree:
`results/v16/wp-a/offline-20261015-01/` (ignored, never staged).

- `regression.log`, exit 0: 267 passed in 18.12s across new preflight, finalize
  guards, provider recovery, STOP scoring, review boundary, graph, agent evidence
  discovery/identity, report grounding, provider runtime, bridge, fault matrix and
  active investigation tests. This preceded the final runner metadata patch.
- `final-tests.log`, exit 0: 15 passed in 6.23s on final preflight/runner changes.
  Four offline-injected runner tests exercise all variants and verify saved variant
  metadata. This fixes the existing runner's default-full envelope mislabel.
- `ruff.log`, exit 0: all three changed Python files pass. `git diff --check` exit 0.
- `preflight-final.log` and `preflight-final/preflight.json`, exit 0: real_requests 0,
  both historical artifacts rejected for G1. Public file and protocol hashes and
  prepared argv are in that receipt.
- Initial `new-tests.log`: 10 passed, 1 failed. The Mock default had zero required
  STOP ACK roles; the negative test now explicitly requests a logs ACK and deletes
  it. No production STOP rule was relaxed.

Remaining acceptance: approved fresh real positive and negative investigations,
authenticated origin, matching effective configuration, semantic root-cause/citation
and missing-discriminator review, and optional repeated stability runs. No claim of
real RCA accuracy, provider reliability, independent Test acceptance or G1 PASS.
