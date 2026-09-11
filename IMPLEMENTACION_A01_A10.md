# Implementación A01–A10 · Acompaña Escolar 0.3.0

Entrega del 9 de septiembre de 2026. Proyecto: `/home/petitavo/acompana-escolar`, separado de SMCBackend. Se conservó la referencia inicial de 190 archivos en `.runtime/implementacion-a01-a10/baseline-manifest.json`. La auditoría original permanece como evidencia histórica. Esta fase final fue implementada y verificada directamente por Codex, sin continuar con Claude.

## Resultado por hallazgo

| Hallazgo | Estado | Cambio y evidencia |
|---|---|---|
| A01 · autorización de predicciones | Corregido y verificado | Acceso por estudiante y finalidad, asignación clínica y permiso de investigación separados. Administración de modelos no concede resultados personales. Registro general sin procedencia individual. Regresiones de autorización en `test_regressions_audit.py`, `test_analysis.py` y `test_permissions_notifications.py`. |
| A02 · limpieza y retención | Corregido y verificado | Limpieza de crudos independiente de autorización, pausa o revocación; se recorren todos los dispositivos. Regresión con estados no elegibles. |
| A03 · suplencia | Corregido y verificado | Concesión mínima por caso escalado, con vencimiento y auditoría; cierre/cambio de suplente revoca acceso. Migración aditiva CaseGrant. Pruebas de caso propio, ajeno y cierre. |
| A04 · pendientes offline | Corregido y verificado en pruebas locales | Formularios, correcciones y solicitudes pendientes no caducan como sensores. Crudos caducados se borran dejando aviso hasta resolución explícita, incluso tras 90 días offline. El estudiante ve pendientes/rechazos/avisos; SQL real de DAO probado en SQLite y UI Flutter. Pendiente la desconexión larga en hardware físico. |
| A05 · dataset local | Corregido y verificado | Constructor desde respuestas, features, movilidad y autorización histórica; procedencia por etiqueta, revisión, disponibilidad, exclusiones, snapshot nuevo y hash. Preview, construcción, entrenamiento y programación en panel. Se vuelve a verificar la cuenta que autorizó el trabajo al ejecutarlo. Sin datos reales suficientes el reporte indica lo que falta. |
| A06 · identidad de evaluación | Corregido y verificado | Métricas recalculadas leyendo el artefacto persistido; hashes de modelo y dataset. El ensayo temporal tiene artefacto y hash propios. Importación no confía en métricas externas; programación no activa modelos. |
| A07 · corte y dependencias | Corregido y verificado | Día cerrado en America/Lima separado del instante de disponibilidad; espera de agregados al programar y ejecutar; retrasos visibles y reintento auditable. Coherencia día/cierre/disponibilidad, revisiones históricas y estimaciones invalidadas sin borrar evidencia anterior. Pruebas con reloj controlado y datos posteriores al corte. |
| A08 · revocación concurrente | Corregido y verificado en PostgreSQL | Comprobación antes de calcular y antes de persistir bajo protocolo de bloqueos; pausa y revocación inhiben inferencias nuevas. Investigación no sustituye autorización clínica. Dos pruebas de concurrencia reales pasan. Si la retirada se confirma después de la transacción de inferencia, invalida/elimina las estimaciones mediante su propio recorrido; no se afirma que una operación futura impida retroactivamente un commit anterior. |
| A09 · historial y transporte | Software corregido y verificado; dependencia externa | Historial propio y corrección versionada en web/Android; conserva original y motivos de seguridad, invalida datasets/modelos fuente afectados. SMTP con TLS, FCM y reintentos independientes; aceptación, entrega y reconocimiento separados y visibles. SMTP verificado con servidor loopback y FCM con adaptador controlado. Faltan credenciales y recepción externa real. |
| A10 · operación | Software/configuración verificados localmente; dependencia externa | HTTPS, secretos, Compose, monitorización, backup cifrado e integridad, restauración con retiradas, rotación PostgreSQL y paquete APK. Sin hosting, DNS, certificados públicos ni operación continua acreditados. La sintaxis Compose se comprobó, no su ejecución completa en Docker. |

## Evidencia ejecutada

Los logs están en [docs/evidencias/implementacion-0.3.0](docs/evidencias/implementacion-0.3.0/). Sólo se usaron bases desechables e identidades ficticias. No se enviaron mensajes a destinatarios externos ni se migró la instalación real.

| Comprobación | Resultado |
|---|---|
| Suite producto sobre PostgreSQL 18 | **38 aprobadas**, incluidas ambas concurrencias; migración desde esquema anterior conserva el registro ficticio y restauración reaplica retirada. `postgres-final.log`. |
| Suite producto SQLite final | **37 aprobadas, 2 omitidas** porque requieren bloqueos PostgreSQL; incluye una nueva regresión temporal añadida después de la pasada PostgreSQL. `sqlite-final.log`. |
| Operación | **65 aprobadas**. `ops-final.log`. |
| Regresiones existentes DEMO/LAB | **20 aprobadas**. `legacy-tests.log`. |
| Ventanas, programación y conservación offline focalizadas | **20 aprobadas**, incluyendo corte Lima y reprocesamiento posterior. `temporal-offline-final.log`. |
| Navegador | **1 recorrido completo aprobado**: administración, invitación, responsable, estudiante, PHQ, revisión, seguimiento y roles. `browser-final.log`. |
| Flutter | Análisis sin incidencias, **9 pruebas aprobadas**. `flutter-current.log`, `flutter-tests.log`. |
| Kotlin/JVM | **5 pruebas aprobadas**, compilación `testDebugUnitTest` satisfactoria. `android-unit-final.log`. |
| Web y contratos | TypeScript/Vite y OpenAPI generados correctamente. Persiste aviso de bundle de unos 683 kB; no es fallo de compilación. `web-final.log`. |
| APK | Compilación debug 0.3.0+4; verificación de firma APK v2 correcta. `apk-build.log`, `apk-signature.log`. |
| Backup cifrado | PostgreSQL aislado: copia íntegra restaurada, copia manipulada rechazada y retirada reaplicada. `encrypted-backup.log`. |
| Rotación de contraseña | ALTER ROLE ejecutado sobre rol ficticio, secreto 0600 y entorno actualizados, rol de prueba eliminado. `rotation-postgres.log`. |
| Compose | Configuración privada + overlay público aceptados por `docker-compose config --quiet`. `compose-check.log` vacío con salida 0. |

Advertencias de dependencias: deprecación de Starlette/AnyIO y Gradle; no se actualizaron dependencias de forma indiscriminada para eliminarlas. No se confunden estas pruebas con un ensayo clínico ni con captura física sostenida.

## APK e instalación

[Descargar APK de pruebas 0.3.0](dist/acompana-escolar-0.3.0-pruebas.apk) · [Instrucciones USB, servidor y cuentas](docs/INSTALAR-0.3.0.md).

SHA-256: `479436074b6809c7afb7d8d864214a867a9d17bf27008a19b6f496a1ccf2cc63`.

No se instaló esta APK porque el teléfono está desconectado. Es una actualización de pruebas con firma de desarrollo, no una release de tienda. El servidor local no queda desplegado en Azure por compilar o instalar la APK.

## Pendientes concretos

- **Software verificado localmente:** recorridos y adaptadores terminados dentro del alcance. Queda la aceptación del paquete en Docker/hosting y hardware de destino; los logs no acreditan esas plataformas. La monitorización distingue ausencia de evidencia de consumo del worker de salud demostrada.
- **Datos:** muestras reales autorizadas, suficientes y representativas, con cobertura temporal, calidad y etiquetas. Seis participantes/dieciocho ventanas es un mínimo técnico para ejecutar fixtures, no tamaño clínicamente suficiente. No hay un modelo real validado.
- **Configuración externa:** dominio/hosting, TLS confiado en el teléfono, secretos SMTP y FCM, configuración Firebase Android, firma institucional, reglas de red, backup externo y prueba de recuperación con objetivos RPO/RTO reales.
- **Decisiones profesionales:** aprobación del instrumento y población, protocolo de seguridad, horarios/recursos, consentimiento y finalidad, interpretación y uso de estimaciones. Propuestas separadas en [PROPUESTAS-ACADEMICAS.md](docs/PROPUESTAS-ACADEMICAS.md); originales no modificados.
- **Teléfono:** instalar preservando datos, permisos reales, pantalla apagada/reinicio, restricciones del fabricante, consumo de batería y acuses FCM. No se simulan resultados de estas comprobaciones.

## Dictámenes independientes

1. **Prueba funcional:** apta para pruebas controladas con identidades ficticias; los recorridos automatizados y APK compilan/pasan. Aceptación física pendiente.
2. **Evaluación predictiva:** no acreditada para datos reales. El circuito técnico existe y sus pruebas usan fixtures; no permite atribuir precisión clínica ni capacidad diagnóstica.
3. **Operación con escolares:** no autorizada por esta entrega. Requiere decisiones institucionales/profesionales, datos autorizados y comprobación del entorno desplegado, hardware y canales externos.

Contratos actualizados en [CONTRATO-DATOS-0.3.0.md](docs/CONTRATO-DATOS-0.3.0.md); operación en [OPERACION-VERIFICABLE.md](docs/OPERACION-VERIFICABLE.md). Corrección bibliográfica en [ACLARACION-MINDCRAFT.md](docs/ACLARACION-MINDCRAFT.md): Mindcraft predictivo 2026 e72501, distinto de aceptabilidad 2023 e44877; ninguno valida el rendimiento de esta aplicación.
