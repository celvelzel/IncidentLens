# Current acceptance update — 2026-10-16

User accepted T5 and authorized its checklist completion. The saved positive has RESOLVED/backend_pool_config_regression, protocol_valid=true and completed STOP, but source_unchanged=false. T6 is explicitly deferred/skipped; historical failed attempts are retained. No additional live calls were made during integration. G1a overall is not PASS; frozen-source acceptance and normal negative abstention remain outstanding. Historical zero-request/pending statements below describe the earlier offline delivery only.

---

# V1.6 real E2E acceptance

G1a/G1b: BLOCKED_AWAITING_USER. New real provider requests:0. No live RCA success or correctness claim.

Implemented offline public-input fingerprinting, saved-artifact screening and executable argument preparation in scripts/v16_e2e_preflight.py; reused existing retest runner and termination evaluator. Corrected retest trace variant metadata for all four runtime aliases. See ../acceptance/v16-offline-e2e-preflight.md for15final tests and267affected regressions, actual historical paths and retained failures.

Preflight only screens technical requirements. Even a real envelope with positive HTTP counts cannot authenticate real execution or semantic correctness; live_verified/g1_accepted remain false. Missing scope, mock, bridge, checkpoint continuation, drift, incomplete STOP, technical failure and result inconsistency cannot establish G1. Current finalized source must be fingerprinted again before approved execution.

## Concrete pending live operation
Existing public development dataset: results/incidentbench/v1/20261013-deepseek-development-pilot/dataset. Existing historical protocol: results/incidentbench/v1/user-retest-reconciliation/pilot-protocol-retest-v4.json. It specifies deepseek-v4-flash-0731, JSON Schema, cache off, request300s,32model requests,24tools,6rounds,3600s per investigation. This is a historical configuration, not user approval or current compatibility verification.

Proposed minimum: incident_2001 positive and incident_2002 missing, full, one attempt each, fresh unique outputs. Total ceiling proposal:64model requests,48tools,7200s investigation wall; actual transport/repair sends must be audited against enforced request limits. Token and monetary ceilings must be set/approved before execution; price/total cost unverified and remains null. Configuration matching, secret presence and compatibility probe remain unverified. No model substitution or unbounded retries. Repeats for G1b require separate approved additional budget.

After approval: regenerate offline preparation on frozen source; verify model/config without exposing secrets; perform only bounded authorized compatibility/E2E calls; preserve all attempts and failures. Independently inspect positive mechanism/service/causal support and negative evidence insufficiency; no machine-generated human signature. Only then may Lead change G1 status.

Final paid-operation preparation (not executed): results/v16/final-qa/20261015-02/live-preparation/preflight.json. Sourcec69ac16; explicit current public/protocol hashes and prepared positive/negative argv. No credentials read by preparation and no real requests. G1 unchanged BLOCKED_AWAITING_USER.
