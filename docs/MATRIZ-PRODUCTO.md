# Complemento de producto: matriz de implementación y aceptación

El complemento del 6 de septiembre sustituye los límites funcionales anteriores. Se conserva el repositorio, DEMO/LAB y sus datos; REAL añade el producto escolar. No se publica ni se habilita captación de menores en esta entrega. La activación del piloto es configuración independiente y queda apagada.

| Requisito | Base existente | Cambio implementado | Aceptación |
|---|---|---|---|
| Institución, aulas, cuentas y asignaciones | User, Participant, Assignment | Módulo escolar y migración aditiva | Administración crea aula, invitación y equipo; dirección sin respuestas |
| Incorporación y autorización | Invitación de dispositivo, consentimiento adulto | Verificación individual, enlace independiente de responsable, asentimiento y renovación | No activa sensores antes de autorizaciones; enlaces de un uso |
| PHQ-9 español | Motor versionado CHECKIN_DEMO | Fuente AETC exacta, checksum, 14 días, ítem 9 independiente | 0–27, funcionamiento aparte, idempotencia y caso con total bajo |
| Apoyo y seguimiento | Contacto, caso y notas | Historial, tareas, citas, bandeja, cobertura y recursos | Respuesta → caso → aviso → reconocimiento → cita → cierre |
| Ubicación y pasos | UsageEvents y cola SQLCipher | Servicio visible Fused/LocationManager, pasos y permisos independientes | Captura real pendiente de teléfono; contratos y límites probados |
| Movilidad y calidad | Features de pantalla | Haversine, brechas, radio, zona voluntaria, entropía, pasos | Medianoche, saltos, permiso aproximado, null y pausas |
| Psicólogo | Cola, detalle y gráfico | Resumen, estudiantes, seguimientos, calendario, informe individual | Asignaciones, notas privadas, unidades y ausencia de modelo honesta |
| Diagnóstico privado | Panel investigador | Permisos separados, mapa temporal solo autorizado | Sin coordenadas en panel psicólogo/exportación general |
| Modelos reales | Pipeline XGBoost sintético | Dataset autorizado, entrenamiento, registro, sombra, activación y rollback | Contrato compatible, particiones sin futuro, fixtures solo en tests |
| Notificaciones | Eventos de panel | Bandeja transaccional, worker, escalamiento y adaptador FCM | Sin afirmar entrega sin acuse; sin envío externo sin configuración |
| Operación | Compose, Azure preparado | REAL local, backups/restauración y APK | Migraciones sin pérdidas, restauración comprobada, build Android |
| UI y separación de pruebas | React y Flutter | Navegación escolar, herramientas aparte, estados vacíos útiles | Playwright, revisión visual, Flutter y pruebas de permisos |

La evidencia y las dependencias externas se detallan en [ENTREGA-PRODUCTO.md](ENTREGA-PRODUCTO.md). La captura física y entrega FCM no se declaran verificadas.

## Archivos principales

- Institución, incorporación, cuestionario, casos y roles: `services/backend/app/school_api.py`, `school_core.py`, `school_schemas.py`, `school_db.py`; migración `88bbfdf4ceb6_school_product.py`.
- Instrumento y movilidad: `app/phq9.py`, `app/mobility.py`, `app/sensor_api.py`, `worker/school.py`; contratos compartidos en `packages/contracts/fixtures`.
- Modelos y notificaciones: `app/model_api.py`, `ml/school_pipeline.py`, `app/notifications.py`.
- Web: `apps/web/src/Product.tsx`, `product.css`; aceptación en `apps/web/product-e2e`.
- Android: `apps/mobile/lib/school.dart`, `SchoolCollector.kt`, `LocationService.kt`, `MobilityMath.kt`, `SchoolPush.kt`, `SchoolReminders.kt`; pruebas en `apps/mobile/test` y `android/app/src/test`.
- Operación: `scripts/product.py`, `product_backup.py`, `verify_product_postgres.py`, `product_e2e.py`, `infra/compose.REAL.yaml` y `infra/Caddyfile.REAL`.
