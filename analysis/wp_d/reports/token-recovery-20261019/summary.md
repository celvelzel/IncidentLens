# WP-D artifact snapshot

- Development-visible exploratory pilot; no formal accuracy claim.
- T6/T5 pre-gates waived by user; strict G1a remains unclosed.
- Candidates require evaluator/manual evidence review; no oracle read.
- Missing artifacts do not establish whether a process is alive.
- Unknown usage is not zero; extra attempts stay separate unless explicitly excluded.
- Measured tokens survive incomplete calls; partial totals are lower bounds, not full usage or estimated cost.
- With final-selection.json, legacy by_variant_original_attempts contains selected cells; use selection_basis and by_variant_selected_attempts.

| Attempt | Case | Architecture | Classification | HTTP | Total tokens | Measured tokens (lower bound if incomplete) | Complete |
|---|---|---|---|---|---|---|---|
| run-01-incident_1002-full | incident_1002 | full | diagnosis_candidate | 22 | unknown | 167009 | False |
| run-02-incident_1002-dynamic_no_verifier | incident_1002 | dynamic_no_verifier | diagnosis_candidate | 24 | unknown | 113225 | False |
| run-03-incident_1001-fixed | incident_1001 | fixed | diagnosis_candidate | 14 | unknown | 66811 | False |
| run-04-incident_1003-full-postfix-01 | incident_1003 | full | runtime_failure | 39 | unknown | 364998 | False |
| run-05-incident_1001-dynamic_no_verifier-retry-02 | incident_1001 | dynamic_no_verifier | normal_abstention_candidate | 39 | unknown | 660845 | False |
| run-06-incident_1002-single | incident_1002 | single | diagnosis_candidate | 15 | unknown | 132192 | False |
| run-07-incident_1003-fixed | incident_1003 | fixed | normal_abstention_candidate | 7 | 38632 | 38632 | True |
| run-08-incident_1001-full-postfix-01 | incident_1001 | full | runtime_failure | 22 | unknown | 221073 | False |
| run-09-incident_1002-fixed | incident_1002 | fixed | normal_abstention_candidate | 13 | unknown | 74985 | False |
| run-10-incident_1003-dynamic_no_verifier | incident_1003 | dynamic_no_verifier | normal_abstention_candidate | 26 | unknown | 220543 | False |
| run-11-incident_1001-single-postfix-01 | incident_1001 | single | runtime_failure | 5 | unknown | 7219 | False |
| run-12-incident_1003-single-postfix-01 | incident_1003 | single | runtime_failure | 1 | unknown | 0 | False |
