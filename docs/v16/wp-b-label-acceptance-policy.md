# WP-B reference-label acceptance policy

Authority: the project owner's explicit WP-B instruction supplied on 2026-10-16 (Asia/Shanghai). This instruction supersedes the earlier requirement to obtain another round of human review before **development/course-project** experiments. It does not change the formal research seal.

The existing 20 Seed and 10 Dev candidate oracles are accepted as project reference answers: `OWNER_REVIEW_ACCEPTED`, equivalent to `project_accepted`. Acceptance applies to the exact frozen oracle hashes in the WP-B freeze record, not to later changed answers. No new review, reviewer identity, review timestamp, human-source record or semantic citation annotation is fabricated. Original `BenchmarkOracle.annotator_status=pending`, review versions and reviewer lists remain unchanged.

The acceptance record is a separate dataset-level sidecar. Its authority is the owner's instruction; it is neither an independent double-review record nor a signature of an external label owner. Automated checks establish consistency, referential integrity and engineering readiness, not independent truth verification. Any change to cause, chronology, identifiability or difficulty requires a visible diff and renewed decision; do not silently repair semantics.

Development scoring may use these reference labels after durable run persistence through `OracleStore`. Existing legacy output can still say `provisional`; interpret this alongside the project-level acceptance sidecar, without relabeling historical raw results. Machine service/mechanism match measures agreement with the project reference. Citation existence and reference-set coverage do not establish semantic grounding; human semantic metrics remain unknown without genuine annotations.

Formal independent review, Test creation, independent-family audit and sealing remain separate and unsatisfied. Keep `formal=false`, `blindness_level=development_visible` and the current fail-closed seal requirements. Do not describe this corpus as an independent blind test, production incidents, cross-source generalization, or proof that Full outperforms another architecture.

Private oracle values and the full evaluator inventory belong under ignored `local_oracles/`. Public Git and frontend/replay outputs receive only public-safe metadata and hashes. The owner acceptance does not grant the Agent runtime oracle access, authorize paid requests, establish provider compatibility or approve a monetary budget.
