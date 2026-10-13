# Annotation guide

All generated labels and claim exports remain pending. No reviewer or independent acceptance is implied by a candidate rationale. Human semantic metrics remain null until authentic records exist.

Each truth review must preserve reviewer_id (anonymous identity), incident_id, source="human", reviewed_at, rationale and labels containing the complete causal oracle fields except reviewer_ids, annotator_status, review_version. Two distinct raw records must independently agree with final labels. Disagreement requires a third independent human adjudication record with labels and rationale. Mere reviewer_ids never suffice for formal sealing. Provenance fields permit audit; software cannot verify that a person actually authored a record.

Citation records contain claim_id, reviewer_id, review_label, rationale, source="human", reviewed_at. Allowed labels: SUPPORTED, CONTRADICTED, INSUFFICIENT, NOT_APPLICABLE. Two independent agreeing records complete a claim; conflicts stay pending until independent adjudication. Keep both original reviews. Unknown and unreviewed are null. Coverage counts unique claims, never duplicate rows. Exported bundles omit variant/model/run identifiers; claim text may still reveal stylistic architecture cues, so strict blindness is not guaranteed.
