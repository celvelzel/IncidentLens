# Independent WP-E QA review

Reviewer: independent read-only ma_reviewer, gpt-6.1-sol high. P0 contracts approved before A/B/C writers. Runtime and offline evaluation approved after fixes; no remaining High/Critical finding in reviewed scope.

| Finding | Severity | Reproduction/evidence | Disposition |
|---|---|---|---|
| Scheduled retries/repairs counted before admission | High | exhausted next guard; monitoring final permit | Fixed: counts at dispatch only; production regression tests |
| Nonfinite local request serialization charged a request | High | temperature NaN, transport POST=0, budget=1 | Fixed: finite configuration plus request build before admission; zero-dispatch regression |
| Pilot rejected explicitly recovered task failure | High | MODEL_RECOVERED followed by normal termination | Fixed: technical_completion delegates to existing termination normalization; real recovered fixture |
| Direct API capability ignored | Medium | enabled json_object config sent default schema | Fixed: optional format sentinel; explicit argument has precedence |
| R2/R3 repair flag missing config fingerprint | Medium | identical model_parameters with distinct repair prompts | Fixed: flag and capability profile added |
| Repair transport retry counted as second correction | Medium | invalid -> 503 -> 200 | Fixed: F31/F32; 107 reliability tests, 110/110 matrix |
| Mock advertised physical HTTP requests | Medium | Measured MockProvider | Fixed: new HTTP field 0, legacy llm_requests retained |
| Live manifest incomplete at startup | Medium | active pilot manifest | Supplemented with POST_LAUNCH_WORKTREE_OBSERVATION timing/limitation; future script records hashes before investigations. This pilot is descriptive, not a fully frozen causal comparison. |

Independent verification: production adapter tests 18 passed before final Mock-metric assertion; reliability tests 107 passed; integrated composition matrix 110/110. Reviewer did not run UI, full suite or real Provider. Final full regression, installation and real outcomes are Lead acceptance evidence.

No prompt/body/API-key export or evidence/schema bypass was found. Historical results remained untouched. Identity binding, hard unknown-token caps and live targeted-repair efficacy remain outside the demonstrated result.

Final independent audit: production runtime 24 passed; full JUnit parsed as 633 passed, 2 skipped, zero failure/error; release matrix 110/110. Reviewer independently reconciled all six pilot traces: R0/R3 physical requests 16/9, repairs 3/2, technical completion 0/3 each, known token lower bounds 59,899/21,376. No High/Critical remained. Original pilot CSV remains preserved; corrected legacy repair totals live in the separate reconciliation directory. Later Lead safe-summary/explicit-invalid-format regression additions are covered by the final frozen full-suite report in V1.3 acceptance.
