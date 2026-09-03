# Navigation Mode Architecture

## Current Role

`gui/modes/navigation_mode.py` is the navigation mode widget. It currently acts as:

- QWidget shell and top toolbar builder.
- Map list and map loader.
- Navigation configuration applier.
- Route editor and route persistence facade.
- Event manager dialog adapter.
- Event system bootstrapper.
- Screen/game-view overlay presenter.
- Navigation runtime loop.
- Navigation intent executor.
- Game-input window-mode controller.
- Calibration and hint-mode controller.

That is too much for one widget. The core problem is not only file length; it is that the widget owns both UI state and cross-system orchestration.

## Verified Current Method Groups

### Widget Shell

Methods:

- `__init__`
- `init_ui`
- `_connect_signals`
- `toggle_params_dialog`
- `toggle_event_dialog`
- `_toggle_owned_dialog`
- `_show_owned_dialog`

Current dependencies:

- PySide widgets and graphics scene.
- `NavParametersDialog`
- `EventManagerDialog`
- `ManualEventTestController`
- `RouteManager`
- `NavigationTaskController`
- `MotionController`
- Event registry/config/coordinator state.

Problem:

`__init__` creates almost every subsystem and mutable state bucket. This makes it hard to test any navigation behavior without constructing the full widget.

Target extraction:

```text
navigation_mode.py
  - construct child presenters/controllers
  - wire top-level signals
  - expose stop_runtime()
```

### Route Editing

Methods:

- `_set_map_click_mode`
- `toggle_exit_mode`
- `toggle_guide_mode`
- `toggle_required_mode`
- `_set_route_buttons_enabled`
- `load_route_data`
- `save_route`
- `undo_guide_point`
- `undo_required_point`
- `clear_route`
- `handle_map_click`

Current dependencies:

- `RouteManager`
- `map_folder_path`
- `route_data`
- `NavigationTaskController.load_route`
- `nav_core.crop_offset`
- `status_label`
- route overlay rendering

Target module:

```text
gui/modes/navigation/route_editor.py
```

Proposed interface:

```python
class NavigationRouteEditor:
    def set_mode(self, mode: str) -> None: ...
    def load(self, map_folder: str | None) -> dict | None: ...
    def save(self) -> bool: ...
    def undo_required(self) -> dict | None: ...
    def undo_guide(self) -> dict | None: ...
    def clear(self) -> dict | None: ...
    def handle_scene_click(self, scene_pos, *, nav_core) -> RouteEditResult: ...
```

Keep in widget:

- Button checked/enabled state.
- Calling presenter to show result messages.

### Map Loading and Config Application

Methods:

- `refresh_map_list`
- `load_map`
- `_apply_config_to_core`
- `_on_parameter_changed`
- `_configure_navigation_task_controller`
- `_save_nav_config`
- `_save_nav_default_config`
- `_compute_scale`

Current helper coverage:

- `navigation/map_runtime.py` already owns map folder discovery, nav config load/save, default config save, logical-to-physical conversion, and capture geometry.

Remaining problem:

`load_map()` still orchestrates too many side effects: reads config, creates `NavigationCore`, applies config to recognizer/pathfinder/motion/controller, initializes events, renders map, enables buttons, and updates status text.

Target modules:

```text
gui/modes/navigation/map_session.py
gui/modes/navigation/config_applier.py
```

Proposed responsibilities:

- `map_session.py`: load selected map, create `NavigationCore`, hold `map_folder_path`, `nav_config`, `nav_core`.
- `config_applier.py`: apply `NavConfig` to `NavigationCore`, `PathFinder`, `MotionController`, and `NavigationTaskController`.

Proposed interface:

```python
@dataclass
class NavigationMapSession:
    map_name: str
    map_folder_path: str
    nav_config: NavConfig
    nav_core: NavigationCore
    config_exists: bool

def load_navigation_map(file_anchor: str, map_name: str) -> NavigationMapSession: ...

def apply_navigation_config(
    *,
    nav_config: NavConfig,
    nav_core: NavigationCore,
    pathfinder,
    motion_controller,
    task_controller,
) -> None: ...
```

### Event Manager Adapter

Methods:

- `_ensure_event_dialog`
- `_connect_event_dialog_signals`
- `_initialize_event_system`
- `_refresh_event_dialog`
- `_on_event_config_changed`
- `_save_event_config`
- `_reset_portal_event_state`
- `_find_game_window_rect`
- `_build_event_tick`
- `_reset_event_move_runtime`
- `_run_portal_manual_test`
- `_set_portal_manual_test_active`
- `_event_status_text`

Current helper coverage:

- `navigation/event_adapter.py` already owns default registry creation, config summary, game-window lookup, `EventTick` creation, and status text.

Remaining problem:

The widget still owns event dialog wiring, event config persistence, manual portal test state, event runtime reset, and status messaging.

Target module:

```text
gui/modes/navigation/event_panel_adapter.py
```

Proposed interface:

```python
class NavigationEventPanelAdapter:
    def ensure_dialog(self) -> EventManagerDialog: ...
    def initialize_for_map(self, map_folder_path: str, map_name: str) -> EventCoordinator: ...
    def update_config(self, event_config) -> None: ...
    def save_config(self) -> bool: ...
    def reset_event_type(self, event_type: str) -> int: ...
    def build_tick(self, now_ms, frame, player_pos, localized_pos, confidence) -> EventTick: ...
    def start_manual_test(self, event_type: str) -> bool: ...
    def stop_manual_test(self, reason: str = "") -> None: ...
```

Widget should keep only user-facing message boxes and top-level button state.

### Overlay Presentation

Methods:

- `_clear_route_overlay`
- `_clear_event_overlay`
- `_global_to_scene`
- `_render_event_overlay`
- `_render_route_overlay`
- `_render_map`
- `_update_overlay_display`
- `_update_monitor_rect`
- `_update_game_view_rect`
- `_refresh_game_view_rect_from_known_position`
- `_show_last_exit_position`

Current helper coverage:

- `navigation/route_overlay.py` renders route, required points, guide points, current path, and subgoal.
- `navigation/event_overlay.py` renders event markers and labels.
- `navigation/viewport_overlay.py` calculates monitor and game-view rectangles.

Remaining problem:

`_render_map()` and marker item lifecycle still live in the widget, and route/event/viewport presenters are called manually from many places.

Target module:

```text
gui/modes/navigation/map_presenter.py
```

Proposed interface:

```python
class NavigationMapPresenter:
    def render_map(self, nav_core) -> None: ...
    def render_route(self, route_data, intent=None) -> None: ...
    def render_events(self, event_coordinator) -> None: ...
    def show_player(self, global_pos, *, capture_rect, player_local_pos) -> None: ...
    def show_hint(self, scene_pos) -> None: ...
    def show_last_exit_position(self, drawing_saved_pos) -> None: ...
    def update_viewport_rects(self, player_pos, *, capture_rect=None, player_local_pos=None) -> None: ...
```

### Runtime Loop

Methods:

- `toggle_auto_navigation`
- `toggle_navigation`
- `_use_unified_navigation_loop`
- `_navigation_loop_unified`
- `navigation_loop`

Current dependencies:

- `QTimer`
- capture geometry
- `app_context.screen_capture`
- `app_context.tracker`
- `nav_core.localize`
- `event_coordinator.observe`
- `event_dialog.refresh_tasks`
- `navigation_task_controller.update`
- `path_finder`
- overlay rendering
- status label formatting
- intent execution

Problem:

`_navigation_loop_unified()` is the highest coupling point. It reads frames, localizes, observes events, builds tasks, updates overlays, formats status, triggers relocalization, executes input, and manages terminal states.

Target module:

```text
gui/modes/navigation/runtime_loop.py
```

Proposed interface:

```python
@dataclass
class NavigationLoopResult:
    localized_pos: tuple[float, float] | None
    confidence: float
    capture_rect: dict
    player_local_pos: tuple[int, int] | None
    event_tick: object | None
    intent: object | None
    status: str

class NavigationRuntimeLoop:
    def start(self, fps: int) -> None: ...
    def stop(self) -> None: ...
    def tick(self) -> NavigationLoopResult | None: ...
```

Widget should consume `NavigationLoopResult` and pass it to presenters/executors.

### Intent Execution and Input Window Mode

Methods:

- `_can_start_auto_navigation`
- `_set_game_input_window_mode`
- `_execute_navigation_intent`

Current dependencies:

- Main window flags.
- `MotionController`
- `NavigationTaskController.record_intent_click`
- `NavigationIntentType`
- status label.

Target modules:

```text
gui/modes/navigation/input_window_mode.py
gui/modes/navigation/intent_executor.py
```

Proposed interfaces:

```python
class GameInputWindowMode:
    def enable(self) -> None: ...
    def disable(self) -> None: ...

class NavigationIntentExecutor:
    def execute(self, intent, now_ms: int) -> IntentExecutionResult: ...
```

`GameInputWindowMode` is GUI-specific. `NavigationIntentExecutor` is an adapter from task-controller intent to `MotionController`; it should be testable with a fake motion controller.

### Calibration and Hint Mode

Methods:

- `set_initial_hint`
- `toggle_hint_mode`
- `_calibrate_screen_center`
- `_handle_calibration_click`
- `eventFilter`

Target module:

```text
gui/modes/navigation/calibration_controller.py
```

Potential split:

- `HintModeController` for scene click to initial hint.
- `ScreenCenterCalibrationController` for `CenterPointSelector` and config update.

## Recommended Extraction Order

1. Add idempotent runtime methods on widget:

```python
def start_runtime(self) -> bool: ...
def stop_runtime(self) -> None: ...
```

This first step lets `MainWindow.closeEvent()` stop navigation safely without calling `toggle_navigation()`.

2. Extract `input_window_mode.py`.

Small surface, low algorithm risk, immediate locality gain.

3. Extract `intent_executor.py`.

This isolates real input side effects and makes task-controller output easier to test.

4. Extract `config_applier.py`.

This removes a dense block from the widget and creates a reusable place for config-to-runtime rules.

5. Extract `route_editor.py`.

Route editing has clear commands and already relies on `RouteManager`.

6. Extract `event_panel_adapter.py`.

Do after route and config because manual event test depends on navigation runtime and controller state.

7. Extract `runtime_loop.py`.

Do this after intent execution, config application, and event panel are isolated. The loop is the riskiest extraction because it crosses every subsystem.

8. Extract `map_presenter.py`.

Can be done before or after runtime loop, but it becomes cleaner once `NavigationLoopResult` exists.

## Public Widget Surface After Split

The target `NavigationModeWidget` should keep:

- `refresh_map_list()`
- `load_map()`
- `start_runtime()`
- `stop_runtime()`
- `toggle_navigation()` as UI slot only
- `toggle_auto_navigation()` as UI slot only
- `stop_auto_navigation()`
- `show_status(text: str)`

Everything else should move behind owned modules or presenters.

## Test Protection

Before extracting runtime loop:

- Unit test `NavigationIntentExecutor` with fake `MotionController`.
- Unit test `GameInputWindowMode` with fake main window object.
- Unit test `apply_navigation_config()` with fake nav core, pathfinder, motion controller, and task controller.
- Unit test `NavigationRouteEditor.handle_scene_click()` against a temporary route folder.
- Add a smoke test for `NavigationRuntimeLoop.tick()` using fake capture, fake nav core, fake event coordinator, and fake task controller.

## Current Status

Status: partial. Method grouping and helper coverage were read. The full behavior of each branch in `_navigation_loop_unified()` has not yet been exhaustively documented.
