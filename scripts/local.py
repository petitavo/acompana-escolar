import os, sys, json, subprocess, signal, time, socket
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
runtime = root / ".runtime"
runtime.mkdir(exist_ok=True)
pidfile = runtime / "local-processes.json"


def run(*args):
    subprocess.run(list(args), check=True, env=env)


env = {
    **os.environ,
    "APP_MODE": "DEMO",
    "COOKIE_SECURE": "false",
    "PYTHONPATH": str(root / "services/backend") + ":" + str(root),
    "DATABASE_URL": "sqlite:///" + str(runtime / "demo.db"),
}
if sys.argv[1] == "stop":
    if pidfile.exists():
        for pid in json.loads(pidfile.read_text()):
            try:
                cwd = Path(f"/proc/{pid}/cwd").resolve(strict=True)
                if cwd == root or root in cwd.parents:
                    os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, FileNotFoundError):
                pass
        pidfile.unlink()
    raise SystemExit()
for port in (8000, 5173):
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(
                f"Puerto {port} ocupado. No se detiene un proceso ajeno; use el servidor ya iniciado o libere el puerto."
            )
if not (root / ".venv/bin/python").exists():
    raise SystemExit("Ejecute make bootstrap primero")
run(str(root / ".venv/bin/alembic"), "upgrade", "head")
run(str(root / ".venv/bin/python"), "-m", "app.cli", "init")
run(str(root / ".venv/bin/python"), "-m", "app.cli", "seed")
processes = []
for name, cmd, cwd in [
    (
        "api",
        [
            str(root / ".venv/bin/uvicorn"),
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        root,
    ),
    ("worker", [str(root / ".venv/bin/python"), "-m", "worker.main"], root),
    ("web", ["npm", "run", "dev"], root / "apps/web"),
]:
    with (runtime / (name + ".log")).open("a") as log:
        p = subprocess.Popen(
            cmd, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True
        )
        processes.append(p.pid)
pidfile.write_text(json.dumps(processes))
print(
    "DEMO local: http://127.0.0.1:5173 · credenciales: .runtime/credentials-demo.json"
)
