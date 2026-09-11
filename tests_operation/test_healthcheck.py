"""operation_healthcheck: pure evaluators, redaction, compose parsing, CLI wiring."""
from datetime import datetime, timedelta, timezone

import pytest

import operation_healthcheck as hc

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


# --- redaction -----------------------------------------------------------

def test_redact_hides_dsn_and_secrets():
    assert "acompana" not in hc.redact("postgresql://acompana:s3cr3t@db:5432/acompana")
    assert hc.redact("password=hunter2 more") == "[redacted] more"
    assert "tok_abc" not in hc.redact("authorization: Bearer tok_abc")


# --- API ----------------------------------------------------------------

def test_evaluate_api_ok():
    r = hc.evaluate_api(200, {"status": "ok", "mode": "REAL", "version": "0.1.0"})
    assert r["status"] == "ok" and r["mode"] == "REAL"


def test_evaluate_api_down_on_error_or_5xx():
    assert hc.evaluate_api(None, None, error="ConnRefused")["status"] == "down"
    assert hc.evaluate_api(503, {})["status"] == "down"


def test_evaluate_api_degraded_when_status_not_ok():
    assert hc.evaluate_api(200, {"status": "starting"})["status"] == "degraded"


# --- database ---------------------------------------------------------

def test_evaluate_database_ok_and_slow():
    assert hc.evaluate_database(True, 12.0, False, 3)["status"] == "ok"
    assert hc.evaluate_database(True, 1500.0, False, 3)["status"] == "degraded"
    assert hc.evaluate_database(False, None, None, None, error="boom")["status"] == "down"


# --- worker (liveness by effect) -------------------------------------

def test_worker_ok_only_with_live_lease():
    jobs = [
        {"state": "completed", "lease_until": None, "created_at": NOW - timedelta(hours=1)},
        {"state": "running", "lease_until": NOW + timedelta(minutes=20), "created_at": NOW},
    ]
    r = hc.evaluate_worker(jobs, NOW, 15)
    assert r["status"] == "ok" and "worker activo" in r["detail"]


def test_worker_degraded_on_expired_lease():
    jobs = [{"state": "running", "lease_until": NOW - timedelta(minutes=1), "created_at": NOW - timedelta(hours=1)}]
    r = hc.evaluate_worker(jobs, NOW, 15)
    assert r["status"] == "degraded" and r["expired_leases"] == 1


def test_worker_degraded_on_stale_queue():
    jobs = [{"state": "queued", "lease_until": None, "created_at": NOW - timedelta(minutes=40)}]
    r = hc.evaluate_worker(jobs, NOW, 15)
    assert r["status"] == "degraded" and r["stale_queued"] == 1


def test_worker_unknown_when_no_work():
    assert hc.evaluate_worker([], NOW, 15)["status"] == "unknown"
    fresh = [{"state": "queued", "lease_until": None, "created_at": NOW - timedelta(minutes=2)}]
    r = hc.evaluate_worker(fresh, NOW, 15)
    assert r["status"] == "unknown"  # not ok: nothing proves the worker is alive
    old_terminal = [{"state": "completed", "lease_until": None, "created_at": NOW - timedelta(days=2)}]
    assert hc.evaluate_worker(old_terminal, NOW, 15)["status"] == "unknown"


# --- overall ---------------------------------------------------------

def test_overall_precedence():
    assert hc.overall({"a": {"status": "ok"}, "b": {"status": "degraded"}}) == "degraded"
    assert hc.overall({"a": {"status": "down"}, "b": {"status": "degraded"}}) == "down"
    assert hc.overall({"a": {"status": "ok"}, "b": {"status": "unknown"}}) == "unknown"
    assert hc.overall({"a": {"status": "degraded"}, "b": {"status": "unknown"}}) == "degraded"
    assert hc.overall({"a": {"status": "ok"}}) == "ok"


# --- compose target -------------------------------------------------

def test_evaluate_compose_maps_services():
    rows = [
        {"Service": "db", "State": "running", "Health": "healthy"},
        {"Service": "api", "State": "running", "Health": "healthy"},
        {"Service": "worker", "State": "running", "Health": ""},
        {"Service": "web", "State": "exited", "Health": ""},
        # proxy missing
    ]
    comps = hc.evaluate_compose(rows)
    assert comps["database"]["status"] == "ok"
    assert comps["worker"]["status"] == "ok"
    assert "no prueba consumo" in comps["worker"]["detail"]
    assert comps["web"]["status"] == "down"
    assert comps["proxy"]["status"] == "down"


def test_compose_ps_parses_ndjson(monkeypatch):
    class R:
        stdout = '{"Service":"api","State":"running","Health":"healthy"}\n{"Service":"db","State":"running","Health":"healthy"}'
    monkeypatch.setattr(hc.subprocess, "run", lambda *a, **k: R())
    rows = hc.compose_ps("infra/compose.REAL.yaml", None)
    assert {r["Service"] for r in rows} == {"api", "db"}


def test_cli_compose_missing_file_exits():
    with pytest.raises(SystemExit):
        hc.run(["--target", "compose"])


def test_cli_direct_requires_urls(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MONITOR_DATABASE_URL", raising=False)
    monkeypatch.delenv("MONITOR_API_URL", raising=False)
    with pytest.raises(SystemExit):
        hc.run(["--target", "direct"])


def test_cli_direct_unknown_worker_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(hc, "probe_database", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(hc, "probe_api", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(hc, "probe_worker", lambda *a, **k: {"status": "unknown", "detail": "sin trabajo"})
    code = hc.run(["--target", "direct", "--api-url", "http://x/health", "--database-url", "postgresql://u@h/d"])
    out = capsys.readouterr().out
    assert code == 1 and '"overall": "unknown"' in out


def test_cli_compose_down_exit_code(monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError("docker")
    monkeypatch.setattr(hc.subprocess, "run", boom)
    code = hc.run(["--target", "compose", "--compose-file", "x.yaml"])
    assert code == 2
    assert "docker" in capsys.readouterr().out
