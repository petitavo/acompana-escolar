"""operation_release: content manifest build, Ed25519 signing, verification."""
import json
import shutil

import pytest

import operation_release as rel

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")


def test_build_and_verify_roundtrip(tmp_path):
    keydir = tmp_path / "keys"
    rel.main(["keygen", "--key-dir", str(keydir)])
    priv = keydir / "release-ed25519.key"
    pub = keydir / "release-ed25519.pub"
    assert oct(priv.stat().st_mode)[-3:] == "600"

    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--sign-key", str(priv), "--out-dir", str(out)])
    manifest = out / "RELEASE-MANIFEST.json"
    assert (out / "RELEASE-MANIFEST.sig").is_file()

    data = json.loads(manifest.read_bytes())
    assert data["format"] == "acompana-release-v1"
    assert data["git"]["commits"] == "none"
    assert data["source"]["file_count"] > 0

    assert rel.verify(manifest, str(pub)) == 0


def test_verify_detects_source_divergence(tmp_path):
    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--out-dir", str(out)])
    manifest = out / "RELEASE-MANIFEST.json"
    data = json.loads(manifest.read_bytes())
    first = next(iter(data["source"]["files"]))
    data["source"]["files"][first] = "0" * 64
    manifest.write_bytes(json.dumps(data, indent=2, sort_keys=True).encode())
    assert rel.verify(manifest, None) == 4


def test_verify_rejects_tampered_manifest_signature(tmp_path):
    keydir = tmp_path / "keys"
    rel.main(["keygen", "--key-dir", str(keydir)])
    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--sign-key", str(keydir / "release-ed25519.key"), "--out-dir", str(out)])
    manifest = out / "RELEASE-MANIFEST.json"
    blob = bytearray(manifest.read_bytes())
    blob[20] ^= 0x01
    manifest.write_bytes(bytes(blob))
    assert rel.verify(manifest, str(keydir / "release-ed25519.pub")) == 3


def test_keygen_refuses_to_overwrite(tmp_path):
    keydir = tmp_path / "keys"
    rel.main(["keygen", "--key-dir", str(keydir)])
    with pytest.raises(SystemExit):
        rel.main(["keygen", "--key-dir", str(keydir)])


def test_build_apk_hash_recorded(tmp_path):
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"not really an apk")
    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--apk", str(apk), "--out-dir", str(out)])
    data = json.loads((out / "RELEASE-MANIFEST.json").read_bytes())
    assert data["artifacts"]["apk"]["sha256"]
    assert data["artifacts"]["apk"]["name"] == "app.apk"
    assert data["artifacts"]["apk"]["bytes"] == len(b"not really an apk")


def _build_with_apk(tmp_path):
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"apk bytes v1")
    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--apk", str(apk), "--out-dir", str(out)])
    return apk, out / "RELEASE-MANIFEST.json"


def test_verify_requires_apk_when_declared(tmp_path):
    _, manifest = _build_with_apk(tmp_path)
    assert rel.verify(manifest, None) == 5  # declared APK, none supplied -> not verified


def test_verify_accepts_matching_apk(tmp_path):
    apk, manifest = _build_with_apk(tmp_path)
    assert rel.verify(manifest, None, str(apk)) == 0


def test_verify_rejects_altered_apk(tmp_path):
    apk, manifest = _build_with_apk(tmp_path)
    apk.write_bytes(b"apk bytes v2 tampered")
    assert rel.verify(manifest, None, str(apk)) == 5


def test_verify_rejects_missing_apk_file(tmp_path):
    apk, manifest = _build_with_apk(tmp_path)
    apk.unlink()
    assert rel.verify(manifest, None, str(apk)) == 5


def test_build_refuses_to_overwrite_release(tmp_path):
    out = tmp_path / "rel"
    rel.main(["build", "--version", "0.0.0-test", "--out-dir", str(out)])
    with pytest.raises(SystemExit):
        rel.main(["build", "--version", "0.0.0-test", "--out-dir", str(out)])
