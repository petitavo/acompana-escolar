from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, AwareDatetime, StrictInt, model_validator, field_validator
from zoneinfo import ZoneInfo
from .schemas import Strict, DeviceInfo


class Setup(Strict):
    name: str = Field(min_length=3, max_length=160)
    timezone: str = "America/Lima"

    @field_validator("timezone")
    @classmethod
    def zone(cls, v):
        ZoneInfo(v)
        return v


class Resource(Strict):
    title: str = Field(min_length=3, max_length=150)
    contact: str = Field(min_length=3, max_length=200)
    verified_by: str = Field(min_length=3, max_length=120)
    verified_at: AwareDatetime


class SchoolZone(Strict):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    radius_m: int = Field(default=150, ge=50, le=1000)


class Settings(Strict):
    document_version: str = Field(default="participacion-v1", min_length=3, max_length=40)
    participation_document: str = Field(min_length=30, max_length=12000)
    purpose: str = Field(min_length=10, max_length=1000)
    primary_id: UUID | None = None
    backup_id: UUID | None = None
    coverage: str = Field(min_length=5, max_length=1000)
    days: list[int] = Field(default=[0, 1, 2, 3, 4], min_length=1, max_length=7)
    opens: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closes: str = Field(default="17:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    acknowledgement_minutes: int = Field(default=1440, ge=5, le=10080)
    safety_minutes: int = Field(default=60, ge=5, le=1440)
    escalation_minutes: int = Field(default=60, ge=5, le=1440)
    resources: list[Resource] = Field(default_factory=list, max_length=12)
    instrument_enabled: bool = False
    professional_decision: str = Field(default="", max_length=3000)
    cadence_days: int = Field(default=14, ge=14, le=90)
    minimum_group: int = Field(default=10, ge=5, le=100)
    external_notifications_authorized: bool = False
    raw_location_retention_days: int = Field(default=7, ge=1, le=7)
    location_interval_minutes: int = Field(default=15, ge=5, le=120)
    location_distance_meters: int = Field(default=100, ge=20, le=1000)
    phq2_weekly_enabled: bool = False
    daily_social_enabled: bool = False
    context_questions_enabled: bool = False
    behavior_change_alerts: bool = False
    school_zone: SchoolZone | None = None
    school_days: list[int] = Field(default=[0, 1, 2, 3, 4], min_length=1, max_length=7)
    school_start: str = Field(default="07:30", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    school_end: str = Field(default="13:30", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def valid(self):
        if any(d not in range(7) for d in self.school_days) or self.school_start >= self.school_end:
            raise ValueError("Horario escolar inválido")
        if any(d not in range(7) for d in self.days) or self.opens >= self.closes:
            raise ValueError("Horario diurno inválido")
        if self.instrument_enabled and (not self.primary_id or not self.backup_id or self.primary_id == self.backup_id or not self.resources or len(self.professional_decision.strip()) < 10):
            raise ValueError("Para habilitar PHQ-9 registre responsable, suplente, recursos verificados y decisión profesional")
        return self


class Account(Strict):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.@-]{3,100}$")
    password: str = Field(min_length=12, max_length=200)
    role: Literal["psychologist", "practitioner", "director", "researcher", "admin"]
    supervisor_id: UUID | None = None
    scopes: list[Literal["diagnostics", "raw_location", "models", "raw_export"]] = Field(default_factory=list)


class ClassroomInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    grade: str = Field(min_length=1, max_length=50)
    period: str = Field(min_length=1, max_length=40)


class StudentInput(Strict):
    display_name: str = Field(min_length=2, max_length=160)
    classroom_id: UUID
    psychologist_id: UUID
    minor: bool = True
    is_test: bool = True
    guardian_channel: str = Field(default="", max_length=160)


class CsvInput(Strict):
    csv: str = Field(min_length=1, max_length=100000)
    classroom_id: UUID
    psychologist_id: UUID
    is_test: bool = True


class VerifyEnrollment(Strict):
    invitation: str = Field(min_length=16, max_length=200)
    verification_code: str = Field(min_length=6, max_length=30)
    device: DeviceInfo


class GuardianApproval(Strict):
    token: str = Field(min_length=16, max_length=200)
    verification_code: str = Field(min_length=6, max_length=30)
    full_name: str = Field(min_length=3, max_length=160)
    relationship: str = Field(min_length=3, max_length=100)
    identity_reference: str = Field(min_length=3, max_length=120)
    document_version: str = Field(max_length=40)
    accepted: bool


class ParticipationInput(Strict):
    action: Literal["assent", "consent", "pause", "resume", "withdraw", "preferences"]
    document_version: str = Field(max_length=40)
    occurred_at: AwareDatetime
    usage: bool = False
    location: bool = False
    steps: bool = False
    raw_location_upload: bool = False
    research_access: bool = False
    reminder_time: str = Field(default="17:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    reminders: bool = True


class SchoolAnswer(Strict):
    instrument_code: Literal["PHQ9_ES_AETC_2016"]
    instrument_version: Literal["AETC-2016-es-2"]
    answers: dict[str, StrictInt]
    functioning: int | None = Field(default=None, ge=0, le=3)
    applied_at: AwareDatetime
    recall_start: AwareDatetime
    recall_end: AwareDatetime


class FollowupInput(Strict):
    case_id: UUID
    kind: Literal["task", "appointment"]
    title: str = Field(min_length=3, max_length=200)
    due_at: AwareDatetime
    location: str = Field(default="", max_length=200)


class FollowupUpdate(Strict):
    state: Literal["pending", "confirmed", "completed", "cancelled"]
    version: int = Field(ge=1)
    contact_confirmed: bool = False
    outcome: str = Field(default="", max_length=1000)


class CalendarInput(Strict):
    classroom_id: UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    kind: Literal["exam", "vacation", "school", "schedule"]
    start_at: AwareDatetime
    end_at: AwareDatetime

    @model_validator(mode="after")
    def bounds(self):
        if self.end_at <= self.start_at or (self.end_at - self.start_at).days > 366:
            raise ValueError("Período inválido")
        return self


class SensorInput(Strict):
    segment_id: str | None = Field(default=None, max_length=40)
    id: UUID
    kind: Literal["location", "steps"]
    occurred_at: AwareDatetime
    timezone: str
    utc_offset_minutes: int = Field(ge=-840, le=840)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    age_ms: int = Field(default=0, ge=0, le=86400000)
    provider: str = Field(max_length=40)
    permission: Literal["precise", "approximate", "activity"]
    mock: bool | None = None
    counter: int | None = Field(default=None, ge=0, le=1000000000)
    boot_id: str | None = Field(default=None, max_length=100)
    battery: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_sensor(self):
        ZoneInfo(self.timezone)
        if self.kind == "location" and (self.latitude is None or self.longitude is None or self.accuracy_m is None or self.permission == "activity"):
            raise ValueError("Ubicación incompleta")
        if self.kind == "steps" and (self.counter is None or not self.boot_id or self.permission != "activity" or self.latitude is not None or self.longitude is not None):
            raise ValueError("Lectura de pasos inválida")
        return self


class SensorBatch(Strict):
    points: list[SensorInput] = Field(min_length=1, max_length=500)


class HomeZone(Strict):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(ge=0, le=100, allow_inf_nan=False)
    radius_m: int = Field(default=150, ge=100, le=500)
    voluntary: Literal[True]


class PushRegistration(Strict):
    token: str = Field(min_length=20, max_length=4096)


class ModelDecision(Strict):
    state: Literal["shadow", "active", "retired"]
    rationale: str = Field(min_length=15, max_length=3000)


class DatasetBuildSpec(Strict):
    name: str = Field(min_length=3, max_length=160)
    task: Literal["concurrent", "prospective"]
    purpose: Literal["clinical", "research"] = "clinical"
    features: list[Literal[
        "interactive_minutes", "night_interactive_minutes", "interactive_session_count",
        "keyguard_hidden_count", "observed_distance_m", "radius_gyration_m",
        "home_minutes", "place_entropy", "observed_steps", "school_minutes",
        "sleep_duration_min", "sleep_onset_min", "wake_min",
    ]] = Field(min_length=1, max_length=13)
    authorization_reference: str = Field(min_length=10, max_length=400)
    include_test: bool = False
    from_day: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_day: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def order(self):
        if self.from_day and self.to_day and self.from_day > self.to_day:
            raise ValueError("Rango de fechas inválido")
        if len(set(self.features)) != len(self.features):
            raise ValueError("Variables repetidas")
        return self


class TrainingScheduleInput(Strict):
    enabled: bool = True
    cadence_days: int = Field(ge=7, le=90)
    auto_retrain: bool = True
    spec: DatasetBuildSpec


class ReportPeriod(Strict):
    start: AwareDatetime
    end: AwareDatetime


class PasswordReset(Strict):
    password: str = Field(min_length=12, max_length=200)
