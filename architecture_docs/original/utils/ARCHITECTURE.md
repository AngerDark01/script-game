# Probe and Diagnostics Architecture

## System Role

`utils` contains standalone probes and diagnostics. These should be verification adapters around production modules, not divergent implementations of production algorithms.

## Current Modules

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `event_icon_probe.py` | Offline/live minimap event icon probe. | Should call production detector components and expose reproducible outputs. |
| `portal_screen_probe.py` | Live/main-view portal confirmer probe. | Should call production main-view confirmer logic. |
| `input_probe.py` | Input/click diagnostics. | Should exercise `InputDriver` and `MotionController` behavior without copying click policy. |
| `route_context_probe.py` | Route projection/progress inspection. | Should exercise `RouteContext` behavior. |
| `navigation_task_probe.py` | Unified task list inspection. | Should exercise task builder/scheduler contracts. |

## Verified Probe Patterns

### `input_probe.py`

Current role: compare real mouse input strategies against the game and print diagnostics.

Verified behavior:

- Sets process DPI awareness to physical coordinates.
- Defaults to dry-run; real input requires `--execute`.
- Can restart as admin with `--restart-admin`.
- Collects target point, DPI awareness, admin status, pydirectinput size/position, Win32 cursor, clip cursor rectangle, target window, and foreground window.
- Supports multiple input strategies:
  - direct `pydirectinput.click(x, y)`,
  - raw Win32 `SetCursorPos + mouse_event`,
  - `pydirectinput.moveTo + click`,
  - `pydirectinput` hold,
  - `InputDriver.move_to + pydirectinput`,
  - `InputDriver.click()`.

Architecture rule:

- This probe may contain alternative input strategies because its job is adapter discovery.
- Production navigation should not copy those branches; it should use `MotionController` plus the chosen command sink.

### `event_icon_probe.py`

Current role: validate minimap event icon detection on live captures or saved images.

Verified behavior:

- Reads map capture config from `map_data/<map>/config.json`.
- Builds capture geometry from either `monitor_region` or logical center plus DPR.
- Reuses production detector pieces:
  - `core.events.detectors.template_matcher`,
  - portal minimap feature matcher,
  - portal shape/color matcher,
  - portal color check.
- Writes raw frames, annotated matches, shape/color masks, and candidate crops.
- Prints accepted and rejected candidate diagnostics with scores and reasons.

Architecture rule:

- Keep CLI parsing, debug drawing, and artifact writing in the probe.
- Keep detector math in `core/events/...`.

### `portal_screen_probe.py`

Current role: validate main-view portal confirmer logic.

Verified behavior:

- Captures explicit rect, full screen, or game window found by title/class.
- Reuses production window finder and portal main-view confirmer functions.
- Writes metadata, raw frames, masks, and annotated candidate images.
- Prints strict-acceptance diagnostics for candidates.

Architecture rule:

- Probe-specific threshold CLI is acceptable, but accepted threshold sets should be saved as config assets if they become production defaults.

### `route_context_probe.py`

Current role: inspect route progress along guide anchors for one map.

Verified behavior:

- Reads `map_data/<map>/route.json`.
- Builds production `RouteContext` from guide points.
- Prints guide anchor progress, required point progress, and exit-region center progress.

Architecture rule:

- Good probe shape: all progress math stays in `RouteContext`; the probe only loads route data and prints values.

### `navigation_task_probe.py`

Current role: inspect generated navigation tasks for one map.

Verified behavior:

- Reads `map_data/<map>/route.json`.
- Builds production `RouteContext`.
- Calls `NavigationTaskBuilder().build()` with route data, no event tasks, and an empty completed-required set.
- Prints task id, kind, target, and route progress.

Architecture rule:

- Keep it as a narrow task-builder adapter.
- If event tasks are added to this probe, use production `EventTask` DTOs or fixtures rather than ad hoc dicts.

## Refactor Rule

When a probe contains useful algorithm logic, move the algorithm to `core` and make the probe an adapter that supplies arguments, writes debug files, and prints results.

## Probe-to-Hook Relationship

The same data printed by probes should eventually be available through hooks:

- Input hooks should expose command, requested/final screen position, backend, target window, cursor before/after, skipped reason, and fallback exception.
- Event detector hooks should expose candidates, accepted/rejected state, score breakdown, and debug artifact paths.
- Navigation task hooks should expose selected task, generated intent, click suppression reason, and route progress.

Do not make probes import GUI widgets. Use production core adapters and write standalone outputs.

## Round Status

Status: partial. Main input/event portal probes and route/task probes have been read. Probe output formats are not documented exhaustively, but production dependency direction is mapped.
