"""write_backup / restore_backup: atomicity, fail-closed, no plaintext leaks.

No PostgreSQL: pg_dump is a fake ``dump_writer`` and pg_restore is the ``consumer``.
"""
import json

import pytest

import operation_backup_crypto as bc

DUMP = b"PGDMP fake custom dump \x00\x01\x02"


def _artifacts(tmp_path):
    """Mirror the real layout: the path passed to write_backup is ARTIFACT_DIR/MODE,
    whose *contents* land under the backup's ``artifacts/``."""
    d = tmp_path / "artifacts_src"
    (d / "model-a1b2").mkdir(parents=True)
    (d / "model-a1b2" / "model.bin").write_bytes(b"weights")
    (d / "deletions.jsonl").write_text('{"participant_id":"p1"}\n')
    return d


def _keyfile(tmp_path, name="k", data=b"z" * 48):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def _writer(payload=DUMP, fail=False):
    def w(path):
        if fail:
            raise RuntimeError("pg_dump reventó")
        path.write_bytes(payload)
    return w


def _tree_hashes(folder):
    return {str(p.relative_to(folder)): bc.sha256_file(p)
            for p in sorted(folder.rglob("*")) if p.is_file()}


# --- backup: happy paths ------------------------------------------------

def test_plaintext_backup_layout(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), None)
    assert (dest / "database.dump").read_bytes() == DUMP
    assert (dest / "artifacts" / "model-a1b2" / "model.bin").read_bytes() == b"weights"
    m = json.loads((dest / "manifest.json").read_text())
    assert m["format"] == "acompana-backup-v1"
    assert "database.dump" in m["files"] and not (dest / "manifest.sig").exists()


def test_encrypted_backup_has_no_plaintext(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    names = sorted(p.name for p in dest.iterdir())
    assert names == ["artifacts.tar.enc", "database.dump.enc", "manifest.json", "manifest.sig"]
    assert b"weights" not in (dest / "artifacts.tar.enc").read_bytes()
    assert b"PGDMP" not in (dest / "database.dump.enc").read_bytes()
    m = json.loads((dest / "manifest.json").read_text())
    assert m["format"] == "acompana-backup-v1-enc" and "encryption" in m


# --- backup: failure paths --------------------------------------------

def _no_staging_left(parent):
    return not any(p.name.startswith(".acompana-bkp-") for p in parent.iterdir())


def test_backup_bad_key_never_runs_dump(tmp_path):
    dest = tmp_path / "bkp"
    seen = []
    def w(path):
        seen.append(path)
        path.write_bytes(DUMP)
    with pytest.raises(SystemExit):
        bc.write_backup(dest, w, _artifacts(tmp_path), str(tmp_path / "absent.key"))
    assert seen == []
    assert not dest.exists() and _no_staging_left(tmp_path)


def test_backup_dump_failure_leaves_nothing(tmp_path):
    dest = tmp_path / "bkp"
    with pytest.raises(RuntimeError):
        bc.write_backup(dest, _writer(fail=True), _artifacts(tmp_path), _keyfile(tmp_path))
    assert not dest.exists() and _no_staging_left(tmp_path)


def test_backup_encryption_failure_leaves_no_pretend_encrypted_dir(tmp_path, monkeypatch):
    dest = tmp_path / "bkp"
    monkeypatch.setattr(bc, "seal", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gcm falló")))
    with pytest.raises(RuntimeError):
        bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    assert not dest.exists() and _no_staging_left(tmp_path)


def test_backup_refuses_existing_destination(tmp_path):
    dest = tmp_path / "bkp"
    dest.mkdir()
    with pytest.raises(SystemExit):
        bc.write_backup(dest, _writer(), _artifacts(tmp_path), None)


def test_backup_files_are_private(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    for p in dest.rglob("*"):
        assert oct(p.stat().st_mode)[-3:] == ("700" if p.is_dir() else "600")


# --- restore ---------------------------------------------------------

def _consume_ok(calls):
    def c(dump_path, artifacts_path, manifest):
        calls.append((dump_path.read_bytes(), sorted(x.name for x in artifacts_path.rglob("*"))))
        return "done"
    return c


def test_encrypted_restore_roundtrip(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    calls = []
    out = bc.restore_backup(dest, _keyfile(tmp_path), _consume_ok(calls), tmp_dir=tmp_path)
    assert out == "done"
    assert calls[0][0] == DUMP
    assert "model.bin" in calls[0][1]


def test_restore_requires_key_for_encrypted(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    with pytest.raises(SystemExit):
        bc.restore_backup(dest, None, _consume_ok([]), tmp_dir=tmp_path)


def test_restore_wrong_key_does_not_touch_source(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path, "a", b"a" * 48))
    before = _tree_hashes(dest)
    with pytest.raises(SystemExit):
        bc.restore_backup(dest, _keyfile(tmp_path, "b", b"b" * 48), _consume_ok([]), tmp_dir=tmp_path)
    assert _tree_hashes(dest) == before


def test_restore_rejects_tampered_ciphertext(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    blob = bytearray((dest / "database.dump.enc").read_bytes())
    blob[0] ^= 0x01
    (dest / "database.dump.enc").write_bytes(bytes(blob))
    with pytest.raises(SystemExit):
        bc.restore_backup(dest, _keyfile(tmp_path), _consume_ok([]), tmp_dir=tmp_path)


def test_restore_rejects_tampered_manifest(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    m = json.loads((dest / "manifest.json").read_text())
    m["format"] = "acompana-backup-v1-enc "
    (dest / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True))
    with pytest.raises(SystemExit):
        bc.restore_backup(dest, _keyfile(tmp_path), _consume_ok([]), tmp_dir=tmp_path)


def test_restore_consumer_failure_cleans_plaintext(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), _keyfile(tmp_path))
    before = _tree_hashes(dest)

    def boom(dump_path, artifacts_path, manifest):
        assert dump_path.read_bytes() == DUMP  # plaintext really was materialized
        raise RuntimeError("pg_restore falló")

    with pytest.raises(RuntimeError):
        bc.restore_backup(dest, _keyfile(tmp_path), boom, tmp_dir=tmp_path)
    assert _tree_hashes(dest) == before
    assert not any(p.name.startswith("acompana-restore-") for p in tmp_path.iterdir())


def test_plaintext_restore_uses_source_without_mutating_it(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), None)
    before = _tree_hashes(dest)
    seen = {}

    def c(dump_path, artifacts_path, manifest):
        seen["dump"] = dump_path
        return 0

    bc.restore_backup(dest, None, c, tmp_dir=tmp_path)
    assert seen["dump"] == dest / "database.dump"
    assert _tree_hashes(dest) == before


def test_restore_detects_checksum_drift_in_plaintext(tmp_path):
    dest = tmp_path / "bkp"
    bc.write_backup(dest, _writer(), _artifacts(tmp_path), None)
    (dest / "database.dump").write_bytes(DUMP + b"x")
    with pytest.raises(SystemExit):
        bc.restore_backup(dest, None, _consume_ok([]), tmp_dir=tmp_path)
