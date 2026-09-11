"""Versioned real-data training and inference; fixtures cannot become active models."""
import hashlib
import json
from pathlib import Path
from datetime import timedelta, date, datetime
from statistics import median
from zoneinfo import ZoneInfo
import numpy as np
from sqlalchemy import select
from app.db import Device, Feature, now, utc, uid
from app.school_db import DatasetRecord, ModelRecord, StudentProfile, MobilityDay, Prediction
from app.features import FEATURES as SCREEN
from app.mobility import FEATURES as MOBILITY, VERSION as MOBILITY_VERSION
from app.phq9 import PHQ9
from app.config import ARTIFACTS

CONTRACT = "school-features-v1.0"
UNITS = {k: v[0] for k, v in {**SCREEN, **MOBILITY}.items()}
FLOORS = {k: v[1] for k, v in {**SCREEN, **MOBILITY}.items()}
PARTS = ("current", "baseline", "delta", "robust_deviation", "available")


def validate_dataset(data):
    if set(data) != {"manifest", "days", "labels"}:
        raise ValueError("Se requieren manifest, days y labels")
    m = data["manifest"]
    required = {"name", "provenance", "authorization_reference", "instrument", "instrument_version", "recall_days", "task", "contract", "units"}
    # A05: metadata a local build attaches. Kept out of the training contract but
    # allowed on the manifest so the snapshot carries its own provenance.
    optional = {"purpose", "source", "built_at", "builder_version", "institution_id",
                "label_provenance", "day_provenance", "exclusions", "selection",
                "cutoff_policy", "timezone", "parent_dataset_sha256"}
    if set(m) - required - optional or required - set(m) or m["provenance"] not in ("authorized_real", "test_fixture") or len(m["authorization_reference"].strip()) < 10:
        raise ValueError("Manifest incompleto: declare procedencia y autorización del dataset")
    if m.get("purpose", "clinical") not in ("clinical", "research"):
        raise ValueError("La finalidad del dataset debe ser clínica o de investigación")
    if "label_provenance" in m:
        ids = {l["id"] for l in data["labels"]}
        if set(m["label_provenance"]) != ids:
            raise ValueError("La procedencia por etiqueta debe cubrir exactamente las etiquetas del dataset")
    if m["instrument"] != PHQ9["instrument_id"] or m["instrument_version"] != PHQ9["version"] or m["recall_days"] != 14 or m["contract"] != CONTRACT or m["task"] not in ("concurrent", "prospective"):
        raise ValueError("Instrumento, ventanas o contrato incompatibles")
    if not m["units"] or any(k not in UNITS or v != UNITS[k] for k, v in m["units"].items()):
        raise ValueError("Variables o unidades incompatibles")
    if not 1 <= len(data["days"]) <= 20000 or not 1 <= len(data["labels"]) <= 2000:
        raise ValueError("Dataset vacío o demasiado grande")
    seen = set()
    for row in data["days"]:
        if set(row) != {"participant_id", "day", "available_at", "window_end", "features"}:
            raise ValueError("Cada día requiere participante, fecha, disponibilidad, cierre y features; no admite coordenadas")
        date.fromisoformat(row["day"])
        if any(datetime.fromisoformat(row[k].replace("Z", "+00:00")).tzinfo is None for k in ("available_at", "window_end")):
            raise ValueError("Disponibilidad y cierre requieren zona horaria explícita")
        a, b = utc(row["available_at"]), utc(row["window_end"])
        if a.utcoffset() is None or a < b or (row["participant_id"], row["day"], a) in seen:
            raise ValueError("Día duplicado o disponibilidad anterior al cierre")
        seen.add((row["participant_id"], row["day"], a))
        zone = ZoneInfo(m.get("timezone", "UTC"))
        local_end = b.astimezone(zone)
        if local_end.date() != date.fromisoformat(row["day"]) + timedelta(days=1) or local_end.hour or local_end.minute or local_end.second or local_end.microsecond:
            raise ValueError("El cierre debe ser la medianoche local posterior al día declarado")
        if set(row["features"]) - set(m["units"]):
            raise ValueError("Columna no declarada")
        for name, v in row["features"].items():
            if set(v) != {"value", "eligible"} or type(v["eligible"]) is not bool or v["value"] is not None and (type(v["value"]) not in (int, float) or not np.isfinite(v["value"]) or v["value"] < 0):
                raise ValueError("Valor o calidad inválidos")
    seen = set()
    for label in data["labels"]:
        if set(label) != {"participant_id", "id", "score", "recall_start", "recall_end", "applied_at"}:
            raise ValueError("Etiqueta inválida")
        if label["id"] in seen or type(label["score"]) is not int or not 0 <= label["score"] <= 27:
            raise ValueError("Etiqueta repetida o fuera de 0–27")
        seen.add(label["id"])
        if any(datetime.fromisoformat(label[k].replace("Z", "+00:00")).tzinfo is None for k in ("recall_start", "recall_end", "applied_at")):
            raise ValueError("Las etiquetas requieren zona horaria explícita")
        if abs((utc(label["recall_end"]) - utc(label["recall_start"])).total_seconds() - 14 * 86400) > 1 or utc(label["applied_at"]) < utc(label["recall_end"]):
            raise ValueError("El período PHQ-9 debe durar 14 días")
    labels_by_person = {}
    for label in sorted(data["labels"], key=lambda x: utc(x["recall_start"])):
        old = labels_by_person.get(label["participant_id"])
        if old and utc(label["recall_start"]) < utc(old["recall_end"]):
            raise ValueError("No se duplican etiquetas con períodos superpuestos")
        labels_by_person[label["participant_id"]] = label
    return m


def vector(days, cutoff, names, zone="UTC", closed_day=None):
    cutoff = utc(cutoff)
    last = date.fromisoformat(closed_day) if closed_day else cutoff.astimezone(ZoneInfo(zone)).date() - timedelta(days=1)
    current_start = last - timedelta(days=6)
    baseline_start = current_start - timedelta(days=28)
    latest = {}
    for row in sorted(days, key=lambda r: utc(r["available_at"])):
        if utc(row["available_at"]) <= cutoff and utc(row["window_end"]) <= cutoff:
            latest[row["day"]] = row
    available = list(latest.values())
    values, explanation = [], {}
    for name in names:
        def window(a, b):
            return [r["features"][name]["value"] for r in available if a <= date.fromisoformat(r["day"]) <= b and name in r["features"] and r["features"][name]["eligible"] and r["features"][name]["value"] is not None]
        past = window(baseline_start, current_start - timedelta(days=1))
        current = window(current_start, last)
        eligible = len(past) >= 14 and len(current) >= 5
        if eligible:
            base, level = median(past), median(current)
            scale = max(FLOORS[name], 1.4826 * median([abs(v - base) for v in past]))
            parts = [level, base, level - base, (level - base) / scale, 1]
        else:
            parts = [None, None, None, None, 0]
        explanation[name] = dict(zip(PARTS, parts))
        values.extend(parts)
    return values, explanation


def windows(data):
    m = validate_dataset(data)
    names = list(m["units"])
    rows = []
    for label in data["labels"]:
        cutoff = label["recall_start"] if m["task"] == "prospective" else label["recall_end"]
        days = [d for d in data["days"] if d["participant_id"] == label["participant_id"]]
        x, explanation = vector(days, cutoff, names, m.get("timezone", "UTC"))
        if not any(v is not None for j, v in enumerate(x) if j % 5 != 4):
            continue
        earlier = [v for v in data["labels"] if v["participant_id"] == label["participant_id"] and v["id"] != label["id"] and max(utc(v["applied_at"]), utc(m.get("label_provenance", {}).get(v["id"], {}).get("collected_at", v["applied_at"]))) < utc(cutoff)]
        earlier.sort(key=lambda v: v["applied_at"])
        rows.append({"x": x, "y": label["score"], "participant_id": label["participant_id"], "label_id": label["id"], "label_start": label["recall_start"], "label_end": label["recall_end"], "cutoff": cutoff, "previous": earlier[-1]["score"] if earlier else None})
    return rows, names


def evaluate(y, pred, people, seed):
    from .pipeline import report_metrics
    return report_metrics(np.array(y), np.array(pred), np.array(people), seed)


def _arrays(part):
    return (np.array([[np.nan if v is None else v for v in r["x"]] for r in part], dtype=float),
            np.array([r["y"] for r in part]))


def dataset_rows(record):
    if record.manifest.get("invalidated_at"):
        raise ValueError("El dataset fue invalidado por una corrección; construya una nueva versión")
    raw = Path(record.path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record.sha256:
        raise ValueError("Checksum del dataset no coincide")
    data = json.loads(raw)
    rows, names = windows(data)
    people = sorted({r["participant_id"] for r in rows})
    if len(people) < 6 or len(rows) < 18:
        raise ValueError("Se requieren al menos 6 participantes y 18 etiquetas con ventanas elegibles")
    return data, rows, names, people


def partition(rows, people, seed):
    """Deterministic 60/20/20 split by participant. Same seed + same rows -> same split."""
    people = sorted(people)
    rng = np.random.default_rng(seed)
    rng.shuffle(people)
    ntrain = max(3, int(len(people) * .6))
    nval = max(1, int(len(people) * .2))
    groups = [people[:ntrain], people[ntrain:ntrain + nval], people[ntrain + nval:]]
    splits = [[r for r in rows if r["participant_id"] in g] for g in groups]
    if any(not s for s in splits):
        raise ValueError("Partición vacía; se requieren más participantes")
    return groups, splits


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate_artifact(disk_path, splits, seed):
    """A06: every reported number is computed from the model bytes ON DISK, reloaded
    here, and stamped with that artifact's sha256. Comparators are fit only on the
    training split."""
    from xgboost import XGBRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    x, y = _arrays(splits[0])
    xt, yt = _arrays(splits[2])
    deployed = XGBRegressor()
    deployed.load_model(disk_path)
    ridge = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), Ridge(alpha=10))
    ridge.fit(x, y)
    levels_idx = [j for j in range(x.shape[1]) if j % 5 in (0, 1, 4)]
    levels = XGBRegressor(n_estimators=80, max_depth=2, learning_rate=.05, random_state=seed, n_jobs=1, tree_method="hist")
    levels.fit(x[:, levels_idx], y)
    mean = float(np.mean(y))
    test_people = [r["participant_id"] for r in splits[2]]
    comparators = {
        "constant": np.full(len(yt), mean),
        "last_questionnaire": np.array([mean if r["previous"] is None else r["previous"] for r in splits[2]]),
        "ridge": ridge.predict(xt),
        "xgboost": deployed.predict(xt),
        "levels_only": levels.predict(xt[:, levels_idx]),
    }
    metrics = {k: evaluate(yt, np.clip(v, 0, 27), test_people, seed) for k, v in comparators.items()}
    metrics["artifact_sha256"] = _sha(disk_path)
    metrics["evaluated_at"] = now().isoformat()
    metrics["test_participants"] = sorted(set(test_people))
    return metrics


def temporal_probe(rows, splits, seed, folder):
    """A separate time-embargoed generalization probe. It is its OWN artifact with
    its OWN hash — never conflated with the deployed model's metrics."""
    from xgboost import XGBRegressor
    times = sorted({r["cutoff"] for r in rows})
    if len(times) < 3:
        return {"status": "insufficient_time_periods"}
    boundary = utc(times[len(times) // 2])
    early = [r for r in splits[0] if utc(r["label_end"]) < boundary - timedelta(days=14)]
    late = [r for r in splits[2] if utc(r["cutoff"]) >= boundary]
    if len(early) < 6 or not late:
        return {"status": "insufficient_time_periods", "boundary": boundary.isoformat()}
    ex, ey = _arrays(early)
    lx, ly = _arrays(late)
    m = XGBRegressor(n_estimators=80, max_depth=2, learning_rate=.05, random_state=seed, n_jobs=1, tree_method="hist")
    m.fit(ex, ey)
    tpath = Path(folder) / "temporal.json"
    m.save_model(tpath)
    tpath.chmod(0o600)
    reloaded = XGBRegressor()
    reloaded.load_model(tpath)
    return {"status": "completed", "embargo_days": 14, "boundary": boundary.isoformat(),
            "train_rows": len(early), "test_rows": len(late),
            "artifact_sha256": _sha(tpath), "artifact": "temporal.json",
            "notice": "Sonda de generalización temporal; artefacto distinto del modelo desplegado",
            "metrics": evaluate(ly, np.clip(reloaded.predict(lx), 0, 27), [r["participant_id"] for r in late], seed)}


def register_evaluated_model(db, record, disk_path, seed, folder, extra_manifest=None, state="registered"):
    """Shared by training and import: partition -> evaluate the on-disk artifact ->
    temporal probe -> ModelRecord. `metrics` and `manifest['temporal']` are each
    bound to the exact artifact hash they were computed from."""
    data, rows, names, people = dataset_rows(record)
    groups, splits = partition(rows, people, seed)
    metrics = evaluate_artifact(disk_path, splits, seed)
    temporal = temporal_probe(rows, splits, seed, folder)
    columns = [f"{name}_{part}" for name in names for part in PARTS]
    artifact_sha = _sha(disk_path)
    manifest = {
        **record.manifest, "timezone": record.manifest.get("timezone", "UTC"), "columns": columns, "feature_names": names, "seed": seed,
        "partitions": {k: v for k, v in zip(("train", "validation", "test"), groups)},
        "labels": len(rows), "artifact_sha256": artifact_sha, "temporal": temporal,
        "trained_at": now().isoformat(), "output_unit": "puntos PHQ-9",
        "clinical_validation": False, "dataset_sha256": record.sha256,
        "missing_values": "XGBoost missing; Ridge imputation fitted on train only",
        **(extra_manifest or {}),
    }
    ident = Path(disk_path).parent.name
    row = ModelRecord(id=ident, institution_id=record.institution_id, dataset_id=record.id,
                      manifest=manifest, metrics=metrics, artifact=str(disk_path), state=state)
    db.add(row)
    return row, metrics, temporal


def train_real(db, job):
    from xgboost import XGBRegressor
    record = db.get(DatasetRecord, job.payload["dataset_id"])
    if not record:
        raise ValueError("Dataset no disponible")
    data, rows, names, people = dataset_rows(record)
    seed = int(job.payload.get("seed", 20260906))
    groups, splits = partition(rows, people, seed)
    x, y = _arrays(splits[0])
    xv, yv = _arrays(splits[1])
    candidates = []
    for depth in (2, 3):
        model = XGBRegressor(n_estimators=80, max_depth=depth, learning_rate=.05, objective="reg:squarederror", random_state=seed, n_jobs=1, tree_method="hist")
        model.fit(x, y)
        candidates.append((float(np.mean(abs(np.clip(model.predict(xv), 0, 27) - yv))), depth, model))
    val_error, depth, model = min(candidates, key=lambda v: v[0])
    ident = uid()
    folder = ARTIFACTS / "models" / ident
    folder.mkdir(parents=True, mode=0o700)
    path = folder / "model.json"
    model.save_model(path)
    path.chmod(0o600)
    extra = {"validation_mae": val_error, "selected_depth": depth,
             "supersedes": job.payload.get("supersedes"), "trigger": job.payload.get("trigger", "manual")}
    row, metrics, temporal = register_evaluated_model(db, record, path, seed, folder, extra)
    return {"model_id": row.id, "metrics": metrics, "temporal": temporal,
            "provenance": record.manifest["provenance"], "artifact_sha256": row.manifest["artifact_sha256"]}


def predict(model_record, values):
    from xgboost import XGBRegressor, DMatrix
    path = Path(model_record.artifact)
    if hashlib.sha256(path.read_bytes()).hexdigest() != model_record.manifest["artifact_sha256"]:
        raise ValueError("Checksum del modelo incompatible")
    m = model_record.manifest
    if m["contract"] != CONTRACT or m["instrument_version"] != PHQ9["version"] or any(UNITS.get(k) != v for k, v in m["units"].items()):
        raise ValueError("Contrato del modelo incompatible")
    if len(values) != len(m["columns"]):
        raise ValueError("Cantidad de variables incompatible")
    model = XGBRegressor()
    model.load_model(path)
    x = np.array([[np.nan if v is None else v for v in values]], dtype=float)
    raw = float(model.predict(x)[0])
    parts = model.get_booster().predict(DMatrix(x), pred_contribs=True)[0]
    if abs(float(sum(parts)) - raw) > 1e-3:
        raise ValueError("La explicación no coincide con el modelo")
    return {"estimate": min(27, max(0, raw)), "raw_estimate": raw, "clipped": raw < 0 or raw > 27, "unit": "puntos PHQ-9", "shap": {"base": float(parts[-1]), "contributions": dict(zip(m["columns"], [float(v) for v in parts[:-1]])), "notice": "Contribuciones al resultado sin recorte; no son causas ni porcentajes"}, "task": m["task"]}


def inference_eligible(db, p, purpose):
    """A08: capture authorization is not analysis authorization. Before inferring —
    and again before persisting — the participant must have a current, non-withdrawn
    authorization, an enabled pilot (or be a test account) and, for a research-purpose
    model, an explicit research consent. Clinical and research purposes are distinct;
    a research consent never substitutes for clinical authorization and vice versa.

    A paused participation also suspends new inference until it is resumed.
    Withdrawal and document changes require renewed authorization."""
    from app.school_core import authorization_status
    from app.config import PILOT_ENABLED
    from app.db import Participant
    if db.get(Participant, p.participant_id).status == "revoked":
        return False, "withdrawn"
    if not authorization_status(db, p)["ready"]:
        return False, "authorization_not_ready"
    if p.policy.get("paused"):
        return False, "participation_paused"
    if not p.is_test and not PILOT_ENABLED:
        return False, "pilot_disabled"
    if purpose == "research" and not (p.is_test or p.policy.get("research_access")):
        return False, "research_consent_missing"
    return True, "eligible"


def infer_registered(db, job):
    from app.db import Participant
    from app.school_db import Institution
    model = db.get(ModelRecord, job.payload["model_id"])
    if not model or model.state not in ("shadow", "active"):
        raise ValueError("Versión no habilitada para ejecución")
    # A08 lock protocol: Institution first, then Participant per row (never Device/User
    # — identity() already took those before the handler ran). ``populate_existing``
    # forces a fresh read so a settings/version change that committed before we
    # acquired the lock is visible; one that has not committed blocks on our lock.
    db.scalars(select(Institution).where(Institution.id == model.institution_id)
               .with_for_update().execution_options(populate_existing=True)).one()
    from worker.school import aggregation_status
    dependency = aggregation_status(db, model.institution_id)
    if not dependency["ready"]:
        from app.db import Idempotency
        from sqlalchemy import delete
        db.execute(delete(Idempotency).where(Idempotency.actor == "school-worker", Idempotency.route == "periodic",
            Idempotency.key.like("infer:" + model.id + ":%")))
        return {"predictions": 0, "skipped": "aggregates_pending", "analysis": dependency}
    purpose = model.manifest.get("purpose", "clinical")
    cutoff = utc(job.payload["cutoff"])
    from zoneinfo import ZoneInfo
    analysis_day = cutoff.astimezone(ZoneInfo(model.manifest.get("timezone", "America/Lima"))).date().isoformat()
    count = 0
    for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == model.institution_id)):
        if p.is_test != (model.manifest["provenance"] == "test_fixture"):
            continue
        existing = db.scalar(select(Prediction).where(Prediction.model_id == model.id, Prediction.participant_id == p.participant_id, Prediction.cutoff == analysis_day))
        if existing and not existing.detail.get("invalidated_at"):
            continue
        ok, _ = inference_eligible(db, p, purpose)
        if not ok:
            continue
        ids = list(db.scalars(select(Device.id).where(Device.participant_id == p.participant_id)))
        merged = {}
        for cls in (Feature, MobilityDay):
            for row in db.scalars(select(cls).where(cls.device_id.in_(ids), cls.created_at <= cutoff).order_by(cls.created_at)):
                value = merged.setdefault(row.day, {"participant_id": p.participant_id, "day": row.day, "available_at": row.created_at.isoformat(), "window_end": row.created_at.isoformat(), "features": {}})
                value["available_at"] = max(value["available_at"], row.created_at.isoformat())
                for name, f in row.detail["features"].items():
                    if name in model.manifest["units"] and f["unit"] == model.manifest["units"][name] and utc(f["window_end"]) <= cutoff:
                        value["features"][name] = {"value": f["value"], "eligible": f["eligible"]}
        values, reference = vector(list(merged.values()), cutoff, model.manifest["feature_names"], model.manifest.get("timezone", "America/Lima"), job.payload.get("closed_day"))
        if not any(v is not None for j, v in enumerate(values) if j % 5 != 4):
            continue
        result = predict(model, values)
        result.update({"state": model.state, "reference": reference, "cutoff": cutoff.isoformat(), "contract": CONTRACT, "purpose": purpose, "model_artifact_sha256": model.manifest.get("artifact_sha256")})
        # A08: re-check eligibility under a participant row lock right before we
        # persist. ``populate_existing`` + refresh defeat identity-map staleness so
        # a withdrawal / preference / version change that COMMITTED before this
        # point always wins (no prediction is written). A change that has not yet
        # committed blocks its writer on this lock until we commit; in that race
        # the prediction may be written and is invalidated immediately afterwards
        # by the withdrawal/renewal path. We do not claim revocation wins for
        # events that linearise after this transaction commits.
        db.scalars(select(Participant).where(Participant.id == p.participant_id)
                   .with_for_update().execution_options(populate_existing=True)).one()
        db.refresh(p)
        ok, reason = inference_eligible(db, p, purpose)
        if not ok:
            continue
        result["generated_at"] = now().isoformat()
        if existing:
            previous = {k: v for k, v in existing.detail.items() if k != "previous_estimates"}
            result["previous_estimates"] = [*existing.detail.get("previous_estimates", []), previous]
            result["revision"] = int(existing.detail.get("revision", 1)) + 1
            existing.detail = result
        else:
            result["revision"] = 1
            db.add(Prediction(model_id=model.id, participant_id=p.participant_id, cutoff=analysis_day, detail=result))
        # A professional, recorded activation authorizes a separate review reason.
        # The instrument's threshold is used transparently; never a diagnosis.
        if model.state == "active" and result["estimate"] >= PHQ9["review_threshold"]:
            from app.cases import add_reason
            add_reason(db, p.participant_id, "model_estimate", {"model_id": model.id, "estimate": result["estimate"], "unit": result["unit"], "cutoff": cutoff.isoformat()}, "worker")
        count += 1
    return {"predictions": count, "model_id": model.id, "state": model.state}
