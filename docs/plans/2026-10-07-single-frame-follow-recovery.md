## Goal

Make the PoE2 dual-player experiment responsive and stable by registering one stationary first frame, processing only the newest live frame, and continuing through short visual dropouts with bounded prediction until visual evidence recovers.

## Architecture Overview

- First-frame registration is a one-shot data task: one memory-anchor snapshot, one screenshot, one candidate extraction, one registration, one result application.
- The live worker keeps a latest-only result slot. It measures capture, recognition, candidate extraction, tracking, and total processing time separately.
- `DualVisualTracker` returns the last trusted per-role/map estimate during a short visual gap. It records prediction age and uncertainty; it requests recovery only after the bounded prediction widfndow or map validity fails.
- UI preview/evidence rendering remains throttled and cannot block the control frame.
- No collision-radius, marker-color, or global confidence retuning is included in this change.

## Tech Stack

- Python 3.x, NumPy, OpenCV, PySide6, pytest.
- Existing `Poe2DualMotionWorker`, `DualVisualTracker`, `Poe2CaptureTestPage`, and the formal mapping/navigation runtime patterns.

## Implementation Tasks

### Task 1: Make first-frame registration single-shot

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`

Add a regression test around `_compute_dual_first_frame()` with a fake preview provider that counts calls. The test must assert one capture and one registration attempt for a stationary first-frame task. Keep the task side-effect free with respect to Qt.

Implementation:

- Replace the fixed `capture_attempts = 3` loop with one capture.
- Remove the inter-frame sleep and consensus list selection.
- Production monitor configurations must submit this one-shot task to
  `Poe2DualFirstFrameWorker`; only minimal test configurations without a
  localization cadence may retain the synchronous hook.
- Keep the first-frame candidate budget separate from the live budget. The
  one-shot experiment uses at most four candidates (two roles plus a bounded
  ambiguity reserve); the live worker may keep its existing six-candidate
  tracking budget.
- Preserve the existing diagnostics shape, but report `capture_attempts=1`, `selected_attempt=1`, and the per-stage timings.
- Keep failure handling unchanged: an empty/invalid/single-candidate frame is a failed first-frame result, not a reason to silently resample.

Verify:

```powershell
pytest -q tests/test_poe2_capture_test_page.py -k "dual_first_frame"
```

Expected: existing first-frame tests plus the new call-count test pass.

Commit: `perf: register dual first frame once`

### Task 2: Add explicit prediction fallback state to the pure dual tracker

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`
- `tests/poe2_live_terrain/test_dual_motion.py` (create if absent)

Add failing tests for:

- one missing marker frame preserving the last trusted player positions;
- a missing marker frame producing `degraded` with `prediction_age_ms` and finite uncertainty;
- recovery after a valid candidate clearing the prediction age without jumping more than the configured observation gate;
- repeated missing frames requesting recovery only after the bounded prediction window.

Implementation:

- Store last trusted native role positions, last accepted timestamp, and per-role velocity.
- When wall geometry is trusted but marker assignment is empty/ambiguous, return the stored/predicted role positions instead of `{}`.
- Compute bounded prediction as `p_hat = p + (alpha*v + beta*u*v_command)*dt`; use prediction hints when supplied by the follow runtime.
- Increase uncertainty with elapsed time; expose `prediction_age_ms`, `prediction_uncertainty_native`, `prediction_active`, and `prediction_reason` in diagnostics.
- Do not emit recovery for a single marker dropout. Keep the existing map-transform and map-instance validity gates.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_dual_motion.py tests/poe2_live_terrain/test_marker_association.py
```

Expected: pure tracker tests pass and no existing association behavior regresses.

Commit: `fix: retain bounded dual positions across visual gaps`

### Task 3: Make live worker timing and latest-only behavior observable

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`
- `tests/test_poe2_dual_motion_worker.py`

Add failing tests that assert the frame result exposes candidate and total processing timings and that a slow producer replaces an older pending result rather than queueing it.

Implementation:

- Add `candidate_ms` and `total_worker_ms` to `DualMotionFrameResult`.
- Time only the candidate extraction call separately from combined wall recognition.
- Keep `_offer()` latest-only; do not add an unbounded queue.
- Use the configured cadence as a lower bound and adaptive backoff only when processing exceeds cadence; never busy-spin.
- Add rate-limited diagnostic emission for completed frames, dropped results, processing EMA, and effective FPS. Diagnostics must not be emitted for every frame from the GUI thread.

Verify:

```powershell
pytest -q tests/test_poe2_dual_motion_worker.py
```

Expected: all worker lifecycle, cleanup, generation, and latest-only tests pass.

Commit: `perf: instrument latest-only dual frame worker`

### Task 4: Keep UI rendering out of the control cadence

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_mixin.py`
- `tests/test_poe2_capture_test_page.py`

Add a regression test that drains multiple worker results and verifies preview rendering is throttled while state consumption remains latest-only.

Implementation:

- Continue consuming every newest state available to the control/follow runtime.
- Keep preview rendering at the existing low preview rate; do not render a full map for each worker result.
- Record render duration separately and never use render failure to mark a tracking frame as invalid.
- Preserve generation checks and retired-worker references until their terminal signal is delivered.

Verify:

```powershell
pytest -q tests/test_poe2_capture_test_page.py -k "dual_motion or worker"
```

Expected: UI lifecycle tests pass and no worker callback is applied after generation changes.

Commit: `perf: decouple dual preview rendering from tracking cadence`

### Task 5: Add offline replay coverage for recovery and frame-rate behavior

Files:

- `tests/poe2_live_terrain/test_dual_follow_replay.py` (create)
- `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`
- `ITERATION_LOG.md`

Create deterministic replay fixtures with: stationary first frame, normal movement, one noisy marker frame, two missing-marker frames, recovery frame, and slow-processing timestamps.

Assertions:

- one first-frame capture is used;
- a single bad frame does not request global recovery or release output;
- predicted positions remain finite and bounded;
- a recovered visual frame returns to visual tracking;
- old frames are discarded and effective processing statistics are recorded;
- map instance changes still force recovery.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_dual_follow_replay.py
python -m compileall -q src
git diff --check
```

Commit: `test: cover single-frame follow recovery replay`

### Task 6: Run focused and full regression checks, then update the checkpoint

Files:

- `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`
- `ITERATION_LOG.md`

Run:

```powershell
pytest -q tests/test_poe2_dual_motion_worker.py tests/poe2_live_terrain/test_dual_motion.py tests/poe2_live_terrain/test_dual_follow_replay.py
pytest -q tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_first_frame.py
python -m compileall -q src
git diff --check
```

Record exact counts, elapsed stage timings from replay, unresolved risks, and the next real-game test boundary. Do not perform real input or game-window testing without explicit user authorization in a later step.

Commit: `docs: record single-frame follow verification`
