# Pendientes priorizados — auditoría del 8 de septiembre de 2026

Son propuestas; esta auditoría no modificó la aplicación. Los IDs enlazan conceptualmente con `AUDITORIA_INTEGRAL.md` y con las reproducciones aisladas de `.runtime/auditoria-20260907/test_audit.py`. Prioridad indica orden de trabajo, no una clasificación clínica.

| Orden | Hallazgo y responsable probable | Cambio concreto | Criterio verificable de cierre |
|---|---|---|---|
| 1 | A01 · Desarrollo | Aplicar autorización por participante y finalidad a predicciones; separar administración del modelo y lectura de salud | Admin/researcher sin autorización no obtiene score, referencia ni ID identificable; profesional asignado sí; pruebas de objeto/institución |
| 2 | A02 · Desarrollo | Ejecutar retención de GPS independientemente de autorización/captura y estado del dispositivo | Datos vencidos se eliminan también con versión caducada, pausa y revocación; datos vigentes permanecen; retirada y restauración conservan exclusiones |
| 3 | A03 · Desarrollo + psicólogo | Definir suplencia con acceso acotado al caso escalado, plazo y auditoría | Suplente notificado puede abrir, reconocer y dar seguimiento al caso; no accede a alumnos ajenos; no queda escalamiento sin responsable |
| 4 | A04 · Desarrollo | Separar limpieza de sensores de pendientes de formulario/apoyo y tratar caducidad explícitamente | Pendiente de más de siete días no desaparece como si se hubiera enviado; reconexión entrega una vez o informa rechazo recuperable; sin duplicados |
| 5 | A08 · Desarrollo + responsables del protocolo | Aplicar elegibilidad de análisis según autorización vigente, finalidad, participación y piloto | No crea predicciones tras retirada o sin permiso aplicable; pruebas con modelo e histórico ficticios; reanudación respeta nueva autorización |
| 6 | A05 · Desarrollo + autores/datos | Construir dataset desde respuestas versionadas y agregados autorizados con cortes disponibles | Exportación reproducible, hash, manifest, exclusiones por calidad/permiso, trazabilidad de cada etiqueta a respuesta; cero fixtures en dataset real |
| 7 | A06/A07 · Desarrollo + autores | Vincular evaluación al artefacto y corregir corte Lima/dependencias de agregación | Hash evaluado coincide con versión activable; prueba de reloj y medianoche; ningún futuro entra, día cerrado disponible aparece; se informa retraso |
| 8 | A05/A06 · Autores + psicólogo | Aprobar instrumento, objetivo concurrente/prospectivo, cohorte y evaluación antes de recoger dataset | Protocolo versionado, autorizaciones, fechas/ventanas, particiones por persona/tiempo, comparadores, métricas e incertidumbre predefinidos |
| 9 | A09 · Desarrollo + autores | Completar/decidir historial y corrección de cuestionarios, correo y reentrenamiento periódico | Backlog ratificado; corrección conserva original y auditoría; transporte probado solo con destinatarios de prueba; jobs repetidos no duplican |
| 10 | A09 · Desarrollo + equipo de pruebas | Aceptación Android física y medición de recursos | Registro por versión/modelo de permisos, reinicio, segundo plano, red, medianoche, pasos y GPS conocidos; batería/bytes/latencia con duración y denominador |
| 11 | A10 · Configuración externa + desarrollo | Preparar despliegue HTTPS, secretos, firma, respaldos cifrados y observabilidad | Recorrido remoto con cuentas controladas; restauración ensayada y RPO/RTO; entrega FCM diferenciada; versión de aplicación identificable |
| 12 | Diferencias documentales · Autores | Actualizar TI/OE, PB, IB, ACP y Metodología sin convertir propuestas técnicas en acuerdos clínicos | Revisión/ratificación del equipo; 4.70 se describe como benchmark ponderado; resultados propios separados de literatura y objetivos |

## Dependencias que no son trabajo resuelto por código

No basta importar un archivo cualquiera como «autorizado». Los autores deben obtener datos compatibles, consentimiento y etiquetas con instrumento/fecha; el psicólogo debe definir finalidad, revisión y cobertura. No existe todavía un dataset local escolar utilizable registrado. El mínimo de seis personas y 18 etiquetas del software es una barrera técnica, no cálculo de potencia ni garantía científica.

FCM, HTTPS, infraestructura y firmas requieren configuración en el destino. Tener créditos de Azure no acredita despliegue. La aceptación del apoderado y asentimiento existen, pero no sustituyen permisos Android ni decisiones del protocolo institucional.

## Secuencia de aceptación

1. Reproducir A01–A04 en base aislada; después de corregir, invertir las aserciones que hoy confirman fallos y ejecutar las regresiones existentes.
2. Repetir incorporación → PHQ → caso → suplente → contacto → cierre y pendientes sin red en dispositivos de prueba.
3. Validar constructor de dataset y contrato temporal con fixtures adversarios; congelar artefacto/particiones/evaluación.
4. Ejecutar recogida y evaluación autorizadas según protocolo; informar resultados aunque XGBoost no supere la constante o el último cuestionario.
5. Pasar aceptación remota y recuperación con cuentas controladas antes de decidir operación escolar. Registrar por separado la aprobación funcional, predictiva y operativa.

No restaurar automáticamente bajo/medio/alto ni inventar sueño o comunicación para aparentar conformidad. No activar el modelo sintético conservado por la auditoría.
