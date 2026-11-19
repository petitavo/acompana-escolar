import csv, io, json, os, time, shutil
from datetime import timedelta, date
from sqlalchemy import select, or_, delete
from app.db import *
from app.config import (
    ARTIFACTS,
    MODE,
    RAW_RETENTION_DAYS,
    FEATURE_RETENTION_DAYS,
    EXPORT_TTL_HOURS,
)
from app.features import process_device
from app.config import FEATURE_VERSION
from app.security import audit


def claim():
    with SessionLocal.begin() as db:
        guard(db)
        job = db.scalar(
            select(Job)
            .where(
                Job.attempts < 3,
                or_(
                    Job.state == "queued",
                    (Job.state == "running") & (Job.lease_until < now()),
                ),
            )
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.state = "running"
        job.attempts += 1
        job.lease_until = now() + timedelta(minutes=30)
        return job.id


def safe_cell(value):
    text = (
        json.dumps(value, ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


def json_safe(value):
    import math

    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def count_missing(value):
    if isinstance(value, dict):
        return sum(count_missing(v) for v in value.values())
    if isinstance(value, list):
        return sum(count_missing(v) for v in value)
    return int(json_safe(value) is None)


def export(db, job):
    body = job.payload
    start = utc(body["start"])
    end = utc(body["end"])
    rows = []
    people = set()
    if body["kind"] == "raw":
        for r in db.scalars(
            select(RawEvent).where(
                RawEvent.occurred_at >= start, RawEvent.occurred_at < end
            )
        ):
            p = db.get(Participant, db.get(Device, r.device_id).participant_id)
            people.add(p.id)
            rows.append({"pseudonym": p.pseudonym, **public(r)})
    elif body["kind"] == "features":
        for r in db.scalars(
            select(Feature).where(
                Feature.day >= str(start.date()), Feature.day < str(end.date())
            )
        ):
            p = db.get(Participant, db.get(Device, r.device_id).participant_id)
            people.add(p.id)
            rows.append({"pseudonym": p.pseudonym, **public(r)})
    else:
        from ml.pipeline import dataset

        rows = [
            r
            for r in dataset(db, "prospective")
            if start <= utc(r["label_recall_start"]) < end
        ]
        people = {r["participant_id"] for r in rows}
    path = ARTIFACTS / (job.id + "." + body["format"])
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as f:
        if body["format"] == "jsonl":
            for row in rows:
                f.write(
                    json.dumps(
                        json_safe(row), ensure_ascii=False, default=str, allow_nan=False
                    )
                    + "\n"
                )
        else:
            fields = list(rows[0]) if rows else ["no_rows"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: safe_cell(v) for k, v in row.items()})
    temporary.chmod(0o600)
    temporary.replace(path)
    audit(db, job.actor, "export.generated", job.id)
    return {
        "rows": len(rows),
        "participants": len(people),
        "participant_ids": sorted(people),
        "environment": MODE,
        "period": [body["start"], body["end"]],
        "expires_at": (now() + timedelta(hours=EXPORT_TTL_HOURS)).isoformat(),
        "origin": "synthetic" if MODE == "DEMO" else "android_lab",
        "feature_version": FEATURE_VERSION,
        "missing_values": count_missing(rows),
    }


def erase(db, pid, actor):
    devices = list(db.scalars(select(Device.id).where(Device.participant_id == pid)))
    cases = list(db.scalars(select(Case.id).where(Case.participant_id == pid)))
    from app.school_db import StudentProfile, Authorization, AccessLink, Followup, Notification, PushToken, SensorPoint, MobilityDay, Prediction, DatasetRecord, ModelRecord, CaseGrant, CheckIn
    school_profile = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == pid))
    if school_profile:
        # Conservative invalidation of authorized datasets/models in the affected
        # institution. Uploaded datasets may use external pseudonyms, so no
        # unprovable claim of exact identity matching is made.
        for model in db.scalars(select(ModelRecord).where(ModelRecord.institution_id == school_profile.institution_id)):
            __import__('pathlib').Path(model.artifact).unlink(missing_ok=True)
            db.execute(delete(Prediction).where(Prediction.model_id == model.id))
            db.delete(model)
        db.flush()
        for dataset in db.scalars(select(DatasetRecord).where(DatasetRecord.institution_id == school_profile.institution_id)):
            __import__('pathlib').Path(dataset.path).unlink(missing_ok=True)
            db.delete(dataset)
        for n in db.scalars(select(Notification)):
            if n.recipient_id in devices or n.detail.get("case_id") in cases:
                db.delete(n)
        db.execute(delete(CaseGrant).where(CaseGrant.participant_id == pid))
        for cls, column, ids in [(Followup, Followup.participant_id, [pid]), (Authorization, Authorization.participant_id, [pid]), (AccessLink, AccessLink.participant_id, [pid]), (SensorPoint, SensorPoint.device_id, devices), (MobilityDay, MobilityDay.device_id, devices), (Prediction, Prediction.participant_id, [pid]), (CheckIn, CheckIn.participant_id, [pid]), (PushToken, PushToken.owner_id, devices), (StudentProfile, StudentProfile.participant_id, [pid])]:
            db.execute(delete(cls).where(column.in_(ids)))
    # Cached administrative invitation/import results can also contain this identity.
    for cached in db.scalars(select(Idempotency)):
        if pid in json.dumps(cached.result, default=str):
            db.delete(cached)
    for job in db.scalars(select(Job).where(Job.kind.in_(["school_training", "school_inference"]))):
        if school_profile and job.payload.get("institution_id") == school_profile.institution_id:
            job.state = "expired"
            job.result = {"reason": "Invalidado por retirada de participación"}
    # Existing exports and derived models can contain the participant; invalidate conservatively.
    for job in db.scalars(select(Job).where(Job.kind.in_(["export", "training"]))):
        if job.kind == "export":
            for path in ARTIFACTS.glob(job.id + ".*"):
                path.unlink(missing_ok=True)
        elif (ARTIFACTS / job.id).is_dir():
            shutil.rmtree(ARTIFACTS / job.id)
        job.state = "expired"
        job.result = {"reason": "Invalidado por borrado de datos de prueba"}
    for cls, column, ids in [
        (Session, Session.device_id, devices),
        (Idempotency, Idempotency.actor, devices),
        (CaseEvent, CaseEvent.case_id, cases),
        (Reason, Reason.case_id, cases),
        (Case, Case.participant_id, [pid]),
        (Response, Response.participant_id, [pid]),
        (Evaluation, Evaluation.participant_id, [pid]),
        (Feature, Feature.device_id, devices),
        (RawEvent, RawEvent.device_id, devices),
        (Capture, Capture.device_id, devices),
        (Consent, Consent.device_id, devices),
        (Interval, Interval.device_id, devices),
        (Device, Device.participant_id, [pid]),
        (Assignment, Assignment.participant_id, [pid]),
        (Invitation, Invitation.participant_id, [pid]),
    ]:
        db.execute(delete(cls).where(column.in_(ids)))
    db.execute(delete(Participant).where(Participant.id == pid))
    audit(db, "worker", "participant.deleted", pid)
    ledger = ARTIFACTS / "deletions.jsonl"
    with ledger.open("a") as f:
        f.write(
            json.dumps({"participant_id": pid, "deleted_at": now().isoformat()}) + "\n"
        )
    ledger.chmod(0o600)
    return {
        "deleted": True,
        "participant_id": pid,
        "backup_notice": "Reaplicar ledger de borrados antes de servir una restauración; no hay eliminación instantánea de backups.",
    }


def maintenance(db):
    if MODE == "REAL":
        from .school import maintenance as school_maintenance
        school_maintenance(db)
    if MODE in ("LAB", "REAL"):
        for d in db.scalars(select(Device).where(Device.status == "active")) if MODE == "LAB" else []:
            from zoneinfo import ZoneInfo

            local = now().astimezone(ZoneInfo(d.detail.get("timezone", "America/Lima")))
            yesterday = str(
                (local - timedelta(days=1 if local.hour >= 8 else 2)).date()
            )
            existing = db.scalar(
                select(Feature).where(
                    Feature.device_id == d.id, Feature.day == yesterday
                )
            )
            queued = any(
                j.payload.get("device_id") == d.id and j.payload.get("end") == yesterday
                for j in db.scalars(
                    select(Job).where(
                        Job.kind == "reprocess",
                        Job.state.in_(["queued", "running", "completed"]),
                    )
                )
            )
            if not existing and not queued:
                db.add(
                    Job(
                        kind="reprocess",
                        actor="worker",
                        payload={
                            "device_id": d.id,
                            "start": str(
                                date.fromisoformat(yesterday) - timedelta(days=1)
                            ),
                            "end": yesterday,
                        },
                    )
                )
        db.execute(
            delete(RawEvent).where(
                RawEvent.created_at < now() - timedelta(days=RAW_RETENTION_DAYS)
            )
        )
        db.execute(
            delete(Feature).where(
                Feature.created_at < now() - timedelta(days=FEATURE_RETENTION_DAYS)
            )
        )
        if MODE == "LAB":
            # A05/A09: questionnaire responses are clinical records, training labels
            # and the student's own history — never retention-deleted in the product.
            # They leave only through withdrawal/erasure. LAB stays throwaway.
            db.execute(
                delete(Response).where(
                    Response.created_at < now() - timedelta(days=FEATURE_RETENTION_DAYS)
                )
            )
    for j in db.scalars(
        select(Job).where(Job.kind == "export", Job.state == "completed")
    ):
        if utc(j.result["expires_at"]) < now():
            for p in ARTIFACTS.glob(j.id + ".*"):
                p.unlink(missing_ok=True)
            j.state = "expired"
    for c in db.scalars(
        select(Case).where(
            Case.state == "new", Case.created_at < now() - timedelta(hours=24), MODE != "REAL"
        )
    ):
        if not db.scalar(
            select(CaseEvent).where(
                CaseEvent.case_id == c.id, CaseEvent.kind == "simulated_escalation"
            )
        ):
            db.add(
                CaseEvent(
                    case_id=c.id,
                    actor="worker",
                    kind="simulated_escalation",
                    detail={
                        "reason": "Sin reconocimiento tras 24 horas",
                        "delivery": "solo bandeja interna, ningún mensaje externo",
                    },
                )
            )


def run_one():
    ident = claim()
    if not ident:
        return False
    try:
        with SessionLocal.begin() as db:
            j = db.get(Job, ident)
            if j.kind == "training":
                from ml.pipeline import train

                result = train(db, j)
            elif j.kind == "school_training":
                from ml.school_pipeline import train_real
                result = train_real(db, j)
            elif j.kind == "school_dataset_build":
                from ml.dataset_builder import build_dataset, persist_dataset
                from app.model_api import validate_build_owner
                validate_build_owner(db, j.payload["owner_id"], j.payload["institution_id"], j.payload["spec"])
                data, report = build_dataset(db, j.payload["institution_id"], j.payload["spec"])
                result = persist_dataset(db, j.payload["institution_id"], j.payload["owner_id"], data, report)
                if j.payload.get("auto_retrain") and result.get("trainable"):
                    db.add(Job(kind="school_training", actor="worker", payload={
                        "dataset_id": result["dataset_id"], "institution_id": j.payload["institution_id"],
                        "seed": 20260906, "trigger": "scheduled_retrain"}))
                    result["retrain_queued"] = True
            elif j.kind == "school_inference":
                from ml.school_pipeline import infer_registered
                result = infer_registered(db, j)
            elif j.kind == "school_mobility":
                from .school import process_mobility
                result = process_mobility(db, j)
            elif j.kind == "export":
                result = export(db, j)
            elif j.kind == "deletion":
                result = erase(db, j.payload["participant_id"], j.actor)
            elif j.kind == "reprocess":
                d = db.get(Device, j.payload["device_id"])
                if not d:
                    raise ValueError("Dispositivo eliminado")
                result = process_device(
                    db,
                    d,
                    j.payload["start"],
                    j.payload["end"],
                    version=FEATURE_VERSION
                    if j.actor == "worker"
                    else FEATURE_VERSION + "/reprocess-" + j.id[:8],
                )
            else:
                raise ValueError("Tipo de job no soportado")
            j.result = result
            j.state = "completed"
            j.lease_until = None
            maintenance(db)
    except Exception as exc:
        with SessionLocal.begin() as db:
            j = db.get(Job, ident)
            j.state = "failed" if j.attempts >= 3 else "queued"
            j.result = {
                "error": type(exc).__name__,
                "message": str(exc)[:250] if isinstance(exc, ValueError) else "El procesamiento falló; revise la configuración y reintente. No se registran payloads.",
            }
            j.lease_until = None
        if os.getenv("WORKER_DEBUG") == "1":
            raise
    return True


def main():
    while True:
        if not run_one():
            with SessionLocal.begin() as db:
                maintenance(db)
            time.sleep(3)


if __name__ == "__main__":
    main()
