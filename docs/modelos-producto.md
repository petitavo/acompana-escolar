# Análisis y modelos del producto

Hay dos capas independientes: cambios de cada participante frente a su propia línea base y modelos entrenados/importados mediante datasets autorizados. Ninguna cifra se presenta como diagnóstico al estudiante.

## Señales y calidad

Pantalla y movilidad conservan unidades, ventanas y procedencia. Movilidad `mobility-v1.0` usa Haversine (radio terrestre 6371008.8 m), excluye precisión >100 m y edad >10 min, no une brechas >30 min ni segmentos separados por pausa y excluye saltos >200 km/h. Divide tramos en medianoche civil. Radio usa centro esférico y ponderación temporal; descanso voluntario usa radio 150 m, transiciones inciertas; diversidad usa DBSCAN geodésico 200 m/mínimo 3 y entropía temporal con observación mínima de 120 min. Pasos usan incrementos no negativos del mismo arranque, sin unir pausas ni cruzar días. Ausencia es null; elegibilidad diaria requiere cobertura suficiente, no se inventa un día completo.

Las fórmulas coinciden en Python y Kotlin mediante siete fixtures compartidos, incluidos antimeridiano, medianoche, baja calidad, resets y pausas. Los resúmenes recibidos tarde reactivan procesamiento. Los cambios estadísticos generan evidencia para revisión; el sistema escolar no cierra automáticamente un caso por recuperación del sensor.

## Dataset y ejecución

El panel de modelos, protegido por permiso `models`, permite importar dataset con manifiesto, entrenar, comparar, registrar versiones, importar artefacto JSON, ejecutar, colocar en sombra, activar con decisión profesional y volver a la versión previa. Los crudos/exportaciones tienen permisos distintos. No se carga pickle.

El contrato exige variables diarias, etiquetas compatibles con PHQ-9, timestamps con zona, disponibilidad anterior al corte y procedencia/autorización documentada. No acepta coordenadas como variables del modelo. Las ventanas usan 28 días previos de baseline y 7 actuales, mínimos 14/5 días, mediana/MAD con pisos por unidad. El corte prospectivo precede la ventana de recuerdo de 14 días de la etiqueta. Se separan participantes entre entrenamiento, validación y prueba; la selección usa validación. Se comparan constante, último valor, Ridge, XGBoost y ablación de niveles; se reportan MAE/RMSE e intervalos bootstrap y evaluación temporal con embargo cuando hay datos suficientes.

Entrenamiento requiere al menos seis personas y dieciocho etiquetas; ese mínimo permite ejecutar el software, no demuestra suficiencia científica. La activación exige evaluación temporal completada, particiones disjuntas, procedencia real y decisión del responsable. Fixtures solo prueban contratos y no pueden activarse como modelo real. Sombra no cambia la prioridad de casos reales. Predicciones conservan versión/checksum y contribuciones SHAP reproducibles en unidades del puntaje, con el recorte de rango separado.

**No se encontró un dataset real autorizado en el repositorio y no se entrenó ni validó clínicamente un modelo real.** Quedan pendientes el dataset compatible, su documentación de autorización y representatividad, evaluación profesional y decisión de uso. El producto mantiene cuestionarios, apoyo, cambios personales y seguimiento disponibles sin modelo.

## Instrumento y referencias

PHQ-9 español AETC 2016, versión interna AETC-2016-es-1. Texto archivado en `docs/instrumentos`, con PDF y SHA-256 verificado: `1041559d940ba6dd5c03132e8922dcc537b750051594322b68c8fe265a79e90c`. Nueve respuestas 0–3, total 0–27; dificultad funcional aparte. Cadencia 14 días; regla del ítem 9 independiente del total. La institución configura responsables, cobertura y recursos antes de activarlo.

- [PDF fuente AETC](https://aidsetc.org/sites/default/files/resources_files/PHQ-9_Spanish.pdf).
- [Información de uso del PHQ-9, AIMS Center](https://aims.uw.edu/resource/phq-9-depression-scale/).
- [Android: tipos de servicio foreground](https://developer.android.com/develop/background-work/services/fgs/service-types).
- [Fused LocationRequest](https://developers.google.com/android/reference/com/google/android/gms/location/LocationRequest.Builder).
- [Firebase HTTP v1](https://firebase.google.com/docs/cloud-messaging/send/v1-api).


## Circuito local y versiones 0.3.0

El panel construye snapshots desde respuestas, features, movilidad y autorizaciones locales. Permite previsualizar exclusiones y programar construcción/reentrenamiento sin promoción automática. Un JSON manual sigue siendo una opción de importación. La construcción clínica real requiere al psicólogo responsable; la finalidad de investigación requiere además permisos y autorización individual. Las predicciones personales no quedan abiertas a quien administra modelos.

Los hashes vinculan cada evaluación al modelo y dataset exactos. El ensayo temporal tiene un artefacto distinto. Las correcciones versionadas de respuestas retiran modelos que utilizaron etiquetas afectadas, conservando sus métricas como evidencia histórica. Consulte [CONTRATO-DATOS-0.3.0.md](CONTRATO-DATOS-0.3.0.md) para cortes locales, disponibilidad y criterios de aceptación.
