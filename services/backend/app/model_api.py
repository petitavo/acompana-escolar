import base64
import hashlib
import json
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from .db import Job, now, utc, uid, public
from .school_db import DatasetRecord, ModelRecord, Prediction, Institution, TrainingSchedule
from .school_core import member, settings, access, analysis_cutoff
from .school_schemas import ModelDecision, Strict, DatasetBuildSpec, TrainingScheduleInput
from .security import identity, database, audit, once
from .config import ARTIFACTS
from pydantic import Field

router = APIRouter(prefix="/api/v1/school/models", tags=["Modelos y evaluación"])


def permission(db, actor, decision=False):
    m = member(db, actor, "admin", "researcher", "psychologist")
    cfg = settings(db.get(Institution, m.institution_id))
    if decision and actor["role"] == "psychologist" and cfg["primary_id"] == actor["id"]:
        return m
    if actor["role"] not in ("admin", "researcher") or "models" not in actor["scopes"]:
        raise HTTPException(403, "Falta permiso de administración de modelos")
    return m


def aggregate_only(value):
    """Registry metadata never becomes a side channel to participant health or identifiers."""
    if isinstance(value, list):
        return [aggregate_only(v) for v in value]
    if not isinstance(value, dict):
        return value
    hidden = {"participant_id", "participant_ids", "participant_mae", "test_participants", "label_provenance",
              "day_provenance", "label_provenance_sample", "functioning", "authorization_ids", "owner_id"}
    result = {k: aggregate_only(v) for k, v in value.items() if k not in hidden}
    if "partitions" in result:
        result["partitions"] = {k: len(v) for k, v in value["partitions"].items()}
    return result


def build_authority(db, actor, institution_id, spec):
    if spec.get("include_test"):
        return
    cfg = settings(db.get(Institution, institution_id))
    if spec.get("purpose", "clinical") == "clinical":
        if actor["role"] != "psychologist" or actor["id"] != cfg["primary_id"]:
            raise HTTPException(403, "La construcción clínica requiere al psicólogo responsable")
    elif actor["role"] not in ("researcher", "admin") or "diagnostics" not in actor["scopes"]:
        raise HTTPException(403, "La investigación requiere permiso de diagnóstico y autorización individual")



def validate_build_owner(db, owner_id, institution_id, spec):
    from .db import User
    user = db.get(User, owner_id)
    if not user:
        raise ValueError("La cuenta que autorizó la construcción ya no está activa")
    actor = {"id": user.id, "role": user.role, "scopes": user.scopes}
    mem = permission(db, actor, True)
    if mem.institution_id != institution_id:
        raise ValueError("La cuenta no pertenece a esta institución")
    build_authority(db, actor, institution_id, spec)

@router.get("")
def registry(actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    models = [{k: v for k, v in public(row).items() if k != "artifact"} for row in db.scalars(select(ModelRecord).where(ModelRecord.institution_id == m.institution_id).order_by(ModelRecord.created_at.desc()))]
    datasets = [{k: v for k, v in public(row).items() if k != "path"} for row in db.scalars(select(DatasetRecord).where(DatasetRecord.institution_id == m.institution_id))]
    jobs = [public(j) for j in db.scalars(select(Job).where(Job.kind.in_(["school_training", "school_inference", "school_dataset_build"])).order_by(Job.created_at.desc()).limit(100)) if j.payload.get("institution_id") == m.institution_id]
    from worker.school import aggregation_status
    return aggregate_only({"status": "registered" if models else "Modelo pendiente de entrenamiento", "models": models, "datasets": datasets, "jobs": jobs, "analysis": aggregation_status(db, m.institution_id)})


@router.post("/datasets")
def import_dataset(body: dict, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    m = permission(db, actor)
    from ml.school_pipeline import validate_dataset, windows
    try:
        manifest = validate_dataset(body)
        usable, names = windows(body)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    def apply():
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        checksum = hashlib.sha256(raw).hexdigest()
        path = ARTIFACTS / "datasets" / (uid() + ".json")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)
        path.chmod(0o600)
        record = DatasetRecord(institution_id=m.institution_id, owner_id=actor["id"], name=manifest["name"], manifest=manifest, path=str(path), sha256=checksum)
        db.add(record)
        db.flush()
        audit(db, actor["id"], "model.dataset_imported", record.id)
        return {"id": record.id, "eligible_labels": len(usable), "features": names, "sha256": checksum}
    return once(db, actor, idempotency_key, "school-dataset", body, apply)


@router.post("/datasets/build")
def build_local_dataset(body: DatasetBuildSpec, preview: bool = False, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    """A05: construct an immutable dataset from local authorized responses + features
    + mobility. ``?preview=true`` returns the selection/exclusions report without
    persisting anything."""
    mem = permission(db, actor, True)
    build_authority(db, actor, mem.institution_id, body.model_dump())
    if preview:
        from ml.dataset_builder import build_dataset
        try:
            _, report = build_dataset(db, mem.institution_id, body.model_dump())
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, str(exc))
        return aggregate_only({"preview": True, **report})
    def apply():
        job = Job(kind="school_dataset_build", actor=actor["id"], payload={"institution_id": mem.institution_id, "owner_id": actor["id"], "spec": body.model_dump()})
        db.add(job)
        db.flush()
        audit(db, actor["id"], "model.dataset_build_queued", job.id)
        return public(job)
    return once(db, actor, idempotency_key, "school-dataset-build", body.model_dump(), apply)


@router.get("/schedule")
def get_schedule(actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    s = db.scalar(select(TrainingSchedule).where(TrainingSchedule.institution_id == m.institution_id))
    if not s:
        return {"configured": False, "note": "La construcción y el reentrenamiento programados no promueven modelos: siempre quedan en 'registered' para revisión."}
    return {"configured": True, "enabled": s.enabled, "cadence_days": s.cadence_days,
            "auto_retrain": s.auto_retrain, "spec": s.spec,
            "next_run_at": public(s)["next_run_at"], "last_run_at": public(s)["last_run_at"],
            "note": "El reentrenamiento programado nunca activa un modelo; conserva comparadores, evaluación, SHAP y rollback."}


@router.put("/schedule")
def put_schedule(body: TrainingScheduleInput, actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    build_authority(db, actor, m.institution_id, body.spec.model_dump())
    s = db.scalar(select(TrainingSchedule).where(TrainingSchedule.institution_id == m.institution_id))
    values = dict(enabled=body.enabled, cadence_days=body.cadence_days, auto_retrain=body.auto_retrain,
                  spec=body.spec.model_dump(), updated_by=actor["id"])
    if s:
        for k, v in values.items():
            setattr(s, k, v)
        if s.next_run_at is None or utc(s.next_run_at) < now():
            s.next_run_at = now()
    else:
        s = TrainingSchedule(institution_id=m.institution_id, next_run_at=now(), **values)
        db.add(s)
    audit(db, actor["id"], "model.schedule_saved", m.institution_id)
    return {"saved": True, "enabled": s.enabled, "next_run_at": s.next_run_at.isoformat()}


@router.get("/datasets/{ident}")
def dataset_detail(ident: UUID, actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    row = db.get(DatasetRecord, str(ident))
    if not row or row.institution_id != m.institution_id:
        raise HTTPException(404, "Dataset no disponible")
    man = row.manifest
    return {"id": row.id, "name": row.name, "sha256": row.sha256, "created_at": public(row)["created_at"],
            "provenance": man.get("provenance"), "purpose": man.get("purpose"), "task": man.get("task"),
            "source": man.get("source", "imported"), "features": list(man.get("units", {})),
            "selection": man.get("selection"), "exclusions": aggregate_only(man.get("exclusions")),
            "label_count": len(man.get("label_provenance", {})),
            "source_labels_count": len(man.get("label_provenance", {})),
            "models": [{"id": mr.id, "state": mr.state, "artifact_sha256": mr.manifest.get("artifact_sha256")}
                       for mr in db.scalars(select(ModelRecord).where(ModelRecord.dataset_id == row.id))]}


@router.post("/datasets/{ident}/train")
def train_dataset(ident: UUID, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    m = permission(db, actor, True)
    record = db.get(DatasetRecord, str(ident))
    if not record or record.institution_id != m.institution_id:
        raise HTTPException(404, "Dataset no disponible")
    def apply():
        job = Job(kind="school_training", actor=actor["id"], payload={"dataset_id": record.id, "institution_id": m.institution_id, "seed": 20260906})
        db.add(job)
        db.flush()
        audit(db, actor["id"], "model.training_queued", job.id)
        return public(job)
    return once(db, actor, idempotency_key, "school-train", {"dataset_id": str(ident)}, apply)


class ModelImport(Strict):
    dataset_id: UUID
    artifact_base64: str = Field(max_length=700000)
    seed: int | None = None


@router.post("/import")
def import_model(body: ModelImport, actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor)
    dataset = db.get(DatasetRecord, str(body.dataset_id))
    if not dataset or dataset.institution_id != m.institution_id:
        raise HTTPException(404, "Dataset autorizado no disponible")
    from ml.school_pipeline import CONTRACT, PARTS, register_evaluated_model, dataset_rows
    from .phq9 import PHQ9
    try:
        raw = base64.b64decode(body.artifact_base64, validate=True)
        decoded = json.loads(raw)
        if not isinstance(decoded, dict) or "learner" not in decoded or decoded["learner"]["objective"]["name"] != "reg:squarederror":
            raise ValueError("Solo se admite JSON nativo XGBoost de regresión; no pickle")
        _, _, names, _ = dataset_rows(dataset)
        columns = [f"{name}_{part}" for name in names for part in PARTS]
        if int(decoded["learner"]["learner_model_param"]["num_feature"]) != len(columns):
            raise ValueError("El artefacto no coincide con las columnas del dataset")
        if dataset.manifest["contract"] != CONTRACT or dataset.manifest["instrument_version"] != PHQ9["version"]:
            raise ValueError("Dataset incompatible con el contrato vigente")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    # A06: the importer supplies only the artifact bytes. The server recomputes the
    # partition, the comparator evaluation and the temporal probe from the dataset
    # + this artifact, so a hand-written manifest can never fake a model's metrics.
    seed = int(body.seed if body.seed is not None else 20260906)
    ident = uid()
    path = ARTIFACTS / "models" / ident / "model.json"
    path.parent.mkdir(parents=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)
    try:
        row, metrics, temporal = register_evaluated_model(
            db, dataset, path, seed, path.parent,
            {"imported_at": now().isoformat(), "imported_by": actor["id"],
             "purpose": dataset.manifest.get("purpose", "clinical"), "trigger": "import"})
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    audit(db, actor["id"], "model.imported", ident)
    return {"id": ident, "state": "registered", "metrics": metrics, "temporal": temporal}


@router.post("/{ident}/decision")
def model_decision(ident: UUID, body: ModelDecision, actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    db.scalar(select(Institution).where(Institution.id == m.institution_id).with_for_update())
    row = db.get(ModelRecord, str(ident))
    if not row or row.institution_id != m.institution_id:
        raise HTTPException(404, "Modelo no disponible")
    if body.state in ("active", "shadow") and db.get(DatasetRecord, row.dataset_id).manifest.get("invalidated_at"):
        raise HTTPException(409, "El dataset fuente está invalidado; construya otra versión")
    if body.state == "active":
        cfg = settings(db.get(Institution, m.institution_id))
        if actor["id"] != cfg["primary_id"] or actor["role"] != "psychologist":
            raise HTTPException(403, "La activación exige la decisión del psicólogo responsable")
        if row.manifest["provenance"] != "authorized_real":
            raise HTTPException(409, "Los modelos de pruebas nunca se activan en el producto")
        if not row.metrics or not row.manifest.get("partitions"):
            raise HTTPException(409, "Falta evaluación registrada")
        # A06: the recorded metrics must belong to *this exact artifact*, computed
        # server-side from the dataset + artifact — never a hand-written manifest.
        if row.metrics.get("artifact_sha256") != row.manifest.get("artifact_sha256"):
            raise HTTPException(409, "La evaluación registrada no corresponde al artefacto de este modelo")
        if not all(k in row.metrics for k in ("constant", "last_questionnaire", "ridge", "xgboost", "levels_only")):
            raise HTTPException(409, "Falta evaluación contra los comparadores")
        partitions = row.manifest.get("partitions", {})
        groups = [set(partitions.get(k, [])) for k in ("train", "validation", "test")]
        if any(not g for g in groups) or any(groups[a] & groups[b] for a, b in ((0,1),(0,2),(1,2))):
            raise HTTPException(409, "Registre particiones independientes de entrenamiento, validación y test")
        temporal = row.manifest.get("temporal", {})
        if temporal.get("status") != "completed":
            raise HTTPException(409, "Falta completar la evaluación temporal antes de activar")
        # The temporal probe is its own embargoed artifact, never the deployed hash.
        if temporal.get("artifact_sha256") in (None, row.manifest.get("artifact_sha256")):
            raise HTTPException(409, "La sonda temporal debe evaluarse como artefacto separado")
        for old in db.scalars(select(ModelRecord).where(ModelRecord.institution_id == m.institution_id, ModelRecord.state == "active", ModelRecord.id != row.id)):
            old.state = "retired"
            old.decisions = [*old.decisions, {"at": now().isoformat(), "actor": actor["id"], "state": "retired", "rationale": "Sustituido explícitamente por " + row.id}]
    row.state = body.state
    row.decisions = [*row.decisions, {"at": now().isoformat(), "actor": actor["id"], **body.model_dump()}]
    audit(db, actor["id"], "model.decision", row.id)
    return {"id": row.id, "state": row.state}


@router.post("/{ident}/infer")
def queue_inference(ident: UUID, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    m = permission(db, actor, True)
    row = db.get(ModelRecord, str(ident))
    if not row or row.institution_id != m.institution_id or row.state not in ("active", "shadow"):
        raise HTTPException(409, "Seleccione una versión en sombra o activa")
    from worker.school import aggregation_status
    if not aggregation_status(db, m.institution_id)["ready"]:
        raise HTTPException(409, "Espere a los agregados pendientes o corrija los jobs fallidos antes de inferir")
    cfg = settings(db.get(Institution, m.institution_id))
    cutoff, closed_day = analysis_cutoff(cfg)  # A07: local-midnight watermark, not UTC
    def apply():
        job = Job(kind="school_inference", actor=actor["id"], payload={"model_id": row.id, "institution_id": m.institution_id, "cutoff": cutoff.isoformat(), "closed_day": closed_day.isoformat()})
        db.add(job)
        db.flush()
        return public(job)
    return once(db, actor, idempotency_key, f"school-infer:{closed_day.isoformat()}", {"model_id": row.id}, apply)


def prediction_subject(db, actor, model, participant_id):
    """A01: an individual estimate is health data. Managing models never grants it.

    Visibility depends on the *model's declared purpose* and the reader's own,
    currently-valid authorization for that participant:
      - clinical-purpose model  -> only the assigned professional (clinical access).
      - research-purpose model   -> only diagnostics scope + the participant's
                                    current research consent.
    Cross-institution is already blocked by ``access`` (raises 404)."""
    purpose = model.manifest.get("purpose", "clinical")
    if purpose == "research":
        return access(db, actor, participant_id, "diagnostics")
    if actor["role"] not in ("psychologist", "practitioner"):
        raise HTTPException(403, "Un modelo clínico solo lo consulta el profesional asignado")
    return access(db, actor, participant_id, "clinical")


@router.get("/{ident}/predictions")
def predictions(ident: UUID, actor=Depends(identity), db=Depends(database)):
    m = permission(db, actor, True)
    row = db.get(ModelRecord, str(ident))
    if not row or row.institution_id != m.institution_id:
        raise HTTPException(404, "Modelo no disponible")
    visible = []
    for p in db.scalars(select(Prediction).where(Prediction.model_id == row.id).order_by(Prediction.cutoff.desc()).limit(400)):
        try:
            prediction_subject(db, actor, row, p.participant_id)
        except HTTPException:
            continue
        visible.append(public(p))
        if len(visible) >= 100:
            break
    audit(db, actor["id"], "model.predictions_read", row.id)
    return visible


@router.post("/aggregate-jobs/{ident}/retry")
def retry_aggregate(ident: UUID, actor=Depends(identity), db=Depends(database)):
    from .db import Device
    from .school_db import StudentProfile
    mem = permission(db, actor, True)
    job = db.scalar(select(Job).where(Job.id == str(ident)).with_for_update())
    device = db.get(Device, job.payload.get("device_id")) if job else None
    profile = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == device.participant_id)) if device else None
    if not job or job.kind not in ("reprocess", "school_mobility") or not profile or profile.institution_id != mem.institution_id:
        raise HTTPException(404, "Agregado no disponible")
    if job.state != "failed":
        raise HTTPException(409, "Solo se reintentan procesos fallidos")
    job.state = "queued"
    job.attempts = 0
    job.lease_until = None
    audit(db, actor["id"], "school.aggregate_retry", job.id)
    return {"id": job.id, "state": job.state}
