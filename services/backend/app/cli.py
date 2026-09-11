import argparse, json, secrets, getpass
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from .db import *
from .security import hasher, digest
from .config import MODE
from .forms import validate_definition, ensure_demo_form


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    seed = sub.add_parser("seed")
    seed.add_argument("--end", default="2026-09-05")
    seed.add_argument("--seed", type=int, default=20260906)
    u = sub.add_parser("create-user")
    u.add_argument("username")
    u.add_argument(
        "--role", choices=["admin", "psychologist", "researcher"], required=True
    )
    p = sub.add_parser("invite")
    p.add_argument("pseudonym")
    p.add_argument("--group", default="Laboratorio")
    a = sub.add_parser("assign")
    a.add_argument("username")
    a.add_argument("pseudonym")
    f = sub.add_parser("import-instrument")
    f.add_argument("path")
    f.add_argument("--enable", action="store_true")
    sub.add_parser("worker-once")
    sub.add_parser("openapi")
    adapter = sub.add_parser("inspect-dataset")
    adapter.add_argument("path")
    adapter.add_argument("manifest")
    args = parser.parse_args()
    if args.cmd == "init":
        initialize()
        with SessionLocal.begin() as db:
            ensure_demo_form(db)
        print("Base inicializada:", MODE)
        return
    if args.cmd == "openapi":
        from .main import app

        Path("packages/contracts/openapi.json").write_text(
            json.dumps(app.openapi(), ensure_ascii=False, indent=2)
        )
        return
    if args.cmd == "worker-once":
        from worker.main import run_one

        print(run_one())
        return
    if args.cmd == "inspect-dataset":
        from ml.import_adapter import inspect

        print(json.dumps(inspect(args.path, args.manifest), indent=2))
        return
    with SessionLocal.begin() as db:
        guard(db)
        if args.cmd == "seed":
            from fixtures.generate import generate

            result = generate(db, args.seed, args.end)
            Path(".runtime").mkdir(exist_ok=True)
            path = Path(".runtime/credentials-demo.json")
            if "credentials" in result:
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                path.chmod(0o600)
            print("DEMO inicializado. Credenciales locales:", path)
        elif args.cmd == "create-user":
            password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
            if len(password) < 12:
                raise ValueError("Mínimo 12 caracteres")
            db.add(
                User(
                    username=args.username,
                    role=args.role,
                    password_hash=hasher.hash(password),
                )
            )
        elif args.cmd == "invite":
            if not args.pseudonym.startswith(MODE + "-"):
                raise ValueError("Seudónimo debe comenzar con " + MODE + "-")
            p = db.scalar(
                select(Participant).where(Participant.pseudonym == args.pseudonym)
            )
            if not p:
                p = Participant(pseudonym=args.pseudonym, group=args.group)
                db.add(p)
                db.flush()
            token = secrets.token_urlsafe(24)
            db.add(
                Invitation(
                    participant_id=p.id,
                    token_hash=digest(token),
                    expires_at=now() + timedelta(days=1),
                )
            )
            print("Invitación de un uso:", token)
        elif args.cmd == "assign":
            user = db.scalar(
                select(User).where(
                    User.username == args.username, User.role == "psychologist"
                )
            )
            p = db.scalar(
                select(Participant).where(Participant.pseudonym == args.pseudonym)
            )
            if not user or not p:
                raise ValueError("Cuenta psicólogo o participante no encontrado")
            db.add(Assignment(user_id=user.id, participant_id=p.id))
        elif args.cmd == "import-instrument":
            definition = validate_definition(json.loads(Path(args.path).read_text()))
            if args.enable and definition["real"]:
                required = {"responsible", "coverage", "acknowledgement", "escalation"}
                if not required.issubset(definition["protocol"]) or not all(
                    definition["protocol"][k].strip() for k in required
                ):
                    raise ValueError("Falta protocolo de atención revisado")
                raise ValueError(
                    "Instrumentos reales se importan deshabilitados en v1. Habilitación requiere implementación y prueba específica del protocolo; use CHECKIN_DEMO_V1"
                )
            db.add(
                Instrument(
                    code=definition["instrument_id"],
                    definition=definition,
                    enabled=args.enable,
                )
            )


if __name__ == "__main__":
    main()
