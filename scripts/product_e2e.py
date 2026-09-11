"""Browser acceptance against a disposable PostgreSQL database, fictional identities only."""
import os,sys,subprocess,uuid,time,socket,json,signal
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
root=Path(__file__).resolve().parents[1];os.chdir(root)
for port in (8002,5175):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Puerto {port} ocupado')
name='product_e2e_'+uuid.uuid4().hex[:10];url=make_url(os.environ['DATABASE_URL']);admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
with admin.connect() as c:c.execute(text(f'CREATE DATABASE "{name}"'))
env={**os.environ,'DATABASE_URL':url.set(database=name).render_as_string(hide_password=False),'TEST_DATABASE_URL':url.set(database=name).render_as_string(hide_password=False),'VITE_API_TARGET':'http://127.0.0.1:8002','PRODUCT_E2E':'1'}
processes=[]
try:
    if '--seed' not in sys.argv:
        subprocess.run([str(root/'.venv/bin/python'),'-c',"import sys;sys.path.insert(0,'services/backend/product_tests');from conftest import *;from test_journeys import setup;initialize();db=SessionLocal();db.add(User(username='admin',role='admin',scopes=['models','diagnostics','raw_location'],password_hash=hasher.hash('test-password-123')));db.commit();db.close();c=TestClient(app);setup(c)"],env=env,check=True)
    for title,command,cwd in [('api',[str(root/'.venv/bin/uvicorn'),'app.main:app','--port','8002','--no-access-log'],root),('web',['npm','run','dev','--','--port','5175'],root/'apps/web')]:
        with (root/'.runtime'/f'product-e2e-{title}.log').open('w') as f:processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=f,stderr=f,start_new_session=True))
    for _ in range(80):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',5175))==0:break
        time.sleep(.2)
    subprocess.run(['npx','playwright','test','--config','playwright.product.config.ts'],cwd=root/'apps/web',env=env,check=True)
finally:
    for p in processes:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
    with admin.connect() as c:c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()
