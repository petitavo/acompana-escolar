"""Verifiable secret rotation / recovery helper for the REAL product (A10).

Rotates the PostgreSQL application-role password and, optionally, rewrites the
private env file that carries ``DATABASE_URL`` / ``POSTGRES_PASSWORD``. Dry-run by
default: it prints a plan with no secret material. ``--apply`` performs the change
inside a transaction and writes the new secret only to a 0600 file you name.

    operation_rotate_secrets.py db-password --dsn "$ADMIN_DSN" --role acompana \
        --new-key-file .runtime/new-db-password [--env-file .runtime/operation.env.REAL] [--apply]

Security: the admin DSN is read from ``--dsn`` or ``$DATABASE_URL``; the new
password is generated locally, quoted using psycopg composables (never in
argv), and never printed. Recovery from total loss is a *restore* (see
``docs/OPERACION-VERIFICABLE.md``), not this tool.
"""
from __future__ import annotations
import argparse,os,secrets,sys,tempfile
from pathlib import Path
from urllib.parse import quote


def _redact_dsn(dsn:str)->str:
    if '@' not in dsn:return dsn
    head,tail=dsn.split('@',1)
    scheme=head.split('//',1)[0] if '//' in head else head
    user=head.split('//',1)[1].split(':',1)[0] if '//' in head else '?'
    return f'{scheme}//{user}:[redacted]@{tail}'


def rotate(dsn:str,role:str,new_key_file:Path,env_file:Path|None,apply:bool)->int:
    import psycopg
    if new_key_file.exists():
        raise SystemExit(f'{new_key_file} ya existe; no se sobrescribe (fail-closed)')
    print(f'Objetivo   : rol "{role}" en {_redact_dsn(dsn)}')
    print(f'Nuevo secreto -> {new_key_file} (0600)')
    if env_file:print(f'Reescribir  : {env_file} (DATABASE_URL / POSTGRES_PASSWORD)')
    if not apply:
        print('\nDRY-RUN. Repita con --apply para ejecutar. Luego: reiniciar api y worker, '
              'y correr scripts/operation_healthcheck.py.')
        return 0
    if env_file and not env_file.is_file():
        raise SystemExit("El archivo de entorno no existe; no se cambió la base")
    with psycopg.connect(dsn,autocommit=False) as conn,conn.cursor() as cur:
        cur.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,))
        if cur.fetchone() is None:
            raise SystemExit(f'El rol {role} no existe; se aborta sin cambios')
        new_password=secrets.token_urlsafe(32)
        # Persist the recovery credential before committing any database change.
        # On an uncertain commit this file remains available to the operator.
        fd=os.open(new_key_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:
            out.write(new_password+'\n');out.flush();os.fsync(out.fileno())
        cur.execute(psycopg.sql.SQL('ALTER ROLE {} WITH PASSWORD {}').format(
            psycopg.sql.Identifier(role), psycopg.sql.Literal(new_password)))
        conn.commit()
    if env_file:
        try:
            _rewrite_env(env_file,role,new_password)
        except Exception:
            raise SystemExit('Contraseña rotada; no se pudo actualizar el entorno. El secreto recuperable está en el archivo indicado; actualice el entorno antes de reiniciar.') from None
    print('Rotación aplicada. Reinicie api y worker con el nuevo secreto y verifique con '
          'operation_healthcheck.py. Sesiones activas siguen válidas hasta expirar.')
    return 0


def _rewrite_env(env_file:Path,role:str,new_password:str)->None:
    if not env_file.is_file():
        raise SystemExit(f'{env_file} no existe; cree primero el env privado a partir de infra/operation.env.example')
    lines=env_file.read_text().splitlines()
    q=quote(new_password,safe='')
    out=[]
    for line in lines:
        if line.startswith('POSTGRES_PASSWORD='):
            out.append('POSTGRES_PASSWORD='+new_password)
        elif line.startswith('DATABASE_URL=') and '@' in line:
            prefix,rest=line.split('://',1)
            creds,host=rest.split('@',1)
            user=creds.split(':',1)[0]
            out.append(f'{prefix}://{user}:{q}@{host}')
        else:
            out.append(line)
    tmp=tempfile.NamedTemporaryFile('w',dir=str(env_file.parent),delete=False)
    tmp.write('\n'.join(out)+'\n');tmp.close()
    os.chmod(tmp.name,0o600)
    os.replace(tmp.name,env_file)


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='cmd',required=True)
    d=s.add_parser('db-password')
    d.add_argument('--dsn',default=os.getenv('DATABASE_URL'))
    d.add_argument('--role',required=True)
    d.add_argument('--new-key-file',required=True)
    d.add_argument('--env-file')
    d.add_argument('--apply',action='store_true')
    a=p.parse_args(argv)
    if not a.dsn:
        raise SystemExit('Falta --dsn o $DATABASE_URL (DSN administrador)')
    return rotate(a.dsn,a.role,Path(a.new_key_file),Path(a.env_file) if a.env_file else None,a.apply)


if __name__=='__main__':
    sys.exit(main())
