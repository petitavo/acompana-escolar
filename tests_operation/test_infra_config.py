"""Static checks on the REAL infra: fail-closed secrets, hardening, HTTPS headers."""
from pathlib import Path

import pytest

INFRA = Path(__file__).resolve().parents[1] / "infra"


def read(name):
    return (INFRA / name).read_text()


def test_compose_real_has_no_insecure_defaults():
    c = read("compose.REAL.yaml")
    assert "CHANGE_ME" not in c
    assert "${POSTGRES_PASSWORD:?" in c
    assert ":-changeme" not in c.lower()
    # secret must not carry an inline default value
    assert "POSTGRES_PASSWORD:-" not in c


def test_compose_real_hardening():
    c = read("compose.REAL.yaml")
    assert "no-new-privileges:true" in c
    assert "cap_drop" in c
    assert "internal: true" in c
    assert 'COOKIE_SECURE: "true"' in c
    assert "APP_MODE: REAL" in c
    assert 'ALLOW_EXTERNAL_NOTIFICATIONS: "true"' not in c


def test_compose_real_distinguishes_worker_health():
    c = read("compose.REAL.yaml")
    assert "worker-healthcheck.py" in c
    assert "/healthcheck.py" in c
    # api + db + worker + web each declare a healthcheck
    assert c.count("healthcheck:") >= 4


def test_worker_healthcheck_script_is_process_only():
    s = read("worker-healthcheck.py")
    assert "worker.main" in s
    assert "PASSWORD" not in s.upper()
    assert "DATABASE_URL" not in s


def test_proxy_binds_loopback_by_default():
    c = read("compose.REAL.yaml")
    assert "${BIND_ADDRESS:-127.0.0.1}" in c


def test_caddy_real_internal_ca_and_locked_admin():
    c = read("Caddyfile.REAL")
    assert "admin off" in c
    assert "tls internal" in c
    assert "X-Frame-Options" in c


def test_caddy_public_has_hsts_and_acme():
    c = read("Caddyfile.PUBLIC")
    assert "Strict-Transport-Security" in c
    assert "admin off" in c
    assert "{$SCHOOL_ACME_EMAIL}" in c


def test_operation_env_example_has_placeholders_only():
    e = read("operation.env.example")
    assert "POSTGRES_PASSWORD=\n" in e or "POSTGRES_PASSWORD=  " in e or "POSTGRES_PASSWORD=            #" in e
    # no obviously real secret committed
    for line in e.splitlines():
        if line.startswith("POSTGRES_PASSWORD=") or line.startswith("SCHOOL_ACME_EMAIL=") or line.startswith("BACKUP_KEY_FILE="):
            assert line.split("=", 1)[1].strip().split("#")[0].strip() == ""


def test_shared_env_example_untouched_by_ops():
    shared = INFRA.parent / ".env.example"
    assert "operation.env" not in shared.read_text()


def test_public_overlay_is_thin():
    c = read("compose.PUBLIC.yaml")
    assert "proxy:" in c
    assert "443:443" in c
    # overlay must not redeclare db/api credentials
    assert "POSTGRES_PASSWORD" not in c


@pytest.mark.parametrize("script", ["deploy/prepare_host.sh"])
def test_prepare_host_does_not_publish(script):
    s = read(script)
    assert "up -d" not in s.split("Pasos manuales")[0]  # no `up` before the manual-steps notice
    assert "set -euo pipefail" in s
