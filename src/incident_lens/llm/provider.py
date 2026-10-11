"""Structured provider boundary. Exceptions never include request or response data."""

import json
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
    def __init__(self, endpoint, api_key, model, temperature=0.0, timeout=30.0, client=None):
        if not endpoint or not api_key or not model:
            raise ProviderError("PROVIDER_CONFIGURATION_REQUIRED")
        self.endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self.model_id = model
        self.temperature = temperature
        self.timeout = timeout
        self._client = client

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        started = time.monotonic()
        usage = dict(
            source="model",
            model_id=self.model_id,
            llm_calls=0,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
        )
        messages = [
            {"role": "system", "content": system_prompt},
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
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        unknown_tokens = set()
        try:
            for attempt in range(2):
                if self.request_guard is not None:
                    self.request_guard()
                usage["llm_calls"] += 1
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
                except httpx.HTTPError:
                    raise ProviderError("PROVIDER_TRANSPORT_ERROR", usage) from None
                if response.status_code in (400, 404, 422):
                    raise ProviderError("STRUCTURED_OUTPUT_COMPATIBILITY_ERROR", usage)
                if response.status_code >= 400:
                    raise ProviderError("PROVIDER_HTTP_ERROR", usage)
                try:
                    data = response.json()
                    token_usage = data.get("usage") or {}
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        n = token_usage.get(key)
                        if key in unknown_tokens:
                            continue
                        if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                            usage[key] = (usage[key] or 0) + n
                        else:
                            usage[key] = None
                            unknown_tokens.add(key)
                    content = data["choices"][0]["message"]["content"]
                    result = output_model.model_validate_json(content)
                    usage["elapsed_ms"] = (time.monotonic() - started) * 1000
                    return result, usage
                except (ValueError, KeyError, IndexError, TypeError, ValidationError):
                    if attempt:
                        raise ProviderError("STRUCTURED_OUTPUT_INVALID", usage) from None
                    messages.append(
                        {
                            "role": "user",
                            "content": "Return valid JSON matching the supplied schema. One repair only.",
                        }
                    )
        finally:
            usage["elapsed_ms"] = (time.monotonic() - started) * 1000
            if self._client is None:
                await client.aclose()
