import hashlib, json, platform
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol
import numpy as np
from sqlalchemy import select
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor
from app.db import *
from app.features import FEATURES, deviation, reconstruct, overlap
from app.config import MODE, ARTIFACTS, FEATURE_VERSION


class FeatureBuilder(Protocol):
    def build(self, cutoff): ...


class LabelBuilder(Protocol):
    def build(self, response): ...


class ModelTrainer(Protocol):
    def fit(self, x, y): ...


class Predictor(Protocol):
    def predict(self, x): ...


class ModelRegistry(Protocol):
    def register(self, manifest): ...


COLUMNS = [
    f"{name}_{part}"
    for name in FEATURES
    for part in ("current", "baseline", "delta", "robust_deviation", "available")
]
CONCURRENT_COLUMNS = [
    "recall_observed_interactive_minutes",
    "recall_confirmed_sessions",
    "recall_operational_coverage",
]


def dataset(db, task="concurrent"):
    if MODE != "DEMO":
        raise ValueError("Modelos sintéticos prohibidos en LAB")
    rows = []
    for p in db.scalars(select(Participant)):
        device = db.scalar(
            select(Device)
            .where(Device.participant_id == p.id)
            .order_by(Device.created_at, Device.id)
            .limit(1)
        )
        if not device:
            continue
        history = {}
        fs = list(
            db.scalars(
                select(Feature)
                .where(Feature.device_id == device.id)
                .order_by(Feature.created_at)
            )
        )
        raw = [
            public(r)
            for r in db.scalars(select(RawEvent).where(RawEvent.device_id == device.id))
        ]
        captures = [
            public(c)
            for c in db.scalars(select(Capture).where(Capture.device_id == device.id))
        ]
        previous = None
        responses = list(
            db.scalars(
                select(Response)
                .where(Response.participant_id == p.id)
                .order_by(Response.created_at)
            )
        )
        for response in responses:
            if (
                response.detail.get("real")
                or response.detail.get("instrument_code") != "CHECKIN_DEMO_V1"
            ):
                continue
            recall_start = utc(response.detail["recall_start"])
            recall_end = utc(response.detail["recall_end"])
            # For concurrent task, use only completed prior features plus today's non-night levels;
            # no response values enter X. Prospective task freezes everything before recall begins.
            cutoff = recall_start if task == "prospective" else recall_end
            history = {}
            for f in fs:
                if utc(f.created_at) <= cutoff:
                    history[f.day] = f.detail
            eval_day = str(
                cutoff.astimezone(
                    __import__("zoneinfo").ZoneInfo("America/Lima")
                ).date()
            )
            summary = deviation(history, eval_day)
            if not summary["eligible"]:
                previous = response.detail["total"]
                continue
            x = []
            for name in FEATURES:
                item = summary["features"][name]
                x += [
                    item.get(part, float("nan"))
                    for part in ("current", "baseline", "delta", "robust_deviation")
                ] + [1 if item["state"] == "available" else 0]
            if task == "concurrent":
                known_events = [
                    r
                    for r in raw
                    if utc(r["created_at"]) <= cutoff
                    and recall_start <= utc(r["occurred_at"]) <= recall_end
                ]
                known_queries = [
                    c
                    for c in captures
                    if utc(c["created_at"]) <= cutoff
                    and c["detail"]["success"]
                    and c["detail"]["permission_before"]
                    and c["detail"]["permission_after"]
                ]
                windows = [
                    (utc(c["start_at"]), utc(c["end_at"])) for c in known_queries
                ]
                intervals, _ = reconstruct(known_events, windows)
                spans = [(utc(i["start"]), utc(i["end"])) for i in intervals]
                x += [
                    overlap(spans, recall_start, recall_end) / 60,
                    len(intervals),
                    overlap(windows, recall_start, recall_end)
                    / max((recall_end - recall_start).total_seconds(), 1),
                ]
            row = {
                "participant_id": p.id,
                "response_id": response.id,
                "cutoff_at": cutoff.isoformat(),
                "feature_start": summary["current_start"],
                "feature_end": summary["current_end"],
                "label_recall_start": recall_start.isoformat(),
                "label_recall_end": recall_end.isoformat(),
                "target": response.detail["total"],
                "previous": previous,
                "x": x,
                "provenance": "DEMO",
                "instrument": "CHECKIN_DEMO_V1",
                "feature_version": FEATURE_VERSION,
            }
            if task == "prospective":
                assert utc(row["cutoff_at"]) <= recall_start
            else:
                row["feature_end"] = str(
                    recall_end.astimezone(
                        __import__("zoneinfo").ZoneInfo("America/Lima")
                    ).date()
                    + timedelta(days=1)
                )
            rows.append(row)
            previous = response.detail["total"]
    return rows


def report_metrics(y, pred, groups, seed):
    mae = float(mean_absolute_error(y, pred))
    rng = np.random.default_rng(seed)
    unique = np.unique(groups)
    estimates = []
    per = {
        str(g): float(mean_absolute_error(y[groups == g], pred[groups == g]))
        for g in unique
    }
    for _ in range(300):
        estimates.append(
            float(
                np.mean(
                    [per[str(g)] for g in rng.choice(unique, len(unique), replace=True)]
                )
            )
        )
    return {
        "mae": mae,
        "rmse": float(mean_squared_error(y, pred) ** 0.5),
        "participant_mae": per,
        "participant_bootstrap_mae_ci95": np.quantile(
            estimates, [0.025, 0.975]
        ).tolist(),
    }


def train(db, job):
    rows = dataset(db, job.payload["task"])
    seed = job.payload["seed"]
    people = sorted({r["participant_id"] for r in rows})
    if len(people) < 6 or len(rows) < 24:
        return {
            "status": "insufficient",
            "reason": "Se requieren al menos 6 participantes y 24 etiquetas para esta partición DEMO",
            "participants": len(people),
            "labels": len(rows),
        }
    rng = np.random.default_rng(seed)
    rng.shuffle(people)
    train_ids = set(people[: int(0.6 * len(people))])
    val_ids = set(people[int(0.6 * len(people)) : int(0.8 * len(people))])
    test_ids = set(people[int(0.8 * len(people)) :])
    assert (
        not train_ids & test_ids and not val_ids & test_ids and not train_ids & val_ids
    )
    sets = [
        [r for r in rows if r["participant_id"] in ids]
        for ids in (train_ids, val_ids, test_ids)
    ]
    if any(len(s) < 2 for s in sets):
        return {
            "status": "insufficient",
            "reason": "Particiones sin etiquetas suficientes",
        }
    x = [np.array([r["x"] for r in s], dtype=float) for s in sets]
    y = [np.array([r["target"] for r in s], dtype=float) for s in sets]
    groups = np.array([r["participant_id"] for r in sets[2]])
    columns = COLUMNS + (
        CONCURRENT_COLUMNS if job.payload["task"] == "concurrent" else []
    )
    assert all(
        not any(t in c for t in ("participant_id", "target", "answer", "response"))
        for c in columns
    )
    metrics = {}
    trained = None
    selected = None
    models = {
        "Constante DEMO": make_pipeline(
            SimpleImputer(keep_empty_features=True), DummyRegressor(strategy="median")
        ),
        "Ridge DEMO": make_pipeline(
            SimpleImputer(keep_empty_features=True), StandardScaler(), Ridge(alpha=10)
        ),
    }
    for name, model in models.items():
        model.fit(x[0], y[0])
        metrics[name] = report_metrics(y[2], model.predict(x[2]), groups, seed)
    previous = np.array(
        [
            r["previous"] if r["previous"] is not None else float(np.median(y[0]))
            for r in sets[2]
        ]
    )
    metrics["Último cuestionario DEMO"] = report_metrics(y[2], previous, groups, seed)
    # Select hyperparameter on validation only. Test stays held out.
    for depth in (2, 3):
        model = XGBRegressor(
            n_estimators=60,
            max_depth=depth,
            learning_rate=0.05,
            reg_lambda=12,
            min_child_weight=5,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=seed,
            n_jobs=1,
        )
        model.fit(x[0], y[0])
        err = float(mean_absolute_error(y[1], model.predict(x[1])))
        if selected is None or err < selected:
            selected = err
            trained = model
    pred = trained.predict(x[2])
    metrics["XGBoost DEMO"] = report_metrics(y[2], pred, groups, seed)
    level_indices = [n * 5 for n in range(len(FEATURES))]
    ablated = XGBRegressor(
        n_estimators=60,
        max_depth=2,
        learning_rate=0.05,
        reg_lambda=12,
        random_state=seed,
        n_jobs=1,
    )
    ablated.fit(x[0][:, level_indices], y[0])
    metrics["XGBoost solo niveles DEMO"] = report_metrics(
        y[2], ablated.predict(x[2][:, level_indices]), groups, seed
    )
    folder = ARTIFACTS / job.id
    folder.mkdir(exist_ok=True)
    model_file = folder / "XGBoost-DEMO.ubj"
    trained.save_model(model_file)
    import shap, xgboost, sklearn

    explainer = shap.TreeExplainer(trained)
    contributions = explainer.shap_values(x[2][:1])[0]
    base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
    prediction = float(pred[0])
    assert abs(base + float(contributions.sum()) - prediction) < 1e-4
    # Temporal evaluation reserves separated calendar windows. Report insufficiency if embargo consumes them.
    dates = sorted({r["feature_end"] for r in rows})
    split1 = dates[int(len(dates) * 0.45)]
    split2 = dates[int(len(dates) * 0.72)]
    temporal_train = [r for r in rows if r["feature_end"] < split1]
    temporal_val = [
        r for r in rows if r["feature_start"] >= split1 and r["feature_end"] < split2
    ]
    temporal_test = [r for r in rows if r["feature_start"] >= split2]
    temporal = {
        "status": "insufficient",
        "embargo_days": 7,
        "boundaries": [split1, split2],
        "counts": [len(temporal_train), len(temporal_val), len(temporal_test)],
        "reason": "El embargo consume la partición de validación o test en esta semilla.",
    }
    if all(len(s) >= 6 for s in (temporal_train, temporal_val, temporal_test)):
        tm = XGBRegressor(
            n_estimators=60, max_depth=2, reg_lambda=12, random_state=seed, n_jobs=1
        )
        tm.fit(
            np.array([r["x"] for r in temporal_train]),
            np.array([r["target"] for r in temporal_train]),
        )
        ty = np.array([r["target"] for r in temporal_test])
        tp = tm.predict(np.array([r["x"] for r in temporal_test]))
        temporal.update(
            status="completed",
            metrics=report_metrics(
                ty, tp, np.array([r["participant_id"] for r in temporal_test]), seed
            ),
            reason=None,
        )
    report = {
        "name": "XGBoost-DEMO — CHECKIN_DEMO_V1",
        "status": "demo_trained",
        "clinical_evidence": False,
        "task": job.payload["task"],
        "seed": seed,
        "participants": len(people),
        "labels": len(rows),
        "coverage": {
            "predicted_participants": len(test_ids),
            "eligible_participants": len(people),
            "excluded_reason": "Historial sin suficientes días elegibles",
        },
        "partitions": {
            "train": sorted(train_ids),
            "validation": sorted(val_ids),
            "test": sorted(test_ids),
        },
        "metrics": metrics,
        "temporal": temporal,
        "validation_mae": selected,
        "feature_version": FEATURE_VERSION,
        "columns": columns,
        "units": {
            c: (
                "proporción"
                if c.endswith(("available", "robust_deviation", "coverage"))
                else "min"
                if "minutes" in c
                else "eventos"
            )
            for c in columns
        },
        "sha256": hashlib.sha256(model_file.read_bytes()).hexdigest(),
        "dependencies": {
            "python": platform.python_version(),
            "xgboost": xgboost.__version__,
            "scikit-learn": sklearn.__version__,
            "shap": shap.__version__,
        },
        "created_at": now().isoformat(),
        "shap": {
            "baseline": base,
            "prediction": prediction,
            "contributions": dict(zip(columns, map(float, contributions))),
            "unit": "puntos CHECKIN_DEMO_V1",
            "notice": "Variables que influyeron en la estimación del modelo; no causas.",
        },
        "notice": "Datos y etiquetas sintéticos. Ninguna métrica constituye evidencia clínica. No se promociona a LAB.",
    }
    (folder / "model-card.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    (folder / "dataset-manifest.json").write_text(
        json.dumps(
            {
                "mode": "DEMO",
                "rows": len(rows),
                "seed": seed,
                "columns": columns,
                "instrument": "CHECKIN_DEMO_V1",
                "records": [{k: v for k, v in r.items() if k != "x"} for r in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report
