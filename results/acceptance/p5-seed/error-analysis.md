# Evaluation error analysis

Split: seed; actual provider: mock.
Mock results are offline smoke checks, not real-model accuracy evidence.

Caching was forced off. Identifiable accuracy, unidentifiable abstention and misleading identifiable accuracy use separate denominators.
Citation validity measures reference existence in current shared evidence; semantic claim support is unreviewed.
Unknown token and USD cost values are blank. No tariff or real-model cost was invented.

| Variant | Runs | Correct / identifiable | Correct abstention / unidentifiable |
| --- | ---: | ---: | ---: |
| single | 6 | 5 / 5 | 1 / 1 |
| fixed | 6 | 2 / 5 | 1 / 1 |
| dynamic_no_verifier | 6 | 5 / 5 | 1 / 1 |
| full | 6 | 5 / 5 | 1 / 1 |

## Cases requiring review

- incident_001 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_003 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
- incident_004 / fixed: INCONCLUSIVE; Fixed schedule completed; execution=none, evaluation=none.
