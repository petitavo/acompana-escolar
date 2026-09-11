"""Local school product on an isolated PostgreSQL cluster, without public hosting."""
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
os.chdir(root)
runtime = root / ".runtime"
runtime.mkdir(exist_ok=True)
pidfile = runtime / "product-processes.json"
pgroot = root / ".tooling/postgres/root"
pgbin = pgroot / "usr/lib/postgresql/18/bin"
data = runtime / "postgres-product"
pwfile = runtime / "product-db-password"
if not pwfile.exists():
    with os.fdopen(os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        out.write(secrets.token_urlsafe(32))
password = pwfile.read_text().strip()
env = {**os.environ, "LD_LIBRARY_PATH": str(pgroot / "usr/lib/x86_64-linux-gnu"), "PGUSER": "acompana_product", "PGPASSWORD": password, "PGHOST": "127.0.0.1", "PGPORT": "55433", "APP_MODE": "REAL", "LOCAL_PRODUCT": "true", "PILOT_ENABLED": "false", "COOKIE_SECURE": "false", "PYTHONPATH": str(root / "services/backend") + ":" + str(root), "DATABASE_URL": f"postgresql+psycopg://acompana_product:{password}@127.0.0.1:55433/acompana_product", "VITE_API_TARGET": "http://127.0.0.1:8001"}


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], env=env, check=True, **kwargs)


action = sys.argv[1] if len(sys.argv) > 1 else "start"
if action == "stop":
    if pidfile.exists():
        for pid in json.loads(pidfile.read_text()):
            try:
                cwd = Path(f"/proc/{pid}/cwd").resolve(strict=True)
                if cwd == root or root in cwd.parents:
                    os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, FileNotFoundError):
                pass
        pidfile.unlink()
    if (data / "postmaster.pid").exists():
        run(pgbin / "pg_ctl", "-D", data, "stop")
    raise SystemExit()
if action == "exec":
    run(*sys.argv[2:])
    raise SystemExit()
if not (pgbin / "postgres").exists():
    raise SystemExit("Falta PostgreSQL local. Use infra/compose.REAL.yaml o configure las herramientas indicadas en docs/producto.md")
for port in (8001, 5174):
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"Puerto {port} ocupado; no se detiene un proceso ajeno")
if not data.exists():
    run(pgbin / "initdb", "-D", data, "-L", pgroot / "usr/share/postgresql/18", "--username=acompana_product", "--auth=scram-sha-256", "--pwfile=" + str(pwfile), stdout=subprocess.DEVNULL)
if not (data / "postmaster.pid").exists():
    run(pgbin / "pg_ctl", "-D", data, "-l", runtime / "postgres-product.log", "-o", "-h 127.0.0.1 -p 55433 -k /tmp", "start")
result = run(pgbin / "psql", "-d", "postgres", "-Atc", "SELECT 1 FROM pg_database WHERE datname='acompana_product'", capture_output=True, text=True)
if result.stdout.strip() != "1":
    run(pgbin / "createdb", "acompana_product")
run(root / ".venv/bin/alembic", "upgrade", "head")
run(root / ".venv/bin/python", "-m", "app.bootstrap_product")
processes = []
for name, command, cwd in [
    ("product-api", [str(root / ".venv/bin/uvicorn"), "app.main:app", "--host", "127.0.0.1", "--port", "8001", "--no-access-log"], root),
    ("product-worker", [str(root / ".venv/bin/python"), "-m", "worker.main"], root),
    ("product-web", ["npm", "run", "dev", "--", "--port", "5174"], root / "apps/web"),
]:
    with (runtime / (name + ".log")).open("a") as log:
        processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True).pid)
pidfile.write_text(json.dumps(processes))
print("Acompaña Escolar: http://127.0.0.1:5174 · PostgreSQL independiente · piloto apagado")
