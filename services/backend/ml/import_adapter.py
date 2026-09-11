"""Compatibilidad de importaciones; no habilita entrenamiento real ni deserializa modelos."""

import json
from pathlib import Path
import pandas as pd

REQUIRED = {
    "participant_id",
    "cutoff_at",
    "feature_start",
    "feature_end",
    "label_recall_start",
    "label_recall_end",
    "target",
    "provenance",
}


def inspect(path, manifest_path):
    path = Path(path)
    manifest = json.loads(Path(manifest_path).read_text())
    if path.suffix not in (".csv", ".parquet"):
        raise ValueError("Solo CSV/Parquet")
    for key in (
        "source",
        "authorization",
        "units",
        "instrument",
        "instrument_version",
        "environment",
        "task",
    ):
        if not manifest.get(key):
            raise ValueError("Manifest incompleto: " + key)
    frame = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
    missing = sorted(REQUIRED - set(frame.columns))
    return {
        "compatible": not missing,
        "missing_columns": missing,
        "rows": len(frame),
        "participants": int(frame.participant_id.nunique())
        if "participant_id" in frame
        else 0,
        "manifest": manifest,
        "notice": "Compatibilidad de esquema únicamente. No acredita equivalencia de sensores, unidades o etiquetas. No se han importado datos.",
    }
