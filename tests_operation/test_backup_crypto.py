"""AES-GCM backup helpers: roundtrip, tamper detection, key/fail-closed rules."""
import json

import pytest

import operation_backup_crypto as bc


def _keyfile(tmp_path, data=b"x" * 48):
    p = tmp_path / "backup.key"
    p.write_bytes(data)
    return p


def test_seal_unseal_roundtrip(tmp_path):
    data_key, _ = bc.load_keys(_keyfile(tmp_path))
    nonce, blob = bc.seal(data_key, b"secreto de prueba")
    assert blob != b"secreto de prueba"
    assert bc.unseal(data_key, nonce, blob) == b"secreto de prueba"


def test_unseal_rejects_tampered_ciphertext(tmp_path):
    data_key, _ = bc.load_keys(_keyfile(tmp_path))
    nonce, blob = bc.seal(data_key, b"payload")
    broken = bytearray(blob)
    broken[0] ^= 0x01
    with pytest.raises(SystemExit):
        bc.unseal(data_key, nonce, bytes(broken))


def test_unseal_rejects_wrong_key(tmp_path):
    a = tmp_path / "a.key"; a.write_bytes(b"a" * 48)
    b = tmp_path / "b.key"; b.write_bytes(b"b" * 48)
    k1, _ = bc.load_keys(a)
    k2, _ = bc.load_keys(b)
    nonce, blob = bc.seal(k1, b"payload")
    with pytest.raises(SystemExit):
        bc.unseal(k2, nonce, blob)


def test_manifest_hmac_detects_change(tmp_path):
    _, mkey = bc.load_keys(_keyfile(tmp_path))
    manifest = json.dumps({"format": "acompana-backup-v1-enc"}).encode()
    sig = bc.manifest_hmac(mkey, manifest)
    assert bc.manifest_hmac_ok(mkey, manifest, sig)
    assert bc.manifest_hmac_ok(mkey, manifest, sig + "\n")
    assert not bc.manifest_hmac_ok(mkey, manifest + b" ", sig)


def test_load_keys_fail_closed_on_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        bc.load_keys(tmp_path / "nope.key")


def test_load_keys_rejects_low_entropy(tmp_path):
    weak = tmp_path / "weak.key"
    weak.write_bytes(b"short")
    with pytest.raises(SystemExit):
        bc.load_keys(weak)


def test_data_and_manifest_keys_differ(tmp_path):
    dk, mk = bc.load_keys(_keyfile(tmp_path))
    assert dk != mk
