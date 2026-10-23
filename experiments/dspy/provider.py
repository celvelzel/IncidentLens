"""Explicit request caps for all offline calls, including optimizer proposals."""

import copy
from threading import Lock

from incident_lens.llm import MockProvider, RealChatProvider


class RequestCap:
    def __init__(self, maximum):
        if type(maximum) is not int or maximum < 1:
            raise ValueError("positive request limit required")
        self.maximum = maximum
        self.used = 0
        self.lock = Lock()

    def __call__(self):
        with self.lock:
            if self.used >= self.maximum:
                raise RuntimeError("offline request cap exhausted")
            self.used += 1


class RequestCappedMixin:
    async def structured_call(self, role, system_prompt, user_payload, output_model):
        delegate = copy.copy(self)
        inherited = self.request_guard

        def guarded():
            self._experiment_cap()
            return inherited() if inherited is not None else None

        delegate.request_guard = guarded
        return await super(RequestCappedMixin, delegate).structured_call(
            role, system_prompt, user_payload, output_model)


class CappedMockProvider(RequestCappedMixin, MockProvider):
    async def structured_call(self, role, system_prompt, user_payload, output_model):
        if role != "offline_optimizer":
            return await super().structured_call(role, system_prompt, user_payload, output_model)
        self._experiment_cap()
        if self.request_guard is not None:
            self.request_guard()
        # A deterministic proposal fixture verifies MIPRO orchestration only.
        # It cannot search for or demonstrate better natural-language instructions.
        if any(field.annotation is not str for field in output_model.model_fields.values()):
            raise ValueError("mock optimizer only supports string proposal fields")
        result = output_model.model_validate({
            key: "Use observed evidence; preserve unresolved alternatives and uncertainty."
            for key in output_model.model_fields})
        return result, {"source": "mock", "llm_calls": 1, "total_tokens": None,
                        "engineering_only": True}



class CappedRealProvider(RequestCappedMixin, RealChatProvider):
    pass


def make_provider(kind, cap, *, model=None):
    import os

    if kind == "mock":
        provider = CappedMockProvider()
    elif kind == "real":
        provider = CappedRealProvider(
            endpoint=os.environ.get("INCIDENT_LENS_DSPY_ENDPOINT", ""),
            api_key=os.environ.get("INCIDENT_LENS_DSPY_API_KEY", ""),
            model=model or os.environ.get("INCIDENT_LENS_DSPY_MODEL", ""),
            timeout=120, temperature=0,
        )
    else:
        raise ValueError("unknown provider")
    provider._experiment_cap = cap
    return provider
