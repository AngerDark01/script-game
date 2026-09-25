# PoE2 导航兼容实时跟踪实施计划

## Goal

把 PoE2 正式实验定位改为“首帧/恢复使用内存锚点局部形状注册，正常运行复用导航模式的多帧位移预测，并用局部形状纠偏”的完整链路。

## Architecture Overview

- `AnchoredAbsoluteRegistrar` 继续负责首帧和恢复，不改为全图搜索。
- 增加通用墙体归一化能力，使视觉 `wall_mask` 与内存 terrain boundary 使用同一形状表示。
- `VisualLocalTracker` 以 `estimate_phase_displacement()` 为正常主路径。
- 位移成功时直接更新位置；形状 matcher 只在低质量、需要纠偏或位移失败时使用。
- 每个 recovery revision 最多读取一次内存；恢复失败后停止自动 tick，等待显式重试。
- 不修改第一页绘图模式，不执行任何输入设备或网络副作用。

## Tech Stack

- Python 3.11
- NumPy
- OpenCV
- pytest
- 现有 Qt 页面和 PoE2 hybrid session/controller

## Task 1: 建立导航兼容跟踪的失败测试

Files:

- `tests/poe2_live_terrain/test_navigation_compatible_tracking.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`

先增加一个使用两个已知平移帧的测试。测试中的地图 reference 使用现有 fake matcher，phase displacement 使用真实 `estimate_phase_displacement`。

Add failing test:

```python
def test_tracker_prefers_frame_to_frame_displacement_before_shape_match():
    previous = make_frame(make_wall_pattern(), frame_id=1)
    current = make_frame(shift_mask(previous.wall_mask, (4, -3)), frame_id=2)
    matcher = RecordingMatcher(valid=True, origin=(100.0, 100.0))
    tracker = VisualLocalTracker(matcher, search_radius=12)
    registration = make_registration(
        position=(200.0, 180.0),
        transform=SimilarityTransform2D(
            angle_degrees=0.0,
            reflect_horizontal=False,
            scale=1.0,
            translation=(100.0, 100.0),
        ),
    )

    result = tracker.track(
        current,
        reference=object(),
        previous_frame=previous,
        previous=registration,
    )

    assert result is not None
    assert result.result.source == "visual_f2f"
    assert result.result.position == pytest.approx((196.0, 183.0), abs=1.0)
    assert matcher.calls == []
```

Verify the test fails before implementation:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_navigation_compatible_tracking.py::test_tracker_prefers_frame_to_frame_displacement_before_shape_match -q
# Expected: FAIL because current VisualLocalTracker discards previous_frame and returns visual_local.
```

Do not change production code in this task. This test locks the missing behavior and the expected source label.

## Task 2: Add canonical wall representation

Files:

- `src/auto_modules/core/localization/canonical_wall.py`
- `tests/test_canonical_wall.py`

Implement only pure array functions. The representation must be binary, single-channel, uint8, and independent of PoE2/UI terminology.

Add:

```python
from __future__ import annotations

import cv2
import numpy as np


def canonical_wall_mask(
    value: np.ndarray,
    *,
    close_kernel_size: int = 3,
    open_kernel_size: int = 1,
    min_component_area: int = 0,
) -> np.ndarray:
    """Normalize wall-like input to a stable binary shape representation."""
    array = np.asarray(value)
    if array.size == 0 or array.ndim not in (2, 3):
        raise ValueError("wall input must be a non-empty 2D or 3D array")
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    result = np.where(array > 0, 255, 0).astype(np.uint8)
    close_size = int(close_kernel_size)
    if close_size > 1:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (close_size, close_size)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
    open_size = int(open_kernel_size)
    if open_size > 1:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (open_size, open_size)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
    if int(min_component_area) > 0:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(result, 8)
        keep = np.zeros_like(result)
        for label in range(1, count):
            if int(stats[label, cv2.CC_STAT_AREA]) >= int(min_component_area):
                keep[labels == label] = 255
        result = keep
    return result


def canonical_boundary_from_walkable(
    walkable: np.ndarray,
    explored: np.ndarray | None = None,
    *,
    close_kernel_size: int = 3,
) -> np.ndarray:
    """Convert walkable/explored layers to the same thin boundary form."""
    walk = np.asarray(walkable).astype(bool)
    if walk.ndim != 2 or walk.size == 0:
        raise ValueError("walkable must be a non-empty 2D array")
    known = np.ones_like(walk, dtype=bool) if explored is None else np.asarray(explored).astype(bool)
    if known.shape != walk.shape:
        raise ValueError("explored shape must match walkable shape")
    mask = np.where(walk & known, 255, 0).astype(np.uint8)
    mask = canonical_wall_mask(mask, close_kernel_size=close_kernel_size)
    padded = np.pad(mask > 0, 1, mode="constant", constant_values=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    eroded = cv2.erode(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    return np.where((dilated & ~eroded) & known, 255, 0).astype(np.uint8)
```

Tests must cover: input immutability, 3D conversion, close/open behavior, small-component removal, explored masking, and mismatched shapes.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_canonical_wall.py -q
# Expected: all canonical wall tests pass.
```

## Task 3: Reuse canonical wall representation in terrain references

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`
- `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py`
- `tests/test_poe2_composition.py`

Replace the local boundary implementation used for matching with `canonical_boundary_from_walkable`. Keep the existing `TerrainReference` contract unchanged. Preserve `reference_boundary_layer(reference)` as an adapter name for callers, but make it delegate to the common function.

Add the following regression assertion:

```python
def test_reference_boundary_and_visual_mask_use_same_binary_contract():
    reference = make_reference_with_walkable_shape()
    terrain_mask = reference_boundary_layer(reference)
    visual_mask = canonical_wall_mask(make_visual_wall_from_same_shape())
    assert terrain_mask.dtype == np.uint8
    assert visual_mask.dtype == np.uint8
    assert terrain_mask.ndim == visual_mask.ndim == 2
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_absolute_registrar.py tests/test_poe2_composition.py -q
# Expected: existing registrar/composition tests plus the representation contract pass.
```

## Task 4: Add a reusable displacement transform helper

Files:

- `src/auto_modules/core/localization/displacement.py`
- `tests/test_displacement.py`

Implement a pure helper that converts a local minimap shift into reference-map coordinates using the already-known similarity transform. Reflection must be applied before rotation, and scale must be applied after the orientation transform.

Add:

```python
from __future__ import annotations

import math


def transform_local_displacement(
    shift: tuple[float, float],
    *,
    angle_degrees: float,
    reflect_horizontal: bool,
    scale: float,
) -> tuple[float, float]:
    x, y = float(shift[0]), float(shift[1])
    if not all(math.isfinite(value) for value in (x, y, angle_degrees, scale)):
        raise ValueError("displacement values must be finite")
    if scale <= 0:
        raise ValueError("scale must be positive")
    if reflect_horizontal:
        x = -x
    radians = math.radians(float(angle_degrees))
    cosine, sine = math.cos(radians), math.sin(radians)
    return (
        scale * (cosine * x - sine * y),
        scale * (sine * x + cosine * y),
    )
```

Tests must cover identity, 90-degree rotation, reflection, scale, and invalid values.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_displacement.py -q
# Expected: all displacement transform tests pass.
```

## Task 5: Add a bounded frame-to-frame displacement adapter

Files:

- `src/auto_modules/core/localization/frame_displacement.py`
- `tests/test_frame_displacement.py`

Wrap `estimate_phase_displacement()` with explicit quality and jump gates. The adapter must return a typed result instead of making state-machine decisions.

Add:

```python
from dataclasses import dataclass
import math
import numpy as np

from auto_modules.core.vision.phase_displacement import estimate_phase_displacement


@dataclass(frozen=True)
class FrameDisplacement:
    shift: tuple[float, float] | None
    quality: float
    distance: float
    accepted: bool
    reason: str


def estimate_bounded_displacement(
    previous: np.ndarray,
    current: np.ndarray,
    *,
    min_quality: float = 0.20,
    max_shift: float = 40.0,
    dead_zone: float = 0.2,
) -> FrameDisplacement:
    shift, quality = estimate_phase_displacement(previous, current, dead_zone=dead_zone)
    quality = float(quality)
    if shift is None:
        return FrameDisplacement(None, quality, 0.0, False, "phase_failed")
    dx, dy = float(shift[0]), float(shift[1])
    distance = float(math.hypot(dx, dy))
    if quality < float(min_quality):
        return FrameDisplacement((dx, dy), quality, distance, False, "low_quality")
    if distance > float(max_shift) and quality < 0.75:
        return FrameDisplacement((dx, dy), quality, distance, False, "large_shift")
    return FrameDisplacement((dx, dy), quality, distance, True, "accepted")
```

Tests must use synthetic translated patterns and cover accepted movement, low quality, large shift, and invalid/empty input behavior inherited from `estimate_phase_displacement`.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_frame_displacement.py -q
# Expected: all displacement gate tests pass.
```

## Task 6: Implement displacement-first `VisualLocalTracker`

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`
- `tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py`
- `tests/poe2_live_terrain/test_navigation_compatible_tracking.py`

Change `VisualLocalTracker.track()` in this order:

1. Canonicalize `previous_frame.wall_mask` and `frame.wall_mask`.
2. Call `estimate_bounded_displacement()`.
3. Transform the local shift through `previous.transform` using `transform_local_displacement()`.
4. Update position with the navigation sign convention: `previous.position - global_shift`.
5. Reject an implausible global jump.
6. Return `source="visual_f2f"` without calling the matcher when displacement is accepted.
7. If displacement is rejected, run the existing matcher around the predicted/previous origin with a bounded radius and return `source="visual_local"` only when accepted.
8. If both paths fail, return `None` so the controller enters recovery.

The tracker must no longer contain `del previous_frame`.

Add tests:

```python
def test_f2f_success_updates_position_without_local_match(): ...
def test_f2f_shift_is_rotated_and_reflected_before_global_update(): ...
def test_low_quality_f2f_falls_back_to_bounded_shape_match(): ...
def test_failed_f2f_and_shape_match_returns_none(): ...
def test_tracker_never_requests_full_map_search(): ...
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py tests/poe2_live_terrain/test_navigation_compatible_tracking.py -q
# Expected: all tracker tests pass; successful movement reports visual_f2f.
```

## Task 7: Wire canonical masks and previous-frame ownership through the session

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/models.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`
- `tests/poe2_live_terrain/test_hybrid_localization_session.py`
- `tests/poe2_live_terrain/test_hybrid_localization_integration.py`

Keep raw evidence available for diagnostics, but ensure every `HybridFrame` consumed by the tracker exposes the same canonical wall representation. Do not put file I/O or PoE2-specific rules in `HybridFrame`.

Add a session integration assertion:

```python
def test_session_passes_consecutive_frames_to_tracker_for_f2f():
    session, tracker = make_session_with_recording_tracker()
    session.start()
    session.tick(now_ms=100)
    session.tick(now_ms=133)
    assert tracker.previous_frame_ids == [(1, 2)]
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_localization_session.py tests/poe2_live_terrain/test_hybrid_localization_integration.py -q
# Expected: session order remains capture -> evidence -> update, with previous frame available.
```

## Task 8: Preserve and test recovery semantics

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`
- `tests/poe2_live_terrain/test_hybrid_localization_controller.py`
- `tests/poe2_live_terrain/test_hybrid_product_runtime.py`

Do not alter the one-read-per-recovery-revision rule. Update diagnostics to distinguish:

- `visual_f2f_success`
- `visual_f2f_rejected`
- `visual_shape_correction_success`
- `visual_local_tracking_failed`
- `recovery_anchor_success`
- `recovery_anchor_failed`

Add/retain tests for:

```python
def test_successful_f2f_never_reads_memory_again(): ...
def test_f2f_failure_allows_one_recovery_read(): ...
def test_recovery_failure_stops_future_reads(): ...
def test_retry_recovery_opens_exactly_one_new_read(): ...
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_localization_controller.py tests/poe2_live_terrain/test_hybrid_product_runtime.py -q
# Expected: all read-count and state-transition tests pass.
```

## Task 9: Add diagnostics and replay metrics

Files:

- `src/auto_modules/features/poe2/live_terrain/hybrid_failure_archive.py`
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`
- `tests/poe2_live_terrain/test_hybrid_failure_archive.py`
- `tools/debug/poe2_live_terrain_localization_probe.py`

For each frame record structured, rate-limited diagnostics:

- frame id and timestamps;
- mode/source;
- f2f shift, quality and rejection reason;
- local shape error and margin when used;
- angle, reflection, scale and transformed global displacement;
- memory read count and recovery revision;
- frame elapsed time.

Failure archives must retain `raw.png`, `processed.png`, `feature.png`, `wall_mask.png`, `terrain.png`, and `localization_failure.json`. Successful replay mode should additionally emit a compact `tracking_metrics.json` with accepted f2f count, local correction count, recovery count, mean/max elapsed time, and position samples.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_failure_archive.py -q
& D:/ACloud/.venv/Scripts/python.exe tools/debug/poe2_live_terrain_localization_probe.py --help
# Expected: archive schema tests pass and the probe remains importable.
```

## Task 10: Full focused regression and documentation sync

Files:

- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Run the complete focused suite:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest `
  tests/poe2_live_terrain `
  tests/test_poe2_composition.py `
  tests/test_poe2_live_terrain_monitoring.py `
  tests/test_poe2_live_terrain_page.py `
  tests/test_poe2_live_terrain_presenter.py `
  tests/test_poe2_live_terrain_presenter_position.py `
  tests/test_poe2_monitor_dialog.py `
  tests/test_main_window_poe2_terrain_page.py `
  tests/test_architecture_boundaries.py -q
& D:/ACloud/.venv/Scripts/python.exe -m compileall -q src/auto_modules
git diff --check
```

Expected: all focused tests pass, compileall exits successfully, and `git diff --check` produces no output.

Update the current-state and iteration documents with:

- the selected navigation-compatible design;
- exact normal/fallback/recovery call chains;
- read-count guarantees;
- replay and real-device acceptance results;
- unresolved map-instance or multi-player limitations.

## Execution order and checkpoints

Tasks must be executed in order. After Tasks 2, 5, 6, 8, and 10 stop for a review checkpoint. No real game input, network synchronization, Xbox, keyboard, or mouse action is part of any checkpoint.

Each task is expected to follow TDD:

1. Add the smallest failing test.
2. Run that test and record the failure.
3. Implement only the task's contract.
4. Run the focused test and the nearest regression set.
5. Commit the task as an independent checkpoint.
