# V16 authentic human review handoff

Status: PENDING; zero reviews recorded. This document assigns no reviewer identities or signatures.

The dataset owner must transfer the public bundle and matching private candidate oracle bundle to two actual group members independently. Verify the hashes in `v16-dataset-audit.md` before review. Each reviewer starts from public observations, then checks the candidate causal chain, minimal sufficient sets, competing explanations, timing, counter-evidence, misleading observations and missing discriminators. Compare each counterfactual pair and the shared encoder lineage. Do not send private labels, specs or review records to runtime, prompts, UI or replay.

Each reviewer independently saves one raw record per incident in their own private review file, preserving actual `reviewer_id`, `incident_id`, `source="human"`, actual `reviewed_at`, rationale and the complete causal `labels` fields required by `annotation-guide.md` (excluding reviewer_ids, annotator_status, review_version). Do not start from a prefilled agreement or invented human metadata. Keep the two original files before reconciliation. Candidate labels remain pending during review.

For disagreements, a third actual group member records independent adjudication, labels and rationale; retain all original records and revisions. The evaluator owner then assembles per-case `truth_reviews.json` using the existing citation_review contracts and validates them. Software validation cannot establish that a human authored a record. Review provenance must be inspectable by the Lead.

Any future held-out dataset requires a separately authored and audited encoder/family, independent label owner, frozen source/prompts/model/protocol and sealing. These 10 visible Dev cases and the 20 Seed are ineligible for an independent Test claim. Accepted human review of these Dev cases alone does not establish G2b.

Private local handoff locations in this worker checkout: `local_oracles/incidentbench_v16_dev/` (candidate labels), `local_oracles/v16-dev-authoring/` (exact specs/reproduction). Preserve or securely transfer them before deleting the worktree; Git cherry-pick transfers public files only.
