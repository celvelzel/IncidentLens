# IncidentBench development scenario catalog

This catalog describes the generated `data/incidentbench_v1` candidate dataset. It does not publish held-out causal blueprints or Test mappings. Counts come from its manifest, not the optional Monitoring/OOD unit fixtures.

| Slice | Cases |
| --- | ---: |
| Core / Seed | 20 |
| Core / Dev | 0 |
| Core / Test | 0 |
| Identifiable candidate labels | 16 |
| Missing discriminators | 4 |
| Ordinary | 4 |
| Misleading | 4 |
| Counterfactual variants | 8 |
| Monitoring | 0 |
| OOD | 0 |
| Accepted human-reviewed labels | 0 |
| Declared source groups | 4 |
| Audited independent families | 0 |

The four declared groups share development encoder lineage and a near-duplicate cluster. Group IDs provide traceability; they do not establish four independent research samples. All groups remain in Seed. Renaming family or cluster IDs cannot establish an unseen-template holdout.

The disclosed `development_config()` in `tests/incidentbench/test_generation.py` creates five variants per group: ordinary, misleading, missing, and two counterfactual variants. Its development mechanisms exercise pool configuration, PostgreSQL connection/lock/query behavior, Redis availability, payment timeouts, and backend resource saturation. These generic encoders demonstrate cross-source causal propagation and queryable discriminators; they are not production incident observations.

An ordinary case has no labeled decoy. A misleading case contains an observable decoy alongside discriminating evidence. A missing case removes sufficient discriminator sets and should permit normal INCONCLUSIVE termination. A counterfactual pair changes its public discriminator and candidate cause, and both members stay together in the split. Counterfactual variants are eight cases forming four pairs, not eight independent interventions.

The builder derives a deterministic causal world and then logs, metrics, changes, configurations, and database observations. Public inputs retain the existing evidence format and neutral symptoms. Candidate cause/support annotations live in a separate evaluator root. Validator success checks consistency and access boundaries; it does not convert generated annotations into human ground truth.

Monitoring and OOD generation has small unit fixtures, but this dataset contains neither cohort. No monitoring precision/recall, OOD robustness, external validity, or production recovery claim follows from this catalog.
