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
core/events/path_mover.py - 事件 MOVE_TO 动作专用 A* 路径、lookahead 子目标和点击节流模块。
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
对外依赖：`NavigationCore`、`MotionController`、`AutoNavigator`、`RouteManager`、`EventCoordinator`、`EventPathMover`、`ManualEventTestController`、`navigation.event_adapter`、`navigation.route_overlay`、`navigation.event_overlay`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`guide_points` 构成可被 A* 逐段追踪的路线骨架，`required_points` 是必须按顺序完成的阶段门，状态机按路线进度判断当前应追普通点还是必经点，并通过 `target_kind` 控制覆盖层只高亮真正当前目标。加载地图时初始化事件 registry/config/coordinator；导航循环每帧通过 `navigation.event_adapter.build_event_tick()` 构造 `EventTick`，事件动作在自动导航开启或手动事件测试开启时优先于普通 auto move 执行。事件 MOVE_TO 不再在本文件内维护路径细节，而是委托 `EventPathMover`；传送门测试按钮文本/选中状态由 `ManualEventTestController` 维护。自动导航开启时会持续运行事件 handler；事件 `MOVE_TO/WAIT/PRESS_KEY/CLICK_SCREEN/COMPLETE/FAIL` 占用当前帧，普通路线导航从下一帧恢复，避免传送门完成帧同时推进主路线。事件管理窗口可见时，导航循环只调用 `EventManagerDialog.refresh_tasks()` 更新任务表，完整 `refresh()` 留给手动刷新、上下文切换和配置变化。路线 overlay 与事件 overlay 的 QGraphicsItem 创建/清理由 `gui/modes/navigation/route_overlay.py` 和 `event_overlay.py` 承担，`NavigationModeWidget` 保留原 `_render_*`/`_clear_*` 方法作为兼容委托入口。事件 registry 默认创建、配置摘要、窗口查找、action 接管判定和事件状态文案由 `event_adapter.py` 承担。本文件不再打印每帧“当前位置/位置来源”调试块，事件操作过程应走 `event_log()`。
### `gui/modes/navigation/event_adapter.py`
职责：封装导航模式和事件系统之间的轻量桥接，不推进事件状态机。
关键导出：`create_default_event_registry`、`event_config_summary`、`find_default_game_window_rect`、`build_event_tick`、`should_event_action_take_control`、`is_terminal_event_action`、`event_status_text`。
对外依赖：`core.events.models.EventTick/EventActionType`、`core.events.registry.EventRegistry`、`core.events.types.portal.PortalEventDefinition`、`core.events.window_finder.find_game_window`。
注意事项：该模块只组装事件系统需要的输入或判断 action 类型；`EventCoordinator.update()`、handler 生命周期和真实输入执行仍由原有模块/页面调用方负责。
### `gui/modes/navigation/event_overlay.py`
职责：封装导航地图事件 marker 的 QGraphics 绘制和清理。
关键导出：`clear_event_overlay`、`global_to_scene`、`render_event_overlay`。
对外依赖：无内部业务模块依赖；只接收调用方传入的 `scene/nav_core/event_coordinator/items`。
注意事项：该模块只移动原 `NavigationModeWidget` 中的绘制细节，不决定事件启用、调度或状态；事件过滤仍由 `EventCoordinator.overlays()` 完成。
### `gui/modes/navigation/map_runtime.py`
职责：封装导航模式地图目录解析、地图列表读取、导航配置读写和截图几何计算。
关键导出：`MISSING_MAP_DATA_LABEL`、`project_root_from_file`、`map_data_dir`、`list_map_names`、`resolve_map_folder`、`load_nav_config`、`save_nav_config`、`physical_center_from_logical`、`build_capture_geometry`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：该模块不弹窗、不改按钮、不初始化 `NavigationCore`；调用方仍负责 UI 状态和异常提示。`build_capture_geometry()` 保留旧契约：显式 `monitor_region` 返回矩形且 player_pos 为 `None`，中心点模式返回正方形截图矩形和截图中心 player_pos。
### `gui/modes/navigation/route_overlay.py`
职责：封装导航路线 overlay 的 QGraphics 绘制，包括出口、必经点、途经点、当前路径和 subgoal。
关键导出：`clear_route_overlay`、`render_route_overlay`。
对外依赖：`gui.modes.navigation.event_overlay.global_to_scene`。
注意事项：该模块只渲染调用方传入的 `route_data/current_path/current_subgoal/current_*_index/current_target_kind`，不读取或写入 `route.json`，不推进自动导航状态机。
### `gui/modes/navigation/viewport_overlay.py`
职责：封装导航相关矩形几何计算，避免页面主类直接维护屏幕幕布/监控框/真实主画面框公式。
关键导出：`screen_overlay_geometry`、`monitor_scene_rect`、`game_view_scene_rect`。
对外依赖：无内部业务模块依赖；只使用传入的 `capture_rect/nav_config/nav_core/player_pos/player_local_pos`。
注意事项：该模块只返回矩形数据，不创建/删除 Qt item，不决定 overlay 是否显示；主类仍负责 `OverlayWindow` 和 QGraphicsRectItem 的 hide/show。

### `gui/modes/mapping_widget.py`
职责：绘图模式主界面，仍负责控件组合、区域/中心选择、实时截图建图、调用地图显示 helper、路径点击入口、参数控件同步和状态栏更新。
关键导出：`MappingWidget`。
对外依赖：`TransparentOverlay`、`CenterPointSelector`、`ColorPickerDialog`、`ScalableMapWidget`、`CollapsibleMapGroup`、`AdvancedSettingsDialog`、`gui.modes.mapping.save_load`、`gui.modes.mapping.map_renderer`、`gui.modes.mapping.params_adapter`。
注意事项：`save_map()`、`save_config()`、`load_saved_params()` 作为外部兼容入口保留，但路径解析、目录创建、JSON 读写和配置 dict 构造已委托 `mapping/save_load.py`。`update_displays()` 和 `_show_image()` 入口保留，但图像转换、全局地图着色、路径线、视野框和当前位置圆点绘制已委托 `mapping/map_renderer.py`。HSV/feature/merge 参数控件读取和已加载参数回填已委托 `mapping/params_adapter.py`；本类仍决定何时调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`，以保持原副作用顺序。

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
关键导出：`FrameRegistration`、`EventTick`、`EventDetection`、`EventObservation`、`EventTask`、`EventAction`、`EventCoordinator`、`EventRegistry`、`EventSystemConfig`、`EventActionExecutor`、`EventPathMover`。
对外依赖：标准库；视觉工具依赖 OpenCV/NumPy。
注意事项：事件 handler 不直接操作鼠标键盘，只返回 `EventAction`；TUI/配置层只能看到 `EventDefinition` 级完整事件，例如 `portal`。`EventPositionStabilizer` 会按同一帧隔离聚类，避免一帧内两个相近事件图标被合并成一个跳动 marker；`EventMemory.merge_observations()` 还会避免同一帧多个 observation 复用同一个刚更新的 task，近距离双传送门依赖 `dedupe_radius` 小于两门间距来稳定显示两个 marker。`EventCoordinator.update()` 会在合并本帧 observation 之后把 `tick.event_tasks` 更新为当前 memory 快照，供 handler 在同一帧判断“另一个已知事件任务”。
`EventCoordinator.reset_event_type(event_type, now_ms)` 是事件管理 UI 的运行时重置入口；它清理同类型 active handler、memory tasks、position clusters、last detections/observations 和 selected task，不改 `event_config.json`，用于同一地图反复识别/执行某类事件。

### `core/events/path_mover.py`
职责：为事件动作中的地图坐标 `MOVE_TO` 提供可复用移动路径规划，不让传送门或未来事件各自复制 A*、lookahead 和点击节流逻辑。
关键导出：`EventMoveStep`、`EventPathMover`。
对外依赖：`core.path_utils`、`core.events.debug.event_log`。
注意事项：输入和输出均为全局地图坐标；它不执行鼠标点击，只返回 `subgoal/should_click/path_kind`，真正点击仍由 `MotionController.move_to_map_target()` 完成。A* 失败时只生成玩家附近短距离 `fallback` probe，避免事件为了靠近目标直接拉长直线穿墙。

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
4. 绘制出口橙色圆、必经点紫色/灰色 marker、途经点青色/灰色 marker，并按当前 target kind 加粗当前目标。
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
5. 后续每帧由 `navigation_loop()` 调用 `EventCoordinator.update(..., run_handlers=True)`，而不是在按钮槽函数中执行一次点击。
副作用：可启动导航循环、启用游戏输入、更新按钮/状态栏并记录事件日志。
失败行为：先决条件缺失时只警告并保持测试未启动。
调用关系：called by `EventManagerDialog.test_portal_requested` signal。

### `build_event_tick(*, now_ms, frame, player_pos, localized_pos, confidence, nav_core, nav_config, map_name: str, capture_provider) -> EventTick`
行为：把导航循环当前帧状态包装成事件系统统一输入。
算法：
1. 接收导航循环已捕获的 raw minimap frame、玩家局部坐标、定位结果和置信度。
2. 从 `nav_core.draw_scale` 读取当前地图缩放；`nav_core` 不存在时回退 `nav_config.draw_scale`。
3. 从 `nav_core.last_frame_registration` 读取当前帧墙体配准契约；`nav_core` 不存在时为 `None`。
4. 组装 `EventTick`，保留 `capture_provider` 供事件 handler 需要主画面截图时使用；`event_tasks` 初始为空，进入 `EventCoordinator.update()` 后由 coordinator 写入当前 memory 任务快照。
副作用：无。
失败行为：不验证图像或定位是否有效；由 `EventCoordinator` 和后续模块按字段值决定是否运行。
调用关系：called by `NavigationModeWidget._build_event_tick()`。

### `should_event_action_take_control(event_action) -> bool`
行为：判断事件 action 是否应优先于普通自动导航移动。
算法：
1. 空 action 返回 `False`。
2. `MOVE_TO`、`CLICK_SCREEN`、`PRESS_KEY`、`WAIT` 返回 `True`，表示事件正在接管本帧行为。
3. `COMPLETE`/`FAIL` 不在此函数中视为接管动作；它们由调用方单独处理手动测试停止。
副作用：无。
失败行为：未知 action type 返回 `False`。
调用关系：called by `NavigationModeWidget._should_event_action_take_control()`。

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

### `NavigationModeWidget._execute_event_move_to(self, target_global_pos)`
行为：消费事件 handler 返回的地图目标点，通过可复用路径移动器执行靠近事件的移动点击。
算法：
1. 校验当前定位位置与目标；不可用时重置 `EventPathMover` 并返回。
2. 打开游戏输入模式和运动控制，并传入当前墙图、探索图、`PathFinder`、时间戳和 lookahead 距离调用 `EventPathMover.step()`。
3. 若没有可用移动步或未达到点击节流条件，保持现有 path/subgoal 供 overlay 显示但不点击。
4. 若应点击，调用 `MotionController.move_to_map_target(current_pos, subgoal)` 映射为真实游戏输入。
5. 只有点击实际返回诊断信息后，调用 `EventPathMover.record_click()` 更新时间和写入事件操作日志。
副作用：可能触发真实鼠标点击；更新事件 path overlay 和日志状态。
失败行为：未定位、无路径、A*/投影暂不可用时不发鼠标输入，下一帧可继续重规划。
调用关系：called by `EventActionExecutor.execute()` through its MOVE_TO callback。

### `EventPathMover.step(self, *, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float) -> EventMoveStep | None`
行为：为事件目标计算或复用地图路径，选出下一次真实点击应追踪的前方子目标。
算法：
1. 将当前位置和事件目标标准化为浮点全局地图坐标。
2. 调用 `_ensure_path()`，按目标变化、离路偏差或 fallback 重试时间决定是否重新规划。
3. 若无法获得至少两个点的路径，记录 `event move path unavailable` 并返回 `None`。
4. 将玩家位置投影到当前路径；投影失败时强制下一帧重规划并返回 `None`。
5. 沿路径累计距离向前插值 `lookahead_distance` 得到 `subgoal`，超过路径终点时使用终点。
6. 用距上次点击至少 260ms、子目标变化至少 8 像素或离路偏差至少 48 像素作为点击节流条件。
7. 返回包含 `path/subgoal/path_kind/should_click/deviation` 的 `EventMoveStep`。
副作用：可更新缓存路径、子目标和重规划时间，并写入事件规划日志。
失败行为：A* 失败不直接失败；`_plan_path()` 降级为短距离 fallback probe。
调用关系：called by `NavigationModeWidget._execute_event_move_to()`。

### `EventPathMover._plan_path(self, current_pos, target_pos, wall_map, pathfinder, explored_map)`
行为：优先 A*，失败时为事件移动生成短距离脱困路径。
算法：
1. 将当前位置与目标四舍五入为 `PathFinder` 使用的整数地图点。
2. 若存在墙图和 pathfinder，则以 `explored_map` 约束调用 `find_path()`。
3. 若 A* 返回路径，删除共线冗余点；单点路径补入真实目标点；计算累计长度并标记 `planned`。
4. 若 A* 无结果，调用 `_local_probe()` 只向目标方向前进最多 84 像素，并按失败次数交替加入左右 44 像素侧向偏移。
5. 返回两点 fallback 路径及累计长度，标记 `fallback`，等待后续重规划。
副作用：fallback 会推进 `probe_index` 以切换探测方向。
失败行为：A* 无路时不会生成直达事件点的长直线点击。
调用关系：called by `EventPathMover._ensure_path()`。

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

### Flow: 绘图模式地图保存和根配置加载
1. 用户点击绘图页保存地图时，`MappingWidget.save_map()` 读取地图名并调用 `ensure_map_folder(__file__, map_name)` 创建 `map_data/<map_name>`。
2. `MappingWidget.save_map()` 调用 `app_context.stitcher.save_map_package(str(map_folder))` 保存地图包，保持原 `MapStitcher` 持久化路径。
3. `build_mapping_config(app_context, fps, include_draw_scale=True)` 读取截图配置、FPS、recognizer 参数、stitcher 参数和 draw_scale。
4. `save_map_config(map_folder, config_data)` 写入 `map_data/<map_name>/config.json`。
5. 绘图页参数变化或区域变化触发 `MappingWidget.save_config()`，它通过 `build_mapping_config(..., include_draw_scale=False)` 构造根配置并由 `save_root_config(__file__, config)` 写入项目根目录 `config.json`。
6. `MappingWidget.load_saved_params()` 启动时调用 `load_root_config(__file__)`；不存在时直接返回，存在时回填 `app_context`、Qt 控件和 recognizer/stitcher 参数。

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
3. `EventManagerDialog.refresh()` 调用 `build_tui_event_options()` 枚举完整事件包，并从 `EventCoordinator.tasks()` 读取运行时任务；导航循环中的实时更新改走 `refresh_tasks()`，只读取运行时任务。
4. 用户勾选全局/单个事件时，dialog 更新 `EventSystemConfig` 内存态并发出 `config_changed`。
5. `NavigationModeWidget._on_event_config_changed()` 将配置写回 coordinator，清空旧事件 marker，并打印事件配置日志。
6. 用户点击“测试传送门”时，`EventManagerDialog.test_portal_requested` 触发 `NavigationModeWidget._run_portal_manual_test()`；按钮状态由 `ManualEventTestController` 同步，导航循环未运行时先启动定位循环。
7. 用户点击“刷新传送门状态”时，`EventManagerDialog.reset_portal_requested` 触发 `NavigationModeWidget._reset_portal_event_state()`；该函数停止手动 portal 测试、调用 `EventCoordinator.reset_event_type("portal")` 清空 portal 任务/聚类/冷却状态，并刷新任务表和地图 marker。
8. 导航循环定位成功后构造 `EventTick`，`EventCoordinator.update()` 检测 raw minimap 图标、合并 memory、把最新任务快照写入 `tick.event_tasks`、选择任务；自动导航开启或手动事件测试开启时推进 handler。
9. 事件 handler 返回 `MOVE_TO` 时，`EventActionExecutor` 调用 `NavigationModeWidget._execute_event_move_to()`；该函数委托 `EventPathMover.step()` 规划事件路径和 subgoal，再由 `MotionController.move_to_map_target()` 真实点击。
10. 事件 handler 返回 `COMPLETE/FAIL` 时，导航循环仍由 `EventActionExecutor` 消费终态 action，清理 event path overlay；若是手动传送门测试则自动停止测试按钮，若是自动导航则普通路线从下一帧继续。
11. `NavigationModeWidget._render_event_overlay()` 从 `EventCoordinator.overlays()` 读取启用事件任务，在地图上绘制事件圆点和状态文本；事件 path/subgoal 也会复用路线 overlay 绘制。
12. 用户点击保存时，`_save_event_config()` 调用 `save_event_config()` 写入当前地图 `event_config.json`。

## 7. 外部集成详情
`main.py` Windows 启动前置条件：先配置 UTF-8 输出和 `logs/runtime.log`，随后默认立即 `FreeConsole()` 释放控制台，再设置 DPI awareness、检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", pythonw.exe, ...)` 触发 UAC 重新启动当前脚本并退出原进程。管理员进程启动后会获取基于项目路径的 Win32 mutex 单实例锁，并扫描已有 `实时小地图拼接系统` 主窗口；如果已有实例存在，新实例直接退出，防止多个 GUI 同时识别事件并向游戏发送移动/按键。默认 GUI 启动不保留控制台，诊断输出写入 `logs/runtime.log`；如需实时控制台，启动前设置 `MINIMAP_DEBUG_CONSOLE=1`，此时不会释放控制台，提权会继续使用 `python.exe` 并把输出同时写入控制台和日志文件。真实游戏输入依赖管理员完整性级别。
`logs/runtime.log` 每次进程启动都会重建，不再把旧会话定位刷屏追加到新会话后面；事件系统另有专用 `logs/event_runtime.log`，用于测试传送门时只看事件链路。

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

`MotionController.click_map_target_once()` is an event-interaction helper, not normal movement guidance. It maps the target map point to screen space with `movement_scale_factor` and `movement_max_click_radius`, but deliberately does not apply `movement_min_click_radius`; if the player and target overlap, it clicks `game_screen_center`. Portal uses this for the pre-`D` mapped portal-point click.

`core/auto_navigator.py` now defaults back to planning-first guidance. User-defined guide points and exit region still define major route intent, but each segment is planned with `PathFinder` on a thinned wall map constrained by `explored_map`. Direct full-segment guidance is retained only as explicit `prefer_direct_guidance=True`; A* failure uses a short local fallback probe near the player and then re-plans. Default automatic click cadence is `auto_click_cooldown_ms=260` and `auto_min_click_target_delta=8.0`, both exposed in the navigation parameter dialog.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation_mode.py::_set_game_input_window_mode()` prevents the PySide main window from intercepting auto-navigation clicks. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

### 2026-05-20 Correction
The stable movement baseline is the original `pydirectinput.click(x, y)` call. Do not replace it with `moveTo + mouseDown + mouseUp` unless it is separately verified in the target game environment. Window focusing is optional (`focus_before_click=False` by default) because it can interfere with the already-working cursor movement path.

`NavParametersDialog.set_config_to_ui()` now uses `QSignalBlocker` while writing widget values and `_connect_signals()` is one-shot. This avoids PySide `disconnect` RuntimeWarning messages during startup/config refresh.

### 2026-05-20 Click Diagnostics
`MotionController._execute_click()` logs the requested coordinate, final coordinate, whether clamping changed it, `pydirectinput.size()`, pydirectinput cursor position before/after, Win32 cursor position before/after, target window information, foreground window information, current `ClipCursor` rectangle, focus HWND, and confirmation-click state. This is intended to separate coordinate mapping failures from Unreal/Windows mouse capture or "click reached the wrong window" failures during real-game testing.

### Event Move Repeat Click
`EventPathMover.step(..., force_repeat_click=True)` keeps the normal 260ms click cooldown but bypasses the "subgoal must change by 8px" gate. Portal uses it only for final approach before `interact_radius`, so repeated same-subgoal clicks continue pushing the character into the exact portal point without weakening the later `D`-press distance check.

### 2026-05-20 Standalone Input Probe
`utils/input_probe.py` is a standalone manual probe for testing real game input before changing `MotionController`. It supports `pydi_click_xy`, `pydi_move_click`, `pydi_hold_xy`, `setcursor_pydi_click`, `setcursor_pydi_hold`, and `setcursor_win32_click`. It is diagnostic-only unless launched with `--execute`.

### 2026-05-20 DPI/Input Coordinate Finding
Runtime probe on the user's machine showed `pydirectinput.size() == (1707, 1067)`, `GetSystemMetrics(0/1) == (1707, 1067)`, and Qt `devicePixelRatio() == 1.5`. Therefore screenshot capture can still require physical coordinates, but `MotionController` should feed `pydirectinput` input coordinates consistently. `_clamp_screen_pos()` is now disabled by default; enabling it can still rewrite targets such as `(1987, 569)` or `(1559, 1469)` to screen-edge points, so it should only be used after the coordinate system is proven.

## 11. Event Runtime Diagnostics
`core/events/debug.py` is the shared logging utility for the event system. It provides `event_log()`, `describe_action()`, and `describe_task()` so event modules print consistent `[Event HH:MM:SS.mmm pid=<pid>] ...` lines instead of ad-hoc debug strings. `event_log()` writes to both the normal runtime output and the dedicated `logs/event_runtime.log`, which is the preferred file for portal/event testing. The PID is intentionally included because multiple GUI processes can otherwise interleave event lines and make a portal bounce look like a single state-machine bug.

`EventMonitor`, `EventMemory`, `EventCoordinator`, `EventRunner`, and `EventActionExecutor` now log detector initialization, observation counts, task creation/confirmation, scheduler selection, handler start, action output, action execution, completion, failure, retry, and ignored states. Repeating frame-level logs are throttled, while click/key/complete/fail actions print immediately.

`PortalMinimapDetector`, `PortalMainViewConfirmer`, and `PortalEventHandler` now log the portal-specific chain: minimap template hits, task global position, movement distance to the portal, key/click interaction, wait-after-interaction, teleport position/environment completion, and timeout failure. Main-view confirmation only runs when `interaction="click"`; default `interaction="key"` goes directly to pressing `D` after arriving near the minimap-derived portal point.

`NavigationModeWidget` logs event-system initialization and event movement/click callbacks, and the status bar now appends a compact event summary from `EventCoordinator.status_summary()`, for example `event:portal running seen=3 act=move_to`. This is intended for live game testing only; it does not change event matching thresholds or navigation movement semantics. The old per-frame localization print block (`当前定位` / `位置来源` / `本帧定位位置`) is intentionally removed so portal/event operation logs remain readable in `logs/runtime.log`.

Event detection and memory updates may run while normal navigation localization is active, but `EventCoordinator.update(..., run_handlers=False)` prevents handlers from advancing unless auto navigation or manual event test mode is enabled. This avoids a misleading state where an event task could log completion without the executor being allowed to move or click.

## 12. Event Manager UI
`gui/dialogs/event_manager_dialog.py` is the independent event-management surface. It is intentionally package-level: the table lists complete events such as `portal`, not the internal minimap detector, main-view confirmer, or handler. The global checkbox toggles `EventSystemConfig.enabled`; each row checkbox toggles `config.events[event_type]["enabled"]`. Selecting a row renders editable controls from the event definition schema; for portal this includes `interact_radius`, which controls how close the player must be before pressing `D` and can now be lowered to 1, plus `portal_point_click_wait_ms`, which controls the pause between the mapped portal-point click and pressing `D`.

The runtime task table reads from `EventCoordinator.tasks()` and shows task ID, event type, state, seen count, confidence, global map position, attempts, and last-seen timestamp. This gives live feedback when a minimap icon is detected even before auto navigation executes the event.

`NavigationModeWidget._render_event_overlay()` draws event markers directly on the navigation map from `EventCoordinator.overlays()`. Pending/observed events use orange, running events use green, and completed/ignored events use gray. Disabled event types and global disabled state are filtered by the coordinator so stale markers do not remain visible after config changes.

The save button writes only the current map's `event_config.json`. This keeps per-map event strategy separate from global code and avoids one map's event settings affecting another map.

The “测试传送门” button is not a one-off movement probe. It toggles `ManualEventTestController`, enables handler execution in the normal navigation loop, and runs the same portal `detect -> localize -> schedule -> MOVE_TO -> PRESS_KEY -> COMPLETE/FAIL` pipeline used by automatic navigation. The button text changes to “停止传送门测试” while that pipeline is active.

The “刷新传送门状态” button is a runtime-only reset for repeated portal testing. It clears current `portal` tasks, completed/ignored cooldown state, and portal localization clusters through `EventCoordinator.reset_event_type("portal")`; it does not edit the event configuration file or disable portal detection.

## 13. Portal Event Current Behavior
The current portal event is minimap-first. `PortalMinimapDetector` detects the portal icon in the raw minimap frame with multi-template/multi-scale matching, then rejects a hit unless the matched patch contains enough blue/cyan portal-icon pixels. The detector now emits only `EventDetection` local minimap candidates; it never creates a trusted global coordinate.

`NavigationCore.localize()` stores `last_frame_registration` whenever player localization succeeds. `EventCoordinator` passes local detections and that registration to `EventPositionStabilizer`, which projects each candidate with `frame_origin_global + local_minimap_pos * draw_scale`, clusters samples by event type and map distance, and emits an `EventObservation` only after `stable_frames` samples stay within `stable_variance`. `EventMemory` only creates/updates tasks from these stable global observations.

When auto navigation or manual portal test mode is enabled, `PortalEventHandler` moves the character toward the minimap-derived portal point until the player is within `arrival_radius`. `MOVE_TO` is executed through `EventPathMover`, which uses A* where available and short local fallback probes instead of direct long-line clicks. During the final approach where `distance > interact_radius`, the handler marks the action with `metadata.force_repeat_click=True`; `EventPathMover.step()` then allows another real click after the normal click cooldown even if the subgoal has not changed, preventing a near-target stall such as staying 7px away from a 1px interaction radius. Once the player is within `interact_radius`, the handler first emits one forced mapped portal-point click (`metadata.force_click_target=True`), waits `portal_point_click_wait_ms`, then sends `D` through `MotionController.press_key()` and enters `wait_result`. The forced click goes through `MotionController.click_map_target_once()` so it targets the mapped portal point rather than using movement minimum radius. With `interaction="click"`, it uses `PortalMainViewConfirmer` to find the blue/purple portal entity in the game window and clicks its screen center.

After interaction, completion is not a fixed timer. The handler waits at least `post_interact_wait_ms`, then returns a teleport completion if the player's global position changes by at least `teleport_min_distance`, if the raw minimap patch around the player differs from the pre-interaction patch by at least `environment_change_threshold`, or if the player has landed within `exit_complete_radius` of another active known portal task and is clearly closer to that task than to the entry portal. The last branch is required for close paired portals where the real teleport distance can be far below `teleport_min_distance`. If none of these checks pass before `teleport_timeout_ms`, the task fails and may retry.

To prevent paired nearby portals from bouncing the character back, `PortalEventHandler` includes `completion_kind="teleport"`, `entry_task_id`, `entry_pos`, and `exit_pos` metadata in the COMPLETE action. `EventRunner` passes that to `EventMemory.complete_teleport_session()`, which creates a `teleport_session_id`, marks the interacted portal as the entry, finds an already-known portal task near the post-teleport player position as the exit, and marks both as completed. If no exit task exists, memory creates a synthetic completed exit task at the post-teleport player position so independent-map teleports still close the session. `EventRunner` refuses to start or continue tasks that are already `completed` or `ignored`, which protects the lifecycle boundary if a caller accidentally passes a terminal task back into the runner.

Cooldown still remains as a secondary guard: `EventMemory` uses `cooldown_radius` for completed or ignored portal observations and `type_cooldown_ms` as a short global same-type cooldown. When a teleport session completes, `EventMemory.complete_teleport_session()` suppresses nearby active tasks around both entry and exit, so future minimap observations of the same portal pair are skipped rather than scheduled again. Cooldown skips are logged with the matched task, cooldown kind, remaining time, and position distance when relevant.

## 14. Event Localization Contract
`core/events/models.py::FrameRegistration` records the wall-registration result for one minimap frame: validity, confidence, global origin of the raw minimap frame, draw scale, player global position, player local minimap position, source (`f2f` or `template_match`), frame size, and debug metadata.

`core/events/models.py::EventDetection` is local-only: event type, confidence, detection time, local minimap position, source, and detector metadata. Detectors must not convert this to global map space.

`core/events/models.py::EventObservation` is stable/global: event type, confidence, observation time, global map position, optional latest local minimap position, source, sample count, variance, and stabilization metadata. `EventMemory.merge_observations()` treats this as already localized and stable.

`core/events/models.py::EventTick.event_tasks` is a runtime memory snapshot, not detector output. `build_event_tick()` leaves it empty; `EventCoordinator.update()` fills it after `EventMemory.merge_observations()`. Handlers use this to compare against already-known tasks without importing memory or scheduler internals.

`core/events/position_stabilizer.py::EventPositionStabilizer.update()` is the shared localization stage for all future event types. It rejects detections when no valid frame registration exists, projects candidates through the same wall alignment used for player localization, clusters nearby samples, expires stale clusters, and emits stable observations only after the configured sample and variance gates pass.

## 15. Structural Audit Snapshot
`gui/modes/navigation_mode.py` is the current highest-risk responsibility hotspot. It owns the navigation page UI, signal wiring, route persistence commands, route overlay drawing, event overlay drawing, map loading, event config bridge, event tick creation, event action callbacks, capture geometry, debug overlay window updates, input-window topmost/lower behavior, calibration, click-mode state, and the navigation loop. The stable external entry remains `gui.modes.navigation_mode.NavigationModeWidget`; refactors should keep this module as a facade/re-export while moving behavior into `gui/modes/navigation/*`.

After the first split, route/event QGraphics overlay item construction lives in `gui/modes/navigation/route_overlay.py` and `gui/modes/navigation/event_overlay.py`. `NavigationModeWidget` still owns when overlays refresh and still exposes the original private methods, but no longer contains the long per-item drawing loops for route and event markers.

After the second split, `gui/modes/navigation/event_adapter.py` owns event registry bootstrapping, config summary strings, default game-window lookup, `EventTick` construction, event-action control checks, terminal event-action checks, and coordinator status text. `NavigationModeWidget` still owns when to initialize the event system, when to call coordinator updates, and how to respond with UI/input side effects.

After the third split, `gui/modes/navigation/map_runtime.py` owns project/map path resolution, map-name listing, `NavConfig` JSON load/save, logical-to-physical center conversion, and capture geometry calculation. `NavigationModeWidget` still owns user feedback, `NavigationCore` construction, button enabling, and applying loaded config to runtime services.

After the fourth split, `gui/modes/navigation/viewport_overlay.py` owns screen overlay geometry, monitor green-rectangle geometry, and game-view orange-rectangle geometry. `NavigationModeWidget` still owns actual Qt item creation and visibility updates.

After the fifth split, `gui/modes/mapping/save_load.py` owns mapping project-root resolution, `map_data` folder creation, root/map `config.json` read/write, and mapping config dict construction. `MappingWidget` still owns dialogs, UI control synchronization, `stitcher.save_map_package()`, recognizer/stitcher parameter application, live capture, rendering orchestration, and topmost state.

After the sixth split, `gui/modes/mapping/map_renderer.py` owns BGR-to-QPixmap conversion, enhanced-map fallback unpacking, global map coloring, path polyline drawing, green viewport rectangle drawing, and current-position marker drawing. `MappingWidget` still decides when to fetch maps from stitcher and when to set Qt widgets.

After the seventh split, `gui/modes/mapping/params_adapter.py` owns feature-parameter dict construction, HSV toggle application, merge-weight application, and loaded recognizer/stitcher parameter widget sync. `MappingWidget` still decides when to apply runtime params and when to persist config, preserving old side-effect order.

`gui/modes/mapping_widget.py` remains the second GUI page hotspot. It owns capture-region selection, center-point selection, live capture, player fallback detection, recognizer/stitcher frame calls, path preview on map click, advanced settings dialog orchestration, and topmost state. The next mapping split should target capture-region/center-selection geometry or capture loop orchestration only if small checks can cover it.

Dialog hotspots are `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/nav_params_dialog.py`, and `gui/dialogs/color_picker_dialog.py`. `AdvancedSettingsDialog` combines tab construction, presets, file IO, runtime recognizer/stitcher application, and default parameter dictionaries. `NavParametersDialog` combines large widget construction, field mapping, config mutation, screen-bound radius estimation, and UI synchronization. `ColorPickerDialog` combines color sampling, HSV range calculation, preview rendering, marker drawing, and debug file output. These are mostly low-to-medium risk because they can be split behind unchanged dialog classes.

After the eighth split, `gui/dialogs/advanced_settings/params_adapter.py` owns advanced-settings widget-to-dict collection, current-param widget loading, default reset values, loaded-param widget sync, and preset widget writes. `AdvancedSettingsDialog` still owns tab layout, file dialogs, JSON save/load, status labels, print messages, and recognizer/stitcher application timing.

After the ninth split, `gui/dialogs/color_picker/hsv_ranges.py` owns HSV conversion/sample/range math and saturation averaging, while `gui/dialogs/color_picker/image_renderer.py` owns OpenCV-to-QPixmap conversion and sample marker drawing. `ColorPickerDialog` still owns point collection, preview mask generation, morphology, debug file output, result text, and accept/reject flow.

Core hotspots are algorithmically sensitive and should be split later. `core/stitcher_core.py` mixes registration, keyframe policy, weighted fusion, map package persistence, statistics, and display-map generation. `core/navigation_core.py` mixes map package loading, F2F tracking, template relocalization, frame-registration contract creation, and display-map rendering. `core/auto_navigator.py` is a large but cohesive state machine; route-progress helpers and fallback probe helpers are reusable candidates, but the state transitions should not be moved until covered by targeted import/behavior checks. `core/motion_controller.py` is the input-control boundary and combines map-to-screen conversion, bottom-click guard, Win32 backend access, pydirectinput fallback, keyboard presses, and click diagnostics.

The event system has comparatively clear module boundaries: `EventCoordinator` orchestrates, `EventMonitor` runs detectors, `EventPositionStabilizer` localizes detections, `EventMemory` owns task lifecycle/cooldown, `EventScheduler` selects work, `EventRunner` owns handler lifecycle, and `EventActionExecutor` bridges actions to GUI-owned callbacks. The main unclear boundary is currently in `NavigationModeWidget`, which still builds `EventTick`, executes event MOVE_TO through GUI state, and draws event overlays.

Reusable capabilities already present: `EventPathMover` is reusable A* lookahead movement for event actions; `path_utils` is reusable route math; `core/events/detectors/template_matcher.py` is reusable template matching; `core/events/window_finder.py` and `core/input_driver.py` are reusable Windows input/window primitives; `NavConfig` and `EventSystemConfig` are separate runtime configuration contracts. Reusable capabilities now extracted from GUI include route overlay rendering, event overlay rendering, navigation capture geometry, navigation viewport geometry, mapping save/load config IO, mapping display rendering, mapping parameter control adapters, advanced-settings parameter mapping, color-picker HSV range math, and color-picker image marker rendering. Reusable capabilities still trapped in GUI include nav-params dialog field mapping and mapping capture-loop orchestration.

Recommended refactor order is: first split navigation GUI helpers with compatibility imports; then split mapping save/load/render helpers; then split dialog schema/helper modules; then isolate motion input backend/diagnostics; then split core navigation/stitching algorithms only after the GUI layer no longer obscures call sites.
