# Architecture Iteration Log

This log follows the iterative reading discipline from the codebase workflow: declare scope before reading, read a small set of files, then record findings and the next round.

## [Round 1] 2026-05-26 - Structure, Scale, and Documentation Skeleton

### A. Round Goal

Target files and sources:

- `CODEBASE.md` - coarse read only, used as current-state index.
- `README.md` and `requirements.txt` - confirm project purpose and stack.
- Python file list and line counts - identify large-file split candidates.
- Existing docs search - avoid overwriting existing architecture artifacts.

Questions for this round:

- What are the top-level systems?
- Which files are immediately too large or too mixed in responsibility?
- Where should module-owned documentation live?
- Which modules should be read in Round 2?

### C. Findings

Key findings:

- (verified) The application is a PySide6 + OpenCV desktop tool for minimap stitching, navigation localization, path planning, event handling, and real input execution.
- (verified) Existing `CODEBASE.md` is useful current-state material, but it is a single large encyclopedia. The new documentation should be module-owned and refactor-oriented.
- (verified) The largest file is `gui/modes/navigation_mode.py` at 1525 lines. It is the first large-file split candidate because it mixes GUI construction, map loading, route editing, navigation loop, event integration, overlay rendering, and input-window behavior.
- (verified) Other high-friction files by size include `gui/dialogs/nav_params_dialog.py` at 771 lines, `core/stitcher_core.py` at 647 lines, `gui/dialogs/advanced_settings_dialog.py` at 629 lines, `core/navigation_core.py` at 611 lines, and `core/navigation_tasks/controller.py` at 567 lines.
- (verified) The codebase already has partial modularization around `core/events`, `core/navigation_tasks`, `gui/modes/navigation`, and `gui/modes/mapping`; the refactor should deepen these modules rather than invent unrelated structure.
- (verified) Working tree has existing modified source files. This architecture pass will avoid source edits unless explicitly requested.

Updated documents:

- `ARCHITECTURE_GUIDE.md`
- `core/ARCHITECTURE.md`
- `core/navigation_tasks/ARCHITECTURE.md`
- `core/events/ARCHITECTURE.md`
- `core/events/types/portal/ARCHITECTURE.md`
- `gui/ARCHITECTURE.md`
- `gui/modes/ARCHITECTURE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `utils/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| Project structure | PENDING | shallow | 1 | File list, existing docs, requirements, and current CODEBASE index reviewed. |
| Entry/runtime startup | PENDING | PENDING | 0 | Planned for Round 2 with `main.py`, `gui/app_context.py`, `gui/main_window.py`. |
| Navigation mode | PENDING | shallow | 1 | Only line count and existing CODEBASE summary reviewed; function bodies not yet read. |
| Mapping core | PENDING | shallow | 1 | Identified as system; algorithm details not yet read. |
| Navigation tasks | PENDING | shallow | 1 | Identified as reusable orchestration candidate; function bodies not yet read. |
| Event system | PENDING | shallow | 1 | Identified hook candidate; function bodies not yet read. |
| Portal event | PENDING | shallow | 1 | Identified as first concrete event adapter; function bodies not yet read. |
| GUI dialogs | PENDING | shallow | 1 | Large files identified; dialog behavior not yet read. |
| Probe scripts | PENDING | shallow | 1 | Identified as diagnostics/verification layer; not yet read. |
| Tests | PENDING | shallow | 1 | Test files listed; assertions not yet read. |

Next round plan:

- Read startup and ownership path: `main.py`, `gui/app_context.py`, `gui/main_window.py`.
- Produce concrete startup/system ownership notes in `gui/ARCHITECTURE.md` and `core/ARCHITECTURE.md`.
- Decide whether `AppContext` is deep enough or should become a formal application composition module.

## [Round 2] 2026-05-26 - Startup and Composition Ownership

### A. Round Goal

Target files:

- `main.py` - process setup, runtime output, admin relaunch, single-instance guard, QApplication startup.
- `gui/app_context.py` - shared core object composition.
- `gui/main_window.py` - top-level GUI ownership and mode switching.

Questions for this round:

- Where is the true application composition root?
- Which core systems are constructed eagerly and shared?
- Does startup logic mix platform setup, logging, process control, and GUI boot enough to need extraction?
- Does the GUI shell own mode lifecycle cleanly?

### C. Findings

Key findings:

- (verified) `main.py` owns several process/platform responsibilities before GUI creation: UTF-8/log redirection, optional console hiding, DPI awareness, UAC relaunch, python/pythonw choice, single-instance mutex, old-window detection, and QApplication startup.
- (verified) The current startup chain is `main.py -> QApplication -> MainWindow -> AppContext -> core service instances -> MappingWidget/NavigationModeWidget`.
- (verified) `AppContext` constructs `ScreenCapture`, `HSVRecognizer`, `MapStitcher(canvas_size=5000)`, `PlayerTracker`, and `PathFinder` eagerly, and also stores mutable monitor state.
- (verified) `AppContext.load_global_config()` and `save_global_config()` are placeholders, so configuration ownership is currently not centralized there.
- (verified) `MainWindow` is mostly a thin shell, but `closeEvent()` reaches into `mapping_widget.capture_timer` and calls `nav_widget.toggle_navigation()`. That is a weak shutdown interface because the shell knows implementation details and uses a toggle instead of an idempotent stop command.
- (inferred) `main.py` should be split before major GUI refactors so process bootstrap does not obscure application composition.

Updated documents:

- `ARCHITECTURE_GUIDE.md` - added verified composition ownership.
- `gui/ARCHITECTURE.md` - added startup ownership and shutdown recommendation.
- `core/ARCHITECTURE.md` - added package export/composition note.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `main.py` | PENDING | partial | 1 | Read full file; process bootstrap responsibilities identified, but no refactor patch planned yet. |
| `gui/app_context.py` | PENDING | partial | 1 | Read full file; eager core service composition and placeholder config hooks identified. |
| `gui/main_window.py` | PENDING | partial | 1 | Read full file; shell mostly thin, shutdown interface is brittle. |
| `core/__init__.py` | PENDING | partial | 1 | Read full file; current top-level core exports identified. |
| `gui/__init__.py` | PENDING | partial | 1 | Read full file; exports `MainWindow` only. |

Next round plan:

- Read method grouping in `gui/modes/navigation_mode.py` without trying to document every line yet.
- Produce a concrete split map for `navigation_mode.py` by responsibility and extraction order.
- Confirm which helper modules already cover parts of the split and which responsibilities remain in the 1525-line widget.

## [Round 3] 2026-05-26 - Navigation Mode Large-File Split Map

### A. Round Goal

Target file:

- `gui/modes/navigation_mode.py` - method grouping and responsibility boundaries.

Supporting files if needed:

- `gui/modes/navigation/map_runtime.py`
- `gui/modes/navigation/route_overlay.py`
- `gui/modes/navigation/event_overlay.py`
- `gui/modes/navigation/viewport_overlay.py`
- `gui/modes/navigation/event_adapter.py`

Questions for this round:

- Which responsibilities are still inside the 1525-line widget?
- Which responsibilities already have helper modules?
- What is the safest extraction order?
- What public methods should remain on `NavigationModeWidget` after extraction?

### C. Findings

Key findings:

- (verified) `gui/modes/navigation_mode.py` is 1525 lines by `Measure-Object -Line`.
- (verified) The widget still owns QWidget construction, route editing, map loading, config application, event dialog wiring, event system initialization, manual portal test control, map rendering, viewport overlay updates, navigation timer control, runtime tick logic, and real input intent execution.
- (verified) Existing helper modules already cover some pure helper behavior: `map_runtime.py` for map/config/capture geometry, `route_overlay.py` for route drawing, `event_overlay.py` for event drawing, `viewport_overlay.py` for rectangle geometry, and `event_adapter.py` for event registry/tick/status helpers.
- (verified) `_navigation_loop_unified()` is the highest coupling method: it captures frames, detects player-local position, localizes globally, observes events, refreshes event dialog tasks, calls `NavigationTaskController.update()`, updates player/viewport overlays, formats status text, forces relocalization, executes navigation intents, and handles terminal arrival/failure.
- (verified) `_execute_navigation_intent()` is a good extraction target because it is the only place that translates `NavigationIntentType` into `MotionController` calls and controller click recording.
- (verified) `_set_game_input_window_mode()` is a small, low-risk GUI-specific extraction target because it only mutates main-window topmost/lower behavior.
- (verified) Route editing has a clean command cluster around `RouteManager` and scene-click conversion; it can become `route_editor.py`.
- (inferred) The safest first source change later is adding `start_runtime()` / `stop_runtime()` methods before extracting modules, because current `MainWindow.closeEvent()` calls `toggle_navigation()` and can accidentally start navigation if state and button are inconsistent.

Updated documents:

- `gui/modes/navigation/ARCHITECTURE.md` - detailed split map and extraction order for `navigation_mode.py`.
- `gui/modes/ARCHITECTURE.md` - linked detailed split map.
- `ARCHITECTURE_GUIDE.md` - linked detailed split map.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/modes/navigation_mode.py` | shallow | partial | 1 | Method groups and major branches read; branch-level algorithm details still pending. |
| `gui/modes/navigation/map_runtime.py` | shallow | partial | 1 | Full file read; already good helper for map/config/capture geometry. |
| `gui/modes/navigation/event_adapter.py` | shallow | partial | 1 | Full file read; event registry/tick/status helpers identified. |
| `gui/modes/navigation/route_overlay.py` | shallow | partial | 1 | Full file read; route drawing helper identified. |
| `gui/modes/navigation/event_overlay.py` | shallow | partial | 1 | Full file read; event overlay drawing helper identified. |
| `gui/modes/navigation/viewport_overlay.py` | shallow | partial | 1 | Full file read; viewport rectangle geometry helper identified. |

Next round plan:

- Read `core/navigation_tasks/models.py`, `controller.py`, and `movement_executor.py`.
- Produce a system-level interface proposal for `NavigationTaskController` and identify which GUI responsibilities can move into navigation-task adapters.
- Check whether event hooks belong in `core/events`, `core/navigation_tasks`, or a bridge between them.

## [Round 4] 2026-05-26 - Unified Navigation Task System Interface

### A. Round Goal

Target files:

- `core/navigation_tasks/models.py`
- `core/navigation_tasks/controller.py`
- `core/navigation_tasks/movement_executor.py`
- `core/navigation_tasks/scheduler.py`
- `core/navigation_tasks/task_builder.py`
- `core/navigation_tasks/route_context.py`

Questions for this round:

- What is the real public interface of the unified navigation task system?
- Which parts are reusable core modules and which are GUI/event adapters?
- Where should event hooks connect without coupling event packages to navigation UI?
- Which responsibilities in `controller.py` should be split first?

### C. Findings

Key findings:

- (verified) `models.py` provides stable DTOs and enums: `NavigationTaskKind`, `NavigationTaskState`, `NavigationIntentType`, `RouteProjection`, `RouteAnchor`, `NavigationTask`, `MovementStep`, and `NavigationIntent`.
- (verified) `NavigationTaskController.update()` has a wide keyword-only interface called directly from the GUI runtime loop. It requires localization, route, event coordinator/tick, map layers, pathfinder, timing, manual event mode, and frame registration.
- (verified) `NavigationTaskController.update()` mixes multiple phases: route reload, active-state guard, localization filtering, coordinate diagnostics, relocalization recovery, required-point completion, task building, task scheduling, task transition handling, event task running, static task running, and intent creation.
- (verified) `NavigationTaskBuilder`, `NavigationTaskScheduler`, `RouteContext`, `MovementExecutor`, and `CoordinateDiagnostics` are already reasonably deep modules with distinct responsibilities.
- (verified) `EventApproachController` is a navigation-layer gate before an event handler can trigger; it uses visibility/settling/movement policy and emits `NavigationIntent`. It should not move into a concrete event package, but event packages may later provide approach preferences.
- (verified) `MovementExecutor` centralizes A*/anchor/fallback planning, lookahead subgoal selection, click throttling, exact path-goal click decisions, stuck detection, and recovery probes. It is a strong reusable component and should stay under navigation tasks or route movement.
- (inferred) The next controller refactor should introduce `NavigationUpdateContext` rather than immediately splitting behavior. Grouping parameters first will shrink the GUI dependency surface and make tests easier.
- (inferred) Event hooks should be split by layer: detection/handler hooks in `core/events`, route/task hooks in `core/navigation_tasks`, and cross-system translation hooks in an event-task runner adapter.

Updated documents:

- `core/navigation_tasks/ARCHITECTURE.md` - expanded with verified interface, controller algorithm, split plan, update context proposal, and hook placement.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/navigation_tasks/models.py` | shallow | partial | 1 | Full file read; DTO contract identified. |
| `core/navigation_tasks/controller.py` | shallow | partial | 1 | Full file read; phase-level algorithm and split points identified. |
| `core/navigation_tasks/movement_executor.py` | shallow | partial | 1 | Full file read; reusable movement component identified. |
| `core/navigation_tasks/scheduler.py` | shallow | partial | 1 | Full file read; route/event selection policy identified. |
| `core/navigation_tasks/task_builder.py` | shallow | partial | 1 | Full file read; unified task composition identified. |
| `core/navigation_tasks/route_context.py` | shallow | partial | 1 | Full file read; route projection/corridor anchor behavior identified. |
| `core/navigation_tasks/event_approach.py` | shallow | partial | 1 | Full file read; navigation-layer event approach gate identified. |
| `core/navigation_tasks/coordinate_diagnostics.py` | shallow | partial | 1 | Full file read; diagnostics/relocalization request role identified. |

Next round plan:

- Read `core/events/models.py`, `coordinator.py`, `memory.py`, `monitor.py`, `runner.py`, and `scheduler.py`.
- Define event system lifecycle hooks and decide what should be core hook, debug hook, GUI adapter, or event package adapter.
- Then read portal event package as the first concrete event package implementation.

## [Round 5] 2026-05-26 - Event System Lifecycle and Hooks

### A. Round Goal

Target files:

- `core/events/models.py`
- `core/events/coordinator.py`
- `core/events/monitor.py`
- `core/events/memory.py`
- `core/events/scheduler.py`
- `core/events/runner.py`
- `core/events/registry.py`
- `core/events/config.py`
- `core/events/base/*.py`

Questions for this round:

- What is the real event lifecycle from detection to action?
- Which interfaces are already generic enough for reusable events?
- Where should hooks live?
- Which current responsibilities should be adapters: debug logging, GUI overlay, config IO, capture/window access?

### C. Findings

Key findings:

- (verified) Event lifecycle is two-phase. `EventCoordinator.observe()` detects/stabilizes/merges event tasks but does not execute handlers. `EventCoordinator.run_task()` executes a selected task only when navigation chooses it.
- (verified) `EventDefinition`, `EventDetector`, and `EventHandler` are minimal and useful event package seams.
- (verified) `EventMemory` owns task lifecycle policy: dedupe, confirm frames, cooldown, retry, ignore, teleport session completion, and nearby suppression. It should remain deep and tested before splitting.
- (verified) `EventRunner` is the seam from generic event runtime to concrete handler actions. It starts handlers, updates them, applies complete/fail behavior to memory, and returns `EventAction`.
- (verified) `EventMonitor` lazily creates one detector per enabled event definition and caches detectors by event type.
- (verified) `overlay_models.py` is a core-safe DTO adapter; PySide rendering remains in `gui/modes/navigation/event_overlay.py`.
- (verified) `capture_provider.py` is already an adapter boundary for handlers needing minimap or full game-view captures.
- (verified) `core/events/config.py` currently embeds portal-specific defaults in the event core. This is a coupling point; defaults should eventually come from `EventDefinition.default_config()` through the registry.
- (inferred) Hooks should be implemented as an injected hook bus/listener, not as many optional methods on `EventDefinition`.
- (inferred) Initial hooks should be observational only. Control-changing hooks can come later after lifecycle tests exist.

Updated documents:

- `core/events/ARCHITECTURE.md` - expanded with verified lifecycle, hook bus proposal, adapter boundaries, memory/runner policy, and config coupling warning.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/events/models.py` | shallow | partial | 1 | Full file read; event DTO/action/task model identified. |
| `core/events/coordinator.py` | shallow | partial | 1 | Full file read; observe/run phases identified. |
| `core/events/monitor.py` | shallow | partial | 1 | Full file read; detector cache and enabled definitions identified. |
| `core/events/memory.py` | shallow | partial | 1 | Full file read; lifecycle policy identified. |
| `core/events/runner.py` | shallow | partial | 1 | Full file read; handler execution seam identified. |
| `core/events/scheduler.py` | shallow | partial | 1 | Full file read; display/status task selection identified. |
| `core/events/registry.py` | shallow | partial | 1 | Full file read; event definition registry identified. |
| `core/events/config.py` | shallow | partial | 1 | Full file read; portal-default coupling identified. |
| `core/events/base/*.py` | PENDING | partial | 1 | Base definition/detector/handler interfaces read. |
| `core/events/overlay_models.py` | shallow | partial | 1 | Full file read; core-safe overlay DTO identified. |
| `core/events/capture_provider.py` | shallow | partial | 1 | Full file read; handler capture adapter identified. |

Next round plan:

- Read portal event package as the first concrete event implementation.
- Identify which portal-specific pieces should be reusable detector components, handler state machine pieces, config adapters, or probe-only utilities.
- Confirm whether the proposed event hooks cover portal needs without adding portal-specific core behavior.

## [Round 6] 2026-05-26 - Portal Event Package Boundary

### A. Round Goal

Target files:

- `core/events/types/portal/definition.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/assets.py`
- `core/events/types/portal/minimap_detector.py`
- `core/events/types/portal/minimap_feature_matcher.py`
- `core/events/types/portal/minimap_shape_color_matcher.py`
- `core/events/types/portal/main_view_confirmer.py`
- `core/events/types/portal/handler.py`

Questions for this round:

- Is `portal` a clean event package behind `EventDefinition`?
- Which detector algorithms are reusable components?
- Does `handler.py` need a state-machine split?
- Which portal behaviors require generic event hooks versus package-local hooks?

### C. Findings

Key findings:

- (verified) `PortalEventDefinition` is a clean event package entrypoint. It exposes identity, config defaults/schema, detector factory, and handler factory.
- (verified) `PortalEventConfig` is a typed config adapter with backward-compatible `detector_mode` fallback from `feature_detector_enabled`.
- (verified) `PortalMinimapDetector` is a mode-dispatch adapter plus final color filter and logging. It should delegate mode strategy and hit filtering to smaller modules.
- (verified) `minimap_feature_matcher.py` is a reusable algorithm component for blue-body binary mask matching.
- (verified) `minimap_shape_color_matcher.py` is the most algorithm-heavy component. It combines blue/outer/shape/edge/color responses and then re-evaluates candidates with F1-like scores and signature score.
- (verified) `main_view_confirmer.py` is a reusable full-screen portal-glow confirmer, but it is not currently used inside `PortalEventHandler.update()`.
- (verified) `PortalEventHandler` is a state machine encoded as string state and loose fields. It should gain explicit phase enum/runtime dataclass before further splitting.
- (verified) Portal completion currently checks known exit portal proximity, player position change, and minimap environment signature change.
- (inferred) Portal-specific hooks can mostly map to generic event/navigation hooks. Detailed candidate rejection may remain detector-local until a generic detector debug hook exists.
- (inferred) `core/events/config.py` should eventually derive portal defaults from `PortalEventDefinition.default_config()` rather than hard-code portal values in core event defaults.

Updated documents:

- `core/events/types/portal/ARCHITECTURE.md` - expanded with verified package interface, detector architecture, algorithm summaries, handler state machine, hook mapping, and split priorities.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/events/types/portal/definition.py` | shallow | partial | 1 | Full file read; package entrypoint confirmed. |
| `core/events/types/portal/config.py` | shallow | partial | 1 | Full file read; typed config adapter confirmed. |
| `core/events/types/portal/assets.py` | shallow | partial | 1 | Full file read; asset constants confirmed. |
| `core/events/types/portal/minimap_detector.py` | shallow | partial | 1 | Full file read; mode dispatch and hit filtering identified. |
| `core/events/types/portal/minimap_feature_matcher.py` | shallow | partial | 1 | Full file read; blue-body matcher summarized. |
| `core/events/types/portal/minimap_shape_color_matcher.py` | shallow | partial | 1 | Full file read; shape/color algorithm summarized. |
| `core/events/types/portal/main_view_confirmer.py` | shallow | partial | 1 | Full file read; full-view confirmer summarized. |
| `core/events/types/portal/handler.py` | shallow | partial | 1 | Full file read; state machine and completion checks identified. |

Next round plan:

- Read mapping/localization core: `core/recognizer_optimized.py`, `core/stitcher_core.py`, `core/navigation_core.py`.
- Identify reusable algorithm modules and stateful runtime boundaries for mapping/localization.
- Then read `core/pathfinder.py`, `core/path_utils.py`, and `core/anchor_path.py` for route planning boundaries.

## [Round 7] 2026-05-26 - Mapping and Localization Core Boundaries

### A. Round Goal

Target files:

- `core/recognizer_optimized.py`
- `core/stitcher_core.py`
- `core/navigation_core.py`

Questions for this round:

- Which algorithms should become reusable pure modules?
- Which classes should remain stateful runtime facades?
- Where are IO, visualization, debug logging, and algorithm decisions mixed?
- What split order protects behavior with tests?

### C. Findings

Key findings:

- (verified) `HSVRecognizer` mixes parameter storage, preprocessing, wall/fog/player extraction, dynamic color filtering, and combined registration mask construction.
- (verified) `HSVRecognizer.extract_combined()` is the key shared output for both stitching and navigation localization: `(match_mask, wall_mask, fog_mask)`.
- (verified) `MapStitcher` mixes map state, map package IO, keyframe/F2F registration, weighted merging, stats, and display rendering.
- (verified) `MapStitcher.add_frame()` is the mapping main chain: first-frame placement, keyframe anchor matching, previous-frame fallback, draw-quality gate, resize/standardize masks, and weighted merge.
- (verified) `MapStitcher._merge_frame_weighted()` is a distinct reusable merge algorithm with clipping, wall weight accumulation, fog/explored update, and display canvas write.
- (verified) `NavigationCore` mixes map package loading, recognizer construction, localization state, F2F tracking, template matching, visual consistency checks, frame registration, and display rendering.
- (verified) `NavigationCore.localize()` is the localization main chain: extract masks, reject low feature counts, try F2F phase correlation, fallback to local/global template matching, update registration and state.
- (verified) `MapStitcher._estimate_displacement()` and `NavigationCore._estimate_displacement()` duplicate the same phase-correlation algorithm.
- (inferred) First low-risk algorithm extraction should be shared phase correlation. The next should be package IO, then weighted merge, then localization matching.

Updated documents:

- `core/ARCHITECTURE.md` - expanded mapping, recognizer, localization responsibilities, main algorithms, split order, and shared phase-correlation extraction.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/recognizer_optimized.py` | shallow | partial | 1 | Full file read; preprocessing/mask/combined responsibilities identified. |
| `core/stitcher_core.py` | shallow | partial | 1 | Full file read in chunks; add_frame and merge algorithm summarized. |
| `core/navigation_core.py` | shallow | partial | 1 | Full file read in chunks; localization algorithm and state responsibilities identified. |

Next round plan:

- Read route planning core: `core/pathfinder.py`, `core/path_utils.py`, `core/anchor_path.py`, and `core/navigation_obstacles.py`.
- Identify reusable geometry/path modules and their tests.

## [Round 8] 2026-05-26 - Route Planning and Geometry Core

### A. Round Goal

Target files:

- `core/pathfinder.py`
- `core/path_utils.py`
- `core/anchor_path.py`
- `core/navigation_obstacles.py`

Questions for this round:

- Which route/path functions are already reusable?
- Is A* cleanly separated from navigation UI and movement policy?
- Does anchor planning belong in route geometry or movement execution?
- What tests protect these modules?

### C. Findings

Key findings:

- (verified) `PathFinder` is mostly a clean GUI-free A* adapter. It owns coordinate downsampling, obstacle-map construction, start-area forgiveness, walkable snapping, 8-direction A*, and global-coordinate reconstruction.
- (verified) `PathFinder._astar()` allows diagonal movement but prevents diagonal corner cutting by rejecting a diagonal step when either adjacent orthogonal side cell is blocked.
- (verified) `PathFinder._build_obstacle_map()` supports wall thinning, optional unknown-area blocking from `explored_map`, and optional safety-margin dilation.
- (verified) `navigation_obstacles.derive_navigation_wall_layer()` is a pure adapter from stitched wall layer to navigation wall layer: threshold first, then optionally erode with a cross kernel to make routing more forgiving without mutating localization data.
- (verified) `path_utils.py` is a reusable geometry module: distance, collinear cleanup, Bresenham line walkability, shortcut smoothing, cumulative path length, point projection, interpolation, distance-to-path, and circular exit-region checks.
- (verified) `anchor_path.py` is route-shaping logic for ordered user guide anchors. It advances to the next forward anchor first; if A* to that anchor fails, it returns a short probe path toward the anchor instead of jumping straight to the final target.
- (verified) Existing tests cover `PathFinder` and `path_utils` through `tests/test_pathfinder.py` and `tests/test_path_utils.py`.
- (inferred) These modules should stay mostly intact. A later `core/routing/` package can group them, but splitting individual algorithms further would reduce locality more than it improves reuse.
- (inferred) `anchor_path.py` needs direct tests because it encodes navigation product policy: ordered-anchor progress, reached-anchor skipping, target progress filtering, and probe fallback.

Updated documents:

- `core/ARCHITECTURE.md` - expanded with route/pathfinding responsibilities, algorithm summaries, package grouping recommendation, and test gaps.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/pathfinder.py` | shallow | partial | 1 | Full file read; A* adapter, obstacle derivation, start clearing, snapping, and no-corner-cutting behavior identified. |
| `core/path_utils.py` | shallow | partial | 1 | Full file read; geometry/path utility algorithms and line-of-sight smoothing identified. |
| `core/anchor_path.py` | shallow | partial | 1 | Full file read; ordered-anchor corridor planning and probe fallback identified. |
| `core/navigation_obstacles.py` | shallow | partial | 1 | Full file read; pure navigation wall-layer derivation confirmed. |

Next round plan:

- Read GUI dialog modules: `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/color_picker_dialog.py`, and `gui/dialogs/event_manager_dialog.py`.
- Identify dialog-to-domain seams, reusable parameter models, and large-dialog split opportunities.

## [Round 9] 2026-05-26 - GUI Dialog Boundaries

### A. Round Goal

Target files:

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/event_manager_dialog.py`

Questions for this round:

- Which dialogs are simple widget adapters versus mixed UI/domain modules?
- Which parameter read/write and validation code should become reusable models or presenters?
- Which dialog files are large enough to split first without changing behavior?
- How should dialogs interact with event/navigation systems after hooks and module seams are introduced?

### C. Findings

Key findings:

- (verified) `NavParametersDialog` is the largest dialog seam. One class creates all tabs, owns help text, owns widget-to-`NavConfig` binding, mutates immutable dataclasses with `dataclasses.replace`, parses HSV text with `ast.literal_eval`, emits `parameters_changed`, and estimates click radii from calibrated screen bounds.
- (verified) `NavParametersDialog.set_config_to_ui()` uses `QSignalBlocker` over child widgets while copying `NavConfig` values into controls. This is the right behavior and should survive any split.
- (verified) `NavParametersDialog._connect_signals()` already contains the core extraction candidate: a field map from widget to `(sub_config, attr)` plus text-field HSV binding.
- (verified) `_auto_estimate_click_radius()` is not UI layout; it is a small calibration policy based on `QApplication.screens()`, physical bounds, and `game_screen_center`.
- (verified) `AdvancedSettingsDialog` is an older dict-based tuning dialog. It directly reaches into `parent.recognizer` and `parent.stitcher`, applies params with `set_params()`, and writes/loads JSON presets from the current working directory.
- (verified) `advanced_settings/params_adapter.py` is a useful but shallow extraction: it moves widget read/write/preset code out of the dialog, but it still depends on exact dialog attribute names.
- (verified) `ColorPickerDialog` has already extracted HSV math and image rendering into helper modules, but `update_preview()` still owns OpenCV mask generation, morphology, and debug artifact writes (`preview_result_*.png`, `preview_before_morph_*.png`, `preview_log_*.txt`) in the current working directory.
- (verified) `EventManagerDialog` is the cleanest dialog pattern. It builds event rows and dynamic parameter widgets from `build_tui_event_options()` schema, emits command signals for save/test/reset, and renders live task state from `coordinator.tasks()`.
- (verified) `EventManagerDialog` mutates `config` in place (`config.enabled`, `config.events[event_type][key]`) before emitting `config_changed`; this differs from `NavParametersDialog` immutable update style.
- (inferred) New dialog code should copy the event-manager schema-driven form pattern and avoid the advanced-settings parent-reach pattern.
- (inferred) Dialog extraction should start with field specs and widget binding, not visual layout. That keeps UI behavior stable while moving reusable parameter semantics into testable modules.

Updated documents:

- `gui/dialogs/ARCHITECTURE.md` - expanded with verified dialog responsibilities, current seams, split order, reusable form-binding strategy, and risk points.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/dialogs/nav_params_dialog.py` | shallow | partial | 1 | Full file read in chunks; tab construction, field map binding, immutable config update, HSV text parsing, and click-radius estimator identified. |
| `gui/dialogs/advanced_settings_dialog.py` | shallow | partial | 1 | Full file read; legacy dict params, direct recognizer/stitcher mutation, preset/file IO responsibilities identified. |
| `gui/dialogs/advanced_settings/params_adapter.py` | PENDING | partial | 1 | Full file read; shallow widget-attribute adapter and preset application identified. |
| `gui/dialogs/color_picker_dialog.py` | shallow | partial | 1 | Full file read; interaction shell, HSV sampling, preview generation, and debug artifact writes identified. |
| `gui/dialogs/color_picker/hsv_ranges.py` | PENDING | partial | 1 | Full file read; pure HSV conversion/range/stat helpers confirmed. |
| `gui/dialogs/color_picker/image_renderer.py` | PENDING | partial | 1 | Full file read; Qt image conversion and marker rendering adapter confirmed. |
| `gui/dialogs/event_manager_dialog.py` | shallow | partial | 1 | Full file read; schema-driven event parameter form and live task table confirmed. |

Next round plan:

- Read mapping GUI mode and related widgets.
- Identify how mapping runtime, stitching state, capture loop, and UI controls should split from presentation.

## [Round 10] 2026-05-26 - Mapping GUI Mode Boundary

### A. Round Goal

Target files:

- `gui/modes/mapping_mode.py`
- `gui/modes/mapping_widget.py`
- `gui/widgets/minimap_widget.py`
- `gui/widgets/clickable_label.py`

Questions for this round:

- Which mapping GUI class owns the runtime capture/stitch loop?
- How does mapping GUI talk to `ScreenCapture`, `HSVRecognizer`, and `MapStitcher`?
- Which responsibilities are presentation-only versus reusable mapping session logic?
- What widget helpers can remain generic components?

### C. Findings

Key findings:

- (verified) There is no `gui/modes/mapping_mode.py`; the mapping workflow entrypoint is `gui/modes/mapping_widget.py`.
- (verified) There is no `gui/widgets/minimap_widget.py`; the mapping display uses `CollapsibleMapGroup` plus `ScalableMapWidget`.
- (verified) `MappingWidget` owns UI construction, monitor region/center selection, capture timer, capture/recognize/stitch loop, display rendering, temporary route planning on map click, recognizer/stitcher parameter updates, advanced/color picker dialogs, root config save/load, map package save, and topmost window behavior.
- (verified) `capture_and_process()` is the mapping main loop: capture square/region, detect player when needed, fallback to last/center position, extract combined masks, get raw gray, call `MapStitcher.add_frame()`, store last capture/player state, update displays, and update stats.
- (verified) Existing helper modules are meaningful but incomplete: `mapping/save_load.py` owns project-root/config/map-folder helpers; `mapping/map_renderer.py` owns BGR pixmap conversion and global-map overlay drawing; `mapping/params_adapter.py` owns shallow widget/param synchronization.
- (verified) `save_load.project_root_from_file()` derives project root from `Path(__file__).resolve().parents[2]`; when called from `gui/modes/mapping_widget.py`, this resolves to the repository root.
- (verified) `MappingWidget.save_map()` writes both stitcher package data and map-specific `config.json` under `map_data/<map_name>/`.
- (verified) `ScalableMapWidget` declares `pixel_clicked = Signal(int, int)` and `MappingWidget` connects it to `on_map_click()`, but the widget never emits that signal in its mouse handlers.
- (verified) `ClickableImageLabel` does implement original-coordinate click conversion and emits `pixel_clicked`; it is used by color picker, not the mapping global map.
- (inferred) `MappingWidget` should be split after extracting a `MappingSession` or `MappingRuntimeLoop` that hides capture/recognize/stitch mechanics behind a small interface.
- (inferred) `ScalableMapWidget` either needs coordinate-click support or the mapping route-click feature should be removed from the title and wiring. This is a concrete behavior risk to verify with UI testing before refactor.

Updated documents:

- `gui/modes/ARCHITECTURE.md` - expanded mapping mode with verified runtime loop, helper module roles, target split, and the `ScalableMapWidget.pixel_clicked` risk.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/modes/mapping_widget.py` | shallow | partial | 1 | Full file read in chunks; capture/stitch loop, config save/load, map save, param updates, and display responsibilities identified. |
| `gui/modes/mapping/save_load.py` | PENDING | partial | 1 | Full file read; project root, map folder, root/map config JSON helpers identified. |
| `gui/modes/mapping/map_renderer.py` | PENDING | partial | 1 | Full file read; BGR pixmap and global map overlay rendering identified. |
| `gui/modes/mapping/params_adapter.py` | PENDING | partial | 1 | Full file read; shallow widget-to-params sync helpers identified. |
| `gui/widgets/clickable_label.py` | shallow | partial | 1 | Full file read; original-coordinate click conversion and wheel zoom signal confirmed. |
| `gui/widgets/scalable_map.py` | PENDING | partial | 1 | Full file read; zoom/pan widget read; declared `pixel_clicked` lacks emit. |
| `gui/widgets/collapsible_group.py` | PENDING | partial | 1 | Full file read; wraps `ScalableMapWidget` with zoom buttons and collapsible group. |

Next round plan:

- Read input system modules: `core/motion_controller.py`, `core/input_driver.py`, and relevant probe/usage files.
- Identify the seam between route intent, screen coordinate mapping, and platform input side effects.

## [Round 11] 2026-05-26 - Input System and Motion Boundary

### A. Round Goal

Target files:

- `core/motion_controller.py`
- `core/input_driver.py`
- `utils/input_probe.py`
- `utils/event_icon_probe.py`
- `utils/portal_screen_probe.py`

Questions for this round:

- Where should the seam live between navigation route intent and concrete click/key side effects?
- Which input behavior belongs in reusable movement mapping versus platform adapter code?
- What existing probe utilities reveal about required diagnostics or dry-run hooks?
- How can input hooks be added without making navigation tasks depend on GUI details?

### C. Findings

Key findings:

- (verified) `MotionController` is more than a simple driver wrapper. It owns map-vector to screen-click mapping, min/max/precision radius policy, control enablement, direct screen clicks, key presses, bottom-click guard, optional screen clamping, optional focus-before-click, backend dispatch, and rich click diagnostics.
- (verified) `MotionController._calculate_target_screen_position()` is pure movement mapping except for writing `last_click_info`.
- (verified) `MotionController._execute_click()` is the main side-effect boundary. It applies bottom guard, optional clamping, window diagnostics, optional focus, sends click through backend, records cursor/window details, and falls back to `pydirectinput.click()`.
- (verified) `MotionController.press_key()` bypasses `InputDriver` and calls `pydirectinput.press()` directly. This is an adapter gap for testability and hookability.
- (verified) `InputDriver` is a concrete Win32 adapter around `ctypes.windll.user32`: cursor move, cursor/window diagnostics, foreground focus, mouse down/up/click, and drag.
- (verified) `utils/input_probe.py` is a real diagnostic adapter. It compares several input strategies, collects DPI/window/cursor state, defaults to dry-run, and only sends input with `--execute`.
- (verified) `tests/test_motion_controller.py` already tests click radius clamping, zero-delta skip, `_execute_click()` diagnostics, optional clamping, focus, and bottom guard using a fake input driver and fake `pydirectinput`.
- (verified) `utils/event_icon_probe.py` calls production portal detector components rather than copying detector algorithms. It owns CLI parsing, capture geometry, debug drawing, and artifact writing.
- (verified) `utils/portal_screen_probe.py` calls production main-view portal confirmer/window-finder functions and owns CLI/capture/debug output.
- (inferred) The first input seam should be an `InputCommandSink`/`GameInputAdapter` behind `MotionController`, not in event handlers or movement executor.
- (inferred) Hooks should observe or wrap `MotionController` commands and results: before command, after command, command skipped, backend failure, and diagnostics snapshot.
- (inferred) `input_probe.py` should remain allowed to contain non-production input strategies because its purpose is comparing adapters. Production navigation should use only the chosen adapter through `MotionController`.

Updated documents:

- `core/ARCHITECTURE.md` - expanded input system with verified `MotionController`/`InputDriver` behavior, adapter gaps, hook locations, and split order.
- `utils/ARCHITECTURE.md` - expanded probe responsibilities and rules for production algorithm reuse.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/motion_controller.py` | shallow | partial | 1 | Full file read; movement mapping, click execution, bottom guard, diagnostics, backend fallback, and key adapter gap identified. |
| `core/input_driver.py` | shallow | partial | 1 | Full file read; Win32 cursor/window/click adapter responsibilities identified. |
| `utils/input_probe.py` | shallow | partial | 1 | Full file read; dry-run diagnostics, input strategy comparison, admin restart, and execute modes identified. |
| `utils/event_icon_probe.py` | shallow | partial | 1 | Full file read in chunks; production detector reuse and debug artifact responsibilities identified. |
| `utils/portal_screen_probe.py` | shallow | partial | 1 | Full file read; production main-view confirmer reuse and window/rect capture diagnostics identified. |
| `tests/test_motion_controller.py` | PENDING | partial | 1 | Full file read; fake driver tests cover mapping and click execution policies. |

Next round plan:

- Read test index and remaining focused probe/task utilities.
- Then consolidate final architecture roadmap with class/module extraction priorities and cross-doc references.

## [Round 12] 2026-05-26 - Tests, Remaining Probes, and Roadmap Consolidation

### A. Round Goal

Target files:

- `tests/*.py`
- `utils/route_context_probe.py`
- `utils/navigation_task_probe.py`
- `ARCHITECTURE_GUIDE.md`

Questions for this round:

- Which refactor candidates already have tests?
- Which risky splits need tests before source changes?
- Do remaining probes follow the production-adapter rule?
- How should the top-level roadmap sequence module/class extraction work?

### C. Findings

Key findings:

- (verified) Existing tests protect several low-level seams: `MotionController`, `PathFinder`, `path_utils`, `NavigationCore` F2F wall-mask behavior, `MapStitcher._merge_frame_weighted()`, recognizer dynamic filtering, and route manager persistence.
- (verified) Tests do not yet directly protect event lifecycle, portal handler state transitions, mapping runtime orchestration, navigation intent execution, dialog binding, or GUI map-click behavior.
- (verified) `route_context_probe.py` and `navigation_task_probe.py` are good narrow probes: they read route data and call production `RouteContext` / `NavigationTaskBuilder` rather than copying route math.
- (verified) `ARCHITECTURE_GUIDE.md` now has a phased roadmap: test guardrails, low-risk deep modules, runtime facades, event hooks/packages, GUI cleanup, and final package organization.
- (inferred) The safest first code changes are pure/helper extractions with tests: `anchor_path` tests, shared phase displacement, weighted merge, motion mapping/bottom guard, and nav dialog click-radius estimator.
- (inferred) The highest-value large-file split remains `gui/modes/navigation_mode.py`, but it should start with `NavigationIntentExecutor`, config applier, runtime start/stop, and event panel adapter rather than a broad file move.
- (inferred) Event hooks should wait until fake-detector/fake-handler lifecycle tests exist; otherwise hook dispatch may accidentally freeze current incidental behavior.

Updated documents:

- `tests/ARCHITECTURE.md` - expanded with verified test contracts and missing test additions.
- `utils/ARCHITECTURE.md` - expanded route/task probe descriptions.
- `ARCHITECTURE_GUIDE.md` - replaced hypotheses with confirmed themes and a phased refactor roadmap.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `tests/test_pathfinder.py` | shallow | partial | 1 | Full file read; corner cutting, wall shrinking, unexplored blocking contracts identified. |
| `tests/test_path_utils.py` | shallow | partial | 1 | Full file read; simplification, projection/interpolation, smoothing, and exit-region contracts identified. |
| `tests/test_navigation_core.py` | shallow | partial | 1 | Full file read; F2F wall-mask regression contract identified. |
| `tests/test_stitcher_core.py` | shallow | partial | 1 | Full file read; weighted merge visibility/fog contracts identified. |
| `tests/test_recognizer_optimized.py` | shallow | partial | 1 | Full file read; dynamic saturation filtering contract identified. |
| `tests/test_route_manager.py` | shallow | partial | 1 | Full file read; route defaults, round-trip, and undo contract identified. |
| `utils/route_context_probe.py` | shallow | partial | 1 | Full file read; production `RouteContext` progress inspection confirmed. |
| `utils/navigation_task_probe.py` | shallow | partial | 1 | Full file read; production `NavigationTaskBuilder` inspection confirmed. |
| `ARCHITECTURE_GUIDE.md` | shallow | partial | 2 | Re-read and updated with confirmed roadmap and cross-module rules. |

Next round plan:

- If continuing documentation only: deepen individual function/class documentation in `CODEBASE.md` format for one module at a time.
- If moving to refactor implementation: start with tests for `anchor_path.py` and `EventCoordinator`, then extract low-risk pure helpers.

## [SYNC] 2026-05-26 - Advanced Settings File IO Cleanup

### A. SYNC Scope

Trigger task: legacy content audit and low-risk behavior-preserving cleanup.

Direct source changes:

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/file_io.py`
- `tests/test_advanced_settings_file_io.py`

Expected impact:

- `AdvancedSettingsDialog.save_current_params()` and `load_params_from_file()` now delegate JSON persistence to a reusable helper.
- Saved parameter snapshots no longer write to the process current working directory; they default to `configs/advanced_settings/`.
- Test coverage now protects filename sanitization, explicit output directories, payload shape, validation, and non-ASCII display formatting.

### C. SYNC Result

Key findings:

- (verified) `advanced_settings/file_io.py` owns default output directory, filename sanitization, JSON dump/load, payload validation, and display formatting.
- (verified) `AdvancedSettingsDialog` still owns Qt file dialog usage, status labels, and recognizer/stitcher apply timing.
- (verified) Importing `gui.dialogs.advanced_settings.file_io` through the full `gui` package triggers unrelated GUI/input dependencies; the new test loads the pure helper by file path to keep the test isolated.

Updated documents:

- `CODEBASE.md`
- `ARCHITECTURE_GUIDE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/ARCHITECTURE_GUIDE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\file_io.py tests\test_advanced_settings_file_io.py`
- `python -m unittest tests.test_advanced_settings_file_io`
- `python -m unittest tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue old-content audit with stricter reference checks for `gui/widgets_fixed.py` before any deletion decision.
- Then consider another low-risk extraction with tests, preferably presets from `AdvancedSettingsDialog` or a pure helper from `NavParametersDialog`.

## [SYNC] 2026-05-26 - Remove Unused widgets_fixed Backup

### A. SYNC Scope

Trigger task: continue legacy content audit.

Direct source changes:

- Deleted `gui/widgets_fixed.py`

Expected impact:

- Active widget imports remain through `gui/widgets/clickable_label.py`, `gui/widgets/scalable_map.py`, and `gui/widgets/collapsible_group.py`.
- Removing the old combined backup reduces duplicate widget definitions and prevents accidental reintroduction of stale behavior.

### C. SYNC Result

Key findings:

- (verified) `rg` found no runtime import of `gui.widgets_fixed`; references were limited to docs/history and the file itself.
- (verified) `widgets_fixed.py` contained old combined definitions for `ClickableImageLabel`, `ScalableMapWidget`, and `CollapsibleMapGroup`.
- (verified) Current runtime code imports the split widget modules under `gui/widgets/`.

Updated documents:

- `CODEBASE.md`
- `gui/ARCHITECTURE.md`
- `architecture_docs/original/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\widgets\clickable_label.py gui\widgets\scalable_map.py gui\widgets\collapsible_group.py gui\modes\mapping_widget.py`
- `python -c "from gui.widgets.clickable_label import ClickableImageLabel; from gui.widgets.scalable_map import ScalableMapWidget; from gui.widgets.collapsible_group import CollapsibleMapGroup; print('ok')"`

Next round plan:

- Continue low-risk cleanup with `AdvancedSettingsDialog` presets extraction, or audit `k_ratio/y_bias` UI compatibility fields before changing them.

## [SYNC] 2026-05-26 - Advanced Settings Preset Data Extraction

### A. SYNC Scope

Trigger task: continue low-risk cleanup after legacy audit.

Direct source changes:

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/params_adapter.py`
- `gui/dialogs/advanced_settings/presets.py`
- `tests/test_advanced_settings_presets.py`

Expected impact:

- Preset option order and non-default preset values now live in a data-only helper.
- `AdvancedSettingsDialog` no longer embeds preset names inline.
- `params_adapter.apply_preset_to_widgets()` still preserves the same widget writes and default reset behavior.

### C. SYNC Result

Key findings:

- (verified) `presets.py` owns `DEFAULT_PRESET_NAME`, `PRESET_NAMES`, and non-default widget-value maps.
- (verified) Default preset remains a full reset path through `reset_widgets_to_default()`.
- (verified) Tests cover preset order, old values, adapter application, default reset, and unknown preset return value without constructing Qt dialogs.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\params_adapter.py gui\dialogs\advanced_settings\presets.py tests\test_advanced_settings_presets.py`
- `python -m unittest tests.test_advanced_settings_presets`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue with `AdvancedSettingsDialog` tab/widget-spec extraction only if a narrow adapter test can cover it, otherwise audit `k_ratio/y_bias` compatibility fields.

## [SYNC] 2026-05-26 - Hide Legacy k_ratio/y_bias UI

### A. SYNC Scope

Trigger task: audit old `NavPreferences.k_ratio/y_bias` compatibility fields.

Direct source changes:

- `gui/dialogs/nav_params_dialog.py`
- `tests/test_navigation_params_compat.py`

Expected impact:

- Old `k_ratio/y_bias` values still load/save through `NavConfig.nav_preferences`.
- The navigation parameter panel no longer exposes controls that do not affect current motion mapping.

### C. SYNC Result

Key findings:

- (verified) `k_ratio/y_bias` are not referenced by `MotionController`, localization, task scheduling, or movement execution.
- (verified) Runtime usage was limited to config model round-trip and `NavParametersDialog` UI/binding.
- (verified) The UI controls and widget-map bindings were removed, while `NavPreferences` remains for old `config.json` compatibility.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\navigation_params.py tests\test_navigation_params_compat.py`
- `python -m unittest tests.test_navigation_params_compat`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Stop here for this cleanup batch unless another old-content candidate is requested; larger tab extraction needs a separate narrow plan and GUI-aware test strategy.

## [SYNC] 2026-05-26 - Nav Params Screen Estimator Extraction

### A. SYNC Scope

Trigger task: continue low-risk dialog cleanup and finish documentation sync for the extracted navigation click-radius estimator.

Direct source changes:

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/nav_params/__init__.py`
- `gui/dialogs/nav_params/screen_estimator.py`
- `tests/test_nav_params_screen_estimator.py`

Expected impact:

- `NavParametersDialog` keeps Qt screen enumeration and UI writes.
- `gui.dialogs.nav_params.screen_estimator.estimate_click_radii()` owns the pure radius policy.
- Tests cover normal estimate, small-screen minimum clamp, large-screen maximum clamp, and out-of-bounds centers.

### C. SYNC Result

Key findings:

- (verified) `_auto_estimate_click_radius()` now delegates radius math to `estimate_click_radii(center, screen_bounds)`.
- (verified) `screen_estimator.py` has no Qt dependency, so it can be tested without importing the full GUI package.
- (verified) Physical-screen detection remains in the dialog adapter through `_screen_physical_bounds_for_center()`.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`

Validation:

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\dialogs\nav_params\screen_estimator.py tests\test_nav_params_screen_estimator.py`
- `python -m unittest tests.test_nav_params_screen_estimator`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_navigation_params_compat tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue old debug-output cleanup by disabling `ColorPickerDialog.update_preview()` artifact writes by default while preserving an explicit diagnostic opt-in.

## [SYNC] 2026-05-26 - Color Picker Debug Output Gating

### A. SYNC Scope

Trigger task: continue old-content audit cleanup after moving color-picker preview debug artifacts out of the current working directory.

Direct source changes:

- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/color_picker/debug_output.py`
- `tests/test_color_picker_debug_output.py`

Expected impact:

- HSV preview rendering still updates the right-side preview label.
- `preview_result_*.png`, `preview_before_morph_*.png`, and `preview_log_*.txt` are no longer written on every preview by default.
- Debug artifacts remain available by setting `MINIMAP_COLOR_PICKER_DEBUG=1`.

### C. SYNC Result

Key findings:

- (verified) `ColorPickerDialog.update_preview()` still builds the same wall mask, performs the same close morphology, and updates the preview label.
- (verified) `write_wall_preview_debug()` is only called when `is_wall_preview_debug_enabled()` accepts `MINIMAP_COLOR_PICKER_DEBUG`.
- (verified) The debug switch is testable without importing PySide widgets or constructing the dialog.

Updated documents:

- `CODEBASE.md`
- `ARCHITECTURE_GUIDE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/ARCHITECTURE_GUIDE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\debug_output.py tests\test_color_picker_debug_output.py`
- `python -m unittest tests.test_color_picker_debug_output`

Next round plan:

- Continue with another low-risk pure/helper extraction only after current docs and regression tests are clean.
