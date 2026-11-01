# Saved-trace analysis

```powershell
python scripts/analyze_eval.py --input results/acceptance/p5-dev/raw-runs.jsonl --out results/analysis-dev
```

Use a new, separate output folder. Existing output folders are rejected; input
artifacts are preserved. The script executes no graph, provider or tools and reads
no dataset oracle files. Each stored state must have a completed report before its
stored `oracle_scoring_fields` are accessed. Missing scoring oracles preserve known execution
facts and leave answer-quality metrics unknown; no oracle is inferred from runtime output.
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

`errors.jsonl` preserves per-run stop reasons and staged STOP/MODEL_FAILURE events,
plus outer execution/evaluation errors. Normal evidence-based abstentions are not
classified as runtime errors. The source raw traces remain unchanged.

The source design's F1–F5 are deployment/config regression, database connection
exhaustion, Redis unavailability, external payment timeout and backend resource
saturation. Slices preserve exact stored failure-mode values rather than guessing
an F label. Misleading presence separates ordinary/misleading cases; identifiability
separates complete/missing causal evidence. Empty groups are omitted. Compare matched
incident IDs across variants using coordination rows and retain original traces;
small synthetic samples cannot establish statistical significance.

`coverage.json` records observed failure-mode counts and explicit ordinary,
misleading, complete and missing counts, including zero. Counts are runs across
variants, not unique incidents. An all-misleading fixture therefore reports
ordinary = 0; it provides no ordinary-case performance evidence. Unobserved
mechanisms have no invented cases or rates; the mechanism map contains observed
values only. Undefined groups are represented by coverage counts, not fabricated
slice rows.

`followup_examples.json` links each REVIEW to the next INVESTIGATE DECISION,
including event IDs (null if absent in a legacy trace), event indexes, verdict,
requested checks and assignments. A check matches only when full stable task
contents match after removing `task_id`, which may change on assignment. Role,
question, filters and expected discriminator therefore remain part of the match;
no fuzzy semantic interpretation is invented. Unrelated assignments have empty
matched checks; reviews without later investigation remain explicit examples.
Counts mean “matches requested checks” and describe trace correspondence, not
proof that a review caused the next action or improved accuracy.

`citation-review.json` labels synthetic incident traces and no human annotation.
It includes report root claims, causal chains, rejected hypotheses, unresolved claims
and support IDs. Cited excerpts and source paths are copied only from matching
incident records in actual TOOL_CALL results, without opening those paths. Missing
citations are listed explicitly. Every bundle remains `awaiting_human`; no supported
or unsupported annotation or semantic support rate is fabricated. Mock outputs are
offline checks, not real-provider quality evidence.

## Scoring version 2 exports

Analysis recomputes scores from complete, immutable traces through the public classifier. Orderly stop and recovered call failures are not exported as run failures. Business plan failure, invalid protocols and terminal runtime failure remain explicit. Layered success/failure/unknown counts accompany each denominator; manifest.json records scoring_version=2 and the source SHA-256. Historical score rows must be rescored before comparison with new rows.
