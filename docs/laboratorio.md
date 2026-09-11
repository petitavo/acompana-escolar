# Acompaña Escolar — Laboratorio

MVP interno, ejecutable y en español: **Flutter/Android + panel del psicólogo + panel investigador + FastAPI + worker**. Proyecto nuevo, independiente de SMCBackend. No diagnóstico, producción con menores ni atención de emergencia garantizada.

- DEMO: datos sintéticos, semilla fija, 12 participantes y 60 días. Cambios, exámenes, permiso perdido, desconexión, poca información y contacto.
- LAB: teléfonos de adultos, eventos UsageStatsManager reales, sin inventar GPS/sueño. Sin modelo clínico habilitado ni inferencias DEMO.
- PostgreSQL por entorno en Compose. SQLite es una alternativa explícita para **DEMO local/tests**, nunca el despliegue LAB.

## Inicio rápido en esta máquina

Los archivos están en `/home/petitavo/acompana-escolar`. La demo local se abre en **http://127.0.0.1:5173/**. Credenciales aleatorias del entorno en `.runtime/credentials-demo.json` (modo de archivo 0600); no están en Git ni se incrustan en la UI.

```bash
cd /home/petitavo/acompana-escolar
make bootstrap
make demo
```

`make demo` utiliza Docker si está instalado; si no, inicia API/worker/web locales con SQLite y lo indica. `make local-demo` fuerza esa modalidad. `make stop` detiene solo los procesos registrados por el script local. Si los puertos 8000/5173 están ocupados, no mata procesos ajenos: informa el conflicto. La URL del móvil se configura al vincularlo o con `--dart-define=API_URL=...`.

Requisitos locales: Python capaz de crear venv, Git, Node 22 y npm. Bootstrap instala uv 0.8.22 en `.bootstrap`, resuelve Python 3.12 y usa `uv.lock`; instala web con `package-lock.json`. No requiere una API key ni Claude. Las descargas de herramientas requieren internet; los datos del laboratorio no se envían a servicios de analítica/LLM.

```bash
# Mostrar credenciales solo en tu terminal
cat .runtime/credentials-demo.json
# DEMO local solamente; detén primero sus servidores
make stop
make reset-demo
make demo
```

`reset-demo` elimina únicamente la base/credenciales DEMO locales, nunca LAB ni volúmenes Docker. En Compose, para reiniciar DEMO deliberadamente: `python scripts/compose.py DEMO down -v` y `make demo`. No ejecutar un reset sobre LAB.

## PostgreSQL y Docker Compose

```bash
make bootstrap
make demo   # con Docker disponible: proyecto Compose acompana-demo
make lab    # requiere Docker; proyecto separado acompana-lab
```

Los scripts generan `.runtime/compose-demo.env` y `.runtime/compose-lab.env` con contraseña PostgreSQL aleatoria, fuera de Git. DEMO y LAB tienen bases, redes y volúmenes diferentes y un guard del servidor. Migración: `alembic upgrade head`; después `app.cli init` carga CHECKIN_DEMO_V1. `app.cli seed` se niega a operar en LAB.

DEMO Compose: http://127.0.0.1:8088. LAB por defecto: https://localhost:8444, accesible solo desde el equipo hasta configurar LAN. Postgres no expone puerto al host. No hay publicación externa de los paneles.

```bash
.venv/bin/python scripts/compose.py DEMO exec api cat .runtime/credentials-demo.json
.venv/bin/python scripts/compose.py LAB exec api python -m app.cli create-user psicologo.lab --role psychologist
.venv/bin/python scripts/compose.py LAB exec api python -m app.cli create-user investigador.lab --role researcher
.venv/bin/python scripts/compose.py LAB exec api python -m app.cli invite LAB-001
.venv/bin/python scripts/compose.py LAB exec api python -m app.cli assign psicologo.lab LAB-001
```

Cuentas administrativas solo CLI; contraseñas mínimo 12 caracteres, solicitadas sin eco. El rol admin no ve datos de salud por defecto.

### HTTPS para teléfono físico

Para un teléfono que se conecte por internet, está preparada la opción [LAB en Azure](docs/azure-lab.md), con servidor dedicado y HTTPS público. Incluye estimación de costo, despliegue y pasos del APK; consulte el estado real antes de asumir que ya está publicado.

En `.runtime/compose-lab.env`, configura `BIND_ADDRESS` con la IP LAN del portátil y `LAB_HOST` con esa misma IP o nombre local resoluble. Mantén la conexión en red privada y permite solo esa red/puerto en tu firewall. Reinicia proxy. Usa en el teléfono `https://IP_LAN:8444`; localhost en el móvil **no** es el portátil.

Caddy genera una CA interna. Obtén su certificado público para confiarlo explícitamente en tu teléfono de prueba:

```bash
.venv/bin/python scripts/compose.py LAB cp proxy:/data/caddy/pki/authorities/local/root.crt .runtime/lab-root.crt
```

Instala ese certificado público como CA de usuario en el teléfono adulto. El APK **debug** confía en CAs de usuario, sin desactivar validación TLS. No compartir claves de Caddy. Release confía solo en el almacén del sistema y necesita certificado/signing apropiados. La configuración HTTP limitada a 10.0.2.2/localhost es solo para emulador debug; no hay cleartext global.

## Comandos de desarrollo

```bash
export PYTHONPATH=services/backend:.
# DEMO local: excepción HTTP explícita para cookies; LAB la rechaza
export APP_MODE=DEMO COOKIE_SECURE=false
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli init
.venv/bin/python -m app.cli seed --seed 20260906 --end 2026-09-05
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# En otra terminal con PYTHONPATH definido:
.venv/bin/python -m worker.main
# En otra terminal:
npm --prefix apps/web run dev
```

API `/api/v1/docs`, contrato `/api/v1/openapi.json`, health `/api/v1/health`. `make contracts` actualiza OpenAPI y tipos TypeScript generados. Excepciones de validación no repiten payloads sensibles.

Instrumento revisado: `.venv/bin/python -m app.cli import-instrument definicion.json` valida e importa **deshabilitado**. La v1 no habilita instrumentos reales: requiere completar y verificar integración del protocolo profesional. Nunca bloquea el formulario demo.

Dataset externo: `.venv/bin/python -m app.cli inspect-dataset datos.csv manifest.json` produce compatibilidad; no descarga ni entrena datos sujetos a acuerdo. Un entrenamiento demo se encola desde el panel, nunca dentro de la respuesta HTTP.

## Android

Versión fijada: Flutter 3.35.7, Dart incluido, JDK 17, Android SDK 36, NDK 27.0.12077973. Las herramientas descargadas para esta ejecución están en `.tooling/` y se excluyen de Git. En otro equipo instala Flutter/Android SDK y añade Flutter a PATH.

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

En esta máquina:

```bash
export JAVA_HOME=/home/petitavo/acompana-escolar/.tooling/jdk
export ANDROID_HOME=/home/petitavo/acompana-escolar/.tooling/android-sdk
export PATH=/home/petitavo/acompana-escolar/.tooling/flutter/bin:$ANDROID_HOME/platform-tools:$PATH
make mobile-test
make apk
```

APK: `apps/mobile/build/app/outputs/flutter-apk/app-debug.apk`. Debug compilado no equivale a captura validada en un teléfono. La guía física exige registrar fabricante/API y comprobar permisos, offline, reintentos y pausa. No hay teléfono físico verificado en esta entrega.

## Verificación

```bash
make test                   # pytest API/dominio/ML + build web
make web-test               # servidores DEMO + semilla activos
make mobile-test            # Flutter disponible en PATH
cd apps/mobile/android && ./gradlew testDebugUnitTest
```

Playwright usa Chrome instalado en `/opt/google/chrome/chrome`; en otro equipo configura `CHROME_PATH` al ejecutable o instala un navegador compatible y adapta `playwright.config.ts`. No copia perfiles ni cookies personales. Solo opera con DEMO. Los tests web dejan notas/estados de prueba persistidos para verificar el circuito.

Ver [VALIDACION.md](docs/VALIDACION.md) para resultados reales y pendientes. No se declara la ejecución de Compose o una prueba física que no se haya realizado.

## Estructura y documentación

```text
apps/mobile/          Flutter + Kotlin (Room/SQLCipher/WorkManager)
apps/web/             React + TypeScript + Vite
services/backend/app/ API, dominio, seguridad y CLI
services/backend/worker/ jobs, exportación, retención y borrado
services/backend/ml/  datasets, entrenamiento y model cards
services/backend/tests/ invariantes API/dominio/ML
services/backend/migrations/ Alembic
packages/contracts/   OpenAPI + tipos TypeScript
fixtures/             generador DEMO explícito
infra/                Compose, Caddy, Nginx y Dockerfiles
scripts/              arranque local/Compose y utilidades
```

- [Guía demo de 15 minutos](docs/guia-demo.md)
- [Guía de teléfono real](docs/android.md)
- [Arquitectura lógica y física](docs/arquitectura.md)
- [Diccionario de datos](docs/diccionario-datos.md)
- [Permisos por API](docs/permisos-api.md)
- [Features y calidad](docs/features.md)
- [Experimentos y límites](docs/ml.md)
- [Protocolo interno](docs/protocolo-interno.md)
- [Limitaciones y backlog](docs/limitaciones.md)

La especificación original se conserva en `docs/especificacion-original.md`. Las simplificaciones de tablas y capacidades pendientes se identifican expresamente en esta documentación.
