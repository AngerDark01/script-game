# Test Architecture

## System Role

`tests` should define the behavioral contracts that protect refactors. Each large-file split should be backed by tests around the extracted interface before the source file is changed.

## Existing Test Areas

| Test file | Covered area | Refactor use |
| --- | --- | --- |
| `test_motion_controller.py` | Click radius, bottom guard, execution options. | Protect input-system split. |
| `test_advanced_settings_file_io.py` | Advanced-settings JSON snapshot save/load helper. | Protect dialog file-IO split and explicit output directory. |
| `test_advanced_settings_presets.py` | Advanced-settings preset names/data and adapter application. | Protect data-only preset extraction. |
| `test_navigation_params_compat.py` | Legacy navigation preferences config round trip. | Protect hiding old UI fields while preserving config compatibility. |
| `test_nav_params_screen_estimator.py` | Navigation click-radius estimate policy. | Protect keeping radius math outside the Qt dialog. |
| `test_color_picker_debug_output.py` | Color-picker preview debug artifact opt-in switch. | Protect old debug-output cleanup. |
| `test_navigation_core.py` | Localization tracking behavior. | Protect localization split. |
| `test_path_utils.py` | Geometry utilities. | Protect route utility extraction. |
| `test_pathfinder.py` | A* movement and obstacle behavior. | Protect pathfinder/obstacle split. |
| `test_phase_displacement.py` | Shared phase-correlation displacement helper. | Protect mapping/localization displacement extraction. |
| `test_recognizer_optimized.py` | Recognition filtering behavior. | Protect recognizer pipeline split. |
| `test_route_manager.py` | Route persistence and mutation. | Protect route repository split. |
| `test_stitcher_core.py` | Visibility/merge behavior. | Protect stitching split. |
| `test_event_definition_repository.py` | Shared local/remote parsing, stable IDs, revision ownership, active-device ownership, and draft cloning. | Protect the canonical event-definition boundary. |
| `test_event_routes.py` | Legacy route normalization and pure dispatch decisions. | Protect route policy from platform adapters. |
| `test_event_execution_runtime.py` | Source/controller isolation and complete state frames. | Protect the shared local/remote execution runtime. |
| `core/runtime/tests/test_event_host_bridge.py` | Exact Host/LAN commands and payloads. | Protect the protocol adapter while core automation remains protocol-free. |
| `core/runtime/tests/test_event_hotkeys.py` | Edge-trigger semantics and supported key names. | Protect the injectable Win32 trigger adapter. |
| `core/runtime/tests/test_event_workbench_service.py` | Local/remote composition, catalog exchange, fanout isolation, direct-send deadline, and shutdown. | Protect the single service composition root. |
| `test_event_workbench_ui.py` | Injected service-only Qt adapter contract. | Prevent JSON, Host, or old-runtime ownership from returning to the page. |

## Verified Contracts

### `test_advanced_settings_file_io.py`

Protected behavior:

- Saving a snapshot uses an explicit caller-supplied directory and sanitizes filename-unsafe characters in the parameter name.
- The JSON payload keeps the original display name, ISO timestamp, and `parameters` object.
- Loading rejects files whose `parameters` field is not a JSON object.
- Display formatting preserves non-ASCII text.

Refactor safety:

- Protects `gui.dialogs.advanced_settings.file_io` without importing the full GUI package, avoiding unrelated `MainWindow`/input dependencies during the test.
- Good enough to keep JSON file IO out of `AdvancedSettingsDialog`; tab extraction still needs separate tests.

### `test_advanced_settings_presets.py`

Protected behavior:

- Preset option names keep the same user-visible order used by the combo box.
- Preset value dictionaries preserve the old widget values for each non-default preset.
- `apply_preset_to_widgets()` applies data-driven preset values, still delegates the default preset to full reset, and returns `False` for unknown names.

Refactor safety:

- Protects `advanced_settings/presets.py` and the adapter path without constructing a Qt dialog.
- Good enough to keep preset definitions out of `AdvancedSettingsDialog`; remaining risk is still the dialog-attribute based widget adapter.

### `test_motion_controller.py`

Protected behavior:

- Short map deltas use `movement_min_click_radius`.
- Long map deltas clamp to `movement_max_click_radius`.
- Zero map delta returns no click target.
- `_execute_click()` preserves out-of-screen requested coordinates unless `clamp_to_screen` is explicitly enabled.
- `_execute_click()` records target window, foreground/cursor diagnostics, requested/final screen position, and backend movement status.
- Optional focus-before-click calls the fake driver.
- Bottom click guard shortens downward clicks before the bottom UI region.

Refactor safety:

- Good enough to start extracting movement mapping and click policy.
- Add key-command and hook-emission tests before changing `press_key()` or adding an input hook bus.

### `test_navigation_params_compat.py`

Protected behavior:

- Old `nav_preferences.k_ratio/y_bias` values still load through `NavConfig.from_dict()`.
- `NavConfig.to_dict()` still writes those fields back unchanged.

Refactor safety:

- Protects removing the ineffective `k_ratio/y_bias` controls from `NavParametersDialog` while keeping old `config.json` files compatible.

### `test_nav_params_screen_estimator.py`

Protected behavior:

- Normal screen bounds produce the same min/max click radii as the old dialog math.
- Small screens clamp to the old minimums.
- Large screens clamp max radius to 900.
- Centers outside bounds return `None`.

Refactor safety:

- Protects `gui.dialogs.nav_params.screen_estimator` without importing the full GUI package.
- Good enough to keep `_auto_estimate_click_radius()` as a Qt adapter and continue extracting `NavParametersDialog` binding separately.

### `test_color_picker_debug_output.py`

Protected behavior:

- Color-picker preview debug output is disabled when the environment flag is absent.
- `MINIMAP_COLOR_PICKER_DEBUG` accepts explicit truthy values: `1`, `true`, `yes`, and `on`.
- Non-truthy values do not enable artifact writes.

Refactor safety:

- Protects the old-debug cleanup so preview rendering cannot silently resume unconditional png/txt writes.
- Does not test OpenCV file writes; those remain covered by the production helper path and can be probed manually when diagnostics are needed.

### `test_pathfinder.py`

Protected behavior:

- A* cannot diagonally cut through a blocked corner.
- Wall shrinking can reopen a false thin wall.
- Unknown/unexplored cells are treated as not walkable when `explored_map` is supplied.

Refactor safety:

- Good enough to move `pathfinder.py` and `navigation_obstacles.py` into a `core/routing/` package if imports are updated mechanically.

### `test_path_utils.py`

Protected behavior:

- Collinear path cleanup keeps turns.
- Exit-region radius check is circular.
- Projection and interpolation along a path use cumulative distance correctly.
- Smoothing shortcuts a fully visible straight segment.

Refactor safety:

- Good enough to move path geometry into `core/routing/geometry.py`.
- Missing direct tests for `line_is_walkable()` out-of-bounds behavior and blocked Bresenham segments.

### `test_navigation_core.py`

Protected behavior:

- F2F tracking uses `wall_mask`, not `match_mask`, when estimating displacement.
- Successful F2F updates global position by negative displacement and returns confidence.

Refactor safety:

- Useful narrow regression for localization matching.
- Not enough to split `NavigationCore` wholesale; add tests for map package loading, forced global relocalization, local/global template-match thresholds, and visual consistency rejection.

### `test_phase_displacement.py`

Protected behavior:

- Identical images are normalized to zero shift through the dead-zone filter.
- Invalid inputs return `(None, 0.0)`, preserving the old `_estimate_displacement()` failure contract.

Refactor safety:

- Protects the shared `core.phase_displacement.estimate_phase_displacement()` helper now used by `MapStitcher` and `NavigationCore`.

### `test_stitcher_core.py`

Protected behavior:

- `_merge_frame_weighted()` uses fog/visibility mask shape rather than always marking a full rectangle explored.
- Very small fog masks fall back to full-rect visibility behavior.

Refactor safety:

- Good first guard for extracting `WeightedMapMerger`.
- Add tests for first-frame placement, keyframe vs previous-frame fallback, displacement rejection, and package save/load before splitting `add_frame()`.

### `test_recognizer_optimized.py`

Protected behavior:

- Saturated dynamic icon pixels are removed from match features in transparent mode while wall pixels remain.

Refactor safety:

- Useful for extracting dynamic filtering.
- Add tests for preprocessing parameters, wall/fog/player mask extraction, player clear radius, and combined weights before splitting recognizer pipeline.

### `test_route_manager.py`

Protected behavior:

- Missing route file returns an empty default main route.
- Exit region, required points, and guide points round-trip through save/load.
- Undo required point affects only required points.

Refactor safety:

- Good enough to extract route repository logic.
- Add schema migration/default tests if route format expands.

### Unified action-event runtime tests

Protected behavior:

- One repository parses both local and remote definitions, gives each event a
  stable ID, increments revision only when content changes, and rebinds local
  ownership to the active Host device without changing ID/revision.
- Route parsing accepts the existing Chinese/English values and emits pure
  `EventDispatch` objects for controller 1, 2, or both.
- Local and remote dispatch share one execution implementation while sessions
  remain isolated by source and controller; cancellation emits neutral state
  only for the canceled source.
- The Host adapter keeps event drain and catalog drain separate and preserves
  exact `event.state`, `event.clear`, `sync.share.event`, and catalog payloads.
- A failed peer does not prevent A -> B/C fanout to later connected peers.
- The Qt page is testable with a fake service and performs no direct filesystem
  writes, Host access, or legacy-runtime construction.

Refactor safety:

- The deleted local, remote, catalog, and direct-sender runtime tests were
  replaced by lower-level contracts and service-level integration tests rather
  than retained as compatibility shells.
- Real controller input and real LAN synchronization remain opt-in; these tests
  use fake trigger sources, fake bridges, temporary files, and offscreen Qt.

## Needed Test Additions

Before splitting large files, add tests for:

- `NavigationModeWidget` orchestration behavior through smaller non-GUI functions where possible.
- `NavigationTaskController` intent conversion and event bridge behavior.
- `EventCoordinator` lifecycle with fake detector/handler adapters.
- Portal handler state transitions with fake ticks and fake captures.
- Config round trips for navigation and event settings.
- `anchor_path.py` ordered-anchor filtering, reached-anchor skipping, direct fallback, and probe fallback.
- `MappingSession.tick()` capture/recognize/stitch behavior with fake capture/recognizer/stitcher adapters.
- `ScalableMapWidget` click-coordinate mapping if map click navigation remains supported.
- `NavParametersDialog` config binding through a non-widget `field_specs` layer.

## Round Status

Status: partial for the full repository. The unified action-event workbench is
covered at pure-module, adapter, service, and GUI boundaries. Visual event
lifecycle, portal handler state, mapping session orchestration, and remaining
navigation GUI extraction still have their own coverage work.
