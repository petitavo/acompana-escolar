package pe.upc.acompana.acompana_escolar

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.hardware.*
import android.location.*
import android.os.*
import androidx.core.app.NotificationCompat
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.location.*
import org.json.JSONObject
import java.time.*
import java.util.UUID
import java.util.concurrent.Executors

/** Explicitly started while Activity is visible. Never restarted by WorkManager or BOOT. */
class LocationService:Service(),SensorEventListener {
    companion object {
        @Volatile var running=false; private set
        @Volatile var locationRunning=false; private set
        @Volatile var stepsRunning=false; private set
        @Volatile var lastError=""; private set
    }
    private var destroyed=false
    private fun enqueue(task:()->Unit){if(!io.isShutdown)try{io.execute(task)}catch(_:java.util.concurrent.RejectedExecutionException){}}

    private val io=Executors.newSingleThreadExecutor()
    private lateinit var vault:Vault
    private lateinit var sensors:SensorManager
    private lateinit var manager:LocationManager
    private var fused:FusedLocationProviderClient?=null
    private var lastStep=0L
    private var boot=""
    private val segment=UUID.randomUUID().toString()
    private val callback=object:LocationCallback(){override fun onLocationResult(result:LocationResult){result.locations.forEach{record(it)}}}
    private val listener=object:android.location.LocationListener {
        override fun onLocationChanged(location:Location){record(location)}
        override fun onProviderEnabled(provider:String){}
        override fun onProviderDisabled(provider:String){}
    }
    override fun onBind(intent:Intent?)=null
    override fun onCreate(){super.onCreate();vault=Vault(this);sensors=getSystemService(SENSOR_SERVICE) as SensorManager;manager=getSystemService(LOCATION_SERVICE) as LocationManager
        boot=android.provider.Settings.Global.getInt(contentResolver,android.provider.Settings.Global.BOOT_COUNT,-1).toString()
        if(boot=="-1")boot=UUID.randomUUID().toString()
    }
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="pause"){
            // Make the local stop effective before an already queued callback can run.
            vault.put("local_pause","true");vault.put("active","false");vault.put("sensor_segment","")
            enqueue{SchoolCollector(this).localPause()};stopSelf();return START_NOT_STICKY
        }
        if(running && intent?.action!="refresh")return START_NOT_STICKY
        if(running){
            try{fused?.removeLocationUpdates(callback);manager.removeUpdates(listener)}catch(_:SecurityException){}
            sensors.unregisterListener(this)
            locationRunning=false;stepsRunning=false;running=false
        }
        lastError=""
        if(vault.get("mode")!="REAL" || vault.get("active")!="true"){stopSelf();return START_NOT_STICKY}
        val location=vault.get("location")=="true" && (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==0 || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==0)
        val steps=vault.get("steps")=="true" && checkSelfPermission(Manifest.permission.ACTIVITY_RECOGNITION)==0 && sensors.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)!=null
        if(!location&&!steps){lastError="Concede ubicación o actividad física para iniciar los sensores elegidos.";stopSelf();return START_NOT_STICKY}
        val nm=getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel("collection","Participación y sensores",NotificationManager.IMPORTANCE_LOW))
        val stop=PendingIntent.getService(this,2,Intent(this,LocationService::class.java).setAction("pause"),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification=NotificationCompat.Builder(this,"collection").setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("Acompaña Escolar").setContentText(if(location&&steps)"Ubicación y pasos activos · puedes pausar" else if(location)"Ubicación activa · puedes pausar" else "Pasos activos · puedes pausar").setOngoing(true).setContentIntent(open).addAction(0,"Pausar",stop).build()
        var type=if(location)ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION else 0
        if(steps&&Build.VERSION.SDK_INT>=34)type=type or ServiceInfo.FOREGROUND_SERVICE_TYPE_HEALTH
        try{
            startForeground(41,notification,type)
            vault.put("sensor_segment",segment);vault.put("sensor_running","true");running=true
            if(location)startLocation()
            if(steps)stepsRunning=sensors.registerListener(this,sensors.getDefaultSensor(Sensor.TYPE_STEP_COUNTER),SensorManager.SENSOR_DELAY_NORMAL)
        }catch(_:Exception){lastError="Android no permitió iniciar los sensores. Revisa los permisos y vuelve a intentarlo con la app abierta.";running=false;vault.put("sensor_running","false");stopSelf()}
        return START_NOT_STICKY
    }
    @Suppress("MissingPermission")
    private fun startLocation(){
        val sampling=JSONObject(vault.get("school_home","{}")).optJSONObject("sampling")
        val interval=(sampling?.optLong("interval_minutes",15)?:15).coerceIn(5,120)*60000
        val distance=(sampling?.optDouble("distance_meters",100.0)?:100.0).coerceIn(20.0,1000.0).toFloat()
        if(GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(this)==ConnectionResult.SUCCESS){
            fused=LocationServices.getFusedLocationProviderClient(this)
            val request=com.google.android.gms.location.LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY,interval).setMinUpdateDistanceMeters(distance).setMinUpdateIntervalMillis(interval).setMaxUpdateAgeMillis(0).build()
            fused!!.requestLocationUpdates(request,callback,mainLooper)
                .addOnSuccessListener{if(!destroyed)locationRunning=true else fused?.removeLocationUpdates(callback)}
                .addOnFailureListener{if(!destroyed)fallback(interval,distance)}
        } else fallback(interval,distance)
    }
    @Suppress("MissingPermission")
    private fun fallback(interval:Long,distance:Float){
        if(destroyed)return
        for(provider in listOf(LocationManager.GPS_PROVIDER,LocationManager.NETWORK_PROVIDER))try{
            if(manager.isProviderEnabled(provider)){
                manager.requestLocationUpdates(provider,interval,distance,listener,mainLooper);locationRunning=true
            }
        }catch(_:Exception){}
        if(!locationRunning)lastError="No hay proveedor de ubicación disponible. Revisa que la ubicación del teléfono esté encendida."
    }
    private fun base(kind:String,at:Instant):JSONObject {
        val zone=ZoneId.systemDefault();val battery=(getSystemService(BATTERY_SERVICE) as BatteryManager).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val p=JSONObject().put("segment_id",segment).put("id",UUID.randomUUID().toString()).put("kind",kind).put("occurred_at",at.toString()).put("timezone",zone.id).put("utc_offset_minutes",zone.rules.getOffset(at).totalSeconds/60)
        if(battery in 0..100)p.put("battery",battery);return p
    }
    private fun record(location:Location){
        val copy=Location(location)
        enqueue{
            if(vault.get("active")!="true" || vault.get("location")!="true"){stopSelf();return@enqueue}
            val precise=checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==0
            if(!precise&&checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)!=0){stopSelf();return@enqueue}
            val age=((SystemClock.elapsedRealtimeNanos()-copy.elapsedRealtimeNanos)/1000000).coerceAtLeast(0)
            if(age>86400000 || !copy.hasAccuracy())return@enqueue
            val at=Instant.ofEpochMilli(copy.time)
            @Suppress("DEPRECATION") val mock=if(Build.VERSION.SDK_INT>=31)copy.isMock else copy.isFromMockProvider
            SchoolCollector(this).sensor(base("location",at).put("latitude",copy.latitude).put("longitude",copy.longitude).put("accuracy_m",copy.accuracy.toDouble()).put("age_ms",age).put("provider",copy.provider?:"unknown").put("permission",if(precise)"precise" else "approximate").put("mock",mock))
        }
    }
    override fun onSensorChanged(event:SensorEvent){
        if(event.sensor.type!=Sensor.TYPE_STEP_COUNTER || event.values.isEmpty())return
        val count=event.values[0].toLong();val at=Instant.now();val millis=SystemClock.elapsedRealtime()
        if(millis-lastStep<60000)return
        lastStep=millis
        enqueue{if(checkSelfPermission(Manifest.permission.ACTIVITY_RECOGNITION)==0)SchoolCollector(this).sensor(base("steps",at).put("counter",count).put("boot_id",boot).put("provider","TYPE_STEP_COUNTER").put("permission","activity"))}
    }
    override fun onAccuracyChanged(sensor:Sensor?,accuracy:Int){}
    override fun onDestroy(){
        destroyed=true;running=false;locationRunning=false;stepsRunning=false
        try{fused?.removeLocationUpdates(callback);manager.removeUpdates(listener)}catch(_:SecurityException){}
        sensors.unregisterListener(this);vault.put("sensor_running","false");io.shutdown();super.onDestroy()
    }
}
