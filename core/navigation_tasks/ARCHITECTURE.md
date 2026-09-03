# Unified Navigation Task System Architecture

## System Role

`core/navigation_tasks` should be the reusable orchestration system that turns route goals and event goals into a single navigation intent stream.

Its ideal interface:

```text
current position + route data + event tasks + map/path dependencies
    -> selected task
    -> movement step or event action
    -> NavigationIntent
```

## Verified Current Interface

Primary caller: `gui/modes/navigation_mode.py::_navigation_loop_unified()`.

Current call shape:

```python
intent = navigation_task_controller.update(
    localized_pos=localized_pos,
    confidence=conf,
    route=main_route,
    event_coordinator=event_coordinator,
    event_tick=event_tick,
    wall_map=nav_core.nav_wall_layer,
    pathfinder=app_context.path_finder,
    explored_map=nav_core.explored_map,
    now_ms=now_ms,
    lookahead_distance=lookahead,
    manual_event_only=portal_test_controller.active and not auto_navigation_enabled,
    frame_registration=nav_core.last_frame_registration,
)
```

This interface is functional but too wide. The caller must know route shape, event coordinator, event tick, map layers, pathfinder, explored map, timing, manual event mode, and localization registration. It means the GUI loop is still carrying too much system knowledge.

Target call shape:

```python
intent = task_controller.update(NavigationUpdateContext(...))
```

Where `NavigationUpdateContext` groups:

- localization snapshot
- route snapshot
- event snapshot/runner adapter
- path planning dependencies
- timing/options

## Current Module Map

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `models.py` | Task, movement step, and navigation intent data models. | Should be the stable contract between GUI, route, movement, and event systems. |
| `task_builder.py` | Builds route/event tasks into one list. | Good candidate for pure task composition interface. |
| `scheduler.py` | Picks current required/exit/event task. | Should hide prioritization rules behind a narrow selection interface. |
| `controller.py` | Coordinates task build, selection, event execution, movement execution, and intent output. | Large file and high-value split candidate. |
| `movement_executor.py` | Shared path planning and click target selection for route/event movement. | Candidate reusable route movement component. |
| `route_context.py` | Route progress, projection, and corridor anchors. | Good reusable geometry/state module. |
| `coordinate_diagnostics.py` | Drift detection and forced relocalization state. | Candidate separate diagnostics module with hook into controller. |
| `event_approach.py` | Event approach behavior. | Needs reading to decide whether it belongs here or under event system. |
| `debug.py` | Navigation task logging. | Should stay adapter-like and not affect core decisions. |

## Current Deep Modules

These modules already have useful depth and should mostly be preserved:

- `models.py` - stable DTOs and enums for navigation tasks, movement steps, and intents.
- `task_builder.py` - turns route goals and event tasks into a unified task list.
- `scheduler.py` - applies route/event selection policy.
- `route_context.py` - route projection and corridor anchor logic.
- `movement_executor.py` - path planning, lookahead, click throttling, stuck recovery, anchor/fallback handling.
- `coordinate_diagnostics.py` - diagnostics and relocalization request state.

The main shallow point is `controller.py`, because it exposes too much of the system through one method and mixes policy layers internally.

## Desired Hooks

These hooks would let navigation and events interact without either side owning the other's internals:

- `on_localization_observed(snapshot)` - after confidence/jump filtering.
- `before_task_build(context)` - lets adapters add/transform dynamic tasks.
- `after_task_build(tasks)` - diagnostics and debug capture.
- `before_task_selection(tasks, active_task_id)` - inspect candidates.
- `after_task_selection(task, reason)` - logging, UI state, diagnostics.
- `before_event_handler(task)` - event approach gate can delay/release handler execution.
- `before_movement_plan(task, current_pos)` - inject anchors, avoid zones, event approach rules.
- `after_movement_step(step)` - diagnostics and overlay publication.
- `on_intent(intent)` - UI/input layer consumption boundary.
- `on_task_terminal(task, status)` - completed/failed cleanup.

Hook placement:

- Navigation task hooks belong in `core/navigation_tasks`, because they describe route/task lifecycle.
- Event detection/handler hooks belong in `core/events`.
- Cross-system hooks should be bridged by an adapter, not by importing GUI or concrete event packages into the task controller.

## Large-File Candidate

`controller.py` is 567 lines. It likely contains several responsibilities:

- Input validation and confidence handling.
- Task list construction.
- Scheduler invocation.
- Event task execution bridge.
- Movement executor bridge.
- Diagnostics and debug metadata.
- Intent creation.

Target split:

```text
controller.py                   # public facade, thin state owner
update_context.py                # NavigationUpdateContext and snapshots
localization_filter.py           # raw/trusted/control position filtering
static_task_runner.py            # required/exit task progression
event_task_runner.py             # EventCoordinator action -> navigation intent bridge
intent_factory.py                # MovementStep/EventAction/static terminal -> NavigationIntent
diagnostic_policy.py             # coordinate diagnostics integration
```

### `controller.py` Current Algorithm

Current `update()` does the following:

1. If a new route dict differs from `self.route`, deep-copy it through `load_route()` and mark controller active.
2. If inactive, return `NavigationIntent(message="navigation task controller inactive")`.
3. Determine whether the latest frame registration is a forced global relocalization.
4. Filter localization through `observe_localization()`:
   - reject missing or low-confidence positions,
   - reject large jumps unless confidence is high or forced,
   - update `trusted_pos`,
   - smooth into `control_pos`,
   - project onto route context and update route progress.
5. Record localization diagnostics.
6. If localization is invalid, return `WAIT`.
7. If forced relocalization is accepted:
   - mark diagnostics accepted,
   - reset movement,
   - optionally keep active event task for portal wait-result relocalization.
8. Consume any pending relocalization request into a `WAIT` intent with `metadata.force_relocalize=True`.
9. Mark required points completed when within arrival radius.
10. Pull dynamic event tasks from `event_coordinator.tasks()`.
11. Build unified tasks through `NavigationTaskBuilder`.
12. Pick one task through `NavigationTaskScheduler`.
13. Record navigation diagnostics.
14. Consume relocalization request again after task selection.
15. If selected task changes:
   - log transition,
   - reset movement,
   - reset event approach for non-event tasks.
16. If event task, call `_update_event_task()`.
17. Otherwise call `_update_static_task()`.

This algorithm is coherent, but too much is hidden behind one method. The first refactor should preserve this flow while moving phases into named modules.

### Static Task Runner

Current `_update_static_task()` handles:

1. Wait if `control_pos` is missing.
2. For exit tasks, check `is_inside_exit_region()`. If inside, stop controller and return `ARRIVED`.
3. For required tasks, if within `arrival_radius`, mark required completed, reset movement, and return `WAIT`.
4. Otherwise call `MovementExecutor.step()`.
5. Translate the returned `MovementStep` into `MOVE_MAP` or `WAIT`.

Extraction target:

```python
class StaticTaskRunner:
    def update(task, state, movement, planning_context, now_ms, lookahead_distance) -> NavigationIntent: ...
```

### Event Task Runner

Current `_update_event_task()` handles:

1. Wait if event context is missing.
2. Run `EventApproachController` until the event task is released for handler execution.
3. Call `event_coordinator.run_task(event_task_id, event_tick)`.
4. Translate `EventActionType` to `NavigationIntentType`:
   - `MOVE_TO` -> movement step or forced target click.
   - `CLICK_SCREEN` -> `CLICK_SCREEN`.
   - `PRESS_KEY` -> `PRESS_KEY`.
   - `WAIT` -> `WAIT`.
   - `COMPLETE` / `FAIL` -> terminal `WAIT` with metadata.
5. Reset movement/approach for terminal event actions.

Extraction target:

```python
class EventTaskRunner:
    def update(task, state, event_context, planning_context, now_ms, lookahead_distance) -> NavigationIntent: ...
```

Important boundary:

`EventApproachController` belongs to navigation, not to the portal event package. It decides when navigation is close/stable enough to allow an event handler to trigger. Event packages may supply approach preferences later, but the approach gate should remain a navigation-layer policy.

## Public Interface Proposal

Introduce grouped context objects:

```python
@dataclass
class LocalizationSnapshot:
    pos: tuple[float, float] | None
    confidence: float
    frame_registration: object | None = None

@dataclass
class PlanningSnapshot:
    wall_map: object
    pathfinder: object
    explored_map: object | None
    lookahead_distance: float

@dataclass
class EventRuntimeSnapshot:
    coordinator: object | None
    tick: object | None
    manual_event_only: bool = False

@dataclass
class NavigationUpdateContext:
    now_ms: int
    localization: LocalizationSnapshot
    route: dict | None
    planning: PlanningSnapshot
    events: EventRuntimeSnapshot
```

Then:

```python
def update(self, context: NavigationUpdateContext) -> NavigationIntent: ...
```

This does not reduce functionality, but it makes the interface stable and gives tests a single fixture object.

## Relationship to GUI Split

Once `NavigationUpdateContext` exists, `gui/modes/navigation/runtime_loop.py` can own context construction and call:

```python
intent = task_controller.update(context)
```

The GUI widget no longer needs to know the full controller parameter list.

Once `NavigationIntentExecutor` exists in GUI/navigation adapter code, `NavigationTaskController` no longer needs to care about click side effects. It already only emits intents, which is good.

## Relationship to Event Hooks

Do not put portal-specific hooks in `NavigationTaskController`.

Recommended shape:

```text
core/events
  emits EventTask + EventAction

core/navigation_tasks
  consumes EventTask through TaskBuilder
  consumes EventAction through EventTaskRunner
  emits NavigationIntent

gui/modes/navigation
  adapts NavigationIntent to MotionController
  adapts event status to UI/dialog/overlay
```

Cross-system extension points should be generic:

- Event system hook: "event task changed".
- Navigation task hook: "event navigation task selected".
- Navigation event runner hook: "event action translated".

Portal can observe these through configuration/log adapters, but should not be required by the task controller.

## Round Status

Status: partial. Main task models, controller, movement executor, scheduler, builder, route context, event approach, and coordinate diagnostics were read. Exhaustive branch-level tests are still pending.

Next read target:

- `core/events/models.py`
- `core/events/coordinator.py`
- `core/events/memory.py`
- `core/events/runner.py`
- `core/events/monitor.py`
