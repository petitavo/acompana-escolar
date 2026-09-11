package pe.upc.acompana.acompana_escolar
import android.app.*
import android.content.*
import android.os.Build
import androidx.core.app.NotificationCompat
import org.json.JSONObject
import java.time.*
object SchoolReminders {
    fun show(context:Context){
        val v=Vault(context);val h=JSONObject(v.get("school_home","{}"));val p=h.optJSONObject("policy")?:return
        if(!p.optBoolean("reminders",true)||!h.optBoolean("questionnaire_enabled")||h.optJSONObject("authorization")?.optBoolean("ready")!=true)return
        if(Build.VERSION.SDK_INT>=33&&context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=0)return
        val now=LocalDateTime.now();val day=now.toLocalDate().toString()
        if(v.get("reminded_day")==day||now.toLocalTime()<LocalTime.parse(p.optString("reminder_time","17:00")))return
        if(SchoolTime.instant(h.getString("next_questionnaire"))>Instant.now())return
        val nm=context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel("school-reminders","Recordatorios personales",NotificationManager.IMPORTANCE_DEFAULT))
        val open=PendingIntent.getActivity(context,3,Intent(context,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE)
        nm.notify(42,NotificationCompat.Builder(context,"school-reminders").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("Acompaña Escolar").setContentText("Tienes una actividad disponible cuando puedas revisarla").setContentIntent(open).setAutoCancel(true).build());v.put("reminded_day",day)
    }
}
