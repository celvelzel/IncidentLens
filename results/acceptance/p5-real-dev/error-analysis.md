# Evaluation error analysis

Split: dev; actual provider: real.
These results come from actual configured provider attempts; failed calls remain in the denominator.

Caching was forced off. Identifiable accuracy, unidentifiable abstention and misleading identifiable accuracy use separate denominators.
Citation validity measures reference existence in current shared evidence; semantic claim support is unreviewed.
Unknown token and USD cost values are blank. No tariff or real-model cost was invented.

| Variant | Runs | Correct / identifiable | Correct abstention / unidentifiable |
| --- | ---: | ---: | ---: |
| single | 10 | 0 / 9 | 0 / 1 |
| fixed | 10 | 0 / 9 | 1 / 1 |
| dynamic_no_verifier | 10 | 0 / 9 | 0 / 1 |
| full | 10 | 0 / 9 | 0 / 1 |

## Cases requiring review

- incident_007 / dynamic_no_verifier: INCONCLUSIVE; MERGE_HYPOTHESIS_ID_COLLISION; execution=none, evaluation=none.
- incident_007 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_007 / full: INCONCLUSIVE; REQUEST_BUDGET_EXCEEDED; execution=none, evaluation=none.
- incident_007 / single: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_008 / dynamic_no_verifier: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_008 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_008 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_008 / single: INCONCLUSIVE; REQUEST_BUDGET_EXCEEDED; execution=none, evaluation=none.
- incident_009 / dynamic_no_verifier: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_009 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_009 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_009 / single: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_010 / dynamic_no_verifier: INCONCLUSIVE; LLM or wall-clock budget exhausted; execution=none, evaluation=none.
- incident_010 / fixed: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_010 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_010 / single: INCONCLUSIVE; STRUCTURED_OUTPUT_INVALID; execution=none, evaluation=none.
- incident_011 / dynamic_no_verifier: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_011 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_011 / single: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_012 / dynamic_no_verifier: INCONCLUSIVE; MERGE_HYPOTHESIS_ID_COLLISION; execution=none, evaluation=none.
- incident_012 / fixed: INCONCLUSIVE; UNOBSERVED_CITATION; execution=none, evaluation=none.
- incident_012 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_012 / single: INCONCLUSIVE; STRUCTURED_OUTPUT_INVALID; execution=none, evaluation=none.
- incident_013 / dynamic_no_verifier: INCONCLUSIVE; MERGE_FINDING_ID_COLLISION; execution=none, evaluation=none.
- incident_013 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_013 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_013 / single: INCONCLUSIVE; STRUCTURED_OUTPUT_INVALID; execution=none, evaluation=none.
- incident_014 / dynamic_no_verifier: INCONCLUSIVE; REQUEST_BUDGET_EXCEEDED; execution=none, evaluation=none.
- incident_014 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_014 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_014 / single: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_015 / dynamic_no_verifier: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_015 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_015 / full: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_015 / single: INCONCLUSIVE; PROVIDER_TIMEOUT; execution=none, evaluation=none.
- incident_016 / dynamic_no_verifier: INCONCLUSIVE; MERGE_HYPOTHESIS_ID_COLLISION; execution=none, evaluation=none.
- incident_016 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_016 / full: INCONCLUSIVE; MERGE_HYPOTHESIS_ID_COLLISION; execution=none, evaluation=none.
- incident_016 / single: INCONCLUSIVE; STRUCTURED_OUTPUT_INVALID; execution=none, evaluation=none.
