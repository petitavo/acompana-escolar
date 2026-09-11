package pe.upc.acompana.acompana_escolar

import java.time.Instant
import java.time.OffsetDateTime

/** Android 10/11 ISO_INSTANT rejects offsets such as +00:00 returned by the API. */
object SchoolTime {
    fun instant(value:String):Instant = OffsetDateTime.parse(value).toInstant()
}
