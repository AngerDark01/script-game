# 方案 C 实施计划：统一 NavigationTask 队列状态机

## Goal

把普通必经点、出口、事件任务统一到一个 `NavigationTaskController` 中调度，消除普通导航和事件系统在 UI 层抢控制的问题。

## Architecture Overview

本计划采用“兼容壳优先”的方案 C 落地方式：

- 新增 `core/navigation_tasks/` 包，承载统一任务模型、路线进度上下文、移动执行器、任务构建器、调度器和控制器。
- 第一阶段不直接删除 `AutoNavigator` 和 `EventPathMover`，而是让它们逐步委托新模块，降低回归风险。
- `EventCoordinator` 拆出 `observe()` 与 `run_task()`，事件检测/定位/记忆继续运行，事件执行由统一 controller 决定。
- `NavigationModeWidget` 最终只消费 `NavigationIntent`，不再同时跑 `event_action` 与 `auto_action` 两套控制流。
- 传送门 handler 第一版保持兼容，后期再把“靠近事件点”从 handler 中净化出来。

## Tech Stack

- Python 3.x
- PySide6 UI
- OpenCV / NumPy 地图处理
- 当前运行入口：`main.py`
- 主要验证方式：`py_compile`、应用启动、游戏内日志观察

## 约束

- 用户已明确不希望做无意义逻辑测试；本计划默认不强制单元测试。
- 每阶段至少做 `py_compile`。
- 每阶段只在用户确认后进入下一阶段，避免一次性改穿。
- 不删除旧逻辑，直到新控制器在游戏内验证可用。
- 保留现有传送门事件可用链路，先兼容再净化。

## 阶段 0：基线保护

### Task 0.1：记录当前运行入口和导入基线

文件：

- `docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md`

动作：

- 不改代码。
- 在开始开发前执行导入编译。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile `
  core\auto_navigator.py `
  core\anchor_path.py `
  core\events\coordinator.py `
  core\events\path_mover.py `
  core\events\runner.py `
  core\events\memory.py `
  core\events\types\portal\handler.py `
  gui\modes\navigation_mode.py
```

期望：

```text
无 SyntaxError
```

## 阶段 1：新增统一任务模型

目标：只新增数据结构，不接入运行流程。

### Task 1.1：新增 `core/navigation_tasks/__init__.py`

文件：

- `core/navigation_tasks/__init__.py`

内容：

```python
"""Unified navigation task controller package.

This package coordinates static route goals and dynamic event tasks.
"""
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\__init__.py
```

### Task 1.2：新增 `core/navigation_tasks/models.py`

文件：

- `core/navigation_tasks/models.py`

内容要点：

- `NavigationTaskKind`
- `NavigationTaskState`
- `NavigationIntentType`
- `NavigationTask`
- `NavigationIntent`
- `MovementStep`
- `RouteProjection`
- `RouteAnchor`

建议完整代码：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NavigationTaskKind(str, Enum):
    REQUIRED = "required"
    EXIT = "exit"
    EVENT = "event"


class NavigationTaskState(str, Enum):
    PENDING = "pending"
    MOVING = "moving"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    IGNORED = "ignored"


class NavigationIntentType(str, Enum):
    NONE = "none"
    MOVE_MAP = "move_map"
    CLICK_SCREEN = "click_screen"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    ARRIVED = "arrived"
    FAILED = "failed"


@dataclass
class RouteProjection:
    point: tuple[float, float]
    progress: float
    segment_index: int
    deviation: float


@dataclass
class RouteAnchor:
    index: int
    point: tuple[float, float]
    progress: float


@dataclass
class NavigationTask:
    id: str
    kind: NavigationTaskKind
    target_pos: tuple[float, float]
    state: NavigationTaskState = NavigationTaskState.PENDING
    priority: int = 0
    route_progress: float | None = None
    source_ref: Any = None
    required_index: int | None = None
    event_type: str | None = None
    radius: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MovementStep:
    path: list[tuple[float, float]] = field(default_factory=list)
    subgoal: tuple[float, float] | None = None
    path_kind: str = "none"
    should_click: bool = False
    deviation: float = 0.0
    reason: str = ""
    task_id: str | None = None


@dataclass
class NavigationIntent:
    type: NavigationIntentType = NavigationIntentType.NONE
    task_id: str | None = None
    task_kind: str | None = None
    player_pos: tuple[float, float] | None = None
    target_pos: tuple[float, float] | None = None
    subgoal: tuple[float, float] | None = None
    path: list[tuple[float, float]] = field(default_factory=list)
    path_kind: str = "none"
    required_index: int | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\models.py
```

### Task 1.3：新增 `core/navigation_tasks/debug.py`

文件：

- `core/navigation_tasks/debug.py`

内容：

```python
from __future__ import annotations

from core.events.debug import event_log


def nav_log(message: str, **fields) -> None:
    event_log(message, **fields)
```

说明：

- 暂时复用 `event_runtime.log`，避免新增日志文件导致调试分散。
- 后续如日志量过大，再拆 `navigation_runtime.log`。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\debug.py
```

## 阶段 2：抽出 RouteContext

目标：统一 `guide_points` 投影、路线进度和锚点消费，不改变运行流程。

### Task 2.1：新增 `core/navigation_tasks/route_context.py`

文件：

- `core/navigation_tasks/route_context.py`

职责：

- 接收 `guide_points`。
- 计算 cumulative lengths。
- `project(point)` 返回 `RouteProjection`。
- `progress_of(point)` 返回路线进度。
- `anchor_at(index)` 返回锚点。
- `next_anchor(current_pos, target_pos, consumed_anchor_index, reached_radius)` 返回下一个前方锚点。
- `consumed_index_for_position(point, reached_radius)` 用当前位置恢复已消费锚点。

实现策略：

- 复用 `core.anchor_path` 当前 `_project_progress_on_polyline` 思路，但不要从私有函数 import。
- 后续 `anchor_path.py` 可以改为调用 `RouteContext`，但第一步先不动。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\route_context.py
```

### Task 2.2：给 `RouteContext` 写离线探针脚本

文件：

- `utils/route_context_probe.py`

职责：

- 读取 `map_data/Aa/route.json`。
- 打印每个 guide 的 progress。
- 打印 required 和 exit 的 progress。
- 验证 `(2577,2474)` 是 guide 5 附近，progress 约 337.69。

命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe utils\route_context_probe.py --map Aa
```

期望输出包含：

```text
guide[4] pos=(2577, 2474) progress=337
required[2] pos=(2608, 2452)
```

说明：

- 这是离线探针，不是单元测试。
- 用于确认路线模型和当前日志能对齐。

## 阶段 3：抽出 MovementExecutor

目标：把普通导航和事件移动的重复移动逻辑集中到一个模块，但先不改变外部行为。

### Task 3.1：新增 `core/navigation_tasks/movement_executor.py`

文件：

- `core/navigation_tasks/movement_executor.py`

职责：

- 持有当前 path/path_goal/path_kind。
- 调用 `plan_path_with_optional_anchors()`。
- 管理 click cooldown。
- 管理 path projection。
- 管理 anchor_step/anchor_probe 到达。
- 管理 local fallback probe。

第一版不要实现完整 stuck recovery，只先覆盖 `EventPathMover` 已有能力：

- target changed 重规划。
- anchor reached 重规划。
- projection failed 重规划。
- deviation too large 重规划。
- fallback retry。

后续再把 `AutoNavigator` 的 stuck recovery 合并进来。

核心接口：

```python
class MovementExecutor:
    def reset(self) -> None: ...

    def step(
        self,
        *,
        task_id: str,
        current_pos,
        target_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context=None,
        force_repeat_click: bool = False,
    ) -> MovementStep | None:
        ...

    def record_click(self, *, now_ms: int, subgoal) -> None:
        ...
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\movement_executor.py
```

### Task 3.2：让 `EventPathMover` 委托 `MovementExecutor`

文件：

- `core/events/path_mover.py`

目标：

- 保留 `EventPathMover.step()` 外部接口不变。
- 内部使用 `MovementExecutor.step()`。
- 保留 `record_click()` 外部接口不变，内部调用 executor。
- 保留 `path/subgoal/path_kind` 属性，供 overlay 使用。

迁移原则：

- 不改 `NavigationModeWidget._execute_event_move_to()`。
- 不改 `PortalEventHandler`。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\path_mover.py core\navigation_tasks\movement_executor.py
```

启动验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe "D:\ACloud\minimap_stitcher copy 13\main.py"
```

手动观察：

- 打开事件管理窗口。
- 测试传送门按钮仍可触发同一事件管线。
- `logs/event_runtime.log` 出现 `event path planned` 或新的 `nav movement planned`。

## 阶段 4：EventCoordinator 拆 observe/run_task

目标：事件检测和事件执行解耦，为统一 controller 调用事件 handler 做准备。

### Task 4.1：新增 `EventCoordinator.observe()`

文件：

- `core/events/coordinator.py`

职责：

- 执行当前 `update()` 中的检测、定位、memory merge、display task 选择。
- 不调用 `EventRunner.update()`。
- 返回当前 active/display tasks 信息，可先返回 `None`，保持内部状态即可。

接口：

```python
def observe(self, tick) -> None:
    ...
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\coordinator.py
```

### Task 4.2：新增 `EventCoordinator.run_task()`

文件：

- `core/events/coordinator.py`

接口：

```python
def run_task(self, task_id: str | None, tick):
    ...
```

规则：

- `task_id is None`：调用 runner idle clear 或返回 None，按现有兼容策略处理。
- 找到对应 task 后调用 `self.runner.update(task, tick, self.config)`。
- 返回 `EventAction`。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\coordinator.py
```

### Task 4.3：保持 `EventCoordinator.update()` 兼容

文件：

- `core/events/coordinator.py`

目标：

- 旧调用仍可工作。
- `update()` 内部改为：

```python
self.observe(tick)
task = pick runnable task as before
return self.runner.update(...)
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\coordinator.py gui\modes\navigation_mode.py
```

启动验证：

- 应用能启动。
- 事件管理窗口仍可显示事件任务。

## 阶段 5：任务构建器

目标：把 route 静态目标和 EventMemory 动态目标统一成 `NavigationTask` 列表。

### Task 5.1：新增 `core/navigation_tasks/task_builder.py`

文件：

- `core/navigation_tasks/task_builder.py`

接口：

```python
class NavigationTaskBuilder:
    def build(
        self,
        *,
        route: dict | None,
        event_tasks: list,
        route_context,
        completed_required: set[int],
    ) -> list[NavigationTask]:
        ...
```

规则：

- `required_points` -> `required:0`, `required:1`, ...
- `exit_region` -> `exit:main`
- active event tasks -> `event:<event_task.id>`
- 事件 task 的 `source_ref` 指向原 `EventTask`。
- completed/ignored 事件不进入可执行任务列表。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\task_builder.py
```

### Task 5.2：新增任务构建探针

文件：

- `utils/navigation_task_probe.py`

职责：

- 读取 `map_data/Aa/route.json`。
- 构建静态 required/exit tasks。
- 打印 task id、kind、target、route_progress。

命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe utils\navigation_task_probe.py --map Aa
```

期望：

```text
required:0
required:1
required:2
exit:main
```

## 阶段 6：统一 Scheduler

目标：先替代 UI 层距离仲裁，但不直接接管移动。

### Task 6.1：新增 `core/navigation_tasks/scheduler.py`

文件：

- `core/navigation_tasks/scheduler.py`

接口：

```python
class NavigationTaskScheduler:
    def pick(
        self,
        *,
        tasks: list[NavigationTask],
        player_pos,
        active_task_id: str | None = None,
        manual_event_only: bool = False,
    ) -> NavigationTask | None:
        ...
```

第一版规则：

1. `active_task_id` 存在则锁定该任务。
2. `manual_event_only=True` 时只选 event task。
3. 找第一个未完成 required。
4. 如果无 required，选 exit。
5. 事件只在路线进度位于 player 和当前静态目标之间时插队。
6. 如果事件无法投影，暂不插队，避免误抢。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\scheduler.py
```

## 阶段 7：NavigationTaskController 第一版

目标：新增 controller，但先不接入 UI 主流程。

### Task 7.1：新增 `core/navigation_tasks/controller.py`

文件：

- `core/navigation_tasks/controller.py`

职责：

- 维护 active task。
- 构建 tasks。
- 调 scheduler。
- 对 required/exit 使用 `MovementExecutor`。
- 对 event 第一版仍允许 handler 返回 `MOVE_TO`，并把 MOVE_TO 交给 `MovementExecutor`。

核心接口：

```python
class NavigationTaskController:
    def __init__(self):
        ...

    def load_route(self, route: dict | None) -> None:
        ...

    def start(self) -> bool:
        ...

    def stop(self) -> None:
        ...

    def update(
        self,
        *,
        localized_pos,
        confidence: float,
        route: dict | None,
        event_coordinator,
        event_tick,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        manual_event_only: bool = False,
    ) -> NavigationIntent:
        ...
```

第一版内部可复用 `AutoNavigator.observe_localization()` 思路，但建议直接复制必要逻辑到 controller，避免 controller 反向依赖 AutoNavigator。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py
```

### Task 7.2：新增 `AutoNavigator` facade 兼容层

文件：

- `core/auto_navigator.py`

目标：

- 不立即重写全部 `AutoNavigator`。
- 先新增可选字段：

```python
self.task_controller = None
self.use_task_controller = False
```

不改变默认行为。

目的：

- 为 UI 接入前做准备。
- 避免一次性替换导致无法回退。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\auto_navigator.py
```

## 阶段 8：UI 接入影子模式

目标：主流程仍按旧逻辑执行，但每帧同时跑新 controller 的“只决策不点击”影子模式，对比日志。

### Task 8.1：在 `NavigationModeWidget` 初始化 controller

文件：

- `gui/modes/navigation_mode.py`

新增：

```python
from core.navigation_tasks.controller import NavigationTaskController
```

初始化：

```python
self.navigation_task_controller = NavigationTaskController()
self.use_navigation_task_controller = False
self.shadow_navigation_task_controller = True
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py
```

### Task 8.2：加载 route 时同步 controller

文件：

- `gui/modes/navigation_mode.py`

在当前 `auto_navigator.load_route(...)` 附近同步：

```python
self.navigation_task_controller.load_route(main_route)
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py
```

### Task 8.3：导航 loop 添加影子决策日志

文件：

- `gui/modes/navigation_mode.py`

在旧 `auto_navigator.update()` 前后，调用 controller 的 dry-run 或 shadow update：

```python
if self.shadow_navigation_task_controller:
    shadow_intent = self.navigation_task_controller.preview(...)
```

如果没有 preview，则 `update(..., execute=False)`。

日志：

```text
nav task selected shadow
```

验证：

- 应用启动。
- 开自动导航。
- `logs/event_runtime.log` 同时出现旧 `auto path planned` 和新 `nav task selected shadow`。
- 不改变鼠标行为。

## 阶段 9：UI 主流程切换到 NavigationIntent

目标：用新 controller 替代旧的 `event_blocks_auto_navigation + auto_action` 双流。

### Task 9.1：新增 intent 执行 helper

文件：

- `gui/modes/navigation_mode.py`

新增方法：

```python
def _execute_navigation_intent(self, intent):
    ...
```

规则：

- `MOVE_MAP`：`motion_controller.move_to_map_target(intent.player_pos, intent.subgoal)`
- `CLICK_SCREEN`：`motion_controller.click_screen_position(...)`
- `PRESS_KEY`：`motion_controller.press_key(...)`
- `WAIT/NONE`：不输入
- `ARRIVED/FAILED`：停止自动导航

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py
```

### Task 9.2：新增开关使用新 controller

文件：

- `gui/modes/navigation_mode.py`

第一版用代码常量或配置：

```python
self.use_navigation_task_controller = True
```

主循环分支：

```text
if use_navigation_task_controller:
    event_coordinator.observe(event_tick)
    intent = navigation_task_controller.update(...)
    _execute_navigation_intent(intent)
else:
    old event_action + auto_action flow
```

保留旧流，方便回退。

验证：

- 应用启动。
- 无事件时，自动导航能沿 required/guide/exit 移动。
- 日志中出现 `nav task selected`、`nav movement planned`。

### Task 9.3：事件接入新 controller

文件：

- `core/navigation_tasks/controller.py`
- `gui/modes/navigation_mode.py`

规则：

- 每帧先 `event_coordinator.observe(event_tick)`。
- controller 从 `event_coordinator.tasks()` 构建 event task。
- event task 被选中后，调用 `event_coordinator.run_task(source_event_task.id, event_tick)`。
- 如果返回 `MOVE_TO`，由 controller 转成 `MOVE_MAP` intent。
- 如果返回 `PRESS_KEY/CLICK_SCREEN/WAIT/COMPLETE/FAIL`，转成对应 `NavigationIntent`。

验证：

- 传送门被识别后，controller 选择 `event:portal:x`。
- 到门附近后按 D。
- 传送完成后回到下一个 required/exit task。

## 阶段 10：移除旧 UI 仲裁

目标：新 controller 稳定后，删掉旧抢控制逻辑。

### Task 10.1：停用 `_allowed_event_task_ids`

文件：

- `gui/modes/navigation_mode.py`

动作：

- 主流程不再调用 `_allowed_event_task_ids()`。
- 方法可暂时保留，但标注 deprecated。

验证：

```powershell
rg -n "_allowed_event_task_ids\\(" gui\modes\navigation_mode.py
```

期望：

```text
只剩方法定义或无主流程调用
```

### Task 10.2：停用 `event_blocks_auto_navigation`

文件：

- `gui/modes/navigation_mode.py`

动作：

- 新 controller 分支不再计算 `event_blocks_auto_navigation`。
- 旧分支保留一段时间。

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py
```

## 阶段 11：传送门 handler 净化

目标：稳定后再做，不作为第一轮必需。

### Task 11.1：事件 definition 声明 trigger 策略

文件：

- `core/events/base/definition.py`
- `core/events/types/portal/definition.py`

新增可选方法：

```python
def trigger_target(self, task):
    return task.global_pos

def arrival_radius(self, config) -> float:
    return float(config.get("arrival_radius", 48))

def interact_radius(self, config) -> float:
    return float(config.get("interact_radius", 18))
```

验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\base\definition.py core\events\types\portal\definition.py
```

### Task 11.2：从 `PortalEventHandler` 移除普通靠近 MOVE_TO

文件：

- `core/events/types/portal/handler.py`

动作：

- 删除或停用：

```python
if distance > arrival_radius:
    return EventAction.move_to(...)
```

- controller 在执行 handler 前负责走到 arrival/interact 半径。
- handler 只处理：
  - force target click
  - wait after click
  - press D
  - wait_result
  - complete/fail

验证：

- 手动测试传送门仍完整执行。
- 自动导航遇到传送门仍完整执行。

## 阶段 12：清理旧移动器

目标：新 controller 稳定后再做。

### Task 12.1：删除或降级 `EventPathMover`

文件：

- `core/events/path_mover.py`
- `gui/modes/navigation_mode.py`

动作：

- 如果没有外部调用，删除 `EventPathMover`。
- 如果仍有兼容调用，保留薄壳并标注 deprecated。

验证：

```powershell
rg -n "EventPathMover|event_path_mover" .
```

期望：

```text
没有主流程依赖
```

### Task 12.2：`AutoNavigator` facade 收口

文件：

- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`

动作：

- 如果 `NavigationTaskController` 已完全替代旧 update，则 `AutoNavigator` 可变成兼容 facade 或后续删除。

不建议立即删除：

- 旧测试可能引用 `AutoNavigator`。
- UI 代码中仍可能有状态展示字段依赖。

## 最终验收清单

### 启动验收

```powershell
D:\ACloud\.venv\Scripts\python.exe "D:\ACloud\minimap_stitcher copy 13\main.py"
```

期望：

- 无 SyntaxError。
- 主窗口启动。
- 事件管理窗口能打开。

### 无事件导航验收

场景：

- 关闭或不触发传送门事件。
- 开始自动导航。

期望：

- `logs/event_runtime.log` 出现 `nav task selected selected=required:...`。
- 到达 required 后出现 `nav task state ... to=completed`。
- 不再高频重复同一个 `anchor_step path_goal=(2577,2474)`。

### 传送门事件验收

场景：

- 事件管理窗口启用 portal。
- 角色能看到传送门小地图图标。

期望：

- `task created portal`。
- `nav task selected selected=event:portal:x`。
- 移动到传送门附近。
- 点门点一次。
- 按 D。
- `portal teleport completed`。
- `teleport session completed`。
- 下一帧选中 required 或 exit，不回头反复传送。

### 手动测试验收

场景：

- 点击事件管理窗口“测试传送门”。

期望：

- 进入 `manual_event_only` 调度模式。
- 只处理 event task。
- 完成后按钮恢复。
- 正式导航和手动测试走同一个 controller/event runner。

## 推荐执行顺序

第一批建议只执行到阶段 4：

1. 新增 models/debug。
2. 新增 RouteContext。
3. 新增 MovementExecutor。
4. EventPathMover 委托 MovementExecutor。
5. EventCoordinator 拆 observe/run_task，保持 update 兼容。

这批完成后，运行行为应该基本不变，但底层已经为方案 C 做好基础。

第二批执行阶段 5 到阶段 9：

1. 任务构建器。
2. Scheduler。
3. Controller。
4. UI 影子模式。
5. UI 主流程切换。

第三批执行阶段 10 到阶段 12：

1. 删除旧 UI 仲裁。
2. 净化传送门 handler。
3. 清理旧移动器和 AutoNavigator facade。

## 回滚策略

- 阶段 1 到 4：只新增模块和兼容委托，回滚简单。
- 阶段 8：影子模式不改变行为，可随时关闭。
- 阶段 9：保留旧分支，用 `use_navigation_task_controller` 回退。
- 阶段 10 以后才删除旧逻辑，必须等游戏内确认稳定后执行。

## CODEBASE 同步要求

每批代码完成后必须同步：

- `CODEBASE.md` §2 新增/更新文件说明。
- `CODEBASE.md` §4 新增 `core/navigation_tasks/*` 模块说明。
- `CODEBASE.md` §5 更新关键函数索引。
- `CODEBASE.md` §6 更新导航 flow。
- `CODEBASE.md` §9 增加调度器风险和回滚策略。
- `ITERATION_LOG.md` 记录每批影响范围、发现和验证命令。
