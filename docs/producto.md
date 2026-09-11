# Guía del producto

## Entornos y acceso

El producto local usa PostgreSQL independiente en 55433, API en 8001 y web en http://127.0.0.1:5174. DEMO permanece en 5173/8000 con sus datos sintéticos y LAB conserva su entrada Android independiente. No se modifica SMCBackend.

En esta máquina las herramientas están en `.tooling`: Flutter 3.35.7, JDK 17, Android SDK 36 y PostgreSQL 18.6. `make bootstrap` prepara Python y web; el script local de producto requiere esas herramientas PostgreSQL existentes. En otra máquina puede utilizarse el Compose REAL o un PostgreSQL instalado y configurado mediante DATABASE_URL; no se sustituye silenciosamente por SQLite.

```bash
cd /home/petitavo/acompana-escolar
make product
# Credenciales: abrir localmente .runtime/credentials-product.json
make product-stop
```

El administrador inicial es `admin.local`; su contraseña aleatoria está solo en ese archivo privado. No utilizar `invitation` como usuario: las invitaciones de estudiantes se canjean en la entrada de estudiante o en Android, con el código independiente que entrega la institución.

## Recorrido para evaluar

1. Iniciar sesión como administrador y crear la institución. Crear cuentas de psicología y dirección, el aula, responsables principal/suplente, horario, canales y recursos. Personalizar finalidad y documento de participación; registrar la decisión profesional antes de habilitar el cuestionario.
2. Crear un estudiante **de prueba** y asignarle psicólogo. Se generan una invitación y un código, además del enlace independiente del responsable si es menor. Entregar los enlaces y códigos por canales verificados; las invitaciones se entregan manualmente; los avisos genéricos pueden usar SMTP/FCM sólo con configuración y autorización institucional.
3. Abrir el enlace del responsable en otra sesión, verificar y registrar identidad/vínculo y autorización. El estudiante canjea su propia invitación y acepta el documento/asentimiento. El colegio debe proporcionar documentos y decisiones aplicables; la verificación técnica no sustituye esa organización.
4. Elegir uso, ubicación, pasos, acceso de investigación y recordatorios por separado. Se puede completar el cuestionario y solicitar apoyo sin conceder GPS. Los sensores necesitan autorizaciones vigentes y, en Android, permisos del sistema e inicio explícito del servicio.
5. Enviar PHQ-9 o solicitar apoyo. Psicología recibe el caso y aviso, reconoce, registra contacto, agenda y completa seguimientos; el estudiante confirma la cita. Dirección administra sin acceder a respuestas individuales. El investigador solo ve lo que permiten sus permisos y autorización del participante.
6. Probar pausa, reanudación, retirada y renovación de acceso. Renovar acceso invalida dispositivos anteriores y conserva el mismo estudiante; restablecer contraseña invalida sesiones anteriores. Cambiar documento exige nueva autorización/asentimiento.

El PHQ-9 usa 14 días, total 0–27 y funcionamiento separado; el ítem de seguridad genera revisión aunque el total sea bajo. El formulario no produce un diagnóstico. Los recursos y cobertura siguen visibles en Android con la última configuración recibida aun sin conexión; una solicitud en cola no se presenta como recibida.

## Instalar y conectar Android

APK de revisión: `.runtime/entrega/acompana-escolar-0.2.1-debug.apk`. Android 10/API 29 o posterior; pasos requieren contador físico. Copiar el archivo al teléfono y permitir la instalación desde la aplicación que lo abre. Es una compilación de desarrollo firmada con clave de desarrollo, no una publicación en Play Store.

Para probar **sin publicar ni configurar dominio**, conectar el Android por USB, habilitar opciones de desarrollador y depuración USB, aceptar su autorización y ejecutar:

```bash
.tooling/android-sdk/platform-tools/adb devices -l
.tooling/android-sdk/platform-tools/adb install -r .runtime/entrega/acompana-escolar-0.2.1-debug.apk
.tooling/android-sdk/platform-tools/adb reverse tcp:8001 tcp:8001
```

En la APK introducir `http://127.0.0.1:8001` y la invitación/código del estudiante de prueba. La excepción HTTP solo funciona en debug y en localhost/emulador. USB debe seguir conectado; el localhost del celular sin `adb reverse` no apunta a esta computadora. Si una instalación anterior usa otra clave, Android rechazará la actualización: conservar sus datos y usar un dispositivo de prueba separado; no desinstalar automáticamente.

Para uso inalámbrico, se necesita un servidor HTTPS alcanzable y de confianza para Android. El entorno local no se ha desplegado en Azure. La receta `infra/compose.REAL.yaml` usa HTTPS con Caddy y CA interna para revisión; su certificado requiere instalación/confianza explícita en dispositivos de prueba. Para despliegue futuro usar dominio/certificado público, secretos propios y configuración institucional; el Compose no los fabrica.

Activar ubicación en la pantalla de participación inicia un servicio visible con pausa. Fused es preferido; LocationManager es alternativa. El intervalo 15 minutos/desplazamiento 100 m es una solicitud, no garantía. No se arranca el servicio de ubicación desde WorkManager o reinicio. Tras force-stop/reinicio, reabrir y activar desde la app. Uso necesita permiso Usage Access, pasos actividad física, recordatorios permiso de notificaciones. Ubicación aproximada permite continuar pero excluye análisis fino. Las brechas quedan ausentes, no en cero.

Los puntos locales y la cola están cifrados. Sin permiso para subir coordenadas se envían resúmenes; la zona voluntaria se calcula localmente. Los días de análisis usan la zona del dispositivo al vincularlo; cada punto conserva además zona/offset observados. Las pausas crean segmentos separados y no se interpolan. Android conserva hasta siete días de puntos para resumir/reintentar; formularios usan borrador/cola local. El portal web requiere conexión para enviar.

## Compilar y firmar

```bash
export JAVA_HOME=/home/petitavo/acompana-escolar/.tooling/jdk
export ANDROID_HOME=/home/petitavo/acompana-escolar/.tooling/android-sdk
cd apps/mobile
../../.tooling/flutter/bin/flutter build apk --debug
# Herramienta LAB separada:
../../.tooling/flutter/bin/flutter build apk --debug -t lib/lab_main.dart
```

Para release configurar ANDROID_KEYSTORE_FILE (ruta absoluta), ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS y ANDROID_KEY_PASSWORD en un entorno privado; luego `flutter build apk --release` o `flutter build appbundle --release`. Sin clave propia el release queda sin firma institucional. No guardar keystores/contraseñas en Git. La identidad del paquete sigue estable para preservar instalaciones. No se promete captura equivalente en iOS.

## Notificaciones

La bandeja y escalamiento funcionan sin Firebase. FCM requiere cuenta de servicio en FCM_SERVICE_ACCOUNT, ALLOW_EXTERNAL_NOTIFICATIONS=true, habilitación institucional y token autorizado. Al compilar Android suministrar FIREBASE_APP_ID, FIREBASE_API_KEY, FIREBASE_PROJECT_ID y FIREBASE_SENDER_ID del proyecto propio. Las credenciales privadas de servicio nunca se incluyen en APK.

Se envían mensajes genéricos sin respuestas, puntajes ni coordenadas. Aceptación del proveedor significa enviado; solo el acuse del dispositivo significa entregado. El reconocimiento profesional se registra aparte. Recordatorios locales y sincronización son aproximados, dependen del sistema y de preferencias. No se verificó envío real FCM ni entrega física en esta máquina.

## Copias, restauración y pruebas

```bash
python3 scripts/product.py exec .venv/bin/python scripts/product_backup.py backup .runtime/copia-producto
python3 scripts/product.py exec .venv/bin/python scripts/product_backup.py restore .runtime/copia-producto restore_revision --deletion-ledger .runtime/artifacts/REAL/deletions.jsonl
make product-test
make product-postgres-test
make product-web-test
make contracts
```

Backup contiene base, artefactos y checksums con permisos privados. Restauración exige una base nueva `restore_*`, no inicia servidores y reaplica el ledger **actual** de retiradas para no recuperar personas borradas. Si todavía no hay ledger, el operador debe verificar que no existan retiradas y proporcionar un archivo vacío explícito; no se omite esta comprobación silenciosamente. Conservar copias y ledger en almacenamiento privado separado del equipo, según la política institucional.

`verify_product_postgres.py` y `product_e2e.py` crean y eliminan bases desechables; no cargan identidades ficticias en la institución principal. El piloto permanece PILOT_ENABLED=false. Localmente COOKIE_SECURE=false es solo para loopback; Compose REAL usa cookies seguras y HTTPS. La retención aplica a crudos y derivados, y la retirada invalida accesos y elimina datos/artefactos vinculados mediante worker. Supervisar los logs privados `.runtime/product-*.log`.

Cambios de la actualización móvil: [Android 0.2.1](CAMBIOS-ANDROID-0.2.1.md).


## Actualización 0.3.0

La entrega vigente, APK y resultados están en [IMPLEMENTACION_A01_A10.md](../IMPLEMENTACION_A01_A10.md). Para historial, correcciones, construcción local de datasets y programación consulte [CONTRATO-DATOS-0.3.0.md](CONTRATO-DATOS-0.3.0.md). Para SMTP, HTTPS, backups y actualización consulte [OPERACION-VERIFICABLE.md](OPERACION-VERIFICABLE.md).
