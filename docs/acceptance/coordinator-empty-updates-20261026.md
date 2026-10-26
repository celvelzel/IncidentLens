# Empty-board hypothesis update guard — 2026-10-26

Four retained Dev3002–3005 attempts failed because a coordinator returned new
hypothesis IDs through hypothesis_updates while the shared hypothesis board was
empty. The generation schema allowed those objects, but the runtime correctly
refused to update unknown hypotheses. The failures remain historical failures.

When reconciliation is unavailable, decide() now constrains hypothesis_updates
to maxItems=0 and explicitly requests an empty array. This also matches legacy
non-reconciliation mode. Registered benchmark hypotheses retain the existing
update schema, observed-evidence limits and post-generation identity checks.
No output is silently cleared, no hypotheses are fabricated, and no runtime
guard is removed. Prompt version advances to v8-empty-update-guard.

Validation: 90 offline tests passed across agent unit tests, graph integration,
review boundaries, repair accounting, the real HTTP adapter fixture and
experiment fairness. Tests cover all four variants, both benchmark flag states,
valid reconciliation, a provider bypassing schema validation, and a malformed
HTTP response repaired once with both requests/tokens charged.

Offline replay of all four previously failed model outputs confirms each now
fails provider-schema validation at hypothesis_updates (too_long), before
dispatch or shared-state mutation. Evidence is retained under
results/acceptance/coordinator-empty-updates-20261026/. No model calls, Oracle
reads, investigation reruns or historical artifact rewrites were performed.

This removes the schema/runtime mismatch; it does not guarantee provider
compliance, recovery by adapters without repair support, or correct diagnosis.
Any new experiment requires a fresh source/prompt lock and output directory.
