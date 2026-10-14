# IncidentBench V1.4

IncidentBench adds deterministic development evidence, evaluator-only candidate labels, actual Graph comparisons and saved-artifact analysis. The present dataset is an offline development corpus: 20 Seed cases, no Dev/Test, no accepted labels, and no audited independent families. See the [scenario catalog](scenario-catalog.md), [research report](release-report.md), [contracts](contracts-freeze.md), and [handoffs](workstream-handoffs.md).

## Dataset card

Version `incidentbench-v1`, interface `incidentbench-v1.0`, builder `causal-world-v1`. The manifest and coverage files are authoritative for a particular generated revision. Four declared source groups share development encoder lineage. Public observations are generated from causal world states, not collected production incidents. Candidate labels remain pending and `blindness_level=development_visible`.

The dataset root contains `manifest.json`, `coverage.json`, `public_case_index.json`, and `rca/{topology,splits,incidents/<id>/public}`. Public case files follow existing IncidentLens contracts: `incident.json`, `logs.jsonl`, `metrics.csv`, `changes.jsonl`, `configs.jsonl`, and optional `database.jsonl`. IDs, source paths and timestamps must be consistent. Family/source metadata is evaluator bookkeeping and is not an Agent prompt. A separate evaluator root contains `rca/incidents/<id>/private/benchmark_oracle.json`; it must never overlap the public root.

`BenchmarkCaseMetadata`, `BenchmarkOracle` and `ExperimentProtocol` in `src/incident_lens/incidentbench/schemas.py` define the schemas. An identifiable candidate requires a sufficient support set; missing cases have none. Accepted labels require actual independent review provenance, not generated reviewer names. The [annotation guide](annotation-guide.md) describes future authentic review records; this offline scope creates no human review.

## Evaluation card

The four benchmark variants are `strong_single_equivalent_tools`, `fixed_four_equivalent_tools`, `dynamic_no_verifier`, and `full`. They execute the actual investigation Graph with equivalent public database access, cache off, fresh providers/budgets and fixed protocol settings. Fixed-four is an explicit benchmark option; legacy fixed-three keeps its behavior.

Raw completion/error states are persisted before evaluator labels are loaded. Candidate scoring on Seed/Dev is provisional. Development Test remains unscored; formal experiments require accepted independent labels and sealing and are currently blocked. Fresh outputs refuse existing directories. Explicit offline `--resume` validates locks and retains completed, failed and interrupted attempts without reexecution; real-provider resume remains unsupported.

Diagnostic service and mechanism must both match. Technical failure stays in attempted-run denominators. Normal INCONCLUSIVE can earn correct-abstention credit only for missing-evidence cases; Monitoring NO_ALERT is separate. Citation existence requires actual observed/shared evidence and is distinct from semantic support. Human support, unsupported-claim and human-grounded metrics remain null without authentic annotations. Cost and incomplete usage remain null. A computed family bootstrap does not establish independence of the current shared-lineage groups.

## Model/provider card

`MockProvider` is deterministic offline contract evidence; it is not a learned model or an estimate of real diagnostic quality. It executes Graph/tool behavior against public observations and carries `source=mock`. Real-provider V1.4 results are pending. Real execution requires a model-matching protocol and an external `--readiness` JSON with matching `model_id`, `response_format`, and `provider_compatible=true`; the runner does not issue an automatic probe. Compatibility evidence alone cannot establish RCA accuracy. No real request is required by the reproduction below and no silent Real-to-Mock substitution is allowed.

## Fresh reproduction in PowerShell

From a fresh checkout with Python 3.11 or newer, install the project and development dependencies:

Benchmark scripts currently require an **editable source checkout**: the manifest
locks repository scripts, prompts and configuration alongside the executing code.
Standalone wheel-only Benchmark execution is unsupported. The separate wheel
verification covers legacy CLI/install/replay behavior; it does not establish
wheel-only IncidentBench execution.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m pytest tests/incidentbench/test_cli_e2e.py -q
```

The CLI E2E test writes a disclosed two-case ordinary/missing fixture from `development_config()` in `tests/incidentbench/test_generation.py`. It invokes build, public and privileged validation, eight actual Mock Graph runs, and saved-state analysis through subprocesses. Its temporary evaluator inputs are development fixtures, not hidden Test mappings. It checks fresh-output refusal and score equality after recomputation.

To reproduce the complete 20-case disclosed development fixture, create a local JSON specification and fresh directories. The specification contains candidate causes and belongs outside the public dataset; do not publish held-out private specifications.

```powershell
New-Item -ItemType Directory -Force local_oracles | Out-Null
.venv\Scripts\python.exe -c "import json,runpy; from pathlib import Path; m=runpy.run_path('tests/incidentbench/test_generation.py'); Path('local_oracles/development-demo.json').write_text(json.dumps(m['development_config']()),encoding='utf-8')"
.venv\Scripts\python.exe scripts/build_incidentbench.py --config local_oracles/development-demo.json --out data/incidentbench_demo --oracle-root local_oracles/incidentbench_demo
.venv\Scripts\python.exe scripts/validate_incidentbench.py --dataset data/incidentbench_demo --mode public
.venv\Scripts\python.exe scripts/validate_incidentbench.py --dataset data/incidentbench_demo --mode privileged --oracle-root local_oracles/incidentbench_demo
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_demo --split seed --variant all --provider mock --cache-mode off --jobs 1 --oracle-root local_oracles/incidentbench_demo --out results/incidentbench/demo-mock
.venv\Scripts\python.exe scripts/analyze_incidentbench.py --input results/incidentbench/demo-mock/raw-runs.jsonl --oracle-root local_oracles/incidentbench_demo --out results/incidentbench/demo-analysis
```

The examples use `--dataset` with the benchmark root containing manifest/index and `rca`; the runner also accepts its `rca` subdirectory. Build requires `--oracle-root`. The runner can omit that argument to produce unscored runs. Keep the original dataset, source checkout, protocol and completion receipt files available for analysis: locks and saved-byte digests reject drift, and artifact directories currently contain absolute local context paths. Portability to a moved checkout requires a separately implemented relocation protocol.

Actual runner outputs include `protocol.json`, `protocol.lock.json`, `experiment-context.json`, durable completion files, `progress.jsonl`, `raw-runs.jsonl`, `scores.jsonl`, `case-level.csv`, `aggregate.json`, `aggregate.csv`, `coverage.json`, `failure-categories.json`, `review-coverage.json`, `statistical-analysis.json`, `paired-differences.csv`, `family-summary.csv`, `citation-review-bundle.jsonl`, `artifact-digests.json`, `errors.jsonl`, and `reproducibility.txt`. Analysis reuses saved state without provider calls and exports recomputed case scores, aggregates and paired/family statistics. Review bundles are pending exports, not human annotations.

For an offline demonstration, show an ordinary report, missing-evidence INCONCLUSIVE, equal-tool four-variant traces and recomputation equality. Label every displayed score as Mock/candidate. Full regression/install evidence and final run counts belong in the Lead's release acceptance logs.

## Known limits

Recorded DeepSeek and Codex child-model development runs, including failures and
usage limitations, are summarized in [development-pilot evidence](development-pilots.md).
The [review and bridge improvement plan](../plans/IncidentLens_V1.4_Review_Bridge_Improvement_Plan.md)
is a plan-only follow-up; it is not implemented runtime behavior.

No independent held-out data, human truth/citation review, real-model V1.4 comparison, production Monitoring/OOD evaluation or executed remediation is present. Formal freeze remains blocked; all human semantic and remediation-effectiveness metrics remain null. Dataset validation establishes contract consistency and does not establish operational truth or model superiority. No V1.5 implementation is included.
