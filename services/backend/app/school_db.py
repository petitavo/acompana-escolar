"""Additive school product tables. Historical DEMO/LAB records remain untouched."""
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base, Row


class Institution(Row, Base):
    __tablename__ = "school_institutions"
    name: Mapped[str] = mapped_column(String(160))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class Classroom(Row, Base):
    __tablename__ = "school_classrooms"
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("institution_id", "name", "period"),)


class Membership(Row, Base):
    __tablename__ = "school_memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"), index=True)
    supervisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StudentProfile(Row, Base):
    __tablename__ = "school_students"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), unique=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"), index=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey("school_classrooms.id"))
    display_name: Mapped[str] = mapped_column(String(160))
    minor: Mapped[bool] = mapped_column(Boolean, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)


class Authorization(Row, Base):
    __tablename__ = "school_authorizations"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class AccessLink(Row, Base):
    __tablename__ = "school_access_links"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Followup(Row, Base):
    __tablename__ = "school_followups"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(Row, Base):
    __tablename__ = "school_notifications"
    recipient_id: Mapped[str] = mapped_column(String(36), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="created")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseGrant(Row, Base):
    """A03: scoped, time-boxed, auditable access to a single escalated case for the
    configured backup psychologist. Never a general assignment to other students."""
    __tablename__ = "school_case_grants"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(40), default="escalation")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("case_id", "user_id", "reason"),)


class PushToken(Row, Base):
    __tablename__ = "school_push_tokens"
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token: Mapped[str] = mapped_column(Text)


class SchoolEvent(Row, Base):
    __tablename__ = "school_calendar"
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"), index=True)
    classroom_id: Mapped[str | None] = mapped_column(ForeignKey("school_classrooms.id"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SensorPoint(Row, Base):
    __tablename__ = "school_sensor_points"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    signature: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON)


class MobilityDay(Row, Base):
    __tablename__ = "school_mobility_days"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    day: Mapped[str] = mapped_column(String(10))
    version: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)


class TrainingSchedule(Row, Base):
    """A05/A06: controlled cadence for dataset construction + optional retraining.
    Retraining only ever produces a `registered` model — never an auto-promotion."""
    __tablename__ = "school_training_schedules"
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cadence_days: Mapped[int] = mapped_column(Integer, default=14)
    auto_retrain: Mapped[bool] = mapped_column(Boolean, default=True)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str] = mapped_column(String(36))


class DatasetRecord(Row, Base):
    __tablename__ = "school_datasets"
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(160))
    manifest: Mapped[dict] = mapped_column(JSON)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))


class ModelRecord(Row, Base):
    __tablename__ = "school_models"
    institution_id: Mapped[str] = mapped_column(ForeignKey("school_institutions.id"))
    dataset_id: Mapped[str] = mapped_column(ForeignKey("school_datasets.id"))
    state: Mapped[str] = mapped_column(String(20), default="registered")
    manifest: Mapped[dict] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    artifact: Mapped[str] = mapped_column(Text)
    decisions: Mapped[list] = mapped_column(JSON, default=list)


class Prediction(Row, Base):
    __tablename__ = "school_predictions"
    model_id: Mapped[str] = mapped_column(ForeignKey("school_models.id"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    cutoff: Mapped[str] = mapped_column(String(10))
    detail: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("model_id", "participant_id", "cutoff"),)


class CheckIn(Row, Base):
    """Cuestionarios breves del piloto (PHQ-2 semanal, pregunta diaria de contacto social,
    preguntas de contexto). Tabla separada para no mezclarlos con las etiquetas PHQ-9."""
    __tablename__ = "school_checkins"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[dict] = mapped_column(JSON)
