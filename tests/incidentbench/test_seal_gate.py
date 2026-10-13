import json

import pytest

from incident_lens.incidentbench.manifest import seal_dataset
from incident_lens.incidentbench.schemas import ExperimentProtocol


def test_seed_only_cannot_be_formally_sealed_even_with_readiness(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "public_case_index.json").write_text(
        json.dumps([{"incident_id": "incident_1001", "split": "seed", "cohort": "core"}])
    )
    monkeypatch.setattr(
        "incident_lens.incidentbench.validator.validate_dataset", lambda *a: {"ok": True}
    )
    protocol = ExperimentProtocol(
        formal=True,
        provider_id="real",
        model_id="frozen-model",
        blindness_level="independent_label_owner",
    )
    with pytest.raises(ValueError, match="nonempty Frozen Test"):
        seal_dataset(
            dataset,
            protocol,
            tmp_path / "oracle",
            tmp_path / "salt",
            {"provider_compatible": True, "independent_label_owner": True},
        )
    assert not (tmp_path / "salt").exists()
