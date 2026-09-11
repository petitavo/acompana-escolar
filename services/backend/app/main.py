import json, secrets
from datetime import timedelta
from uuid import UUID
from urllib.parse import urlparse
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response as HTTPResponse,
    Header,
    Query,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from .db import *
from .config import MODE, COOKIE_SECURE, CONSENT_VERSION, ARTIFACTS, RAW_RETENTION_DAYS
from .schemas import *
from .security import (
    database,
    identity,
    require,
    assigned,
    own_device,
    once,
    audit,
    digest,
    hasher,
)
from .forms import ensure_demo_form, score
from .cases import add_reason, case_view

app = FastAPI(
    title="Acompaña Escolar",
    version="0.3.0",
    description="Producto escolar con roles, participación informada, análisis y revisión profesional. Herramientas DEMO y LAB separadas. No diagnóstico automático.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)
API = "/api/v1"


@app.middleware("http")
async def boundary(request, call_next):
    correlation = uid()
    if MODE == "REAL":
        path = request.url.path
        legacy_write = path in ("/api/v1/enrollments/redeem", "/api/v1/me/participation-events", "/api/v1/questionnaire-responses", "/api/v1/contact-requests")
        if path.startswith("/api/v1/lab/") or path in ("/api/v1/questionnaires/due", "/api/v1/me/questionnaire-responses") or legacy_write:
            return JSONResponse({"detail": "Use el recorrido escolar; las herramientas de prueba están separadas"}, 404)
    length = request.headers.get("content-length", "0")
    if not length.isdigit() or int(length) > 1_000_000:
        return JSONResponse({"detail": "Solicitud demasiado grande"}, 413)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        payload = await request.body()
        if len(payload) > 1_000_000:
            return JSONResponse({"detail": "Solicitud demasiado grande"}, 413)
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(
        "origin"
    ):
        origin = urlparse(request.headers["origin"]).netloc
        if origin != request.headers.get("host"):
            return JSONResponse({"detail": "Origen no permitido"}, 403)
    result = await call_next(request)
    result.headers["X-Correlation-ID"] = correlation
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Referrer-Policy"] = "no-referrer"
    return result


@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                for e in exc.errors()
            ]
        },
    )


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Conflicto concurrente o identificador ya utilizado; reintente con la misma clave"
        },
    )


@app.get(API + "/health")
def health(db=Depends(database)):
    db.execute(select(1))
    return {"status": "ok", "mode": MODE, "version": app.version}


@app.post(API + "/auth/login")
def login(body: Login, request: Request, response: HTTPResponse, db=Depends(database)):
    key = digest(
        (request.client.host if request.client else "unknown")
        + ":"
        + body.username.lower()
    )
    attempt = db.get(LoginAttempt, key)
    if attempt and utc(attempt.until) > now() and attempt.count >= 5:
        raise HTTPException(429, "Demasiados intentos. Espere 15 minutos")
    user = db.scalar(
        select(User).where(User.username == body.username, User.environment == MODE)
    )
    valid = False
    try:
        valid = (
            hasher.verify(user.password_hash, body.password)
            if user
            else hasher.verify(DUMMY_HASH, body.password)
        )
    except (VerifyMismatchError, InvalidHashError):
        pass
    if not user or not valid:
        if not attempt:
            attempt = LoginAttempt(
                key=key, count=0, until=now() + timedelta(minutes=15)
            )
            db.add(attempt)
        if utc(attempt.until) < now():
            attempt.count = 0
            attempt.until = now() + timedelta(minutes=15)
        attempt.count += 1
        db.commit()
        raise HTTPException(401, "Credenciales inválidas")
    if MODE == "REAL":
        from .school_db import Membership
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
        if membership and not membership.active:
            raise HTTPException(403, "Cuenta desactivada")
    if attempt:
        db.delete(attempt)
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires_at=now() + timedelta(hours=8),
        )
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=28800,
        path="/api",
    )
    audit(db, user.id, "auth.login")
    return {
        "id": user.id,
        "scopes": user.scopes,
        "role": user.role,
        "username": user.username,
        "csrf_token": csrf,
        "mode": MODE,
    }


DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


@app.post(API + "/auth/logout")
def logout(response: HTTPResponse, actor=Depends(identity), db=Depends(database)):
    actor["session"].revoked = True
    response.delete_cookie(
        "session", path="/api", secure=COOKIE_SECURE, samesite="strict"
    )
    return {"ok": True}


@app.get(API + "/me")
def me(actor=Depends(identity), db=Depends(database)):
    result = {
        "id": actor["id"],
        "scopes": actor.get("scopes", []),
        "role": actor["role"],
        "mode": MODE,
        "username": actor.get("username"),
        "csrf_token": actor["session"].csrf,
    }
    if actor["role"] == "participant":
        d = own_device(actor)
        result.update(
            device_id=d.id,
            participant_id=d.participant_id,
            pseudonym=db.get(Participant, d.participant_id).pseudonym,
            status=d.status,
            detail=d.detail,
        )
    return result


@app.get(API + "/me/collection-policy")
def policy(actor=Depends(identity)):
    d = own_device(actor)
    return {
        "mode": MODE,
        "active": d.status == "active",
        "consent_version": CONSENT_VERSION,
        "share_packages": d.share_packages,
        "max_batch": 500,
        "gps": "not_implemented",
        "steps": "not_implemented",
        "raw_retention_days": RAW_RETENTION_DAYS,
    }


@app.post(API + "/enrollments/redeem")
def enroll(body: Enrollment, db=Depends(database)):
    invite = db.scalar(
        select(Invitation)
        .where(
            Invitation.token_hash == digest(body.invitation),
            Invitation.environment == MODE,
        )
        .with_for_update()
    )
    if not invite or invite.used or utc(invite.expires_at) <= now():
        raise HTTPException(401, "Invitación inválida, usada o vencida")
    participant = db.get(Participant, invite.participant_id)
    if participant.status == "revoked":
        raise HTTPException(409, "Participación revocada")
    invite.used = True
    device = Device(
        participant_id=invite.participant_id, detail=body.device.model_dump()
    )
    db.add(device)
    db.flush()
    token = secrets.token_urlsafe(48)
    db.add(
        Session(
            device_id=device.id,
            token_hash=digest(token),
            csrf="",
            expires_at=now() + timedelta(days=30),
        )
    )
    audit(db, device.id, "device.enrolled")
    return {
        "device_id": device.id,
        "token": token,
        "mode": MODE,
        "pseudonym": participant.pseudonym,
    }


@app.post(API + "/me/participation-events")
def participate(
    body: Participation,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    d = own_device(actor)

    def apply():
        at = utc(body.occurred_at)
        if at > now() + timedelta(minutes=5):
            raise HTTPException(422, "Reloj futuro")
        intervals = list(
            db.scalars(
                select(Interval)
                .where(Interval.device_id == d.id)
                .order_by(Interval.start_at)
            )
        )
        last = intervals[-1] if intervals else None
        if body.action in ("consent", "resume"):
            if d.status == "active" or body.action == "consent" and intervals:
                raise HTTPException(409, "Estado incompatible")
            if body.action == "consent" and not body.adult:
                raise HTTPException(422, "LAB requiere aceptación de adulto")
            if body.action == "resume" and not intervals:
                raise HTTPException(409, "Falta consentimiento inicial")
            if last and at < utc(last.end_at or last.start_at):
                raise HTTPException(409, "Los intervalos no pueden retroceder")
            if body.action == "consent":
                db.add(
                    Consent(
                        device_id=d.id,
                        version=body.consent_version,
                        detail={
                            "adult": True,
                            "share_packages": body.share_packages,
                            "accepted_at": at.isoformat(),
                        },
                    )
                )
            d.status = "active"
            d.share_packages = body.share_packages
            db.add(Interval(device_id=d.id, start_at=at))
        elif body.action in ("pause", "revoke"):
            if last and last.end_at is None:
                if at < utc(last.start_at):
                    raise HTTPException(409, "La pausa precede el consentimiento")
                last.end_at = at
            d.status = "revoked" if body.action == "revoke" else "paused"
            if body.action == "revoke":
                for s in db.scalars(select(Session).where(Session.device_id == d.id)):
                    s.revoked = True
        else:
            d.share_packages = body.share_packages
            db.add(
                Consent(
                    device_id=d.id,
                    version=CONSENT_VERSION,
                    detail={
                        "package_policy": body.share_packages,
                        "accepted_at": at.isoformat(),
                    },
                )
            )
        audit(db, d.id, "participation." + body.action, d.id)
        return {
            "status": d.status,
            "recorded_at": now().isoformat(),
            "share_packages": d.share_packages,
        }

    return once(
        db, actor, idempotency_key, "participation", body.model_dump(mode="json"), apply
    )


def allowed_interval(db, d, start, end):
    return any(
        utc(x.start_at) <= start and (x.end_at is None or utc(x.end_at) >= end)
        for x in db.scalars(select(Interval).where(Interval.device_id == d.id))
    )


@app.post(API + "/capture-sessions")
def capture(body: CaptureInput, actor=Depends(identity), db=Depends(database)):
    d = own_device(actor, True)
    if MODE == "REAL":
        from .school_core import sensor_allowed
        if not sensor_allowed(db, d, "usage", body.start_at) or not sensor_allowed(db, d, "usage", body.end_at):
            raise HTTPException(403, "El uso del teléfono no está autorizado")
    d = own_device(actor, True)
    ident = str(body.id)
    existing = db.get(Capture, ident)
    if existing:
        if existing.device_id != d.id:
            raise HTTPException(409, "ID no disponible")
        if existing.detail != body.model_dump(mode="json"):
            raise HTTPException(409, "ID con otro contenido")
        return {"accepted": [ident], "duplicate": True}
    if body.end_at > now() + timedelta(minutes=5):
        raise HTTPException(422, "Consulta con reloj futuro")
    if not allowed_interval(db, d, body.start_at, body.end_at):
        raise HTTPException(403, "Consulta fuera del período autorizado")
    db.add(
        Capture(
            id=ident,
            device_id=d.id,
            start_at=body.start_at,
            end_at=body.end_at,
            detail=body.model_dump(mode="json"),
        )
    )
    d.detail = {
        **d.detail,
        **{
            k: v
            for k, v in body.model_dump(mode="json").items()
            if k
            in (
                "battery",
                "charging",
                "connected",
                "outbox_pending",
                "keyguard_available",
            )
        },
        "last_query": body.end_at.isoformat(),
        "last_sync": now().isoformat(),
        "usage_access": "available" if body.permission_after else "permission_missing",
    }
    if MODE == "REAL":
        from worker.school import queue_received_days
        queue_received_days(db, d, [body.start_at, body.end_at], "reprocess")
    return {"accepted": [ident], "duplicate": False}


@app.post(API + "/events/batch")
def events_batch(body: Batch, actor=Depends(identity), db=Depends(database)):
    d = own_device(actor, True)
    if MODE == "REAL":
        from .school_core import sensor_allowed
        if not sensor_allowed(db, d, "usage"):
            raise HTTPException(403, "El uso del teléfono no está autorizado")
    accepted = []
    duplicates = []
    rejected = []
    for item in body.events:
        ident = str(item.event_id)
        reason = None
        c = db.get(Capture, str(item.capture_session_id))
        at = utc(item.occurred_at)
        old = db.get(RawEvent, ident)
        if str(item.device_id) != d.id:
            reason = "wrong_device"
        elif old:
            if (
                old.device_id == d.id
                and old.event_type == item.event_type
                and utc(old.occurred_at) == at
                and old.source == item.source
                and old.timezone == item.timezone
                and old.capture_session_id == str(item.capture_session_id)
                and old.payload
                == {
                    **item.payload.model_dump(exclude_none=True),
                    "utc_offset_minutes": item.utc_offset_minutes,
                }
            ):
                duplicates.append(ident)
                continue
            reason = "id_conflict"
        elif item.source != (
            "synthetic_generator" if MODE == "DEMO" else "android_usage_events"
        ):
            reason = "wrong_provenance"
        elif not c or c.device_id != d.id:
            reason = "unknown_capture_session"
        elif not (
            c.detail["success"]
            and c.detail["permission_before"]
            and c.detail["permission_after"]
        ):
            reason = "permission_not_verified"
        elif not utc(c.start_at) <= at <= utc(c.end_at):
            reason = "outside_capture_window"
        elif not allowed_interval(db, d, at, at):
            reason = "outside_consent"
        elif MODE == "REAL" and not sensor_allowed(db, d, "usage", at):
            reason = "outside_usage_authorization"
        elif item.payload.package and (
            not d.share_packages
            or item.event_type not in ("ACTIVITY_RESUMED", "ACTIVITY_PAUSED")
        ):
            reason = "package_not_authorized"
        if reason:
            rejected.append({"event_id": ident, "reason": reason, "permanent": True})
            continue
        payload = item.payload.model_dump(exclude_none=True)
        payload["utc_offset_minutes"] = item.utc_offset_minutes
        db.add(
            RawEvent(
                id=ident,
                device_id=d.id,
                capture_session_id=c.id,
                occurred_at=at,
                event_type=item.event_type,
                timezone=item.timezone,
                payload=payload,
                source=item.source,
                clock_flag=at > now() + timedelta(minutes=5)
                or at < now() - timedelta(days=7)
                if MODE in ("LAB", "REAL")
                else False,
                consent_version=item.consent_version,
            )
        )
        db.flush()
        accepted.append(ident)
    if MODE == "REAL" and accepted:
        from worker.school import queue_received_days
        queue_received_days(db, d, [item.occurred_at for item in body.events if str(item.event_id) in accepted], "reprocess")
    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "received_at": now().isoformat(),
    }


@app.get(API + "/questionnaires/due")
def due(actor=Depends(identity), db=Depends(database)):
    own_device(actor)
    return [
        dict(code=f.code, **f.definition)
        for f in db.scalars(select(Instrument).where(Instrument.enabled == True))
    ]


@app.get(API + "/me/questionnaire-responses")
def response_history(actor=Depends(identity), db=Depends(database)):
    d = own_device(actor)
    return [
        public(r)
        for r in db.scalars(
            select(Response)
            .where(Response.participant_id == d.participant_id)
            .order_by(Response.created_at.desc())
            .limit(100)
        )
    ]


@app.post(API + "/questionnaire-responses")
def submit(
    body: AnswerInput,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    d = own_device(actor, True)

    def apply():
        form = db.scalar(
            select(Instrument).where(
                Instrument.code == body.instrument_code, Instrument.enabled == True
            )
        )
        if not form:
            raise HTTPException(404, "Instrumento no habilitado")
        if body.applied_at > now() + timedelta(minutes=5):
            raise HTTPException(422, "Fecha futura")
        total, review, item_rules = score(form.definition, body.answers)
        if (
            form.code == "CHECKIN_DEMO_V1"
            and (body.recall_end - body.recall_start).total_seconds() > 86400
        ):
            raise HTTPException(422, "El check-in demo se refiere a hoy")
        result = Response(
            participant_id=d.participant_id,
            instrument_id=form.id,
            detail={
                **body.model_dump(mode="json"),
                "total": total,
                "complete": True,
                "instrument_version": form.definition["version"],
                "real": form.definition["real"],
            },
        )
        db.add(result)
        db.flush()
        case = None
        if review:
            case = add_reason(
                db,
                d.participant_id,
                "questionnaire_review"
                if form.definition["real"]
                else "questionnaire_review_demo",
                {
                    "response_id": result.id,
                    "total": total,
                    "rules": item_rules,
                    "notice": form.definition["notice"],
                },
                d.id,
            )
        audit(db, d.id, "questionnaire.submitted", result.id)
        return {
            "response_id": result.id,
            "saved": True,
            "case_created": case is not None,
        }

    return once(
        db, actor, idempotency_key, "questionnaire", body.model_dump(mode="json"), apply
    )


@app.post(API + "/contact-requests")
def contact(
    body: ContactInput,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    d = own_device(actor, True)

    def apply():
        c = add_reason(
            db,
            d.participant_id,
            "contact_request",
            {
                "requested_at": body.requested_at.isoformat(),
                "notice": "Prueba interna; no garantiza atención de emergencia",
            },
            d.id,
        )
        return {
            "received": True,
            "case_id": c.id,
            "status": "aviso creado; pendiente de reconocimiento",
        }

    return once(
        db, actor, idempotency_key, "contact", body.model_dump(mode="json"), apply
    )


@app.post(API + "/me/deletion-requests")
def request_deletion(
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    d = own_device(actor)

    def apply():
        # Revoke immediately; erasure itself is a leased background job.
        for device in db.scalars(
            select(Device).where(Device.participant_id == d.participant_id)
        ):
            device.status = "revoked"
            for s in db.scalars(select(Session).where(Session.device_id == device.id)):
                s.revoked = True
        # A08: lock the participant row so concurrent inference re-checks after this.
        part = db.scalars(
            select(Participant).where(Participant.id == d.participant_id)
            .with_for_update().execution_options(populate_existing=True)
        ).one()
        part.status = "revoked"
        job = Job(
            kind="deletion", actor=d.id, payload={"participant_id": d.participant_id}
        )
        db.add(job)
        db.flush()
        audit(db, d.id, "deletion.requested", job.id)
        return {"job_id": job.id, "status": "queued", "devices_revoked": True}

    return once(db, actor, idempotency_key, "deletion", {}, apply)


@app.get(API + "/psych/cases")
def cases(
    state: str | None = None,
    kind: str | None = None,
    group: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    actor=Depends(identity),
    db=Depends(database),
):
    require(actor, "psychologist")
    q = (
        select(Case)
        .join(Assignment, Assignment.participant_id == Case.participant_id)
        .where(Assignment.user_id == actor["id"])
    )
    if state:
        q = q.where(Case.state == state)
    rows = [case_view(db, c) for c in db.scalars(q)]
    if group:
        rows = [c for c in rows if c["group"] == group]
    if kind:
        rows = [c for c in rows if any(r["kind"] == kind for r in c["reasons"])]

    def rank(c):
        return (
            min(
                (
                    {
                        "contact_request": 0,
                        "questionnaire_review": 1,
                        "questionnaire_review_demo": 1,
                        "behavior_change": 2,
                    }.get(r["kind"], 3)
                    for r in c["reasons"]
                    if r["active"]
                ),
                default=4,
            ),
            c["created_at"],
        )

    return sorted(rows, key=rank)[:limit]


def get_case(db, actor, ident, write=False):
    case = db.get(Case, str(ident))
    if not case:
        raise HTTPException(404, "Caso no disponible")
    if MODE == "REAL":
        # A03: case-scoped — assigned professionals, or a backup with a live grant
        # for *this* case only.
        from .school_core import case_scope
        actor["_case_scope"] = case_scope(db, actor, case, write)
    else:
        assigned(db, actor, case.participant_id)
    return case


@app.get(API + "/psych/cases/{ident}")
def case_detail(ident: UUID, actor=Depends(identity), db=Depends(database)):
    case = get_case(db, actor, ident)
    view = case_view(db, case, True)
    if actor.get("_case_scope") == "escalation":
        view["access_scope"] = "escalation"
        view["access_notice"] = "Acceso de suplencia acotado a este caso. No incluye el perfil clínico completo ni otros casos del estudiante."
    return view


@app.post(API + "/psych/cases/{ident}/transitions")
def transition(
    ident: UUID, body: Transition, actor=Depends(identity), db=Depends(database)
):
    case = get_case(db, actor, ident, write=True)
    allowed = {
        "new": {"acknowledged", "closed"},
        "acknowledged": {"contact_planned", "in_followup", "closed"},
        "contact_planned": {"in_followup", "closed"},
        "in_followup": {"closed"},
        "closed": {"new"},
    }
    if body.state == "new":
        db.scalar(
            select(Participant)
            .where(Participant.id == case.participant_id)
            .with_for_update()
        )
        other = db.scalar(
            select(Case).where(
                Case.participant_id == case.participant_id,
                Case.id != case.id,
                Case.state != "closed",
            )
        )
        if other:
            raise HTTPException(
                409, "Ya existe un caso activo; continúe la revisión en ese caso"
            )
    if body.state not in allowed[case.state]:
        raise HTTPException(409, "Transición no permitida desde este estado")
    result = db.execute(
        update(Case)
        .where(Case.id == case.id, Case.version == body.version)
        .values(state=body.state, version=Case.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "El caso cambió. Actualice antes de guardar")
    if body.state == "closed" and MODE == "REAL":
        # A03: a resolved case releases every scoped backup grant it created.
        from .school_core import revoke_case_grants
        revoke_case_grants(db, case.id)
    db.add(
        CaseEvent(
            case_id=case.id,
            actor=actor["id"],
            kind="transition",
            detail=body.model_dump(),
        )
    )
    audit(db, actor["id"], "case.transition", case.id)
    db.flush()
    db.refresh(case)
    return case_view(db, case, True)


@app.post(API + "/psych/cases/{ident}/notes")
def note(
    ident: UUID,
    body: Note,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    case = get_case(db, actor, ident, write=True)

    def apply():
        row = CaseEvent(
            case_id=case.id,
            actor=actor["id"],
            kind="review_note",
            detail={"text": body.text},
        )
        db.add(row)
        db.flush()
        audit(db, actor["id"], "case.note", case.id)
        return {"id": row.id}

    return once(
        db, actor, idempotency_key, "note:" + str(ident), body.model_dump(), apply
    )


@app.get(API + "/psych/participants/{ident}/summary")
def summary(ident: UUID, actor=Depends(identity), db=Depends(database)):
    pid = str(ident)
    assigned(db, actor, pid)
    p = db.get(Participant, pid)
    device_ids = list(db.scalars(select(Device.id).where(Device.participant_id == pid)))
    latest = {}
    for f in db.scalars(
        select(Feature)
        .where(Feature.device_id.in_(device_ids))
        .order_by(Feature.created_at)
    ):
        latest[f.day] = {
            "id": f.id,
            "day": f.day,
            "version": f.version,
            "features": f.detail["features"],
        }
    return {
        "participant": public(p),
        "features": sorted(latest.values(), key=lambda x: x["day"])[-60:],
        "evaluations": [
            public(e)
            for e in db.scalars(
                select(Evaluation)
                .where(Evaluation.participant_id == pid)
                .order_by(Evaluation.cutoff.desc())
                .limit(10)
            )
        ],
        "questionnaires": [
            public(r)
            for r in db.scalars(
                select(Response)
                .where(Response.participant_id == pid)
                .order_by(Response.created_at.desc())
                .limit(30)
            )
        ],
        "academic_events": [
            public(e)
            for e in db.scalars(
                select(AcademicEvent).where(AcademicEvent.group == p.group)
            )
        ],
    }


@app.post(API + "/psych/usability-feedback")
def feedback(body: Feedback, actor=Depends(identity), db=Depends(database)):
    require(actor, "psychologist")
    job = Job(
        kind="usability_feedback",
        actor=actor["id"],
        state="completed",
        payload=body.model_dump(),
    )
    db.add(job)
    return {"saved": True}


@app.get(API + "/lab/overview")
def overview(actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    return {
        "mode": MODE,
        "participants": db.scalar(select(func.count()).select_from(Participant)),
        "devices": db.scalar(select(func.count()).select_from(Device)),
        "events": db.scalar(select(func.count()).select_from(RawEvent)),
        "jobs_pending": db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.state.in_(["queued", "running"]))
        ),
        "capabilities": {
            "usage_events": "available",
            "gps": "not_implemented",
            "steps": "not_implemented",
            "sleep": "not_implemented",
        },
        "notice": "Cobertura operacional no equivale a todo el comportamiento observado.",
    }


@app.get(API + "/lab/devices")
def devices(actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    return [
        {**public(d), "pseudonym": db.get(Participant, d.participant_id).pseudonym}
        for d in db.scalars(select(Device))
    ]


@app.get(API + "/lab/devices/{ident}")
def device_detail(ident: UUID, actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    d = db.get(Device, str(ident))
    if not d:
        raise HTTPException(404, "Dispositivo no disponible")
    return {
        **public(d),
        "pseudonym": db.get(Participant, d.participant_id).pseudonym,
        "captures": [
            public(c)
            for c in db.scalars(
                select(Capture)
                .where(Capture.device_id == d.id)
                .order_by(Capture.created_at.desc())
                .limit(100)
            )
        ],
        "intervals": [
            public(i)
            for i in db.scalars(select(Interval).where(Interval.device_id == d.id))
        ],
    }


@app.get(API + "/lab/events")
def event_list(
    device_id: UUID | None = None,
    event_type: str | None = None,
    source: str | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(identity),
    db=Depends(database),
):
    require(actor, "researcher")
    q = select(RawEvent)
    if device_id:
        q = q.where(RawEvent.device_id == str(device_id))
    if event_type:
        q = q.where(RawEvent.event_type == event_type)
    if source:
        q = q.where(RawEvent.source == source)
    if start:
        q = q.where(RawEvent.occurred_at >= start)
    if end:
        q = q.where(RawEvent.occurred_at < end)
    if cursor:
        q = q.where(RawEvent.id > cursor)
    rows = list(db.scalars(q.order_by(RawEvent.id).limit(limit + 1)))
    return {
        "items": [public(r) for r in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


@app.get(API + "/lab/features")
def features(
    device_id: UUID | None = None,
    day: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    actor=Depends(identity),
    db=Depends(database),
):
    require(actor, "researcher")
    q = select(Feature)
    if device_id:
        q = q.where(Feature.device_id == str(device_id))
    if day:
        q = q.where(Feature.day == day)
    return [
        public(f)
        for f in db.scalars(
            q.order_by(Feature.day.desc(), Feature.created_at.desc()).limit(limit)
        )
    ]


@app.get(API + "/lab/features/{ident}/lineage")
def lineage(ident: UUID, actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    f = db.get(Feature, str(ident))
    if not f:
        raise HTTPException(404, "Feature no disponible")
    ids = f.detail["lineage"]["event_ids"]
    raw = list(db.scalars(select(RawEvent).where(RawEvent.id.in_(ids))))
    return {
        "feature": public(f),
        "events": [public(r) for r in raw],
        "raw_expired": len(raw) < len(ids),
        "notice": "Cada reproceso crea otra versión; las revisiones conservan sus referencias.",
    }


def queue_job(db, actor, key, kind, payload):
    def apply():
        job = Job(kind=kind, actor=actor["id"], payload=payload)
        db.add(job)
        db.flush()
        audit(db, actor["id"], kind + ".queued", job.id)
        return {"id": job.id, "state": "queued"}

    return once(db, actor, key, kind, payload, apply)


@app.post(API + "/lab/reprocessing-jobs", status_code=202)
def reprocess(
    body: ReprocessInput,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    require(actor, "researcher")
    if not db.get(Device, str(body.device_id)):
        raise HTTPException(404, "Dispositivo no disponible")
    return queue_job(
        db, actor, idempotency_key, "reprocess", body.model_dump(mode="json")
    )


@app.post(API + "/lab/training-runs", status_code=202)
def train(
    body: JobInput,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    require(actor, "researcher")
    if MODE != "DEMO":
        raise HTTPException(
            409,
            "LAB: modelo todavía no disponible; no se entrenan datos reales en este MVP",
        )
    return queue_job(db, actor, idempotency_key, "training", body.model_dump())


@app.get(API + "/lab/training-runs")
@app.get(API + "/lab/jobs")
def jobs(actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    return [
        public(j)
        for j in db.scalars(
            select(Job)
            .where(Job.actor == actor["id"])
            .order_by(Job.created_at.desc())
            .limit(100)
        )
    ]


@app.get(API + "/lab/training-runs/{ident}")
def job_detail(ident: UUID, actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    j = db.get(Job, str(ident))
    if not j or j.actor != actor["id"]:
        raise HTTPException(404, "Job no disponible")
    return public(j)


@app.post(API + "/lab/exports", status_code=202)
def export(
    body: ExportInput,
    actor=Depends(identity),
    db=Depends(database),
    idempotency_key: str | None = Header(default=None),
):
    require(actor, "researcher")
    if body.kind == "labeled" and MODE == "LAB":
        raise HTTPException(
            409,
            "Dataset etiquetado real no habilitado en v1; exporte crudo autorizado o features",
        )
    return queue_job(db, actor, idempotency_key, "export", body.model_dump(mode="json"))


@app.get(API + "/lab/exports/{ident}/download")
def download(ident: UUID, actor=Depends(identity), db=Depends(database)):
    require(actor, "researcher")
    j = db.get(Job, str(ident))
    if not j or j.actor != actor["id"] or j.kind != "export":
        raise HTTPException(404, "Exportación no disponible")
    if j.state != "completed":
        raise HTTPException(409, "Exportación no terminada")
    if now() >= utc(j.result["expires_at"]):
        raise HTTPException(410, "Exportación vencida")
    path = ARTIFACTS / (j.id + "." + j.payload["format"])
    if not path.is_file():
        raise HTTPException(410, "Exportación eliminada")
    audit(db, actor["id"], "export.download", j.id)
    return FileResponse(
        path,
        filename=f"{MODE}-{j.payload['kind']}.{j.payload['format']}",
        media_type="text/csv"
        if j.payload["format"] == "csv"
        else "application/x-ndjson",
    )

# Product routes are additive; legacy DEMO/LAB tools retain their own contracts.
from .school_api import router as school_router
from .sensor_api import router as sensor_router
app.include_router(school_router)
app.include_router(sensor_router)
from .model_api import router as model_router
app.include_router(model_router)
from .response_history import router as response_history_router
app.include_router(response_history_router)
