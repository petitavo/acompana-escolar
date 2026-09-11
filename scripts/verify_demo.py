"""Readback del experimento y exportación DEMO usando la API autenticada."""

import json, time
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
credentials = json.loads((root / ".runtime/credentials-demo.json").read_text())[
    "credentials"
]
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as c:
    login = c.post(
        "/api/v1/auth/login",
        json={
            "username": "investigador.demo",
            "password": credentials["investigador.demo"],
        },
    )
    login.raise_for_status()
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    r = c.post(
        "/api/v1/lab/training-runs",
        headers={"Idempotency-Key": "final-prospective-demo"},
        json={"seed": 20260906, "task": "prospective"},
    )
    r.raise_for_status()
    ident = r.json()["id"]
    for _ in range(60):
        j = c.get("/api/v1/lab/training-runs/" + ident).json()
        if j["state"] in ("completed", "failed"):
            break
        time.sleep(1)
    assert j["state"] == "completed", j
    (root / "docs/model-card-demo.json").write_text(
        json.dumps(j["result"], ensure_ascii=False, indent=2)
    )
    r = c.post(
        "/api/v1/lab/exports",
        headers={"Idempotency-Key": "final-export-demo"},
        json={
            "kind": "features",
            "format": "csv",
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-09-06T00:00:00Z",
        },
    )
    r.raise_for_status()
    ident = r.json()["id"]
    for _ in range(30):
        j = c.get("/api/v1/lab/training-runs/" + ident).json()
        if j["state"] == "completed":
            break
        time.sleep(1)
    result = c.get("/api/v1/lab/exports/" + ident + "/download")
    result.raise_for_status()
    assert "synthetic" in result.text or "DEMO" in result.text
    print(
        "API→worker→modelo DEMO y exportación autenticada verificados. Model card: docs/model-card-demo.json"
    )
