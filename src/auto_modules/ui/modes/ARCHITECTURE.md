# GUI Modes Architecture

## System Role

`gui/modes` owns the two main user workflows:

- Mapping mode: capture minimap frames and build map packages.
- Navigation mode: load map packages, localize the player, edit route targets, run navigation, and show overlays.

## Large-File Priority

### `navigation_mode.py` - 1525 lines

This is the primary split candidate.

Observed mixed responsibilities from the existing index:

- UI construction.
- Signal wiring.
- Map list and map loading.
- Route editing.
- Navigation loop.
- Event system initialization and dialog wiring.
- Automatic navigation control.
- Overlay display.
- Parameter saving/loading.
- Screen/game-view calibration.
- Input-window topmost/lowering behavior.

Target split:

```text
navigation_mode.py              # thin QWidget shell
navigation/runtime_loop.py      # timer tick, capture, localization, controller update
navigation/map_loader.py        # map list, config, route data loading
navigation/route_editor.py      # map click modes and route mutations
navigation/event_panel_adapter.py # dialog wiring and event config save/reset
navigation/input_window_mode.py # topmost/lower/focus behavior
navigation/status_presenter.py  # labels and button state
navigation/overlay_presenter.py # route/event/viewport overlay coordination
```

Existing helper files already provide a start:

- `navigation/map_runtime.py`
- `navigation/route_overlay.py`
- `navigation/event_overlay.py`
- `navigation/viewport_overlay.py`
- `navigation/event_adapter.py`

The next step should deepen these helpers and move orchestration out of the main widget.

Detailed split map: [navigation/ARCHITECTURE.md](navigation/ARCHITECTURE.md).

### `mapping_widget.py` - 634 lines

Likely split:

```text
mapping_widget.py              # thin QWidget shell
mapping/runtime_loop.py         # capture and stitch timer loop
mapping/project_io.py           # project root, map package, config save/load
mapping/status_presenter.py     # labels and UI state
mapping/overlay_presenter.py    # current position and map overlay display
mapping/region_calibration.py   # monitor region/center selection state
mapping/session.py              # capture -> recognize -> stitch workflow facade
```

Existing helper files:

- `mapping/map_renderer.py`
- `mapping/params_adapter.py`
- `mapping/save_load.py`

Verified current responsibilities:

- `MappingWidget.__init__()` stores `app_context` and `main_window`, creates a `QTimer`, connects it to `capture_and_process()`, creates `TransparentOverlay`, builds UI, and loads saved config.
- `create_control_panel()` builds region selection, monitoring controls, geometry/stitching controls, HSV toggles, feature controls, advanced settings, and stats.
- `create_display_panel()` builds live capture display and a collapsible global map display.
- `select_region()` and `select_center_point()` start full-screen selection overlays and wire their result signals.
- `on_region_selected()` stores a physical capture region in `app_context.monitor_region`, clears logical center mode, enables controls, and saves config.
- `on_center_selected()` stores logical center and physical center, switches to square capture mode, enables controls, and saves config.
- `toggle_monitoring()` flips `app_context.monitoring` and starts/stops `capture_timer` at `1000 // fps`.
- `capture_and_process()` is the mapping runtime loop.
- `update_displays()` renders current capture and global map overlay.
- `on_map_click()` plans a temporary path through `PathFinder` from current stitcher position to clicked map coordinate.
- `save_map()` writes map package plus map-specific config under `map_data/<map_name>/`.
- `load_saved_params()` reads root `config.json`, restores monitor selection, recognizer/stitcher params, and geometry widgets.

`capture_and_process()` algorithm:

1. Return immediately when `app_context.monitoring` is false.
2. Capture either:
   - a square around the calibrated physical center, with player position fixed to the square center, or
   - the selected physical region, then detect the player from `recognizer.extract_player()` through `tracker.detect_player()`.
3. If player detection fails in region mode, reuse `last_player_local_pos`; if that is unavailable, fall back to the image center.
4. Call `recognizer.extract_combined(img, player_pos=player_pos)` to get registration/wall/fog masks.
5. Get raw grayscale through `recognizer.get_raw_gray(img)`.
6. Call `stitcher.add_frame(img, combined, wall_mask, fog_mask, raw_gray=raw_gray, player_pos=player_pos)`.
7. Store last capture size and player-local position.
8. Render preprocessed capture and global map.
9. Update statistics from `stitcher.get_statistics()`.

Existing helper depth:

- `mapping/save_load.py` is a useful IO module. It derives the project root from the caller file, builds `map_data` paths, reads/writes JSON, and builds mapping config from `app_context`.
- `mapping/map_renderer.py` is a useful presentation adapter. It converts OpenCV BGR images to `QPixmap`, unpacks enhanced-map crop results, draws route polyline, current position, and field-of-view rectangle.
- `mapping/params_adapter.py` is shallow. It reduces clutter, but still depends on widget objects and mutates recognizer/stitcher directly.

Target flow:

```text
MappingWidget
  ├─ MappingSession.start/stop/tick()
  │    ├─ CaptureSource adapter
  │    ├─ PlayerLocalizer adapter
  │    ├─ Recognizer facade
  │    └─ MapStitcher facade
  ├─ MappingPresenter.render_capture/render_global_map()
  ├─ MappingConfigStore load/save
  └─ emits UI commands: select region, select center, open dialogs, save map
```

Refactor order:

1. Extract `MappingSession.tick()` around `capture_and_process()` and return a DTO containing current image, combined mask, player position, capture size, and stitcher position.
2. Extract `MappingConfigStore` by deepening `mapping/save_load.py`; remove `__file__` from call sites once the project root is injected by `AppContext`.
3. Extract `MappingPresenter` around `update_displays()` and `map_renderer.py`.
4. Replace direct recognizer/stitcher mutation in `params_adapter.py` with typed parameter DTOs or command methods.
5. Only then split UI construction into section builders.

Concrete behavior risk:

- `ScalableMapWidget` declares `pixel_clicked = Signal(int, int)`, and `MappingWidget.create_display_panel()` connects it to `on_map_click()`, but `ScalableMapWidget` does not emit `pixel_clicked` in its mouse handlers. The "click to set navigation point" behavior should be verified and either implemented by coordinate mapping or removed from this mapping view.

### Generic Widget Helpers

`ClickableImageLabel`:

- Converts displayed pixmap coordinates back into original image coordinates.
- Accounts for centered pixmap offsets and display/original scale.
- Emits `pixel_clicked(original_x, original_y)` and `wheel_zoom(delta)`.
- Current user: color picker.

`ScalableMapWidget`:

- Owns scroll area, zoom-in/out/reset, fit-to-view, drag-to-pan, and Ctrl+wheel zoom.
- Does not currently map click coordinates to image coordinates despite declaring `pixel_clicked`.

`CollapsibleMapGroup`:

- Wraps `ScalableMapWidget` in a checkable group with zoom buttons.
- Good enough as a presentational widget; no core logic should move into it.

## Round Status

Status: partial. Mapping runtime, helper modules, and relevant widget helpers have been read. UI layout details are sufficient for refactor planning; source changes still need tests around capture tick and map click behavior.

Next navigation-mode read should focus on method grouping, not line-by-line behavior yet.
