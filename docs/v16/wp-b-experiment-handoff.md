# WP-B → WP-D benchmark handoff

Scope: development/course-project comparison, owner-approved reference labels; not an independent blind test. Authority and limits: [label policy](wp-b-label-acceptance-policy.md). No paid execution is authorized by this handoff. Run from the isolated WP-B checkout; retain the original repository and saved completion paths.

## Inputs and access

Original repository `$R = 'C:\Develop\python_projects\COMP5584_Agents\IncidentLens'`. Python `$P = "$R\.venv\Scripts\python.exe"`. Set `$env:PYTHONPATH="$PWD\src"` in the intended frozen checkout before invoking Python; this prevents the editable installation from importing another worktree.

| Split | Public dataset | Evaluator-only root | Size |
|---|---|---|---:|
| Seed | `$R/data/incidentbench_v1` | `$R/local_oracles/incidentbench_v1` | 20 |
| Dev | `$R/data/incidentbench_v16_dev` | `$R/local_oracles/incidentbench_v16_dev` | 10 |

Each runtime dataset includes manifest, coverage, public index, topology, split IDs and public case observations. Oracle file layout is `rca/incidents/<id>/private/benchmark_oracle.json`. Evaluator credentials/permissions must remain separate from Agent filesystem/tool access. Never mount the oracle root as runtime data, tool response, prompt context or frontend Replay input. Run raw persistence precedes receipt-gated oracle access. Keep raw Agent artifacts separate from evaluator output containing reference comparisons.

The full case-ID list and hashes are in [inventory](wp-b-final-dataset-inventory.md) and `docs/incidentbench/wp-b-project-accepted-freeze.json`; detailed causes, support, competing alternatives and misleading references are in the ignored evaluator inventory, whose exact path is recorded in validation. Owner acceptance is an external sidecar; original pending reviewer provenance is preserved.

## Freeze and offline preparation

After final source integration, run the finalizer from that checkout with fresh outputs:

```powershell
& $P scripts/finalize_wp_b_dataset.py --repository $R --public-out "$R/results/v16/wp-b-final/freeze.json" --evaluator-out "$R/local_oracles/wp-b-final/inventory.json" --pilot-public-out "$R/results/v16/wp-b-final/pilot-public" --pilot-oracle-out "$R/local_oracles/wp-b-final/pilot-oracles"
```

The three-case pilot copies the original ordinary, misleading and insufficient-evidence case bytes; no root cause or observation is regenerated. Pilot metadata is a separately hashed subset, not the complete Seed manifest. Prepared and validated input already exists at `$R/results/wp-b/pilot-public`, with evaluator-only labels at `$R/local_oracles/wp-b-pilot`: `incident_1001` ordinary, `incident_1002` misleading, and `incident_1003` insufficient evidence, all in Seed. Use these existing paths or prepare fresh outputs with the command above. Validate both public and privileged modes before model execution. No provider is constructed by the finalizer/validator or offline evaluator.

## Four-architecture execution

`scripts/run_incidentbench.py --variant all` executes `strong_single_equivalent_tools`, `fixed_four_equivalent_tools`, `dynamic_no_verifier`, and `full`. Keep the complete set and paired schedule. One repeat means 12 pilot investigations, 80 Seed investigations and 40 Dev investigations. The pilot is additional preparation evidence, not an independent repeat of the full experiment.

Start from `configs/incidentbench-protocol.yaml`. Before real execution, create a private frozen real protocol: set `provider_id=real`, the explicitly approved `model_id`, a unique protocol ID, and keep `formal=false`, `blindness_level=development_visible`. Temperature 0, cache off, jobs 1, equivalent tools, four variants, seeded schedule 14100, analysis seed 14101, and identical budgets/recovery settings apply across architectures. Default proposal per investigation: six rounds, 24 tools, 32 logical model calls, 600-second wall limit, 180-second request timeout. These are proposed ceilings, not approval or guaranteed adequacy; historical real failures justify a small pilot first. Freeze response format, provider recovery/repair settings in `configs/system.yaml`, dependency versions, prompts and all source hashes as well. Do not substitute a model or adjust ceilings midway through a paired batch.

Real execution additionally requires authentic external provider readiness matching model/response format and explicit budget approval. Readiness is compatibility evidence, not a successful RCA result. Do not fabricate `provider_compatible=true`. Credentials stay in the existing project-local mechanism and must never be printed or committed. Freeze a protocol lock through `manifest.create_lock(dataset, ExperimentProtocol(...))` after final preparation; use a separate lock for each dataset/subset.

After approval, copy the default YAML into the ignored WP-D directory and edit the approved model/provider and ceilings explicitly. Never use the Mock protocol for a real invocation. Create the lock without constructing a provider (set the three paths first):

```powershell
$Dataset = "$R/results/wp-b/pilot-public"
$Protocol = "$R/local_oracles/wp-d/pilot-protocol.yaml"
$Lock = "$R/local_oracles/wp-d/pilot-lock.json"
@'
import json, sys, yaml
from pathlib import Path
from incident_lens.incidentbench.manifest import create_lock
from incident_lens.incidentbench.schemas import ExperimentProtocol
dataset, protocol_path, lock_path = map(Path, sys.argv[1:])
protocol = ExperimentProtocol.model_validate(yaml.safe_load(protocol_path.read_bytes()))
assert protocol.provider_id == "real" and not protocol.formal
assert protocol.model_id not in {"mock", "deterministic-public-policy-v1", "TO_FILL_BEFORE_FREEZE"}
with lock_path.open("x", encoding="utf-8") as stream:
    json.dump(create_lock(dataset, protocol), stream, indent=2, sort_keys=True)
'@ | & $P - $Dataset $Protocol $Lock
```

```powershell
# Execute ONLY after WP-D has obtained model/readiness/budget approval.
& $P scripts/run_incidentbench.py --dataset "$R/results/v16/wp-b-final/pilot-public" --split seed --variant all --provider real --protocol "$R/local_oracles/wp-d/pilot-protocol.yaml" --protocol-lock "$R/local_oracles/wp-d/pilot-lock.json" --readiness "$R/local_oracles/wp-d/readiness.json" --cache-mode off --jobs 1 --out "$R/results/v16/wp-d/pilot-UNIQUE"
# Repeat with the complete Seed/Dev roots, their respective split/lock and fresh output.
```

Omitting `--oracle-root` intentionally keeps execution artifacts unscored and suitable for oracle-isolated runtime inspection. Score later in an evaluator-only process after completion. The runner also supports receipt-gated inline scoring, but those outputs are private evaluator artifacts and must not be served as ordinary reports.

## Scoring, analysis and recovery

`scripts/analyze_incidentbench.py --input <batch>/raw-runs.jsonl --out <fresh-analysis>` verifies the original experiment lock and replays saved scoring without provider calls. Add `--oracle-root` only in the evaluator environment, keeping the output private. Preserve original paths: existing completion receipts bind absolute saved-state paths and no relocation protocol exists. New additive `scripts/wp_b_evaluate.py` supplies separate service/mechanism matches, outcome categories and reference coverage. Example (fresh output required):

```powershell
& $P scripts/wp_b_evaluate.py --experiment "$R/results/v16/eval-smoke/integrated-seed-20261015-02" --dataset "$R/data/incidentbench_v1" --oracle-root "$R/local_oracles/incidentbench_v1" --historical-source-root "$R/results/v16/wp-b-historical-source" --repository $R --acceptance docs/incidentbench/wp-b-project-accepted-freeze.json --out "$R/local_oracles/wp-b-final/seed-recheck-UNIQUE"
```

For newly executed batches, pass their exact frozen execution checkout as `--historical-source-root`. The preserved 142-file historical snapshot matches all four historical source/scripts/config/prompt tree digests and the dependency lock; it was reconstructed without altering the dirty primary checkout. Read the output's actual per-row oracle digest alongside the external owner acceptance freeze; the generic evaluator does not automatically declare arbitrary input labels owner-approved. See validation for actual output paths. Never interpret citation existence or reference-set coverage as independently confirmed semantic grounding.

Existing Seed80 and Dev40 Mock ledgers are reused from `$R/results/v16/eval-smoke/integrated-{seed,dev}-20261015-02`. Their source/locks describe the historical implementation; new offline evaluation is a new scorer version, not a new execution of those investigations. Do not edit the historical scores/locks to disguise drift. Unknown/incomplete usage or cost remains null, with known lower bounds shown separately.

Real `--resume` is unsupported and fails closed. Stop on interruption; preserve failed and interrupted attempts and request a separately approved recovery plan. Do not silently restart failed cases or omit them from denominators. Offline Mock `--resume` requires exact original source/data/protocol/parameter/evaluator locks and validates existing outputs. A changed source needs a new output directory, not an edited lock.

## Analysis and scale

Primary descriptive contrasts: Full vs Single, Full vs Fixed, Full vs Dynamic No Verifier, paired by case/repeat. Report accuracy, correct/incorrect abstention, diagnostic errors and technical subtypes separately; include all attempted cases in the applicable denominators. Report misleading-case results, per-case sufficiency of Single, and measured requests/tools/time/known usage. Retain missing label counts instead of turning unknown labels into success/failure. Verifier contrast is an architectural ablation, not a causal proof about every internal component.

The default logical-call ceilings imply at most 384 admitted calls for the 12-run pilot and 3,840 for the 120-run complete batch; physical HTTP attempts can differ because transport retries and repair requests are separately measured. Wall ceilings sum to two hours and 20 hours respectively with jobs=1, excluding setup/scoring. These are ceiling arithmetic, not runtime/cost predictions. No approved dollar/token ceiling or verified current unit price is available; cost is unknown. WP-D must approve a monetary limit and monitor actual attempts, retries and usage rather than assume the logical cap is an HTTP or dollar cap.

Historical DeepSeek pilot evidence records 28 investigation HTTP requests across eight technically failed investigations, plus a separate compatibility probe. Known investigation tokens were 85,291 as a lower bound; only five of eight runs had complete usage. Bridge runs have different identity/isolation/accounting limits and cannot estimate API prices. These local records justify provider-risk controls, not a precise cost forecast. Mock timing under concurrent validation load is unsuitable for architecture speed claims.

Seed and Dev share `causal-world-v1` encoder lineage and near-duplicate grouping. Treat the combined 30 as correlated development cases; descriptive paired differences are primary. Existing family bootstrap/exact discordance outputs are exploratory and cannot certify independent samples or significance. No production reliability, independent blind performance, cross-source generalization, semantic-grounding correctness or Full superiority is established. Formal G2b/sealing and real E2E gates remain distinct from WP-B engineering readiness.
