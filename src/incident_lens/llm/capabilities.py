"""Explicit provider capabilities; constructing a profile performs no network I/O."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProviderCapabilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    response_format: Literal["json_schema", "json_object"]
    supports_output_cap: bool = False
    supports_retry_after: bool = True
    capability_source: Literal["explicit_config", "validated_probe"]
