import hashlib, secrets, json
from datetime import timedelta
from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from argon2 import PasswordHasher
from .db import *
from .config import MODE

hasher = PasswordHasher()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def database():
    with SessionLocal() as db:
        guard(db)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def identity(request: Request, db=Depends(database)):
    auth = request.headers.get("authorization", "")
    bearer = auth.startswith("Bearer ")
    token = auth[7:] if bearer else request.cookies.get("session", "")
    session = db.scalar(
        select(Session).where(
            Session.token_hash == digest(token),
            Session.environment == MODE,
            Session.revoked == False,
        )
    )
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "Sesión inválida o vencida")
    if session.device_id:
        if not bearer:
            raise HTTPException(401, "Se requiere token de dispositivo")
        device = db.scalar(
            select(Device).where(Device.id == session.device_id).with_for_update()
        )
        if not device or device.status == "revoked":
            raise HTTPException(401, "Dispositivo revocado")
        return {
            "id": device.id,
            "role": "participant",
            "device": device,
            "session": session,
            "scopes": [],
        }
    if bearer:
        raise HTTPException(401, "La sesión web requiere cookie")
    user = db.scalar(
        select(User)
        .where(User.id == session.user_id, User.environment == MODE)
        .with_for_update()
    )
    if not user:
        raise HTTPException(401, "Cuenta no disponible")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
        request.headers.get("x-csrf-token", ""), session.csrf
    ):
        raise HTTPException(403, "CSRF inválido")
    return {
        "id": user.id,
        "role": user.role,
        "session": session,
        "scopes": user.scopes,
        "username": user.username,
    }


def require(actor, *roles):
    if actor["role"] not in roles:
        raise HTTPException(403, "Acceso no autorizado para este rol")


def assigned(db, actor, participant_id):
    if MODE == "REAL":
        from .school_core import access
        access(db, actor, participant_id)
        return
    require(actor, "psychologist")
    if not db.scalar(
        select(Assignment).where(
            Assignment.user_id == actor["id"],
            Assignment.participant_id == participant_id,
            Assignment.environment == MODE,
        )
    ):
        raise HTTPException(404, "Participante no disponible")


def own_device(actor, active=False):
    require(actor, "participant")
    device = actor["device"]
    if active and device.status != "active":
        raise HTTPException(
            409, "La participación está pausada o no tiene consentimiento"
        )
    return device


def once(db, actor, key, route, body, fn):
    if not key or len(key) > 120:
        raise HTTPException(422, "Idempotency-Key requerido (máximo 120 caracteres)")
    signature = digest(json.dumps(body, sort_keys=True, default=str))
    old = db.scalar(
        select(Idempotency).where(
            Idempotency.actor == actor["id"],
            Idempotency.key == key,
            Idempotency.route == route,
        )
    )
    if old:
        if old.digest != signature:
            raise HTTPException(409, "Clave idempotente reutilizada con otro contenido")
        return old.result
    result = fn()
    db.add(
        Idempotency(
            actor=actor["id"], key=key, route=route, digest=signature, result=result
        )
    )
    db.flush()
    return result


def audit(db, actor, action, target=None):
    db.add(Audit(actor=actor, action=action, target=target))
