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
