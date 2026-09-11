package pe.upc.acompana.acompana_escolar

import org.junit.Assert.*
import org.junit.Test
import java.time.format.DateTimeParseException

class SchoolTimeTest {
    @Test fun apiAndAndroidInstantsAgreeWithFractionalPrecision() {
        val saved=SchoolTime.instant("2026-09-07T02:18:35.959931+00:00")
        assertEquals(1788747515959L,saved.toEpochMilli())
        assertEquals(saved,SchoolTime.instant("2026-09-07T02:18:35.959931Z"))
        assertEquals(saved,SchoolTime.instant("2026-09-06T21:18:35.959931-05:00"))
        assertEquals(saved,SchoolTime.instant("2026-09-07T07:48:35.959931+05:30"))
        assertEquals(959931000,saved.nano)
    }
    @Test(expected=DateTimeParseException::class) fun timezoneIsRequired() {
        SchoolTime.instant("2026-09-07T02:18:35")
    }
}
