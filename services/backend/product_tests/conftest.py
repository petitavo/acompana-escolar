import os, tempfile
os.environ.update(APP_MODE='REAL', LOCAL_PRODUCT='true', PILOT_ENABLED='false', COOKIE_SECURE='false', DATABASE_URL=os.environ.get('TEST_DATABASE_URL') or 'sqlite:///'+tempfile.mktemp(suffix='.db'), ARTIFACT_DIR=tempfile.mkdtemp())
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, initialize, SessionLocal, User
from app.main import app
from app.security import hasher

@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine)
    initialize()
    with SessionLocal.begin() as db:
        db.add(User(username='admin',role='admin',scopes=['diagnostics','models','raw_location'],password_hash=hasher.hash('test-password-123')))
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def login(c, name='admin'):
    c.headers.pop('authorization',None)
    r=c.post('/api/v1/auth/login',json={'username':name,'password':'test-password-123'})
    assert r.status_code==200,r.text
    c.headers['x-csrf-token']=r.json()['csrf_token']
    return r.json()
