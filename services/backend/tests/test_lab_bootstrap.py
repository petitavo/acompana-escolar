"""Provisioning must survive retries without replacing credentials or consent."""

import os
from pathlib import Path
import subprocess
import sys


def test_lab_bootstrap_is_idempotent_and_does_not_consent(tmp_path):
    code = r'''
import json
from pathlib import Path
from sqlalchemy import select, func
from app.db import *
from app.bootstrap_lab import bootstrap
from app.security import digest
initialize()
path = Path("credentials.json")
bootstrap(path)
original = path.read_text()
with SessionLocal.begin() as db:
    invitation = db.scalar(select(Invitation))
    invitation.used = True
bootstrap(path)
assert path.read_text() == original
assert path.stat().st_mode & 0o777 == 0o600
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(User)) == 3
    assert db.scalar(select(func.count()).select_from(Participant)) == 1
    assert db.scalar(select(func.count()).select_from(Assignment)) == 1
    assert db.scalar(select(func.count()).select_from(Invitation)) == 1
    assert db.scalar(select(Invitation)).used
    assert db.scalar(select(func.count()).select_from(Consent)) == 0
    assert db.scalar(select(func.count()).select_from(Device)) == 0
    assert db.scalar(select(func.count()).select_from(RawEvent)) == 0
with SessionLocal.begin() as db:
    db.scalar(select(Participant)).status = "revoked"
try:
    bootstrap(path)
except RuntimeError:
    pass
else:
    raise AssertionError("No debe reactivar participantes retirados")
'''
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, 'PYTHONPATH': str(backend), 'APP_MODE': 'LAB', 'COOKIE_SECURE': 'true', 'DATABASE_URL': f'sqlite:///{tmp_path}/test.db', 'ARTIFACT_DIR': str(tmp_path / 'artifacts')},
    )
    assert result.returncode == 0, result.stderr


def test_lab_bootstrap_refuses_demo(tmp_path):
    from app.bootstrap_lab import bootstrap
    import pytest

    with pytest.raises(RuntimeError, match='APP_MODE=LAB'):
        bootstrap(tmp_path / 'credentials.json')
    assert not (tmp_path / 'credentials.json').exists()
