"""Pure structured-output validation; provider content never enters diagnostics."""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

Model = TypeVar("Model", bound=BaseModel)


def output_messages(system_prompt, user_payload, schema):
    """One wire prompt for HTTP and development bridge calls alike."""
    from incident_lens.llm.provider import json_payload

    return [
        {"role": "system", "content": system_prompt
         + "\nReturn a NEW output object, not the input state. The required output JSON Schema is:\n"
         + json.dumps(schema)},
        {"role": "user", "content": json.dumps(json_payload(user_payload))},
    ]


_SUMMARIES = {
    "INVALID_RESPONSE_ENVELOPE": "Response envelope is invalid or has no string content.",
    "INVALID_JSON": "Response content is not valid JSON.",
    "SCHEMA_VALIDATION_FAILED": "Response JSON does not match the required schema.",
    "RESPONSE_TRUNCATED": "Response output is incomplete.",
    "DOMAIN_VALIDATION_FAILED": "Response failed runtime domain validation.",
}
_SAFE_TYPES = frozenset(
    "missing extra_forbidden string_type int_type int_parsing float_type float_parsing "
    "bool_type bool_parsing list_type dict_type model_type literal_error enum "
    "string_too_long string_too_short too_long too_short greater_than greater_than_equal "
    "less_than less_than_equal datetime_type datetime_parsing datetime_from_date_parsing "
    "date_type date_parsing finite_number value_error assertion_error".split()
)


def strict_schema(output_model: type[Model]) -> dict:
    """Return the model schema with every declared property marked required.

    Providers that enforce OpenAI-style ``strict`` JSON Schema only emit keys listed in
    ``required``. Pydantic omits fields that carry defaults, so the model silently drops
    them and cross-field validators reject the otherwise-valid object. Listing every
    property keeps optional semantics expressible through explicit ``null``/``[]`` values.
    """
    schema = output_model.model_json_schema()
    _require_all_properties(schema)
    return schema


def _require_all_properties(node):
    """Recursively require every object property, following Pydantic's schema shapes."""
    if not isinstance(node, dict):
        return node
    properties = node.get("properties")
    if isinstance(properties, dict) and properties:
        node["required"] = list(properties)
    for key in ("properties", "$defs", "definitions"):
        child = node.get(key)
        if isinstance(child, dict):
            for value in child.values():
                _require_all_properties(value)
    for key in ("items", "additionalProperties", "not"):
        child = node.get(key)
        if isinstance(child, dict):
            _require_all_properties(child)
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        child = node.get(key)
        if isinstance(child, list):
            for value in child:
                _require_all_properties(value)
    return node


class StructuredOutputError(ValueError):
    """A safe category and summary, independent of untrusted error text."""

    def __init__(self, category, summary=None):
        # Caller-supplied summaries may contain input or provider exception text.
        self.category = category if category in _SUMMARIES else "INVALID_RESPONSE_ENVELOPE"
        self.phase = {
            "INVALID_RESPONSE_ENVELOPE": "envelope",
            "INVALID_JSON": "syntax",
            "SCHEMA_VALIDATION_FAILED": "schema",
            "RESPONSE_TRUNCATED": "syntax",
            "DOMAIN_VALIDATION_FAILED": "domain",
        }[self.category]
        self.summary = _SUMMARIES[self.category]
        self.repairable = self.category in {
            "INVALID_JSON",
            "SCHEMA_VALIDATION_FAILED",
            "RESPONSE_TRUNCATED",
        }
        super().__init__(self.summary)


def _schema_paths(loc, schema):
    """Follow only schema-owned properties; dictionary keys and union tags are hidden."""
    root = schema
    parts = []
    for item in loc:
        while "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/"):
                return ".".join(parts) or "$"
            schema = root
            for key in ref[2:].split("/"):
                schema = schema.get(key.replace("~1", "/").replace("~0", "~"), {})
        if isinstance(item, int) and "items" in schema:
            parts.append("[]")
            schema = schema["items"]
        elif isinstance(item, str) and item in schema.get("properties", {}):
            parts.append(item)
            schema = schema["properties"][item]
        else:
            break
    return ".".join(parts) or "$"


def validate_response(data, output_model: type[Model]) -> Model:
    """Validate the first chat-completion choice, without changing business facts."""
    if not isinstance(data, dict):
        raise StructuredOutputError("INVALID_RESPONSE_ENVELOPE")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise StructuredOutputError("INVALID_RESPONSE_ENVELOPE")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise StructuredOutputError("INVALID_RESPONSE_ENVELOPE")
    if choice.get("finish_reason") == "length":
        raise StructuredOutputError("RESPONSE_TRUNCATED")
    content = message["content"]
    try:
        # Reject nonstandard NaN/Infinity constants, as required by JSON syntax.
        json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except json.JSONDecodeError as exc:
        truncated = bool(content.strip()) and (
            exc.pos >= len(content.rstrip()) or exc.msg.startswith("Unterminated string")
        )
        category = "RESPONSE_TRUNCATED" if truncated else "INVALID_JSON"
        error = StructuredOutputError(category)
        # Only recognize protocol shape at the start of non-JSON content. Never
        # echo tool names, arguments or arbitrary model text into diagnostics.
        if re.match(r"<[｜|]+DSML[｜|]+", content.lstrip()):
            error.summary += " Output shape: tool_call_markup."
            error.args = (error.summary,)
            error.tool_call_markup = True
        raise error from None
    except (ValueError, RecursionError):
        raise StructuredOutputError("INVALID_JSON") from None
    try:
        return output_model.model_validate_json(content)
    except ValidationError as exc:
        error = StructuredOutputError("SCHEMA_VALIDATION_FAILED")
        schema = output_model.model_json_schema()
        details = []
        for issue in exc.errors(include_url=False, include_context=False, include_input=False)[:8]:
            kind = issue["type"] if issue["type"] in _SAFE_TYPES else "validation_error"
            details.append(f"{_schema_paths(issue['loc'], schema)}: {kind}")
        if details:
            error.summary += " " + "; ".join(details)
            error.args = (error.summary,)
        raise error from None


def repair_message(error: StructuredOutputError) -> str:
    """Produce bounded corrective instructions with safe validation diagnostics."""
    if not error.repairable:
        return "Output repair is unavailable for this failure."
    message = (
        "Return a new JSON object matching the supplied JSON Schema. "
        "One repair only. " + error.summary
    )
    if getattr(error, "tool_call_markup", False):
        message += (
            " The previous response emitted tool-call markup instead of JSON. "
            "No callable tools are registered for this structured response. "
            "Do not invoke tools or emit DSML, XML or tool_calls. "
            "Express planned or follow-up work only through JSON fields allowed by the schema; "
            "during analysis, use requested_checks for future tasks."
        )
    return message
