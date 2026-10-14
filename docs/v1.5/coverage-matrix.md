# V1.5 required scenario coverage

This maps the authority's scenarios to meaningful executable assertions, not invented
counts. All paths are repository-relative. Final full-suite evidence is in
`results/v15/final-20261014/`; release-report.md records actual run outcomes.
Engineering tests use public Seed or locally constructed synthetic fixtures. They
cannot satisfy real-provider, reviewed Dev, or sealed Frozen Test acceptance.

Abbreviations below refer to files in `tests/active_investigation/`:
contracts=`test_candidate_contracts.py`, generation=`test_candidate_generation.py`,
eligibility=`test_candidate_eligibility.py`, features=`test_feature_extraction.py`,
selector=`test_selector.py`, graph=`test_graph_integration.py`,
fairness=`test_active_experiment_fairness.py`, replay=`test_score_replay.py`,
ablations=`test_ablations.py`, cost=`test_cost_estimation.py`.

| ID | Automated evidence / scope |
|---|---|
| T01 | contracts: roundtrip, invalid_candidates |
| T02 | contracts: invalid_config, selection_policy_strict |
| T03 | generation: three_origins_and_replay |
| T04 | generation three_origins; eligibility: rejections (run/incident/snapshot) |
| T05 | generation: cold_start_public_acl_and_window |
| T06 | generation: dedup_request_precedence_and_cap, semantic_changes_not_merged |
| T07 | generation: multi_service_cap_preserves_role_diversity |
| T08 | generation: deterministic_service_order_and_no_mutation |
| T09 | eligibility: stop_acl_and_completed_board, rejections |
| T10 | eligibility rejections; generation cold_start_public_acl_and_window |
| T11 | eligibility: stop_acl_and_completed_board; features redundancy_snapshot_and_window |
| T12 | eligibility rejections; graph snapshot_changes_with_visible_hypothesis |
| T13 | features: no_competition_bootstrap; selector cold_start_prioritizes_foundational_sources_without_faking_D |
| T14 | features: distinct_predictions_not_mode_lookup, generic_service_match_is_not_discrimination, permutation_invariant |
| T15 | features: requested_gap_independent_of_discrimination, negation_preserved_in_requested_check |
| T16 | features: missing_source_gate_independent_of_discrimination |
| T17 | features: redundancy_snapshot_and_window |
| T18 | generation semantic_changes_not_merged; features redundancy_snapshot_and_window |
| T19 | features: features_finite_and_no_mutation |
| T20 | selector: deterministic_tie; generation three_origins_and_replay |
| T21 | contracts cost_unknown_is_null; cost unknown_cost_not_zero |
| T22 | selector: ablation_rankings_actually_differ (injected synthetic calibrated costs; real calibration BLOCKED) |
| T23 | selector: diversity |
| T24 | selector: negative_and_zero_no_selection, aggregate_request_reserve, negative_value_abstains |
| T25 | eligibility budget_reserves; selector aggregate_request_reserve, two_physical_tasks_and_verifier_reserve |
| T26 | selector aggregate_tool_reserve; graph tight_budget_no_overflow |
| T27 | graph: stop_during_selection_prevents_publication |
| T28 | selector: hard_rejection_beats_value; eligibility rejections |
| T29 | graph: off_does_not_import_selector; baseline frozen full suite + CLI smokes |
| T30 | graph: shadow_keeps_original_execution_and_report, shadow_selector_failure_is_observation_only |
| T31 | graph: enabled_really_materializes_selected_tasks (semantic task fields and actual assignment IDs) |
| T32 | graph: terminal_coordinator_never_calls_caes[FINALIZE] |
| T33 | graph: terminal_coordinator_never_calls_caes[ABSTAIN] |
| T34 | generation three_origins; features requested_gap; graph integration and saved multi-round selections |
| T35 | tests/isolation/test_tool_acl.py: publish_requires_queried_ids_and_shared_fetch |
| T36 | tests/unit/test_runtime.py + tests/integration/test_review_boundary.py; graph terminal bypass and pure existing finalize_errors |
| T37 | tests/unit/test_runtime.py + tests/integration/test_workflow_v12.py task attempts/retries |
| T38 | tests/integration/test_provider_runtime_v13.py + test_recovery_concurrency_v13.py; graph measured_provider_cost_adapter and recovery_physical_reserve_normalized_once |
| T39 | tests/isolation/test_tool_acl.py: parallel_global_budget_is_atomic; tests/reliability/test_runtime_boundaries.py |
| T40 | tests/unit/test_runtime.py STOP/late-result cases; graph stopped_runtime_no_selection_or_new_tasks |
| T41 | tests/cache/test_semantic.py off/exact/semantic/namespace and actual graph assertions |
| T42 | eligibility rejections; tests/isolation/test_tool_acl.py parallel_incidents_do_not_share_ledgers |
| T43 | graph runtime_never_reads_oracle_or_private_files; tests/incidentbench/test_oracle_leakage.py synthetic boundary assertions |
| T44 | ablations real_mapping; selector off_must_bypass; genuine six-group Graph test |
| T45 | ablations common_pool_config; selector ablation_rankings_actually_differ common candidate inputs |
| T46 | selector ablation_rankings_actually_differ + aggregate/hard budget tests |
| T47 | selector ablation_rankings_actually_differ (different actual chosen candidate under no-D) |
| T48 | selector ablation_rankings_actually_differ; graph materialization; saved decisions replay |
| T49 | ablations genuine Graph all six includes actual benchmark_fixed4; existing incidentbench adapter tests |
| T50 | fairness strict configs, ablations common pool, replay drift checks PASS engineering; **BLOCKED_BY_UPSTREAM formal Frozen fairness** |
| T51 | replay research_gates_before_provider; incidentbench synthetic postcompletion scoring tests PASS boundary; **BLOCKED_BY_UPSTREAM trusted Frozen Oracle scoring** |
| T52 | replay research_gates_before_provider; source=mock/HTTP0/token-null exports |
| T53 | replay cancelled_durable_not_rerun + started_orphan_retained_unknown; existing evaluation failure denominator tests |
| T54 | tests/evaluation/test_termination.py + test_failure_scoring.py normal stop vs failure |
| T55 | fairness null_cost_and_single_cluster; contracts cost_unknown_is_null; recovery orphan unknown |
| T56 | fairness null_cost_and_single_cluster + tests/incidentbench/test_statistics.py synthetic grouped pairing PASS; **BLOCKED_BY_UPSTREAM valid independent-family CI** |
| T57 | replay resume_rejects_drift_and_foreign_ledgers; tests/incidentbench/test_experiment_fairness.py hash mutation checks PASS; **BLOCKED_BY_UPSTREAM formally sealed experiment** |
| T58 | tests/integration/test_graph.py; frozen baseline and final wheel legacy smoke |
| T59 | tests/evaluation/test_evaluation.py actual_seed_variants; tests/unit/test_agents.py |
| T60 | same actual variants plus tests/integration/test_graph.py |
| T61 | same actual variants asserts no-verifier path; original dispatch retained |
| T62 | tests/unit/test_database.py; tests/integration/test_workflow_v12.py; tool ACL assertions |
| T63 | tests/unit/test_monitoring.py + test_remediation.py; tests/integration/test_workflow_v12.py |
| T64 | tests/unit/test_runtime.py; tests/integration/test_workflow_v12.py STOP/ACK assertions |
| T65 | tests/reliability/test_fault_matrix.py + runtime_boundaries; V1.3 provider/HTTP/repair tests |
| T66 | tests/incidentbench/test_cli_e2e.py + graph_adapter synthetic/public smoke; six-group public Seed run; **BLOCKED_BY_UPSTREAM reviewed data/Oracle acceptance** |
| T67 | replay replay_cli_normal_envelopes; tests/integration/test_artifacts.py old replay; final wheel active/shadow/old replay smoke |
| T68 | scripts/verify_install.py seven measured commands, final installed wheel active smoke, full pytest and Ruff logs |

T50/T51/T56/T57/T66 remain explicitly BLOCKED_BY_UPSTREAM for the authoritative
research acceptance; passing their engineering boundary tests does not change that.
