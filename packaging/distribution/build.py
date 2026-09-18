"""Assemble an isolated, relocatable offline payload without modifying the source venv."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import zipfile
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'packaging' / 'build' / 'installer-cache'
DOWNLOADS = {
    'python-3.12.10-embed-amd64.zip': ('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip', '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'),
    'ViGEmBus_1.22.0_x64_x86_arm64.exe': ('https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe', '89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a'),
    'innosetup-6.7.1.exe': ('https://github.com/jrsoftware/issrc/releases/download/is-6_7_1/innosetup-6.7.1.exe', '4d11e8050b6185e0d49bd9e8cc661a7a59f44959a621d31d11033124c4e8a7b0'),
}
ROOT_REQUIREMENTS = ['PySide6_Essentials', 'numpy', 'opencv-python', 'mss', 'rapidocr-onnxruntime', 'PyDirectInput']
CODE_DIRS = ('src/auto_modules',)
SECRET_KEYS = {'apikey', 'password', 'passwd', 'clientsecret', 'accesstoken', 'refreshtoken', 'privatekey', 'authorization', 'secret', 'token'}


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_destination(root: Path, name: str) -> Path:
    relative = PurePosixPath(str(name).replace('\\', '/'))
    if relative.is_absolute() or PureWindowsPath(name).drive or '..' in relative.parts:
        raise ValueError(f'Unsafe archive path: {name}')
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes destination: {name}')
    return target


def select_runtime_sources(root: Path):
    for name in ('main.py',):
        if (root / name).is_file():
            yield root / name
    for directory in CODE_DIRS:
        for path in sorted((root / directory).rglob('*.py')):
            if not path.is_symlink() and '__pycache__' not in path.parts and 'tests' not in path.relative_to(root).parts:
                yield path
    for path in sorted((root / 'resources').rglob('*')):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in {'.png', '.jpg', '.json', '.onnx', '.txt', '.md'}:
            yield path


def sanitize_config(value):
    if isinstance(value, dict):
        return {key: (None if key in {'monitor_region', 'monitor_logical_center'} else sanitize_config(item))
                for key, item in value.items() if key.lower().replace('_', '').replace('-', '') not in SECRET_KEYS}
    if isinstance(value, list):
        return [sanitize_config(item) for item in value]
    return value


def dependency_closure(requirements):
    selected = {}
    pending = list(requirements)
    while pending:
        requirement = Requirement(pending.pop())
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        name = canonicalize_name(requirement.name)
        dist = metadata.distribution(name)
        if requirement.specifier and dist.version not in requirement.specifier:
            raise ValueError(f'Dependency version mismatch: {requirement}, installed {dist.version}')
        if name in selected:
            continue
        direct = dist.read_text('direct_url.json')
        if direct and json.loads(direct).get('dir_info', {}).get('editable'):
            raise ValueError(f'Editable dependency is not portable: {name}')
        selected[name] = dist
        pending.extend(dist.requires or [])
    return [selected[name] for name in sorted(selected)]


def copy_distribution(dist, target: Path):
    site = Path(dist.locate_file('')).resolve()
    for entry in dist.files or []:
        name = str(entry).replace('\\', '/')
        # Console scripts are tied to the source interpreter; only library files travel.
        if '..' in PurePosixPath(name).parts or name.endswith(('.pyc', '.pth')) or '__pycache__' in name or name.endswith('/direct_url.json'):
            continue
        source = Path(dist.locate_file(entry)).resolve()
        if not source.is_relative_to(site) or not source.is_file():
            raise ValueError(f'Invalid dependency file: {dist.metadata["Name"]}: {entry}')
        output = safe_destination(target, name)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)


def copy_template(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == '.json':
        value = sanitize_config(json.loads(source.read_text(encoding='utf-8-sig')))
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        shutil.copy2(source, target)


def copy_native_runtime(python: Path):
    """Use the wheel's redistributables app-local, including ONNX-first startup."""
    qt = python / 'Lib' / 'site-packages' / 'PySide6'
    copied = {}
    for source in sorted(qt.glob('*140*.dll')):
        target = python / source.name
        if not target.exists():  # Keep CPython's own vcruntime version.
            shutil.copy2(source, target)
            copied[source.name] = {'source': 'PySide6_Essentials/PySide6/' + source.name, 'sha256': sha256(target)}
    for required in ('msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
        if not (python / required).is_file():
            raise ValueError(f'Missing app-local native runtime: {required}')
    return copied


def verified_download(name: str) -> Path:
    path = CACHE / name
    url, digest = DOWNLOADS[name]
    if not path.is_file() or sha256(path) != digest:
        raise ValueError(f'Missing or wrong cached artifact: {name}. Download {url} and verify SHA256 {digest}.')
    return path


def run(command):
    print('RUN', *map(str, command), flush=True)
    subprocess.run(list(map(str, command)), check=True)


def assemble(destination: Path, dotnet: Path, lock_file: Path):
    if sys.platform != 'win32' or sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 12) or platform.machine().lower() != 'amd64':
        raise ValueError('Build requires Windows x64 CPython 3.12; native wheels must match the embedded runtime.')
    if destination.exists():
        raise ValueError('Build destination must be new; existing releases are never deleted or overwritten.')
    locked = [line.strip() for line in lock_file.read_text().splitlines() if line.strip() and not line.startswith('#')]
    distributions = dependency_closure(locked)
    expected = {canonicalize_name(Requirement(line).name) for line in locked}
    if {canonicalize_name(d.metadata['Name']) for d in distributions} != expected:
        raise ValueError('Lock file is not the complete transitive dependency closure.')
    destination.mkdir(parents=True)
    python = destination / 'python'
    python.mkdir()
    with zipfile.ZipFile(verified_download('python-3.12.10-embed-amd64.zip')) as archive:
        for member in archive.infolist():
            target = safe_destination(python, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
    (python / 'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n../app\n../app/src\n', encoding='utf-8')
    for dist in distributions:
        print('Dependency', dist.metadata['Name'], dist.version, flush=True)
        copy_distribution(dist, python / 'Lib' / 'site-packages')
    native_runtime = copy_native_runtime(python)
    shutil.copytree(ROOT / 'packaging' / 'distribution' / 'licenses', destination / 'licenses')
    shutil.copy2(ROOT / 'packaging' / 'distribution' / 'THIRD_PARTY_NOTICES.md', destination / 'licenses')
    for source in select_runtime_sources(ROOT):
        target = safe_destination(destination / 'app', source.relative_to(ROOT).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(ROOT / 'packaging' / 'distribution' / 'smoke_check.py', destination / 'app' / 'smoke_check.py')
    templates = [ROOT / 'data' / 'config.json']
    templates.extend((ROOT / 'data' / 'virtual_gamepad' / 'configs').glob('controller-*.json'))
    templates.extend(p for p in (ROOT / 'data' / 'maps').rglob('*') if p.is_file() and not p.is_symlink()
                     and p.suffix.lower() in {'.json', '.npz', '.png'} and '.before_apply_' not in p.name)
    for source in templates:
        if not source.is_file():
            continue
        relative = source.relative_to(ROOT / 'data')
        copy_template(source, destination / 'defaults' / relative)
    prerequisites = destination / 'prerequisites'
    prerequisites.mkdir()
    driver = verified_download('ViGEmBus_1.22.0_x64_x86_arm64.exe')
    shutil.copy2(driver, prerequisites / driver.name)
    run([dotnet, 'publish', ROOT / 'services/virtual_gamepad/host/src/VirtualGamepadHost/VirtualGamepadHost.csproj', '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true', '-o', destination / 'host'])
    run([dotnet, 'publish', ROOT / 'packaging/installer/launcher/AutoModulesLauncher.csproj', '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true', '-p:PublishSingleFile=true', '-p:IncludeNativeLibrariesForSelfExtract=true', '-o', destination])
    subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                    "if ((Get-AuthenticodeSignature -LiteralPath $env:AUTO_MODULES_VERIFY_FILE).Status -ne 'Valid') { throw 'Bundled Python signature invalid' }"],
                   env={**os.environ, 'AUTO_MODULES_VERIFY_FILE': str(python / 'python.exe')}, check=True)
    (destination / 'BUILD-INFO.txt').write_text('Offline runtime assembled from pinned installed distribution records; development caches and identities excluded.\n', encoding='utf-8')
    # RECORD metadata and licenses from every selected wheel travel with the runtime.
    manifest = {'format': 1, 'python': '3.12.10', 'native_runtime': native_runtime, 'dependencies': {d.metadata['Name']: d.version for d in distributions},
                'upstream': {name: {'url': url, 'sha256': digest} for name, (url, digest) in DOWNLOADS.items()},
                'files': {p.relative_to(destination).as_posix(): sha256(p) for p in destination.rglob('*') if p.is_file()}}
    (destination / 'release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('PAYLOAD_READY', destination, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dotnet', type=Path, default=ROOT.parent / 'dotnet-sdk2/dotnet.exe')
    parser.add_argument('--print-lock', action='store_true')
    args = parser.parse_args()
    if args.print_lock:
        for dist in dependency_closure(ROOT_REQUIREMENTS):
            print(f'{dist.metadata["Name"]}=={dist.version}')
        return
    if not args.output:
        parser.error('--output is required')
    assemble(args.output.resolve(), args.dotnet, ROOT / 'packaging/distribution/requirements.lock')


if __name__ == '__main__':
    main()
