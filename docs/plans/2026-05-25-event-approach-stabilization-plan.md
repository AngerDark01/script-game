# Event Approach Stabilization Plan

## Goal
让事件任务在进入真实游戏视野后先用短距离 A* 收敛到事件附近，停稳 0.5-1s，再释放给具体事件 handler 执行触发动作；第一版只优化事件，不改锚点逻辑。

## Current Source Chain

- `gui/modes/navigation_mode.py:_navigation_loop_unified()` 每帧截图、定位、构造 `EventTick`，再调用 `NavigationTaskController.update()`。
- `core/navigation_tasks/controller.py:_update_event_task()` 当前先调用 `event_coordinator.run_task()`，再把 `EventAction.MOVE_TO/PRESS_KEY/WAIT/COMPLETE` 转成导航意图。
- `core/events/types/portal/handler.py:PortalEventHandler.update()` 当前在人物进入 `interact_radius` 后会先强制点传送门点，再等待 `portal_point_click_wait_ms`，然后按 `D`。
- `core/navigation_tasks/movement_executor.py:MovementExecutor.step()` 当前负责 A*、锚点路径、lookahead、点击冷却、卡住恢复；普通事件移动也复用它。
- `gui/modes/navigation/viewport_overlay.py:game_view_scene_rect()` 已经用 `game_view_map_size` 画橙色真实游戏视野框，可复用同一几何判断事件是否进入真实视野。

## Architecture Decision

新增一个导航层的事件靠近门禁，不放进 `PortalEventHandler`：

```text
core/navigation_tasks/event_approach.py
```

原因：

- 事件靠近是导航控制问题，不是传送门业务问题。
- 后续其他事件也要复用“进入真实视野 -> 近距离收敛 -> 停稳 -> 执行事件”的流程。
- 必须在调用 `event_coordinator.run_task()` 之前拦截，否则 `PortalEventHandler` 会提前改变内部状态并返回 `PRESS_KEY`。

## Two-Phase Behavior

### Phase 1: Minimap Visible, Real View Not Visible

事件已经被小地图识别并定位，但事件点不在橙色真实视野框内：

```text
event_pos not inside game_view_rect(player_pos, game_view_map_size)
```

行为：

- 继续用当前 A* + 锚点导航向事件点移动。
- 不调用事件 handler。
- 不允许按 D。
- 不允许强制点击事件点。

### Phase 2: Event Inside Real Game View

事件点进入橙色真实视野框后：

```text
event_pos inside game_view_rect(player_pos, game_view_map_size, margin)
```

行为：

- 切换为事件近距离收敛。
- 仍用 A*，因为真实视野内也可能有墙。
- lookahead 缩短，点击冷却加长。
- 到达事件附近后停止移动点击。
- 稳定等待 0.5-1s。
- 满足停稳条件后才调用具体事件 handler。

## Simplified Approach Algorithm

第一版不做环形采样，不猜“门边站位点”。直接利用 A* 路径末端。

输入：

```text
player_pos
event_pos
wall_map
pathfinder
explored_map
route_context
```

步骤：

1. 对 `player_pos -> event_pos` 做 A*，仍允许当前路线锚点参与。
2. 从 A* 路径末端取一个“停止点”：

```text
approach_target = path 上距离 event_pos 前方 approach_stop_distance 的点
```

默认：

```text
approach_stop_distance = max(12, interact_radius * 0.7)
```

3. 如果人物距离 `approach_target` 仍较远，沿路径短 lookahead 点击：

```text
event_approach_lookahead = 24-40
event_approach_click_cooldown_ms = 700-1000
```

4. 如果人物到 `approach_target` 已进入停止半径：

```text
distance(player_pos, approach_target) <= event_stop_radius
```

停止点击，进入 settle。

5. settle 期间只等待，不再移动点击。
6. settle 成功后，再检查：

```text
distance(player_pos, event_pos) <= interact_radius
```

满足后释放给 handler；不满足则允许一次精确事件点点击，再重新 settle。

## State Machine

```text
FAR
  event not in real view
  use normal MovementExecutor step

VISIBLE
  event enters real view
  compute A* path and approach_target

APPROACH
  short lookahead, slow click cadence

SETTLING
  no movement clicks
  wait for stable position

READY
  release to EventCoordinator/EventRunner/PortalEventHandler

RELEASED
  handler owns execution until COMPLETE/FAIL
```

Important rule:

```text
Once READY releases a task to handler, the approach gate must not block that task again until terminal.
```

This prevents portal `wait_result` from being interrupted after pressing `D`.

## Stop And Stable Conditions

Default conditions:

```text
distance(player_pos, approach_target) <= event_stop_radius
no movement click in last event_settle_ms
stable frame count >= event_stable_frames
frame-to-frame player movement <= event_max_motion_per_frame
localization confidence >= event_min_confidence
```

Recommended defaults:

```text
event_visible_margin = 30
event_approach_lookahead = 36
event_approach_click_cooldown_ms = 800
event_stop_radius = 18
event_settle_ms = 800
event_stable_frames = 2
event_max_motion_per_frame = 8
event_min_confidence = 0.58
event_force_click_after_settle_fail = true
```

## Files To Change

### 1. `core/navigation_tasks/event_approach.py`

Add a new controller and result model:

```python
@dataclass
class EventApproachResult:
    ready: bool
    intent: NavigationIntent | None = None
    phase: str = "far"
    approach_target: tuple[float, float] | None = None
    reason: str = ""


class EventApproachController:
    def reset(self) -> None: ...
    def release_task(self, task_id: str) -> None: ...
    def is_released(self, task_id: str) -> bool: ...
    def update(...) -> EventApproachResult: ...
```

Key responsibilities:

- Track current event task id.
- Determine real-view visibility from `game_view_map_size`.
- Use existing `MovementExecutor` to obtain A* path.
- Override near-event subgoal to stop before event center.
- Track settle window and stable frames.
- Emit compact `nav_log()` records:

```text
event approach phase
event approach visible
event approach target
event approach settling
event approach ready
event approach blocked
```

### 2. `core/navigation_tasks/models.py`

Optionally extend `MovementStep` with:

```python
remaining_distance: float = 0.0
```

This is useful for approach diagnostics but not mandatory if `EventApproachController` computes distance itself from the path.

### 3. `core/navigation_tasks/controller.py`

Add:

```python
self.event_approach = EventApproachController()
```

Before this line in `_update_event_task()`:

```python
action = event_coordinator.run_task(event_task_id, event_tick)
```

insert the approach gate:

```text
if event task not released:
  approach_result = event_approach.update(...)
  if not approach_result.ready:
    return approach_result.intent
  event_approach.release_task(task.id)

action = event_coordinator.run_task(...)
```

On `COMPLETE` / `FAIL`:

```python
self.event_approach.reset()
```

On task transition:

```python
if selected.id != self.active_task_id:
    self.event_approach.reset()
```

### 4. `gui/navigation_params.py`

Add navigation-level defaults:

```python
event_visible_margin: int = 30
event_approach_lookahead: int = 36
event_approach_click_cooldown_ms: int = 800
event_stop_radius: int = 18
event_settle_ms: int = 800
event_stable_frames: int = 2
event_max_motion_per_frame: float = 8.0
event_force_click_after_settle_fail: bool = True
```

These belong to navigation config because they control movement behavior, not portal business.

### 5. `gui/dialogs/nav_params_dialog.py`

Expose the above parameters in a separate page/group:

```text
事件靠近/停稳
```

Each row should explain the effect:

- 真实视野边距
- 事件近距离 lookahead
- 事件近距离点击冷却
- 事件停靠半径
- 停稳等待时间
- 停稳帧数
- 最大停稳位移
- 停稳失败后是否精确点事件点

### 6. `gui/modes/navigation_mode.py`

In `_configure_navigation_task_controller()` copy nav config into:

```python
self.navigation_task_controller.event_approach.configure(...)
```

Do not read UI values directly in the approach controller.

### 7. `core/events/types/portal/handler.py`

Keep portal handler mostly unchanged.

Expected behavior after approach gate:

- When handler starts receiving updates, player should already be inside or very near `interact_radius`.
- Existing `portal point click before interaction -> wait -> press D -> wait_result` can stay.
- Later, `interaction_key` can be made configurable, but this plan keeps default `D`.

## Verification Plan

The project preference is not to spend time on broad logic tests. Verification should be:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile `
  core\navigation_tasks\event_approach.py `
  core\navigation_tasks\controller.py `
  gui\navigation_params.py `
  gui\dialogs\nav_params_dialog.py `
  gui\modes\navigation_mode.py
```

Manual in-game verification:

1. Start navigation.
2. Let portal appear only in minimap view.
3. Confirm logs show:

```text
event approach phase=far visible=False
```

4. Move until portal enters orange real-view box.
5. Confirm logs show:

```text
event approach phase=approach visible=True
event approach settling
event approach ready
portal point click before interaction
portal interaction key
```

6. Confirm no `portal interaction key` appears before `event approach ready`.
7. Confirm after `portal interaction key`, approach gate does not re-block `portal wait_result`.

## Expected Log Signal

Good run should look like:

```text
nav task selected | selected=event:portal:1
event approach far | visible=False
event approach visible | visible=True
event approach target | approach_target=(...)
event approach settling | stable=1
event approach ready | stable=2 waited_ms=800
portal handler start
portal point click before interaction
portal interaction key
portal teleport completed
teleport session completed
```

Bad run diagnostics:

```text
event approach path unavailable
event approach settle reset | reason=moved_too_much
event approach blocked | reason=not_visible
event approach force target click
```

## Risks And Guards

- If `event_coordinator.run_task()` is not called until READY, event memory task remains PENDING longer. This is acceptable because `NavigationTaskController.active_task_id` locks the selected event.
- If localization is offset, settle may never become READY. Logs must include raw/control positions and confidence.
- If A* cannot reach event_pos because the icon is on a wall, first version may stop too far. The fallback is one exact event-point click after settle failure, but no immediate D until settle succeeds.
- If `game_view_map_size` is too small or too large, phase transition will be wrong. Keep it UI-configurable and log visibility margin.

## Out Of Scope

- No anchor behavior changes.
- No portal detection false-positive fix in this plan.
- No second portal-session memory/cooldown rewrite in this plan.
- No YOLO or main-view visual detector in this plan.
