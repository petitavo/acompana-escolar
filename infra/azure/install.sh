#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/acompana-escolar
hostname_arg="${1:?Falta hostname público}"
if [[ ! "$hostname_arg" =~ ^[a-z0-9.-]+\.cloudapp\.azure\.com$ ]]; then
  echo 'Hostname Azure inválido' >&2
  exit 1
fi
mkdir -p .runtime
if [[ ! -f .runtime/azure-lab.env ]]; then
  python3 - "$hostname_arg" <<'PY'
import os, secrets, sys
with os.fdopen(os.open('.runtime/azure-lab.env', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as out:
    out.write('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32) + '\nLAB_HOST=' + sys.argv[1] + '\n')
PY
fi
compose=(docker compose --env-file .runtime/azure-lab.env -f infra/azure/compose.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" build
"${compose[@]}" up -d --wait db
"${compose[@]}" run --rm --no-deps api alembic upgrade head
"${compose[@]}" run --rm --no-deps api python -m app.cli init
"${compose[@]}" run --rm --no-deps api python -m app.bootstrap_lab
"${compose[@]}" up -d --wait --wait-timeout 180
"${compose[@]}" ps
