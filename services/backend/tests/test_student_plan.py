from datetime import timedelta
from types import SimpleNamespace

from app.db import SessionLocal, Participant, now
from app.school_db import CheckIn, Institution
from app.school_core import settings
from app.checkins import student_plan


def _participant(db):
    p = Participant(pseudonym="PLAN-TEST")
    db.add(p)
    db.flush()
    return SimpleNamespace(participant_id=p.id)


def test_plan_lists_enabled_forms_in_order_with_next_dates():
    cfg = settings(Institution(name="x", settings={
        "instrument_enabled": True, "cadence_days": 14,
        "phq2_weekly_enabled": True, "daily_social_enabled": True, "context_questions_enabled": False,
    }))
    with SessionLocal.begin() as db:
        p = _participant(db)
        plan = student_plan(db, p, cfg, None)
        assert [i["code"] for i in plan] == ["PHQ9", "PHQ2_SEMANAL", "CONTACTO_DIARIO"]
        assert plan[0]["questions"] == 9 and plan[0]["next_at"] is None
        # Mientras el PHQ-9 está pendiente, la pregunta del día espera a que se responda.
        assert plan[2]["after_phq9"] is True
        # El alumno nunca recibe puntajes ni etiquetas clínicas en el plan.
        assert all(set(i) <= {"code", "title", "why", "questions", "every_days", "next_at", "after_phq9"} for i in plan)

        db.add(CheckIn(participant_id=p.participant_id, code="CONTACTO_DIARIO", applied_at=now(), detail={}))
        db.flush()
        later = student_plan(db, p, cfg, now() + timedelta(days=14))
        daily = [i for i in later if i["code"] == "CONTACTO_DIARIO"][0]
        assert daily["next_at"] is not None and daily["after_phq9"] is False


def test_plan_is_empty_when_nothing_is_enabled():
    cfg = settings(Institution(name="x", settings={}))
    with SessionLocal.begin() as db:
        assert student_plan(db, _participant(db), cfg, None) == []
