> Actualización vigente: [Implementación A01–A10 / versión 0.3.0](../IMPLEMENTACION_A01_A10.md). Los resultados y APK que siguen documentan entregas anteriores.

# Entrega del complemento — 6 de septiembre de 2026

Implementado sobre `/home/petitavo/acompana-escolar`, conservando Flutter, FastAPI, PostgreSQL, web, DEMO/LAB y migración aditiva. SMCBackend no se modificó. Producto local: http://127.0.0.1:5174. Base principal sin estudiantes ficticios; pruebas con bases desechables. No publicado, no piloto activo.

## Estado verificable

| Área | Implementado | Verificado automáticamente | Verificado en teléfono | Requiere credencial | Requiere dato externo/configuración |
|---|---|---|---|---|---|
| Institución, cuentas, aulas, CSV, asignación, recuperación | Sí | API y recorrido web; revocación de sesiones/accesos anteriores | No aplica a administración web | Acceso inicial en archivo privado local | Responsables, calendario y configuración institucional |
| Responsable, verificación, asentimiento, renovación, retirada | Sí | Roles, enlaces individuales, idempotencia y borrado | Pendiente Android físico | Canales se entregan manualmente; no correo automático | Documentos y autorizaciones de participantes reales |
| PHQ-9 y solicitud de apoyo | Sí | Texto/checksum, 0–27, seguridad con total bajo, no dependencia de GPS, caso y seguimiento | UI Flutter probada; no hardware | Ninguna adicional para pruebas | Decisión profesional, cobertura y recursos institucionales |
| Uso, ubicación y pasos | Sí | Kotlin, permisos/políticas API, deduplicación y siete fixtures de movilidad | **Pendiente: adb no detecta teléfonos** | No para USB; HTTPS para remoto | Android con permisos/hardware; batería, force-stop y reinicio físicos |
| Movilidad, baseline y cambios | Sí | Medianoche, brechas, antimeridiano, reinicios de contador, segmentos de pausa, null, ventanas | Pendiente captura física y duración real | No | Días observados para baseline individual |
| Cola, bandeja, citas, contacto, cierre e informe | Sí | Recorrido web completo, propiedad/asignación, dirección sin datos clínicos | Portal responsive; no teléfono físico | Cuentas del equipo | Organización del equipo |
| Notificaciones y escalamiento | Sí | Bandeja, reintentos, proveedor simulado, estados de entrega y acuse separados | **Pendiente entrega FCM real** | Proyecto Firebase y cuenta de servicio | Habilitación institucional y permisos del dispositivo |
| Entrenamiento, importación, comparación, SHAP, registro y sombra/activación | Sí | Dataset fixture, exclusión del futuro, comparación, checksum y predicción reproducible, activación fixture prohibida | No aplica | Según acceso al dataset | **No hay dataset real autorizado ni modelo clínicamente validado** |
| Diagnóstico/exportación | Sí | Roles/IDOR, permiso de exportación separado, crudo GPS solo autorizado, fechas inválidas rechazadas | Pendiente puntos físicos | Permisos internos específicos | Consentimiento de investigación/crudos cuando corresponda |
| Migraciones, backup/restauración, APK | Sí | PostgreSQL conserva registro anterior; restauración conserva artefactos y reaplica retirada; build/firma APK | Instalación física pendiente | Firma institucional para release; no requerida para APK debug | Docker runtime no disponible; solo sintaxis Compose comprobada |

## Pruebas ejecutadas

- Backend de producto: **13 pruebas pasan en PostgreSQL y 13 en SQLite**.
- Regresión backend anterior: **20 pruebas pasan**.
- Playwright producto: **1 recorrido completo pasa**, desde administración/estudiante/responsable hasta revisión, cita, contacto y cierre; informe y límites de dirección incluidos.
- Playwright DEMO conservado: **3 recorridos pasan**. Se corrigió la llamada al módulo de notificaciones escolares para que DEMO/LAB no dependan de sus tablas.
- Flutter: **analyze sin incidencias y 4 pruebas pasan**, incluidas tres capturas de interfaz. Son renders de tests, no evidencia física.
- Kotlin: **3 tests JVM pasan**, uno recorre los siete casos compartidos Python/Kotlin.
- Web: TypeScript/Vite compilan; **npm audit: 0 vulnerabilidades** en el árbol verificado. Aviso restante de tamaño del bundle (~677 kB sin comprimir) no impide ejecución.
- Contratos OpenAPI y TypeScript regenerados.
- APK Android 0.2.0, versionCode 2, min API 29, target 36, firma v2 verificada.
- Migración inicial → head sin pérdida del registro de comprobación; pg_dump/pg_restore con artefactos independientes y ledger actual de retiradas comprobados.
- Compose REAL: configuración sintáctica válida; no se afirma ejecución de contenedores, dado que no hay daemon Docker.

Logs: [verificacion.txt](evidencias/producto/verificacion.txt). Hay un aviso de deprecación de Starlette/AnyIO en tests; no fallos. Se verificó la web local y su proxy con respuesta de salud REAL después de reiniciar API/worker/web.

## Pantallas revisadas

Capturas de identidades ficticias en entorno desechable:

- [Acceso](evidencias/producto/01-acceso.png), [administración de estudiantes](evidencias/producto/02-estudiantes.png).
- [Inicio estudiante responsive](evidencias/producto/03-estudiante-movil.png), [cuestionario](evidencias/producto/04-phq-movil.png).
- [Cola de psicología](evidencias/producto/05-cola-psicologia.png), [caso con seguridad y total bajo](evidencias/producto/06-caso.png), [seguimientos](evidencias/producto/07-seguimientos.png).
- Renders Flutter: [incorporación](evidencias/producto/flutter-product-onboarding.png), [inicio](evidencias/producto/flutter-product-home.png), [PHQ](evidencias/producto/flutter-product-phq.png).

## Instalación y próximos requisitos externos

APK: `.runtime/entrega/acompana-escolar-0.2.0-debug.apk`.
SHA-256: `8c40fd039e95f37007dd85885099af33c982c6aa70dad6a296f86ef6ade50d66`.

Seguir [producto.md](producto.md) para instalar por USB y utilizar `adb reverse` con el servidor local. No hay URL pública ni despliegue Azure por esta orden. Para probar captura física hace falta conectar un Android, conceder permisos y observar datos reales; los tests no sustituyen esa verificación. FCM requiere credenciales propias. El entrenamiento real requiere un dataset autorizado compatible y evaluación profesional; [modelos-producto.md](modelos-producto.md) documenta el contrato y límites.

La entrega permite revisar recorridos y configurar el producto. No declara validación clínica, entrega física de notificaciones ni aceptación completa del piloto mientras esas dependencias sigan pendientes.

## Ajuste de participación posterior a la instalación

Se explica la autorización pendiente y se añade «Comprobar autorización». Los interruptores aclaran que seleccionan datos y que los permisos Android se conceden después de guardar. Flutter analyze sin incidencias y cinco tests pasan, incluida la comprobación de que no se autoriza participación ni solicitan permisos cuando falta el responsable. APK actualizada sobre el Moto G9 Plus conservando sus datos.

## Actualización disponible 0.2.1

La APK móvil actual es `.runtime/entrega/acompana-escolar-0.2.1-debug.apk`. Véase [CAMBIOS-ANDROID-0.2.1.md](CAMBIOS-ANDROID-0.2.1.md) para correcciones, pruebas y comprobaciones físicas pendientes. Esta actualización no se instaló porque el teléfono está desconectado. Las referencias 0.2.0 y su checksum anteriores corresponden a la entrega inicial.
