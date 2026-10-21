# WP-D retained trace inspection — 2026-10-21

Scope: read-only inspection of 12 retained completed executions; no new test,
model call, runtime tool execution or historical failure-rate calculation.
`per-run.csv` and `inspection.json` contain reproducible extraction and 48 input hashes.

## Resource observations

| Variant | Model requests | Tools | Sum of round_index | Reviews | Finalize rejections |
|---|---:|---:|---:|---:|---:|
| Full | 67 | 51 | 12 | 13 independent | 1 |
| Dynamic no verifier | 48 | 34 | 11 | 0 | 0 |
| Fixed | 26 | 23 | 3 | 0 | 1 |
| Single | 52 | 44 | 10 | 8 self reviews | 0 |

All groups retain two reference matches and one correct abstention. In this selected
sample Full uses 28.8% more requests than Single, 39.6% more than No Verifier and
157.7% more than Fixed. These are observed completed-run resource counts, not API
prices, execution speed, population estimates or evidence of statistically significant
quality benefit. Request counts include repair requests; do not add repairs again.
Historical trace elapsed_ms is null; event span includes operator serving delays and
must not be substituted for API latency. Tokens and costs remain unknown.

Full's insufficient reviews and follow-up checks demonstrate an executed review
mechanism; they do not establish a corrected final diagnosis relative to the baseline.
Single also performs self-review. Finalize rejections are gate actions, not independent
proof of Verifier effectiveness. Rounds are saved round_index values, not graph steps.

## Semantic inspection (engineering review, not independent human adjudication)

All eight root-cause conclusions have an observed change E-003 and config diff E-004
for the matching incident: backend db_pool_max falls 20 to 2 at 12:00:10 under
concurrency 120. Pool waiters 118 (where observed) and the deadline log at 12:00:14
provide corroborating symptoms. All published supporting IDs occur in successful
TOOL_CALL observations. This supports the reference mechanism in the synthetic
case pack; citation existence alone does not certify every sentence or alternative rejection.

| Slot | Root-mechanism support | Alternative-rejection concern |
|---|---|---|
| 1 Full/1002 | E-003/E-004/E-008 support configuration then symptom | PostgreSQL exhaustion contradicted by E-007 (30/100). No specific rejection defect flagged in this inspection. |
| 2 NoVerifier/1002 | E-003/E-004/E-005 support pool change and waiters | E-004 supports a leading cause but does not directly refute all backend resource saturation. |
| 3 Fixed/1001 | E-003/E-004/E-008/E-009 support mechanism and propagation | E-004 alone does not refute payment timeout or all resource pressure. |
| 5 NoVerifier/1001 | E-003/E-004/E-005 support mechanism | One PostgreSQL rejection includes E-004 and generic gateway E-009; these are not direct contrary observations. E-006/E-007 are the relevant capacity evidence. |
| 6 Single/1002 | E-003/E-004/E-005/E-008 support mechanism | T-payment says payment has no downstream dependencies; it does not demonstrate payment is healthy/fast. |
| 8 Full/1001 | E-003/E-004/E-005/E-008 support mechanism | Same T-payment misuse; pool waiters/config change are not direct CPU/memory-health evidence. |
| 9 Fixed/1002 | E-003/E-004/E-008 support mechanism | E-004 alone does not directly contradict resource saturation. |
| 11 Single/1001 | E-003/E-004/E-005 support mechanism | E-007 counters database cap exhaustion. No specific rejection defect flagged in this inspection. |

Six of eight resolved reports therefore have at least one weak alternative rejection.
Do not relabel these eight reports fully semantically grounded. No deterministic
keyword rule can repair this defect; the shared prompt now distinguishes positive
support, direct contradiction, missing data and topology facts. Runtime guards remain.

All four incident_1003 reports abstain normally with null root_cause and completed
STOP. The public pack supplies generic deadline symptoms and baseline telemetry,
but no config-change mechanism or database cause discriminator. Empty successful
queries demonstrate unavailable evidence, not healthy services. Abstention is supported.
Full's review sometimes calls missing corroboration a contradiction; lack of support
must remain distinct from an actual refuting observation.

## Scope caveats

Slot 10 uses timeout 1200s versus 420s in the other retained runs; slots 4/11 use
replacement attempts and slot 11 had an ACL reminder. Owner accepts a conditional
completed-run exploratory comparison. This report does not recompute historical
failure denominators, declare strict G4/G1a passed, or establish Full superiority.
