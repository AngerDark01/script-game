# Navigation Mode 架构

## 当前角色

`gui/modes/navigation/widget.py` 是导航页真实 QWidget 组合根，`gui.modes.navigation.NavigationModeWidget` 是正式入口。旧 `gui/modes/navigation_mode.py` 已删除。

它现在不再承载全部实现细节，但仍拥有 Qt 生命周期、核心子系统实例、定时器、scene item 引用和少量旧 slot wrapper。旧长 docstring 已压缩为 wrapper 级说明，避免重复描述已经迁走的内联实现。真实行为已经按功能包下沉：

- `ui/`：控件布局、signal wiring、小窗/完整布局切换；`layout.py` 只做总装，真实控件创建下沉到 `components/` 和 `compact/`。
- `composition/`：导航页 lifecycle/controller targets wiring 和定时器/runtime 组合顺序。
- `map/`：地图列表、地图载入 session、配置读写、capture geometry、地图点击生命周期。
- `config/`：`NavConfig` 应用、保存、默认配置保存和脏状态提示。
- `route/`：路线编辑、路线面板命令、route.json load/save/undo/clear 后的运行态同步。
- `events/`：事件弹窗生命周期、事件配置保存、portal 手动测试、事件运行态重置。
- `display/`：Qt scene item、路线/事件 overlay、monitor/game-view 框、上次退出点 marker 的引用写回。
- `runtime/`：导航命令生命周期、整帧 frame loop、capture-localize tick、事件观测、任务 controller context 组装、intent consumption、小地图样本采集落盘。
- `sampling/`：小地图样本采集浮窗和非阻塞保存反馈，复用 `runtime/minimap_sample_capture.py` 的落盘 helper。
- `input/`：输入窗口模式和 `NavigationIntent` 到 `MotionController` 的执行 adapter。
- `presentation/`：状态栏、弹窗、overlay 绘制、地图加载状态、配置保存状态等纯 UI 写入。
- `calibration/`：屏幕中心选择、DPR/坐标转换、校准结果写回。

核心边界：GUI 负责把用户动作和 Qt 状态翻译成 core 调用；core 负责定位、路径、任务编排、事件动作和输入映射策略。GUI 不应该重写 core 算法。

## 当前公共表面

`NavigationModeWidget` 仍保留这些外部可调用入口：

- `refresh_map_list()` / `load_map()`
- `toggle_navigation()` / `stop_runtime()` / `toggle_auto_navigation()`
- `navigation_loop()`，内部只转到 `_navigation_loop_unified()`
- 路线 slot：`load_route_data()`、`save_route()`、`undo_guide_point()`、`undo_required_point()`、`clear_route()`
- 配置 slot：`_apply_config_to_core()`、`_save_nav_config()`、`_save_nav_default_config()`
- 事件 slot：`_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`
- 展示 wrapper：`_render_map()`、`_render_route_overlay()`、`_render_event_overlay()`、`_update_monitor_rect()`、`_update_game_view_rect()`
- 样本采集入口：`toggle_minimap_sample_window()`、`capture_minimap_sample()`、`save_minimap_sample()`

这些 wrapper 是 GUI 内部兼容入口，不再是长期设计目标。后续如果调用方全部迁到功能包或 signal 直连功能包，可以继续删除。

## 当前数据流

### 地图载入

1. `load_map()` 读取 combo 当前地图名。
2. `NavigationMapLoadLifecycle.load_selected_map()` 调用 map session/config helpers。
3. 写回 `map_folder_path`、`nav_config`、`nav_core`、`_capture_center_physical`。
4. 应用 config 到 `NavigationCore`、`PathFinder`、`MotionController`、`NavigationTaskController`。
5. `initialize_navigation_event_system()` 读取事件配置、创建 `EventCoordinator`、创建 `GameWindowCaptureProvider`、刷新事件弹窗并记录初始化日志，widget 只写回 runtime 字段。
6. 渲染地图、恢复上次退出点、刷新路线/事件 overlay、启用按钮和状态文案。

### 导航循环

0. `NavigationRuntimeFrameLoop.run()` 拥有定时器单帧编排顺序，`NavigationModeWidget._navigation_loop_unified()` 只保留 Qt timer 兼容入口。
1. `capture_navigation_localization_tick()` 计算截图区域、抓取 frame、解析玩家局部坐标、调用 `NavigationCore.localize()`。
2. frame loop 把本帧 `frame`、`capture_rect`、`player_pos` 缓存到 `NavigationModeWidget._latest_minimap_frame/_latest_minimap_capture_rect/_latest_minimap_player_local_pos`，供样本采集直接保存最近监视区域，不额外触发事件识别或任务调度。
3. `observe_navigation_events()` 构造 event tick、调用 `EventCoordinator.observe()`、刷新事件 overlay 和可见弹窗任务列表。
4. `update_navigation_task_controller()` 组装 `NavigationUpdateContext`，调用 `NavigationTaskController.update_context()`。
5. `update_localization_view()` 更新玩家 marker、monitor 框和 game-view 框。
6. `show_navigation_runtime_status()` 写状态栏。
7. 若有 `NavigationIntent`，先刷新路线 overlay，再由 `consume_navigation_intent()` 处理强制重定位、真实输入执行、manual test terminal stop 和 ARRIVED/FAILED 收束。

### 小地图样本采集

1. `navigation/ui/components/toolbars.py` 在辅助工具栏创建 `截图窗口` 和 `保存小地图样本` 两个入口，初始禁用，避免未加载地图时保存无上下文截图。
2. 地图加载成功后，`NavigationModeWidget._set_loaded_map_session()` 启用两个入口，并同步 `NavigationSampleCaptureLifecycle` 的 ready 状态。
3. `截图窗口` 通过 `NavigationSampleCaptureLifecycle.toggle_window()` 打开 `sampling/window.py::MinimapSampleCaptureWindow`。该窗口是独立置顶小窗，默认移动到屏幕右下角，适合单屏游戏运行时手动采样。
4. 浮窗内的保存按钮连接到 `NavigationSampleCaptureLifecycle.save_sample()`，使用非阻塞状态文案反馈，不弹出 QMessageBox，避免打断游戏画面上的连续采样。
5. 顶部工具栏的 `保存小地图样本` 仍连接到 `NavigationModeWidget.save_minimap_sample()`，用于主窗口内的一次性保存；失败时保留 QMessageBox 提示。
6. 真正采样由 `NavigationModeWidget.capture_minimap_sample()` 执行：优先读取 frame loop 缓存的最近小地图帧；如果导航循环尚未产生缓存，则调用 `capture_current_minimap_frame()` 依据当前 `NavConfig` 的监视几何即时截取一次。
7. `runtime/minimap_sample_capture.py::save_minimap_sample()` 把图像统一转成 BGR，写入 `debug/minimap_samples/<map_name>/<timestamp>_<map_name>_minimap.png`，并写同名 JSON 元数据。
8. JSON 元数据包含 `map_name`、`source`、`capture_rect`、`monitor_size`、`player_local_pos`、`frame_shape` 和图片路径，后续可以直接被掉落物/传送门识别 probe 作为样本来源。

### 事件弹窗

1. `_ensure_event_dialog()` 委托 `NavigationEventDialogLifecycle.ensure_dialog()`。
2. 首次创建时连接配置变更、保存、portal 测试、portal reset 信号。
3. 弹窗显示前刷新 registry/config/coordinator/map name。
4. portal 手动测试的按钮状态由 `ManualEventTestController` 同步。

### 导航页小窗布局

1. `navigation/ui/layout.py` 保留 `build_navigation_ui(owner)` 入口，按顺序组装地图选择栏、主导航操作栏、辅助工具栏、路线工具栏、地图视图和状态栏。
2. `navigation/ui/components/toolbars.py` 拆分四组控件：地图选择、主导航动作、路线编辑工具、辅助工具。所有旧按钮属性名仍写回 `owner`，例如 `btn_start`、`btn_auto_nav`、`event_button`、`params_button`、`sample_window_button`。
3. `navigation/ui/components/map_view.py` 独立创建 `QGraphicsScene/QGraphicsView`，并初始化 `map_item/player_item/monitor_rect_item/path_item` 等 scene item 引用。
4. `NavigationMapGraphicsView` 只管理地图显示缩放：地图加载和窗口尺寸变化时默认 `fit_map()` 适应视口；工具栏提供“地图- / 适应地图 / 地图+”；Ctrl+滚轮也可缩放。该缩放只改变 `QGraphicsView` transform，不改变 `NavConfig.draw_scale`、scene 坐标、路径点、事件目标或定位投影。
5. `navigation/ui/compact/controller.py::NavigationCompactUiController` 只负责 presentation：默认小窗模式、地图 view 最大高度、路线工具栏显隐和按钮文案；小窗/完整布局切换后会延迟触发一次 `fit_map()`，避免视口变大但地图仍停在旧比例。
6. 小窗模式默认启用：地图 view 最大高度约 `380px`，路线工具栏默认折叠，通过 `路线工具` 按钮临时展开；`完整布局` 按钮切回完整模式后路线工具栏常显，地图 view 不限制最大高度。
7. 小窗布局不改变 `NavConfig`、capture geometry、定位算法、事件观测顺序或 `NavigationTaskController` 状态，只改变 Qt widget 组织和可见性。

## 已完成的壳清理

- 旧 GUI 入口壳已删除：`navigation_mode.py`、`mapping/save_load.py`、`mapping/params_adapter.py`、`navigation/map_runtime.py`、`navigation/route_overlay.py`、`navigation/event_overlay.py`、`navigation/viewport_overlay.py`、`event_test_controller.py`。
- `MainWindow` 已从 `gui.modes.navigation` 导入 `NavigationModeWidget`。
- GUI 实现侧已不再依赖旧 core 顶层壳，改用 `core.localization`、`core.input`、`core.routing`、`core.vision`、`core.mapping`、`core.platform`。
- 小地图样本采集已作为导航页独立能力接入：UI 按钮、置顶采样浮窗、单帧缓存、即时截图 fallback 和 PNG+JSON 落盘 helper 已分离，不进入 core 识别算法层。

## 剩余优化候选

### 1. 继续收窄 `NavigationModeWidget.__init__`

`__init__` 仍创建大量 subsystem 和 lambda targets。下一步可以把 target DTO 构造集中到 `navigation/bootstrap/` 或 `navigation/composition/`，但要避免做成只搬运参数的“超大参数工厂”。

### 2. 导航循环 facade

已落地为 `NavigationRuntimeFrameLoop`。当前它持有 `NavigationModeWidget` owner，以避免为了单帧顺序制造超大 callback DTO；后续如果继续工程化，应把 owner 访问收窄为 targets DTO，而不是把 frame loop 拆回多个浅 helper。

### 3. Qt event filter

`eventFilter()` 已只保留 Qt 安装入口；左键 scene 点击识别已下沉到 `map/event_filter.py`，真实 hint/route/manual move 语义仍在 `NavigationMapClickLifecycle`。

## 风险

- `NavigationModeWidget` 仍是多系统组合根，继续拆分时最大风险是把状态写回顺序打乱。
- runtime frame loop 目前通过 owner 访问 widget 状态，风险是隐藏依赖；后续如需增强复用性，应收窄依赖而不是扩大 callback 列表。
- 事件弹窗、portal 手动测试和 auto navigation 共用 timer/input 状态，任何拆分都必须保留 `NavigationTaskController`、`MotionController`、button checked state 的原顺序。
- 小地图样本采集保存的是当前监视区域原始帧，默认不做人物遮罩或掉落物后处理；这些样本用于诊断 detector，不能把保存阶段做成识别算法的一部分，否则会污染后续回归样本。
- 采样浮窗是置顶工具窗，如果用户把它拖到小地图监视区域上方，保存出来的样本会包含窗口遮挡；采样时应把窗口放在不覆盖监视区域的位置。
- 小窗模式隐藏路线工具栏时，按钮本身仍存在并保持 signal wiring；不要在 compact controller 中创建/销毁 route buttons，否则 `RoutePanelController` 和 signal wiring 会断引用。

当前状态：partial。结构已经比旧单文件清晰，`widget.py` 从约 950 行降到约 420 行；`__init__` target DTO 构造已迁入 navigation 局部 composition module；`ui/layout.py` 已降为总装入口，工具栏、地图视图、状态栏和小窗控制器已拆分。下一步应优先继续删除已经无人调用的内部 wrapper，或收窄 composition/frame loop 的 owner 依赖，而不是仅按行数继续切。
