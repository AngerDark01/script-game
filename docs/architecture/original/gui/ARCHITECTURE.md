# GUI Architecture

## System Role

`gui` owns PySide6 widgets, user workflows, timers, dialogs, overlays, and configuration editing. It should coordinate core systems but should not contain reusable algorithms.

## Current Module Map

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `app_context.py` | Shared service composition for capture, stitcher, tracker, pathfinder, recognizer, and monitor state. | Candidate application composition root, but currently behaves like a mutable object bag with empty config hooks. |
| `main_window.py` | Top-level window, mode buttons, stacked pages, and mode switching. | Mostly thin; should avoid timer internals during shutdown. |
| `navigation_params.py` | Navigation config and runtime parameter models. | Stable config contract candidate; may belong near core if GUI-free. |
| `modes/` | Mapping/navigation mode screens and helpers. | Needs stronger controller/runtime/presenter split. |
| `dialogs/` | Parameter and tool dialogs. | Several large files need extraction into form sections and adapters. |
| `selection/` | Overlay tools for region/center selection. | GUI adapter components. |
| `widgets/` | Reusable PySide widgets. | Consolidated active widget package; old `widgets_fixed.py` backup has been removed. |

## Target GUI Split

```text
gui
├── composition
│   └── app_context / service creation
├── shell
│   └── main window and mode switching
├── modes
│   ├── mapping mode
│   └── navigation mode
├── dialogs
│   ├── parameter forms
│   ├── event manager
│   └── diagnostic tools
├── overlays
│   ├── screen selection
│   ├── map route overlay
│   └── event overlay
└── widgets
    └── reusable PySide components
```

## Main Refactor Principle

GUI modules should translate user actions and render state. Core modules should own decisions. If a PySide method contains route selection, event scheduling, path planning, or input policy, that behavior is probably in the wrong place.

## Verified Startup Ownership

`MainWindow.__init__()` currently:

1. Sets title and geometry.
2. Creates `AppContext(self)`.
3. Calls `setup_ui()`.
4. Adds `WindowStaysOnTopHint`.

`setup_ui()` currently:

1. Creates mapping/navigation mode buttons.
2. Creates `QStackedWidget`.
3. Instantiates `MappingWidget(self.app_context, self)`.
4. Instantiates `NavigationModeWidget(self.app_context, self)`.
5. Defaults to mapping mode.

`switch_mode(index)` only switches the stacked widget and refreshes the navigation map list when entering navigation mode.

`closeEvent()` directly stops `mapping_widget.capture_timer` and calls `nav_widget.toggle_navigation()`. This is a fragile shutdown interface because the shell knows timer implementation details and `toggle_navigation()` is a command toggle rather than an idempotent stop method.

## Composition Root Recommendation

Make application composition explicit:

```text
gui/app.py
  create_qapplication(argv)
  create_main_window(app_services)

gui/app_context.py
  create_core_services(config)
  AppContext dataclass/QObject with explicit fields

gui/main_window.py
  only shell, mode switching, and shutdown delegation
```

Preferred shutdown interface:

```text
MappingWidget.stop_runtime()
NavigationModeWidget.stop_runtime()
```

This lets `MainWindow.closeEvent()` stop workflows without knowing timers or whether navigation is currently running.

## Round Status

Status: partial. Startup ownership files were read; mode internals are still pending.

Next read targets:

- `gui/modes/navigation_mode.py` method grouping.
- `gui/modes/mapping_widget.py` method grouping.
