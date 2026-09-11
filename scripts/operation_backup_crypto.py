"""Authenticated encryption + atomic orchestration for the backup procedure (A10).

Kept in a separate importable module so ``scripts/product_backup.py`` and the
isolated tests exercise exactly the same code, including the failure paths.

Scheme: AES-256-GCM over each payload with a random 96-bit nonce; keys derived as
``sha256(secret || label)`` from a key file holding >= 32 random bytes; a separate
key authenticates the manifest with HMAC-SHA256.

Guarantees:
* the key file is validated *before* any dump/copy work begins;
* a backup is built in a private staging dir and moved into place with a single
  ``os.rename`` — a failure never leaves the destination, and never leaves a
  directory that claims to be encrypted while still holding plaintext;
* a restore decrypts into a private temp dir that is always removed, and never
  mutates the source copy.
"""
from __future__ import annotations
import hashlib
import hmac
import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Callable

DATA_LABEL = b"acompana-backup/data"
MANIFEST_LABEL = b"acompana-backup/manifest"
FORMATS = ("acompana-backup-v1", "acompana-backup-v1-enc")


def load_keys(path: str | Path) -> tuple[bytes, bytes]:
    kf = Path(path)
    if not kf.is_file():
        raise SystemExit("Falta el archivo de clave de cifrado; no se continúa (fail-closed)")
    raw = kf.read_bytes().strip()
    if len(raw) < 32:
        raise SystemExit("La clave de cifrado debe tener al menos 32 bytes de entropía")
    return (
        hashlib.sha256(raw + DATA_LABEL).digest(),
        hashlib.sha256(raw + MANIFEST_LABEL).digest(),
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seal(key: bytes, data: bytes) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(nonce, data, None)


def unseal(key: bytes, nonce: bytes, blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    try:
        return AESGCM(key).decrypt(nonce, blob, None)
    except InvalidTag:
        raise SystemExit("El descifrado falló: clave incorrecta o copia manipulada")


def manifest_hmac(manifest_key: bytes, manifest_bytes: bytes) -> str:
    return hmac.new(manifest_key, manifest_bytes, hashlib.sha256).hexdigest()


def manifest_hmac_ok(manifest_key: bytes, manifest_bytes: bytes, signature: str) -> bool:
    return hmac.compare_digest(manifest_hmac(manifest_key, manifest_bytes), signature.strip())


def _tar_members_safe(tf: tarfile.TarFile) -> None:
    for m in tf.getmembers():
        if m.name != "artifacts" and not m.name.startswith("artifacts/"):
            raise SystemExit("Tar de artefactos con rutas inesperadas")
        if m.islnk() or m.issym():
            raise SystemExit("Tar de artefactos con enlaces no permitidos")


def encrypt_backup_dir(folder: Path, data_key: bytes) -> dict:
    """In place inside a *staging* dir: replace ``database.dump`` + ``artifacts/``
    with AES-GCM blobs. Returns the ``encryption`` sub-manifest."""
    enc = {"algorithm": "AES-256-GCM", "kdf": "sha256(secret||label)"}
    n1, c1 = seal(data_key, (folder / "database.dump").read_bytes())
    (folder / "database.dump.enc").write_bytes(c1)
    (folder / "database.dump").unlink()
    enc["database"] = {"nonce": n1.hex()}

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        tf.add(folder / "artifacts", arcname="artifacts")
    n2, c2 = seal(data_key, buf.getvalue())
    (folder / "artifacts.tar.enc").write_bytes(c2)
    shutil.rmtree(folder / "artifacts")
    enc["artifacts"] = {"nonce": n2.hex()}
    return enc


def decrypt_backup_dir(src: Path, dest: Path, data_key: bytes, enc: dict) -> None:
    """Read ``*.enc`` from ``src`` and materialize plaintext into ``dest``.
    ``src`` is never modified."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "database.dump").write_bytes(
        unseal(data_key, bytes.fromhex(enc["database"]["nonce"]), (src / "database.dump.enc").read_bytes())
    )
    plain = unseal(data_key, bytes.fromhex(enc["artifacts"]["nonce"]), (src / "artifacts.tar.enc").read_bytes())
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r") as tf:
        _tar_members_safe(tf)
        tf.extractall(dest, filter="data")


def write_backup(
    dest: Path,
    dump_writer: Callable[[Path], None],
    artifacts_dir: Path,
    key_file: str | None,
) -> Path:
    """Atomically build a backup directory at ``dest``.

    ``dump_writer(path)`` must create the custom-format dump at ``path``.
    On *any* failure ``dest`` is not created and no staging dir survives.
    """
    dest = Path(dest).resolve()
    if dest.exists():
        raise SystemExit("El destino de la copia ya existe; no se sobrescribe")
    dest.parent.mkdir(parents=True, exist_ok=True)

    data_key = manifest_key = None
    if key_file:  # validate the key BEFORE dumping / copying anything
        data_key, manifest_key = load_keys(key_file)

    stage = Path(tempfile.mkdtemp(dir=str(dest.parent), prefix=".acompana-bkp-"))
    moved = False
    try:
        os.chmod(stage, 0o700)
        dump_writer(stage / "database.dump")
        if Path(artifacts_dir).exists():
            shutil.copytree(artifacts_dir, stage / "artifacts")
        else:
            (stage / "artifacts").mkdir()

        manifest: dict = {"format": FORMATS[0], "artifact_root": str(artifacts_dir)}
        if key_file:
            manifest["format"] = FORMATS[1]
            manifest["encryption"] = encrypt_backup_dir(stage, data_key)
        manifest["files"] = {
            str(p.relative_to(stage)): sha256_file(p)
            for p in sorted(stage.rglob("*"))
            if p.is_file()
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        if key_file:
            (stage / "manifest.sig").write_text(
                manifest_hmac(manifest_key, (stage / "manifest.json").read_bytes()) + "\n"
            )
        for p in sorted(stage.rglob("*")):
            p.chmod(0o700 if p.is_dir() else 0o600)
        os.chmod(stage, 0o700)
        os.rename(stage, dest)
        moved = True
    finally:
        if not moved:
            shutil.rmtree(stage, ignore_errors=True)
    return dest


def _validate_backup(src: Path, key_file: str | None) -> tuple[dict, bool, bytes | None]:
    src = src.resolve()
    manifest = json.loads((src / "manifest.json").read_text())
    if manifest.get("format") not in FORMATS:
        raise SystemExit("Formato de copia desconocido")
    encrypted = "encryption" in manifest
    if encrypted and not key_file:
        raise SystemExit("Copia cifrada: se requiere --key-file para restaurar (fail-closed)")
    if key_file and not encrypted:
        raise SystemExit("Se indicó --key-file pero la copia no está cifrada")
    data_key = None
    if encrypted:
        data_key, manifest_key = load_keys(key_file)  # validated before any work
        sig = (src / "manifest.sig").read_text() if (src / "manifest.sig").is_file() else ""
        if not manifest_hmac_ok(manifest_key, (src / "manifest.json").read_bytes(), sig):
            raise SystemExit("HMAC del manifiesto inválido: copia manipulada o clave incorrecta")
    for name, checksum in manifest["files"].items():
        p = (src / name).resolve()
        if not p.is_relative_to(src) or not p.is_file() or sha256_file(p) != checksum:
            raise SystemExit("Checksum o ruta inválidos en la copia")
    return manifest, encrypted, data_key


def restore_backup(
    src: Path,
    key_file: str | None,
    consumer: Callable[[Path, Path, dict], object],
    tmp_dir: str | Path | None = None,
):
    """Validate ``src``, then call ``consumer(dump_path, artifacts_path, manifest)``.

    For encrypted copies the plaintext lives only in a private temp dir that is
    removed no matter how ``consumer`` ends. ``src`` is never modified.
    """
    src = Path(src).resolve()
    manifest, encrypted, data_key = _validate_backup(src, key_file)
    if not encrypted:
        return consumer(src / "database.dump", src / "artifacts", manifest)
    work = Path(tempfile.mkdtemp(dir=str(tmp_dir) if tmp_dir else None, prefix="acompana-restore-"))
    try:
        os.chmod(work, 0o700)
        decrypt_backup_dir(src, work, data_key, manifest["encryption"])
        return consumer(work / "database.dump", work / "artifacts", manifest)
    finally:
        shutil.rmtree(work, ignore_errors=True)
