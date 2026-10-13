# Ownership and dependencies
Lead: provider.py, budget.py, graph.py, config/CLI, evaluation runner, exports, existing tests, README and acceptance.
WP-A isolated IncidentLens-v13-a: errors.py, transport_retry.py, test_provider_errors_v13.py, test_provider_http_retry_v13.py.
WP-B isolated IncidentLens-v13-b: recovery.py, permits.py, test_recovery_policy_v13.py, test_recovery_concurrency_v13.py.
WP-C isolated IncidentLens-v13-c: structured_output.py, capabilities.py, test_structured_output_v13.py, test_provider_capability_v13.py.
WP-D after P4: reliability fixtures, metrics, evaluation script/protocol; isolated worktree.
WP-E: independent read-only P0 and final review.
DAG: P0 + QA -> A/B/C -> Lead P4 -> D P5 -> real P6 -> QA/P7. No shared writer concurrency; no worker delegation.

## Integration evidence

WP-A c01141e, WP-B 32d00fa, WP-C 89e10cd were individually verified then cherry-picked. WP-D 12fcff6 and 9f2bd47 were cherry-picked; its 19c9ed6 fix was copied from named owner files after unrelated staged STOP work caused Git to refuse cherry-pick. The original index was preserved. Worktrees remain available for reproducibility; their shared-file Lead adjustments were not included in owner commits.

P0 QA approved frozen contracts. WP-E independently reviewed concurrent guards, request admission, cancellation, unknown usage, nested retry/repair, domain safety, Mock metrics and evaluation fairness. High findings were corrected before acceptance; post-launch live manifest timing remains explicitly qualified. Lead formatting repairs preserve pre-existing STOP implementation semantics.
