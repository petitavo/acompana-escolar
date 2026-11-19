from datetime import timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from .db import Assignment, Device, Interval, Participant, User, now, utc, public
from .school_db import Institution, Membership, StudentProfile, Authorization, Notification, CaseGrant
from .config import MODE, PILOT_ENABLED
from .security import require, audit


def settings(institution):
    return {
        "timezone": "America/Lima", "document_version": "participacion-v1",
        "participation_document": "El responsable de la institución debe registrar aquí la información de participación, los datos, la finalidad y los derechos antes de invitar estudiantes.",
        "purpose": "Acompañamiento y revisión profesional de bienestar escolar.",
        "coverage": "Horario y recursos de apoyo pendientes de configuración por el equipo.",
        "days": [0, 1, 2, 3, 4], "opens": "08:00", "closes": "17:00",
        "resources": [], "primary_id": None, "backup_id": None,
        "acknowledgement_minutes": 1440, "safety_minutes": 60, "escalation_minutes": 60,
        "instrument_enabled": False, "professional_decision": "", "cadence_days": 14,
        "minimum_group": 10, "external_notifications_authorized": False,
        "raw_location_retention_days": 7, "location_interval_minutes": 15,
        "location_distance_meters": 100,
        # Piloto: cuestionarios breves (apagados hasta que el equipo los active).
        "phq2_weekly_enabled": False, "daily_social_enabled": False, "context_questions_enabled": False,
        # Cambio de conducta: se muestra en el panel como información; solo abre caso si se activa.
        "behavior_change_alerts": False,
        # Asistencia por GPS: zona del colegio y horario de clases (lunes=0).
        "school_zone": None, "school_days": [0, 1, 2, 3, 4], "school_start": "07:30", "school_end": "13:30",
        **institution.settings,
    }


def school_zone(cfg):
    """Zona y horario del colegio que el teléfono usa para estimar asistencia. No es dato personal."""
    z = cfg.get("school_zone")
    if not z:
        return None
    return {"latitude": z["latitude"], "longitude": z["longitude"], "radius_m": z.get("radius_m", 150),
            "days": cfg["school_days"], "start": cfg["school_start"], "end": cfg["school_end"],
            "timezone": cfg.get("timezone", "America/Lima")}


def member(db, actor, *roles):
    require(actor, *(roles or ("admin", "director", "psychologist", "practitioner", "researcher")))
    row = db.scalar(select(Membership).where(Membership.user_id == actor["id"], Membership.active == True))
    if not row:
        raise HTTPException(403, "Cuenta sin institución activa")
    return row


def profile(db, pid):
    row = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == str(pid)))
    if not row:
        raise HTTPException(404, "Estudiante no disponible")
    return row


def access(db, actor, pid, purpose="clinical"):
    p = profile(db, pid)
    m = member(db, actor)
    if p.institution_id != m.institution_id:
        raise HTTPException(404, "Estudiante no disponible")
    if purpose == "administration":
        require(actor, "admin", "director")
    elif purpose in ("diagnostics", "raw_location"):
        require(actor, "admin", "researcher")
        if "diagnostics" not in actor["scopes"] or purpose == "raw_location" and "raw_location" not in actor["scopes"]:
            raise HTTPException(403, "Falta permiso específico de diagnóstico")
        if not p.is_test and not p.policy.get("research_access"):
            raise HTTPException(403, "El participante no autorizó acceso de investigación")
        if purpose == "raw_location" and not p.policy.get("raw_location_upload"):
            raise HTTPException(403, "No se comparten coordenadas crudas")
    else:
        require(actor, "psychologist", "practitioner")
        owners = [actor["id"]]
        if actor["role"] == "practitioner":
            supervisor = db.scalar(select(Membership).where(Membership.user_id == m.supervisor_id, Membership.active == True))
            if not supervisor or supervisor.institution_id != m.institution_id:
                raise HTTPException(403, "Practicante sin supervisión activa")
            # Both practitioner and supervisor must be explicitly assigned.
            if not db.scalar(select(Assignment).where(Assignment.user_id == m.supervisor_id, Assignment.participant_id == p.participant_id)):
                raise HTTPException(404, "Estudiante no disponible")
        if not db.scalar(select(Assignment).where(Assignment.user_id.in_(owners), Assignment.participant_id == p.participant_id)):
            raise HTTPException(404, "Estudiante no disponible")
    return p


# --- A03: scoped, time-boxed access to a *single escalated case* -----------------
# A case grant never widens into general access to the student. It authorizes work
# on one case id only: find it in the queue, open it, acknowledge / plan contact /
# close it. It does not authorize the clinical profile, the individual report,
# mobility, predictions, or any other case (past or present) of the same student.
GRANT_MINUTES = 14 * 24 * 60  # a fixed window; never extended on maintenance ticks


def active_case_grant(db, user_id, case_id):
    return db.scalar(select(CaseGrant).where(
        CaseGrant.user_id == user_id,
        CaseGrant.case_id == str(case_id),
        CaseGrant.revoked_at == None,
        CaseGrant.expires_at > now(),
    ))


def granted_case_ids(db, user_id):
    return [g.case_id for g in db.scalars(select(CaseGrant).where(
        CaseGrant.user_id == user_id, CaseGrant.revoked_at == None, CaseGrant.expires_at > now()))]


def case_scope(db, actor, case, write=False):
    """Return 'assigned' or 'escalation' for a case; raise 404 otherwise.

    'escalation' is a backup psychologist acting on this one escalated case."""
    require(actor, "psychologist", "practitioner")
    p = profile(db, case.participant_id)
    m = member(db, actor)
    if p.institution_id != m.institution_id:
        raise HTTPException(404, "Caso no disponible")
    try:
        access(db, actor, case.participant_id, "clinical")
        return "assigned"
    except HTTPException:
        pass
    if actor["role"] == "psychologist" and active_case_grant(db, actor["id"], case.id):
        audit(db, actor["id"], "school.backup_case_" + ("write" if write else "read"), case.id)
        return "escalation"
    raise HTTPException(404, "Caso no disponible")


def grant_case_access(db, case, user_id, reason="escalation"):
    """Idempotent: one grant per (case, user, reason). A live grant is returned
    unchanged — its window is fixed and NOT pushed forward on repeated maintenance
    runs. A previously revoked grant for a returning backup is reinstated with a
    fresh fixed window (that is a new decision, not an unbounded extension)."""
    existing = db.scalar(select(CaseGrant).where(CaseGrant.case_id == case.id, CaseGrant.user_id == user_id, CaseGrant.reason == reason))
    if existing:
        if existing.revoked_at is not None:
            existing.revoked_at = None
            existing.expires_at = now() + timedelta(minutes=GRANT_MINUTES)
            audit(db, "worker", "school.case_grant_reinstated", case.id)
        return existing
    grant = CaseGrant(case_id=case.id, participant_id=case.participant_id, user_id=user_id, reason=reason, expires_at=now() + timedelta(minutes=GRANT_MINUTES))
    db.add(grant)
    db.flush()
    audit(db, "worker", "school.case_grant_created", case.id)
    return grant


def revoke_case_grants(db, case_id, user_id=None, reason=None):
    q = select(CaseGrant).where(CaseGrant.case_id == str(case_id), CaseGrant.revoked_at == None)
    if user_id:
        q = q.where(CaseGrant.user_id == user_id)
    if reason:
        q = q.where(CaseGrant.reason == reason)
    for grant in db.scalars(q):
        grant.revoked_at = now()
        audit(db, "worker", "school.case_grant_revoked", str(case_id))


def revoke_user_backup_grants(db, user_id):
    """The institution replaced this backup: end every escalation grant they hold."""
    for grant in db.scalars(select(CaseGrant).where(
        CaseGrant.user_id == str(user_id), CaseGrant.reason == "escalation", CaseGrant.revoked_at == None)):
        grant.revoked_at = now()
        audit(db, "worker", "school.case_grant_revoked", grant.case_id)


def revoke_stale_escalation_grants(db, case_id, keep_user_id):
    """Drop escalation grants for a case held by anyone other than the current backup."""
    for grant in db.scalars(select(CaseGrant).where(
        CaseGrant.case_id == str(case_id), CaseGrant.reason == "escalation",
        CaseGrant.user_id != keep_user_id, CaseGrant.revoked_at == None)):
        grant.revoked_at = now()
        audit(db, "worker", "school.case_grant_revoked", str(case_id))


def authorization_status(db, p):
    cfg = settings(db.get(Institution, p.institution_id))
    current = cfg["document_version"]
    rows = list(db.scalars(select(Authorization).where(Authorization.participant_id == p.participant_id, Authorization.version == current).order_by(Authorization.created_at)))
    latest = {r.kind: r for r in rows}
    accepted = lambda k: k in latest and latest[k].detail.get("accepted") is True
    guardian = accepted("guardian") if p.minor else True
    student = accepted("assent") if p.minor else accepted("consent")
    verified = bool(db.scalar(select(Authorization.id).where(Authorization.participant_id == p.participant_id, Authorization.kind == "verification")))
    withdrawn = db.get(Participant, p.participant_id).status == "revoked"
    ready = verified and guardian and student and not withdrawn
    return {"version": current, "verified": verified, "guardian": guardian, "student": student, "ready": ready, "withdrawn": withdrawn, "minor": p.minor}


def student_actor(db, actor, require_ready=False):
    require(actor, "participant")
    p = profile(db, actor["device"].participant_id)
    if db.get(Participant, p.participant_id).status == "revoked":
        raise HTTPException(403, "La participación fue retirada")
    state = authorization_status(db, p)
    if require_ready and not state["ready"]:
        raise HTTPException(409, "Complete las autorizaciones de la versión vigente")
    if require_ready and not p.is_test and not PILOT_ENABLED:
        raise HTTPException(409, "El piloto real aún no está habilitado por la institución")
    return p


def sensor_allowed(db, d, kind, at=None):
    p = profile(db, d.participant_id)
    if not authorization_status(db, p)["ready"] or (not p.is_test and not PILOT_ENABLED) or d.status != "active" or not p.policy.get(kind):
        return False
    if at is not None:
        moment = utc(at)
        if not any(utc(i.start_at) <= moment and (i.end_at is None or moment < utc(i.end_at)) for i in db.scalars(select(Interval).where(Interval.device_id == d.id))):
            return False
        since = p.policy.get(kind + "_since")
        if not since or moment < utc(since):
            return False
    return True


def safe_profile(db, p):
    policy = {k: v for k, v in p.policy.items() if k not in ("home_zone", "guardian_channel")}
    return {**public(p), "policy": policy, "authorization": authorization_status(db, p)}


def notify(db, recipient, key, kind, title, detail=None, due=None):
    existing = db.scalar(select(Notification).where(Notification.dedupe_key == key))
    if existing:
        return existing
    n = Notification(recipient_id=recipient, dedupe_key=key, kind=kind, title=title, detail=detail or {}, due_at=due or now())
    db.add(n)
    db.flush()
    return n


def notify_case(db, case, kind, evidence_id):
    if MODE != "REAL":
        return
    p = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == case.participant_id))
    if not p:
        return
    cfg = settings(db.get(Institution, p.institution_id))
    owners = list(db.scalars(select(Assignment.user_id).join(User, User.id == Assignment.user_id).where(Assignment.participant_id == p.participant_id, User.role == "psychologist")))
    if not owners and cfg.get("primary_id"):
        owners = [cfg["primary_id"]]
    for owner in owners:
        notify(db, owner, f"case:{case.id}:{kind}:{evidence_id}:{owner}", "case", "Tienes una revisión pendiente", {"case_id": case.id, "reason_kind": kind, "ack_due_at": (now() + timedelta(minutes=cfg["safety_minutes"] if kind == "safety_review" else cfg["acknowledgement_minutes"])).isoformat(), "institution_id": p.institution_id})


def analysis_cutoff(cfg, at=None):
    """Separate event-day closure from actual availability of computed aggregates."""
    from datetime import timedelta
    instant = at or now()
    local = instant.astimezone(ZoneInfo(cfg["timezone"]))
    closed = local.date() - timedelta(days=1 if local.hour >= 9 else 2)
    return instant, closed


def coverage_now(cfg, at=None):
    local = (at or now()).astimezone(ZoneInfo(cfg["timezone"]))
    return {"open": local.weekday() in cfg["days"] and cfg["opens"] <= local.strftime("%H:%M") < cfg["closes"], "text": cfg["coverage"], "resources": cfg["resources"], "notice": "La recepción de una respuesta no significa atención inmediata. Consulta el horario del equipo."}
