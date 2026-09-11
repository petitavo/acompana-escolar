import os, tempfile

os.environ["APP_MODE"] = "DEMO"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL"
) or "sqlite:///" + tempfile.mktemp(prefix="acompana-tests-", suffix=".db")
os.environ["ARTIFACT_DIR"] = tempfile.mkdtemp(prefix="acompana-artifacts-")
import pytest
from fastapi.testclient import TestClient
from app.db import *
from app.main import app
from app.security import hasher, digest
from app.forms import ensure_demo_form
from datetime import timedelta


@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine)
    initialize()
    with SessionLocal.begin() as db:
        ensure_demo_form(db)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def users():
    result = {}
    with SessionLocal.begin() as db:
        for role in ["psychologist", "researcher", "admin"]:
            u = User(
                username=role, password_hash=hasher.hash("test-password-123"), role=role
            )
            db.add(u)
            db.flush()
            result[role] = u.id
    return result


def login(client, role):
    r = client.post(
        "/api/v1/auth/login", json={"username": role, "password": "test-password-123"}
    )
    assert r.status_code == 200, r.text
    client.headers["x-csrf-token"] = r.json()["csrf_token"]
    return r.json()


@pytest.fixture
def phone(client):
    with SessionLocal.begin() as db:
        p = Participant(pseudonym="DEMO-TEST")
        db.add(p)
        db.flush()
        db.add(
            Invitation(
                token_hash=digest("test-invitation-123456"),
                participant_id=p.id,
                expires_at=now() + timedelta(days=1),
            )
        )
        pid = p.id
    response = client.post(
        "/api/v1/enrollments/redeem",
        json={
            "invitation": "test-invitation-123456",
            "device": {
                "android_api": 35,
                "manufacturer": "Ficticio",
                "model": "Fixture",
                "app_version": "test",
                "timezone": "America/Lima",
            },
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    client.headers["authorization"] = "Bearer " + data["token"]
    r = client.post(
        "/api/v1/me/participation-events",
        headers={"Idempotency-Key": "consent"},
        json={
            "action": "consent",
            "occurred_at": (now() - timedelta(hours=4)).isoformat(),
            "adult": True,
        },
    )
    assert r.status_code == 200, r.text
    return {**data, "participant_id": pid}
