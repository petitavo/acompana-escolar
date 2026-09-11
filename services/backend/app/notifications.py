"""Inbox always works. FCM is opt-in and never equates provider acceptance to delivery."""
import os
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select
from .db import Case, CaseEvent, Device, Response, Job, now, utc
from .school_db import Notification, PushToken, Institution, StudentProfile, Followup, Membership
from .school_core import settings, notify, authorization_status, grant_case_access


def channel_status():
    file = os.getenv("FCM_SERVICE_ACCOUNT", "")
    return {"inbox": "available", "push": "configured" if file and Path(file).is_file() else "requires_credentials", "delivery": "FCM accepted → sent; device receipt → delivered", "email": "configured" if os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM") else "requires_credentials", "external_sending": os.getenv("ALLOW_EXTERNAL_NOTIFICATIONS", "false") == "true"}


def send_push(token, notification):
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import requests
    file = os.environ["FCM_SERVICE_ACCOUNT"]
    credentials = service_account.Credentials.from_service_account_file(file, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
    credentials.refresh(Request())
    response = requests.post(f"https://fcm.googleapis.com/v1/projects/{credentials.project_id}/messages:send", headers={"Authorization": "Bearer " + credentials.token}, json={"message": {"token": token, "data": {"notification_id": notification.id}, "android": {"priority": "normal"}}}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError("FCM no aceptó el mensaje")
    receipt = response.json().get("name")
    if not receipt:
        raise RuntimeError("FCM no devolvió identificador de aceptación")
    return receipt


def recipient_institution(db, recipient):
    m = db.scalar(select(Membership).where(Membership.user_id == recipient, Membership.active == True))
    if m:
        return db.get(Institution, m.institution_id)
    d = db.get(Device, recipient)
    if d and d.status != "revoked":
        p = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == d.participant_id))
        return db.get(Institution, p.institution_id) if p else None
    return None


def valid_email(value):
    import re
    return isinstance(value, str) and len(value) <= 254 and bool(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value))


def send_email(address, notification):
    """SMTP acceptance is a handoff, not proof of inbox delivery or reading."""
    import smtplib, ssl
    from email.message import EmailMessage
    from urllib.parse import urlparse
    sender = os.environ["SMTP_FROM"]
    if not valid_email(address) or not valid_email(sender):
        raise ValueError("Dirección inválida")
    host = os.environ["SMTP_HOST"]
    mode = os.getenv("SMTP_SECURITY", "starttls")
    if mode not in ("starttls", "tls") and not (mode == "test_plain" and host in ("127.0.0.1", "localhost", "::1")):
        raise ValueError("SMTP requiere TLS; transporte plano solo para pruebas locales")
    message = EmailMessage()
    message["From"], message["To"] = sender, address
    message["Subject"] = "Tienes una notificación en Acompaña Escolar"
    message["Message-ID"] = f"<{notification.id}@{sender.split('@')[1]}>"
    content = "Abre Acompaña Escolar para revisar tu bandeja de notificaciones."
    url = os.getenv("SCHOOL_PUBLIC_URL", "")
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc and not parsed.query and not parsed.fragment and not parsed.username:
        content += "\n" + url
    message.set_content(content)
    port = int(os.getenv("SMTP_PORT", "465" if mode == "tls" else "587"))
    smtp = smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) if mode == "tls" else smtplib.SMTP(host, port, timeout=15)
    with smtp:
        if mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        user = os.getenv("SMTP_USER")
        if user:
            path = os.getenv("SMTP_PASSWORD_FILE")
            password = Path(path).read_text().strip() if path else os.getenv("SMTP_PASSWORD", "")
            smtp.login(user, password)
        if smtp.send_message(message):
            raise RuntimeError("SMTP rechazó el destinatario")
    return str(message["Message-ID"])


def dispatch(db, at=None):
    at = at or now()
    for n in db.scalars(select(Notification).where(Notification.state.in_(["created", "sent", "delivered"]), Notification.due_at <= at).order_by(Notification.created_at.desc()).with_for_update(skip_locked=True).limit(200)):
        i = recipient_institution(db, n.recipient_id)
        cfg = settings(i) if i else {}
        if not cfg.get("external_notifications_authorized") or os.getenv("ALLOW_EXTERNAL_NOTIFICATIONS") != "true":
            continue
        membership = db.scalar(select(Membership).where(Membership.user_id == n.recipient_id, Membership.active == True))
        device = db.get(Device, n.recipient_id)
        student = db.scalar(select(StudentProfile).where(StudentProfile.participant_id == device.participant_id)) if device else None
        if membership and not membership.preferences.get("reminders", True) or student and not student.policy.get("reminders", True):
            continue
        tokens = list(db.scalars(select(PushToken).where(PushToken.owner_id == n.recipient_id)))
        address = membership.preferences.get("notification_email") if membership else None
        channels = dict(n.detail.get("channels", {}))
        for channel, enabled in (("push", bool(tokens) and channel_status()["push"] == "configured"),
                                 ("email", valid_email(address) and channel_status()["email"] == "configured")):
            state = dict(channels.get(channel, {}))
            attempts = state.get("attempts", 0)
            if not enabled or state.get("state") == "accepted" or attempts >= 3 or state.get("next_attempt_at") and utc(state["next_attempt_at"]) > at:
                continue
            state["attempts"] = attempts + 1
            try:
                # Track each token independently to avoid retrying accepted devices.
                accepted = dict(state.get("accepted_tokens", {}))
                if channel == "push":
                    for token in tokens:
                        if token.token_hash not in accepted:
                            accepted[token.token_hash] = send_push(token.token, n)
                    state["accepted_tokens"] = accepted
                else:
                    send_email(address, n)
                state.update(state="accepted", accepted_at=at.isoformat())
                if n.state == "created":
                    n.state = "sent"
            except Exception:
                if channel == "push":
                    state["accepted_tokens"] = accepted
                state.update(state="failed" if attempts + 1 >= 3 else "retry_pending",
                             error="No se confirmó aceptación del proveedor",
                             next_attempt_at=(at + timedelta(minutes=5 * (attempts + 1))).isoformat())
            channels[channel] = state
        n.detail = {**n.detail, "channels": channels}


def maintain_notifications(db, at=None):
    from zoneinfo import ZoneInfo
    at = at or now()
    for n in list(db.scalars(select(Notification).where(Notification.kind == "case", Notification.acknowledged_at == None))):
        case = db.get(Case, n.detail.get("case_id"))
        if not case or case.state != "new" or utc(n.detail["ack_due_at"]) > at:
            continue
        i = db.get(Institution, n.detail.get("institution_id"))
        if not i:
            continue
        cfg = settings(i)
        backup = cfg.get("backup_id")
        if backup:
            # A03: escalation must not be a dead end. Grant the *current* backup scoped
            # access to exactly this case (fixed window, not extended on later ticks).
            # If the institution changed the backup, drop any stale escalation grant for
            # this case held by someone who is no longer the backup.
            from .school_core import revoke_stale_escalation_grants
            revoke_stale_escalation_grants(db, case.id, backup)
            grant = grant_case_access(db, case, backup, "escalation")
            escalation = notify(db, backup, f"escalation:{n.id}:{backup}", "escalation", "Una revisión requiere reconocimiento", {"case_id": case.id, "origin_notification": n.id, "ack_due_at": (at + timedelta(minutes=cfg["escalation_minutes"])).isoformat(), "case_access_expires_at": grant.expires_at.isoformat(), "scope": "solo este caso"})
            if not n.detail.get("escalated_at"):
                n.detail = {**n.detail, "escalated_at": at.isoformat()}
                db.add(CaseEvent(case_id=case.id, actor="worker", kind="escalated_to_backup", detail={"notification_id": escalation.id, "at": at.isoformat()}))
            if not escalation.acknowledged_at and utc(escalation.detail["ack_due_at"]) <= at and cfg.get("primary_id"):
                notify(db, cfg["primary_id"], "escalation-unack:" + escalation.id, "escalation", "Sigue pendiente una revisión del equipo", {"case_id": case.id})
    for f in db.scalars(select(Followup).where(Followup.state.in_(["pending", "confirmed"]))):
        owner = db.scalar(select(Membership).where(Membership.user_id == f.owner_id, Membership.active == True))
        if not owner or not owner.preferences.get("reminders", True):
            continue
        local = at.astimezone(ZoneInfo(settings(db.get(Institution, owner.institution_id))["timezone"]))
        if utc(f.due_at) - timedelta(hours=1) <= at and local.strftime("%H:%M") >= owner.preferences.get("reminder_time", "08:00"):
            notify(db, f.owner_id, "followup-due:" + f.id, "followup", "Tienes un seguimiento por realizar", {"case_id": f.case_id, "followup_id": f.id})
    for p in db.scalars(select(StudentProfile)):
        i = db.get(Institution, p.institution_id)
        cfg = settings(i)
        if not cfg["instrument_enabled"] or not p.policy.get("reminders", True) or not authorization_status(db, p)["ready"]:
            continue
        local = at.astimezone(ZoneInfo(cfg["timezone"]))
        if local.strftime("%H:%M") < p.policy.get("reminder_time", "17:00"):
            continue
        last = db.scalar(select(Response).where(Response.participant_id == p.participant_id).order_by(Response.created_at.desc()))
        if last and utc(last.detail.get("applied_at", last.created_at)) + timedelta(days=cfg["cadence_days"]) > at:
            continue
        for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id, Device.status != "revoked")):
            notify(db, d.id, f"questionnaire-due:{d.id}:{local.date()}", "reminder", "Tienes un cuestionario disponible", {"date": str(local.date())})
    dispatch(db, at)
