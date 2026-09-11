# Protocolo interno y privacidad

Esta entrega se limita a datos ficticios o teléfonos de investigadores/adultos voluntarios. No captar menores. Autorización del director no sustituye consentimiento parental, asentimiento ni revisión institucional del futuro piloto. Este repositorio no implementa ese piloto.

Antes de LAB: designar responsable técnico, describir categorías a recopilar, obtener aceptación adulta y configurar servidor HTTPS de confianza. La app solicita consentimiento antes de captura. El permiso especial de uso se concede en ajustes y es opcional respecto a formularios. El detalle de paquetes es otra opción, desactivada por defecto. La interfaz no muestra puntuación predictiva ni ranking al participante.

Solo existe CHECKIN_DEMO_V1 habilitado: energía, concentración, descanso; tres preguntas inventadas con opciones 0–3, suma 0–9, umbral ≥6 arbitrario. Incompletos no generan total. Solicitud de contacto crea caso independientemente del modelo. Mostrar pendiente hasta acuse servidor, y distinguir aviso creado, reconocido y contacto registrado.

El importador valida definiciones revisadas y una DSL limitada a suma, umbral y reglas por ítem gte/eq. No usa eval. Versiones no se sobreescriben. Instrumentos reales se importan deshabilitados; aun con campos de protocolo cargados, **v1 rechaza habilitarlos** porque su cobertura profesional/escalamiento necesitan una integración específica validada. No se copió PHQ/KADS de memoria.

Pausa local detiene WorkManager, cancela eventos/capturas sin enviar y encola la pausa. Reanudación reinicia el cursor desde el nuevo intervalo; no recupera huecos. Retirada/borrado detiene captura inmediatamente; si hay red, servidor revoca dispositivos antes del job. Sin red, el participante debe volver a sincronizar la petición: el servidor todavía no puede conocerla. Esta limitación es visible en la cola, no se afirma retiro remoto antes del acuse.

Cifrado Android: Room usa realmente SQLCipher, con passphrase aleatoria protegida por AES-GCM y Android Keystore. Configuración sensible/token también cifrados. No se guardan claves privadas en APK. Backups de aplicación desactivados. No hay screenshots, analytics o payloads enviados a terceros.

Retención propuesta del laboratorio: crudo local/servidor 7 días; features/respuestas de prueba 90 días; exports 24h. Son decisiones operativas, no plazos legales. Retención corre con el worker y se omite sobre fixtures DEMO para conservar reproducibilidad. La auditoría mínima conserva actor/acción/UUID, no respuestas. El job de borrado purga datos del participante y elimina conservadoramente exportaciones/modelos derivados. Ledger de UUID borrados queda separado.

Backups: no se crea una promesa automática. Si el operador los configura, cifrarlos, limitar acceso y caducidad (propuesta interna: 7 días). Antes de servir una restauración, reaplicar `deletions.jsonl` de un almacenamiento que no se restaure hacia atrás. Este procedimiento es manual en v1; no está verificado como automatización de restauración. No se promete eliminación instantánea de copias.
