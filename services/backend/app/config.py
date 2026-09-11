import os
from pathlib import Path

MODE = os.getenv("APP_MODE", "DEMO")
if MODE not in ("DEMO", "LAB", "REAL"):
    raise RuntimeError("APP_MODE debe ser DEMO, LAB o REAL")
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{Path.cwd()}/.runtime/{MODE.lower()}.db"
)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
LOCAL_PRODUCT = os.getenv("LOCAL_PRODUCT", "false").lower() == "true"
PILOT_ENABLED = os.getenv("PILOT_ENABLED", "false").lower() == "true"
if MODE in ("LAB", "REAL") and not COOKIE_SECURE and not (MODE == "REAL" and LOCAL_PRODUCT and not PILOT_ENABLED):
    raise RuntimeError("LAB exige cookies Secure y HTTPS")
ARTIFACTS = Path(os.getenv("ARTIFACT_DIR", ".runtime/artifacts")) / MODE
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ARTIFACTS.chmod(0o700)
FEATURE_VERSION = "screen-v1.0"
CONSENT_VERSION = "lab-v1"
RAW_RETENTION_DAYS = int(os.getenv("RAW_RETENTION_DAYS", "7"))
FEATURE_RETENTION_DAYS = int(os.getenv("FEATURE_RETENTION_DAYS", "90"))
EXPORT_TTL_HOURS = int(os.getenv("EXPORT_TTL_HOURS", "24"))
if not (
    1 <= RAW_RETENTION_DAYS <= 30
    and 1 <= FEATURE_RETENTION_DAYS <= 365
    and 1 <= EXPORT_TTL_HOURS <= 24
):
    raise RuntimeError("Retención fuera de límites de laboratorio")
