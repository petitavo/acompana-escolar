"""A08 — concurrent revocation vs. inference, on real PostgreSQL row locks.

Skipped unless the product suite runs against PostgreSQL
(``TEST_DATABASE_URL=postgresql://…``). Codex runs this with a private database.

Semantics under PostgreSQL READ COMMITTED with ``SELECT … FOR UPDATE`` on the
participant row taken by ``infer_registered`` right before the eligibility
re-check and the ``INSERT``:

* A withdrawal / authorization change that **commits before** the inference
  acquires the participant lock is always honoured — no prediction is written.
* A withdrawal that is still **uncommitted** when the inference takes the lock
  blocks its writer until the inference transaction commits. The prediction may
  be written in that window and is then invalidated by the withdrawal path
  (``delete(Prediction)`` in ``withdraw`` / ``erase``). We do **not** claim
  "revocation always wins" for events that linearise after the inference commit.
* Neither ordering deadlocks (lock order: Institution → Participant, never a
  Device/User row inside the job).
"""
import threading
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import SessionLocal, engine, Participant, Feature, Device, now
from app.school_db import StudentProfile, Prediction, ModelRecord
from conftest import login
from test_journeys import setup, enroll, authorize, post, A

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="needs real row locks; set TEST_DATABASE_URL to a PostgreSQL DSN",
)


def _seed_history(db, device_id, days_back=45):
    base = now().replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(days_back, 1, -1):
        day = (base - timedelta(days=offset)).date()
        window_end = base - timedelta(days=offset - 1)
        f = Feature(device_id=device_id, day=day.isoformat(), version="screen-v1.0",
                    detail={"features": {"observed_steps": {"value": 3000 + offset * 7, "eligible": True,
                                                            "unit": "pasos", "window_end": window_end.isoformat()}}})
        f.created_at = window_end
        db.add(f)


def _ready_shadow_model(c):
    from test_analysis import fixture_dataset
    from ml.school_pipeline import train_real
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    c.headers["authorization"] = "Bearer " + phone["token"]
    authorize(c, inv, cfg)
    pid = inv["student"]["participant_id"]
    login(c)
    data = fixture_dataset()
    ds = post(c, "/models/datasets", data)
    job = post(c, f"/models/datasets/{ds['id']}/train")
    with SessionLocal.begin() as db:
        mid = train_real(db, SimpleNamespace(payload=job["payload"]))["model_id"]
    post(c, f"/models/{mid}/decision", {"state": "shadow", "rationale": "Prueba de carrera controlada"})
    with SessionLocal.begin() as db:
        dev = db.scalar(select(Device).where(Device.participant_id == pid))
        _seed_history(db, dev.id)
    return pid, mid


def test_withdrawal_before_lock_blocks_prediction(client, monkeypatch):
    pid, mid = _ready_shadow_model(client)
    computed = threading.Event()
    withdrawn = threading.Event()

    import ml.school_pipeline as sp
    real_predict = sp.predict

    def slow_predict(model, values):
        out = real_predict(model, values)
        computed.set()
        assert withdrawn.wait(10)
        return out

    monkeypatch.setattr(sp, "predict", slow_predict)
    cutoff = now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = {}

    def infer():
        with SessionLocal.begin() as db:
            result["r"] = sp.infer_registered(db, SimpleNamespace(payload={"model_id": mid, "cutoff": cutoff.isoformat()}))

    def revoke():
        assert computed.wait(10)
        with SessionLocal.begin() as db:
            part = db.scalars(select(Participant).where(Participant.id == pid).with_for_update()).one()
            part.status = "revoked"
        withdrawn.set()

    ta, tb = threading.Thread(target=infer), threading.Thread(target=revoke)
    ta.start(); tb.start(); ta.join(15); tb.join(15)
    assert not ta.is_alive() and not tb.is_alive(), "deadlock / hang"
    assert result["r"]["predictions"] == 0
    with SessionLocal() as db:
        assert db.scalar(select(Prediction).where(Prediction.model_id == mid)) is None


def test_withdrawal_after_lock_is_invalidated(client, monkeypatch):
    pid, mid = _ready_shadow_model(client)
    computed = threading.Event()

    import ml.school_pipeline as sp
    from app.school_api import withdraw
    from app.school_core import profile
    real_predict = sp.predict

    def signalling_predict(model, values):
        out = real_predict(model, values)
        computed.set()
        return out

    monkeypatch.setattr(sp, "predict", signalling_predict)
    cutoff = now().replace(hour=0, minute=0, second=0, microsecond=0)
    done = {}

    def infer():
        with SessionLocal.begin() as db:
            done["r"] = sp.infer_registered(db, SimpleNamespace(payload={"model_id": mid, "cutoff": cutoff.isoformat()}))

    def revoke():
        assert computed.wait(10)
        time.sleep(0.2)  # let inference reach its participant lock first
        with SessionLocal.begin() as db:
            withdraw(db, profile(db, pid), "test-race")

    ta, tb = threading.Thread(target=infer), threading.Thread(target=revoke)
    ta.start(); tb.start(); ta.join(20); tb.join(20)
    assert not ta.is_alive() and not tb.is_alive(), "deadlock / hang"
    # Whether or not the row was briefly written, the withdrawal path removed it.
    with SessionLocal() as db:
        assert db.scalar(select(Prediction).where(Prediction.model_id == mid)) is None
        assert db.get(Participant, pid).status == "revoked"
