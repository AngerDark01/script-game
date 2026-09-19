# Event System Architecture

## System Role

`core/events` contains two reusable, GUI-free event capability families. The
navigation event runtime observes frames, stabilizes detections, stores event
tasks, selects runnable tasks, runs event handlers, and reports generic actions
back to navigation. `core/events/automation` normalizes configured action-event
definitions and routes, then advances controller-state sessions without knowing
about hotkeys, Host clients, LAN peers, or Qt.

The event system should not know GUI widgets, route editing, or concrete mouse/key execution. It should emit generic actions and lifecycle state.

## Verified Event Lifecycle

Current runtime lifecycle:

```text
EventCoordinator.observe(tick)
  ├── EventMonitor.detect(tick, config)
  │     ├── EventDefinition.create_detector(config).detect(...)
  │     └── EventDetection -> TargetDetection(MINIMAP) -> independent EventDetection
  │           └── expose generic observations via EventMonitor.last_target_detections
  ├── EventPositionStabilizer.update(detections, frame_registration, config, now_ms)
  ├── EventMemory.merge_observations(observations, config, now_ms)
  │     ├── create EventTask(state=OBSERVED)
  │     ├── merge nearby observations into existing EventTask
  │     ├── apply completed cooldown/type cooldown
  │     └── mark EventTask PENDING when confirm frames reached
  ├── tick.event_tasks = EventMemory.tasks()
  └── EventScheduler.pick(active_tasks, player_pos)
        └── only selects display/status task here

NavigationTaskController.update(...)
  └── TaskBuilder consumes EventCoordinator.tasks()
      └── selected navigation event task calls EventCoordinator.run_task(task_id, tick)

EventCoordinator.run_task(task_id, tick)
  └── EventRunner.update(selected_task, tick, config)
        ├── start handler if task changed
        │     └── EventDefinition.create_handler(config).start(task)
        ├── EventHandler.update(tick, task) -> EventAction
        ├── COMPLETE -> EventMemory.mark_completed / complete_teleport_session
        ├── FAIL -> EventMemory.mark_failed
        └── returns EventAction to navigation task controller
```

Important detail: `EventCoordinator.observe()` does not execute handlers. It only detects, stabilizes, merges memory, and chooses a display/status task. Handler execution starts only when navigation selects an event task and calls `run_task()`.

## Current Module Map

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `models.py` | Event tick, detection, observation, task, and action models. | Stable contract candidate. |
| `config.py` | Default event config and map-level config IO. | Could split pure defaults/schema from filesystem adapter. |
| `registry.py` | Event definition registry. | Good extension seam for event packages. |
| `monitor.py` | Runs enabled detectors, caches them, and composes legacy results through the perception adapter. | Hook point for detector lifecycle and shared-schema observation. |
| `perception_adapter.py` | Pure `EventDetection`/`TargetDetection(MINIMAP)` conversion and batch normalization. | Reusable schema seam; must not contain Portal/Loot recognition or handler policy. |
| `position_stabilizer.py` | Projects local detections to global positions and clusters over frames. | Reusable algorithm component. |
| `memory.py` | Event task lifecycle, dedupe, confirm, cooldown, failure/completion state. | Core state module; likely deep but needs careful reading. |
| `scheduler.py` | Picks pending/running event tasks. | Small scheduler module. |
| `runner.py` | Starts handlers and applies complete/fail outcomes to memory. | Execution lifecycle module. |
| `coordinator.py` | Unified event entrypoint for navigation loop. | Should be thin facade over monitor/stabilizer/memory/scheduler/runner. |
| `capture_provider.py` | Supplies minimap/main-view captures to handlers. | Adapter boundary. |
| `window_finder.py` | Windows game-window discovery. | Platform adapter. |
| `debug.py` | Event runtime logging. | Diagnostics adapter. |
| `overlay_models.py` | Converts event task state to overlay data. | UI-facing DTO adapter, still core-safe if it has no PySide dependency. |
| `automation/definitions.py` | Canonical versioned action-event records and the only record-to-`ActionTrack` parser. | Stable repository/definition boundary. |
| `automation/routes.py` | Route normalization and pure trigger-to-dispatch decisions. | Stable policy boundary with no platform IO. |
| `automation/execution.py` | Shared local/remote execution keyed by source and controller. | Stable source-scoped state-machine runtime. |

## Action Event Automation Boundary

```text
EventDefinitionRepository
  ├── local/remote records from EventStore
  ├── ExecutableEventDefinition snapshots
  ├── stable id + revision ownership
  └── catalog identity resolution

EventRouteRepository -> EventRouter -> EventDispatch
                                         │
                                         ▼
EventExecutionRuntime(source, controller) -> EventStateFrame
```

Rules verified in the implementation:

- Local and remote records use the same `parse_event_definition()` path.
- Active `EventSession` instances keep their definition snapshot; a later save
  only affects the next start.
- Mutable sessions are isolated by `(source, controller)`, so stopping remote
  execution cannot clear local execution on the same controller.
- `EventRouter` emits only domain-neutral dispatches. It does not poll keys,
  inspect peers, or send controller state.
- `EventExecutionRuntime.tick()` emits complete neutral-safe XInput state
  dictionaries through `EventStateFrame`; only an upper adapter may write them.
- When the Host reveals the active device ID, local records are rebound to that
  owner without changing stable IDs or revisions.

Platform composition is deliberately outside this package in
`core/runtime/event_service`: `HotkeyTriggerSource` reads Win32 key state,
`HostEventBridge` owns exact Host/LAN commands, and `EventWorkbenchService`
assembles those adapters with the pure modules.

## Current Public Event Package Interface

`EventDefinition` is the event package seam:

```python
class EventDefinition:
    event_type: str
    display_name: str
    description: str

    def default_config(self) -> dict: ...
    def config_schema(self) -> dict: ...
    def create_detector(self, config): ...
    def create_handler(self, config): ...
```

`EventDetector` interface:

```python
def detect(self, tick, config) -> list[EventDetection]: ...
```

`EventHandler` interface:

```python
def start(self, task) -> None: ...
def update(self, tick, task) -> EventAction | None: ...
def reset(self) -> None: ...
```

This is a good minimal seam. It should remain small. Hooks should not be added directly as many optional methods on `EventDefinition`; use a hook bus/listener object instead.

## Proposed Lifecycle Hooks

The event system can become extensible if `EventCoordinator` accepts a hook bus. This avoids adding many optional methods to `EventDefinition`.

```text
observe phase:
  on_event_tick_start(tick)
  on_detector_initialized(event_type, detector)
  on_detections(event_type, detections)
  on_observations(observations)
  on_task_created(task)
  on_task_seen(task, observation)
  on_task_confirmed(task)
  on_display_task_selected(task)
  on_event_tick_end(summary)

run phase:
  on_runner_idle_clear(previous_task)
  on_handler_started(task, handler)
  on_handler_action(task, action)
  on_task_completed(task, action)
  on_task_failed(task, action)
  on_task_requeued(task)
```

Concrete hook adapters:

- Debug log hook.
- GUI overlay hook.
- Metrics hook.
- Test capture hook.
- Event-specific tuning hook.

Hook implementation sketch:

```python
class EventHook:
    def on_task_created(self, task): ...
    def on_handler_action(self, task, action): ...

class EventHookBus:
    def __init__(self, hooks=None):
        self.hooks = list(hooks or [])

    def emit(self, name: str, *args, **kwargs) -> None:
        for hook in self.hooks:
            method = getattr(hook, name, None)
            if method:
                method(*args, **kwargs)
```

Then inject:

```python
EventCoordinator(registry, config, hooks=EventHookBus([...]))
```

Do not make hooks return control decisions at first. Keep them observational until the lifecycle is stable.

## Desired Event Package Interface

Each event type should be a package adapter that provides:

- Event identity and display metadata.
- Default config and config schema.
- Detector factory.
- Handler factory.
- Optional overlay formatting.
- Optional approach policy.
- Optional validation probes.

The core event system should not import portal-specific code except through registration.

Refined interface:

```text
Event package
  ├── EventDefinition
  │     ├── identity/display/config schema
  │     ├── detector factory
  │     └── handler factory
  ├── detector components
  ├── handler state machine
  ├── config typed adapter
  ├── assets
  └── optional probes
```

The package may include internal detector variants, confirmers, and assets, but the rest of the app should see only the complete event type, such as `portal`.

## Adapter Boundaries

Keep these as adapters, not core policy:

- `config.py` file IO: map-folder `event_config.json` persistence.
- `capture_provider.py`: static/game-window capture adapter for handlers.
- `window_finder.py`: Windows-specific window lookup.
- `overlay_models.py`: core-safe DTO for GUI overlay, but PySide rendering remains in GUI.
- `debug.py`: logging hook candidate.
- `core/runtime/event_service/hotkeys.py`: Win32 key-edge adapter for action events.
- `core/runtime/event_service/host_bridge.py`: virtual-gamepad Host and LAN protocol adapter.
- `gui/modes/events/workbench.py`: Qt editing/status adapter over `EventWorkbenchService`.

Potential split:

```text
core/events/config_model.py       # EventSystemConfig and defaults
core/events/config_io.py          # event_config.json load/save
core/events/hooks.py              # EventHook/EventHookBus
core/events/coordinator.py        # lifecycle facade
```

## Coordinator Split

`EventCoordinator` is currently still reasonably small, but it owns both observe and run facade behavior. If it grows with hooks, split internally:

```text
coordinator.py        # public facade
observer.py           # detect -> stabilize -> memory merge
task_runtime.py       # run selected task through EventRunner
overlay_adapter.py    # task_to_overlay/status summary facade if needed
```

Do not split yet unless hook injection makes `coordinator.py` materially more complex.

## Memory Policy

`EventMemory` is a deep module. It owns:

- Deduping observations into tasks.
- Confirmation frames.
- Position/type cooldown.
- Retry/ignore behavior.
- Teleport session completion.
- Nearby pending suppression.
- Synthetic related task creation.

This should remain one module until tests cover event lifecycle behavior. Splitting it prematurely would scatter task lifecycle rules.

## Runner Policy

`EventRunner` is a good seam between generic event runtime and event package handlers:

- Starts handler when selected task changes.
- Requeues running task if runner becomes idle.
- Applies `COMPLETE`/`FAIL` to memory.
- Lets handler actions flow back to navigation as generic `EventAction`.

Future hook placement:

- `on_handler_started` after `active_handler.start(task)`.
- `on_handler_action` after handler update returns non-null action.
- `on_task_completed` or `on_task_failed` before `_clear()`.

## Config Boundary

`DEFAULT_EVENT_CONFIG` contains only game-neutral runtime fields and an empty
`events` mapping. Concrete definitions own their defaults. Navigation loads the
persisted config, then applies the active registry through:

```text
load_event_config(map_folder)
  -> apply_registered_event_defaults(registry, config)
       -> EventDefinition.default_config()
```

This lets new event packages register defaults without editing core config.

## Round Status

Status: partial for the visual/navigation event family. The action-event family
is now split into pure automation modules plus a platform service and is covered
by focused repository, routing, execution, adapter, service, and GUI tests.

Concrete Torchlight events live under `features/torchlight/{portal,loot}` and
are documented at that business boundary rather than as core event modules.
