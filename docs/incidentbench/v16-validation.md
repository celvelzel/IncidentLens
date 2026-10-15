# V16 dataset validation record

Evidence level: UNIT / OFFLINE_MOCK. All commands ran in `.worktrees/v16-b` using the main workspace `.venv/Scripts/python.exe`, with `PYTHONPATH=$PWD/src` so imports use this worktree. No provider requests or paid calls occurred.

Raw logs and exit files: `results/v16/dataset/wp-b-20261015-01/` in the worker checkout. Source runtime and scripts remained unchanged throughout validation and Mock execution.

| Command (Python prefix omitted) | Result |
|---|---|
| `local_oracles/v16-dev-authoring/generate.py` | exit 0; 10 cases; deterministic second build public/private hashes match |
| `scripts/validate_incidentbench.py --dataset data/incidentbench_v1 --mode public` | exit 0 |
| `scripts/validate_incidentbench.py --dataset data/incidentbench_v16_dev --mode public` | exit 0 |
| `scripts/validate_incidentbench.py --dataset data/incidentbench_v16_dev --mode privileged --oracle-root local_oracles/incidentbench_v16_dev` | exit 0 |
| `-m pytest tests/incidentbench/test_generation_v16_dataset.py -q` | exit 0; 2 passed |
| `-m ruff check tests/incidentbench/test_generation_v16_dataset.py` | exit 0 |
| `scripts/run_incidentbench.py --dataset data/incidentbench_v16_dev --split dev --variant all --provider mock --cache-mode off --jobs 1 --out results/v16/dataset/wp-b-20261015-01/mock` | exit 0; 40 unique run keys, 10 per variant |
| `manifest.check_private_git(local_oracles, repository)` | PASS; private files ignored and untracked |

Mock outcomes: 40 FINISHED; 12 RESOLVED and 28 INCONCLUSIVE. Stop reasons: 20 missing discriminator, 8 fixed schedule unresolved causal gaps, 12 no stop reason. All attempts retained in `mock/raw-runs.jsonl`; `mock-summary.json` records counts. The runner received no `--oracle-root`; output is unscored engineering evidence. Report statuses are not RCA correctness or correct-abstention scores. There is no live-provider or human-reviewed result.

Private candidate oracles were loaded only by the separate privileged validator, not by Mock investigations. Private bundles remain local; public Git does not provide private labels. Existing Seed data and source files were not changed.

Full generation/leakage/IncidentBench regression: `-m pytest tests/incidentbench -q` exited 0: **88 passed, 1 skipped in 146.56s**. The platform-dependent skip is retained; it is not proof of Windows link safety.
