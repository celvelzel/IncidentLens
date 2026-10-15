# V1.6 status — M0 in progress

Actual baseline HEAD 62ec53475f4f4c71b9e1cccf33532763c90156f2; main. Initial git status: ?? docs/plans/v16/. Requested docs/v16 plan paths did not exist; authoritative input found at docs/plans/v16/. Original plans unchanged. Python 3.13.5; existing .venv, no dependency upgrades.

G0 IN_PROGRESS: full baseline pytest running; Ruff/validate-data/list-cases/Mock CLI/replay exit0. Raw logs: results/v16/preflight/m0-20261015-01/. Replay and CLI benchmark targeted regression running. Contracts and isolated worktrees created; workers not yet started pending baseline completion.

G1a/G1b BLOCKED_AWAITING_USER: no paid provider authorization; no new real requests. Historical offline continuation is not live E2E success.
G2a IN_PROGRESS: original20 seed,0 dev,0 test; fresh audit pending.
G2b BLOCKED_AWAITING_USER: real double review, independent label owner/family audit/sealing needed.
G3 NOT_STARTED; G4 BLOCKED_UPSTREAM; G5 NOT_STARTED.

## Approvals and human work
Real provider approval must specify model/config, total request/token/cost/wall limits before any paid probe. Unknown dollar costs remain null. Two actual group members must independently review candidate oracles/citations; third adjudicates disagreement. Coding agents cannot sign. Independent held-out ownership and family audit required before Test claims. Offline work proceeds meanwhile.

## M0 completed — G0 PASS
Actual full baseline: 914 passed, 3 skipped in267.79s, pytest exit0. Targeted benchmark CLI/Web/artifacts:12 passed in31.18s exit0. Ruff, validate-data, list-cases, Mock positive, Replay, check-environment, benchmark public validation: exit0. Baseline source was not edited during tests. Metadata drift: installed package metadata0.1.0 vs pyproject0.1.3; actual imports point to this checkout src. Final wheel verification required.

G0 PASS evidence: results/v16/preflight/m0-20261015-01/{pytest.log,pytest.exit,targeted.log,ruff.log,mock.log,replay.log,benchmark-public.log,dependencies.txt,head.txt,input-plan-hashes.json}; docs/v16/contract-freeze.md and ownership.md. Three skips remain Windows symlink capability limitations, not proof of link safety. Independent QA flagged replay evidence authorization, download sibling-link confinement, fresh artifact overwrite and metric semantics for follow-up. No safety guard weakened. Implementation wave A/B/C begins after this record.

## Independent QA baseline and resolved shared defects
WP-E read-only identified report sibling-link confinement, unobserved replay evidence, nested private Oracle fragments, and CLI artifact overwrites. Lead implemented boundary checks and25passing targeted tests (lead-boundaries-v2.log, exit0). First run2failed23passed retained in lead-boundaries.log: one test fixture missing stat metadata and existing empty-directory CLI compatibility; both corrected without removing tests. Ruff exit0. Contract v1.1 released. Final integrated QA still pending. A/B/C running isolated, D queued for next slot.
