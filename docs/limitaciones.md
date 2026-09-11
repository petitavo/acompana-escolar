# Alcance comprobable y backlog

## Entrega implementada

Circuito demo persistente, auth con roles/asignaciones, captura Kotlin y cola cifrada, formularios con borrador/outbox, casos/notas/transiciones, reconstrucción diaria, calidad y referencia robusta, worker con leases, experimento DEMO/comparadores/SHAP, exportaciones autenticadas, retención/borrado y contratos. APK debug compilable. Consulte VALIDACION para distinguir código, tests y hardware.

## Límites técnicos explícitos

- Sin teléfono físico conectado/verificado: permiso real, eventos por fabricante, cifrado durante ejecución, WorkManager tras cierre, falta de red y pausa deben verificarse siguiendo `android.md`.
- Docker/Compose no instalado en esta máquina: archivos de despliegue disponibles; el arranque de contenedores no se declara probado. PostgreSQL nativo, si se probó, figura separado en VALIDACION.
- La evidencia del permiso es muestreada antes/después de consultas. No garantiza continuidad absoluta entre consultas ni captura completa de Android. No interpretar cobertura operacional como comportamiento observado al 100%.
- v1 procesa referencia por dispositivo; no combina varios teléfonos de una persona. La app no usa sensores iOS.
- `app_foreground_minutes` opcional pendiente. GPS, pasos, movilidad, sueño, Firebase y producción con menores fuera de v1.
- Instrumentos reales se importan deshabilitados. El protocolo profesional debe implementarse/verificarse específicamente antes de habilitación. El demo no sustituye una escala revisada.
- Notificaciones y escalamiento son internos/simulados. La plantilla de FCM futura no envía mensajes. No hay garantía de atención de emergencia.
- Backup/restauración y reaplicación del ledger de borrados son procedimientos documentados, todavía manuales. No existe prueba automatizada de restauración de backups.
- Firma de release pendiente. El APK entregado es debug, para laboratorio adulto.
- Exportación: elimina conservadoramente todos los modelos/exports del entorno ante borrado de una persona. Política segura pero poco selectiva; mejorar linaje de artefactos para invalidación específica.
- Muchos nombres de tablas propuestos se consolidaron en JSON/entidades de eventos/jobs. Ver diccionario. No se inventa normalización inexistente.
- Las pruebas disponibles son una base de ingeniería, no auditoría exhaustiva de seguridad, validación clínica ni validación educativa longitudinal.

## Próximos pasos

1. Ejecutar y registrar la guía en dos fabricantes Android; probar bloqueo, reinicio, force-stop, revocación durante consulta, días sin datos y cambio de zona.
2. Validar Compose/PostgreSQL y HTTPS LAN en entorno del laboratorio, con restauración/borrados y rotación de claves.
3. Mejorar evidencia de continuidad de permisos, diagnóstico del reloj, retención configurable por protocolo y sincronización de grandes colas con restricciones de batería.
4. Ampliar trazabilidad: exportar linaje congelado, comparar revisiones y verificar consentimiento/pausa ante datos atrasados del teléfono.
5. Protocolo profesional e instrumentos revisados: permisos, texto exacto, reglas por ítem, cobertura, reconocimiento/escalamiento; evaluación separada de ML.
6. Evaluación académica de funcionalidad/usabilidad y estudios posteriores de datos reales autorizados. No promover métricas sintéticas a resultados clínicos.
