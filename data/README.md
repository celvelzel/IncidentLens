# Synthetic IncidentLens fixtures

All observations are synthetic. Five seed cases cover local backend connection-pool
regression, database connection exhaustion, unavailable Redis, external payment
timeouts and backend resource saturation. The sixth seed deliberately omits the
configuration diff and discriminating pool/database capacity metrics, so the visible
evidence does not uniquely identify the root cause.

`scripts/generate_cases.py` deterministically creates 6 seed, 10 dev and 20 test
packs. `scripts/generate_database_cases.py` then appends an additive database
cohort of 4 packs (incident_037-incident_040), each carrying an additional
`public/database.jsonl` evidence file: connection capacity at its limit (037),
healthy-database observations that rule out connection exhaustion (038), a
transaction-lock contention case whose inherited logs, metrics and oracle are
rewritten (039), and one pack with an empty `database.jsonl` plus the discriminating
configuration diff removed (040). That gives 40 packs in total. Generated variants
alter onset time, propagation delay, request concurrency, metric values, symptom
wording, service-specific background logs and noise volume. Five packs omit crucial
discriminating evidence. Variants share five causal templates; this dataset does not
establish production generalization.

Split IDs are fixed in `splits/` (seed, dev, test and the additive database
cohort). Test membership is a holdout convention, not proof of blind evaluation.
Generated test truth must not be used to tune prompts.
Recorded real-model evaluation and source-freeze evidence live in
`docs/acceptance/live-continuation.md`; this is not an independently collected
production test set. Every generated pack currently includes decoy evidence:
ordinary coverage is zero, and analysis reports that gap explicitly.

Runtime reads only the six fixed filenames under each `public/` directory
(`database.jsonl` may be empty and is skipped when absent) and
`topology/services.yaml`. Private oracles are administrative/evaluation artifacts.
`EvidenceProvider.validate_public()` never reads them; the separate offline
`scripts/validate_dataset.py` checks both public data and oracle citations.

Each ID embeds a neutral incident identifier and source row number. Public metadata
contains only raw observation fields, never answer labels. The injected request
payload in logs is intentionally untrusted data for isolation tests.
