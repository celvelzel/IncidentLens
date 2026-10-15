# V16 dataset audit and engineering release

Evidence level: UNIT / OFFLINE_MOCK only. The original 20 Seed remain unchanged (16 identifiable candidates, 4 missing, 4 declared groups, 0 accepted labels, 0 audited independent families). `v16-inventory.csv` inventories every case. Candidate cause and decisive/counter-evidence mappings are deliberately withheld from this public inventory; evaluator-only candidates require private review. Public validator passes; this checks contracts and references, not human causal validity.

The new `data/incidentbench_v16_dev/` contains 10 newly generated development cases, IDs 3001–3010: 2 ordinary, 2 misleading, 2 missing and 4 counterfactual cases forming 2 pairs. There are 8 identifiable candidates and 2 insufficient candidates. All are pending review; no accepted labels or Test cases exist. Public observations differ from Seed in incident IDs, dates, workload and intervention/propagation timing. These are new observations from the existing causal-world-v1 simulator, not independent causal families or encoders. The 2 declared groups and Seed share `cluster_causal_world_v1`; never combine them as independent train/test evidence. Same-split near duplication is intentional development material. Missing variants remove causal discriminators; pair interventions change both candidate mechanism and public observations, rather than only labels. The encoder remains a small queue/capacity model, not production fidelity evidence.

Public sources are logs, metrics, changes, configs and database observations where generated. Multi-source sufficiency, alternatives, decoy plausibility and whether the missing cases truly require abstention remain human review questions. Public IDs and source schemas pass automated validation. No per-incident answer key or private source specs are published. Runtime uses only `<public-root>/rca`; the runner smoke receives no oracle root.

## Reproduction and provenance

Base source: `62ec53475f4f4c71b9e1cccf33532763c90156f2`. No builder/runtime/schema modifications were required. Builder source digest is recorded in the dataset manifest. The exact authoring config and generator are evaluator-only at ignored `local_oracles/v16-dev-authoring/{spec.json,generate.py}`. Labels are separately rooted at ignored `local_oracles/incidentbench_v16_dev/`. These local files are not transported by the public commit: the evaluator owner must securely retain them. Do not infer label availability in a clean checkout.

Two fresh builds were byte-identical, including private labels. Hash algorithm: `incident_lens.incidentbench.manifest.digest_tree` (sorted relative paths, NUL, file bytes).

- Public whole-tree SHA256: `fbafae81ce91af19f66dba7a7c633fc58ca59e6dbac6bfb8419199d6aa2bda26`.
- Private label-tree SHA256: `bd6f31a193b7b92955690da87bb2db3bf324d8159705701733de0dfc448e9e4f`.
- Raw evidence: worktree `results/v16/dataset/wp-b-20261015-01/` (ignored). Generation summary retains both hashes and deterministic reproduction result.

Generation uses the main `.venv/Scripts/python.exe` with `PYTHONPATH=<v16-b>/src`. Validators: `scripts/validate_incidentbench.py --dataset <root> --mode public`; private check adds `--mode privileged --oracle-root local_oracles/incidentbench_v16_dev`. Seed public, new public and new privileged checks each exit 0. Full IncidentBench tests and four-variant Mock results are recorded in `v16-validation.md`.

G2a engineering material is available subject to Lead acceptance and Mock completion. G2b remains BLOCKED_AWAITING_USER: no real human review, independent encoder audit or sealed held-out ownership. No research-quality, true blind Test or live-provider claim is supported.
