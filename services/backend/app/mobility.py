"""mobility-v1.0. Deterministic contract also implemented in Android MobilityMath.

Observed segments only: no interpolation through gaps, no inference of an address.
The contract fixtures exercise the same numbers in Python and Kotlin.
"""
from math import radians, sin, cos, atan2, sqrt, asin, log
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from .db import utc

VERSION = "mobility-v1.1"
LEGACY_VERSIONS = {"mobility-v1.0"}
PARAMETERS = {"max_accuracy_m": 100, "max_age_ms": 600000, "max_gap_minutes": 30, "max_speed_kmh": 200, "home_radius_m": 150, "dbscan_eps_m": 200, "dbscan_min_samples": 3, "minimum_observed_minutes": 120}
FEATURES = {"observed_distance_m": ("m", 200), "radius_gyration_m": ("m", 100), "home_minutes": ("min", 30), "place_entropy": ("nats", 0.1), "observed_steps": ("pasos", 100), "school_minutes": ("min", 30)}
# mobility-v1.0 no tenía asistencia; se sigue aceptando de teléfonos sin actualizar.
LEGACY_FEATURES = [k for k in FEATURES if k != "school_minutes"]


def haversine(a, b):
    lat1, lat2 = radians(a[0]), radians(b[0])
    dlat, dlon = lat2 - lat1, radians(b[1] - a[1])
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371008.8 * 2 * asin(min(1, sqrt(max(0, h))))


def clusters(points):
    """DBSCAN with geodesic meters; only the past samples supplied to this call."""
    neighbours = [[j for j, b in enumerate(points) if haversine((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"])) <= PARAMETERS["dbscan_eps_m"]] for a in points]
    labels = [-1] * len(points)
    visited = set()
    cluster = 0
    for i in range(len(points)):
        if i in visited:
            continue
        visited.add(i)
        if len(neighbours[i]) < PARAMETERS["dbscan_min_samples"]:
            continue
        labels[i] = cluster
        queue = list(neighbours[i])
        while queue:
            j = queue.pop()
            if j not in visited:
                visited.add(j)
                if len(neighbours[j]) >= PARAMETERS["dbscan_min_samples"]:
                    queue.extend(k for k in neighbours[j] if k not in visited)
            if labels[j] == -1:
                labels[j] = cluster
        cluster += 1
    return labels


def school_window(school, d, tz):
    """Horario de clases del día (UTC) si el día es lectivo; None en fines de semana o sin zona."""
    if not school or d.weekday() not in school.get("days", [0, 1, 2, 3, 4]):
        return None
    a = datetime.combine(d, time.fromisoformat(school.get("start", "07:30")), tz).astimezone(timezone.utc)
    b = datetime.combine(d, time.fromisoformat(school.get("end", "13:30")), tz).astimezone(timezone.utc)
    return (a, b) if b > a else None


def day_summary(samples, day, zone="America/Lima", home=None, cutoff=None, school=None):
    d = date.fromisoformat(day)
    tz = ZoneInfo(zone)
    start = datetime.combine(d, time.min, tz).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), time.min, tz).astimezone(timezone.utc)
    cutoff = utc(cutoff) if cutoff else end
    effective_end = min(end, cutoff)
    duration = max(0, (effective_end - start).total_seconds() / 60)
    rows = sorted([r for r in samples if start - timedelta(minutes=30) <= utc(r["occurred_at"]) <= min(cutoff, end + timedelta(minutes=30))], key=lambda r: (utc(r["occurred_at"]), r.get("id", "")))
    points, excluded = [], []
    for r in rows:
        if r["kind"] != "location":
            continue
        reason = "low_accuracy" if r["accuracy_m"] > PARAMETERS["max_accuracy_m"] else "stale_fix" if r.get("age_ms", 0) > PARAMETERS["max_age_ms"] else "approximate_permission" if r.get("permission") != "precise" else None
        if reason:
            excluded.append({"id": r.get("id"), "reason": reason})
        else:
            points.append(r)
    weights = [0.0] * len(points)
    distance, observed, inside, outside, gaps = 0.0, 0.0, 0.0, 0.0, 0
    segments = []
    class_hours = school_window(school, d, tz)
    school_observed, school_inside = 0.0, 0.0
    for i, (a, b) in enumerate(zip(points, points[1:])):
        ta, tb = utc(a["occurred_at"]), utc(b["occurred_at"])
        gap = (tb - ta).total_seconds() / 60
        clipped = max(0, (min(tb, effective_end) - max(ta, start)).total_seconds() / 60)
        if a.get("segment_id") != b.get("segment_id"):
            gaps += 1
            continue
        if clipped <= 0 or gap <= 0:
            continue
        if gap > PARAMETERS["max_gap_minutes"]:
            gaps += 1
            continue
        meters = haversine((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"]))
        if meters / (gap / 60) / 1000 > PARAMETERS["max_speed_kmh"]:
            excluded.append({"id": b.get("id"), "reason": "incompatible_jump"})
            continue
        observed += clipped
        # A boundary-crossing distance is allocated in proportion to its observed
        # duration. This is an explicit engineering approximation, not a route.
        distance += meters * clipped / gap
        weights[i] += clipped / 2
        weights[i + 1] += clipped / 2
        segments.append((i, i + 1, clipped))
        if class_hours:
            ws, we = class_hours
            within = max(0, (min(tb, we, effective_end) - max(ta, ws)).total_seconds() / 60)
            if within > 0:
                school_observed += within
                if all(haversine((v["latitude"], v["longitude"]), (school["latitude"], school["longitude"])) <= school.get("radius_m", 150) for v in (a, b)):
                    school_inside += within
        if home:
            radius = home.get("radius_m", 150)
            at_home = [haversine((v["latitude"], v["longitude"]), (home["latitude"], home["longitude"])) <= radius for v in (a, b)]
            if all(at_home):
                inside += clipped
            elif not any(at_home):
                outside += clipped
    radius = None
    if observed > 0:
        x = sum(w * cos(radians(p["latitude"])) * cos(radians(p["longitude"])) for p, w in zip(points, weights))
        y = sum(w * cos(radians(p["latitude"])) * sin(radians(p["longitude"])) for p, w in zip(points, weights))
        z = sum(w * sin(radians(p["latitude"])) for p, w in zip(points, weights))
        center = (atan2(z, sqrt(x * x + y * y)) * 180 / 3.141592653589793, atan2(y, x) * 180 / 3.141592653589793)
        radius = sqrt(sum(w * haversine((p["latitude"], p["longitude"]), center) ** 2 for p, w in zip(points, weights)) / sum(weights))
    labels = clusters(points)
    dwell = {}
    for a, b, minutes in segments:
        if labels[a] >= 0 and labels[a] == labels[b]:
            dwell[labels[a]] = dwell.get(labels[a], 0) + minutes
    dwell_total = sum(dwell.values())
    entropy = -sum((v / dwell_total) * log(v / dwell_total) for v in dwell.values()) if dwell_total >= PARAMETERS["minimum_observed_minutes"] else None
    step_rows = [r for r in rows if r["kind"] == "steps"]
    step_count, step_minutes, resets = 0, 0.0, 0
    for a, b in zip(step_rows, step_rows[1:]):
        ta, tb = utc(a["occurred_at"]), utc(b["occurred_at"])
        gap = (tb - ta).total_seconds() / 60
        # A counter delta crossing midnight cannot be split without inventing
        # steps. Count only pairs entirely within this civil day.
        if a.get("segment_id") != b.get("segment_id") or not start <= ta < tb <= effective_end or gap > 30:
            continue
        if a.get("boot_id") != b.get("boot_id") or b["counter"] < a["counter"]:
            resets += 1
            continue
        step_count += b["counter"] - a["counter"]
        step_minutes += gap
    coverage = min(1, observed / duration) if duration else 0
    values = {"observed_distance_m": distance if observed else None, "radius_gyration_m": radius, "home_minutes": inside if home and observed else None, "place_entropy": entropy, "observed_steps": step_count if step_minutes else None, "school_minutes": school_inside if class_hours and school_observed else None}
    class_minutes = (class_hours[1] - class_hours[0]).total_seconds() / 60 if class_hours else 0
    features = {}
    for name, value in values.items():
        if name == "school_minutes":
            # Asistencia: basta con observar la mitad del horario de clases (el GPS falla bajo techo).
            # La cobertura se expresa sobre el día, como las demás variables; la elegibilidad
            # se decide sobre el horario de clases.
            minutes = school_observed
            cov = min(1, minutes / duration) if duration else 0
            eligible = value is not None and bool(class_minutes) and minutes >= 0.5 * class_minutes and cutoff >= end
        else:
            minutes = step_minutes if name == "observed_steps" else observed
            cov = min(1, minutes / duration) if duration else 0
            eligible = value is not None and cov >= 0.8 and cutoff >= end
        features[name] = {"value": round(value, 4) if value is not None else None, "unit": FEATURES[name][0], "state": "missing" if value is None else "observed" if eligible else "partial", "eligible": eligible, "operational_coverage": round(cov, 4), "observed_minutes": round(minutes, 3), "window_start": start.isoformat(), "window_end": end.isoformat()}
    return {"version": VERSION, "day": day, "features": features, "quality": {"observed_minutes": round(observed, 3), "gap_count": gaps, "excluded_count": len(excluded), "step_resets": resets, "inside_minutes": round(inside, 3) if home and observed else None, "outside_minutes": round(outside, 3) if home and observed else None, "uncertain_minutes": round(max(0, duration - inside - outside), 3), "period_minutes": duration, "cluster_observed_minutes": round(dwell_total, 3), "school_observed_minutes": round(school_observed, 3) if class_hours else None}, "lineage": {"point_ids": [p.get("id") for p in rows], "excluded": excluded, "parameters": PARAMETERS}, "notice": "Estimaciones del tiempo y trayectos observados con el teléfono; las brechas no se rellenan. No mide aislamiento, sueño ni actividad física total. La asistencia es el tiempo observado dentro de la zona del colegio en horario de clases."}
