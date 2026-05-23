# Event System Implementation Plan

## Goal
Implement the approved loose-coupled event architecture and deliver the first complete `portal` event without embedding portal-specific logic into `NavigationModeWidget`.

## Architecture Overview
The event system is exposed to navigation through `EventCoordinator`. TUI/config only sees complete event definitions such as `portal`; internal modules like minimap detector, main-view confirmer, and handler remain private to the event package. Event handlers return `EventAction` objects, and only `ActionExecutor` performs movement/click/key actions.

## Tech Stack
- Python 3
- PySide6 for current UI integration
- OpenCV / NumPy for image detection
- `unittest` for logic tests
- Existing `SquareScreenCapture`, `AutoNavigator`, `MotionController`, and `InputDriver`

## Phase 1: Core Event Contracts
### Task 1: Add event model dataclasses
Files:
- `core/events/__init__.py`
- `core/events/models.py`
- `tests/test_events_models.py`

Implement:
- `EventTick`
- `EventObservation`
- `EventTask`
- `EventAction`
- `EventActionType`
- `EventTaskState`

Tests:
- `EventAction.move_to()` builds a MOVE_TO action with global target.
- `EventAction.click_screen()` builds a CLICK_SCREEN action.
- `EventTask.mark_seen()` updates confidence and `last_seen_ms`.
- `EventTask.mark_completed()` sets state and timestamp.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_models
```

Expected:
```text
OK
```

Commit:
```text
feat: add event core models
```

### Task 2: Add event definition/detector/handler base protocols
Files:
- `core/events/base/__init__.py`
- `core/events/base/definition.py`
- `core/events/base/detector.py`
- `core/events/base/handler.py`
- `tests/test_events_base.py`

Implement:
- `EventDefinition` protocol/ABC.
- `EventDetector` protocol/ABC.
- `EventHandler` protocol/ABC.

Tests:
- A fake definition exposes `event_type`, `display_name`, config schema, detector factory, handler factory.
- A fake handler returns `EventAction.wait()`.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_base
```

Expected:
```text
OK
```

Commit:
```text
feat: add event base protocols
```

### Task 3: Add event registry
Files:
- `core/events/registry.py`
- `tests/test_events_registry.py`

Implement:
- `EventRegistry.register(definition)`
- `EventRegistry.get(event_type)`
- `EventRegistry.definitions()`
- duplicate event type rejection

Tests:
- Register `portal` fake definition.
- Lookup by event type.
- Duplicate registration raises `ValueError`.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_registry
```

Expected:
```text
OK
```

Commit:
```text
feat: add event registry
```

## Phase 2: Config, Projection, Memory
### Task 4: Add event config loader and merger
Files:
- `core/events/config.py`
- `assets/event_profiles/default.json`
- `tests/test_events_config.py`

Implement:
- `EventSystemConfig`
- load defaults from `assets/event_profiles/default.json`
- optional map override from `map_data/<map>/event_config.json`
- per-event config lookup

Tests:
- default config includes `portal.enabled`.
- map override changes only provided fields.
- disabled global config disables all event handling.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_config
```

Expected:
```text
OK
```

Commit:
```text
feat: add event config loading
```

### Task 5: Add minimap-to-global projector
Files:
- `core/events/projector.py`
- `tests/test_events_projector.py`

Implement:
```text
global_x = player_global_x + (local_x - player_local_x) / draw_scale
global_y = player_global_y + (local_y - player_local_y) / draw_scale
```

Tests:
- Center local position maps to player global position.
- Positive local delta maps using `draw_scale`.
- Missing player position returns `None`.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_projector
```

Expected:
```text
OK
```

Commit:
```text
feat: add event coordinate projector
```

### Task 6: Add event memory lifecycle
Files:
- `core/events/memory.py`
- `tests/test_events_memory.py`

Implement:
- Merge observations into tasks by `event_type + distance radius`.
- Require configurable `confirm_frames` before task becomes pending.
- Preserve task after it leaves minimap view.
- Mark completed and prevent immediate retrigger during cooldown.
- Mark failed and ignore after retry limit.

Tests:
- Same portal over 3 frames yields one task.
- Same portal after completion within cooldown does not create a new task.
- Nearby repeated observations dedupe.
- Far observations create separate tasks.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_memory
```

Expected:
```text
OK
```

Commit:
```text
feat: add event memory lifecycle
```

## Phase 3: Detection Utilities and Portal Event Package
### Task 7: Extract reusable template matcher
Files:
- `core/events/detectors/__init__.py`
- `core/events/detectors/template_matcher.py`
- `tests/test_events_template_matcher.py`

Implement:
- Move generic multi-scale template matching logic from `utils/event_icon_probe.py` into reusable core utility.
- Keep probe script as a CLI wrapper using the shared utility.

Tests:
- Synthetic image with pasted template returns one hit.
- Two templates near same center dedupe.
- No template match returns empty accepted hits but exposes best candidate for diagnostics if requested.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_template_matcher
D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\event_icon_probe.py
```

Expected:
```text
OK
```

Commit:
```text
feat: extract event template matcher
```

### Task 8: Add portal event config/assets/definition
Files:
- `core/events/types/__init__.py`
- `core/events/types/portal/__init__.py`
- `core/events/types/portal/assets.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/definition.py`
- `tests/test_portal_definition.py`

Implement:
- `PortalEventConfig`
- paths to minimap templates and main-view detector params
- `PortalEventDefinition`
- config schema suitable for TUI rendering

Tests:
- Definition exposes `event_type == "portal"`.
- Default config contains `enabled`, `priority`, `interaction`, `arrival_radius`.
- Asset paths exist.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_portal_definition
```

Expected:
```text
OK
```

Commit:
```text
feat: add portal event definition
```

### Task 9: Add portal minimap detector
Files:
- `core/events/types/portal/minimap_detector.py`
- `tests/test_portal_minimap_detector.py`

Implement:
- Load portal minimap templates from assets.
- Detect portal candidates from raw minimap frame.
- Convert local minimap center to global map position through `EventProjector`.
- Return `EventObservation(event_type="portal")`.

Tests:
- Synthetic minimap frame with template returns observation.
- Observation includes local and global coordinates.
- Low score returns no observation.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_portal_minimap_detector
```

Expected:
```text
OK
```

Commit:
```text
feat: add portal minimap detector
```

### Task 10: Extract portal main-view confirmer
Files:
- `core/events/types/portal/main_view_confirmer.py`
- `tests/test_portal_main_view_confirmer.py`

Implement:
- Move reusable blue/cyan/violet mask + contour scoring logic from `utils/portal_screen_probe.py`.
- Load thresholds from `blue_glow_detector_v1.json`.
- Return strict accepted candidates only.
- Keep probe script as CLI wrapper using the shared confirmer.

Tests:
- Synthetic blue circular portal returns accepted candidate.
- Small UI-like blue circle is below accepted threshold.
- Long blue rectangle is not accepted.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_portal_main_view_confirmer
D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\portal_screen_probe.py
```

Expected:
```text
OK
```

Commit:
```text
feat: add portal main-view confirmer
```

### Task 11: Add portal event handler state machine
Files:
- `core/events/types/portal/handler.py`
- `tests/test_portal_handler.py`

Implement states:
- `MOVE_NEAR_EVENT`
- `CONFIRM_MAIN_VIEW`
- `INTERACT`
- `WAIT_RESULT`
- `COMPLETE`
- `FAILED`

Tests:
- Far from event returns `MOVE_TO`.
- Near event with confirmed main-view candidate returns `CLICK_SCREEN`.
- No confirmation before timeout returns retry or fail.
- Exceed retry limit returns `FAIL`.
- After click and success signal returns `COMPLETE`.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_portal_handler
```

Expected:
```text
OK
```

Commit:
```text
feat: add portal event handler
```

## Phase 4: Coordinator and Action Execution
### Task 12: Add capture provider adapter
Files:
- `core/events/capture_provider.py`
- `tests/test_events_capture_provider.py`

Implement:
- `CaptureProvider` protocol.
- Simple `StaticCaptureProvider` for tests.
- Navigation adapter placeholder that can wrap current screen capture and configured game window rect.

Tests:
- Static provider returns minimap and game-view frames.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_capture_provider
```

Expected:
```text
OK
```

Commit:
```text
feat: add event capture provider
```

### Task 13: Add action executor
Files:
- `core/events/action_executor.py`
- `tests/test_events_action_executor.py`

Implement:
- Execute `MOVE_TO` by calling an injected movement callback.
- Execute `CLICK_SCREEN` by calling an injected click callback.
- Execute `WAIT`, `COMPLETE`, `FAIL` without side effects.

Tests:
- MOVE_TO invokes movement callback with target global pos.
- CLICK_SCREEN invokes click callback with screen pos.
- WAIT does not invoke movement/click callbacks.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_action_executor
```

Expected:
```text
OK
```

Commit:
```text
feat: add event action executor
```

### Task 14: Add coordinator, monitor, scheduler, runner
Files:
- `core/events/coordinator.py`
- `core/events/monitor.py`
- `core/events/scheduler.py`
- `core/events/runner.py`
- `tests/test_events_coordinator.py`

Implement:
- `EventMonitor` calls enabled detectors.
- `EventScheduler` preserves running task; otherwise picks highest priority pending task.
- `EventRunner` starts handler and updates task on COMPLETE/FAIL.
- `EventCoordinator.update(tick)` returns event action or `None`.

Tests:
- Disabled event config returns no action.
- Observation becomes task after confirm frames.
- Pending portal starts handler.
- Running task is not preempted.
- COMPLETE marks task completed and releases active task.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_coordinator
```

Expected:
```text
OK
```

Commit:
```text
feat: add event coordinator flow
```

## Phase 5: Navigation Integration
### Task 15: Wire event coordinator into NavigationMode initialization
Files:
- `gui/modes/navigation_mode.py`
- `tests/test_navigation_event_integration.py`

Implement:
- Create event registry with `PortalEventDefinition`.
- Load `event_config.json` for current map when map loads.
- Initialize `EventCoordinator`.
- Do not execute actions yet in this task.

Tests:
- Loading a map initializes coordinator when event config exists.
- Missing `event_config.json` uses defaults.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_navigation_event_integration
```

Expected:
```text
OK
```

Commit:
```text
feat: initialize event coordinator in navigation mode
```

### Task 16: Feed EventTick from navigation loop
Files:
- `gui/modes/navigation_mode.py`
- `tests/test_navigation_event_integration.py`

Implement:
- Build `EventTick` after localization.
- Pass raw minimap frame, player global pos, local minimap player pos, draw scale, confidence, capture provider.
- If coordinator returns `None`, keep existing AutoNavigator behavior unchanged.

Tests:
- Fake coordinator receives tick with raw frame and localized pos.
- Existing auto navigation path still runs when coordinator returns `None`.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_navigation_event_integration tests.test_auto_navigator
```

Expected:
```text
OK
```

Commit:
```text
feat: feed event coordinator from navigation loop
```

### Task 17: Execute event actions before normal auto move
Files:
- `gui/modes/navigation_mode.py`
- `core/events/action_executor.py`
- `tests/test_navigation_event_integration.py`

Implement:
- If coordinator returns `MOVE_TO`, call ActionExecutor and skip normal AutoNavigator click for that frame.
- If `CLICK_SCREEN`, execute click and skip normal AutoNavigator.
- If `WAIT`, skip normal AutoNavigator for that frame.
- If `COMPLETE/FAIL`, allow normal AutoNavigator next frame.

Tests:
- Event MOVE_TO suppresses normal route click.
- Event WAIT suppresses normal route click.
- No event action preserves existing behavior.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_navigation_event_integration tests.test_auto_navigator tests.test_motion_controller
```

Expected:
```text
OK
```

Commit:
```text
feat: execute event actions in navigation loop
```

### Task 18: Add event overlay model and rendering
Files:
- `core/events/overlay_models.py`
- `gui/modes/navigation_mode.py`
- `tests/test_events_overlay.py`

Implement:
- `EventOverlayModel`.
- Coordinator exposes overlay models from memory.
- Navigation map renders event marker labels without knowing portal internals.

Tests:
- Pending portal task creates overlay model.
- Completed task can be hidden or rendered as completed according to config.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_overlay
```

Expected:
```text
OK
```

Commit:
```text
feat: render event overlays
```

## Phase 6: TUI/Config Surface
### Task 19: Add event config persistence helpers
Files:
- `core/events/config.py`
- `tests/test_events_config.py`

Implement:
- Save `map_data/<map>/event_config.json`.
- Preserve unknown keys for forward compatibility.
- Validate enabled event types against registry.

Tests:
- Saving config writes expected JSON.
- Unknown event type is ignored or surfaced as validation warning.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_config
```

Expected:
```text
OK
```

Commit:
```text
feat: persist event configuration
```

### Task 20: Add TUI-facing event options model
Files:
- `core/events/config.py`
- `tests/test_events_tui_model.py`

Implement:
- Function that returns complete event options from registry:
  - `event_type`
  - `display_name`
  - `enabled`
  - `schema`
  - `current_values`
- Do not expose internal detector/confirmer names.

Tests:
- Portal appears as one option.
- No `PortalMinimapDetector` or `PortalMainViewConfirmer` appears in option output.

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_tui_model
```

Expected:
```text
OK
```

Commit:
```text
feat: add tui event options model
```

## Phase 7: End-to-End Verification
### Task 21: Run full unit suite
Files:
- no code changes

Verify:
```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_events_models tests.test_events_base tests.test_events_registry tests.test_events_config tests.test_events_projector tests.test_events_memory tests.test_events_template_matcher tests.test_portal_definition tests.test_portal_minimap_detector tests.test_portal_main_view_confirmer tests.test_portal_handler tests.test_events_capture_provider tests.test_events_action_executor tests.test_events_coordinator tests.test_navigation_event_integration tests.test_events_overlay tests.test_events_tui_model tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller tests.test_navigation_core tests.test_recognizer_optimized tests.test_stitcher_core
```

Expected:
```text
OK
```

Commit:
```text
test: verify event system integration
```

### Task 22: Manual probe verification
Files:
- no code changes unless probes need import-path updates

Verify minimap portal templates:
```powershell
D:\ACloud\.venv\Scripts\python.exe utils\event_icon_probe.py --map-folder map_data\A1 --template assets\event_templates\portal\minimap\portal_minimap_01.png --template assets\event_templates\portal\minimap\portal_minimap_02.png --threshold 0.60 --top-k 10 --output-dir debug\event_probe\portal_match_after_integration
```

Verify main-view portal confirmer:
```powershell
D:\ACloud\.venv\Scripts\python.exe utils\portal_screen_probe.py --params assets\event_detectors\portal\main_view\blue_glow_detector_v1.json --output-dir debug\portal_screen_probe\after_integration --top-k 12
```

Expected:
- Minimap probe still reports accepted hits when portal icons are visible.
- Main-view probe reports one accepted portal when the real portal entity is visible, or zero accepted when it is not visible/blocked.

Commit:
```text
test: verify event probes after integration
```

## Execution Options
Option A: execute this plan in the current session task-by-task.

Option B: execute in a separate session with human checkpoints between phases.
