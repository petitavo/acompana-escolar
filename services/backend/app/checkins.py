"""Cuestionarios breves para el piloto.

- PHQ2_SEMANAL: ítems 1 y 2 del PHQ-9 (mismo texto y opciones), cada 7 días.
- CONTACTO_DIARIO: una pregunta de un toque sobre contacto social del día.
- CONTEXTO_MENSUAL: tres preguntas adaptadas de la Encuesta Mundial de Salud Escolar
  (GSHS): acoso escolar, apoyo de los padres y amigos cercanos.

Ninguno reemplaza al PHQ-9 ni abre casos automáticamente: se guardan para validar el
piloto y como variables de contexto del modelo. La pregunta 9 y el botón de ayuda siguen
siendo las vías de alerta inmediata.
"""
from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field, AwareDatetime, StrictInt
from sqlalchemy import select
from .db import now, utc
from .school_db import CheckIn, Institution
from .school_core import student_actor, settings
from .school_schemas import Strict
from .security import identity, database, once, audit
from .phq9 import PHQ9

router = APIRouter(prefix="/api/v1/school/me/check-ins", tags=["Cuestionarios breves"])

_PHQ_OPTIONS = PHQ9["options"]

CHECKINS = {
    "PHQ2_SEMANAL": {
        "instrument_id": "PHQ2_SEMANAL",
        "kind": "checkin",
        "title": "Revisión breve (2 preguntas)",
        "version": "phq2-aetc-2016-es-1",
        "setting": "phq2_weekly_enabled",
        "cadence_days": 7,
        "recall_days": 14,
        "recall": PHQ9["recall"],
        "questions": [q for q in PHQ9["questions"] if q["id"] in PHQ9["phq2_items"]],
        "options": _PHQ_OPTIONS,
        "provenance": PHQ9["provenance"],
        "notice": "PHQ-2 (Kroenke et al., 2003) con su periodo validado de 2 semanas. Se ofrece en la semana intermedia entre dos PHQ-9 (nunca en los 7 días posteriores a uno). Solo para seguimiento del piloto; no abre casos.",
    },
    "CONTACTO_DIARIO": {
        "instrument_id": "CONTACTO_DIARIO",
        "kind": "checkin",
        "title": "Pregunta del día",
        "version": "contacto-diario-1",
        "setting": "daily_social_enabled",
        "cadence_days": 1,
        "recall_days": 1,
        "recall": "Piensa solo en el día de hoy.",
        "questions": [{"id": "social", "text": "Hoy, ¿cuánto tiempo pasaste conversando o compartiendo con otras personas (en persona, por llamada o mensajes)?"}],
        "options": [
            {"value": 0, "label": "Nada"},
            {"value": 1, "label": "Muy poco"},
            {"value": 2, "label": "Algo"},
            {"value": 3, "label": "Bastante"},
            {"value": 4, "label": "Mucho"},
        ],
        "provenance": "Escala de un ítem inspirada en el reporte diario de contacto social del College Experience Study (Nepal et al., 2024).",
        "notice": "Pregunta de validación del piloto; no abre casos.",
    },
    "CONTEXTO_MENSUAL": {
        "instrument_id": "CONTEXTO_MENSUAL",
        "kind": "checkin",
        "title": "Tres preguntas sobre tu entorno",
        "version": "gshs-contexto-1",
        "setting": "context_questions_enabled",
        "cadence_days": 30,
        "recall_days": 30,
        "recall": "Piensa en los últimos 30 días.",
        "questions": [
            {"id": "bullying", "text": "Durante los últimos 30 días, ¿cuántos días te molestaron, insultaron o acosaron otros estudiantes?",
             "options": [{"value": 0, "label": "Ningún día"}, {"value": 1, "label": "1 o 2 días"}, {"value": 2, "label": "3 a 5 días"}, {"value": 3, "label": "6 a 9 días"}, {"value": 4, "label": "10 a 19 días"}, {"value": 5, "label": "20 días o más"}]},
            {"id": "parents", "text": "Durante los últimos 30 días, ¿con qué frecuencia tus padres o apoderados entendieron tus problemas y preocupaciones?",
             "options": [{"value": 0, "label": "Nunca"}, {"value": 1, "label": "Rara vez"}, {"value": 2, "label": "A veces"}, {"value": 3, "label": "Casi siempre"}, {"value": 4, "label": "Siempre"}]},
            {"id": "friends", "text": "¿Cuántos amigos o amigas cercanos tienes?",
             "options": [{"value": 0, "label": "Ninguno"}, {"value": 1, "label": "1"}, {"value": 2, "label": "2"}, {"value": 3, "label": "3 o más"}]},
        ],
        "options": [],
        "provenance": "Adaptado de la Encuesta Mundial de Salud Escolar (GSHS, OMS/CDC), preguntas de acoso, apoyo familiar y amistades.",
        "notice": "Contexto escolar y social; no abre casos.",
    },
}


def options_for(definition, question):
    return question.get("options") or definition["options"]


def enabled(cfg, code):
    return bool(cfg.get(CHECKINS[code]["setting"]))


def last_phq9_at(db, p):
    from .db import Response
    from .phq9 import ensure_phq9
    form = ensure_phq9(db)
    row = db.scalar(select(Response).where(Response.participant_id == p.participant_id, Response.instrument_id == form.id).order_by(Response.created_at.desc()))
    return utc(row.detail.get("applied_at", row.created_at)) if row else None


def due(db, p, cfg, code):
    if code == "PHQ2_SEMANAL":
        # Repetiría los ítems 1 y 2 del PHQ-9 recién respondido: esperar una semana.
        previous = last_phq9_at(db, p)
        if previous is None or previous + timedelta(days=7) - timedelta(hours=12) > now():
            return False
    last = db.scalar(select(CheckIn).where(CheckIn.participant_id == p.participant_id, CheckIn.code == code).order_by(CheckIn.applied_at.desc()))
    if not last:
        return True
    days = CHECKINS[code]["cadence_days"] if code != "CONTEXTO_MENSUAL" else max(cfg["cadence_days"], 28)
    if days == 1:
        # Pregunta diaria: una vez por día calendario en la zona del colegio.
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(cfg.get("timezone", "America/Lima"))
        return utc(last.applied_at).astimezone(zone).date() < now().astimezone(zone).date()
    return utc(last.applied_at) + timedelta(days=days) - timedelta(hours=12) <= now()


def due_forms(db, p, cfg):
    return [{**{k: v for k, v in CHECKINS[c].items() if k != "setting"}, "submit_path": "/me/check-ins"}
            for c in CHECKINS if enabled(cfg, c) and due(db, p, cfg, c)]


class CheckInAnswer(Strict):
    instrument_code: str = Field(max_length=40)
    instrument_version: str = Field(max_length=40)
    answers: dict[str, StrictInt]
    applied_at: AwareDatetime
    recall_start: AwareDatetime | None = None
    recall_end: AwareDatetime | None = None
    functioning: int | None = None


@router.post("")
def answer(body: CheckInAnswer, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor, True)
    cfg = settings(db.get(Institution, p.institution_id))
    definition = CHECKINS.get(body.instrument_code)
    if not definition or body.instrument_version != definition["version"]:
        raise HTTPException(422, "Cuestionario desconocido o versión anterior; actualiza la app")
    if not enabled(cfg, body.instrument_code):
        raise HTTPException(409, "El equipo no tiene activo este cuestionario")
    if body.applied_at > now() + timedelta(minutes=5) or body.applied_at < now() - timedelta(days=7):
        raise HTTPException(422, "Fecha de aplicación inválida")
    expected = {q["id"]: {o["value"] for o in options_for(definition, q)} for q in definition["questions"]}
    if set(body.answers) != set(expected) or any(v not in expected[k] for k, v in body.answers.items()):
        raise HTTPException(422, "Responde todas las preguntas con una opción válida")

    def apply():
        if not due(db, p, cfg, body.instrument_code):
            raise HTTPException(409, "Ya respondiste este cuestionario en este período")
        total = sum(body.answers.values())
        row = CheckIn(participant_id=p.participant_id, code=body.instrument_code, applied_at=body.applied_at, detail={
            "answers": body.answers, "version": definition["version"], "total": total,
            "screening_positive": total >= PHQ9["phq2_threshold"] if body.instrument_code == "PHQ2_SEMANAL" else None,
            "real": not p.is_test})
        db.add(row)
        db.flush()
        audit(db, actor["id"], "school.checkin", row.id)
        return {"received": True, "id": row.id, "message": "Gracias, tu respuesta fue recibida"}
    return once(db, actor, idempotency_key, "school-checkin", body.model_dump(mode="json"), apply)


def history(db, participant_id, limit=200):
    rows = db.scalars(select(CheckIn).where(CheckIn.participant_id == participant_id).order_by(CheckIn.applied_at.desc()).limit(limit))
    return [{"id": r.id, "code": r.code, "title": CHECKINS.get(r.code, {}).get("title", r.code), "applied_at": utc(r.applied_at).isoformat(), **r.detail} for r in rows]
