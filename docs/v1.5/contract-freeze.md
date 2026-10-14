# CAES v1 interface and writer freeze

Authority: `docs/plans/IncidentLens_V1.5_CodingAgent_Implementation_Plan.md`, read in full.
Base: 7c48da1. Contract source: orchestration/active_investigation/contracts.py.
P1 contract checks: 12 passed. JSON schema export/hash recorded alongside baseline artifacts.

Lead owns contracts.py, policy.py, graph.py, schemas/workflow.py, orchestration/config.py,
CLI, configs and README. A owns candidate_generator.py/eligibility.py and candidate tests
(excluding test_candidate_contracts.py). B owns feature_extractors.py/cost_estimator.py/
selector.py and their tests. C owns evaluation/active_evidence, three v15 scripts and
evaluation tests. D follows integration and owns algorithm/fairness/results documentation.
E is read-only independent QA. Workers do not delegate and never edit other owners' files.

Frozen callable interfaces:

```python
generate_candidates(visible: VisibleState, proposals: tuple[InvestigationTask, ...],
                    role_acl: dict[str, tuple[str, ...]], config: PolicyConfig
                    ) -> tuple[CandidateAction, ...]
candidate_signature(candidate: CandidateAction) -> str
check_eligibility(candidate: CandidateAction, visible: VisibleState,
                  budget: BudgetView, role_acl: dict[str, tuple[str, ...]],
                  config: PolicyConfig) -> str | None  # stable rejection code or None
estimate_cost(candidate: CandidateAction, budget: BudgetView) -> CostEstimate
extract_features(candidate: CandidateAction, visible: VisibleState,
                 cost: CostEstimate) -> CandidateFeatures
select_candidates(candidates: tuple[CandidateAction, ...], visible: VisibleState,
                  budget: BudgetView, role_acl: dict[str, tuple[str, ...]],
                  config: PolicyConfig, policy: PolicyName) -> SelectionDecision
```

No model/tool/Oracle calls in these functions. DTO nested containers are shallow-frozen;
Lead constructs detached deep copies and validates their digest again before materialization.
Published hypothesis predictions, questions, source categories and observed IDs only;
no provider handle, evidence record metadata/path, dataset family/split/label enters CAES.
ACL is passed explicitly from runtime workflow; database is absent in ordinary legacy RCA.
Complete state digest includes run/incident/round, published hypotheses/questions/checks,
board digest and task completion signatures. IDs remain runtime-owned.

Cost fallback: two Investigator logical requests, <=2 planned tools, conservative physical
attempt multiplier from configured provider. Token/latency unknown remains null. Reserve
at least one Verifier request and fetch tool; reserve is max(existing recovery reserve,
policy reserve), not added twice. Estimate never charges a permit. Zero selection uses
explicit ABSTAIN with NO_USEFUL_ACTION, never a loop. All existing dispatch/merge/gates remain.

B1 bypasses CAES. B1c first_eligible, B2 active_no_cost, B3 active_no_discrimination,
B4 active_evidence share generation and hard feasibility. B0 maps actual benchmark fixed-four.
Experiments here are unsealed Seed engineering diagnostics; empty Dev/Test and pending
human labels block P4/P5 research and confidence claims. No Test Oracle reading is authorized.
