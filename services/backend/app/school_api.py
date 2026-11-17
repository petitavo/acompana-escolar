"""School product API. Every staff record is institution- and assignment-scoped."""
import csv
import io
import json
import secrets
from datetime import timedelta, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, update, or_, delete
from .db import *
from .school_db import *
from .school_schemas import *
from .school_core import *
from .security import database, identity, digest, hasher, once, audit, require
from .config import MODE, PILOT_ENABLED
from .forms import score
from .phq9 import PHQ9, ensure_phq9, phq2
from .cases import add_reason, case_view

router = APIRouter(prefix="/api/v1/school", tags=["Producto escolar"])


def institutional(db, actor, *roles):
    m = member(db, actor, *roles)
    return db.get(Institution, m.institution_id)


@router.get("/bootstrap")
def bootstrap_status(actor=Depends(identity), db=Depends(database)):
    require(actor, "admin", "director", "psychologist", "practitioner", "researcher")
    m = db.scalar(select(Membership).where(Membership.user_id == actor["id"], Membership.active == True))
    return {"configured": m is not None, "role": actor["role"], "scopes": actor["scopes"], "institution": public(db.get(Institution, m.institution_id)) if m and actor["role"] in ("admin", "psychologist") else {"name": db.get(Institution, m.institution_id).name} if m else None, "pilot_enabled": PILOT_ENABLED, "mode": MODE}


@router.post("/setup")
def setup(body: Setup, actor=Depends(identity), db=Depends(database)):
    require(actor, "admin")
    if db.scalar(select(Membership).where(Membership.user_id == actor["id"])):
        raise HTTPException(409, "Esta cuenta ya tiene una institución")
    institution = Institution(name=body.name, settings={"timezone": body.timezone})
    db.add(institution)
    db.flush()
    db.add(Membership(user_id=actor["id"], institution_id=institution.id))
    ensure_phq9(db)
    audit(db, actor["id"], "school.setup", institution.id)
    return public(institution)


@router.get("/settings")
def get_settings(actor=Depends(identity), db=Depends(database)):
    institution = institutional(db, actor, "admin", "psychologist")
    return {"id": institution.id, "name": institution.name, **settings(institution), "instrument": PHQ9, "pilot_enabled": PILOT_ENABLED}


@router.put("/settings")
def put_settings(body: Settings, actor=Depends(identity), db=Depends(database)):
    institution = institutional(db, actor, "admin", "psychologist")
    # A08: settings changes (document version, backup) must serialise against
    # in-flight inference/maintenance that also lock the institution row.
    db.scalar(select(Institution).where(Institution.id == institution.id).with_for_update().execution_options(populate_existing=True))
    old = settings(institution)
    value = body.model_dump(mode="json")
    if body.instrument_enabled:
        defaults = settings(Institution(name="defaults", settings={}))
        if any(value[k] == defaults[k] for k in ("participation_document", "purpose", "coverage")):
            raise HTTPException(422, "Complete la información de participación, finalidad y cobertura antes de habilitar el instrumento")
    for owner in (body.primary_id, body.backup_id):
        if owner and not db.scalar(select(Membership).join(User, Membership.user_id == User.id).where(Membership.institution_id == institution.id, Membership.user_id == str(owner), Membership.active == True, User.role == "psychologist")):
            raise HTTPException(422, "Responsable y suplente deben ser psicólogos activos de esta institución")
    document_changed = old["participation_document"] != value["participation_document"] or old["purpose"] != value["purpose"]
    if document_changed and old["document_version"] == value["document_version"] and db.scalar(select(StudentProfile.id).where(StudentProfile.institution_id == institution.id)):
        raise HTTPException(409, "Cambie la versión del documento para renovar las autorizaciones")
    institution.settings = {"timezone": old["timezone"], **value}
    ensure_phq9(db)
    if str(old.get("backup_id")) != str(value.get("backup_id")):
        # A03: the previous backup is no longer authorised for any escalated case.
        from .school_core import revoke_user_backup_grants
        if old.get("backup_id"):
            revoke_user_backup_grants(db, str(old["backup_id"]))
    if old["document_version"] != value["document_version"]:
        for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == institution.id)):
            for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id, Device.status != "revoked")):
                d.status = "paused"
                for interval in db.scalars(select(Interval).where(Interval.device_id == d.id, Interval.end_at == None)):
                    interval.end_at = now()
                notify(db, d.id, f"renew:{d.id}:{value['document_version']}", "renewal", "Revisa la nueva información de participación")
            # A08: predictions must be re-earned under the renewed authorization;
            # existing estimates are not silently carried across a version change.
            db.execute(delete(Prediction).where(Prediction.participant_id == p.participant_id))
        audit(db, actor["id"], "school.predictions_invalidated_by_renewal", institution.id)
    audit(db, actor["id"], "school.settings", institution.id)
    return {"saved": True, "renewal_required": old["document_version"] != value["document_version"]}


@router.get("/accounts")
def accounts(actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor)
    return [{"id": u.id, "username": u.username, "role": u.role, "scopes": u.scopes if actor["role"] == "admin" else [], "supervisor_id": m.supervisor_id, "active": m.active} for u, m in db.execute(select(User, Membership).join(Membership, Membership.user_id == User.id).where(Membership.institution_id == i.id))]


@router.post("/accounts")
def create_account(body: Account, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin")
    if body.role == "practitioner":
        if not body.supervisor_id or not db.scalar(select(User).join(Membership, Membership.user_id == User.id).where(User.id == str(body.supervisor_id), User.role == "psychologist", Membership.institution_id == i.id, Membership.active == True)):
            raise HTTPException(422, "Seleccione un psicólogo supervisor de la institución")
    if body.role not in ("researcher", "admin") and body.scopes:
        raise HTTPException(422, "Los permisos técnicos son independientes del rol escolar")
    u = User(username=body.username, role=body.role, password_hash=hasher.hash(body.password), scopes=body.scopes)
    db.add(u)
    db.flush()
    db.add(Membership(user_id=u.id, institution_id=i.id, supervisor_id=str(body.supervisor_id) if body.supervisor_id else None))
    audit(db, actor["id"], "school.account_created", u.id)
    return {"id": u.id, "username": u.username, "role": u.role}


@router.post("/accounts/{ident}/disable")
def disable_account(ident: UUID, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin")
    m = db.scalar(select(Membership).where(Membership.user_id == str(ident), Membership.institution_id == i.id))
    if not m or m.user_id == actor["id"]:
        raise HTTPException(409, "No se puede desactivar esta cuenta")
    m.active = False
    for s in db.scalars(select(Session).where(Session.user_id == m.user_id)):
        s.revoked = True
    audit(db, actor["id"], "school.account_disabled", m.user_id)
    return {"disabled": True}


@router.get("/classrooms")
def classrooms(actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor)
    return [public(c) for c in db.scalars(select(Classroom).where(Classroom.institution_id == i.id).order_by(Classroom.period, Classroom.grade, Classroom.name))]


@router.post("/classrooms")
def create_classroom(body: ClassroomInput, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin", "director")
    c = Classroom(institution_id=i.id, **body.model_dump())
    db.add(c)
    db.flush()
    audit(db, actor["id"], "school.classroom_created", c.id)
    return public(c)


# Código de acceso del estudiante: 8 caracteres sin letras/números que se confundan
# (0/O, 1/I/L). 31^8 ≈ 8.5e11 combinaciones; un solo uso, vence en 7 días y /enroll
# limita los intentos fallidos.
ACCESS_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def access_code():
    raw = "".join(secrets.choice(ACCESS_ALPHABET) for _ in range(8))
    return raw[:4] + "-" + raw[4:]


def normalize_access(value):
    return "".join(c for c in value.upper() if c.isalnum())


def make_link(db, p, purpose, version, channel=""):
    token = access_code() if purpose == "student" else secrets.token_urlsafe(32)
    code = str(secrets.randbelow(90000000) + 10000000)
    link = AccessLink(participant_id=p.participant_id, token_hash=digest(normalize_access(token) if purpose == "student" else token), purpose=purpose, expires_at=now() + timedelta(days=7), detail={"code_hash": digest(code), "version": version, "channel": channel, "delivery": "operator_pending", "failed_attempts": 0})
    db.add(link)
    db.flush()
    return {"id": link.id, "token": token, "verification_code": code, "expires_at": link.expires_at.isoformat(), "delivery": "Pendiente de entrega individual por el operador; código por canal separado"}


def add_student(db, i, body, actor):
    c = db.get(Classroom, str(body.classroom_id))
    if not c or c.institution_id != i.id:
        raise HTTPException(404, "Aula no disponible")
    if not db.scalar(select(Membership).join(User, User.id == Membership.user_id).where(Membership.institution_id == i.id, User.id == str(body.psychologist_id), User.role == "psychologist", Membership.active == True)):
        raise HTTPException(422, "Seleccione un psicólogo de la institución")
    p = Participant(pseudonym="ESC-" + secrets.token_hex(5).upper(), group=c.name)
    db.add(p)
    db.flush()
    s = StudentProfile(participant_id=p.id, institution_id=i.id, classroom_id=c.id, display_name=body.display_name, minor=body.minor, is_test=body.is_test, policy={"usage": False, "location": False, "steps": False, "raw_location_upload": False, "research_access": False, "guardian_channel": body.guardian_channel})
    db.add(s)
    db.flush()
    db.add(Assignment(user_id=str(body.psychologist_id), participant_id=p.id))
    cfg = settings(i)
    invitation = make_link(db, s, "student", cfg["document_version"])
    guardian = make_link(db, s, "guardian", cfg["document_version"], body.guardian_channel) if s.minor else None
    audit(db, actor["id"], "school.student_invited", p.id)
    return {"student": safe_profile(db, s), "invitation": invitation, "guardian": guardian}


@router.post("/students")
def create_student(body: StudentInput, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    i = institutional(db, actor, "admin", "director")
    return once(db, actor, idempotency_key, "school-student", body.model_dump(mode="json"), lambda: add_student(db, i, body, actor))


@router.post("/students/import")
def import_students(body: CsvInput, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    i = institutional(db, actor, "admin", "director")
    reader = csv.DictReader(io.StringIO(body.csv))
    if set(reader.fieldnames or []) != {"name", "minor", "guardian_channel"}:
        raise HTTPException(422, "CSV requiere columnas name,minor,guardian_channel")
    entries = list(reader)
    if not 1 <= len(entries) <= 100:
        raise HTTPException(422, "Importe entre 1 y 100 estudiantes")
    validated = []
    for idx, r in enumerate(entries, 2):
        if r.get("minor") not in ("true", "false") or not r.get("name", "").strip() or None in r:
            raise HTTPException(422, f"Fila {idx}: nombre o minor inválidos")
        validated.append(StudentInput(display_name=r["name"].strip(), minor=r["minor"] == "true", guardian_channel=r["guardian_channel"], classroom_id=body.classroom_id, psychologist_id=body.psychologist_id, is_test=body.is_test))
    return once(db, actor, idempotency_key, "school-import", body.model_dump(mode="json"), lambda: {"created": [add_student(db, i, v, actor) for v in validated]})


@router.get("/students")
def students(actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor)
    rows = []
    for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == i.id).order_by(StudentProfile.display_name)):
        if actor["role"] in ("psychologist", "practitioner"):
            try:
                access(db, actor, p.participant_id)
            except HTTPException:
                continue
        elif actor["role"] == "researcher" and not p.is_test and not p.policy.get("research_access"):
            continue
        value = safe_profile(db, p)
        value["assignments"] = list(db.scalars(select(Assignment.user_id).where(Assignment.participant_id == p.participant_id)))
        value["status"] = db.get(Participant, p.participant_id).status
        rows.append(value)
    return rows


@router.post("/students/{ident}/assign/{user_id}")
def assign_student(ident: UUID, user_id: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident, "administration")
    m = db.scalar(select(Membership).join(User, User.id == Membership.user_id).where(Membership.user_id == str(user_id), Membership.institution_id == p.institution_id, Membership.active == True, User.role.in_(["psychologist", "practitioner"])))
    if not m:
        raise HTTPException(404, "Profesional no disponible")
    if not db.scalar(select(Assignment).where(Assignment.user_id == str(user_id), Assignment.participant_id == p.participant_id)):
        db.add(Assignment(user_id=str(user_id), participant_id=p.participant_id))
    audit(db, actor["id"], "school.assigned", p.participant_id)
    return {"assigned": True}


@router.post("/students/{ident}/guardian-link")
def renew_guardian(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident, "administration")
    if not p.minor:
        raise HTTPException(409, "El adulto autoriza su propia participación")
    cfg = settings(db.get(Institution, p.institution_id))
    for link in db.scalars(select(AccessLink).where(AccessLink.participant_id == p.participant_id, AccessLink.purpose == "guardian", AccessLink.used == False)):
        link.used = True
    audit(db, actor["id"], "school.guardian_link", p.participant_id)
    return make_link(db, p, "guardian", cfg["document_version"], p.policy.get("guardian_channel", ""))


def checked_link(db, token, purpose, code=None):
    link = db.scalar(select(AccessLink).where(AccessLink.token_hash == digest(token), AccessLink.purpose == purpose).with_for_update())
    if not link or link.used or utc(link.expires_at) <= now() or link.detail.get("failed_attempts", 0) >= 5:
        raise HTTPException(401, "Enlace inválido, usado o vencido")
    if code is not None and not secrets.compare_digest(link.detail["code_hash"], digest(code)):
        link.detail = {**link.detail, "failed_attempts": link.detail.get("failed_attempts", 0) + 1}
        db.commit()
        raise HTTPException(401, "Código de verificación incorrecto")
    return link


@router.get("/guardian/info")
def guardian_info(token: str = Query(min_length=16, max_length=200), db=Depends(database)):
    link = checked_link(db, token, "guardian")
    p = profile(db, link.participant_id)
    cfg = settings(db.get(Institution, p.institution_id))
    return {"student_name": p.display_name, "document_version": cfg["document_version"], "document": cfg["participation_document"], "purpose": cfg["purpose"], "is_test": p.is_test, "channel": "Código individual entregado por la institución; no es el código del estudiante"}


@router.post("/guardian/approve")
def guardian_approve(body: GuardianApproval, db=Depends(database)):
    link = checked_link(db, body.token, "guardian", body.verification_code)
    p = profile(db, link.participant_id)
    db.scalars(select(Participant).where(Participant.id == p.participant_id)
               .with_for_update().execution_options(populate_existing=True)).one()
    cfg = settings(db.get(Institution, p.institution_id))
    if body.document_version != cfg["document_version"] or link.detail["version"] != body.document_version:
        raise HTTPException(409, "Documento actualizado; solicite un enlace nuevo")
    link.used = True
    db.add(Authorization(participant_id=p.participant_id, kind="guardian", version=body.document_version, actor_id=link.id, detail={"accepted": body.accepted, "full_name": body.full_name, "relationship": body.relationship, "identity_reference": body.identity_reference, "channel": link.detail.get("channel"), "verification": "individual_link_and_separate_code", "document": cfg["participation_document"]}))
    receipt = make_link(db, p, "guardian_manage", cfg["document_version"])
    audit(db, link.id, "school.guardian_decision", p.participant_id)
    return {"saved": True, "accepted": body.accepted, "management_token": receipt["token"], "management_expires_at": receipt["expires_at"]}


@router.post("/guardian/withdraw")
def guardian_withdraw(body: dict[str, str], db=Depends(database)):
    if set(body) != {"token"}:
        raise HTTPException(422, "Se requiere el comprobante de autorización")
    link = checked_link(db, body["token"], "guardian_manage")
    p = profile(db, link.participant_id)
    withdraw(db, p, link.id)
    link.used = True
    return {"withdrawn": True}


ENROLL_FAILURES = 20


@router.post("/enroll")
def enroll_student(body: VerifyEnrollment, request: Request, db=Depends(database)):
    short = normalize_access(body.invitation)
    if len(short) == 8 and not body.verification_code:
        # Un solo código: se limita el número de intentos fallidos por origen.
        from .db import LoginAttempt
        key = digest("enroll:" + (request.client.host if request.client else "unknown"))
        attempt = db.get(LoginAttempt, key)
        if attempt and utc(attempt.until) > now() and attempt.count >= ENROLL_FAILURES:
            raise HTTPException(429, "Demasiados intentos. Espera 15 minutos")
        try:
            link = checked_link(db, short, "student")
        except HTTPException:
            if not attempt:
                attempt = LoginAttempt(key=key, count=0, until=now() + timedelta(minutes=15))
                db.add(attempt)
            if utc(attempt.until) < now():
                attempt.count, attempt.until = 0, now() + timedelta(minutes=15)
            attempt.count += 1
            db.commit()
            raise HTTPException(401, "Código incorrecto, usado o vencido. Revísalo o pide uno nuevo al colegio")
        method = "access_code"
    else:
        if not body.verification_code:
            raise HTTPException(422, "Falta el código")
        link = checked_link(db, short if len(short) == 8 else body.invitation, "student", body.verification_code)
        method = "invitation_and_separate_code"
    p = profile(db, link.participant_id)
    if db.get(Participant, p.participant_id).status == "revoked":
        raise HTTPException(409, "Participación retirada")
    link.used = True
    device = Device(participant_id=p.participant_id, detail=body.device.model_dump())
    db.add(device)
    db.flush()
    token = secrets.token_urlsafe(48)
    db.add(Session(device_id=device.id, token_hash=digest(token), csrf="", expires_at=now() + timedelta(days=30)))
    version = settings(db.get(Institution, p.institution_id))["document_version"]
    db.add(Authorization(participant_id=p.participant_id, kind="verification", version=version, actor_id=device.id, detail={"accepted": True, "method": method}))
    audit(db, device.id, "school.enrolled", p.participant_id)
    return {"token": token, "device_id": device.id, "mode": MODE, "pseudonym": db.get(Participant, p.participant_id).pseudonym, "name": p.display_name}


def withdraw(db, p, actor_id):
    # A08: take the participant row lock before flipping status so a concurrent
    # inference blocks here and re-checks eligibility (seeing the withdrawal) before
    # it can persist anything.
    part = db.scalars(select(Participant).where(Participant.id == p.participant_id)
                      .with_for_update().execution_options(populate_existing=True)).one()
    part.status = "revoked"
    for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id)):
        d.status = "revoked"
        for interval in db.scalars(select(Interval).where(Interval.device_id == d.id, Interval.end_at == None)):
            interval.end_at = now()
        for s in db.scalars(select(Session).where(Session.device_id == d.id)):
            s.revoked = True
    cfg = settings(db.get(Institution, p.institution_id))
    db.add(Authorization(participant_id=p.participant_id, kind="withdrawal", version=cfg["document_version"], actor_id=actor_id, detail={"accepted": True}))
    # Individual estimates do not outlive the participation that authorized them.
    db.execute(delete(Prediction).where(Prediction.participant_id == p.participant_id))
    db.add(Job(kind="deletion", actor=actor_id, payload={"participant_id": p.participant_id}))
    audit(db, actor_id, "school.withdrawal", p.participant_id)


@router.post("/students/{ident}/withdraw")
def admin_withdraw(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident, "administration")
    withdraw(db, p, actor["id"])
    return {"withdrawn": True}


@router.get("/me")
def student_home(actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    cfg = settings(db.get(Institution, p.institution_id))
    rows = list(db.scalars(select(Response).where(Response.participant_id == p.participant_id).order_by(Response.created_at.desc()).limit(1)))
    due = utc(rows[0].detail.get("applied_at", rows[0].created_at)) + timedelta(days=cfg["cadence_days"]) if rows else now()
    return {"analysis_timezone": actor["device"].detail.get("timezone", "America/Lima"), "name": p.display_name, "is_test": p.is_test, "authorization": authorization_status(db, p), "policy": {k: v for k, v in p.policy.items() if k not in ("home_zone", "guardian_channel")}, "document": cfg["participation_document"], "purpose": cfg["purpose"], "coverage": coverage_now(cfg), "next_questionnaire": due.isoformat(), "questionnaire_enabled": cfg["instrument_enabled"], "has_home_zone": bool(p.policy.get("home_zone")), "capture_active": actor["device"].status == "active", "pilot_enabled": PILOT_ENABLED or p.is_test, "sampling": {"interval_minutes": cfg["location_interval_minutes"], "distance_meters": cfg["location_distance_meters"]}, "school_zone": school_zone(cfg)}


@router.post("/me/participation")
def student_participation(body: ParticipationInput, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor)
    cfg = settings(db.get(Institution, p.institution_id))
    if body.document_version != cfg["document_version"]:
        raise HTTPException(409, "Lea y acepte la versión vigente")
    if body.occurred_at > now() + timedelta(minutes=5) or body.occurred_at < now() - timedelta(days=7):
        raise HTTPException(422, "Fecha fuera de la ventana permitida")

    def apply():
        d = actor["device"]
        # A08: serialise participation changes (assent/consent/research/withdraw)
        # against a concurrent inference through the participant row lock.
        db.scalars(select(Participant).where(Participant.id == p.participant_id)
                   .with_for_update().execution_options(populate_existing=True)).one()
        if body.action == "withdraw":
            withdraw(db, p, d.id)
            return {"withdrawn": True}
        if body.action in ("assent", "consent"):
            if (p.minor and body.action != "assent") or (not p.minor and body.action != "consent"):
                raise HTTPException(422, "La autorización del adulto responsable usa un enlace separado")
            if p.minor and not authorization_status(db, p)["guardian"]:
                raise HTTPException(409, "Falta la autorización del responsable")
            db.add(Authorization(participant_id=p.participant_id, kind=body.action, version=body.document_version, actor_id=d.id, detail={"accepted": True, "document": cfg["participation_document"]}))
            db.flush()
        if not authorization_status(db, p)["ready"]:
            raise HTTPException(409, "Complete las autorizaciones")
        old = p.policy
        policy = {**old, **{k: getattr(body, k) for k in ("usage", "location", "steps", "raw_location_upload", "research_access", "reminder_time", "reminders")}}
        if policy["raw_location_upload"] and not policy["location"]:
            raise HTTPException(422, "Compartir coordenadas requiere compartir ubicación")
        for kind in ("usage", "location", "steps"):
            if policy[kind] and (not old.get(kind) or d.status != "active"):
                policy[kind + "_since"] = max(body.occurred_at, now()).isoformat()
        policy["paused"] = body.action == "pause" or body.action == "preferences" and (d.status != "active" or old.get("paused", False))
        p.policy = policy
        if policy["paused"] or not p.is_test and not PILOT_ENABLED:
            d.status = "paused"
            for interval in db.scalars(select(Interval).where(Interval.device_id == d.id, Interval.end_at == None)):
                interval.end_at = body.occurred_at
        else:
            d.status = "active"
            if not db.scalar(select(Interval).where(Interval.device_id == d.id, Interval.end_at == None)):
                db.add(Interval(device_id=d.id, start_at=now()))
        db.add(Authorization(participant_id=p.participant_id, kind="preferences", version=body.document_version, actor_id=d.id, detail={"usage": body.usage, "location": body.location, "steps": body.steps, "raw_location_upload": body.raw_location_upload, "research_access": body.research_access, "action": body.action}))
        audit(db, d.id, "school.participation", p.participant_id)
        return {"saved": True, "capture_active": d.status == "active", "policy": {k: v for k, v in policy.items() if k not in ("home_zone", "guardian_channel")}}
    return once(db, actor, idempotency_key, "school-participation", body.model_dump(mode="json"), apply)


@router.get("/me/questionnaires")
def due_questionnaires(actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    cfg = settings(db.get(Institution, p.institution_id))
    if not cfg["instrument_enabled"] or not authorization_status(db, p)["ready"] or not p.is_test and not PILOT_ENABLED:
        return []
    from .checkins import due_forms
    if phq9_due(db, p, cfg):
        # Mientras el PHQ-9 esté pendiente se muestra solo: así nadie encadena
        # varios cuestionarios seguidos. Las preguntas breves aparecen después.
        return [{**PHQ9, "kind": "phq9", "submit_path": "/me/questionnaires", "coverage": coverage_now(cfg)}]
    return [{**f, "coverage": coverage_now(cfg)} for f in due_forms(db, p, cfg)]


def phq9_due(db, p, cfg):
    form = ensure_phq9(db)
    last = db.scalar(select(Response).where(Response.participant_id == p.participant_id, Response.instrument_id == form.id).order_by(Response.created_at.desc()))
    return not last or utc(last.detail.get("applied_at", last.created_at)) + timedelta(days=cfg["cadence_days"]) <= now()


@router.post("/me/questionnaires")
def answer_questionnaire(body: SchoolAnswer, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor, True)
    cfg = settings(db.get(Institution, p.institution_id))
    if not cfg["instrument_enabled"]:
        raise HTTPException(409, "El equipo todavía no ha habilitado el instrumento")
    def apply():
        form = ensure_phq9(db)
        total, review, rules = score(PHQ9, body.answers)
        if total > 0 and body.functioning is None:
            raise HTTPException(422, "Complete la pregunta de funcionamiento; no se suma al puntaje")
        if body.applied_at > now() + timedelta(minutes=5) or body.applied_at < now() - timedelta(days=7):
            raise HTTPException(422, "Fecha de aplicación inválida")
        if abs((body.recall_end - body.recall_start).total_seconds() - 14 * 86400) > 1 or abs((body.applied_at - body.recall_end).total_seconds()) > 300:
            raise HTTPException(422, "El PHQ-9 pregunta por las dos semanas anteriores a la aplicación")
        last = db.scalar(select(Response).where(Response.participant_id == p.participant_id, Response.instrument_id == form.id).order_by(Response.created_at.desc()))
        if last and body.applied_at < utc(last.detail["applied_at"]) + timedelta(days=cfg["cadence_days"]):
            raise HTTPException(409, "Este período ya tiene una respuesta; no se duplican etiquetas")
        row = Response(participant_id=p.participant_id, instrument_id=form.id, detail={**body.model_dump(mode="json"), "total": total, "complete": True, "real": not p.is_test, "provenance": "test_account" if p.is_test else "participant_report", "definition_sha256": PHQ9["definition_sha256"], "phq2": phq2(body.answers), "review_threshold": PHQ9["review_threshold"], "authorization_snapshot": authorization_status(db, p), "research_access_at_collection": bool(p.policy.get("research_access")), "revision": 1})
        db.add(row)
        db.flush()
        if total >= PHQ9["review_threshold"]:
            add_reason(db, p.participant_id, "questionnaire_review", {"response_id": row.id, "total": total, "instrument": PHQ9["instrument_id"]}, actor["id"])
        if "safety_review" in rules:
            add_reason(db, p.participant_id, "safety_review", {"response_id": row.id, "item": "q9", "notice": "Requiere valoración profesional; no establece peligro inminente"}, actor["id"])
        audit(db, actor["id"], "school.questionnaire", row.id)
        return {"received": True, "response_id": row.id, "message": "Tu respuesta fue recibida", "coverage": coverage_now(cfg)}
    return once(db, actor, idempotency_key, "school-questionnaire", body.model_dump(mode="json"), apply)


@router.post("/me/support")
def support(actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor)
    def apply():
        c = add_reason(db, p.participant_id, "contact_request", {"requested_at": now().isoformat()}, actor["id"])
        notify(db, actor["id"], "support:" + str(idempotency_key) + ":" + actor["id"], "support_received", "Tu solicitud fue recibida", {"case_id": c.id})
        audit(db, actor["id"], "school.support", c.id)
        return {"received": True, "case_id": c.id, "message": "Tu solicitud fue recibida"}
    return once(db, actor, idempotency_key, "school-support", {}, apply)


@router.get("/me/requests")
def my_requests(actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    cases = list(db.scalars(select(Case).where(Case.participant_id == p.participant_id)))
    return {"requests": [{"id": c.id, "created_at": c.created_at.isoformat(), "state": c.state} for c in cases if db.scalar(select(Reason).where(Reason.case_id == c.id, Reason.kind == "contact_request"))], "appointments": [{"id": f.id, "date": f.due_at.isoformat(), "state": f.state, "place": f.detail.get("location", ""), "title": "Cita con el equipo de psicología"} for f in db.scalars(select(Followup).where(Followup.participant_id == p.participant_id, Followup.kind == "appointment").order_by(Followup.due_at))]}


@router.post("/me/appointments/{ident}/confirm")
def confirm_appointment(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    f = db.get(Followup, str(ident))
    if not f or f.participant_id != p.participant_id or f.kind != "appointment":
        raise HTTPException(404, "Cita no disponible")
    if f.state not in ("pending", "confirmed"):
        raise HTTPException(409, "Esta cita ya terminó o fue cancelada")
    f.state = "confirmed"
    f.version += 1
    notify(db, f.owner_id, "appointment-confirmed:" + f.id, "appointment", "Una cita fue confirmada", {"case_id": f.case_id})
    return {"confirmed": True}


def minimal_case_student(db, participant_id):
    """A03: the minimum the backup needs to work an escalated case — a name, the
    pseudonym/classroom, whether it is a test account, and authorization state.
    No policy, no research flag, no home zone."""
    p = profile(db, participant_id)
    part = db.get(Participant, participant_id)
    auth = authorization_status(db, p)
    return {"participant_id": participant_id, "display_name": p.display_name, "pseudonym": part.pseudonym,
            "group": part.group, "classroom_id": p.classroom_id, "is_test": p.is_test, "minor": p.minor,
            "status": part.status, "authorization": {k: auth[k] for k in ("ready", "withdrawn", "version")}}


@router.get("/cases")
def school_cases(actor=Depends(identity), db=Depends(database)):
    require(actor, "psychologist", "practitioner")
    from .school_core import granted_case_ids
    allowed = {p["participant_id"]: p for p in students(actor, db)}
    grants = set(granted_case_ids(db, actor["id"])) if actor["role"] == "psychologist" else set()
    rows, seen = [], set()
    for c in db.scalars(select(Case).where(or_(Case.participant_id.in_(allowed), Case.id.in_(grants))).order_by(Case.created_at)):
        if c.id in seen:
            continue
        seen.add(c.id)
        value = case_view(db, c)
        if c.participant_id in allowed:
            value["student"] = allowed[c.participant_id]
        else:
            value["student"] = minimal_case_student(db, c.participant_id)
            value["access_scope"] = "escalation"
        value["next_action"] = next((public(f) for f in db.scalars(select(Followup).where(Followup.case_id == c.id, Followup.state.in_(["pending", "confirmed"])).order_by(Followup.due_at))), None)
        rows.append(value)
    def priority(c):
        kinds = {r["kind"] for r in c["reasons"] if r["active"]}
        return (0 if "safety_review" in kinds else 1 if "contact_request" in kinds else 2 if "questionnaire_review" in kinds else 3, c["created_at"])
    return sorted(rows, key=priority)


@router.get("/overview")
def overview(actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor)
    if actor["role"] in ("psychologist", "practitioner"):
        cases = school_cases(actor, db)
        ids = [c["id"] for c in cases]
        return {"pending": sum(c["state"] == "new" for c in cases), "support": sum(c["state"] != "closed" and any(r["kind"] == "contact_request" for r in c["reasons"]) for c in cases), "overdue": db.scalar(select(func.count()).select_from(Followup).where(Followup.case_id.in_(ids), Followup.state.in_(["pending", "confirmed"]), Followup.due_at < now())), "students": len(students(actor, db)), "recent": cases[:5]}
    rows = list(db.scalars(select(StudentProfile).where(StudentProfile.institution_id == i.id)))
    return {"students": len(rows), "classrooms": db.scalar(select(func.count()).select_from(Classroom).where(Classroom.institution_id == i.id)), "pending_authorizations": sum(not authorization_status(db, p)["ready"] for p in rows), "pilot_enabled": PILOT_ENABLED, "instrument_enabled": settings(i)["instrument_enabled"]}


@router.get("/students/{ident}/profile")
def clinical_profile(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident)
    from .main import summary
    result = summary(ident, actor, db)
    ids = list(db.scalars(select(Device.id).where(Device.participant_id == p.participant_id)))
    latest = {}
    for d in db.scalars(select(MobilityDay).where(MobilityDay.device_id.in_(ids)).order_by(MobilityDay.created_at)):
        latest[d.day] = public(d)
    result["student"] = safe_profile(db, p)
    result["mobility"] = list(latest.values())[-60:]
    result["predictions"] = [public(v) for v in db.scalars(select(Prediction).join(ModelRecord, ModelRecord.id == Prediction.model_id).where(Prediction.participant_id == p.participant_id, ModelRecord.state == "active").order_by(Prediction.cutoff.desc()).limit(30))]
    result["reference_message"] = "Estamos construyendo tu referencia" if not result["evaluations"] else None
    from .checkins import history as checkin_history
    result["checkins"] = checkin_history(db, p.participant_id)
    return result


@router.get("/followups")
def followups(actor=Depends(identity), db=Depends(database)):
    require(actor, "psychologist", "practitioner")
    from .school_core import granted_case_ids
    ids = [p["participant_id"] for p in students(actor, db)]
    grants = set(granted_case_ids(db, actor["id"])) if actor["role"] == "psychologist" else set()
    return [public(f) for f in db.scalars(select(Followup).where(or_(Followup.participant_id.in_(ids), Followup.case_id.in_(grants))).order_by(Followup.due_at))]


@router.post("/followups")
def create_followup(body: FollowupInput, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    from .school_core import case_scope
    case = db.get(Case, str(body.case_id))
    if not case:
        raise HTTPException(404, "Caso no disponible")
    case_scope(db, actor, case, write=True)
    p = profile(db, case.participant_id)
    def apply():
        f = Followup(participant_id=p.participant_id, case_id=case.id, owner_id=actor["id"], kind=body.kind, title=body.title, due_at=body.due_at, detail={"location": body.location})
        db.add(f)
        db.flush()
        db.add(CaseEvent(case_id=case.id, actor=actor["id"], kind="followup_created", detail={"followup_id": f.id, "kind": f.kind, "due_at": f.due_at.isoformat()}))
        if f.kind == "appointment":
            for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id, Device.status != "revoked")):
                notify(db, d.id, "appointment:" + f.id + ":" + d.id, "appointment", "Tienes una cita por confirmar", {"appointment_id": f.id})
        audit(db, actor["id"], "school.followup_created", f.id)
        return public(f)
    return once(db, actor, idempotency_key, "school-followup", body.model_dump(mode="json"), apply)


@router.put("/followups/{ident}")
def update_followup(ident: UUID, body: FollowupUpdate, actor=Depends(identity), db=Depends(database)):
    from .school_core import case_scope
    f = db.get(Followup, str(ident))
    if not f:
        raise HTTPException(404, "Seguimiento no disponible")
    case = db.get(Case, f.case_id)
    if not case:
        raise HTTPException(404, "Seguimiento no disponible")
    case_scope(db, actor, case, write=True)
    if body.state == "completed" and len(body.outcome.strip()) < 3:
        raise HTTPException(422, "Registre el resultado del seguimiento")
    changed = db.execute(update(Followup).where(Followup.id == f.id, Followup.version == body.version).values(state=body.state, version=Followup.version + 1, detail={**f.detail, "contact_confirmed": body.contact_confirmed, "outcome": body.outcome}))
    if not changed.rowcount:
        raise HTTPException(409, "El seguimiento cambió; actualice antes de guardar")
    db.add(CaseEvent(case_id=f.case_id, actor=actor["id"], kind="followup_updated", detail={"followup_id": f.id, **body.model_dump()}))
    audit(db, actor["id"], "school.followup_updated", f.id)
    db.flush()
    db.refresh(f)
    return public(f)


@router.get("/calendar")
def calendar(actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor)
    return [public(e) for e in db.scalars(select(SchoolEvent).where(SchoolEvent.institution_id == i.id).order_by(SchoolEvent.start_at))]


@router.post("/calendar")
def create_calendar(body: CalendarInput, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin", "director", "psychologist")
    if body.classroom_id:
        c = db.get(Classroom, str(body.classroom_id))
        if not c or c.institution_id != i.id:
            raise HTTPException(404, "Aula no disponible")
    e = SchoolEvent(institution_id=i.id, **body.model_dump(exclude={"classroom_id"}), classroom_id=str(body.classroom_id) if body.classroom_id else None)
    db.add(e)
    db.flush()
    audit(db, actor["id"], "school.calendar", e.id)
    return public(e)


@router.delete("/calendar/{ident}")
def delete_calendar(ident: UUID, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin", "director", "psychologist")
    e = db.get(SchoolEvent, str(ident))
    if not e or e.institution_id != i.id:
        raise HTTPException(404, "Evento no disponible")
    db.delete(e)
    audit(db, actor["id"], "school.calendar_deleted", str(ident))
    return {"deleted": True}


@router.get("/cohort-summary/{ident}")
def cohort_summary(ident: UUID, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin", "director", "psychologist")
    c = db.get(Classroom, str(ident))
    if not c or c.institution_id != i.id:
        raise HTTPException(404, "Aula no disponible")
    pids = list(db.scalars(select(StudentProfile.participant_id).where(StudentProfile.classroom_id == c.id)))
    cfg = settings(i)
    device_ids = list(db.scalars(select(Device.id).where(Device.participant_id.in_(pids), Device.status == "active")))
    contributors = set(db.scalars(select(Device.participant_id).join(Feature, Feature.device_id == Device.id).where(Device.id.in_(device_ids), Feature.day >= (now() - timedelta(days=7)).date().isoformat())))
    if len(contributors) < cfg["minimum_group"]:
        return {"available": False, "message": "No se muestra el agregado: faltan participantes con datos suficientes", "minimum_group": cfg["minimum_group"]}
    return {"available": True, "participants_with_data": len(contributors), "period_days": 7, "notice": "Resumen de disponibilidad; no clasifica la salud del aula"}


@router.get("/notifications")
def inbox(actor=Depends(identity), db=Depends(database)):
    return [public(n) for n in db.scalars(select(Notification).where(Notification.recipient_id == actor["id"], Notification.due_at <= now()).order_by(Notification.created_at.desc()).limit(100))]


@router.post("/notifications/{ident}/ack")
def acknowledge_notification(ident: UUID, actor=Depends(identity), db=Depends(database)):
    n = db.get(Notification, str(ident))
    if not n or n.recipient_id != actor["id"]:
        raise HTTPException(404, "Aviso no disponible")
    n.state = "acknowledged"
    n.acknowledged_at = now()
    audit(db, actor["id"], "notification.ack", n.id)
    return {"acknowledged": True}


@router.post("/notifications/{ident}/delivered")
def delivered_notification(ident: UUID, actor=Depends(identity), db=Depends(database)):
    n = db.get(Notification, str(ident))
    if not n or n.recipient_id != actor["id"]:
        raise HTTPException(404, "Aviso no disponible")
    if n.state != "acknowledged":
        n.state = "delivered"
    n.detail = {**n.detail, "device_receipt_at": now().isoformat()}
    return {"recorded": True}


@router.post("/push-token")
def push_token(body: PushRegistration, actor=Depends(identity), db=Depends(database)):
    h = digest(body.token)
    old = db.scalar(select(PushToken).where(PushToken.token_hash == h))
    if old and old.owner_id != actor["id"]:
        raise HTTPException(409, "Token vinculado a otra cuenta; retire el anterior")
    if not old:
        db.add(PushToken(owner_id=actor["id"], token_hash=h, token=body.token))
    return {"registered": True}


@router.get("/preferences")
def preferences(actor=Depends(identity), db=Depends(database)):
    return member(db, actor).preferences


@router.put("/preferences")
def save_preferences(body: dict, actor=Depends(identity), db=Depends(database)):
    m = member(db, actor)
    if set(body) - {"display_name", "reminder_time", "reminders", "notification_email"} or len(str(body.get("display_name", ""))) > 160:
        raise HTTPException(422, "Preferencias inválidas")
    from .notifications import valid_email
    if body.get("notification_email") and not valid_email(body["notification_email"]):
        raise HTTPException(422, "Correo inválido")
    if "reminder_time" in body:
        try:
            time.fromisoformat(body["reminder_time"])
        except (ValueError, TypeError):
            raise HTTPException(422, "Hora inválida")
    m.preferences = {**m.preferences, **body}
    return m.preferences


@router.get("/channels")
def channels(actor=Depends(identity), db=Depends(database)):
    institutional(db, actor, "admin", "psychologist")
    from .notifications import channel_status
    return channel_status()


@router.get("/students/{ident}/authorizations")
def authorization_history(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident, "administration")
    audit(db, actor["id"], "school.authorization_history", p.participant_id)
    return [public(a) for a in db.scalars(select(Authorization).where(Authorization.participant_id == p.participant_id).order_by(Authorization.created_at))]


@router.get("/students/{ident}/report", response_class=HTMLResponse)
def individual_report(ident: UUID, start: AwareDatetime, end: AwareDatetime, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident)
    import html
    try:
        a, b = utc(start), utc(end)
        if not 0 < (b - a).total_seconds() <= 366 * 86400:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Seleccione un período de hasta un año")
    escape = lambda x: html.escape(str(x))
    responses = list(db.scalars(select(Response).where(Response.participant_id == p.participant_id, Response.created_at >= a, Response.created_at <= b).order_by(Response.created_at)))
    cases = list(db.scalars(select(Case).where(Case.participant_id == p.participant_id)))
    events = list(db.scalars(select(CaseEvent).where(CaseEvent.case_id.in_([c.id for c in cases]), CaseEvent.created_at >= a, CaseEvent.created_at <= b).order_by(CaseEvent.created_at)))
    questionnaires = ''.join(f'<tr><td>{escape(r.detail["applied_at"])}</td><td>PHQ-9 · {escape(r.detail.get("instrument_version", ""))}</td><td>{r.detail["total"]} / 27</td></tr>' for r in responses)
    actions = ''.join(f'<li><strong>{escape(e.created_at.isoformat())}</strong> · {escape(e.kind)}<p>{escape(e.detail.get("text") or e.detail.get("reason") or json.dumps(e.detail, ensure_ascii=False))}</p></li>' for e in events if e.kind != "evidence_added")
    ids = list(db.scalars(select(Device.id).where(Device.participant_id == p.participant_id)))
    summaries = []
    for cls in (Feature, MobilityDay):
        for row in db.scalars(select(cls).where(cls.device_id.in_(ids), cls.day >= a.date().isoformat(), cls.day <= b.date().isoformat()).order_by(cls.day)):
            for name, v in row.detail["features"].items():
                summaries.append(f'<tr><td>{escape(row.day)}</td><td>{escape(name)}</td><td>{escape(v["value"] if v["value"] is not None else "Sin datos")} {escape(v["unit"])}</td><td>{escape(v["state"])}</td></tr>')
    text = f'<!doctype html><html lang="es"><meta charset="utf-8"><title>Informe individual — Acompaña Escolar</title><style>body{{font:15px system-ui;max-width:900px;margin:40px auto;color:#123047}}h1,h2{{color:#087f83}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}p{{line-height:1.6}}@media print{{body{{margin:15mm}}}}</style><h1>Acompaña Escolar</h1><h2>Informe individual · {escape(p.display_name)}</h2><p>Período: {escape(start)} — {escape(end)}. Elaborado: {escape(now().isoformat())}.</p><p>Documento privado para el profesional asignado. {"Cuenta de prueba." if p.is_test else ""}</p><h2>Instrumentos</h2><table><tr><th>Aplicación</th><th>Instrumento</th><th>Puntaje</th></tr>{questionnaires}</table><h2>Datos observados</h2><table><tr><th>Día</th><th>Variable</th><th>Valor</th><th>Calidad</th></tr>{"".join(summaries)}</table><h2>Acciones y seguimiento</h2><ol>{actions}</ol><h2>Alcance</h2><p>Los cuestionarios y estimaciones requieren valoración profesional. Los datos parciales no describen el día completo; el uso nocturno no mide sueño. Este informe no contiene ubicaciones crudas ni establece un diagnóstico.</p></html>'
    audit(db, actor["id"], "school.report_exported", p.participant_id)
    return HTMLResponse(text, headers={"Content-Disposition": 'attachment; filename="informe-individual.html"', "Cache-Control": "no-store"})


@router.post("/accounts/{ident}/password")
def reset_password(ident: UUID, body: PasswordReset, actor=Depends(identity), db=Depends(database)):
    i = institutional(db, actor, "admin")
    m = db.scalar(select(Membership).where(Membership.user_id == str(ident), Membership.institution_id == i.id, Membership.active == True))
    if not m:
        raise HTTPException(404, "Cuenta no disponible")
    db.get(User, m.user_id).password_hash = hasher.hash(body.password)
    for session in db.scalars(select(Session).where(Session.user_id == m.user_id)):
        session.revoked = True
    audit(db, actor["id"], "school.password_reset", m.user_id)
    return {"updated": True}


@router.post("/students/{ident}/access-link")
def renew_student_access(ident: UUID, actor=Depends(identity), db=Depends(database)):
    p = access(db, actor, ident, "administration")
    if db.get(Participant, p.participant_id).status == "revoked":
        raise HTTPException(409, "La participación ya fue retirada")
    for link in db.scalars(select(AccessLink).where(AccessLink.participant_id == p.participant_id, AccessLink.purpose == "student", AccessLink.used == False)):
        link.used = True
    for device in db.scalars(select(Device).where(Device.participant_id == p.participant_id)):
        device.status = "revoked"
        for interval in db.scalars(select(Interval).where(Interval.device_id == device.id, Interval.end_at == None)):
            interval.end_at = now()
        for session in db.scalars(select(Session).where(Session.device_id == device.id)):
            session.revoked = True
    cfg = settings(db.get(Institution, p.institution_id))
    result = make_link(db, p, "student", cfg["document_version"])
    audit(db, actor["id"], "school.student_access_renewed", p.participant_id)
    return {"student": safe_profile(db, p), "invitation": result, "guardian": None}
