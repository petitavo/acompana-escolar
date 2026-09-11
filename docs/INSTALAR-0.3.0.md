# Probar Acompaña Escolar 0.3.0 en Android

APK de pruebas: `dist/acompana-escolar-0.3.0-pruebas.apk` (167 056 166 bytes). Es debug, firmada para desarrollo; no está publicada en Play Store ni instala un servidor. Conservar la misma firma permite actualizar sin desinstalar. No desinstale si Android rechaza la actualización por firma distinta: primero hay que resolver la firma y conservar pendientes locales.

SHA-256: `479436074b6809c7afb7d8d864214a867a9d17bf27008a19b6f496a1ccf2cc63`.

## Prueba local por USB

Desde `/home/petitavo/acompana-escolar`, conecte y desbloquee el teléfono, habilite depuración y acepte la clave RSA del equipo. El siguiente arranque aplica las migraciones aditivas al producto local; antes de actualizar una instalación con datos relevantes debe haber un respaldo recuperable. Las pruebas de esta entrega usaron bases distintas, sin migrar la instalación real.

```bash
python3 scripts/product.py start
.tooling/android-sdk/platform-tools/adb devices
.tooling/android-sdk/platform-tools/adb install -r dist/acompana-escolar-0.3.0-pruebas.apk
.tooling/android-sdk/platform-tools/adb reverse tcp:8001 tcp:8001
```

En Android, use como servidor `http://127.0.0.1:8001`. Esa excepción HTTP sólo está permitida en la APK debug y funciona mientras existe la conexión USB y `adb reverse`. Para usarlo sin USB se requiere una dirección HTTPS real accesible desde el teléfono.

Panel profesional: `http://127.0.0.1:5174`. Use la cuenta institucional existente; la cuenta inicial local se documenta en `docs/producto.md` y sus credenciales permanecen en el archivo privado del entorno. No use `invitation` como usuario. El estudiante entra con invitación individual y código; el responsable usa el enlace de responsable con su propio código.

## Recorrido de comprobación

1. En el panel, configure psicólogo, suplente, horario, recursos y decisión profesional del instrumento. Cree una identidad ficticia de prueba.
2. Si es menor, complete primero el recorrido del responsable. En el celular canjee invitación/código, registre participación y seleccione los datos voluntarios.
3. Compruebe los permisos Android por separado: ubicación, actividad física y acceso de uso según la opción elegida. Autorizar participación en el servidor no concede permisos del sistema.
4. Envíe un cuestionario y una solicitud. Revise Mis respuestas y cree una corrección con motivo. El original debe seguir visible; el panel conserva cualquier motivo de seguridad previo.
5. Desconecte la red y envíe otra solicitud: debe quedar pendiente. Al reconectar debe mostrar recepción real o rechazo explicado, nunca recepción simulada. Revise también los avisos de datos de sensores caducados.
6. En el panel del psicólogo, revise caso, reconocimiento, seguimiento y cierre. La cuenta suplente sólo puede atender el caso concedido por escalamiento.
7. En Modelos y evaluación, previsualice la selección local. Sin muestras suficientes el software explica lo que falta; no genera rendimiento clínico ficticio. Los entrenamientos programados nunca se activan automáticamente.

Pendiente de dispositivo físico: captura sostenida, comportamiento con pantalla apagada, reinicio y restricciones de batería del fabricante; no se consideran probados por compilar el APK. La entrega externa SMTP/FCM y HTTPS público también requieren sus credenciales, dominio y comprobación de recepción real.
