"""A05 (local dataset builder) · A06 (evaluation bound to artifact) · A07 (local
cutoff / dependencies / late data) · controlled scheduler without auto-promotion."""
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionLocal, Device, Feature, Response, Participant, now, utc
from app.school_db import (
    Institution, StudentProfile, DatasetRecord, ModelRecord, Prediction, TrainingSchedule,
)
from app.phq9 import PHQ9
from conftest import login
from test_journeys import setup, post, A

STEP = "observed_steps"


def _seed_local_data(c, n_students=8, labels_per=5, days=85):
    """Enrolls/authorizes N non-minor test students and inserts, directly in the DB,
    daily step features + spaced PHQ-9 responses so the builder has real local rows.
    Stays inside the 90-day feature retention window."""
    inv, cfg = setup(c, False)
    classroom = c.get(A + "/classrooms").json()[0]
    people = c.get(A + "/accounts").json()
    psy = next(p["id"] for p in people if p["username"] == "psicologo")
    pids = []
    for k in range(n_students):
        student = inv if k == 0 else post(c, "/students", {
            "display_name": f"Estudiante {k}", "classroom_id": classroom["id"],
            "psychologist_id": psy, "minor": False, "is_test": True, "guardian_channel": ""})
        phone = post(c, "/enroll", {"invitation": student["invitation"]["token"],
                                    "verification_code": student["invitation"]["verification_code"],
                                    "device": {"android_api": 35, "manufacturer": "F", "model": "T",
                                               "app_version": "t", "timezone": "America/Lima"}})
        c.headers["authorization"] = "Bearer " + phone["token"]
        post(c, "/me/participation", {"action": "consent", "document_version": cfg["document_version"],
                                      "occurred_at": now().isoformat()})
        del c.headers["authorization"]
        pids.append(student["student"]["participant_id"])

    tz = ZoneInfo("America/Lima")
    start_day = (now().astimezone(tz).date() - timedelta(days=days + 2))
    with SessionLocal.begin() as db:
        for idx, pid in enumerate(pids):
            dev = db.scalar(select(Device).where(Device.participant_id == pid))
            for n in range(days):
                day = start_day + timedelta(days=n)
                window_end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz).astimezone(timezone.utc)
                available = window_end + timedelta(hours=9)
                f = Feature(device_id=dev.id, day=day.isoformat(), version="screen-v1.0",
                            detail={"features": {STEP: {"value": 2000 + idx * 120 + n * 4, "unit": "pasos",
                                                        "eligible": True, "state": "observed",
                                                        "window_start": (window_end - timedelta(days=1)).isoformat(),
                                                        "window_end": window_end.isoformat()}}})
                f.created_at = available
                db.add(f)
            iid = _instrument_id(db)
            for j in range(labels_per):
                applied = datetime.combine(start_day + timedelta(days=28 + j * 14), datetime.min.time(), tz).astimezone(timezone.utc)
                r = Response(participant_id=pid, instrument_id=iid,
                             detail={"instrument_code": PHQ9["instrument_id"], "instrument_version": PHQ9["version"],
                                     "answers": {f"q{i}": (idx + j) % 3 for i in range(1, 10)}, "functioning": 1,
                                     "applied_at": applied.isoformat(), "recall_end": applied.isoformat(),
                                     "recall_start": (applied - timedelta(days=14)).isoformat(),
                                     "total": (idx * 2 + j * 3) % 20, "complete": True, "real": False,
                                     "provenance": "test_account", "definition_sha256": PHQ9["definition_sha256"]})
                r.created_at = applied + timedelta(hours=1)
                db.add(r)
    return cfg, pids


def _instrument_id(db):
    from app.db import Instrument
    return db.scalar(select(Instrument.id).where(Instrument.code == PHQ9["instrument_id"]))


# --------------------------------------------------------------------------- A05
def test_builder_produces_immutable_snapshot_with_per_label_provenance(client):
    c = client
    cfg, pids = _seed_local_data(c)
    from ml.dataset_builder import build_dataset, persist_dataset

    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        data, report = build_dataset(db, inst, {
            "name": "Construcción local de prueba", "task": "prospective", "purpose": "clinical",
            "features": [STEP], "authorization_reference": "Protocolo ficticio de pruebas automatizadas",
            "include_test": True})
        assert report["trainable"], report["missing_for_training"]
        # per-label provenance covers exactly the labels, with authorization + source
        man = data["manifest"]
        assert set(man["label_provenance"]) == {l["id"] for l in data["labels"]}
        one = next(iter(man["label_provenance"].values()))
        assert one["source"] == "test_account" and "authorization_at_collection" in one
        assert one["definition_sha256"] == PHQ9["definition_sha256"]
        assert man["provenance"] == "test_fixture" and man["source"] == "local_builder"
        assert man["selection"]["build_cutoff"] and man["selection"]["closed_day"]
        result = persist_dataset(db, inst, _admin_id(db), data, report)
        dsid, sha = result["dataset_id"], result["sha256"]

    # immutable: stored bytes match the returned hash, re-read is identical
    with SessionLocal() as db:
        rec = db.get(DatasetRecord, dsid)
        raw = __import__("pathlib").Path(rec.path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha == rec.sha256

    # connected to training (no hand-authored JSON needed)
    job = post(c, f"/models/datasets/{dsid}/train")
    from ml.school_pipeline import train_real
    with SessionLocal.begin() as db:
        tr = train_real(db, SimpleNamespace(payload=job["payload"]))
    assert tr["metrics"]["artifact_sha256"] == tr["artifact_sha256"]


def _admin_id(db):
    from app.db import User
    return db.scalar(select(User.id).where(User.username == "admin"))


def test_builder_explains_exclusions(client):
    c = client
    cfg, pids = _seed_local_data(c, n_students=7)
    # withdraw one participant
    with SessionLocal.begin() as db:
        db.get(Participant, pids[0]).status = "revoked"
    from ml.dataset_builder import build_dataset
    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        _, report = build_dataset(db, inst, {
            "name": "x2", "task": "prospective", "purpose": "research",
            "features": [STEP], "authorization_reference": "Referencia de prueba automatizada larga",
            "include_test": True})
    reasons = {e["reason"] for e in report["excluded_participants"]}
    assert "withdrawn" in reasons
    # research purpose without research consent excludes non-test... here test accounts
    # are allowed, so at minimum the withdrawn one is out and it is explained.
    assert pids[0] in {e["participant_id"] for e in report["excluded_participants"]}


def test_builder_preview_does_not_persist(client):
    c = client
    _seed_local_data(c)
    before = _dataset_count(c)
    r = post(c, "/models/datasets/build?preview=true", {
        "name": "solo vista previa", "task": "concurrent", "features": [STEP],
        "authorization_reference": "Referencia de autorización de prueba", "include_test": True})
    assert r["preview"] is True and "excluded_labels" in r
    assert _dataset_count(c) == before


def _dataset_count(c):
    return len(c.get(A + "/models").json()["datasets"])


# --------------------------------------------------------------------------- A06
def test_evaluation_bound_to_artifact_and_import_cannot_fake_metrics(client):
    c = client
    cfg, pids = _seed_local_data(c)
    from ml.dataset_builder import build_dataset, persist_dataset
    from ml.school_pipeline import train_real, predict
    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        data, report = build_dataset(db, inst, {"name": "d", "task": "prospective", "features": [STEP],
                                                "authorization_reference": "Referencia de prueba automatizada",
                                                "include_test": True})
        dsid = persist_dataset(db, inst, _admin_id(db), data, report)["dataset_id"]
    job = post(c, f"/models/datasets/{dsid}/train")
    with SessionLocal.begin() as db:
        mid = train_real(db, SimpleNamespace(payload=job["payload"]))["model_id"]

    with SessionLocal() as db:
        m = db.get(ModelRecord, mid)
        assert m.metrics["artifact_sha256"] == m.manifest["artifact_sha256"]
        art = m.artifact

    # tamper the artifact -> predict refuses (hash mismatch)
    p = __import__("pathlib").Path(art)
    p.write_bytes(p.read_bytes() + b" ")
    with SessionLocal() as db:
        m = db.get(ModelRecord, mid)
        import pytest
        with pytest.raises(ValueError):
            predict(m, [0.0] * len(m.manifest["columns"]))

    # import: server recomputes metrics from dataset+artifact; caller supplies only bytes.
    # re-train to get a clean artifact, then import its bytes as a new model
    job2 = post(c, f"/models/datasets/{dsid}/train")
    with SessionLocal.begin() as db:
        mid2 = train_real(db, SimpleNamespace(payload=job2["payload"]))["model_id"]
    with SessionLocal() as db:
        raw = __import__("pathlib").Path(db.get(ModelRecord, mid2).artifact).read_bytes()
    import base64
    imported = post(c, "/models/import", {"dataset_id": dsid, "artifact_base64": base64.b64encode(raw).decode()})
    with SessionLocal() as db:
        im = db.get(ModelRecord, imported["id"])
        assert im.metrics["artifact_sha256"] == im.manifest["artifact_sha256"]
        assert {"constant", "ridge", "xgboost"} <= set(im.metrics)


def _wide_fixture():
    """A large hand-built dataset (bypasses DB retention) so the temporal probe
    completes and the activation gates can be exercised."""
    from ml.school_pipeline import CONTRACT
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    data = {"manifest": {"name": "wide", "provenance": "authorized_real",
                         "authorization_reference": "Protocolo ficticio para pruebas automatizadas",
                         "instrument": PHQ9["instrument_id"], "instrument_version": PHQ9["version"],
                         "recall_days": 14, "task": "prospective", "contract": CONTRACT,
                         "units": {STEP: "pasos"}, "purpose": "clinical"},
            "days": [], "labels": []}
    for p in range(10):
        for d in range(300):
            day = start + timedelta(days=d)
            end = (day + timedelta(days=1)).isoformat()
            data["days"].append({"participant_id": f"w{p}", "day": day.date().isoformat(),
                                 "available_at": end, "window_end": end,
                                 "features": {STEP: {"value": 1000 + p * 90 + d * 3, "eligible": True}}})
        for k in range(8):
            e = start + timedelta(days=60 + k * 28)
            data["labels"].append({"id": f"w{p}-{k}", "participant_id": f"w{p}",
                                   "score": (p + k * 2) % 20, "applied_at": e.isoformat(),
                                   "recall_end": e.isoformat(), "recall_start": (e - timedelta(days=14)).isoformat()})
    return data


def test_temporal_probe_is_a_separate_artifact_and_gates_activation(client):
    c = client
    setup(c)
    from ml.school_pipeline import train_real
    data = _wide_fixture()
    ds = post(c, "/models/datasets", data)
    job = post(c, f"/models/datasets/{ds['id']}/train")
    with SessionLocal.begin() as db:
        mid = train_real(db, SimpleNamespace(payload=job["payload"]))["model_id"]
        m = db.get(ModelRecord, mid)
        t = m.manifest["temporal"]
        assert t["status"] == "completed"
        assert t["artifact_sha256"] and t["artifact_sha256"] != m.manifest["artifact_sha256"]
        assert m.metrics["artifact_sha256"] == m.manifest["artifact_sha256"]
    post(c, f"/models/{mid}/decision", {"state": "shadow", "rationale": "Sombra para prueba de activación"})
    login(c, "psicologo")
    # tamper the temporal hash to equal the deployed hash -> activation refused
    with SessionLocal.begin() as db:
        m = db.get(ModelRecord, mid)
        m.manifest = {**m.manifest, "temporal": {**m.manifest["temporal"], "artifact_sha256": m.manifest["artifact_sha256"]}}
    r = c.post(A + f"/models/{mid}/decision", json={"state": "active", "rationale": "Intento con sonda no separada"})
    assert r.status_code == 409 and "separado" in r.text


def test_activation_rejects_mismatched_evaluation(client):
    c = client
    cfg, pids = _seed_local_data(c)
    from ml.dataset_builder import build_dataset, persist_dataset
    from ml.school_pipeline import train_real
    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        data, report = build_dataset(db, inst, {"name": "d", "task": "prospective", "features": [STEP],
                                                "authorization_reference": "Referencia de prueba automatizada",
                                                "include_test": True})
        # A real authorized-provenance dataset is required for activation.
        data["manifest"]["provenance"] = "authorized_real"
        dsid = persist_dataset(db, inst, _admin_id(db), data, report)["dataset_id"]
    job = post(c, f"/models/datasets/{dsid}/train")
    with SessionLocal.begin() as db:
        mid = train_real(db, SimpleNamespace(payload=job["payload"]))["model_id"]
        m = db.get(ModelRecord, mid)
        m.metrics = {**m.metrics, "artifact_sha256": "deadbeef"}  # pretend a different artifact
    post(c, f"/models/{mid}/decision", {"state": "shadow", "rationale": "Sombra para prueba de activación"})
    login(c, "psicologo")
    r = c.post(A + f"/models/{mid}/decision", json={"state": "active", "rationale": "Intento de activación con evaluación ajena"})
    assert r.status_code == 409 and "artefacto" in r.text


# --------------------------------------------------------------------------- A07
def test_analysis_cutoff_preserves_availability_and_local_watermark():
    from app.school_core import analysis_cutoff
    cfg = {"timezone": "America/Lima"}
    # 2026-09-08 07:00 Lima == 12:00Z -> before 09:00 local, last available day is D-2
    at = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    cutoff, closed = analysis_cutoff(cfg, at)
    assert closed.isoformat() == "2026-09-06"
    assert cutoff == at  # Availability is checked at execution time, not yesterday midnight.
    # 2026-09-08 15:00 Lima == 20:00Z -> after 09:00 local, D-1
    cutoff, closed = analysis_cutoff(cfg, datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc))
    assert closed.isoformat() == "2026-09-07"
    assert cutoff == datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc)


def test_late_data_invalidates_dependent_predictions(client):
    c = client
    cfg, pids = _seed_local_data(c, n_students=6)
    with SessionLocal.begin() as db:
        i = db.scalar(select(Institution)).id
        ds = DatasetRecord(institution_id=i, owner_id=_admin_id(db), name="x", manifest={}, path="/x", sha256="0" * 64)
        db.add(ds); db.flush()
        mr = ModelRecord(institution_id=i, dataset_id=ds.id, manifest={}, metrics={}, artifact="/x")
        db.add(mr); db.flush()
        db.add(Prediction(model_id=mr.id, participant_id=pids[0], cutoff="2026-09-05", detail={"score": 5}))
        db.add(Prediction(model_id=mr.id, participant_id=pids[0], cutoff="2026-08-01", detail={"score": 5}))
    from worker.school import queue_received_days
    with SessionLocal.begin() as db:
        dev = db.scalar(select(Device).where(Device.participant_id == pids[0]))
        queue_received_days(db, dev, [datetime(2026, 9, 4, 12, tzinfo=timezone.utc)], "reprocess")
    with SessionLocal() as db:
        left = {p.cutoff for p in db.scalars(select(Prediction).where(Prediction.participant_id == pids[0]))}
        assert left == {"2026-08-01", "2026-09-05"}  # Original evidence is retained.
        rows = {p.cutoff: p.detail for p in db.scalars(select(Prediction))}
        assert rows["2026-09-05"]["invalidation_reason"] == "late_sensor_data"
        assert "invalidated_at" not in rows["2026-08-01"]


def test_maintenance_waits_for_dependencies_before_inference(client):
    c = client
    cfg, pids = _seed_local_data(c, n_students=6)
    from ml.dataset_builder import build_dataset, persist_dataset
    from ml.school_pipeline import train_real
    from worker.school import maintenance
    with SessionLocal.begin() as db:
        inst = db.scalar(select(Institution)).id
        data, report = build_dataset(db, inst, {"name": "d", "task": "prospective", "features": [STEP],
                                                "authorization_reference": "Referencia de prueba automatizada",
                                                "include_test": True})
        dsid = persist_dataset(db, inst, _admin_id(db), data, report)["dataset_id"]
    job = post(c, f"/models/datasets/{dsid}/train")
    with SessionLocal.begin() as db:
        mid = train_real(db, SimpleNamespace(payload=job["payload"]))["model_id"]
    post(c, f"/models/{mid}/decision", {"state": "shadow", "rationale": "Sombra para prueba de dependencias"})

    from app.db import Job
    with SessionLocal.begin() as db:
        # a pending reprocess for one device blocks the whole institution's inference
        dev = db.scalar(select(Device).where(Device.participant_id == pids[0]))
        db.add(Job(kind="reprocess", actor="worker", state="running",
                   payload={"device_id": dev.id, "start": "2026-09-05", "end": "2026-09-06"}))
    with SessionLocal.begin() as db:
        maintenance(db)
        assert not db.scalar(select(Job).where(Job.kind == "school_inference"))
    with SessionLocal.begin() as db:
        for j in db.scalars(select(Job).where(Job.kind.in_(["reprocess", "school_mobility"]))):
            j.state = "completed"
    with SessionLocal.begin() as db:
        maintenance(db)
        assert db.scalar(select(Job).where(Job.kind == "school_inference"))


# --------------------------------------------------------------------------- scheduler
def test_schedule_builds_and_retrains_without_auto_promotion(client):
    c = client
    cfg, pids = _seed_local_data(c)
    r = c.put(A + "/models/schedule", json={
        "enabled": True, "cadence_days": 14, "auto_retrain": True,
        "spec": {"name": "Programado", "task": "prospective", "features": [STEP],
                 "authorization_reference": "Protocolo de prueba automatizada", "include_test": True}})
    assert r.status_code == 200, r.text

    from worker.school import maintenance
    from worker.main import run_one
    with SessionLocal.begin() as db:
        maintenance(db)  # Fresh aggregate jobs must finish before the due build.
    for _ in range(80):
        if not run_one():
            break
    with SessionLocal.begin() as db:
        maintenance(db)
    from app.db import Job
    with SessionLocal() as db:
        assert db.scalar(select(Job).where(Job.kind == "school_dataset_build"))
    for _ in range(80):
        if not run_one():
            break
    with SessionLocal() as db:
        jobs = [(j.kind, j.state) for j in db.scalars(select(Job)) if j.state not in ("completed",)]
        built = db.scalar(select(DatasetRecord).where(DatasetRecord.name == "Programado"))
        assert built is not None and built.manifest["source"] == "local_builder", jobs
        allj = [(j.kind, j.state, j.result) for j in db.scalars(select(Job)) if j.kind in ("school_dataset_build", "school_training")]
        models = list(db.scalars(select(ModelRecord)))
        assert models, ("auto_retrain should have produced a model", allj)
        assert all(m.state == "registered" for m in models)  # never auto-activated
    with SessionLocal() as db:
        s = db.scalar(select(TrainingSchedule))
        assert utc(s.next_run_at) > now()  # cadence advanced


def test_queued_build_rechecks_owner_membership(client):
    c = client
    _seed_local_data(c)
    job = post(c, '/models/datasets/build', {'name': 'Revocación de programador', 'task': 'prospective',
        'features': [STEP], 'authorization_reference': 'Referencia de prueba automatizada', 'include_test': True})
    from app.school_db import Membership
    from app.db import Job
    from worker.main import run_one
    with SessionLocal.begin() as db:
        owner = db.get(Job, job['id']).payload['owner_id']
        membership = db.scalar(select(Membership).where(Membership.user_id == owner))
        membership.active = False
    for _ in range(80):
        if not run_one():
            break
    with SessionLocal() as db:
        assert db.get(Job, job['id']).state == 'failed'
        assert not db.scalar(select(DatasetRecord).where(DatasetRecord.name == 'Revocación de programador'))


def test_failed_aggregate_retry_resets_claim_budget(client):
    c = client
    _, pids = _seed_local_data(c, n_students=6)
    from app.db import Job
    with SessionLocal.begin() as db:
        device = db.scalar(select(Device).where(Device.participant_id == pids[0]))
        job = Job(kind='school_mobility', actor='worker', state='failed', attempts=3,
                  payload={'device_id': device.id, 'day': '2026-09-05'})
        db.add(job); db.flush(); jid = job.id
    result = post(c, f'/models/aggregate-jobs/{jid}/retry')
    assert result['state'] == 'queued'
    with SessionLocal() as db:
        assert db.get(Job, jid).attempts == 0
    post(c, f'/models/aggregate-jobs/{jid}/retry', code=409)


def test_lima_window_uses_available_revision_not_future_reprocessing():
    from ml.school_pipeline import vector
    cutoff = datetime(2026, 9, 8, 14, tzinfo=timezone.utc)  # 09:00 Lima
    rows = []
    for offset in range(35):
        end = datetime(2026, 9, 8, 5, tzinfo=timezone.utc) - timedelta(days=offset)
        rows.append({'participant_id': 'fixture', 'day': (end-timedelta(days=1)).date().isoformat(),
                     'window_end': end.isoformat(), 'available_at': (end+timedelta(hours=3)).isoformat(),
                     'features': {STEP: {'value': 100, 'eligible': True}}})
    # A correction received after this cut cannot alter the historical vector.
    for row in rows[:7]:
        rows.append({**row, 'available_at': (cutoff+timedelta(hours=1)).isoformat(),
                     'features': {STEP: {'value': 999, 'eligible': True}}})
    before, _ = vector(rows, cutoff, [STEP], 'America/Lima', '2026-09-07')
    after, _ = vector(rows, cutoff+timedelta(hours=2), [STEP], 'America/Lima', '2026-09-07')
    assert before[0] == 100 and after[0] == 999
