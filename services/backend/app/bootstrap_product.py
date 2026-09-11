"""Initial local administrator; institution and pilot stay unconfigured."""
import json
import os
import secrets
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal, User, initialize
from .config import MODE
from .security import hasher
from .phq9 import ensure_phq9


def main():
    if MODE != "REAL":
        raise SystemExit("Use APP_MODE=REAL para iniciar el producto")
    initialize()
    path = Path(".runtime/credentials-product.json")
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        value = {"username": "admin.local", "password": secrets.token_urlsafe(24), "url": "http://127.0.0.1:5174", "notice": "Cuenta de configuración local; no habilita el piloto ni carga datos ficticios"}
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
    value = json.loads(path.read_text())
    with SessionLocal.begin() as db:
        if not db.scalar(select(User).where(User.username == value["username"])):
            db.add(User(username=value["username"], password_hash=hasher.hash(value["password"]), role="admin", scopes=["diagnostics", "raw_location", "models", "raw_export"]))
        ensure_phq9(db)
    print("Producto inicializado; cuenta en .runtime/credentials-product.json")


if __name__ == "__main__":
    main()
