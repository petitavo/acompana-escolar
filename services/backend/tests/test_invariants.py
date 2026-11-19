import json
from datetime import timedelta, datetime, timezone, date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.db import *
from app.config import ARTIFACTS
from app.features import build_day, deviation, reconstruct
from app.forms import score, DEMO_FORM, validate_definition
from app.security import digest
from app.cases import add_reason
from worker.main import run_one, export, erase, safe_cell
from conftest import login

A = "/api/v1"


def capture_and_event(client, phone):
    at = now() - timedelta(minutes=30)
    cid = uid()
    body = {
        "id": cid,
        "start_at": (at - timedelta(minutes=20)).isoformat(),
        "end_at": now().isoformat(),
        "success": True,
        "permission_before": True,
        "permission_after": True,
        "count": 1,
    }
    r = client.post(A + "/capture-sessions", json=body)
    assert r.status_code == 200, r.text
    event = {
        "event_id": uid(),
        "device_id": phone["device_id"],
        "occurred_at": at.isoformat(),
        "timezone": "America/Lima",
        "event_type": "SCREEN_INTERACTIVE",
        "source": "synthetic_generator",
        "payload": {},
        "capture_session_id": cid,
    }
    return body, event


def test_ingest_three_retries_and_same_batch_duplicates(client, phone):
    capture, event = capture_and_event(client, phone)
    for n in range(3):
        r = client.post(A + "/events/batch", json={"events": [event, event]})
        assert r.status_code == 200, r.text
        assert len(r.json()["accepted"]) == (1 if n == 0 else 0)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RawEvent)) == 1


def test_payload_allowlist_and_no_packages_by_default(client, phone):
    _, e = capture_and_event(client, phone)
    e["payload"] = {"sms_text": "not allowed"}
    assert client.post(A + "/events/batch", json={"events": [e]}).status_code == 422
    e["payload"] = {"package": "com.example.app"}
    e["event_type"] = "ACTIVITY_RESUMED"
    r = client.post(A + "/events/batch", json={"events": [e]})
    assert r.json()["rejected"][0]["reason"] == "package_not_authorized"


def test_modes_cannot_mix_provenance_or_database(client, phone):
    _, e = capture_and_event(client, phone)
    e["source"] = "android_usage_events"
    assert (
        client.post(A + "/events/batch", json={"events": [e]}).json()["rejected"][0][
            "reason"
        ]
        == "wrong_provenance"
    )
    with SessionLocal.begin() as db:
        db.get(Environment, 1).mode = "LAB"
    with pytest.raises(RuntimeError):
        initialize()


def test_pause_resume_excludes_gap_and_revocation_denies_stale_token(client, phone):
    _, e = capture_and_event(client, phone)
    paused = now() - timedelta(minutes=50)
    assert (
        client.post(
            A + "/me/participation-events",
            headers={"Idempotency-Key": "pause"},
            json={"action": "pause", "occurred_at": paused.isoformat()},
        ).status_code
        == 200
    )
    assert client.post(A + "/events/batch", json={"events": [e]}).status_code == 409
    assert (
        client.post(
            A + "/me/participation-events",
            headers={"Idempotency-Key": "resume"},
            json={"action": "resume", "occurred_at": now().isoformat()},
        ).status_code
        == 200
    )
    assert (
        client.post(A + "/events/batch", json={"events": [e]}).json()["rejected"][0][
            "reason"
        ]
        == "outside_consent"
    )
    assert (
        client.post(
            A + "/me/participation-events",
            headers={"Idempotency-Key": "revoke"},
            json={"action": "revoke", "occurred_at": now().isoformat()},
        ).status_code
        == 200
    )
    assert client.post(A + "/events/batch", json={"events": [e]}).status_code == 401


def test_uuid_spoofing_and_capture_ownership(client, phone):
    _, e = capture_and_event(client, phone)
    e["device_id"] = uid()
    assert (
        client.post(A + "/events/batch", json={"events": [e]}).json()["rejected"][0][
            "reason"
        ]
        == "wrong_device"
    )
    e["device_id"] = phone["device_id"]
    e["capture_session_id"] = uid()
    assert (
        client.post(A + "/events/batch", json={"events": [e]}).json()["rejected"][0][
            "reason"
        ]
        == "unknown_capture_session"
    )


def test_forms_complete_idempotent_and_contact_without_model(client, phone):
    t = now().isoformat()
    body = {
        "instrument_code": "CHECKIN_DEMO_V1",
        "answers": {"energy": 3},
        "applied_at": t,
        "recall_start": t,
        "recall_end": t,
    }
    assert (
        client.post(
            A + "/questionnaire-responses",
            headers={"Idempotency-Key": "form"},
            json=body,
        ).status_code
        == 422
    )
    body["answers"] = {"energy": 3, "focus": 2, "rest": 2}
    for _ in range(3):
        assert (
            client.post(
                A + "/questionnaire-responses",
                headers={"Idempotency-Key": "form"},
                json=body,
            ).status_code
            == 200
        )
    for _ in range(2):
        assert (
            client.post(
                A + "/contact-requests",
                headers={"Idempotency-Key": "contact"},
                json={"requested_at": t},
            ).status_code
            == 200
        )
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Response)) == 1
        assert db.scalar(select(func.count()).select_from(Case)) == 1
        assert db.scalar(select(func.count()).select_from(Reason)) == 2
    body["answers"]["energy"] = 0
    assert (
        client.post(
            A + "/questionnaire-responses",
            headers={"Idempotency-Key": "form"},
            json=body,
        ).status_code
        == 409
    )


def test_cookie_csrf_rbac_idor_and_optimistic_transition(client, users):
    with SessionLocal.begin() as db:
        p = Participant(pseudonym="DEMO-ASSIGNED")
        other = Participant(pseudonym="DEMO-OTHER")
        db.add_all([p, other])
        db.flush()
        db.add(Assignment(participant_id=p.id, user_id=users["psychologist"]))
        c = add_reason(db, p.id, "contact_request", {})
        o = add_reason(db, other.id, "contact_request", {})
        cid = c.id
        other_id = o.id
    login(client, "researcher")
    assert client.get(A + "/psych/cases").status_code == 403
    assert client.get(A + "/psych/cases/" + cid).status_code == 403
    login(client, "admin")
    assert client.get(A + "/lab/events").status_code == 403
    assert client.get(A + "/psych/cases").status_code == 403
    login(client, "psychologist")
    assert len(client.get(A + "/psych/cases").json()) == 1
    assert client.get(A + "/psych/cases/" + other_id).status_code == 404
    assert client.get(A + "/lab/events").status_code == 403
    body = {"state": "acknowledged", "version": 1, "reason": "Prueba de revisión"}
    assert (
        client.post(
            A + "/psych/cases/" + cid + "/transitions",
            headers={"x-csrf-token": ""},
            json=body,
        ).status_code
        == 403
    )
    assert (
        client.post(A + "/psych/cases/" + cid + "/transitions", json=body).status_code
        == 200
    )
    body["state"] = "closed"
    assert (
        client.post(A + "/psych/cases/" + cid + "/transitions", json=body).status_code
        == 409
    )


def test_login_rate_limit_and_origin(client, users):
    for _ in range(5):
        assert (
            client.post(
                A + "/auth/login", json={"username": "admin", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            A + "/auth/login", json={"username": "admin", "password": "wrong"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            A + "/auth/login",
            headers={"origin": "https://evil.example"},
            json={"username": "admin", "password": "test-password-123"},
        ).status_code
        == 403
    )


def event(at, kind):
    return {"id": uid(), "occurred_at": at, "event_type": kind}


def query(a, b, success=True):
    return {
        "id": uid(),
        "start_at": a,
        "end_at": b,
        "detail": {
            "success": success,
            "permission_before": True,
            "permission_after": True,
        },
    }


def test_night_pair_cross_midnight_duplicate_out_of_order_and_null():
    a = "2026-08-01T03:10:00Z"
    b = "2026-08-01T03:25:00Z"
    qs = [query("2026-07-31T05:00:00Z", "2026-08-01T11:00:00Z")]
    events = [
        event(b, "SCREEN_NON_INTERACTIVE"),
        event(a, "SCREEN_INTERACTIVE"),
        event(a, "SCREEN_INTERACTIVE"),
    ]
    f = build_day(events, qs, "2026-07-31")
    assert f["features"]["night_interactive_minutes"]["value"] == 15
    assert f["features"]["interactive_minutes"]["value"] == 15
    partial = build_day([event(a, "SCREEN_INTERACTIVE")], qs, "2026-07-31")
    assert partial["features"]["night_interactive_minutes"]["state"] == "partial"
    assert partial["features"]["night_interactive_minutes"]["value"] == 0
    missing = build_day([], [], "2026-07-31")
    assert missing["features"]["night_interactive_minutes"]["value"] is None
    zero = build_day([], qs, "2026-07-31")
    assert zero["features"]["night_interactive_minutes"]["value"] == 0
    assert zero["features"]["night_interactive_minutes"]["eligible"]
    cross = build_day(
        [
            event("2026-08-01T04:50:00Z", "SCREEN_INTERACTIVE"),
            event("2026-08-01T05:10:00Z", "SCREEN_NON_INTERACTIVE"),
        ],
        qs,
        "2026-07-31",
    )
    assert cross["features"]["interactive_minutes"]["value"] == 10
    assert cross["features"]["night_interactive_minutes"]["value"] == 20


def test_gap_and_reboot_never_extend_duration():
    a = utc("2026-08-01T03:00:00Z")
    b = a + timedelta(hours=4)
    events = [
        event(a.isoformat(), "SCREEN_INTERACTIVE"),
        event(b.isoformat(), "SCREEN_NON_INTERACTIVE"),
    ]
    spans = [(a, a + timedelta(minutes=10)), (b - timedelta(minutes=10), b)]
    intervals, discard = reconstruct(events, spans)
    assert not intervals
    assert discard[0]["reason"] == "unverified_gap"
    events.insert(1, event((a + timedelta(minutes=2)).isoformat(), "DEVICE_STARTUP"))
    intervals, discard = reconstruct(events, [(a, b)])
    assert not intervals


def test_nonoverlap_mad_zero_and_future_does_not_change_frozen_evaluation():
    start = date(2026, 7, 1)
    history = {}
    for n in range(35):
        value = 30 if n < 28 else 90
        history[str(start + timedelta(days=n))] = {
            "features": {
                k: {"value": value, "eligible": True}
                for k in (
                    "interactive_minutes",
                    "night_interactive_minutes",
                    "interactive_session_count",
                    "keyguard_hidden_count",
                )
            }
        }
    cutoff = str(start + timedelta(days=35))
    before = deviation(history, cutoff)
    assert before["reference_end"] == before["current_start"]
    assert before["features"]["interactive_minutes"]["robust_deviation"] == 4
    history[str(start + timedelta(days=40))] = {
        "features": {k: {"value": 9999, "eligible": True} for k in before["features"]}
    }
    assert deviation(history, cutoff) == before


def test_item_rule_independent_of_total_and_no_eval():
    definition = {
        **DEMO_FORM,
        "review_threshold": 9,
        "item_rules": [
            {
                "question_id": "energy",
                "operator": "gte",
                "value": 1,
                "reason": "revisar ítem",
            }
        ],
    }
    total, review, rules = score(definition, {"energy": 1, "focus": 0, "rest": 0})
    assert total == 1 and review and rules
    with pytest.raises(Exception):
        validate_definition({**definition, "scoring": '__import__("os")'})


def test_export_authenticated_expiring_audited_and_deletion(client, users, phone):
    _, e = capture_and_event(client, phone)
    client.post(A + "/events/batch", json={"events": [e]})
    client.headers.pop("authorization")
    login(client, "researcher")
    req = {
        "kind": "raw",
        "format": "csv",
        "start": (now() - timedelta(days=1)).isoformat(),
        "end": now().isoformat(),
    }
    job = client.post(
        A + "/lab/exports", headers={"Idempotency-Key": "export"}, json=req
    ).json()
    assert run_one()
    assert client.get(A + "/lab/exports/" + job["id"] + "/download").status_code == 200
    assert safe_cell(' =WEBSERVICE("x")').startswith("'")
    with SessionLocal.begin() as db:
        j = db.get(Job, job["id"])
        j.result = {
            **j.result,
            "expires_at": (now() - timedelta(seconds=1)).isoformat(),
        }
        assert db.scalar(select(Audit).where(Audit.action == "export.generated"))
    assert client.get(A + "/lab/exports/" + job["id"] + "/download").status_code == 410
    with SessionLocal.begin() as db:
        erase(db, phone["participant_id"], "test")
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RawEvent)) == 0
        assert db.get(Participant, phone["participant_id"]) is None
        assert db.scalar(select(Audit).where(Audit.action == "participant.deleted"))
    assert not (ARTIFACTS / (job["id"] + ".csv")).exists()


def test_lease_recovery_executes_job(client, users):
    with SessionLocal.begin() as db:
        j = Job(
            kind="export",
            actor=users["researcher"],
            state="running",
            attempts=1,
            lease_until=now() - timedelta(seconds=1),
            payload={
                "kind": "raw",
                "format": "csv",
                "start": (now() - timedelta(days=1)).isoformat(),
                "end": now().isoformat(),
            },
        )
        db.add(j)
        db.flush()
        ident = j.id
    assert run_one()
    with SessionLocal() as db:
        j = db.get(Job, ident)
        assert j.state == "completed"
        assert j.attempts == 2


def test_cross_environment_rows_and_frozen_snapshots_rejected():
    with pytest.raises(ValueError):
        with SessionLocal.begin() as db:
            db.add(Participant(pseudonym="LAB-NOT-DEMO", environment="LAB"))
    with SessionLocal.begin() as db:
        p = Participant(pseudonym="DEMO-FROZEN")
        db.add(p)
        db.flush()
        ev = Evaluation(
            participant_id=p.id,
            cutoff="2026-08-01",
            version="v1",
            detail={"eligible": False},
        )
        db.add(ev)
        db.flush()
        ident = ev.id
    with pytest.raises(ValueError):
        with SessionLocal.begin() as db:
            db.get(Evaluation, ident).detail = {"eligible": True}


def test_behavior_resolution_preserves_questionnaire_and_human_followup():
    from app.features import persist_case

    names = [
        "interactive_minutes",
        "night_interactive_minutes",
        "interactive_session_count",
        "keyguard_hidden_count",
    ]
    with SessionLocal.begin() as db:
        p = Participant(pseudonym="DEMO-CHANGES")
        db.add(p)
        db.flush()
        for day in ("2026-08-01", "2026-08-02", "2026-08-03"):
            e = Evaluation(
                participant_id=p.id,
                cutoff=day,
                version="v1",
                detail={
                    "eligible": True,
                    "candidate": True,
                    "features": {
                        n: {"state": "available", "robust_deviation": 4} for n in names
                    },
                },
            )
            db.add(e)
            db.flush()
            persist_case(db, p.id, e)
        c = db.scalar(select(Case).where(Case.participant_id == p.id))
        assert c
        c.state = "in_followup"
        add_reason(db, p.id, "questionnaire_review_demo", {"total": 7})
        for day in ("2026-08-04", "2026-08-05", "2026-08-06"):
            e = Evaluation(
                participant_id=p.id,
                cutoff=day,
                version="v1",
                detail={
                    "eligible": True,
                    "candidate": False,
                    "features": {
                        n: {"state": "available", "robust_deviation": 0} for n in names
                    },
                },
            )
            db.add(e)
            db.flush()
            persist_case(db, p.id, e)
        assert c.state == "in_followup"
        assert db.scalar(
            select(Reason).where(
                Reason.case_id == c.id, Reason.kind == "questionnaire_review_demo"
            )
        ).active
        assert not db.scalar(
            select(Reason).where(
                Reason.case_id == c.id, Reason.kind == "behavior_change"
            )
        ).active


def test_reopen_conflicts_with_an_existing_active_case(client, users):
    with SessionLocal.begin() as db:
        p = Participant(pseudonym="DEMO-REOPEN")
        db.add(p)
        db.flush()
        db.add(Assignment(user_id=users["psychologist"], participant_id=p.id))
        closed = Case(participant_id=p.id, state="closed")
        db.add(closed)
        db.flush()
        ident = closed.id
        add_reason(db, p.id, "contact_request", {})
    login(client, "psychologist")
    r = client.post(
        A + "/psych/cases/" + ident + "/transitions",
        json={"state": "new", "version": 1, "reason": "Reabrir caso ficticio"},
    )
    assert r.status_code == 409
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Case).where(Case.state != "closed")
            )
            == 1
        )


def test_screen_broadcast_source_is_declared_and_never_mixed(client, phone):
    # El teléfono sin "Acceso al uso" declara la fuente en la sesión de captura.
    from app.schemas import CaptureInput

    body, e = capture_and_event(client, phone)
    assert CaptureInput(**{**body, "id": uid(), "source": "android_screen_broadcast"})
    e["source"] = "android_screen_broadcast"
    rejected = client.post(A + "/events/batch", json={"events": [e]}).json()["rejected"]
    assert rejected[0]["reason"] == "wrong_provenance"
