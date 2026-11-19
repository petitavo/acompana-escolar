package pe.upc.acompana.acompana_escolar

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.app.usage.UsageEvents
import android.content.Context
import android.os.Build
import android.os.Process
import android.os.SystemClock
import android.os.BatteryManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.work.*
import org.json.JSONObject
import org.json.JSONArray
import java.time.Instant
import java.time.ZoneId
import java.util.UUID
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

class ApiFailure(val status:Int):Exception("Servidor HTTP $status")
class Collector(private val context:Context){
    private val vault=Vault(context)
    private val database=LabDatabase.get(context)
    private val dao=database.packets()
    private val http=OkHttpClient.Builder().callTimeout(30,TimeUnit.SECONDS).build()
    companion object {val mutex=Any();val names=mapOf(15 to "SCREEN_INTERACTIVE",16 to "SCREEN_NON_INTERACTIVE",17 to "KEYGUARD_SHOWN",18 to "KEYGUARD_HIDDEN",1 to "ACTIVITY_RESUMED",2 to "ACTIVITY_PAUSED",26 to "DEVICE_SHUTDOWN",27 to "DEVICE_STARTUP")}
    fun permission():Boolean {
        val ops=context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        return ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,Process.myUid(),context.packageName)==AppOpsManager.MODE_ALLOWED
    }
    fun request(path:String,method:String="GET",body:String?=null,key:String=UUID.randomUUID().toString()):String {
        val url=vault.get("server").trimEnd('/')+"/api/v1"+path
        val builder=Request.Builder().url(url).header("Idempotency-Key",key)
        val token=vault.get("token");if(token.isNotEmpty())builder.header("Authorization","Bearer $token")
        if(method!="GET")builder.method(method,(body?:"{}").toRequestBody("application/json".toMediaType()))
        return http.newCall(builder.build()).execute().use{response->
            if(!response.isSuccessful){
                if(response.code==401 && vault.get("token").isNotEmpty()){
                    vault.put("active","false");vault.put("local_status","revoked");dao.cancelCapture()
                    WorkManager.getInstance(context).cancelUniqueWork("lab-collection")
                    if(vault.get("mode")=="REAL"){
                        vault.put("sensor_segment","");context.stopService(android.content.Intent(context,LocationService::class.java))
                        WorkManager.getInstance(context).cancelUniqueWork("school-sync")
                    }
                }
                throw ApiFailure(response.code)
            }
            response.body?.string()?:"{}"
        }
    }
    fun enroll(server:String,invitation:String):JSONObject=synchronized(mutex){
        val uri=java.net.URI(server)
        require(uri.scheme=="https" || uri.scheme=="http" && uri.host in listOf("10.0.2.2","127.0.0.1","localhost")){"Usa HTTPS; HTTP solo emulador local de depuración"}
        require(uri.userInfo==null && uri.query==null && uri.fragment==null){"URL inválida"}
        check(vault.get("token").isEmpty()){ "El dispositivo ya está vinculado" }
        vault.put("server",server)
        val payload=JSONObject().put("invitation",invitation).put("device",JSONObject().put("android_api",Build.VERSION.SDK_INT).put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("app_version","0.1.0").put("timezone",ZoneId.systemDefault().id))
        val response=JSONObject(request("/enrollments/redeem","POST",payload.toString()))
        vault.put("token",response.getString("token"));vault.put("device",response.getString("device_id"));vault.put("mode",response.getString("mode"));vault.put("pseudonym",response.getString("pseudonym"));vault.put("active","false")
        return status()
    }
    fun participation(action:String,share:Boolean=false):JSONObject=synchronized(mutex){
        val at=System.currentTimeMillis();val active=action in listOf("consent","resume")
        require(vault.get("token").isNotEmpty()){"Primero vincula el teléfono"}
        if(action=="package_policy")vault.put("share_packages",share.toString())
        else{
            vault.put("active",active.toString());vault.put("local_status",if(active)"active" else if(action=="pause")"paused" else "revoked")
            if(active){vault.put("interval_start",at.toString());vault.put("cursor",at.toString());vault.put("share_packages",share.toString())}
            else {dao.cancelCapture();WorkManager.getInstance(context).cancelUniqueWork("lab-collection")}
        }
        val payload=JSONObject().put("action",action).put("occurred_at",Instant.ofEpochMilli(at).toString()).put("consent_version",if(vault.get("mode")=="REAL")vault.get("document_version") else "lab-v1").put("adult",true).put("share_packages",share)
        enqueue("participation","/me/participation-events",payload)
        if(active && vault.get("mode")=="LAB")schedule()
        try{sync()}catch(e:Exception){vault.put("sync_error","Pendiente de conexión al servidor")}
        status()
    }
    private fun enqueue(kind:String,path:String,body:JSONObject):String {
        val id=UUID.randomUUID().toString();dao.insert(Packet(id,kind,path,body.toString(),System.currentTimeMillis()));return id
    }
    fun capture():JSONObject=synchronized(mutex){
        if(vault.get("active")!="true" || (vault.get("mode")!="LAB" && vault.get("mode")!="REAL") || vault.get("mode")=="REAL" && vault.get("usage")!="true")return status()
        val startAllowed=vault.get("interval_start","0").toLong()
        val end=System.currentTimeMillis();var start=CapturePolicy.start(startAllowed,vault.get("cursor",startAllowed.toString()).toLong(),end)
        // Sin "Acceso al uso" (Android lo restringe en apps instaladas fuera de Play Store),
        // la pantalla se mide con los avisos de encendido/apagado que escucha el servicio.
        // Solo cuenta el tiempo en que de verdad se estuvo escuchando.
        val usageAccess=permission()
        val listenSince=vault.get("screen_listen_since").toLongOrNull()
        val broadcast=vault.get("mode")=="REAL" && !usageAccess && LocationService.screenListening && listenSince!=null
        if(broadcast && listenSince!!>start)start=listenSince
        if(end<=start)return status()
        val before=usageAccess||broadcast;val sessionId=UUID.randomUUID().toString();val packets=mutableListOf<Packet>()
        var success=false;var error="none"
        val source=if(broadcast)"android_screen_broadcast" else "android_usage_events"
        try{
            if(!before)error="permission_missing"
            else if(broadcast){
                for(row in dao.localScreen(start,end)){
                    val raw=JSONObject(row.body);val t=raw.getLong("t");val name=raw.getString("name")
                    if(!CapturePolicy.permitted(t,startAllowed,start,end))continue
                    val stable=vault.get("device")+"|"+t+"|"+name+"|"
                    val fingerprint=java.security.MessageDigest.getInstance("SHA-256").digest(stable.toByteArray()).joinToString(""){"%02x".format(it)}
                    val id=UUID.nameUUIDFromBytes(stable.toByteArray()).toString();val zone=ZoneId.systemDefault();val instant=Instant.ofEpochMilli(t)
                    val body=JSONObject().put("schema_version","1.0").put("event_id",id).put("device_id",vault.get("device")).put("occurred_at",instant.toString()).put("timezone",zone.id).put("utc_offset_minutes",zone.rules.getOffset(instant).totalSeconds/60).put("event_type",name).put("source",source).put("payload",JSONObject()).put("capture_session_id",sessionId).put("consent_version",vault.get("document_version"))
                    packets.add(Packet(id,"event","/events/batch",body.toString(),end,fingerprint))
                }
                success=true
            }
            else{
                val service=context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
                val query=service.queryEvents(start,end)
                if(query==null)error="device_locked"
                else {
                    while(query.hasNextEvent()){
                        val event=UsageEvents.Event();query.getNextEvent(event)
                        val name=names[event.eventType]?:continue
                        if(!CapturePolicy.permitted(event.timeStamp,startAllowed,start,end))continue
                        val payload=JSONObject()
                        if(vault.get("share_packages")=="true" && event.eventType in listOf(1,2) && !event.packageName.isNullOrBlank())payload.put("package",event.packageName)
                        val stable=vault.get("device")+"|"+event.timeStamp+"|"+name+"|"+payload.optString("package","")
                        val fingerprint=java.security.MessageDigest.getInstance("SHA-256").digest(stable.toByteArray()).joinToString(""){"%02x".format(it)}
                        val id=UUID.nameUUIDFromBytes(stable.toByteArray()).toString();val zone=ZoneId.systemDefault();val instant=Instant.ofEpochMilli(event.timeStamp)
                        val body=JSONObject().put("schema_version","1.0").put("event_id",id).put("device_id",vault.get("device")).put("occurred_at",instant.toString()).put("timezone",zone.id).put("utc_offset_minutes",zone.rules.getOffset(instant).totalSeconds/60).put("event_type",name).put("source","android_usage_events").put("payload",payload).put("capture_session_id",sessionId).put("consent_version",if(vault.get("mode")=="REAL")vault.get("document_version") else "lab-v1")
                        packets.add(Packet(id,"event","/events/batch",body.toString(),end,fingerprint))
                    }
                    success=true
                }
            }
        }catch(e:SecurityException){error="permission_missing"}catch(e:Exception){error="query_failed"}
        val after=if(broadcast)LocationService.screenListening && vault.get("screen_listen_since")==listenSince.toString() else permission()
        if(!after){success=false;error="permission_missing"}
        dao.dropLocalScreen(end)
        if(vault.get("active")!="true")return status()
        val battery=context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val conn=context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps=conn.getNetworkCapabilities(conn.activeNetwork)
        val report=JSONObject().put("id",sessionId).put("start_at",Instant.ofEpochMilli(start).toString()).put("end_at",Instant.ofEpochMilli(end).toString()).put("success",success).put("permission_before",before).put("permission_after",after).put("count",packets.size).put("error",error).put("charging",battery.isCharging).put("connected",caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)==true).put("outbox_pending",dao.countPending()).put("monotonic_ms",SystemClock.elapsedRealtime()).put("keyguard_available",true).put("source",source)
        val level=battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);if(level in 0..100)report.put("battery",level)
        database.runInTransaction{
            dao.insert(Packet(sessionId,"capture","/capture-sessions",report.toString(),end))
            if(success && before && after)packets.forEach{dao.insert(it)}
        }
        // Never backfill a period where permission was missing, even after it returns.
        vault.put("cursor",end.toString());vault.put("last_query",Instant.ofEpochMilli(end).toString());vault.put("capture_error",error)
        val retentionCut=end-TimeUnit.DAYS.toMillis(vault.get("raw_retention_days","7").toLong())
        dao.expireStaleCaptures(retentionCut);dao.purgeDelivered(retentionCut);status()
    }
    fun sync():JSONObject=synchronized(mutex){
        if(vault.get("token").isEmpty())return status()
        // Pause/revoke operations go first and can be sent while collection is locally stopped.
        for(packet in dao.policies()){
            try{request(packet.path,"POST",packet.body,packet.id);dao.confirm(listOf(packet.id))}
            catch(e:ApiFailure){if(e.status in listOf(401,403)){vault.put("active","false");dao.reject(packet.id,"auth_revoked");return status()};throw e}
        }
        for(packet in dao.pending("deletion")){
            request(packet.path,"POST",packet.body,packet.id)
            vault.put("active","false");vault.put("local_status","revoked");dao.clear()
            WorkManager.getInstance(context).cancelUniqueWork("lab-collection")
            return status()
        }
        if(vault.get("local_status")=="revoked")return status()
        val policy=JSONObject(request("/me/collection-policy"))
        if(!policy.optBoolean("active")){vault.put("active","false");vault.put("local_status","paused");dao.cancelCapture();return status()}
        if(vault.get("active")!="true")return status()
        vault.put("share_packages",policy.optBoolean("share_packages").toString())
        vault.put("raw_retention_days",policy.optInt("raw_retention_days",7).coerceIn(1,30).toString())
        // Permission is rechecked before transmitting captured usage. Forms remain usable without it.
        run {
            for(packet in dao.pending("capture")){
                try{request(packet.path,"POST",packet.body,packet.id);dao.confirm(listOf(packet.id))}
                catch(e:ApiFailure){if(CapturePolicy.terminalHttp(e.status))dao.reject(packet.id,"http_"+e.status) else throw e}
            }
            if(permission()){
                val packets=dao.pending("event")
                if(packets.isNotEmpty()){
                    val batch=JSONArray();packets.forEach{batch.put(JSONObject(it.body))}
                    val result=JSONObject(request("/events/batch","POST",JSONObject().put("events",batch).toString()))
                    val confirmed=mutableListOf<String>()
                    for(name in listOf("accepted","duplicates")){val list=result.getJSONArray(name);for(i in 0 until list.length())confirmed.add(list.getString(i))}
                    dao.confirm(confirmed)
                    val rejected=result.getJSONArray("rejected");for(i in 0 until rejected.length()){val row=rejected.getJSONObject(i);dao.reject(row.getString("event_id"),row.getString("reason"))}
                }
            }
        }
        for(kind in listOf("questionnaire","contact","deletion"))for(packet in dao.pending(kind)){
            try{
                request(packet.path,"POST",packet.body,packet.id);dao.confirm(listOf(packet.id))
                if(kind=="deletion"){vault.put("active","false");vault.put("local_status","revoked");dao.clear();WorkManager.getInstance(context).cancelUniqueWork("lab-collection")}
            }catch(e:ApiFailure){if(CapturePolicy.terminalHttp(e.status))dao.reject(packet.id,"http_"+e.status) else throw e}
        }
        vault.put("last_sync",Instant.now().toString());vault.put("sync_error","");status()
    }
    fun status():JSONObject {
        return JSONObject().put("enrolled",vault.get("token").isNotEmpty()).put("active",vault.get("active")=="true").put("local_status",vault.get("local_status","pending")).put("pseudonym",vault.get("pseudonym")).put("mode",vault.get("mode")).put("device_id",vault.get("device")).put("share_packages",vault.get("share_packages")=="true").put("usage_access",if(permission())"available" else "permission_missing").put("outbox_pending",dao.countPending()).put("events_local",dao.countEvents()).put("rejected",dao.countRejected()).put("expired_captures",dao.countExpired()).put("pending_forms",dao.countPendingForms()).put("last_query",vault.get("last_query")).put("last_sync",vault.get("last_sync")).put("capture_error",vault.get("capture_error")).put("sync_error",vault.get("sync_error")).put("gps","not_implemented").put("steps","not_implemented")
    }
    fun forms():String {
        return try{val result=request("/questionnaires/due");vault.put("cached_forms",result);result}
        catch(e:Exception){val cached=vault.get("cached_forms");if(cached.isNotEmpty())cached else throw e}
    }
    fun history():String=request("/me/questionnaire-responses")
    fun draft(value:String?=null):String {if(value!=null)vault.put("form_draft",value);return vault.get("form_draft","{}")}
    fun submit(body:String):JSONObject=synchronized(mutex){
        require(vault.get("active")=="true"){"La participación está pausada"}
        enqueue("questionnaire","/questionnaire-responses",JSONObject(body));vault.put("form_draft","{}")
        try{sync()}catch(e:Exception){vault.put("sync_error","Formulario pendiente de sincronización")};status()
    }
    fun contact():JSONObject=synchronized(mutex){
        require(vault.get("active")=="true"){"La participación está pausada"}
        enqueue("contact","/contact-requests",JSONObject().put("requested_at",Instant.now().toString()))
        try{sync()}catch(e:Exception){vault.put("sync_error","Solicitud pendiente de sincronización")};status()
    }
    fun delete():JSONObject=synchronized(mutex){
        enqueue("deletion","/me/deletion-requests",JSONObject())
        // Request deletion online first; on network failure retain request but stop capture immediately.
        try{sync()}finally{vault.put("active","false");dao.cancelCapture();WorkManager.getInstance(context).cancelUniqueWork("lab-collection")}
        status()
    }
    fun schedule(){
        val work=PeriodicWorkRequestBuilder<CollectionWorker>(15,TimeUnit.MINUTES).setBackoffCriteria(BackoffPolicy.EXPONENTIAL,30,TimeUnit.SECONDS).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("lab-collection",ExistingPeriodicWorkPolicy.KEEP,work)
    }
}
class CollectionWorker(context:Context,params:WorkerParameters):Worker(context,params){
    override fun doWork():Result=try{val collector=Collector(applicationContext);collector.capture();collector.sync();Result.success()}catch(e:Exception){Result.retry()}
}
