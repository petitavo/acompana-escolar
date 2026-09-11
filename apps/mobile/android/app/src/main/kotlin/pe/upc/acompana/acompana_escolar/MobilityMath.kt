package pe.upc.acompana.acompana_escolar

import org.json.JSONObject
import org.json.JSONArray
import java.time.*
import kotlin.math.*

/** Same version, filters and temporal weighting as backend app/mobility.py. */
object MobilityMath {
    const val VERSION="mobility-v1.0"
    fun distance(a:Pair<Double,Double>,b:Pair<Double,Double>):Double {
        val la=Math.toRadians(a.first);val lb=Math.toRadians(b.first)
        val h=sin((lb-la)/2).pow(2)+cos(la)*cos(lb)*sin(Math.toRadians(b.second-a.second)/2).pow(2)
        return 6371008.8*2*asin(sqrt(h.coerceIn(0.0,1.0)))
    }
    private fun coord(p:JSONObject)=p.getDouble("latitude") to p.getDouble("longitude")
    private fun at(p:JSONObject)=Instant.parse(p.getString("occurred_at")).toEpochMilli()
    private fun round(v:Double,n:Int)=kotlin.math.round(v*10.0.pow(n))/10.0.pow(n)
    fun summary(samples:List<JSONObject>,day:String,zone:String,home:JSONObject?=null,cutoff:Instant?=null):JSONObject {
        val d=LocalDate.parse(day);val z=ZoneId.of(zone)
        val start=d.atStartOfDay(z).toInstant().toEpochMilli();val end=d.plusDays(1).atStartOfDay(z).toInstant().toEpochMilli();val cut=cutoff?.toEpochMilli()?:end
        val effective=min(end,cut);val duration=max(0.0,(effective-start)/60000.0)
        val rows=samples.filter{at(it)>=start-1800000 && at(it)<=min(cut,end+1800000)}.sortedWith(compareBy({at(it)},{it.optString("id")}))
        val excluded=JSONArray()
        val points=rows.filter{it.getString("kind")=="location"}.filter{
            val reason=when {it.getDouble("accuracy_m")>100->"low_accuracy";it.optLong("age_ms")>600000->"stale_fix";it.optString("permission")!="precise"->"approximate_permission";else->null}
            if(reason!=null)excluded.put(JSONObject().put("id",it.optString("id")).put("reason",reason));reason==null
        }
        val weights=DoubleArray(points.size);val segments=mutableListOf<Triple<Int,Int,Double>>()
        var meters=0.0;var observed=0.0;var inside=0.0;var outside=0.0;var gaps=0
        for(i in 0 until points.size-1){
            val a=points[i];val b=points[i+1];val gap=(at(b)-at(a))/60000.0
            val clipped=max(0.0,(min(at(b),effective)-max(at(a),start))/60000.0)
            if(a.optString("segment_id")!=b.optString("segment_id")){gaps++;continue}
            if(clipped<=0 || gap<=0)continue
            if(gap>30){gaps++;continue}
            val distance=distance(coord(a),coord(b))
            if(distance/(gap/60)/1000>200){excluded.put(JSONObject().put("id",b.optString("id")).put("reason","incompatible_jump"));continue}
            observed+=clipped;meters+=distance*clipped/gap;weights[i]+=clipped/2;weights[i+1]+=clipped/2;segments.add(Triple(i,i+1,clipped))
            if(home!=null){val ha=distance(coord(a),coord(home))<=home.optDouble("radius_m",150.0);val hb=distance(coord(b),coord(home))<=home.optDouble("radius_m",150.0);if(ha&&hb)inside+=clipped else if(!ha&&!hb)outside+=clipped}
        }
        var radius:Double?=null
        if(observed>0){
            var x=0.0;var y=0.0;var zz=0.0
            points.forEachIndexed{i,p->val lat=Math.toRadians(p.getDouble("latitude"));val lon=Math.toRadians(p.getDouble("longitude"));x+=weights[i]*cos(lat)*cos(lon);y+=weights[i]*cos(lat)*sin(lon);zz+=weights[i]*sin(lat)}
            val center=Math.toDegrees(atan2(zz,sqrt(x*x+y*y))) to Math.toDegrees(atan2(y,x))
            radius=sqrt(points.indices.sumOf{weights[it]*distance(coord(points[it]),center).pow(2)}/weights.sum())
        }
        val neighbours=points.map{p->points.indices.filter{distance(coord(p),coord(points[it]))<=200}}
        val labels=IntArray(points.size){-1};val visited=mutableSetOf<Int>();var cluster=0
        for(i in points.indices){
            if(!visited.add(i) || neighbours[i].size<3)continue
            labels[i]=cluster;val queue=ArrayDeque(neighbours[i])
            while(queue.isNotEmpty()){val j=queue.removeLast();if(visited.add(j)&&neighbours[j].size>=3)queue.addAll(neighbours[j].filter{it !in visited});if(labels[j]==-1)labels[j]=cluster}
            cluster++
        }
        val dwell=mutableMapOf<Int,Double>()
        segments.forEach{(a,b,m)->if(labels[a]>=0&&labels[a]==labels[b])dwell[labels[a]]=(dwell[labels[a]]?:0.0)+m}
        val total=dwell.values.sum();val entropy=if(total>=120)-dwell.values.sumOf{(it/total)*ln(it/total)} else null
        val steps=rows.filter{it.getString("kind")=="steps"};var count=0L;var stepMinutes=0.0;var resets=0
        steps.zipWithNext().forEach{(a,b)->val ta=at(a);val tb=at(b);val gap=(tb-ta)/60000.0
            if(a.optString("segment_id")==b.optString("segment_id")&&ta>=start&&ta<tb&&tb<=effective&&gap<=30){if(a.optString("boot_id")!=b.optString("boot_id")||b.getLong("counter")<a.getLong("counter"))resets++ else {count+=b.getLong("counter")-a.getLong("counter");stepMinutes+=gap}}
        }
        val values=linkedMapOf("observed_distance_m" to if(observed>0)meters else null,"radius_gyration_m" to radius,"home_minutes" to if(home!=null&&observed>0)inside else null,"place_entropy" to entropy,"observed_steps" to if(stepMinutes>0)count.toDouble() else null)
        val units=listOf("m","m","min","nats","pasos");val features=JSONObject()
        values.entries.forEachIndexed{i,(name,value)->
            val minutes=if(name=="observed_steps")stepMinutes else observed;val coverage=if(duration>0)min(1.0,minutes/duration) else 0.0;val eligible=value!=null&&coverage>=0.8&&cut>=end
            features.put(name,JSONObject().put("value",value?.let{round(it,4)}?:JSONObject.NULL).put("unit",units[i]).put("state",if(value==null)"missing" else if(eligible)"observed" else "partial").put("eligible",eligible).put("operational_coverage",round(coverage,4)).put("observed_minutes",round(minutes,3)).put("window_start",Instant.ofEpochMilli(start).toString()).put("window_end",Instant.ofEpochMilli(end).toString()))
        }
        return JSONObject().put("version",VERSION).put("day",day).put("features",features).put("quality",JSONObject().put("observed_minutes",round(observed,3)).put("gap_count",gaps).put("excluded_count",excluded.length()).put("step_resets",resets).put("inside_minutes",if(home!=null&&observed>0)round(inside,3) else JSONObject.NULL).put("outside_minutes",if(home!=null&&observed>0)round(outside,3) else JSONObject.NULL).put("uncertain_minutes",round(max(0.0,duration-inside-outside),3)).put("period_minutes",duration).put("cluster_observed_minutes",round(total,3)))
            .put("lineage",JSONObject().put("point_ids",JSONArray(rows.map{it.optString("id")})).put("excluded",excluded).put("parameters",JSONObject("{\"max_accuracy_m\":100,\"max_age_ms\":600000,\"max_gap_minutes\":30,\"max_speed_kmh\":200,\"home_radius_m\":150,\"dbscan_eps_m\":200,\"dbscan_min_samples\":3,\"minimum_observed_minutes\":120}")))
            .put("notice","Estimaciones del tiempo y trayectos observados con el teléfono; las brechas no se rellenan. No mide aislamiento, sueño ni actividad física total.")
    }
}
