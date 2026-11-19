# Cómo funciona Acompaña Escolar (versión 0.4.4, piloto)

Este documento resume qué hace la aplicación, cómo funciona cada parte y qué hay que hacer para el piloto con unos 30 estudiantes.

## En una frase

Acompaña Escolar es un sistema de software para que el equipo de psicología de un colegio acompañe a sus estudiantes. Junta tres fuentes de información: cuestionarios breves (PHQ-9 y preguntas cortas), una solicitud directa de ayuda y algunos indicadores del uso del celular (pantalla, movimiento, descanso y asistencia). El sistema no diagnostica. Ordena la información y propone revisiones para que un profesional decida.

## Partes del sistema

| Parte | Tecnología | Qué hace |
|---|---|---|
| App del estudiante | Flutter + Kotlin (Android) | Vincula el teléfono, pide permisos, muestra cuestionarios, permite pedir ayuda y calcula los indicadores en el propio teléfono |
| Panel web | React (Vite) | Lo usan administración, dirección y psicología: invitaciones, autorizaciones, casos, perfiles y configuración |
| Backend | FastAPI + PostgreSQL | Guarda todo, aplica las reglas (corte del PHQ-9, pregunta 9, permisos por rol) y expone la API |
| Worker | Python | Tareas en segundo plano: resúmenes diarios, cambios de comportamiento, retiros, avisos |
| Módulo de ML | XGBoost + SHAP | Construye el dataset y entrena un modelo que estima el puntaje del siguiente PHQ-9. Queda inactivo hasta tener datos reales suficientes |

## Flujo del estudiante (app)

1. **Código de acceso.** El colegio crea al estudiante en el panel y le entrega un código de 8 caracteres (por ejemplo `ABCD-2345`). El estudiante instala la app y escribe solo ese código: el servidor ya va fijo dentro del APK. El código sirve una sola vez, vence en 7 días y el servidor limita los intentos fallidos.
2. **Autorización.** Si es menor de edad, el apoderado autoriza primero desde su propio enlace. Luego el estudiante lee el documento de participación y marca qué quiere compartir: uso de pantalla, ubicación, pasos y recordatorios. Todo es opcional.
3. **Permisos en un botón.** Al aceptar, el alumno vuelve a Inicio y el paso 2 queda marcado. "Activar permisos" abre una sola pantalla con la lista (uso de pantalla, avisos, ubicación, pasos, batería y, al final, ubicación siempre e inicio automático en las marcas que lo necesitan) y un botón que:
   - guarda de una vez lo que se comparte (un solo viaje al servidor, así las ventanas de Android salen al instante);
   - pide seguidas las ventanas de Android;
   - antes de lo que se hace en Ajustes (ubicación siempre, inicio automático) dice en una línea qué tocar, y al volver sigue solo.

   Lo que el alumno rechaza no se vuelve a pedir solo. Si Android ya no muestra la ventana, la fila dice "Bloqueado" y al tocarla abre Ajustes. Siempre hay "Ahora no".

   **Ya no se pide "Acceso al uso".** Android 13+ lo bloquea en apps instaladas fuera de Play Store ("configuración restringida") y en algunos Samsung ni siquiera aparece la opción para desbloquearlo. Ahora el uso de pantalla se mide con los avisos de encendido/apagado de la pantalla que escucha el servicio de la app (fuente `android_screen_broadcast`). Si el teléfono tuviera "Acceso al uso" concedido, se sigue usando el historial de Android (`android_usage_events`).

4. **Inicio.** Una cabecera de color con el nombre del alumno y "Tu camino": tres pasos numerados (aceptar participar, preparar el teléfono, responder el cuestionario). El paso que toca ahora se marca con "Ahora" y tiene su botón. Debajo están "Quiero que me contacten" y el horario del equipo. Los avisos (verde = listo, ámbar = falta algo o no hay conexión, rojo = no se pudo) quedan fijos arriba y se cierran con una X.
5. **Cuestionarios.** El PHQ-9 aparece cada 14 días o más (según configure el colegio). Si el equipo los activa, también aparecen:
   - el PHQ-2 (preguntas 1 y 2 del PHQ-9), solo en la semana intermedia entre dos PHQ-9, para no repetir preguntas recién respondidas,
   - una pregunta diaria de contacto social,
   - tres preguntas mensuales de entorno (acoso, apoyo de los padres, amigos), adaptadas de la GSHS.

   Mientras el PHQ-9 esté pendiente se muestra solo, para no encadenar cuestionarios. Si el estudiante marca algo distinto de "Ningún día" en la pregunta 9, la app le muestra en ese momento a quién llamar, con un botón "Llamar" que abre el marcador.
6. **Sin internet.** Todo se guarda cifrado en el teléfono y se envía después. La pestaña Solicitudes muestra el estado de cada envío.
7. **Pausar o retirarse.** En Participación se puede pausar la captura, cambiar lo que se comparte o retirarse; al retirarse se borran sus datos.

## Qué se calcula en el teléfono y qué no

- **Pantalla:** cuántas veces y cuánto tiempo se enciende, y el uso nocturno. No se sabe qué apps se usan. Se mide solo mientras el servicio de la app está activo (necesita que el alumno comparta ubicación o pasos); el tiempo en que Android cerró la app queda como no cubierto, no como cero.
- **Descanso (nuevo, `sleep-proxy-v1.0`):** el periodo más largo sin usar el teléfono entre las 20:00 y las 12:00. Los usos de menos de 2 minutos, como mirar la hora, no lo cortan. Si no hubo uso antes o después, o el permiso no estuvo activo, el dato queda como parcial y no entra al análisis. **No mide sueño real**; es una aproximación conocida en la literatura (StudentLife).
- **Movilidad:** distancia, radio de movimiento, tiempo en la zona habitual y diversidad de lugares. Se calcula en el teléfono; al servidor solo llegan resúmenes diarios.
- **Asistencia (nuevo, `mobility-v1.1`):** minutos dentro del círculo del colegio en horario de clases. El colegio define el centro, el radio, el horario y los días en el panel. Solo se envían los minutos, nunca las coordenadas. Si se observó menos de la mitad del horario, el dato no es elegible.
- **Pasos:** si el teléfono tiene sensor y el estudiante lo permite.
- **Nunca:** micrófono, voz, texto, contenido de mensajes ni lista de apps.

## Panel web (psicología y administración)

- **Administración:** crea aulas, cuentas y estudiantes; entrega invitaciones (ahora con enlace y un botón para copiar el mensaje para el estudiante); configura responsables, horario de atención y recursos de ayuda.
- **Configuración, sección 5 "Piloto" (nueva):** activa el PHQ-2 semanal, la pregunta diaria y las preguntas de entorno; define la zona del colegio y el horario de clases; decide si los cambios de comportamiento abren casos (por defecto no, solo se muestran como información).
- **Casos:** se abren por cuatro motivos, ordenados por prioridad:
  1. respuesta distinta de cero en la pregunta 9 (revisión de seguridad, siempre);
  2. el estudiante pidió contacto;
  3. PHQ-9 de **11 o más** (corte para adolescentes, Richardson et al., 2010);
  4. estimación del modelo, solo si hay un modelo autorizado y activo.
- **Perfil del estudiante:**
  - historial de PHQ-9, con el PHQ-2 guardado aparte;
  - preguntas breves;
  - tendencias de uso nocturno, descanso estimado, movilidad y asistencia, con la calidad de cada día.

  Los días sin datos se muestran vacíos, no como cero.
- **Seguimientos, notas y citas** dentro de cada caso.

## Backend

- La API está en `/api/v1/school/...`. Cada rol solo ve lo suyo (por ejemplo, un psicólogo ve sus casos y los del suplente cuando corresponde).
- El PHQ-9 queda guardado con su versión (`AETC-2016-es-2`), el total, el PHQ-2 y el corte usado.
- Las preguntas breves van a la tabla nueva `school_checkins` (migración `c3d4e5f6a7b8`) y **nunca** abren casos.
- El worker arma los resúmenes diarios (`screen-v1.1` con descanso) y borra los datos al retirarse un estudiante.

## Módulo de ML

- Variables por ventana de 14 días:
  - promedio, variabilidad y desviación personal de cada indicador (pantalla, descanso, movilidad, asistencia y pasos);
  - **el puntaje del PHQ-9 anterior y los días transcurridos desde ese cuestionario** (nuevo).
- La validación agrupa por persona: LeaveOneGroupOut con hasta 40 estudiantes y GroupKFold(5) con más. Así el modelo nunca se evalúa con alguien que vio al entrenar.
- Se compara siempre contra dos referencias simples:
  - "repetir el último cuestionario";
  - "predecir la media".

  Se reportan sensibilidad, especificidad y AUC en el corte de 11. Si el modelo no supera al último cuestionario, eso se reporta tal cual.
- El modelo sintético no se activa. Con 30 estudiantes el resultado esperable es exploratorio; el aporte principal del piloto es el software y la calidad de los datos.

## Checklist del piloto

1. Compilar el APK en una PC con Android SDK:
   ```
   cd apps/mobile
   flutter build apk --release --dart-define=API_URL=https://SU-SERVIDOR
   ```
   Con `API_URL` compilado, el estudiante solo escribe su código. Firmar siempre con la misma clave (carpeta `firma`, fuera del repo) para poder instalar actualizaciones encima.
2. Desplegar el backend y aplicar las migraciones (`alembic upgrade head`).
3. En el panel, Configuración:
   - responsables y suplente;
   - horario de atención;
   - recursos de ayuda;
   - sección 5 del piloto (zona del colegio y preguntas breves).
4. Probar en al menos un Xiaomi/Redmi, un Samsung y un Motorola. En cada uno, pasar la guía completa, dejar el teléfono una noche y revisar al día siguiente que aparezcan pantalla, descanso y movilidad en el perfil.
5. Crear a los estudiantes y entregar a cada uno su código de acceso en privado.

## Limitaciones conocidas

- El código Kotlin (permisos, batería, inicio automático, asistencia) no se pudo compilar en el entorno donde se hicieron estos cambios. Debe compilarse y probarse en teléfonos reales antes del piloto.
- Algunas marcas (sobre todo Xiaomi, Huawei y vivo) pueden cerrar la app aunque se sigan todos los pasos. Por eso la cobertura de cada día se muestra siempre.
- El descanso es una aproximación por uso del teléfono, no una medición de sueño.
- El PHQ-9 usa el texto validado AETC 2016 para adultos (trata de "usted" y menciona trabajo y tareas del hogar). No se modificó para no romper la validez del instrumento; si el equipo prefiere una versión para adolescentes (PHQ-A en español), debe decidirse con el asesor y registrarse como versión nueva.
