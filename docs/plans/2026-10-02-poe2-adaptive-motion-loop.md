# PoE2 实验版自适应运动闭环实现计划

## Goal

在 PoE2 实验页内实现基于局部地图复杂度、实际 native 位移反馈和在线输入校准的高效运动闭环；保持定位、路线、输出和 UI 模块独立，并通过同一份冻结观测快照协同工作，稳定后再抽取通用引擎能力。

## Architecture Overview

```text
PoE2 frame/position adapters
        │
        ▼
MotionSnapshotBuilder
        │
        ├── LocalComplexityClassifier
        │       └── OPEN / TRANSITION / CONSTRAINED / UNKNOWN
        │
        ├── SequentialMotionEstimator
        │       └── predicted position, velocity, covariance
        │
        ├── AdaptiveInputCalibrator
        │       └── stick/native basis, speed and duration gains
        │
        └── ClosedLoopMotionController
                ├── nominal regulated pursuit
                ├── short candidate pulse evaluation
                ├── arrival/stall/recovery decisions
                └── neutral/stop intent
                                │
                                ▼
                      PoE2 motion/output adapter
                                │
                                ▼
                       ProgramFollowOutput
```

The first implementation remains under `features/poe2/live_terrain/experimental/multiplayer_follow/`. Common routing and localization modules are consumed through existing interfaces and are not changed until replay and real PoE2 samples validate the contracts. `footprint_radius=2.0` remains the explicit PoE2 experiment value; `minimum_clearance=6.0`, `clearance_radius=20.0`, `safety_margin=2` and `arrival_radius=8.0` remain separate parameters.

The runtime uses one latest snapshot per control tick. Wall distance, route samples, complexity features, estimator update, command selection and diagnostics read that snapshot rather than capturing or converting the map repeatedly.

## Tech Stack

- Python 3.12, dataclasses, NumPy, OpenCV distance transforms already used by the project.
- PySide6 PoE2 experiment page and existing latest-only dual motion worker.
- Existing `LocalMotionController`, `SimulatedFollowRuntime`, `ProgramFollowOutput`, `ProgramGamepadOutput` and route/pathfinder contracts.
- pytest for pure contracts, replay tests and runtime integration tests.

## Implementation Tasks

### Task 1: Add immutable motion-loop contracts and snapshot builder

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/motion_models.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/motion_snapshot.py`
- `tests/poe2_live_terrain/test_motion_loop_models.py`

Write failing tests first for finite points, native coordinate space, map-version fencing, stale frame rejection and immutable diagnostics. Add `MotionObservation`, `MotionCommand`, `MotionResponse`, `MotionCalibrationState`, `MotionSnapshot` and `MotionPhase` with explicit fields for native position, target, route, wall clearance, peer relation, frame age, confidence, previous command and map/registration versions. The snapshot builder must reject mixed map versions and preserve a read-only wall/distance view.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_motion_loop_models.py -q
# Expected: all model and snapshot contract tests pass
```

### Task 2: Implement local geometry complexity classification

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/complexity.py`
- `tests/poe2_live_terrain/test_motion_complexity.py`

Write failing tests for open room, narrow corridor, corner, unknown map, stale localization and a two-player close-distance case. Implement `LocalComplexityClassifier` using the existing wall distance field and route geometry. Compute `c_p10`, `c_min`, route free ratio, unknown ratio, directional visibility, curvature, turn density, localization quality and command alignment. Normalize each feature to `[0, 1]` and calculate:

```text
complexity =
    .30 * low_clearance + .20 * low_visibility + .10 * low_free
  + .10 * unknown + .12 * curvature + .08 * turn_density
  + .06 * localization_uncertainty + .04 * motion_residual
```

Apply hard gates for stale/unknown localization and collision clearance. Add hysteresis: entering constrained after 2–3 qualifying frames, leaving only after 4–6 safe frames. Expose every component and threshold in diagnostics; do not hide a hard gate behind the aggregate score.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_motion_complexity.py -q
# Expected: classification states and feature diagnostics are deterministic
```

### Task 3: Implement sequential estimator and online input calibration

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/motion_calibration.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/sequential_motion.py`
- `tests/poe2_live_terrain/test_motion_calibration.py`
- `tests/poe2_live_terrain/test_sequential_motion.py`

Write failing tests for valid command/response updates, low-displacement rejection, direction mismatch, target progress, covariance growth and per-role state isolation. Reuse the semantics of the existing `PositionStateEstimator`: command output is prediction, visual/native displacement is observation, and Mahalanobis/quality gates reject bad observations.

Implement bounded recursive least squares for:

```text
v_native = A * stick + bias
```

and exponential smoothing for observed speed. Freeze calibration when the frame is stale, map versions differ, displacement is below the minimum, collision is likely or recovery is active. Bound axis signs, gains, parameter step size and speed. Keep state keyed by controller and role; no module-global mutable state.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_motion_calibration.py tests/poe2_live_terrain/test_sequential_motion.py -q
# Expected: accepted responses update state; invalid responses do not contaminate it
```

### Task 4: Add the closed-loop controller facade

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/closed_loop_controller.py`
- `tests/poe2_live_terrain/test_closed_loop_controller.py`

Write failing tests for nominal open movement, constrained candidate pulses, transition blending, unknown stop, arrival, speed reduction and stalled recovery. Implement `ClosedLoopMotionController.step(snapshot)` with the sequence:

```text
classify local complexity
→ update sequential estimate
→ choose local waypoint
→ choose nominal or candidate-pulse policy
→ calculate bounded stick vector and duration
→ return command plus next phase and diagnostics
```

Use regulated pursuit in `OPEN`, short candidate pulses in `CONSTRAINED`, blended commands in `TRANSITION`, and neutral output in `UNKNOWN`. Candidate scoring must include progress, path alignment, clearance, collision risk, direction change and speed overshoot. Arrival requires distance and progress confirmation; no-progress uses a bounded window and returns a recovery intent instead of repeatedly issuing the same vector.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_closed_loop_controller.py -q
# Expected: each phase produces bounded, explainable commands
```

### Task 5: Integrate the facade into the PoE2 experimental runtime

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/__init__.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

Write failing integration tests using a deterministic plant: one tick issues a command, the next accepted visual position creates a response, calibration updates, and the next command changes according to speed/alignment. Verify two roles have isolated calibration state, `footprint_radius=2.0` is preserved by the PoE2 composition, and existing route diagnostics remain present. Add a single runtime observation adapter that creates `MotionSnapshot` once per tick and passes it to classifier, estimator and controller. Do not add memory reads to normal movement; only the existing explicit recovery path may request one.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -q
# Expected: existing runtime tests plus closed-loop integration pass
```

### Task 6: Connect output boundary and diagnostics without duplicate work

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`
- `tests/test_poe2_capture_test_page.py`

Write failing tests for neutral output on `UNKNOWN/ARRIVED/BLOCKED`, command duration propagation, map-version fencing and latest-only diagnostics. Keep `ProgramFollowOutput` as the only output boundary. Extend the existing motion log with region state, complexity components, chosen policy, command id, duration, native-before/after, alignment, speed ratio, calibration confidence and recovery reason. The page must render diagnostics from the same runtime observation and must not recapture or recompute the wall map for the side panel.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_multiplayer_follow_runtime.py tests/test_poe2_capture_test_page.py -q
# Expected: output safety and UI diagnostic tests pass
```

### Task 7: Replay, performance and documentation audit

Files:

- `tests/poe2_live_terrain/test_motion_loop_replay.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Add replay coverage for open room, wall approach, narrow door, dead end, stale frame, repeated frame, direction inversion and two-player proximity. Measure per-stage timing, dropped latest-only results, command-to-feedback latency and peak bounded queue size. Run focused tests, compileall and diff check. Update the checkpoint, architecture log and CODEBASE sections for new contracts, flow, parameters and risks. Do not claim real-device success until the user runs the explicitly authorized movement experiment.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain tests/test_poe2_capture_test_page.py -q
D:\ACloud\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

## Execution Order

Tasks 1–3 are pure contracts and can be tested without input. Task 4 is the controller policy. Task 5 integrates it into the existing PoE2 runtime. Task 6 connects the existing output/GUI boundaries. Task 7 performs replay, performance and documentation review. No task sends real input or starts LAN synchronization unless the user explicitly starts the corresponding experiment.
