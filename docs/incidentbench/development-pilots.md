# V1.4 development-pilot evidence

Recorded runs: 2026-10-13 (Asia/Shanghai). This document reports actual development
execution, not formal Frozen Test acceptance. Both pilots used two disclosed Seed
fixtures: an identifiable pool-configuration case and a missing-discriminator case,
renumbered `incident_2001` and `incident_2002`. Candidate labels came from the
development generator and remain provisional.

## Configured DeepSeek API

The configured model identifier was `deepseek-v4-flash-0731`, accessed through the
user-configured API gateway. A measured `json_schema` probe succeeded: one request,
255 tokens, approximately 15 seconds. This establishes simple response compatibility,
not reliable complex Agent outputs or an independently verified upstream model identity.

Two cases × four equivalent-tool Graph conditions produced eight real investigations.
Settings: temperature 0, cache off, jobs 1, one repeat, four rounds, twelve tools,
sixteen model requests, 300-second investigation budget and 180-second request limit.
No Mock substitution occurred.

| Condition | Technical completion | Investigation HTTP requests |
| --- | ---: | ---: |
| Strong single, equivalent tools | 0/2 | 4 |
| Fixed four, equivalent tools | 0/2 | 16 |
| Dynamic without Verifier | 0/2 | 4 |
| Full | 0/2 | 4 |

Three investigations ended with `PROVIDER_TIMEOUT`, five with
`STRUCTURED_OUTPUT_INVALID`. Fixed-four runs reached seven tool calls each before
failure. Failure records did not retain enough field-level diagnostics to establish
the precise structured-output defect.

There were 28 investigation HTTP requests plus the separate probe. Saved model-call
events contain **85,291 known investigation tokens as a lower bound**; only five of
eight investigations have complete usage. Aggregate investigation tokens and cost
remain unknown. The probe's 255 tokens are separate from that lower bound.

All eight saved states were rescored; parsed case-level results matched the originals.
Receipt hashes matched and event-derived HTTP counts agreed with the saved score
counts. All eight attempts failed technically: failed INCONCLUSIVE reports are not
correct evidence-insufficient abstentions. No diagnostic or architecture superiority
claim follows from these results.

## Codex gpt-6-luna / high child model

A single explicitly configured `gpt-6-luna`, high-effort child model, started without
parent conversation history, supplied structured responses over a local file bridge.
The actual investigation Graph ran the same two cases in the single equivalent-tool
condition with the same 300/180 time limits and 4/12/16 round/tool/request limits.
Only role prompts, public state, output schemas and actual tool results were supplied;
private candidate labels were read by the evaluator after states were saved.

| Case | Technical completion | Stop reason | Tools | Admitted calls |
| --- | --- | --- | ---: | ---: |
| incident_2001 | false | TIMEOUT | 4 | 8 |
| incident_2002 | false | TIMEOUT | 3 | 7 |

Both runs exhausted the 300-second total budget. Thirteen consumed responses passed
Schema validation. Two late responses were retained but not consumed. Saved-state
rescoring matched for both cases. Platform token usage, cost, internal HTTP counts and
actual temperature control were unavailable; no DeepSeek request was made by this bridge.

Two Reviews supplied the sentinel target ID `none` when no hypothesis existed.
The Schema accepted the string, although it was not an actual hypothesis ID. This is
a semantic validation gap, not proof that finalization can accept fabricated causes.
The first plan also suggested undiscovered metric names; subsequent tool planning
used an empty name list to discover available metrics.

The child model retained context between calls and cases. File handling and model/tool
round trips counted against elapsed time. Access restrictions were task instructions,
not OS isolation. This is a descriptive bridge pilot, not a fair HTTP-provider comparison.

## Next steps and artifact scope

The [review and bridge improvement plan](../plans/IncidentLens_V1.4_Review_Bridge_Improvement_Plan.md)
sets the next-run total budget to 600 seconds while retaining the 180-second per-response
limit. It covers no-hypothesis routing, target-ID validation before state mutation and
measured bridge lifecycle improvements. Those changes and the 600-second retest have
not been implemented by this documentation update. More total time alone does not
resolve invalid structured responses or prove a remedy for individual request timeouts.

Raw states, receipts and private evaluator material remain local under
`results/incidentbench/v1/20261013-deepseek-development-pilot/` and
`results/incidentbench/v1/20261013-luna-high-subagent-pilot/`. They are not uploaded with
this document. This public summary therefore does not independently reconstruct API
responses. Model-authored scenario designs and user-confirmed model review suggestions
retain model provenance; they do not count as independent human reviews. Formal sealing,
human semantic metrics, independent Test data and production generalization remain pending.
