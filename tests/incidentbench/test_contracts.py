import pytest
from pydantic import ValidationError

from incident_lens.incidentbench.schemas import ExperimentProtocol


def test_protocol_rejects_cache_and_fake_formal():
    for patch in ({"cache_mode": "read_write"}, {"formal": True}, {"variants": ["full"]}):
        with pytest.raises(ValidationError):
            ExperimentProtocol(**patch)


def test_protocol_roundtrip():
    protocol = ExperimentProtocol()
    assert ExperimentProtocol.model_validate_json(protocol.model_dump_json()) == protocol
