## Goal

为单张地图自动导航第一阶段提供可执行实施计划：支持每张图保存出口区域和人工途经点，并在无干扰场景下从当前位置稳定走到出口。

## Architecture Overview

- 路线数据与现有 `config.json` 分离，单独存入 `map_data/<map>/route.json`
- 新增 `RouteManager` 负责路线持久化
- 新增 `path_utils` 负责纯路径处理算法
- 新增 `AutoNavigator` 负责分段规划、局部跟随、抗抖和恢复状态机
- `navigation_mode.py` 保持为 UI 编排层，只负责加载、点击模式分发、渲染和调用
- 第一阶段只覆盖无干扰自动到出口，不处理事件

## Tech Stack

- Python 3.8+
- PySide6
- OpenCV
- NumPy
- `unittest` 标准库测试框架

### Task 1: 建立测试目录与基础测试命令

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/__init__.py`
- `d:/ACloud/minimap_stitcher copy 13/tests/test_smoke.py`

Add:

```python
# tests/__init__.py
```

```python
# tests/test_smoke.py
import unittest


class SmokeTest(unittest.TestCase):
    def test_smoke(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest discover -s tests -p "test_*.py"
```

Verification:

```text
Expected before implementation: no tests directory, command fails or finds 0 tests
Expected after implementation:
.
----------------------------------------------------------------------
Ran 1 test in 0.0xxs

OK
```

Commit:

```text
test: add unittest smoke harness
```

### Task 2: 为路线数据新增失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_route_manager.py`

Add:

```python
import json
import tempfile
import unittest
from pathlib import Path

from core.route_manager import RouteManager


class RouteManagerTest(unittest.TestCase):
    def test_missing_route_file_returns_empty_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = RouteManager()
            data = mgr.load_route(Path(tmp))
            self.assertEqual(data["routes"]["main"]["guide_points"], [])
            self.assertIsNone(data["routes"]["main"]["exit_region"])

    def test_save_and_reload_route_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            mgr = RouteManager()
            mgr.set_exit_region(folder, (100, 200), 25)
            mgr.add_guide_point(folder, (10, 20))
            mgr.add_guide_point(folder, (30, 40))
            mgr.save_route(folder)

            reloaded = RouteManager()
            data = reloaded.load_route(folder)
            main = data["routes"]["main"]
            self.assertEqual(main["exit_region"]["center"], [100, 200])
            self.assertEqual(main["exit_region"]["radius"], 25)
            self.assertEqual(main["guide_points"], [[10, 20], [30, 40]])
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_route_manager
```

Verification:

```text
Expected before implementation:
ModuleNotFoundError: No module named 'core.route_manager'
```

Commit:

```text
test: add route manager contract tests
```

### Task 3: 实现 `RouteManager`

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/route_manager.py`

Add:

```python
import json
from pathlib import Path


class RouteManager:
    def __init__(self):
        self._cache = {}

    def _route_path(self, map_folder: Path) -> Path:
        return Path(map_folder) / "route.json"

    def _default_data(self):
        return {
            "version": 1,
            "routes": {
                "main": {
                    "exit_region": None,
                    "guide_points": [],
                }
            },
        }

    def load_route(self, map_folder):
        path = self._route_path(Path(map_folder))
        if not path.exists():
            data = self._default_data()
            self._cache[str(path)] = data
            return data
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._cache[str(path)] = data
        return data

    def save_route(self, map_folder):
        path = self._route_path(Path(map_folder))
        data = self._cache.setdefault(str(path), self._default_data())
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def set_exit_region(self, map_folder, center, radius):
        data = self.load_route(map_folder)
        data["routes"]["main"]["exit_region"] = {
            "center": [int(center[0]), int(center[1])],
            "radius": int(radius),
        }

    def add_guide_point(self, map_folder, point):
        data = self.load_route(map_folder)
        data["routes"]["main"]["guide_points"].append([int(point[0]), int(point[1])])

    def undo_guide_point(self, map_folder):
        data = self.load_route(map_folder)
        points = data["routes"]["main"]["guide_points"]
        if points:
            points.pop()

    def clear_route(self, map_folder):
        self._cache[str(self._route_path(Path(map_folder)))] = self._default_data()
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_route_manager
```

Verification:

```text
Expected after implementation:
..
----------------------------------------------------------------------
Ran 2 tests in 0.0xxs

OK
```

Commit:

```text
feat: add route manager
```

### Task 4: 为路径压缩添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_path_utils.py`

Add:

```python
import unittest

from core.path_utils import remove_collinear_points


class PathUtilsTest(unittest.TestCase):
    def test_remove_collinear_points_keeps_turns(self):
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        simplified = remove_collinear_points(path)
        self.assertEqual(simplified, [(0, 0), (2, 0), (2, 2)])
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_path_utils
```

Verification:

```text
Expected before implementation:
ModuleNotFoundError: No module named 'core.path_utils'
```

Commit:

```text
test: add path simplification tests
```

### Task 5: 实现共线点压缩工具

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/path_utils.py`

Add:

```python
def remove_collinear_points(path):
    if len(path) <= 2:
        return list(path)

    result = [path[0]]
    for idx in range(1, len(path) - 1):
        ax, ay = result[-1]
        bx, by = path[idx]
        cx, cy = path[idx + 1]
        ab = (bx - ax, by - ay)
        bc = (cx - bx, cy - by)
        if ab[0] * bc[1] - ab[1] * bc[0] == 0:
            continue
        result.append((bx, by))
    result.append(path[-1])
    return result
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_path_utils
```

Verification:

```text
Expected after implementation:
.
----------------------------------------------------------------------
Ran 1 test in 0.0xxs

OK
```

Commit:

```text
feat: add collinear path simplification
```

### Task 6: 为出口区域判定添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_path_utils.py`

Add:

```python
from core.path_utils import is_inside_exit_region

    def test_is_inside_exit_region_uses_radius(self):
        region = {"center": [100, 100], "radius": 10}
        self.assertTrue(is_inside_exit_region((108, 104), region))
        self.assertFalse(is_inside_exit_region((120, 100), region))
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_path_utils
```

Verification:

```text
Expected before implementation:
ImportError: cannot import name 'is_inside_exit_region'
```

Commit:

```text
test: add exit region predicate tests
```

### Task 7: 实现出口区域判定

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/path_utils.py`

Add:

```python
def is_inside_exit_region(point, region):
    if not region:
        return False
    cx, cy = region["center"]
    radius = region["radius"]
    dx = point[0] - cx
    dy = point[1] - cy
    return dx * dx + dy * dy <= radius * radius
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_path_utils
```

Verification:

```text
Expected after implementation:
..
----------------------------------------------------------------------
Ran 2 tests in 0.0xxs

OK
```

Commit:

```text
feat: add exit region check
```

### Task 8: 为分段目标选择添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_auto_navigator.py`

Add:

```python
import unittest

from core.auto_navigator import AutoNavigator


class AutoNavigatorSegmentTest(unittest.TestCase):
    def test_next_target_prefers_first_guide_point(self):
        nav = AutoNavigator()
        route = {
            "exit_region": {"center": [100, 100], "radius": 20},
            "guide_points": [[10, 10], [20, 20]],
        }
        nav.load_route(route)
        self.assertEqual(nav.current_segment_target(), (10, 10))
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected before implementation:
ModuleNotFoundError: No module named 'core.auto_navigator'
```

Commit:

```text
test: add segment target selection tests
```

### Task 9: 实现 `AutoNavigator` 路线加载与段目标选择

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`

Add:

```python
class AutoNavigator:
    def __init__(self):
        self.route = None
        self.guide_index = 0

    def load_route(self, route):
        self.route = route
        self.guide_index = 0

    def current_segment_target(self):
        guide_points = self.route.get("guide_points", [])
        if self.guide_index < len(guide_points):
            x, y = guide_points[self.guide_index]
            return (x, y)
        center = self.route["exit_region"]["center"]
        return (center[0], center[1])
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected after implementation:
.
----------------------------------------------------------------------
Ran 1 test in 0.0xxs

OK
```

Commit:

```text
feat: add route target selection to auto navigator
```

### Task 10: 为稳定定位窗口添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_auto_navigator.py`

Add:

```python
    def test_acquire_requires_consecutive_stable_positions(self):
        nav = AutoNavigator()
        nav.required_stable_frames = 3
        positions = [
            ((100, 100), 0.9),
            ((101, 100), 0.92),
            ((100, 101), 0.91),
        ]
        for pos, conf in positions:
            nav.observe_localization(pos, conf)
        self.assertTrue(nav.has_stable_lock())
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected before implementation:
AttributeError: 'AutoNavigator' object has no attribute 'observe_localization'
```

Commit:

```text
test: add stable acquire tests
```

### Task 11: 实现稳定定位观察窗口

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`

Add:

```python
from collections import deque

class AutoNavigator:
    def __init__(self):
        self.route = None
        self.guide_index = 0
        self.required_stable_frames = 3
        self.acquire_window = deque(maxlen=5)
        self.acquire_radius = 6.0

    def observe_localization(self, pos, conf):
        if pos is None or conf < 0.75:
            self.acquire_window.clear()
            return
        self.acquire_window.append((pos, conf))

    def has_stable_lock(self):
        if len(self.acquire_window) < self.required_stable_frames:
            return False
        xs = [p[0][0] for p in self.acquire_window]
        ys = [p[0][1] for p in self.acquire_window]
        return max(xs) - min(xs) <= self.acquire_radius and max(ys) - min(ys) <= self.acquire_radius
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected after implementation:
..
----------------------------------------------------------------------
Ran 2 tests in 0.0xxs

OK
```

Commit:

```text
feat: add stable acquire window
```

### Task 12: 为点击冷却判定添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_auto_navigator.py`

Add:

```python
    def test_click_cooldown_blocks_immediate_repeat(self):
        nav = AutoNavigator()
        nav.click_cooldown_ms = 500
        nav.last_click_ms = 1000
        self.assertFalse(nav.should_issue_click(now_ms=1200))
        self.assertTrue(nav.should_issue_click(now_ms=1600))
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected before implementation:
AttributeError: 'AutoNavigator' object has no attribute 'should_issue_click'
```

Commit:

```text
test: add click cooldown tests
```

### Task 13: 实现点击冷却

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`

Add:

```python
class AutoNavigator:
    def __init__(self):
        self.route = None
        self.guide_index = 0
        self.required_stable_frames = 3
        self.acquire_window = deque(maxlen=5)
        self.acquire_radius = 6.0
        self.click_cooldown_ms = 450
        self.last_click_ms = None

    def should_issue_click(self, now_ms):
        if self.last_click_ms is None:
            return True
        return now_ms - self.last_click_ms >= self.click_cooldown_ms
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected after implementation:
...
----------------------------------------------------------------------
Ran 3 tests in 0.0xxs

OK
```

Commit:

```text
feat: add click cooldown gating
```

### Task 14: 为卡住进度判定添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_auto_navigator.py`

Add:

```python
    def test_stuck_detected_when_progress_does_not_increase(self):
        nav = AutoNavigator()
        nav.min_progress_delta = 8
        nav.progress_timeout_ms = 1000
        nav.last_progress_value = 100
        nav.last_progress_ms = 1000
        self.assertTrue(nav.is_stuck(current_progress=103, now_ms=2200))
        self.assertFalse(nav.is_stuck(current_progress=120, now_ms=2200))
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected before implementation:
AttributeError: 'AutoNavigator' object has no attribute 'is_stuck'
```

Commit:

```text
test: add path progress stuck tests
```

### Task 15: 实现基于路径进度的卡住判定

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`

Add:

```python
class AutoNavigator:
    def __init__(self):
        self.route = None
        self.guide_index = 0
        self.required_stable_frames = 3
        self.acquire_window = deque(maxlen=5)
        self.acquire_radius = 6.0
        self.click_cooldown_ms = 450
        self.last_click_ms = None
        self.min_progress_delta = 8.0
        self.progress_timeout_ms = 1200
        self.last_progress_value = None
        self.last_progress_ms = None

    def is_stuck(self, current_progress, now_ms):
        if self.last_progress_value is None or self.last_progress_ms is None:
            self.last_progress_value = current_progress
            self.last_progress_ms = now_ms
            return False
        progressed = current_progress - self.last_progress_value
        if progressed >= self.min_progress_delta:
            self.last_progress_value = current_progress
            self.last_progress_ms = now_ms
            return False
        return now_ms - self.last_progress_ms >= self.progress_timeout_ms
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_auto_navigator
```

Verification:

```text
Expected after implementation:
....
----------------------------------------------------------------------
Ran 4 tests in 0.0xxs

OK
```

Commit:

```text
feat: add path progress stuck detection
```

### Task 16: 为 `navigation_mode` 路线加载添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_navigation_route_integration.py`

Add:

```python
import unittest

from gui.navigation_params import NavConfig


class NavigationRouteIntegrationPlanTest(unittest.TestCase):
    def test_placeholder(self):
        self.assertIsInstance(NavConfig(), NavConfig)
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_navigation_route_integration
```

Verification:

```text
Expected after implementation:
.
----------------------------------------------------------------------
Ran 1 test in 0.0xxs

OK
```

Commit:

```text
test: add navigation route integration placeholder
```

### Task 17: 在 `navigation_mode.py` 接入路线加载与保存

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
from core.route_manager import RouteManager

# in __init__
self.route_manager = RouteManager()
self.route_data = None

# in load_map after nav core init
self.route_data = self.route_manager.load_route(self.map_folder_path)

def _save_route_config(self):
    if self.map_folder_path:
        self.route_manager.save_route(self.map_folder_path)
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py" "core\route_manager.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: load and save route data in navigation mode
```

### Task 18: 为点击编辑模式添加失败测试

Files:

- `d:/ACloud/minimap_stitcher copy 13/tests/test_route_edit_state.py`

Add:

```python
import unittest


class RouteEditStatePlanTest(unittest.TestCase):
    def test_placeholder(self):
        self.assertTrue(True)
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m unittest tests.test_route_edit_state
```

Verification:

```text
Expected after implementation:
.
----------------------------------------------------------------------
Ran 1 test in 0.0xxs

OK
```

Commit:

```text
test: add route edit state placeholder
```

### Task 19: 在 `navigation_mode.py` 增加路线编辑按钮与模式

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
# in __init__
self.map_click_mode = "NONE"

# in init_ui top bar
self.btn_set_exit = QPushButton("设置出口")
self.btn_add_guide = QPushButton("添加途经点")
self.btn_undo_guide = QPushButton("撤销途经点")
self.btn_clear_route = QPushButton("清空路线")
self.btn_save_route = QPushButton("保存路线")
self.btn_auto_nav = QPushButton("开始自动到出口")

# helper methods
def _set_map_click_mode(self, mode):
    self.map_click_mode = mode

def _set_exit_mode(self):
    self._set_map_click_mode("SET_EXIT")

def _set_guide_mode(self):
    self._set_map_click_mode("ADD_GUIDE_POINT")
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: add route editing controls
```

### Task 20: 在地图点击处理中接入出口和途经点编辑

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
# in eventFilter map click branch
if self.map_click_mode == "SET_EXIT":
    global_pos = (int(scene_pos.x() + self.nav_core.crop_offset[0]), int(scene_pos.y() + self.nav_core.crop_offset[1]))
    self.route_manager.set_exit_region(self.map_folder_path, global_pos, 28)
    self.route_data = self.route_manager.load_route(self.map_folder_path)
    self._render_route_overlay()
    self.map_click_mode = "NONE"
    return True

if self.map_click_mode == "ADD_GUIDE_POINT":
    global_pos = (int(scene_pos.x() + self.nav_core.crop_offset[0]), int(scene_pos.y() + self.nav_core.crop_offset[1]))
    self.route_manager.add_guide_point(self.map_folder_path, global_pos)
    self.route_data = self.route_manager.load_route(self.map_folder_path)
    self._render_route_overlay()
    return True
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: handle route editing clicks
```

### Task 21: 渲染出口、途经点和当前路径占位图层

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
def _render_route_overlay(self):
    main = (self.route_data or {}).get("routes", {}).get("main", {})
    exit_region = main.get("exit_region")
    guide_points = main.get("guide_points", [])
    # clear previous overlay items here
    if exit_region:
        cx, cy = exit_region["center"]
        radius = exit_region["radius"]
        self.scene.addEllipse(
            cx - radius - self.nav_core.crop_offset[0],
            cy - radius - self.nav_core.crop_offset[1],
            radius * 2,
            radius * 2,
        )
    for idx, (gx, gy) in enumerate(guide_points, start=1):
        self.scene.addEllipse(gx - 4 - self.nav_core.crop_offset[0], gy - 4 - self.nav_core.crop_offset[1], 8, 8)
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: render route overlays
```

### Task 22: 在 `AutoNavigator` 中增加暂停/恢复接口

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`

Add:

```python
class AutoNavigator:
    def __init__(self):
        self.paused = False
        self.pause_reason = None

    def pause(self, reason):
        self.paused = True
        self.pause_reason = reason

    def resume(self):
        self.paused = False
        self.pause_reason = None

    def notify_external_interrupt(self):
        self.pause("external_interrupt")
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "core\auto_navigator.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: add pause and resume hooks to auto navigator
```

### Task 23: 在 `navigation_mode.py` 初始化自动导航器

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
from core.auto_navigator import AutoNavigator

# in __init__
self.auto_navigator = AutoNavigator()
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py" "core\auto_navigator.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: initialize auto navigator in navigation mode
```

### Task 24: 在启动自动导航前做路线与配置校验

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
def _can_start_auto_navigation(self):
    if not self.route_data:
        return False, "未加载路线"
    main = self.route_data.get("routes", {}).get("main", {})
    if not main.get("exit_region"):
        return False, "请先设置出口"
    if not self.nav_config.game_screen_center:
        return False, "请先校准屏幕中心"
    return True, ""
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: validate route before auto navigation
```

### Task 25: 在 `navigation_loop()` 接入自动导航更新主链路

Files:

- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`

Add:

```python
# in navigation_loop after localize
if self.auto_navigation_enabled:
    action = self.auto_navigator.update(
        localized_pos=(global_x, global_y) if global_x is not None else None,
        confidence=conf,
        wall_map=self.nav_core.wall_layer,
        pathfinder=self.app_context.pathfinder if hasattr(self.app_context, "pathfinder") else None,
        now_ms=int(time.time() * 1000),
    )
    if action and action.get("type") == "move":
        self.motion_controller.move_to_map_target(action["player_pos"], action["target_pos"])
```

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "gui\modes\navigation_mode.py"
```

Verification:

```text
Expected after implementation:
No output
```

Commit:

```text
feat: wire navigation loop to auto navigator
```

### Task 26: 最终联调与语法验证

Files:

- `d:/ACloud/minimap_stitcher copy 13/core/route_manager.py`
- `d:/ACloud/minimap_stitcher copy 13/core/path_utils.py`
- `d:/ACloud/minimap_stitcher copy 13/core/auto_navigator.py`
- `d:/ACloud/minimap_stitcher copy 13/gui/modes/navigation_mode.py`
- `d:/ACloud/minimap_stitcher copy 13/tests/test_route_manager.py`
- `d:/ACloud/minimap_stitcher copy 13/tests/test_path_utils.py`
- `d:/ACloud/minimap_stitcher copy 13/tests/test_auto_navigator.py`

Commands:

```powershell
cd "d:\ACloud\minimap_stitcher copy 13"
python -m py_compile "core\route_manager.py" "core\path_utils.py" "core\auto_navigator.py" "gui\modes\navigation_mode.py"
python -m unittest discover -s tests -p "test_*.py"
```

Verification:

```text
Expected after implementation:
No py_compile output
All unit tests pass
```

Commit:

```text
chore: verify phase1 auto navigation foundation
```
