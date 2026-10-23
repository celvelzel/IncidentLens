# DSPy acceptance evidence

`validation.json` records engineering checks only. `retained-audit/` inventories
historical artifacts and exports a pending semantic-review worksheet.

Reproduce from the repository root:

```bash
python -m experiments.dspy audit --root . --out results/dspy-new-audit
python -m experiments.dspy.smoke --out results/dspy-new-smoke
```

The smoke runs actual DSPy optimizer code with deterministic mock tasks/proposals,
then 160 complete LangGraph investigations. It is not real-model evidence.
Full generated traces, candidate bundles, pending samples and system CSVs are local
reproducible outputs; the committed report stores their aggregate and export hashes.
No production prompt bundle was promoted.
