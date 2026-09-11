"""Student-owned response history. Corrections append; originals and safety reasons survive."""
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field
from sqlalchemy import select
from .db import Response, Participant, now, utc
from .school_db import Institution, DatasetRecord, ModelRecord, Prediction
from .school_core import student_actor, authorization_status
from .school_schemas import Strict
from .security import identity, database, once, audit
from .phq9 import PHQ9
from .forms import score
from .cases import add_reason

router = APIRouter(prefix="/api/v1/school/me/questionnaires", tags=["Historial de respuestas"])


class Correction(Strict):
    answers: dict[str, int]
    functioning: int | None = Field(default=None, ge=0, le=3)
    reason: str = Field(min_length=3, max_length=500)


def response_root(row):
    return row.detail.get("root_response_id", row.id)


def current_responses(rows):
    latest = {}
    for row in sorted(rows, key=lambda r: (int(r.detail.get("revision", 1)), utc(r.created_at), r.id)):
        latest[response_root(row)] = row
    return list(latest.values())


def invalidate_response_dependents(db, institution_id, response_ids):
    """Keep immutable files and measured metrics; withdraw their eligibility, not their history."""
    ids = set(response_ids)
    for ds in db.scalars(select(DatasetRecord).where(DatasetRecord.institution_id == institution_id)):
        provenance = ds.manifest.get("label_provenance", {})
        if not ids.intersection(provenance):
            continue
        ds.manifest = {**ds.manifest, "invalidated_at": now().isoformat(),
                       "invalidation_reason": "source_response_corrected"}
        for model in db.scalars(select(ModelRecord).where(ModelRecord.dataset_id == ds.id)):
            model.state = "retired"
            model.decisions = [*model.decisions, {"at": now().isoformat(), "state": "retired",
                                "rationale": "Una respuesta fuente fue corregida; reconstruya y evalúe otra versión"}]
            for pred in db.scalars(select(Prediction).where(Prediction.model_id == model.id)):
                pred.detail = {**pred.detail, "invalidated_at": now().isoformat(),
                               "invalidation_reason": "source_response_corrected"}


@router.get("/history")
def history(actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    rows = list(db.scalars(select(Response).where(Response.participant_id == p.participant_id)
                           .order_by(Response.created_at.desc()).limit(300)))
    current = {r.id for r in current_responses(rows)}
    # Only the student's own answers. Never total, clinical notes, model estimates or thresholds.
    return [{"id": r.id, "root_response_id": response_root(r), "revision": r.detail.get("revision", 1),
             "current": r.id in current, "received_at": utc(r.created_at).isoformat(),
             "applied_at": r.detail.get("applied_at"), "recall_start": r.detail.get("recall_start"),
             "recall_end": r.detail.get("recall_end"), "instrument": r.detail.get("instrument_code"),
             "instrument_version": r.detail.get("instrument_version"), "answers": r.detail.get("answers", {}),
             "functioning": r.detail.get("functioning"), "correction_reason": r.detail.get("correction_reason"),
             "definition": {k: PHQ9[k] for k in ("title", "recall", "questions", "options", "functioning", "version", "instrument_id")},
             "state": "received", "can_correct": r.id in current and r.detail.get("definition_sha256") == PHQ9["definition_sha256"]}
            for r in rows]


@router.post("/{ident}/corrections")
def correct(ident: UUID, body: Correction, actor=Depends(identity), db=Depends(database),
            idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor, True)
    db.scalars(select(Institution).where(Institution.id == p.institution_id).with_for_update()).one()
    db.scalars(select(Participant).where(Participant.id == p.participant_id).with_for_update()).one()
    db.refresh(p)
    student_actor(db, actor, True)  # Recheck authorization after acquiring the writer locks.
    original = db.get(Response, str(ident))
    if not original or original.participant_id != p.participant_id:
        raise HTTPException(404, "Respuesta no disponible")

    def apply():
        all_rows = list(db.scalars(select(Response).where(Response.participant_id == p.participant_id)))
        if original.id not in {r.id for r in current_responses(all_rows)}:
            raise HTTPException(409, "Hay una versión más reciente; actualice el historial")
        if original.detail.get("definition_sha256") != PHQ9["definition_sha256"]:
            raise HTTPException(409, "La versión del instrumento requiere revisión del equipo")
        total, _, rules = score(PHQ9, body.answers)
        if total and body.functioning is None:
            raise HTTPException(422, "Complete la pregunta de funcionamiento")
        root = response_root(original)
        row = Response(participant_id=p.participant_id, instrument_id=original.instrument_id,
            detail={**original.detail, "answers": body.answers, "functioning": body.functioning,
                    "total": total, "root_response_id": root, "supersedes": original.id,
                    "revision": int(original.detail.get("revision", 1)) + 1,
                    "correction_reason": body.reason.strip(), "corrected_at": now().isoformat(),
                    "authorization_snapshot": authorization_status(db, p)})
        db.add(row); db.flush()
        invalidate_response_dependents(db, p.institution_id, [r.id for r in all_rows if response_root(r) == root])
        if total >= PHQ9["review_threshold"]:
            add_reason(db, p.participant_id, "questionnaire_review", {"response_id": row.id,
                       "total": total, "correction_of": original.id}, actor["id"])
        if "safety_review" in rules:
            add_reason(db, p.participant_id, "safety_review", {"response_id": row.id, "item": "q9",
                       "correction_of": original.id}, actor["id"])
        # Never resolve an existing safety reason automatically, even if the new answer is zero.
        audit(db, actor["id"], "school.questionnaire_corrected", row.id)
        return {"received": True, "response_id": row.id, "revision": row.detail["revision"],
                "message": "Corrección recibida. Conservamos la respuesta original y su historial."}
    return once(db, actor, idempotency_key, "school-questionnaire-correction:" + str(ident), body.model_dump(), apply)
