# Contratos y criterios de aceptación 0.3.0

## Selección, disponibilidad y versiones

El constructor local usa respuestas PHQ-9, Feature y MobilityDay y el historial Authorization. Se elige explícitamente `clinical` o `research` y se separa `test_fixture` de `authorized_real`. Se excluyen retirados, autorizaciones incompletas, ausencia de autorización de investigación cuando corresponde, instrumentos incompatibles, ventanas sin calidad y etiquetas con períodos superpuestos. La selección real comprueba autorización histórica; el fixture queda marcado expresamente, sin inventar consentimiento histórico.

Cada etiqueta conserva identificador de respuesta, raíz y revisión, instrumento y hash de definición, fecha de recepción y evidencia de autorización. Cada día conserva procedencia de fuentes y fecha de disponibilidad. El snapshot JSON se escribe como archivo nuevo con SHA-256; no se reescribe para acomodar una corrección. La invalidación posterior es metadata de elegibilidad en el registro, mientras los bytes y las métricas históricas se conservan.

`window_end` debe ser la medianoche posterior al día declarado en la zona del manifest; `available_at` no puede preceder al cierre. Revisiones distintas del mismo día requieren distinta disponibilidad; cada corte toma la última que ya estaba disponible. En el constructor local la zona es America/Lima. La importación antigua sin zona conserva UTC y el modelo registra esa elección explícitamente.

Antes de las 09:00 locales, el último día de análisis es D−2; después es D−1. El instante de disponibilidad es el momento efectivo de ejecución, separado de ese día cerrado. Los agregados pendientes o fallidos bloquean ejecución; el panel informa los retrasos y permite reintentar fallos. Datos tardíos invalidan estimaciones dependientes y permiten nueva revisión conservando la anterior.

## Evaluación y decisiones

Una evaluación se vincula al hash del artefacto leído del disco y al hash del dataset. La importación recalcula métricas; no acepta como evidencia métricas declaradas por el importador. La prueba temporal produce otro artefacto identificado. Programar construcción y entrenamiento no promueve modelos: quedan registrados. La activación exige una decisión profesional trazable; correcciones de fuentes retiran modelos afectados.

Administrar modelos no permite ver predicciones individuales. La atención requiere asignación al estudiante y autorización vigente; la investigación exige los permisos correspondientes. El registro general omite procedencia individual y métricas identificables por participante. Un suplente recibe una concesión explícita y temporal para el caso escalado, no acceso indiscriminado a perfiles.

## Respuestas y entrega

El historial del estudiante devuelve sus propias respuestas, fechas, revisión y estado, sin total, predicciones, umbrales ni notas clínicas. La corrección se crea con clave de idempotencia y sólo sobre la revisión vigente. Conservar el original y un motivo de seguridad previo es obligatorio.

La cola distingue recepción por el servidor de pendiente, rechazo y caducidad. Formularios, correcciones y solicitudes pendientes no caducan como sensores. Al caducar sensores se elimina el contenido crudo y se conserva el aviso hasta una resolución explícita. Un HTTP de rechazo no equivale a recepción.

Correo y FCM tienen intentos independientes, hasta tres, con esperas crecientes. La aceptación del proveedor produce `sent`; un acuse del dispositivo produce `delivered` y la acción del destinatario `acknowledged`. Las pruebas locales no acreditan llegada a una bandeja externa o a un celular físico.

## Superficies públicas

OpenAPI y tipos generados: `packages/contracts/openapi.json` y `api.d.ts`. Nuevas rutas bajo `/api/v1/school`: historial y correcciones del estudiante; construcción/preview de datasets; programación; detalle del dataset; reintento de agregados. La configuración personal admite correo de notificaciones. Los recorridos de laboratorio permanecen separados de los del producto.
