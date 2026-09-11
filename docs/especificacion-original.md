# Prompt maestro para Codex — MVP interno de seguimiento escolar

Versión 1.0 · 6 de septiembre de 2026 · Entregable: instrucciones de construcción, no aplicación ya implementada.

## 1. Tu tarea y resultado esperado

Actúa como ingeniero de software responsable de implementar este MVP de extremo a extremo. Construye código ejecutable, no solo mockups. Lee primero AGENTS.md y el repositorio existente, conserva trabajo ajeno, crea un plan y avanza por entregas verticales. No solicites decisiones rutinarias de stack o diseño: las siguientes decisiones son el punto de partida. Documenta cualquier limitación técnica real y continúa con las partes independientes. No inventes pruebas en dispositivos que no hayas realizado.

El proyecto académico UPC propone apoyar la revisión de estudiantes del Colegio Santa María del Camino mediante cuestionarios, registros del celular y cambios respecto al historial personal. Somos dos autores de Ingeniería de Software. Este MVP es exclusivamente para pruebas internas con datos ficticios y teléfonos de investigadores/adultos voluntarios. El colegio dispone de psicólogo, que evaluará el producto y, en un futuro piloto autorizado, sería responsable de revisar los casos. El permiso de la dirección no equivale a autorización para captar datos de menores.

Implementa tres interfaces:

1. App Flutter para Android instalada en teléfono real: incorporación, permisos, captura verificable, cuestionarios, sincronización y control de participación.
2. Panel web del psicólogo: cola de revisión, detalle del caso, resultados del cuestionario y evolución conductual explicada, seguimiento y registro de decisiones.
3. Panel web de investigación: dispositivos, permisos, datos crudos permitidos, trazabilidad de transformaciones, calidad y experimentos de ML.

Nombre provisional: **Acompaña Escolar — Laboratorio**. Interfaz íntegramente en español. No diagnosticar ni presentar una probabilidad clínica no validada. La primera versión debe poder demostrarse sin esperar semanas de datos ni conseguir un dataset externo.

## 2. Dos modos independientes

### DEMO

- Participantes y registros sintéticos, banner persistente “Demostración · datos ficticios”.
- Semilla reproducible: 12 participantes ficticios, 60 días, variedad de registros y cuestionarios de prueba. Incluir evolución estable, cambio persistente, exámenes, pérdida de permisos, falta de internet, pocos datos y solicitud de ayuda.
- Entrenar un modelo de demostración con etiquetas sintéticas para probar el circuito técnico. Su nombre siempre incluye “DEMO”; ninguna métrica constituye evidencia clínica.
- Un generador explícito crea datos. Nunca un endpoint que finja haberlos leído de un teléfono.

### LAB

- Solo teléfonos de adultos que acepten la prueba. Registros realmente captados por Android y cuestionarios de prueba o instrumentos habilitados según la sección 7.
- Identificador tipo LAB-001; sin DNI, dirección domiciliaria ni información real de escolares.
- Captura y sincronización reales desde el primer día. Baseline y ML pueden mostrar “Todavía no disponible”.
- Las alertas conductuales siguen siendo de cambio observado. ML experimental no toma decisiones de atención.
- No existe modo de producción con menores en esta entrega. No debe impedirse la demo por esta exclusión.

Separar modos en servidor: dataset/entorno y permisos; preferentemente bases independientes mediante perfiles Compose. No basta un filtro visual. Nunca mezclar datos reales con sintéticos al entrenar, exportar o calcular métricas.

## 3. Arquitectura concreta

Monorepo:

```text
apps/mobile/                 Flutter + puente Android Kotlin
apps/web/                    React + TypeScript + Vite
services/backend/app/        FastAPI, API y lógica de dominio
services/backend/worker/     procesamiento en segundo plano
services/backend/ml/         entrenamiento y evaluación fuera de peticiones HTTP
services/backend/tests/
packages/contracts/          OpenAPI y contratos generados
infra/                       Docker Compose, proxy y configuración
docs/                        arquitectura, diccionario, guía de prueba y decisiones
fixtures/                    generadores y ejemplos sintéticos
```

Stack propuesto: Flutter Material 3; Kotlin para UsageStatsManager, Room y WorkManager; React con componentes accesibles y gráficos sencillos; FastAPI + Pydantic + SQLAlchemy + Alembic; PostgreSQL; scikit-learn, XGBoost y SHAP para experimentos. Selecciona versiones estables compatibles al implementar, registra versiones y lockfiles. No dependas de versiones “latest” sin fijar.

Arquitectura lógica: interfaces → API autenticada → servicios de dominio → PostgreSQL. Un worker independiente usa la misma lógica de features que los experimentos. No dupliques fórmulas en frontend, móvil y notebooks. La app guarda eventos sin conexión; el backend es la fuente del cálculo versionado.

Docker Compose levanta `db`, `api`, `worker`, `web` y proxy para acceso HTTPS cuando corresponda. Una tabla de jobs PostgreSQL con bloqueo transaccional, intentos y recuperación de leases vencidos basta en el MVP; no incorporar Redis/Celery por inercia. Un comando encola procesos; el worker los ejecuta. Ningún entrenamiento largo dentro de la respuesta HTTP.

Notificaciones iniciales: bandeja persistente en el panel con actualización periódica; no requiere Firebase. La futura integración FCM va detrás de una interfaz, desactivada. Una notificación push futura contendría solo aviso genérico, nunca puntajes o respuestas sensibles.

Entrega `.env.example` sin secretos, migraciones, healthchecks, script de inicialización y comandos reales en README. App conectable al servidor mediante URL configurable para desarrollo, no URL fija en código.

## 4. Roles y separación de accesos

| Rol | Acceso |
|---|---|
| Participante LAB | Solo su dispositivo, respuestas, consentimiento, estado y solicitudes |
| Psicólogo | Solo participantes asignados, cuestionarios y resúmenes; revisión de casos |
| Investigador | Datos técnicos seudonimizados y exportaciones explícitas del LAB; experimentos |
| Administrador | Cuentas, asignaciones y configuración; sin acceso implícito a todos los datos de salud |

Autoriza cada endpoint y cada objeto en backend. La pantalla oculta no es control de acceso. Asignación explícita al caso para psicólogo; investigador con scope específico para respuestas de instrumentos reales si existieran. Una persona puede tener dos cuentas de prueba; no fusionar permisos silenciosamente.

Autenticación: cuentas administrativas creadas por CLI, sin registro público; invitación de un solo uso para teléfono. Contraseñas con Argon2, sesiones revocables, límites de intentos. Web usa cookies HttpOnly/Secure/SameSite con protección CSRF; móvil usa token revocable almacenado con protección del sistema. No guardar tokens web en localStorage. Las credenciales de demo solo se generan/habilitan bajo perfil DEMO, nunca hardcodeadas como acceso permanente.

## 5. Qué datos captar realmente en Android

MVP Android nativo a través de Flutter, minSdk inicial 29; target/compile SDK según documentación vigente al construir. iOS queda fuera de captura real: no prometer que ofrece las mismas APIs. El panel web no puede recoger uso de otras aplicaciones.

### Obligatorio: capacidad de captura y eventos de uso

Usar UsageStatsManager con acceso de uso autorizado explícitamente en ajustes. Consultar UsageEvents cuando esté disponible. Exponer capacidades por versión y fabricante; un permiso declarado no prueba que haya datos.

| Registro | Campos permitidos | Qué representa |
|---|---|---|
| Evento de pantalla | instante, SCREEN_INTERACTIVE / SCREEN_NON_INTERACTIVE | Estado interactivo del dispositivo; no atención humana medida |
| Evento de bloqueo | instante, KEYGUARD_SHOWN / KEYGUARD_HIDDEN, si disponible | Bloqueo ocultado/mostrado; no identidad de quien usa el teléfono |
| Evento de actividad | instante, ACTIVITY_RESUMED / ACTIVITY_PAUSED, paquete si autorizado | Actividad Android; no equivale uno a uno a abrir una app |
| Consulta del colector | inicio/fin consultados, éxito/error, permiso, cantidad, cursor | Evidencia de funcionamiento de captura, aunque no haya eventos |
| Estado de dispositivo | API Android, fabricante/modelo, versión app, zona horaria | Compatibilidad y diagnóstico sin identificadores de hardware |
| Estado técnico muestreado | batería, carga, conectividad, fecha | Depuración de sincronización; no variable clínica inicial |

No captar texto de mensajes, pulsaciones, llamadas, SMS, contactos, micrófono, cámara, notificaciones ajenas, URLs o contenido de pantalla. No usar AccessibilityService, root, keylogger ni privilegios de administrador para evitar permisos. No solicitar QUERY_ALL_PACKAGES para inventariar el teléfono. Paquetes obtenidos de eventos de uso requieren opción explícita separada “Compartir detalle de aplicaciones para la prueba”; por defecto omitir paquete antes de persistir/exportar.

GPS y pasos: sección de capacidades previstas, con `not_implemented` visible. No implementarlos antes de completar el circuito obligatorio. La primera entrega no estima movilidad ni sueño. Mostrar “Uso nocturno del teléfono”, jamás “Horas dormidas”. Si falta un sensor, no rellenarlo con valores ficticios.

### Captura local y sincronización

Kotlin tiene la responsabilidad de colectar incluso cuando Flutter no está abierto: WorkManager programa trabajo periódico best effort, Room conserva la cola y el cursor. El puente Flutter consulta estado y permite “Capturar ahora”/“Sincronizar ahora”. No depender de un temporizador Dart vivo en segundo plano. No prometer ejecución exacta cada 15 minutos; WorkManager puede demorarse y force-stop impide trabajo hasta reabrir.

- Consulta incremental con pequeño solapamiento y deduplicación. Captura hasta ahora, sin retroceder antes del inicio del consentimiento ni atravesar períodos pausados.
- Eventos crudos locales permitidos, append-only; asignar ID persistente al capturar, no al enviar. Dedupe del solapamiento mediante huella de campos estables, documentando colisiones posibles y política.
- Room/almacenamiento con cifrado elegido y documentado; claves protegidas por Android Keystore. No afirmar cifrado si solo se está usando SQLite ordinario. Desactivar backups de datos sensibles y mantener secretos fuera de logs.
- Reintentos con backoff, lotes hasta 500 eventos, confirmación de IDs, idempotencia y transacciones. Distinguir rechazo definitivo de error temporal. Borrar de outbox solo lo confirmado.
- Fechas del evento UTC, offset/zona originales, received_at del servidor y reloj monotónico para diagnóstico cuando aplique. Reloj futuro/desviado se marca y excluye del análisis hasta revisión; no se corrige silenciosamente.
- Revocación/pausa detiene captura. Reanudar crea otro intervalo permitido. No recuperar retrospectivamente los datos del período pausado. Revocar permiso a mitad de consulta vuelve a comprobar autorización antes de guardar/enviar.
- Permiso concedido con cero eventos no significa “sin uso” ni “sin datos” automáticamente. Conservar resultado de consulta y evaluar calidad por separado.

## 6. Panel técnico: ver lo crudo y cómo se transforma

Rutas `/lab/overview`, `/lab/devices`, `/lab/devices/:id`, `/lab/events`, `/lab/features`, `/lab/experiments`, `/lab/exports`.

Pantalla de dispositivo: participante seudónimo, fabricante/Android, permisos reales, última consulta/sync, outbox pendiente, fallos, estado de batería, versiones, hora del teléfono y capacidades `available`, `permission_missing`, `unsupported`, `temporarily_unavailable`, `not_implemented`.

Explorador de eventos con filtros de participante/dispositivo, fecha, tipo y origen; paginación por cursor; vista tabla y JSON permitido. Ejemplo de contrato, ficticio:

```json
{
  "schema_version": "1.0",
  "event_id": "UUID",
  "device_id": "UUID",
  "occurred_at": "2026-09-06T03:20:00Z",
  "timezone": "America/Lima",
  "event_type": "SCREEN_INTERACTIVE",
  "source": "android_usage_events",
  "payload": {},
  "capture_session_id": "UUID",
  "consent_version": "lab-v1"
}
```

El servidor determina participante y entorno desde identidad autenticada; no confía en un participant_id enviado. Valida payload por tipo con lista permitida, límites y versiones. No aceptar JSON arbitrario con datos sensibles.

Vista trazabilidad: seleccionar un día → intervalos reconstruidos → eventos usados, descartados y motivo → feature diaria → baseline → desviación → caso. Conservar versión y linaje incluso al reprocesar. Ejemplo demostrativo: 22:10 pantalla interactiva, 22:25 no interactiva → 15 minutos nocturnos; identificar datos ficticios.

Exportación CSV/JSONL seudonimizada por período y permiso, asincrónica, auditada, caducidad 24 horas. Mitigar inyección de fórmulas CSV. Descarga autenticada, sin enlaces públicos. Distinguir exportación de crudo, features y dataset etiquetado. Mostrar filas, participantes únicos, ausencias, período, versión y origen. Nunca exportar secretos ni archivos de modelos cargados por otros usuarios.

## 7. Cuestionarios: dos funciones diferentes

Mindcraft distinguía cuestionarios de referencia iniciales (etiquetas) y respuestas diarias sobre bienestar que también eran entradas del modelo. No confundas ambos. En nuestro MVP, el cuestionario de referencia futuro será el objetivo que intentamos estimar; sus respuestas de la misma fecha no entran como variables para predecir ese mismo resultado.

### Funcionalidad ejecutable ahora

Motor de formularios versionados, con borrador local, opciones, validación, envío idempotente, puntuación en servidor, historial y generación de caso por reglas. Incluir `CHECKIN_DEMO_V1`, inventado, con tres preguntas: “¿Cómo sentiste tu energía hoy?”, “¿Qué tan fácil te resultó concentrarte hoy?”, “¿Cómo sentiste tu descanso hoy?”. Opciones 0 muy bien / 1 bien / 2 regular / 3 mal. Suma 0–9 solo para probar software; no llamarlo PHQ, KADS o escala validada. Regla de demostración >=6 crea `questionnaire_review_demo`; está rotulada como arbitraria y no clínica. No incluir ítems de autolesión inventados.

Incluir petición separada “Quiero que me contacten”, que crea un caso sin necesidad de puntaje. En modo interno, informar que se prueba el flujo y no existe atención de emergencia garantizada. El dispositivo muestra si está pendiente de envío; no dice “psicólogo avisado” antes del acuse servidor.

### Instrumento real preparado, pero no inventado

Crear importador CLI de definición revisada: `instrument_id`, versión, idioma, procedencia, permisos de uso, preguntas exactas, opciones, ventana de recuerdo, scoring, umbrales de revisión y reglas por ítem suministradas explícitamente. No usar eval ni código ejecutable de usuario; DSL limitada y validada. No copiar/adaptar de memoria PHQ-A, PHQ-9 o KADS-6 ni tratarlos como equivalentes. Si falta instrumento revisado, la app sigue operativa con el demo. Separar claramente “motor implementado” de “instrumento habilitado”.

Un instrumento real exige configuración de responsable, cobertura, confirmación y escalamiento antes de habilitarse para participantes. Las reglas de atención son independientes del ML y pueden activarse por un ítem aunque el total sea bajo. Una notificación enviada no es una derivación atendida. En el piloto futuro, cuestionarios autoadministrados no eliminan la responsabilidad profesional de respuesta.

Guardar fecha de aplicación, inicio/fin del período preguntado, respuestas, total calculado, completitud y versión. Un cuestionario incompleto no se convierte en cero; no generar etiqueta final ni puntaje parcial comparable. Cadencia inicial de demo configurable; futura cadencia del instrumento se fija en protocolo, no por ocurrencia del desarrollador.

## 8. Features y cambios personales: reglas exactas del laboratorio

“Feature” es una variable calculada a partir de registros. Baseline significa referencia personal. No transformar una desviación estadística en riesgo clínico.

### Features diarias v1

1. `interactive_minutes`: suma de intervalos de pantalla interactiva reconstruidos, sin duplicaciones.
2. `night_interactive_minutes`: parte de esos intervalos en 22:00–06:00 hora local. Definir noche D como D 22:00 hasta D+1 06:00; solo cerrar al acabar la noche.
3. `interactive_session_count`: número de intervalos iniciados; no llamarlos desbloqueos.
4. `keyguard_hidden_count`: conteo independiente, si disponible; no usar sustitutos sin nombrarlos.
5. `app_foreground_minutes` opcional técnico: intervalos por paquete si autorizado; advertir multitarea y no sumarlos como tiempo de pantalla.

Reconstrucción mediante máquina de estados ordenada por tiempo. Manejar duplicados, eventos fuera de orden, reinicio, intervalo que cruza medianoche y extremos sin pareja. Nunca extender una pantalla abierta hasta ahora a través de una brecha sin evidencias. Intervalos incompletos quedan como incompletos y no son una duración confirmada. Límite de duración diaria física 24h, con manejo de día local según zona; no clipping silencioso para esconder errores.

### Calidad

Almacenar por feature valores y estados separados: `observed`, `partial`, `missing`, `unsupported`. Mostrar número de consultas exitosas, ventanas consultadas, errores y permisos. La cobertura operacional es unión de ventanas consultadas exitosamente dentro de períodos autorizados / duración objetivo. No equivale a completitud garantizada de Android. Marcar esa limitación en documentación, no “100% de comportamiento capturado”.

Configuración LAB propuesta, no validada clínicamente: día elegible requiere cobertura operacional >=80%, permiso continuo documentado en el período y ausencia de brecha conocida que impida reconstrucción de esa feature. Falta de trazabilidad del permiso se marca incierta. Para noche se evalúa el tramo nocturno específico. Un día con consultas verificadas y sin uso puede ser cero; un día sin captura es null.

### Baseline y desviación

- Evaluación diaria al cerrar datos; ventana actual últimos 7 días completos. Requiere >=5 días elegibles por feature.
- Referencia: 28 días inmediatamente anteriores a la ventana actual; requiere >=14 días elegibles por feature. Referencia y actual no se superponen. Usar solo información conocida a la fecha de evaluación.
- Baseline = mediana de días elegibles de referencia. Actual = mediana de días elegibles actuales. Delta = actual - baseline, en unidad original.
- Desviación robusta = delta / max(1.4826 × MAD_referencia, piso). MAD es mediana de diferencias absolutas respecto a la mediana. Pisos de laboratorio: 15 minutos para duraciones y 5 eventos para conteos, configurables/versionados, sin sentido clínico.
- Porcentaje de cambio solo si baseline >0; si es cero mostrar delta y “porcentaje no definido”.
- Candidato de cambio: valor absoluto de desviación >=3 en al menos una feature elegible. Persistencia: 3 evaluaciones diarias consecutivas. Son ventanas superpuestas, no 3 pruebas independientes.
- Crea un caso `behavior_change`, describiendo dirección, magnitud, fechas y calidad. No usa palabras depresión, bajo/medio/alto riesgo.
- Deduplicar por participante y motivo abierto. Actualizar evidencia del caso; cerrar automáticamente solo motivo conductual tras 3 evaluaciones elegibles con todas las features monitorizadas por debajo de 2. Si faltan datos, conservar abierto con evidencia insuficiente; no fingir recuperación. Un caso humano en seguimiento no se cierra por algoritmo.
- Primer resultado depende de historial elegible, no prometer 7 días. DEMO permite reloj simulado y 60 días precargados. LAB prohíbe fechas de captura fabricadas.

Calendario académico: entidad de exámenes, vacaciones y eventos, rango y grupo. Mostrar anotaciones en las series. En v1 no restar automáticamente el cambio compartido ni suprimir alertas por exámenes; el contexto puede coexistir con problemas reales.

## 9. ML: implementado como experimento, con valor medible

Interfaces `FeatureBuilder`, `LabelBuilder`, `ModelTrainer`, `Predictor`, `ModelRegistry`. Estados de modelo `none`, `demo_trained`, `experimental`, `retired`. Ningún modelo clínicamente validado preinstalado.

Modelo candidato compartido XGBoostRegressor: una sola función entrenada con filas de múltiples participantes. Entradas: niveles actuales, baseline, deltas, desviaciones, disponibilidad y contexto temporal disponible. No participant_id, device_id, nombre, paquete identificador, texto de psicólogo ni categoría de derivación. Las características son personales; eso no crea un modelo separado por alumno.

Objetivo: estimar el total de un instrumento y versión únicos. Inicialmente total de CHECKIN_DEMO_V1 en entorno DEMO. Mostrar “Estimación experimental del cuestionario”, no probabilidad de depresión. No convertir la salida automáticamente en categorías clínicas. Inferencias sintéticas nunca se ejecutan sobre participantes LAB reales.

### Construcción temporal del dataset

Una fila por respuesta completa de referencia, no replicar una etiqueta en todas las semanas cercanas. Definir `cutoff_at`, `feature_start/end`, `label_recall_start/end`, target y provenance. Dos tareas explícitas:

- Concurrente: features del período que pregunta el cuestionario; estimar síntomas del mismo período. No se llama predicción temprana.
- Prospectiva: features terminan antes de comenzar todo el período de recuerdo del cuestionario futuro. Ejemplo: datos días 1–14, cuestionario día 28 sobre días 15–28. No basta que terminen antes de pulsar “enviar”.

Para cuestionario demo referido a hoy, construir su propio calendario de etiquetas; no atribuirle recuerdo de 14 días. Cuestionarios previos pueden ser comparación o entrada disponible al cutoff; el cuestionario objetivo jamás.

Pipeline reproducible: particiones primero, imputación/normalización/selección y ajuste solo con train; validación para hiperparámetros; test reservado. Evaluación por participantes apartados para nuevos usuarios, y temporal para futuros períodos de usuarios conocidos. Excluir ventanas que cruzan fronteras temporales según el contrato y documentar el embargo. Ajustes personales en test solo con historial anterior al cutoff, nunca su futuro o etiquetas objetivo. No split aleatorio por filas repetidas.

Comparar: predicción constante (mediana train), último cuestionario disponible por persona, Ridge con pocas features y XGBoost regularizado. Ablación: niveles actuales frente a niveles + desviaciones. Eso responde si personalizar aporta valor y si XGBoost mejora algo sencillo.

Métricas regresión: MAE, RMSE, error por participante e intervalos mediante remuestreo de participantes. Reportar cobertura: cuántas personas tienen predicción y por qué faltan otras. Reportar n de participantes únicos, etiquetas y distribución; muchas filas no reemplazan una muestra independiente. No imponer “100 alumnos = suficiente”. Si no hay partición viable, retornar informe de insuficiencia en vez de fabricar métricas. En entrenamiento real, definir plan de tamaño/evaluación posteriormente.

Panel de experimentos: ejecutar job, progreso, seed, versión de features/instrumento, tarea, particiones, métricas comparativas, procedencia y artefactos. Modelo no se promociona automáticamente por ganar una métrica. Cada modelo incluye hash, dependencias, fecha, manifest de columnas/unidades y model card.

SHAP solo en modelos compatibles entrenados: contribuciones en unidades del resultado de regresión, baseline y suma hasta predicción. No porcentajes causales. Texto “Variables que influyeron en la estimación del modelo”; no “causas de depresión”. En muestras reales, salida visible en laboratorio; en panel del psicólogo solo demostraciones rotuladas hasta contar con evaluación apropiada.

GLOBEM/StudentLife no son dependencia bloqueante. Crear adaptador CSV/Parquet con manifest y validación de esquema para futuras importaciones; nunca descargar datos sujetos a acuerdo sin acceso autorizado. No asumir mismas unidades, sensores o etiquetas, ni disponer de un modelo preentrenado clínico. Dejar contratos y reporte de compatibilidad; el entrenamiento demo ya funciona con fixtures.

## 10. Panel del psicólogo y flujo útil

Rutas `/psych/queue`, `/psych/participants/:id`, `/psych/cases/:id`, `/psych/history`.

Cola con filas: seudónimo/nombre ficticio, grupo, motivos, antigüedad, estado de revisión, fecha último cuestionario, datos suficientes/parciales. Filtros por tipo/estado/grupo; ordenar con reglas transparentes: solicitud de contacto y reglas de cuestionario según configuración, después cambios persistentes; dentro de categoría antigüedad. Esta prioridad de trabajo no es gravedad diagnóstica. Los nombres clínicos solo pertenecen a instrumento real habilitado, no al detector de cambios.

Estados de caso: `new`, `acknowledged`, `contact_planned`, `in_followup`, `closed`. Evidencia append-only y transiciones auditadas con actor, fecha, motivo. Permitir reabrir. Un caso puede contener motivos distintos; conservar cada uno y no borrar el de cuestionario cuando se normaliza el celular. Unir motivos recientes en un caso activo por participante; no crear 7 duplicados semanales.

Detalle: tarjetas separadas de cuestionario, comportamiento y calidad. Gráfico 35–60 días con banda de referencia y período actual; unidades/leyenda y anotación de exámenes. Frases como “Uso nocturno observado: 65 min; referencia: 25 min; cambio: +40 min”. Mostrar fecha del dato, no solo fecha de procesamiento. Sin mapas de ubicaciones ni listado de apps en este panel.

Acciones: tomar caso, planificar contacto, añadir nota de prueba, registrar revisión, cerrar con motivo. No implementar diagnóstico automatizado ni terapia. Diferenciar “aviso creado”, “aviso reconocido” y “contacto registrado”. Registrar entregas fallidas y vencimiento de reconocimiento configurable en laboratorio; el worker debe mostrar pendientes y escalamiento simulado, sin enviar mensajes externos reales.

Evaluación de usabilidad: tarea de revisar tres casos ficticios, tiempo de realización y formulario breve de comentarios sobre claridad/utilidad, separado de cuestionarios de salud. No interpretar satisfacción como exactitud clínica.

## 11. Pantallas del participante y diseño

App: bienvenida al laboratorio → invitación → explicación de datos → consentimiento LAB → permisos opcionales → inicio. Inicio muestra próximo cuestionario, captura activa/pausada, última sincronización, botón sincronizar y estado pendiente. Secciones “Mis datos”, “Cuestionarios”, “Participación”. En Mis datos ver categorías recogidas y totales técnicos propios; no puntuación predictiva ni ranking frente a compañeros.

Diseño: fondo claro #F8FAFC, texto #0F172A, primario azul #1D4ED8, acento teal #0F766E; ámbar para atención pendiente. Rojo para error operativo o solicitud que necesita actuación según protocolo, no para marcar al estudiante. Usar texto/iconos además del color; foco teclado, contraste AA, controles táctiles >=48dp, tipografía legible. Web responsive con sidebar en escritorio y navegación compacta móvil. Evitar gamificación de síntomas, rachas obligatorias y etiquetas estigmatizantes.

Componentes: banner de modo, badge de procedencia, calidad, timestamps, tablas paginadas, gráficos con unidades, estados vacío/cargando/error/sin permiso/sin conexión. Mostrar placeholders funcionales explicados, jamás gráficos de datos ficticios en modo LAB. Notas técnicas extensas solo en panel investigador.

## 12. Modelo de datos mínimo

Todas las entidades con UUID, created_at UTC, entorno y claves foráneas. Separar identidad de registros conductuales.

- `users`, `roles`, `user_roles`, `sessions`, `assignments`.
- `participants`: pseudonym, grupo, entorno, estado; vínculo identificativo separado.
- `devices`: participant, plataforma, versiones, estado, token revocable.
- `consents`, `participation_intervals`, `permission_snapshots`.
- `capture_sessions`: rango consultado, errores, conteos, permisos.
- `raw_events`: event_id único por dispositivo, tipo, fecha, payload permitido, procedencia, consentimiento.
- `daily_features`: participant/device, día/ventana, nombre, unidad, valor nullable, calidad, versión, linaje.
- `baseline_snapshots`, `deviation_evaluations`: cutoff, referencia, actual, mad, delta, estado.
- `academic_events`: grupo, rango, tipo y descripción sin salud.
- `instrument_definitions`, `questionnaire_responses`, `questionnaire_answers`.
- `cases`, `case_reasons`, `case_events`, `review_notes`, `notification_outbox`.
- `jobs`, `dataset_manifests`, `training_runs`, `model_versions`, `predictions`.
- `audit_events`, `export_jobs`, `deletion_jobs`.

Restricciones: no cruzar entorno o participantes entre relaciones; respuestas completas inmutables con nueva versión si hay corrección; no cascade que elimine auditoría necesaria sin política. Índices por participante/fecha, dispositivo/event_id, case status y jobs. No guardar binarios grandes en Postgres si se pueden guardar en volumen protegido con manifest.

## 13. API mínima y contratos

Prefijo `/api/v1`. OpenAPI con ejemplos sintéticos y errores. Fechas ISO8601 con zona, paginación limitada, correlation_id sin payload sensible en logs.

| Endpoint orientativo | Acción |
|---|---|
| POST /auth/login, /auth/logout | Sesiones |
| POST /enrollments/redeem | Vincular dispositivo con invitación |
| GET /me, /me/collection-policy | Identidad y política permitida |
| POST /me/participation-events | Pausa/reanudación/revocación idempotente |
| POST /capture-sessions, /events/batch | Ingesta validada, acuse por ID |
| GET /questionnaires/due | Formularios habilitados |
| POST /questionnaire-responses | Respuesta completa e idempotente |
| POST /contact-requests | Solicitud independiente del puntaje |
| GET /psych/cases, /psych/participants/{id}/summary | Datos autorizados |
| POST /psych/cases/{id}/transitions | Transición con versión optimista |
| GET /lab/devices, /lab/events, /lab/features | Diagnóstico autorizado |
| POST /lab/reprocessing-jobs | Recalcular con versión y linaje |
| POST /lab/training-runs | Lanzar entrenamiento asíncrono |
| GET /lab/training-runs/{id} | Estado e informe |
| POST /lab/exports | Exportación restringida |
| POST /me/deletion-requests | Retirada/borrado de datos de prueba |

409 en conflictos de estado; 422 en esquema inválido; 401/403 correctos; rate limits, límites de lote y payload. Ingesta parcial explícita `accepted`, `duplicates`, `rejected` con razón. Idempotency-Key en operaciones relevantes. Controlar que un dispositivo revocado no ingrese eventos atrasados.

## 14. Seguridad y operación interna

HTTPS para teléfonos reales; documentar certificado confiable de laboratorio o túnel privado, sin exposición pública por defecto. Emulador puede usar acceso local de debug con excepción limitada; release no admite cleartext global. Nunca recomendar desactivar validación TLS. Postgres no expuesto a internet. Exportaciones y artefactos protegidos, logs sanitizados, secretos fuera de git.

Investigadores solo ven crudo autorizado de adultos LAB. Retención propuesta configurable: crudo local/servidor 7 días, features/cuestionarios de prueba 90 días y exports 24h; describir que son decisiones de laboratorio, no plazos legales. Conservar el manifest/linaje y señalar cuando el crudo ya expiró y no se puede reproducir. Job de borrado elimina datos del participante y revoca dispositivos/sesiones; registra auditoría mínima sin respuestas. Backups internos caducan según política explícita y al restaurar reaplicar registro de borrados; no prometer eliminación instantánea de copias si no está implementada.

No usar datos/telemetría de salud en servicios externos de analítica o LLM. Deshabilitar reportes de errores que capturen pantallas/payload. Nunca almacenar claves privadas dentro del APK. Artefactos de modelos solo generados por jobs internos confiables; no deserializar pickle de cargas arbitrarias.

## 15. Secuencia de implementación y pruebas de aceptación

### Entrega A: circuito demo completo

Repo, Compose, auth/roles, migraciones, fixtures. Paneles y app mostrando un mismo backend. Formulario demo → respuesta guardada → caso → reconocimiento → nota → cierre. No botones simulados que no persistan.

### Entrega B: teléfono real

APK debug compilable/instalable; acceso de uso, puente Kotlin, Room/WorkManager, consentimiento y outbox. Capturar interacción real → sincronizar → evento visible en panel técnico con dispositivo y fecha. Anotar modelo/versión Android probados. Si no hay SDK/dispositivo disponible, entregar código y comandos exactos y señalar pruebas pendientes; no declarar esta entrega verificada en hardware.

### Entrega C: transformación y trazabilidad

Reconstrucción determinista, calidad, features, baseline y casos de cambio. Navegar de caso hasta registros fuente. Manejar día sin eventos con evidencia frente a día ausente, reinicio, pausa, duplicado, intervalos cruzados y datos atrasados. Feature nueva/reproceso no sobreescribe silenciosamente resultados usados en una revisión anterior.

### Entrega D: experimento de ML

Generador sintético con semilla → manifest → particiones → modelos comparadores → XGBoost → métricas → registro → predicción demo y SHAP. Ablación de desviaciones. LAB sin modelo válido muestra no disponible. Datos insuficientes producen informe entendible, no un resultado de éxito vacío.

Pruebas necesarias:

1. RBAC/IDOR: investigador/participante no acceden casos o datos ajenos por cambiar UUID; separación DEMO/LAB a nivel servidor.
2. Mismo lote enviado tres veces produce una sola colección de eventos. Fallo de red no pierde outbox.
3. Pausar/revocar impide captar, enviar y recuperar retrospectivamente períodos no autorizados.
4. Secuencia conocida pantalla 22:10–22:25 produce 15 minutos nocturnos; intervalos superpuestos no duplican tiempo; falta de cierre se informa.
5. Ventanas baseline y actual no se superponen; futuro no modifica retrospectivamente una predicción congelada; MAD cero no divide por cero.
6. Cuestionario incompleto no genera score final; regla por ítem configurada no es anulada por ML; solicitud de contacto funciona sin modelo.
7. Retrys de cuestionario y procesamiento no duplican casos; transiciones concurrentes generan conflicto explícito.
8. Dataset no contiene target contemporáneo entre entradas; partición por participante y restricciones temporales comprobadas por aserciones.
9. Exportación auditada/autorizada, expiración y borrado de datos de prueba verificables.
10. Playwright para recorrido web demo; tests API/dominio y pruebas Flutter/Kotlin pertinentes. Registrar resultados reales y pendientes.

No crear cientos de tests triviales; cubrir invariantes anteriores. Inspeccionar visualmente app/paneles cuando el entorno lo permita. Sin tool disponible, documentar limitación.

## 16. Cómo ejecutarlo y qué debes entregar

Crear README con prerrequisitos, versiones, comandos de arranque, migración, semilla, creación de usuarios y build APK. Proponer y hacer funcionar comandos simples como `make demo`, `make lab`, `make test` y `make reset-demo`; reset destructivo solo en DEMO. Explicar IP LAN vs localhost y acceso del teléfono al backend, HTTPS, firewall y logs sanitizados. No dejar pasos ocultos dependientes de tu máquina.

Guía manual de 15 minutos: levantar demo, entrar como psicólogo, revisar caso, cambiar de rol para ver trazabilidad, completar cuestionario, ejecutar experimento. Guía aparte de teléfono real: instalar, registrar, autorizar, usar otras apps unos minutos, capturar, sincronizar, inspeccionar, desconectar/reconectar red y pausar. Explicar que calibración longitudinal requiere días reales; usar fixtures solo en demo.

Entregables del repositorio: código completo, migraciones, contratos, fixtures, pruebas, README, arquitectura lógica/física (Mermaid), diccionario de datos, matriz de permisos por API, protocolo interno, documentación de features, informe/model card demo, limitaciones y backlog posterior. Reporte final con qué funciona, comandos ejecutados, pruebas reales, APK si se pudo compilar y qué exige teléfono físico.

La aceptación requiere demostrar utilidad operativa y captura trazable. No afirmar que ya detecta depresión ni que una puntuación bibliográfica de XGBoost prueba superioridad. No detener toda la implementación porque falte aprobación de un instrumento clínico: construir y verificar el circuito interno definido.

## 17. Fundamento y límites que deben conservarse

Fuentes consultadas para esta especificación; al implementar confirmar APIs/versiones vigentes. Los parámetros de ventanas, pisos, umbrales, stack y retención anteriores son decisiones propuestas para laboratorio, no resultados extraídos de estos artículos.

- Mindcraft, Kadirvelu et al., JMIR 2026: https://www.jmir.org/2026/1/e72501 — combina autorreportes cotidianos y sensores para estimar categorías basadas en cuestionarios iniciales. Sus resultados no equivalen a validar nuestro XGBoost ni anticipar depresión futura. Las respuestas diarias son features distintas de las etiquetas iniciales.
- Stamatis et al., 2024: https://www.nature.com/articles/s44184-023-00041-y — analiza promedios personales y desviaciones en adultos; respalda investigar cambios concretos, no etiquetar cualquier anomalía como depresión. Baseline retrospectivo de investigación no se copia usando datos futuros en una app.
- Android UsageStatsManager: https://developer.android.com/reference/android/app/usage/UsageStatsManager — permiso especial de uso, consulta de eventos y límites de disponibilidad.
- Android UsageEvents.Event: https://developer.android.com/reference/android/app/usage/UsageEvents.Event — semántica y versiones de eventos.
- Android WorkManager: https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work — ejecución periódica no exacta.
- SHAP TreeExplainer: https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html — explicaciones del modelo, no causas clínicas.

## 18. Prioridad si aparecen límites de tiempo

Completar primero captura real de pantalla/uso, eventos crudos, cuestionario demo y revisión del psicólogo. Luego baseline y experimento. GPS, pasos, Firebase, iOS, inferencia clínica, múltiples colegios, integraciones sanitarias y modelos profundos quedan fuera de v1. No ampliar esos módulos dejando incompleto el recorrido principal. Conservar todas las pantallas de estados y la distinción real/sintético, porque son necesarias para evaluar honestamente el MVP.
