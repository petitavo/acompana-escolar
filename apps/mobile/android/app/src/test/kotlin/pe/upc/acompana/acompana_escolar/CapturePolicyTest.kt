package pe.upc.acompana.acompana_escolar
import org.junit.Assert.*
import org.junit.Test
class CapturePolicyTest {
    @Test fun resumeNeverQueriesPausedPeriod(){
        val resumed=1_000_000L
        assertEquals(resumed,CapturePolicy.start(resumed,100_000,resumed+30_000))
        assertFalse(CapturePolicy.permitted(resumed-1,resumed,resumed,resumed+100))
        assertTrue(CapturePolicy.permitted(resumed+1,resumed,resumed,resumed+100))
    }
    @Test fun overlapBoundedAndFailuresDistinguished(){
        assertEquals(140_000L,CapturePolicy.start(100_000,200_000,250_000))
        assertFalse(CapturePolicy.terminalHttp(503))
        assertTrue(CapturePolicy.terminalHttp(422))
    }
}
