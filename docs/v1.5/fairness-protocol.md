# Controlled comparison and saved replay

Status: Seed engineering protocol. Formal research is BLOCKED; see
`experiment-preregistration.md`. Actual modules are `evaluation/active_evidence`,
`orchestration/active_investigation` and the three `scripts/*v15*` entry points.

| Group | Actual Graph/workflow path | Contrast |
| --- | --- | --- |
| B0 | fixed + benchmark_fixed_four + equivalent database tools; CAES bypass | Auxiliary fixed-four reference |
| B1 | full + current_dynamic; CAES bypass | Deployment baseline |
| B1c | full + first_eligible | Generator-order same-pool control |
| B2 | full + active_no_cost | Removes cost ranking, retains hard feasibility |
| B3 | full + active_no_discrimination | Removes D weight, retains other features |
| B4 | full + active_evidence | Full CAES |

B1c/B2/B3/B4 use the same generator and feasibility rules for identical visible input.
Once actions diverge, later evidence states and candidate pools can diverge; whole-run
pools are not asserted identical. Replay a common snapshot under each selector for
selection attribution. B4-B1 mixes generator and selector changes; B4-B1c addresses
selector attribution. B0's fixed batching differs and is an auxiliary comparison.

Runner controls: fresh provider per run, same model/temperature/recovery parameters,
public dataset revision, prompt/schema/dependency/source locks verified per run, cache
off, jobs=1, legacy_rca, equivalent database ACL, no monitoring/remediation, matched
round/request/tool/wall limits. Physical requests include failures/retries/repairs;
unknown tokens/cost remain null. Formal/Test and real-provider gates fail before
provider execution. No automatic mock substitution is a real-provider result.

From a checkout with installed dependencies (replace Python path for another machine):

```powershell
$py = 'C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $PWD 'src'
& $py scripts/run_v15_active_eval.py --help
& $py scripts/run_v15_active_eval.py --dataset data/incidentbench_v1 --split seed --variants B0 B1 B1c B2 B3 B4 --provider mock --cache-mode off --jobs 1 --out results/v15/seed-UNIQUE
& $py scripts/analyze_v15_active.py --input results/v15/seed-UNIQUE --out results/v15/analysis-UNIQUE
& $py scripts/replay_v15_selection.py --trace results/v15/active-smoke-20261014/trace.json
```

UNIQUE paths must not exist; the runner preserves old results. Replay's last example
uses the historical main-checkout artifact, not an artifact included in every clone.
Use any saved list, `events`, or `state.events` envelope for local replay. Legacy traces
with no ACTION_SELECTED events return `[]` normally. JSON is the current trace view;
no old UI modification or additional renderer is needed for the secondary UI gate.
Replay calls only pure selection logic; it does not rerun evidence collection.

`--protocol FILE.json` loads strict `ActiveProtocol` settings; explicit CLI values
override corresponding fields. Tight-budget diagnostics use a separate protocol with
identical reduced limits for every group and a new output directory. Current defaults:
6 rounds, 24 tools, 32 model requests, 600 seconds, 1 repeat, run-order seed 15100,
analysis seed 15101, 10000 bootstrap samples. These are executable defaults, not
registered Frozen Test choices. Main 67fb9a5 adds `--resume` for verified Mock-only
ledgers: source/protocol/receipt/prefix locks must match; completed records are not
rerun, orphan STARTED records remain unknown failed attempts and are not re-executed.
Older incompatible checkpoints are refused. Use the original output path and saved
protocol; this does not authorize real-provider or formal research recovery.
`--frozen-protocol` is not an implemented flag.

Artifacts include protocol/manifest/run-order, durable raw-runs/errors/progress,
state receipts, case-level/aggregate/paired/action/family tables, uncertainty,
calibration and source hashes. Raw rows retain failed and stopped runs. Diagnosis,
workflow completion and runtime failure are distinct. Root correctness, correct
abstention and human grounded success stay null without reviewed evaluator labels.
Existence of citations alone is not semantic support. Usage coverage accompanies cost.
Analyzer refuses incomplete schedules, duplicate rows, modified artifacts or invalid
state receipts. Interrupted ledgers remain evidence even when aggregate analysis refuses.

Future formal analysis pairs cases, averages replicates within case/variant, and
clusters source-linked families together; repeated template variants are not independent
families. Primary contrast B4-B1, key mechanism B4-B1c, exploratory B0/B2/B3. Technical
failures remain in quality denominators; normal inconclusive outcomes are not silently
deleted or called correct abstention. Too few independent clusters produce null CI
with a reason. Report raw differences, denominators and missingness before inference.
