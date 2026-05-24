# 方案 C：统一任务队列状态机设计

## 目标

方案 C 的目标是从架构上消除“普通导航、必经点、锚点、事件”之间的控制权冲突。

核心结论：

- 把 `required_points`、`exit_region`、事件任务都抽象成统一的 `NavigationTask`。
- 新增统一调度器 `NavigationTaskScheduler`，由它决定当前应该处理哪个任务。
- 普通导航和事件不再分别抢控制，而是都通过同一个任务队列进入移动/执行状态机。
- `AutoNavigator` 不再自己选择 `required_points[required_index]` 或出口，而是变成“移动执行器”。
- 事件 handler 仍保留事件内部执行逻辑，但事件的“靠近触发点”阶段交给统一移动执行器。

这是更彻底的架构重构，适合长期扩展多个随机事件、分支事件、复杂地图策略，但改动面明显大于方案 B。

## 当前源码事实

### 现有普通导航

`AutoNavigator` 当前同时承担三类职责：

1. 定位稳定与控制位置平滑。
2. 当前目标选择：`required_points[required_index]` 或 `exit_region.center`。
3. 路径规划、lookahead、点击节流、卡住恢复。

代码位置：

- `core/auto_navigator.py`

当前目标选择逻辑：

```text
_select_segment_target()
  if required_index < len(required_points):
      return "required", required_points[required_index]
  return "exit", exit_center
```

### 现有事件系统

事件系统当前独立维护任务：

```text
EventCoordinator
  -> EventMemory.active_tasks()
  -> EventScheduler.pick()
  -> EventRunner.update()
  -> EventAction
```

事件 task 状态：

```text
OBSERVED -> PENDING -> RUNNING -> COMPLETED / FAILED / IGNORED
```

代码位置：

- `core/events/models.py`
- `core/events/memory.py`
- `core/events/coordinator.py`
- `core/events/scheduler.py`
- `core/events/runner.py`

### 现有事件移动

事件 handler 返回：

```text
EventAction.move_to(task.global_pos)
```

由 UI 执行：

```text
NavigationModeWidget._execute_event_move_to()
  -> EventPathMover.step()
  -> MotionController.move_to_map_target()
```

代码位置：

- `core/events/path_mover.py`
- `gui/modes/navigation_mode.py`

### 现有冲突点

当前系统是两个调度器并存：

```text
普通导航调度器：AutoNavigator._select_segment_target()
事件调度器：EventCoordinator -> EventScheduler -> EventRunner
```

UI 层用 `_allowed_event_task_ids()` 做临时仲裁：

```text
事件距离 <= 普通目标距离 -> 允许事件执行
```

这只是“抢控制权”的补丁，不是真正统一的导航决策。

## 方案 C 核心思想

新增一个统一导航任务模型：

```text
NavigationTask
  kind = required | exit | event
  id
  target_pos
  route_progress
  priority
  state
  source
```

所有目标进入同一个调度器：

```text
required_points -> static tasks
exit_region -> static final task
EventMemory.active_tasks() -> dynamic tasks
```

统一调度器每帧输出：

```text
NavigationDecision
  task
  phase = move_to_trigger | execute_event | complete | wait
```

然后统一执行：

```text
NavigationTaskController.update()
  -> 选任务
  -> 如果任务需要移动，调用 MovementExecutor
  -> 如果任务是事件且已到触发范围，调用 EventRunner
  -> 如果任务完成，更新 task 状态，并重新调度
```

## 新增模块建议

### `core/navigation_tasks/models.py`

职责：统一导航任务数据结构。

建议结构：

```python
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


@dataclass
class NavigationTask:
    id: str
    kind: NavigationTaskKind
    target_pos: tuple[int, int]
    state: NavigationTaskState
    priority: int = 0
    route_progress: float | None = None
    source_ref: object | None = None
    required_index: int | None = None
    event_type: str | None = None
    metadata: dict = field(default_factory=dict)
```

### `core/navigation_tasks/route_context.py`

职责：统一路线走廊和进度上下文。

这个模块可复用方案 B 的 `RouteProgressModel`。

建议职责：

- 投影当前位置。
- 投影所有 task。
- 判断 task 是否在前方。
- 维护已消费锚点。
- 判断 required task 是否已越过。

### `core/navigation_tasks/task_builder.py`

职责：每帧从 route 和事件 memory 构建任务视图。

输入：

- `route_data["required_points"]`
- `route_data["exit_region"]`
- `event_coordinator.tasks()`
- 当前 player position
- 已完成 required index 或 required task 状态

输出：

```python
list[NavigationTask]
```

规则：

- `required_points` 生成 `required:<index>`。
- `exit_region` 生成 `exit:main`。
- `EventTask` 生成 `event:<event_task.id>`。
- 已完成的静态 required 不再生成 pending task。
- 已 completed/ignored 的事件不生成可执行 task，但可生成 overlay task。

### `core/navigation_tasks/scheduler.py`

职责：统一决定当前任务。

建议第一版排序规则：

1. 正在执行的事件任务锁定优先。
2. 已经 moving/executing 的任务优先，除非失败或完成。
3. 静态 required 按 index 约束，但允许跳过已经越过的 required。
4. 事件作为动态 required，如果在当前路线前方、且不晚于当前 required/exit 太多，则可插队。
5. exit 永远在所有 required 完成后可执行。

建议伪代码：

```python
def pick(tasks, player_projection, active_task_id=None):
    if active_task_id:
        return task_by_id(active_task_id)

    current_static = first_uncompleted_required_or_exit(tasks)
    event_candidates = forward_events_before_or_near(current_static)

    if event_candidates:
        return best_event(event_candidates)

    return current_static
```

### `core/navigation_tasks/controller.py`

职责：统一状态机。

它替代现在 UI 层的事件/普通导航仲裁。

建议状态流：

```text
IDLE
ACQUIRE
SELECT_TASK
MOVE_TO_TASK
EXECUTE_TASK
WAIT_TASK
COMPLETE_TASK
RECOVER
ARRIVED
FAILED
```

执行规则：

- `required` task：移动到目标后完成。
- `exit` task：移动到出口区域后 `ARRIVED`。
- `event` task：先移动到事件触发范围，再调用事件 handler 执行。

### `core/navigation_tasks/movement_executor.py`

职责：统一普通导航和事件移动。

它可以从现有两个模块合并而来：

- `AutoNavigator._plan_segment`
- `AutoNavigator._follow_segment`
- `EventPathMover.step`

统一输出：

```python
@dataclass
class MovementStep:
    path: list[tuple[float, float]]
    subgoal: tuple[float, float] | None
    should_click: bool
    path_kind: str
    task_id: str
    reason: str
```

`MovementExecutor` 不关心任务是 required、exit 还是 event；它只负责：

- A* 路径
- 锚点消费
- lookahead
- 点击节流
- path deviation 重规划
- stuck recovery

## 修改现有模块

### `core/auto_navigator.py`

方案 C 下，`AutoNavigator` 有两个选择：

#### C1：保留类名，重写为 facade

外部仍调用：

```python
auto_navigator.update(...)
```

内部委托：

```text
NavigationTaskController.update()
```

优点：UI 改动较小。

缺点：`AutoNavigator` 名称不再准确。

#### C2：新增 `NavigationTaskController`，逐步替换 UI 调用

UI 改为：

```python
self.navigation_controller.update(...)
```

优点：命名清晰。

缺点：改动面更大。

推荐 C1 起步，C2 后续重命名。

### `core/events/coordinator.py`

事件检测、定位、memory 继续保留。

但事件 handler 的执行不再由 `EventCoordinator.update()` 直接调度，拆成两步：

```python
coordinator.observe(tick) -> update detections/memory/overlays only
coordinator.run_task(task_id, tick) -> EventRunner.update(task, tick, config)
```

当前 `update()` 可保留兼容：

```python
def update(...):
    self.observe(tick)
    return self.run_allowed_task(...)
```

方案 C 最终由 `NavigationTaskController` 决定什么时候调用 `run_task()`。

### `core/events/scheduler.py`

事件内部 scheduler 可以降级或删除。

因为统一 `NavigationTaskScheduler` 已经负责事件和普通目标排序。

保留价值：

- 事件系统单独测试时仍可用。
- 手动事件测试模式可复用。

建议第一版保留，但普通导航主流程不再依赖它做最终任务选择。

### `core/events/path_mover.py`

逐步迁移到：

```text
core/navigation_tasks/movement_executor.py
```

第一阶段可以让 `EventPathMover` 内部直接调用 `MovementExecutor`，保持外部接口不变。

最终删除重复逻辑：

- path cache
- path_goal
- click cooldown
- fallback probe
- anchor_step 到达判断

### `gui/modes/navigation_mode.py`

UI 主循环简化为：

```text
1. 定位
2. event_coordinator.observe()
3. navigation_controller.update(
     player_pos,
     route_data,
     event_tasks,
     wall_map,
     explored_map,
     pathfinder,
   )
4. 如果 controller 输出 click intent，则 MotionController 执行
5. 如果 controller 输出 key/screen click，则 EventActionExecutor 执行
6. 更新 overlay/status
```

移除或降级：

- `_allowed_event_task_ids`
- `event_blocks_auto_navigation`
- `_execute_event_move_to` 中的大量路径逻辑
- `event_path_mover`

保留：

- EventManagerDialog
- overlay 绘制
- 手动测试按钮
- MotionController 回调

## 统一任务状态机细节

### REQUIRED 任务

来源：

```text
route.json.required_points
```

完成条件：

- 距离到 required point <= arrival radius。
- 或路线进度已经越过 required progress + margin。

完成动作：

- 标记 `required:<index>` completed。
- 更新当前静态路线进度。
- 选择下一个任务。

注意：

- required 不再由 `required_index` 单独控制，`required_index` 可以变成从 completed required tasks 推导出的只读值。

### EXIT 任务

来源：

```text
route.json.exit_region
```

激活条件：

- 所有 required tasks completed。

完成条件：

- `is_inside_exit_region(player_pos, exit_region)`。

完成动作：

- 整体导航 `ARRIVED`。

### EVENT 任务

来源：

```text
EventMemory.active_tasks()
```

激活条件：

- 事件配置 enabled。
- event task state 是 pending/running。
- 调度器判定它在当前路线前方并且应该处理。

阶段：

```text
MOVE_TO_TASK:
  移动到事件触发点

EXECUTE_TASK:
  调用事件 handler

WAIT_TASK:
  handler 返回 WAIT 时暂停普通移动

COMPLETE_TASK:
  handler 返回 COMPLETE/FAIL 后更新 EventMemory
```

传送门例子：

```text
task=event portal:1
MOVE_TO_TASK -> 走到 portal.global_pos 附近
EXECUTE_TASK -> PortalEventHandler 返回 force target click / press d / wait
COMPLETE_TASK -> EventMemory.complete_teleport_session()
SELECT_TASK -> 从传送后的当前位置重新选任务
```

## 统一执行输出

控制器输出应统一成 `NavigationIntent`：

```python
class NavigationIntentType(str, Enum):
    NONE = "none"
    MOVE_MAP = "move_map"
    CLICK_SCREEN = "click_screen"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    ARRIVED = "arrived"
    FAILED = "failed"


@dataclass
class NavigationIntent:
    type: NavigationIntentType
    task_id: str | None = None
    task_kind: str | None = None
    player_pos: tuple[float, float] | None = None
    target_pos: tuple[float, float] | None = None
    subgoal: tuple[float, float] | None = None
    path: list[tuple[float, float]] = field(default_factory=list)
    message: str = ""
    metadata: dict = field(default_factory=dict)
```

UI 只消费 intent：

```text
MOVE_MAP -> MotionController.move_to_map_target(player_pos, subgoal)
CLICK_SCREEN -> MotionController.click_screen_position(screen_pos)
PRESS_KEY -> MotionController.press_key(key)
WAIT -> no input
ARRIVED/FAILED -> stop auto nav
```

## 事件 handler 适配

当前 `PortalEventHandler.update()` 既负责靠近判断，也返回 `MOVE_TO`。

方案 C 推荐分阶段处理：

### 第一阶段兼容

保持 handler 原样。

如果 handler 返回 `MOVE_TO`：

- controller 把它当作“事件要求移动到某点”。
- 使用统一 `MovementExecutor` 执行。

### 第二阶段净化

事件 handler 不再负责“走到事件附近”。

事件 definition 提供：

```python
def trigger_target(task) -> tuple[int, int]:
    return task.global_pos

def arrival_radius(config) -> float:
    return ...

def interact_radius(config) -> float:
    return ...
```

controller 负责靠近。

handler 只在到达触发范围后处理：

- 点击事件点
- 按 D
- 等待完成
- 判断完成/失败

这样事件四阶段会更清晰：

```text
识别定位：EventCoordinator
导航触发：NavigationTaskController + MovementExecutor
事件执行：EventHandler
事件结束：EventHandler + EventMemory
```

## 日志要求

方案 C 必须比当前日志更强，否则状态机更大后更难调。

### 调度日志

```text
nav task selected
  selected=event:portal:1|required:2|exit:main
  previous=...
  reason=active_lock|event_before_required|required_order|exit_after_required
  player_progress=...
  task_progress=...
```

### 任务状态日志

```text
nav task state
  task=required:2
  from=pending
  to=moving|completed
  reason=distance_reached|progress_reached
```

### 移动日志

```text
nav movement planned
  task=event:portal:1
  path_kind=anchor_step
  anchor_index=4
  consumed_anchor_index=3
  path_goal=(x,y)
  reason=target_changed|anchor_reached|deviation|stuck
```

### 事件执行日志

保留当前：

- `portal handler start`
- `portal move near`
- `portal point click before interaction`
- `portal interaction key`
- `portal teleport completed`
- `teleport session completed`

增加 controller 级日志：

```text
nav event execute
  task=portal:1
  action=press_key d
```

## 迁移步骤

### 第 1 步：抽出 `MovementExecutor`

从 `AutoNavigator` 和 `EventPathMover` 中提取重复逻辑：

- path cache
- path projection
- lookahead
- click cooldown
- anchor_step / anchor_probe
- fallback probe
- stuck detection

保留旧类调用新 executor。

验收：

- 普通导航行为不变。
- 事件移动行为不变。
- 日志增加 movement reason。

### 第 2 步：抽出 `RouteContext`

实现与方案 B 相同的路线投影和锚点消费模型。

验收：

- 普通导航和事件移动共用同一模型。
- 当前 `(2577,2474)` 重复规划问题被解决。

### 第 3 步：建立静态任务列表

新增：

- `required:<index>`
- `exit:main`

让 `AutoNavigator` 从静态任务列表取目标，而不是直接访问 `required_points`。

验收：

- 不开启事件时，路线行为和普通导航一致。
- required 完成和 exit 到达日志来自 task 状态。

### 第 4 步：把事件 task 映射为 `NavigationTask`

从 `EventMemory.active_tasks()` 生成动态 task。

第一版不改变 EventRunner，只让统一 scheduler 决定哪个 event task 可执行。

验收：

- 事件 UI 仍能显示 task。
- 传送门 pending 后，统一调度器能选择它。

### 第 5 步：统一调度器替换 UI 仲裁

删除主流程中的：

- `_allowed_event_task_ids`
- `event_blocks_auto_navigation`

改成：

```text
NavigationTaskController 输出当前 intent。
```

验收：

- 普通导航和事件不会同帧抢鼠标。
- running 事件锁定。
- 事件完成后自动回到下一个合适 task。

### 第 6 步：净化事件 handler

把 `PortalEventHandler` 中的靠近阶段逐步挪到 controller。

当前：

```text
handler distance > arrival_radius -> MOVE_TO
```

目标：

```text
controller distance > trigger_radius -> MovementExecutor
handler only handles click/key/wait/complete
```

验收：

- 手动测试传送门和自动导航传送门仍走同一管线。
- 新事件可以只声明 trigger target 和 handler 执行逻辑。

## 风险

### 风险 1：改动面大

方案 C 会影响：

- `core/auto_navigator.py`
- `core/events/coordinator.py`
- `core/events/path_mover.py`
- `core/events/runner.py`
- `core/events/types/portal/handler.py`
- `gui/modes/navigation_mode.py`
- overlay/status 相关代码

风险比方案 B 高。

### 风险 2：旧测试按钮和正式导航行为可能分叉

当前手动传送门测试依赖 `portal_test_controller.active` 放宽事件执行限制。

方案 C 下需要把“手动测试”也建模为一个调度模式：

```text
manual_event_test:
  only event tasks are eligible
  route required/exit tasks are disabled
```

否则测试按钮可能又和正式流程分叉。

### 风险 3：事件 handler 改造容易破坏传送门现有可用版本

传送门目前基本可用，直接拆 handler 可能引入回归。

缓解：

- 第一阶段 handler 不拆，只把 `MOVE_TO` 交给统一 executor。
- 等统一调度稳定后，再把靠近逻辑从 handler 挪走。

### 风险 4：调度器规则复杂化

多个事件、多个 required、出口、失败重试、冷却都会进入一个调度器。

缓解：

- 第一版只支持单条主路线 + pending/running event。
- 所有调度决策必须有日志。
- 不在第一版实现复杂优先级策略。

## 优点

- 架构最干净。
- 普通导航、事件、出口完全统一。
- 长期支持更多随机事件更稳。
- 可以彻底移除 UI 层仲裁补丁。
- 事件四阶段边界最清楚。

## 缺点

- 改动大，短期风险高。
- 实现周期长。
- 当前传送门可用逻辑可能被扰动。
- 需要更严格的日志和阶段验收。

## 与方案 B 的核心区别

方案 B：

```text
保留 AutoNavigator 和 EventPathMover 两个执行器。
新增 RouteProgressModel 统一进度和锚点消费。
事件仲裁仍在 UI 层或轻量桥接层完成。
```

方案 C：

```text
新增 NavigationTaskController。
普通 required、exit、event 全部变成 NavigationTask。
统一调度器决定当前任务。
统一 MovementExecutor 执行移动。
UI 只消费 NavigationIntent。
```

## 推荐结论

如果目标是长期架构正确，方案 C 是最终形态。

但如果当前目标是快速修复导航卡住并继续调传送门，方案 C 不适合作为下一步直接实施。更稳妥的路线是：

1. 先做方案 B，统一路线进度和锚点消费。
2. 等普通导航和传送门稳定后，再用方案 C 的思想逐步抽 `MovementExecutor` 和 `NavigationTaskController`。

也就是说，方案 C 更适合作为中期架构目标，而不是当前立即落地的首个修复。
