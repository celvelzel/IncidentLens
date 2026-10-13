"""Structured provider boundary. Exceptions never include request or response data."""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, ValidationError


class ProviderError(RuntimeError):
    """Sanitized provider failure with measured usage where available."""

    def __init__(self, code, usage=None):
        super().__init__(code)
        self.code = code
        self.usage = usage or {}


class LLMProvider(ABC):
    model_id = "unknown"
    temperature = 0.0
    request_guard = None
    token_observer = None

    @abstractmethod
    async def structured_call(self, role, system_prompt, user_payload, output_model):
        """Return a validated model and measured usage metadata."""


def json_payload(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: json_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_payload(v) for v in value]
    return value


class RealChatProvider(LLMProvider):
    def __init__(
        self,
        endpoint,
        api_key,
        model,
        temperature=0.0,
        timeout=180.0,
        client=None,
        structured_repair_retries=1,
        response_format_mode="json_schema",
        thinking=None,
    ):
        if not endpoint or not api_key or not model:
            raise ProviderError("PROVIDER_CONFIGURATION_REQUIRED")
        if type(structured_repair_retries) is not int or structured_repair_retries not in (0, 1):
            raise ValueError("structured_repair_retries must be zero or one")
        if response_format_mode not in ("json_schema", "json_object"):
            raise ValueError("Unsupported response format")
        if thinking not in (None, "enabled", "disabled"):
            raise ValueError("Unsupported thinking setting")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Request timeout must be positive and finite")
        self.endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self.model_id = model
        self.temperature = temperature
        self.timeout = timeout
        self._client = client
        self.structured_repair_retries = structured_repair_retries
        self.response_format_mode = response_format_mode
        self.thinking = thinking

    @property
    def model_parameters(self):
        return {
            "temperature": self.temperature,
            "response_format": self.response_format_mode,
            "thinking": self.thinking,
            "structured_repair_retries": self.structured_repair_retries,
            "request_timeout_seconds": self.timeout,
        }

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        started = time.monotonic()
        usage = dict(
            source="model",
            model_id=self.model_id,
            llm_calls=0,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            measured_total_tokens=0,
            tokens_complete=True,
        )
        messages = [
            {
                "role": "system",
                "content": system_prompt + "\nReturn a NEW output object, not the input state. "
                "The required output JSON Schema is:\n"
                + json.dumps(output_model.model_json_schema()),
            },
            {"role": "user", "content": json.dumps(json_payload(user_payload))},
        ]
        body = dict(
            model=self.model_id,
            temperature=self.temperature,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "strict": True,
                    "schema": output_model.model_json_schema(),
                },
            },
        )
        if self.response_format_mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        if self.thinking is not None:
            body["thinking"] = {"type": self.thinking}
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        unknown_tokens = set()
        request_pending = False
        try:
            for attempt in range(self.structured_repair_retries + 1):
                if self.request_guard is not None:
                    try:
                        self.request_guard()
                    except RuntimeError:
                        raise ProviderError("REQUEST_BUDGET_EXCEEDED", usage) from None
                usage["llm_calls"] += 1
                request_pending = True
                try:
                    response = await client.post(
                        self.endpoint
                        if self.endpoint.endswith("/chat/completions")
                        else self.endpoint + "/chat/completions",
                        json=body,
                        headers={"Authorization": "Bearer " + self._api_key},
                        timeout=self.timeout,
                    )
                except httpx.TimeoutException:
                    raise ProviderError("PROVIDER_TIMEOUT", usage) from None
                except asyncio.CancelledError:
                    raise ProviderError("PROVIDER_CANCELLED", usage) from None
                except httpx.HTTPError:
                    raise ProviderError("PROVIDER_TRANSPORT_ERROR", usage) from None
                if response.status_code in (400, 404, 422):
                    raise ProviderError("STRUCTURED_OUTPUT_COMPATIBILITY_ERROR", usage)
                if response.status_code >= 400:
                    raise ProviderError("PROVIDER_HTTP_ERROR", usage)
                try:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ValueError("Invalid response envelope")
                    token_usage = data.get("usage") or {}
                    if not isinstance(token_usage, dict):
                        raise ValueError("Invalid usage envelope")
                    total = token_usage.get("total_tokens")
                    if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
                        usage["measured_total_tokens"] += total
                        if self.token_observer is not None:
                            self.token_observer(total)
                    else:
                        usage["tokens_complete"] = False
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        n = token_usage.get(key)
                        if key in unknown_tokens:
                            continue
                        if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                            usage[key] = (usage[key] or 0) + n
                        else:
                            usage[key] = None
                            unknown_tokens.add(key)
                    request_pending = False
                    content = data["choices"][0]["message"]["content"]
                    result = output_model.model_validate_json(content)
                    usage["elapsed_ms"] = (time.monotonic() - started) * 1000
                    return result, usage
                except (ValueError, KeyError, IndexError, TypeError, ValidationError):
                    if request_pending:
                        usage["tokens_complete"] = False
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                            usage[key] = None
                            unknown_tokens.add(key)
                        request_pending = False
                    if attempt >= self.structured_repair_retries:
                        raise ProviderError("STRUCTURED_OUTPUT_INVALID", usage) from None
                    messages.append(
                        {
                            "role": "user",
                            "content": "Return valid JSON matching the supplied schema. One repair only.",
                        }
                    )
        finally:
            if request_pending:
                usage["tokens_complete"] = False
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    usage[key] = None
            usage["elapsed_ms"] = (time.monotonic() - started) * 1000
            if self._client is None:
                await client.aclose()
