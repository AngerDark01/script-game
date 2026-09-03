# auto_modules 导航 UI 视觉优化实施计划

## Goal

将导航页改造成地图优先、状态清晰、可在约 460–720px 宽度运行的深色战术面板，同时保持现有拼接、定位、路由和事件逻辑不变。

## Architecture Overview

- `gui/main_window.py` 继续负责应用窗口和模式切换。
- `gui/modes/navigation/ui/` 负责导航页布局、工具栏和响应式模式。
- 新增 `gui/theme.py` 作为集中式 Qt 样式入口，避免在各组件内散落样式字符串。
- `gui/modes/navigation/presentation/` 负责地图空状态、状态 HUD 和覆盖物视觉属性。
- 小窗模式隐藏低频工具，核心操作保留在地图上下文附近；完整模式通过可展开工具栏访问全部功能。
- 不修改 `core/` 算法模块。

## Tech Stack

- Python 3.8+
- PySide6 >= 6.6
- Qt Widgets / QGraphicsView
- `unittest` + `QT_QPA_PLATFORM=offscreen` 进行 UI 回归检查

## 实施顺序

### Task 1: 建立导航布局回归测试

Files:

- `tests/test_navigation_ui_layout.py`

先加入失败测试，锁定当前问题：在 1600×1000 下工具栏不能被拉到超过 56px；在 500×700 下窗口宽度不应超过 520px；地图视图必须占据可用剩余高度。

Add:

```python
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


class NavigationUiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.switch_mode(1)
        self.nav = self.window.nav_widget

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_compact_rows_do_not_absorb_vertical_space(self):
        self.window.resize(1600, 1000)
        self.window.show()
        self.app.processEvents()
        for bar in (
            self.nav.map_selector_bar,
            self.nav.navigation_actions_bar,
            self.nav.utility_bar,
            self.nav.status_label,
        ):
            self.assertLessEqual(bar.height(), 56)
        self.assertGreater(self.nav.view.height(), 500)

    def test_compact_window_has_a_realistic_minimum_width(self):
        self.window.resize(500, 700)
        self.window.show()
        self.app.processEvents()
        self.assertLessEqual(self.window.width(), 520)


if __name__ == "__main__":
    unittest.main()
```

Verify the tests fail against the current UI:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_ui_layout -v
# Expected: test_compact_rows_do_not_absorb_vertical_space fails
# Expected: test_compact_window_has_a_realistic_minimum_width fails
```

Commit: `test: lock navigation compact layout regressions`

### Task 2: Add the centralized dark theme tokens

Files:

- `gui/theme.py`
- `gui/main_window.py`
- `tests/test_theme.py`

Add a small pure function and a stylesheet builder so tests do not depend on widget rendering:

```python
COLORS = {
    "window": "#0B1220",
    "surface": "#111C2B",
    "canvas": "#071019",
    "border": "#26364A",
    "text": "#E5EEF7",
    "muted": "#91A4B8",
    "primary": "#38BDF8",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}


def app_stylesheet() -> str:
    return """
    QWidget { color: #E5EEF7; background: #0B1220; font-size: 13px; }
    QToolBar, QFrame[role="surface"] { background: #111C2B; border: 1px solid #26364A; }
    QPushButton { min-height: 34px; padding: 0 12px; border: 1px solid #33465C; border-radius: 6px; background: #172538; }
    QPushButton:hover { border-color: #38BDF8; background: #1D344B; }
    QPushButton:checked, QPushButton[role="primary"] { background: #0E7490; border-color: #38BDF8; }
    QPushButton[role="danger"] { background: #51202A; border-color: #EF4444; }
    QPushButton:disabled { color: #66788D; background: #111A27; border-color: #243244; }
    QComboBox, QSpinBox, QDoubleSpinBox { min-height: 34px; background: #0F1A28; border: 1px solid #33465C; border-radius: 6px; padding: 0 8px; }
    QGraphicsView { background: #071019; border: 1px solid #26364A; }
    """
```

Apply it once in `MainWindow.__init__` with `self.setStyleSheet(app_stylesheet())`, and test that the returned stylesheet contains the required role selectors and palette tokens.

Verify:

```powershell
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_theme -v
# Expected: all theme token tests pass
```

Commit: `feat: add navigation dark visual theme`

### Task 3: Fix compact height allocation and toolbar sizing

Files:

- `gui/modes/navigation/ui/components/toolbars.py`
- `gui/modes/navigation/ui/layout.py`
- `gui/modes/navigation/ui/compact/controller.py`
- `tests/test_navigation_ui_layout.py`

Make each toolbar vertically fixed and let the map consume available height. The compact controller must not cap the map at 380px:

```python
# in _toolbar_widget
from PySide6.QtWidgets import QSizePolicy

widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
widget.setMinimumHeight(40)
widget.setMaximumHeight(40)
```

Use compact mode values:

```python
if self.compact:
    self.owner.view.setMinimumHeight(220)
    self.owner.view.setMaximumHeight(16777215)
else:
    self.owner.view.setMinimumHeight(320)
    self.owner.view.setMaximumHeight(16777215)
```

Set the navigation layout alignment to `Qt.AlignTop` for the fixed controls and retain the map stretch factor of 1. Update the tests from Task 1 and verify both dimensions.

Verify:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_ui_layout -v
# Expected: 2 tests pass
```

Commit: `fix: make compact navigation layout responsive`

### Task 4: Add a map-first empty state

Files:

- `gui/modes/navigation/ui/components/map_view.py`
- `gui/modes/navigation/presentation/map_empty_state.py`
- `gui/modes/navigation/widget.py`
- `tests/test_navigation_empty_state.py`

Add a centered overlay widget in the map view containing a title, one sentence of guidance, and a `加载地图` button. It must be visible when no map item exists and hidden after `set_map_item`.

Required API:

```python
class NavigationMapEmptyState(QFrame):
    load_requested = Signal()

    def set_message(self, title: str, detail: str) -> None: ...
    def set_visible_for_map(self, has_map: bool) -> None: ...
```

Connect `load_requested` to `owner.load_map`, and update the message when loading fails. The state must remain inside the map canvas instead of using the bottom status label as the only feedback.

Verify:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_empty_state -v
# Expected: empty state is visible without a map and hidden after a map item is attached
```

Commit: `feat: add map loading empty state`

### Task 5: Replace the one-line status with a compact HUD

Files:

- `gui/modes/navigation/ui/components/status.py`
- `gui/modes/navigation/presentation/status_presenter.py`
- `gui/modes/navigation/widget.py`
- `tests/test_navigation_status_hud.py`

Build a status row with four labeled values: `地图`, `定位`, `置信度`, `导航/事件`. Keep `build_navigation_status_text` as a compatibility fallback, but render the new labels from structured values so long strings do not push controls off-screen.

The HUD must expose a method equivalent to:

```python
def update_navigation_hud(
    hud,
    *,
    map_name: str,
    localization: str,
    confidence: float | None,
    activity: str,
) -> None: ...
```

Use tabular numeric formatting for coordinates/confidence and set `aria`-equivalent Qt accessible names on the value labels via `setAccessibleName`.

Verify:

```powershell
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_status_hud -v
# Expected: idle, localized, navigating, and failure states render without truncating the primary action
```

Commit: `feat: add navigation status hud`

### Task 6: Reorganize actions for compact mode

Files:

- `gui/modes/navigation/ui/components/toolbars.py`
- `gui/modes/navigation/ui/compact/controller.py`
- `gui/modes/navigation/ui/signals.py`
- `tests/test_navigation_compact_actions.py`

Keep only map selection, primary navigation action, status, and a `更多` button in the narrow layout. Put route editing, parameter panel, event management, sample capture, calibration, and zoom controls in a checkable secondary panel. Preserve the existing widget attributes so lifecycle code and signal wiring remain compatible.

Use short visible labels only when width is below 720px and retain full explanatory text in `setToolTip`. The primary button label must reflect state (`设置起点`, `开始定位`, `自动到出口`, `停止导航`) rather than showing all three phases as equal-weight buttons.

Verify:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_compact_actions -v
# Expected: compact mode keeps core actions visible and moves low-frequency actions into the secondary panel
```

Commit: `feat: prioritize compact navigation actions`

### Task 7: Improve map overlay legibility

Files:

- `gui/modes/navigation/presentation/map_presenter.py`
- `gui/modes/navigation/presentation/route_overlay.py`
- `gui/modes/navigation/presentation/event_overlay.py`
- `tests/test_navigation_overlay_style.py`

Use cosmetic pens for route/marker outlines, add a dark halo behind text labels, and introduce shape semantics:

- player: filled directional marker;
- exit: orange door/ring;
- required point: purple diamond;
- guide point: cyan hollow circle;
- current route: bright yellow/blue line with dark outline.

Add a small in-canvas legend that is shown only when overlays exist. Ensure state text is not color-only and that zooming keeps marker strokes readable.

Verify:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest tests.test_navigation_overlay_style -v
# Expected: overlay pens are cosmetic and all marker classes expose a text/shape distinction
```

Commit: `feat: improve navigation map overlay readability`

### Task 8: Full offscreen visual regression pass

Files:

- `tests/test_navigation_ui_layout.py`
- `tests/test_navigation_empty_state.py`
- `tests/test_navigation_status_hud.py`
- `tests/test_navigation_compact_actions.py`
- `tests/test_navigation_overlay_style.py`

Add a single smoke test that constructs `MainWindow`, switches to navigation mode, renders at 500×700, 800×800, and 1600×1000, and checks that the window, map view, HUD, and empty state are visible without exceptions.

Verify:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m compileall -q core gui main.py
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest discover -s tests -v
# Expected: new UI tests pass; any remaining legacy import errors are documented as pre-existing stale-test failures
```

Commit: `test: add navigation ui visual regression coverage`
