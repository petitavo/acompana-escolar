package pe.upc.acompana.acompana_escolar
import org.junit.Test
import org.junit.Assert.*
import org.json.*
class MobilityMathTest {
    @Test fun sharedContract(){
        val cases=JSONArray(java.io.File("../../../../packages/contracts/fixtures/mobility-v1.json").readText())
        for(i in 0 until cases.length()){
            val c=cases.getJSONObject(i);val rows=c.getJSONArray("samples")
            val result=MobilityMath.summary((0 until rows.length()).map{rows.getJSONObject(it)},c.getString("day"),c.getString("zone"),c.optJSONObject("home"))
            val expected=c.getJSONObject("expected")
            for(key in listOf("features","quality"))compare(c.getString("name")+"."+key,expected.getJSONObject(key),result.getJSONObject(key))
        }
    }
    private fun compare(path:String,a:JSONObject,b:JSONObject){
        for(key in a.keys()){
            val av=a.get(key);val bv=b.get(key)
            if(av is JSONObject)compare("$path.$key",av,bv as JSONObject)
            else if(key in listOf("window_start","window_end"))assertEquals(java.time.Instant.parse(av.toString()),java.time.Instant.parse(bv.toString()))
            else if(av is Number)assertEquals("$path.$key",av.toDouble(),(bv as Number).toDouble(),.00015)
            else assertEquals("$path.$key",av,bv)
        }
    }
}
