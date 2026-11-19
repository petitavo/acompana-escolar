package pe.upc.acompana.acompana_escolar

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.room.*
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory

/** AES-GCM key lives in Android Keystore. SharedPreferences stores ciphertext only. */
class Vault(context: Context) {
    private val prefs=context.getSharedPreferences("encrypted_lab_config",Context.MODE_PRIVATE)
    private val alias="acompana-lab-key-v1"
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        if(!store.containsAlias(alias)){
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply{
                init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            }.generateKey()
        }
        return store.getKey(alias,null) as SecretKey
    }
    fun put(name:String,value:String){
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key())
        val bytes=cipher.iv+cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        check(prefs.edit().putString(name,Base64.encodeToString(bytes,Base64.NO_WRAP)).commit())
    }
    fun get(name:String,default:String=""):String {
        val encoded=prefs.getString(name,null)?:return default
        val bytes=Base64.decode(encoded,Base64.NO_WRAP)
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,bytes.copyOfRange(0,12)))
        return String(cipher.doFinal(bytes.copyOfRange(12,bytes.size)),Charsets.UTF_8)
    }
    fun databasePassphrase():ByteArray {
        var encoded=get("database_passphrase")
        if(encoded.isEmpty()){val bytes=ByteArray(32);SecureRandom().nextBytes(bytes);encoded=Base64.encodeToString(bytes,Base64.NO_WRAP);put("database_passphrase",encoded)}
        return Base64.decode(encoded,Base64.NO_WRAP)
    }
    fun clearParticipation(){
        val edit=prefs.edit()
        prefs.all.keys.filter{it!="database_passphrase"}.forEach{edit.remove(it)}
        check(edit.commit())
    }
    fun clear(){check(prefs.edit().clear().commit())}
}
@Entity(tableName="outbox",indices=[Index(value=["fingerprint"],unique=true)])
data class Packet(@PrimaryKey val id:String,val kind:String,val path:String,val body:String,val createdAt:Long,val fingerprint:String?=null,val state:String="pending",val error:String?=null)
@Dao interface PacketDao {
    @Insert(onConflict=OnConflictStrategy.IGNORE) fun insert(row:Packet):Long
    @Query("SELECT * FROM outbox WHERE id=:id") fun packet(id:String):Packet?
    @Query("SELECT * FROM outbox WHERE state='pending' AND kind=:kind ORDER BY createdAt,id LIMIT :limit") fun pending(kind:String,limit:Int=500):List<Packet>
    @Query("SELECT * FROM outbox WHERE kind='participation' AND state='pending' ORDER BY createdAt,id LIMIT 100") fun policies():List<Packet>
    @Query("UPDATE outbox SET state='confirmed',error=NULL WHERE id IN (:ids)") fun confirm(ids:List<String>)
    @Query("UPDATE outbox SET state='rejected',error=:reason WHERE id=:id") fun reject(id:String,reason:String)
    @Query("UPDATE outbox SET state='cancelled',error='participation_paused' WHERE state='pending' AND kind IN ('event','capture','location','steps','summary')") fun cancelCapture()
    @Query("UPDATE outbox SET state='cancelled' WHERE kind=:kind AND state='pending'") fun cancelKind(kind:String)
    @Query("SELECT * FROM outbox WHERE kind IN ('local_location','local_steps') AND createdAt>=:since ORDER BY createdAt,id") fun localSensors(since:Long):List<Packet>
    @Query("SELECT * FROM outbox WHERE kind='local_screen' AND createdAt>=:from AND createdAt<=:to ORDER BY createdAt,id") fun localScreen(from:Long,to:Long):List<Packet>
    @Query("DELETE FROM outbox WHERE kind='local_screen' AND createdAt<=:until") fun dropLocalScreen(until:Long)
    @Query("SELECT COUNT(*) FROM outbox WHERE state='pending'") fun countPending():Int
    @Query("SELECT COUNT(*) FROM outbox WHERE kind='event'") fun countEvents():Int
    @Query("SELECT COUNT(*) FROM outbox WHERE state='rejected'") fun countRejected():Int
    @Query("SELECT COUNT(*) FROM outbox WHERE state='expired'") fun countExpired():Int
    @Query("SELECT COUNT(*) FROM outbox WHERE state='pending' AND kind IN ('school_form','school_support','school_correction')") fun countPendingForms():Int
    // A04: retention of raw sensor captures is SEPARATE from delivery of pending
    // questionnaires / support / participation / deletion.
    //  1. expireStaleCaptures: a stale *capture* pending past retention is marked
    //     'expired' with a reason and its raw body is wiped — a durable, visible
    //     tombstone (never a silent delete, never marked as received).
    //  2. purgeDelivered: only rows that actually reached the server (confirmed) or
    //     were voided (cancelled) are removed once past retention.
    // Expired capture metadata remains until explicit dismissal, including after long absences.
    // Pending and rejected form/support packets are NEVER deleted here; the student
    // resolves a rejection explicitly via dismiss().
    @Query("UPDATE outbox SET state='expired',error='capture_window_expired',body='' WHERE createdAt < :before AND state IN ('pending','local') AND kind IN ('event','capture','location','steps','summary','local_location','local_steps')") fun expireStaleCaptures(before:Long)
    @Query("DELETE FROM outbox WHERE createdAt < :before AND state IN ('confirmed','cancelled')") fun purgeDelivered(before:Long)
    @Query("DELETE FROM outbox WHERE id=:id AND state IN ('rejected','expired')") fun dismiss(id:String):Int
    @Query("SELECT * FROM outbox WHERE state IN ('pending','rejected','expired') ORDER BY createdAt DESC LIMIT 200") fun deliveryLog():List<Packet>
    @Query("DELETE FROM outbox") fun clear()
}
@Database(entities=[Packet::class],version=1,exportSchema=false)
abstract class LabDatabase:RoomDatabase(){abstract fun packets():PacketDao
    companion object {
        @Volatile private var instance:LabDatabase?=null
        fun get(context:Context):LabDatabase=instance?:synchronized(this){instance?:run{
            System.loadLibrary("sqlcipher")
            Room.databaseBuilder(context.applicationContext,LabDatabase::class.java,"lab-encrypted.db")
                .openHelperFactory(SupportOpenHelperFactory(Vault(context).databasePassphrase())).build().also{instance=it}
        }}
    }
}
