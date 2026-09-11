"""Encrypted backup / restore drill against a DISPOSABLE database (A10).

Companion to ``scripts/verify_product_postgres.py`` (which stays untouched and
covers the plain path). This one exercises the *encrypted* procedure end to end:

  1. create a throwaway DB on the current cluster, migrate it to head;
  2. insert one fictitious withdrawn participant and a matching ledger entry;
  3. ``product_backup.py backup --key-file``  -> assert ciphertext artifacts exist;
  4. copy the backup, flip one byte -> assert restore refuses (fail-closed);
  5. ``product_backup.py restore --key-file`` from the pristine copy into a fresh
     ``restore_*`` DB -> assert the withdrawal was re-applied (participant absent);
  6. drop both DBs and remove the temp trees.

Run it through the local product wrapper so PostgreSQL tooling + PYTHONPATH are set:

    python3 scripts/product.py exec .venv/bin/python scripts/operation_backup_drill.py

No real product data is touched: every DB name is generated and dropped here.
Requires a reachable PostgreSQL (``$DATABASE_URL``); it is NOT run in CI without one.
"""
from __future__ import annotations
import json,os,secrets,shutil,subprocess,sys,uuid
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

root=Path(__file__).resolve().parents[1]
os.chdir(root)
base=make_url(os.environ['DATABASE_URL'])
if base.get_backend_name()!='postgresql':
    raise SystemExit('El ensayo requiere PostgreSQL (DATABASE_URL)')
mode=os.getenv('APP_MODE','REAL')
name='drill_'+uuid.uuid4().hex[:10]
restored='restore_'+uuid.uuid4().hex[:10]
admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT')
work=root/'.runtime'/name
py=str(root/'.venv/bin/python')


def sh(*args,**kw):
    return subprocess.run([str(a) for a in args],env=env,**{'check':True,**kw})


with admin.connect() as c:c.execute(text(f'CREATE DATABASE "{name}"'))
url=base.set(database=name)
work.mkdir(mode=0o700,parents=True)
key_file=work/'backup.key';key_file.write_bytes(secrets.token_bytes(48));key_file.chmod(0o600)
env={**os.environ,'DATABASE_URL':url.render_as_string(hide_password=False),
     'ARTIFACT_DIR':str(work/'artifacts'),'APP_MODE':mode,
     'PYTHONPATH':str(root/'services/backend')+os.pathsep+str(root)}
(work/'artifacts'/mode).mkdir(parents=True)
(work/'artifacts'/mode/'proof.txt').write_text('artefacto ficticio')

ok=False
try:
    subprocess.run([str(root/'.venv/bin/alembic'),'upgrade','head'],env=env,check=True)
    e=create_engine(url)
    with e.begin() as c:
        c.execute(text("INSERT INTO participants(id,environment,created_at,pseudonym,status,\"group\") "
                       f"VALUES ('drill-withdrawn','{mode}',CURRENT_TIMESTAMP,'FICTICIO-RETIRO','withdrawn','A')"))
    e.dispose()
    ledger=work/'deletions.jsonl'
    ledger.write_text(json.dumps({'participant_id':'drill-withdrawn'})+'\n');ledger.chmod(0o600)

    sh(py,'scripts/product_backup.py','backup',str(work/'backup'),'--key-file',str(key_file))
    names=sorted(p.name for p in (work/'backup').iterdir())
    assert 'database.dump.enc' in names and 'artifacts.tar.enc' in names,f'faltan artefactos cifrados: {names}'
    assert 'database.dump' not in names,'la copia dejó el dump en claro'
    manifest=json.loads((work/'backup'/'manifest.json').read_text())
    assert manifest['format']=='acompana-backup-v1-enc' and 'encryption' in manifest,'manifiesto no marca cifrado'

    tampered=work/'backup_tampered';shutil.copytree(work/'backup',tampered)
    blob=bytearray((tampered/'database.dump.enc').read_bytes());blob[0]^=0x01
    (tampered/'database.dump.enc').write_bytes(blob)
    bad=subprocess.run([py,'scripts/product_backup.py','restore',str(tampered),'restore_'+uuid.uuid4().hex[:8],
                        '--deletion-ledger',str(ledger),'--key-file',str(key_file)],env=env,capture_output=True,text=True)
    assert bad.returncode!=0,'la restauración aceptó una copia manipulada'

    sh(py,'scripts/product_backup.py','restore',str(work/'backup'),restored,'--deletion-ledger',str(ledger),'--key-file',str(key_file))
    r=create_engine(base.set(database=restored))
    with r.connect() as c:
        assert c.execute(text("SELECT count(*) FROM participants WHERE id='drill-withdrawn'")).scalar()==0,\
            'la retirada no se reaplicó en la restauración'
    r.dispose()
    assert (root/'.runtime'/restored/'artifacts'/mode/'proof.txt').read_text()=='artefacto ficticio'
    ok=True
    print('VERIFICADO: backup cifrado con integridad, rechazo de copia manipulada y retirada reaplicada en restauración aislada.')
finally:
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'DROP DATABASE IF EXISTS "{restored}" WITH (FORCE)'))
    admin.dispose()
    shutil.rmtree(work,ignore_errors=True)
    shutil.rmtree(root/'.runtime'/restored,ignore_errors=True)
sys.exit(0 if ok else 1)
