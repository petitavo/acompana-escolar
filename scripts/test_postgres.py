"""Isolated native PostgreSQL test cluster; never uses a user's existing database."""

import subprocess, os, secrets, json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
pgroot = root / ".tooling/postgres/root"
bin = pgroot / "usr/lib/postgresql/18/bin"
data = root / ".runtime/postgres-test"
pwfile = root / ".runtime/postgres-password"
password = secrets.token_urlsafe(24)
if pwfile.exists():
    password = pwfile.read_text().strip()
else:
    pwfile.write_text(password)
    pwfile.chmod(0o600)
env = {
    **os.environ,
    "LD_LIBRARY_PATH": str(pgroot / "usr/lib/x86_64-linux-gnu"),
    "PGPASSWORD": password,
    "PGUSER": "lab_test",
    "PGHOST": "127.0.0.1",
    "PGPORT": "55432",
}


def run(*args, **kw):
    return subprocess.run([str(a) for a in args], env=env, check=True, **kw)


if not data.exists():
    run(
        bin / "initdb",
        "-D",
        data,
        "-L",
        pgroot / "usr/share/postgresql/18",
        "--username=lab_test",
        "--auth=scram-sha-256",
        "--pwfile=" + str(pwfile),
        stdout=subprocess.DEVNULL,
    )
run(
    bin / "pg_ctl",
    "-D",
    data,
    "-l",
    root / ".runtime/postgres.log",
    "-o",
    "-h 127.0.0.1 -p 55432 -k /tmp",
    "start",
)
try:
    subprocess.run([str(bin / "createdb"), "lab_tests"], env=env, capture_output=True)
    testenv = {
        **env,
        "TEST_DATABASE_URL": f"postgresql+psycopg://lab_test:{password}@127.0.0.1:55432/lab_tests",
        "PYTHONPATH": "services/backend:.",
    }
    with (root / ".runtime/pytest-postgres.log").open("w") as f:
        subprocess.run(
            [str(root / ".venv/bin/pytest"), "-q"],
            env=testenv,
            stdout=f,
            stderr=subprocess.STDOUT,
            check=True,
        )
    subprocess.run([str(bin / "dropdb"), "--if-exists", "lab_migrations"], env=env, check=True)
    subprocess.run(
        [str(bin / "createdb"), "lab_migrations"], env=env, capture_output=True
    )
    menv = {
        **env,
        "DATABASE_URL": f"postgresql+psycopg://lab_test:{password}@127.0.0.1:55432/lab_migrations",
        "PYTHONPATH": "services/backend:.",
    }
    subprocess.run(
        [str(root / ".venv/bin/alembic"), "upgrade", "head"], env=menv, check=True
    )
    subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "app.cli", "init"], env=menv, check=True
    )
    print("PostgreSQL: tests y migración completados")
finally:
    run(bin / "pg_ctl", "-D", data, "stop")
