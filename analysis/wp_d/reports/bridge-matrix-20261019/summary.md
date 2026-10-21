# WP-D bridge matrix — updated 2026-10-21

## Current completed-run results

All 12 retained slots completed: 8 reference-matching diagnoses and 4 correct
abstentions. Every retained run reports protocol_valid=true, source_unchanged=true,
runtime_failure=false and completed STOP. Slot 10 now normally abstains with no
root cause, using 17 requests and no repair requests.

| Variant | Ordinary 1001 | Misleading 1002 | Missing evidence 1003 |
|---|---|---|---|
| Full | reference match | reference match | correct abstention |
| Dynamic no verifier | reference match | reference match | correct abstention |
| Fixed | reference match | reference match | correct abstention |
| Single | reference match | reference match | correct abstention |

Selected-run totals: 193 model requests, 2 repair requests, 0 bridge HTTP requests.
Tokens and costs remain unknown. Reference matching and citation coverage are
not complete human semantic support review.

## Owner-accepted analysis scope

On 2026-10-21 the owner accepted the local network constraints and operational
adjustments for project-level development comparison. Quality analysis therefore
uses the retained completed execution for each slot. No overall failure denominator
is recomputed here; 12/12 describes coverage of selected completed slots, not
first-attempt success, provider reliability or an unbiased overall accuracy estimate.

This is an owner-accepted exploratory comparison. It cannot establish statistically
significant Full superiority or causal Verifier benefit: all variants have identical
reference-match/abstention outcomes on these three visible development cases.

## Execution provenance and limits

Slot 10 request_timeout changed from 420 to 1200 seconds; the other slots use 420.
Slots 4 and 11 use retests, and slot 11 received an additional ACL reminder.
Historical ROLE_TOOL_PROPOSAL_FORBIDDEN (slot 10) and COORDINATOR_TASK_ACL_INVALID
(slot 11) are response/ACL failures, not established network failures. Earlier failed
run directories were removed locally; some archived failures remain in Git.
These facts remain relevant to interpretation despite owner acceptance.

Model identity, temperature and external-agent isolation remain unverified. The
batch cannot replace real API G1a or establish the original strict G4 comparison.
Bridge functional validation can be closed within this explicitly reduced scope.

Current machine-readable results: final-summary-20261021.json.
summary.json is the historical 2026-10-19 snapshot (11/12), not the current result.
Detailed serving provenance remains in the batch serving-notes.md.
