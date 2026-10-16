# WP-B dataset validation

Validation on 2026-10-16 used the original repository's existing Seed20 and Dev10
bytes and evaluator-only roots. Both public and privileged validators returned
`ok=true`, `errors=[]` for each dataset. The prepared three-case Pilot also passed
privileged validation. No source dataset or reference label changed.

`scripts/finalize_wp_b_dataset.py` reuses existing schema, `validate_dataset`,
`check_private_git`, safe-path and `digest_tree` APIs. It checks manifest/public
hashes, split/index/files, duplicate case and evidence IDs, Oracle file coverage,
evidence references, cause-specific discriminators, multi-source support and
cause-before-support-symptom chronology, missing-evidence support/rationale,
counterfactual pairing and public-file/answer isolation. Existing validator limits
apply: consistency checks do not certify real-world truth or semantic grounding.
There is no new independent human review or semantic annotation.

Combined Seed/Dev checks report zero exact public duplicates and 20 cross-split
normalized excerpt pairs >=0.97, with a shared cluster and encoder. These findings
are retained in the freeze; they limit independent-sample inference rather than
silently rewriting accepted cases. See [inventory](wp-b-final-dataset-inventory.md).

Reproduction from an editable source checkout (fresh output paths required):

```powershell
$env:PYTHONPATH='src'
python scripts/finalize_wp_b_dataset.py --repository C:/Develop/python_projects/COMP5584_Agents/IncidentLens --public-out results/wp-b/freeze-recheck.json --evaluator-out C:/Develop/python_projects/COMP5584_Agents/IncidentLens/local_oracles/wp-b-recheck/inventory.json
# Optional fresh Pilot outputs, containing copied original bytes:
python scripts/finalize_wp_b_dataset.py --repository C:/Develop/python_projects/COMP5584_Agents/IncidentLens --public-out results/wp-b/pilot-freeze-recheck.json --evaluator-out C:/Develop/python_projects/COMP5584_Agents/IncidentLens/local_oracles/wp-b-pilot-recheck/inventory.json --pilot-public-out C:/Develop/python_projects/COMP5584_Agents/IncidentLens/results/wp-b/pilot-recheck --pilot-oracle-out C:/Develop/python_projects/COMP5584_Agents/IncidentLens/local_oracles/wp-b-pilot-recheck/labels
python -m pytest tests/incidentbench/test_wp_b_finalization.py -q
python -m ruff check scripts/finalize_wp_b_dataset.py tests/incidentbench/test_wp_b_finalization.py
```

Actual targeted tests: **5 passed in 69.98s**; Ruff: **all checks passed**.
Tests cover deterministic inventory/original-byte preservation, safe public
allowlisting, pending provenance preservation, hash-drift rejection, Pilot byte
identity/validation, evaluator output confinement, and refusal to overwrite.
The fixtures are disclosed generated test data, not replacements for the frozen
existing corpus. The finalizer's actual original-corpus execution separately
returned `cases=30`, `status=project_accepted`.

The existing `results/v16/final-qa/20261015-02/experiment-verification.json`
was inspected: Seed80 + Dev40, 120 unique attempted keys, zero technical failures,
120 unscored, zero HTTP, exact saved-score recomputation and companion-byte equality.
These are historical Mock engineering receipts, not new scored model experiments.
No paid call or redundant 120-run regeneration was performed by B1.

The private inventory and Pilot labels are ignored and evaluator-only. The public
freeze is allowlisted from public case metadata; private root causes, support IDs,
rationales and misleading annotations are excluded. The finalizer changes no
runtime, core contracts, formal Seal behavior or scorer. Runtime isolation and
scorer regression findings belong to the coordinating WP-B acceptance report.

## Final integrated validation — 2026-10-16

Validated implementation: `b500005651ed5373bdd01869a764d2f2c786ad9b`, isolated
`codex/wp-b-finalization` checkout. The finalizer was rerun from this checkout:
30 cases, both public/privileged audits passed, frozen reference bytes unchanged.
The committed freeze is the resulting `docs/incidentbench/wp-b-project-accepted-freeze.json`;
its SHA-256 is `27dfe942ceda351c8a9f52b6212d8f6e34b19765926cf2ce4381ce2c435e43d4`.
Dataset version: `wp-b-project-accepted-v1`. Validated canonical default protocol
SHA-256: `f041cd492fda139bc286459c1e43a75d98f48fefb50f2553b3833e193cf3ff4b`.
This default development protocol is not an approved real-model protocol.

| Validation | Actual result |
|---|---|
| Lead `python -m pytest -q -rs` | 977 passed, 3 skipped, 384.90s, exit 0 |
| Lead `python -m ruff check src scripts tests` | all checks passed |
| Lead `git diff --check` | passed |
| Download isolation + existing V16 artifact boundaries | 14 passed |
| Independent QA targeted suite | 50 passed, 1 skipped, 101.97s |
| Independent QA changed-file Ruff and diff checks | passed |
| Original Seed80 + Dev40 ledger/state/identity/digest validation | all 120 pass |
| Original no-oracle score recomputation | exactly equal to retained unscored scores |
| Integrated-source accepted-reference scoring + repeated recomputation | 80 + 40 rows exactly equal; zero label-load errors |
| Historical-source paired analysis with reference labels | 80 + 40 rows; scores agree with integrated evaluator |
| Pilot/Seed/Dev input and frozen Mock lock preparation | 3/20/10 cases; 12/80/40 scheduled keys; no investigations executed |

All skipped tests concern unavailable Windows symlink privileges. Simulated
reparse confinement tests pass; this does not claim an OS sandbox. Full regression
includes meaningful four-architecture CLI Mock smoke coverage; the existing
120-case-variant experiment was not regenerated. No paid request was issued.

The main repository's existing uncommitted `graph.py`/`termination.py` changes were
preserved. Their source hashes differ from the old experiment lock. A 142-file
historical snapshot at `results/v16/wp-b-historical-source` reconstructs exact
historical source/scripts/config/prompt bytes (all four tree hashes match), using
the saved fingerprint and matching Git blob/newline candidates. Dependency bytes
also match. Historical execution and current evaluator provenance are separate.
The current evaluator source-tree digest is
`d695dd7a56f251f0d0245b8b89f2ac2b64f0c12b9a70af35bab3c6a2c7dd437e`.

Original-repository evidence paths:

- `results/v16/wp-b-final-pytest.log` and `.exit`: full-suite output and exit 0.
- `results/v16/wp-b-final/freeze.json`: actual finalizer output.
- `local_oracles/wp-b-final/inventory.json`: full evaluator-only inventory.
- `local_oracles/wp-b-final/{seed,dev}-evaluation-integrated/evaluation.json`:
  final accepted-reference metrics; complete evaluator lock matches the integrated
  checkout, exact frozen public/oracle hashes and acceptance file hash verified.
- `local_oracles/wp-b-final/{seed,dev}-paired-analysis/`: historical locked
  analyzer output with Full vs Single/Fixed/Dynamic contrasts. Its
  `exact_scores_equal=false` is expected because original scores were unscored
  and labels were newly supplied; repeated labelled scoring and cross-analyzer
  agreement are independently true. Historical files were not rewritten.
- `results/v16/wp-b-final/final-verification.json`: source/hash/receipt,
  no-oracle equality, labelled repeatability and paired-score agreement receipt.
- `results/v16/wp-b-final/input-command-verification-integrated.json`: final
  input/command preparation, explicitly imported from this worktree. Its private
  `*-mock-protocol-lock-integrated.json` locks remain under `local_oracles/wp-b-final`.
- `results/v16/wp-b-final/pilot-public`,
  `local_oracles/wp-b-final/pilot-oracles`, and
  `local_oracles/wp-b-final/pilot-acceptance.json`: ready three-case subset inputs.

The earlier `input-command-verification.json` is superseded: its process resolved
the editable installation to the primary checkout. It is preserved for audit;
the integrated replacement explicitly verifies the imported module path and
records the current source digest. An initial coordinator audit command similarly
failed to import the new module before setting `PYTHONPATH`; no artifacts were
changed by that failed command. The corrected full verification passed. A worker
CLI test also failed when another worker added source files mid-test, correctly
triggering source-drift refusal; the stable integrated full suite passes that
test. Failed/intermediate outputs remain retained, never deleted or relabeled.

Independent QA findings were resolved: downloads now use validated Replay data;
private reports are rendered from validated state; evaluator output is confined
to an ignored/untracked repository `local_oracles` tree; provider failures use
the actual normalized counter; `project_accepted` requires exact public/oracle
freeze hashes. No formal seal, runtime guard or label provenance was weakened.
