# V1.6 dataset plan and review status

G2a engineering acceptance: PASS after final integrated QA. G2b BLOCKED_AWAITING_USER.

Original20Seed unchanged. Actual new Dev10:2ordinary,2misleading,2missing,4counterfactual cases (2pairs). New Test0; accepted human labels0; audited independent families0. Shared causal-world-v1 encoder is disclosed; new dates/IDs/workloads are not independent families. No strict blind/generalization claim.

Public data: data/incidentbench_v16_dev. Candidate labels: ignored local_oracles/incidentbench_v16_dev; exact authoring retained in ignored local_oracles/v16-dev-authoring and original B worktree. Do not stage or feed these into runtime, prompts, replay or screenshots. Root copies preserved without overwrite and hashes compared. Public whole-treefbafae81ce91af19f66dba7a7c633fc58ca59e6dbac6bfb8419199d6aa2bda26; privatebd6f31a193b7b92955690da87bb2db3bf324d8159705701733de0dfc448e9e4f.

See ../incidentbench/v16-dataset-audit.md, v16-inventory.csv, v16-validation.md and v16-review-handoff.md. B validators all exit0;88IncidentBench tests passed,1Windows skip. Mock40attempts (10per variant),0oracle access, unscored;12resolved28inconclusive are workflow outcomes only. Main validators and exact hashes independently verified after byte restoration. First integration hash failure retained at results/v16/integration/20261015-01/dev-validation-first.log; newline-restoration.json lists7files. .gitattributes now preserves exact public dataset bytes.

Two real group members must independently review causal sufficiency, chronology, alternatives, missing evidence and semantic citation support with original human-source records. Third reviewer resolves disagreements. Independent label owner, substantive encoder/family audit and sealing remain necessary for G2b. Agents did not sign or invent reviewers. Public inventory intentionally withholds per-case private candidate answers.

## Final Lead acceptance
G2a PASS engineering: integrated final-source40Dev attempts and exact saved analysis exit0; public/private validation, pending provenance, family/lineage limits independently reviewed. Final source full regression950passed3skipped. G2b still BLOCKED_AWAITING_USER. No accepted labels or new Test are implied.
