# 传送门事件案例文档：事件四阶段方法论

## 目标

这份文档用当前已经能跑通的 `portal` 传送门事件作为样例，固定事件系统的分析方式：

1. 事件识别：识别事件特征，并把事件定位到全局大地图坐标。
2. 导航到事件触发点，执行触发事件：事件可能先出现在小地图上，但人物还没到真实触发范围，需要接管移动。
3. 执行事件：触发后执行事件自身逻辑，不同事件差异最大。
4. 事件结束：每个事件必须有明确结束条件，防止重复触发或卡住主导航。

核心原则：传送门不是一次性补丁目标，而是用于验证“事件逻辑如何临时接管普通导航，并在结束后恢复导航”的第一个案例。

## 当前传送门链路

```text
NavigationModeWidget.navigation_loop()
  -> NavigationCore.localize()
  -> build_event_tick()
  -> EventCoordinator.update()
      -> EventMonitor.detect()
          -> PortalMinimapDetector.detect()
      -> EventPositionStabilizer.update()
      -> EventMemory.merge_observations()
      -> EventScheduler.pick()
      -> EventRunner.update()
          -> PortalEventHandler.update()
  -> EventActionExecutor.execute()
      -> MOVE_TO: NavigationModeWidget._execute_event_move_to()
          -> EventPathMover.step()
          -> MotionController.move_to_map_target()
      -> PRESS_KEY: MotionController.press_key("d")
      -> COMPLETE: EventMemory.complete_teleport_session()
```

手动“测试传送门”和自动导航现在走同一条事件管线。测试按钮只负责打开 `portal_test_controller.active`，真正执行仍然发生在每帧导航循环里，不是按钮槽函数里单独点击一次。

## 阶段 1：事件识别和全局定位

### 传送门当前实现

`PortalMinimapDetector` 在原始小地图截图 `raw_minimap_frame` 上做多模板、多尺度匹配，并用蓝/青色像素比例做二次过滤。它只输出 `EventDetection`：

```text
event_type = "portal"
local_minimap_pos = 小地图截图内的图标中心
confidence = 模板匹配分数
metadata = 模板名、尺度、bbox、颜色比例等调试信息
```

`EventPositionStabilizer` 再使用本帧墙体配准结果 `FrameRegistration` 把局部坐标投影到全局地图：

```text
event_global_pos = frame_origin_global + event_local_minimap_pos * draw_scale
```

随后它按事件类型和全局距离做多帧聚类，只有满足 `stable_frames` 和 `stable_variance` 的聚类才输出 `EventObservation`。`EventMemory` 只接受稳定后的 `EventObservation` 创建或更新 `EventTask`。

### 可通用部分

这一阶段应该作为所有小地图事件的通用管线：

- `EventDetection` 必须是局部候选，不直接信任单帧全局坐标。
- `EventPositionStabilizer` 负责把局部候选统一投影到全局地图，并多帧稳定。
- `EventMemory` 负责任务去重、确认、冷却、完成/忽略状态。
- `core/events/detectors/template_matcher.py` 可以复用给其它图标类事件。

### 事件特定部分

不同事件只替换这些内容：

- 图标模板或其它识别模型，例如模板、颜色规则、YOLO、特征匹配。
- 阈值配置，例如 `minimap_threshold`、`max_candidates`、`min_blue_ratio`。
- 去重/聚类参数，例如 `localization_cluster_radius`、`stable_variance`、`dedupe_radius`。
- `event_type`、优先级、显示名称和配置 schema。

## 阶段 2：导航到事件触发点并触发

### 传送门当前实现

`PortalEventHandler.update()` 根据人物和 `task.global_pos` 的距离决定下一步：

```text
distance > arrival_radius
  -> EventAction.move_to(task.global_pos, reason="move near portal")

arrival_radius >= distance > interact_radius
  -> EventAction.move_to(task.global_pos, metadata={"force_repeat_click": True})

distance <= interact_radius
  -> 先强制点击一次映射到地图传送门点的位置
  -> 等待 portal_point_click_wait_ms
  -> EventAction.press_key("d")
```

真正的移动由 `EventActionExecutor` 调用 `NavigationModeWidget._execute_event_move_to()`，再委托 `EventPathMover.step()`：

- 优先使用当前墙图和 `PathFinder.find_path()` 做每一段 A*。
- 普通导航里的 `guide_points` 作为有序软锚点传入路径规划；规划器按用户添加顺序把当前位置之前的锚点视为已路过，只推进到当前主目标投影之前的下一个前方锚点。
- 如果下一个锚点 A* 暂不可达，先返回 `anchor_probe` 朝该锚点短探测；到达锚点或探测点后重新规划，不能直接长距离冲最终事件点。
- 生成 lookahead 子目标，而不是一直点击事件点本身。
- 如果 A* 不可用，则用短距离 fallback probe 脱困，不生成很长的直线点击。
- 最终靠近阶段支持 `force_repeat_click=True`，允许同一个子目标按冷却重复点击，避免距离还差几像素但不再移动。

### 可通用部分

这一阶段也应该沉淀为所有事件复用的通用能力：

- handler 只返回 `EventAction.move_to(global_pos)`，不直接操作鼠标。
- `EventPathMover` 负责事件目标的 A* 路径、lookahead、点击节流、fallback probe。
- `guide_points` 的语义是软锚点：普通导航和事件导航都可以借助它们构造路径，但事件触发和事件完成恢复后都不能把它们当作必须追踪的顺序目标。
- `EventActionExecutor` 统一消费 `MOVE_TO`、`PRESS_KEY`、`CLICK_SCREEN`、`WAIT`、`COMPLETE`、`FAIL`。
- 事件不是一识别就抢控制，而是作为动态必经点参与主目标仲裁：普通导航开启时，只有事件任务距离不大于当前普通主目标距离，或事件已经 `RUNNING`，事件动作才会中断普通导航；被选中的事件动作占用当前帧时，普通自动导航必须暂停本帧点击，避免主路线和事件路线抢鼠标。

### 事件特定部分

不同事件只替换这些内容：

- 触发点坐标：可以是事件图标中心、图标附近偏移点、入口点、NPC 交互点等。
- 到达半径和交互半径：例如传送门用 `arrival_radius` 和 `interact_radius`。
- 触发动作：按键、屏幕点击、连续点击、等待提示、打开 UI 等。
- 最终靠近策略：是否需要 `force_repeat_click`，是否需要点击事件点本身。

### 当前架构问题

`EventPathMover` 已经是可复用模块，但事件移动执行入口仍在 `NavigationModeWidget._execute_event_move_to()`。这说明阶段 2 还没有完全从 GUI 页面抽离：

- 合理现状：当前为了接入已有 `MotionController`、`nav_core.wall_layer`、`PathFinder`，先放在导航页面里是可工作的。
- 架构风险：如果后续事件变多，`navigation_mode.py` 可能再次变成动作分发和策略堆积点。
- 建议方向：后续可以抽出 `EventMovementExecutor` 或 `NavigationEventBridge`，把 `_execute_event_move_to()`、`_event_move_lookahead_distance()`、事件 path overlay 输入整理成独立模块，`NavigationModeWidget` 只做 UI 生命周期和依赖注入。

## 阶段 3：执行事件

### 传送门当前实现

传送门事件比较特殊：触发和执行基本是同一件事。人物足够靠近后：

1. 先点击一次小地图定位出来的传送门映射点，让角色更贴近门。
2. 等待 `portal_point_click_wait_ms`。
3. 按 `D`。
4. 进入 `wait_result`，等待传送结果。

当前默认 `interaction="key"`，不再依赖主画面蓝紫实体确认。大画面传送门识别探针保留为技术资产，但不是当前传送门闭环的主流程。

注意：当前配置 schema 仍保留 `interaction="click"` 选项，但 `PortalEventHandler` 代码会记录 `portal forcing key interaction` 并继续走按 `D`。这属于配置契约残留，不应把它理解为当前可用的主画面点击分支。后续要么移除该选项，要么重新实现为独立的二阶段确认/点击策略。

### 可通用部分

这一阶段很难完全通用，但可以通用“动作表达方式”：

- `EventAction.press_key(key)` 表达按键。
- `EventAction.click_screen(screen_pos)` 表达屏幕点击。
- `EventAction.wait(ms)` 表达等待。
- handler 内部维护自己的状态机，但只能返回动作意图，不直接执行输入。

### 事件特定部分

不同事件的复杂度主要集中在这里：

- 传送门：靠近后按 `D`，执行逻辑很短。
- NPC/机关：可能需要识别 UI、选择选项、等待动画。
- 随机事件：可能需要战斗、拾取、绕路、确认完成条件。

所以阶段 3 应允许事件 handler 自己复杂，但必须遵守统一输入输出协议。

## 阶段 4：事件结束

### 传送门当前实现

传送门进入 `wait_result` 后不靠固定等待直接完成，而是检测是否真的传送：

- 人物全局坐标相对按 `D` 前移动超过 `teleport_min_distance`。
- 小地图人物周边环境签名变化超过 `environment_change_threshold`。
- 人物落在另一个已知传送门任务附近，并且明显比入口门更接近该出口门。

完成时 `PortalEventHandler` 返回：

```text
EventAction.complete(
  reason="portal teleport completed",
  metadata={
    completion_kind: "teleport",
    entry_task_id: 当前入口任务,
    entry_pos: 入口门坐标,
    exit_pos: 传送后人物坐标
  }
)
```

`EventRunner` 看到 `completion_kind="teleport"` 后调用 `EventMemory.complete_teleport_session()`：

- 标记入口传送门完成。
- 找到或创建出口传送门任务，并标记完成。
- 抑制入口/出口附近 pending 任务。
- 写入冷却，避免两门之间反复传送。

### 可通用部分

阶段 4 可以抽象为“完成策略”，但不同事件会有不同条件：

- 位移完成：人物位置发生明显变化。
- 环境完成：局部地图/画面签名变化。
- 目标消失：事件图标消失或 UI 消失。
- 任务完成：某个任务状态、奖励 UI、交互按钮消失。
- 成对完成：入口和出口、开始点和结束点需要同时标记完成。

### 事件特定部分

传送门的特殊点是“成对完成”。当入口传送到出口后，出口不能再被立即当成新事件执行，否则就会来回传送。这个逻辑不应该写成普通冷却的偶然效果，而应该作为 `teleport` 完成策略的一部分明确保留。

## 架构规范性检查

### 已经规范的部分

- `EventDefinition` 对外暴露完整事件包，TUI 只展示 `portal`，不展示 detector/handler 等内部模块。
- `PortalMinimapDetector` 只负责识别候选，不负责调度、记忆或执行。
- `EventPositionStabilizer` 已经把“事件局部坐标 -> 全局地图坐标”的逻辑从传送门里抽成通用模块。
- `EventMemory` 统一处理任务去重、完成、忽略、冷却，避免每个事件自己维护列表。
- `PortalEventHandler` 不直接调用鼠标键盘，只返回 `EventAction`。
- 手动测试和自动导航走同一条 handler/action 管线，避免测试代码和正式代码分叉。

### 仍需警惕的部分

- `NavigationModeWidget` 仍承担事件系统初始化、tick 构造、动作执行、overlay 刷新、手动测试按钮接入，职责偏重。
- 阶段 2 的 `MOVE_TO` 执行还挂在 `_execute_event_move_to()`，虽然内部委托了 `EventPathMover`，但动作执行上下文仍和 GUI 页面耦合。
- `PortalEventHandler` 内包含传送门点点击、按键、完成判断三类逻辑，当前可接受；如果后续传送门逻辑继续变复杂，应考虑拆成 `approach_policy`、`interaction_policy`、`completion_policy`。
- `main_view_confirmer` 目前保留为资产但默认不在主流程使用，文档和代码注释要持续保持一致，避免后续误以为传送门必须走大画面确认。

## 对后续事件的模板

新增事件时优先按下面模板设计，不要直接往导航循环里塞逻辑：

```text
core/events/types/<event>/
  definition.py      对外完整事件包：名称、默认配置、schema、detector、handler
  config.py          事件参数 dataclass
  minimap_detector.py 或 detector.py
                     只输出 EventDetection
  handler.py         只维护事件状态机，返回 EventAction
  assets.py          模板/模型/参数资产路径
```

事件生命周期必须先写清：

```text
识别：
  用什么图标/特征发现事件？
  输出的小地图局部坐标是什么？
  哪些阈值是事件特定配置？

定位：
  是否能直接复用 EventPositionStabilizer？
  如果事件点不等于图标中心，偏移规则在哪里定义？

导航触发：
  触发点是什么？
  arrival_radius / interact_radius 如何定义？
  是否需要最终 repeated click？
  是否会和主导航抢控制？

执行：
  触发后有哪些动作？
  是否需要 UI 识别、按键、点击、等待？

结束：
  成功条件是什么？
  失败/超时条件是什么？
  是否需要同时标记相关事件完成？
  完成后如何冷却，避免重复触发？
```

## 结论

当前代码已经基本符合“完整事件包 + 通用识别定位 + 通用动作协议 + 事件特定 handler”的方向。第 1 阶段已经比较通用；第 2 阶段已经有 `EventPathMover` 作为通用移动核心，但执行入口仍耦合在 `NavigationModeWidget`，后续新增事件前应优先把事件移动执行上下文继续抽离，防止事件越多，导航页面越重。
