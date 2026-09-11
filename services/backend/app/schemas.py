from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import (
    StrictInt,
    BaseModel,
    ConfigDict,
    Field,
    AwareDatetime,
    field_validator,
    model_validator,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class DeviceInfo(Strict):
    android_api: int = Field(ge=29, le=100)
    manufacturer: str = Field(max_length=80)
    model: str = Field(max_length=100)
    app_version: str = Field(max_length=40)
    timezone: str = Field(max_length=64)


class Enrollment(Strict):
    invitation: str = Field(min_length=16, max_length=200)
    device: DeviceInfo


class Participation(Strict):
    action: Literal["consent", "pause", "resume", "revoke", "package_policy"]
    occurred_at: AwareDatetime
    consent_version: str = Field(default="lab-v1", max_length=40)
    adult: bool = False
    share_packages: bool = False


class CaptureInput(Strict):
    id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    success: bool
    permission_before: bool
    permission_after: bool
    count: int = Field(ge=0, le=1000000)
    error: Literal["permission_missing", "device_locked", "query_failed", "none"] = (
        "none"
    )
    battery: int | None = Field(default=None, ge=0, le=100)
    charging: bool | None = None
    connected: bool | None = None
    outbox_pending: int = Field(default=0, ge=0)
    monotonic_ms: int | None = Field(default=None, ge=0)
    keyguard_available: bool = True

    @model_validator(mode="after")
    def bounds(self):
        if (
            self.end_at < self.start_at
            or (self.end_at - self.start_at).total_seconds() > 86400
        ):
            raise ValueError("Rango inválido; máximo 24 horas")
        return self


class EventPayload(Strict):
    package: str | None = Field(
        default=None, max_length=200, pattern=r"^[a-zA-Z0-9_.]+$"
    )


class EventInput(Strict):
    schema_version: Literal["1.0"] = "1.0"
    event_id: UUID
    device_id: UUID
    occurred_at: AwareDatetime
    timezone: str
    utc_offset_minutes: int = Field(default=-300, ge=-840, le=840)
    event_type: Literal[
        "SCREEN_INTERACTIVE",
        "SCREEN_NON_INTERACTIVE",
        "KEYGUARD_SHOWN",
        "KEYGUARD_HIDDEN",
        "ACTIVITY_RESUMED",
        "ACTIVITY_PAUSED",
        "DEVICE_SHUTDOWN",
        "DEVICE_STARTUP",
    ]
    source: Literal["android_usage_events", "synthetic_generator"]
    payload: EventPayload = Field(default_factory=EventPayload)
    capture_session_id: UUID
    consent_version: str = Field(default="lab-v1", max_length=40)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Zona desconocida")
        return value


class Batch(Strict):
    events: list[EventInput] = Field(min_length=1, max_length=500)


class AnswerInput(Strict):
    instrument_code: str = Field(max_length=80)
    answers: dict[str, StrictInt]
    applied_at: AwareDatetime
    recall_start: AwareDatetime
    recall_end: AwareDatetime

    @model_validator(mode="after")
    def bounds(self):
        if self.recall_end < self.recall_start or self.applied_at < self.recall_start:
            raise ValueError("Período inválido")
        return self


class ContactInput(Strict):
    requested_at: AwareDatetime


class Transition(Strict):
    state: Literal["new", "acknowledged", "contact_planned", "in_followup", "closed"]
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class Note(Strict):
    text: str = Field(min_length=1, max_length=2000)


class JobInput(Strict):
    seed: int = Field(default=20260906, ge=0, le=2147483647)
    task: Literal["concurrent", "prospective"] = "concurrent"


class ReprocessInput(Strict):
    device_id: UUID
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ExportInput(Strict):
    kind: Literal["raw", "features", "labeled"]
    format: Literal["csv", "jsonl"] = "csv"
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def bounds(self):
        if not 0 < (self.end - self.start).total_seconds() <= 90 * 86400:
            raise ValueError("Período máximo 90 días")
        return self


class Feedback(Strict):
    duration_seconds: int = Field(ge=0, le=86400)
    clarity: int = Field(ge=1, le=5)
    usefulness: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
