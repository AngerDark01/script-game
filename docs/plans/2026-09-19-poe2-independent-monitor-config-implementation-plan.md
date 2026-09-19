# PoE2 独立监控配置实现计划

## Goal

在现有主窗口中为 PoE2 增加完全独立的监控配置窗口和配置运行时边界，同时复用通用截图、区域选择和坐标能力，不依赖页面 1、2 的导航业务对象。

## Architecture Overview

- `MainWindow` 继续注册 `Poe2LiveTerrainPage`，本阶段不拆新的产品启动器。
- PoE2 新增自己的 `Poe2MonitorConfig`、配置存储、区域绑定和配置窗口。
- 通用的监控矩形和截图接口放在基础/适配层；不得把 PoE2 或导航术语放进通用模块。
- `Poe2LiveTerrainPage` 只组合 PoE2 服务和 PoE2 配置窗口，不读取 `NavConfig`、`NavigationModeWidget` 或导航页实例。
- 配置运行中锁定；停止运行后才允许编辑。当前定位服务尚未实现，因此先建立显式的 runtime-active 契约。
- 地图快照仍由现有内存服务管理，监控配置单独持久化到 PoE2 配置目录。

## Tech Stack

- Python `>=3.11`
- PySide6
- NumPy/OpenCV 现有截图与识别依赖
- pytest，项目配置见 `pyproject.toml`

## Task 1: Add a generic monitor-binding contract

Files:

- `src/auto_modules/core/spatial/monitor_binding.py`
- `src/auto_modules/core/spatial/__init__.py`
- `tests/test_monitor_binding.py`

### TDD

1. Add the failing tests:

```python
from dataclasses import FrozenInstanceError

import pytest

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


def test_capture_rect_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="positive"):
        CaptureRect(left=0, top=0, width=0, height=100)


def test_monitor_binding_is_immutable_and_serializable():
    binding = MonitorBinding(
        rect=CaptureRect(left=10, top=20, width=320, height=240),
        screen_id="primary",
        coordinate_space="physical_desktop",
        dpi_scale_x=1.0,
        dpi_scale_y=1.0,
        player_marker_position=(160, 120),
    )
    assert binding.rect.as_dict() == {"left": 10, "top": 20, "width": 320, "height": 240}
    assert binding.as_dict()["screen_id"] == "primary"
    with pytest.raises(FrozenInstanceError):
        binding.screen_id = "secondary"
```

2. Verify the tests fail:

```powershell
python -m pytest tests/test_monitor_binding.py -q
# Expected: collection error because monitor_binding is not implemented.
```

3. Implement the smallest contract:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("capture rectangle dimensions must be positive")

    def as_dict(self) -> dict[str, int]:
        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
        }


@dataclass(frozen=True)
class MonitorBinding:
    rect: CaptureRect
    screen_id: str = "primary"
    coordinate_space: str = "physical_desktop"
    dpi_scale_x: float = 1.0
    dpi_scale_y: float = 1.0
    player_marker_position: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not self.screen_id:
            raise ValueError("screen_id is required")
        if self.dpi_scale_x <= 0 or self.dpi_scale_y <= 0:
            raise ValueError("dpi scales must be positive")

    def as_dict(self) -> dict:
        return {
            "rect": self.rect.as_dict(),
            "screen_id": self.screen_id,
            "coordinate_space": self.coordinate_space,
            "dpi_scale_x": float(self.dpi_scale_x),
            "dpi_scale_y": float(self.dpi_scale_y),
            "player_marker_position": list(self.player_marker_position)
            if self.player_marker_position is not None
            else None,
        }
```

Export both symbols from `src/auto_modules/core/spatial/__init__.py` without importing any UI or PoE2 module.

4. Verify:

```powershell
python -m pytest tests/test_monitor_binding.py -q
# Expected: 2 passed.
```

5. Commit: `feat: add generic monitor binding contract`

## Task 2: Add independent PoE2 monitor configuration and storage

Files:

- `src/auto_modules/adapters/poe2_live_terrain/monitor_config.py`
- `tests/poe2_live_terrain/test_monitor_config.py`

### TDD

1. Add failing tests:

```python
from auto_modules.adapters.poe2_live_terrain.monitor_config import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
)


def test_missing_file_returns_independent_defaults(tmp_path):
    config = Poe2MonitorConfigStore(tmp_path).load()
    assert config.binding is None
    assert config.search_radius == 96


def test_save_and_load_round_trip(tmp_path):
    store = Poe2MonitorConfigStore(tmp_path)
    original = Poe2MonitorConfig(search_radius=144, match_threshold=0.82)
    path = store.save(original)
    assert path.name == "monitor.json"
    assert store.load() == original


def test_invalid_json_does_not_import_navigation_config(tmp_path):
    path = tmp_path / "monitor.json"
    path.write_text('{"monitor_region": {"left": 1}}', encoding="utf-8")
    config = Poe2MonitorConfigStore(tmp_path).load()
    assert config.binding is None
```

2. Verify failure:

```powershell
python -m pytest tests/poe2_live_terrain/test_monitor_config.py -q
# Expected: collection error because monitor_config is not implemented.
```

3. Implement a JSON-backed PoE2-only store. It must use an atomic temporary file and never read `NavConfig` or navigation paths. The model should contain `binding`, `search_radius`, `match_threshold`, and `sample_interval_ms`, validate positive values, and serialize through `MonitorBinding.as_dict()`.

4. Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_monitor_config.py -q
# Expected: 3 passed.
```

5. Commit: `feat: add isolated poe2 monitor config store`

## Task 3: Add a generic region capture adapter for PoE2

Files:

- `src/auto_modules/adapters/poe2_live_terrain/monitor_source.py`
- `tests/poe2_live_terrain/test_monitor_source.py`

### TDD

1. Add failing tests:

```python
import numpy as np

from auto_modules.adapters.poe2_live_terrain.monitor_source import MonitorFrameSource
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


class FakeCapture:
    def __init__(self):
        self.calls = []

    def capture(self, x, y, width, height):
        self.calls.append((x, y, width, height))
        return np.zeros((height, width, 3), dtype=np.uint8)


def test_capture_uses_poe2_binding_only():
    backend = FakeCapture()
    source = MonitorFrameSource(backend)
    binding = MonitorBinding(CaptureRect(5, 7, 32, 24))
    frame = source.capture(binding)
    assert frame.shape == (24, 32, 3)
    assert backend.calls == [(5, 7, 32, 24)]
```

2. Verify failure:

```powershell
python -m pytest tests/poe2_live_terrain/test_monitor_source.py -q
# Expected: collection error because monitor_source is not implemented.
```

3. Implement `MonitorFrameSource` with constructor injection of the existing capture backend and one method:

```python
class MonitorFrameSource:
    def __init__(self, capture_backend) -> None:
        self._capture_backend = capture_backend

    def capture(self, binding: MonitorBinding):
        rect = binding.rect
        return self._capture_backend.capture(
            rect.left,
            rect.top,
            rect.width,
            rect.height,
        )
```

Do not add a PoE2 branch to `SquareScreenCapture` and do not read `AppContext.monitor_region`.

4. Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_monitor_source.py -q
# Expected: 1 passed.
```

5. Commit: `feat: add poe2 monitor frame source`

## Task 4: Add the independent PoE2 monitor configuration dialog

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/monitor_dialog.py`
- `tests/test_poe2_monitor_dialog.py`

### TDD

1. Add a Qt test that constructs the dialog with a fake store and verifies it does not receive or mutate `NavConfig`:

```python
import pytest

pytest.importorskip("PySide6")

from auto_modules.ui.modes.poe2_live_terrain.monitor_dialog import Poe2MonitorConfigDialog


def test_dialog_uses_poe2_config_and_emits_save(qtbot):
    dialog = Poe2MonitorConfigDialog(config=make_config(), parent=None)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "PoE2 监控配置"
    assert dialog.search_radius_spin.value() == 96
```

2. Verify the test fails because the dialog and fixture do not exist.

3. Implement a non-modal `QDialog` with:

- `config_saved = Signal(object)`;
- a region-selection button that consumes the generic overlay result;
- read-only labels for current rectangle and player marker;
- `search_radius_spin`, `match_threshold_spin`, and `sample_interval_spin`;
- Save/Cancel buttons;
- `set_editable(enabled: bool)` for runtime locking;
- no import from `ui.modes.navigation` and no `NavConfig` field.

4. Verify:

```powershell
python -m pytest tests/test_poe2_monitor_dialog.py -q
# Expected: 1 passed.
```

5. Commit: `feat: add poe2 monitor config dialog`

## Task 5: Wire the dialog into the PoE2 page without navigation coupling

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `tests/test_poe2_live_terrain_page.py`

### TDD

1. Add failing behavior tests:

```python
def test_page_opens_its_own_monitor_dialog(qtbot, service, config_store):
    page = Poe2LiveTerrainPage(service=service, config_store=config_store)
    qtbot.addWidget(page)
    page.open_monitor_config()
    assert page.monitor_dialog.isVisible()
    assert page.monitor_dialog.config_store is config_store


def test_page_does_not_require_navigation_page(qtbot, service, config_store):
    page = Poe2LiveTerrainPage(service=service, config_store=config_store)
    qtbot.addWidget(page)
    assert page.nav_config is None
```

2. Verify the new tests fail against the current page.

3. Add a `monitor_config` button, lazy dialog creation, an injected `Poe2MonitorConfigStore`, and a `runtime_active`/`set_runtime_active()` contract. The page must retain its current terrain capture flow. Configuration must be loaded from the PoE2 store, and `set_runtime_active(True)` must call `dialog.set_editable(False)`.

4. Verify focused page tests:

```powershell
python -m pytest tests/test_poe2_live_terrain_page.py -q
# Expected: existing page tests plus the new tests pass.
```

5. Commit: `feat: wire isolated poe2 monitor dialog into page`

## Task 6: Inject PoE2 configuration from the main window and preserve shutdown behavior

Files:

- `src/auto_modules/ui/main_window.py`
- `tests/test_main_window_poe2_terrain_page.py`

### TDD

1. Add a test that constructs `MainWindow` with the existing debug archive and asserts the PoE2 page receives a PoE2 config store rooted below the PoE2 data directory, without constructing or reading `NavConfig` for the page.

2. Verify the test fails because the current constructor only injects the terrain service.

3. Instantiate `Poe2MonitorConfigStore(data_root() / "poe2_live_terrain")` in the PoE2 composition block and pass it to `Poe2LiveTerrainPage`. Keep the current page index and existing shutdown call unchanged. Do not remove or alter page 1/2 behavior.

4. Verify:

```powershell
python -m pytest tests/test_main_window_poe2_terrain_page.py tests/test_poe2_live_terrain_page.py -q
# Expected: all focused UI tests pass.
python -m pytest tests/poe2_live_terrain tests/test_main_window_poe2_terrain_page.py tests/test_poe2_live_terrain_page.py -q
# Expected: all PoE2 tests pass.
```

5. Commit: `feat: inject isolated poe2 monitor config`

## Task 7: Verify architecture and document the boundary

Files:

- `docs/plans/2026-09-19-poe2-independent-monitor-config-design.md`
- `README.md` (only if the existing PoE2 section needs the configuration workflow)
- `tests/test_poe2_live_terrain_page.py` (only if a missing boundary assertion is found)

Verification:

```powershell
python -m pytest tests/test_monitor_binding.py tests/poe2_live_terrain tests/test_poe2_monitor_dialog.py tests/test_poe2_live_terrain_page.py tests/test_main_window_poe2_terrain_page.py -q
python -m compileall -q src tests tools packaging
git diff --check
```

Expected: all focused tests pass, compilation succeeds, and `git diff --check` reports no whitespace errors. Review imports to confirm no PoE2 monitor module imports `NavigationModeWidget`, `NavConfig`, or `NavParametersDialog`.

Commit: `test: verify poe2 monitor boundary`

## Out of Scope for This Plan

- First-frame global localization.
- Local re-localization and phase displacement.
- Player marker rendering on the terrain map.
- Automatic following.
- Xbox, LAN, Host, or real input behavior.
- Real PoE2 desktop capture tests in the default test suite.
