# WP-B final dataset inventory

Dataset version: `wp-b-project-accepted-v1`. Existing bytes are frozen by the
[machine-readable inventory](../incidentbench/wp-b-project-accepted-freeze.json).
Its source commit identifies the input checkout; it is not a formal Seal or a
lock for a future model run. WP-D must create its existing protocol/source lock
from the final integrated source before execution.

The project owner's 2026-10-16 authorization accepts the existing 20 Seed and
10 Dev candidate references for course-project Development evaluation:
`project_accepted` / `OWNER_REVIEW_ACCEPTED`. Existing Oracle provenance stays
unchanged (`pending`); no reviewer identities, human-source records or formal
acceptance are synthesized. Formal independent double review and blind sealing
remain separate, unmet requirements.

All paths below are relative to the original repository
`C:/Develop/python_projects/COMP5584_Agents/IncidentLens`.

| Split | Public dataset | Evaluator-only Oracle | Cases |
| --- | --- | --- | ---: |
| Seed | `data/incidentbench_v1` | `local_oracles/incidentbench_v1` | 20 |
| Dev | `data/incidentbench_v16_dev` | `local_oracles/incidentbench_v16_dev` | 10 |

Seed IDs: `incident_1001`, `incident_1002`, `incident_1003`, `incident_1004`,
`incident_1005`, `incident_1006`, `incident_1007`, `incident_1008`, `incident_1009`,
`incident_1010`, `incident_1011`, `incident_1012`, `incident_1013`, `incident_1014`,
`incident_1015`, `incident_1016`, `incident_1017`, `incident_1018`, `incident_1019`,
`incident_1020`.

Dev IDs: `incident_3001`, `incident_3002`, `incident_3003`, `incident_3004`,
`incident_3005`, `incident_3006`, `incident_3007`, `incident_3008`, `incident_3009`,
`incident_3010`.

The public JSON lists every case's split, challenge tags, family, source blueprint,
cluster, pair and public hash using public metadata only. Per-case fault mechanism,
culprit service, reference cause, identifiability, support sets, misleading and
contradicting evidence IDs, causal sequence and insufficiency rationale are retained
only in ignored `local_oracles/wp-b-project-accepted-v1/inventory-protocol.json`.
The private inventory preserves the existing Oracle fields verbatim as structured
values; original Oracle files remain byte-identical. Competing hypotheses have no
separate annotation field in the existing schema and are explicitly `null` / `not
separately annotated`, rather than fabricated from other cases.

| SHA-256 | Seed | Dev |
| --- | --- | --- |
| Manifest bytes | `acdd163e5e29b18934efda0eed9eaa977ae30daf1aa6309f4d6d149d063368b8` | `247425f6b5e79b37eb41e9533fb022cdec6c310194df218d018902046506ff0f` |
| Public tree | `5a76e499e8172f9c4e754f789f1b377f9d7a78a59ff262ec271becaab3b80f07` | `fbafae81ce91af19f66dba7a7c633fc58ca59e6dbac6bfb8419199d6aa2bda26` |
| Oracle tree | `13ed24fa585015cb7a7790ae53e19765091699873f1ab1a13015b3dcf6cf1d9d` | `bd6f31a193b7b92955690da87bb2db3bf324d8159705701733de0dfc448e9e4f` |

The tree hashes reuse `incidentbench.manifest.digest_tree`, including relative
filenames and original bytes. No dataset or Oracle was regenerated or relabeled.

There are zero identical public case-tree hashes across the 30 cases, but 20
cross-split pairs have normalized excerpt similarity >=0.97. The shared
`cluster_causal_world_v1` and `causal-world-v1` encoder are disclosed in the JSON.
Normalization removes numbers and incident IDs using the existing validator's
heuristic. This is a template-overlap signal, not an equivalence proof or an
independent semantic annotation. Seed/Dev are development-visible data; do not
claim unseen-template generalization or 30 independent research samples.

The prepared Pilot is a three-case Seed subset at `results/wp-b/pilot-public`,
with evaluator-only labels at `local_oracles/wp-b-pilot`: `incident_1001`
(ordinary), `incident_1002` (misleading), `incident_1003` (missing evidence).
It retains original evidence, topology and Oracle bytes; only subset metadata,
coverage and manifest hashes are recalculated. It does not replace the frozen
Seed/Dev datasets. The regular runner can use `--dataset results/wp-b/pilot-public
--split seed --oracle-root local_oracles/wp-b-pilot`; real execution still needs
WP-D's model/readiness/protocol and separate budget approval.
