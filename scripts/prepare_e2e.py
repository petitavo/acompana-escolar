"""Caso DEMO aislado en participante ficticio existente; permite repetir el recorrido."""

import json
from sqlalchemy import select
from app.db import *
from app.config import MODE
from app.cases import add_reason

if MODE != "DEMO":
    raise SystemExit("Solo DEMO")
with SessionLocal.begin() as db:
    p = db.scalar(select(Participant).where(Participant.pseudonym == "DEMO-001"))
    c = add_reason(db, p.id, "contact_request", {"synthetic": True, "source": "e2e"})
    print(json.dumps({"case_id": c.id, "participant_id": p.id}))
