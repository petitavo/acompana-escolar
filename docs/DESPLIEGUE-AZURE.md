# Despliegue Azure del producto

Instalación independiente en Azure for Students, grupo `rg-acompana-escolar-product`, máquina `acompana-product`, región `mexicocentral`, tamaño `Standard_B2als_v2`, 2 vCPU y 4 GiB de RAM, disco Standard SSD de 32 GiB. No utiliza el grupo `smcgroup` ni los datos del producto local.

URL verificada: https://acompana-product-zrzcsjpld7gfm.mexicocentral.cloudapp.azure.com
APK actual (0.3.1): https://acompana-product-zrzcsjpld7gfm.mexicocentral.cloudapp.azure.com/downloads/acompana-escolar-0.3.1.apk

El estado verificado se guarda en `.runtime/azure-product/verification.json`. No confundir la existencia del servidor con la verificación de HTTP, TLS o acceso de cuenta; esas comprobaciones se registran por separado.

## Cuenta y celular

La cuenta inicial es `admin.local`. Su contraseña exclusiva de Azure se conserva en `.runtime/azure-product/credentials-product.json` con permisos 0600. No es la contraseña del entorno local. La institución todavía requiere configuración; no se migran estudiantes, invitaciones ni autorizaciones.

En Android se introduce la URL pública como servidor, sin `/api` ni `/student`. Las cuentas de estudiantes usan invitación y código, no el usuario del administrador. El responsable de un menor recibe otro enlace y código. El APK publicado es de pruebas, no una versión firmada para tienda.

Se despliega `APP_MODE=REAL`, con `PILOT_ENABLED=false`: permite identidades de prueba, no habilita por sí solo participación real de escolares. SMTP y FCM permanecen apagados hasta disponer de credenciales, configuración y autorización institucional. No hay un modelo clínicamente validado.

## Operación

Fuentes: `infra/azure-product` y `scripts/azure_product.py`. La identidad del host SSH se obtiene mediante Azure Run Command y se compara con clave fijada en `known_hosts`; no se desactiva la verificación SSH ni TLS. Sólo HTTP/HTTPS se abren al público, SSH queda limitado a la IP administradora. PostgreSQL y API no publican puertos de host.

Las claves SSH, entorno y credenciales no van dentro del paquete de código ni del APK. No se copió la base local. Nginx omite registros de URL para no conservar tokens de invitación en logs de acceso. Los contenedores tienen reinicio automático y límites de rotación de logs; el proxy solicita y renueva TLS público.

El servidor consume créditos mientras está asignado. Para detener el cómputo conservando datos, desde el proyecto:

```bash
.tooling/azure-cli/bin/az vm deallocate --subscription c212df7f-36a7-45eb-ab77-ff2386f76d63 --resource-group rg-acompana-escolar-product --name acompana-product
```

El disco y la IP siguen siendo recursos facturables. Para volver a encenderlo, sustituya `deallocate` por `start`. No elimine el grupo ni volúmenes para detener una prueba.

Antes de un piloto real quedan: operación de backups externos y ensayo de recuperación sobre este host, monitorización de disponibilidad, configuración de canales, decisiones profesionales y validación física de captura/batería en el teléfono. Los ensayos locales previos no sustituyen estas comprobaciones del entorno desplegado.


## Resultado comprobado

HTTPS público válido, web HTTP 200, API en modo REAL versión 0.3.0, inicio de sesión de administrador HTTP 200 y descarga APK HTTP 200. El hash SHA-256 del APK alojado coincide con el archivo entregado localmente. Verificación: 2026-09-10T04:35:42Z. Docker dejó API, base, web y proxy en ejecución; el worker está en ejecución, sin afirmar que la mera presencia del proceso demuestre procesamiento de una cola real.

## Actualización Android 0.3.1

Permisos simplificados y cuestionario automático. Descarga y hash verificados en `docs/evidencias/mobile-0.3.1/published.json`; cambios y pruebas en `docs/CAMBIOS-ANDROID-0.3.1.md`. El servidor conserva API 0.3.0. El APK anterior sigue disponible. El acceso SSH del administrador se ajustó a su nueva IP /32, conservando la autenticación por clave y la verificación del host.
