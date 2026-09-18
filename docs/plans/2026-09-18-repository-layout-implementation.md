# Repository Layout Migration Implementation Plan

## Goal

Move Auto Modules into the approved layered repository structure, update every
import and physical path consumer, and preserve existing behavior.

## Architecture Overview

Python code becomes one `src` package named `auto_modules`. Generic capability,
application orchestration, external adapters, UI, and bootstrap are explicit
layers. C# runtimes live in `services`; immutable resources, writable data,
developer tools, documentation, and packaging each receive one top-level owner.
All path lookup is centralized in `auto_modules.paths`.

## Tech Stack

- Python 3, PySide6, NumPy, OpenCV, MSS
- pytest/unittest
- C#/.NET 8 Windows projects
- Inno Setup packaging

## Task 1: Protect the verified baseline

Files: no source files.

Verify:

```powershell
git status --porcelain=v1
git rev-parse pre-reorg/2026-09-18^{}
```

Expected: clean status before migration and tag resolves to `be69838...`.

## Task 2: Add package/test configuration and the path contract

Files:

- `pyproject.toml`
- `src/auto_modules/__init__.py`
- `src/auto_modules/paths.py`
- `tests/test_runtime_paths.py`

Test first: cover source defaults and both environment overrides. Then implement
`package_root`, `repository_root`, `resource_root`, and `data_root` without any
caller-supplied root argument.

Verify:

```powershell
python -m pytest tests/test_runtime_paths.py -q
```

Expected: path tests pass with repository resources/data defaults.

Commit: `refactor: establish src package and runtime path contract`

## Task 3: Move the Python core package and rewrite imports

Files:

- `core/**` -> `src/auto_modules/core/**`
- all Python source/tests importing `core`
- path consumers formerly importing `core.runtime_paths`

Mechanically move the package, rewrite imports to `auto_modules.core`, remove
`runtime_paths.py` after callers use `auto_modules.paths`, and compile the entire
package before proceeding.

Verify:

```powershell
python -m compileall -q src/auto_modules/core tests
python -m pytest tests/test_pathfinder.py tests/test_event_session.py -q
```

Expected: compilation succeeds and focused core/application precursor tests pass.

Commit: `refactor: move reusable capabilities into auto_modules core`

## Task 4: Extract application orchestration and external adapters

Files:

- `src/auto_modules/core/runtime/event_service/**`
- `src/auto_modules/core/runtime/event_session.py`
- `src/auto_modules/core/runtime/follow_*.py`
- `src/auto_modules/core/runtime/dual_follow_session.py`
- `src/auto_modules/core/runtime/follower_controller.py`
- new `src/auto_modules/application/events/**`
- new `src/auto_modules/application/event_workbench/**`
- new `src/auto_modules/application/follow/**`
- new `src/auto_modules/adapters/host/**`
- new `src/auto_modules/adapters/windows/**`
- affected tests/imports

Move orchestration without changing behavior. Preserve injectable bridge and
hotkey contracts, but make concrete defaults a bootstrap responsibility.

Verify:

```powershell
python -m pytest tests/test_event_session.py tests/test_event_workbench_service.py tests/test_event_host_bridge.py tests/test_event_hotkeys.py -q
```

Expected: focused event/runtime tests pass without Host or keyboard activity.

Commit: `refactor: separate application services from external adapters`

## Task 5: Move UI, workflows and bootstrap

Files:

- `gui/**` -> `src/auto_modules/ui/**`
- `workflows/**` -> `src/auto_modules/application/workflows/**`
- `main.py`
- new `src/auto_modules/bootstrap/main.py`
- `logging_system.py` -> `src/auto_modules/adapters/logging.py`
- affected tests/imports

Move the existing root startup implementation to bootstrap, leave a thin root
launcher, and rewrite `gui`/`workflows` imports to package imports.

Verify:

```powershell
python -m compileall -q src main.py
python -c "import auto_modules.ui.main_window; import auto_modules.bootstrap.main"
```

Expected: all modules compile and both composition entry points import.

Commit: `refactor: package ui workflows and bootstrap`

## Task 6: Separate virtual-gamepad Python code and C# services

Files:

- `virtual_gamepad/client/python/**` -> `src/auto_modules/adapters/virtual_gamepad/**`
- `virtual_gamepad/ui/virtual_gamepad_ui/**` -> `src/auto_modules/ui/virtual_gamepad/**`
- `virtual_gamepad/host/**` -> `services/virtual_gamepad/host/**`
- `virtual_gamepad/launcher/**` -> `services/virtual_gamepad/launcher/**`
- `virtual_gamepad/protocol/**` -> `services/virtual_gamepad/protocol/**`
- `lan_input_sync/**` -> `services/lan_input_sync/**`
- C# project files and launcher path tests
- affected Python tests/imports

Update all Python package names, launcher environment construction, and C#
`ProjectReference` values. Do not alter named-pipe commands or LAN protocol data.

Verify:

```powershell
python -m pytest tests -q -k "gamepad or host_bridge or lan"
dotnet test services/lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj
dotnet test services/virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj
```

Expected: Python tests pass; C# tests pass when an SDK is installed, otherwise the
missing SDK is reported explicitly.

Commit: `refactor: group device runtimes under adapters and services`

## Task 7: Move resources, writable data and developer tools

Files:

- `assets/**` -> `resources/assets/**`
- `configs/events/**` -> `data/events/**`
- `map_data/**` -> `data/maps/**`
- local ignored `config.json` -> local ignored `data/config.json`
- `virtual_gamepad/configs/default.json` -> `resources/defaults/virtual_gamepad/default.json`
- `debug/**`, `utils/**`, `virtual_gamepad/scripts/**`, `tools/**` -> organized `tools/**`
- all resource/data/tool path consumers
- `.gitignore`

Update tools to import from `auto_modules`, use the shared path API, and keep
generated output ignored in its new location.

Verify:

```powershell
python -m compileall -q tools
python -m pytest tests/test_runtime_paths.py -q
```

Expected: tools compile and paths resolve only through the shared contract.

Commit: `refactor: separate resources data and developer tools`

## Task 8: Move packaging and update installed-layout contracts

Files:

- `distribution/**` -> `packaging/distribution/**`
- `installer/**` -> `packaging/installer/**`
- distribution builder/smoke tests
- installer `RuntimeLayout` and tests
- service launcher source-mode paths

Package `main.py`, `src/auto_modules`, and `resources`; seed only explicit
defaults into the writable install data directory. Keep `app/main.py` as the
installer launch target.

Verify:

```powershell
python -m pytest tests -q -k "distribution or packaging or runtime_layout"
python packaging/distribution/smoke_check.py --help
dotnet test packaging/installer/tests/Installer.Tests.csproj
```

Expected: Python smoke checks pass; installer tests pass when an SDK exists.

Commit: `refactor: align packaging with layered repository layout`

## Task 9: Consolidate documentation and remove stale paths

Files:

- `architecture_docs/**` -> `docs/architecture/**`
- `a_project_desc/**` -> `docs/archive/project_desc/**`
- root guide/release documents -> `docs/guides/**` or `docs/archive/**`
- `README.md`, `AGENTS.md`, architecture links

Rewrite repository-relative links and commands. Search tracked text for every
retired top-level path and classify each remaining occurrence as historical or
incorrect.

Verify:

```powershell
git grep -n -E "(^|[^a-zA-Z_])(from|import) (core|gui|workflows|virtual_gamepad_ui)"
git grep -n -E "virtual_gamepad/(host|launcher)|lan_input_sync/src|distribution/build.py|installer/launcher"
```

Expected: no production import uses an old package; old physical paths appear
only in explicitly archived historical documents.

Commit: `docs: align project documentation with repository layout`

## Task 10: Full verification and ontology synchronization

Files:

- `CODEBASE.md`
- `ITERATION_LOG.md`
- relevant architecture records

Run import-boundary checks, focused suites, full Python discovery, packaging
checks, and available C# tests. Then update the living codebase description and
record direct/propagated changes in the iteration log.

Verify:

```powershell
python -m compileall -q src tests tools main.py
python -m pytest -q
git diff --check
git status --short
```

Expected: no import/compile/path regression; all available tests pass or only
documented pre-existing/environmental failures remain.

Commit: `docs: synchronize architecture after repository migration`
