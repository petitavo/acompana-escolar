"""A05 — build an immutable training dataset from *local* authorized data.

Sources: questionnaire responses (labels), daily screen features and mobility-day
aggregates (days), and the authorization state at collection time. Every label
carries its own provenance; every excluded label/participant carries a reason.
The result is the exact `{manifest, days, labels}` contract the trainer consumes,
so training is never limited to a hand-authored JSON.
"""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import Device, Feature, Participant, Response, now, utc
from app.school_db import Institution, StudentProfile, MobilityDay, Authorization
from app.school_core import settings, authorization_status, analysis_cutoff
from app.phq9 import PHQ9

BUILDER_VERSION = "school-dataset-builder-v1.1"


def _overlaps(a_start, a_end, b_start, b_end):
    return utc(a_start) < utc(b_end) and utc(b_start) < utc(a_end)


def collection_authorization(db, p, at):
    rows = list(db.scalars(select(Authorization).where(Authorization.participant_id == p.participant_id,
        Authorization.created_at <= utc(at)).order_by(Authorization.created_at)))
    latest = {r.kind: r for r in rows}
    student = latest.get("assent" if p.minor else "consent")
    version = student.version if student else None
    guardian = latest.get("guardian")
    ready = bool(student and student.detail.get("accepted") is True and "verification" in latest
                 and (not p.minor or guardian and guardian.version == version and guardian.detail.get("accepted") is True))
    if "withdrawal" in latest and (not student or utc(latest["withdrawal"].created_at) >= utc(student.created_at)):
        ready = False
    preferences = latest.get("preferences")
    return {"ready": ready, "version": version, "authorization_ids": [r.id for r in latest.values()],
            "research_access": bool(preferences and preferences.detail.get("research_access")),
            "as_of": utc(at).isoformat(), "source": "authorization_history"}


def build_dataset(db, institution_id, spec, at=None):
    """Return (data, report). `data` is the trainer contract; `report` summarises
    selection and exclusions. Does not persist anything."""
    from ml.school_pipeline import CONTRACT, UNITS, windows, validate_dataset

    at = at or now()
    inst = db.scalar(select(Institution).where(Institution.id == institution_id).with_for_update().execution_options(populate_existing=True))
    if not inst:
        raise ValueError("Institución no disponible")
    cfg = settings(inst)
    include_test = bool(spec.get("include_test"))
    provenance = "test_fixture" if include_test else "authorized_real"
    task = spec["task"]
    if task not in ("concurrent", "prospective"):
        raise ValueError("task debe ser concurrent o prospective")
    purpose = spec.get("purpose", "clinical")
    if purpose not in ("clinical", "research"):
        raise ValueError("purpose debe ser clinical o research")
    feat_names = [f for f in spec.get("features", []) if f in UNITS]
    if not feat_names:
        raise ValueError("Seleccione al menos una variable observada válida")
    units = {n: UNITS[n] for n in feat_names}
    auth_ref = str(spec.get("authorization_reference", "")).strip()
    if len(auth_ref) < 10:
        raise ValueError("Registre la referencia de autorización/protocolo del dataset (mínimo 10 caracteres)")
    from_day, to_day = spec.get("from_day"), spec.get("to_day")
    from datetime import date
    for day in (from_day, to_day):
        if day:
            date.fromisoformat(day)
    if from_day and to_day and from_day > to_day:
        raise ValueError("Rango de fechas invertido")

    cutoff_utc, closed_day = analysis_cutoff(cfg, at)

    days, labels, label_prov, day_prov = [], [], {}, {}
    excl_participants, excl_labels, excl_days = [], [], []
    selected_participants = 0

    for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == institution_id).order_by(StudentProfile.created_at)):
        if p.is_test != include_test:
            continue
        part = db.get(Participant, p.participant_id)
        auth = authorization_status(db, p)
        reason = None
        if part.status == "revoked":
            reason = "withdrawn"
        elif not auth["ready"]:
            reason = "authorization_not_ready"
        elif purpose == "research" and not (p.is_test or p.policy.get("research_access")):
            reason = "research_consent_missing"
        if reason:
            excl_participants.append({"participant_id": p.participant_id, "reason": reason})
            continue
        selected_participants += 1
        device_ids = list(db.scalars(select(Device.id).where(Device.participant_id == p.participant_id)))

        # Retain each as-of revision; training chooses the last version available at its label cutoff.
        source_rows = []
        for cls in (Feature, MobilityDay):
            source_rows.extend(db.scalars(select(cls).where(cls.device_id.in_(device_ids))))
        merged = {}
        revisions = {}
        for row in sorted(source_rows, key=lambda x: (utc(x.created_at), x.id)):
            day = row.day
            if utc(row.created_at) > cutoff_utc or day > closed_day.isoformat():
                continue
            if (from_day and day < from_day) or (to_day and day > to_day):
                continue
            accepted = {}
            window_end = None
            for name in feat_names:
                f = row.detail.get("features", {}).get(name)
                if not f or f.get("unit") != units[name] or not f.get("window_end"):
                    continue
                end = utc(f["window_end"])
                if end > cutoff_utc or utc(row.created_at) < end:
                    continue
                evidence = collection_authorization(db, p, end)
                if not include_test and (not evidence["ready"] or purpose == "research" and not evidence["research_access"]):
                    excl_days.append({"day": day, "reason": "collection_authorization_missing"})
                    continue
                accepted[name] = {"value": f["value"], "eligible": bool(f["eligible"])}
                window_end = end.isoformat()
            if not accepted:
                continue
            slot = merged.setdefault(day, {"features": {}, "sources": []})
            slot["features"].update(accepted)
            slot["sources"].append({"table": row.__tablename__, "id": row.id,
                                    "version": row.version, "available_at": utc(row.created_at).isoformat()})
            available = utc(row.created_at).isoformat()
            key = f"{p.participant_id}:{day}:{available}"
            revisions[key] = {"participant_id": p.participant_id, "day": day, "available_at": available,
                              "window_end": window_end, "features": dict(slot["features"])}
            day_prov[key] = {"sources": list(slot["sources"]), "test_fixture": include_test}
        days.extend(revisions.values())

        kept = []
        from app.response_history import current_responses
        from app.forms import score
        responses = list(db.scalars(select(Response).where(Response.participant_id == p.participant_id, Response.created_at <= cutoff_utc)))
        for r in current_responses(responses):
            det = r.detail or {}
            if not det.get("complete") or det.get("total") is None:
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "incomplete_response"})
                continue
            evidence = collection_authorization(db, p, r.created_at)
            if not include_test and (not evidence["ready"] or purpose == "research" and not evidence["research_access"]):
                excl_labels.append({"label_id": r.id, "reason": "collection_authorization_missing"})
                continue
            if det.get("instrument_code") != PHQ9["instrument_id"] or det.get("instrument_version") != PHQ9["version"] or det.get("definition_sha256") != PHQ9["definition_sha256"]:
                excl_labels.append({"label_id": r.id, "reason": "instrument_definition_mismatch"})
                continue
            try:
                verified_score = score(PHQ9, det.get("answers", {}))[0]
            except Exception:
                excl_labels.append({"label_id": r.id, "reason": "invalid_source_answers"})
                continue
            applied, rs, re_ = det.get("applied_at"), det.get("recall_start"), det.get("recall_end")
            if not (applied and rs and re_):
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "missing_dates"})
                continue
            if (from_day and re_[:10] < from_day) or (to_day and re_[:10] > to_day):
                continue
            if utc(applied) > cutoff_utc:
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "applied_after_build_cutoff"})
                continue
            label_cut = rs if task == "prospective" else re_
            if utc(label_cut) > cutoff_utc:
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "window_after_build_cutoff"})
                continue
            if det.get("definition_sha256") not in (None, PHQ9["definition_sha256"]):
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "instrument_definition_mismatch"})
                continue
            if any(_overlaps(rs, re_, k[1], k[2]) for k in kept):
                excl_labels.append({"label_id": r.id, "participant_id": p.participant_id, "reason": "overlapping_recall"})
                continue
            kept.append((r.id, rs, re_))
            labels.append({"participant_id": p.participant_id, "id": r.id, "score": verified_score,
                           "recall_start": rs, "recall_end": re_, "applied_at": applied})
            label_prov[r.id] = {
                "participant_id": p.participant_id,
                "source": det.get("provenance", "participant_report"),
                "instrument": det.get("instrument_code", PHQ9["instrument_id"]),
                "instrument_version": det.get("instrument_version"),
                "definition_sha256": det.get("definition_sha256"),
                "collected_at": utc(r.created_at).isoformat(),
                
                "authorization_at_collection": evidence,
                "revision": det.get("revision", 1), "root_response_id": det.get("root_response_id", r.id),
                "test_fixture": include_test,
            }

    manifest = {
        "name": spec["name"], "provenance": provenance, "authorization_reference": auth_ref,
        "instrument": PHQ9["instrument_id"], "instrument_version": PHQ9["version"],
        "recall_days": 14, "task": task, "contract": CONTRACT, "units": units,
        "purpose": purpose, "source": "local_builder", "built_at": at.isoformat(),
        "builder_version": BUILDER_VERSION, "institution_id": institution_id,
        "timezone": cfg["timezone"], "cutoff_policy": "local_closed_day_09h_with_actual_availability",
        "selection": {"features": feat_names, "include_test": include_test,
                      "from_day": from_day, "to_day": to_day,
                      "build_cutoff": cutoff_utc.isoformat(), "closed_day": closed_day.isoformat()},
        "label_provenance": label_prov, "day_provenance": day_prov,
        "exclusions": {"participants": excl_participants, "labels": excl_labels, "days": excl_days},
    }
    data = {"manifest": manifest, "days": days, "labels": labels}

    if not labels or not days:
        report = _report(data, [], selected_participants)
        return data, report

    usable = windows(data)[0]
    usable_ids = {r["label_id"] for r in usable}
    for l in labels:
        if l["id"] not in usable_ids:
            excl_labels.append({"label_id": l["id"], "participant_id": l["participant_id"], "reason": "no_eligible_window"})
    labels = [l for l in labels if l["id"] in usable_ids]
    label_prov = {k: v for k, v in label_prov.items() if k in usable_ids}
    kept_p = {l["participant_id"] for l in labels}
    days = [d for d in days if d["participant_id"] in kept_p]
    day_prov = {k: v for k, v in day_prov.items() if k.split(":", 1)[0] in kept_p}
    manifest["label_provenance"], manifest["day_provenance"] = label_prov, day_prov
    manifest["exclusions"] = {"participants": excl_participants, "labels": excl_labels, "days": excl_days}
    data = {"manifest": manifest, "days": days, "labels": labels}
    if labels:
        validate_dataset(data)
    return data, _report(data, usable, selected_participants)


def _report(data, usable, selected_participants):
    m = data["manifest"]
    people = sorted({l["participant_id"] for l in data["labels"]})
    return {
        "name": m["name"], "task": m["task"], "purpose": m["purpose"], "provenance": m["provenance"],
        "features": m["selection"]["features"], "timezone": m["timezone"],
        "build_cutoff": m["selection"]["build_cutoff"], "closed_day": m["selection"]["closed_day"],
        "participants_selected": selected_participants, "participants_with_labels": len(people),
        "labels": len(data["labels"]), "eligible_windows": len(usable), "days": len(data["days"]),
        "excluded_participants": m["exclusions"]["participants"],
        "excluded_labels": m["exclusions"]["labels"],
        "excluded_days": m["exclusions"]["days"],
        "trainable": len(people) >= 6 and len(usable) >= 18,
        "missing_for_training": _missing(people, usable),
    }


def _missing(people, usable):
    need = []
    if len(people) < 6:
        need.append(f"{6 - len(people)} participante(s) autorizados con ventana elegible")
    if len(usable) < 18:
        need.append(f"{18 - len(usable)} etiqueta(s) PHQ-9 con ventana elegible")
    return need


def persist_dataset(db, institution_id, owner_id, data, report):
    """Write the immutable snapshot + a DatasetRecord."""
    from app.config import ARTIFACTS
    from app.db import uid
    from app.school_db import DatasetRecord
    from app.security import audit
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    checksum = hashlib.sha256(raw).hexdigest()
    path = ARTIFACTS / "datasets" / (uid() + ".json")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)
    record = DatasetRecord(institution_id=institution_id, owner_id=owner_id,
                           name=data["manifest"]["name"], manifest=data["manifest"],
                           path=str(path), sha256=checksum)
    db.add(record)
    db.flush()
    audit(db, owner_id, "model.dataset_built", record.id)
    return {"dataset_id": record.id, "sha256": checksum, **report}
