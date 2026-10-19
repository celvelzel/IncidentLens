"""Structured provider boundary. Exceptions never include request or response data."""

import asyncio
import math
import time
from abc import ABC, abstractmethod
from contextvars import ContextVar
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from incident_lens.llm.usage import begin_request, record_usage

HTTP_CALL_CONTEXT = ContextVar("incident_lens_http_call", default=None)


class ProviderError(RuntimeError):
    """Sanitized provider failure with measured usage where available."""

    def __init__(self, code, usage=None, failure=None):
        super().__init__(code)
        self.code = code
        self.usage = usage or {}
        self.failure = failure
        if failure is not None:
            self.usage["failure"] = failure.model_dump(mode="json")


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
        response_format_mode=None,
        thinking=None,
        recovery=None,
        clock=time.monotonic,
        sleeper=asyncio.sleep,
        rng=None,
        targeted_structured_repair=True,
    ):
        if not all(isinstance(value, str) and value for value in (endpoint, api_key, model)):
            raise ProviderError("PROVIDER_CONFIGURATION_REQUIRED")
        try:
            url = httpx.URL(endpoint)
        except httpx.InvalidURL:
            raise ValueError("Endpoint must be an absolute HTTP(S) URL") from None
        if url.scheme not in ("http", "https") or not url.host:
            raise ValueError("Endpoint must be an absolute HTTP(S) URL")
        if type(structured_repair_retries) is not int or structured_repair_retries not in (0, 1):
            raise ValueError("structured_repair_retries must be zero or one")
        from incident_lens.orchestration.recovery import RecoveryConfig

        self.recovery = (
            recovery
            if isinstance(recovery, RecoveryConfig)
            else RecoveryConfig.model_validate(recovery or {})
        )
        if response_format_mode is None:
            response_format_mode = (
                self.recovery.format_capability if self.recovery.enabled else "json_schema"
            )
        if response_format_mode not in ("json_schema", "json_object"):
            raise ValueError("Unsupported response format")
        if thinking not in (None, "enabled", "disabled"):
            raise ValueError("Unsupported thinking setting")
        if type(temperature) not in (int, float) or not math.isfinite(temperature):
            raise ValueError("Temperature must be finite")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Request timeout must be positive and finite")
        self.endpoint = endpoint.rstrip("/")
        # The campus-only endpoint is unreachable via system proxy env vars; other endpoints keep them.
        self._trust_env = httpx.URL(endpoint).host != "genai.comp.polyu.edu.hk"
        self._api_key = api_key
        self.model_id = model
        self.temperature = temperature
        self.timeout = timeout
        self._client = client
        self.structured_repair_retries = structured_repair_retries
        from incident_lens.llm.capabilities import ProviderCapabilityProfile

        self.capability_profile = ProviderCapabilityProfile(
            response_format=response_format_mode, capability_source="explicit_config"
        )
        self.response_format_mode = response_format_mode
        self.thinking = thinking
        self.clock = clock
        self.sleeper = sleeper
        import random

        self.rng = rng or random.Random(0)
        self.targeted_structured_repair = targeted_structured_repair
        self.recovery_snapshot = None
        self.stop_guard = None
        self.event_observer = None
        self.request_reconciler = None

    @property
    def model_parameters(self):
        return {
            "temperature": self.temperature,
            "response_format": self.response_format_mode,
            "thinking": self.thinking,
            "structured_repair_retries": self.structured_repair_retries,
            "request_timeout_seconds": self.timeout,
            "provider_recovery": self.recovery.model_dump(mode="json"),
            "targeted_structured_repair": self.targeted_structured_repair,
            "capability_profile": self.capability_profile.model_dump(mode="json"),
        }

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        if self.recovery.enabled:
            return await self._reliable_call(role, system_prompt, user_payload, output_model)
        return await self._legacy_call(role, system_prompt, user_payload, output_model)

    async def _legacy_call(self, role, system_prompt, user_payload, output_model):
        from incident_lens.llm.structured_output import output_messages, strict_schema

        started = time.monotonic()
        usage = dict(
            source="model",
            model_id=self.model_id,
            llm_calls=0,
            actual_http_requests=0,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            measured_total_tokens=0,
            tokens_complete=True,
            provider_recovery_enabled=False,
        )
        schema = strict_schema(output_model)
        messages = output_messages(system_prompt, user_payload, schema)
        body = dict(
            model=self.model_id,
            temperature=self.temperature,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        if self.response_format_mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        if self.thinking is not None:
            body["thinking"] = {"type": self.thinking}
        client = self._client or httpx.AsyncClient(timeout=self.timeout, trust_env=self._trust_env)
        request_pending = False
        permit = None
        reconciler = self.request_reconciler
        try:
            for attempt in range(self.structured_repair_retries + 1):
                if self.request_guard is not None:
                    try:
                        permit = self.request_guard()
                    except RuntimeError:
                        raise ProviderError("REQUEST_BUDGET_EXCEEDED", usage) from None
                usage["llm_calls"] += 1
                usage["actual_http_requests"] += 1
                begin_request(usage)
                request_pending = True
                attempt_started = self.clock()
                try:
                    response = await asyncio.wait_for(client.post(
                        self.endpoint
                        if self.endpoint.endswith("/chat/completions")
                        else self.endpoint + "/chat/completions",
                        json=body,
                        headers={"Authorization": "Bearer " + self._api_key},
                        timeout=self.timeout,
                    ), timeout=self.timeout)
                except (httpx.TimeoutException, TimeoutError) as exc:
                    from incident_lens.llm.errors import classify_transport

                    info = classify_transport(
                        exc if isinstance(exc, httpx.TimeoutException) else httpx.ReadTimeout("deadline"),
                        elapsed_ms=(self.clock() - attempt_started) * 1000,
                        http_attempt_index=usage["llm_calls"],
                    )
                    raise ProviderError("PROVIDER_TIMEOUT", usage, info) from None
                except asyncio.CancelledError as exc:
                    exc.usage = usage
                    raise
                except httpx.HTTPError as exc:
                    from incident_lens.llm.errors import classify_transport

                    info = classify_transport(exc, elapsed_ms=(self.clock() - attempt_started) * 1000,
                                              http_attempt_index=usage["llm_calls"])
                    raise ProviderError("PROVIDER_TRANSPORT_ERROR", usage, info) from None
                if response.status_code >= 400:
                    from incident_lens.llm.errors import classify_http

                    try:
                        envelope = response.json()
                    except ValueError:
                        envelope = None
                    envelope = envelope if isinstance(envelope, dict) else {}
                    total = record_usage(usage, envelope.get("usage"))
                    if total is not None and self.token_observer is not None:
                        self.token_observer(total)
                    if reconciler is not None:
                        reconciler(permit, total)
                    request_pending = False
                    error = envelope.get("error")
                    code = error.get("code") if isinstance(error, dict) else None
                    info = classify_http(response.status_code, response.headers, code,
                                         elapsed_ms=(self.clock() - attempt_started) * 1000,
                                         http_attempt_index=usage["llm_calls"],
                                         usage_complete=usage["tokens_complete"])
                    raise ProviderError(info.legacy_code, usage, info)
                try:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ValueError("Invalid response envelope")
                    token_usage = data.get("usage") or {}
                    if not isinstance(token_usage, dict):
                        raise ValueError("Invalid usage envelope")
                    total = record_usage(usage, token_usage)
                    if total is not None and self.token_observer is not None:
                        self.token_observer(total)
                    if reconciler is not None:
                        reconciler(permit, total if type(total) is int and total >= 0 else None)
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
                        if reconciler is not None:
                            reconciler(permit, None)
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
                if reconciler is not None:
                    reconciler(permit, None)
                usage["tokens_complete"] = False
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    usage[key] = None
            usage["elapsed_ms"] = (time.monotonic() - started) * 1000
            if self._client is None:
                await client.aclose()

    async def _reliable_call(self, role, system_prompt, user_payload, output_model):
        from incident_lens.llm.errors import FailureInfo, classify_http, classify_transport
        from incident_lens.llm.structured_output import (
            StructuredOutputError,
            output_messages,
            repair_message,
            strict_schema,
            validate_response,
        )
        from incident_lens.llm.transport_retry import compute_backoff
        from incident_lens.orchestration.recovery import BudgetSnapshot, decide_http_retry

        started = self.clock()
        logical_id = "logical-" + uuid4().hex
        # Capture callbacks once, never reread mutable provider attributes mid-call.
        guard, observer = self.request_guard, self.token_observer
        stop, snapshot, emit = self.stop_guard, self.recovery_snapshot, self.event_observer
        reconciler = self.request_reconciler
        config = self.recovery.model_copy(deep=True)
        usage = dict(
            source="model",
            model_id=self.model_id,
            llm_calls=0,
            actual_http_requests=0,
            logical_structured_calls=1,
            logical_call_id=logical_id,
            transport_retries=0,
            repair_requests=0,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            measured_total_tokens=0,
            tokens_complete=True,
            provider_recovery_enabled=True,
            provider_attempts=[],
        )
        schema = strict_schema(output_model)
        messages = output_messages(system_prompt, user_payload, schema)
        body = dict(model=self.model_id, temperature=self.temperature, messages=messages)
        body["response_format"] = (
            {"type": "json_object"}
            if self.response_format_mode == "json_object"
            else {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            }
        )
        if self.thinking is not None:
            body["thinking"] = {"type": self.thinking}
        client = self._client or httpx.AsyncClient(timeout=self.timeout, trust_env=self._trust_env)
        retries = repairs = 0
        pending = False
        permit = None
        next_kind = None

        def event(kind, **details):
            safe = dict(
                logical_call_id=logical_id, http_attempt_index=usage["llm_calls"], **details
            )
            usage["provider_attempts"].append(dict(event_type=kind, **safe))
            if emit is not None:
                emit(kind, role=role, **safe)

        def mark_unknown():
            # begin_request already recorded an unknown physical attempt. Keep
            # earlier measurements, even if a later request never responds.
            from incident_lens.llm.usage import refresh_usage

            refresh_usage(usage)

        def budget_snapshot():
            return (
                snapshot()
                if snapshot is not None
                else BudgetSnapshot(
                    remaining_request_permits=config.max_physical_attempts_per_call
                    - usage["llm_calls"],
                    remaining_wall_seconds=max(
                        0.0,
                        self.timeout * config.max_physical_attempts_per_call
                        - (self.clock() - started),
                    ),
                )
            )

        def failure_error(info):
            usage["failure"] = info.model_dump(mode="json")
            return ProviderError(info.legacy_code, usage, info)

        context_token = HTTP_CALL_CONTEXT.set(logical_id)
        try:
            while True:
                if stop is not None:
                    stop()
                if usage["llm_calls"] >= config.max_physical_attempts_per_call:
                    info = FailureInfo(
                        category="REQUEST_BUDGET_EXHAUSTED",
                        legacy_code="REQUEST_BUDGET_EXCEEDED",
                        retryable=False,
                        phase="budget",
                        logical_call_id=logical_id,
                        http_attempt_index=usage["llm_calls"],
                        elapsed_ms=(self.clock() - started) * 1000,
                        usage_complete=usage["tokens_complete"],
                    )
                    event("BUDGET_RETRY_DENIED", category=info.category)
                    raise failure_error(info)
                # Serialize/build before admission: local bad payloads cost no HTTP permit.
                try:
                    if client.is_closed:
                        raise ValueError("Closed client")
                    request = client.build_request(
                        "POST",
                        self.endpoint
                        if self.endpoint.endswith("/chat/completions")
                        else self.endpoint + "/chat/completions",
                        json=body,
                        headers={"Authorization": "Bearer " + self._api_key},
                        timeout=min(
                            self.timeout, max(0.001, budget_snapshot().remaining_wall_seconds)
                        ),
                    )
                except (ValueError, TypeError, httpx.InvalidURL):
                    info = FailureInfo(
                        category="INVALID_REQUEST",
                        legacy_code="PROVIDER_INVALID_REQUEST",
                        retryable=False,
                        phase="transport",
                        logical_call_id=logical_id,
                        http_attempt_index=usage["llm_calls"],
                        usage_complete=True,
                    )
                    raise failure_error(info) from None
                if guard is not None:
                    try:
                        permit = guard()
                    except RuntimeError as exc:
                        reason = str(exc)
                        category = (
                            "TOKEN_BUDGET_EXHAUSTED"
                            if "token" in reason.lower()
                            else "WALL_BUDGET_EXHAUSTED"
                            if "wall" in reason.lower()
                            else "REQUEST_BUDGET_EXHAUSTED"
                        )
                        info = FailureInfo(
                            category=category,
                            legacy_code="REQUEST_BUDGET_EXCEEDED",
                            retryable=False,
                            phase="budget",
                            logical_call_id=logical_id,
                            http_attempt_index=usage["llm_calls"],
                            elapsed_ms=(self.clock() - started) * 1000,
                            usage_complete=usage["tokens_complete"],
                        )
                        event("BUDGET_RETRY_DENIED", category=info.category)
                        raise failure_error(info) from None
                usage["llm_calls"] += 1
                usage["actual_http_requests"] += 1
                begin_request(usage)
                if next_kind == "retry":
                    retries += 1
                    usage["transport_retries"] = retries
                elif next_kind == "repair":
                    repairs += 1
                    usage["repair_requests"] = repairs
                next_kind = None
                pending = True
                event(
                    "PROVIDER_ATTEMPT",
                    http_attempt_id=f"{logical_id}-{usage['llm_calls']}",
                    repair_index=repairs,
                )
                info = None
                response = None
                attempt_started = self.clock()
                context = dict(
                    logical_call_id=logical_id,
                    http_attempt_index=usage["llm_calls"],
                    elapsed_ms=(self.clock() - started) * 1000,
                    usage_complete=False,
                )
                try:
                    response = await asyncio.wait_for(
                        client.send(request), timeout=min(
                            self.timeout, max(0.001, budget_snapshot().remaining_wall_seconds)
                        ),
                    )
                except asyncio.CancelledError as exc:
                    mark_unknown()
                    if reconciler is not None:
                        reconciler(permit, None)
                    pending = False
                    event("PROVIDER_FAILURE_CLASSIFIED", category="CANCELLED")
                    # Preserve native cancellation, while wrappers/budget can retain usage.
                    exc.usage = usage
                    raise
                except (httpx.HTTPError, TimeoutError) as exc:
                    if isinstance(exc, TimeoutError):
                        exc = httpx.ReadTimeout("Request deadline exceeded")
                    context["elapsed_ms"] = (self.clock() - attempt_started) * 1000
                    info = classify_transport(exc, **context)
                if info is None and response.status_code >= 400:
                    code = None
                    envelope = None
                    try:
                        envelope = response.json()
                        error = envelope.get("error") if isinstance(envelope, dict) else None
                        code = error.get("code") if isinstance(error, dict) else None
                    except ValueError:
                        pass
                    context["elapsed_ms"] = (self.clock() - attempt_started) * 1000
                    info = classify_http(response.status_code, response.headers, code, **context)
                if info is not None:
                    reported = envelope.get("usage") if response is not None and isinstance(envelope, dict) else None
                    total = record_usage(usage, reported)
                    if total is not None and observer is not None:
                        observer(total)
                    info = info.model_copy(update={"usage_complete": usage["tokens_complete"]})
                    if reconciler is not None:
                        reconciler(permit, total)
                    pending = False
                    event(
                        "PROVIDER_FAILURE_CLASSIFIED",
                        **info.model_dump(
                            mode="json", exclude={"logical_call_id", "http_attempt_index"}
                        ),
                    )
                    current = budget_snapshot()
                    decision = decide_http_retry(
                        info,
                        current,
                        False,
                        config,
                        transport_retry_count=retries,
                        physical_attempt_count=usage["llm_calls"],
                    )
                    # Retry-After must be considered before approving deadline feasibility.
                    delay = compute_backoff(retries, info.retry_after_seconds, config, self.rng)
                    if (
                        decision.action != "RETRY_HTTP"
                        or delay + config.min_request_time_seconds > current.remaining_wall_seconds
                    ):
                        event(
                            "BUDGET_RETRY_DENIED" if info.retryable else "PROVIDER_RETRY_DENIED",
                            reason=decision.reason,
                        )
                        raise failure_error(info)
                    event("PROVIDER_RETRY_SCHEDULED", delay_seconds=delay, category=info.category)
                    await self.sleeper(delay)
                    if stop is not None:
                        stop()
                    next_kind = "retry"
                    continue
                try:
                    data = response.json()
                except ValueError:
                    data = None
                token_data = data.get("usage") if isinstance(data, dict) else None
                token_data = token_data if isinstance(token_data, dict) else {}
                total = record_usage(usage, token_data)
                if total is not None and observer is not None:
                    observer(total)
                if reconciler is not None:
                    reconciler(permit, total if type(total) is int and total >= 0 else None)
                pending = False
                try:
                    result = validate_response(data, output_model)
                except StructuredOutputError as exc:
                    phase = "schema" if exc.category == "SCHEMA_VALIDATION_FAILED" else "syntax"
                    info = FailureInfo(
                        category=(
                            "UNKNOWN_PROVIDER_ERROR"
                            if exc.category == "INVALID_RESPONSE_ENVELOPE"
                            else exc.category
                        ),
                        legacy_code="STRUCTURED_OUTPUT_INVALID",
                        retryable=False,
                        phase=phase,
                        logical_call_id=logical_id,
                        http_attempt_index=usage["llm_calls"],
                        elapsed_ms=(self.clock() - started) * 1000,
                        usage_complete=usage["tokens_complete"],
                    )
                    event(
                        "PROVIDER_FAILURE_CLASSIFIED",
                        category=info.category,
                        phase=phase,
                        validation_summary=exc.summary,
                        output_model=output_model.__name__,
                    )
                    current = budget_snapshot()
                    if (
                        not exc.repairable
                        or repairs
                        >= min(config.max_structured_repairs, self.structured_repair_retries)
                        or usage["llm_calls"] >= config.max_physical_attempts_per_call
                        or current.remaining_request_permits <= config.reserve_verifier_requests
                        or (current.stage_remaining is not None and current.stage_remaining <= 0)
                        or current.remaining_wall_seconds < config.min_request_time_seconds
                        or (current.remaining_tokens is not None and current.remaining_tokens <= 0)
                    ):
                        raise failure_error(info) from None
                    if stop is not None:
                        stop()
                    next_kind = "repair"
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                repair_message(exc)
                                if self.targeted_structured_repair
                                else "Return valid JSON matching the supplied schema. One repair only."
                            ),
                        }
                    )
                    event("STRUCTURED_REPAIR", repair_index=repairs + 1)
                    continue
                if stop is not None:
                    stop()
                event("PROVIDER_CALL_COMPLETED", usage_complete=usage["tokens_complete"])
                return result, usage
        except asyncio.CancelledError as exc:
            exc.usage = usage
            raise
        finally:
            if pending:
                mark_unknown()
                if reconciler is not None:
                    reconciler(permit, None)
            usage["elapsed_ms"] = (self.clock() - started) * 1000
            HTTP_CALL_CONTEXT.reset(context_token)
            if self._client is None:
                await client.aclose()
