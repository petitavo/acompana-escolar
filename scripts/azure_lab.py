"""Deploy the adult Android LAB into its own Azure resource group.

No credentials or DEMO database are bundled. All Azure calls specify a subscription.
Run `plan` first; `deploy` provisions billable resources. No automatic deletion.
"""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime' / 'azure'
AZ = os.environ.get('ACOMPANA_AZ') or shutil.which('az') or str(ROOT / '.tooling/azure-cli/bin/az')


def save_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
    path.chmod(0o600)


def bundle(destination):
    roots = ['.dockerignore', 'pyproject.toml', 'uv.lock', 'alembic.ini', 'services/backend', 'fixtures', 'packages/contracts', 'infra', 'apps/web']
    excluded = {'node_modules', 'dist', '__pycache__', '.pytest_cache', '.runtime', '.git', '.tooling'}
    with tarfile.open(destination, 'w:gz') as archive:
        for root in roots:
            p = ROOT / root
            for file in sorted(p.rglob('*')) if p.is_dir() else [p]:
                relative = file.relative_to(ROOT)
                if not file.is_file() or file.is_symlink() or excluded.intersection(relative.parts):
                    continue
                if file.name.startswith(('.env', 'credentials')) or file.suffix in {'.db', '.pyc', '.pem', '.key'}:
                    continue
                archive.add(file, arcname=str(relative), recursive=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'validate', 'deploy', 'status', 'stop', 'start'])
    parser.add_argument('--subscription', required=True)
    parser.add_argument('--location', default='mexicocentral')
    parser.add_argument('--size', default='Standard_B2als_v2')
    parser.add_argument('--resource-group', default='rg-acompana-escolar-lab')
    args = parser.parse_args()
    os.chdir(ROOT)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)

    def az(*parts):
        result = subprocess.run([AZ, *parts, '--subscription', args.subscription, '--only-show-errors', '-o', 'json'], check=True, text=True, capture_output=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    account = az('account', 'show')
    if account['state'] != 'Enabled':
        raise RuntimeError('Suscripción no habilitada')
    groups = az('group', 'list')
    existing = next((g for g in groups if g['name'] == args.resource_group), None)
    if existing and (existing.get('tags') or {}).get('project') != 'acompana-escolar':
        raise RuntimeError('El grupo ya existe y no pertenece a este proyecto; no se modifica')

    if args.action == 'plan':
        print(json.dumps({'subscription': account['name'], 'subscription_id': account['id'], 'resource_group': args.resource_group, 'location': args.location, 'size': args.size, 'mode': 'LAB', 'disk_gb': 32, 'public_ports': [80, 443], 'ssh': 'IP administrador /32; solo clave', 'billing': 'VM por hora + disco + IPv4 + tráfico; stop libera cómputo, disco e IP siguen facturando'}, indent=2, ensure_ascii=False))
        return
    if args.action in {'status', 'stop', 'start'}:
        if not existing:
            raise RuntimeError('No existe el grupo de este LAB')
        if args.action in {'stop', 'start'}:
            az('vm', 'deallocate' if args.action == 'stop' else 'start', '-g', args.resource_group, '-n', 'acompana-lab')
        print(json.dumps(az('vm', 'show', '-g', args.resource_group, '-n', 'acompana-lab', '-d'), indent=2))
        return

    public_ip = urllib.request.urlopen('https://api.ipify.org', timeout=20).read().decode().strip()
    ipaddress.IPv4Address(public_ip)
    key = STATE / 'id_ed25519'
    if not key.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'acompana-azure-lab', '-f', str(key)], check=True)
    params = {
        'location': {'value': args.location}, 'vmSize': {'value': args.size},
        'adminPublicKey': {'value': Path(str(key) + '.pub').read_text().strip()},
        'sshSourceCidr': {'value': public_ip + '/32'},
    }
    paramfile = STATE / 'parameters.json'
    save_private(paramfile, {'$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#', 'contentVersion': '1.0.0.0', 'parameters': params})
    if not existing:
        az('group', 'create', '-n', args.resource_group, '-l', args.location, '--tags', 'project=acompana-escolar', 'environment=LAB')
    if args.action == 'validate':
        az('deployment', 'group', 'validate', '-g', args.resource_group, '--template-file', 'infra/azure/main.bicep', '--parameters', '@' + str(paramfile))
        print('Azure validó la plantilla. Se preparó el grupo; no se crearon servidores, discos ni IP.')
        return
    print('Creando infraestructura Azure del LAB…', flush=True)
    result = az('deployment', 'group', 'create', '-g', args.resource_group, '-n', 'acompana-lab', '--template-file', 'infra/azure/main.bicep', '--parameters', '@' + str(paramfile))
    outputs = {k: v['value'] for k, v in result['properties']['outputs'].items()}
    save_private(STATE / 'deployment.json', {**outputs, 'subscription': account['id'], 'resource_group': args.resource_group})
    print('Esperando Docker y verificando la identidad SSH mediante Azure…', flush=True)
    host_result = az('vm', 'run-command', 'invoke', '-g', args.resource_group, '-n', outputs['vmName'], '--command-id', 'RunShellScript', '--scripts', 'set -eu\ncloud-init status --wait >/dev/null\nsystemctl is-active --quiet docker\ndocker compose version >/dev/null\ncat /etc/ssh/ssh_host_ed25519_key.pub')
    message = '\n'.join(v.get('message', '') for v in host_result['value'])
    host_key = re.search(r'^ssh-ed25519 [A-Za-z0-9+/=]+', message, re.MULTILINE)
    if not host_key:
        raise RuntimeError('Azure no devolvió la clave SSH del servidor. Revise cloud-init con Run Command.')
    known = STATE / 'known_hosts'
    known.write_text(outputs['hostname'] + ' ' + host_key.group() + '\n')
    ssh_options = ['-i', str(key), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known), '-o', 'ConnectTimeout=20']
    target = 'azureuser@' + outputs['hostname']
    archive = STATE / 'source.tar.gz'
    bundle(archive)
    print('Enviando código y construyendo servicios (sin datos ni credenciales locales)…', flush=True)
    subprocess.run(['scp', *ssh_options, str(archive), target + ':/opt/acompana-escolar/source.tar.gz'], check=True)
    command = 'cd /opt/acompana-escolar && tar -xzf source.tar.gz && rm source.tar.gz && sudo bash infra/azure/install.sh ' + shlex.quote(outputs['hostname'])
    subprocess.run(['ssh', *ssh_options, target, command], check=True)
    # Credentials travel only through verified SSH; never Azure deployment logs.
    command = 'cd /opt/acompana-escolar && sudo docker compose --env-file .runtime/azure-lab.env -f infra/azure/compose.yaml exec -T api cat .runtime/credentials-lab.json'
    creds = json.loads(subprocess.run(['ssh', *ssh_options, target, command], check=True, text=True, capture_output=True).stdout)
    creds['url'] = outputs['url']
    save_private(ROOT / '.runtime/credentials-lab.json', creds)
    print('Servicios iniciados. Comprobando certificado HTTPS y modo LAB…', flush=True)
    import time
    for attempt in range(24):
        try:
            with urllib.request.urlopen(outputs['url'] + '/api/v1/health', timeout=10) as response:
                health = json.load(response)
            if health.get('mode') != 'LAB' or health.get('status') != 'ok':
                raise RuntimeError('El servidor no respondió como LAB saludable')
            print(json.dumps({'url': outputs['url'], 'health': health, 'credentials': '.runtime/credentials-lab.json'}, indent=2))
            break
        except (OSError, ValueError):
            if attempt == 23:
                raise RuntimeError('Servicios creados, pero HTTPS aún no está verificado. Revise logs del proxy; no desactive TLS.')
            time.sleep(5)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        # Azure errors do not contain login tokens; subprocesses carrying account
        # credentials are never printed. Re-raise only the command status.
        if error.stderr and 'az' in str(error.cmd[0]):
            print(error.stderr, file=__import__('sys').stderr)
        raise SystemExit(f'Operación interrumpida (código {error.returncode}); no se eliminaron recursos.')
