"""Verifiable release packaging & update procedure for Acompaña Escolar (A10).

The branch has no commits, so a release is pinned by a content manifest instead of
a git SHA: every tracked source file hashed (sha256), plus the APK hash when a
build is provided, plus environment notes. The manifest is signed with a detached
Ed25519 signature using the system ``openssl`` (no extra dependency).

    operation_release.py keygen  --key-dir .runtime/release-keys
    operation_release.py build   --version 0.3.0 [--apk PATH] --sign-key KEY
    operation_release.py verify  --manifest PATH --verify-key PUB [--apk PATH]

``verify`` checks the signature, that the working tree matches every hashed source
file, AND every declared artifact (APK hash + size): if the manifest declares an
APK, ``--apk`` is required and a missing/altered file fails the verification.
``build`` refuses to overwrite an existing release or key (fail-closed).

Exit codes: 0 ok · 3 signature/manifest invalid · 4 source divergence ·
5 declared artifact missing or altered.

Secrets: the private key path is an argument, never its contents; nothing secret
is printed. ``build`` writes under ``.runtime/releases/<version>/`` (git-ignored).
This packages a release; it does not publish or deploy anything.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def tracked_files()->list[Path]:
    try:
        out=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
        names=sorted({n for n in out.split('\0') if n})
        if names:
            return [ROOT/n for n in names if (ROOT/n).is_file()]
    except (subprocess.CalledProcessError,FileNotFoundError):
        pass
    skip={'.git','.venv','.bootstrap','.runtime','.tooling','node_modules','dist','__pycache__','build','.dart_tool'}
    return [p for p in ROOT.rglob('*') if p.is_file() and not any(part in skip for part in p.relative_to(ROOT).parts)]


def canonical(manifest:dict)->bytes:
    return json.dumps(manifest,indent=2,sort_keys=True).encode()


def openssl(*args:str,**kw)->subprocess.CompletedProcess:
    return subprocess.run(['openssl',*args],check=True,capture_output=True,**kw)


def keygen(key_dir:Path)->None:
    key_dir.mkdir(parents=True,exist_ok=True);key_dir.chmod(0o700)
    priv=key_dir/'release-ed25519.key';pub=key_dir/'release-ed25519.pub'
    if priv.exists() or pub.exists():raise SystemExit(f'Ya existe una clave en {key_dir}; no se sobrescribe (fail-closed)')
    fd=os.open(priv,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(fd)
    openssl('genpkey','-algorithm','ed25519','-out',str(priv))
    priv.chmod(0o600)
    openssl('pkey','-in',str(priv),'-pubout','-out',str(pub))
    print(f'Clave privada: {priv} (0600, fuera de Git)\nClave pública: {pub}  -> distribuir con las verificaciones')


def build(version:str,apk:str|None,sign_key:str|None,out_dir:Path|None)->Path:
    out_dir=out_dir or ROOT/'.runtime'/'releases'/version
    out_dir.mkdir(parents=True,exist_ok=True);out_dir.chmod(0o700)
    if (out_dir/'RELEASE-MANIFEST.json').exists():
        raise SystemExit(f'Ya existe una release en {out_dir}; no se sobrescribe (fail-closed)')
    files={str(p.relative_to(ROOT)):_sha256(p) for p in sorted(tracked_files())}
    manifest={
        'format':'acompana-release-v1',
        'version':version,
        'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source':{'file_count':len(files),'files':files},
        'git':{'commits':'none','note':'rama sin commits: la identidad es este manifiesto de contenido'},
        'artifacts':{},
    }
    if apk:
        ap=Path(apk)
        if not ap.is_file():raise SystemExit(f'APK no encontrado: {ap}')
        manifest['artifacts']['apk']={'name':ap.name,'sha256':_sha256(ap),'bytes':ap.stat().st_size}
    mpath=out_dir/'RELEASE-MANIFEST.json'
    mpath.write_bytes(canonical(manifest))
    if sign_key:
        sk=Path(sign_key)
        if not sk.is_file():raise SystemExit('Clave de firma ausente (fail-closed)')
        openssl('pkeyutl','-sign','-inkey',str(sk),'-rawin','-in',str(mpath),'-out',str(out_dir/'RELEASE-MANIFEST.sig'))
        print(f'Manifiesto firmado: {out_dir/"RELEASE-MANIFEST.sig"}')
    else:
        print('AVISO: manifiesto sin firmar. Para el procedimiento de producción use --sign-key.')
    print(f'Release empaquetada en {out_dir} ({len(files)} archivos).')
    return mpath


def _check_artifacts(manifest:dict,apk:str|None)->tuple[int,list[str]]:
    problems=[]
    declared=manifest.get('artifacts',{})
    if 'apk' in declared:
        want=declared['apk']
        if not apk:
            return 5,[f'el manifiesto declara el APK "{want["name"]}"; pase --apk RUTA para verificarlo']
        ap=Path(apk)
        if not ap.is_file():
            problems.append(f'APK no encontrado en {ap}')
        else:
            if _sha256(ap)!=want['sha256']:problems.append('el sha256 del APK no coincide con el manifiesto')
            if ap.stat().st_size!=want.get('bytes'):problems.append('el tamaño del APK no coincide con el manifiesto')
    return (5 if problems else 0),problems


def verify(manifest_path:Path,verify_key:str|None,apk:str|None=None)->int:
    raw=manifest_path.read_bytes()
    if verify_key:
        vk=Path(verify_key)
        sig=manifest_path.with_suffix('.sig')
        if not sig.is_file():raise SystemExit('Falta RELEASE-MANIFEST.sig')
        try:
            openssl('pkeyutl','-verify','-pubin','-inkey',str(vk),'-rawin','-in',str(manifest_path),'-sigfile',str(sig))
        except subprocess.CalledProcessError:
            print('FIRMA INVÁLIDA');return 3
        print('Firma Ed25519 válida.')
    try:
        manifest=json.loads(raw)
    except json.JSONDecodeError:
        print('MANIFIESTO ILEGIBLE');return 3
    if manifest.get('format')!='acompana-release-v1':raise SystemExit('Formato de manifiesto desconocido')
    mismatched=[]
    for rel,digest in manifest['source']['files'].items():
        p=ROOT/rel
        if not p.is_file() or _sha256(p)!=digest:mismatched.append(rel)
    if mismatched:
        print(f'DIVERGENCIA: {len(mismatched)} archivo(s) no coinciden con el manifiesto:')
        for m in mismatched[:20]:print('  -',m)
        return 4
    code,problems=_check_artifacts(manifest,apk)
    if code:
        print('ARTEFACTO DECLARADO SIN VERIFICAR:')
        for pr in problems:print('  -',pr)
        return code
    extra=f' + APK {manifest["artifacts"]["apk"]["name"]}' if 'apk' in manifest.get('artifacts',{}) else ''
    print(f'VERIFICADO: {len(manifest["source"]["files"])} archivos{extra} coinciden con la release {manifest["version"]}.')
    return 0


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='cmd',required=True)
    g=s.add_parser('keygen');g.add_argument('--key-dir',default=str(ROOT/'.runtime'/'release-keys'))
    bd=s.add_parser('build');bd.add_argument('--version',required=True);bd.add_argument('--apk');bd.add_argument('--sign-key');bd.add_argument('--out-dir')
    v=s.add_parser('verify');v.add_argument('--manifest',required=True);v.add_argument('--verify-key');v.add_argument('--apk')
    a=p.parse_args(argv)
    if a.cmd=='keygen':keygen(Path(a.key_dir));return 0
    if a.cmd=='build':build(a.version,a.apk,a.sign_key,Path(a.out_dir) if a.out_dir else None);return 0
    return verify(Path(a.manifest),a.verify_key,a.apk)


if __name__=='__main__':
    sys.exit(main())
