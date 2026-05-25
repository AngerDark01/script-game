# CODEBASE

## 1. 项目概览
PySide6 + OpenCV 的实时小地图拼接与导航工具。绘图模式从游戏小地图截图提取 HSV/墙体特征并写入 `map_data/<name>/map_data.npz`；导航模式读取同一份地图数据、用实时截图定位玩家全局地图坐标，并可基于用户设置的出口、必经点、途经点执行自动导航。当前任务相关的关键约束是：定位截图范围、地图全局坐标、真实主画面点击范围必须分离，不能用旧偏移参数修正定位。

## 2. 目录结构图
```text
main.py - 创建 QApplication 和 MainWindow。
gui/app_context.py - 初始化共享服务：ScreenCapture、MapStitcher、PlayerTracker、PathFinder。
gui/main_window.py - 创建绘图/导航两个模式并共享 AppContext。
gui/navigation_params.py - 定义 NavConfig、RecognizerParams、NavPreferences，并负责 config.json 序列化契约。
gui/dialogs/nav_params_dialog.py - 导航参数 UI，按定位识别/算法/移动/路径/调试分页，使用 widget_map 将控件变化写回 NavConfig。
gui/dialogs/event_manager_dialog.py - 独立事件管理窗口，展示完整事件选配和运行中事件任务状态。
gui/dialogs/advanced_settings_dialog.py - 高级参数弹窗主类，组合图像预处理、特征、参数管理和拼接算法 tabs。
gui/dialogs/advanced_settings/__init__.py - 高级参数弹窗 helper 包入口。
gui/dialogs/advanced_settings/params_adapter.py - 高级参数弹窗控件与参数 dict/预设之间的映射 helper。
gui/dialogs/color_picker_dialog.py - 交互式 HSV 颜色采样弹窗，负责采样点交互、预览和 debug 输出。
gui/dialogs/color_picker/__init__.py - 颜色选择弹窗 helper 包入口。
gui/dialogs/color_picker/hsv_ranges.py - 颜色选择弹窗 HSV 转换、采样值提取和范围计算 helper。
gui/dialogs/color_picker/image_renderer.py - 颜色选择弹窗 OpenCV 图像转 QPixmap 和采样点 marker 绘制 helper。
gui/modes/navigation_mode.py - 导航模式主 UI、地图加载、定位循环、路线编辑、自动导航、事件动作接入和范围框显示。
gui/modes/navigation/__init__.py - 导航模式拆分 helper 包入口。
gui/modes/navigation/event_adapter.py - 导航模式与事件系统之间的轻量桥接 helper。
gui/modes/navigation/event_overlay.py - 导航地图上的事件 marker 绘制和事件 overlay item 清理。
gui/modes/navigation/map_runtime.py - 导航地图目录、配置读写和截图几何计算 helper。
gui/modes/navigation/route_overlay.py - 导航路线、出口、必经点、途经点、当前路径和子目标 overlay 绘制。
gui/modes/navigation/viewport_overlay.py - 导航屏幕幕布、监控绿框、真实主画面橙框的矩形计算 helper。
gui/modes/event_test_controller.py - 手动事件测试按钮状态控制，避免测试 UI 状态散落在导航主文件。
gui/modes/mapping_widget.py - 绘图模式主 UI、截图建图循环、地图显示和参数控件同步。
gui/modes/mapping/__init__.py - 绘图模式拆分 helper 包入口。
gui/modes/mapping/map_renderer.py - 绘图模式 BGR/QPixmap 转换和全局地图 overlay 绘制 helper。
gui/modes/mapping/params_adapter.py - 绘图模式参数控件与 recognizer/stitcher 运行时参数之间的桥接 helper。
gui/modes/mapping/save_load.py - 绘图模式项目路径、map_data 目录和 config.json 读写 helper。
core/navigation_core.py - 导航定位核心，将实时小地图截图匹配到全局地图坐标。
core/stitcher_core.py - 建图拼接核心，维护 wall_layer/explored_map/current_pos。
core/navigation_obstacles.py - 从原始 wall_layer 派生 A* 专用的宽容障碍层，不改变定位用墙图。
core/pathfinder.py - A* 寻路，输入输出地图全局坐标。
core/path_utils.py - 路径平滑、投影、插值、出口区域判断工具。
core/anchor_path.py - 可选软锚点路径规划工具，供统一移动执行器把途经点作为有序锚点走廊。
core/navigation_tasks/__init__.py - 统一导航任务控制器包入口。
core/navigation_tasks/models.py - required/exit/event 统一任务、移动步骤和动作意图数据模型。
core/navigation_tasks/route_context.py - 用户辅助锚点折线投影、路线进度和前方锚点查询。
core/navigation_tasks/movement_executor.py - 普通路线和事件目标共用的 A*、锚点 lookahead、点击节流执行器。
core/navigation_tasks/task_builder.py - 把 route.json 静态目标和 EventMemory 动态事件任务合并成 NavigationTask 列表。
core/navigation_tasks/scheduler.py - 在 required、exit、event 中选择当前应处理任务。
core/navigation_tasks/controller.py - 统一导航任务控制器，输出 MOVE_MAP/CLICK_SCREEN/PRESS_KEY/ARRIVED/FAILED 意图。
core/navigation_tasks/coordinate_diagnostics.py - 坐标漂移诊断与内部强制重定位请求状态机。
core/navigation_tasks/debug.py - 将导航任务日志写入事件运行日志。
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
core/events/window_finder.py - Windows 游戏窗口枚举、DPI awareness 和窗口矩形获取。
core/events/detectors/template_matcher.py - 多模板、多尺度图标匹配通用工具。
core/events/types/portal/definition.py - `portal` 完整事件包对外定义。
core/events/types/portal/minimap_detector.py - 传送门小地图图标 detector。
core/events/types/portal/minimap_feature_matcher.py - 传送门小地图蓝色本体特征匹配器，避免整块背景模板绑定。
core/events/types/portal/minimap_shape_color_matcher.py - 传送门小地图形状+颜色联合匹配器，可由 portal `detector_mode=shape_color` 接入运行时，也可由探针离线验证。
core/events/types/portal/main_view_confirmer.py - 传送门主画面蓝紫发光实体 confirmer。
core/events/types/portal/handler.py - 传送门事件执行状态机，返回通用 EventAction。
assets/event_templates/portal/minimap/portal_minimap_01.png - 传送门小地图图标模板 1，供事件识别探针和后续 PortalMinimapDetector 使用。
assets/event_templates/portal/minimap/portal_minimap_02.png - 传送门小地图图标模板 2，覆盖同类传送门图标的另一种小地图外观。
assets/event_detectors/portal/main_view/blue_glow_detector_v1.json - 大画面传送门蓝紫发光检测参数资产。
assets/event_detectors/portal/main_view/README.md - 大画面传送门检测资产说明和复现命令。
utils/event_icon_probe.py - 独立事件图标探针，用原始小地图截图验证多模板匹配。
utils/portal_screen_probe.py - 独立大画面传送门探针，用游戏窗口截图验证蓝紫发光实体识别。
utils/route_context_probe.py - 离线打印 route.json 中辅助锚点、必经点和出口的路线进度。
utils/navigation_task_probe.py - 离线打印统一导航任务列表，确认 required/exit/event 的投影顺序。
docs/plans/2026-05-22-event-system-design.md - 事件系统模块边界、传送门事件 v1 和探针结果记录。
docs/plans/2026-05-22-event-system-architecture-design.md - 审核通过的事件系统代码结构架构设计。
docs/plans/2026-05-22-event-system-implementation-plan.md - 事件系统 TDD 实现任务拆分计划。
docs/plans/2026-05-23-portal-event-case-study.md - 以传送门为案例固化事件四阶段方法论，并检查当前代码架构的通用化边界。
docs/plans/2026-05-24-navigation-route-progress-option-b-design.md - 导航冲突方案 B 设计：保留现有普通导航和事件移动执行器，新增统一路线进度/锚点消费模型。
docs/plans/2026-05-24-navigation-task-queue-option-c-design.md - 导航冲突方案 C 设计：把必经点、出口和事件抽象成统一 NavigationTask，由统一任务队列状态机调度。
docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md - 用户选定方案 C 后的详细实施计划，按 RouteContext、MovementExecutor、EventCoordinator 拆分、TaskBuilder/Scheduler/Controller、UI 接入和旧逻辑清理分阶段执行。
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
                                  ├──▶ EventCoordinator.observe/run_task
                                  ├──▶ NavigationTaskController ──▶ NavigationIntent
                                  └──▶ MotionController ──▶ Win32 mouse_event / key input
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
│ NavigationTaskController │
│ select route/event task  │
│ MovementExecutor -> step │
└──────────┬───────────────┘
           ▼ MOVE_MAP intent
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
注意事项：`monitor_size`/`draw_scale` 服务定位一致性；`game_view_map_size` 和点击半径参数服务主画面移动控制，不能反向影响定位。`RecognizerParams` 严格接收当前代码声明的字段，包含绘图页写入的 `player_clear_radius`；未知字段不做静默过滤，配置和代码不一致时应直接暴露。

### `core/motion_controller.py`
职责：把 `NavigationTaskController` 输出的地图全局子目标转换为屏幕物理坐标点击。
关键导出：`MotionController`。
对外依赖：`core.input_driver.InputDriver`；`pydirectinput.click` 仅为异常兜底。
注意事项：当前不负责寻路、不负责定位，只处理“地图方向 -> 屏幕点击”。`movement_scale_factor` 先得到原始屏幕半径，再由 `movement_min_click_radius`/`movement_max_click_radius` 夹紧；底部 UI 防误点由 `bottom_click_guard_pixels` 在最终点击前单独处理，不反向修改移动比例。事件系统的显式屏幕点击走 `click_screen_position()`，事件按键走 `press_key()`，避免 handler 直接调用私有输入细节。

### `gui/dialogs/event_manager_dialog.py`
职责：独立事件管理窗口，用于测试和运行时观察事件系统。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`。
注意事项：事件选配表只展示完整事件包，例如 `portal`；不会暴露 minimap detector、main-view confirmer、handler 等内部步骤。任务表从 `EventCoordinator.tasks()` 刷新，展示 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。完整 `refresh()` 会重建事件表和参数控件；运行中高频更新使用 `refresh_tasks()` 只刷新任务表，避免导航循环反复重建按钮和参数控件。选中事件行后，参数面板根据该事件的 `config_schema()` 自动生成控件，参数变化只更新内存态配置并发出 `config_changed`，点击保存才写入当前地图 `event_config.json`。`test_portal_button.clicked` 通过 lambda 丢弃 Qt 的 checked 参数后再发出无参 `test_portal_requested`，避免信号参数污染导航层槽函数。`reset_portal_button` 发出 `reset_portal_requested`，由导航页清空 portal 运行时任务和定位聚类，方便同一地图反复测试。

### `gui/dialogs/advanced_settings_dialog.py`
职责：高级参数弹窗主类，负责 tab 构建、按钮/文件对话框连接、参数文件读写和 recognizer/stitcher 实时应用时机。
关键导出：`AdvancedSettingsDialog`。
对外依赖：`gui.dialogs.advanced_settings.params_adapter`。
注意事项：`load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口保留，内部委托参数映射 helper。文件保存/加载路径、JSON 格式、状态文案和应用到 recognizer/stitcher 的顺序仍由本类维护；helper 不做文件 IO，也不弹窗。

### `gui/dialogs/advanced_settings/__init__.py`
职责：高级参数弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/advanced_settings/params_adapter.py`
职责：封装高级参数弹窗控件与参数 dict/预设之间的双向映射。
关键导出：`load_params_to_widgets`、`collect_params_from_widgets`、`reset_widgets_to_default`、`apply_loaded_params_to_widgets`、`apply_preset_to_widgets`。
对外依赖：无内部业务模块依赖；只操作传入 dialog 的已存在控件。
注意事项：该模块不保存参数文件、不读取 JSON、不调用 recognizer/stitcher。`reset_widgets_to_default()` 保持旧 reset 字段集合，不额外写 `blur_strength_spin`；`load_params_to_widgets()` 仍写入 `blur_strength_spin=3`，保持旧加载当前参数行为。

### `gui/dialogs/color_picker_dialog.py`
职责：交互式颜色选择弹窗，负责采样点交互、模式切换、HSV 计算流程、预览刷新、debug 图片/日志输出和结果返回。
关键导出：`ColorPickerDialog`。
对外依赖：`core.recognizer_optimized.HSVRecognizer`、`gui.widgets.clickable_label.ClickableImageLabel`、`gui.dialogs.color_picker.hsv_ranges`、`gui.dialogs.color_picker.image_renderer`。
注意事项：`calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口保留，内部委托 helper。`update_preview()` 仍在本类内维护 mask、形态学、debug png/txt 输出，避免改变调试文件内容和生成时机。

### `gui/dialogs/color_picker/__init__.py`
职责：颜色选择弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/color_picker/hsv_ranges.py`
职责：封装颜色选择弹窗中的 BGR->HSV 转换、采样点 HSV 提取、HSV 范围计算和平均饱和度计算。
关键导出：`bgr_to_hsv`、`hsv_values_at_points`、`calculate_hsv_range`、`mean_saturation`。
对外依赖：无内部业务模块依赖；只使用 OpenCV/Numpy。
注意事项：`calculate_hsv_range()` 保持旧算法：均值、标准差、`max(std*2, [5,20,20])` 容差、HSV 边界 `[0,0,0]` 到 `[179,255,255]`。

### `gui/dialogs/color_picker/image_renderer.py`
职责：封装颜色选择弹窗中的 OpenCV 图像转 QPixmap 和采样 marker 绘制。
关键导出：`pixmap_from_image`、`draw_sample_markers`。
对外依赖：无内部业务模块依赖；只使用 OpenCV 和 PySide6 图像绘制类。
注意事项：灰度图仍使用 `QImage.Format_Grayscale8`，彩色图仍 BGR 转 RGB；marker 颜色、半径、缩放公式和 label 固定尺寸逻辑保持原 `_show_image()` 行为。

### `gui/modes/navigation_mode.py`
职责：导航模式 UI 与运行循环，包含地图加载、定位、路线编辑、自动导航动作消费、绿色定位框和橙色真实可见框绘制。
关键导出：`NavigationModeWidget`。
对外依赖：`NavigationCore`、`MotionController`、`NavigationTaskController`、`RouteManager`、`EventCoordinator`、`ManualEventTestController`、`navigation.event_adapter`、`navigation.route_overlay`、`navigation.event_overlay`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`required_points` 是必须按顺序完成的阶段门；`guide_points` 是有序软锚点/辅助走廊，只在 `MovementExecutor` 规划 required、exit 或 event 目标时塑形路线，不作为独立导航目标。导航循环每帧先定位，再通过 `EventCoordinator.observe()` 持续检测/定位/记忆事件，随后由 `NavigationTaskController.update()` 在 required、exit、event 之间统一调度并输出 `NavigationIntent`。事件被选中后才调用 `EventCoordinator.run_task()` 推进 handler；事件 `MOVE_TO` 与普通目标共用同一个 `MovementExecutor`，事件 `PRESS_KEY/CLICK_SCREEN` 也统一在 `_execute_navigation_intent()` 中消费。传送门手动测试只是把 controller 置为 manual-event-only 模式，不再走单独事件移动链路。事件管理窗口可见时，导航循环只调用 `EventManagerDialog.refresh_tasks()` 更新任务表，完整 `refresh()` 留给手动刷新、上下文切换和配置变化。路线 overlay 与事件 overlay 的 QGraphicsItem 创建/清理由 `gui/modes/navigation/route_overlay.py` 和 `event_overlay.py` 承担。本文件不再打印每帧“当前位置/位置来源”调试块，导航/事件操作过程走 `logs/event_runtime.log`。
### `gui/modes/navigation/event_adapter.py`
职责：封装导航模式和事件系统之间的轻量桥接，不推进事件状态机。
关键导出：`create_default_event_registry`、`event_config_summary`、`find_default_game_window_rect`、`build_event_tick`、`should_event_action_take_control`、`is_terminal_event_action`、`event_status_text`。
对外依赖：`core.events.models.EventTick/EventActionType`、`core.events.registry.EventRegistry`、`core.events.types.portal.PortalEventDefinition`、`core.events.window_finder.find_game_window`。
注意事项：该模块只组装事件系统需要的输入和状态文案；当前主链路不再使用 action 接管判定函数，事件 handler 的执行由 `NavigationTaskController` 通过 `EventCoordinator.run_task()` 触发，真实输入由 `_execute_navigation_intent()` 统一消费。
### `gui/modes/navigation/event_overlay.py`
职责：封装导航地图事件 marker 的 QGraphics 绘制和清理。
关键导出：`clear_event_overlay`、`global_to_scene`、`render_event_overlay`。
对外依赖：无内部业务模块依赖；只接收调用方传入的 `scene/nav_core/event_coordinator/items`。
注意事项：该模块只移动原 `NavigationModeWidget` 中的绘制细节，不决定事件启用、调度或状态；事件过滤仍由 `EventCoordinator.overlays()` 完成。
### `gui/modes/navigation/map_runtime.py`
职责：封装导航模式地图目录解析、地图列表读取、导航配置读写和截图几何计算。
关键导出：`MISSING_MAP_DATA_LABEL`、`project_root_from_file`、`map_data_dir`、`list_map_names`、`resolve_map_folder`、`load_nav_config`、`save_nav_config`、`save_default_nav_config`、`physical_center_from_logical`、`build_capture_geometry`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：该模块不弹窗、不改按钮、不初始化 `NavigationCore`；调用方仍负责 UI 状态和异常提示。`load_nav_config()` 优先读取当前地图 `config.json`，缺失时读取项目根 `config.json` 作为默认配置但仍返回 `config_exists=False` 供 UI 提示。`save_default_nav_config()` 合并写入项目根 `config.json`，保留绘图模式的 `stitcher_params` 等非导航字段。`build_capture_geometry()` 保留旧契约：显式 `monitor_region` 返回矩形且 player_pos 为 `None`，中心点模式返回正方形截图矩形和截图中心 player_pos。
### `gui/modes/navigation/route_overlay.py`
职责：封装导航路线 overlay 的 QGraphics 绘制，包括出口、必经点、途经点、当前路径和 subgoal。
关键导出：`clear_route_overlay`、`render_route_overlay`。
对外依赖：`gui.modes.navigation.event_overlay.global_to_scene`。
注意事项：该模块只渲染调用方传入的 `route_data/current_path/current_subgoal/current_*_index/current_target_kind`，不读取或写入 `route.json`，不推进自动导航状态机。途经点显示为 `A1/A2/...` 辅助锚点，不再根据 `guide_index` 标记已完成或当前目标。
### `gui/modes/navigation/viewport_overlay.py`
职责：封装导航相关矩形几何计算，避免页面主类直接维护屏幕幕布/监控框/真实主画面框公式。
关键导出：`screen_overlay_geometry`、`monitor_scene_rect`、`game_view_scene_rect`。
对外依赖：无内部业务模块依赖；只使用传入的 `capture_rect/nav_config/nav_core/player_pos/player_local_pos`。
注意事项：该模块只返回矩形数据，不创建/删除 Qt item，不决定 overlay 是否显示；主类仍负责 `OverlayWindow` 和 QGraphicsRectItem 的 hide/show。

### `gui/modes/mapping_widget.py`
职责：绘图模式主界面，仍负责控件组合、区域/中心选择、实时截图建图、调用地图显示 helper、路径点击入口、参数控件同步和状态栏更新。
关键导出：`MappingWidget`。
对外依赖：`TransparentOverlay`、`CenterPointSelector`、`ColorPickerDialog`、`ScalableMapWidget`、`CollapsibleMapGroup`、`AdvancedSettingsDialog`、`gui.modes.mapping.save_load`、`gui.modes.mapping.map_renderer`、`gui.modes.mapping.params_adapter`。
注意事项：`save_map()`、`save_config()`、`load_saved_params()` 作为外部兼容入口保留，但路径解析、目录创建、JSON 读写和配置 dict 构造已委托 `mapping/save_load.py`。`update_displays()` 和 `_show_image()` 入口保留，但图像转换、全局地图着色、路径线、视野框和当前位置圆点绘制已委托 `mapping/map_renderer.py`。HSV/feature/merge 参数控件读取和已加载参数回填已委托 `mapping/params_adapter.py`；本类仍决定何时调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`，以保持原副作用顺序。高分辨率绘图参数 `draw_scale`、`canvas_size`、`player_clear_radius`、`wall_close_kernel_size` 已作为绘图页控件暴露；空地图时几何参数可立即重建画布，已有帧时仅保存为下次重置/新地图使用。

### `gui/modes/mapping/__init__.py`
职责：绘图模式 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/modes/mapping/map_renderer.py`
职责：封装绘图模式图像展示相关转换和 OpenCV overlay 绘制。
关键导出：`pixmap_from_bgr`、`unpack_enhanced_map_result`、`render_global_map_pixmap`。
对外依赖：无内部业务模块依赖；只使用 OpenCV/Numpy/PySide6 图像类型。
注意事项：该模块不读取 `app_context`、不调用 stitcher、不设置 Qt 控件；调用方传入已取出的地图图像、裁剪偏移、路径、当前位置、draw_scale、player_pos 和 capture_size。颜色、线宽和 fallback 解包逻辑保持原 `MappingWidget.update_displays()` 行为。

### `gui/modes/mapping/params_adapter.py`
职责：封装绘图模式参数控件到 recognizer/stitcher 参数字段的轻量映射。
关键导出：`apply_hsv_toggles`、`feature_params_from_widgets`、`apply_merge_weight`、`sync_recognizer_widgets`、`sync_stitcher_widgets`。
对外依赖：无内部业务模块依赖；只使用传入的控件和 recognizer/stitcher 对象。
注意事项：该模块不保存配置、不弹窗、不创建控件、不阻断 Qt 信号。`sync_recognizer_widgets()` 和 `sync_stitcher_widgets()` 保持原 `setChecked()`/`setValue()` 写回顺序和默认值，因此仍可能触发既有信号副作用；这是为保持行为不变而刻意保留。

### `gui/modes/mapping/save_load.py`
职责：封装绘图模式项目根目录解析、`map_data` 目录定位、地图目录创建、根级/地图级 `config.json` 读写和配置 dict 构造。
关键导出：`project_root_from_file`、`map_data_dir`、`map_folder_for_name`、`ensure_map_folder`、`root_config_path`、`build_mapping_config`、`save_json_config`、`load_json_config`、`save_root_config`、`load_root_config`、`save_map_config`。
对外依赖：无内部业务模块依赖；通过传入的 `app_context` 读取当前 recognizer/stitcher 参数。
注意事项：该模块不弹窗、不写 Qt 控件、不调用 `stitcher.save_map_package()`；`json.dump(..., indent=4)` 保持旧保存格式，未设置 `ensure_ascii=False` 以避免改变现有输出行为。

### `gui/modes/event_test_controller.py`
职责：把手动事件测试按钮的 active 状态、checked 状态和显示文案封装到独立小模块，避免导航主文件同时承担 UI 状态同步细节。
关键导出：`ManualEventTestController`。
对外依赖：无内部模块依赖。
注意事项：该类只同步按钮状态，不决定事件选择、事件执行、导航启动或停止；这些仍由 `NavigationModeWidget` 和事件系统负责。`button` 可为 `None`，此时状态仍可维护但不会触碰 UI。

### `core/route_manager.py`
职责：维护每张地图的 `route.json`，持久化出口、必经点、途经点。
关键导出：`RouteManager`。
对外依赖：标准库 `json`、`pathlib.Path`。
注意事项：`required_points` 和 `guide_points` 是两套独立序列；`clear_route()` 会同时清空两类点，避免旧路线状态残留。

### `core/anchor_path.py`
职责：为地图坐标 A* 提供可选软锚点规划，避免普通导航和事件移动各自复制“把辅助点放进路径规划”的逻辑。
关键导出：`AnchorPathResult`、`plan_path_with_optional_anchors`。
对外依赖：`core.path_utils.point_distance`。
注意事项：该模块不会把锚点当作自动导航完成目标，也不会把锚点做成最短路图。`guide_points` 按用户添加顺序形成有序走廊；当前位置之前的锚点视为已路过，当前位置到当前主目标投影之间的锚点会按顺序保留。`anchor_step` 表示先走到下一个前方锚点，调用方到达后重新规划；`anchor_probe` 表示该锚点 A* 暂不可达时先朝它做约 84 像素短探测，不再直接点击不可达锚点；只有没有前方锚点时才直接 A* 到当前主目标。

### `core/navigation_tasks/*`
职责：方案 C 的统一导航任务层，把静态路线目标和动态事件目标放进同一调度与移动执行链路。
关键导出：`NavigationTaskController`、`NavigationTaskScheduler`、`NavigationTaskBuilder`、`MovementExecutor`、`RouteContext`、`NavigationTask`、`NavigationIntent`、`NavigationIntentType`。
对外依赖：`core.anchor_path`、`core.path_utils`、`core.events.models.EventActionType`。
注意事项：`NavigationTaskController` 是自动导航和手动事件测试的唯一运行控制器；原普通导航器、事件路径移动器、事件动作执行器三个旧模块已删除。`RouteContext` 负责 guide_points 折线投影和单调路线进度；`NavigationTaskBuilder` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中可运行事件转成 `NavigationTask`；`NavigationTaskScheduler` 只对 event 持有 active lock，静态 required/exit 每帧重新仲裁以允许新事件抢占；`MovementExecutor` 在任务切换时由 controller 重置，避免上一任务的路径和点击节流污染下一任务。事件 `MOVE_TO` 和普通 required/exit 都走 `MovementExecutor.step()`，事件 `PRESS_KEY/CLICK_SCREEN` 直接转成 `NavigationIntent` 由 GUI 消费。`CoordinateDiagnostics` 是内部坐标恢复机制，不进入事件系统，不和 portal 等业务事件竞争调度。

### `core/navigation_core.py`
职责：读取 `map_data.npz`，用实时小地图截图定位玩家在全局地图中的坐标。
关键导出：`NavigationCore`。
对外依赖：`HSVRecognizer`、`core.navigation_obstacles.derive_navigation_wall_layer`。
注意事项：`draw_scale` 必须与建图保持一致；定位运行时以 `map_data.npz` 里的 `draw_scale` 为权威来源，导航配置里的同名字段只作为旧配置/显示兼容，发现不一致会记录 `navigation draw_scale config mismatch` 并使用地图包值。输出坐标是全局地图坐标，不是屏幕点击坐标。原始 `wall_layer` 必须保持不变并继续服务定位、事件配准和地图显示；`nav_wall_layer` 是由原始墙图派生出的 A* 专用障碍层，可按 `nav_wall_erode_iterations` 侵蚀以放宽窄通道。`wall_match_close_kernel_size` 用于让导航模板匹配复现建图时的墙体闭运算；新地图包会把 `wall_close_kernel_size` 写入 npz，旧地图回退 3。`fog_layer` 仍会随地图包保存，但当前显示默认只渲染 `explored_map`（灰）和 `wall_layer`（白），不额外铺蓝底。战斗/事件场景下，F2F 跟踪优先使用 `wall_mask` 而不是混合 `match_mask`，以降低动态边缘特效带来的漂移。`request_full_map_localization()` / `request_global_relocalization()` 只用于清空 F2F 状态并强制下一帧走与开始导航一致的完整 `wall_layer` 模板匹配，不允许引入固定偏移补偿。模板匹配失败会节流打印 `Localization template match failed`，包含置信度、阈值、full_map/forced 状态、raw/scaled mask 尺寸、特征数、搜索区域和闭运算核，专门用于排查绘图层与实时识别层不一致。

### `core/navigation_obstacles.py`
职责：把定位用原始墙图转换为导航寻路可使用的宽容墙图。
关键导出：`derive_navigation_wall_layer`。
对外依赖：无内部模块依赖。
注意事项：该模块只返回派生数组，不写回 `wall_layer`。它是“视觉/定位墙体”和“A* 障碍墙体”分离的边界，后续不能把侵蚀后的结果用于 `NavigationCore.localize()` 或事件 `EventPositionStabilizer`。

### `core/pathfinder.py`
职责：把调用方传入的障碍层结合 `explored_map` 转为低分辨率 A* 网格，并输出全局地图路径点。
关键导出：`PathFinder`。
对外依赖：无内部模块依赖。
注意事项：路径点用于地图导航，不能直接当屏幕点击点。默认 `safety_margin=0`、`wall_shrink_iterations=0`，墙体变薄优先在 `NavigationCore.nav_wall_layer` 派生阶段完成，避免双重侵蚀。`start_clear_radius` 会在 A* 网格上清空玩家当前位置附近的小圆，容忍“定位点落在视觉墙像素内”；`walkable_snap_radius` 控制起终点落障碍时寻找最近可走格的半径。`explored_map==0` 必须视为不可走，否则 A* 会穿过地图外黑区。

### `core/stitcher_core.py`
职责：将实时小地图墙层/地面层融合到全局地图，并输出供绘图模式与导航模式共用的地图包。
关键导出：`MapStitcher`。
对外依赖：`cv2`、`numpy`。
注意事项：当前版本不再把整块截图矩形无脑写入 `explored_map`；优先使用 `fog_mask` 作为精准可见区域，并同步维护 `fog_layer`，这样生成的地图更接近游戏实际小地图结构。

### `utils/event_icon_probe.py`
职责：不接入导航主循环，只用于验证“原始小地图截图 + 事件图标模板”能否识别出事件候选。
关键导出：`CaptureGeometry`、`parse_args()`、`load_config()`、`build_capture_geometry()`、`probe_frame()`、`main()`。
对外依赖：`core.capture.SquareScreenCapture`。
注意事项：事件识别必须使用 raw minimap frame，不使用 `HSVRecognizer.extract_combined()` 之后的定位特征图；脚本需要和游戏同权限运行，非管理员权限可能抓到黑帧。`--template` 和 `--image` 均可重复传入；静态图片模式用于验证用户提供截图是否能被当前模板资产识别。默认仍可跑整块模板诊断；加 `--portal-feature-detector` 时改用运行时 portal 蓝色本体特征算法，打印 mask/density 分数和蓝色像素范围，用于区分“背景模板不鲁棒”和“本体特征不可分”的问题；加 `--portal-shape-color-detector` 时改用探针专用形状+颜色联合算法，同时保存蓝色 core mask、白/灰 outer-ring mask、combined shape mask 和 accepted/rejected 候选裁剪，用于确认误报是否来自“只有蓝色相似但外环/轮廓不完整”。

### `gui/dialogs/event_manager_dialog.py`
职责：事件系统的非模态管理窗口，展示完整事件选配、事件参数、识别任务状态，并发出保存、测试传送门、刷新传送门状态信号。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`。
注意事项：窗口使用 `Qt.Tool` 且 `WA_DeleteOnClose=False`，避免手动传送门测试期间主窗口进入游戏输入模式后，事件面板跟随父窗口层级被隐藏或关闭后无法再次打开。导航页每次打开事件管理时会确保窗口存在、刷新上下文并显式 `show/raise/activate`。

### `utils/portal_screen_probe.py`
职责：不接入导航主循环，只用于验证主游戏画面里传送门实体是否能被视觉识别。
关键导出：`main()`。
对外依赖：`core.capture.SquareScreenCapture`、`core.events.window_finder`、`core.events.types.portal.main_view_confirmer`。
注意事项：该探针默认枚举 `UnrealWindow` / `Torchlight` 游戏窗口并抓整块窗口画面；也支持 `--rect` 或 `--full-screen`。探针现在复用 portal 事件包的 main-view confirmer，避免探针算法和运行时算法漂移。

### `core/events/*`
职责：事件系统核心层。`EventCoordinator` 是导航模式唯一事件入口；`EventRegistry` 只注册完整事件包；`EventMemory` 管理事件实例生命周期；`EventRunner` 调用具体事件 handler。
关键导出：`FrameRegistration`、`EventTick`、`EventDetection`、`EventObservation`、`EventTask`、`EventAction`、`EventCoordinator`、`EventRegistry`、`EventSystemConfig`。
对外依赖：标准库；视觉工具依赖 OpenCV/NumPy。
注意事项：事件 handler 不直接操作鼠标键盘，只返回 `EventAction`；TUI/配置层只能看到 `EventDefinition` 级完整事件，例如 `portal`。`EventCoordinator.observe()` 只做检测、事件定位、memory 合并、任务表/overlay 状态更新；`EventCoordinator.run_task(task_id, tick)` 只推进被统一导航调度器选中的事件任务。旧 UI 层事件允许集合兼容入口已删除，避免重新引入 UI 层事件仲裁。`EventPositionStabilizer` 会按同一帧隔离聚类，避免一帧内两个相近事件图标被合并成一个跳动 marker；`EventMemory.merge_observations()` 还会避免同一帧多个 observation 复用同一个刚更新的 task，近距离双传送门依赖 `dedupe_radius` 小于两门间距来稳定显示两个 marker。事件执行抢占规则已迁移到 `NavigationTaskScheduler`，事件本身作为动态必经点参与 required/exit 的统一调度。
`EventCoordinator.reset_event_type(event_type, now_ms)` 是事件管理 UI 的运行时重置入口；它清理同类型 active handler、memory tasks、position clusters、last detections/observations 和 selected task，不改 `event_config.json`，用于同一地图反复识别/执行某类事件。

### `core/events/types/portal/*`
职责：传送门完整事件包。对外暴露 `PortalEventDefinition`，内部拆分小地图 detector、主画面 confirmer 和 handler。
关键导出：`PortalEventDefinition`。
对外依赖：`core.events.detectors.template_matcher`、`core.events.types.portal.minimap_feature_matcher`、`core.events.types.portal.minimap_shape_color_matcher`、`core.events.types.portal.main_view_confirmer`。
注意事项：小地图 detector 的识别算法由 `PortalEventConfig.detector_mode` 选择：`template` 只走旧灰度/边缘整块模板；`feature` 只走蓝色本体特征；`feature_then_template` 先走蓝色本体特征、无命中再回退整块模板；`shape_color` 走形状+颜色联合匹配。旧配置只含 `feature_detector_enabled=false` 时会被兼容映射为 `detector_mode=template`，避免已有地图行为突然改变。shape+color 同时要求蓝色核心、白/灰外环、组合轮廓、边缘和 HSV 颜色一致，适合压住“蓝色相似但不是传送门”的误报。命中后仍必须通过 `_portal_color_check()`，避免白色墙体、圆形地形细节被识别成传送门。当前传送门主流程是靠近后点击映射传送门点、短暂等待、再按 `D`；即使配置残留 `interaction="click"`，`PortalEventHandler` 也会强制按键交互并记录日志，不再要求主画面蓝紫实体确认。按键/点击后 handler 等待位置变化或小地图周边环境变化才判定传送完成，避免固定等待导致误完成；完成动作会携带入口和出口坐标，runner 将出口附近的传送门任务也标记 completed，防止双门来回触发。

## 5. 函数索引与算法实现
### `minimap_feature_matcher.portal_blue_mask(image: np.ndarray, *, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95) -> np.ndarray`
行为：从 raw minimap 或模板图中提取传送门蓝/青本体像素，输出 0/255 二值 mask。
算法：
1. 灰度图先转 BGR，彩色图取前三通道。
2. BGR 转 HSV。
3. 按 hue 范围构造颜色 mask，支持 hue 区间跨 0 的情况。
4. 叠加饱和度和亮度下限，输出 uint8 二值图。
副作用：无。
失败行为：输入为空会由 OpenCV 抛出异常，调用方负责不传空帧。

### `minimap_feature_matcher.match_portal_features(frame: np.ndarray, templates: list[PortalFeatureTemplate], scales: list[float], *, top_k: int, threshold: float, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95, min_blue_pixels: int = 36, max_blue_pixels: int = 420) -> list[PortalFeatureHit]`
行为：用传送门蓝色本体特征做多尺度匹配，避免整块模板把背景/墙体当成识别依据。
算法：
1. 调用 `portal_blue_mask()` 从 raw frame 提取二值蓝色特征图。
2. 对每个模板蓝色特征和每个 scale 做最近邻缩放。
3. 用 `cv2.matchTemplate(..., TM_CCOEFF_NORMED)` 在二值特征图上匹配，并清理 NaN/Inf 响应。
4. 以 `threshold - 0.18` 收集候选，再对候选窗口统计蓝色像素数量，过滤过少或过多的蓝色区域。
5. 计算 `density_score`，衡量候选蓝色像素数量与模板蓝色像素数量是否接近。
6. 组合 `score = mask_score * 0.86 + density_score * 0.14`，低于阈值的候选丢弃。
7. 调用 `merge_feature_hits()` 按中心距离去重并返回最高分候选。
副作用：无。
失败行为：无模板或空帧返回空列表；后续 detector 会回退到整块模板兜底。

### `minimap_shape_color_matcher.portal_blue_mask(image: np.ndarray, *, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95) -> np.ndarray`
行为：从 raw minimap 或模板图中提取传送门蓝/青核心像素，输出 0/255 二值 mask。
算法：
1. 将灰度输入转 BGR，彩色输入取前三通道。
2. BGR 转 HSV。
3. 按 hue 区间、饱和度下限和亮度下限构造蓝/青核心 mask，支持 hue 区间跨 0。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常，调用方负责过滤。

### `minimap_shape_color_matcher.portal_outer_mask(image: np.ndarray, *, sat_max: int = 115, val_min: int = 105, blue_mask: np.ndarray | None = None) -> np.ndarray`
行为：提取传送门图标白/灰外环像素，用于把“只有蓝色相似”的假候选排除。
算法：
1. 将输入转 HSV。
2. 选取低饱和、高亮度像素作为白/灰外环候选。
3. 如果传入 `blue_mask`，从外环候选中排除蓝色核心像素。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常。

### `minimap_shape_color_matcher.match_portal_shape_color(frame: np.ndarray, templates: list[TemplateSpec], scales: list[float], *, top_k: int, params: PortalShapeColorParams | None = None, collect_threshold: float | None = None) -> tuple[list[PortalShapeColorHit], PortalShapeColorDebug]`
行为：探针专用的传送门小地图联合匹配入口，同时验证蓝色核心、白/灰外环、整体形状、边缘和 masked HSV 颜色相似度。
算法：
1. 从 raw frame 生成 `frame_blue`、`frame_outer`、`frame_shape=blue|outer` 和 Canny 边缘图。
2. 对每个模板和每个 scale，生成对应的蓝色 mask、外环 mask、组合 shape mask、edge mask 和缩放模板图。
3. 分别计算 blue/outer/shape/edge mask 的 `TM_CCORR_NORMED` 响应，以及基于 shape mask 的 BGR masked color response。
4. 将候选响应按 `blue*0.30 + outer*0.24 + shape*0.24 + edge*0.12 + color*0.10` 合成，先以 `threshold - 0.22` 收集宽松候选。
5. 对每个候选窗口计算 blue、outer、shape、edge 的 F1-like score 和 masked HSV color score。
6. 用 `blue*0.31 + outer*0.25 + shape*0.25 + edge*0.11 + color*0.08` 得到最终 score。
7. 依次应用门禁：总分、blue shape、outer shape、combined shape、blue 像素下限/上限、outer 像素下限；失败原因写入 `reject_reasons`。
8. 调用 `merge_shape_color_hits()` 合并重复候选，合并时优先保留 accepted，再按分数排序。
9. 返回候选列表和调试 mask，供 probe 保存可视化图片。
副作用：无；调用方保存 debug 图片。
失败行为：无有效模板特征时跳过对应模板；OpenCV masked color response 不支持时回退为空响应，不中断探针。

### `minimap_shape_color_matcher.merge_shape_color_hits(hits: list[PortalShapeColorHit], top_k: int, center_radius: float = 12.0) -> list[PortalShapeColorHit]`
行为：把多个模板/尺度产生的传送门候选按中心距离去重。
算法：
1. 按 `(accepted, score)` 降序遍历候选，保证通过门禁的候选不会被同位置高分 rejected 候选挤掉。
2. 对每个候选，计算其中心与已保留候选中心的距离。
3. 距离小于动态半径时视为同一图标，只保留先进入的候选。
4. 保留数量达到 `top_k` 后停止。
副作用：无。
失败行为：空输入返回空列表。

### `PortalMinimapDetector.detect(self, tick, config) -> list[EventDetection]`
行为：传送门小地图事件识别入口，按 `detector_mode` 在 template、feature、feature_then_template、shape_color 四种算法之间选择。
算法：
1. 将外部 config 规范化为 `PortalEventConfig`，并按 HSV feature 参数刷新模板蓝色特征。
2. raw minimap frame 为空或模板缺失时节流记录 skipped 并返回空。
3. `_detector_mode()` 读取 `detector_mode`；值非法时按旧 `feature_detector_enabled` 映射为 `feature_then_template` 或 `template`。
4. `template` 模式直接调用 `match_templates()`。
5. `feature` 模式只调用 `_detect_feature_hits()`。
6. `feature_then_template` 模式先调用 `_detect_feature_hits()`，无命中时调用 `match_templates()` 兜底。
7. `shape_color` 模式调用 `_detect_shape_color_hits()`；该函数只返回 accepted shape+color 候选，并在所有候选都被拒绝时记录 `portal minimap shape-color rejected`。
8. 全部模式无命中时，节流记录 `portal minimap no hits`，包含当前模式、raw frame 蓝色特征像素数量、feature 阈值和 shape 外环阈值。
9. 对候选按 `max_candidates` 截断前，逐个调用 `_portal_color_check()` 做最终蓝色比例过滤。
10. 为每个 accepted hit 输出 local-only `EventDetection`，metadata 记录 detector source、template、mask/density/shape score/blue pixel 等诊断字段。
11. 节流记录 `portal minimap hits`，包含 mode、source 和最佳候选各类分数。
副作用：更新 detector 当前 config、feature template cache 和事件日志。
失败行为：未命中返回空列表；不会直接创建全局事件坐标。

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
调用关系：called by `NavigationModeWidget._execute_navigation_intent()` when consuming a `PRESS_KEY` intent.

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
1. 调用 `render_event_overlay(scene, nav_core, event_coordinator, event_overlay_items)`。
2. helper 若 scene/nav_core/coordinator 任一不可用，会清空旧事件 marker 后返回空列表。
3. helper 从 `EventCoordinator.overlays()` 读取当前启用事件的 overlay 模型。
4. helper 用 `nav_core.crop_offset` 将全局地图坐标转换为当前裁剪场景坐标。
5. helper 按 overlay 颜色绘制圆点；`running` 状态半径更大，并在圆点旁绘制事件名称和状态文本。
副作用：清空并重建 `event_overlay_items` 中的 QGraphicsItem。
失败行为：坐标为空或无法映射时跳过该 marker。
调用关系：called by `navigation_loop()` and `_render_route_overlay()`。

### `render_route_overlay(scene, nav_core, route_data, items: list, current_path=None, current_subgoal=None, current_required_index=None, current_guide_index=None, current_target_kind=None)`
行为：根据现有路线数据和自动导航运行态绘制出口、必经点、途经点、当前路径和子目标。
算法：
1. 清空传入的旧 route overlay items。
2. 从 `route_data["routes"]["main"]` 读取 `exit_region`、`required_points`、`guide_points`。
3. 使用 `global_to_scene()` 将全局坐标减去 `nav_core.crop_offset` 得到场景坐标。
4. 绘制出口橙色圆、必经点紫色/灰色 marker、途经点青色 `A1/A2/...` 辅助锚点；途经点不再按当前 target kind 加粗或标记完成。
5. 如传入 `current_path`，构造 `QPainterPath` 绘制黄色路径线。
6. 如传入 `current_subgoal`，绘制洋红色子目标点。
7. 返回新的 item 列表和 route path item。
副作用：向 QGraphicsScene 添加/移除 QGraphicsItem。
失败行为：scene/nav_core 不可用时由调用方早退；单点无法映射时跳过该点。
调用关系：called by `NavigationModeWidget._render_route_overlay()`。

### `render_event_overlay(scene, nav_core, event_coordinator, items: list) -> list`
行为：根据事件系统 overlay 模型绘制事件 marker。
算法：
1. scene/nav_core/event_coordinator 任一不可用时清空旧事件 items 并返回空列表。
2. 清空旧事件 items。
3. 遍历 `event_coordinator.overlays()`，读取每个 overlay 的 `global_pos/color/state/label`。
4. 调用 `global_to_scene()` 转换坐标。
5. 绘制事件圆点和文本 label，running 状态使用更大半径。
副作用：向 QGraphicsScene 添加/移除事件 QGraphicsItem。
失败行为：单个 overlay 坐标无法映射时跳过。
调用关系：called by `NavigationModeWidget._render_event_overlay()`。

### `EventManagerDialog.refresh(self) -> None`
行为：执行完整刷新，重建事件选配表、参数面板和事件任务表。
算法：
1. 调用 `_refresh_events()` 重建完整事件选配表。
2. 调用 `_refresh_tasks()` 从 coordinator 读取当前任务列表。
3. 当 registry/config 不存在时禁用全局复选框并显示未加载状态。
4. 事件复选框变化通过 `config_changed` 把内存态配置交回导航模式。
5. 保存按钮只发出 `save_requested`，实际路径由导航模式写入当前地图目录。
副作用：重建 QTableWidget 行和状态文案。
失败行为：coordinator 查询异常时 `_current_tasks()` 降级为空列表。
调用关系：called by `EventManagerDialog.set_context()`、刷新按钮、配置勾选变化。

### `EventManagerDialog.refresh_tasks(self) -> None`
行为：只刷新事件任务表和状态摘要，不重建事件选配表、参数面板或按钮。
算法：
1. 调用 `_refresh_tasks()` 从 coordinator 读取当前任务列表。
2. 用现有任务行数据更新 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。
3. 当 config 存在时更新底部状态摘要。
副作用：重写任务 QTableWidget 行和状态文案；不修改事件选配控件和参数控件。
失败行为：coordinator 查询异常时 `_current_tasks()` 降级为空列表。
调用关系：called by `NavigationModeWidget.navigation_loop()` while the event dialog is visible.

### `ManualEventTestController._sync_button(self) -> None`
行为：使手动事件测试按钮的文字和选中状态与 `active` 一致。
算法：
1. 若没有绑定按钮，直接返回，保留纯状态控制能力。
2. 当 `active=True` 时设置停止文案，否则设置启动文案。
3. 仅在控件 checked 值与 `active` 不一致时调用 `setChecked()`，避免无意义 UI 反复写入。
副作用：写入 Qt 按钮文本和 checked 状态。
失败行为：无绑定按钮时无 UI 副作用且不抛错。
调用关系：called by `__init__()`、`start()`、`stop()`、`reset_button()`。

### `NavigationModeWidget._run_portal_manual_test(self)`
行为：响应“测试传送门/停止传送门测试”按钮，以正式事件 pipeline 启停手动传送门执行。
算法：
1. 若 `portal_test_controller.active` 已为真，停止手动测试并返回。
2. 校验事件协调器、地图定位内核和游戏屏幕中心均已就绪；失败时恢复按钮显示并弹出警告。
3. 若导航定时器未运行，则复用 `toggle_navigation()` 启动定位循环；启动失败时停止继续执行。
4. 调用 `_set_portal_manual_test_active(True)`，开启游戏输入模式和运动控制。
5. 后续每帧由 `_navigation_loop_unified()` 调用 `EventCoordinator.observe()` 识别事件，再由 `NavigationTaskController.update(..., manual_event_only=True)` 选择并执行事件任务。
副作用：可启动导航循环、启用游戏输入、更新按钮/状态栏并记录事件日志。
失败行为：先决条件缺失时只警告并保持测试未启动。
调用关系：called by `EventManagerDialog.test_portal_requested` signal。

### `NavigationModeWidget._execute_navigation_intent(self, intent, now_ms: int) -> None`
行为：消费统一导航控制器输出的动作意图，并把地图目标、屏幕点击或按键转换为真实输入。
算法：
1. `NONE/WAIT` 不执行输入，只保留状态栏和 overlay。
2. `MOVE_MAP` 校验 `player_pos/subgoal`，打开游戏输入模式并启用 `MotionController`。
3. 若 intent metadata 带 `force_click_target`，调用 `MotionController.click_map_target_once()` 点击映射后的事件目标点；否则调用 `MotionController.move_to_map_target()` 做方向移动点击。
4. 真实点击成功后调用 `NavigationTaskController.record_intent_click()`，让 `MovementExecutor` 更新点击冷却和上次子目标。
5. `CLICK_SCREEN` 直接调用 `MotionController.click_screen_position()`。
6. `PRESS_KEY` 直接调用 `MotionController.press_key()`。
副作用：可能触发真实鼠标/键盘输入，更新状态栏点击诊断和 controller 点击节流状态。
失败行为：缺少必要坐标或 key 时跳过输入；底层输入异常由 `MotionController`/输入后端处理。
调用关系：called by `NavigationModeWidget._navigation_loop_unified()` after `NavigationTaskController.update()`。

### `build_event_tick(*, now_ms, frame, player_pos, localized_pos, confidence, nav_core, nav_config, map_name: str, capture_provider) -> EventTick`
行为：把导航循环当前帧状态包装成事件系统统一输入。
算法：
1. 接收导航循环已捕获的 raw minimap frame、玩家局部坐标、定位结果和置信度。
2. 从 `nav_core.draw_scale` 读取当前地图缩放；`nav_core` 不存在时回退 `nav_config.draw_scale`。
3. 从 `nav_core.last_frame_registration` 读取当前帧墙体配准契约；`nav_core` 不存在时为 `None`。
4. 组装 `EventTick`，保留 `capture_provider` 供事件 handler 需要主画面截图时使用；`event_tasks` 初始为空，进入 `EventCoordinator.observe()` 后由 coordinator 写入当前 memory 任务快照。
副作用：无。
失败行为：不验证图像或定位是否有效；由 `EventCoordinator` 和后续模块按字段值决定是否运行。
调用关系：called by `NavigationModeWidget._build_event_tick()`。

### `NavigationModeWidget._navigation_loop_unified(self)`
行为：当前唯一导航循环，统一完成定位、事件观察、任务调度、overlay/status 更新和动作意图消费。
算法：
1. 根据导航配置构造截图矩形，捕获 raw minimap frame。
2. 根据配置获取玩家局部位置：显式监视区域走玩家识别，中心点模式使用截图中心。
3. 调用 `NavigationCore.localize()` 得到全局位置和置信度。
4. 构造 `EventTick` 后调用 `EventCoordinator.observe()`，只做事件检测、定位和 memory 更新。
5. 自动导航或手动事件测试启用时，调用 `NavigationTaskController.update()`；普通自动导航允许 required/exit/event 统一调度，手动事件测试使用 `manual_event_only=True`。
6. 更新玩家点、绿色监视框、橙色真实可见框、路线 overlay 和事件 overlay。
7. 调用 `_execute_navigation_intent()` 消费 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY`。
8. 收到 `ARRIVED/FAILED` 时停止自动导航并恢复窗口输入模式。
副作用：更新 UI、事件任务表、controller 状态、可能执行真实输入。
失败行为：截图失败、配置缺失或定位低置信时跳过移动，等待下一帧。
调用关系：called by `navigation_loop()` compatibility entry and QTimer after `_use_unified_navigation_loop()` rewires the timer.

### `map_runtime.build_capture_geometry(nav_config: NavConfig | None, capture_center_physical)`
行为：根据导航配置生成真实屏幕截图矩形和玩家在截图中的局部坐标。
算法：
1. 配置为空时返回 `(None, None, capture_center_physical)`。
2. 若存在 `monitor_region`，将 `left/top/width/height` 转为 int 后返回，player_pos 为 `None`。
3. 若没有 `monitor_logical_center` 或物理中心尚不可用，返回空几何。
4. 中心点模式下用 `monitor_size // 2` 从物理中心计算正方形截图 rect。
5. 返回 player_pos 为截图中心 `(width // 2, height // 2)`。
副作用：无。
失败行为：缺少中心或配置不完整时返回空几何，由调用方决定是否隐藏 overlay 或跳过导航循环。
调用关系：called by `NavigationModeWidget._build_capture_geometry()`。

### `viewport_overlay.monitor_scene_rect(player_pos, capture_rect, player_local_pos, nav_core)`
行为：计算绿色小地图截图范围框在导航地图场景中的矩形。
算法：
1. 校验 player_pos、capture_rect、player_local_pos 和 nav_core。
2. 读取 `nav_core.crop_offset` 和 `draw_scale`。
3. 将截图宽高乘以 draw_scale 得到地图坐标尺寸。
4. 将玩家局部截图坐标乘以 draw_scale，作为从玩家全局位置回推截图左上角的偏移。
5. 返回 `(rect_x, rect_y, rect_w, rect_h)`。
副作用：无。
失败行为：输入不完整时返回 `None`。
调用关系：called by `NavigationModeWidget._update_monitor_rect()`。

### `viewport_overlay.game_view_scene_rect(player_pos, nav_core, nav_config)`
行为：计算橙色真实主画面可见/可交互范围框在导航地图场景中的矩形。
算法：
1. 校验 player_pos、nav_core、nav_config。
2. 读取 `nav_config.game_view_map_size`；小于等于 0 时返回 `None`。
3. 用 `nav_core.crop_offset` 将玩家全局位置转换到当前地图场景。
4. 以玩家位置为中心，返回边长为 `game_view_map_size` 的正方形矩形。
副作用：无。
失败行为：输入不完整或尺寸无效时返回 `None`，调用方隐藏橙色框。
调用关系：called by `NavigationModeWidget._update_game_view_rect()`。

### `build_mapping_config(app_context, fps: int, *, include_draw_scale: bool = False) -> dict`
行为：把绘图模式当前运行态序列化为旧版 `config.json` 字段字典。
算法：
1. 从 `app_context.monitor_logical_center`、`monitor_size`、`monitor_region` 读取截图配置。
2. 使用传入 `fps` 写入帧率字段，避免 helper 依赖 Qt spinbox。
3. 调用 `app_context.recognizer.get_params()` 和 `app_context.stitcher.get_params()` 获取算法参数。
4. 当 `include_draw_scale=True` 时，在字典前部加入 `draw_scale`，用于地图级配置；根级配置保持旧字段集合。
副作用：读取 recognizer/stitcher 参数，不写文件。
失败行为：若 `app_context` 缺少 recognizer 或 stitcher 参数接口，会按原调用路径抛出异常。
调用关系：called by `MappingWidget.save_map()` and `MappingWidget.save_config()`。

### `MappingWidget._build_mapping_config_with_ui_overrides(self, *, include_draw_scale: bool = False) -> dict`
行为：在通用绘图配置基础上叠加绘图页几何/清晰度控件值。
算法：
1. 调用 `build_mapping_config()` 收集截图、FPS、recognizer 和 stitcher 当前运行参数。
2. 用 UI 控件覆盖 `stitcher_params.draw_scale`、`canvas_size`、`wall_close_kernel_size`。
3. 用 UI 控件覆盖 `recognizer_params.player_clear_radius`。
4. `include_draw_scale=True` 时同步写入顶层 `draw_scale`，供导航模式按地图包坐标体系加载。
副作用：读取 Qt 控件值，不写文件。
失败行为：控件缺失时沿原调用路径抛异常。
调用关系：called by `MappingWidget.save_map()` and `MappingWidget.save_config()`。

### `ensure_map_folder(file_path: str | Path, map_name: str) -> Path`
行为：根据当前源码文件定位项目 `map_data/<map_name>` 目录并确保存在。
算法：
1. 将 `file_path` resolve 为绝对路径。
2. 取 `parents[2]` 作为项目根目录，与原 `dirname(dirname(dirname(__file__)))` 保持一致。
3. 拼接 `map_data/map_name`。
4. 调用 `mkdir(parents=True, exist_ok=True)` 创建目录。
副作用：可能创建 `map_data/<map_name>` 目录。
失败行为：文件系统权限或非法地图名导致 `OSError` 向上传播，保持原保存失败路径不吞异常。
调用关系：called by `MappingWidget.save_map()`。

### `save_root_config(file_path: str | Path, config: dict) -> Path`
行为：把绘图模式全局配置写入项目根目录 `config.json`。
算法：
1. 通过 `root_config_path(file_path)` 定位项目根目录配置文件。
2. 调用 `save_json_config()` 以 UTF-8 和 `indent=4` 写入 JSON。
3. 返回写入路径供调用方需要时使用。
副作用：覆盖项目根目录 `config.json`。
失败行为：JSON 序列化或文件写入异常向上传播。
调用关系：called by `MappingWidget.save_config()`。

### `load_root_config(file_path: str | Path) -> dict | None`
行为：读取项目根目录 `config.json`，不存在时保持旧行为直接返回空。
算法：
1. 通过 `root_config_path(file_path)` 定位配置文件。
2. 若文件不存在，返回 `None`。
3. 文件存在时调用 `load_json_config()` 读取 dict。
副作用：读取项目根目录 `config.json`。
失败行为：JSON 格式错误会抛出 `json.JSONDecodeError`，由 `MappingWidget.load_saved_params()` 原有 except 处理。
调用关系：called by `MappingWidget.load_saved_params()`。

### `render_global_map_pixmap(*, global_map, crop_x1: int, crop_y1: int, nav_path, current_position, draw_scale: float, player_pos=None, capture_size=None) -> QPixmap | None`
行为：将 `MapStitcher.get_enhanced_map()` 返回的全局地图图像绘制成可显示的 Qt pixmap。
算法：
1. 空地图直接返回 `None`。
2. 灰度图先转换为 BGR，彩色图复制一份，避免修改原地图数据。
3. 若存在 `nav_path`，将全局路径点减去裁剪偏移，点数超过 1 时用黄色 polyline 绘制。
4. 将 `current_position` 减去裁剪偏移得到当前人物场景坐标。
5. 若 `capture_size` 和 `player_pos` 存在，用 `draw_scale` 计算小地图视野框宽高和人物在截图中的偏移，并绘制绿色矩形。
6. 绘制当前位置绿色实心圆和红色外圈。
7. 调用 `pixmap_from_bgr()` 转为 `QPixmap` 返回。
副作用：无文件或 UI 副作用；只在内部副本上绘制。
失败行为：输入图像 shape 不符合 OpenCV BGR/GRAY 预期时由 OpenCV/PySide 抛错。
调用关系：called by `MappingWidget.update_displays()`。

### `pixmap_from_bgr(image) -> QPixmap | None`
行为：把 OpenCV BGR 图像转换为 Qt `QPixmap`。
算法：
1. 输入为空时返回 `None`。
2. 用 `cv2.cvtColor(..., COLOR_BGR2RGB)` 转为 RGB。
3. 用图像宽高和 `channels * width` 构造 `QImage`。
4. 对 `QImage` copy 后创建 `QPixmap`，避免引用临时 numpy buffer。
副作用：创建 Qt 图像对象。
失败行为：非三通道 BGR 输入会由 OpenCV 或 QImage 构造抛错；当前调用方只传预处理截图或已转为 BGR 的全局图。
调用关系：called by `MappingWidget._show_image()` and `render_global_map_pixmap()`。

### `feature_params_from_widgets(*, clahe_check, deepen_check, wall_weight_spin, edge_weight_spin, gray_weight_spin, canny_low_spin, canny_high_spin) -> dict`
行为：从绘图页 feature 控件读取 recognizer 参数 dict。
算法：
1. 从 CLAHE 和颜色深化复选框读取布尔值。
2. 从墙体、边缘、灰度权重 spinbox 读取整数权重。
3. 从 Canny low/high spinbox 读取边缘阈值。
4. 返回字段名与原 `recognizer.set_params()` 契约一致的 dict。
副作用：无；只读取控件。
失败行为：控件对象缺少 `isChecked()` 或 `value()` 时向上传播 `AttributeError`。
调用关系：called by `MappingWidget.update_feature_params()`。

### `sync_recognizer_widgets(params: dict, *, clahe_check, deepen_check, wall_weight_spin, edge_weight_spin, gray_weight_spin, canny_low_spin, canny_high_spin) -> None`
行为：将已加载 recognizer 参数按旧默认值和旧顺序写回绘图页控件。
算法：
1. 用 `clahe_enabled=True`、`deepen_enabled=True` 写回复选框默认值。
2. 用 `wall_weight=50`、`edge_weight=30`、`gray_weight=20` 写回权重控件默认值。
3. 用 `edge_low=50`、`edge_high=150` 写回 Canny 阈值控件默认值。
4. 不阻断 Qt 信号，保留旧加载配置时可能触发 `update_feature_params()` 的副作用。
副作用：写入 Qt 控件状态，可能触发既有信号。
失败行为：缺少参数键时使用旧默认值；控件写入失败向上传播。
调用关系：called by `MappingWidget.load_saved_params()`。

### `apply_hsv_toggles(recognizer, wall_check, fog_check) -> None`
行为：将绘图页 HSV 开关同步到 recognizer 运行时对象。
算法：
1. 读取墙体识别复选框状态并写入 `recognizer.enable_wall`。
2. 读取迷雾识别复选框状态并写入 `recognizer.enable_fog`。
副作用：修改 recognizer 运行时字段。
失败行为：recognizer 或控件缺少对应属性/方法时向上传播异常。
调用关系：called by `MappingWidget.update_hsv_params()`。

### `collect_params_from_widgets(dialog) -> dict`
行为：从高级参数弹窗全部参数控件采集 recognizer/stitcher 参数 dict。
算法：
1. 读取预处理控件：颜色深化、对比、蓝色增强、Gamma、Tophat、CLAHE。
2. 读取特征控件：Canny 阈值、墙体/边缘/灰度权重。
3. 读取透明模式和饱和度过滤控件。
4. 若拼接器控件存在，读取 `conf_thresh/keyframe_thresh/weight_add/weight_cap`；不存在时使用旧 fallback 默认值。
5. 返回字段名与旧 `AdvancedSettingsDialog.apply_params()` 构造的 dict 一致。
副作用：无；只读取控件。
失败行为：控件不存在或类型不匹配时抛出 `AttributeError`，保持旧直接访问失败路径。
调用关系：called by `AdvancedSettingsDialog.apply_params()`。

### `load_params_to_widgets(dialog, params: dict) -> None`
行为：将当前高级参数 dict 写入弹窗控件。
算法：
1. 固定写入 `blur_strength_spin=3`，保持旧加载当前参数行为。
2. 用各字段旧默认值写入预处理、特征、透明模式、饱和度过滤控件。
3. 若拼接器控件存在，写入拼接器参数默认值。
副作用：写入 Qt 控件状态。
失败行为：缺失参数键使用旧默认值；控件写入异常向上传播。
调用关系：called by `AdvancedSettingsDialog.load_current_params()`。

### `apply_preset_to_widgets(dialog, preset: str) -> bool`
行为：根据高级参数弹窗预设名称写入对应控件值。
算法：
1. `"默认参数"` 调用 `reset_widgets_to_default()`。
2. `"流放之路优化"` 写入对比、蓝色增强、边缘阈值和权重预设。
3. `"火炬之光优化"` 写入另一组对比、蓝色增强、边缘阈值和权重预设。
4. `"高对比度模式"` / `"低对比度模式"` 只写入旧实现中的对比、蓝色增强和 CLAHE clip。
5. 未识别预设返回 `False`，调用方当前不使用返回值。
副作用：写入 Qt 控件状态。
失败行为：控件缺失时抛出 `AttributeError`。
调用关系：called by `AdvancedSettingsDialog.apply_preset()`。

### `calculate_hsv_range(hsv_values) -> tuple`
行为：根据颜色选择弹窗采样的 HSV 值计算推荐 HSV 最小/最大范围。
算法：
1. 将采样值列表转换为 numpy array。
2. 沿采样点维度计算 HSV 均值和标准差。
3. 计算容差 `maximum(std * 2, [5, 20, 20])`。
4. 用均值减/加容差得到初始范围。
5. 将范围 clamp 到 HSV 合法边界 `[0,0,0]` 和 `[179,255,255]`。
6. 返回均值、int 最小 HSV、int 最大 HSV。
副作用：无。
失败行为：空采样列表会产生 numpy warning/NaN；调用方仍在 `calculate_hsv_ranges()` 入口检查至少有采样点。
调用关系：called by `ColorPickerDialog._calculate_range()`。

### `pixmap_from_image(image, fallback_image=None) -> QPixmap`
行为：把颜色选择弹窗中的 OpenCV 图像转换为 Qt pixmap。
算法：
1. `image` 不为空时使用它，否则使用 fallback image。
2. 灰度图按 `QImage.Format_Grayscale8` 构造。
3. BGR 彩色图先转 RGB，再按 `QImage.Format_RGB888` 构造。
4. 返回 `QPixmap.fromImage(q_image)`，保持旧实现未 copy 的行为。
副作用：创建 Qt 图像对象。
失败行为：image 和 fallback 都为空或 shape 非预期时抛出异常。
调用关系：called by `ColorPickerDialog._show_image()`。

### `draw_sample_markers(pixmap: QPixmap, *, original_width: int, original_height: int, zoom: float, wall_points, player_points) -> QPixmap`
行为：在缩放后的颜色选择图像上绘制墙体/人物采样 marker。
算法：
1. 按原图宽高和 zoom 计算目标 pixmap 尺寸。
2. 使用 `Qt.KeepAspectRatio` 和 `Qt.SmoothTransformation` 缩放。
3. 计算缩放后显示宽高相对原图的 scale_x/scale_y。
4. 墙体点使用蓝色 pen/brush 绘制外圈半径 5、内点半径 2。
5. 人物点使用绿色 pen/brush 绘制同样尺寸 marker。
6. 结束 painter 并返回缩放后的 pixmap。
副作用：修改缩放后的 pixmap 副本。
失败行为：原图尺寸为 0 会除零；调用方初始化时已来自截图尺寸。
调用关系：called by `ColorPickerDialog._show_image()`。

### `EventCoordinator.observe(self, tick) -> None`
行为：运行事件检测、局部到全局定位、任务记忆和显示任务选择，但不推进任何事件 handler。
算法：
1. 全局事件配置关闭时停止/清理 active runner，清空 last action 和 selected task。
2. 调用 `EventMonitor.detect()` 在 raw minimap frame 上产生局部 `EventDetection`。
3. 调用 `EventPositionStabilizer.update()` 使用 `FrameRegistration` 将局部检测投影为稳定全局 `EventObservation`。
4. 调用 `EventMemory.merge_observations()` 合并、确认、去重和冷却任务，并把当前 tasks 写入 `tick.event_tasks`。
5. 用全部启用 active tasks 选择 `display_task`，用于 status/overlay/任务表。
副作用：更新 `last_detections/last_observations/last_selected_task`，修改 `EventMemory` 状态，并写事件日志。
失败行为：检测/定位失败时保留既有 memory；全局关闭时停止 active runner。
调用关系：called by `NavigationModeWidget._navigation_loop_unified()` before task scheduling.

### `EventCoordinator.run_task(self, task_id: str | None, tick)`
行为：只推进由统一导航调度器选中的事件任务，并返回该 handler 输出的 `EventAction`。
算法：
1. 全局事件配置关闭时停止 active runner 并返回 `None`。
2. `task_id is None` 时调用 `EventRunner.update(None, ...)`，用于清理或 requeue。
3. 在启用 active tasks 中查找指定 `task_id`。
4. 未找到时记录 `coordinator run_task missing`，并调用 runner 空更新。
5. 找到任务后调用 `_run_selected_task()`，由 `EventRunner` 启动/继续 handler 并返回 action。
副作用：更新 `last_action`、`EventRunner.active_task` 和 `EventMemory` 中的任务状态。
失败行为：任务不存在或事件关闭时返回 `None`，不会直接触发输入。
调用关系：called by `NavigationTaskController._update_event_task()`。

### `plan_path_with_optional_anchors(*, wall_map, pathfinder, start_pos, target_pos, explored_map=None, anchors=None, max_anchors: int = 48, max_anchor_factor: float = 1.8, max_anchor_branching: int = 4, min_progress: float = 24.0) -> AnchorPathResult | None`
行为：在地图全局坐标上优先按用户添加顺序构建有序锚点走廊，供普通导航和事件移动共用。
算法：
1. 将起点、目标和锚点转为整数地图点。
2. `_ordered_corridor_anchors()` 去重并保留 UI 添加顺序，把当前位置投影到锚点折线得到路线进度。
3. 把当前进度之前的锚点视为已路过；把超过当前主目标投影之后的锚点过滤掉，避免锚点抢过必经点、事件或出口。
4. 如果存在前方锚点，只规划 `当前位置 -> 下一个锚点` 的 A* 段并返回 `path_kind="anchor_step"`。
5. 如果下一个锚点 A* 暂不可达，返回两点 `anchor_probe`，让调用方先朝该锚点做约 84 像素短探测。
6. 只有无前方锚点时才直接 A* 到当前主目标并返回 `path_kind="planned"`。
7. 二者都不可用时返回 `None`。
副作用：无真实输入副作用；只调用 `PathFinder.find_path()` 做路径查询。
失败行为：没有墙图/pathfinder、直接路径和锚点路径都不存在时返回 `None`，由调用方执行局部 fallback。
调用关系：called by `MovementExecutor._plan_path()`。

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

### `derive_navigation_wall_layer(wall_layer, *, erode_iterations: int = 1, threshold: int = 50) -> np.ndarray`
行为：从原始建图墙层派生 A* 专用墙层。
算法：
1. 校验 `wall_layer` 不为空。
2. 将输入转换为 `uint8`。
3. 按 `threshold` 二值化，得到只有墙/非墙的导航源图。
4. 当 `erode_iterations > 0` 时，用 3x3 十字核腐蚀墙像素，使视觉墙体变薄、窄通道变宽。
5. 返回新的 `nav_wall` 数组。
副作用：无；不会修改传入的原始 `wall_layer`。
失败行为：`wall_layer is None` 时抛出 `ValueError`。
调用关系：called by `NavigationCore.__init__()` and `NavigationCore.rebuild_navigation_wall_layer()`。

### `NavigationTaskController.update(self, *, localized_pos, confidence: float, route: dict | None, event_coordinator, event_tick, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, manual_event_only: bool = False, frame_registration=None) -> NavigationIntent`
行为：消费当前定位、路线和事件 memory 快照，统一输出普通路线或事件动作意图。
算法：
1. 路线对象变化时重新 `load_route()` 并保持 controller active。
2. 未 active 时返回 `NONE` intent；定位为空、置信度过低或低置信大跳变时返回 `WAIT`。
3. `observe_localization()` 维护 `trusted_pos/control_pos` 和单调 `route_progress`；若本帧是强制全局模板重定位成功帧，则硬重置 `control_pos`，不做平滑。
4. `CoordinateDiagnostics.record_localization()` 和 `record_navigation_state()` 记录 raw/trusted/control/target/route deviation/frame registration；只有 `NavigationCore` 视觉校验产生的 `visual_mismatch` 或极端 `raw_jump` 会触发强制重定位，路线偏差和近目标卡住只写诊断日志。
5. 若诊断状态机产出 relocalization request，返回 `WAIT` 且在 metadata 标记 `force_relocalize=True`，本帧不点击。
6. `_update_required_progress()` 用距离或路线进度越过判断已完成必经点，完成后清路径和 active task。
7. `NavigationTaskBuilder.build()` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中 runnable 事件合成任务列表。
8. `NavigationTaskScheduler.pick()` 选择当前任务；事件 active 时持锁，静态目标不持锁，允许新事件动态抢占。
9. 任务切换时记录 `nav task transition` 并重置共享 `MovementExecutor`，避免上一任务路径/点击冷却污染下一任务。
10. static required/exit 走 `_update_static_task()`；event 走 `_update_event_task()` 并调用 `EventCoordinator.run_task()`。
11. 返回 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY/WAIT/ARRIVED/FAILED` 之一，由 GUI 层统一执行输入。
副作用：更新定位平滑状态、已完成必经点集合、active task、共享移动执行器、坐标诊断恢复状态和事件 runner 状态。
失败行为：无路径时返回 `WAIT path unavailable`，不会生成穿墙长直线点击；事件上下文缺失时返回 `WAIT`。
调用关系：called by `NavigationModeWidget._navigation_loop_unified()`。

### `MovementExecutor.step(self, *, task_id: str, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context=None, soft_anchors=None, force_repeat_click: bool = False) -> MovementStep | None`
行为：为当前 required、exit 或 event 地图目标规划/复用路径，选出本帧 lookahead 子目标和是否应点击。
算法：
1. 标准化当前位置和目标坐标。
2. `_ensure_path()` 根据目标变化、路径为空、锚点段到达、离路偏差或 fallback 过期判断是否重规划。
3. `_plan_path()` 优先从 `RouteContext.corridor_anchors()` 获取当前位置到当前任务目标之间的前方锚点。
4. 若有前方锚点，调用 `plan_path_with_optional_anchors()` 只规划到下一个锚点；若无锚点则直接 A* 到当前任务目标。
5. 如果 A* 失败，生成玩家附近短距离 `fallback` probe，而不是直接点击远端目标。
6. 将当前位置投影到当前路径，沿累计距离向前插值 `lookahead_distance` 得到 `subgoal`。
7. 冷却满足且子目标变化、首次点击、强制重复或离路偏差较大时设置 `should_click=True`。
8. 返回包含 path、subgoal、path_kind、deviation 的 `MovementStep`。
副作用：更新缓存路径、路径终点、子目标、重规划时间和 fallback probe index。
失败行为：路径不可用或投影失败返回 `None`，调用方本帧不输入。
调用关系：called by `NavigationTaskController._update_static_task()` and `_update_event_task()`。

### `NavigationTaskScheduler.pick(self, *, tasks: list[NavigationTask], player_pos, route_context, active_task_id: str | None = None, manual_event_only: bool = False) -> NavigationTask | None`
行为：在静态路线目标和动态事件目标中选择当前应处理任务。
算法：
1. 过滤出 `PENDING/MOVING/EXECUTING` 任务；手动事件测试时只保留 event。
2. 如果 active task 是 event 且仍 runnable，直接返回它，保证事件执行到终态。
3. 普通模式先找下一个未完成 required，若没有则选 exit 作为 base target。
4. 计算玩家路线进度与 base target 进度，只把位于两者之间或略靠前的 event 纳入候选。
5. 用“前方路线进度差、priority、欧氏距离、task id”排序，选择最靠近当前前进方向的任务。
6. 任务变化时写 `nav task selected` 日志。
副作用：只维护 `_last_selected_id` 以减少重复日志。
失败行为：无 runnable 任务时返回 `None`。
调用关系：called by `NavigationTaskController.update()`。

### `PathFinder._build_obstacle_map(self, wall_map, grid_w, grid_h, explored_map=None)`
行为：把调用方传入的导航障碍层转换为 A* 使用的低分辨率障碍图。
算法：
1. 将输入障碍层转为 `uint8` 并阈值化。
2. 如果 `wall_shrink_iterations > 0`，再次用 `MORPH_CROSS` 腐蚀墙像素；当前默认值为 0，避免和 `nav_wall_layer` 派生阶段重复变薄。
3. 将障碍图 resize 到 A* 网格尺寸。
4. 再阈值化得到 `binary_map`。
5. 如果传入 `explored_map`，把已探索区域 resize 到同一网格，`explored_map==0` 的网格强制设为障碍。
6. 如果 `safety_margin > 0`，按降采样后的半径膨胀障碍；当前默认 0。
副作用：无。
失败行为：输入图形状不合法时 OpenCV resize/threshold 异常向上传播。
调用关系：called by `PathFinder.find_path()`。

### `PathFinder._clear_start_area(self, obstacle_map, start_grid)`
行为：清空 A* 起点附近小圆，容忍玩家定位点压在线条/墙边。
算法：
1. 将 `start_clear_radius` 按 `downsample_factor` 转为网格半径。
2. 半径小于等于 0 时直接返回原障碍图。
3. 复制障碍图，裁剪起点附近局部窗口。
4. 在局部窗口内画圆形 mask，并把 mask 覆盖区域置为可走。
5. 返回清空后的障碍图副本。
副作用：无。
失败行为：窗口越界或空窗口时返回复制后的障碍图。
调用关系：called by `PathFinder.find_path()`。

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
1. `NavigationModeWidget._navigation_loop_unified()` 输入 `capture_rect`、屏幕截图帧和当前路线配置；输出 `localized_pos=(global_x, global_y)`；副作用是更新地图上的玩家点、绿色定位框、橙色真实可见框和事件 marker。
2. `NavigationCore.localize()` 输入实时小地图截图和 `player_pos`；输出地图全局坐标和置信度；副作用是更新 `current_pos/last_good_pos/prev_mask`。
3. `EventCoordinator.observe()` 输入 `EventTick(frame, frame_registration, player_global_pos)`；输出 memory 中的 active event tasks；副作用是检测 raw minimap 图标、稳定全局事件坐标、更新事件 overlay，但不推进 handler。
4. `NavigationTaskController.update()` 输入定位、`route["main"]`、`EventCoordinator.tasks()`、`nav_core.nav_wall_layer`、`explored_map` 和 `PathFinder`；先用 `NavigationTaskBuilder` 构造 required/exit/event 任务，再由 `NavigationTaskScheduler` 选择一个当前任务；输出 `NavigationIntent`。
5. 静态 required/exit 或事件 `MOVE_TO` 进入 `MovementExecutor.step()`；该执行器通过 `RouteContext.corridor_anchors()` 和 `plan_path_with_optional_anchors()` 优先按前方 guide 点走廊规划 `anchor_step/anchor_probe`，无前方锚点时才直接规划目标，最后输出地图子目标 `subgoal` 和 `path_kind`。
6. 事件任务被选中时，`NavigationTaskController._update_event_task()` 调用 `EventCoordinator.run_task(event_task_id, tick)` 推进 handler；`MOVE_TO` 复用第 5 步，`PRESS_KEY/CLICK_SCREEN/COMPLETE/FAIL` 转成统一 `NavigationIntent`。
7. `NavigationModeWidget._execute_navigation_intent()` 消费 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY`；`MOVE_MAP` 调用 `MotionController.move_to_map_target()`，带 `force_click_target` 时调用 `click_map_target_once()`，成功点击后回写 `NavigationTaskController.record_intent_click()` 更新点击节流状态。
8. `MotionController._execute_click()` 输入屏幕物理坐标；先用 `_apply_bottom_click_guard()` 避免落入底部 UI，再通过 `InputDriver.click()` 执行 Win32 `SetCursorPos + mouse_event`，失败时才回退 `pydirectinput.click(x, y)`。

### Flow: 导航参数保存和加载
1. `NavigationModeWidget.load_map()` 读取 `map_data/<map>/config.json`。
2. `NavConfig.from_dict()` 将 dict 转为配置对象；缺失新字段时使用默认值。
3. `NavParametersDialog.set_config_to_ui()` 将配置同步到控件。
4. 控件变化触发 `_update_config_value()`，通过 `dataclasses.replace()` 创建新配置并发出 `parameters_changed`。
5. `NavigationModeWidget._on_parameter_changed()` 保存内存态配置，立即更新 `MotionController` 的屏幕中心、移动比例、点击半径和底部禁点区，并通过 `_refresh_game_view_rect_from_known_position()` 重绘橙色框。
6. `_apply_config_to_core()` 调用 `NavigationCore.rebuild_navigation_wall_layer(nav_wall_erode_iterations)`，并把 `path_start_clear_radius`、`path_walkable_snap_radius` 写入共享 `PathFinder`。
7. 同步调用 `_configure_navigation_task_controller()`，把点击冷却、重复点击阈值、锚点到达半径、卡住判定间隔、最小进度、恢复次数和路径偏离阈值写入 `NavigationTaskController.movement`。
8. 用户保存时 `_save_nav_config()` 调用 `NavConfig.to_dict()` 写回地图配置文件，并再次刷新橙色框。
9. 用户点击“保存为默认配置”时，`_save_nav_default_config()` 调用 `save_default_nav_config(__file__, nav_config)` 合并写入项目根 `config.json`，用于没有地图配置时的默认导航参数。

### Flow: 绘图模式地图保存和根配置加载
1. 用户点击绘图页保存地图时，`MappingWidget.save_map()` 读取地图名并调用 `ensure_map_folder(__file__, map_name)` 创建 `map_data/<map_name>`。
2. `MappingWidget.save_map()` 调用 `app_context.stitcher.save_map_package(str(map_folder))` 保存地图包；`MapStitcher.save_map_package()` 会把 `wall_layer`、`explored_map`、`fog_layer`、`current_pos`、`canvas_size` 和 `draw_scale` 写入 `map_data.npz`。
3. `MappingWidget._build_mapping_config_with_ui_overrides(include_draw_scale=True)` 读取截图配置、FPS、recognizer/stitcher 参数，并叠加绘图页 `draw_scale/canvas_size/player_clear_radius/wall_close_kernel_size` 控件值；`MapStitcher.save_map_package()` 同时把 `wall_close_kernel_size` 写入 `map_data.npz` 供导航定位复现墙体模板形态学。
4. `save_map_config(map_folder, config_data)` 写入 `map_data/<map_name>/config.json`。
5. 绘图页参数变化或区域变化触发 `MappingWidget.save_config()`，它通过 `_build_mapping_config_with_ui_overrides(include_draw_scale=False)` 构造根配置并由 `save_root_config(__file__, config)` 写入项目根目录 `config.json`。
6. `MappingWidget.load_saved_params()` 启动时调用 `load_root_config(__file__)`；不存在时直接返回，存在时回填 `app_context`、Qt 控件和 recognizer/stitcher 参数；当 stitcher 仍为空地图时，几何参数会立即重建画布。

### Flow: 点击半径诊断
1. `MotionController._calculate_target_screen_position()` 记录 `raw_screen_radius` 和夹紧后的 `screen_radius`。
2. `NavigationModeWidget.navigation_loop()` 在实际点击后追加显示 `click r:<screen_radius>/raw:<raw_screen_radius>`。
3. 如果 `raw` 明显大于 `r`，说明当前点击被 `movement_max_click_radius` 限制；如果 `raw` 和 `r` 都小，说明路径子目标距离或映射比例过小。

### Flow: 事件图标探针
1. `event_icon_probe.main()` 读取 `map_data/A1/config.json`，按 DPR 将小地图逻辑中心转换为物理截图矩形；如果传入 `--image`，仍加载配置用于输出一致的诊断上下文，但跳过实时截图。
2. 实时模式下 `SquareScreenCapture.capture()` 返回 raw minimap frame；静态模式下 `cv2.imread()` 读取每个 `--image` 指定图片。两种输入都必须是未经过定位特征图后处理的事件图标层。
3. 未传 `--portal-feature-detector` 时，`event_icon_probe.probe_frame()` 对每个 `--template` 调用 `core.events.detectors.template_matcher.match_single_template()`，执行多尺度灰度+边缘匹配。
4. 传入 `--portal-feature-detector` 时，脚本调用 `core.events.types.portal.minimap_feature_matcher.build_feature_templates()` 从模板中抠出蓝色本体二值特征，再调用 `match_portal_features()` 在 raw frame 的蓝色二值图上匹配。
5. 传入 `--portal-shape-color-detector` 时，脚本调用 `core.events.types.portal.minimap_shape_color_matcher.match_portal_shape_color()`，同时输出蓝色核心、白/灰外环、组合形状 mask、debug 框图和候选裁剪。
6. `core.events.detectors.template_matcher.merge_hits()`、`minimap_feature_matcher.merge_feature_hits()` 或 `minimap_shape_color_matcher.merge_shape_color_hits()` 合并不同模板/尺度对同一图标的重复命中。
7. 脚本保存 raw/debug 图片并打印每个 accepted/rejected hit；若无 accepted hit，则打印每个模板的 best candidate、feature detector 空结果或 shape+color reject reasons，用于确认失败发生在背景模板匹配、蓝色本体特征、外环/轮廓过滤、颜色过滤还是后续事件定位层。

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
3. `EventManagerDialog.refresh()` 调用 `build_tui_event_options()` 枚举完整事件包，并从 `EventCoordinator.tasks()` 读取运行时任务；导航循环中的实时更新改走 `refresh_tasks()`，只读取运行时任务。
4. 用户勾选全局/单个事件时，dialog 更新 `EventSystemConfig` 内存态并发出 `config_changed`。
5. `NavigationModeWidget._on_event_config_changed()` 将配置写回 coordinator，清空旧事件 marker，并打印事件配置日志。
6. 用户点击“测试传送门”时，`EventManagerDialog.test_portal_requested` 触发 `NavigationModeWidget._run_portal_manual_test()`；按钮状态由 `ManualEventTestController` 同步，导航循环未运行时先启动定位循环。
7. 用户点击“刷新传送门状态”时，`EventManagerDialog.reset_portal_requested` 触发 `NavigationModeWidget._reset_portal_event_state()`；该函数停止手动 portal 测试、调用 `EventCoordinator.reset_event_type("portal")` 清空 portal 任务/聚类/冷却状态，并刷新任务表和地图 marker。
8. 导航循环定位成功后构造 `EventTick` 并调用 `EventCoordinator.observe()`；该阶段只检测 raw minimap 图标、合并 memory、把最新任务快照写入 `tick.event_tasks`、选择显示任务，不执行 handler。
9. 自动导航或手动事件测试启用时，`NavigationTaskController.update()` 从 `EventCoordinator.tasks()` 获取 pending/running event tasks，并把它们作为动态必经点和 required/exit 一起调度；手动传送门测试通过 `manual_event_only=True` 只选择事件任务。
10. 被选中的事件任务通过 `EventCoordinator.run_task(task_id, tick)` 推进 handler；handler 返回 `MOVE_TO` 时复用 `MovementExecutor.step()` 规划事件路径和 subgoal，返回 `PRESS_KEY/CLICK_SCREEN` 时直接转成 `NavigationIntent`。
11. `NavigationModeWidget._execute_navigation_intent()` 统一消费事件和普通导航的移动/点击/按键；终态事件 action 会让手动测试按钮自动停止，自动导航则从下一帧按当前位置重新调度 required/event/exit。
12. `NavigationModeWidget._render_event_overlay()` 从 `EventCoordinator.overlays()` 读取启用事件任务，在地图上绘制事件圆点和状态文本；当前 path/subgoal 复用路线 overlay 绘制。
13. 用户点击保存时，`_save_event_config()` 调用 `save_event_config()` 写入当前地图 `event_config.json`。

## 7. 外部集成详情
`main.py` Windows 启动前置条件：先配置 UTF-8 输出和 `logs/runtime.log`，随后默认立即 `FreeConsole()` 释放控制台，再设置 DPI awareness、检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", pythonw.exe, ...)` 触发 UAC 重新启动当前脚本并退出原进程。管理员进程启动后会获取基于项目路径的 Win32 mutex 单实例锁，并扫描已有 `实时小地图拼接系统` 主窗口；如果已有实例存在，新实例直接退出，防止多个 GUI 同时识别事件并向游戏发送移动/按键。默认 GUI 启动不保留控制台，诊断输出写入 `logs/runtime.log`；如需实时控制台，启动前设置 `MINIMAP_DEBUG_CONSOLE=1`，此时不会释放控制台，提权会继续使用 `python.exe` 并把输出同时写入控制台和日志文件。真实游戏输入依赖管理员完整性级别。
`logs/runtime.log` 每次进程启动都会重建，不再把旧会话定位刷屏追加到新会话后面；事件系统另有专用 `logs/event_runtime.log`，用于测试传送门时只看事件链路。

`InputDriver.click(x, y)`：由 `MotionController._execute_click()` 的 `win32_mouse_event` 后端调用，执行 `SetCursorPos(x, y)` 后用 Win32 `mouse_event` 分开发送 left-down/left-up。该路径来自旧脚本 `t2.py` 的可用实现，当前是游戏点击主后端。

`pydirectinput.click(x, y)`：仍作为 `MotionController` 的异常兜底和诊断工具保留。失败风险包括游戏窗口未聚焦、坐标在窗口外、权限/输入钩子被游戏屏蔽。

`pydirectinput.press(key)`：由 `MotionController.press_key()` 在事件 `PRESS_KEY` 动作中调用，目前主要服务传送门事件配置为按键交互时的 `D` 键。它同样依赖管理员权限和正确前台窗口。

`utils/event_icon_probe.py`：独立事件识别探针，依赖 `core.capture.SquareScreenCapture`、OpenCV 模板匹配和 portal 蓝色本体 feature matcher。真实游戏窗口下需要管理员权限才能可靠捕获 raw minimap；非管理员权限可能返回黑帧，不应误判为识别算法失败。静态 `--image` 模式不依赖截图权限，适合先验证模板资产自身是否覆盖某个用户截图外观；`--portal-feature-detector` 用于验证运行时传送门识别算法。

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
`anchor_arrival_radius: int` - 辅助锚点到达/消费半径，默认 26；只影响 guide_points 锚点推进，不改变必经点完成半径。
`movement_progress_timeout_ms: int` - 路径进度不足时触发卡住恢复的时间窗口，默认 1200ms。
`movement_min_progress_delta: float` - 卡住判定窗口内至少需要前进的路径距离，默认 12.0。
`movement_max_recover_attempts: int` - 单次路径上允许的恢复探测次数，默认 2，耗尽后强制重规划。
`movement_path_deviation_threshold: float` - 人物偏离当前规划路径多少地图像素时重规划，默认 96.0。
`bottom_click_guard_pixels: int` - 屏幕底部禁点区高度，默认 300px，设为 0 可关闭；只在点击落入底部 UI 时沿原方向缩短半径。
`nav_wall_erode_iterations: int` - 从原始 `wall_layer` 派生 A* 专用墙图时的腐蚀次数，默认 1；只影响寻路，不影响定位/事件配准。
`path_start_clear_radius: int` - A* 网格构建后清空玩家起点附近障碍的地图像素半径，默认 30。
`path_walkable_snap_radius: int` - A* 起终点落在障碍内时搜索最近可走点的地图像素半径，默认 18。
`coordinate_visual_check_interval_ms: int` - F2F 跟踪时做截图-大地图视觉一致性校验的间隔，默认 800ms；0 表示关闭自动视觉校验。
`coordinate_visual_check_margin: int` - 围绕当前导航人物位置做模板校验的搜索边距，默认 140 地图像素。
`coordinate_visual_match_min_confidence: float` - 视觉校验最佳匹配最低置信度，默认 0.72，低于该值不作为偏移证据。
`coordinate_visual_mismatch_threshold: float` - 视觉最佳贴图位置与当前导航人物点的距离阈值，默认 24 地图像素。
`coordinate_visual_mismatch_frames: int` - 连续多少次视觉校验偏移才触发强制重定位，默认 3。

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
`detector_mode: str` - 小地图传送门识别算法，支持 `template`、`feature`、`feature_then_template`、`shape_color`。默认 `feature_then_template` 保持当前行为；`shape_color` 用于实测更严格的形状+颜色联合识别。
`minimap_threshold: float` - 小地图事件识别阈值；portal 当前优先用于蓝色本体 feature score，整块模板兜底也复用该值。
`max_candidates: int` - 单帧最多接受的传送门候选数，默认 2。
`min_blue_ratio: float` - 模板 bbox 周围必须满足的蓝/青传送门像素比例，过滤白墙误匹配。
`feature_hue_min: int` / `feature_hue_max: int` - portal 本体特征 HSV hue 范围，默认 82..136。
`feature_sat_min: int` / `feature_val_min: int` - portal 本体特征 HSV 饱和度/亮度下限，默认 55/95。
`feature_min_blue_pixels: int` / `feature_max_blue_pixels: int` - portal 候选窗口内蓝色本体像素数量范围，默认 36..420；`feature_max_blue_pixels=0` 表示不设上限。
`shape_outer_sat_max: int` / `shape_outer_val_min: int` - shape_color 模式下白/灰外环 HSV 阈值。
`shape_min_blue_score: float` / `shape_min_outer_score: float` / `shape_min_shape_score: float` - shape_color 模式下蓝色核心、外环和组合形状的最低 F1-like 分数。
`shape_min_outer_pixels: int` - shape_color 模式下候选框内必须包含的最少白/灰外环像素。
`confirm_frames: int` - 需要连续/累计识别多少帧后进入 pending。
`dedupe_radius: int` - memory 合并同类事件任务的半径；A1 传送门默认 32，用于把相距约 69px 的双门拆成两个任务。
`arrival_radius: int` - 玩家距离事件点多少地图像素内开始主画面确认。
`interact_radius: int` - 玩家距离传送门地图点多少地图像素内才进入交互阶段；事件管理页下限为 1。
`portal_point_click_wait_ms: int` - 进入交互阶段后，先点击一次映射传送门点，再等待多少毫秒按 `D`。
`retry_limit: int` - 失败后的重试次数。
`cooldown_ms: int` - 完成后的同位置冷却时间。
`cooldown_radius: int` - 完成后屏蔽附近同类传送门的地图半径，防止成对传送门来回触发。
`exit_complete_radius: int` - 传送成功后，将角色新位置附近多少地图像素内的同类传送门标记为出口 completed；handler 也用它判断是否已落在另一个已知传送门附近。
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

`MotionController.click_map_target_once()` is an event-interaction helper, not normal movement guidance. It maps the target map point to screen space with `movement_scale_factor` and `movement_max_click_radius`, but deliberately does not apply `movement_min_click_radius`; if the player and target overlap, it clicks `game_screen_center`. Portal uses this for the pre-`D` mapped portal-point click when `NavigationIntent.metadata.force_click_target` is set.

`core/navigation_tasks/movement_executor.py` is the single map-space movement planner for required points, exit movement, and event `MOVE_TO`. User-defined guide points shape route intent through `RouteContext.corridor_anchors()`: current-position-before anchors are ignored, forward anchors between the player and current selected task are preserved, and movement advances by `anchor_step` or `anchor_probe` before direct target A*. Anchor path-goal arrival uses configurable `anchor_arrival_radius`; while an anchor/fallback path goal is still pending, the executor allows repeat clicks after the normal cooldown even if the subgoal barely changed, so a successful anchor plan cannot stall only because `auto_min_click_target_delta` suppressed the click. Stuck recovery now probes toward the active anchor/fallback path goal instead of the final route target, and exhausted recovery attempts set an explicit force-replan flag for the next frame. Automatic click cadence, target-delta suppression, anchor radius, stuck timeout, min progress, recover count, and deviation threshold are all exposed in the navigation parameter dialog and applied to `NavigationTaskController.movement`.

When the player is close to the current `anchor_step`/`anchor_probe` path goal but still outside `anchor_arrival_radius`, `MovementExecutor` switches from normal movement clicks to an exact path-goal click. The returned `MovementStep.force_click_target=True` is propagated through `NavigationTaskController` into `NavigationIntent.metadata`, so `NavigationModeWidget._execute_navigation_intent()` uses `MotionController.click_map_target_once()` and bypasses `movement_min_click_radius`. This prevents near-anchor map deltas such as 20-40px from being inflated into 299px screen-radius clicks that overshoot the anchor. During this final-anchor settle window, recovery probes are suppressed for about 2.2s; if the anchor is still not reached, normal stuck recovery can resume.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation_mode.py::_set_game_input_window_mode()` prevents the PySide main window from intercepting auto-navigation clicks. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

### 2026-05-20 Correction
The stable movement baseline is the original `pydirectinput.click(x, y)` call. Do not replace it with `moveTo + mouseDown + mouseUp` unless it is separately verified in the target game environment. Window focusing is optional (`focus_before_click=False` by default) because it can interfere with the already-working cursor movement path.

`NavParametersDialog.set_config_to_ui()` now uses `QSignalBlocker` while writing widget values and `_connect_signals()` is one-shot. This avoids PySide `disconnect` RuntimeWarning messages during startup/config refresh.

### 2026-05-20 Click Diagnostics
`MotionController._execute_click()` logs the requested coordinate, final coordinate, whether clamping changed it, `pydirectinput.size()`, pydirectinput cursor position before/after, Win32 cursor position before/after, target window information, foreground window information, current `ClipCursor` rectangle, focus HWND, and confirmation-click state. This is intended to separate coordinate mapping failures from Unreal/Windows mouse capture or "click reached the wrong window" failures during real-game testing.

### Event Move Repeat Click
`MovementExecutor.step(..., force_repeat_click=True)` keeps the normal 260ms click cooldown but bypasses the "subgoal must change by 8px" gate. Portal handler sets this flag only for final approach before `interact_radius`, so repeated same-subgoal clicks continue pushing the character into the exact portal point without weakening the later `D`-press distance check. The same executor state is reset on every selected task transition, preventing a previous required/event click from suppressing the next task.

### 2026-05-20 Standalone Input Probe
`utils/input_probe.py` is a standalone manual probe for testing real game input before changing `MotionController`. It supports `pydi_click_xy`, `pydi_move_click`, `pydi_hold_xy`, `setcursor_pydi_click`, `setcursor_pydi_hold`, and `setcursor_win32_click`. It is diagnostic-only unless launched with `--execute`.

### 2026-05-20 DPI/Input Coordinate Finding
Runtime probe on the user's machine showed `pydirectinput.size() == (1707, 1067)`, `GetSystemMetrics(0/1) == (1707, 1067)`, and Qt `devicePixelRatio() == 1.5`. Therefore screenshot capture can still require physical coordinates, but `MotionController` should feed `pydirectinput` input coordinates consistently. `_clamp_screen_pos()` is now disabled by default; enabling it can still rewrite targets such as `(1987, 569)` or `(1559, 1469)` to screen-edge points, so it should only be used after the coordinate system is proven.

## 11. Event Runtime Diagnostics
`core/events/debug.py` is the shared logging utility for the event system. It provides `event_log()`, `describe_action()`, and `describe_task()` so event modules print consistent `[Event HH:MM:SS.mmm pid=<pid>] ...` lines instead of ad-hoc debug strings. `event_log()` writes to both the normal runtime output and the dedicated `logs/event_runtime.log`, which is the preferred file for portal/event testing. The PID is intentionally included because multiple GUI processes can otherwise interleave event lines and make a portal bounce look like a single state-machine bug.

`EventMonitor`, `EventMemory`, `EventCoordinator`, `EventRunner`, and `NavigationTaskController` log detector initialization, observation counts, task creation/confirmation, display-task selection, navigation task selection/transition, handler start, action output, action execution, completion, failure, retry, and ignored states. Repeating frame-level logs are throttled, while click/key/complete/fail actions print immediately.

`PortalMinimapDetector`, retained `PortalMainViewConfirmer` probe assets, and `PortalEventHandler` now log the portal-specific chain: minimap template hits, task global position, movement distance to the portal, mapped portal-point click, key interaction, wait-after-interaction, teleport position/environment completion, and timeout failure. Current runtime portal flow is minimap-first and key-based: after arriving near the minimap-derived portal point it clicks that mapped point once, waits briefly, then presses `D`; main-view confirmation is not part of the active default portal loop.

`NavigationModeWidget` logs event-system initialization and unified navigation intent execution, and the status bar now appends a compact event summary from `EventCoordinator.status_summary()`, for example `event:portal running seen=3 act=move_to`. This is intended for live game testing only; it does not change event matching thresholds or navigation movement semantics. The old per-frame localization print block (`当前定位` / `位置来源` / `本帧定位位置`) is intentionally removed so portal/event operation logs remain readable in `logs/runtime.log`.

Event detection and memory updates may run while normal navigation localization is active, but handlers only advance when `NavigationTaskController` selects an event task and calls `EventCoordinator.run_task()`. This avoids a misleading state where an event task could log completion without the unified controller being allowed to move or click.

## 12. Event Manager UI
`gui/dialogs/event_manager_dialog.py` is the independent event-management surface. It is intentionally package-level: the table lists complete events such as `portal`, not the internal minimap detector, main-view confirmer, or handler. The global checkbox toggles `EventSystemConfig.enabled`; each row checkbox toggles `config.events[event_type]["enabled"]`. Selecting a row renders editable controls from the event definition schema; for portal this includes `interact_radius`, which controls how close the player must be before pressing `D` and can now be lowered to 1, plus `portal_point_click_wait_ms`, which controls the pause between the mapped portal-point click and pressing `D`. Portal recognition parameters such as `minimap_threshold`, `max_candidates`, `min_blue_ratio`, `feature_sat_min`, `feature_val_min`, and feature blue-pixel bounds are exposed here rather than being hidden constants.

The runtime task table reads from `EventCoordinator.tasks()` and shows task ID, event type, state, seen count, confidence, global map position, attempts, and last-seen timestamp. This gives live feedback when a minimap icon is detected even before auto navigation executes the event.

`NavigationModeWidget._render_event_overlay()` draws event markers directly on the navigation map from `EventCoordinator.overlays()`. Pending/observed events use orange, running events use green, and completed/ignored events use gray. Disabled event types and global disabled state are filtered by the coordinator so stale markers do not remain visible after config changes.

The save button writes only the current map's `event_config.json`. This keeps per-map event strategy separate from global code and avoids one map's event settings affecting another map.

The “测试传送门” button is not a one-off movement probe. It toggles `ManualEventTestController`, enables handler execution in the normal navigation loop, and runs the same portal `detect -> localize -> schedule -> MOVE_TO -> PRESS_KEY -> COMPLETE/FAIL` pipeline used by automatic navigation. The button text changes to “停止传送门测试” while that pipeline is active.

The “刷新传送门状态” button is a runtime-only reset for repeated portal testing. It clears current `portal` tasks, completed/ignored cooldown state, and portal localization clusters through `EventCoordinator.reset_event_type("portal")`; it does not edit the event configuration file or disable portal detection.

## 13. Portal Event Current Behavior
The current portal event is minimap-first. `PortalMinimapDetector` now exposes multiple selectable minimap recognition modes in the event manager: `template`, `feature`, `feature_then_template`, and `shape_color`. The default remains `feature_then_template`: first use the blue/cyan portal-body feature matcher in the raw minimap frame, then fall back to the older full-image gray/edge template matcher. This default was kept after the 2026-05-25 live probe showed the current portal icon scored only `0.6021` with the old full-template path at threshold `0.74`, while the feature matcher scored `0.9206` on the same frame. `shape_color` is available for user testing and was wired after static probes showed it accepted the real portal at `(54,83)` while rejecting the lower blue false-looking candidate at `(79,117)`. Every accepted hit still passes `_portal_color_check()` before becoming an `EventDetection`; the detector emits only local minimap candidates and never creates a trusted global coordinate. `feature_detector_enabled` is retained only for legacy config compatibility; new tuning should use `detector_mode`.

`NavigationCore.localize()` stores `last_frame_registration` whenever player localization succeeds. `EventCoordinator` passes local detections and that registration to `EventPositionStabilizer`, which projects each candidate with `frame_origin_global + local_minimap_pos * draw_scale`, clusters samples by event type and map distance, and emits an `EventObservation` only after `stable_frames` samples stay within `stable_variance`. `EventMemory` only creates/updates tasks from these stable global observations. The frame registration draw scale is the map-package scale, not a user-adjusted offset or stale navigation config value.

When auto navigation or manual portal test mode is enabled, `PortalEventHandler` moves the character toward the minimap-derived portal point until the player is within `arrival_radius`. The handler returns `EventAction.move_to(global_pos)`; `NavigationTaskController` converts that to a `MOVE_MAP` intent through the shared `MovementExecutor`, so portal movement uses the same A*/guide-anchor/fallback/click-throttle behavior as required points and exit movement. During the final approach where `distance > interact_radius`, the handler marks the action with `metadata.force_repeat_click=True`; `MovementExecutor.step()` then allows another real click after the normal click cooldown even if the subgoal has not changed, preventing a near-target stall such as staying 7px away from a 1px interaction radius. Once the player is within `interact_radius`, the handler first emits one forced mapped portal-point click (`metadata.force_click_target=True`), waits `portal_point_click_wait_ms`, then sends `D` through `MotionController.press_key()` and enters `wait_result`. The forced click goes through `MotionController.click_map_target_once()` so it targets the mapped portal point rather than using movement minimum radius. The schema still has an `interaction="click"` choice, but current handler behavior forces key interaction and treats main-view confirmation as a retained probe/asset path rather than the active portal flow.

After interaction, completion is not a fixed timer. The handler waits at least `post_interact_wait_ms`, then asks navigation for a full-map localization frame while it is waiting for teleport completion; this uses the same full-map template path as navigation start and bypasses normal jump rejection because a portal teleport is an expected large movement. The handler returns a teleport completion if the player has landed within `exit_complete_radius` of another active known portal task and is closer to that task than to the entry portal, if the player's global position changes by at least `teleport_min_distance`, or if the raw minimap patch around the player differs from the pre-interaction patch by at least `environment_change_threshold`. The known-exit branch is checked first because close paired portals can be far below `teleport_min_distance`. If none of these checks pass before `teleport_timeout_ms`, the task fails and may retry.

To prevent paired nearby portals from bouncing the character back, `PortalEventHandler` includes `completion_kind="teleport"`, `entry_task_id`, `entry_pos`, `exit_task_id` when a known exit task is found, `exit_pos`, and `exit_player_pos` metadata in the COMPLETE action. `EventRunner` passes that to `EventMemory.complete_teleport_session()`, which creates a `teleport_session_id`, marks the interacted portal as the entry, prefers the explicit exit task id, otherwise finds an already-known portal task near the post-teleport player position as the exit, and marks both as completed. If no exit task exists, memory creates a synthetic completed exit task at the post-teleport player position so independent-map teleports still close the session. `EventRunner` refuses to start or continue tasks that are already `completed` or `ignored`, which protects the lifecycle boundary if a caller accidentally passes a terminal task back into the runner.

Cooldown still remains as a secondary guard: `EventMemory` uses `cooldown_radius` for completed or ignored portal observations and `type_cooldown_ms` as a short global same-type cooldown. When a teleport session completes, `EventMemory.complete_teleport_session()` suppresses nearby active tasks around both entry and exit, so future minimap observations of the same portal pair are skipped rather than scheduled again. Cooldown skips are logged with the matched task, cooldown kind, remaining time, and position distance when relevant.

## 14. Event Localization Contract
`core/events/models.py::FrameRegistration` records the wall-registration result for one minimap frame: validity, confidence, global origin of the raw minimap frame, draw scale, player global position, player local minimap position, source (`f2f` or `template_match`), frame size, and debug metadata.

`core/events/models.py::EventDetection` is local-only: event type, confidence, detection time, local minimap position, source, and detector metadata. Detectors must not convert this to global map space.

`core/events/models.py::EventObservation` is stable/global: event type, confidence, observation time, global map position, optional latest local minimap position, source, sample count, variance, and stabilization metadata. `EventMemory.merge_observations()` treats this as already localized and stable.

`core/events/models.py::EventTick.event_tasks` is a runtime memory snapshot, not detector output. `build_event_tick()` leaves it empty; `EventCoordinator.observe()` fills it after `EventMemory.merge_observations()`. Handlers use this to compare against already-known tasks without importing memory or scheduler internals.

`core/events/position_stabilizer.py::EventPositionStabilizer.update()` is the shared localization stage for all future event types. It rejects detections when no valid frame registration exists, projects candidates through the same wall alignment used for player localization, clusters nearby samples, expires stale clusters, and emits stable observations only after the configured sample and variance gates pass.

## 15. Event Four-Phase Methodology
`docs/plans/2026-05-23-portal-event-case-study.md` records the project-level event methodology using `portal` as the first concrete case. Future event work should be evaluated through four phases: event recognition/localization, navigation to trigger point and triggering, event-specific execution, and event completion.

Phase 1 is already mostly shared: concrete detectors emit local `EventDetection` values, `EventPositionStabilizer` projects them through wall registration, and `EventMemory` only accepts stable `EventObservation` values. New minimap-based events should normally replace only detector assets/thresholds and event-specific config, not rewrite localization or memory.

Phase 2 is now shared through the unified navigation task layer and the event approach gate. Before an event handler is allowed to execute, `NavigationTaskController` asks `EventApproachController` to move toward the event with normal A* + guide anchors until the event enters the configured real-view box, then switch to short-lookahead A* without route anchors, stop near the event, and wait for stable frames. After the gate releases the task, handlers may still return `EventAction.move_to(global_pos)`, `PRESS_KEY`, `WAIT`, or `COMPLETE`, and `MovementExecutor` remains the shared A*, click throttling, and fallback-probe engine. The remaining coupling is that `NavigationModeWidget._navigation_loop_unified()` still wires capture/localization/UI overlay dependencies and consumes `NavigationIntent` with `MotionController`; future refactors should move more of that wiring behind navigation-mode helper modules without changing the task/controller protocol.

Phase 3 remains event-specific by design. Handlers may maintain complex state machines, but they must express side effects through `EventAction` rather than directly calling mouse/keyboard APIs. Portal is simple because triggering and execution are effectively the same: click the mapped portal point, wait briefly, then press `D`.

Phase 4 requires an explicit completion strategy per event. Portal uses a teleport completion strategy: position jump, local minimap environment change, or landing near another known portal. It then marks both entry and exit tasks completed through `EventMemory.complete_teleport_session()` to prevent bounce loops.

## 16. Structural Audit Snapshot
`gui/modes/navigation_mode.py` is still the main UI hotspot, but scheme C has removed the old split between normal navigation execution and event movement execution. It owns the navigation page UI, signal wiring, route persistence commands, map loading, event config bridge, event tick creation, capture geometry, debug overlay window updates, input-window topmost/lower behavior, calibration, click-mode state, the unified navigation loop, and final `NavigationIntent` consumption. The stable external entry remains `gui.modes.navigation_mode.NavigationModeWidget`; future refactors should keep this module as a facade/re-export while moving UI wiring into `gui/modes/navigation/*`.

After the first split, route/event QGraphics overlay item construction lives in `gui/modes/navigation/route_overlay.py` and `gui/modes/navigation/event_overlay.py`. `NavigationModeWidget` still owns when overlays refresh and still exposes the original private methods, but no longer contains the long per-item drawing loops for route and event markers.

After the second split, `gui/modes/navigation/event_adapter.py` owns event registry bootstrapping, config summary strings, default game-window lookup, `EventTick` construction, legacy event-action helper predicates, and coordinator status text. `NavigationModeWidget` still owns when to initialize the event system and when to call `EventCoordinator.observe()`, but event execution selection now lives in `NavigationTaskController` rather than UI-level helper predicates.

After the third split, `gui/modes/navigation/map_runtime.py` owns project/map path resolution, map-name listing, `NavConfig` JSON load/save, logical-to-physical center conversion, and capture geometry calculation. Saving navigation config merges into the existing map `config.json` instead of overwriting it, preserving mapping-only fields such as `stitcher_params` that are needed to keep drawing and navigation environments comparable. `NavigationModeWidget` still owns user feedback, `NavigationCore` construction, button enabling, and applying loaded config to runtime services.

After the fourth split, `gui/modes/navigation/viewport_overlay.py` owns screen overlay geometry, monitor green-rectangle geometry, and game-view orange-rectangle geometry. `NavigationModeWidget` still owns actual Qt item creation and visibility updates.

After the fifth split, `gui/modes/mapping/save_load.py` owns mapping project-root resolution, `map_data` folder creation, root/map `config.json` read/write, and mapping config dict construction. `MappingWidget` still owns dialogs, UI control synchronization, `stitcher.save_map_package()`, recognizer/stitcher parameter application, live capture, rendering orchestration, and topmost state.

After the sixth split, `gui/modes/mapping/map_renderer.py` owns BGR-to-QPixmap conversion, enhanced-map fallback unpacking, global map coloring, path polyline drawing, green viewport rectangle drawing, and current-position marker drawing. `MappingWidget` still decides when to fetch maps from stitcher and when to set Qt widgets.

After the seventh split, `gui/modes/mapping/params_adapter.py` owns feature-parameter dict construction, HSV toggle application, merge-weight application, and loaded recognizer/stitcher parameter widget sync. `MappingWidget` still decides when to apply runtime params and when to persist config, preserving old side-effect order.

`gui/modes/mapping_widget.py` remains the second GUI page hotspot. It owns capture-region selection, center-point selection, live capture, player fallback detection, recognizer/stitcher frame calls, path preview on map click, advanced settings dialog orchestration, and topmost state. The next mapping split should target capture-region/center-selection geometry or capture loop orchestration only if small checks can cover it.

Dialog hotspots are `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/nav_params_dialog.py`, and `gui/dialogs/color_picker_dialog.py`. `AdvancedSettingsDialog` combines tab construction, presets, file IO, runtime recognizer/stitcher application, and default parameter dictionaries. `NavParametersDialog` now has functional tabs for positioning recognition, recognition algorithm values, movement click mapping, path/A* controls, and map/debug controls, but still owns widget construction, field mapping, config mutation, screen-bound radius estimation, default-config save signal, and UI synchronization. `ColorPickerDialog` combines color sampling, HSV range calculation, preview rendering, marker drawing, and debug file output. These are mostly low-to-medium risk because they can be split behind unchanged dialog classes.

After the eighth split, `gui/dialogs/advanced_settings/params_adapter.py` owns advanced-settings widget-to-dict collection, current-param widget loading, default reset values, loaded-param widget sync, and preset widget writes. `AdvancedSettingsDialog` still owns tab layout, file dialogs, JSON save/load, status labels, print messages, and recognizer/stitcher application timing.

After the ninth split, `gui/dialogs/color_picker/hsv_ranges.py` owns HSV conversion/sample/range math and saturation averaging, while `gui/dialogs/color_picker/image_renderer.py` owns OpenCV-to-QPixmap conversion and sample marker drawing. `ColorPickerDialog` still owns point collection, preview mask generation, morphology, debug file output, result text, and accept/reject flow.

Core hotspots are algorithmically sensitive and should be split later. `core/stitcher_core.py` mixes registration, keyframe policy, weighted fusion, map package persistence, statistics, and display-map generation. `core/navigation_core.py` mixes map package loading, F2F tracking, template relocalization, frame-registration contract creation, and display-map rendering. `core/navigation_tasks/*` is now the shared route/event movement layer and should remain small, testable modules rather than being folded back into the UI. `core/motion_controller.py` is the input-control boundary and combines map-to-screen conversion, bottom-click guard, Win32 backend access, pydirectinput fallback, keyboard presses, and click diagnostics.

The event system has comparatively clear module boundaries: `EventCoordinator` observes detections and runs only a selected task, `EventMonitor` runs detectors, `EventPositionStabilizer` localizes detections, `EventMemory` owns task lifecycle/cooldown, `EventScheduler` selects display/event-runner work inside the event layer, and `EventRunner` owns handler lifecycle. There is no event-specific action executor now; event actions become `NavigationIntent` through `NavigationTaskController`, then the GUI consumes the same intent path used by normal route navigation.

## 17. Navigation Conflict Design Options
`docs/plans/2026-05-24-navigation-route-progress-option-b-design.md` records the rejected/intermediate option B for historical comparison. It kept normal navigation and event movement as separate executors with shared route progress, but the user selected scheme C instead, so option B is no longer the active implementation direction.

Option B's useful idea, route progress and guide-anchor consumption, was absorbed into `RouteContext`, `NavigationTaskScheduler`, `MovementExecutor`, and `core/anchor_path.py` rather than implemented as two separate executors.

`docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` records the active architecture now implemented in source: UI-level arbitration and dual executors have been replaced with a unified `NavigationTask` queue where required points, exit, and event tasks are scheduled by one `NavigationTaskController`. Shared movement behavior lives in `MovementExecutor`; old movement wrappers and their tests have been deleted.

`docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md` remains the implementation record. The current source has already passed the planned cleanup boundary: the old ordinary navigator module, old event path mover module, old event action executor module, and their dedicated ordinary-navigator test have been removed; `NavigationModeWidget.navigation_loop()` is only a compatibility wrapper that calls `_navigation_loop_unified()`.

Reusable capabilities already present: `MovementExecutor` is reusable A* + guide-anchor + fallback movement for route and event targets; `RouteContext` is reusable route progress/projection; `path_utils` is reusable route math; `core/events/detectors/template_matcher.py` is reusable template matching; `core/events/types/portal/minimap_feature_matcher.py` is a reusable pattern for small minimap icons whose stable feature is a colored body rather than full background pixels; `core/events/types/portal/minimap_shape_color_matcher.py` is a stricter reusable probe pattern for icons with colored core plus light outer-ring/shape constraints; `core/events/window_finder.py` and `core/input_driver.py` are reusable Windows input/window primitives; `NavConfig` and `EventSystemConfig` are separate runtime configuration contracts. Reusable capabilities now extracted from GUI include route overlay rendering, event overlay rendering, navigation capture geometry, navigation viewport geometry, mapping save/load config IO, mapping display rendering, mapping parameter control adapters, advanced-settings parameter mapping, color-picker HSV range math, and color-picker image marker rendering. Reusable capabilities still trapped in GUI include nav-params dialog field mapping and mapping capture-loop orchestration.

Recommended refactor order is: first split navigation GUI helpers with compatibility imports; then split mapping save/load/render helpers; then split dialog schema/helper modules; then isolate motion input backend/diagnostics; then split core navigation/stitching algorithms only after the GUI layer no longer obscures call sites.

## 18. Coordinate Drift Diagnostics
`core/navigation_tasks/coordinate_diagnostics.py` is the dedicated coordinate-mismatch diagnostic and internal relocalization trigger module. It writes file-only records to `logs/coordinate_diagnostics.log` and intentionally does not print to the console or `runtime.log`. `CoordinateDiagnostics.record_localization()` records invalid localization, low confidence, raw-position jumps, large raw-vs-control gaps, long F2F tracking, and visual coordinate mismatch evidence from `FrameRegistration.metadata`. `CoordinateDiagnostics.record_navigation_state()` still records route projection deviation, raw/control arrival disagreement, and "near target but not completed" stalls for the current required/exit/event task, but these are diagnostic-only and no longer trigger forced relocalization. Recovery scoring now has only two primary signals: `visual_mismatch` and `raw_jump`. `visual_mismatch` is produced only after `NavigationCore` locally re-matches the current minimap wall mask near the tracked position and the best visual position stays farther than `coordinate_visual_mismatch_threshold` for `coordinate_visual_mismatch_frames` checks. `raw_jump` remains an emergency trigger for extreme F2F jumps. Route deviation, near-target stall, raw-control smoothing gap, and long F2F duration never force relocalization by themselves.

`NavigationCore.localize()` now adds a lightweight visual consistency check to the F2F branch. Every `coordinate_visual_check_interval_ms`, it scales the current wall mask to map resolution, searches only a small margin around the current tracked player position, and records `visual_player`, `visual_delta`, `visual_delta_dist`, `visual_conf`, and `visual_expected_score` into the frame registration metadata. This implements the user-facing rule: if the screenshot visually belongs at point A but the navigation point is B, and that difference is stable, then relocalize. It avoids using route shape, anchor state, or A* fallback as evidence of coordinate drift.

`NavigationTaskController.update(..., frame_registration=...)` now receives `NavigationCore.last_frame_registration` from `NavigationModeWidget._navigation_loop_unified()`. The controller uses diagnostics as a navigation-internal recovery event: it returns `WAIT` with `metadata.force_relocalize=True`, resets `MovementExecutor`, and prevents movement clicks during the recovery frame. When a forced global template match succeeds, `observe_localization(..., force_snap=True)` snaps `trusted/control` to the accepted coordinate. Normal coordinate recovery clears the old active task so scheduling replans from the corrected position; portal post-interaction recovery keeps the active event task when `forced_reason="portal_wait_result"` so the same handler can mark the teleport session complete.

`NavigationCore.request_full_map_localization(reason)` is the shared full-map recovery entry point, and `request_global_relocalization(reason)` remains a compatibility alias. It clears `is_localized`, `prev_mask`, and `prev_wall_mask`; the next `localize()` call skips F2F/local search, runs the same full-map `wall_layer` template matching path used on navigation start, uses the base `confidence_threshold` instead of a stricter recovery-only threshold, bypasses normal jump rejection, and tags `FrameRegistration.metadata.forced_global=True`. `NavigationModeWidget._navigation_loop_unified()` consumes the force-relocalize intent, calls this method, logs `navigation forced global relocalization`, and returns before executing input.

`docs/plans/2026-05-24-coordinate-drift-diagnostics.md` records the current implemented relocalization strategy and the dedicated log events: `coordinate relocalization requested/forced/accepted/rejected`. Fixed global offset parameters remain prohibited.

## 19. Event Approach Stabilization
`core/navigation_tasks/event_approach.py` is the reusable navigation-layer gate for event trigger positioning. `EventApproachConfig` stores the user-tunable movement contract: `enabled`, `game_view_map_size`, `visible_margin`, `approach_lookahead`, `click_cooldown_ms`, `stop_radius`, `settle_ms`, `stable_frames`, and `max_motion_per_frame`. `EventApproachController.update()` returns an `EventApproachResult`; it never calls an event handler directly.

Execution order for an event task is now: `NavigationTaskController._update_event_task()` checks `event_approach.is_released(task.id)`; if not released, `EventApproachController.update()` either returns a movement/wait `NavigationIntent` or marks the task ready; only after ready does the controller call `event_coordinator.run_task(event_task_id, event_tick)`. This prevents `PortalEventHandler` from pressing `D` before the shared navigation layer has confirmed the event is inside the real-view box and the player has settled near it.

The approach algorithm has two movement phases. In the far phase, the target is the event global position and `MovementExecutor.step()` receives the normal `RouteContext`, so guide anchors still shape the route toward the event. When the event enters the real-view square centered on the player (`game_view_map_size / 2 + visible_margin`), the controller forces a replan, calls `MovementExecutor.step()` with `route_context=None`, a shorter `approach_lookahead`, and a per-call `click_cooldown_ms` override. This keeps the final approach wall-aware without letting old route anchors pull the player past the event.

The settle phase starts once the player is within `event_stop_radius` of either the event point or the path-derived approach point just before the event. During settling, no movement click is emitted. The gate releases only after `event_settle_ms` has elapsed and `event_stable_frames` consecutive frames stay within `event_max_motion_per_frame`. After release, the task id is recorded so the same event handler can continue through `portal_point_click`, `press D`, and `wait_result` without being blocked by the gate again. `COMPLETE`, `FAIL`, controller stop, route runtime reset, or manual event reset clear that released state.

`MovementExecutor.step()` now accepts an optional per-call `click_cooldown_ms`. This is intentionally not stored as global executor state; normal route navigation and anchor movement continue to use `NavConfig.auto_click_cooldown_ms`, while event final approach uses `NavConfig.event_approach_click_cooldown_ms`.

`gui/navigation_params.py::NavConfig` serializes the event approach parameters, and `gui/dialogs/nav_params_dialog.py` exposes them in the “事件靠近” tab. `gui/modes/navigation_mode.py::_configure_navigation_task_controller()` is the only UI bridge that copies those config values into `NavigationTaskController.event_approach`.

Expected event logs for a good portal run are `event approach far`, `event approach approach`, `event approach settling`, `event approach ready`, `event approach released`, then portal-specific logs such as `portal point click before interaction`, `portal interaction key`, and `portal teleport completed`. If the player never releases, inspect the same log fields for `visible`, `distance`, `waited_ms`, `stable_frames`, and `motion` before changing portal handler logic.
