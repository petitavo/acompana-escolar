"""Private PostgreSQL + artifacts backup; restoration always creates a fresh database.
Run through `python scripts/product.py exec .venv/bin/python scripts/product_backup.py ...`.

Encryption (A10): pass ``--key-file PATH`` (or env ``BACKUP_KEY_FILE``) on ``backup``
to write an authenticated encrypted copy (AES-256-GCM over the dump and over a tar
of the artifacts) plus an HMAC over the manifest. ``restore`` auto-detects an
encrypted backup and then *requires* the same ``--key-file`` (fail-closed).

The key file must hold a high-entropy secret (>= 32 random bytes) and live outside
the repository; the path is an argument, the secret never is, and no secret is
printed. In the PRODUCTION procedure the key is mandatory (see
``docs/OPERACION-VERIFICABLE.md``); the plaintext mode is only for local tests and
stays byte-for-byte compatible with ``scripts/verify_product_postgres.py``.

The backup is assembled in a private staging dir and moved into place atomically:
a failure at any step (key, pg_dump, copy, encryption, checksum) leaves neither the
destination nor a half-written "encrypted" folder holding plaintext. A restore
decrypts only into a private temp dir that is always removed and never touches the
source copy.
"""
import argparse,json,os,re,shutil,subprocess,sys
from pathlib import Path
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parent))
from operation_backup_crypto import write_backup,restore_backup

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
sub=parser.add_subparsers(dest='action',required=True)
b=sub.add_parser('backup');b.add_argument('directory');b.add_argument('--key-file',default=os.getenv('BACKUP_KEY_FILE'))
r=sub.add_parser('restore');r.add_argument('directory');r.add_argument('database');r.add_argument('--deletion-ledger',required=True);r.add_argument('--key-file',default=os.getenv('BACKUP_KEY_FILE'))
args=parser.parse_args()
url=make_url(os.environ['DATABASE_URL'])
if url.get_backend_name()!='postgresql':raise SystemExit('Esta herramienta requiere PostgreSQL')
pgbin=Path(os.getenv('PG_BIN',str(root/'.tooling/postgres/root/usr/lib/postgresql/18/bin')))
env={**os.environ,'PGHOST':url.host or '127.0.0.1','PGPORT':str(url.port or 5432),'PGUSER':url.username or '', 'PGPASSWORD':url.password or ''}
def pg(name,*items,**kw):return subprocess.run([str(pgbin/name),*map(str,items)],env=env,check=True,**kw)
artifacts=(Path(os.getenv('ARTIFACT_DIR',str(root/'.runtime/artifacts')))/os.getenv('APP_MODE','REAL')).resolve()
folder=Path(args.directory).resolve()

if args.action=='backup':
    write_backup(folder,lambda p:pg('pg_dump','--format=custom','--no-owner','--file',p,url.database),artifacts,args.key_file)
    print('Backup privado creado:',folder,'(cifrado)' if args.key_file else '(sin cifrar; solo pruebas locales)')
else:
    if not re.fullmatch(r'restore_[a-z0-9_]{1,45}',args.database):raise SystemExit('El destino debe comenzar por restore_ y ser una base nueva')
    ledger=Path(args.deletion_ledger).resolve()
    if not ledger.is_file():raise SystemExit('Falta el ledger actual de retiradas; no se restaura sin comprobarlo')
    entries=[json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    restored=root/'.runtime'/args.database/'artifacts'/os.getenv('APP_MODE','REAL')
    if restored.parent.exists():raise SystemExit('El directorio de restauración ya existe')

    def consumer(dump_path,artifacts_path,manifest):
        pg('createdb',args.database) # Fails if the name already exists; never overwrites a DB.
        pg('pg_restore','--exit-on-error','--no-owner','--dbname',args.database,dump_path)
        restored.parent.mkdir(parents=True,mode=0o700)
        shutil.copytree(artifacts_path,restored)
        for p in restored.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
        os.environ['DATABASE_URL']=url.set(database=args.database).render_as_string(hide_password=False)
        os.environ['ARTIFACT_DIR']=str(restored.parent)
        # Imports happen after selecting the new database and independent artifact copy.
        from app.db import SessionLocal,Participant
        from app.school_db import ModelRecord,DatasetRecord
        from sqlalchemy import select
        from worker.main import erase
        original=Path(manifest['artifact_root'])
        with SessionLocal.begin() as db:
            for cls,field in ((ModelRecord,'artifact'),(DatasetRecord,'path')):
                for row in db.scalars(select(cls)):
                    old=Path(getattr(row,field)).resolve()
                    if not old.is_relative_to(original):raise RuntimeError('Artefacto fuera del directorio registrado')
                    setattr(row,field,str(restored/old.relative_to(original)))
            db.flush()
            erased=0
            for entry in entries:
                if db.get(Participant,entry['participant_id']):erase(db,entry['participant_id'],'restore-ledger');erased+=1
        return erased

    try:
        erased=restore_backup(folder,args.key_file,consumer,tmp_dir=root/'.runtime')
    except BaseException:
        # Do not leave a half-restored database or artifact tree behind.
        subprocess.run([str(pgbin/'dropdb'),'--if-exists',args.database],env=env,check=False)
        shutil.rmtree(root/'.runtime'/args.database,ignore_errors=True)
        raise
    print(f'Restauración aislada completada: {args.database}; {erased} retiradas reaplicadas. Servidores no iniciados.')
