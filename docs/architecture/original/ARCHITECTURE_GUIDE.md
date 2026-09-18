# Architecture Guide

This guide is the top-level index for the engineering refactor reading pass. It is intentionally separate from `CODEBASE.md`: `CODEBASE.md` describes the current codebase, while this guide tracks reusable module boundaries, extension seams, large-file split candidates, and staged refactor plans.

## Reading Direction

Start here, then drill into the module-owned documents near the code they describe:

- [core/ARCHITECTURE.md](core/ARCHITECTURE.md) - Core systems overview: mapping, localization, route planning, movement input, and shared models.
- [core/navigation_tasks/ARCHITECTURE.md](core/navigation_tasks/ARCHITECTURE.md) - Unified navigation task system and its interaction with events.
- [core/events/ARCHITECTURE.md](core/events/ARCHITECTURE.md) - Event system lifecycle, reusable hooks, memory, scheduling, and runner seams.
- [core/events/types/portal/ARCHITECTURE.md](core/events/types/portal/ARCHITECTURE.md) - Portal event package as the first concrete event adapter.
- [gui/ARCHITECTURE.md](gui/ARCHITECTURE.md) - GUI shell, shared app context, dialogs, and mode ownership.
- [gui/modes/ARCHITECTURE.md](gui/modes/ARCHITECTURE.md) - Mapping and navigation mode split strategy.
- [gui/modes/navigation/ARCHITECTURE.md](gui/modes/navigation/ARCHITECTURE.md) - Detailed split map for `navigation_mode.py`.
- [gui/dialogs/ARCHITECTURE.md](gui/dialogs/ARCHITECTURE.md) - Parameter, event, advanced settings, and color picker dialog responsibilities.
- [utils/ARCHITECTURE.md](utils/ARCHITECTURE.md) - Probe scripts and diagnostics as reusable verification tools.
- [tests/ARCHITECTURE.md](tests/ARCHITECTURE.md) - Existing test contracts and refactor safety net.

Process and coverage live in [ARCHITECTURE_ITERATION_LOG.md](ARCHITECTURE_ITERATION_LOG.md).

## Target Abstraction Levels

The refactor plan will use these levels consistently:

- System - a full runtime capability with ownership of a user-visible workflow or long-lived state.
- Module - a package or file group with a stable interface and hidden implementation.
- Component - a class/function group reused inside one or more modules.
- Adapter - concrete integration with GUI, filesystem, Windows input, OpenCV, or a concrete event type.
- Hook - lifecycle callback or extension point that lets new behavior join without editing the core loop.

## First-Pass System Map

```text
┌──────────────────────────────┐
│ PySide6 Desktop Application  │
└──────────────┬───────────────┘
               │ owns UI state and timers
               ▼
┌──────────────────────────────┐
│ GUI Modes                    │
│ Mapping / Navigation         │
└───────┬──────────────┬───────┘
        │              │
        ▼              ▼
┌──────────────┐   ┌─────────────────────┐
│ Mapping Core │   │ Navigation Runtime  │
│ stitch map   │   │ localize + schedule │
└──────┬───────┘   └──────────┬──────────┘
       │                      │
       ▼                      ▼
┌──────────────┐   ┌─────────────────────┐
│ Map Package  │   │ Task / Event System │
│ npz/config   │   │ route/event/exit    │
└──────────────┘   └──────────┬──────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Input System │
                       │ click/key    │
                       └──────────────┘
```

## Confirmed Refactor Themes

These themes are based on the current reading pass and should guide the first implementation plan.

0. Startup should be split into process bootstrap and Qt application composition. `main.py` currently owns UTF-8/log redirection, console hiding, DPI awareness, UAC relaunch, single-instance locking, old-window detection, and QApplication startup.
1. `gui/modes/navigation_mode.py` should become a thin coordinator. Runtime loop, route editing, event dialog wiring, overlay rendering, config application, and input execution should become separate modules with explicit interfaces.
2. The event system should expose lifecycle hooks through a hook bus/listener, not by adding many optional methods to `EventDefinition`.
3. `core/navigation_tasks` is close to a reusable orchestration system. It should keep producing intents and avoid owning click/key side effects.
4. Movement input should stay behind `MotionController` and a future command-sink interface. Windows APIs, `pydirectinput`, focus behavior, and click diagnostics should not leak into navigation logic.
5. Mapping and localization share image-recognition and displacement concepts, but their stateful runtime facades should stay separate.
6. Probe scripts should remain verification adapters for production algorithms and integrations.
7. Not every module needs splitting. Route/pathfinding modules are already cohesive; grouping them later under `core/routing/` is enough.

## Composition Ownership

Verified current startup chain:

```text
main.py
  ├── configure_runtime_output()
  ├── hide_console_if_not_debugging()
  ├── set_process_dpi_awareness()
  ├── relaunch_as_admin()
  ├── acquire_single_instance_lock()
  ├── has_existing_main_window()
  └── main()
        ├── QApplication(sys.argv)
        └── MainWindow()
              ├── AppContext()
              │     ├── ScreenCapture()
              │     ├── HSVRecognizer()
              │     ├── MapStitcher(canvas_size=5000)
              │     ├── PlayerTracker()
              │     └── PathFinder()
              ├── MappingWidget(app_context, main_window)
              └── NavigationModeWidget(app_context, main_window)
```

Refactor direction:

- `main.py` should become a short script that delegates process setup to a bootstrap module and GUI creation to an application module.
- `AppContext` should become the explicit composition root for shared core modules, or be renamed/split if it remains only a passive object bag.
- Mode widgets should receive only the interfaces they need over time, not the whole mutable context.

## Refactor Roadmap

### Phase 0 - Test Guardrails

Do this before large source edits.

- Add `anchor_path.py` tests for ordered-anchor filtering, reached-anchor skipping, direct fallback, and probe fallback.
- Add `EventCoordinator` tests with fake definition/detector/handler/memory timing.
- Add `PortalEventHandler` phase/state tests with fake ticks and fake captures.
- Add `MappingSession.tick()` tests using fake capture, recognizer, tracker, and stitcher.
- Add `NavParametersDialog` binding tests only after field specs are extracted into non-widget data.
- Add `ScalableMapWidget` click-coordinate test if mapping map clicks remain supported.

### Phase 1 - Low-Risk Deep Modules

These have existing tests or are mostly pure.

- Shared `estimate_phase_displacement()` has been extracted to `core/phase_displacement.py`; next low-risk core extraction is `WeightedMapMerger`.
- Extract `WeightedMapMerger` from `MapStitcher._merge_frame_weighted()`.
- Group route modules into `core/routing/` only if imports are already being touched.
- Extract `MotionController` movement mapping and bottom-click guard into pure helpers.
- Done: `NavParametersDialog` click-radius math has been extracted to `gui/dialogs/nav_params/screen_estimator.py`.

### Phase 2 - Runtime Facades

These reduce the 1000+ line coordination files without changing algorithms.

- Add idempotent `start_runtime()` / `stop_runtime()` to navigation mode.
- Extract `NavigationIntentExecutor` from `NavigationModeWidget._execute_navigation_intent()`.
- Extract `MappingSession` from `MappingWidget.capture_and_process()`.
- Extract `NavigationConfigApplier` for applying `NavConfig` to `NavigationCore`, `PathFinder`, `MotionController`, and task controllers.
- Extract `EventPanelAdapter` from navigation mode event dialog wiring.

### Phase 3 - Event Hooks and Packages

Add extension points after lifecycle tests exist.

- Introduce observational `EventHookBus`.
- Emit hooks for observe start/end, detector candidates, task selected, handler action, task completed/failed/ignored.
- Keep hooks out of portal-specific code unless a portal debug hook is explicitly needed.
- Move portal defaults out of `core/events/config.py` toward event definitions/registry.
- Convert `PortalEventHandler` string state into a phase enum and runtime dataclass.

### Phase 4 - GUI Surface Cleanup

These are valuable but should follow runtime extraction.

- Convert navigation parameters to declarative field specs and generic config binding.
- Keep `EventManagerDialog` mostly intact as the model for schema-driven forms.
- Extract color picker preview mask/stats and path-controlled debug output.
- Color picker debug output path is explicit through `gui/dialogs/color_picker/debug_output.py` and is now gated by `MINIMAP_COLOR_PICKER_DEBUG`.
- Advanced-settings JSON snapshots now go through `gui/dialogs/advanced_settings/file_io.py` into `configs/advanced_settings/`, and preset values now live in `advanced_settings/presets.py`; direct parent mutation and tab extraction remain.
- Stop `AdvancedSettingsDialog` from directly mutating parent recognizer/stitcher if it remains active.
- Fix or remove mapping global-map click behavior depending on whether `ScalableMapWidget.pixel_clicked` is intended.

### Phase 5 - Package Organization

Only move files once interfaces are stable.

```text
core/
├── mapping/
├── localization/
├── recognition/
├── routing/
├── input/
├── navigation_tasks/
└── events/

gui/
├── app/
├── modes/
│   ├── mapping/
│   └── navigation/
└── dialogs/
```

## Cross-Module Rules

- Core modules must not import PySide widgets.
- Event packages must not execute mouse/keyboard input directly; they return actions/intents.
- Navigation task modules should emit `NavigationIntent`, not call `MotionController`.
- GUI modules may adapt signals, timers, and widgets to core facades.
- Probes may write files and print diagnostics, but detector/planner/input algorithms should live in production modules.
