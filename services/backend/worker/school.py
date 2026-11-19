from datetime import timedelta, date
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from app.db import Device, Feature, Job, Idempotency, Evaluation, now, utc
from app.school_db import SensorPoint, MobilityDay, StudentProfile, Institution, ModelRecord, TrainingSchedule, Prediction
from app.school_core import settings, authorization_status, analysis_cutoff, school_zone
from app.mobility import day_summary, VERSION
from app.config import FEATURE_RETENTION_DAYS


def enqueue_once(db, key, kind, payload):
    if db.scalar(select(Idempotency.id).where(Idempotency.actor == "school-worker", Idempotency.key == key, Idempotency.route == "periodic")):
        return
    job = Job(kind=kind, actor="worker", payload=payload)
    db.add(job)
    db.flush()
    db.add(Idempotency(actor="school-worker", key=key, route="periodic", digest=key, result={"job_id": job.id}))


def process_mobility(db, job):
    d = db.get(Device, job.payload["device_id"])
    if not d:
        return {"skipped": "device_removed"}
    p = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == d.participant_id))
    day = job.payload["day"]
    if not p:
        return {"skipped": "no_school_profile"}
    # No fine coordinates uploaded means Android submits the same aggregate
    # contract; do not overwrite those local aggregates with empty server data.
    if not p.policy.get("raw_location_upload"):
        evaluate_mobility(db, d, day)
        return {"source": "android_local_summary"}
    points = [r.detail for r in db.scalars(select(SensorPoint).where(SensorPoint.device_id == d.id, SensorPoint.occurred_at >= utc(day + "T00:00:00Z") - timedelta(days=1), SensorPoint.occurred_at <= utc(day + "T00:00:00Z") + timedelta(days=2)))]
    school = school_zone(settings(db.get(Institution, p.institution_id)))
    result = day_summary(points, day, d.detail.get("timezone", "America/Lima"), p.policy.get("home_zone"), now(), school)
    result["source"] = "server_authorized_raw"
    db.add(MobilityDay(device_id=d.id, day=day, version=VERSION, detail=result))
    db.flush()
    evaluate_mobility(db, d, day)
    return {"day": day, "features": len(result["features"]), "source": result["source"]}


def evaluate_mobility(db, d, day):
    from app.features import deviation, persist_case
    from app.mobility import FEATURES
    cutoff = str(date.fromisoformat(day) + timedelta(days=1))
    existing = db.scalar(select(Evaluation).where(Evaluation.participant_id == d.participant_id, Evaluation.cutoff == cutoff, Evaluation.version == VERSION))
    latest = {}
    for r in db.scalars(select(MobilityDay).where(MobilityDay.device_id == d.id, MobilityDay.day <= day).order_by(MobilityDay.created_at)):
        latest[r.day] = r.detail
    result = deviation(latest, cutoff, FEATURES)
    if existing:
        if existing.detail == result:
            return
        existing.detail = result
        evaluation = existing
    else:
        evaluation = Evaluation(participant_id=d.participant_id, cutoff=cutoff, version=VERSION, detail=result)
        db.add(evaluation)
    db.flush()
    persist_case(db, d.participant_id, evaluation)


def maybe_schedule_build(db, institution, cfg):
    """A05/A06: controlled cadence. Enqueues a dataset-build job and, if configured,
    a retraining job — which only ever yields a *registered* model, never a promotion."""
    sched = db.scalar(select(TrainingSchedule).where(TrainingSchedule.institution_id == institution.id))
    if not sched or not sched.enabled or utc(sched.next_run_at) > now():
        return
    key = f"sched-build:{institution.id}:{now().date().isoformat()}"
    if db.scalar(select(Idempotency.id).where(Idempotency.actor == "school-worker", Idempotency.key == key, Idempotency.route == "periodic")):
        return
    job = Job(kind="school_dataset_build", actor="worker", payload={
        "institution_id": institution.id, "owner_id": sched.updated_by, "spec": sched.spec,
        "auto_retrain": sched.auto_retrain, "trigger": "scheduled"})
    db.add(job)
    db.flush()
    db.add(Idempotency(actor="school-worker", key=key, route="periodic", digest=key, result={"job_id": job.id}))
    sched.last_run_at = now()
    sched.next_run_at = now() + timedelta(days=sched.cadence_days)


def aggregation_status(db, institution_id):
    devices = set(db.scalars(select(Device.id).join(StudentProfile, StudentProfile.participant_id == Device.participant_id)
                            .where(StudentProfile.institution_id == institution_id)))
    rows = [j for j in db.scalars(select(Job).where(Job.kind.in_(["reprocess", "school_mobility"]),
            Job.state.in_(["queued", "running", "failed"]))) if j.payload.get("device_id") in devices]
    return {"pending_aggregates": sum(j.state in ("queued", "running") for j in rows),
            "failed_aggregates": sum(j.state == "failed" for j in rows),
            "failed_jobs": [{"id": j.id, "kind": j.kind} for j in rows if j.state == "failed"],
            "ready": not rows, "notice": "La inferencia espera a los agregados; los fallos deben reintentarse tras su corrección"}


def maintenance(db):
    from app.notifications import maintain_notifications
    # Dependency watermark: devices with an unfinished screen/mobility recompute must
    # not have inference run for the target day yet (A07 — run dependencies first).
    pending_dep_devices = {j.payload.get("device_id") for j in db.scalars(
        select(Job).where(Job.kind.in_(["reprocess", "school_mobility"]), Job.state.in_(["queued", "running"])))}
    for i in db.scalars(select(Institution).with_for_update()):
        cfg = settings(i)
        cutoff, closed_day = analysis_cutoff(cfg)  # A07: local-midnight watermark
        target_days = [closed_day, closed_day - timedelta(days=1)]
        institution_blocked = False
        for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == i.id)):
            # A02: retention of stored raw location runs for EVERY device regardless
            # of authorization / pause / revocation; only capture+processing is gated.
            ready = authorization_status(db, p)["ready"]
            for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id)):
                if ready and d.status != "revoked":
                    for day in target_days:
                        ds = day.isoformat()
                        enqueue_once(db, f"screen:{d.id}:{ds}", "reprocess", {"device_id": d.id, "start": str(day - timedelta(days=1)), "end": ds})
                        enqueue_once(db, f"mobility:{d.id}:{ds}", "school_mobility", {"device_id": d.id, "day": ds})
                    if d.id in pending_dep_devices:
                        institution_blocked = True
                db.execute(delete(SensorPoint).where(SensorPoint.device_id == d.id, SensorPoint.created_at < now() - timedelta(days=cfg["raw_location_retention_days"])))
        db.flush()
        dependency = aggregation_status(db, i.id)
        institution_blocked = not dependency["ready"]
        if not institution_blocked:
            maybe_schedule_build(db, i, cfg)
        for model in db.scalars(select(ModelRecord).where(ModelRecord.institution_id == i.id, ModelRecord.state.in_(["shadow", "active"]))):
            key = f"infer:{model.id}:{closed_day.isoformat()}"
            if db.scalar(select(Idempotency.id).where(Idempotency.actor == "school-worker", Idempotency.key == key, Idempotency.route == "periodic")):
                continue
            if institution_blocked:
                continue  # dependencies still running; a later tick will enqueue
            enqueue_once(db, key, "school_inference", {"model_id": model.id, "cutoff": cutoff.isoformat(), "closed_day": closed_day.isoformat(), "institution_id": i.id})
    db.execute(delete(MobilityDay).where(MobilityDay.created_at < now() - timedelta(days=FEATURE_RETENTION_DAYS)))
    maintain_notifications(db)


def queue_received_days(db, device, moments, kind):
    """Coalesce pending recalculations; delayed authorized uploads refresh closed days."""
    zone = ZoneInfo(device.detail.get("timezone", "America/Lima"))
    days = sorted({utc(t).astimezone(zone).date() for t in moments})
    pending = list(db.scalars(select(Job).where(Job.kind == kind, Job.state == "queued")))
    for day in days:
        if kind == "reprocess":
            payload = {"device_id": device.id, "start": str(day - timedelta(days=1)), "end": str(day)}
        else:
            payload = {"device_id": device.id, "day": str(day)}
        if not any(j.payload == payload for j in pending):
            row = Job(kind=kind, actor="worker", payload=payload)
            db.add(row)
            pending.append(row)
    # Preserve the previous estimate as evidence, then allow a new as-of revision.
    if days:
        for prediction in db.scalars(select(Prediction).where(Prediction.participant_id == device.participant_id,
                                                             Prediction.cutoff >= str(min(days)))):
            prediction.detail = {**prediction.detail, "invalidated_at": now().isoformat(), "invalidation_reason": "late_sensor_data"}
        model_ids = list(db.scalars(select(ModelRecord.id).join(StudentProfile, StudentProfile.institution_id == ModelRecord.institution_id)
                                   .where(StudentProfile.participant_id == device.participant_id)))
        for ident in model_ids:
            db.execute(delete(Idempotency).where(Idempotency.actor == "school-worker", Idempotency.route == "periodic",
                                                Idempotency.key.like("infer:" + ident + ":%")))
