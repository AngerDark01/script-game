# Repository Layout Design

## Goal

Reorganize Auto Modules so repository layout expresses the approved bottom-up
architecture, while preserving the verified event, virtual-gamepad, LAN, OCR,
navigation, and UI behavior.

The migration is structural. It must not send real input, start LAN
synchronization, or change business behavior.

## Target Layout

```text
auto_modules/
  src/auto_modules/
    core/                 reusable, side-effect-free or effect-neutral capabilities
    application/          use cases, services, lifecycle and workflow orchestration
    adapters/             Windows, Host, file, OCR-provider and transport boundaries
    ui/                   PySide6 presentation and UI composition
    bootstrap/            application startup and dependency assembly
    paths.py              the only repository/resource/data layout authority
  services/
    virtual_gamepad/      C# Host, launcher and wire protocol
    lan_input_sync/       C# LAN synchronization library and tests
  resources/
    assets/               immutable templates, detector definitions and model manifests
    defaults/             source-controlled default configuration
  data/                   writable development data; installed builds use an external path
  tools/                  probes, diagnostics, maintenance and developer launchers
  tests/                  Python tests, mirroring the source packages where useful
  docs/
    architecture/         current and historical architecture records
    guides/               user/developer guides
    plans/                approved designs and implementation plans
    archive/              superseded project notes
  packaging/
    distribution/         portable payload builder and smoke verification
    installer/            installer launcher and Inno Setup project
  main.py                 thin source/install bootstrap
  pyproject.toml          Python import and test configuration
  AGENTS.md
  CODEBASE.md
  ITERATION_LOG.md
  README.md
```

## Dependency Direction

```text
bootstrap -> ui -> application -> core
                \-> adapters -> core contracts

tools -> any public package needed by that tool
packaging -> repository layout only
services -> their own C# contracts and external drivers
```

`core` must never import `application`, `adapters`, `ui`, or `bootstrap`.
`application` may depend on `core` contracts and receives adapter implementations
through constructors or factories. `ui` invokes application services and may use
presentation-safe core models, but does not own persistence, Host, or network
policy. `bootstrap` is the composition root and is the only layer expected to
know concrete implementations across all Python layers.

## Existing-to-Target Mapping

| Existing path | Target path | Rule |
|---|---|---|
| `core/` | `src/auto_modules/core/` | Move first, then extract orchestration/adapters listed below |
| `core/runtime/event_service/service.py` | `src/auto_modules/application/event_workbench/service.py` | Workbench lifecycle orchestration |
| `core/runtime/event_service/models.py` | `src/auto_modules/application/event_workbench/models.py` | Application-facing status models |
| `core/runtime/event_service/host_bridge.py` | `src/auto_modules/adapters/host/event_bridge.py` | Named-pipe/Host side effects |
| `core/runtime/event_service/hotkeys.py` | `src/auto_modules/adapters/windows/hotkeys.py` | Windows key-state adapter |
| `core/runtime/event_session.py` | `src/auto_modules/application/events/session.py` | Event execution use case |
| `core/runtime/follow_*.py`, `dual_follow_session.py`, `follower_controller.py` | `src/auto_modules/application/follow/` | Follow use cases and worker orchestration |
| `gui/` | `src/auto_modules/ui/` | Rename package and use `auto_modules.ui.*` imports |
| `workflows/` | `src/auto_modules/application/workflows/` | Reusable end-to-end application workflows |
| `logging_system.py` | `src/auto_modules/adapters/logging.py` | Process logging/output adapter |
| `virtual_gamepad/client/python/` | `src/auto_modules/adapters/virtual_gamepad/` | Python Host client adapter |
| `virtual_gamepad/ui/virtual_gamepad_ui/` | `src/auto_modules/ui/virtual_gamepad/` | Integrated and standalone gamepad UI |
| `virtual_gamepad/host`, `launcher`, `protocol` | `services/virtual_gamepad/` | Independent C# runtime and protocol |
| `lan_input_sync/` | `services/lan_input_sync/` | Independent C# service/library |
| `assets/` | `resources/assets/` | Immutable runtime resources |
| `virtual_gamepad/configs/default.json` | `resources/defaults/virtual_gamepad/default.json` | Shipped default only |
| `configs/events/` | `data/events/` | Writable development event definitions and routes |
| `map_data/` | `data/maps/` | Writable map packages |
| `config.json` | `data/config.json` | Local ignored configuration; move without committing secrets |
| `debug/`, `utils/`, root `tools/` | `tools/` subdirectories | Executable development utilities, not importable app code |
| `distribution/`, `installer/` | `packaging/distribution/`, `packaging/installer/` | Build and installation code |
| `architecture_docs/` | `docs/architecture/` | Architecture archive and localized copies |
| `a_project_desc/` | `docs/archive/project_desc/` | Historical design material |
| scattered root guides/releases | `docs/guides/` or `docs/archive/` | Keep root operational files only |

## Import Rules

All application imports are absolute from the installed package:

```python
from auto_modules.core.routing import PathFinder
from auto_modules.application.event_workbench import EventWorkbenchService
from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient
from auto_modules.ui.main_window import MainWindow
```

Relative imports remain acceptable inside one cohesive subpackage. No production
module may import `core`, `gui`, `workflows`, `virtual_gamepad.client.python`, or
`virtual_gamepad_ui` as a top-level package after migration. Tests run with
`src` on `sys.path` through `pyproject.toml`; they must not mutate `sys.path` to
recreate the old layout.

No compatibility packages named `core` or `gui` are retained. This makes stale
imports fail immediately instead of silently preserving the old architecture.

## Runtime Paths

`src/auto_modules/paths.py` is the only authority for physical layout:

```python
package_root()     # .../src/auto_modules
repository_root()  # source checkout or installed app root
resource_root()    # AUTO_MODULES_RESOURCE_DIR or <root>/resources
data_root()        # AUTO_MODULES_DATA_DIR or <root>/data
```

Production modules receive concrete paths from these functions or from caller
injection. They must not infer roots with `Path(__file__).parents[n]`.

Source mode resolves `<repo>/resources` and `<repo>/data`. The installer sets
`AUTO_MODULES_DATA_DIR` to the per-user writable directory and may set
`AUTO_MODULES_RESOURCE_DIR` to the installed immutable resources. The same
package therefore runs in both layouts without feature-specific path logic.

## Bootstrap and Packaging

Root `main.py` only adds `<root>/src` to `sys.path` and calls
`auto_modules.bootstrap.main.main()`. Runtime initialization, single-instance
handling, logging, and Qt composition live under `bootstrap` and adapters.

The portable payload keeps this shape:

```text
app/main.py
app/src/auto_modules/...
app/resources/...
defaults/...
host/...
python/...
```

The installer continues launching `app/main.py`. Defaults are generated from
source-controlled defaults plus a sanitized local development config; writable
data is never bundled wholesale.

## C# Service Layout

The C# namespaces and assembly names do not change. Only filesystem paths and
`ProjectReference` values change. `LauncherPaths` receives the repository or
installed service root explicitly and derives:

- Host output under `services/virtual_gamepad/host/...` in source mode.
- Python UI package under `src/auto_modules/ui/virtual_gamepad`.
- Python import root `<repo>/src`.
- LAN project under `services/lan_input_sync`.

This keeps the named-pipe and LAN protocols stable while making service
ownership visible in the repository.

## Verification

Verification proceeds from the lowest layer upward:

1. Import compilation and a scan proving no old package imports remain.
2. Pure core and application unit tests.
3. UI and adapter tests with fakes only.
4. Virtual-gamepad Python protocol tests.
5. C# project build/tests when an SDK is available.
6. Packaging smoke tests and payload path assertions.
7. Full Python discovery.

No verification step sends physical/virtual input or starts LAN synchronization.
The protected pre-migration tag remains the recovery point for the last verified
device behavior.
