package pe.upc.acompana.acompana_escolar

/** Pure capture boundaries; used by Android collection and JVM regression tests. */
object CapturePolicy {
    fun start(intervalStart:Long,cursor:Long,now:Long):Long = maxOf(intervalStart,cursor-60_000,now-86_400_000)
    fun permitted(timestamp:Long,intervalStart:Long,queryStart:Long,queryEnd:Long):Boolean = timestamp>=intervalStart && timestamp>=queryStart && timestamp<=queryEnd
    fun terminalHttp(code:Int):Boolean = code in listOf(403,409,422)
}
