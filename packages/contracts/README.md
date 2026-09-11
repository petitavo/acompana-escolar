# Contratos

`openapi.json` se genera desde Pydantic/FastAPI con `make contracts`. `/api/v1/docs` permite explorar el esquema ejecutable. `api.d.ts` contiene los tipos TypeScript generados. Todos los ejemplos de prueba son sintéticos.

El servidor deriva entorno/participante desde sesión. Fechas con zona ISO8601; UUID persistentes; payload con lista permitida; eventos máximo 500. Las operaciones relevantes requieren `Idempotency-Key` estable en reintentos. Respuesta parcial de ingesta: `accepted`, `duplicates`, `rejected` (razón y rechazo definitivo). El cliente conserva todo registro no confirmado.
