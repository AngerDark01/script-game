NavigationModeWidget.navigation_loop()
  -> AutoNavigator.update()
      -> observe_localization()
      -> _align_route_to_current_position()
      -> _select_segment_target()
      -> plan_path_with_optional_anchors()
      -> _follow_segment()
  -> MotionController.move_to_map_target()
```

关键文件：

- `core/auto_navigator.py`
- `core/anchor_path.py`
- `gui/modes/navigation_mode.py`

当前真实主目标只有两类：

- `required_points[required_index]`
- `exit_region.center`

`guide_points` 不再是主目标，只作为软锚点参与规划。

### 锚点规划链路

当前共享规划入口：

```text
plan_path_with_optional_anchors(
  start_pos,
  target_pos,
  anchors=guide_points,
)
```

当前规则：

1. 把 `guide_points` 按用户添加顺序去重。
2. 把当前位置投影到 `guide_points` 折线，得到 `start_progress`。
3. 把目标投影到 `guide_points` 折线，得到 `target_progress`。
4. 找出 `start_progress` 和 `target_progress` 之间的前方锚点。
5. 如果有前方锚点，只 A* 到第一个锚点，返回 `anchor_step`。
6. 如果该锚点不可达，返回朝锚点方向的 `anchor_probe`。
7. 如果没有前方锚点，才 A* 到真实目标。

当前问题：函数内部只根据当前位置即时推断下一个锚点，没有外部“已消费锚点”状态。

### 事件链路

当前事件入口：

```text
NavigationModeWidget.navigation_loop()
  -> EventCoordinator.update()
      -> EventMonitor.detect()
      -> EventPositionStabilizer.update()
      -> EventMemory.merge_observations()
      -> EventScheduler.pick()
      -> EventRunner.update()
          -> PortalEventHandler.update()
  -> EventActionExecutor.execute()
      -> MOVE_TO: NavigationModeWidget._execute_event_move_to()
          -> EventPathMover.step()
              -> plan_path_with_optional_anchors()
          -> MotionController.move_to_map_target()
```

关键文件：

- `core/events/coordinator.py`
- `core/events/runner.py`
- `core/events/path_mover.py`
- `core/events/types/portal/handler.py`
- `gui/modes/navigation_mode.py`

事件移动也复用 `plan_path_with_optional_anchors()`，但事件移动状态由 `EventPathMover` 自己维护，和 `AutoNavigator` 的路径状态分离。

### 当前仲裁逻辑

`NavigationModeWidget._allowed_event_task_ids()` 当前用直线距离仲裁事件：

```text
route_target = auto_navigator.segment_target_for_position(player_pos)
route_distance = point_distance(player_pos, route_target)

if task_distance <= route_distance:
    allow event
```

问题：直线距离不等于沿 `guide_points` 路线走廊的前进距离。事件可能直线近但路线绕远，也可能路线前方更合理但直线稍远。

## 当前冲突根因

### 冲突 1：锚点到达半径和跳过半径不一致

当前代码行为：

- `AutoNavigator._follow_segment()` 用 `arrival_radius = 26` 判断锚点段到达。
- `anchor_path._ordered_corridor_anchors()` 内部 `reached_radius` 约为 `8`。

结果：

```text
角色距离锚点 8~26 像素：
  AutoNavigator 认为锚点已到达，清路径重规划。
  anchor_path 认为锚点还没跳过，又选同一个锚点。
  下一帧继续规划同一个 anchor_step，不发真实点击。
```

这就是最新日志里 `(2577,2474)` 反复规划的直接原因。

### 冲突 2：锚点没有“消费状态”

当前 `anchor_path.py` 每次根据当前位置重新推断前方锚点。它不知道上一段已经选择过哪个锚点，也不知道该锚点是否已经被逻辑消费。

因此即使普通导航认为某个 `anchor_step` 到达，只要当前位置投影没有越过足够多，下一次规划仍可能选择同一个锚点。

### 冲突 3：必经点和事件没有统一排序

当前普通导航是强顺序：

```text
required_points[0] -> required_points[1] -> required_points[2] -> exit
```

事件是额外仲裁：

```text
如果事件直线距离 <= 当前普通目标直线距离，则事件可执行。
```

这会导致三类问题：

- 事件完成后，普通导航可能回到原 required_index。
- 事件如果在路线前方但直线略远，可能被压住。
- 事件如果直线近但在路线回头方向，可能错误接管。

### 冲突 4：普通导航和事件移动各自维护路径状态

`AutoNavigator` 有：

- `current_path`
- `current_path_goal`
- `current_path_kind`
- `last_click_target`
- `route_progress`

`EventPathMover` 有：

- `path`
- `path_goal`
- `path_kind`
- `last_click_target`

两者共享同一个规划函数，但不共享路线进度上下文，因此对同一个锚点是否已跳过的判断可能不同。

## 设计原则

1. `guide_points` 是路线走廊，不是任务目标。
2. `required_points` 是静态主目标。
3. `event task` 是动态主目标。
4. 所有目标都先投影到同一条 `guide_points` 折线上，再比较“路线前进距离”。
5. 锚点一旦到达，必须被消费，不能只清路径。
6. 事件运行中必须锁定，不能被普通导航打断。
7. 事件完成后必须触发普通导航重新对齐 `required_index` 和路线进度。
8. 所有重规划必须记录原因，不能只打印 `auto path planned`。

## 新增模块建议

### `core/route_progress.py`

职责：把 `guide_points` 抽象成可查询、可投影、可消费的路线走廊。

建议数据结构：

```python
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
class RouteTarget:
    kind: str  # required | exit | event
    id: str
    point: tuple[float, float]
    progress: float | None
    priority: int = 0
```

建议核心类：

```python
class RouteProgressModel:
    def __init__(self, guide_points, *, reached_radius: float):
        ...

    def project(self, point) -> RouteProjection | None:
        ...

    def progress_of(self, point) -> float | None:
        ...

    def anchors_between(
        self,
        start_progress: float,
        target_progress: float,
        *,
        consumed_until_index: int | None,
    ) -> list[RouteAnchor]:
        ...

    def next_anchor(
        self,
        current_pos,
        target_pos,
        *,
        consumed_until_index: int | None,
    ) -> RouteAnchor | None:
        ...

    def consumed_index_for_position(self, point) -> int:
        ...
```

### 为什么不继续放在 `anchor_path.py`

`anchor_path.py` 当前是“规划函数”，但现在需要长期持有运行时语义：

- 当前路线进度
- 已消费锚点
- 必经点投影
- 事件投影
- 路线偏离

这些不是纯路径规划职责，应该独立出来，供 `AutoNavigator`、`EventPathMover` 和事件仲裁共同使用。

## 修改现有模块

### `core/anchor_path.py`

保留职责：只负责“给定当前路线上下文，生成一段路径”。

建议改动：

```python
def plan_path_with_optional_anchors(
    *,
    wall_map,
    pathfinder,
    start_pos,
    target_pos,
    explored_map=None,
    route_model=None,
    consumed_anchor_index=None,
    reached_radius=26.0,
    probe_distance=84.0,
) -> AnchorPathResult | None:
    ...
```

`AnchorPathResult` 增加：

```python
anchor_index: int | None
anchor_progress: float | None
plan_reason: str
```

关键规则：

- `reached_radius` 必须和调用方的锚点到达半径一致。
- 如果返回 `anchor_step`，必须带上 `anchor_index`。
- 调用方到达该锚点后，用 `anchor_index` 更新“已消费锚点”。

### `core/auto_navigator.py`

保留职责：普通导航状态机。

新增运行时字段：

```python
self.route_model = None
self.consumed_anchor_index = -1
self.current_anchor_index = None
self.last_replan_reason = ""
```

普通导航每帧逻辑调整：

1. `observe_localization()` 后，用 `RouteProgressModel.project()` 更新 `route_progress`。
2. `_align_route_to_current_position()` 使用统一投影结果推进 `required_index`。
3. `_plan_segment()` 调用 `plan_path_with_optional_anchors(..., consumed_anchor_index=self.consumed_anchor_index)`。
4. 如果返回 `anchor_step`，记录 `current_anchor_index`。
5. `_follow_segment()` 判断锚点到达时：

```text
if current_path_kind in anchor_step/anchor_probe and distance_to_path_goal <= anchor_reached_radius:
    consumed_anchor_index = max(consumed_anchor_index, current_anchor_index)
    clear path
    state = PLAN_SEGMENT
```

6. 事件完成或导航重启时，使用当前位置重新恢复 `consumed_anchor_index` 和 `required_index`。

### `core/events/path_mover.py`

保留职责：事件 `MOVE_TO` 的路径和点击节流。

新增字段：

```python
self.consumed_anchor_index = -1
self.current_anchor_index = None
```

调整：

- `step(..., route_model=None, soft_anchors=None)` 优先使用 `route_model`。
- 到达 `anchor_step` 的 `path_goal` 时消费 `current_anchor_index`。
- target 变化超过阈值时重置事件移动自己的锚点状态。
- 事件结束、按键、屏幕点击时 `reset()` 清理事件移动锚点状态。

注意：事件移动仍不直接推进普通导航的 `required_index`。事件完成后由 UI 或桥接层通知 `AutoNavigator.reset_with_current_position()`，让普通导航重新对齐。

### `gui/modes/navigation_mode.py`

短期保留入口，但调整仲裁：

当前：

```text
task_distance <= route_distance
```

改为：

```text
route_target_progress = route_model.progress_of(current_route_target)
event_progress = route_model.progress_of(event.global_pos)
player_progress = route_model.project(player_pos).progress

event_ahead = event_progress >= player_progress - small_margin
event_before_route_target = event_progress <= route_target_progress + event_margin

if event_ahead and event_before_route_target:
    allow event
```

如果事件无法投影到路线，降级为当前直线距离逻辑，但必须打印：

```text
event arbitration fallback euclidean
```

事件 action 接管规则保持：

- `MOVE_TO`
- `CLICK_SCREEN`
- `PRESS_KEY`
- `WAIT`

都会阻断普通导航本帧。

### `core/events/coordinator.py`

保持当前结构，不需要大改。

可选增强：

- `update()` 传入 `route_context` 给 scheduler。
- 或保持 `allowed_task_ids` 由 UI 计算，暂不扩大 coordinator 职责。

方案 B 推荐先不改 coordinator，避免扩大改动面。

## 统一目标排序规则

### 静态主目标

普通导航的静态目标仍然是：

```text
required_points[required_index] -> exit
```

但 `required_index` 不再只靠距离推进，而是用统一路线进度推进。

### 动态事件目标

事件目标不进入 `required_points` 列表，不修改 route.json。

它在运行时被视为：

```text
RouteTarget(kind="event", id=task.id, point=task.global_pos)
```

事件是否接管，按规则判断：

```text
如果已有 active_task：
    继续执行 active_task
否则：
    获取当前普通主目标 route_target
    比较 player -> event 和 player -> route_target 的路线进度距离
    事件在当前前方且不晚于当前普通目标太多，则允许事件接管
```

### 事件完成后

事件完成后执行：

```text
AutoNavigator.reset_with_current_position(current_pos)
AutoNavigator.route_alignment_done = False
```

下一帧普通导航会重新：

- 计算 route_progress
- 跳过已经越过的 required_points
- 计算 consumed_anchor_index
- 从当前位置继续走向下一个普通主目标

## 当前 Aa 路线示例

`map_data/Aa/route.json` 当前关键点：

```text
required 3 = (2608,2452)
guide 5   = (2577,2474), progress=337.69
required 3 progress ~= 375.68
guide 6   = (2699,2393), progress=484.13
exit      = (3892,2032)
```

当前卡住过程：

```text
当前位置 progress ~= 337.70
目标 required=(2608,2452)
规划器继续选择 guide 5=(2577,2474)
AutoNavigator 又认为 guide 5 已到达
循环重复
```

方案 B 后：

```text
到达 guide 5:
  consumed_anchor_index = 4

下一次规划 required=(2608,2452):
  next_anchor 不允许再返回 index <= 4 的锚点
  直接规划到 required 3，或选择 guide 6，取决于 target_progress

如果 required 3 progress 已越过:
  required_index 推进到 exit
```

## 日志要求

新增或调整日志，必须能回答“为什么重规划”。

普通导航日志：

```text
auto replan
  reason=anchor_reached|path_deviation|stuck|target_changed|route_aligned|missing_path
  player=(x,y)
  route_progress=...
  consumed_anchor_index=...
  current_anchor_index=...
  target_kind=required|exit
  target=(x,y)
```

事件仲裁日志：

```text
event arbitration route-progress
  player_progress=...
  route_target=...
  route_target_progress=...
  event=portal:1
  event_progress=...
  decision=allow|hold
  reason=event_before_route_target|event_behind_player|fallback_euclidean
```

事件移动日志：

```text
event path planned
  target=(x,y)
  path_kind=anchor_step|anchor_probe|planned|fallback
  anchor_index=...
  consumed_anchor_index=...
  reason=target_changed|anchor_reached|deviation|fallback_retry
```

## 迁移步骤

### 第 1 步：抽出路线进度模型

新增 `core/route_progress.py`。

从 `core/anchor_path.py` 移出或复用这些逻辑：

- `_dedupe_anchor_order`
- `_anchor_cumulative_lengths`
- `_project_progress_on_polyline`
- `anchor_route_progress`
- `anchor_progress_map`

验收：

- 不改变现有导航行为。
- `AutoNavigator` 仍可调用旧 helper。

### 第 2 步：锚点消费状态接入普通导航

修改：

- `core/anchor_path.py`
- `core/auto_navigator.py`

完成：

- `AnchorPathResult` 返回 `anchor_index`。
- `AutoNavigator` 到达锚点后消费该 index。
- 锚点跳过半径和到达半径统一。

验收：

- `event_runtime.log` 不再出现同一个 `anchor_step path_goal=(2577,2474)` 高频重复。
- 到达一个锚点后，下一次规划不会再选择同一锚点。

### 第 3 步：普通导航 required 对齐改用统一模型

修改：

- `AutoNavigator._route_progress_for_position`
- `AutoNavigator._required_progress_map`
- `AutoNavigator._align_route_to_current_position`
- `AutoNavigator.segment_target_for_position`

完成：

- `required_index` 按统一 `RouteProgressModel` 推进。
- 导航重启时能从当前位置恢复 `required_index` 和 `consumed_anchor_index`。

### 第 4 步：事件仲裁改用路线进度

修改：

- `NavigationModeWidget._allowed_event_task_ids`

完成：

- 事件与当前普通主目标按路线进度比较。
- 无法投影时才用直线距离兜底。
- running 事件继续锁定执行。

### 第 5 步：事件移动接入锚点消费

修改：

- `core/events/path_mover.py`
- `NavigationModeWidget._execute_event_move_to`

完成：

- `EventPathMover` 也消费锚点 index。
- 事件目标变化时重置事件移动锚点状态。
- 事件完成后通知普通导航重新对齐。

## 风险

### 风险 1：路线投影错误

如果 `guide_points` 折线有回头、交叉或贴墙过近，最近点投影可能跳到错误段。

缓解：

- `RouteProjection` 记录 `segment_index` 和 `deviation`。
- 如果 deviation 太大，则不使用 route-progress 仲裁，降级到直线距离。
- 日志打印 `projection_deviation`。

### 风险 2：锚点被过早消费

如果角色定位抖动到锚点半径内，但实际没走过，可能跳过用户定制路径。

缓解：

- 锚点消费需要连续 2 帧到达，或路线进度超过该锚点 progress。
- 对 `anchor_probe` 和 `anchor_step` 区分：`anchor_probe` 到达短探测点时不一定消费最终锚点，除非探测点足够接近锚点。

### 风险 3：事件抢主线

事件作为动态目标后，可能在用户不想处理时接管。

缓解：

- 保留事件 UI 开关。
- 每类事件可配置 `route_arbitration_mode`：
  - `off`
  - `before_current_target`
  - `nearest`
  - `priority`

第一版只实现 `before_current_target`。

### 风险 4：普通导航和事件移动状态仍分离

方案 B 保留两个移动器，可能仍有少量状态不一致。

缓解：

- 两者都使用同一个 `RouteProgressModel`。
- 两者都使用相同 `reached_radius`。
- 事件结束后强制普通导航重对齐。

## 优点

- 改动范围可控。
- 能直接解决当前锚点反复规划。
- 不推翻事件系统现有结构。
- 传送门和未来事件都能复用统一路线进度。
- 比方案 C 更容易边测试边落地。

## 缺点

- 普通导航和事件移动仍是两个执行器。
- `NavigationModeWidget` 仍然承担事件动作桥接职责。
- 长期看仍可能需要抽出统一任务队列。

## 推荐结论

如果当前目标是尽快让“普通导航 + 传送门事件 + 锚点路线”稳定可用，推荐选方案 B。

方案 B 是当前项目最合适的下一步：它先统一路线进度和锚点消费，解决真实卡点，同时不大规模重写事件系统。
