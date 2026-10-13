# IncidentBench interface freeze v1.0

Authoritative contracts: src/incident_lens/incidentbench/schemas.py, INTERFACE_VERSION incidentbench-v1.0. No worker edits schemas or shared runtime.

Dataset: data/incidentbench_v1/{rca/{topology,incidents/<id>/public,splits},manifest.json,public_case_index.json}. Index uses BenchmarkCaseMetadata; opaque family/pair/source IDs are evaluator metadata, never Agent payload. Candidate Oracle outside public root, local_oracles/incidentbench_v1/rca/incidents/<id>/private/benchmark_oracle.json; ignored, development_visible, pending.

A owns builder/family_split/scenarios/build CLI/generation tests. build_dataset(config,out,oracle_root) -> coverage dict; refuses existing outputs, deterministic bytes. Generic mechanism encoders only in published source. No human review claims.

B owns OracleStore/validator/manifest/citation_review and associated CLIs/tests. OracleStore(root).load_after_completion(incident_id, completed_state) -> BenchmarkOracle; exact incident+run+durable completion receipt, reject links/traversal. validate_dataset(dataset, oracle_root=None) -> dict with ok/errors/coverage. digest_tree(root) -> str; create_lock(dataset,protocol) -> dict; verify_lock(lock,dataset,protocol) rejects drift. seal refuses pending labels/formal placeholder/provider incompatibility; test label commitment secret salt outside public output.

C owns normalizer/scorer/statistics/experiment and runner/analyze CLIs/tests. normalize(state) dict; score_benchmark_run(state,oracle=None,annotations=None) dict; aggregate(rows) list. run_experiment(dataset,split,provider_factory,out,protocol,oracle_root=None) async -> rows; actual run_investigation, cache None, WorkflowOptions(database_equivalent_tools=True, benchmark_fixed_four=True for fixed-four). Variant mapping strong_single->single, fixed_four->fixed, others same. Lead adds benchmark_fixed_four workflow flag before integration. Raw state durably written before any oracle load; preserve failures and unique run keys. Fresh outputs only; resume explicit locked protocol if implemented.

Metadata family/index not passed to Graph. All variants equal information/budgets. Mock results source=mock. Formal Test forbidden before accepted labels and sealing; development Test may execute unscored only. Candidate scoring is explicitly provisional. Technical errors stay denominators. Monitoring/OOD never core denominator. Human metrics null until authentic review. Review artifacts anonymous and variant-blinded.

Lead integrations only: graph/workflow additive fixed-four flag; config/README/source manifest. Merge B -> A -> C -> D, with tests per gate. E read-only independent security/fairness QA. No V1.5. No historical results overwritten.
