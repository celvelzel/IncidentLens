from types import SimpleNamespace

from incident_lens.orchestration.report import observed_chain, render_report
from incident_lens.schemas import Hypothesis, RCAReport


def test_report_uses_observations_instead_of_unverified_predictions():
    from datetime import datetime, timezone

    from incident_lens.schemas import EvidenceRecord

    record = EvidenceRecord(
        evidence_id="E1", incident_id="incident_001", source_type="metrics", service="backend",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), source_path="public/metrics.jsonl",
        excerpt="pool_waiters=118", metadata={},
    )
    hypothesis = Hypothesis(hypothesis_id="H1", culprit_service="backend", failure_mode="pool",
                            support_ids=["E1"], status="SUPPORTED",
                            predicted_observations=["UNOBSERVED latency rises"])
    chain = observed_chain(SimpleNamespace(evidence_index={"E1": record}), hypothesis)
    assert "pool_waiters=118" in chain[0] and "[E1]" in chain[0]
    assert "UNOBSERVED" not in str(chain)
    report = RCAReport(run_id="run1", incident_id="incident_001", status="RESOLVED",
                       root_cause=hypothesis, causal_chain=chain,
                       supporting_evidence_ids=["E1"], stop_reason="accepted")
    rendered = render_report(report)
    confirmed, predictions = rendered.split("## Predictions (not confirmed observations)")
    assert "UNOBSERVED" not in confirmed
    assert "UNOBSERVED latency rises" in predictions
