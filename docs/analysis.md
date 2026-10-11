# Saved-trace analysis

```powershell
python scripts/analyze_eval.py --input results/acceptance/p5-dev/raw-runs.jsonl --out results/analysis-dev
```

Use a new, separate output folder. Existing output folders are rejected; input
artifacts are preserved. The script executes no graph, provider or tools and reads
no dataset oracle files. Each stored state must have a completed report before its
stored `oracle_scoring_fields` are accessed. Missing scoring oracles fail explicitly.
Metrics are recomputed with `score_completed`, not copied from cached metrics.

`coordination.csv` contains one row per run: round index, INVESTIGATE decisions,
replanning decisions (INVESTIGATE decisions after the first), assigned task roles,
actual TOOL_CALL events, insufficient/conflicted REVIEW counts and the sum of
requested checks in reviews. Dynamic role transitions count consecutive
INVESTIGATE decisions with different sets of assigned roles; they are descriptive
counts for all variants, not proof of dynamic improvement. Repeated review requests
are counted each time they occur. Decision events can include attempted assignments
rejected by a runtime guard; round index records actual graph progression.

`mechanism-slices.csv` groups variant, stored oracle failure mode, misleading
evidence presence and identifiability. It reports n, correct roots, correct
abstentions, runtime failures, citation totals and rates with applicable denominators.
Root accuracy is undefined for unidentifiable groups and abstention accuracy is
undefined for identifiable groups; citation validity is undefined without citations.
STOP failures remain in the relevant denominator.

The source design's F1–F5 are deployment/config regression, database connection
exhaustion, Redis unavailability, external payment timeout and backend resource
saturation. Slices preserve exact stored failure-mode values rather than guessing
an F label. Misleading presence separates ordinary/misleading cases; identifiability
separates complete/missing causal evidence. Empty groups are omitted. Compare matched
incident IDs across variants using coordination rows and retain original traces;
small synthetic samples cannot establish statistical significance.

`citation-review.json` labels synthetic incident traces and no human annotation.
It includes report root claims, causal chains, rejected hypotheses, unresolved claims
and support IDs. Cited excerpts and source paths are copied only from matching
incident records in actual TOOL_CALL results, without opening those paths. Missing
citations are listed explicitly. Every bundle remains `awaiting_human`; no supported
or unsupported annotation or semantic support rate is fabricated. Mock outputs are
offline checks, not real-provider quality evidence.
