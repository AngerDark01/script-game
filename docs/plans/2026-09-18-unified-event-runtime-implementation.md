# Unified Event Runtime Implementation Plan

## Goal

Replace three parallel event runtimes and GUI-owned persistence with one
reusable event execution stack and an injected `EventWorkbenchService`, while
preserving the known-good Host/LAN protocol behavior.

## Architecture Overview

Pure event-domain code lives under `core/events/automation/`: normalized event
definitions, route records, dispatch decisions, and controller/source-scoped
execution. Platform integrations live under `core/runtime/event_service/`:
Win32 trigger input, Host state output, LAN transport, catalog exchange, and
the service composition root. The PySide page depends only on the service.

The Git tag `known-good/event-runtime-2026-09-18` is the behavioral baseline.
The C# Host and LAN wire commands are not changed.

## Tech Stack

- Python 3.12-compatible standard library (`dataclasses`, `threading`,
  `queue`, `pathlib`, `typing`)
- PySide6 for the presentation adapter
- Existing `VirtualGamepadClient` named-pipe protocol
- `pytest` and `unittest`
- Existing C#/.NET Host tests for protocol regression

### Task 1: Normalize executable event definitions

Files:

- Add `core/events/automation/__init__.py`
- Add `core/events/automation/definitions.py`
- Add `tests/test_event_definition_repository.py`

Write a failing test proving local and remote records use the same parser and
that a returned definition is a snapshot:

```python
def test_repository_uses_one_parser_for_local_and_remote_records(tmp_path):
    local = [{"id": "l1", "name": "roll", "revision": 1,
              "tracks": [{"mode": "once", "buttons": ["B"], "hold_ms": 80}]}]
    remote = [{"id": "r1", "name": "dash", "revision": 2,
               "tracks": [{"mode": "continuous", "buttons": ["LS_RIGHT"],
                           "hold_ms": 50, "interval_ms": 100, "end_ms": 500}]}]
    (tmp_path / "events.json").write_text(json.dumps(local), encoding="utf-8")
    (tmp_path / "remote_events.json").write_text(json.dumps(remote), encoding="utf-8")
    repository = EventDefinitionRepository(tmp_path, "device-a")
    definitions = repository.definitions()
    local[0]["tracks"][0]["buttons"][0] = "A"
    assert definitions["roll"].tracks[0].buttons == ("B",)
    assert definitions["dash"].tracks[0].mode is TrackMode.CONTINUOUS
```

Verify failure:

```powershell
python -m pytest tests/test_event_definition_repository.py -q
# Expected: import/collection failure because core.events.automation does not exist.
```

Implement `ExecutableEventDefinition`, `parse_event_definition()`, and
`EventDefinitionRepository` as the only conversion from records to
`ActionTrack` objects. The repository wraps `EventStore`, exposes local,
remote, visible, save, catalog, apply-remote, lookup, and shared-event identity
resolution operations.

Verify:

```powershell
python -m pytest tests/test_event_definition_repository.py core/events/tests/test_event_store.py tests/test_action_tracks.py -q
# Expected: all pass.
```

Commit: `refactor: centralize executable event definitions`

### Task 2: Normalize routes and dispatch decisions

Files:

- Add `core/events/automation/routes.py`
- Add `tests/test_event_routes.py`

Write failing tests for Chinese/English legacy normalization, one/two-controller
selection, local dispatch, remote dispatch, malformed records, and save/load.

Required public contracts:

```python
@dataclass(frozen=True)
class EventRoute:
    source: str
    trigger: str
    event_name: str
    target: str
    controllers: tuple[int, ...]

@dataclass(frozen=True)
class EventDispatch:
    event_name: str
    controllers: tuple[int, ...]
    remote: bool

class EventRouteRepository:
    def load(self) -> tuple[EventRoute, ...]: ...
    def save(self, routes: Iterable[EventRoute | Mapping]) -> None: ...

class EventRouter:
    def triggers(self) -> tuple[str, ...]: ...
    def dispatches(self, trigger: str) -> tuple[EventDispatch, ...]: ...
```

Verify failure, implement minimal normalization, then verify:

```powershell
python -m pytest tests/test_event_routes.py -q
# Expected before implementation: fail. Expected after implementation: pass.
```

Commit: `refactor: add reusable event routing contracts`

### Task 3: Add a source- and controller-scoped execution runtime

Files:

- Add `core/events/automation/execution.py`
- Add `tests/test_event_execution_runtime.py`

Write failing tests proving:

- local and remote dispatch use the same implementation;
- Controller 1 and Controller 2 progress independently;
- replacing definitions does not mutate an active lifecycle;
- canceling `event:remote` does not clear `event:local`;
- tick output is a complete neutral-safe XInput state.

Required contracts:

```python
@dataclass(frozen=True)
class EventStateFrame:
    source: str
    controller: int
    state: dict

class EventExecutionRuntime:
    def replace_definitions(self, definitions: Mapping[str, ExecutableEventDefinition]) -> None: ...
    def start(self, source: str, event_name: str, controllers: Iterable[int], *, instance_id: str | None = None) -> bool: ...
    def cancel_source(self, source: str) -> None: ...
    def tick(self) -> tuple[EventStateFrame, ...]: ...
```

Use existing `EventSession` and `state_from_inputs()`; do not add Host, LAN,
thread, or filesystem dependencies.

Verify:

```powershell
python -m pytest tests/test_event_execution_runtime.py tests/test_event_session.py tests/test_event_gamepad_output.py -q
# Expected: all pass.
```

Commit: `refactor: unify event execution by source and controller`

### Task 4: Extract Host and LAN protocol adapters

Files:

- Add `core/runtime/event_service/__init__.py`
- Add `core/runtime/event_service/host_bridge.py`
- Add `core/runtime/tests/test_event_host_bridge.py`

Write failing tests around an injected fake client. The adapter must expose:

```python
class HostEventBridge:
    def connect(self, timeout: float = 2.0) -> None: ...
    def status(self) -> dict: ...
    def data_only_peers(self) -> tuple[dict, ...]: ...
    def drain_events(self) -> tuple[dict, ...]: ...
    def drain_catalogs(self) -> tuple[dict, ...]: ...
    def publish_catalog(self, peer_id: str, catalog: dict) -> dict: ...
    def send_event(self, peer_id: str, payload: dict) -> dict: ...
    def write_state(self, frame: EventStateFrame, ttl_ms: int = 120) -> dict: ...
    def clear_source(self, controller: int, source: str) -> dict: ...
    def close(self) -> None: ...
```

Assert exact existing commands and payload fields. Assert catalog drain never
calls `sync.share.drain`, and event drain never calls catalog drain implicitly.

Verify:

```powershell
python -m pytest core/runtime/tests/test_event_host_bridge.py -q
# Expected: pass after implementation.
```

Commit: `refactor: isolate event host and lan protocol access`

### Task 5: Extract the trigger-source adapter

Files:

- Add `core/runtime/event_service/hotkeys.py`
- Add `core/runtime/tests/test_event_hotkeys.py`

Implement an injectable edge-triggered adapter:

```python
class HotkeyTriggerSource:
    def __init__(self, key_state=None): ...
    def poll(self, keys: Iterable[str]) -> tuple[str, ...]: ...
```

Map F1-F12, A-Z, SPACE, and arrow names offered by the current UI. Tests must
prove held keys emit once, release rearms the key, unknown names are ignored,
and construction/import does not require Windows until the default key reader
is used.

Verify:

```powershell
python -m pytest core/runtime/tests/test_event_hotkeys.py -q
# Expected: pass.
```

Commit: `refactor: isolate event hotkey triggers`

### Task 6: Compose the unified workbench service

Files:

- Add `core/runtime/event_service/models.py`
- Add `core/runtime/event_service/service.py`
- Add `core/runtime/tests/test_event_workbench_service.py`

Write failing tests using fake bridge and trigger adapters. Cover local route
execution, remote inbox execution, catalog send/apply, peer failure isolation,
controller separation, explicit remote send deadline, idempotent stop, and
source-specific clear.

Required UI-facing surface:

```python
@dataclass(frozen=True)
class EventWorkbenchStatus:
    local_running: bool
    remote_running: bool
    connected: bool
    peer_count: int
    trigger_count: int
    receive_count: int
    last_event: str
    error: str

class EventWorkbenchService:
    def start(self) -> None: ...
    def set_local_running(self, enabled: bool) -> None: ...
    def set_remote_running(self, enabled: bool) -> None: ...
    def load_local_events(self) -> list[dict]: ...
    def load_remote_events(self) -> list[dict]: ...
    def load_routes(self) -> list[dict]: ...
    def save(self, events: Iterable[dict], routes: Iterable[dict]) -> None: ...
    def send_remote_event(self, device_id: str, event_name: str, controllers: Iterable[int]) -> dict: ...
    def status(self) -> EventWorkbenchStatus: ...
    def shutdown(self) -> None: ...
```

The worker loop is the only owner of the long-lived bridge. It reloads
definitions/routes after save, keeps catalog drain separate, dispatches local
and remote events through one `EventExecutionRuntime`, and writes returned
frames through `HostEventBridge`.

Verify:

```powershell
python -m pytest core/runtime/tests/test_event_workbench_service.py core/runtime/tests/test_event_host_bridge.py -q
# Expected: all pass.
```

Commit: `refactor: compose unified event workbench service`

### Task 7: Move the GUI onto the service contract

Files:

- Modify `gui/modes/events/workbench.py`
- Modify `tests/test_event_workbench_ui.py`
- Modify `gui/main_window.py` only if explicit injection is needed at the app
  composition root

First change the UI test to inject a fake service and assert:

```python
page = EventWorkbenchPage(root=tmp_path, service=fake_service)
assert fake_service.started
page._save()
assert fake_service.saved_events
page._toggle_runtime()
assert fake_service.local_running
page._send_remote_event()
assert fake_service.sent
page.shutdown()
assert fake_service.stopped
```

Then remove all JSON reads/writes, `VirtualGamepadClient` access, and legacy
runtime construction from the page. Keep editing buffers and widget rendering
in the page. Map service status snapshots to the existing labels and buttons.

Verify:

```powershell
python -m pytest tests/test_event_workbench_ui.py -q
# Expected: pass with QT_QPA_PLATFORM=offscreen set by the test.
```

Commit: `refactor: make event workbench a service adapter`

### Task 8: Delete parallel runtimes and migrate regression tests

Files:

- Delete `core/runtime/local_event_runtime.py`
- Delete `core/runtime/remote_event_runtime.py`
- Delete `core/runtime/event_catalog_runtime.py`
- Delete `core/runtime/remote_event_sender.py`
- Replace `core/runtime/tests/test_remote_event_delivery.py` with service-level
  regression cases
- Delete or migrate `core/runtime/tests/test_event_catalog_runtime.py`
- Update imports found by `rg`

Before deletion, run:

```powershell
rg -n "LocalEventRuntime|RemoteEventRuntime|EventCatalogRuntime|RemoteEventSender|local_event_runtime|remote_event_runtime|event_catalog_runtime|remote_event_sender" . -g "!docs/**" -g "!CODEBASE.md" -g "!ARCHITECTURE_ITERATION_LOG.md"
# Expected: only files listed in this task and tests planned for migration.
```

After deletion, run the same command. Expected: no source/test matches.

Verify behavior:

```powershell
python -m pytest core/runtime/tests/test_event_workbench_service.py core/runtime/tests/test_event_host_bridge.py tests/test_event_workbench_ui.py tests/test_event_session.py tests/test_event_lifecycle.py tests/test_event_gamepad_output.py tests/test_event_button_chords.py -q
# Expected: all pass.
```

Commit: `refactor: remove parallel event runtimes`

### Task 9: Run focused protocol and architecture regression

Files:

- Modify only tests or implementation files needed by failures proven in this
  task; do not weaken assertions.

Run Python regression:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m pytest core/events/tests core/runtime/tests tests/test_action_tracks.py tests/test_event_session.py tests/test_event_lifecycle.py tests/test_event_gamepad_output.py tests/test_event_button_chords.py tests/test_event_workbench_ui.py -q
# Expected: all selected tests pass.
```

Run C# Host/LAN tests without starting real synchronization:

```powershell
dotnet test virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj --no-restore
# Expected: all tests pass.
```

Check module boundaries:

```powershell
rg -n "PySide6|ctypes|VirtualGamepadClient|sync\.share|event\.state|event\.clear" core/events/automation
# Expected: no matches.
rg -n "json\.loads|json\.dumps|VirtualGamepadClient|LocalEventRuntime|RemoteEventRuntime|EventCatalogRuntime|RemoteEventSender" gui/modes/events/workbench.py
# Expected: no matches.
```

Commit fixes, if any, as `fix: preserve event runtime regression contracts`.

### Task 10: Synchronize architecture documentation

Files:

- Modify `CODEBASE.md`
- Modify `ARCHITECTURE_GUIDE.md`
- Modify `ARCHITECTURE_ITERATION_LOG.md`
- Modify the relevant module-owned architecture documents under `core/`,
  `gui/`, and `tests/`

Follow the `codebase-ontology` SYNC procedure: declare direct changes and
blast radius before documentation reads, update function/data-flow entries,
replace the three resolved risk entries, and record exact validation output.

Verify final tree:

```powershell
git diff --check
git status --short
git diff "known-good/event-runtime-2026-09-18" --stat
# Expected: no whitespace errors; only planned implementation, tests, plans,
# and synchronized architecture documents differ from the known-good tag.
```

Commit: `docs: synchronize unified event runtime architecture`
