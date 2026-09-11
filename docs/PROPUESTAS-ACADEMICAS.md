# Propuestas de alineación académica — 9 de septiembre de 2026

Documento separado: no modifica los originales de los autores ni representa aprobación profesional.

| Tema | Software implementado | Propuesta para los autores / decisión pendiente |
|---|---|---|
| Instrumento | PHQ-9 versionado, nueve ítems, recuerdo de 14 días; funcionamiento separado del total | El psicólogo debe confirmar pertinencia, población, texto y protocolo de aplicación antes de habilitar un piloto. No sustituir por otro instrumento sin versionar respuestas y modelos. |
| Objetivo predictivo | Regresión del total PHQ-9 en puntos 0–27; tareas concurrente y prospectiva separadas | Describir predicción de una puntuación autoinformada, no diagnóstico. No convertirla en categorías bajo/medio/alto sin protocolo y validación adicionales. |
| Desviación personal | Ventana actual de 7 días frente a 28 días anteriores; medianas, MAD y suelo por variable; exige al menos 5 y 14 días válidos respectivamente | Explicar los criterios como decisiones de ingeniería sujetas a validación, no puntos de corte clínicos establecidos. |
| Sensores | Uso de pantalla, pasos y movilidad según disponibilidad, permisos y elección del estudiante | Declarar faltantes y calidad; no inferir que activar una casilla prueba captura. GPS aproximado, ausencia de hardware y restricciones del fabricante cambian la cobertura. |
| Cadencia | Cuestionarios de 14 días sin solapar períodos; correcciones conservan fecha y período originales | Confirmar la cadencia y seguimiento con el responsable. La fecha de corrección no crea una observación longitudinal nueva. |
| Arquitectura | Android con cola local protegida; API, PostgreSQL, worker, panel profesional y registro de datasets/modelos | Separar consentimiento, permiso Android, calidad observada, estimación y actuación profesional en el documento metodológico. |
| Evaluación | Separación por participante, comparadores y métricas del artefacto exacto; prueba temporal con su propio hash | No atribuir al modelo final las métricas del modelo temporal. Definir tamaño muestral y validación externa con asesoría metodológica. |
| Correcciones | Respuesta original conservada; nueva revisión, dataset fuente invalidado y modelos dependientes retirados | Definir ventanas de corrección y revisión profesional. Un cambio posterior nunca elimina automáticamente un motivo de seguridad. |
| Finalidad | Autorización clínica vigente; investigación exige permiso adicional de investigación | Confirmar responsables, base de autorización, retención y acceso para cada finalidad. La autorización de investigación no sustituye la de atención. |

Los fixtures sirven para probar código, no para estimar rendimiento en escolares. El mínimo técnico de seis participantes y dieciocho ventanas elegibles sólo permite ejecutar las particiones de prueba; no establece suficiencia estadística ni clínica. Faltan datos reales autorizados, suficientes por participante y período, y una evaluación prospectiva supervisada.

La referencia predictiva Mindcraft es el artículo de 2026 e72501. El artículo e44877 de 2023 corresponde a aceptabilidad. La distinción y fuente están en [ACLARACION-MINDCRAFT.md](ACLARACION-MINDCRAFT.md); ninguno demuestra el rendimiento de Acompaña Escolar.
