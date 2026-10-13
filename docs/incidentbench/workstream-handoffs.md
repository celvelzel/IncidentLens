# IncidentBench workstream handoffs

The shared interface is `incidentbench-v1.0`; see [contracts-freeze.md](contracts-freeze.md). Each worker uses its assigned worktree and edits only owned files. The Lead owns integration, final generated data, source manifests, root documentation and final validation. No existing result directory is reused.

| Workstream | Owned responsibility | Evidence needed for handoff |
| --- | --- | --- |
| A | Deterministic causal builder, family split, development generation | Counts, byte determinism, public compatibility, shared-lineage limitations |
| B | Oracle boundaries, validator, manifest/seal, review workflow | Public/privileged checks, completion-gated labels, refusal paths, honest pending reviews |
| C | Actual Graph runner, normalization/scoring, analysis and CLI | Four equivalent-tool variants, durable raw completion before labels, failure denominators, offline tests |
| D | Dataset/evaluation/provider cards, reproduction and CLI E2E | Actual commands, fresh-output refusal, Mock provenance, no invented human or model results |
| E | Read-only independent QA | Findings and remaining risks; no functional edits |
| Lead | Shared runtime/config integration and final evidence | Integrated regression logs, hashes, actual run counts and final release status |

Use this record for every completed handoff:

```text
WORK_PACKET:
BASE_COMMIT:
OWNER / BRANCH / WORKTREE:
ALLOWED_WRITE_PATHS:
READ_ONLY_DEPENDENCIES:
INTERFACE_VERSION:
NEW CONTRACTS REQUESTED:
FILES CHANGED:
COMMANDS ACTUALLY RUN:
TEST PASS/FAIL/SKIP:
DATA OR SOURCE SHA256:
ARTIFACT PATHS VERIFIED:
REVIEW STATUS / UNCERTAINTIES:
READY FOR LEAD MERGE: YES | NO
```

Current research gates remain explicit: zero accepted labels, zero human reviewers, zero audited independent families, no Dev/Test data, no formal freeze, and pending real-provider evaluation. Offline implementation acceptance and scientific effectiveness acceptance must be reported separately.
