from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from incident_lens.schemas import Identifier, StrictModel
from incident_lens.schemas.contracts import timezone_required


class TimeWindow(StrictModel):
    start_ts: datetime
    end_ts: datetime

    @field_validator("start_ts", "end_ts", mode="before")
    @classmethod
    def parse_time(cls, value):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timezone_required(value) if isinstance(value, datetime) else value

    @model_validator(mode="after")
    def ordered_window(self):
        if self.start_ts > self.end_ts:
            raise ValueError("start_ts must not exceed end_ts")
        return self


class LogsArgs(TimeWindow):
    service: Identifier
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"] | None = None
    contains: str | None = Field(default=None, max_length=1024)
    limit: int = Field(default=50, ge=1, le=50)


class MetricsArgs(TimeWindow):
    service: Identifier
    metric_names: list[Identifier] = Field(max_length=50)


class DependenciesArgs(StrictModel):
    service: Identifier | None = None


class ChangesArgs(StrictModel):
    service: Identifier | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    change_type: Literal["deployment", "config", "maintenance", "scaling"] | None = None

    @field_validator("start_ts", "end_ts", mode="before")
    @classmethod
    def parse_time(cls, value):
        return TimeWindow.parse_time(value) if value is not None else None

    @model_validator(mode="after")
    def ordered_window(self):
        if self.start_ts and self.end_ts and self.start_ts > self.end_ts:
            raise ValueError("start_ts must not exceed end_ts")
        return self


class ConfigDiffArgs(StrictModel):
    change_id: Identifier


class FetchArgs(StrictModel):
    ids: list[Identifier] = Field(min_length=1, max_length=50)


class DatabaseArgs(TimeWindow):
    service: Identifier = "postgres"
    limit: int = Field(default=50, ge=1, le=50)


ARGUMENT_MODELS = {
    **{
        name: DatabaseArgs
        for name in (
            "get_db_connections",
            "get_db_active_sessions",
            "get_db_lock_waits",
            "get_db_slow_queries",
            "get_db_health_metrics",
        )
    },
    "query_logs": LogsArgs,
    "query_metrics": MetricsArgs,
    "get_dependencies": DependenciesArgs,
    "query_changes": ChangesArgs,
    "get_config_diff": ConfigDiffArgs,
    "fetch_evidence_by_ids": FetchArgs,
}
