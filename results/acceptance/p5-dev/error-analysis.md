# Evaluation error analysis

Split: dev; actual provider: mock.
Mock results are offline smoke checks, not real-model accuracy evidence.

Caching was forced off. Identifiable accuracy, unidentifiable abstention and misleading identifiable accuracy use separate denominators.
Citation validity measures reference existence in current shared evidence; semantic claim support is unreviewed.
Unknown token and USD cost values are blank. No tariff or real-model cost was invented.

| Variant | Runs | Correct / identifiable | Correct abstention / unidentifiable |
| --- | ---: | ---: | ---: |
| single | 10 | 9 / 9 | 1 / 1 |
| fixed | 10 | 4 / 9 | 1 / 1 |
| dynamic_no_verifier | 10 | 9 / 9 | 1 / 1 |
| full | 10 | 9 / 9 | 1 / 1 |

## Cases requiring review

- incident_008 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_009 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_013 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_014 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_016 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
