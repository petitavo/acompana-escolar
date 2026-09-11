# Recorrido de 15 minutos

1. **0–3 min:** `make demo`. Abrir la URL indicada, leer `.runtime/credentials-demo.json` (en Compose, consultar dentro de api). Ingresar como `psicologo.demo`. Confirmar banner sintético y cola priorizada.
2. **3–6 min:** abrir DEMO-003: ver solicitud de contacto, formulario de prueba y cambio persistente separados. Revisar gráfico nocturno y contexto de exámenes. Reconocer, añadir nota ficticia, planificar contacto o cerrar con motivo. Recargar y comprobar persistencia.
3. **6–9 min:** cerrar sesión e ingresar como `investigador.demo`. Ver dispositivos con permiso perdido, outbox y pocos datos. Explorar eventos y JSON permitido. Abrir Variables y trazabilidad → Ver origen → intervalos/eventos/descarte.
4. **9–12 min:** abrir otra pestaña en `/participant`. Usar invitación de la semilla o crear otra con `app.cli invite DEMO-001`. Aceptar prueba adulta ficticia, completar las tres preguntas con Mal y enviar. Solicitar contacto. Volver al psicólogo y revisar el nuevo motivo sin depender del modelo. El formulario web no simula captura del teléfono.
5. **12–14 min:** Experimentos → ejecutar DEMO prospectivo. Esperar al worker, comparar constante/último cuestionario/Ridge/XGBoost/ablación. Revisar participantes apartados, evaluación temporal y SHAP en puntos.
6. **14–15 min:** crear una exportación de features para el período sintético; esperar estado completado, descargar con sesión, comprobar filas/procedencia/caducidad. Registrar por separado comentarios de claridad/usabilidad de la prueba.

Revisar tres casos ficticios y registrar tiempo de tarea y claridad/utilidad no mide exactitud clínica. La API `/psych/usability-feedback` guarda esos comentarios en un tipo de job separado, sin mezclarlos con questionnaires. La UI ofrece el formulario en Historial.

La semilla tiene reloj simulado fijo hasta 2026-09-05 (noche cerrada la mañana siguiente). `--end` cambia ese reloj de manera reproducible junto con la seed. LAB no permite este generador ni reemplaza semanas de calibración con datos sintéticos.
