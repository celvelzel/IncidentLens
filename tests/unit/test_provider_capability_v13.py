import pytest
from pydantic import ValidationError

from incident_lens.llm.capabilities import ProviderCapabilityProfile


@pytest.mark.parametrize("mode", ["json_schema", "json_object"])
@pytest.mark.parametrize("source", ["explicit_config", "validated_probe"])
def test_explicit_profiles(mode, source):
    profile = ProviderCapabilityProfile(response_format=mode, capability_source=source)
    assert profile.response_format == mode
    assert not profile.supports_output_cap
    assert profile.supports_retry_after
    assert profile.capability_source == source
    assert ProviderCapabilityProfile.model_validate_json(profile.model_dump_json()) == profile


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"response_format": "json_schema"},
        {"capability_source": "explicit_config"},
        {"response_format": "auto", "capability_source": "explicit_config"},
        {"response_format": "json_object", "capability_source": "guessed"},
        {
            "response_format": "json_schema",
            "capability_source": "explicit_config",
            "fallback": True,
        },
        {
            "response_format": "json_schema",
            "capability_source": "explicit_config",
            "supports_output_cap": "true",
        },
        {
            "response_format": "json_schema",
            "capability_source": "explicit_config",
            "supports_retry_after": 1,
        },
    ],
)
def test_invalid_profile_never_falls_back(fields):
    with pytest.raises(ValidationError):
        ProviderCapabilityProfile(**fields)


def test_profile_is_immutable():
    profile = ProviderCapabilityProfile(
        response_format="json_schema", capability_source="explicit_config"
    )
    with pytest.raises(ValidationError):
        profile.response_format = "json_object"


def test_capabilities_can_be_explicitly_disabled():
    profile = ProviderCapabilityProfile(
        response_format="json_object",
        capability_source="validated_probe",
        supports_output_cap=True,
        supports_retry_after=False,
    )
    assert profile.supports_output_cap
    assert not profile.supports_retry_after
