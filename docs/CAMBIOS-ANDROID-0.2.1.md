# Android 0.2.1 — participación, permisos y segundo plano

Actualización preparada el 7 de septiembre de 2026. El teléfono está desconectado: esta APK se entrega para la siguiente prueba y no se ha instalado en él. El acceso e identidad del paquete se conservan al actualizar con la misma firma; no hay que crear otra invitación ni repetir autorizaciones ya recibidas.

## Qué se corrigió

- Fechas del servidor: `SchoolTime` acepta UTC con `+00:00`, `Z` y otros offsets con fracciones. El fallo `DateTimeParseException` se reprodujo en Android 11 y la corrección inicial permitió ver los permisos en el Moto G9 Plus antes de desconectarlo. Esta versión incorpora la corrección también para recordatorios y pruebas de equivalencia temporal.
- Participación: el estado de autorización se carga independientemente del cuestionario/historial. Una respuesta fallida de estos módulos ya no oculta una aceptación válida. Después de aceptar se muestra la confirmación y la pantalla se desplaza a los permisos.
- Permisos: se espera el resultado del diálogo Android, se distinguen concedido/denegado/ajustes necesarios y se actualiza su estado. La denegación permite continuar con cuestionarios y solicitudes. Cambiar preferencias sin guardarlas no concede permisos ni habilita nuevos sensores.
- Captura: el estado de servicio encendido procede del proceso actual, no de un indicador persistido que podría sobrevivir al cierre. Inicios repetidos no registran listeners duplicados; callbacks posteriores a la detención no reinician el proveedor. Se informa de errores de arranque sin afirmar recepción de muestras.
- Pausa: guardar preferencias mientras está pausado no reanuda la participación. La parada local se conserva incluso si la petición está pendiente o se rechaza; reanudar requiere confirmación. Desactivar subida de coordenadas cancela paquetes de ubicación aún pendientes.
- Sin conexión: el worker intenta guardar uso autorizado antes de sincronizar. Un error de registro de push no impide enviar apoyo/cuestionarios. Una sesión revocada detiene sensores y no reactiva captura desde una copia antigua de la configuración.

## Investigación aplicada

Los permisos se solicitan a partir de una acción del usuario y se comprueba su respuesta, conservando funciones que no los necesitan. [Guía oficial de permisos Android](https://developer.android.com/training/permissions/requesting).

Android 11 y posteriores gestionan el permiso de ubicación de fondo desde ajustes; se explica cómo abrirlos. No se fuerza su concesión. [Ubicación en segundo plano](https://developer.android.com/develop/sensors-and-location/location/permissions/background).

El servicio se inicia desde la app visible y puede continuar al minimizarla, con notificación y pausa. No se inicia silenciosamente después de reiniciar o forzar cierre; WorkManager se usa para captura de uso/sincronización periódica, sin prometer intervalos exactos de GPS. [Restricciones de servicios foreground](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start).

## Verificación

- Flutter: análisis estático sin incidencias; ocho pruebas, incluidas aceptación confirmada con permisos visibles, actualización parcial fallida, responsable pendiente y permiso denegado sin arranque automático.
- Kotlin/JVM: cinco pruebas, incluidas equivalencia de fechas de la API, zona obligatoria, límites de captura y siete fixtures compartidos de movilidad.
- Backend: catorce pruebas de producto, incluida pausa → cambio de preferencias → sigue pausado → reanudación explícita.
- APK debug compilada, versión 0.2.1, versionCode 3; firma y checksum registrados al empaquetar.
- [Captura de interfaz](evidencias/producto/flutter-permisos-0.2.1.png): render Flutter de prueba; no es una captura física del teléfono.

Los logs se conservan en `docs/evidencias/producto/verificacion-0.2.1.txt`. La ejecución de permisos y sensores en un teléfono desconectado no se declara probada.

## Próxima prueba física

1. Reconectar el Android y actualizar con `.runtime/entrega/acompana-escolar-0.2.1-debug.apk` mediante `adb install -r`. Mantener la firma y los datos; no desinstalar para resolver un conflicto.
2. Restablecer `adb reverse tcp:8001 tcp:8001` y, para enlaces del portal en el teléfono, `adb reverse tcp:5174 tcp:5174`. La aplicación local usa `http://127.0.0.1:8001`; al desconectar USB no alcanza ese servidor, aunque conserva la cola local.
3. Abrir Participación: una aceptación ya recibida debe mostrar «Tu participación ya está aceptada». Conceder o denegar cada permiso elegido y comprobar el resultado visible.
4. Iniciar sensores con la app abierta; verificar notificación, primer dato real y sincronización. Minimizar, caminar, pausar y comprobar que no hay muestras del período pausado. El servicio encendido por sí solo no demuestra que llegó una muestra.
5. Probar desconexión/reconexión, ajustes durante la pausa, reinicio y cierre forzado. En estos últimos, comprobar estado detenido y arranque explícito al reabrir. Validar recepción real en diagnóstico sin publicar coordenadas.

La APK está preparada para esa comprobación. No hay publicación Azure, habilitación de piloto real ni modelo clínicamente validado por estos cambios.

SHA-256 de la APK: `369aba8bd8a6d3b5757a87d72822e3f14241b64684ee450e76e90d931d07d81e`.
