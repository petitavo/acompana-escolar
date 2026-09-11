# Variables, calidad y trazabilidad v1

`services/backend/app/features.py` es la única implementación. El móvil no calcula cambios ni puntuaciones. Las transformaciones y experimentos reutilizan este módulo.

Eventos se ordenan por instante/UUID. SCREEN_INTERACTIVE abre un intervalo; SCREEN_NON_INTERACTIVE lo cierra. Repeticiones del mismo estado no suman duración. DEVICE_STARTUP/SHUTDOWN invalidan extremos abiertos. Falta de pareja o brecha sin consultas exitosas produce un descarte, nunca se extiende hasta “ahora”. Los intervalos se unen antes de sumar y se recortan contra la ventana local. No se hace clipping silencioso a 24 horas: los extremos locales admiten días de 23/25 horas por DST.

- `interactive_minutes`: minutos confirmados en el día local.
- `night_interactive_minutes`: noche D = D 22:00 a D+1 06:00, solo cerrada tras acabar.
- `interactive_session_count`: intervalos confirmados iniciados en el día, no “desbloqueos”.
- `keyguard_hidden_count`: eventos de bloqueo ocultado, con capacidad independiente.

`app_foreground_minutes` es opcional en la especificación y queda pendiente; sí se pueden capturar eventos de actividad y paquetes autorizados para diagnóstico. No se suman como pantalla. GPS, pasos, movilidad y sueño no están implementados.

Valor y estado están separados: `observed`, `partial`, `missing`, `unsupported`. Las duraciones parciales solo suman pares confirmados y exponen descartes; cero con una cola abierta **no** significa ausencia de uso. `missing`/`unsupported` producen null. Cero con ventana consultada y sin eventos puede ser observado.

Cobertura operacional = unión de consultas exitosas con permiso antes/después / duración objetivo. No garantiza completitud de Android. Los snapshots muestrean autorización; no prueban que el permiso permaneció continuo entre consultas. La implementación solo declara elegible si ≥80% de cobertura, ventana cerrada, sin pérdida conocida de permiso ni brechas/incompletos que afecten la reconstrucción. **Limitación:** los snapshots por consulta son evidencia muestreada, no una prueba de permiso continuo. Hasta validar esta incertidumbre en hardware, use los cambios LAB como experimentales, no como observación exhaustiva.

Referencia: 28 días antes de los últimos 7 completos. Mínimos 14/5 días elegibles por variable. Mediana actual menos mediana de referencia = delta. MAD = mediana de distancias absolutas a la mediana. Desviación = delta / max(1.4826 × MAD, piso). Pisos: 15 min y 5 eventos. No tienen sentido clínico. Porcentaje solo si referencia >0.

Candidato: |desviación|≥3. Tres evaluaciones diarias consecutivas generan motivo `behavior_change`. Son ventanas superpuestas, no pruebas independientes. Solo se resuelve automáticamente el motivo conductual tras tres evaluaciones completas bajo 2 en todas las variables. Faltantes no son recuperación; un caso en seguimiento humano no se cierra automáticamente.

Los snapshots de evaluación son inmutables. Reprocesar crea registros nuevos y versión explícita. La vista de linaje enlaza intervalos, UUID usados/descartados y consultas; si expiró el crudo se indica que no es completamente reproducible. La semilla usa un calendario simulado anclado en `--end`; solo DEMO permite datos sintéticos futuros respecto al reloj físico.

El worker LAB programa el cierre después de las 08:00 locales para incluir la noche terminada. Un reproceso manual puede mostrar ventana abierta como no disponible. La calibración LAB necesita días reales; no se rellena con fixtures.
