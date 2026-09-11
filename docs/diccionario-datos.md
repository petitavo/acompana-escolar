# Diccionario y decisiones de persistencia

Todas las entidades operativas usan UUID, `created_at` UTC y `environment`. `environment_guard` y `login_attempts` son tablas técnicas. Seudónimo y grupo no contienen DNI, domicilio ni nombres de menores.

| Tabla | Contenido y relación |
|---|---|
| users | Nombre de cuenta único, hash Argon2, rol único y scopes explícitos |
| sessions | SHA-256 del token, usuario **o** dispositivo, CSRF, vencimiento y revocación |
| participants | Seudónimo único, grupo y estado; sin identificadores de escolares |
| assignments | Par único psicólogo–participante |
| invitations | Hash de invitación de un uso, participante y caducidad |
| devices | Participante, estado de participación, permiso para paquetes y diagnóstico permitido |
| consents | Versión, aceptación adulta o cambio de política de paquetes |
| participation_intervals | Inicio inclusivo / fin del período autorizado, por dispositivo |
| capture_sessions | Ventana consultada, permiso antes/después, éxito, cantidad, error y estado técnico |
| raw_events | UUID persistente, captura y dispositivo, instante, zona, tipo, procedencia, payload permitido, flag de reloj |
| daily_features | Dispositivo, día, versión y JSON de valores, calidad y linaje |
| deviation_evaluations | Participante, cutoff y versión únicos, snapshot de medianas/MAD/deltas |
| academic_events | Grupo y fechas de exámenes/vacaciones ficticios |
| instrument_definitions | Definición exacta versionada, procedencia, uso permitido, reglas declarativas, habilitación |
| questionnaire_responses | Respuestas completas inmutables, período, fecha, total calculado y versión |
| cases | Participante, estado y versión optimista |
| case_reasons | Motivo independiente, evidencia inicial y estado activo/resuelto |
| case_events | Evidencia sucesiva, notas, transiciones, avisos y escalamiento simulado append-only |
| jobs | Tipo, actor, estado, intentos, lease, parámetros y resultado/manifest |
| audit_events | Actor, acción y UUID objetivo; sin respuestas ni notas |
| idempotency_keys | Actor/ruta/clave únicos, hash de solicitud y acuse |
| login_attempts | Contador y plazo de bloqueo por hash de origen y cuenta |

Para mantener el MVP pequeño, `user.role` reemplaza roles/user_roles; `questionnaire_responses.detail` agrupa answers; `deviation_evaluations.detail` incluye baseline; `case_events` agrupa review_notes y notification_outbox; `jobs` y manifiestos de archivos agrupan training_runs/model_versions/export_jobs/deletion_jobs. Las relaciones sensibles siguen usando FK, no se delega autorización al JSON. No se implementó una tabla de identidades escolares.

Raw payload: `package` solo en ACTIVITY_RESUMED/PAUSED con autorización separada. El servidor añade `utc_offset_minutes`. Rechaza claves desconocidas. No se admite texto de mensajes, URLs, geolocalización ni contenido de pantalla.

Los campos dinámicos de diagnóstico, features y artefactos se describen en OpenAPI, `docs/features.md` y la model card. No hay blobs grandes en PostgreSQL. Las exportaciones caducan a 24 horas. Los nombres de archivos son UUID generados internamente y su descarga exige sesión del investigador que las creó.
