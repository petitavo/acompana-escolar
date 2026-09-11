"""operation_rotate_secrets: dry-run safety, DSN redaction, env rewrite."""
import pytest

import operation_rotate_secrets as rot


def test_redact_dsn_hides_password():
    out = rot._redact_dsn("postgresql+psycopg://acompana:s3cr3t@db:5432/acompana")
    assert "s3cr3t" not in out and "acompana" in out and "[redacted]" in out


def test_dry_run_touches_nothing(tmp_path, capsys):
    key = tmp_path / "new-db-password"
    code = rot.rotate("postgresql://acompana:pw@db:5432/acompana", "acompana", key, None, apply=False)
    assert code == 0
    assert not key.exists()
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "pw" not in out


def test_refuses_existing_key_file(tmp_path):
    key = tmp_path / "k"
    key.write_text("x")
    with pytest.raises(SystemExit):
        rot.rotate("postgresql://u:p@h/db", "acompana", key, None, apply=False)


def test_rewrite_env_updates_both_lines(tmp_path):
    env = tmp_path / "operation.env.REAL"
    env.write_text(
        "POSTGRES_USER=acompana\n"
        "POSTGRES_PASSWORD=old\n"
        "DATABASE_URL=postgresql+psycopg://acompana:old@db:5432/acompana\n"
        "SCHOOL_HOST=escuela.example\n"
    )
    rot._rewrite_env(env, "acompana", "n3w/pass+word")
    text = env.read_text()
    assert "POSTGRES_PASSWORD=n3w/pass+word" in text
    assert "postgresql+psycopg://acompana:n3w%2Fpass%2Bword@db:5432/acompana" in text
    assert "SCHOOL_HOST=escuela.example" in text
    assert oct(env.stat().st_mode)[-3:] == "600"


def test_rewrite_env_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        rot._rewrite_env(tmp_path / "absent", "acompana", "x")


def test_cli_requires_dsn(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit):
        rot.main(["db-password", "--role", "acompana", "--new-key-file", "/tmp/whatever"])
