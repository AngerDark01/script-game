# Command-assisted live follow implementation plan

## Goal

Keep PoE2 live-role follow localized and actively recovering through temporary
marker loss without treating predictions as visual feedback.

## Architecture Overview

The PoE2 experiment owns a per-role fixed-lag estimator. The output adapter
reports successful effective commands; the estimator predicts from those
commands and corrects with same-instance visual observations. The existing
follow runtime consumes a typed predicted position but never uses it for
calibration, contact, or confirmed arrival. The UI composition preserves the
target and triggers the existing recovery workflow on evidence-based failure.

## Tech Stack

Python 3, NumPy, pytest and PyQt; existing `PositionStateEstimator`,
`ProgramGamepadOutput`, `ProgramFollowOutput`, `SimulatedFollowRuntime`, and
`Poe2CaptureTestPage`.

## Tasks

### 1. Prove the current failure

Files: `tests/poe2_live_terrain/test_command_role_tracker.py`,
`tests/test_poe2_capture_test_page.py`.

Test a program role hidden beyond the old 2-second bound while wall frames
remain fresh; the existing page must fail this test by releasing output.
Test a manual leader separately: no invented command displacement.

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_command_role_tracker.py tests/test_poe2_capture_test_page.py`

### 2. Report successful output, not planned output

Files: `src/auto_modules/adapters/virtual_gamepad/program_output.py`,
`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`,
`tests/test_program_gamepad.py`,
`tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`.

Add an immutable receipt with `accepted_at_ms`, `effective_axes`, and `ttl_ms`
only after `program.state` succeeds; a fake output without a receipt cannot
drive dead reckoning. A newer output replaces the previous pulse.

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_program_gamepad.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

### 3. Predict and correct independently per role

Files: `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`,
`tests/poe2_live_terrain/test_command_role_tracker.py`.

Implement `seed(role, map, point, captured_at)`,
`record_output(role, interval)`, `observe(role, point, captured_at, covariance)`,
and `estimate(role, now_ms)`. Replay accepted, non-overlapping intervals from
the visual anchor; keep distinct predicted/observed provenance and reject
stale visual frames. Test overlap, expiry, delayed correction, uncertainty,
same-instance reset, and two-role isolation.

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_command_role_tracker.py`

### 4. Keep predicted data out of feedback and arrival

Files: `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`,
`tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`.

Treat `command_prediction` and `target_hold` as estimates. Do not update
observed speed, calibration, contact, or no-progress from them. Clamp hidden
role pulses to a short horizon. A predicted position inside arrival radius
requests confirmation/re-anchor rather than returning `ARRIVED`.

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

### 5. Compose and diagnose live follow

Files: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`,
`tests/test_poe2_capture_test_page.py`,
`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`.

Seed the tracker at live-follow start. On each fresh frame correct visible
roles; for a hidden program role feed its command estimate into the runtime.
For a hidden manual leader retain only the last measured target. Feed receipts
back after successful output writes. Preserve the target through one-shot
re-anchor. Log state, source, uncertainty, output interval and recovery reason.

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py tests/poe2_live_terrain/test_command_role_tracker.py`

### 6. Review and sync

Run focused PoE2 regression, compileall, `git diff --check`, then manually
trace start -> frame -> estimate -> route -> output -> recovery -> resume.
Update `ITERATION_LOG.md` and affected sections of `CODEBASE.md`. Do not
commit the current dirty worktree as a task step: it contains pre-existing
user changes in shared files.
