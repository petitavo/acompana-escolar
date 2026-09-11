from sqlalchemy import select
from .db import *
from .security import audit


def add_reason(db, pid, kind, detail, actor="worker"):
    db.scalar(select(Participant).where(Participant.id == pid).with_for_update())
    case = db.scalar(
        select(Case)
        .where(Case.participant_id == pid, Case.state != "closed")
        .order_by(Case.created_at.desc())
    )
    if not case:
        case = Case(participant_id=pid)
        db.add(case)
        db.flush()
        db.add(
            CaseEvent(
                case_id=case.id,
                actor=actor,
                kind="notification_created",
                detail={"delivery": "panel", "acknowledgement_due_hours": 24},
            )
        )
    reason = db.scalar(
        select(Reason).where(
            Reason.case_id == case.id, Reason.kind == kind, Reason.active == True
        )
    )
    if not reason:
        reason = Reason(case_id=case.id, kind=kind, detail=detail)
        db.add(reason)
    db.add(
        CaseEvent(
            case_id=case.id,
            actor=actor,
            kind="evidence_added",
            detail={"reason": kind, "evidence": detail},
        )
    )
    audit(db, actor, "case.evidence", case.id)
    db.flush()
    from .school_core import notify_case
    notify_case(db, case, kind, detail.get("response_id") or reason.id)
    return case


def case_view(db, case, detail=False):
    participant = db.get(Participant, case.participant_id)
    result = {
        **public(case),
        "pseudonym": participant.pseudonym,
        "group": participant.group,
        "reasons": [
            public(r)
            for r in db.scalars(select(Reason).where(Reason.case_id == case.id))
        ],
    }
    response = db.scalar(
        select(Response)
        .where(Response.participant_id == participant.id)
        .order_by(Response.created_at.desc())
    )
    result["last_questionnaire"] = response.detail["applied_at"] if response else None
    evaluation = db.scalar(
        select(Evaluation)
        .where(Evaluation.participant_id == participant.id)
        .order_by(Evaluation.cutoff.desc())
    )
    result["quality"] = (
        "sufficient" if evaluation and evaluation.detail.get("eligible") else "partial"
    )
    if detail:
        result["events"] = [
            public(e)
            for e in db.scalars(
                select(CaseEvent)
                .where(CaseEvent.case_id == case.id)
                .order_by(CaseEvent.created_at)
            )
        ]
    return result
