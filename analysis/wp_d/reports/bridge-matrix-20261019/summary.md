# WP-D bridge matrix — 2026-10-19

Development bridge batch: `results/v16/wp-d/matrix-bridge-subagent-20261019`.
All 15 attempts (12 original slots + 3 retests) are preserved, including failures.
`summary.json` records each attempt. Its descriptive selection uses retests for
slots 4, 10 and 11; it does not replace the original results or establish a preregistered selection.

| Variant | Ordinary 1001 | Misleading 1002 | Missing evidence 1003 |
|---|---|---|---|
| Full | diagnosis | diagnosis | abstention after retest |
| Dynamic no verifier | diagnosis | diagnosis | runtime failure, both attempts |
| Fixed | diagnosis | diagnosis | abstention |
| Single | diagnosis after retest | diagnosis | abstention |

First-attempt completion: 9/12. Post-retest completion: 11/12.
Post-retest outcomes: 8 reference-matching diagnoses, 3 correct abstentions,
1 technical failure. All eight diagnoses match backend/backend_pool_config_regression
and include the reference support pair E-003/E-004. This is reference matching and
citation coverage, not complete human semantic support review.

Slot 4 originally timed out. Slot 10 originally proposed a task-forbidden tool;
its retest returned invalid JSON and the repair request timed out unserved.
Slot 11 originally assigned tools outside the role ACL; its retest included an
extra ACL reminder. These failures must remain in reliability accounting;
the missing-evidence slot 10 technical INCONCLUSIVE is not a correct abstention.

All attempts report protocol_valid=true and source_unchanged=true; saved source,
retest source, dataset revision and protocol agree across attempts.
All attempts combined: 234 model requests, 3 repair requests, 0 bridge HTTP
requests. Tokens and cost are unknown. Subagent provider-side usage is unmeasured.

Functional expectations are substantially met, but the matrix still has one
failed slot. Full superiority and a causal Verifier benefit are not established:
Full, Fixed and Single share the same selected outcomes. Three correlated visible
development cases, one repeat, selective retests, an extra reminder and unverified
model identity/temperature/isolation prevent a formal controlled comparison or
real-provider acceptance claim. See serving-notes.md for procedural caveats.
