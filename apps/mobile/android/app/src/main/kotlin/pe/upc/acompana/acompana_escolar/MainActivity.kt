package pe.upc.acompana.acompana_escolar

import android.content.Intent
import android.provider.Settings
import android.net.Uri
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors

class MainActivity:FlutterActivity(){
    private val executor=Executors.newSingleThreadExecutor()
    private var permissionReply:MethodChannel.Result?=null
    private var permissionKind=""
    private fun permissionGranted(kind:String):Boolean=when(kind){
        "location"->checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)==0 || checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)==0
        "steps"->checkSelfPermission(android.Manifest.permission.ACTIVITY_RECOGNITION)==0
        "background"->checkSelfPermission(android.Manifest.permission.ACCESS_BACKGROUND_LOCATION)==0
        "notifications"->androidx.core.app.NotificationManagerCompat.from(this).areNotificationsEnabled()
        else->false
    }
    // Para pedir ubicación exigimos la precisa: los resúmenes de movilidad descartan puntos aproximados.
    private fun requestSatisfied(kind:String):Boolean=if(kind=="location")checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)==0 else permissionGranted(kind)
    private var permissionList:Array<String> = arrayOf()
    private fun permissionResult(result:MethodChannel.Result,state:String){result.success(org.json.JSONObject().put("state",state).toString())}
    private fun askPermission(kind:String,result:MethodChannel.Result){
        if(permissionReply!=null){result.error("PERMISSION_BUSY","Responde primero al permiso que está abierto",null);return}
        if(kind=="settings"){
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:$packageName")))
            permissionResult(result,"settings_opened");return
        }
        val v=Vault(this);val home=org.json.JSONObject(v.get("school_home","{}"))
        val policy=home.optJSONObject("policy")
        if(home.optJSONObject("authorization")?.optBoolean("ready")!=true || v.get("local_status")=="revoked" || v.get("policy_pending")=="true"){result.error("PARTICIPATION_REQUIRED","Primero completa tu participación",null);return}
        val preference=when(kind){"background"->"location";"notifications"->"reminders";else->kind}
        if(policy?.optBoolean(preference)!=true){result.error("PREFERENCE_REQUIRED","Primero guarda tu preferencia para este permiso",null);return}
        if(kind=="usage") {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:$packageName")))
            permissionResult(result,"settings_opened");return
        }
        if(requestSatisfied(kind)){permissionResult(result,"granted");return}
        if(kind=="background" && !permissionGranted("location")){result.error("LOCATION_REQUIRED","Primero permite ubicación al usar la app",null);return}
        if(kind=="background" && android.os.Build.VERSION.SDK_INT>=30){
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:$packageName")))
            permissionResult(result,"settings_opened");return
        }
        if(kind=="notifications" && android.os.Build.VERSION.SDK_INT<33){
            startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName))
            permissionResult(result,"settings_opened");return
        }
        val permissions=when(kind){
            "location"->arrayOf(android.Manifest.permission.ACCESS_COARSE_LOCATION,android.Manifest.permission.ACCESS_FINE_LOCATION)
            "steps"->arrayOf(android.Manifest.permission.ACTIVITY_RECOGNITION)
            "notifications"->arrayOf(android.Manifest.permission.POST_NOTIFICATIONS)
            "background"->arrayOf(android.Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            else->{result.error("PERMISSION_UNKNOWN","Permiso desconocido",null);return}
        }
        // Android deja de mostrar la ventana tras dos rechazos ("no volver a preguntar").
        // En ese caso informamos "blocked" y la app explica cómo activarlo en Ajustes.
        if(v.get("permission_blocked_$kind")=="true" && permissions.none{shouldShowRequestPermissionRationale(it)}){
            permissionResult(result,"blocked");return
        }
        permissionReply=result;permissionKind=kind;permissionList=permissions;v.put("permission_asked_$kind","true")
        requestPermissions(permissions,61)
    }
    override fun onRequestPermissionsResult(requestCode:Int,permissions:Array<out String>,grantResults:IntArray){
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        if(requestCode==61){
            val reply=permissionReply;permissionReply=null
            if(reply!=null){
                val state=when{
                    requestSatisfied(permissionKind)->"granted"
                    permissionKind=="location" && permissionGranted("location")->"approximate"
                    permissionList.none{shouldShowRequestPermissionRationale(it)}->"blocked"
                    else->"denied"
                }
                Vault(this).put("permission_blocked_$permissionKind",(state=="blocked").toString())
                permissionResult(reply,state)
            }
        }
    }

    override fun configureFlutterEngine(engine:FlutterEngine){
        super.configureFlutterEngine(engine)
        MethodChannel(engine.dartExecutor.binaryMessenger,"pe.upc.acompana/collector").setMethodCallHandler{call,result->
            if(call.method=="schoolPermission"){
                try{askPermission(call.argument<String>("kind")?:"",result)}catch(_:Exception){permissionReply=null;result.error("PERMISSION_ERROR","No se pudo abrir el permiso. Revisa los ajustes del teléfono",null)}
            }else if(call.method=="schoolStartSensors"){
                val v=Vault(this)
                if(v.get("active")!="true" || v.get("local_status")=="revoked" || v.get("policy_pending")=="true"){
                    result.error("PARTICIPATION_REQUIRED","Guarda o reanuda tu participación antes de iniciar sensores",null)
                }else if(!(v.get("location")=="true" && permissionGranted("location")) && !(v.get("steps")=="true" && permissionGranted("steps"))){
                    result.error("PERMISSION_REQUIRED","Concede ubicación o actividad física para iniciar los sensores elegidos",null)
                }else try{
                    val intent=Intent(this,LocationService::class.java)
                    if(call.argument<Boolean>("reconfigure")==true)intent.action="refresh"
                    startForegroundService(intent)
                    android.os.Handler(mainLooper).postDelayed({
                        executor.execute{
                            val snapshot=SchoolCollector(applicationContext).status()
                            runOnUiThread{result.success(snapshot)}
                        }
                    },350)
                }catch(_:Exception){result.error("SENSOR_START","Abre la aplicación y comprueba los permisos",null)}
            }else if(call.method=="schoolDeviceSetup"){
                result.success(DeviceSetup.info(this).toString())
            }else if(call.method=="schoolOpenBattery"){
                permissionResult(result,DeviceSetup.openBattery(this))
            }else if(call.method=="schoolOpenAutostart"){
                permissionResult(result,DeviceSetup.openAutostart(this))
            }else if(call.method=="schoolDial"){
                // ACTION_DIAL solo abre el marcador con el número: no llama ni requiere permiso.
                val number=(call.argument<String>("number")?:"").filter{it.isDigit()||it=='+'}
                if(number.isEmpty()){result.error("NO_NUMBER","Número inválido",null)}
                else{
                    try{startActivity(Intent(Intent.ACTION_DIAL,Uri.parse("tel:$number")));result.success("{}")}
                    catch(e:Exception){result.error("NO_DIALER","Este teléfono no tiene marcador",null)}
                }
            }else if(call.method=="schoolOpenSettings"){
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:$packageName")))
                permissionResult(result,"settings_opened")
            }else if(call.method=="schoolSetupConfirm"){
                val key=call.argument<String>("key")?:""
                if(key in listOf("autostart")){Vault(this).put("setup_$key",(call.argument<Boolean>("value")?:true).toString())}
                result.success(DeviceSetup.info(this).toString())
            }else if(call.method=="openUsageSettings"){
                startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:$packageName")));result.success(null)
            }else executor.execute{
                try{
                    val collector=Collector(applicationContext)
                    val response=when(call.method){
                        "schoolForget"->SchoolCollector(applicationContext).forgetRevoked()
                        "schoolStatus"->SchoolCollector(applicationContext).status()
                        "schoolEnroll"->SchoolCollector(applicationContext).enroll(call.argument<String>("server")!!,call.argument<String>("invitation")!!,call.argument<String>("code")!!)
                        "schoolHome"->SchoolCollector(applicationContext).home()
                        "schoolParticipation"->SchoolCollector(applicationContext).participation(call.argument<String>("body")!!)
                        "schoolSync"->SchoolCollector(applicationContext).sync()
                        "schoolHistory"->SchoolCollector(applicationContext).history()
                        "schoolCorrection"->SchoolCollector(applicationContext).correct(call.argument<String>("id")!!,call.argument<String>("body")!!)
                        "schoolForms"->SchoolCollector(applicationContext).forms()
                        "schoolRequests"->SchoolCollector(applicationContext).requests()
                        "schoolDraft"->SchoolCollector(applicationContext).draft(call.argument<String>("value"))
                        "schoolSubmit"->SchoolCollector(applicationContext).submit(call.argument<String>("body")!!,call.argument<String>("path")?:"/me/questionnaires")
                        "schoolSupport"->SchoolCollector(applicationContext).support()
                        "schoolConfirm"->SchoolCollector(applicationContext).confirm(call.argument<String>("id")!!)
                        "schoolDeliveryLog"->SchoolCollector(applicationContext).deliveryLog()
                        "schoolDismiss"->SchoolCollector(applicationContext).dismiss(call.argument<String>("id")!!)
                        "schoolHomeZone"->SchoolCollector(applicationContext).homeZone(call.argument<Boolean>("clear")?:false)
                        "status"->collector.status().toString()
                        "enroll"->collector.enroll(call.argument<String>("server")!!,call.argument<String>("invitation")!!).toString()
                        "participation"->collector.participation(call.argument<String>("action")!!,call.argument<Boolean>("share")?:false).toString()
                        "capture"->collector.capture().toString()
                        "sync"->collector.sync().toString()
                        "forms"->collector.forms()
                        "history"->collector.history()
                        "draft"->collector.draft(call.argument<String>("value"))
                        "submit"->collector.submit(call.argument<String>("body")!!).toString()
                        "contact"->collector.contact().toString()
                        "delete"->collector.delete().toString()
                        else->throw IllegalArgumentException("Método no soportado")
                    }
                    runOnUiThread{result.success(response)}
                }catch(e:Exception){if(BuildConfig.DEBUG)android.util.Log.e("SchoolBridge",call.method+": "+e.javaClass.simpleName);runOnUiThread{result.error("LAB_OPERATION",if(e is ApiFailure)"Servidor HTTP ${e.status}; datos pendientes conservados" else e.message?:"No se pudo completar la operación",null)}}
            }
        }
    }
}
