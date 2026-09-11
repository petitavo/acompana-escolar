# Android 0.3.1 (5): permisos y cuestionario

Un solo botón «Permitir» guarda la elección y abre la solicitud de Android. Cada opción indica Concedido, Pendiente o No activado; los sensores no compatibles se identifican sin botón. Al regresar desde ajustes se actualiza el estado. Los permisos de uso, segundo plano o denegados permanentemente requieren la pantalla de ajustes que Android permita abrir.

La captura autorizada de ubicación/pasos se inicia automáticamente desde la app visible; incorporar un permiso actualiza el servicio existente. Una participación pausada conserva su pausa. Pausar/Reanudar queda visible y el documento, preferencias adicionales y retiro quedan en un bloque plegable. La aceptación informada sigue visible antes de participar.

El cuestionario se consulta al abrir la app, al volver a ella, al entrar en su pestaña y cada 45 segundos mientras permanece activa. Se quitó la entrada duplicada en Inicio. La interfaz distingue carga, ausencia de pendientes y fallo de conexión.

## Verificación

15 pruebas Flutter aprobadas (incluyen permiso denegado, activación de un toque, preferencias sin conexión, participación pausada, incorporación de pasos y regreso desde ajustes). Flutter analyze sin incidencias. Compilación Android completada y 5 pruebas Kotlin aprobadas. Firma APK verificada. Evidencias en `docs/evidencias/mobile-0.3.1`.

No hubo teléfono conectado: falta comprobar los diálogos específicos del fabricante y la captura física en segundo plano. Las pruebas de interfaz usan un puente nativo simulado; la compilación y las pruebas Kotlin no sustituyen ese ensayo.

El APK de pruebas lleva prellenada la dirección del servidor Azure. Se instala como actualización sobre 0.3.0, sin desinstalar ni borrar datos.

APK: `dist/acompana-escolar-0.3.1-pruebas.apk` (167206490 bytes). SHA-256: `0a4054b40c95c7cd99aa46c902927fa2a8257b355db073753b45292bf6ac64bf`. Se comprobó que conserva el certificado de firma de 0.3.0.

Publicado y verificado por HTTPS el 2026-09-10T14:49:51.569242+00:00: [0.3.1](https://acompana-product-zrzcsjpld7gfm.mexicocentral.cloudapp.azure.com/downloads/acompana-escolar-0.3.1.apk). Descarga HTTP 200, petición parcial 206 y SHA-256 remoto idéntico al local.
