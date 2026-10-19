# WP-D artifact snapshot

- Development-visible exploratory pilot; no formal accuracy claim.
- T6/T5 pre-gates waived by user; strict G1a remains unclosed.
- Candidates require evaluator/manual evidence review; no oracle read.
- Missing artifacts do not establish whether a process is alive.
- Unknown usage is not zero; extra attempts stay separate unless explicitly excluded.
- With final-selection.json, legacy by_variant_original_attempts contains selected cells; use selection_basis and by_variant_selected_attempts.

| Attempt | Case | Architecture | Classification | HTTP | Tokens |
|---|---|---|---|---|---|
| run-01-incident_1002-full | incident_1002 | full | diagnosis_candidate | 22 | unknown |
| run-02-incident_1002-dynamic_no_verifier | incident_1002 | dynamic_no_verifier | diagnosis_candidate | 24 | unknown |
| run-03-incident_1001-fixed | incident_1001 | fixed | diagnosis_candidate | 14 | unknown |
| run-04-incident_1003-full | incident_1003 | full | runtime_failure | 12 | unknown |
| run-05-incident_1001-dynamic_no_verifier-retry-02 | incident_1001 | dynamic_no_verifier | normal_abstention_candidate | 39 | unknown |
| run-06-incident_1002-single | incident_1002 | single | diagnosis_candidate | 15 | unknown |
| run-07-incident_1003-fixed | incident_1003 | fixed | normal_abstention_candidate | 7 | 38632 |
| run-08-incident_1001-full | incident_1001 | full | runtime_failure | 5 | unknown |
| run-09-incident_1002-fixed | incident_1002 | fixed | normal_abstention_candidate | 13 | unknown |
| run-10-incident_1003-dynamic_no_verifier | incident_1003 | dynamic_no_verifier | normal_abstention_candidate | 26 | unknown |
| run-11-incident_1001-single | incident_1001 | single | runtime_failure | 17 | unknown |
| run-12-incident_1003-single | incident_1003 | single | runtime_failure | 21 | unknown |
