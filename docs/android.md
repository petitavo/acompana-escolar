# Captura Android y prueba física

Flutter 3.35.7, Android minSdk 29, compile/target 36, Kotlin 2.1.0, AGP 8.9.1, Gradle 8.12, WorkManager 2.10.3, Room 2.7.2, SQLCipher 4.10.0, OkHttp 4.12.0. Consultar manifiestos/lockfiles para versiones exactas resueltas.

`MainActivity` ofrece MethodChannel; `Collector` ejecuta consultas, red y coordinación en un executor nativo. `CollectionWorker` funciona sin Flutter abierto, sujeto a restricciones de Android. No hay temporizador Dart de captura. El trabajo periódico es best effort de 15 min y reintento exponencial; ahorro de batería y force-stop pueden retrasarlo.

Consulta incremental con 60 s de solapamiento, nunca antes de consentimiento/reanudación, con máximo 24 h por consulta. Si una ausencia supera 24 h, se pierde ese tramo en vez de inventar cobertura. Si falta permiso, avanza cursor y registra consulta fallida para no recuperar el período sin permiso al concederlo después.

Huella SHA-256 de dispositivo, milisegundo, tipo y paquete **solo si autorizado**. UUID derivado persistente y índice único de huella. Eventos idénticos al milisegundo se coalescen; pueden existir colisiones semánticas de Android (dos eventos realmente distintos indistinguibles). La deduplicación no prueba identidad humana ni número de aperturas.

Capturas y eventos se guardan en una transacción Room. Confirmados quedan como registro local hasta retención; la selección outbox usa estado pending. Lotes máximo 500, acuse accepted/duplicates, rechazos definitivos separados de fallos de red. Una respuesta perdida se reenvía con el mismo UUID/cuerpo. Consultas técnicas fallidas se sincronizan aunque el acceso de uso esté ausente; eventos requieren permiso comprobado nuevamente.

La cola de formularios y contacto usa el mismo almacenamiento cifrado y UUID idempotente. Borrador local cifrado. Los controles de participación van antes que datos en sincronización. En DEMO la app no captura datos Android; solo formularios. En LAB, la procedencia real se etiqueta `android_usage_events`.

## Pasos con teléfono adulto

1. Ejecutar perfil LAB PostgreSQL y configurar HTTPS con certificado confiable. Con la CLI crear `LAB-001`, invitación y asignación al psicólogo.
2. Instalar APK debug: `adb install -r apps/mobile/build/app/outputs/flutter-apk/app-debug.apk`.
3. Abrir app, introducir URL HTTPS accesible desde el teléfono e invitación. No usar `localhost` del portátil: en el móvil refiere al móvil.
4. Aceptar consentimiento adulto; dejar detalle de aplicaciones desactivado inicialmente.
5. Abrir ajustes de acceso de uso y concederlo a Acompaña. Volver y verificar estado; esto todavía no prueba captura.
6. Usar otras apps y alternar pantalla/bloqueo durante varios minutos. Volver, Capturar ahora, Sincronizar ahora.
7. En panel investigador buscar dispositivo, ver consulta con permiso y eventos reales con hora/origen. Anotar fabricante, modelo, API, zona, hora, conteo y UUID de ejemplo.
8. Desconectar internet, capturar, observar outbox. Reconectar y sincronizar varias veces; no duplicar eventos.
9. Pausar, usar teléfono, reanudar; comprobar que el hueco no se captura. Revocar acceso en ajustes durante/entre consultas y comprobar diagnóstico.
10. Enviar formulario y solicitud de contacto; revisar caso desde psicólogo. Retirarse y verificar revocación/borrado.

Release prohíbe cleartext. Debug permite HTTP solamente a 10.0.2.2, localhost y 127.0.0.1 para emulador; para un teléfono físico también exige HTTPS. Debug confía en certificados de usuario para la CA del laboratorio; release solo confía en el almacén de sistema. Nunca desactivar TLS ni usar un trust manager permisivo.

**Estado:** APK compilado y tests de Flutter/JVM indicados en `VALIDACION.md`. No hay teléfono físico verificado; no se asegura captura de un fabricante concreto, funcionamiento en segundo plano, cifrado en dispositivo o recuperación tras apagado hasta ejecutar esta guía. No hay captura iOS ni servicio Accessibility.
