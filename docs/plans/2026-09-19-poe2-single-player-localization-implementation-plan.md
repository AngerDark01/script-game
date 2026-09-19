# PoE2 单人人物实时定位与轨迹验证计划

## Goal

在现有主窗口的 PoE2 页面中，接入独立的小地图监控，使用通用引擎能力完成首帧全局定位、后续局部跟踪，并在已加载的完整地形图上显示单人人物的真实位置和移动轨迹。

## Architecture Overview

```text
PoE2 实验业务
  terrain reference / player policy / runtime composition
        -> 通用定位引擎
           observations / global-local registration / recovery / trajectory
                -> 基础能力
                   capture / OpenCV / coordinate transforms
```

- PoE2 规则和组合代码暂放在 `tools/experiments/poe2_live_terrain/`。
- 可复用的定位契约和状态机放在 `src/auto_modules/core/`，不得导入 PoE2 或导航页。
- UI 通过注入协议调用 runtime，不在 UI 中复制识别或匹配算法。
- 当前只做单人定位和轨迹显示。
- 不实现目标点、路线计算、路线显示、自动跟随或真实输入。
- 引擎契约预留 0..N 个候选实体，为后续多人角色选择提供扩展点；多人选择策略本阶段不实现。

## Tech Stack

- Python `>=3.11`
- NumPy/OpenCV
- PySide6
- pytest
- 现有 `SquareScreenCapture`、`MapRuntime`、`LocalMapMatcher`、`phase_tracker`、`FrameRegistration`、`LocalizationResult`

## Task 1: Add generic entity-observation contracts

Files:

- `src/auto_modules/core/localization/observations.py`
- `src/auto_modules/core/localization/__init__.py`
- `tests/test_localization_observations.py`

Purpose: make the engine able to represent zero, one, or many observed entities without using the word “player” in the contract.

### TDD

1. Add failing tests:

```python
import pytest

from auto_modules.core.localization.observations import (
    ObservationCandidate,
    ObservationFrame,
)


def test_candidate_requires_finite_local_position_and_confidence():
    with pytest.raises(ValueError):
        ObservationCandidate(local_position=(1, 2), confidence=1.2)


def test_observation_keeps_all_candidates_and_selected_identity():
    first = ObservationCandidate(
        local_position=(12, 18),
        confidence=0.91,
        identity_hint="primary",
    )
    second = ObservationCandidate(local_position=(80, 42), confidence=0.77)
    frame = ObservationFrame(
        captured_at_ms=100,
        candidates=(first, second),
        selected_index=0,
        source="synthetic",
    )
    assert frame.selected.local_position == (12, 18)
    assert len(frame.candidates) == 2
    assert frame.is_fresh is True
```

2. Verify failure:

```powershell
python -m pytest tests/test_localization_observations.py -q
# Expected: collection error because observations.py is not implemented.
```

3. Implement frozen dataclasses:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class ObservationCandidate:
    local_position: tuple[int, int]
    confidence: float
    identity_hint: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.local_position) != 2:
            raise ValueError("local_position must contain two values")
        if not all(isfinite(float(value)) for value in self.local_position):
            raise ValueError("local_position must be finite")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "evidence", dict(self.evidence))


@dataclass(frozen=True)
class ObservationFrame:
    captured_at_ms: int
    candidates: tuple[ObservationCandidate, ...] = ()
    selected_index: int | None = None
    source: str = ""
    stale: bool = False

    @property
    def selected(self) -> ObservationCandidate | None:
        if self.selected_index is None:
            return None
        if not 0 <= self.selected_index < len(self.candidates):
            return None
        return self.candidates[self.selected_index]

    @property
    def is_fresh(self) -> bool:
        return not self.stale and self.selected is not None
```

4. Export the contracts from `core.localization` without importing UI or PoE2.

5. Verify:

```powershell
python -m pytest tests/test_localization_observations.py -q
# Expected: 2 passed.
```

6. Commit: `feat: add generic localization observation contract`

## Task 2: Add a generic global/local localization state machine

Files:

- `src/auto_modules/core/localization/map_localizer.py`
- `tests/test_map_localizer.py`

Purpose: move the global-first/local-follow/recovery policy into the engine, while injecting recognition and matching operations from the business adapter.

### Required behavior

The state machine must expose these modes:

```text
NEED_GLOBAL
LOCAL_TRACKING
RECOVERY_REQUIRED
STOPPED
```

Rules:

- The first valid frame calls the injected global matcher.
- A localized frame first tries phase prediction and a bounded local matcher.
- A local failure returns an invalid result and changes the next state to `RECOVERY_REQUIRED`.
- A local failure must not silently call the global matcher again in the same frame.
- The next frame in recovery performs global matching.
- A result includes source (`global`, `phase`, `local`, `failed`), confidence, position, and metadata.

### TDD

1. Add tests with fake matchers:

```python
from auto_modules.core.localization.map_localizer import LocalizationMode, MapLocalizer


def test_first_frame_uses_global_matcher():
    calls = []
    localizer = MapLocalizer(
        global_match=lambda frame: calls.append("global") or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: calls.append("local") or ((101.0, 81.0), 0.8),
        phase_predict=lambda previous, current: None,
    )
    result = localizer.update("frame-1")
    assert result.position == (100.0, 80.0)
    assert result.source == "global"
    assert calls == ["global"]
    assert localizer.mode is LocalizationMode.LOCAL_TRACKING


def test_local_failure_requires_global_recovery_on_next_frame():
    calls = []
    localizer = MapLocalizer(
        global_match=lambda frame: calls.append("global") or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: calls.append("local") or None,
        phase_predict=lambda previous, current: (101.0, 80.0),
    )
    localizer.update("frame-1")
    failed = localizer.update("frame-2")
    assert failed.position is None
    assert failed.source == "failed"
    assert calls == ["global", "local"]
    assert localizer.mode is LocalizationMode.RECOVERY_REQUIRED
    recovered = localizer.update("frame-3")
    assert recovered.source == "global"
    assert calls == ["global", "local", "global"]
```

2. Verify failure:

```powershell
python -m pytest tests/test_map_localizer.py -q
# Expected: collection error because map_localizer.py is not implemented.
```

3. Implement `MapLocalizer` using injected callables and the existing `LocalizationResult` contract. Do not import `NavigationCore`, `NavConfig`, `Poe2Snapshot`, or UI classes. Keep the phase prediction hook optional so the engine remains useful for static/global-only consumers.

4. Verify:

```powershell
python -m pytest tests/test_map_localizer.py tests/test_localization_result.py -q
# Expected: all focused localization tests pass.
```

5. Commit: `feat: add reusable global-local localization state machine`

## Task 3: Add a generic confirmed trajectory buffer

Files:

- `src/auto_modules/core/localization/trajectory.py`
- `tests/test_localization_trajectory.py`

Purpose: show movement history without treating a stale fallback coordinate as a new observation.

### TDD

1. Add tests:

```python
from auto_modules.core.localization.trajectory import TrajectoryBuffer


def test_only_fresh_confirmed_positions_extend_the_trail():
    trail = TrajectoryBuffer(max_length=3)
    trail.append((10, 10), captured_at_ms=1, confidence=0.9, fresh=True)
    trail.append((11, 10), captured_at_ms=2, confidence=0.8, fresh=True)
    trail.append((99, 99), captured_at_ms=3, confidence=0.1, fresh=False)
    assert trail.points == ((10.0, 10.0), (11.0, 10.0))


def test_reset_clears_all_history():
    trail = TrajectoryBuffer()
    trail.append((1, 2), captured_at_ms=1, confidence=1.0, fresh=True)
    trail.reset()
    assert trail.points == ()
```

2. Verify failure:

```powershell
python -m pytest tests/test_localization_trajectory.py -q
# Expected: collection error because trajectory.py is not implemented.
```

3. Implement a bounded immutable-read trajectory buffer. The buffer stores position, timestamp, confidence, and source internally, but exposes a tuple of points for rendering. It must reject non-finite positions and ignore `fresh=False` observations.

4. Verify:

```powershell
python -m pytest tests/test_localization_trajectory.py -q
# Expected: 2 passed.
```

5. Commit: `feat: add confirmed localization trajectory buffer`

## Task 4: Build the PoE2 terrain reference for localization

Files:

- `tools/experiments/poe2_live_terrain/terrain_reference.py`
- `tests/poe2_live_terrain/test_terrain_reference.py`

Purpose: convert the existing in-memory `TerrainSnapshot` into a reference contract consumed by the generic engine. Do not read pixels back from the display `QPixmap`.

### TDD

1. Add a synthetic snapshot test:

```python
import numpy as np

from tools.experiments.poe2_live_terrain.terrain_reference import build_reference


def test_reference_separates_walkable_cells_from_unknown_and_blocked_cells(snapshot_factory):
    snapshot = snapshot_factory(
        cell_state=np.array([[1, 0, -1], [1, 1, 0]], dtype=np.int8),
        known_mask=np.array([[1, 1, 0], [1, 1, 1]], dtype=np.uint8),
    )
    reference = build_reference(snapshot)
    assert reference.walkable_mask.tolist() == [[True, False, False], [True, True, False]]
    assert reference.wall_layer.dtype == np.uint8
    assert reference.wall_layer[0, 0] == 0
    assert reference.wall_layer[0, 1] == 255
    assert reference.explored_map[0, 2] == 0
```

2. Verify failure:

```powershell
python -m pytest tests/poe2_live_terrain/test_terrain_reference.py -q
# Expected: collection error because terrain_reference.py is not implemented.
```

3. Implement a PoE2-specific reference builder that derives:

- `walkable_mask = (cell_state == 1) & (known_mask > 0)`;
- `wall_layer = 0` for walkable cells and `255` otherwise;
- an explored/known layer with unknown cells excluded;
- immutable arrays and the original terrain dimensions.

The display presenter may use a different palette; it must not be reused as the navigation reference.

4. Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_terrain_reference.py tests/poe2_live_terrain/test_contracts.py -q
# Expected: all reference and snapshot tests pass.
```

5. Commit: `feat: add poe2 terrain localization reference`

## Task 5: Add PoE2 single-player observation policy and calibration

Files:

- `tools/experiments/poe2_live_terrain/calibration.py`
- `tools/experiments/poe2_live_terrain/player_policy.py`
- `tests/poe2_live_terrain/test_player_policy.py`
- `tests/poe2_live_terrain/test_poe2_calibration.py`

### Design

- The recognizer may return multiple generic `ObservationCandidate` values.
- The single-player policy accepts exactly one candidate above the configured threshold.
- A frame with no acceptable candidate is invalid; it must not invent the minimap center.
- The policy keeps candidate evidence and can later be replaced by a multiplayer selector.
- Calibration stores minimap-to-reference scale, axis direction, optional Y inversion, and the configured local player marker position.

### TDD

1. Add tests:

```python
from tools.experiments.poe2_live_terrain.player_policy import select_single_player
from auto_modules.core.localization.observations import ObservationCandidate, ObservationFrame


def test_single_player_policy_selects_only_high_confidence_candidate():
    frame = ObservationFrame(
        captured_at_ms=10,
        candidates=(
            ObservationCandidate((12, 14), 0.88),
            ObservationCandidate((80, 80), 0.35),
        ),
        selected_index=None,
    )
    selected = select_single_player(frame, min_confidence=0.7)
    assert selected.local_position == (12, 14)


def test_single_player_policy_returns_none_without_a_valid_candidate():
    frame = ObservationFrame(captured_at_ms=10, candidates=())
    assert select_single_player(frame, min_confidence=0.7) is None
```

2. Verify failure:

```powershell
python -m pytest tests/poe2_live_terrain/test_player_policy.py tests/poe2_live_terrain/test_poe2_calibration.py -q
# Expected: collection error because the experiment modules are not implemented.
```

3. Implement the single-player policy and a frozen calibration object. Reject invalid scales, zero-sized frames, and non-finite offsets. Do not put the policy in `core`.

4. Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_player_policy.py tests/poe2_live_terrain/test_poe2_calibration.py -q
# Expected: all focused policy/calibration tests pass.
```

5. Commit: `feat: add poe2 single-player selection policy`

## Task 6: Compose the PoE2 live localization runtime

Files:

- `tools/experiments/poe2_live_terrain/runtime.py`
- `tests/poe2_live_terrain/test_localization_runtime.py`

### Runtime contract

The runtime receives injected objects for capture, recognition, reference map, and generic localizer. It returns a typed frame state containing:

- raw minimap frame;
- observation candidates and selected entity;
- localization result;
- latest confirmed position;
- trajectory points;
- mode/source/confidence;
- elapsed timings and failure reason.

The runtime must not call `PathFinder`, `FollowerPlanner`, input adapters, Host, or LAN services.

### TDD

1. Add fake capture/recognizer tests:

```python
def test_first_runtime_tick_reports_global_position_and_updates_trail(runtime):
    state = runtime.tick(now_ms=100)
    assert state.localization.source == "global"
    assert state.position == (100.0, 80.0)
    assert state.trajectory == ((100.0, 80.0),)


def test_failed_player_detection_does_not_append_center_fallback(runtime_with_missing_player):
    state = runtime_with_missing_player.tick(now_ms=100)
    assert state.position is None
    assert state.trajectory == ()
    assert state.failure_reason == "player_not_detected"
```

2. Verify failure:

```powershell
python -m pytest tests/poe2_live_terrain/test_localization_runtime.py -q
# Expected: collection error because runtime.py is not implemented.
```

3. Implement the orchestration using the engine contracts from Tasks 1-3 and the PoE2 adapters from Tasks 4-5. Log one structured line per meaningful state transition and throttle steady-state diagnostics.

4. Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_localization_runtime.py tests/test_map_localizer.py tests/test_localization_trajectory.py -q
# Expected: all runtime and engine localization tests pass.
```

5. Commit: `feat: compose poe2 live single-player localization runtime`

## Task 7: Add the PoE2 UI monitor preview and map marker/trail display

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `tests/test_poe2_live_terrain_page.py`
- `tests/test_poe2_live_terrain_presenter.py`

### Behavior

- Add a live minimap preview separate from the full terrain map.
- Add Start/Stop Monitoring controls.
- Start a `QTimer` only after initialization, terrain capture, and valid PoE2 monitor configuration.
- Update the full-map person marker and trail from runtime state.
- Show mode (`global`, `local`, `recovery`), confidence, local/global position, and frame time.
- Stop the timer and release the last frame when the page is hidden or shut down.
- Do not add target or route controls.

### TDD

1. Add fake-runtime page tests:

```python
def test_start_monitoring_updates_minimap_preview_and_status(qtbot, page, runtime):
    qtbot.addWidget(page)
    page.start_monitoring()
    runtime.emit_state_for_test()
    assert not page.minimap_preview.pixmap().isNull()
    assert "global" in page.localization_status.text()


def test_stop_monitoring_stops_timer_and_clears_live_frame(qtbot, page):
    qtbot.addWidget(page)
    page.start_monitoring()
    page.stop_monitoring()
    assert not page.monitor_timer.isActive()
    assert page.minimap_preview.pixmap().isNull()
```

2. Verify failure:

```powershell
python -m pytest tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py -q
# Expected: new monitor assertions fail before implementation.
```

3. Wire the page to an injected runtime protocol. Keep the current manual terrain initialization/capture behavior. Use the existing `ScalableMapWidget` for the terrain image; add marker/trail rendering through a PoE2 presenter or a narrow generic overlay API only if the current widget cannot update it without copying navigation UI code.

4. Verify:

```powershell
python -m pytest tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py tests/test_main_window_poe2_terrain_page.py -q
# Expected: all focused PoE2 UI tests pass.
```

5. Commit: `feat: display poe2 live minimap and player trail`

## Task 8: Connect the runtime in the current main window and update the checkpoint

Files:

- `src/auto_modules/ui/main_window.py`
- `tests/test_main_window_poe2_terrain_page.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `README.md` (only the current PoE2 capability section)

### Rules

- Keep current mode indices stable.
- Inject the PoE2 experiment runtime from the bootstrap layer; the page itself must not import `tools.experiments`.
- Do not construct or modify `NavConfig`, `NavigationModeWidget`, or navigation runtime state for PoE2 localization.
- Preserve gamepad/LAN lifecycle and shutdown behavior.
- Update the checkpoint only after focused tests pass, recording the exact validation status and any calibration observations.

### Verification

```powershell
python -m pytest tests/test_localization_observations.py tests/test_map_localizer.py tests/test_localization_trajectory.py tests/poe2_live_terrain -q
python -m pytest tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py tests/test_main_window_poe2_terrain_page.py tests/test_navigation_ui_layout.py -q
python -m compileall -q src tests tools packaging
git diff --check
```

Expected: focused engine, experiment, and UI tests pass; compilation succeeds; no new whitespace errors are reported.

Commit: `test: verify poe2 single-player localization integration`

## Manual PoE2 Verification Gate

After Tasks 1-8 pass, perform a manual test with no real input automation:

1. Open the current main window and PoE2 page.
2. Configure the PoE2 monitor region and verify the live preview.
3. Start PoE2, enter an area, initialize the session, and capture terrain.
4. Start monitoring and confirm the first accepted result has `source=global`.
5. Confirm the marker is placed at the real character icon position, not a forced minimap center.
6. Move the character through several directions and compare the marker/trail with the game.
7. Confirm local tracking is used after the first global match.
8. Force a temporary recognition failure and confirm the runtime reports recovery instead of inventing a center position.
9. Stop monitoring and confirm the timer, capture source, and frame cache are released.

Record the following in `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`:

- monitor rectangle and frame size;
- player marker observation characteristics;
- map/minimap scale and axis direction;
- first global match confidence and elapsed time;
- local tracking confidence and elapsed time;
- observed failure/recovery behavior;
- known remaining inaccuracies.

## Explicitly Deferred

- Multiplayer identity selection and simultaneous player trails.
- Route planning and route display.
- Automatic following and movement execution.
- Dynamic obstacle updates.
- Xbox, keyboard, mouse, LAN, Host, and network side effects.
