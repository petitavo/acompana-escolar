# Verificación ejecutada

Fecha: 2026-09-06 UTC. Código en `/home/petitavo/acompana-escolar`, independiente de SMCBackend.

## Preparación adicional de Azure LAB

- Suite actual SQLite: **20 pruebas aprobadas**, incluidas dos de aprovisionamiento LAB (reintento sin duplicados ni rotación de claves, sin consentimiento implícito y rechazo de DEMO/participante retirado). Las 18 pruebas PostgreSQL de la tabla inferior corresponden a la ejecución anterior, sin estos dos tests nuevos.
- Bicep compilado; Docker Compose 2.39.4 validó `infra/azure/compose.yaml`; `bash -n` aprobó `infra/azure/install.sh`.
- Paquete de despliegue inspeccionado: 55 archivos, con `.dockerignore`, sin contraseñas, bases locales ni `node_modules`.
- Azure for Students: sesión comprobada, proveedores Compute/Network registrados y grupo independiente vacío creado. Azure validó B2als_v2 en México Central y Canadá Central; rechazó B2als_v2/B2s en East US 2 y B2als_v2 en South Central US por disponibilidad.
- **Aún no desplegado:** inventario del grupo vacío, sin VM, discos ni IP. Falta ejecutar `deploy`, construir/iniciar contenedores, verificar HTTPS público y probar el APK con un Android físico. No se ejecutaron contenedores localmente.
- Propuesta seleccionada: México Central, B2als_v2, costo base aproximado US$36.51 por 730 horas (VM + IPv4 + disco), más operaciones/montaje/tráfico. No es un tope de facturación. Ver `docs/azure-lab.md`.

## Verificación inicial del MVP

| Comprobación | Resultado real |
|---|---|
| API/dominio/ML con SQLite temporal | 18 pruebas aprobadas |
| Mismas invariantes con PostgreSQL nativo 18.6 | 18 pruebas aprobadas |
| Alembic sobre base PostgreSQL nueva | Migración inicial aplicada e init correcto |
| Build React/TypeScript/Vite | Correcto |
| Playwright, Chrome instalado | 3 recorridos aprobados: psicólogo, investigador y formulario → caso |
| Responsive web 390×844 | Inspección y captura; sin desborde horizontal del documento |
| Flutter 3.35.7 analyze | Sin incidencias |
| Flutter test | 1 prueba de interfaz aprobada |
| Kotlin/JVM testDebugUnitTest | 2 pruebas aprobadas, 0 fallos |
| Flutter build apk --debug | APK generado, 177,544,850 bytes |
| API → job → worker → entrenamiento → SHAP | Ejecutado, model card guardada |
| Exportación vía API y descarga autenticada | Ejecutada y descargada correctamente |
| make reset-demo y make demo sin Docker | Ejecutados, demo local iniciada |
| adb devices -l | Sin dispositivos conectados |
| Docker Compose | No ejecutado: Docker no está instalado |
| Teléfono físico / sensores reales | No probado; guía y código disponibles |

APK SHA-256: `ca75c9e64e75309b71d9331a4c5a2e81339299c528f9f367bda0a0560acb725b`.

El APK compila con SDK 36/JDK 17 e incluye el puente Kotlin, Room/SQLCipher y WorkManager. Esto no prueba que la captura, cifrado en ejecución o segundo plano funcionen en un fabricante concreto. La comprobación física sigue pendiente.

PostgreSQL se ejecutó en un cluster efímero exclusivo de pruebas en localhost:55432, con contraseña aleatoria. Se detuvo al terminar. La prueba nativa usa 18.6; Compose fija 16.10 y todavía requiere ejecución en Docker. No se han modificado instalaciones o bases PostgreSQL ajenas.

Las pruebas cubren RBAC/IDOR, cookies/CSRF, idempotencia, separación DEMO/LAB, pausa/revocación, esquema/payload, máquina de estados, medianas/MAD y ventanas sin solapamiento, snapshots inmutables, conservación de motivos humanos, reglas de cuestionario por ítem, exportación/expiración/borrado, recuperación de leases, particiones por participante y suma aditiva SHAP.

La prueba Playwright usa una cuenta de prueba y deja notas/transiciones ficticias. Puede repetirse: prepara un caso del participante DEMO-001. No se accedió a perfiles personales del navegador.

Advertencias no bloqueantes observadas: deprecación interna de AnyIO/Starlette TestClient; chunk web de aproximadamente 590 kB sin comprimir; advertencias de compatibilidad futura de Gradle 9. La versión fijada de Gradle 8.12 compiló y ejecutó las pruebas. No se presentan como errores resueltos ni como resultados clínicos.

## Evidencias

- [Cola del psicólogo](evidencias/cola-psicologo.png)
- [Caso y decisiones persistidas](evidencias/detalle-caso.png)
- [Vista móvil web](evidencias/web-movil.png)
- [Experimento DEMO](evidencias/experimentos.png)
- [Formulario del participante](evidencias/formulario.png)
- [Resultados PostgreSQL](evidencias/pytest-postgres.txt)
- [Análisis Flutter](evidencias/flutter-analyze.txt)
- [Compilación APK](evidencias/apk-build.txt)
- [Model card generada](model-card-demo.json)

Los datos de capturas, cuestionarios, imágenes e informes son exclusivamente ficticios. No se probó ni afirmó detección de depresión, precisión clínica o utilidad en menores.
