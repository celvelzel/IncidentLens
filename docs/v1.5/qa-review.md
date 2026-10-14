# WP-E independent QA record

Reviewer is read-only and independent of WP-A/B/C/D and Lead integration.
Final reviewed runtime `2611182`; detailed artifacts in `results/v15/final-20261014`.
No private/local_oracles/Frozen Test Oracle read. Full source/spec review and bounded
reproduction complement Lead validation; they do not replace research acceptance.

| Issue | Severity / actual defect | Owner / correction | Retest |
|---|---|---|---|
| QA01 | High: visible DTO nested objects aliased live state | Lead detached/deep-copied field validators | contracts visible_projection_detaches_live_objects |
| QA02 | High: Shadow scorer exception aborted original dynamic execution | Lead graph fallback, STOP/deadline retained | graph shadow_selector_failure_is_observation_only |
| QA03 | High: runtime task template partial ACL caused ROLE_TOOL_PROPOSAL_FORBIDDEN | WP-A complete explicit role ACL | generation templates_use_full_explicit_runtime_acl + real graph smoke |
| QA04 | Medium: invalid requests could starve legal Coordinator proposals before cap | WP-A order legal proposals/requests/templates first | generation invalid_requested_checks_cannot_starve_proposal |
| QA05 | Medium: D depended on hypothesis order | Lead8754d4d both-sided prediction contrast overlap | features permutation invariance, independent12pass |
| QA06 | Medium: action-only ID comparison could claim algorithm change | Lead compare actual semantic task fields/assigned task IDs | graph enabled_really_materializes_selected_tasks |
| QA07 | Medium: exported score lacked actual tools | Leadcee3987 reads state.tool_calls_used, unknown None | fairness actual_tool_count_and_unknown_failure_count; v3 counters independently recomputed |
| QA08 | High acceptance blocker: duplicate test module basenames broke default pytest collection | Lead2611182 rename active fairness file | independent27tests collected0errors; clean full run required |
| QA09 | Medium: physical Recovery reserve multiplied twice as logical calls | Lead2611182 ceil physical/logical conversion before max | independent46bounded pass; graph15pass; permits not charged |

Previous reviewer turn interrupted on account usage limit was not counted as a PASS.
Its pending work was explicitly resumed/reassigned to final independent reviewer.
WP-E checked final normal/tight batches:120 unique raw+scores+runIDs each,23 top-level
artifact hashes each,120 state receipt/score recomputations each,ordered240 STARTED/DURABLE
records each,247+163 pure selection replays, source/public/protocol lock and no-hypothesis
D=0 at177 normal/144 tight selection rounds. All actual requests/tools fit configured
limits. All63 tight BUDGET_EXHAUSTED failures remain scored/retained. Quality null.

Historical120 batch has four preserved Verifier failures; historical192 selections
were independently replayed in an isolated process using historical9ab8f9d selector.
Its source is explicitly stale and missing tools field is not silently rewritten.

Fresh wheel seven commands exit0, SHA
`eeded25230eb0cc54444b650760cf5c5bd0a8c545fad191b0c90e08b7595734a`.
Reviewer invoked installed interpreter outside repo and verified package and policy
import paths are environment/Lib/site-packages. Active16requests/8tools INCONCLUSIVE;
Shadow15/9 RESOLVED; all three installed Active snapshots replay exactly.

Full-r3:849passed,1UI replay failure,3skipped (298.88s). UI selected a different
historical state. UI/app.py and test_ui.py are unchanged from7c48da1. Standalone
UI retest after installation/smokes finished:1passed47.83s. Concurrent addition of
saved-trace options is a plausible existing widget-reset cause, not established
causality. This negative is retained; a clean serial full-r4 supplies final acceptance.
Remaining limitation: avoid concurrent saved-trace creation during UI/AppTest replay
validation; artifact replay CLI itself validates the explicitly named trace.

No remaining Critical/High/Medium CAES code findings after2611182 bounded review.
Final clean full-r4 independently verified:850passed,3skipped,328.11s; JUnit853tests,
0errors,0failures,3skips (Windows symlink privilege unavailable). Engineering WP-E PASS.
Installed wheel policy/selector/metrics bytes also match current source exactly.
Final clean full-suite outcome and release status are recorded in release-report.md;
formal P4/P5/T50/T51/T56/T57/T66 remain BLOCKED_BY_UPSTREAM regardless of engineering QA.
