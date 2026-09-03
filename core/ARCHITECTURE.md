# Core Architecture

## System Role

`core` owns reusable runtime behavior that should not depend on PySide widgets. It should expose small interfaces for:

- Mapping and stitching.
- Image recognition and player tracking.
- Navigation localization.
- Path planning and route utilities.
- Movement input execution.
- Event processing and navigation task orchestration through subpackages.

## Public Package Interface

`core/__init__.py` currently exports:

- `ScreenCapture`
- `HSVRecognizer`
- `MapStitcher`
- `PlayerTracker`
- `PathFinder`

This is the current default composition surface used by `gui/app_context.py`.

Refactor implication: as more systems become explicit packages, `core/__init__.py` should avoid becoming a broad convenience import for every subsystem. Keep it limited to stable top-level capabilities, or move composition imports into `gui/app_context.py`.

## Current Modules

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `capture.py` | Screen capture source. | Should be an adapter behind a capture interface used by mapping, navigation, and events. |
| `recognizer_optimized.py` | HSV/wall/fog/player feature extraction. | Candidate for reusable image feature pipeline with explicit parameter object. |
| `phase_displacement.py` | Shared phase-correlation displacement helper. | Newly extracted reusable algorithm used by mapping and localization wrappers. |
| `stitcher_core.py` | Stateful map stitching and map package IO. | Candidate for splitting package IO, displacement estimation, and frame merge strategy. |
| `navigation_core.py` | Runtime localization against saved map data. | Candidate for separating map package loading, frame matching, and tracking state. |
| `navigation_obstacles.py` | Derives A* obstacle layer from wall layer. | Already looks like a deep utility if its interface remains small. |
| `pathfinder.py` | A* implementation. | Should stay GUI-free and expose stable path planning contract. |
| `path_utils.py` | Path smoothing/projection/interpolation utilities. | Candidate shared geometry component. |
| `anchor_path.py` | Optional soft-anchor path planning. | Candidate reusable route shaping module used by movement executor. |
| `motion_controller.py` | Map target to screen click/key actions. | Should be an input-system facade, with Windows/pydirectinput details hidden behind `input_driver.py`. |
| `input_driver.py` | Win32 input adapter. | Concrete adapter for real input side effects. |

## Target System Split

```text
core
├── mapping system
│   ├── recognizer pipeline
│   ├── displacement estimator
│   ├── frame merge strategy
│   └── map package repository
├── localization system
│   ├── map package reader
│   ├── frame matcher
│   └── tracking state
├── route planning system
│   ├── obstacle derivation
│   ├── A* pathfinder
│   ├── route geometry
│   └── anchor corridor planner
└── input system
    ├── movement target mapper
    ├── click/key command executor
    └── platform adapters
```

## Immediate Split Candidates

### `core/stitcher_core.py`

Current risk: map package IO, stateful stitching, phase/displacement behavior, weighted merging, and visualization output appear to live together.

Likely extraction modules:

- `core/mapping/package_io.py` - save/load map package.
- `core/mapping/displacement.py` - phase correlation and smoothing.
- `core/mapping/merge.py` - first-frame placement and weighted frame merge.
- `core/mapping/view.py` - cropped/enhanced map rendering.

Verified responsibilities:

- Stateful map canvas: `canvas`, `wall_layer`, `fog_layer`, `explored_map`, `weight_layer`, current position, keyframe/previous frame.
- Map package IO: `save_map_package()`, `load_map_package()`.
- Frame registration: `add_frame()` chooses keyframe phase correlation or previous-frame fallback.
- Displacement utility: `_estimate_displacement()` uses `cv2.phaseCorrelate` with Hanning window and dead-zone filter.
- Merge algorithm: `_merge_frame_weighted()` clips frame ROI, updates wall weight layer, applies visibility/explored map, and writes display canvas.
- Display rendering: `get_cropped_map()`, `get_enhanced_map()`.

`add_frame()` algorithm:

1. Increment frame counters and choose player position in local minimap coordinates.
2. If first frame:
   - place frame at canvas center,
   - set current keyframe and previous frame,
   - return success.
3. Try keyframe anchor matching:
   - phase correlate `keyframe_mask` with current `match_mask`,
   - reject low quality,
   - reject large jump unless quality is high.
4. If anchor is valid:
   - convert shift to global scaled delta,
   - update current global position from keyframe position.
5. If anchor is invalid:
   - phase correlate `prev_mask` with current `match_mask`,
   - reject low quality or excessive F2F shift,
   - update current global position from previous position,
   - update keyframe only when current feature count is high enough.
6. If match succeeds but quality is below `draw_quality_gate`, update previous frame but skip map merge.
7. Resize save/fog masks by `draw_scale`.
8. Standardize wall thickness.
9. Merge into map through `_merge_frame_weighted()`.
10. Update previous frame and match statistics.

Refactor order:

1. `estimate_phase_displacement(img1, img2)` has been extracted to `core/phase_displacement.py`; keep `_estimate_displacement()` as a compatibility wrapper while callers and tests still patch it.
2. Extract `MapPackageRepository` for `.npz` save/load.
3. Extract `WeightedMapMerger` around `_merge_frame_weighted()`.
4. Extract display rendering only after map package and merge tests exist.

### `core/navigation_core.py`

Current risk: map loading, localization, tracking mode, confidence handling, and debug details may be coupled.

Likely extraction modules:

- `core/localization/map_package.py` - loaded map data and coordinate metadata.
- `core/localization/frame_matcher.py` - local/global frame matching algorithms.
- `core/localization/tracking_state.py` - F2F/localized state transitions.

Verified responsibilities:

- Map package loading from `map_data.npz`.
- Navigation obstacle layer derivation.
- Runtime recognizer construction.
- Localization state: current/last/drawing positions, localized flags, previous masks, forced relocalization flags.
- Frame registration metadata for event positioning and coordinate diagnostics.
- F2F tracking using phase correlation.
- Local/global template matching against `wall_layer`.
- Visual consistency check around the expected player position.
- Display map rendering and crop offset calculation.

`localize()` algorithm:

1. Reject missing frame.
2. Resolve player position from argument, last player-local position, or frame center.
3. Use `HSVRecognizer.extract_combined()` to get `match_mask`, `wall_mask`, and `fog_mask`.
4. Reject if match/wall feature counts are below thresholds.
5. Consume forced-global relocalization flag and decide full-map vs local search.
6. If already localized and not forced:
   - phase correlate previous wall mask against current wall mask,
   - reject low confidence or large shift,
   - update current global position by `-shift * draw_scale`,
   - run optional visual consistency check,
   - set frame registration source `f2f`,
   - return position.
7. If F2F is unavailable or rejected:
   - choose full map or local search window,
   - resize wall mask to map `draw_scale`,
   - standardize wall template thickness,
   - `cv2.matchTemplate()` against search area,
   - require confidence based on full/local mode,
   - compute global player coordinate from matched top-left plus scaled player local position,
   - reject large local relocalization jumps,
   - update localization state and frame registration source `template_match`.
8. On failure, clear or downgrade state and return `(None, None, confidence)`.

Refactor order:

1. `estimate_phase_displacement(img1, img2)` has been extracted to `core/phase_displacement.py`; keep `_estimate_displacement()` as a compatibility wrapper while tests and callers adapt.
2. Extract `MapDataPackage` loader.
3. Extract `FrameRegistrationFactory`.
4. Extract `LocalizationMatcher` for F2F and template match.
5. Keep `NavigationCore` as a stateful facade until callers are adapted.

### Route Planning Modules

Current state: route planning is one of the cleaner parts of `core`. The modules are GUI-free, mostly pure, and already separate low-level geometry from A* and ordered-anchor route shaping.

Candidate package grouping:

```text
core/routing/
├── obstacles.py      # current navigation_obstacles.py
├── pathfinder.py     # current pathfinder.py
├── geometry.py       # current path_utils.py
└── anchors.py        # current anchor_path.py
```

This package move is optional and should be delayed until callers are touched for another reason. The current files already have useful locality; splitting the individual algorithms further would mostly create pass-through modules.

Verified responsibilities:

- `navigation_obstacles.derive_navigation_wall_layer()` turns the stitched wall layer into a navigation-only wall layer by thresholding and optional cross-kernel erosion. This keeps A* forgiving without altering localization data.
- `PathFinder.find_path()` is the public A* planning adapter. It accepts map-space start/end positions and returns map-space path points.
- `path_utils.py` owns reusable route geometry: distance, collinear simplification, Bresenham line walkability, shortcut smoothing, cumulative distances, projection, interpolation, path distance, and exit-region checks.
- `anchor_path.plan_path_with_optional_anchors()` owns ordered user-guide-anchor policy before falling back to direct A*.

`PathFinder.find_path()` algorithm:

1. Convert map-space `start_pos` and `end_pos` into downsampled grid cells using `downsample_factor`.
2. Reject start/end cells outside the downsampled map bounds.
3. Build a downsampled obstacle grid:
   - threshold the wall map,
   - optionally erode wall pixels before downsampling through `wall_shrink_iterations`,
   - optionally mark unexplored cells as obstacles from `explored_map`,
   - optionally dilate obstacles by `safety_margin`.
4. Clear a circular start area based on `start_clear_radius` to tolerate local wall noise around the live player.
5. If start or end is still blocked, search nearby grid cells within `walkable_snap_radius` and snap to the first walkable cell found by Manhattan-radius scan.
6. Run A* over 8-neighbor movement:
   - orthogonal cost is `1.0`,
   - diagonal cost is `1.414`,
   - Manhattan distance is the heuristic,
   - diagonal movement is rejected when either adjacent orthogonal side cell is blocked, preventing corner cutting.
7. Reconstruct the grid path from `came_from`.
8. Convert grid cells back to map-space center points and append the exact requested end point when needed.

`path_utils.smooth_path()` algorithm:

1. Return `[]` for empty input.
2. Remove exactly collinear intermediate points.
3. Starting from the current anchor point, probe backward from the final point until a Bresenham line is walkable.
4. Jump the anchor to the farthest visible point.
5. Repeat until the final point is reached.

`anchor_path.plan_path_with_optional_anchors()` algorithm:

1. Normalize start, target, and anchors to integer points.
2. Dedupe anchors while preserving authoring order.
3. Project start and target progress onto the ordered anchor polyline.
4. Keep only forward anchors between current progress and target progress, skipping already reached anchors.
5. If at least one forward anchor remains:
   - try A* from start to the next anchor,
   - return `path_kind="anchor_step"` on success,
   - otherwise return a short two-point `path_kind="anchor_probe"` toward that anchor.
6. If no anchors are relevant, plan direct A* to the target and return `path_kind="planned"`.
7. Return `None` only when there is no anchor fallback and direct A* fails.

Refactor guidance:

1. Keep these modules source-compatible until movement/navigation tests cover route selection.
2. Add direct tests for `anchor_path.py`, especially forward-anchor filtering, reached-anchor skipping, direct fallback, and probe fallback.
3. If a package move is desired, move all four files together into `core/routing/` and update imports mechanically.
4. Do not merge anchor policy into `PathFinder`; A* should remain a low-level planner while anchor planning remains a route-shaping policy.

### `core/motion_controller.py`

Current risk: movement math, click policy, concrete click execution, diagnostics, and key execution live in one class.

Verified responsibilities:

- Stores calibration and movement parameters: `game_screen_center`, movement scale, min/max click radius, precision cap, bottom click guard, backend, and control enablement.
- Converts map-space player/target coordinates into a screen click around the calibrated character center.
- Supports forced precise mapped target clicks for near-goal or event point interactions.
- Supports direct screen clicks for event actions.
- Executes keyboard interactions through `pydirectinput.press()`.
- Applies bottom-click guard to avoid screen-bottom UI.
- Optionally clamps coordinates to the visible screen.
- Optionally focuses the target window before clicking.
- Collects rich click diagnostics into `last_click_info`: requested/final screen pos, radius, target window, foreground window, cursor positions, backend, bottom guard, and confirmation behavior.
- Lazily constructs `InputDriver` so unit tests can inject fakes.

`move_to_map_target()` algorithm:

1. Reject when `control_enabled` is false.
2. Reject when `game_screen_center` is not calibrated.
3. Compute delta between target and player in map coordinates.
4. Reject near-zero map distance.
5. Convert map distance to raw screen radius through `movement_scale_factor`.
6. Clamp screen radius to `[movement_min_click_radius, movement_max_click_radius]`.
7. Normalize map delta to a direction vector.
8. Add direction-scaled radius to `game_screen_center`.
9. Execute the resulting screen click through `_execute_click()`.

`click_map_target_once()` differs by using `_calculate_mapped_target_screen_position()`:

- no minimum radius,
- radius is capped by `movement_precision_click_max_radius`,
- works even when the map target is nearly overlapping the player.

`_execute_click()` algorithm:

1. Normalize requested screen coordinates to integers.
2. Lazily acquire `InputDriver` if the selected backend, diagnostics, or focus behavior need it.
3. Apply `_apply_bottom_click_guard()` to shorten downward clicks that would land in bottom UI.
4. Optionally clamp to screen bounds.
5. Record requested/guarded/final screen coordinates in `last_click_info`.
6. If debug diagnostics are enabled, collect target window, foreground window, cursor clip rectangle, and Win32 cursor position.
7. Optionally focus the window under the click target.
8. Record pydirectinput screen size and cursor position.
9. Send click through `_send_click()`.
10. Record cursor positions after click.
11. If the preferred backend fails, print the exception and fall back to `pydirectinput.click(x, y, button=...)`.

`_apply_bottom_click_guard()` algorithm:

1. Return unchanged when guard is disabled or no game center is calibrated.
2. Resolve screen height from `InputDriver` or `pydirectinput.size()`.
3. Compute `forbidden_top = screen_height - bottom_click_guard_pixels`.
4. Compute `safe_y = forbidden_top - bottom_click_guard_margin`.
5. Return unchanged if target `y` is already safe or not below the character center.
6. Interpolate from game center to requested point so the adjusted point lands at `safe_y`.
7. Return adjusted point plus diagnostic info.

Likely extraction modules:

- `core/input/movement_mapping.py` - pure map delta to screen coordinate and radius result.
- `core/input/click_policy.py` - bottom guard, optional screen clamp, precision cap, and diagnostic DTOs.
- `core/input/command_sink.py` - click/key command interface plus hook dispatch.
- `core/input/win32_driver.py` - current `input_driver.py` implementation.
- `core/input/pydirect_driver.py` - pydirectinput fallback/key adapter if keyboard remains pydirect-based.

Target seam:

```text
NavigationIntentExecutor
  └─ MotionController
       ├─ MovementMapper          # pure
       ├─ ClickPolicy             # pure-ish
       ├─ InputHookBus            # before/after/skipped/failure diagnostics
       └─ InputCommandSink
            ├─ Win32MouseEventSink
            └─ PyDirectInputSink
```

Hook points:

- `before_input_command(command, context)` - inspect click/key before side effects.
- `after_input_command(command, result)` - observe success, final cursor/window diagnostics.
- `input_command_skipped(reason, context)` - disabled control, missing calibration, zero delta, empty key.
- `input_backend_failed(command, exception)` - preferred backend failed before fallback.

Adapter gap:

- `press_key()` currently calls `pydirectinput.press()` directly and is not covered by `InputDriver`. Introduce a key-capable command sink before adding deeper event input hooks.

Tests:

- `tests/test_motion_controller.py` already covers min/max radius mapping, zero-delta skip, `_execute_click()` diagnostics, explicit screen clamp, focus-before-click, and bottom guard with fake drivers.
- Add tests before extraction for forced target clicks, direct screen clicks, key command adapter, and hook emission.

### `core/recognizer_optimized.py`

Current risk: parameter storage, image preprocessing, wall/fog/player extraction, dynamic-object filtering, and combined registration mask creation live in one class.

Verified responsibilities:

- Holds all HSV/preprocess parameters and mutable CLAHE kernels.
- Wall preprocessing with gamma, blur, CLAHE, top-hat, percentile stretch, deepen/blue boost.
- Fog preprocessing with blur, percentile stretch, and mild brighten.
- Transparent wall score `(V - S * penalty)` plus top-hat.
- Wall/fog/player mask extraction.
- Small component filtering.
- Combined mask extraction for stitching/localization.

`extract_combined()` algorithm:

1. Extract wall mask through wall preprocessing.
2. Extract fog mask through fog preprocessing.
3. Build wall-processed grayscale image and Canny edges.
4. If saturation filter is enabled:
   - threshold high-saturation pixels from raw HSV,
   - optionally restrict filtering to player radius,
   - dilate dynamic mask,
   - remove dynamic pixels from wall, fog, and edges.
5. Clear player-centered dynamic radius from wall, fog, and edges.
6. Normalize wall/edge weights.
7. Blend wall mask and edge mask into `match_mask`.
8. Clear player radius from `match_mask`.
9. Return `(match_mask, wall_mask, fog_mask)`.

Refactor target:

```text
core/recognition/params.py          # HSVRecognizerParams or dataclass
core/recognition/preprocess.py      # wall/fog preprocessing functions
core/recognition/masks.py           # wall/fog/player mask extraction
core/recognition/dynamic_filter.py  # saturation/player clear filtering
core/recognition/combined.py        # match/save/fog combined output
```

Keep `HSVRecognizer` as compatibility facade initially.

## Shared Phase Displacement

`MapStitcher._estimate_displacement()` and `NavigationCore._estimate_displacement()` now delegate to:

```python
def estimate_phase_displacement(img1, img2, *, dead_zone: float = 0.2) -> tuple[tuple[float, float] | None, float]:
    ...
```

This helper performs Hanning-window phase correlation, normalizes tiny shifts inside the dead zone to `(0.0, 0.0)`, and preserves the existing failure contract `(None, 0.0)`.

Tests:

- `tests/test_phase_displacement.py` covers identical-image dead-zone normalization and invalid-input failure behavior.
- `tests/test_navigation_core.py` still verifies that F2F tracking passes wall masks into the displacement wrapper.
- `tests/test_stitcher_core.py` remains the merge safety net.

## Round Status

Status: partial. Package export and composition use were read; algorithm bodies are still pending.

Next read targets:

- `core/pathfinder.py`, `core/path_utils.py`, `core/anchor_path.py`
