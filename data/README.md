# Synthetic IncidentLens fixtures

All observations are synthetic. Five seed cases cover local backend connection-pool
regression, database connection exhaustion, unavailable Redis, external payment
timeouts and backend resource saturation. The sixth seed deliberately omits the
configuration diff and discriminating pool/database capacity metrics, so the visible
evidence does not uniquely identify the root cause.

`scripts/generate_cases.py` deterministically creates 6 seed, 10 dev and 20 test
packs. Generated variants alter onset time, propagation delay, request concurrency,
metric values, symptom wording, service-specific background logs and noise volume.
Four packs omit crucial discriminating evidence. Variants share five causal
templates; this dataset does not establish production generalization.

Split IDs are fixed in `splits/`. Test membership is a holdout convention, not proof
of blind evaluation. Generated test truth must not be used to tune prompts. No real
model evaluation or independent test freeze is claimed.

Runtime reads only the five fixed filenames under each `public/` directory and
`topology/services.yaml`. Private oracles are administrative/evaluation artifacts.
`EvidenceProvider.validate_public()` never reads them; the separate offline
`scripts/validate_dataset.py` checks both public data and oracle citations.

Each ID embeds a neutral incident identifier and source row number. Public metadata
contains only raw observation fields, never answer labels. The injected request
payload in logs is intentionally untrusted data for isolation tests.
