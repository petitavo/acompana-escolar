"""Generación explícita, reproducible y exclusiva DEMO. Nunca simula una captura LAB."""

import random, secrets
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from app.db import *
from app.config import MODE, FEATURE_VERSION
from app.security import hasher, digest
from app.forms import ensure_demo_form
from app.features import build_day, deviation, persist_case
from app.cases import add_reason


def fixed(name):
    return str(uuid5(NAMESPACE_URL, "acompana-demo:" + name))


def generate(db, seed=20260906, end="2026-09-05"):
    if MODE != "DEMO":
        raise RuntimeError("Generador prohibido fuera de DEMO")
    if db.scalar(select(Participant).limit(1)):
        return {"already_seeded": True}
    rng = random.Random(seed)
    end = date.fromisoformat(end)
    start = end - timedelta(days=59)
    zone = ZoneInfo("America/Lima")
    credentials = {}
    users = {}
    for role, name in [
        ("psychologist", "psicologo.demo"),
        ("researcher", "investigador.demo"),
        ("admin", "admin.demo"),
    ]:
        password = secrets.token_urlsafe(18)
        user = User(
            id=fixed(name),
            username=name,
            password_hash=hasher.hash(password),
            role=role,
        )
        db.add(user)
        users[role] = user
        credentials[name] = password
    db.flush()
    instrument = ensure_demo_form(db)
    for i in range(12):
        pid = fixed(f"p{i}")
        did = fixed(f"d{i}")
        pseudo = f"DEMO-{i + 1:03}"
        p = Participant(
            id=pid, pseudonym=pseudo, group="Grupo A" if i < 6 else "Grupo B"
        )
        db.add(p)
        db.flush()
        db.add(Assignment(user_id=users["psychologist"].id, participant_id=pid))
        d = Device(
            id=did,
            participant_id=pid,
            status="active",
            detail={
                "manufacturer": "Generador sintético",
                "model": "Dispositivo ficticio",
                "android_api": 35,
                "app_version": "0.1.0-DEMO",
                "timezone": "America/Lima",
                "usage_access": "available",
                "battery": 74,
                "outbox_pending": 0,
                "last_sync": datetime.combine(end, time(23, 59), zone).isoformat(),
                "keyguard_available": True,
            },
        )
        db.add(d)
        db.flush()
        begin = datetime.combine(start, time.min, zone)
        db.add(
            Consent(
                device_id=did,
                version="lab-v1",
                detail={"synthetic": True, "adult": True},
            )
        )
        db.add(Interval(device_id=did, start_at=begin))
        captures = []
        events = []
        byday = {}
        for n in range(61):
            day = start + timedelta(days=n)
            if i == 4 and n >= 54 or i == 5 and n in (54, 55, 56) or i == 6 and n < 54:
                continue
            a = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
            b = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(
                timezone.utc
            )
            cid = fixed(f"{i}-{day}-capture")
            c = Capture(
                id=cid,
                device_id=did,
                start_at=a,
                end_at=b,
                created_at=b,
                detail={
                    "success": True,
                    "permission_before": True,
                    "permission_after": True,
                    "count": 8,
                    "error": "none",
                    "synthetic": True,
                },
            )
            db.add(c)
            db.flush()
            captures.append(public(c))
            night = 20 + i * 2 + rng.randrange(-5, 6)
            if i in (1, 2, 3) and n >= 48:
                night += 85 if i != 3 else 50
            durations = [
                20 + rng.randrange(0, 20),
                35 + rng.randrange(0, 25),
                15 + rng.randrange(0, 15),
                night,
            ]
            for hour, duration in zip((8, 13, 18, 22), durations):
                at = datetime.combine(day, time(hour, 10), zone)
                sample_end = at + timedelta(minutes=duration + 1)
                sample_id = fixed(f"{i}-{day}-{hour}-capture")
                sample = Capture(
                    id=sample_id,
                    device_id=did,
                    start_at=at - timedelta(minutes=1),
                    end_at=sample_end,
                    created_at=sample_end,
                    detail={
                        "success": True,
                        "permission_before": True,
                        "permission_after": True,
                        "count": 3,
                        "error": "none",
                        "synthetic": True,
                    },
                )
                db.add(sample)
                db.flush()
                captures.append(public(sample))
                for kind, stamp in [
                    ("SCREEN_INTERACTIVE", at),
                    ("SCREEN_NON_INTERACTIVE", at + timedelta(minutes=duration)),
                    ("KEYGUARD_HIDDEN", at),
                ]:
                    event = RawEvent(
                        id=fixed(f"{i}-{day}-{hour}-{kind}"),
                        device_id=did,
                        capture_session_id=sample_id,
                        occurred_at=stamp,
                        created_at=sample_end,
                        event_type=kind,
                        timezone="America/Lima",
                        payload={},
                        source="synthetic_generator",
                        consent_version="lab-v1",
                        clock_flag=False,
                    )
                    db.add(event)
                    db.flush()
                    events.append(public(event))
        for n in range(60):
            day = start + timedelta(days=n)
            lo = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
            hi = lo + timedelta(hours=32)
            detail = build_day(
                [e for e in events if lo <= utc(e["occurred_at"]) < hi],
                [
                    c
                    for c in captures
                    if utc(c["end_at"]) > lo and utc(c["start_at"]) < hi
                ],
                str(day),
                cutoff=hi,
            )
            f = Feature(
                id=fixed(f"{i}-{day}-feature"),
                device_id=did,
                day=str(day),
                version=FEATURE_VERSION,
                detail=detail,
                created_at=hi,
            )
            db.add(f)
            byday[str(day)] = detail
            if n >= 20:
                # A separate noisy synthetic target; questionnaire answers never become predictors.
                val = max(
                    0,
                    min(
                        9,
                        round(
                            2
                            + (3 if i in (1, 2, 3) and n >= 48 else 0)
                            + rng.gauss(0, 1.2)
                        ),
                    ),
                )
                answers = {
                    "energy": min(val, 3),
                    "focus": min(max(val - 3, 0), 3),
                    "rest": max(val - 6, 0),
                }
                stamp = datetime.combine(day, time(23, 58), zone)
                db.add(
                    Response(
                        id=fixed(f"{i}-{day}-response"),
                        participant_id=pid,
                        instrument_id=instrument.id,
                        created_at=stamp,
                        detail={
                            "instrument_code": instrument.code,
                            "instrument_version": "1",
                            "answers": answers,
                            "total": val,
                            "complete": True,
                            "real": False,
                            "applied_at": stamp.isoformat(),
                            "recall_start": datetime.combine(
                                day, time.min, zone
                            ).isoformat(),
                            "recall_end": stamp.isoformat(),
                            "synthetic": True,
                        },
                    )
                )
            cutoff = str(day + timedelta(days=1))
            ev = Evaluation(
                id=fixed(f"{i}-{cutoff}-eval"),
                participant_id=pid,
                cutoff=cutoff,
                version=FEATURE_VERSION,
                detail=deviation(byday, cutoff),
                created_at=hi,
            )
            db.add(ev)
            db.flush()
            persist_case(db, pid, ev)
        if i in (0, 2):
            add_reason(
                db,
                pid,
                "contact_request",
                {
                    "requested_at": datetime.combine(end, time(10), zone).isoformat(),
                    "synthetic": True,
                },
            )
        if i in (2, 7):
            add_reason(
                db,
                pid,
                "questionnaire_review_demo",
                {
                    "total": 7,
                    "notice": "Regla arbitraria ≥6, no clínica",
                    "synthetic": True,
                },
            )
        if i == 4:
            d.detail = {**d.detail, "usage_access": "permission_missing"}
        if i == 5:
            d.detail = {**d.detail, "connected": False, "outbox_pending": 24}
    db.add(
        AcademicEvent(
            group="Grupo A",
            detail={
                "start": str(end - timedelta(days=11)),
                "end": str(end - timedelta(days=4)),
                "type": "exams",
                "description": "Semana de exámenes ficticia",
            },
        )
    )
    p = db.get(Participant, fixed("p0"))
    code = secrets.token_urlsafe(24)
    db.add(
        Invitation(
            token_hash=digest(code),
            participant_id=p.id,
            expires_at=now() + timedelta(days=7),
        )
    )
    credentials["invitation"] = code
    return {
        "seed": seed,
        "end": str(end),
        "participants": 12,
        "interactive_participant": "DEMO-001",
        "credentials": credentials,
    }
