# V16 evaluation protocol and pilot DRY RUN

Evidence level: OFFLINE_MOCK. Seed20 is visible development material from a
shared generator lineage. It is neither independent Test evidence nor evidence
of real model quality. No private labels are needed for Stage 0.

The existing runner executes all four equivalent-tool Graph variants with fresh
provider instances, independent run IDs, cache off, jobs=1, fixed seeded order,
equal request/tool/round/wall ceilings and current_dynamic mode. Its lock covers
source, scripts, prompts, config, dependencies, public dataset and protocol.
Do not edit these inputs between execution and reanalysis. Architecture-specific
prompt differences remain part of the architecture treatment.

## Metrics

`scores.jsonl` and historical aggregates retain their existing definitions.
Historical `root_cause_correct` / `root_cause_accuracy` mean service/mechanism
match with technical completion. They do not establish evidence support.

`v16-metrics.json` is a separate, deterministic companion derived only from
completion-gated scorer output. It reports every selected attempt, variant and
failure count. Technical completion, runtime failure and budget exhaustion use
all attempts as their denominator. Budget exhaustion means the normalized
`BUDGET_EXHAUSTED` termination reason. Unknown labels remain null.

`mechanism_service_match_rate` explicitly names the historical matching metric.
`root_cause_correct_rate` requires complete actual human semantic review of all
labelled identifiable attempts; otherwise its numerator and rate are null, with
eligible denominator and reviewed count shown. A structurally present citation
or matched evidence ID does not substitute for human semantic judgment.

`false_resolution_rate` is a labelled service/mechanism error metric: a RESOLVED
report on a Missing case, or a service/mechanism mismatch on an identifiable
case. Both strata are also reported separately. Technical failures remain in
their labelled denominator; an unscored case is excluded from label-dependent
rates and remains in engineering attempt counts. This metric does not assert
that every matching report is semantically supported.

Citation existence and human semantic support remain separate per-run values.
The existing runner retains usage, latency, tool, request, token and cost fields;
unknown usage/cost must remain null. The V16 companion supplies no confidence
intervals or p values because independent source families are not established.
Historical statistical artifacts retain historical definitions and are not
evidence of independence.

## Stage 0 commands

Run from `.worktrees/v16-d`, using the main checkout's Python interpreter and
`PYTHONPATH=<absolute-worktree>/src`:

```powershell
& ../../.venv/Scripts/python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split seed --variant all --provider mock --cache-mode off --jobs 1 --out results/v16/<unique>/mock80
& ../../.venv/Scripts/python.exe scripts/analyze_incidentbench.py --input results/v16/<unique>/mock80/raw-runs.jsonl --out results/v16/<unique>/analysis
```

Do not supply `--oracle-root` for unlabelled engineering validation. Reanalysis
verifies lock, ledger/order/identity, artifact digests and durable state receipts,
then recomputes historical scores through the same scorer without a provider.
`score-recomputation.json` records exact score equality; retain any inequality
and investigate rather than relabelling it successful. The companion must also
match byte for byte between execution and reanalysis.

## Real pilot DRY RUN only

Execution status: BLOCKED_AWAITING_USER. Paid requests made: zero.

- G1a: obtain a fresh external provider readiness record matching the actual
  model, response format and frozen protocol. Historical offline success does
  not satisfy this gate.
- G2a: obtain the accepted visible Dev manifest and its review/provenance record.
  Do not substitute Seed results for the new Dev set or treat candidate labels
  as independently reviewed truth.
- Budget: user must approve model/config and total physical request, token,
  cost and wall limits before constructing a real pilot execution.
- Scope: choose 2–4 visible Dev cases, four variants, one repeat. The current
  CLI selects a complete split; use an explicitly versioned pilot dataset and
  manifest rather than silently filtering cases or changing the experiment name.
- Freeze the pilot dataset, source, config, prompts, model parameters, protocol,
  order seed and budgets; validate equivalent tools and failure-inclusive rates.
- Run only after the above gates pass; retain raw states, receipts, failures,
  scores, locks, review bundle and provider usage. Unknown costs remain null.
- G2b remains blocked until actual independent review, adjudication, source
  family audit and label-owner sealing. No formal/Test claim is authorized.

No real command is executable from this checklist alone. The dry run deliberately
does not instantiate a real provider or read credentials/private labels.
