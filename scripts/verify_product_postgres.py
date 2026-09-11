"""Independent acceptance DBs on the local product cluster; original product DB untouched."""
import os,subprocess,sys,uuid,json,shutil
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
root=Path(__file__).resolve().parents[1];os.chdir(root)
url=make_url(os.environ['DATABASE_URL']);name='product_test_'+uuid.uuid4().hex[:10]
admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
with admin.connect() as c:c.execute(text(f'CREATE DATABASE "{name}"'))
url=url.set(database=name)
env={**os.environ,'TEST_DATABASE_URL':url.render_as_string(hide_password=False),'DATABASE_URL':url.render_as_string(hide_password=False)}
try:
    subprocess.run([str(root/'.venv/bin/pytest'),'services/backend/product_tests','-q','--disable-warnings'],env=env,check=True)
    # Additive migration preserves a record created with the original schema.
    e=create_engine(url)
    with e.begin() as c:c.execute(text('DROP SCHEMA public CASCADE'));c.execute(text('CREATE SCHEMA public'))
    subprocess.run([str(root/'.venv/bin/alembic'),'upgrade','402d6c27faaa'],env=env,check=True)
    with e.begin() as c:c.execute(text("INSERT INTO participants(id,environment,created_at,pseudonym,status,\"group\") VALUES ('preserve-old-fixture','REAL',CURRENT_TIMESTAMP,'FICTICIO-PRESERVAR','active','A')"))
    subprocess.run([str(root/'.venv/bin/alembic'),'upgrade','head'],env=env,check=True)
    with e.connect() as c:assert c.execute(text("SELECT pseudonym FROM participants WHERE id='preserve-old-fixture'")).scalar()=='FICTICIO-PRESERVAR'
    e.dispose()
    work=root/'.runtime'/name;work.mkdir(mode=0o700)
    env['ARTIFACT_DIR']=str(work/'artifacts');(work/'artifacts').mkdir();(work/'artifacts'/'REAL').mkdir();(work/'artifacts'/'REAL'/'backup-proof.txt').write_text('Artefacto ficticio que debe sobrevivir a la copia')
    subprocess.run([str(root/'.venv/bin/python'),'scripts/product_backup.py','backup',str(work/'backup')],env=env,check=True)
    ledger=work/'latest-deletions.jsonl';ledger.write_text(json.dumps({'participant_id':'preserve-old-fixture'})+'\n');ledger.chmod(0o600)
    restored='restore_'+uuid.uuid4().hex[:10]
    try:
        subprocess.run([str(root/'.venv/bin/python'),'scripts/product_backup.py','restore',str(work/'backup'),restored,'--deletion-ledger',str(ledger)],env=env,check=True)
        assert (root/'.runtime'/restored/'artifacts'/'REAL'/'backup-proof.txt').read_text()=='Artefacto ficticio que debe sobrevivir a la copia'
        r=create_engine(url.set(database=restored))
        with r.connect() as c:assert c.execute(text("SELECT count(*) FROM participants WHERE id='preserve-old-fixture'")).scalar()==0
        r.dispose()
    finally:
        with admin.connect() as c:c.execute(text(f'DROP DATABASE IF EXISTS "{restored}" WITH (FORCE)'))
    print('VERIFICADO: pruebas PostgreSQL, migración aditiva conserva registros, backup y restauración con retiradas reaplicadas.')
finally:
    with admin.connect() as c:c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()
