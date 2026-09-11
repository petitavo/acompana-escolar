from sqlalchemy import select
from app.db import *
from fixtures.generate import generate
from ml.pipeline import dataset, train, COLUMNS


def test_demo_participant_split_no_target_features_and_shap_sum():
    with SessionLocal.begin() as db:
        generate(db)
        rows = dataset(db, "prospective")
        assert len(rows) > 24
        concurrent = dataset(db, "concurrent")
        assert any(r["x"][-1] > 0 for r in concurrent)
        assert all(len(r["x"]) == len(COLUMNS) + 3 for r in concurrent)
        for r in rows:
            assert utc(r["cutoff_at"]) <= utc(r["label_recall_start"])
        assert not any("target" in c or "answer" in c or "_id" in c for c in COLUMNS)
        job = Job(
            kind="training",
            actor=db.scalar(select(User.id).where(User.role == "researcher")),
            payload={"task": "prospective", "seed": 42},
        )
        db.add(job)
        db.flush()
        result = train(db, job)
        sets = result["partitions"]
        assert not set(sets["train"]) & set(sets["test"])
        assert not set(sets["validation"]) & set(sets["test"])
        shap = result["shap"]
        assert (
            abs(
                shap["baseline"]
                + sum(shap["contributions"].values())
                - shap["prediction"]
            )
            < 1e-4
        )
        assert result["clinical_evidence"] is False
