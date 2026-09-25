# PoE2 一次性地图人物定位显示

## Goal

在 PoE2 实验页点击“获取当前地图”后，读取同一游戏会话中的本地玩家世界坐标，将其转换为 native terrain grid，并把人物点叠加到当前地图展示上；本阶段不做持续跟踪、方向匹配、导航或输入控制。

## Architecture Overview

- 静态 `TerrainSnapshot` 保持不变；人物位置使用独立的 `PlayerPositionSample` 数据契约。
- PoE2 内存读取封装在实验业务的只读适配器中，复用已经验证的 `windows_capture` 布局解析，不把进程地址泄露到 UI。
- 坐标换算是纯函数：`grid_x = world_x * 23 / 250`、`grid_y = world_y * 23 / 250`。
- presenter 接收可选人物点并在地图 `QPixmap` 上绘制固定比例的绿色圆点；无位置时保持原地图输出。
- 一次性读取失败不影响地图快照，页面显示明确的定位状态并记录日志。

## Tech Stack

- Python 3.11+、NumPy、PySide6、现有 `windows_capture.py` 只读 `ReadProcessMemory` 适配器。
- pytest；Qt presenter 测试使用现有 offscreen fixture。

## Implementation Plan

### Task 1: Add the position contract and pure coordinate conversion

Files:

- `src/auto_modules/features/poe2/live_terrain/player_position.py`
- `tests/poe2_live_terrain/test_player_position.py`

Test first:

```python
def test_world_position_converts_to_native_grid():
    sample = PlayerPositionSample.from_world(
        world=(250.0, 500.0, -12.0),
        captured_at="2026-09-22T03:27:56+00:00",
        area_instance="MapFlotsam:BB9AA6DE",
    )
    assert sample.grid == (23.0, 46.0)
    assert sample.world == (250.0, 500.0, -12.0)
```

Implement a frozen dataclass with `world`, `grid`, `captured_at`, and `area_instance`; reject non-finite values and expose `from_world` as the only conversion entry point. Verify with:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_player_position.py
```

Expected: `1 passed`.

### Task 2: Add a read-only PoE2 player position adapter

Files:

- `src/auto_modules/features/poe2/live_terrain/player_position.py`
- `tests/poe2_live_terrain/test_player_position.py`

Test first with a fake reader and resolved layout: the adapter must resolve `Render`, read `+0x138`, return `PlayerPositionSample`, and return a diagnostic failure instead of sending input when `Render` is absent. The production adapter uses `find_process_id`, `resolve_poe2_descriptor`, `ProcessReader`, and `resolve_poe2_layout` from `D:/ACloud/poe2-map-research/windows_capture.py`; it only requests the existing read/query process permissions.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_player_position.py
```

Expected: adapter contract tests pass without requiring a live game.

### Task 3: Compose one-shot capture with the existing experiment page

Files:

- `src/auto_modules/ui/modes/poe2/composition.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/test_poe2_live_terrain_presenter.py`

Test first:

```python
def test_capture_map_draws_player_position_when_source_returns_sample(qtbot):
    page = Poe2CaptureTestPage(service=fake_service, player_position_source=fake_source)
    page.capture_map()
    assert page.player_position_label.text().startswith("人物网格位置：")
```

Extend `present_snapshot` with an optional `player_position`; copy the terrain pixmap, draw a green marker at `sample.grid`, and keep the existing output unchanged when the argument is `None`. Inject a one-shot source into `Poe2CaptureTestPage`; after `service.capture()` succeeds, call it with `snapshot.metadata.instance_id`, update the metadata/status labels, and log `step=test_page.player_position_success` or `step=test_page.player_position_failed`. A failed position read must not clear the freshly captured map.

Verify:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py tests/test_poe2_live_terrain_presenter.py
```

Expected: existing page/presenter tests plus the new one-shot marker tests pass.

### Task 4: Run focused regression and live smoke test

Files: no additional source files.

Verify the focused suite and then run the existing sequence with PoE2 open:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain tests/test_poe2_capture_test_page.py tests/test_poe2_live_terrain_presenter.py
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/poe2-map-research/experiments/live-terrain-preview/live_preview.py init
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/poe2-map-research/experiments/live-terrain-preview/live_preview.py capture
```

Manual acceptance: the experiment page shows the captured map, a green person marker at the memory-derived grid position, the area instance remains consistent, and no Xbox/keyboard/mouse/network action occurs.

