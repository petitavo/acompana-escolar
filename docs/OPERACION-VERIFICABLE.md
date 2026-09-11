# Operación verificable (A10)

Cierra el hallazgo **A10 — Operación no acreditada** con configuración y
procedimientos *reproducibles*. No despliega nada, no publica nada y no mide
lo que no se puede medir aquí. Todo lo que sí es aislable se prueba en
`tests_operation/`.

**No se certifica** (falta prueba con infraestructura/hardware real): envío
externo FCM y acuse de entrega, TLS público y disponibilidad del hosting, cifrado
en reposo de discos/volúmenes del proveedor, RPO/RTO, captura sostenida o batería
en el teléfono. Los adaptadores y procedimientos quedan listos y con una
comprobación reproducible; la verificación final es de Codex con esa
infraestructura.

Revisión final realizada directamente por Codex. El conjunto A01–A10 incluye también backend, ML, web y Android; este documento describe operación. Las pruebas se ejecutan con bases y destinatarios ficticios, sin cambios sobre datos reales.

---

## 1. HTTPS / proxy

| Archivo | Uso | TLS |
|---|---|---|
| `infra/Caddyfile.REAL` | revisión privada por HTTPS, sin dominio | CA interna (`tls internal`); el certificado debe confiarse explícitamente en cada dispositivo |
| `infra/Caddyfile.PUBLIC` | hosting propio con dominio | certificado público ACME para `{$SCHOOL_HOST}`, HSTS `includeSubDomains` |

Ambos: `admin off`, cabeceras `X-Frame-Options: DENY`, `X-Content-Type-Options`,
`Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`, límite de cuerpo
2 MB y logs con `query`, `Authorization` y `Cookie` redactados. El `web` (nginx)
ya fija la CSP y limita `login` (ver `infra/nginx.conf`).

`COOKIE_SECURE=true` es obligatorio en REAL desplegado (lo exige
`services/backend/app/config.py`; sólo el producto local en loopback puede
relajarlo, y este compose no lo hace).

## 2. Despliegue adaptado al stack real (sin publicar)

`infra/compose.REAL.yaml` (revisión privada):

* Secretos **sólo** por env-file privado creado desde `infra/operation.env.example`
  (`chmod 600`, ignorado por Git). Cada variable obligatoria usa `${VAR:?}`:
  si falta, `docker compose` aborta. **No hay defaults inseguros.**
* Red `private` `internal: true` (db/api/worker/web sin salida ni puertos).
  `proxy` publica sólo en `${BIND_ADDRESS:-127.0.0.1}:${HTTPS_PORT:-8444}`.
* Endurecido: `no-new-privileges`, `cap_drop: [ALL]`, `read_only` + `tmpfs`
  en api/worker/web, `restart: unless-stopped`, `logging` rotado (10 MB × 5).
* Healthchecks que **distinguen componentes** (§3).

`infra/compose.PUBLIC.yaml` es un *overlay* fino que sólo da egress y publica
80/443 en el `proxy` para hosting con dominio:

```bash
CADDYFILE=Caddyfile.PUBLIC \
docker compose --env-file .runtime/operation.env.REAL \
  -f infra/compose.REAL.yaml -f infra/compose.PUBLIC.yaml config --quiet
```

`infra/deploy/prepare_host.sh` valida el env privado (existencia, permisos
600/400, variables obligatorias no vacías), corre `compose config` + `build` y
crea la clave de backup si falta. **No** ejecuta `up`, ni firewall, ni DNS, ni
aprovisiona nube. `infra/deploy/acompana-escolar.service` reafirma el estado
deseado tras reinicio del host (recuperación de caída = `restart` de compose +
esta unidad).

Pendiente externo: host real, dominio + DNS, reglas de firewall, y confianza
del certificado en los teléfonos de prueba (para `Caddyfile.REAL`).

## 3. Healthcheck y monitorización reproducible

`scripts/operation_healthcheck.py` — un JSON, sin datos ni secretos (DSN,
contraseñas, tokens y cabeceras se redactan; salida de error saneada). Código
de salida `0` ok / `1` degradado o **indeterminado** / `2` caído.

| Componente | Señal | No expone |
|---|---|---|
| `database` | `SELECT 1` + latencia, `pg_is_in_recovery()`, nº de conexiones | ninguna fila |
| `api` | `GET /api/v1/health` == 200 y `status=ok`; informa `mode`, `version` | — |
| `worker` | *liveness por efecto*: `ok` **sólo** con un job `running` cuyo lease sigue en el futuro (el worker lo renovó); `degraded` con lease vencido (cayó a mitad) o cola más vieja que `--worker-stale-minutes` (no consume); **`unknown` si no hay trabajo** — la ausencia de jobs no es salud. Conteos por estado. | payloads de jobs |

El `worker` sano pero ocioso da `unknown`, no `ok`: no hay forma de distinguirlo
de uno caído sin trabajo que procesar. Para forzar una señal, encolar un job de
prueba, o combinar con el healthcheck del contenedor (abajo).

```bash
# Contra el compose (estados de contenedor + health):
.venv/bin/python scripts/operation_healthcheck.py --target compose \
  --compose-file infra/compose.REAL.yaml --env-file .runtime/operation.env.REAL

# Directo (producto local o cualquier host con acceso):
MONITOR_API_URL=https://escuela.example:8444/api/v1/health \
MONITOR_DATABASE_URL="$DATABASE_URL" MONITOR_CA_CERT=./caddy-root.crt \
.venv/bin/python scripts/operation_healthcheck.py
```

El healthcheck del contenedor `worker` (`infra/worker-healthcheck.py`) sólo
comprueba **presencia del proceso** `worker.main` — mantiene credenciales fuera
del healthcheck. Presencia de proceso **no** prueba que consuma la cola; ese
límite se declara también en la salida de `--target compose`. La comprobación de
consumo real es el `--target direct` (`evaluate_worker`).

## 4. Backup cifrado con integridad y restore aislado

`scripts/product_backup.py` conserva el modo en claro (compatibilidad exacta con
`scripts/verify_product_postgres.py`) y añade cifrado:

* `--key-file PATH` (o env `BACKUP_KEY_FILE`): archivo con ≥ 32 bytes aleatorios.
  La ruta es argumento; **el secreto nunca** está en argv ni en logs.
* `backup --key-file`: `database.dump` y un tar de `artifacts/` se cifran con
  **AES-256-GCM** (nonce de 96 bits, claves `sha256(secreto‖etiqueta)`), y el
  `manifest.json` se autentica con **HMAC-SHA256** (`manifest.sig`). Formato
  `acompana-backup-v1-enc`.
* **Atomicidad**: la copia se arma en un directorio de staging privado (`0700`) y
  se mueve a su sitio con un único `os.rename`. La clave se valida **antes** de
  ejecutar `pg_dump` o copiar nada. Si falla cualquier paso (clave, dump, copia,
  cifrado, checksum) **no queda el destino** ni un directorio que aparente estar
  cifrado conservando crudos.
* `restore`: detecta el cifrado por el manifiesto y **exige** `--key-file`
  (fail-closed). Valida clave + HMAC del manifiesto + checksums antes de descifrar.
  El texto en claro se materializa **sólo** en un directorio temporal privado que
  se elimina pase lo que pase (éxito, `pg_restore` fallido, o validación fallida);
  la copia de origen **nunca** se modifica. La extracción del tar rechaza rutas
  fuera de `artifacts/` y enlaces. Si la restauración aborta a mitad, se hace
  `dropdb --if-exists` de la base parcial y se borra el árbol de artefactos.
* La restauración **siempre** crea una base nueva `restore_*`, **no** inicia
  servidores y **reaplica el ledger actual de retiradas** (`worker.main.erase`)
  para no recuperar personas borradas. Nunca escribe sobre el producto.

Producción: el procedimiento usa `--key-file` **obligatorio** (AES-256-GCM). El
modo en claro queda **sólo para pruebas locales** (compatibilidad con
`verify_product_postgres.py`). La clave (≥ 32 bytes aleatorios,
`openssl rand -base64 48`) y las copias van en **medio separado del host y fuera
del repositorio** (`.runtime/` ya está en `.gitignore`), según la política
institucional. Este repositorio no fija esa política ni guarda claves.

```bash
# Procedimiento de producción (clave obligatoria):
python3 scripts/product.py exec .venv/bin/python scripts/product_backup.py \
  backup .runtime/copia-$(date +%F) --key-file "$BACKUP_KEY_FILE"
python3 scripts/product.py exec .venv/bin/python scripts/product_backup.py \
  restore .runtime/copia-2026-09-08 restore_revision \
  --deletion-ledger .runtime/artifacts/REAL/deletions.jsonl --key-file "$BACKUP_KEY_FILE"
```

### Ensayo para Codex (base desechable, no se ejecuta sin PostgreSQL)

`scripts/operation_backup_drill.py`: crea una base efímera, migra, inserta un
participante retirado ficticio, hace `backup --key-file`, comprueba que existen
los artefactos cifrados, que una copia con un byte alterado **es rechazada**, que
la restauración reaplica la retirada, y **destruye** ambas bases y los temporales.

```bash
python3 scripts/product.py exec .venv/bin/python scripts/operation_backup_drill.py
# Regresión del camino en claro (sin cambios):
make product-postgres-test
```

Pendiente externo: cifrado en reposo del disco/volumen y de la copia en el
proveedor de hosting; **no se mide aquí**. GCM prueba integridad y
confidencialidad del archivo de copia, no el cifrado del almacenamiento remoto.

## 5. Rotación / recuperación de secretos

`scripts/operation_rotate_secrets.py db-password` — *dry-run* por defecto (imprime
un plan sin material secreto). Con `--apply`: `ALTER ROLE` en transacción (la
contraseña va como parámetro ligado, no en argv), escribe el nuevo secreto sólo
en un archivo `0600` que tú nombras, y opcionalmente reescribe atómicamente el
env privado (`DATABASE_URL` con la contraseña URL-encoded y `POSTGRES_PASSWORD`).

```bash
.venv/bin/python scripts/operation_rotate_secrets.py db-password \
  --dsn "$ADMIN_DSN" --role acompana \
  --new-key-file .runtime/db-password.next --env-file .runtime/operation.env.REAL --apply
# luego: recrear api y worker con el nuevo secreto y correr operation_healthcheck.py
```

Recuperación ante pérdida total = restaurar desde una copia cifrada (§4) a un
host nuevo y repuntar `DATABASE_URL`. Las sesiones activas siguen válidas hasta
expirar; forzar cierre = cambiar contraseñas de usuario por el flujo de la app.

## 6. Empaquetado / actualización de release

La rama no tiene commits, así que la identidad de una release es un **manifiesto
de contenido firmado**, no un SHA de git.

`scripts/operation_release.py`:

```bash
.venv/bin/python scripts/operation_release.py keygen --key-dir .runtime/release-keys
.venv/bin/python scripts/operation_release.py build --version 0.3.0 \
  --apk dist/acompana-escolar-0.3.0-pruebas.apk \
  --sign-key .runtime/release-keys/release-ed25519.key
.venv/bin/python scripts/operation_release.py verify \
  --manifest .runtime/releases/0.3.0/RELEASE-MANIFEST.json \
  --verify-key .runtime/release-keys/release-ed25519.pub \
  --apk dist/acompana-escolar-0.3.0-pruebas.apk
```

* `build`: hash sha256 de cada fuente incluida, también archivos nuevos no ignorados (`git ls-files --cached --others --exclude-standard`), hash y tamaño
  del APK si se pasa, y firma **Ed25519 detached** con el `openssl` del sistema
  (sin dependencias nuevas). Escribe en `.runtime/releases/<version>/` y **se
  niega a sobrescribir** una release o una clave ya existente (fail-closed).
* `verify`: comprueba la firma, que el árbol actual coincide con **cada** archivo
  del manifiesto **y cada artefacto declarado** (APK: hash + tamaño). Si el
  manifiesto declara un APK, `--apk` es obligatorio. Salida `0` ok · `3`
  firma/manifiesto inválido · `4` divergencia de fuentes · `5` artefacto
  declarado ausente o alterado. Una release **no** se declara verificada sin
  comprobar sus artefactos.

Procedimiento de actualización:

1. `operation_release.py build` de la versión candidata y `verify` en el host.
2. `docker compose ... build` con el código verificado.
3. `docker compose ... run --rm api alembic upgrade head`, seguido de `docker compose ... up -d --wait` (migraciones aditivas ya cubiertas por
   `verify_product_postgres.py`; conservan registros del esquema anterior).
4. `operation_healthcheck.py --target compose` y un `--target direct` — el
   segundo confirma consumo del worker (el primero sólo ve el proceso).
5. Rollback: `up -d` de la imagen/manifiesto anterior; la restauración de datos,
   si hiciera falta, es §4 (a base nueva, nunca encima).

APK: firma de desarrollo, distribución por archivo, sin tienda. La firma
institucional de release exige keystore propio (ver `docs/producto.md`,
"Compilar y firmar"); la APK de pruebas 0.3.0 ya está compilada; no lleva firma institucional.

Pendiente externo: keystore Android institucional; distribución de la clave
pública Ed25519 de release al equipo verificador.

---

## Estado A10

| Punto | Estado | Evidencia |
|---|---|---|
| HTTPS público / CA interna | configurado, no desplegado | `infra/Caddyfile.PUBLIC`, `infra/Caddyfile.REAL`, `tests_operation/test_infra_config.py` |
| Secretos sin defaults inseguros | corregido | `infra/operation.env.example`, `${VAR:?}` en compose, tests |
| Despliegue adaptado sin publicar | configurado | `infra/compose.REAL.yaml`, `infra/compose.PUBLIC.yaml`, `infra/deploy/` |
| Monitorización API/worker/DB reproducible | implementado y probado (aislado) | `scripts/operation_healthcheck.py`, `tests_operation/test_healthcheck.py` |
| Backup cifrado + integridad + restore aislado | verificado en PostgreSQL 18 aislado, incluida manipulación y retiradas | `scripts/product_backup.py`, `scripts/operation_backup_crypto.py`, `tests_operation/test_backup_*.py`, `scripts/operation_backup_drill.py` |
| Rotación / recuperación | ALTER ROLE y archivo recuperable 0600 verificados en PostgreSQL aislado | `scripts/operation_rotate_secrets.py`, `tests_operation/test_rotate_secrets.py` |
| Firma / plan de actualización de release | implementado y probado | `scripts/operation_release.py`, `tests_operation/test_release.py` |
| RPO/RTO medidos, cifrado en reposo del hosting | **dependencia externa** | requiere host/proveedor real; no se declara verificado |
| Certificado confiado en teléfonos, DNS, firewall | **dependencia externa** | requiere dominio y dispositivos |
| Línea base por commit | sin commit; referencia por contenido | la rama sigue sin commits; identidad = manifiesto de `operation_release.py` |

## Correo y permisos de salida

Configure SMTP_HOST, SMTP_FROM y SMTP_SECURITY=starttls o tls; coloque la contraseña en `.runtime/provider-secrets/smtp-password`, legible únicamente por el operador y el uid 10001 del backend. Configure SMTP_PASSWORD_FILE=/run/provider-secrets/smtp-password. La cuenta destinataria registra su correo en Configuración personal. Los mensajes sólo indican que existe una notificación: no incluyen nombres de estudiantes, puntuaciones o motivos de revisión. Se necesitan tanto la autorización institucional como ALLOW_EXTERNAL_NOTIFICATIONS=true.

El overlay público habilita salida de red del worker para SMTP/FCM; no publica sus puertos. Aceptación SMTP/FCM significa `sent`, no entrega efectiva. Cada canal conserva hasta tres intentos y sus estados; FCM requiere un acuse desde la aplicación para `delivered`. El estado final `acknowledged` exige la acción del propietario en el panel. El SMTP controlado se verificó mediante un servidor efímero en loopback; no se enviaron mensajes externos.
