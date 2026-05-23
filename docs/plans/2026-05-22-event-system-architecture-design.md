# Event System Architecture Design

## 目标
建立一个松耦合事件系统，让自动跑图可以持续监视游戏事件，并在触发事件时临时接管导航，完成事件后恢复原跑图流程。

第一版事件是 `portal` 传送门。对外它必须是一个完整事件类型，可在 TUI/配置界面中启用、禁用和调整策略。小地图图标识别、大画面实体确认、靠近、点击、完成判断都是 `portal` 内部实现细节。

## 非目标
- 不在第一版引入 YOLO 或训练流程。
- 不把事件逻辑直接写进 `NavigationModeWidget.navigation_loop()`。
- 不让具体事件 handler 直接调用鼠标、键盘或 UI。
- 不把 `PortalMinimapDetector`、`PortalMainViewConfirmer` 等内部模块暴露给 TUI 作为可选项。
- 不让大画面识别单独触发传送门事件；它只作为小地图事件发现后的二阶段确认。

## 核心原则
1. 外部按完整业务事件编排，内部按技术步骤拆模块。
2. 主导航只认识统一事件协议，不 import 具体事件类型。
3. 事件 handler 只返回动作意图，不直接执行输入。
4. 小地图事件检测使用 raw minimap frame，不使用定位后处理特征图。
5. 大画面识别通过统一 capture provider 获取截图，不在事件内部随意抓屏。
6. 坐标分层必须明确：`local_minimap_pos`、`global_map_pos`、`screen_pos` 不允许混用。
7. 每个事件包独立拥有 detector、handler、assets、config schema，新增事件不应修改已有事件代码。

## 推荐目录结构
```text
core/events/
  __init__.py
  models.py
  config.py
  registry.py
  coordinator.py
  monitor.py
  memory.py
  scheduler.py
  runner.py
  projector.py
  capture_provider.py
  action_executor.py
  overlay_models.py
  debug.py

core/events/base/
  __init__.py
  definition.py
  detector.py
  handler.py

core/events/detectors/
  __init__.py
  template_matcher.py

core/events/types/
  __init__.py
  portal/
    __init__.py
    definition.py
    config.py
    minimap_detector.py
    main_view_confirmer.py
    handler.py
    assets.py

assets/event_templates/portal/minimap/
  portal_minimap_01.png
  portal_minimap_02.png

assets/event_detectors/portal/main_view/
  blue_glow_detector_v1.json
  README.md

assets/event_profiles/
  default.json
```

## 对外协议
### EventDefinition
每个事件包只通过 `EventDefinition` 对外暴露。

```python
class EventDefinition:
    event_type: str
    display_name: str
    description: str

    def default_config(self) -> dict: ...
    def config_schema(self) -> dict: ...
    def create_detector(self, config) -> EventDetector: ...
    def create_handler(self, config) -> EventHandler: ...
```

`portal` 对外只注册一个定义：

```python
PortalEventDefinition(
    event_type="portal",
    display_name="传送门",
)
```

TUI/配置界面只读取 `EventDefinition.config_schema()`，不会知道 `PortalMinimapDetector` 或 `PortalMainViewConfirmer` 的存在。

### EventDetector
Detector 只负责观察，不负责记忆、调度或执行。

```python
class EventDetector:
    event_type: str

    def detect(self, tick: EventTick, config: EventConfig) -> list[EventObservation]: ...
```

### EventHandler
Handler 只负责当前事件下一步要做什么，不直接点击鼠标。

```python
class EventHandler:
    event_type: str

    def start(self, task: EventTask) -> None: ...
    def update(self, tick: EventTick, task: EventTask) -> EventAction: ...
    def reset(self) -> None: ...
```

### EventAction
事件系统对导航层输出统一动作。

```text
NONE              无动作，正常跑图
MOVE_TO           移动到地图全局坐标
CLICK_SCREEN      点击屏幕坐标
PRESS_KEY         按键
WAIT              等待若干毫秒或若干帧
COMPLETE          当前事件完成
FAIL              当前事件失败
PAUSE_NAVIGATION  暂停普通跑图
RESUME_NAVIGATION 恢复普通跑图
```

动作由 `ActionExecutor` 执行。handler 不能直接调用 `MotionController`、`InputDriver` 或 `pydirectinput`。

## 核心数据模型
### EventTick
由 `NavigationModeWidget.navigation_loop()` 每帧构造。

```python
EventTick:
    now_ms: int
    raw_minimap_frame: np.ndarray
    player_global_pos: tuple[int, int] | None
    player_local_minimap_pos: tuple[int, int] | None
    localization_confidence: float
    draw_scale: float
    map_name: str
    capture_provider: CaptureProvider
```

### EventObservation
Detector 输出的单帧观察结果。

```python
EventObservation:
    event_type: str
    local_minimap_pos: tuple[int, int] | None
    global_pos: tuple[int, int] | None
    confidence: float
    source: str
    observed_at_ms: int
    metadata: dict
```

### EventTask
进入记忆和调度后的事件实例。

```python
EventTask:
    id: str
    event_type: str
    global_pos: tuple[int, int]
    state: pending | running | completed | failed | ignored
    priority: int
    first_seen_ms: int
    last_seen_ms: int
    completed_at_ms: int | None
    attempts: int
    confidence: float
    metadata: dict
```

### EventAction
Handler 返回给主系统的动作意图。

```python
EventAction:
    type: str
    target_global_pos: tuple[int, int] | None
    screen_pos: tuple[int, int] | None
    key: str | None
    wait_ms: int | None
    reason: str
    metadata: dict
```

## 运行时数据流
```text
NavigationMode.navigation_loop()
  -> capture raw minimap frame
  -> NavigationCore.localize()
  -> build EventTick
  -> EventCoordinator.update(tick)
      -> EventMonitor.detect()
      -> EventMemory.merge_observations()
      -> EventScheduler.pick_active_task()
      -> EventRunner.update_active_task()
      -> returns EventAction | None
  -> if EventAction:
       ActionExecutor.execute(action)
     else:
       AutoNavigator normal route flow
  -> render event overlays
```

## 模块职责
### EventCoordinator
事件系统唯一入口。负责组合 monitor、memory、scheduler、runner，并对导航循环返回一个动作。

不做：
- 不做具体图像识别。
- 不做具体事件状态机。
- 不直接操作鼠标键盘。
- 不渲染 UI。

### EventMonitor
读取注册表中启用的事件定义，调用各事件 detector。

输入：
- `EventTick`
- 当前地图事件配置

输出：
- `list[EventObservation]`

### EventMemory
维护事件任务池。

职责：
- 将 observation 合并为 task。
- 按 `event_type + global_pos radius` 去重。
- 支持连续多帧确认。
- 事件离开小地图视野后仍保留。
- 完成事件进入冷却，避免重复触发。
- 失败事件可按配置重试或忽略。

第一版可只做内存态，不持久化到磁盘。后续如果需要跨进程恢复，再考虑 session 文件。

### EventScheduler
从 `EventMemory` 里选择当前要处理的事件。

默认排序：
1. enabled
2. state is pending/running
3. priority 高
4. 距离玩家近
5. first_seen_ms 早

第一版规则：
- 正在 running 的事件优先继续，除非失败或完成。
- 不抢占 running 事件。
- portal 优先级默认高于普通随机事件。
- 失败次数超过 `retry_limit` 后标记 ignored。

### EventRunner
维护当前 active task 和 handler 实例。

职责：
- task 从 pending 进入 running 时创建 handler。
- 调用 handler.update()。
- 根据 `COMPLETE` / `FAIL` 更新 task 状态。
- 事件结束后释放 active handler。

### EventProjector
负责坐标转换。

```text
local_minimap_pos
  + player_local_minimap_pos
  + player_global_pos
  + draw_scale
  -> global_map_pos
```

禁止 detector 自己散落实现坐标转换，避免绘图/定位/事件三套坐标不一致。

### CaptureProvider
给事件系统提供截图能力。

```python
class CaptureProvider:
    def capture_minimap_raw(self) -> np.ndarray: ...
    def capture_game_view(self) -> np.ndarray: ...
    def game_view_rect(self) -> dict: ...
```

第一版可以由 `NavigationModeWidget` 适配现有 `SquareScreenCapture`。事件内部只拿 provider，不直接 new capture。

### ActionExecutor
统一执行事件动作。

职责：
- `MOVE_TO` 交给现有 AutoNavigator/MotionController 路径。
- `CLICK_SCREEN` 交给现有 input driver。
- `PRESS_KEY` 后续扩展键盘输入。
- 统一做 debug 日志、窗口焦点、管理员权限、底部禁点等处理。

第一版可以先支持：
- `MOVE_TO`
- `CLICK_SCREEN`
- `WAIT`
- `COMPLETE`
- `FAIL`

## Portal 事件包设计
### 对外形态
`portal` 是一个完整事件。

TUI 只显示：
```text
[x] 传送门
  priority
  interaction: click | key
  minimap_threshold
  confirm_frames
  arrival_radius
  retry_limit
```

不会显示：
```text
PortalMinimapDetector
PortalMainViewConfirmer
PortalHandler
```

### 内部结构
```text
core/events/types/portal/
  definition.py
    PortalEventDefinition

  config.py
    PortalEventConfig

  minimap_detector.py
    PortalMinimapDetector
    使用 assets/event_templates/portal/minimap/*.png

  main_view_confirmer.py
    PortalMainViewConfirmer
    使用 assets/event_detectors/portal/main_view/blue_glow_detector_v1.json

  handler.py
    PortalEventHandler

  assets.py
    PORTAL_MINIMAP_TEMPLATES
    PORTAL_MAIN_VIEW_PARAMS
```

### Portal 内部状态机
```text
PENDING
  -> MOVE_NEAR_EVENT
  -> CONFIRM_MAIN_VIEW
  -> INTERACT
  -> WAIT_RESULT
  -> COMPLETE

失败分支：
  CONFIRM_MAIN_VIEW timeout -> RETRY_MOVE_OR_FAIL
  INTERACT no result -> RETRY_INTERACT_OR_FAIL
  retry_limit exceeded -> FAILED/IGNORED
```

### PortalMinimapDetector
职责：
- 在 raw minimap frame 上做多模板匹配。
- 输出 `EventObservation(event_type="portal")`。
- 只输出候选，不判断是否要处理。

内部规则：
- 使用已有 `portal_minimap_01.png`、`portal_minimap_02.png`。
- 同一帧多模板按中心距离去重。
- 连续 `confirm_frames` 后才进入 memory 的 confirmed task。

### PortalMainViewConfirmer
职责：
- 在靠近事件点后检查主游戏画面是否存在真实传送门实体。
- 只作为二阶段确认，不主动创建事件。

内部规则：
- 使用 `blue_glow_detector_v1.json`。
- 绿色 accepted 才可点击。
- 橙色 below-threshold 只写 debug，不触发动作。
- 当传送门实体不在视野或被遮挡时，0 accepted 是正确结果。

### PortalEventHandler
职责：
- 控制传送门事件完整执行过程。
- 对 runner 返回通用动作。

行为：
1. 如果距离 `task.global_pos` 大于 `arrival_radius`，返回 `MOVE_TO(task.global_pos)`。
2. 到达附近后，通过 `CaptureProvider.capture_game_view()` 获取主画面。
3. 调用 `PortalMainViewConfirmer`。
4. 如果确认到实体，返回 `CLICK_SCREEN(candidate.center)` 或 `PRESS_KEY("D")`。
5. 点击后进入等待状态。
6. 通过小地图图标消失、画面变化、短超时等条件判断完成。
7. 失败则按 `retry_limit` 重试，超过后返回 `FAIL`。

## 配置设计
### 地图级配置
推荐新增：

```text
map_data/<map_name>/event_config.json
```

示例：
```json
{
  "enabled": true,
  "profile": "default",
  "events": {
    "portal": {
      "enabled": true,
      "priority": 100,
      "interaction": "click",
      "minimap_threshold": 0.6,
      "confirm_frames": 2,
      "arrival_radius": 80,
      "retry_limit": 2,
      "cooldown_ms": 15000
    }
  }
}
```

### 全局默认配置
```text
assets/event_profiles/default.json
```

地图级配置只覆盖差异项。

### TUI 配置来源
TUI 不手写每个事件的 UI 字段。它读取：

```python
EventRegistry.definitions()
  -> EventDefinition.display_name
  -> EventDefinition.config_schema()
  -> current event_config.json value
```

这样新增事件后，只注册 `EventDefinition`，TUI 自动出现该事件配置。

## Overlay 设计
事件系统向 UI 输出 `EventOverlayModel`，UI 不读取内部 task。

```python
EventOverlayModel:
    event_id: str
    event_type: str
    display_name: str
    global_pos: tuple[int, int]
    state: str
    priority: int
    color: str
    label: str
```

UI 可显示：
- 已发现事件点。
- 当前处理事件。
- 失败/忽略事件。
- 事件置信度或 debug 标签。

## Debug 设计
每个事件包必须支持 debug 输出，但 debug 不影响主流程。

建议目录：
```text
debug/events/<session_id>/<event_type>/<event_id>/
  minimap_raw_*.png
  minimap_match_*.png
  main_view_raw_*.png
  main_view_debug_*.png
  state_log.jsonl
```

日志最少包含：
- task id
- state transition
- action returned
- detector confidence
- screen/global coordinates
- failure reason

## 失败和恢复
### 通用失败
- 低定位置信度：事件系统暂停执行，等待定位恢复。
- 事件目标不可达：返回 `FAIL` 或降级重试。
- 点击后无结果：重试 interaction。
- 多次失败：标记 ignored，并进入 cooldown。

### 恢复普通跑图
事件结束后不重置整个 AutoNavigator。推荐：
- 暂停普通跑图时保存 running 状态。
- 事件完成后让 AutoNavigator 根据当前定位重新接入最近路线点。
- 不恢复旧的局部路径，因为事件过程中人物已经移动。

## 与现有代码的接入点
### NavigationModeWidget
最小修改点：
1. 初始化 `EventCoordinator`、`CaptureProvider`、`ActionExecutor`。
2. `navigation_loop()` 中构造 `EventTick`。
3. 在 AutoNavigator 之前调用 `EventCoordinator.update(tick)`。
4. 如果返回事件动作，则执行动作并跳过普通 auto move。
5. 渲染 `EventOverlayModel`。

### AutoNavigator
第一版不改内部算法。事件 `MOVE_TO` 可以复用现有移动能力，但动作入口应由 `ActionExecutor` 统一调用。

### MotionController/InputDriver
不让事件 handler 直接调用。只允许 `ActionExecutor` 调用。

### RouteManager
不把事件存进 route。路线点和事件点是两套概念。

## 第一阶段实现边界
第一阶段只实现完整 `portal` 事件闭环：
1. 注册 `PortalEventDefinition`。
2. 读取/保存 `event_config.json`。
3. 小地图识别 portal。
4. EventMemory 去重和确认。
5. Scheduler 选中 portal。
6. Handler 移动到 portal 附近。
7. 大画面确认 portal 实体。
8. 返回点击动作。
9. 完成/失败后恢复跑图。

不实现：
- 多随机事件。
- YOLO。
- 复杂抢占。
- 持久化 session memory。
- 事件策略编辑器的高级 UI。

## 审核问题
1. `event_config.json` 是否作为独立配置文件，不塞进主 `config.json`？
2. TUI 是否只展示完整事件，例如“传送门”，不展示内部 detector/confirmer？
3. 第一版 scheduler 是否采用“不抢占 running 事件”的简单策略？
4. 传送门完成判断第一版是否允许先用“点击后等待 + 小地图图标消失/画面变化”这种保守判断？
5. 事件结束后是否按“当前定位重新接入路线”，而不是恢复旧路径？
