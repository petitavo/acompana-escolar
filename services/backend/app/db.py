from datetime import datetime, timezone
from sqlalchemy import text as sql_text
from uuid import uuid4
from sqlalchemy import (
    create_engine,
    event,
    String,
    DateTime,
    JSON,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL, MODE
from pathlib import Path

if DATABASE_URL.startswith("sqlite:///"):
    Path(DATABASE_URL[10:]).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_fk(dbapi, _):
        dbapi.execute("PRAGMA foreign_keys=ON")


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def iso(value):
    return value.isoformat() if value else None


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class Base(DeclarativeBase):
    pass


class Row:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    environment: Mapped[str] = mapped_column(String(4), default=MODE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Environment(Base):
    __tablename__ = "environment_guard"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(4))


class User(Row, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(24))
    scopes: Mapped[list] = mapped_column(JSON, default=list)


class Session(Row, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(default=False)


class Participant(Row, Base):
    __tablename__ = "participants"
    pseudonym: Mapped[str] = mapped_column(String(50), unique=True)
    group: Mapped[str] = mapped_column(String(50), default="Laboratorio")
    status: Mapped[str] = mapped_column(String(20), default="active")


class Assignment(Row, Base):
    __tablename__ = "assignments"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    __table_args__ = (UniqueConstraint("user_id", "participant_id"),)


class Device(Row, Base):
    __tablename__ = "devices"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    share_packages: Mapped[bool] = mapped_column(default=False)


class Invitation(Row, Base):
    __tablename__ = "invitations"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(default=False)


class Consent(Row, Base):
    __tablename__ = "consents"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    version: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict] = mapped_column(JSON)


class Interval(Row, Base):
    __tablename__ = "participation_intervals"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Capture(Row, Base):
    __tablename__ = "capture_sessions"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detail: Mapped[dict] = mapped_column(JSON)


class RawEvent(Row, Base):
    __tablename__ = "raw_events"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    capture_session_id: Mapped[str] = mapped_column(ForeignKey("capture_sessions.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    timezone: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40))
    clock_flag: Mapped[bool] = mapped_column(default=False)
    consent_version: Mapped[str] = mapped_column(String(30))


class Instrument(Row, Base):
    __tablename__ = "instrument_definitions"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    definition: Mapped[dict] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=False)


class Response(Row, Base):
    __tablename__ = "questionnaire_responses"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), index=True
    )
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument_definitions.id"))
    detail: Mapped[dict] = mapped_column(JSON)


class Case(Row, Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index(
            "uq_active_case_per_participant",
            "participant_id",
            unique=True,
            sqlite_where=sql_text("state <> 'closed'"),
            postgresql_where=sql_text("state <> 'closed'"),
        ),
    )
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), index=True
    )
    state: Mapped[str] = mapped_column(String(30), default="new", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Reason(Row, Base):
    __tablename__ = "case_reasons"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(default=True)
    detail: Mapped[dict] = mapped_column(JSON)


class CaseEvent(Row, Base):
    __tablename__ = "case_events"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    actor: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)


class Feature(Row, Base):
    __tablename__ = "daily_features"
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    version: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)


class Evaluation(Row, Base):
    __tablename__ = "deviation_evaluations"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), index=True
    )
    cutoff: Mapped[str] = mapped_column(String(10), index=True)
    version: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("participant_id", "cutoff", "version"),)


class AcademicEvent(Row, Base):
    __tablename__ = "academic_events"
    group: Mapped[str] = mapped_column(String(50))
    detail: Mapped[dict] = mapped_column(JSON)


class Job(Row, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class Audit(Row, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(36))


class Idempotency(Row, Base):
    __tablename__ = "idempotency_keys"
    actor: Mapped[str] = mapped_column(String(36))
    key: Mapped[str] = mapped_column(String(120))
    route: Mapped[str] = mapped_column(String(80))
    digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("actor", "key", "route"),)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


SessionLocal = sessionmaker(engine, expire_on_commit=False)

from . import school_db  # Register additive tables with the existing metadata.


def guard(db):
    marker = db.get(Environment, 1)
    if not marker or marker.mode != MODE:
        raise RuntimeError(
            "Base sin inicializar o entorno incompatible; ejecute migraciones"
        )


def initialize():
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        row = db.get(Environment, 1)
        if row and row.mode != MODE:
            raise RuntimeError("Prohibido mezclar DEMO/LAB en una base")
        if not row:
            db.add(Environment(id=1, mode=MODE))


def public(row):
    return {
        c.name: (
            iso(getattr(row, c.name))
            if isinstance(getattr(row, c.name), datetime)
            else getattr(row, c.name)
        )
        for c in row.__table__.columns
    }


@event.listens_for(SessionLocal.class_, "before_flush")
def protect_records(db, flush_context, instances):
    for obj in db.new:
        if (
            isinstance(obj, Row)
            and obj.environment is not None
            and obj.environment != MODE
        ):
            raise ValueError("Una fila no puede cruzar el entorno de la base")
    for obj in db.dirty:
        if isinstance(
            obj, (RawEvent, Response, CaseEvent, Audit, Feature, Evaluation)
        ) and db.is_modified(obj):
            raise ValueError("Registro inmutable: cree una revisión o evento nuevo")
