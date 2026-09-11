"""Perfiles con proyectos/volúmenes independientes y secretos aleatorios fuera de Git."""

import os, sys, secrets, subprocess, shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
mode = sys.argv[1].upper()
if mode not in ("DEMO", "LAB"):
    raise SystemExit("Modo no permitido")
if not shutil.which("docker"):
    if mode == "DEMO" and len(sys.argv) == 2:
        print(
            "Docker no está instalado. Iniciando DEMO local SQLite (solo desarrollo).",
            flush=True,
        )
        subprocess.run([sys.executable, "scripts/local.py", "start"], check=True)
        raise SystemExit()
    raise SystemExit("Se requiere Docker Compose para LAB/PostgreSQL. Consulte README.")
p = root / ".runtime" / ("compose-" + mode.lower() + ".env")
p.parent.mkdir(exist_ok=True)
if not p.exists():
    p.write_text(
        f"APP_MODE={mode}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nCOOKIE_SECURE={'true' if mode == 'LAB' else 'false'}\nBIND_ADDRESS=127.0.0.1\nHTTP_PORT={8088 if mode == 'DEMO' else 8089}\nHTTPS_PORT={8443 if mode == 'DEMO' else 8444}\nLAB_HOST=localhost\n"
    )
    p.chmod(0o600)
command = [
    "docker",
    "compose",
    "--env-file",
    str(p),
    "-f",
    "infra/compose.yaml",
    "-p",
    "acompana-" + mode.lower(),
    "--profile",
    mode.lower(),
]


def run(*args):
    subprocess.run(
        command + list(args), check=True, env={**os.environ, "APP_MODE": mode}
    )


if len(sys.argv) > 2:
    run(*sys.argv[2:])
    raise SystemExit()
run("build")
run("up", "-d", "db")
run("run", "--rm", "api", "alembic", "upgrade", "head")
run("run", "--rm", "api", "python", "-m", "app.cli", "init")
if mode == "DEMO":
    run("run", "--rm", "api", "python", "-m", "app.cli", "seed")
run("up", "-d")
print("Entorno iniciado:", mode, "; puertos y credenciales en README y .runtime/")
