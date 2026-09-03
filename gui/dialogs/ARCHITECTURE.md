# GUI Dialogs Architecture

## System Role

`gui/dialogs` owns interactive configuration and diagnostic UI. Dialogs should adapt user input to typed configuration objects or command requests. They should not own core algorithms.

## Current Large Files

| File | Lines | Refactor concern |
| --- | ---: | --- |
| `nav_params_dialog.py` | 771 | Many parameter sections and widget mapping likely live in one dialog class. |
| `advanced_settings_dialog.py` | 639 | Tab construction, file dialogs, presets, and apply behavior may be mixed, though parameter IO now has helpers. |
| `color_picker_dialog.py` | 395 | UI, sampling, preview, HSV math, and debug output may be mixed, though helper modules already exist. |
| `event_manager_dialog.py` | 337 | Event list, task table, schema-driven parameter form, save/test/reset actions. |

## Target Dialog Split

### Navigation Parameters

```text
nav_params_dialog.py             # dialog shell, tabs, save/apply signals
nav_params/field_specs.py        # field metadata: label, help, range, type, config path
nav_params/widget_factory.py     # QSpinBox/QDoubleSpinBox/QCheckBox/QLineEdit creation from specs
nav_params/config_binding.py     # NavConfig <-> widgets, immutable dataclass replace
nav_params/screen_estimator.py   # click radius estimates from calibrated center and screen bounds
nav_params/sections.py           # optional tab/section assembly after field specs are stable
```

Verified current behavior:

- `NavParametersDialog._init_ui()` builds six tabs: positioning, recognition, movement, path, event, and map/debug.
- `_connect_signals()` owns a large widget map from control instance to `(sub_config_name, attr_name)`.
- `_update_config_value()` updates `NavConfig` or nested config dataclasses with `dataclasses.replace()` and emits `parameters_changed`.
- `_update_config_text_value()` parses HSV list text through `ast.literal_eval()` and ignores incomplete/invalid text without emitting.
- `set_config_to_ui()` copies `NavConfig` values into widgets while blocking child widget signals with `QSignalBlocker`.
- `_auto_estimate_click_radius()` keeps Qt screen-bound lookup in the dialog and delegates radius math to `nav_params/screen_estimator.py`.
- Legacy `NavPreferences.k_ratio/y_bias` still round-trip through config serialization, but they are no longer visible or editable in the dialog because current motion mapping does not use them.

Extraction order:

1. Done: `screen_estimator.estimate_click_radii(center, screen_bounds)` is now the pure radius policy. Qt screen enumeration stays in the dialog adapter and physical bounds are passed into the helper for tests.
2. Extract `config_binding.py` around the existing widget maps. Keep exact widget names at first to avoid layout churn.
3. Convert the widget map into declarative `field_specs.py`, one section at a time. Start with path/event parameters because they are newer and less tied to HSV text parsing.
4. Extract tab/section builders only after binding tests exist. Layout extraction before binding extraction would mostly move complexity sideways.

Target interaction:

```text
NavParametersDialog
  ├─ field_specs grouped by section
  ├─ WidgetBinder writes NavConfig -> widgets
  ├─ WidgetBinder reads widget changes -> NavConfig
  ├─ ScreenClickEstimator returns suggested radii
  └─ emits parameters_changed/save_requested/save_default_requested
```

### Advanced Settings

Existing helper modules:

```text
advanced_settings_dialog.py      # shell and buttons
advanced_settings/params_adapter.py
advanced_settings/file_io.py     # JSON load/save target directory and errors
advanced_settings/presets.py     # preset names and widget-value data
```

Potential extra modules:

```text
advanced_settings/tabs.py        # tab construction
```

Verified current behavior:

- The dialog still works with a plain `dict` rather than `NavConfig`/`RecognizerParams`.
- It reaches into `parent.recognizer` and `parent.stitcher` and calls `set_params()` directly.
- `save_current_params()` delegates to `advanced_settings/file_io.py` and writes `params_<safe_name>_<timestamp>.json` into `configs/advanced_settings/`.
- `load_params_from_file()` opens from `configs/advanced_settings/`, validates a JSON object with a `parameters` object, and stores it in `temp_loaded_params`.
- `params_adapter.py` centralizes widget reads/writes and applies preset data to widgets, but it remains a shallow adapter because it depends on dialog attribute names.
- `file_io.py` centralizes filename sanitization, directory creation, JSON payload shape, validation, and display formatting.
- `presets.py` centralizes preset option order and widget-value dictionaries for non-GUI tests.

Refactor guidance:

- Treat this as a legacy tuning surface. Do not expand it for new navigation/event settings.
- If it must stay, give it explicit command signals (`params_apply_requested`, `preset_apply_requested`) instead of direct parent mutation.
- Keep JSON file IO inside `advanced_settings/file_io.py`; do not reintroduce current-working-directory writes.
- Continue reducing dialog-attribute coupling in `params_adapter.py`; preset values are now data-only.

### Color Picker

Existing helper modules:

- `color_picker/hsv_ranges.py`
- `color_picker/image_renderer.py`

Potential extra modules:

```text
color_picker_dialog.py          # shell and interactions
color_picker/preview.py          # mask/preview/debug rendering
color_picker/debug_output.py     # png/txt output
```

Verified current behavior:

- `ColorPickerDialog` constructs an `HSVRecognizer`, applies optional recognizer params, preprocesses the screenshot, and stores original/sample state.
- `hsv_ranges.py` is pure HSV math: BGR->HSV conversion, point sampling, tolerance-based range calculation, and mean saturation.
- `image_renderer.py` is a Qt rendering adapter: OpenCV image to pixmap and fixed-size sample markers.
- `calculate_hsv_ranges()` samples wall/player points and recommends disabling saturation filtering when sampled wall saturation is high.
- `update_preview()` still combines HSV mask generation, morphology, and preview rendering. Debug artifact writes are opt-in through `MINIMAP_COLOR_PICKER_DEBUG`.

Refactor guidance:

- Extract `build_wall_preview_mask(image, hsv_range)` returning mask plus stats.
- Keep `write_wall_preview_debug(...)` path-controlled and opt-in; do not reintroduce unconditional preview artifact writes.
- Keep `ColorPickerDialog` as interaction state and result packaging: selected points, current mode, zoom, accepted ranges.

Current artifact status:

- `preview_result_*.png`, `preview_before_morph_*.png`, and `preview_log_*.txt` are written through `color_picker/debug_output.py` to `debug/color_picker/` only when `MINIMAP_COLOR_PICKER_DEBUG` is enabled.

### Event Manager

Verified current behavior:

- `EventManagerDialog` is already close to the desired schema-driven pattern.
- `build_tui_event_options(registry, config)` supplies event rows, display names, descriptions, current values, and editable parameter schema.
- `_create_param_widget()` maps schema types to Qt controls: float, int, bool, choice, and read-only label fallback.
- It emits command-style signals for save, test portal, and reset portal.
- It reads live task rows from `coordinator.tasks()` and displays event task state, confidence, map coordinate, attempts, and last-seen timestamp.

Refactor guidance:

- Use this as the model for future settings surfaces: schema defines fields; dialog renders fields.
- Extract generic schema form rendering only when a second dialog uses it. Until then, `EventManagerDialog` is deep enough.
- Decide one config mutation style. `EventManagerDialog` mutates `config` in place, while `NavParametersDialog` emits a replaced dataclass. Prefer immutable updates for typed dataclasses and in-place updates only for mutable dict-backed config.

## Dialog-to-System Interaction Rules

- Dialogs should emit typed signals or command signals.
- Dialogs should not call `recognizer.set_params()`, `stitcher.set_params()`, movement methods, or event handlers directly.
- Dialogs may render live state from read-only query methods such as `coordinator.tasks()`.
- Dialog field definitions should live near the dialog package, but domain validation should live with `NavConfig`, event config schemas, or core parameter dataclasses.

## Highest-Value Split Order

1. `nav_params_dialog.py`: extract click radius estimator and config/widget binding.
2. `color_picker_dialog.py`: extract preview mask/stats and optional debug gating.
3. `advanced_settings_dialog.py`: stop direct parent mutation and split presets/tabs if this dialog remains active.
4. `EventManagerDialog`: leave mostly intact; revisit only when generic schema forms are needed elsewhere.

## Round Status

Status: partial. Main dialog files and current helper modules have been read. Deep line-by-line UI layout inventory is not necessary before source refactoring, but binding and side-effect behavior is now mapped.
