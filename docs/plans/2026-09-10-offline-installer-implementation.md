# Offline installer implementation plan

## Goal
Produce a verified offline Windows x64 installer for the full workbench including virtual-controller prerequisites.

## Architecture Overview
Use a bundled isolated CPython runtime, pinned project dependencies, self-contained .NET executables, per-user mutable data, and Inno Setup with a verified driver bootstrap. Preserve the existing developer tree and all user changes.

## Tech Stack
Python 3.12.10 embeddable, existing pinned PySide6/OpenCV/NumPy/RapidOCR dependencies, .NET 8, Inno Setup 6, official signed ViGEmBus 1.22.0.

## Execution
Use subagent-driven-development for the bounded native installer subsystem; root handles Python payload and runtime paths. Spec review then code-quality review, then final integrated review. Local branches/checkpoints; no unrelated files in commits.

### 1. Add tested mutable-data resolver
Files: `core/runtime_paths.py`, `tests/test_runtime_paths.py`.
Contract:
```python
import os
from pathlib import Path
def data_root(project_root: Path) -> Path:
    value = os.environ.get('AUTO_MODULES_DATA_DIR')
    return Path(value).resolve() if value else Path(project_root).resolve()
```
Write tests first for missing variable, alternate path and spaces/non-ASCII. Run `D:/ACloud/.venv/Scripts/python.exe -m unittest tests.test_runtime_paths`; observe failure then implement and rerun. Commit only these files.

### 2. Route config/maps/profile/logs without changing development defaults
Files: `gui/composition/paths.py`, `gui/main_window.py`, `main.py`, `gui/gamepad/host_manager.py`, existing focused tests plus `tests/test_runtime_paths.py`.
Use `data_root(project_root) / 'map_data'`, `data_root(project_root) / 'config.json'`, `data_root(project_root) / 'virtual_gamepad' / 'configs'` and logs. Installed host override `AUTO_MODULES_HOST_DIR` selects packaged self-contained exe first; absent override keeps existing behavior. Add failing integration assertions for installed overrides, implement, run focused tests and commit exact paths.

### 3. Native launcher data seeding (independent subsystem)
Files: `installer/launcher/{AutoModulesLauncher.csproj,Program.cs,app.manifest,...}`, `installer/tests/**`.
Launcher derives root from `AppContext.BaseDirectory`, never D:/ACloud. Seed defaults only when missing; never overwrite existing data or resurrect files inside an existing map. Start bundled pythonw with ArgumentList and WorkingDirectory, clearing PYTHONHOME/PYTHONPATH and setting data and host environment. Show errors in visible dialog. Self-contained publish: `D:/ACloud/dotnet-sdk2/dotnet.exe publish installer/launcher/AutoModulesLauncher.csproj -c Release -r win-x64 --self-contained true -o <payload-root>`. Unit-test quoting/path selection/seeding before implementation; commit subsystem only after tests.

### 4. Driver bootstrap and Inno integration
Files: `installer/launcher/**`, `installer/AutoModules.iss`, `installer/README.md`, installer tests.
Support installer driver ensure/check modes with explicit exit-code handling. Validate pinned driver hash and Authenticode signer before running official setup. Existing compatible driver skips installer; failing installation is surfaced; reboot code remains reboot-required. Test classifications via injected seams; actual existing-driver probe may create only neutral devices when no host active. Inno Setup has desktop shortcut, optional initial maps, preserves user data, never uninstalls shared ViGEmBus. No automatic reboot. Publish includes notices.

### 5. Pinned payload manifest
Files: `distribution/build.py`, `distribution/requirements.lock`, `distribution/README.md`, `tests/test_distribution.py`.
Build dependency closure from explicitly selected project requirements pinned to current known versions. Exclude local editable mihomo and unrelated API clients. Python download uses upstream URL plus recorded SHA256, dependency wheels are downloaded on build machine only. Source allowlist covers runtime modules and assets; maps/profiles go to defaults. Test exclusion, path traversal checks and no credential inclusion before implementing. Build staging is a unique ignored directory; no recursive deletion of broad paths.

### 6. Isolated runtime smoke check
Files: `distribution/smoke_check.py`, payload generated manifest.
Invoke isolated embedded Python from a path with spaces/non-ASCII with PYTHONPATH/PYTHONHOME unset and PATH excluding developer runtimes. Import GUI/actions/OCR runtime, instantiate demo UI, verify model assets and packaged host --help. Do not manipulate user game input or install drivers in development by surprise. Record actual output and dependency versions.

### 7. Build offline Setup.exe and verify
Download/verify build compiler, publish native executables, assemble payload and compile Inno. Verify setup metadata, bundled prerequisites, hashes, runtime smoke and UI. Test installing into a separate test directory preserving user data and using existing compatible driver; never overwrite running developer binaries. Document any test that needs clean Windows/second PC. Final overall review then scoped commits, provide exact installer file and checksums.
