package pe.upc.acompana.acompana_escolar
import android.app.*
import android.content.*
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONObject
import java.util.UUID

object SchoolPush {
    fun configure(context:Context){
        if(BuildConfig.FIREBASE_APP_ID.isEmpty() || BuildConfig.FIREBASE_API_KEY.isEmpty() || BuildConfig.FIREBASE_PROJECT_ID.isEmpty() || BuildConfig.FIREBASE_SENDER_ID.isEmpty())return
        val vault=Vault(context)
        if(vault.get("token").isEmpty() || JSONObject(vault.get("school_home","{}")).optJSONObject("policy")?.optBoolean("reminders",true)!=true)return
        if(Build.VERSION.SDK_INT>=33 && context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=0)return
        if(FirebaseApp.getApps(context).isEmpty())FirebaseApp.initializeApp(context,FirebaseOptions.Builder().setApplicationId(BuildConfig.FIREBASE_APP_ID).setApiKey(BuildConfig.FIREBASE_API_KEY).setProjectId(BuildConfig.FIREBASE_PROJECT_ID).setGcmSenderId(BuildConfig.FIREBASE_SENDER_ID).build())
        FirebaseMessaging.getInstance().token.addOnSuccessListener{vault.put("pending_push_token",it)}
    }
}
class SchoolMessagingService:FirebaseMessagingService(){
    override fun onNewToken(token:String){Vault(this).put("pending_push_token",token)}
    override fun onMessageReceived(message:RemoteMessage){
        val id=message.data["notification_id"]?:return
        try{UUID.fromString(id)}catch(_:Exception){return}
        val vault=Vault(this)
        if(vault.get("token").isEmpty())return
        // A durable receipt is queued only when Android actually invokes this callback.
        val db=LabDatabase.get(this)
        db.packets().insert(Packet(UUID.randomUUID().toString(),"school_receipt","/school/notifications/$id/delivered","{}",System.currentTimeMillis()))
        if(JSONObject(vault.get("school_home","{}")).optJSONObject("policy")?.optBoolean("reminders",true)!=true)return
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=0)return
        val nm=getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel("school-updates","Novedades del equipo",NotificationManager.IMPORTANCE_DEFAULT))
        val open=PendingIntent.getActivity(this,4,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        nm.notify(id.hashCode(),NotificationCompat.Builder(this,"school-updates").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("Acompaña Escolar").setContentText("Tienes una novedad. Abre la aplicación para verla.").setAutoCancel(true).setContentIntent(open).build())
    }
}
