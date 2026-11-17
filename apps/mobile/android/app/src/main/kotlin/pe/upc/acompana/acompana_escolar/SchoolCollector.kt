package pe.upc.acompana.acompana_escolar

import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.work.*
import org.json.JSONObject
import org.json.JSONArray
import java.time.Instant
import java.time.ZoneId
import java.time.LocalDate
import java.util.UUID
import java.util.concurrent.TimeUnit

/** Product outbox: encrypted locally, stable id per operation, receipt only after HTTP success. */
class SchoolCollector(private val context:Context) {
    private val vault=Vault(context)
    private val dao=LabDatabase.get(context).packets()
    private val transport=Collector(context)
    private fun request(path:String,method:String="GET",body:String?=null,key:String=UUID.randomUUID().toString())=transport.request("/school"+path,method,body,key)
    fun enroll(server:String,invitation:String,code:String):String=synchronized(Collector.mutex){
        val uri=java.net.URI(server)
        require(uri.scheme=="https" || BuildConfig.DEBUG && uri.scheme=="http" && uri.host in listOf("10.0.2.2","127.0.0.1","localhost")){"Usa la dirección HTTPS de tu institución"}
        require(uri.userInfo==null && uri.query==null && uri.fragment==null){"Dirección inválida"}
        check(vault.get("token").isEmpty()){"Este teléfono ya está vinculado"}
        vault.put("server",server)
        val body=JSONObject().put("invitation",invitation).put("verification_code",code).put("device",JSONObject().put("android_api",Build.VERSION.SDK_INT).put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("app_version",BuildConfig.VERSION_NAME).put("timezone",ZoneId.systemDefault().id))
        val r=JSONObject(request("/enroll","POST",body.toString()))
        vault.put("token",r.getString("token"));vault.put("device",r.getString("device_id"));vault.put("mode",r.getString("mode"));vault.put("pseudonym",r.getString("pseudonym"));vault.put("active","false")
        schedule(); home(); status()
    }
    private fun cached(path:String,key:String,empty:String):String=try{
        request(path).also{vault.put(key,it);if(key=="school_home")vault.put("home_offline","false")}
    }catch(e:Exception){
        if(key=="school_home")vault.put("home_offline","true")
        if(e is ApiFailure && e.status in listOf(401,403))throw e
        vault.get(key,empty)
    }
    fun home():String {
        val text=cached("/me","school_home","{}")
        val home=JSONObject(text)
        if(home.has("analysis_timezone"))vault.put("analysis_timezone",home.getString("analysis_timezone"))
        if(home.has("authorization")){
            val p=home.getJSONObject("policy")
            if(home.optBoolean("capture_active") && vault.get("active")!="true"){
                val begin=System.currentTimeMillis().toString();vault.put("interval_start",begin);vault.put("cursor",begin)
            }
            for(kind in listOf("usage","location","steps"))if(p.has(kind+"_since"))vault.put(kind+"_since",SchoolTime.instant(p.getString(kind+"_since")).toEpochMilli().toString())
            vault.put("document_version",home.getJSONObject("authorization").getString("version"))
            val pending=dao.policies().isNotEmpty()
            if(!pending)for(k in listOf("usage","location","steps","raw_location_upload"))vault.put(k,p.optBoolean(k).toString())
            val active=home.optBoolean("capture_active") && home.getJSONObject("authorization").optBoolean("ready") && home.optBoolean("pilot_enabled") && vault.get("local_status")!="revoked" && vault.get("local_pause")!="true"
            // A pending local pause cannot be undone by a stale server response.
            if(!pending)vault.put("active",active.toString())
            if(!active)stopSensors()
        }
        return text
    }
    fun status():String {
        val pending=dao.policies().isNotEmpty();vault.put("policy_pending",pending.toString())
        val running=LocationService.running
        val locationPermission=if(context.checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)==0)"precise" else if(context.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)==0)"approximate" else "missing"
        return transport.status()
            .put("gps",if(LocationService.locationRunning)"running" else "stopped")
            .put("reauth_required",vault.get("local_status")=="revoked")
            .put("home",JSONObject(vault.get("school_home","{}")))
            .put("home_offline",vault.get("home_offline")=="true")
            .put("policy_pending",pending)
            .put("sensor_running",running)
            .put("location_running",LocationService.locationRunning)
            .put("steps_running",LocationService.stepsRunning)
            .put("sensor_error",LocationService.lastError)
            .put("location_permission",locationPermission)
            .put("battery_unrestricted",DeviceSetup.batteryUnrestricted(context))
            .put("background_location",context.checkSelfPermission(android.Manifest.permission.ACCESS_BACKGROUND_LOCATION)==0)
            .put("steps_permission",context.checkSelfPermission(android.Manifest.permission.ACTIVITY_RECOGNITION)==0)
            .put("notifications_permission",androidx.core.app.NotificationManagerCompat.from(context).areNotificationsEnabled())
            .put("steps_supported",(context.getSystemService(Context.SENSOR_SERVICE) as android.hardware.SensorManager).getDefaultSensor(android.hardware.Sensor.TYPE_STEP_COUNTER)!=null)
            .toString()
    }
    private fun queue(kind:String,path:String,body:String):String {
        val id=UUID.randomUUID().toString();dao.insert(Packet(id,kind,"/school"+path,body,System.currentTimeMillis()));return id
    }
    fun participation(body:String):String=synchronized(Collector.mutex){
        val p=JSONObject(body);val action=p.getString("action")
        val previousActive=vault.get("active")=="true"
        val enabling=listOf("usage","location","steps").any{p.optBoolean(it) && vault.get(it)!="true"}
        if(enabling || action in listOf("assent","consent","resume")){vault.put("active","false");stopSensors()}
        // Stop locally first, even without connectivity; resumption waits for server acceptance.
        if(action in listOf("pause","withdraw") || p.optBoolean("location")!=(vault.get("location")=="true") || p.optBoolean("steps")!=(vault.get("steps")=="true"))stopSensors()
        if(action in listOf("pause","withdraw")){vault.put("local_pause","true");vault.put("active","false");dao.cancelCapture()}
        for(k in listOf("usage","location","steps","raw_location_upload")){
            if(!p.optBoolean(k)){dao.cancelKind(k);if(k=="usage"){dao.cancelKind("capture");dao.cancelKind("event")}}
            if(p.optBoolean(k) && (vault.get(k)!="true" || !previousActive))vault.put(k+"_since",System.currentTimeMillis().toString())
            vault.put(k,p.optBoolean(k).toString())
        }
        if(!p.optBoolean("raw_location_upload"))dao.cancelKind("location")
        val id=queue("participation","/me/participation",body);vault.put("policy_pending","true")
        try{sync()}catch(e:Exception){vault.put("sync_error","Tu decisión está guardada y pendiente de conexión")}
        JSONObject(status()).put("decision_state",dao.packet(id)?.state?:if(action=="withdraw" && vault.get("token").isEmpty())"confirmed" else "unknown").toString()
    }
    fun forms()=if(dao.pending("school_form").isNotEmpty())"[]" else cached("/me/questionnaires","school_forms","[]")
    fun history()=cached("/me/questionnaires/history","school_history","[]")
    fun correct(id:String,body:String):String=synchronized(Collector.mutex){
        UUID.fromString(id)
        if(dao.pending("school_correction").any{it.path.contains(id)})throw IllegalStateException("Ya hay una corrección pendiente")
        queue("school_correction","/me/questionnaires/$id/corrections",body)
        try{sync()}catch(_:Exception){}
        status()
    }
    fun requests()=cached("/me/requests","school_requests","{}")
    // A04: the student can see every unresolved local item — pending (waiting for the
    // server), rejected (server refused, e.g. duplicate period) and expired capture
    // tombstones — and explicitly dismiss a rejected/expired one. A pending
    // questionnaire/support packet is never removed here; it waits until delivered.
    fun deliveryLog():String {
        val labels=mapOf("school_correction" to "Corrección de cuestionario","school_form" to "Respuesta de cuestionario","school_support" to "Solicitud de acompañamiento",
            "school_appointment" to "Confirmación de cita","participation" to "Cambio de participación","deletion" to "Solicitud de retiro")
        val arr=JSONArray()
        for(p in dao.deliveryLog()){
            val capture=p.kind in listOf("event","capture","location","steps","summary","local_location","local_steps")
            arr.put(JSONObject().put("id",p.id).put("state",p.state).put("created_at",Instant.ofEpochMilli(p.createdAt).toString())
                .put("kind",p.kind).put("label",labels[p.kind]?:if(capture)"Datos de sensores" else p.kind)
                .put("error",p.error?:"").put("dismissible",p.state=="rejected"||p.state=="expired")
                .put("category",if(capture)"capture" else "form"))
        }
        return arr.toString()
    }
    fun dismiss(id:String):String {
        require(UUID.fromString(id).toString()==id){"Identificador inválido"}
        dao.dismiss(id);return status()
    }
    fun draft(value:String?):String {if(value!=null)vault.put("school_draft",value);return vault.get("school_draft","{}")}
    fun submit(body:String,path:String="/me/questionnaires"):String=synchronized(Collector.mutex){
        require(path in listOf("/me/questionnaires","/me/check-ins")){"Destino de envío no permitido"}
        check(dao.pending("school_form").isEmpty()){"Ya tienes una respuesta pendiente de envío"}
        queue("school_form",path,body);vault.put("school_draft","{}");vault.put("school_forms","[]")
        try{sync()}catch(e:Exception){vault.put("sync_error","Respuesta guardada en el teléfono; pendiente de recepción")};status()
    }
    fun support():String=synchronized(Collector.mutex){
        if(dao.pending("school_support").isEmpty())queue("school_support","/me/support","{}")
        try{sync()}catch(e:Exception){vault.put("sync_error","Solicitud guardada en el teléfono; todavía no recibida")};status()
    }
    fun forgetRevoked():String=synchronized(Collector.mutex){
        require(vault.get("local_status")=="revoked"){"Primero solicita la renovación de tu acceso a la institución"}
        stopSensors();dao.clear();vault.clearParticipation();status()
    }
    fun confirm(id:String):String {UUID.fromString(id);queue("school_appointment","/me/appointments/$id/confirm","{}");try{sync()}catch(_:Exception){};return status()}
    fun stopSensors(){vault.put("sensor_segment","");context.stopService(Intent(context,LocationService::class.java));vault.put("sensor_running","false")}
    fun localPause(){
        stopSensors();vault.put("local_pause","true");vault.put("active","false");dao.cancelCapture()
        val p=JSONObject(vault.get("school_home","{}")).optJSONObject("policy")?:JSONObject()
        val b=JSONObject().put("action","pause").put("document_version",vault.get("document_version")).put("occurred_at",Instant.now().toString())
        for(k in listOf("usage","location","steps","raw_location_upload","research_access","reminders"))b.put(k,p.optBoolean(k))
        queue("participation","/me/participation",b.toString())
    }
    fun sensor(point:JSONObject)=synchronized(Collector.mutex){
        val kind=point.getString("kind")
        if(vault.get("active")!="true" || vault.get(kind)!="true" || point.optString("segment_id")!=vault.get("sensor_segment"))return@synchronized
        if(Instant.parse(point.getString("occurred_at")).toEpochMilli()<vault.get(kind+"_since","${System.currentTimeMillis()}").toLong())return@synchronized
        val id=point.getString("id")
        dao.insert(Packet(id,"local_$kind","",point.toString(),System.currentTimeMillis(),state="local"))
        if(kind=="steps" || vault.get("raw_location_upload")=="true")dao.insert(Packet(UUID.randomUUID().toString(),kind,"/school/me/sensors",JSONObject().put("points",JSONArray().put(point)).toString(),System.currentTimeMillis()))
        if(kind=="location")vault.put("last_location",point.toString())
        val nowMs=System.currentTimeMillis();val retentionCut=nowMs-TimeUnit.DAYS.toMillis(7)
        dao.expireStaleCaptures(retentionCut);dao.purgeDelivered(retentionCut)
    }
    fun homeZone(clear:Boolean):String {
        if(clear){vault.put("home_zone","");if(vault.get("raw_location_upload")=="true")request("/me/home-zone","DELETE");return status()}
        val p=JSONObject(vault.get("last_location","{}"))
        require(p.optString("permission")=="precise" && p.optDouble("accuracy_m",9999.0)<=100 && System.currentTimeMillis()-Instant.parse(p.getString("occurred_at")).toEpochMilli()<=600000){"Primero obtén una ubicación precisa reciente"}
        val h=JSONObject().put("latitude",p.getDouble("latitude")).put("longitude",p.getDouble("longitude")).put("accuracy_m",p.getDouble("accuracy_m"))
        if(vault.get("raw_location_upload")=="true")request("/me/home-zone","PUT",h.toString())
        vault.put("home_zone",h.toString());return status()
    }
    fun sync():String=synchronized(Collector.mutex){
        if(vault.get("token").isEmpty())return@synchronized status()
        for(p in dao.policies()){
            try{
                transport.request(p.path,"POST",p.body,p.id);dao.confirm(listOf(p.id))
                if(JSONObject(p.body).optString("action") in listOf("resume","assent","consent"))vault.put("local_pause","false")
            }
            catch(e:ApiFailure){if(e.status in listOf(400,401,403,409,422)){dao.reject(p.id,"http_${e.status}");vault.put("active","false");stopSensors();continue} else throw e}
            if(JSONObject(p.body).optString("action")=="withdraw"){dao.clear();vault.put("active","false");stopSensors();vault.clearParticipation();WorkManager.getInstance(context).cancelUniqueWork("school-sync");return@synchronized status()}
        }
        home()
        SchoolPush.configure(context)
        val pendingToken=vault.get("pending_push_token")
        if(pendingToken.isNotEmpty())try{
            request("/push-token","POST",JSONObject().put("token",pendingToken).toString());vault.put("pending_push_token","")
        }catch(_:Exception){/* Optional push registration must not block support or forms. */}
        // Requests and responses do not depend on optional sensor permissions.
        for(kind in listOf("school_receipt","school_support","school_form","school_correction","school_appointment","capture","event","location","steps","summary")){
            for(p in dao.pending(kind)){
                if(kind in listOf("capture","event","location","steps","summary") && vault.get("active")!="true")continue
                if(kind in listOf("capture","event") && (vault.get("usage")!="true" || !transport.permission()))continue
                try{
                    if(kind=="event"){
                        val r=JSONObject(transport.request(p.path,"POST",JSONObject().put("events",JSONArray().put(JSONObject(p.body))).toString(),p.id))
                        if(r.getJSONArray("rejected").length()>0){dao.reject(p.id,"server_rejected");continue}
                    } else if(kind in listOf("location","steps")){
                        val r=JSONObject(transport.request(p.path,"POST",p.body,p.id))
                        if(r.getJSONArray("rejected").length()>0){dao.reject(p.id,"sensor_rejected");continue}
                    } else transport.request(p.path,"POST",p.body,p.id)
                    dao.confirm(listOf(p.id))
                } catch(e:ApiFailure){if(e.status in listOf(400,401,403,409,422)){dao.reject(p.id,"http_${e.status}")}else throw e}
            }
        }
        if(vault.get("active")=="true" && vault.get("raw_location_upload")!="true"){
            for(offset in 7L downTo 1L){
                val analysisZone=ZoneId.of(vault.get("analysis_timezone",ZoneId.systemDefault().id))
                val day=LocalDate.now(analysisZone).minusDays(offset).toString()
                if(vault.get("summary_$day").isEmpty()){
                    val rows=dao.localSensors(System.currentTimeMillis()-TimeUnit.DAYS.toMillis(7)).map{JSONObject(it.body)}.filter{vault.get(it.getString("kind"))=="true"}
                    val home=if(vault.get("home_zone").isEmpty())null else JSONObject(vault.get("home_zone"))
                    val school=JSONObject(vault.get("school_home","{}")).optJSONObject("school_zone")
                    val summary=MobilityMath.summary(rows,day,analysisZone.id,home,null,school)
                    summary.remove("lineage");summary.remove("notice");queue("summary","/me/sensor-summary",summary.toString());vault.put("summary_$day","queued")
                }
            }
        }
        val nowMs=System.currentTimeMillis();val retentionCut=nowMs-TimeUnit.DAYS.toMillis(7)
        dao.expireStaleCaptures(retentionCut);dao.purgeDelivered(retentionCut)
        vault.put("last_sync",Instant.now().toString());vault.put("sync_error","");status()
    }
    private fun schedule(){WorkManager.getInstance(context).enqueueUniquePeriodicWork("school-sync",ExistingPeriodicWorkPolicy.KEEP,PeriodicWorkRequestBuilder<SchoolWorker>(15,TimeUnit.MINUTES).build())}
}
class SchoolWorker(context:Context,params:WorkerParameters):Worker(context,params){
    override fun doWork():Result=try{DeviceSetup.restartIfNeeded(applicationContext);val c=SchoolCollector(applicationContext);Collector(applicationContext).capture();c.sync();SchoolReminders.show(applicationContext);Result.success()}catch(_:Exception){Result.retry()}
}
