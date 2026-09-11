# Matriz de autorización

Todos los paths comienzan con `/api/v1`. El backend aplica los controles; ocultar navegación es solo UX. Una persona usa cuentas distintas si necesita roles distintos.

| API | Participante | Psicólogo | Investigador | Admin |
|---|---|---|---|---|
| auth/login | Invitación, no contraseña | Su cuenta | Su cuenta | Su cuenta |
| me / logout | Propia identidad | Propia | Propia | Propia |
| enrollments/redeem | Invitación válida y no usada | — | — | Crea invitación por CLI |
| me/collection-policy | Propio dispositivo | — | — | — |
| me/participation-events | Propio dispositivo, orden temporal validado | — | — | — |
| capture-sessions / events/batch | Propio dispositivo activo, intervalo autorizado y procedencia del entorno | — | — | — |
| questionnaires/due / questionnaire-responses | Propias, completas, versión habilitada | — | — | — |
| contact-requests / me/deletion-requests | Propias, idempotentes | — | — | — |
| psych/cases y detalle | — | Solo asignados | — | — |
| psych/participants/:id/summary | — | Solo asignados; sin crudo ni paquetes | — | — |
| psych/cases/:id/transitions/notes | — | Asignado, CSRF, versión optimista | — | — |
| psych/usability-feedback | — | Cuenta propia, sin datos de salud | — | — |
| lab/devices/events/features/lineage | — | — | Técnicos del entorno | — |
| lab/reprocessing-jobs | — | — | Dispositivo existente del entorno | — |
| lab/training-runs | — | — | Solo DEMO, job propio | — |
| lab/exports | — | — | Crudo/features; dataset etiquetado solo DEMO | — |
| lab/exports/:id/download | — | — | Solo creador, no vencida | — |
| CLI cuentas/asignaciones/instrumentos | — | — | — | Operador de infraestructura |

La invitación contiene al menos 192 bits aleatorios y expira. Los tokens se guardan hasheados en el servidor. Web: cookies HttpOnly, SameSite Strict y Secure (excepción local DEMO HTTP); header CSRF en mutaciones y comprobación de Origin. No hay tokens web en localStorage. El formulario web de prueba mantiene el token de su dispositivo únicamente en memoria.

El servidor limita intentos de login a cinco por cuenta/origen en 15 minutos. Nginx agrega límite de tasa para login y 1 MB por solicitud. Hay límites de longitud, lotes de 500 y paginación máxima de 200. El despliegue permanece local por defecto; no se ha hecho una auditoría de seguridad exhaustiva ni se habilita exposición pública.

Pruebas implementadas: cambios de UUID, rol incorrecto, casos sin asignación, CSRF ausente, reuso de claves con otro cuerpo, origen/procedencia incorrectos y revocación. Las relaciones entre IDs se comprueban antes de persistir.

Solo puede existir un caso activo por participante (índice único parcial). Reabrir un caso cuando ya hay otro activo devuelve 409 para conservar ese único seguimiento.
