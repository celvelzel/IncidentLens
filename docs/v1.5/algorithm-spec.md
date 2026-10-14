# CAES v1: implemented algorithm

Status: engineering implementation; empirical improvement is unestablished. Authority:
`../plans/IncidentLens_V1.5_CodingAgent_Implementation_Plan.md`. Implementation reviewed
at `1c95339`; defaults are development starting values, not fitted research parameters.

CAES prioritizes investigation tasks after Coordinator INVESTIGATE. FINALIZE and ABSTAIN
retain their existing authority. Default `current_dynamic` bypasses CAES. Shadow records
recommendations while executing Coordinator tasks. Enabled policies materialize at most
two selected tasks through runtime identity, TaskManager, ACL, budget and STOP checks.
Merge, Verifier and FinalizeGate continue to decide evidence acceptance and root cause.

Candidate generation is deterministic and makes no model/tool call. Sources are
Coordinator proposals, published Verifier checks and public role templates. Canonical
signatures include the evidence snapshot; changed windows/snapshots permit new checks.
Duplicate requests take source precedence. Legal Coordinator proposals, legal requests,
then templates precede invalid candidates before the default six-candidate cap. Templates
round-robin legal roles across public services. Overflow is not an assessed candidate:
inspect saved `coordinator_proposed_tasks` and `visible.requested_checks` when auditing
truncation. Overflow has no individual assessment/rejection record. Filters are planning
hints; actual tool arguments still pass existing tool schema validation. No provider handle,
private Oracle, family, split or answer label enters the visible projection.

| Feature | Exact current rule | Interpretation |
| --- | --- | --- |
| D | Fraction of pairs of non-rejected published hypotheses whose prediction token sets differ and whose contrast and both predictions overlap the candidate question/discriminator | Lexical expected discriminative value; no pairs means 0 |
| U | 1 for an exact published requested check; otherwise maximum question-token coverage over visible open questions | Predicted gap coverage |
| G | 0 for an already represented role source, .5 for a missing source, 1 for missing source plus published grounding errors | Potential source contribution, never gate sufficiency |
| R | 1 for an identical completed signature on the same snapshot, otherwise 0 | Exact repetition; static eligibility also rejects duplicates |
| C | `2 * physical_request_multiplier` requests and 2 planned tool invocations | Conservative fixed fallback; tokens and latency are null |

Tokenization lowercases `[a-z0-9]+` and removes a small generic stop-word set;
negation tokens remain. Main's subsequent permutation-symmetry fix requires both
predictions to overlap beyond public service names. This lexical heuristic can miss paraphrases
and overvalue superficial differences. It is neither calibrated information gain nor
a probability of a successful investigation. Lead's subsequent d51fbfc refinement feeds
existing pure `finalize_errors` into the published grounding gap list used by G; this
evaluates current gaps and never authorizes finalize. G is independent of D but can correlate
with it in real tasks. C is not a measured cost or a charged permit.

`V = .40 D + .30 U + .30 G - .30 R`; B4 score is
`V / (.01 + 1.0 * estimated_requests + .25 * estimated_tools)`.
B2 uses denominator 1; B3 sets D weight to zero. Stable score ties normally use candidate ID.
At cold start (no non-rejected published hypotheses), equal scores use the conservative
Logs, Metrics, Database, Changes role order, then prefer a Coordinator proposal within
the same role, then candidate ID. This cee3987 correction keeps D at zero and prevents
an ID hash from preferring an uninformative empty-Board investigation. It is a public
role prior, not Dev calibration or an Oracle-derived ranking. The earlier batch and
its four Verifier BAD_ARGS failures remain retained separately.
B1c preserves generator order. Positive score above `min_score=0` is required for
scored policies. Selection traverses the fixed ranked order; it does not rerank after
each selection. Same-role/same-filter token Jaccard overlap applies a .15 penalty;
overlap >= .95 excludes a second task, with opposite negation sets treated as distinct.
Each task and their aggregate must fit requests/tools plus Verifier reserve. The
adapter converts the physical Recovery reserve to logical calls with ceiling division
before taking max with the policy reserve, avoiding a second retry multiplication.
This can conservatively reserve up to multiplier-minus-one extra physical permits.
Unknown latency is not fabricated; runtime deadline remains authoritative.

Uniform fallback costs mean B2 and B4 can coincide. Synthetic tests with injected
`dev_aggregate` estimates prove cost-sensitive control flow, not empirical calibration.
Zero selected tasks yield `NO_USEFUL_ACTION` and safe ABSTAIN rather than an empty loop.

Saved `CANDIDATES_GENERATED` and `ACTION_SELECTED` events expose public state, candidates,
ACL, budget, config and selection. `coordinator_proposed_tasks` and
`selector_executed_tasks` distinguish proposals, shadow recommendations and execution.
Assessments distinguish rejected candidates from eligible candidates left unselected;
an eligible unselected task is not necessarily an ACL rejection. Offline replay verifies
saved selection without model/tool calls; observed evidence and final reports remain
separate from these predicted scores. See `fairness-protocol.md` for executable commands.
