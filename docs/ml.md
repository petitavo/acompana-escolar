# Experimento DEMO

`ml/pipeline.py` construye una fila por respuesta completa de CHECKIN_DEMO_V1. Se preservan response_id, feature_start/end, cutoff, período preguntado, target y procedencia. UUID se usan para particiones/linaje, nunca en X. Respuestas contemporáneas, notas y paquetes no entran como predictores. Historial anterior al cutoff únicamente; cuestionario previo es comparador separado.

Partición principal por participante (~60/20/20), con semilla fija. Imputación/normalización se ajustan solo con train. XGBoost evalúa profundidades 2/3 en validación y usa test apartado una vez para comparar. Modelos: constante mediana, último cuestionario disponible, Ridge, XGBoost regularizado y ablación de solo niveles. No se ajusta un modelo por alumno.

MAE, RMSE, error por participante e IC mediante remuestreo de participantes (300 réplicas). Reporta cantidad de personas y etiquetas; test con pocos participantes sigue siendo solo demostración. Evaluación temporal separada con ventanas que no crucen las fronteras y embargo de 7 días; si no queda partición suficiente, se registra insuficiencia.

Salida: `XGBoost-DEMO.ubj`, `model-card.json`, `dataset-manifest.json`. Hash SHA-256, seed, columnas, unidades, versiones y fecha. SHAP TreeExplainer verifica base + contribuciones = predicción con tolerancia 1e-4. Las contribuciones están en puntos del cuestionario, nunca como causas o porcentajes clínicos.

No se auto-promociona un ganador. LAB no ejecuta modelos sintéticos. No se afirma validez clínica, superioridad de XGBoost ni suficiencia de 100 escolares. El entrenamiento demo funciona sin descargar GLOBEM/StudentLife.

El adaptador CSV/Parquet revisa manifest de fuente, autorización, unidades, instrumento/versión, entorno y tarea. Emite compatibilidad de esquema, sin importar automáticamente ni presumir equivalencia de sensores.

**Tareas:** la prospectiva corta antes de empezar el período preguntado. La concurrente agrega minutos/intervalos confirmados dentro del período de la respuesta y su cobertura operacional, usando solo registros/consultas conocidos al cutoff. Puede tener cobertura parcial: se representa explícitamente y no se convierte en observación completa. Los totales/respuestas objetivo nunca forman parte de X.
