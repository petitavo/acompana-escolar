# Probar el APK Android con un servidor LAB en Azure

Este despliegue aloja el panel, API, worker y PostgreSQL en una VM Ubuntu 24.04 dedicada. No sube la base DEMO ni entrena modelos sintéticos en LAB. El APK existente acepta la URL HTTPS del servidor; no necesita recompilarse para cambiar de servidor.

## Estado de preparación

Configuración en `infra/azure/`, script `scripts/azure_lab.py`. El 2026-09-06 Azure aceptó la validación previa de `Standard_B2als_v2` en México Central y Canadá Central. Se seleccionó México Central por costo y ubicación. East US 2 rechazó B2als_v2 y B2s, y South Central US rechazó B2als_v2 por `SkuNotAvailable`. Existe el grupo vacío `rg-acompana-escolar-lab`; todavía no se desplegó ningún servidor. Se registraron los proveedores Microsoft.Compute y Microsoft.Network.

Un despliegue exitoso guarda su URL en `.runtime/azure/deployment.json` y comprueba `/api/v1/health` con certificado válido y `mode=LAB`. Una validación previa no reserva capacidad ni sustituye la prueba física del teléfono.

## Recursos y costo estimado

- Una VM `Standard_B2als_v2`, 2 CPU y 4 GiB; Ubuntu con Docker Compose y 2 GiB de swap.
- Disco Standard SSD de 32 GiB; volúmenes persistentes para PostgreSQL, artefactos y certificados.
- IPv4 Standard estática y nombre DNS `acompana-lab-….mexicocentral.cloudapp.azure.com`.
- HTTPS automático de Caddy, puertos públicos 80/443; SSH solo desde la IPv4 del administrador y con clave propia. Base de datos y API sin puertos públicos directos.
- Grupo independiente `rg-acompana-escolar-lab`; nunca se utiliza el grupo de SMCBackend.

Consulta de la [API oficial de precios](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) del 2026-09-06, USD sin impuestos ni descuentos: VM Linux en México Central US$0.0414/h (US$30.22 por 730 horas), IPv4 Standard US$0.005/h y disco E4 US$2.64/mes. Subtotal US$36.51; reservar aproximadamente US$37/mes más operaciones/montaje de disco y tráfico. La propuesta inicial de East US 2 costaba unos US$34/mes, pero allí Azure rechazó el tamaño. No es un límite de gasto ni una promesa de gratuidad. Los créditos elegibles se descuentan según las condiciones de la suscripción. Verificar SKU, región y cuota antes de crear.

`stop` ejecuta **deallocate**: deja de cobrar el cómputo, pero persisten disco e IP (aproximadamente US$6/mes más otros cargos aplicables). Apagar dentro de Ubuntu no equivale necesariamente a liberar cómputo. La aplicación queda inaccesible mientras esté detenida; el teléfono mantiene su cola local. No hay apagado programado ni límite de gasto automatizado. Eliminar recursos detiene sus cargos futuros pero exige respaldar los datos y una decisión explícita; este script no elimina nada.

## Preparar y desplegar

Desde la raíz del proyecto, usar Python del proyecto y Azure CLI autenticada. En este equipo se instaló CLI 2.90.0 de forma aislada en `.tooling/azure-cli/`; en otro equipo el script usa `az` del PATH o `ACOMPANA_AZ`.

```bash
.tooling/azure-cli/bin/az account list --output table
# Si falta sesión, autenticación interactiva en Microsoft; no compartir contraseña/token:
.tooling/azure-cli/bin/az login --use-device-code

.venv/bin/python scripts/azure_lab.py plan --subscription ID_SUSCRIPCION --location mexicocentral
# Validar con Azure; prepara el grupo vacío, sin servidores ni discos:
.venv/bin/python scripts/azure_lab.py validate --subscription ID_SUSCRIPCION --location mexicocentral
# Este comando sí crea recursos con costo:
.venv/bin/python scripts/azure_lab.py deploy --subscription ID_SUSCRIPCION --location mexicocentral
```

El script obtiene la IPv4 actual del administrador mediante `api.ipify.org`, crea una clave SSH exclusiva, aprovisiona con Bicep, verifica la clave del servidor a través de Azure Run Command, envía únicamente el código permitido, construye contenedores, ejecuta migraciones y crea las cuentas LAB. Los secretos viajan por SSH verificado y se guardan fuera de Git con permisos 0600; nunca en parámetros de Azure ni en el paquete de código. Los servicios reinician después de encender la VM. Si el comando falla tras crear infraestructura, los recursos pueden seguir existiendo y facturando: revisar `status` y el portal. No se destruyen datos para resolver errores.

La configuración inicial local detectó una suscripción Azure for Students que permite `mexicocentral`, `southcentralus`, `canadacentral`, `brazilsouth` y `eastus2`; `eastus` no estaba permitido. Esa política puede cambiar. Una región permitida no garantiza cuota o disponibilidad del tamaño elegido.

## Instalar y probar en Android 10 o superior

1. Copiar `apps/mobile/build/app/outputs/flutter-apk/app-debug.apk` al teléfono por USB y abrirlo; autorizar instalación desde esa fuente. Alternativamente, con depuración USB autorizada: `adb install -r apps/mobile/build/app/outputs/flutter-apk/app-debug.apk`.
2. Abrir Acompaña. En URL introducir el campo `url` de `.runtime/credentials-lab.json`, sin añadir `/api/v1`.
3. Pegar el valor `invitation` en la app Android. No es un nombre de usuario y no debe gastarse en el formulario web. Dura 24 horas y es de un uso.
4. Aceptar participación adulta y conceder acceso de uso. Dejar compartir nombres de aplicaciones desactivado en la primera prueba.
5. Usar otras aplicaciones y bloquear/desbloquear el celular varios minutos. Volver a Acompaña, tocar **Capturar ahora** y **Sincronizar ahora**.
6. Abrir la URL pública en la computadora. Entrar con `investigador.lab` y su contraseña del mismo archivo. Buscar `LAB-001` y comprobar eventos `android_usage_events` con fecha y dispositivo reales.
7. Probar sin internet, reintentar sincronización y verificar ausencia de duplicados. Pausar captura y comprobar que el período pausado no aparece. Registrar modelo, Android y resultados siguiendo `docs/android.md`.

El panel LAB arranca sin historial ficticio: que un gráfico esté vacío al principio es normal. Los resúmenes diarios y el historial personal requieren días elegibles; unos minutos verifican transporte/captura, no calibración longitudinal. Los modelos sintéticos no se habilitan en LAB.

Si la invitación venció o ya se usó, generar otra en la VM (Run Command o SSH). No volver a sembrar ni resetear la base:

```bash
cd /opt/acompana-escolar
sudo docker compose --env-file .runtime/azure-lab.env -f infra/azure/compose.yaml exec api python -m app.cli invite LAB-001
```

## Operación

```bash
.venv/bin/python scripts/azure_lab.py status --subscription ID_SUSCRIPCION
.venv/bin/python scripts/azure_lab.py stop --subscription ID_SUSCRIPCION
.venv/bin/python scripts/azure_lab.py start --subscription ID_SUSCRIPCION
```

Para revisar problemas en la VM: `sudo cloud-init status --long`, `sudo journalctl -u docker`, y desde `/opt/acompana-escolar`, `sudo docker compose --env-file .runtime/azure-lab.env -f infra/azure/compose.yaml logs --tail 100 api worker proxy`. No publicar logs ni archivos con credenciales o registros personales.

Esta primera VM tiene un solo disco y no configura copias de seguridad externas ni alta disponibilidad. Es un laboratorio para adultos, no un despliegue escolar de producción. El APK es debug, distribuido por archivo, sin tienda; no captura en iPhone. Consulte [HTTPS de Caddy](https://caddyserver.com/docs/automatic-https) y [VM Linux con Azure CLI](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/quick-create-cli).
