# CODEBASE

## 1. 项目概览
PySide6 + OpenCV 的实时小地图拼接与导航工具。绘图模式从游戏小地图截图提取 HSV/墙体特征并写入 `map_data/<name>/map_data.npz`；导航模式读取同一份地图数据、用实时截图定位玩家全局地图坐标，并可基于用户设置的出口、必经点、途经点执行自动导航。当前任务相关的关键约束是：定位截图范围、地图全局坐标、真实主画面点击范围必须分离，不能用旧偏移参数修正定位。

## 2. 目录结构图
```text
main.py - 创建 QApplication 和 MainWindow。
gui/app_context.py - 初始化共享服务：ScreenCapture、MapStitcher、PlayerTracker、PathFinder。
gui/main_window.py - 创建绘图/导航两个模式并共享 AppContext。
gui/navigation_params.py - 定义 NavConfig、RecognizerParams、NavPreferences，并负责 config.json 序列化契约。
gui/dialogs/nav_params_dialog.py - 导航参数 UI，使用 widget_map 将控件变化写回 NavConfig。
gui/dialogs/event_manager_dialog.py - 独立事件管理窗口，展示完整事件选配和运行中事件任务状态。
gui/modes/navigation_mode.py - 导航模式主 UI、地图加载、定位循环、路线编辑、自动导航和范围框显示。
gui/modes/mapping_widget.py - 绘图模式，保存 map_data.npz 和地图 config.json。
core/navigation_core.py - 导航定位核心，将实时小地图截图匹配到全局地图坐标。
core/stitcher_core.py - 建图拼接核心，维护 wall_layer/explored_map/current_pos。
core/pathfinder.py - A* 寻路，输入输出地图全局坐标。
core/path_utils.py - 路径平滑、投影、插值、出口区域判断工具。
core/auto_navigator.py - 自动导航状态机，输出路径子目标和是否应点击。
core/motion_controller.py - 将地图方向转换成真实屏幕鼠标点击。
core/events/models.py - 事件系统通用数据结构和动作类型。
core/events/config.py - 事件配置默认值、地图级 event_config.json 加载/保存和 TUI 事件选项输出。
core/events/registry.py - 完整事件包注册表，TUI/Coordinator 只通过它枚举事件。
core/events/coordinator.py - 导航循环调用的事件系统统一入口。
core/events/memory.py - 事件实例生命周期、去重、确认帧、完成冷却和失败状态管理。
core/events/monitor.py - 调用启用事件的 detector，并缓存 detector 避免每帧重载模板。
core/events/scheduler.py - 在 pending/running 事件中选择当前处理任务。
core/events/runner.py - 启动事件 handler 并根据 COMPLETE/FAIL 更新 memory。
core/events/position_stabilizer.py - 通过当前帧墙体配准把事件局部候选投影到全局地图，并用多帧聚类输出稳定事件坐标。
core/events/capture_provider.py - 为事件 handler 提供小地图/主画面截图来源。
core/events/action_executor.py - 执行事件返回的 MOVE_TO/CLICK_SCREEN/PRESS_KEY/WAIT 等通用动作。
core/events/window_finder.py - Windows 游戏窗口枚举、DPI awareness 和窗口矩形获取。
core/events/detectors/template_matcher.py - 多模板、多尺度图标匹配通用工具。
core/events/types/portal/definition.py - `portal` 完整事件包对外定义。
core/events/types/portal/minimap_detector.py - 传送门小地图图标 detector。
core/events/types/portal/main_view_confirmer.py - 传送门主画面蓝紫发光实体 confirmer。
core/events/types/portal/handler.py - 传送门事件执行状态机，返回通用 EventAction。
assets/event_templates/portal/minimap/portal_minimap_01.png - 传送门小地图图标模板 1，供事件识别探针和后续 PortalMinimapDetector 使用。
assets/event_templates/portal/minimap/portal_minimap_02.png - 传送门小地图图标模板 2，覆盖同类传送门图标的另一种小地图外观。
assets/event_detectors/portal/main_view/blue_glow_detector_v1.json - 大画面传送门蓝紫发光检测参数资产。
assets/event_detectors/portal/main_view/README.md - 大画面传送门检测资产说明和复现命令。
utils/event_icon_probe.py - 独立事件图标探针，用原始小地图截图验证多模板匹配。
utils/portal_screen_probe.py - 独立大画面传送门探针，用游戏窗口截图验证蓝紫发光实体识别。
docs/plans/2026-05-22-event-system-design.md - 事件系统模块边界、传送门事件 v1 和探针结果记录。
docs/plans/2026-05-22-event-system-architecture-design.md - 审核通过的事件系统代码结构架构设计。
docs/plans/2026-05-22-event-system-implementation-plan.md - 事件系统 TDD 实现任务拆分计划。
tests/test_auto_navigator.py - 自动导航状态机行为测试。
tests/test_motion_controller.py - 点击半径夹紧逻辑测试。
```

## 3. 架构全景
```text
Level 1
┌──────────────┐       ┌──────────────────────────┐       ┌──────────────┐
│ Game screen  │ ───▶  │ Minimap Stitcher/Nav App │ ───▶  │ Mouse click  │
└──────────────┘       └──────────────────────────┘       └──────────────┘
```

```text
Level 2
┌──────────────┐
│ MainWindow   │
└──────┬───────┘
       ├──▶ MappingWidget ──▶ MapStitcher ──▶ map_data.npz/config.json
       └──▶ NavigationModeWidget ──▶ NavigationCore ──▶ global player pos
                                  ├──▶ AutoNavigator ──▶ map subgoal
                                  ├──▶ EventCoordinator ──▶ event task/action
                                  └──▶ MotionController ──▶ Win32 mouse_event click
```

```text
Level 3: navigation click path
┌──────────────────────┐
│ navigation_loop      │
│ capture minimap      │
│ localize player      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ AutoNavigator.update │
│ map pos -> path      │
│ path -> subgoal      │
└──────────┬───────────┘
           ▼ issued_click=True
┌────────────────────────────┐
│ MotionController           │
│ normalize map direction    │
│ clamp screen click radius  │
└──────────┬─────────────────┘
           ▼
┌──────────────────────┐
│ Win32 mouse_event    │
└──────────────────────┘
```

## 4. 模块与文件详解
### `gui/navigation_params.py`
职责：定义导航配置数据模型，并把地图 `config.json` 转换为运行时 `NavConfig`。
关键导出：`NavConfig`、`RecognizerParams`、`NavPreferences`、`_parse_hsv_list`。
对外依赖：无内部模块依赖。
注意事项：`monitor_size`/`draw_scale` 服务定位一致性；`game_view_map_size` 和点击半径参数服务主画面移动控制，不能反向影响定位。

### `core/motion_controller.py`
职责：把 `AutoNavigator` 给出的地图全局子目标转换为屏幕物理坐标点击。
关键导出：`MotionController`。
对外依赖：`core.input_driver.InputDriver`；`pydirectinput.click` 仅为异常兜底。
注意事项：当前不负责寻路、不负责定位，只处理“地图方向 -> 屏幕点击”。`movement_scale_factor` 先得到原始屏幕半径，再由 `movement_min_click_radius`/`movement_max_click_radius` 夹紧；底部 UI 防误点由 `bottom_click_guard_pixels` 在最终点击前单独处理，不反向修改移动比例。事件系统的显式屏幕点击走 `click_screen_position()`，事件按键走 `press_key()`，避免 handler 直接调用私有输入细节。

### `gui/dialogs/event_manager_dialog.py`
职责：独立事件管理窗口，用于测试和运行时观察事件系统。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`。
注意事项：事件选配表只展示完整事件包，例如 `portal`；不会暴露 minimap detector、main-view confirmer、handler 等内部步骤。任务表从 `EventCoordinator.tasks()` 刷新，展示 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。勾选变化只更新内存态配置并发出 `config_changed`，点击保存才写入当前地图 `event_config.json`。

### `gui/modes/navigation_mode.py`
职责：导航模式 UI 与运行循环，包含地图加载、定位、路线编辑、自动导航动作消费、绿色定位框和橙色真实可见框绘制。
关键导出：`NavigationModeWidget`。
对外依赖：`NavigationCore`、`MotionController`、`AutoNavigator`、`RouteManager`、`EventCoordinator`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`guide_points` 构成可被 A* 逐段追踪的路线骨架，`required_points` 是必须按顺序完成的阶段门，状态机按路线进度判断当前应追普通点还是必经点，并通过 `target_kind` 控制覆盖层只高亮真正当前目标。加载地图时初始化事件 registry/config/coordinator；导航循环每帧构造 `EventTick`，事件动作在自动导航开启时优先于普通 auto move 执行。事件管理按钮打开 `EventManagerDialog`，地图上的事件标记来自 `EventCoordinator.overlays()`；全局关闭事件系统或关闭单个事件时，禁用事件不会再显示活动 marker。

### `core/route_manager.py`
职责：维护每张地图的 `route.json`，持久化出口、必经点、途经点。
关键导出：`RouteManager`。
对外依赖：标准库 `json`、`pathlib.Path`。
注意事项：`required_points` 和 `guide_points` 是两套独立序列；`clear_route()` 会同时清空两类点，避免旧路线状态残留。

### `core/auto_navigator.py`
职责：自动导航状态机，等待稳定定位、规划当前段路径、选择路径前方子目标、控制点击冷却和卡住恢复。
关键导出：`AutoNavigator`。
对外依赖：`core.path_utils`。
注意事项：输出的是地图全局坐标的 `target_pos/subgoal`，不应掺入屏幕点击半径。阶段 1 默认规划优先：`PathFinder` 使用变薄后的墙图，A* 失败时才进入局部脱困 fallback。`guide_points + exit` 始终是路线接入和行走骨架；`required_points` 不直接替代路线骨架，而是按其投影到路线骨架上的进度成为阶段门，接近当前必经点后才推进 `required_index`。

### `core/navigation_core.py`
职责：读取 `map_data.npz`，用实时小地图截图定位玩家在全局地图中的坐标。
关键导出：`NavigationCore`。
对外依赖：`HSVRecognizer`。
注意事项：`draw_scale` 必须与建图保持一致；输出坐标是全局地图坐标，不是屏幕点击坐标。`fog_layer` 仍会随地图包保存，但当前显示默认只渲染 `explored_map`（灰）和 `wall_layer`（白），不额外铺蓝底。战斗/事件场景下，F2F 跟踪优先使用 `wall_mask` 而不是混合 `match_mask`，以降低动态边缘特效带来的漂移。

### `core/pathfinder.py`
职责：对 `wall_layer` 先做墙体变薄，并结合 `explored_map` 排除未知区域，再降采样运行 A*，输出全局地图路径点。
关键导出：`PathFinder`。
对外依赖：无内部模块依赖。
注意事项：路径点用于地图导航，不能直接当屏幕点击点。默认 `safety_margin=0`、`wall_shrink_iterations=1`，优先避免缝隙/窄路被建图墙体误封；`explored_map==0` 必须视为不可走，否则 A* 会穿过地图外黑区。

### `core/stitcher_core.py`
职责：将实时小地图墙层/地面层融合到全局地图，并输出供绘图模式与导航模式共用的地图包。
关键导出：`MapStitcher`。
对外依赖：`cv2`、`numpy`。
注意事项：当前版本不再把整块截图矩形无脑写入 `explored_map`；优先使用 `fog_mask` 作为精准可见区域，并同步维护 `fog_layer`，这样生成的地图更接近游戏实际小地图结构。

### `utils/event_icon_probe.py`
职责：不接入导航主循环，只用于验证“原始小地图截图 + 事件图标模板”能否识别出事件候选。
关键导出：`CaptureGeometry`、`MatchHit`、`TemplateSpec`、`match_template()`、`merge_hits()`、`main()`。
对外依赖：`core.capture.SquareScreenCapture`。
注意事项：事件识别必须使用 raw minimap frame，不使用 `HSVRecognizer.extract_combined()` 之后的定位特征图；脚本需要和游戏同权限运行，非管理员权限可能抓到黑帧。`--template` 可重复传入，多模板结果会按中心距离去重，低于阈值时仍打印每个模板的最佳候选用于调参诊断。

### `utils/portal_screen_probe.py`
职责：不接入导航主循环，只用于验证主游戏画面里传送门实体是否能被视觉识别。
关键导出：`main()`。
对外依赖：`core.capture.SquareScreenCapture`、`core.events.window_finder`、`core.events.types.portal.main_view_confirmer`。
注意事项：该探针默认枚举 `UnrealWindow` / `Torchlight` 游戏窗口并抓整块窗口画面；也支持 `--rect` 或 `--full-screen`。探针现在复用 portal 事件包的 main-view confirmer，避免探针算法和运行时算法漂移。

### `core/events/*`
职责：事件系统核心层。`EventCoordinator` 是导航模式唯一入口；`EventRegistry` 只注册完整事件包；`EventMemory` 管理事件实例生命周期；`EventRunner` 调用具体事件 handler；`EventActionExecutor` 执行动作。
关键导出：`FrameRegistration`、`EventTick`、`EventDetection`、`EventObservation`、`EventTask`、`EventAction`、`EventCoordinator`、`EventRegistry`、`EventSystemConfig`、`EventActionExecutor`。
对外依赖：标准库；视觉工具依赖 OpenCV/NumPy。
注意事项：事件 handler 不直接操作鼠标键盘，只返回 `EventAction`；TUI/配置层只能看到 `EventDefinition` 级完整事件，例如 `portal`。`EventPositionStabilizer` 会按同一帧隔离聚类，避免一帧内两个相近事件图标被合并成一个跳动 marker；`EventMemory.merge_observations()` 还会避免同一帧多个 observation 复用同一个刚更新的 task，近距离双传送门依赖 `dedupe_radius` 小于两门间距来稳定显示两个 marker。

### `core/events/types/portal/*`
职责：传送门完整事件包。对外暴露 `PortalEventDefinition`，内部拆分小地图 detector、主画面 confirmer 和 handler。
关键导出：`PortalEventDefinition`。
对外依赖：`core.events.detectors.template_matcher`、`core.events.types.portal.main_view_confirmer`。
注意事项：小地图 detector 用 raw minimap 多模板匹配创建 `portal` observation，但模板命中后还必须通过蓝/青色像素比例校验，避免白色墙体、圆形地形细节被识别成传送门。默认交互方式是靠近传送门后直接按 `D`，不再要求主画面蓝紫实体确认；如果配置为 `click` 才走主画面 confirmer 二阶段确认。按键/点击后 handler 等待位置变化或小地图周边环境变化才判定传送完成，避免固定等待导致误完成；完成动作会携带入口和出口坐标，runner 将出口附近的传送门任务也标记 completed，防止双门来回触发。

## 5. 函数索引与算法实现
### `MotionController._calculate_target_screen_position(self, player_global_pos: tuple, target_global_pos: tuple) -> tuple[int, int] | None`
行为：把地图全局方向映射到人物屏幕中心附近的真实点击点。
算法：
1. 计算 `delta_map = target_global_pos - player_global_pos`。
2. 用 `math.hypot` 得到地图距离；若距离接近 0，记录 `last_click_info` 并返回 `None`。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[movement_min_click_radius, movement_max_click_radius]`。
5. 将地图方向归一化为单位向量。
6. 屏幕点击点等于 `game_screen_center + direction * screen_radius`。
7. 记录 `last_click_info`，包含 map_delta、raw_screen_radius、screen_radius、direction、screen_pos。
副作用：更新 `self.last_click_info`。
失败行为：目标距离为 0 时不返回点击点。
调用关系：called by `MotionController.move_to_map_target()`；间接 called by `NavigationModeWidget.navigation_loop()`。

### `MotionController._apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None)`
行为：防止自动导航点击落入游戏底部 UI 区域。
算法：
1. 若 `bottom_click_guard_pixels <= 0` 或未校准 `game_screen_center`，直接返回原点击点。
2. 从 `InputDriver.screen_height` 或 `pydirectinput.size()` 获取屏幕高度。
3. 计算禁点区顶部 `forbidden_top = screen_height - bottom_click_guard_pixels`，安全线 `safe_y = forbidden_top - bottom_click_guard_margin`。
4. 若目标 `y <= safe_y`，不调整。
5. 若目标在人物中心下方且超过安全线，沿 `game_screen_center -> screen_pos` 线段按比例缩短到 `safe_y`。
6. 返回调整后的点击点和 `bottom_guard` 诊断信息。
副作用：无直接鼠标副作用；调用方把结果写入 `last_click_info`。
失败行为：无法获取屏幕高度时保持原点并记录 `reason=no_screen_height`。
调用关系：called by `MotionController._execute_click()`。

### `MotionController.press_key(self, key: str, reason: str = "event_key")`
行为：为事件 handler 返回的 `PRESS_KEY` 动作发送键盘输入。
算法：
1. 检查 `control_enabled`，未启用时打印跳过并返回 `None`。
2. 将 key 转为小写字符串并去掉空白。
3. 空 key 直接跳过，避免向输入后端发送无效按键。
4. 调用 `pydirectinput.press(normalized_key)` 发送按键。
5. 返回包含 key/reason 的诊断 dict。
副作用：向当前游戏/前台窗口发送键盘输入。
失败行为：未开启控制或 key 为空时不执行输入；`pydirectinput.press()` 异常不在本函数吞掉。
调用关系：called by `NavigationModeWidget._execute_event_key_press()`。

### `NavigationModeWidget._update_game_view_rect(self, player_pos)`
行为：在地图视图中绘制橙色真实主画面范围框。
算法：
1. 校验 `game_view_rect_item`、`player_pos`、`nav_core`、`nav_config` 是否存在。
2. 读取 `nav_config.game_view_map_size`，小于等于 0 时隐藏橙色框。
3. 用 `nav_core.crop_offset` 将全局地图坐标转换为当前场景坐标。
4. 以玩家位置为中心，绘制边长为 `game_view_map_size` 的正方形。
副作用：更新 QGraphicsRectItem。
调用关系：called by `NavigationModeWidget.navigation_loop()`。

### `NavigationModeWidget._refresh_game_view_rect_from_known_position(self)`
行为：参数变化或保存后，在没有等待下一帧导航循环的情况下刷新橙色真实可见框。
算法：
1. 校验 `nav_core` 是否存在。
2. 按优先级选择 `nav_core.current_pos`、`nav_core.last_good_pos`、`nav_core.drawing_saved_pos`。
3. 找到可用位置后调用 `_update_game_view_rect()`。
副作用：立即更新 QGraphicsRectItem。
调用关系：called by `_on_parameter_changed()` and `_save_nav_config()`。

### `NavigationModeWidget._render_event_overlay(self)`
行为：在导航地图上绘制已识别事件任务 marker。
算法：
1. 若 scene/nav_core/coordinator 任一不可用，清空旧事件 marker 后返回。
2. 从 `EventCoordinator.overlays()` 读取当前启用事件的 overlay 模型。
3. 用 `nav_core.crop_offset` 将全局地图坐标转换为当前裁剪场景坐标。
4. 按 overlay 颜色绘制圆点；`running` 状态半径更大。
5. 在圆点旁绘制事件名称和状态文本。
副作用：清空并重建 `event_overlay_items` 中的 QGraphicsItem。
失败行为：坐标为空或无法映射时跳过该 marker。
调用关系：called by `navigation_loop()` and `_render_route_overlay()`。

### `EventManagerDialog.refresh(self) -> None`
行为：刷新事件选配表和事件任务表。
算法：
1. 调用 `_refresh_events()` 重建完整事件选配表。
2. 调用 `_refresh_tasks()` 从 coordinator 读取当前任务列表。
3. 当 registry/config 不存在时禁用全局复选框并显示未加载状态。
4. 事件复选框变化通过 `config_changed` 把内存态配置交回导航模式。
5. 保存按钮只发出 `save_requested`，实际路径由导航模式写入当前地图目录。
副作用：重建 QTableWidget 行和状态文案。
失败行为：coordinator 查询异常时 `_current_tasks()` 降级为空列表。
调用关系：called by `NavigationModeWidget.toggle_event_dialog()` and `navigation_loop()`。

### `NavParametersDialog._auto_estimate_click_radius(self)`
行为：根据已校准的角色屏幕中心和物理屏幕边界估算点击半径，避免 2K 屏幕下半径配置过小。
算法：
1. 校验当前 `NavConfig` 和 `game_screen_center`。
2. 调用 `_screen_physical_bounds_for_center()` 找到包含该中心点的屏幕物理边界。
3. 计算中心点到屏幕四边的最小距离 `safe_radius`。
4. 取 `max_radius = clamp(safe_radius * 0.70, lower=180, upper=900)`。
5. 取 `min_radius = max(120, max_radius * 0.55)`。
6. 写入最小/最大点击半径控件，触发配置变更信号。
副作用：更新参数面板控件和 `nav_status_label`。
调用关系：called by `nav_auto_click_radius_btn.clicked`。

### `AutoNavigator.update(self, localized_pos, confidence: float, wall_map, pathfinder, now_ms: int, lookahead_distance=None)`
行为：消费当前定位结果，输出状态或移动动作。
算法：
1. 若暂停或未启动，返回状态。
2. 用 `observe_localization()` 过滤低置信度和异常跳变。
3. ACQUIRE/SHORT_LOST 状态需要稳定窗口满足后才规划。
4. PLAN_SEGMENT 先调用 `_align_route_to_current_position()` 将 `guide_index` 接入到当前位置附近，但不会越过当前必经点在路线骨架上的进度。
5. `_select_segment_target()` 比较当前普通点进度和当前必经点投影进度：普通点仍在必经点之前时追普通点；必经点已到达或位于当前普通点之前时追必经点；两类点都完成后追出口。
6. 默认调用 `PathFinder.find_path()` 用变薄墙图和已探索区域规划当前段路径；若显式 `prefer_direct_guidance=True` 才强制直线段。
7. 如果 A* 因墙体/障碍失败，不再构造到 `segment_target` 的长直线路径，而是用 `_set_local_fallback_path()` 生成当前人物附近、朝目标方向的一小段临时脱困点。
8. FOLLOW_SEGMENT 状态把当前位置投影到路径并选择 lookahead 子目标。
9. `click_cooldown_ms` 和 `min_click_target_delta` 满足时返回 `{"type": "move", "issued_click": True, "target_pos": subgoal}`。
10. 如果临时脱困点到达或无进展，进入 PLAN_SEGMENT 重新跑 A*；卡住时进入 STUCK_RECOVER，先做小幅左右绕障试探，再按冷却重规划或失败。
副作用：更新状态机、平滑控制位置、点击冷却时间。
调用关系：called by `NavigationModeWidget.navigation_loop()`。

### `AutoNavigator._set_local_fallback_path(self, target)`
行为：A* 失败时生成局部脱困路径，而不是直接点击下一目标点。
算法：
1. 调用 `_local_probe_towards_target()`，以当前人物位置为起点、当前段目标为方向参考。
2. `direct_fallback_distance` 限制前进距离，默认约 96 地图像素。
3. `direct_fallback_side_distance` 和 `direct_fallback_attempts` 在重复失败时轻微左右偏移。
4. 将 `current_path` 设置为 `[control_pos, probe]`。
5. 标记 `current_path_kind="local_fallback"`，让 `_follow_segment()` 到达临时点后重新规划而不是推进路线段。
副作用：更新 `current_path/current_path_kind/direct_fallback_attempts`。
调用关系：called by `AutoNavigator._plan_segment()`。

### `AutoNavigator._align_route_to_current_position(self)`
行为：自动导航启动或重定位后，根据当前位置选择应该追踪的路线标记。
算法：
1. 如果本轮已经对齐或没有当前位置，直接返回。
2. 读取 `guide_points + exit_region.center` 作为有序标记点。
3. 如果仍有未完成 `required_points`，计算当前必经点投影到路线骨架上的进度，后续接入候选不能超过该进度之后的第一个普通点。
4. 计算当前位置到每个标记点的距离，得到最近标记候选。
5. 调用 `_candidate_index_from_nearest_route_segment()`；若当前位置贴近某条路线段，则候选改为该段的下一个标记，避免在两个标记之间回头追上一个点。
6. 如果距离最近标记小于 `arrival_radius * route_marker_arrival_factor`，认为该标记已到达，目标推进到下一个标记。
7. 将 `guide_index` 设置为候选标记索引，并清空当前路径，下一步重新 A* 到该标记。
副作用：更新 `guide_index/current_path/current_target/current_path_kind`。
调用关系：called by `AutoNavigator._plan_segment()`。

### `AutoNavigator._select_segment_target(self)`
行为：在普通路线骨架、当前必经点和出口之间选择本次 A* 应追踪的段目标。
算法：
1. 若没有有效路线，返回 `("none", None)`。
2. 读取当前 `guide_index` 对应的普通点和当前 `required_index` 对应的必经点。
3. 当普通点和必经点同时存在时，把必经点投影到 `guide_points + exit` 路线骨架，得到必经点路线进度；同时读取当前普通点的路线进度。
4. 如果必经点进度小于等于当前普通点进度，返回 `("required", required_point)`，表示阶段门已经到达当前路线位置，必须先完成。
5. 如果当前普通点仍在必经点之前，返回 `("guide", guide_point)`，继续沿人工路线骨架行走，避免直接拉直线去下一个必经点。
6. 若只剩必经点则返回必经点；若只剩普通点则返回普通点；两者都完成后返回出口中心。
副作用：无；调用方会把结果写入 `current_target/current_target_kind`。
调用关系：called by `current_segment_target()`、`current_segment_target_kind()`、`_plan_segment()`。

### `AutoNavigator._candidate_index_from_nearest_route_segment(self, points)`
行为：当当前位置在路线段附近时，按路线方向接入下一标记。
算法：
1. 遍历每一段 `points[i] -> points[i+1]`。
2. 将当前位置投影到线段，计算投影点和线段距离。
3. 选择距离最近且小于 `route_snap_max_distance` 的线段。
4. 如果投影参数 `t <= route_snap_segment_threshold`，候选仍是该段起点；否则候选是该段终点，即沿路线向出口方向推进。
副作用：无。
调用关系：called by `_align_route_to_current_position()`。

### `PathFinder._build_obstacle_map(self, wall_map, grid_w, grid_h)`
行为：把建图墙层转换为 A* 使用的低分辨率障碍图。
算法：
1. 将输入墙图转为 `uint8` 并阈值化。
2. 如果 `wall_shrink_iterations > 0`，用 `MORPH_CROSS` 腐蚀墙像素，让建图偏厚的墙体变薄。
3. 将变薄后的墙图 resize 到 A* 网格尺寸。
4. 再阈值化得到 `binary_map`。
5. 如果传入 `explored_map`，把已探索区域 resize 到同一网格，`explored_map==0` 的网格强制设为障碍。

### `PathFinder._astar(self, grid, start, end)`
行为：在低分辨率障碍图上执行 8 方向 A*。
算法：
1. 从 `start` 开始，用 `g_score + heuristic` 的最小堆扩展节点。
2. 邻居支持上下左右和四个对角方向。
3. 若目标邻居本身是障碍，直接跳过。
4. 若是对角移动，还要额外检查两侧正交相邻格；任一侧是障碍就禁止斜穿角，避免从墙角之间硬挤过去。
5. 使用直行 `1.0`、斜走 `1.414` 的代价累计，直到到达终点或无路可走。

### `MapStitcher._merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False)`
行为：把当前帧的墙体层与地面/禁区候选层融合进全局地图。
算法：
1. 根据当前全局坐标和玩家在小地图中的相对位置，计算当前帧在画布上的 ROI。
2. 对墙体像素累积 `weight_layer`，权重大于阈值后再写入 `wall_layer`，避免单帧噪声污染地图。
3. 从 `fog_mask` 提取精准可见区域；像素数足够时，将其写入 `fog_layer` 并作为本帧 `explored_map` 的更新依据。
4. 只有当地面/迷雾提取几乎为空时，才回退到旧的“整块截图矩形” explored 逻辑，避免某些地图完全不出背景。
5. 强制把墙体也并入 `explored_map`，保证裁剪和导航不会把边界丢掉。

### `MapStitcher.get_enhanced_map(self, margin=500)`
行为：返回绘图模式显示用的彩色全局图。
算法：
1. 以 `explored_map`/`wall_layer` 的非零包围盒为基础自动裁剪。
2. `explored_map` 显示为灰色有效区域。
3. `fog_layer` 继续保存在地图包中，但默认不直接渲染到 UI。
4. `wall_layer` 显示为白色墙体并覆盖在最上层。

### `HSVRecognizer.extract_combined(self, img, player_pos=None)`
行为：提取用于拼接/导航的组合特征。
算法：
1. 先提取 `wall_mask`、`fog_mask` 和 `edges`。
2. 对高饱和度彩色区域生成 `dynamic_mask`，并做一次小核膨胀，把事件图标/彩色技能标记及其轮廓一起抹掉。
3. 将 `dynamic_mask` 同时从 `wall_mask`、`fog_mask`、`edges` 中剔除，避免动态图标污染静态地图特征。
4. 在人物中心周围再挖一个固定半径的圆形屏蔽区，压制玩家脚下和近身特效。
5. 最后才把 `wall_mask` 和 `edges` 融合成 `match_mask`，用于配准。
6. 如果 `safety_margin <= 0`，直接返回，不再默认膨胀墙体。
7. 如果显式设置安全边距，则按网格比例膨胀障碍图。
副作用：无。
调用关系：called by `PathFinder.find_path()`。

### `event_icon_probe.match_template(frame: np.ndarray, template: np.ndarray, mask: np.ndarray | None, scales: list[float], top_k: int, threshold: float) -> list[MatchHit]`
行为：对单个事件图标模板执行多尺度匹配，返回超过阈值的候选。
算法：
1. 将原始小地图帧转换为灰度图，并用 Canny 提取边缘。
2. 遍历 `scales`，按比例缩放模板和可选 alpha mask。
3. 对灰度模板执行 `cv2.matchTemplate(..., TM_CCOEFF_NORMED)`。
4. 如果模板边缘足够多，再执行边缘模板匹配，并按 `gray*0.72 + edge*0.28` 合成分数。
5. 如果存在有效 alpha mask，追加 masked `TM_CCORR_NORMED` 响应，并与灰度响应加权后取更高分。
6. 用 `_response_hits()` 按局部抑制半径提取 top-k 候选，避免同一图标重复输出多个相邻峰值。
7. 按 `score` 降序返回候选。
副作用：无。
调用关系：called by `event_icon_probe.main()`。

### `event_icon_probe.merge_hits(hits: list[MatchHit], top_k: int, center_radius: float = 12.0) -> list[MatchHit]`
行为：把多个模板或多个尺度产生的候选按图标中心去重。
算法：
1. 按 `score` 从高到低遍历所有候选。
2. 计算当前候选中心与已保留候选中心的欧氏距离。
3. 若距离小于动态半径，视为同一事件图标，只保留较高分候选。
4. 保留数量达到 `top_k` 后停止。
副作用：无。
调用关系：called by `event_icon_probe.main()`。

### `event_icon_probe.main() -> int`
行为：读取地图配置，抓取 raw minimap frame，加载一个或多个事件模板，输出匹配结果和调试图片。
算法：
1. 解析 `--map-folder`、可重复 `--template`、阈值、尺度、输出目录等参数。
2. 从 `config.json` 读取 `monitor_region` 或 `monitor_logical_center/monitor_size`，结合 DPR 得到物理截图矩形。
3. 用 `SquareScreenCapture.capture()` 抓取原始小地图帧并保存。
4. 若提供模板，对每个模板调用 `match_template()`，再用 `merge_hits()` 去重。
5. 保存带框 debug 图；若没有候选超过阈值，仍打印每个模板的最佳低分候选，区分“阈值过高/图标不在视野”和“截图失败”。
副作用：写入 `debug/event_probe/...` 图片；初始化和关闭屏幕捕获后端。
调用关系：standalone CLI。

### `portal_screen_probe.build_blue_glow_mask(frame: np.ndarray) -> np.ndarray`
行为：从主游戏画面中提取传送门可能使用的蓝/青/紫发光区域。
算法：
1. 将 BGR 帧转换为 HSV。
2. 分别对 cyan、blue、violet 三段 HSV 范围做 `cv2.inRange()`。
3. 合并三段 mask，保留传送门、蓝色 UI、冰蓝怪物高光等全部候选发光区域。
4. 用 3x3 椭圆开运算去孤立噪点。
5. 用 11x11 椭圆闭运算连接被纹理切断的发光弧线，再轻微膨胀。
副作用：无。
调用关系：called by `portal_screen_probe.detect_portal_candidates()`。

### `portal_screen_probe.detect_portal_candidates(frame: np.ndarray, min_area: float, max_area_ratio: float) -> tuple[list[PortalCandidate], np.ndarray]`
行为：把蓝紫发光 mask 转换为候选框并计算传送门相似分。
算法：
1. 调用 `build_blue_glow_mask()` 得到二值 mask。
2. `cv2.findContours()` 查找外轮廓。
3. 过滤面积太小、bbox 占整帧比例太大、宽高太小或宽高比极端的轮廓。
4. 计算轮廓面积、bbox、中心点、发光填充率、圆度和宽高比。
5. 用面积分、发光分、形状分和圆度分加权得到 `score`。
6. 按分数降序返回候选和 mask。
副作用：无。
调用关系：called by `portal_screen_probe.main()`。

### `portal_screen_probe.is_strict_portal_candidate(candidate: PortalCandidate, args: argparse.Namespace) -> bool`
行为：把宽松视觉候选收紧为可执行事件确认候选。
算法：
1. 要求 `score >= threshold`。
2. 要求 bbox 宽高均超过资产阈值，排除 UI 小图标。
3. 要求轮廓面积超过阈值，排除小蓝色亮点。
4. 要求圆度、发光填充率和宽高偏斜满足阈值，排除蓝色机关、怪物冰蓝高光和长条 UI。
副作用：无。
调用关系：called by `portal_screen_probe.draw_candidates()` and `portal_screen_probe.main()`。

## 6. 完整数据流链路
### Flow: 自动导航移动点击
1. `NavigationModeWidget.navigation_loop()` 输入 `capture_rect`、屏幕截图帧；输出 `localized_pos=(global_x, global_y)`；副作用是更新地图上的玩家点、绿色定位框、橙色真实可见框。
2. `NavigationCore.localize()` 输入实时小地图截图和 `player_pos`；输出地图全局坐标和置信度；副作用是更新 `current_pos/last_good_pos/prev_mask`。
3. `AutoNavigator.update()` 输入地图全局坐标、置信度、`wall_layer`、`explored_map`、`PathFinder`；默认用变薄墙图和已探索区域做 A* 当前段规划，失败时才生成局部脱困点；输出 `auto_action`，其中 `target_pos` 是地图全局子目标。
4. `NavigationModeWidget.navigation_loop()` 检查 `auto_action.type == "move"` 且 `issued_click=True`；副作用是调用运动控制器。
5. `MotionController.move_to_map_target()` 输入玩家地图全局坐标和目标地图全局坐标；输出 `last_click_info`；副作用是调用 `_execute_click()`。
6. `MotionController._execute_click()` 输入屏幕物理坐标；先用 `_apply_bottom_click_guard()` 避免落入底部 UI，再通过 `InputDriver.click()` 执行 Win32 `SetCursorPos + mouse_event`，失败时才回退 `pydirectinput.click(x, y)`。

### Flow: 导航参数保存和加载
1. `NavigationModeWidget.load_map()` 读取 `map_data/<map>/config.json`。
2. `NavConfig.from_dict()` 将 dict 转为配置对象；缺失新字段时使用默认值。
3. `NavParametersDialog.set_config_to_ui()` 将配置同步到控件。
4. 控件变化触发 `_update_config_value()`，通过 `dataclasses.replace()` 创建新配置并发出 `parameters_changed`。
5. `NavigationModeWidget._on_parameter_changed()` 保存内存态配置，立即更新运动控制器参数，并通过 `_refresh_game_view_rect_from_known_position()` 重绘橙色框。
6. 同步调用 `AutoNavigator.configure()` 应用自动点击冷却和目标变化阈值。
7. 用户保存时 `_save_nav_config()` 调用 `NavConfig.to_dict()` 写回地图配置文件，并再次刷新橙色框。

### Flow: 点击半径诊断
1. `MotionController._calculate_target_screen_position()` 记录 `raw_screen_radius` 和夹紧后的 `screen_radius`。
2. `NavigationModeWidget.navigation_loop()` 在实际点击后追加显示 `click r:<screen_radius>/raw:<raw_screen_radius>`。
3. 如果 `raw` 明显大于 `r`，说明当前点击被 `movement_max_click_radius` 限制；如果 `raw` 和 `r` 都小，说明路径子目标距离或映射比例过小。

### Flow: 事件图标探针
1. `event_icon_probe.main()` 读取 `map_data/A1/config.json`，按 DPR 将小地图逻辑中心转换为物理截图矩形。
2. `SquareScreenCapture.capture()` 返回 raw minimap frame；该帧保留传送门/事件/Boss 等彩色动态 UI 图标。
3. `event_icon_probe.match_template()` 对每个传送门小地图模板做多尺度灰度+边缘匹配。
4. `event_icon_probe.merge_hits()` 合并不同模板/尺度对同一图标的重复命中。
5. 脚本保存 raw/debug 图片并打印每个 accepted hit；若无 accepted hit，则打印每个模板的 best candidate 作为阈值诊断。

### Flow: 大画面传送门探针
1. `portal_screen_probe.main()` 设置 DPI awareness，枚举 `UnrealWindow` / `Torchlight` 窗口或使用手工 `--rect`。
2. `SquareScreenCapture.capture()` 抓取整块主游戏窗口画面。
3. `portal_screen_probe.build_blue_glow_mask()` 提取蓝/青/紫发光区域。
4. `portal_screen_probe.detect_portal_candidates()` 生成宽松候选，并计算面积、发光占比、圆度、宽高比和综合分。
5. `portal_screen_probe.is_strict_portal_candidate()` 将候选收紧为绿色 accepted 传送门实体；非严格候选以橙色框输出，只供调参。
6. 脚本保存 raw/mask/debug 图片和 `last_probe_source.json`，后续事件处理器可复用参数资产。

### Flow: 事件管理 UI 和地图标记
1. `NavigationModeWidget.load_map()` 成功后调用 `_initialize_event_system()`，读取当前地图 `event_config.json`，创建 `EventCoordinator` 和 `GameWindowCaptureProvider`。
2. 用户点击“事件管理”按钮时，`toggle_event_dialog()` 调用 `_refresh_event_dialog()`，把 registry/config/coordinator/map_name 传给 `EventManagerDialog.set_context()`。
3. `EventManagerDialog.refresh()` 调用 `build_tui_event_options()` 枚举完整事件包，并从 `EventCoordinator.tasks()` 读取运行时任务。
4. 用户勾选全局/单个事件时，dialog 更新 `EventSystemConfig` 内存态并发出 `config_changed`。
5. `NavigationModeWidget._on_event_config_changed()` 将配置写回 coordinator，清空旧事件 marker，并打印事件配置日志。
6. 导航循环定位成功后构造 `EventTick`，`EventCoordinator.update()` 检测 raw minimap 图标、合并 memory、选择任务；只有自动导航开启时才推进 handler。
7. `NavigationModeWidget._render_event_overlay()` 从 `EventCoordinator.overlays()` 读取启用事件任务，在地图上绘制事件圆点和状态文本。
8. 用户点击保存时，`_save_event_config()` 调用 `save_event_config()` 写入当前地图 `event_config.json`。

## 7. 外部集成详情
`main.py` Windows 启动前置条件：先配置 UTF-8 输出和 `logs/runtime.log`，随后默认立即 `FreeConsole()` 释放控制台，再设置 DPI awareness、检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", pythonw.exe, ...)` 触发 UAC 重新启动当前脚本并退出原进程。默认 GUI 启动不保留控制台，诊断输出写入 `logs/runtime.log`；如需实时控制台，启动前设置 `MINIMAP_DEBUG_CONSOLE=1`，此时不会释放控制台，提权会继续使用 `python.exe` 并把输出同时写入控制台和日志文件。真实游戏输入依赖管理员完整性级别。

`InputDriver.click(x, y)`：由 `MotionController._execute_click()` 的 `win32_mouse_event` 后端调用，执行 `SetCursorPos(x, y)` 后用 Win32 `mouse_event` 分开发送 left-down/left-up。该路径来自旧脚本 `t2.py` 的可用实现，当前是游戏点击主后端。

`pydirectinput.click(x, y)`：仍作为 `MotionController` 的异常兜底和诊断工具保留。失败风险包括游戏窗口未聚焦、坐标在窗口外、权限/输入钩子被游戏屏蔽。

`pydirectinput.press(key)`：由 `MotionController.press_key()` 在事件 `PRESS_KEY` 动作中调用，目前主要服务传送门事件配置为按键交互时的 `D` 键。它同样依赖管理员权限和正确前台窗口。

`utils/event_icon_probe.py`：独立事件识别探针，依赖 `core.capture.SquareScreenCapture` 和 OpenCV 模板匹配。真实游戏窗口下需要管理员权限才能可靠捕获 raw minimap；非管理员权限可能返回黑帧，不应误判为识别算法失败。

`utils/portal_screen_probe.py`：独立大画面实体识别探针，依赖 Windows 窗口枚举、DPI awareness、`SquareScreenCapture` 和 OpenCV HSV/轮廓分析。当前只作为传送门事件第二阶段确认技术资产；当传送门实体离开视野或被遮挡时，零 accepted 是正确输出。

## 8. 数据模型与契约
### `NavConfig`
字段：
`draw_scale: float` - 建图/定位地图缩放。
`monitor_logical_center: tuple[int, int] | None` - 小地图截图中心，服务定位。
`monitor_region: dict | None` - 拉框截图区域，服务定位。
`monitor_size: int` - 正方形截图边长，服务定位。
`fps: int` - 导航循环刷新率。
`game_screen_center: tuple[int, int] | None` - 主游戏画面人物屏幕中心，服务鼠标点击。
`movement_scale_factor: float` - 地图距离到原始屏幕点击半径的比例。
`game_view_map_size: int` - 橙色真实主画面可见/可交互框在地图坐标中的边长。
`movement_min_click_radius: int` - 屏幕点击最小半径，防止点在人物脚下。
`movement_max_click_radius: int` - 屏幕点击最大半径，防止点出真实可交互区域。
`auto_click_cooldown_ms: int` - 自动导航两次真实点击之间的最小间隔，默认 260ms。
`auto_min_click_target_delta: float` - 冷却结束后，子目标至少变化多少地图像素才重复点击，默认 8.0。
`bottom_click_guard_pixels: int` - 屏幕底部禁点区高度，默认 300px，设为 0 可关闭；只在点击落入底部 UI 时沿原方向缩短半径。

### `EventSystemConfig`
字段：
`enabled: bool` - 全局事件系统开关。
`profile: str` - 当前事件配置方案名，默认 `default`。
`events: dict` - 每个完整事件包的配置，key 为事件类型，例如 `portal`。
`raw: dict` - 从 `event_config.json` 读取并保留的原始配置，用于保存时保留未知字段。

`portal` 默认配置字段：
`enabled: bool` - 是否启用传送门完整事件。
`priority: int` - 多事件调度优先级。
`interaction: str` - 交互方式，`click` 或 `key`，默认 `key`。
`minimap_threshold: float` - 小地图模板匹配阈值。
`max_candidates: int` - 单帧最多接受的传送门候选数，默认 2。
`min_blue_ratio: float` - 模板 bbox 周围必须满足的蓝/青传送门像素比例，过滤白墙误匹配。
`confirm_frames: int` - 需要连续/累计识别多少帧后进入 pending。
`dedupe_radius: int` - memory 合并同类事件任务的半径；A1 传送门默认 32，用于把相距约 69px 的双门拆成两个任务。
`arrival_radius: int` - 玩家距离事件点多少地图像素内开始主画面确认。
`retry_limit: int` - 失败后的重试次数。
`cooldown_ms: int` - 完成后的同位置冷却时间。
`cooldown_radius: int` - 完成后屏蔽附近同类传送门的地图半径，防止成对传送门来回触发。
`exit_complete_radius: int` - 传送成功后，将角色新位置附近多少地图像素内的同类传送门标记为出口 completed。
`type_cooldown_ms: int` - 完成后短时间屏蔽所有同类传送门新观察，用于跨门瞬间的稳定期。
`post_interact_wait_ms: int` - 按 D/点击后等待画面稳定的最短时间。
`teleport_timeout_ms: int` - 等待传送完成的最长时间。
`teleport_min_distance: int` - 用地图坐标判断传送成功的最小位置变化距离。
`environment_change_threshold: float` - 用玩家周边小地图截图签名判断传送成功的变化阈值。

## 9. 风险与隐患登记
P1 - `MotionController._calculate_target_screen_position()` 默认半径未校准。触发条件：游戏实际点击触发距离大于 180px 或可交互范围小于 360px。复现方式：自动导航状态栏显示 `click r`，但人物不移动或点击到不可达点。建议：在参数面板调整最小/最大点击半径，并用橙色框观察真实可见范围。

P1 - `main.py` 的 UAC relaunch 会启动一个新的管理员进程并退出原进程。触发条件：从非管理员 shell/IDE 启动。复现方式：启动后弹出 UAC，授权后 GUI 进程启动；如果用户取消授权，程序退出。建议：测试时查看 `logs/runtime.log` 中的 `Admin: True`；只有设置 `MINIMAP_DEBUG_CONSOLE=1` 时才依赖控制台输出。

P2 - `NavigationModeWidget._render_route_overlay()` 在自动导航每帧清空并重绘路线层。触发条件：高 FPS 或长路径。复现方式：地图视图卡顿或闪烁。建议：后续按路径/subgoal 变化缓存绘制。

P2 - `portal_screen_probe.detect_portal_candidates()` 依赖蓝紫发光外观。触发条件：其他事件或怪物使用大面积蓝紫特效，或传送门被怪物/场景遮挡。复现方式：debug 图中橙色候选很多但绿色 accepted 为 0，或绿色框落在非传送门实体。建议：正式事件系统中把它作为“小地图事件已发现后的二阶段确认”，并要求连续多帧稳定后再点击。

## 10. Input Control Current Notes
`core/input_driver.py` is part of the movement chain. It wraps Win32 `SetCursorPos`, `WindowFromPoint`, `SetForegroundWindow`, `GetForegroundWindow`, `GetClipCursor`, and `mouse_event`; `click()` performs separate down/up events with a short hold instead of a combined instant click.

`core/motion_controller.py` still owns only map-direction to screen-click conversion. The main project backend is `win32_mouse_event`: `MotionController._send_click()` calls `InputDriver.click(x, y, button="primary", hold_seconds=0.05, move_delay=0.02)`. `pydirectinput.click(x, y)` is only used as a fallback if the primary backend raises.

`core/auto_navigator.py` now defaults back to planning-first guidance. User-defined guide points and exit region still define major route intent, but each segment is planned with `PathFinder` on a thinned wall map constrained by `explored_map`. Direct full-segment guidance is retained only as explicit `prefer_direct_guidance=True`; A* failure uses a short local fallback probe near the player and then re-plans. Default automatic click cadence is `auto_click_cooldown_ms=260` and `auto_min_click_target_delta=8.0`, both exposed in the navigation parameter dialog.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation_mode.py::_set_game_input_window_mode()` prevents the PySide main window from intercepting auto-navigation clicks. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

### 2026-05-20 Correction
The stable movement baseline is the original `pydirectinput.click(x, y)` call. Do not replace it with `moveTo + mouseDown + mouseUp` unless it is separately verified in the target game environment. Window focusing is optional (`focus_before_click=False` by default) because it can interfere with the already-working cursor movement path.

`NavParametersDialog.set_config_to_ui()` now uses `QSignalBlocker` while writing widget values and `_connect_signals()` is one-shot. This avoids PySide `disconnect` RuntimeWarning messages during startup/config refresh.

### 2026-05-20 Click Diagnostics
`MotionController._execute_click()` logs the requested coordinate, final coordinate, whether clamping changed it, `pydirectinput.size()`, pydirectinput cursor position before/after, Win32 cursor position before/after, target window information, foreground window information, current `ClipCursor` rectangle, focus HWND, and confirmation-click state. This is intended to separate coordinate mapping failures from Unreal/Windows mouse capture or "click reached the wrong window" failures during real-game testing.

### 2026-05-20 Standalone Input Probe
`utils/input_probe.py` is a standalone manual probe for testing real game input before changing `MotionController`. It supports `pydi_click_xy`, `pydi_move_click`, `pydi_hold_xy`, `setcursor_pydi_click`, `setcursor_pydi_hold`, and `setcursor_win32_click`. It is diagnostic-only unless launched with `--execute`.

### 2026-05-20 DPI/Input Coordinate Finding
Runtime probe on the user's machine showed `pydirectinput.size() == (1707, 1067)`, `GetSystemMetrics(0/1) == (1707, 1067)`, and Qt `devicePixelRatio() == 1.5`. Therefore screenshot capture can still require physical coordinates, but `MotionController` should feed `pydirectinput` input coordinates consistently. `_clamp_screen_pos()` is now disabled by default; enabling it can still rewrite targets such as `(1987, 569)` or `(1559, 1469)` to screen-edge points, so it should only be used after the coordinate system is proven.

## 11. Event Runtime Diagnostics
`core/events/debug.py` is the shared console logging utility for the event system. It provides `event_log()`, `describe_action()`, and `describe_task()` so event modules print consistent `[Event HH:MM:SS.mmm] ...` lines instead of ad-hoc debug strings.

`EventMonitor`, `EventMemory`, `EventCoordinator`, `EventRunner`, and `EventActionExecutor` now log detector initialization, observation counts, task creation/confirmation, scheduler selection, handler start, action output, action execution, completion, failure, retry, and ignored states. Repeating frame-level logs are throttled, while click/key/complete/fail actions print immediately.

`PortalMinimapDetector`, `PortalMainViewConfirmer`, and `PortalEventHandler` now log the portal-specific chain: minimap template hits, task global position, movement distance to the portal, key/click interaction, wait-after-interaction, teleport position/environment completion, and timeout failure. Main-view confirmation only runs when `interaction="click"`; default `interaction="key"` goes directly to pressing `D` after arriving near the minimap-derived portal point.

`NavigationModeWidget` logs event-system initialization and event movement/click callbacks, and the status bar now appends a compact event summary from `EventCoordinator.status_summary()`, for example `event:portal running seen=3 act=move_to`. This is intended for live game testing only; it does not change event matching thresholds or navigation movement semantics.

Event detection and memory updates may run while normal navigation localization is active, but `EventCoordinator.update(..., run_handlers=False)` prevents handlers from advancing unless auto navigation is enabled. This avoids a misleading state where an event task could log completion without the executor being allowed to move or click.

## 12. Event Manager UI
`gui/dialogs/event_manager_dialog.py` is the independent event-management surface. It is intentionally package-level: the table lists complete events such as `portal`, not the internal minimap detector, main-view confirmer, or handler. The global checkbox toggles `EventSystemConfig.enabled`; each row checkbox toggles `config.events[event_type]["enabled"]`.

The runtime task table reads from `EventCoordinator.tasks()` and shows task ID, event type, state, seen count, confidence, global map position, attempts, and last-seen timestamp. This gives live feedback when a minimap icon is detected even before auto navigation executes the event.

`NavigationModeWidget._render_event_overlay()` draws event markers directly on the navigation map from `EventCoordinator.overlays()`. Pending/observed events use orange, running events use green, and completed/ignored events use gray. Disabled event types and global disabled state are filtered by the coordinator so stale markers do not remain visible after config changes.

The save button writes only the current map's `event_config.json`. This keeps per-map event strategy separate from global code and avoids one map's event settings affecting another map.

## 13. Portal Event Current Behavior
The current portal event is minimap-first. `PortalMinimapDetector` detects the portal icon in the raw minimap frame with multi-template/multi-scale matching, then rejects a hit unless the matched patch contains enough blue/cyan portal-icon pixels. The detector now emits only `EventDetection` local minimap candidates; it never creates a trusted global coordinate.

`NavigationCore.localize()` stores `last_frame_registration` whenever player localization succeeds. `EventCoordinator` passes local detections and that registration to `EventPositionStabilizer`, which projects each candidate with `frame_origin_global + local_minimap_pos * draw_scale`, clusters samples by event type and map distance, and emits an `EventObservation` only after `stable_frames` samples stay within `stable_variance`. `EventMemory` only creates/updates tasks from these stable global observations.

When auto navigation is enabled, `PortalEventHandler` moves the character toward the minimap-derived portal point until the player is within `arrival_radius`. With default `interaction="key"`, it then sends `D` through `MotionController.press_key()` and enters `wait_result`; it does not require main-view blue-glow confirmation. With `interaction="click"`, it uses `PortalMainViewConfirmer` to find the blue/purple portal entity in the game window and clicks its screen center.

After interaction, completion is not a fixed timer. The handler waits at least `post_interact_wait_ms`, then marks the task complete only if the player's global position changes by at least `teleport_min_distance` or the raw minimap patch around the player differs from the pre-interaction patch by at least `environment_change_threshold`. If neither happens before `teleport_timeout_ms`, the task fails and may retry.

To prevent paired nearby portals from bouncing the character back, `EventMemory` uses `cooldown_radius` for completed portal observations and `type_cooldown_ms` as a short global same-type cooldown. When a portal task completes, `EventRunner` also calls `suppress_nearby_pending()` so already-created nearby portal tasks are marked ignored.

## 14. Event Localization Contract
`core/events/models.py::FrameRegistration` records the wall-registration result for one minimap frame: validity, confidence, global origin of the raw minimap frame, draw scale, player global position, player local minimap position, source (`f2f` or `template_match`), frame size, and debug metadata.

`core/events/models.py::EventDetection` is local-only: event type, confidence, detection time, local minimap position, source, and detector metadata. Detectors must not convert this to global map space.

`core/events/models.py::EventObservation` is stable/global: event type, confidence, observation time, global map position, optional latest local minimap position, source, sample count, variance, and stabilization metadata. `EventMemory.merge_observations()` treats this as already localized and stable.

`core/events/position_stabilizer.py::EventPositionStabilizer.update()` is the shared localization stage for all future event types. It rejects detections when no valid frame registration exists, projects candidates through the same wall alignment used for player localization, clusters nearby samples, expires stale clusters, and emits stable observations only after the configured sample and variance gates pass.
