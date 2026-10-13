import json
from datetime import datetime
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, field_validator

from incident_lens.llm.structured_output import (
    StructuredOutputError,
    repair_message,
    validate_response,
)


class Nested(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=5)
    status: Literal["ok", "failed"]
    timestamp: datetime
    rows: list[Nested]


def envelope(content, finish_reason="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


def valid():
    return {
        "name": "demo",
        "status": "ok",
        "timestamp": "2026-10-13T12:00:00Z",
        "rows": [{"count": 1}],
    }


def failure(data, category, repairable=True):
    with pytest.raises(StructuredOutputError) as caught:
        validate_response(data, Output)
    assert caught.value.category == category
    assert caught.value.repairable is repairable
    return caught.value


def test_valid_first_choice_and_no_mutation():
    data = envelope(json.dumps(valid()))
    data["choices"].append({"message": {"content": "invalid second choice"}})
    before = json.dumps(data)
    assert validate_response(data, Output).rows[0].count == 1
    assert json.dumps(data) == before


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "secret",
        {},
        {"choices": None},
        {"choices": {}},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{}]},
        {"choices": [{"message": []}]},
        envelope(None),
        envelope({}),
        envelope(42),
    ],
)
def test_invalid_envelopes_cannot_repair(data):
    error = failure(data, "INVALID_RESPONSE_ENVELOPE", False)
    assert repair_message(error) == "Output repair is unavailable for this failure."


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "not JSON",
        "```json\n{}\n```",
        '{"a": NaN}',
        '{"a": Infinity}',
        '{"a": -Infinity}',
        '{"a": nope}',
    ],
)
def test_invalid_json(content):
    failure(envelope(content), "INVALID_JSON")


@pytest.mark.parametrize("content", ["{", "[1,", '{"name": "secret', '{"a": 1'])
def test_truncated_json(content):
    failure(envelope(content), "RESPONSE_TRUNCATED")


@pytest.mark.parametrize("content", [json.dumps(valid()), "invalid"])
def test_explicit_length_never_success(content):
    failure(envelope(content, "length"), "RESPONSE_TRUNCATED")


@pytest.mark.parametrize(
    "changes,path,kind",
    [
        ({"name": None}, "name", "string_type"),
        ({"name": ""}, "name", "string_too_short"),
        ({"name": "secret-secret"}, "name", "string_too_long"),
        ({"status": "secret"}, "status", "literal_error"),
        ({"timestamp": "secret"}, "timestamp", "datetime_from_date_parsing"),
        ({"rows": [{"count": "secret"}]}, "rows.[].count", "int_parsing"),
    ],
)
def test_schema_safe_details(changes, path, kind):
    payload = valid() | changes
    error = failure(envelope(json.dumps(payload)), "SCHEMA_VALIDATION_FAILED")
    assert f"{path}: {kind}" in repair_message(error)
    assert "secret" not in str(error)
    assert "secret" not in repair_message(error)


def test_missing_field_and_extra_property_do_not_leak():
    payload = valid()
    del payload["name"]
    payload["secret-prompt-ignore-schema"] = "secret"
    payload["rows"][0]["secret-nested-property"] = "secret"
    error = failure(envelope(json.dumps(payload)), "SCHEMA_VALIDATION_FAILED")
    assert "name: missing" in error.summary
    assert "extra_forbidden" in error.summary
    assert "secret" not in repair_message(error)


@pytest.mark.parametrize("content", ["null", "[]", "42", '"secret"'])
def test_json_non_object_is_schema_failure(content):
    error = failure(envelope(content), "SCHEMA_VALIDATION_FAILED")
    assert "secret" not in error.summary


def test_custom_validator_error_text_hidden():
    class Custom(BaseModel):
        value: str

        @field_validator("value")
        @classmethod
        def reject(cls, value):
            raise ValueError("secret provider error " + value)

    with pytest.raises(StructuredOutputError) as caught:
        validate_response(envelope('{"value":"secret-input"}'), Custom)
    assert "value: value_error" in caught.value.summary
    assert "secret" not in repair_message(caught.value)


def test_constructor_does_not_echo_untrusted_summary_or_category():
    error = StructuredOutputError("INVALID_JSON", "secret raw content")
    assert "secret" not in str(error)
    unknown = StructuredOutputError("secret category", "secret")
    assert unknown.category == "INVALID_RESPONSE_ENVELOPE"
    assert "secret" not in str(unknown)


def test_domain_failure_is_not_repairable():
    error = StructuredOutputError("DOMAIN_VALIDATION_FAILED", "secret evidence")
    assert not error.repairable
    assert "secret" not in repair_message(error)


def test_schema_validation_preserves_evidence_for_runtime_guard():
    class Proposal(BaseModel):
        evidence_ids: list[str]

    result = validate_response(envelope('{"evidence_ids":["fabricated-id"]}'), Proposal)
    assert result.evidence_ids == ["fabricated-id"]


def test_dictionary_keys_and_union_tags_are_hidden():
    class Container(BaseModel):
        values: dict[str, Nested]
        choice: Nested | int

    with pytest.raises(StructuredOutputError) as caught:
        validate_response(
            envelope(
                json.dumps({"values": {"secret-key": {"count": "secret"}}, "choice": "secret"})
            ),
            Container,
        )
    assert "values: int_parsing" in caught.value.summary
    assert "secret" not in caught.value.summary


def test_diagnostics_are_bounded():
    payload = valid() | {f"secret-{index}": index for index in range(100)}
    error = failure(envelope(json.dumps(payload)), "SCHEMA_VALIDATION_FAILED")
    assert error.summary.count("extra_forbidden") == 8


@pytest.mark.parametrize(
    "category,phase",
    [
        ("INVALID_RESPONSE_ENVELOPE", "envelope"),
        ("INVALID_JSON", "syntax"),
        ("SCHEMA_VALIDATION_FAILED", "schema"),
        ("RESPONSE_TRUNCATED", "syntax"),
        ("DOMAIN_VALIDATION_FAILED", "domain"),
    ],
)
def test_safe_failure_phase(category, phase):
    assert StructuredOutputError(category).phase == phase
