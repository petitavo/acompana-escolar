from datetime import timedelta, date
from zoneinfo import ZoneInfo
from typing import Literal
from uuid import UUID
import json
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import Field, AwareDatetime, StrictBool, field_validator
from sqlalchemy import select
from .db import Device, Job, now, utc, public, Interval
from .school_db import SensorPoint, MobilityDay, Institution
from .school_schemas import SensorBatch, HomeZone, Strict
from .school_core import student_actor, sensor_allowed, settings, profile, access, member
from .security import identity, database, digest, audit, once
from .mobility import VERSION, FEATURES, LEGACY_VERSIONS, LEGACY_FEATURES, school_window

router = APIRouter(prefix="/api/v1/school", tags=["Sensores autorizados"])


@router.post("/me/sensors")
def ingest(body: SensorBatch, actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor, True)
    d = actor["device"]
    accepted, duplicates, rejected = [], [], []
    for point in body.points:
        pid = str(point.id)
        value = point.model_dump(mode="json")
        signature = digest(json.dumps(value, sort_keys=True))
        old = db.get(SensorPoint, pid)
        reason = None
        if old:
            if old.device_id == d.id and old.signature == signature:
                duplicates.append(pid)
                continue
            reason = "id_conflict"
        elif point.occurred_at > now() + timedelta(minutes=5) or point.occurred_at < now() - timedelta(days=7):
            reason = "outside_retention_or_future"
        elif not sensor_allowed(db, d, point.kind, point.occurred_at):
            reason = "permission_or_authorization_missing"
        elif point.kind == "location" and not p.policy.get("raw_location_upload"):
            reason = "raw_location_upload_disabled"
        if reason:
            rejected.append({"id": pid, "reason": reason})
            continue
        db.add(SensorPoint(id=pid, device_id=d.id, kind=point.kind, occurred_at=point.occurred_at, signature=signature, detail=value))
        accepted.append(pid)
    if accepted and p.policy.get("raw_location_upload"):
        from worker.school import queue_received_days
        queue_received_days(db, d, [point.occurred_at for point in body.points if str(point.id) in accepted], "school_mobility")
    d.detail = {**d.detail, "last_sensor_sync": now().isoformat(), "sensor_points_accepted": len(accepted)}
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


@router.put("/me/home-zone")
def home_zone(body: HomeZone, actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor, True)
    if not p.policy.get("raw_location_upload"):
        raise HTTPException(409, "La zona se conserva solo en tu teléfono mientras no compartas coordenadas")
    p.policy = {**p.policy, "home_zone": {**body.model_dump(), "provided_at": now().isoformat(), "source": "participant_voluntary"}}
    audit(db, actor["id"], "school.home_zone_set", p.participant_id)
    return {"saved": True}


@router.delete("/me/home-zone")
def remove_home_zone(actor=Depends(identity), db=Depends(database)):
    p = student_actor(db, actor)
    p.policy = {k: v for k, v in p.policy.items() if k != "home_zone"}
    audit(db, actor["id"], "school.home_zone_removed", p.participant_id)
    return {"removed": True}


class LocalFeature(Strict):
    value: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str
    state: Literal["missing", "partial", "observed"]
    eligible: StrictBool
    operational_coverage: float = Field(ge=0, le=1, allow_inf_nan=False)
    observed_minutes: float = Field(ge=0, le=1500, allow_inf_nan=False)
    window_start: AwareDatetime
    window_end: AwareDatetime


class LocalQuality(Strict):
    observed_minutes: float = Field(ge=0, le=1500, allow_inf_nan=False)
    gap_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    step_resets: int = Field(ge=0)
    inside_minutes: float | None = Field(ge=0, le=1500, allow_inf_nan=False)
    outside_minutes: float | None = Field(ge=0, le=1500, allow_inf_nan=False)
    uncertain_minutes: float = Field(ge=0, le=1500, allow_inf_nan=False)
    period_minutes: float = Field(ge=0, le=1500, allow_inf_nan=False)
    cluster_observed_minutes: float = Field(ge=0, le=1500, allow_inf_nan=False)
    school_observed_minutes: float | None = Field(default=None, ge=0, le=1500, allow_inf_nan=False)


class LocalSummary(Strict):
    day: date
    version: str
    features: dict[str, LocalFeature]
    quality: LocalQuality


@router.post("/me/sensor-summary")
def local_summary(body: LocalSummary, actor=Depends(identity), db=Depends(database), idempotency_key: str | None = Header(default=None)):
    p = student_actor(db, actor, True)
    d = actor["device"]
    expected = set(FEATURES) if body.version == VERSION else set(LEGACY_FEATURES) if body.version in LEGACY_VERSIONS else None
    if expected is None or set(body.features) != expected:
        raise HTTPException(422, "Contrato de movilidad incompatible")
    from .school_core import school_zone
    school = school_zone(settings(db.get(Institution, p.institution_id)))
    if not now().date() - timedelta(days=7) <= body.day <= now().date():
        raise HTTPException(422, "Día fuera de retención")
    from math import isfinite
    approved = {}
    for name, feature in body.features.items():
        row = feature.model_dump(mode="json")
        if set(row) - {"value", "unit", "state", "eligible", "operational_coverage", "observed_minutes", "window_start", "window_end"}:
            raise HTTPException(422, "El resumen no admite coordenadas ni campos adicionales")
        kind = "steps" if name == "observed_steps" else "location"
        value = row.get("value")
        if row.get("unit") != FEATURES[name][0] or value is not None and (not isinstance(value, (float, int)) or not isfinite(value) or value < 0):
            raise HTTPException(422, "Unidad o valor inválido")
        if value is not None and not sensor_allowed(db, d, kind):
            raise HTTPException(403, "Esta variable no fue autorizada")
        if not 0 <= row.get("operational_coverage", -1) <= 1 or not 0 <= row.get("observed_minutes", -1) <= 1500:
            raise HTTPException(422, "Cobertura inválida")
        a, b = utc(row.get("window_start", "")), utc(row.get("window_end", ""))
        zone = ZoneInfo(d.detail.get("timezone", "America/Lima"))
        if a.astimezone(zone).date() != body.day or a.astimezone(zone).time().isoformat() != "00:00:00" or b.astimezone(zone).date() != body.day + timedelta(days=1) or b.astimezone(zone).time().isoformat() != "00:00:00":
            raise HTTPException(422, "La ventana debe coincidir con el día civil del teléfono")
        if value is not None and b <= utc(p.policy.get(kind + "_since", now().isoformat())):
            raise HTTPException(403, "El período antecede a la autorización")
        if row["observed_minutes"] > (b-a).total_seconds() / 60 or abs(row["operational_coverage"] - row["observed_minutes"] / ((b-a).total_seconds()/60)) > .001:
            raise HTTPException(422, "Cobertura y minutos no coinciden")
        if not 0 < (b-a).total_seconds() <= 25 * 3600:
            raise HTTPException(422, "Ventana inválida")
        if name == "school_minutes":
            hours = school_window(school, body.day, zone)
            needed = 0.5 * (hours[1] - hours[0]).total_seconds() / 60 if hours else None
            eligible = value is not None and needed is not None and row["observed_minutes"] >= needed and b <= now()
        else:
            eligible = value is not None and row.get("operational_coverage", 0) >= 0.8 and b <= now()
        row = {**row, "eligible": eligible, "source": "android_local_summary"}
        approved[name] = row
    quality = body.quality.model_dump()
    if set(quality) - {"observed_minutes", "gap_count", "excluded_count", "step_resets", "inside_minutes", "outside_minutes", "uncertain_minutes", "period_minutes", "cluster_observed_minutes", "school_observed_minutes"}:
        raise HTTPException(422, "Calidad contiene campos no permitidos")
    if any(v is not None and (not isinstance(v, (int, float)) or not isfinite(v) or v < 0) for v in quality.values()):
        raise HTTPException(422, "Calidad inválida")
    period = quality["period_minutes"]
    if quality["observed_minutes"] > period or quality["cluster_observed_minutes"] > quality["observed_minutes"] or abs((quality["inside_minutes"] or 0) + (quality["outside_minutes"] or 0) + quality["uncertain_minutes"] - period) > .01:
        raise HTTPException(422, "Duraciones de calidad incompatibles")
    def apply():
        row = MobilityDay(device_id=d.id, day=body.day.isoformat(), version=body.version, detail={"features": approved, "quality": quality, "source": "android_local_summary", "lineage": {"contract": body.version, "raw_uploaded": False}})
        db.add(row)
        db.flush()
        from worker.school import evaluate_mobility
        evaluate_mobility(db, d, body.day.isoformat())
        return {"saved": True, "id": row.id}
    return once(db, actor, idempotency_key, "sensor-summary", body.model_dump(mode="json"), apply)


@router.get("/diagnostics/devices")
def devices(actor=Depends(identity), db=Depends(database)):
    m = member(db, actor, "admin", "researcher")
    if "diagnostics" not in actor["scopes"]:
        raise HTTPException(403, "Falta permiso de diagnóstico")
    from .school_db import StudentProfile
    rows = []
    for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == m.institution_id)):
        if not p.is_test and not p.policy.get("research_access"):
            continue
        for d in db.scalars(select(Device).where(Device.participant_id == p.participant_id)):
            rows.append({**public(d), "display_name": p.display_name, "is_test": p.is_test, "raw_location_available": p.policy.get("raw_location_upload", False) and "raw_location" in actor["scopes"]})
    audit(db, actor["id"], "diagnostics.devices")
    return rows


@router.get("/diagnostics/{ident}")
def diagnostic(ident: UUID, kind: str = "usage", start: AwareDatetime | None = None, end: AwareDatetime | None = None, actor=Depends(identity), db=Depends(database)):
    d = db.get(Device, str(ident))
    if not d:
        raise HTTPException(404, "Dispositivo no disponible")
    if kind not in ("usage", "location", "steps", "features"):
        raise HTTPException(422, "Tipo de dato inválido")
    access(db, actor, d.participant_id, "raw_location" if kind == "location" else "diagnostics")
    from .db import RawEvent, Capture, Feature
    since = utc(start) if start else now() - timedelta(days=7)
    until = utc(end) if end else now()
    if until <= since or until - since > timedelta(days=90):
        raise HTTPException(422, "Período inválido")
    if kind in ("location", "steps"):
        rows = [public(r) for r in db.scalars(select(SensorPoint).where(SensorPoint.device_id == d.id, SensorPoint.kind == kind, SensorPoint.occurred_at >= since, SensorPoint.occurred_at <= until).order_by(SensorPoint.occurred_at).limit(2000))]
    elif kind == "features":
        rows = [public(r) for r in db.scalars(select(MobilityDay).where(MobilityDay.device_id == d.id, MobilityDay.day >= since.date().isoformat(), MobilityDay.day <= until.date().isoformat()).order_by(MobilityDay.day).limit(100))]
        rows += [public(r) for r in db.scalars(select(Feature).where(Feature.device_id == d.id, Feature.day >= since.date().isoformat(), Feature.day <= until.date().isoformat()).limit(100))]
    else:
        rows = [public(r) for r in db.scalars(select(RawEvent).where(RawEvent.device_id == d.id, RawEvent.occurred_at >= since, RawEvent.occurred_at <= until).order_by(RawEvent.occurred_at).limit(2000))]
    audit(db, actor["id"], "diagnostics." + kind, d.id)
    return {"device": public(d), "rows": rows, "captures": [public(c) for c in db.scalars(select(Capture).where(Capture.device_id == d.id).order_by(Capture.end_at.desc()).limit(20))]}


@router.get("/diagnostics/{ident}/export")
def export_diagnostic(ident: UUID, kind: str = "usage", start: AwareDatetime | None = None, end: AwareDatetime | None = None, actor=Depends(identity), db=Depends(database)):
    from fastapi.responses import Response
    if "raw_export" not in actor["scopes"]:
        raise HTTPException(403, "La exportación requiere un permiso distinto de diagnóstico y modelos")
    if kind not in ("usage", "steps", "features"):
        raise HTTPException(422, "Las coordenadas no se incluyen en exportaciones generales")
    result = diagnostic(ident, kind, start, end, actor, db)
    header = {"type": "metadata", "exported_at": now().isoformat(), "kind": kind, "start": start, "end": end, "rows": len(result["rows"]), "limit": 2000, "notice": "Extracto técnico autorizado; sin coordenadas ni información clínica. Use períodos menores para conjuntos mayores al límite."}
    raw = "\n".join(json.dumps(row, ensure_ascii=False, default=str, allow_nan=False) for row in [header, *result["rows"]]) + "\n"
    audit(db, actor["id"], "school.diagnostic_export", str(ident))
    return Response(raw, media_type="application/x-ndjson", headers={"Content-Disposition": f'attachment; filename="datos-{kind}.jsonl"'})
