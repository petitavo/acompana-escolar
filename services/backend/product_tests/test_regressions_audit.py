"""Regressions for AUDITORIA_INTEGRAL.md A01–A04, A08.

Each test here corresponds to a defect reproduction in
``.runtime/auditoria-20260907/test_audit.py``. The audit tests "passed" by
confirming the *broken* behaviour; these assert the *corrected* behaviour and
must fail if the fix is reverted.
"""
import re
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, User, Participant, now
from app.security import hasher
from app.school_db import (
    Institution,
    StudentProfile,
    SensorPoint,
    DatasetRecord,
    ModelRecord,
    Prediction,
    CaseGrant,
)
from conftest import login
from test_journeys import setup, enroll, authorize, post, A


# --------------------------------------------------------------------------- A02
def test_retention_runs_despite_expired_authorization_and_revoked_device(client):
    c = client
    inv, cfg = setup(c, False)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    authorize(c, inv, cfg)
    from worker.school import maintenance

    with SessionLocal.begin() as db:
        i = db.scalar(select(Institution))
        original = i.settings
        i.settings = {**original, "document_version": "renewal-regression"}
        from app.db import Device

        dev = db.scalar(select(Device))
        old = SensorPoint(
            device_id=dev.id,
            kind="location",
            occurred_at=now() - timedelta(days=30),
            created_at=now() - timedelta(days=30),
            signature="fixture",
            detail={"fixture": True},
        )
        fresh = SensorPoint(
            device_id=dev.id,
            kind="location",
            occurred_at=now(),
            created_at=now(),
            signature="fixture",
            detail={"fixture": True},
        )
        db.add_all([old, fresh])
        db.flush()
        old_id, fresh_id = old.id, fresh.id
        # Authorization is not "ready" (document version changed) yet retention runs.
        maintenance(db)
        assert db.get(SensorPoint, old_id) is None
        assert db.get(SensorPoint, fresh_id) is not None

    # Revoked device: expired raw points must still be purged.
    with SessionLocal.begin() as db:
        from app.db import Device

        dev = db.scalar(select(Device))
        dev.status = "revoked"
        p = SensorPoint(
            device_id=dev.id,
            kind="location",
            occurred_at=now() - timedelta(days=30),
            created_at=now() - timedelta(days=30),
            signature="fixture",
            detail={"fixture": True},
        )
        db.add(p)
        db.flush()
        pid = p.id
        maintenance(db)
        assert db.get(SensorPoint, pid) is None


# --------------------------------------------------------------------------- A01
def _seed_model(db, institution_id, participant_id, purpose, research_access=False):
    p = db.scalar(select(StudentProfile).where(StudentProfile.institution_id == institution_id))
    p.is_test = False
    p.policy = {**p.policy, "research_access": research_access}
    owner = db.scalar(select(User).where(User.username == "admin"))
    ds = DatasetRecord(institution_id=institution_id, owner_id=owner.id, name="isolated-fixture",
                       manifest={"purpose": purpose}, path="/not-used", sha256="0" * 64)
    db.add(ds)
    db.flush()
    m = ModelRecord(institution_id=institution_id, dataset_id=ds.id,
                    manifest={"purpose": purpose}, metrics={}, artifact="/not-used")
    db.add(m)
    db.flush()
    db.add(Prediction(model_id=m.id, participant_id=participant_id, cutoff="2026-09-01",
                      detail={"score": 19, "fixture": True}))
    return m.id


def test_predictions_visibility_by_model_purpose_and_authorization(client):
    c = client
    inv, cfg = setup(c, False)
    pid = inv["student"]["participant_id"]
    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        clinical_model = _seed_model(db, inst, pid, "clinical")
        research_model = _seed_model(db, inst, pid, "research", research_access=False)

    def scores(mid):
        r = c.get(A + f"/models/{mid}/predictions")
        return r.status_code, ([x["participant_id"] for x in r.json()] if r.status_code == 200 else None)

    # --- clinical model ---------------------------------------------------------
    login(c)  # admin, models+diagnostics scope
    assert scores(clinical_model) == (200, [])          # admin: never clinical estimates
    login(c, "psicologo")                                # assigned professional
    assert scores(clinical_model) == (200, [pid])
    login(c, "suplente")                                 # unassigned psychologist
    st, ids = scores(clinical_model)
    assert st == 403 or ids == []

    # --- research model, no research consent ----------------------------------
    login(c)
    assert scores(research_model) == (200, [])
    # grant research consent -> admin (diagnostics scope) now sees it
    with SessionLocal.begin() as db:
        p = db.scalar(select(StudentProfile))
        p.policy = {**p.policy, "research_access": True}
    assert scores(research_model) == (200, [pid])
    # clinical model is still invisible to admin even with research consent
    assert scores(clinical_model) == (200, [])
    # a clinical professional cannot read a research-purpose model
    login(c, "psicologo")
    st, ids = scores(research_model)
    assert st == 403 or ids == []

    # --- cross-institution ---------------------------------------------------
    with SessionLocal.begin() as db:
        db.add(User(username="admin-b", role="admin", scopes=["models", "diagnostics"],
                    password_hash=hasher.hash("test-password-123")))
    login(c, "admin-b")
    assert c.post(A + "/setup", json={"name": "Otra institución"}).status_code == 200
    assert c.get(A + f"/models/{research_model}/predictions").status_code == 404


# --------------------------------------------------------------------------- A03
def _transition(c, case_id, state, reason="Prueba de suplencia"):
    detail = c.get(f"/api/v1/psych/cases/{case_id}").json()
    return c.post(
        f"/api/v1/psych/cases/{case_id}/transitions",
        json={"state": state, "version": detail["version"], "reason": reason},
    )


def _escalate(at_days=2):
    from app.notifications import maintain_notifications
    with SessionLocal.begin() as db:
        maintain_notifications(db, now() + timedelta(days=at_days))


def test_backup_case_grant_is_scoped_to_the_single_escalated_case(client):
    c = client
    inv, cfg = setup(c, False)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    post(c, "/me/support")  # opens a case + notifies primary
    pid = inv["student"]["participant_id"]

    # A second student with their own escalated-looking case: the backup must not see it.
    login(c)
    classroom = c.get(A + "/classrooms").json()[0]
    other = post(c, "/students", {"display_name": "Otro estudiante", "classroom_id": classroom["id"],
                                  "psychologist_id": cfg["primary_id"], "minor": False, "is_test": True,
                                  "guardian_channel": "Canal ficticio"})
    other_pid = other["student"]["participant_id"]
    other_phone = post(c, "/enroll", {"invitation": other["invitation"]["token"],
                                      "verification_code": other["invitation"]["verification_code"],
                                      "device": {"android_api": 35, "manufacturer": "F", "model": "T",
                                                 "app_version": "t", "timezone": "America/Lima"}})
    c.headers["authorization"] = "Bearer " + other_phone["token"]
    post(c, "/me/support")
    del c.headers["authorization"]

    # An older, already-closed case for the first student.
    login(c, "psicologo")
    first_cases = c.get(A + "/cases").json()
    old_case_id = next(x["id"] for x in first_cases if x["participant_id"] == pid)
    assert _transition(c, old_case_id, "acknowledged").status_code == 200
    assert _transition(c, old_case_id, "closed").status_code == 200
    # New support request -> a brand new case for the same student.
    c.headers["authorization"] = "Bearer " + phone["token"]
    post(c, "/me/support")
    del c.headers["authorization"]
    login(c, "psicologo")
    new_case_id = next(x["id"] for x in c.get(A + "/cases").json()
                       if x["participant_id"] == pid and x["state"] != "closed")
    other_case_id = next(x["id"] for x in c.get(A + "/cases").json() if x["participant_id"] == other_pid)
    # the other student's case is handled by the primary -> it never escalates
    assert _transition(c, other_case_id, "acknowledged").status_code == 200

    _escalate()
    with SessionLocal.begin() as db:
        grants = list(db.scalars(select(CaseGrant).where(CaseGrant.revoked_at == None)))
        assert {g.case_id for g in grants} == {new_case_id}

    # ---- backup (suplente) view -------------------------------------------------
    login(c, "suplente")
    queue = c.get(A + "/cases").json()
    assert {x["id"] for x in queue} == {new_case_id}
    assert queue[0].get("access_scope") == "escalation"
    # no clinical profile / report / full history, no other case (same or other student)
    assert c.get(A + f"/students/{pid}/profile").status_code == 404
    assert c.get(A + f"/students/{pid}/report?start=2026-01-01T00:00:00Z&end=2026-06-01T00:00:00Z").status_code == 404
    assert c.get(f"/api/v1/psych/cases/{old_case_id}").status_code == 404
    assert c.get(f"/api/v1/psych/cases/{other_case_id}").status_code == 404
    detail = c.get(f"/api/v1/psych/cases/{new_case_id}").json()
    assert detail["access_scope"] == "escalation"

    # can acknowledge, add a contact followup, and close *this* case
    assert _transition(c, new_case_id, "acknowledged").status_code == 200
    fu = c.post(A + "/followups", json={"case_id": new_case_id, "kind": "appointment",
                                        "title": "Contacto de suplencia", "due_at": (now() + timedelta(days=1)).isoformat(),
                                        "location": "Orientación"}, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert fu.status_code == 200, fu.text
    # cannot create a followup on the other student's case
    assert c.post(A + "/followups", json={"case_id": other_case_id, "kind": "task",
                                          "title": "Intento fuera de alcance",
                                          "due_at": (now() + timedelta(days=1)).isoformat(), "location": ""},
                  headers={"Idempotency-Key": str(uuid.uuid4())}).status_code == 404
    assert _transition(c, new_case_id, "closed").status_code == 200

    # closing releases the grant
    with SessionLocal.begin() as db:
        assert not list(db.scalars(select(CaseGrant).where(CaseGrant.revoked_at == None)))
    assert c.get(f"/api/v1/psych/cases/{new_case_id}").status_code == 404


def test_backup_grant_expires_and_follows_backup_change(client):
    c = client
    inv, cfg = setup(c, False)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    post(c, "/me/support")
    del c.headers["authorization"]
    login(c, "psicologo")
    case_id = c.get(A + "/cases").json()[0]["id"]
    _escalate()

    # expiry: force the window into the past -> access ends, no maintenance extension
    with SessionLocal.begin() as db:
        for g in db.scalars(select(CaseGrant)):
            g.expires_at = now() - timedelta(minutes=1)
    login(c, "suplente")
    assert c.get(f"/api/v1/psych/cases/{case_id}").status_code == 404
    _escalate(at_days=3)  # a later maintenance tick must NOT silently re-extend
    from app.db import utc
    with SessionLocal.begin() as db:
        g = db.scalar(select(CaseGrant).where(CaseGrant.reason == "escalation"))
        assert utc(g.expires_at) < now()
    assert c.get(f"/api/v1/psych/cases/{case_id}").status_code == 404

    # backup change: create a third psychologist, make them the backup
    login(c)
    third = post(c, "/accounts", {"username": "suplente2", "password": "test-password-123", "role": "psychologist"})
    body = {k: v for k, v in c.get(A + "/settings").json().items() if k in {
        "document_version", "participation_document", "purpose", "primary_id", "backup_id", "coverage",
        "days", "opens", "closes", "acknowledgement_minutes", "safety_minutes", "escalation_minutes",
        "resources", "instrument_enabled", "professional_decision", "cadence_days", "minimum_group",
        "external_notifications_authorized", "raw_location_retention_days", "location_interval_minutes",
        "location_distance_meters"}}
    body["backup_id"] = third["id"]
    assert c.put(A + "/settings", json=body).status_code == 200
    with SessionLocal.begin() as db:
        old_grants = [g for g in db.scalars(select(CaseGrant)) if g.user_id == cfg["backup_id"]]
        assert old_grants and all(g.revoked_at is not None for g in old_grants)
    _escalate(at_days=4)
    login(c, "suplente")
    assert c.get(f"/api/v1/psych/cases/{case_id}").status_code == 404
    login(c, "suplente2")
    assert c.get(f"/api/v1/psych/cases/{case_id}").status_code == 200


# --------------------------------------------------------------------------- A04
KOTLIN_STORE = Path(
    "apps/mobile/android/app/src/main/kotlin/pe/upc/acompana/acompana_escolar/LocalStore.kt"
)


def _dao_query(name):
    src = KOTLIN_STORE.read_text()
    return re.search(r'@Query\("([^"]+)"\)\s*fun\s+' + re.escape(name), src).group(1)


def test_native_retention_keeps_visible_tombstones_and_never_touches_forms():
    """Runs the *real* sequence of DAO statements, not just the DELETE, and checks
    a durable, visible resolution survives while pending forms/support stay put."""
    expire_captures = _dao_query("expireStaleCaptures")
    purge_delivered = _dao_query("purgeDelivered")
    dismiss = _dao_query("dismiss")

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE outbox (id TEXT, createdAt INTEGER, state TEXT, kind TEXT, error TEXT, body TEXT)")
    day = 86_400_000
    NOW = 1_000_000 * day
    rows = [
        ("f_old", NOW - 8 * day, "pending", "school_form", None, '{"answers":1}'),
        ("s_old", NOW - 40 * day, "pending", "school_support", None, "{}"),
        ("p_old", NOW - 8 * day, "pending", "participation", None, "{}"),
        ("f_rej", NOW - 40 * day, "rejected", "school_form", "http_409", '{"answers":2}'),
        ("cap_stale", NOW - 90 * day, "pending", "event", None, '{"raw":"payload"}'),
        ("cap_done", NOW - 8 * day, "confirmed", "capture", None, "{}"),
        ("cap_tomb_old", NOW - 40 * day, "expired", "event", "capture_window_expired", ""),
        ("f_new", NOW - day, "pending", "school_form", None, "{}"),
    ]
    db.executemany("INSERT INTO outbox VALUES (?,?,?,?,?,?)", rows)

    retention = NOW - 7 * day
    db.execute(expire_captures, {"before": retention})
    db.execute(purge_delivered, {"before": retention})

    state = {r[0]: (r[1], r[2]) for r in db.execute("SELECT id, state, body FROM outbox")}
    # pending user obligations: untouched, still visible
    assert state["f_old"] == ("pending", '{"answers":1}')
    assert state["s_old"][0] == "pending"
    assert state["p_old"][0] == "pending"
    assert state["f_new"][0] == "pending"
    # a rejected form stays visible (durable), resolved only by explicit dismiss
    assert state["f_rej"][0] == "rejected"
    # stale capture -> durable tombstone with raw body wiped, NOT deleted, NOT "received"
    assert state["cap_stale"] == ("expired", "")
    # Delivered capture is purged; unresolved metadata survives even 90 days offline.
    assert "cap_done" not in state
    assert state["cap_tomb_old"] == ("expired", "")

    # explicit dismissal removes a rejected/expired item, nothing else
    db.execute(dismiss, {"id": "cap_stale"})
    db.execute(dismiss, {"id": "f_old"})  # pending -> must be ignored by the guard
    left = {r[0] for r in db.execute("SELECT id FROM outbox")}
    assert "cap_stale" not in left and "f_old" in left


# --------------------------------------------------------------------------- A08
def test_inference_eligibility_tracks_authorization(client):
    c = client
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    authorize(c, inv, cfg)
    from ml.school_pipeline import inference_eligible

    with SessionLocal.begin() as db:
        p = db.scalar(select(StudentProfile))
        ok, reason = inference_eligible(db, p, "clinical")
        assert ok, reason

        # Concurrent withdrawal wins.
        db.get(Participant, p.participant_id).status = "revoked"
        ok, reason = inference_eligible(db, p, "clinical")
        assert not ok and reason == "withdrawn"

    with SessionLocal.begin() as db:
        p = db.scalar(select(StudentProfile))
        db.get(Participant, p.participant_id).status = "active"
        # Research purpose needs an explicit research consent for a non-test student.
        p.is_test = False
        p.policy = {**p.policy, "research_access": False}
        ok, reason = inference_eligible(db, p, "research")
        assert not ok and reason in ("research_consent_missing", "pilot_disabled")


def _seed_step_history(db, device_id, participant_id, days_back=45):
    from app.db import Feature

    base = now().replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(days_back, 1, -1):
        day = (base - timedelta(days=offset)).date()
        window_end = base - timedelta(days=offset - 1)
        f = Feature(
            device_id=device_id,
            day=day.isoformat(),
            version="screen-v1.0",
            detail={
                "features": {
                    "observed_steps": {
                        "value": 3000 + offset * 7,
                        "eligible": True,
                        "unit": "pasos",
                        "window_end": window_end.isoformat(),
                    }
                }
            },
        )
        f.created_at = window_end
        db.add(f)


def test_infer_registered_skips_revoked_participant(client):
    from types import SimpleNamespace
    from ml.school_pipeline import train_real, infer_registered
    from test_analysis import fixture_dataset

    c = client
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    authorize(c, inv, cfg)
    pid = inv["student"]["participant_id"]
    login(c)  # back to the admin cookie session for model administration

    data = fixture_dataset()
    ds = post(c, "/models/datasets", data)
    job = post(c, f"/models/datasets/{ds['id']}/train")
    with SessionLocal.begin() as db:
        result = train_real(db, SimpleNamespace(payload=job["payload"]))
        mid = result["model_id"]
    post(c, f"/models/{mid}/decision", {"state": "shadow", "rationale": "Prueba de inferencia controlada"})

    with SessionLocal.begin() as db:
        from app.db import Device

        dev = db.scalar(select(Device).where(Device.participant_id == pid))
        _seed_step_history(db, dev.id, pid)

    cutoff = now().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal.begin() as db:
        r = infer_registered(db, SimpleNamespace(payload={"model_id": mid, "cutoff": cutoff.isoformat()}))
    assert r["predictions"] == 1

    with SessionLocal.begin() as db:
        db.get(Participant, pid).status = "revoked"
    later = (cutoff + timedelta(days=1)).isoformat()
    with SessionLocal.begin() as db:
        r = infer_registered(db, SimpleNamespace(payload={"model_id": mid, "cutoff": later}))
    assert r["predictions"] == 0
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(Prediction).where(
                    Prediction.model_id == mid, Prediction.cutoff == later[:10]
                )
            )
            is None
        )
