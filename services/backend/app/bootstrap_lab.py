"""Provision initial LAB accounts from the server console; never an HTTP endpoint."""

import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from .config import MODE
from .db import Assignment, Invitation, Participant, SessionLocal, User, guard, now
from .security import digest, hasher


def bootstrap(path: Path) -> dict:
    if MODE != "LAB":
        raise RuntimeError("El aprovisionamiento de cuentas reales exige APP_MODE=LAB")
    roles = {"psicologo.lab": "psychologist", "investigador.lab": "researcher", "admin.lab": "admin"}
    # Persist generated secrets before the transaction so a failed/repeated setup
    # can reuse them without rotating established credentials or invitations.
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        values = {
            "mode": "LAB",
            "participant": "LAB-001",
            "credentials": {name: secrets.token_urlsafe(24) for name in roles},
            "invitation": secrets.token_urlsafe(32),
            "invitation_expires_at": (now() + timedelta(days=1)).isoformat(),
            "notice": "Invitación para Android de un uso y 24 horas; no es un usuario web.",
        }
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            json.dump(values, out, indent=2, ensure_ascii=False)
    path.chmod(0o600)
    values = json.loads(path.read_text())
    if values["mode"] != "LAB" or values["participant"] != "LAB-001":
        raise RuntimeError("Archivo de credenciales incompatible")
    with SessionLocal.begin() as db:
        guard(db)
        users = {}
        for name, role in roles.items():
            user = db.scalar(select(User).where(User.username == name))
            if user is None:
                user = User(username=name, role=role, password_hash=hasher.hash(values["credentials"][name]))
                db.add(user)
                db.flush()
            elif user.environment != MODE or user.role != role or not hasher.verify(user.password_hash, values["credentials"][name]):
                raise RuntimeError("Cuenta existente incompatible; no se cambia su contraseña")
            users[name] = user
        participant = db.scalar(select(Participant).where(Participant.pseudonym == values["participant"]))
        if participant is None:
            participant = Participant(pseudonym=values["participant"], group="Prueba Android adultos")
            db.add(participant)
            db.flush()
        if participant.environment != MODE or participant.status == "revoked":
            raise RuntimeError("Participante incompatible o revocado; no se reactiva")
        invitation = db.scalar(select(Invitation).where(Invitation.token_hash == digest(values["invitation"])))
        if invitation is None:
            from datetime import datetime

            db.add(Invitation(participant_id=participant.id, token_hash=digest(values["invitation"]), expires_at=datetime.fromisoformat(values["invitation_expires_at"])))
        if not db.scalar(select(Assignment).where(Assignment.user_id == users["psicologo.lab"].id, Assignment.participant_id == participant.id)):
            db.add(Assignment(user_id=users["psicologo.lab"].id, participant_id=participant.id))
    return {"mode": MODE, "participant": values["participant"], "credentials_file": str(path)}


if __name__ == "__main__":
    print(json.dumps(bootstrap(Path(".runtime/credentials-lab.json"))))
