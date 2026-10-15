# WP-D Stage 0 evidence

Worktree: `C:/Develop/python_projects/COMP5584_Agents/IncidentLens/.worktrees/v16-d`
Branch: `codex/v16-d`; baseline: `62ec534`.
Evidence root: `results/v16/wp-d-20261015-01/` (ignored, retained locally).
Interpreter: main checkout `.venv/Scripts/python.exe`, Python 3.13.5;
`PYTHONPATH` points to this worktree's `src`.

The exact Stage 0 commands in `v16-protocol.md` were executed using
`results/v16/wp-d-20261015-01/mock80` and the sibling `analysis` output.
Run and analysis both exited 0. No oracle root was supplied, no private labels
were loaded, and no paid requests were made.

Actual manifest: 80 raw runs, 80 distinct run keys, 20 distinct incidents,
20 attempts for each of the four variants. All 80 technically completed;
failure counts are empty, budget exhaustion is zero. All 80 label statuses
are unscored. Label-dependent rates and human semantic support remain null.
There is no observed failure to conceal in this run; failure-inclusive behavior
is separately exercised by metric tests and the existing fairness suite.

Analysis recomputed 80 saved states, validated durable receipts and source locks,
and recorded `exact_scores_equal: true` in `analysis/score-recomputation.json`.
The execution and analysis V16 metrics are byte-identical. Raw states, order,
protocol, locks, ledgers, scores, bundles and failure files remain at the
recorded worktree location; none are committed.

SHA256:

| Artifact | Digest |
|---|---|
| raw-runs.jsonl | b87fb03a1ce15e13b0ed3541703bccb439c183b76493684d59bfe02250fc1750 |
| scores.jsonl | ec6782c286b4e6bc391825b591dc3655254efb765be34d07a2dde875f0e3a0cc |
| v16-metrics.json | 1f2d49438dc96f7f5298ce2dc08dab1b4150fd5f82050dd2fe9f0beda2e2a539 |
| locked source | 9ee5d9cade0a75868f5763690f81b5f6b38c392f4f1498f27d4b5294ba8b2733 |
| locked scripts | 03c395f80e147bbc4f609bfb7a18c9ec55e16dd1570eb05b5e48d286ee63d085 |
| locked protocol | 7545f218f4d61b2831c90aaf8f708f808f290e1e0be3102266e011e3b43a7798 |
| locked public dataset | 5a76e499e8172f9c4e754f789f1b377f9d7a78a59ff262ec271becaab3b80f07 |

The complete lock and per-file hashes are retained in `evidence-manifest.json`.
This documents the frozen worktree inputs, not later integrated main inputs;
integration changes require a new lock and run.

Validation: `pytest tests/evaluation -q`: 71 passed, exit 0 (63.68 seconds).
Targeted V16 metric tests: 5 passed, exit 0. Ruff on the four changed Python
files: passed, exit 0. Logs and exit files are retained under the evidence root.
Existing experiment fairness suite: 20 passed, exit 0 (96.17 seconds), including
failure-inclusive scoring, fresh providers, fail-closed gates and resume integrity.

Stage 0: PASS / OFFLINE_MOCK. Real pilot: BLOCKED_AWAITING_USER (G1/G2 and
explicit budget). Formal/Test and G4 research evidence: BLOCKED_UPSTREAM.
No semantic quality, architecture superiority or independent-family inference
is established by this unlabelled Mock run.
