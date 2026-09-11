# Auditoría integral de Acompaña Escolar

Fecha de cierre: 8 de septiembre de 2026. Encargo: `Prompt_Auditoria_Integral_Codex.md`. Auditoría de lectura, con pruebas y entregables aislados; no se aplicaron correcciones a la aplicación ni se publicó el producto.

## 1. Dictamen

Existe un producto funcional: aplicación Flutter con integración Android nativa, portal del responsable, panel profesional, administración, API FastAPI, persistencia PostgreSQL, cuestionarios, casos y seguimiento. El recorrido web de incorporación → autorización → solicitud/cuestionario → revisión → cita/contacto → cierre pasó en una base desechable. No es únicamente una maqueta ni un laboratorio.

**No está completo ni listo para operar con escolares.** Se reprodujeron cuatro defectos de autorización, escalamiento, conservación y entrega pendiente. La captura continua en hardware, batería, transporte público seguro y notificaciones externas siguen sin validación suficiente. Tampoco hay resultados predictivos locales evaluados: el entorno REAL consultado contiene cero datasets, cero modelos registrados y cero predicciones.

| Dictamen independiente | Resultado | Condiciones |
|---|---|---|
| Listo para probar funcionalmente | Sí, con cuentas controladas y límites explícitos | El recorrido principal pasa; escalamiento y desconexiones largas tienen fallos conocidos. Falta completar aceptación física Android. |
| Listo para evaluar rendimiento predictivo local | No todavía | Hay entrenamiento ejecutable con fixtures. Faltan dataset autorizado y trazable, puente desde capturas/respuestas, protocolo temporal y correcciones de evaluación. |
| Listo para operar con escolares | No | Resolver A01–A04, revisar elegibilidad de inferencia, protocolo profesional, permisos físicos y despliegue/operación. La aceptación de un formulario no acredita por sí sola todos estos requisitos. |

## 2. Identidad, fuentes y límites

Repositorio: `/home/petitavo/acompana-escolar`, separado de SMCBackend. Rama: `codex/mvp-laboratorio`. **Sin commits: no existe HEAD**. La identidad reproducible es el manifiesto de 187 archivos de código/configuración/documentación capturado el 2026-09-07T23:06:23Z, en `.runtime/auditoria-20260907/source-manifest.json`, SHA-256 `5de875af6c1aae0d55f434c94ea6b2814894da03476a06982f184142d41f52f4`. La verificación final (`integrity-check.json`) confirmó que los 187 archivos originales mantienen su hash. Los cambios locales iniciales están en `status-before.txt`; la copia auditada está en `snapshot/`. No se encontró AGENTS.md en las ubicaciones consultadas.

Se consultaron los seis DOCX solicitados en `/home/petitavo/Pictures`: TI, PB, IB, ACP, Estado del Arte y Metodologia_Indice_Riesgo, además de los prompts MVP, Complemento y Auditoría y el brief adjunto. **No faltan TI/PB/ACP.** `documents/inventario.json` conserva rutas, hashes completos, tamaño, fecha del archivo y metadatos disponibles; `documents/Pictures__*.txt` conserva párrafos y tablas extraídos. Los localizadores Pxxxx y Txxx.Rxxx usados aquí corresponden a esa extracción, no a páginas inventadas. La portada de TI indica 21 de junio de 2026; las fechas del sistema de archivos no acreditan aprobación académica ni clínica.

Se revisaron objetivos, alcance, backlog, arquitectura, metodología y tablas comparativas relevantes. Se inventariaron variantes en Downloads sin tratarlas como sustitutos silenciosos de Pictures. No se certificó cada referencia bibliográfica, cuartil, búsqueda sistemática ni conclusión de los 40 artículos. La conformidad documental es parcial y se detallan las diferencias, aunque estén disponibles todos los originales.

| Fuente en Pictures | SHA-256 de la versión revisada |
|---|---|
| ACP_Valenzuela_Aldhair_Huanca_Gustavo.docx | `f50c3dc6fe82d8e3b1d02b880d7567c305b03c6c9a3e383a70f3fad04419ae0b` |
| Estado del Arte.docx | `0a1a96cbf8c68da8af21b75e5ff777a71782ae6551b872043d215a1553fb49f8` |
| IB_Valenzuela_Aldhair_Huanca_Gustavo.docx | `5f21f6446764ad6b7c742b10250d562e0348e8ebac7ad7e054ca4b7226e51e26` |
| Metodologia_Indice_Riesgo.docx | `c302721392822767bda131c01eb129efe83c91f8999660c8cc1235b861bec610` |
| PB_Valenzuela_Aldhair_Huanca_Gustavo.docx | `060cde398217629b6a132e4f4cc4830ffe0cebe45c6f1adb8a0390b72b5c56c3` |
| TI_Valenzuela_Aldhair_Huanca_Gustavo.docx | `c8b316cfbe634ad64e67713ad92946c3893899969236aa308c59f2a46895c000` |
| Prompt_Codex_MVP_Seguimiento_Escolar.md | `ff35438a143ff26a36f926e2f0370fd8e6408160c50b63f5a20b76f9a122e7e7` |
| Complemento_Codex_Producto_Completo.md | `cb6733e878c70b3ce6119989ac7d384a6eef9dcbfb2ce8b78563a66c79dc1a08` |
| Prompt_Auditoria_Integral_Codex.md | `165082737f5bb436c2e3a23406b8066d74f900b58329375bd414f603122c6a9b` |

Evidencia interna: rutas `services/backend/app`, `worker`, `ml`, tests de producto y laboratorio, código Flutter/Kotlin, contratos, migraciones, scripts de aceptación, despliegue y respaldo, documentación y artefactos existentes. La revisión de seguridad es manual dentro de esta auditoría integral; no es un informe sellado del plugin Codex Security.

No hubo teléfono conectado durante esta auditoría. La evidencia previa de instalación/apertura en Moto G9 Plus Android 11 no demuestra captura sostenida ni consumo. La consulta del entorno REAL fue de agregados en transacción de solo lectura: 20 RawEvent, 8 Feature, 4 SensorPoint, 5 MobilityDay y 0 Response; además, DatasetRecord=0, ModelRecord=0, Prediction=0. Son registros recibidos, no una medición validada de cada teléfono ni prueba de procedencia clínica. No se incluyen nombres, tokens, coordenadas o respuestas individuales.

## 3. Pruebas ejecutadas

Todos los logs siguientes están en `.runtime/auditoria-20260907/`. Las bases usadas por las suites y el navegador son temporales; los destinatarios son ficticios.

| Comando/entrada | Resultado | Alcance y evidencia |
|---|---|---|
| `.venv/bin/pytest services/backend/product_tests -q` | 14 pasan | `product-tests.log`: incorporación, roles, PHQ, retirada, sensores, modelos, SHAP, idempotencia. SQLite aislado por conftest. |
| `.venv/bin/pytest services/backend/tests -q` | 20 pasan | `legacy-tests.log`: reconstrucción, ventanas, calidad, reglas, contratos y separación de laboratorio. No convierte fixtures en sensores físicos. |
| `python3 scripts/product.py exec .venv/bin/python .runtime/auditoria-20260907/snapshot/scripts/product_e2e.py` | 1 recorrido pasa | `web-e2e.log`; PostgreSQL desechable y Playwright. Roles, autorización, PHQ, reconocimiento, cita, contacto y cierre. Vista móvil web, no Android nativo. |
| `python3 scripts/product.py exec .venv/bin/python .runtime/auditoria-20260907/snapshot/scripts/verify_product_postgres.py` | 14 pasan + migración y restauración verificadas | `postgres-check.log`: preserva un registro de esquema anterior y reaplica una retirada al restaurar. No prueba recuperación de una caída de Azure. |
| `npm --prefix apps/web run build`, en snapshot | Pasa | `web-build.log`; advertencia de tamaño de bundle, no error de compilación. |
| `../../.tooling/flutter/bin/flutter analyze`, en snapshot/apps/mobile | Sin incidencias | `flutter-analyze.log`. |
| `../../.tooling/flutter/bin/flutter test`, misma ubicación | 8 pasan | `flutter-tests.log`: pantallas, instrumento, negativa de permisos y autorización confirmada. Canal nativo sustituido por dobles de prueba. |
| `PYTHONPATH=services/backend .venv/bin/pytest .runtime/auditoria-20260907/test_audit.py -q` | 5 pasan | `audit-checks.log`: cuatro reproducciones de defectos y entrenamiento sintético conservado. Aquí «pasa» significa que la prueba confirmó el comportamiento defectuoso esperado. |

Las suites tienen advertencia de deprecación Starlette/AnyIO. No se ejecutó una nueva instalación ni prueba OEM; tampoco se presenta el APK existente como recompilado en esta auditoría. Un intento inicial de Flutter usó una ruta relativa incorrecta; se corrigió la invocación sobre el snapshot y las ejecuciones válidas son las de la tabla.

La matriz CSV separa «implementado y verificado», «implementado sin verificación suficiente», «parcial», «ausente», «simulado», «dependencia externa» y «fuera de alcance acordado». No se calcula un porcentaje subjetivo de completitud. Los detalles de cada prueba pueden localizarse por símbolo en los archivos indicados.

## 4. Lo dicho por el compañero vs lo implementado

| Propuesta original y fuente | Decisión posterior/procedencia | Implementación actual | Consecuencia y juicio |
|---|---|---|---|
| Z-scores personales y ventanas 3/7/14/30; Metodología | Prompts posteriores piden referencia robusta y calidad explícita | `school_pipeline.vector`: mediana actual 7 días; baseline anterior 28, mínimo 5/7 y 14/28; escala MAD con piso | Conserva personalización, cambia estadístico y ventanas. Justificación técnica plausible, requiere actualizar metodología y evaluar sensibilidad. |
| XGBoost compartido, no 100 modelos individuales | Complemento conserva modelo compartido con características personales | Un XGBRegressor por versión, no uno por alumno | Coincide en arquitectura; no demuestra beneficio local. |
| PHQ-A/KADS-6 como etiqueta | Complemento permite PHQ-9 estándar español con decisión profesional | `PHQ9_ES_AETC_2016`, AETC-2016-es-1, PHQ-9 estándar | No son instrumentos intercambiables. Registrar elección profesional y cambiar documentos/dataset, no renombrar PHQ-9 como PHQ-A. |
| Clasificar bajo/medio/alto semanalmente; PB US-12/15/18 | Prompts posteriores priorizan regresión y motivos independientes | Puntaje estimado 0–27; cola de prioridad operativa; worker con ejecución diaria | Cambia objetivo y cadencia. Pendiente de ratificación académica/profesional. La prioridad no es probabilidad ni clase diagnóstica. |
| SHAP explica alertas | Complemento exige contribuciones reales y límites | `predict` usa `pred_contribs`, contrasta suma con salida sin recorte | Implementado y comprobado con fixture; unidades de puntos, no porcentajes causales. Las reglas no son SHAP. |
| Sueño, pantalla, movilidad, comunicación; TI P0052, Metodología T002 | Complemento distingue observación de inferencia y excluye contenido privado | Pantalla, GPS y pasos; no duración de sueño, llamadas, SMS ni socialización inferida | Parcial respecto de TI. No corresponde inventar variables; revisar alcance y necesidad de proxies validados. |
| XGBoost 4.70/5; IB T004.R009 | Comparación empírica requerida después | Comparadores entrenables: constante, último PHQ, Ridge, niveles, XGBoost | 4.70 es una valoración ponderada del benchmarking documental, no 94% de precisión ni medición de esta app. |
| Normalizar cohorte para quitar efecto de exámenes; Metodología P0037 | Contexto conocido sin ocultar cambios automáticamente | Calendario como anotación; no columna del modelo ni descuento automático | Diferencia razonable de transparencia; requiere actualizar metodología. |
| Firebase y correo automático; ACP P0077/P0145, PB US-17 | Producto admite bandeja y entrega operativa explícita | Bandeja persistente; adaptador FCM condicionado; sin transporte SMTP operativo | FCM depende de configuración y prueba; correo es trabajo de software pendiente. No declarar «enviado» porque existe notificación. |
| Arquitectura y nube académicas | Se implementa producto local con posibilidad de despliegue | Flutter/Kotlin, React, FastAPI, PostgreSQL, XGBoost; jobs persistidos en DB | Registrar React y cola real. No exigir Redis/NGINX vacíos; diferenciar infraestructura diseñada y desplegada. Azure no está acreditado como despliegue activo. |

El TI describe sueño y socialización como señales de entrada y sus objetivos de investigación no quedan cumplidos por implementar pantalla/GPS. El ACP también excluye llamadas: debe resolverse esa contradicción con la tabla de comunicación de Metodología. El Estado del Arte tiene criterios de exclusión que exigen métricas del modelo; los estudios de aceptabilidad deben clasificarse aparte o justificar la excepción.

**Comprobación bibliográfica puntual:** el artículo Mindcraft e44877 revisado es de desarrollo/aceptabilidad: 39 estudiantes, dos semanas; no aporta en ese texto un entrenamiento predictivo que autorice mezclar cuestionario objetivo con sus entradas. Si el equipo pretende citar otro trabajo de Mindcraft con cuestionarios iniciales y predictores diarios, debe identificarlo y contrastar su definición de target. No se adopta como hecho la atribución del prompt sin esa fuente. [Artículo original de Mindcraft](https://formative.jmir.org/2023/1/e44877).

## 5. Instrumento, alertas y datos

El instrumento está definido literalmente en `services/backend/app/phq9.py:PHQ9`; la copia de fuente está en `docs/instrumentos/PHQ-9_Spanish_AETC.pdf`, SHA-256 `1041559d940ba6dd5c03132e8922dcc537b750051594322b68c8fe265a79e90c`. Se revisaron instrucción de últimas dos semanas, los nueve ítems (interés, ánimo, sueño, energía, apetito, autovaloración, concentración, actividad psicomotora y autolesión), opciones 0–3 y funcionamiento separado, frente al texto institucional archivado. La prueba verifica hash y suma, no reemplaza revisión de pertinencia para adolescentes. Texto exacto de cada ítem/opción y atribución permanecen consultables en ese módulo y PDF, sin alteraciones de instrumento por esta auditoría.

Es **PHQ-9 estándar español**, no PHQ-A ni KADS-6. Se suman nueve respuestas completas, rango 0–27; funcionamiento no suma. El código propone revisión con total ≥10 y motivo independiente de seguridad si q9≥1. Estos son disparadores de revisión, no diagnóstico ni prueba de atención realizada. La configuración exige habilitación/decisión registrada; falta evaluar la calidad y pertinencia de esa decisión para el piloto. AIMS informa que no hace falta permiso para reproducir/distribuir PHQ-9; esto no equivale a autorización institucional para recoger respuestas. [AIMS Center](https://aims.uw.edu/resource/phq-9-depression-scale/), [PDF institucional](https://aidsetc.org/sites/default/files/resources_files/PHQ-9_Spanish.pdf).

Hay validación de respuestas completas y rangos, control de versión, período y duplicados. No se imputan ausentes a cero. La suite cubre idempotencia, total y q9 independiente aun sin modelo. No se encontró recorrido explícito de corrección posterior de una respuesta ni un historial completo de cuestionarios enviado para el alumno: no confundir «Mis solicitudes» con ese historial. El borrador local existe; la cola puede perderlo una vez enviado a pendientes por A04.

El psicólogo ve estudiantes asignados, series/calidad/referencia personal, respuestas, motivos de caso y seguimiento. Los orígenes son solicitud de apoyo, cuestionario, regla de cambio conductual y, solo con una versión activa, estimación ML que supere el umbral configurado en código. Una estimación baja no borra un motivo preocupante. El estudiante no recibe el score predictivo. Dirección obtiene agregados, no el perfil clínico. A01 es una excepción importante a la separación deseada.

### Captura efectiva y límites

Android mínimo 10/API29. UsageStatsManager/UsageEvents permiten reconstruir interacción y cambios de bloqueo; actividad foreground y desbloqueo no son sinónimos. El acceso de uso se concede en ajustes especiales. GPS utiliza LocationManager y permisos Android separados; paso usa TYPE_STEP_COUNTER cuando el hardware lo ofrece. Servicio foreground/listeners y WorkManager están implementados; aceptar participación en la app no concede permisos del sistema por sí solo.

Se conservan hora/zona, precisión/proveedor y tipo de permiso de ubicación; enviar coordenadas crudas requiere preferencia distinta. Sin ella se preparan resúmenes locales. Datos aproximados o imprecisos pueden recibirse con metadatos pero no se convierten automáticamente en movilidad elegible. No se recoge contenido de mensajes, audio o fotos. No se demostró cálculo operativo de minutos por aplicación/categoría; tampoco sueño, comunicación ni actividad física total. Pantalla nocturna no mide cuánto durmió alguien.

Persistencia: Room con SQLCipher, clave mediante Vault/Android Keystore, outbox/cursor, reintentos e idempotencia; esto acredita mecanismos de cifrado local, no una inspección forense completa del dispositivo. Pausa/revocación y segmentos impiden unir períodos no autorizados en pruebas. Un sensor ausente produce falta de dato, no cero observado. Falta medir reinicios reales, app cerrada, ahorro de energía, pérdida prolongada de red y batería. No se promete ejecución tras force-stop ni intervalos exactos.

## 6. ML: qué existe y qué falta

**Hoy aporta capacidad técnica real de entrenamiento e inferencia comprobada con sintéticos; no resultados reales evaluados en escolares.** La ruta del producto es `services/backend/ml/school_pipeline.py`. `XGBRegressor`, objetivo `reg:squarederror`, 80 árboles, learning_rate 0.05, selección de profundidad 2/3 con validación. Predice puntos PHQ-9; presenta salida recortada a 0–27 y conserva salida cruda para SHAP. No hay probabilidad calibrada ni XGBClassifier activo en REAL.

El registro admite dataset externo JSON con manifest, days y labels; valida instrumento/versión, unidades, procedencia declarada (`authorized_real` o `test_fixture`), fechas y etiqueta. **No construye automáticamente ese dataset desde Response + Feature + MobilityDay + autorizaciones locales.** Registrar una referencia de autorización de diez caracteres no verifica por sí solo los documentos ni la procedencia de cada etiqueta. No se entrenará automáticamente solo por dejar celulares captando: hace falta implementar esa unión/exportación controlada, reunir respuestas y ventanas suficientes y aprobar el protocolo.

### Artefactos trazables

REAL: directorio de artefactos sin modelo registrado y conteos de base en cero. No hay nombre, fecha de entrenamiento ni hash de un modelo clínico/local que se pueda informar honestamente.

DEMO: dos carpetas (`8916d980-c266-4f75-a3da-84cc745e88f1` y `4052c83c-11e1-4cbe-a9b4-e3485b15bc4f`) bajo `.runtime/artifacts/DEMO`, ambas con `XGBoost-DEMO.ubj`, SHA-256 `c3c0e757fa013a56667faec45363a4803cb602593ba603d8d9acbf6f3c86191f`. Sus cards declaran CHECKIN_DEMO_V1, seed 20260906, 11 participantes sintéticos elegibles, 423 etiquetas y 3 participantes de test/predicción. No son PHQ reales. Sus fechas de archivo no se convierten en fechas acreditadas de recogida escolar.

Auditoría: se ejecutó `test_preserve_synthetic_training_artifact` y se conservó `.runtime/auditoria-20260907/synthetic-training/{dataset.json,model.json,evidence.json}`. Son seis identidades ficticias, 720 días generados y 36 etiquetas artificiales, tarea prospectiva PHQ-9 compatible por contrato; manifest incluye fecha UTC de entrenamiento y hash del modelo. Se verificó suma SHAP con tolerancia 0.001 y la suite original impide activar fixtures. Entrenamiento conservado: 2026-09-08T15:26:10.997052+00:00; SHA-256 del modelo `6de4c965f7d6dcc3d1e48cfb215276a6b2caccc46e780826757aa9643b4e3769`. Sus métricas demuestran ejecución, no rendimiento útil. El anexo generado `artifact-inventory.json` conserva hashes/fechas de los artefactos inspeccionados.

### Columnas y ventanas

| Variable base | Unidad; piso para escala | Fuente/cálculo |
|---|---|---|
| interactive_minutes | min; 15 | Unión de intervalos de pantalla interactiva dentro de ventanas válidas |
| night_interactive_minutes | min; 15 | Intersección nocturna 22:00–06:00 según zona |
| interactive_session_count | eventos; 5 | Sesiones reconstruidas, no tiempo por app |
| keyguard_hidden_count | eventos; 5 | Eventos de desbloqueo, distintos de foreground |
| observed_distance_m | m; 200 | Suma geodésica de segmentos observados válidos |
| radius_gyration_m | m; 100 | Dispersión de puntos válidos observados |
| home_minutes | min; 30 | Tiempo observado respecto de zona voluntaria; ausencia GPS no significa casa |
| place_entropy | nats; 0.1 | Entropía de lugares agrupados, no medida de sociabilidad |
| observed_steps | pasos; 100 | Diferencias del contador por segmento/arranque; descarta unión de reinicios |

Por cada variable declarada se generan exactamente cinco columnas con sufijos `_current`, `_baseline`, `_delta`, `_robust_deviation`, `_available`. Son hasta 45 columnas; el manifest fija el subconjunto efectivo. El fixture conservado usa únicamente observed_steps y sus cinco columnas. No hay identificador personal ni respuestas del cuestionario objetivo como predictor.

Current = mediana de siete días anteriores al corte; baseline = mediana de los 28 días anteriores a current, sin superposición. Delta = current − baseline. Desviación = delta / max(piso, 1.4826·MAD). Se exigen 5 días actuales y 14 basales elegibles por variable; faltantes se representan como null/NaN más indicador 0, no como bienestar. XGBoost usa missing; Ridge ajusta imputación solo con train. No hay un estimador alternativo calibrado para cada combinación de sensores; manejar NaN no acredita equivalencia de rendimiento.

`mobility.day_summary` restringe precisión ≤100m, antigüedad ≤10min, brecha ≤30min, velocidad ≤200km/h; radio casa 150m, DBSCAN 200m/3 muestras, mínimo observado 120min para calidad de movilidad. Las pruebas cubren puntos imprecisos/aproximados, medianoche, brechas, pausa, reinicio y falta de sensor. Estos parámetros son decisiones técnicas, no umbrales clínicos.

### Tiempo y evaluación

Ejemplo: respuesta el 29 de agosto de 2026 sobre 15–29 de agosto. En `concurrent`, corte al 29: la ventana 22–28 se superpone al recuerdo, por lo que estima síntomas contemporáneos. En `prospective`, corte al 15: ventana 8–14 y baseline anterior, para estimar el período 15–29; deben excluirse registros que aún no estaban disponibles al 15. Usar sensores anteriores al envío no basta para llamar prospectivo al primer caso.

El código exige fechas con zona, disponibilidad/cierre ≤corte, etiquetas sin recuerdo superpuesto por persona, una ventana por etiqueta; no aplica SMOTE. Divide personas aproximadamente 60/20/20, selecciona profundidad con validación y evalúa test con constante, último cuestionario disponible, Ridge y XGBoost; ablación «levels_only» conserva current/baseline/available. Reporta MAE/RMSE e intervalo bootstrap por persona. No debe informar sensibilidad o probabilidad calibrada como si estuvieran medidas; prevalencia, cobertura local y comparación clínica están pendientes.

Hay comprobación temporal con embargo de 14 días, pero entrena **otro** `temporal_model` con profundidad 2 y datos tempranos, mientras el artefacto guardado es `model`. Su resultado no certifica automáticamente el artefacto desplegado (A06). Además, el corte diario UTC de `worker.school.maintenance` precede al cierre del día en Lima y a agregados calculados a las 08:00; puede excluir el último día local (A07). La comprobación de formato no relaciona de manera completa `day` con el cierre declarado por un importador: esa coherencia merece endurecimiento y prueba adversaria antes de afirmar ausencia de fuga universal.

Jobs asíncronos, registry, hash, estado registrado/sombra/activo/retirado y decisiones de sustitución existen. Inferencia deduplica modelo/persona/fecha y añade motivo independiente en activo; no elimina cuestionario o solicitud. La activación verifica procedencia/particiones/estado temporal declarados, pero no acredita revisión externa ni legitimidad de cada etiqueta importada. Faltan evaluación real, controles de elegibilidad A08 y aceptación de rollback en operación desplegada.

## 7. Hallazgos y correcciones propuestas

**A01 — Alta; bloquea uso real. Lectura de predicciones individuales por permiso técnico.** `app/model_api.py:permission,predictions` permite admin/researcher con scope models; devuelve `public(Prediction)` por institución sin aplicar autorización de investigación individual ni asignación clínica. Reproducción: `test_admin_models_reads_unconsented_individual_prediction` crea una predicción ficticia para perfil no test y research_access=false; perfil clínico devuelve 403, predicciones 200 con participante/score. Corregir aplicando controles por objeto/finalidad y minimizando datos del registry. Añadir regresión para investigador, admin, responsable y otra institución.

**A02 — Alta; bloquea uso real. GPS vencido conservado al caducar autorización.** `worker/school.py:maintenance` ejecuta continue antes de borrar SensorPoint si autorización.ready=false; omite también dispositivos revocados en ese bucle. Reproducción `test_retention_skipped_when_document_changes`: punto ficticio de 30 días permanece al cambiar document_version; al restaurar autorización válida el control sí lo elimina. Separar limpieza de retención de elegibilidad para captar/procesar, incluir todos los estados y coordinar con borrado/backup.

**A03 — Alta; bloquea recorrido de escalamiento.** El suplente configurado recibe una notificación de escalamiento, pero `school_core.access` exige asignación clínica que la configuración de suplente no concede. `test_backup_notified_but_cannot_read_profile`: notificación presente y perfil 404. Diseñar acceso acotado y auditable al caso escalado, o asignación explícita que la configuración valide. No abrir todos los perfiles al suplente para solucionar un caso.

**A04 — Alta; bloquea entrega fiable con desconexión larga.** `LocalStore.kt:PacketDao.expire` ejecuta DELETE por edad sin filtrar estado/tipo; `SchoolCollector.sensor/sync` llama a siete días. Afecta school_form y school_support pendientes además de sensores. `test_native_expiry_deletes_pending_questionnaire` ejecuta el SQL exacto en SQLite aislado y demuestra eliminación de formulario pendiente antiguo. No es una reproducción de siete días en hardware. Separar retención cruda de entrega, conservar o resolver explícitamente pendientes, mostrar expiración y nunca confundirla con recepción.

**A05 — Alta; bloquea evaluación local. Dataset local no construido.** Importación/entrenamiento existen; falta recorrido de selección autorizada y unión de respuestas versionadas con días/ventanas disponibles, dataset inmutable y procedencia por etiqueta. Evidencia: `model_api.import_dataset` y `school_pipeline.windows/train_real`; no hay constructor correspondiente desde Response. Implementar exportador/constructor con exclusiones, fechas, consentimiento de investigación, hashes y informe de elegibilidad. Separar este trabajo de software de conseguir participantes, permisos y etiquetas reales.

**A06 — Alta para afirmaciones predictivas. Evaluación temporal no vinculada al artefacto final.** Evidencia estática `school_pipeline.train_real`: temporal_model.fit/predict versus model.save_model. Registrar cada modelo evaluado con hash y período o evaluar prospectivamente el artefacto congelado. No interpretar temporal.status=completed como rendimiento temporal medido del binario activado. Añadir prueba que vincule hash/evaluación/activación. No se atribuye explotación ni mala fe al importador.

**A07 — Media; afecta actualidad del análisis. Corte UTC desalineado con agregación local.** `worker.school.maintenance` y `model_api.queue_inference` fijan medianoche UTC. Ejemplo 8 de septiembre: corte 00:00Z es 7 de septiembre 19:00 Lima; el día 7 termina a las 05:00Z del 8 y se agrega más tarde. `infer_registered` excluye cierres/creaciones posteriores. Verificación estática de la secuencia; pendiente prueba de integración que fije reloj/cola. Definir corte local, fecha efectiva y watermark de disponibilidad; procesar dependencias antes de inferir y exponer retrasos.

**A08 — Alta; elegibilidad de inferencia insuficientemente protegida.** `infer_registered` filtra institución y correspondencia is_test/provenance, pero no comprueba autorización vigente, research_access, estado de participación ni piloto en ese bucle. Con histórico y modelo disponibles podría persistir nuevas estimaciones fuera del alcance autorizado. Hallazgo de código, no ejecución sobre población real: no había modelo REAL. Definir finalidad clínica/investigación y sus permisos, comprobarlos antes de cada inferencia y probar revocación, renovación y piloto deshabilitado.

**A09 — Dependencias y producto parcial.** Historial/corrección de cuestionarios del alumno, transporte de correo y reentrenamiento periódico desde capturas locales no completados; FCM no verificado externamente; consumo y tolerancia OEM no medidos. PB US-08/10/13/17/23/24 no se pueden dar por plenamente satisfechas. Resolver software pendiente y luego ensayar configuración real con cuentas de prueba.

**A10 — Operación no acreditada.** Entorno actual local HTTP; no demuestra TLS público, cifrado de discos/backup en hosting, monitorización ni disponibilidad. SQLCipher del teléfono no prueba cifrado PostgreSQL en reposo. Backup/restauración aislados pasaron; faltan RPO/RTO medidos en destino, secretos/rotación, firma release, plan de actualización y prueba de pérdida/restauración. La rama sin commits impide referenciar una versión por commit: crear una línea base revisada después de resolver hallazgos, fuera de esta auditoría.

## 8. Documentación y aceptación pendientes

Autores: actualizar TI/resumen/OE para distinguir objetivo científico de resultados medidos; no usar «biomarcadores completamente justificados» o prevención de falsos positivos como conclusión de una revisión. Mantener OE2 de diseño separado de OE3 implementación y OE4 evaluación; documentar cuáles tienen evidencia. Actualizar PB US-12/15/18 para regresión, prioridad y cadencia; US-13/17/24 para alcance real y criterios de aceptación. En IB conservar 4.70 como decisión ponderada y añadir resultados de experimentos cuando existan.

ACP/arquitectura: documentar React, Kotlin, SQLCipher, jobs en DB, registro ML y modalidad de despliegue realmente elegida. Aclarar contradicción de llamadas y exclusiones, y fechas del proyecto (10 meses/2026 frente a calendario 2026-2/2027-1). En Metodología registrar MAD, ventanas 7/28, niveles actuales, ausencia de sueño/comunicación, instrumento, target, corte y evaluación por persona/tiempo. No cambiar los originales automáticamente.

Psicólogo/equipo: elegir instrumento para población y propósito, horario, recursos verificados, umbrales de revisión, atención a q9 y suplencia efectiva. Autores/datos: protocolo de recogida, autorizaciones, diccionario y etiquetas trazables. Desarrollo: A01–A08 y pendientes de producto. Configuración externa: HTTPS, infraestructura, FCM y recuperación. Ninguna de estas decisiones queda tomada por una propuesta del asistente.

Aceptación física pendiente: instalar una versión identificada en teléfono de prueba; probar autorización renovada, negación/permiso aproximado/preciso y revocación desde ajustes; registrar secuencia conocida pantalla/bloqueo/pasos/GPS; verificar outbox→acuse→agregado; cruzar medianoche y reinicio; ensayar red intermitente, ahorro de batería, cierre y force-stop; medir consumo, bytes/día y latencia con duración/denominador. Registrar resultados por modelo Android; no simular éxito. Repetir ruta suplente y restauración con datos ficticios después de corregir.

## 9. Respuestas directas

1. **¿Está todo?** No. Existe recorrido principal, pero faltan resolver cuatro fallos reproducidos, puente de dataset local, controles/evaluación de inferencia, partes de historial/correo y aceptación física/operativa.
2. **¿Qué cambió?** PHQ-9 en vez de PHQ-A/KADS, regresión en vez de bajo/medio/alto, MAD 7/28 en vez de z-scores/ventanas múltiples, niveles además de desviaciones, motivos separados, sin sueño/comunicación medidos. El complemento justifica cambios de producto; los documentos necesitan ratificación y actualización.
3. **¿Qué datos recoge hoy cada teléfono?** Puede captar eventos de pantalla, ubicación autorizada y contador de pasos disponible. No se verificó aquí que cada teléfono esté captando; los agregados del servidor acreditan recepción limitada, no cobertura continua. Sin permisos/hardware/conexión, la disponibilidad varía.
4. **¿Qué ve el psicólogo?** Cola y perfiles asignados, series/calidad, cuestionarios y seguimiento. Alertas por solicitud, respuesta o regla conductual; ML únicamente con versión activa. Hoy REAL no tiene predicciones registradas.
5. **¿Qué modelo se ejecuta?** La ruta productiva ejecuta XGBRegressor cuando hay modelo registrado habilitado. No lo hay en REAL. Existen artefactos DEMO y un modelo sintético conservado de auditoría; ninguno es rendimiento escolar medido.
6. **¿Qué se probó y qué se supone?** Backend, PostgreSQL/migración/restauración, UI web, Flutter con dobles, cálculos por fixtures y entrenamiento/SHAP pasaron. Captura OEM sostenida, batería, entrega externa y rendimiento predictivo local no fueron verificados.
7. **¿Siguiente corrección más importante?** Antes de nuevas pruebas con información sensible, cerrar A01 y A02; para completar el recorrido corregir A03/A04. Para evaluar ML, el siguiente desarrollo imprescindible es A05 junto con A06/A07/A08 y un dataset real autorizado. Desplegar por sí solo no resuelve estas brechas.
