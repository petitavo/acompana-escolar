import os, sys, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if os.environ.get("APP_MODE", "DEMO") != "DEMO":
    raise SystemExit("Reset prohibido en LAB")
if (root / ".runtime/local-processes.json").exists():
    subprocess.run([sys.executable, "scripts/local.py", "stop"], check=True)
for name in ("demo.db", "demo.db-shm", "demo.db-wal", "credentials-demo.json"):
    (root / ".runtime" / name).unlink(missing_ok=True)
print("Solo DEMO local reiniciado. LAB y volúmenes Docker no se han modificado.")
