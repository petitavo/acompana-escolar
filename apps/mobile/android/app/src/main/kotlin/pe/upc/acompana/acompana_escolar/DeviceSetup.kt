package pe.upc.acompana.acompana_escolar

import android.Manifest
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import org.json.JSONObject

/**
 * Ajustes del fabricante que deciden si Android deja trabajar la app en segundo plano.
 * Xiaomi, Huawei, Oppo, Vivo y Samsung cierran apps "dormidas" aunque tengan permisos;
 * por eso la guía de permisos incluye batería e inicio automático.
 */
object DeviceSetup {
    /** Pantallas conocidas de "inicio automático" por fabricante. Se prueba cada una en orden. */
    private val autostart = listOf(
        "com.miui.securitycenter" to "com.miui.permcenter.autostart.AutoStartManagementActivity",
        "com.huawei.systemmanager" to "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity",
        "com.huawei.systemmanager" to "com.huawei.systemmanager.optimize.process.ProtectActivity",
        "com.hihonor.systemmanager" to "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity",
        "com.coloros.safecenter" to "com.coloros.safecenter.permission.startup.StartupAppListActivity",
        "com.coloros.safecenter" to "com.coloros.safecenter.startupapp.StartupAppListActivity",
        "com.oplus.safecenter" to "com.oplus.safecenter.permission.startup.StartupAppListActivity",
        "com.vivo.permissionmanager" to "com.vivo.permissionmanager.activity.BgStartUpManagerActivity",
        "com.iqoo.secure" to "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager",
        "com.asus.mobilemanager" to "com.asus.mobilemanager.autostart.AutoStartActivity",
    )

    fun batteryUnrestricted(context: Context): Boolean =
        (context.getSystemService(Context.POWER_SERVICE) as PowerManager).isIgnoringBatteryOptimizations(context.packageName)

    private fun autostartIntent(context: Context): Intent? = autostart.asSequence()
        .map { Intent().setComponent(ComponentName(it.first, it.second)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }
        .firstOrNull { context.packageManager.resolveActivity(it, PackageManager.MATCH_DEFAULT_ONLY) != null }

    fun info(context: Context): JSONObject = JSONObject()
        .put("manufacturer", Build.MANUFACTURER.lowercase())
        .put("brand", Build.BRAND.lowercase())
        .put("model", Build.MODEL)
        .put("sdk", Build.VERSION.SDK_INT)
        .put("battery_unrestricted", batteryUnrestricted(context))
        .put("autostart_screen", autostartIntent(context) != null)
        .put("autostart_confirmed", Vault(context).get("setup_autostart") == "true")

    /** Pide quitar la optimización de batería; si el fabricante bloquea el diálogo, abre la lista. */
    fun openBattery(context: Context): String {
        if (batteryUnrestricted(context)) return "granted"
        val pkg = Uri.parse("package:" + context.packageName)
        val tries = listOf(
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, pkg),
            Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS),
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, pkg),
        )
        for (intent in tries) {
            try { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return "settings_opened" } catch (_: Exception) {}
        }
        return "unavailable"
    }

    fun openAutostart(context: Context): String {
        val intent = autostartIntent(context) ?: Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + context.packageName)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try { context.startActivity(intent); "settings_opened" } catch (_: Exception) {
            try { context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + context.packageName)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); "settings_opened" } catch (_: Exception) { "unavailable" }
        }
    }

    /**
     * Reinicia la captura cuando el sistema cerró el servicio (reinicio del teléfono, limpieza de
     * memoria del fabricante). Solo si la participación sigue activa y el alumno dio ubicación
     * "todo el tiempo" o quitó la restricción de batería; la notificación permanente sigue
     * mostrando que la captura está activa y permite pausarla.
     */
    fun restartIfNeeded(context: Context) {
        if (LocationService.running) return
        val v = Vault(context)
        if (v.get("mode") != "REAL" || v.get("active") != "true" || v.get("local_status") == "revoked" || v.get("local_pause") == "true" || v.get("policy_pending") == "true") return
        val fine = context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == 0 || context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == 0
        val background = context.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) == 0
        val location = v.get("location") == "true" && fine && background
        val steps = v.get("steps") == "true" && context.checkSelfPermission(Manifest.permission.ACTIVITY_RECOGNITION) == 0
        if (!location && !(steps && batteryUnrestricted(context))) return
        try { context.startForegroundService(Intent(context, LocationService::class.java)) } catch (_: Exception) {
            // Android puede negar el inicio desde segundo plano; se reintentará al abrir la app.
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            DeviceSetup.restartIfNeeded(context.applicationContext)
        }
    }
}
