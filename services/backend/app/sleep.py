"""sleep-proxy-v1.0. Estimación del descanso a partir del uso de pantalla (proxy P1).

El celular no mide sueño. Lo que sí se puede observar es el periodo nocturno más largo
sin usar el teléfono, que en estudios con universitarios se acerca al sueño real
(p. ej., Abdullah et al., 2014; StudentLife). Reglas:

- Ventana de la noche: 20:00 del día anterior a 12:00 del día indicado (se asigna al día
  en que la persona despierta).
- Usos de menos de 2 minutos (mirar la hora, apagar una alarma) no cortan el descanso.
- Solo cuentan pausas que empiezan y terminan con un uso observado: si no hubo uso antes
  o después, no se sabe cuándo empezó o terminó y no se inventa.
- La pausa debe estar cubierta por consultas exitosas de uso (el permiso estaba activo);
  si no, el dato queda como parcial y no entra al análisis.
"""
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

VERSION = "sleep-proxy-v1.0"
REFERENCE = "18:00 del día anterior"
# unidad, piso de escala para la desviación robusta
FEATURES = {
    "sleep_duration_min": ("min", 30),
    "sleep_onset_min": ("min desde 18:00", 30),
    "wake_min": ("min desde 18:00", 30),
}
PARAMETERS = {"window_start": "20:00", "window_end": "12:00", "ignore_use_shorter_than_min": 2, "minimum_rest_min": 120, "minimum_coverage": 0.8}


def _overlap(spans, a, b):
    total = 0.0
    for s, e in spans:
        lo, hi = max(s, a), min(e, b)
        if hi > lo:
            total += (hi - lo).total_seconds()
    return total


def sleep_features(spans, windows, day, zone="America/Lima", cutoff=None):
    """spans: usos interactivos [(inicio, fin)] en UTC; windows: periodos con consulta
    exitosa y permiso activo. Devuelve el mismo formato que features.build_day."""
    tz = ZoneInfo(zone)
    d = date.fromisoformat(day)
    a = datetime.combine(d - timedelta(days=1), time(20), tz).astimezone(timezone.utc)
    b = datetime.combine(d, time(12), tz).astimezone(timezone.utc)
    ref = datetime.combine(d - timedelta(days=1), time(18), tz).astimezone(timezone.utc)
    closed = cutoff is None or cutoff >= b
    coverage = _overlap(windows, a, b) / (b - a).total_seconds()
    uses = sorted((max(s, a), min(e, b)) for s, e in spans if e > a and s < b and (e - s).total_seconds() >= PARAMETERS["ignore_use_shorter_than_min"] * 60)
    best = None
    for (s1, e1), (s2, _) in zip(uses, uses[1:]):
        if s2 > e1 and (best is None or s2 - e1 > best[1] - best[0]):
            best = (e1, s2)
    values = {"sleep_duration_min": None, "sleep_onset_min": None, "wake_min": None}
    state, eligible = "missing", False
    if closed and coverage > 0 and best:
        onset, wake = best
        gap_coverage = _overlap(windows, onset, wake) / max(1.0, (wake - onset).total_seconds())
        duration = (wake - onset).total_seconds() / 60
        values = {
            "sleep_duration_min": round(duration, 1),
            "sleep_onset_min": round((onset - ref).total_seconds() / 60, 1),
            "wake_min": round((wake - ref).total_seconds() / 60, 1),
        }
        eligible = coverage >= PARAMETERS["minimum_coverage"] and gap_coverage >= 0.95 and duration >= PARAMETERS["minimum_rest_min"]
        state = "observed" if eligible else "partial"
    result = {}
    for name, (unit, _) in FEATURES.items():
        result[name] = {
            "value": values[name], "unit": unit, "state": state, "eligible": eligible,
            "operational_coverage": round(coverage, 4),
            "window_start": a.isoformat(), "window_end": b.isoformat(),
        }
    return result


def clock(minutes_from_18):
    """Convierte 'min desde 18:00' a hora local legible (HH:MM)."""
    if minutes_from_18 is None:
        return None
    total = (18 * 60 + int(round(minutes_from_18))) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"
