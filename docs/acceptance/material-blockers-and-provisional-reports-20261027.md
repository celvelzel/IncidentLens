# Material blockers and useful inconclusive reports

## Problem and resulting behavior

A supported explanation could be blocked by any OPEN alternative, even when that alternative had only a generic timeout or unanswered question. Inconclusive reports then discarded useful candidate/evidence summaries, displaying little more than “no root cause.”

The finalization gate now checks whether an alternative has an **observed cause-specific mechanism discriminator**, using the same public-evidence discriminator interface as the selected cause. Generic symptoms, unsupported possibilities and unrelated business errors alone do not veto another explanation. Alternatives are retained OPEN; the runtime does not fabricate a rejection or treat absent telemetry as proof of health. A real observed competing mechanism still blocks. Unobserved citations remain an integrity blocker.

Hypotheses now have `optional_questions` in addition to `open_questions`. Optional corroboration is retained and displayed without blocking finalization. Existing `open_questions` remain blocking for compatibility: arbitrary text is not automatically relabeled. Prompts explicitly require a material attribution gap for blocking questions and requested checks, explain optional corroboration, and discourage proving every imaginable alternative false. Existing selected-candidate contradictions, independent sources, mechanism evidence, supported investigations, full verifier acceptance and review snapshot requirements remain in force.

## Reports and scoring

Reports add a deterministic evidence assessment:

- `CONFIRMED`: the investigation accepted a resolved cause.
- `LIKELY`: one leading candidate meets the evidence checks without recorded material blockers, but no final diagnosis was accepted. Report status remains INCONCLUSIVE and root_cause remains null.
- `INSUFFICIENT`: attribution has material gaps, conflicts, insufficient mechanism support, or a runtime failure.

Up to three evidence-backed non-rejected explanations are retained as provisional OPEN hypotheses, ordered by mechanism evidence and independent source support, not calibrated probabilities. No unsupported candidate is invented. Only observed supporting records are copied into provisional observations; predictions are not promoted to facts. Reports retain concrete causal gaps, suggested follow-up checks and separate optional corroboration. Follow-up text cannot dispatch tools or change the investigation state. A likely assessment is not RCA success.

The web report and evidence inspector distinguish provisional citations from accepted diagnosis support. Provisional references receive the same state citation/provenance validation and are included in citation-existence metrics, while root-cause success and termination semantics are unchanged. Legacy saved reports receive default-empty additive fields; companion metadata comparison validates/normalizes both objects before equality, rejecting changed/unknown content while preserving historical replay.

## Validation

Offline regression covers unsupported/question-only and generic-symptom alternatives, background business errors, positive competing mechanisms, real contradictions, optional vs blocking questions, stale reviews, uncertain reports without diagnosis success credit, fabricated provisional citations, no-evidence reports, and legacy companion equality. Existing rival-blocking tests now supply actual positive mechanism evidence rather than relying on an unsupported question.

Frontend tests exercise unconfirmed labels, evidence references, report sections, XSS escaping, and prefix-gated replay. Desktop/mobile rendering is checked with a standalone local HTML report and all page network requests blocked. Example traces/reports are generated with MockProvider only in `results/acceptance/material-blockers-reporting-20261027/final`; these are engineering fixtures, not evidence of improved real-model accuracy.

The broader suite exposed a finish-budget mismatch in the optional active-evidence selector: it could reserve only one finishing call while the graph required both a final decision and a full review. Its effective reservation now matches the graph before selecting tasks, including configured physical retry multipliers. A low-budget regression verifies that an unfundable selection is not published as executable and does not cause a late runtime failure. This does not add request permits or change fixed/global budgets.

No paid investigation was rerun and no historical experiment artifact was modified. Future real comparisons need a fresh batch containing all variants with the new code/prompt snapshot; do not replace only failed or losing prior runs.

Final checks: `INCIDENT_LENS_OFFLINE_TESTS=1 .venv/bin/python -m pytest tests -q` — **1108 passed, 3 skipped**; Node frontend/replay suite — **23 passed**; Ruff and `git diff --check` passed. Browser rendering assertions passed at 1280px and 390px widths with an isolated temporary Chrome profile and page networking blocked.
