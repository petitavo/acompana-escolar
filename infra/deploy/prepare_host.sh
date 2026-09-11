#!/usr/bin/env bash
# Prepare a self-hosted REAL deployment WITHOUT publishing anything.
# It validates the private env, checks the compose config, builds images and
# creates a backup key if missing. It does NOT run `up`, provision a cloud host,
# open firewall ports or touch DNS. Run from the repository root.
set -euo pipefail
umask 077

env_file="${1:-.runtime/operation.env.REAL}"
compose_file="infra/compose.REAL.yaml"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker no está instalado en este host" >&2
  exit 1
fi
if [[ ! -f "$env_file" ]]; then
  echo "Falta $env_file. Cree uno privado a partir de infra/operation.env.example (chmod 600)." >&2
  exit 1
fi
perm="$(stat -c '%a' "$env_file")"
if [[ "$perm" != "600" && "$perm" != "400" ]]; then
  echo "$env_file debe ser 600/400 (actual: $perm)" >&2
  exit 1
fi

# Required, no-default variables must be present and non-empty.
missing=()
for key in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD RAW_RETENTION_DAYS FEATURE_RETENTION_DAYS SCHOOL_HOST; do
  val="$(grep -E "^${key}=" "$env_file" | head -1 | cut -d= -f2- || true)"
  [[ -n "$val" ]] || missing+=("$key")
done
if (( ${#missing[@]} )); then
  echo "Variables obligatorias vacías en $env_file: ${missing[*]}" >&2
  exit 1
fi

compose=(docker compose --env-file "$env_file" -f "$compose_file")
"${compose[@]}" config --quiet
"${compose[@]}" build

key_file="$(grep -E '^BACKUP_KEY_FILE=' "$env_file" | head -1 | cut -d= -f2- || true)"
if [[ -n "$key_file" && ! -f "$key_file" ]]; then
  install -m 600 /dev/null "$key_file"
  openssl rand -base64 48 | tr -d '\n' > "$key_file"
  echo "Clave de backup creada en $key_file (guárdela en medio separado)."
fi

cat <<'DONE'
Host preparado. Pasos manuales que NO ejecuta este script:
  * DNS de SCHOOL_HOST apuntando a este host (solo para Caddyfile.PUBLIC).
  * Reglas de firewall (80/443 solo si se publica).
  * Arranque real:   docker compose --env-file <env> -f infra/compose.REAL.yaml up -d --wait
  * Verificación:    .venv/bin/python scripts/operation_healthcheck.py --target compose \
                       --compose-file infra/compose.REAL.yaml --env-file <env>
DONE
