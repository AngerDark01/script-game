# 架构迭代日志

本日志是中文复刻版，记录本次架构阅读过程、每轮目标、关键发现、覆盖状态和下一步计划。详细模块说明已沉淀到各模块自己的 `ARCHITECTURE.md` 中。

## Round 1 - 项目结构与文档骨架

### A. 本轮目标

- 粗读项目目录、顶层配置、现有 `CODEBASE.md`。
- 建立独立的架构说明入口和按模块分散的说明文件。
- 找出超长文件和第一批拆分候选。

### C. 本轮发现

- 最大文件集中在 GUI 导航、参数对话框、建图/定位 core、导航任务 controller。
- 当前文档不能只放一个文件；应按功能模块就近放置。
- 新增文档入口：
  - `ARCHITECTURE_GUIDE.md`
  - `ARCHITECTURE_ITERATION_LOG.md`
  - `core/ARCHITECTURE.md`
  - `gui/ARCHITECTURE.md`
  - `gui/modes/ARCHITECTURE.md`
  - `gui/dialogs/ARCHITECTURE.md`
  - `utils/ARCHITECTURE.md`
  - `tests/ARCHITECTURE.md`

下一轮计划：阅读入口、组合根、主窗口和包导出。

## Round 2 - 启动与组合根

### A. 本轮目标

- 阅读 `main.py`、`gui/app_context.py`、`gui/main_window.py`、`core/__init__.py`、`gui/__init__.py`。
- 搞清楚进程启动、Qt 启动、共享服务创建和 mode 注入关系。

### C. 本轮发现

- `main.py` 同时承担 runtime 输出、控制台隐藏、DPI、UAC、单实例锁、旧窗口检测和 QApplication 创建。
- `AppContext` 是当前共享服务组合点，创建 capture、recognizer、stitcher、tracker、pathfinder，并保存 monitor 状态。
- `MainWindow.closeEvent()` 直接知道 `mapping_widget.capture_timer` 和 `nav_widget.toggle_navigation()`，shutdown 接口不稳定。
- 建议先加幂等 `stop_runtime()`，再让 shell 调用 mode 的停止接口。

更新文档：

- `ARCHITECTURE_GUIDE.md`
- `gui/ARCHITECTURE.md`

下一轮计划：读 `gui/modes/navigation_mode.py` 的方法分组。

## Round 3 - `navigation_mode.py` 拆分地图

### A. 本轮目标

- 按方法组阅读导航模式大文件。
- 找出 widget shell、runtime loop、route editor、event adapter、overlay presenter、input execution 的边界。

### C. 本轮发现

- `NavigationModeWidget` 同时是 QWidget、地图加载器、配置应用器、路线编辑器、事件管理 adapter、overlay presenter、导航 runtime loop、intent executor、窗口模式控制器、校准控制器。
- 高耦合点是 `_navigation_loop_unified()`：截图、定位、事件 observe、task update、overlay、status、relocalize、input execution 都在里面。
- 推荐拆分：
  - `runtime_loop.py`
  - `intent_executor.py`
  - `input_window_mode.py`
  - `config_applier.py`
  - `route_editor.py`
  - `event_panel_adapter.py`
  - `map_session.py`
  - `map_presenter.py`
  - `calibration_controller.py`

推荐顺序：

1. 先加 `start_runtime()` / `stop_runtime()`。
2. 抽 `input_window_mode.py`。
3. 抽 `intent_executor.py`。
4. 抽 `config_applier.py`。
5. 抽 `route_editor.py`。
6. 抽 `event_panel_adapter.py`。
7. 抽 `runtime_loop.py`。
8. 抽 `map_presenter.py`。

更新文档：

- `gui/modes/navigation/ARCHITECTURE.md`

下一轮计划：读 `core/navigation_tasks`。

## Round 4 - 统一导航任务系统

### A. 本轮目标

- 阅读 task models、controller、movement executor、scheduler、builder、route context、event approach、diagnostics。
- 明确 route/event/exit 如何统一成 intent。

### C. 本轮发现

- `core/navigation_tasks` 是比较接近可复用的编排系统。
- 当前 `NavigationTaskController.update()` 参数太宽，GUI loop 必须知道 route、event coordinator、tick、wall map、pathfinder、explored map、timing、manual event mode、frame registration。
- 建议引入 `NavigationUpdateContext`，分组：
  - localization snapshot
  - route snapshot
  - event runtime snapshot
  - planning snapshot
  - timing/options
- `controller.py` 建议拆成：
  - `update_context.py`
  - `localization_filter.py`
  - `static_task_runner.py`
  - `event_task_runner.py`
  - `intent_factory.py`
  - `diagnostic_policy.py`
- `EventApproachController` 属于 navigation 层，不属于 portal event package。

更新文档：

- `core/navigation_tasks/ARCHITECTURE.md`

下一轮计划：读 `core/events`。

## Round 5 - 事件系统生命周期

### A. 本轮目标

- 阅读 event models、coordinator、monitor、memory、runner、scheduler、registry、config、base interfaces、overlay models、capture provider。
- 明确 observe phase 和 run phase 的边界。

### C. 本轮发现

- 事件生命周期是两阶段：
  - `EventCoordinator.observe()` 只检测、稳定、合并 memory、选择 display/status task。
  - 真正执行 handler 要等 navigation 选中 event task 后调用 `run_task()`。
- `EventMemory` 是深模块，拥有 dedupe、confirm frames、cooldown、retry、ignore、teleport session completion、nearby suppression 等策略，不应过早拆。
- `EventRunner` 是 generic runtime 到 concrete handler 的执行 seam。
- `capture_provider.py` 是 handler 获取 minimap/main-view capture 的 adapter。
- `overlay_models.py` 是 core-safe DTO；PySide 渲染仍在 GUI。
- `core/events/config.py` 当前硬编码 portal 默认值，是 core 依赖具体事件包的耦合点。
- Hook 应用 hook bus/listener 实现，先只做观察型 hook，不改变控制流。

更新文档：

- `core/events/ARCHITECTURE.md`

下一轮计划：读 portal event package。

## Round 6 - Portal 事件包边界

### A. 本轮目标

- 阅读 portal definition、config、assets、minimap detector、feature matcher、shape/color matcher、main-view confirmer、handler。
- 验证 portal 是否是干净的事件包边界。

### C. 本轮发现

- `PortalEventDefinition` 是干净入口：identity、默认配置、schema、detector factory、handler factory。
- `PortalEventConfig` 是 typed config adapter，并保留兼容 fallback。
- `PortalMinimapDetector` 是 mode dispatch adapter，内部混了 template/feature/shape_color 选择和 final color filter。
- `minimap_feature_matcher.py` 是可复用蓝色主体特征匹配组件。
- `minimap_shape_color_matcher.py` 是算法最重组件，综合 blue/outer/shape/edge/color 响应，再做 F1-like score 和 signature score。
- `main_view_confirmer.py` 是可复用 full-screen portal glow confirmer，但当前未接入 `PortalEventHandler.update()`。
- `PortalEventHandler` 是字符串状态机，应先引入 `PortalHandlerPhase` enum 和 runtime dataclass。

更新文档：

- `core/events/types/portal/ARCHITECTURE.md`

下一轮计划：读 mapping/localization core。

## Round 7 - 建图与定位 core

### A. 本轮目标

- 阅读 `core/recognizer_optimized.py`、`core/stitcher_core.py`、`core/navigation_core.py`。
- 找出可复用算法和有状态 runtime facade。

### C. 本轮发现

- `HSVRecognizer` 混合参数、预处理、wall/fog/player 提取、动态颜色过滤、combined registration mask。
- `HSVRecognizer.extract_combined()` 是建图和导航定位共享输出：`(match_mask, wall_mask, fog_mask)`。
- `MapStitcher` 混合 map state、map package IO、keyframe/F2F registration、weighted merging、stats、display rendering。
- `MapStitcher.add_frame()` 是建图主链：首帧放置、keyframe anchor matching、previous-frame fallback、draw-quality gate、mask resize/standardize、weighted merge。
- `NavigationCore` 混合 map package loading、recognizer construction、localization state、F2F tracking、template matching、visual consistency、frame registration、display rendering。
- `MapStitcher._estimate_displacement()` 和 `NavigationCore._estimate_displacement()` 复制了 phase correlation 算法。
- 第一优先提取：共享 `phase_correlate_shift()`；之后是 package IO、weighted merge、localization matching。

更新文档：

- `core/ARCHITECTURE.md`

下一轮计划：读 route/pathfinding core。

## Round 8 - 路由规划与几何 core

### A. 本轮目标

- 阅读 `core/pathfinder.py`、`core/path_utils.py`、`core/anchor_path.py`、`core/navigation_obstacles.py`。
- 判断 A*、几何工具、anchor planning 是否已经可复用。

### C. 本轮发现

- `PathFinder` 是较干净的 GUI-free A* adapter，负责 downsample、obstacle map、start-area 清理、walkable snapping、8 方向 A*、global path 重建。
- `_astar()` 允许斜向移动，但禁止 diagonal corner cutting。
- `_build_obstacle_map()` 支持 wall thinning、explored_map 未知区域阻塞、safety-margin dilation。
- `derive_navigation_wall_layer()` 是纯 adapter：threshold 后可用 cross kernel erode，让 A* 更宽容，不改定位数据。
- `path_utils.py` 是可复用几何模块。
- `anchor_path.py` 负责用户 guide anchors 的 route-shaping。它先尝试下一个 forward anchor；如果 A* 到 anchor 失败，返回朝 anchor 的短 probe path，而不是直接跳最终目标。
- 已有 `test_pathfinder.py` 和 `test_path_utils.py`，缺 `anchor_path.py` 直接测试。

更新文档：

- `core/ARCHITECTURE.md`

下一轮计划：读 GUI dialogs。

## Round 9 - GUI Dialog 边界

### A. 本轮目标

- 阅读 `nav_params_dialog.py`、`advanced_settings_dialog.py`、`color_picker_dialog.py`、`event_manager_dialog.py` 以及已有 helper。
- 找出参数 binding、校验、预览、schema form 的可复用抽象。

### C. 本轮发现

- `NavParametersDialog` 是最大 dialog seam：tabs、help text、widget-to-`NavConfig` binding、`dataclasses.replace`、HSV text parse、`parameters_changed`、click radii 估算都在一个类里。
- `set_config_to_ui()` 用 `QSignalBlocker` 阻塞子控件信号，这个行为拆分后必须保留。
- `_connect_signals()` 里的 widget map 是最核心提取点。
- `_auto_estimate_click_radius()` 属于校准策略，不是 UI 布局。
- `AdvancedSettingsDialog` 是旧版 dict-based 调参面板，会直接 reach into `parent.recognizer` 和 `parent.stitcher`。
- `advanced_settings/params_adapter.py` 是有用但浅的抽离，仍依赖具体 dialog attribute 名。
- `ColorPickerDialog` 已抽 HSV math 和 image rendering，但 `update_preview()` 仍混合 mask generation、morphology、preview rendering 和 debug 文件写入当前目录。
- `EventManagerDialog` 是最好的模式：schema-driven 参数表，command signals，live task state。
- 新 dialog 应复用 event-manager 的 schema-driven 方式，避免 advanced-settings 的 parent-reach 模式。

更新文档：

- `gui/dialogs/ARCHITECTURE.md`

下一轮计划：读 mapping GUI。

## Round 10 - Mapping GUI 模式边界

### A. 本轮目标

- 阅读 `gui/modes/mapping_widget.py`、mapping helpers、相关 widgets。
- 明确 capture/stitch loop、显示、配置保存、地图保存和参数更新职责。

### C. 本轮发现

- 实际没有 `gui/modes/mapping_mode.py`；入口是 `gui/modes/mapping_widget.py`。
- 实际没有 `gui/widgets/minimap_widget.py`；mapping display 使用 `CollapsibleMapGroup` + `ScalableMapWidget`。
- `MappingWidget` 同时拥有 UI、region/center selection、capture timer、capture/recognize/stitch loop、display、临时 route planning、参数更新、dialogs、config、map save、topmost。
- `capture_and_process()` 是建图主循环：capture、player detect/fallback、extract combined、raw gray、`stitcher.add_frame()`、更新显示和 stats。
- helper 状态：
  - `mapping/save_load.py` 是有用 IO helper。
  - `mapping/map_renderer.py` 是有用 presentation adapter。
  - `mapping/params_adapter.py` 比较浅，仍直接依赖 widget。
- 具体风险：`ScalableMapWidget` 声明 `pixel_clicked`，`MappingWidget` 也连接了 `on_map_click()`，但 widget 从未 emit 这个 signal；“点击设置导航点”可能是断的。

更新文档：

- `gui/modes/ARCHITECTURE.md`

下一轮计划：读 input system。

## Round 11 - 输入系统与 Motion 边界

### A. 本轮目标

- 阅读 `core/motion_controller.py`、`core/input_driver.py`、input/event probe 和 motion tests。
- 找出 route intent、screen coordinate mapping、真实 click/key 副作用的 seam。

### C. 本轮发现

- `MotionController` 不只是 driver wrapper。它拥有 map-vector 到 screen-click 映射、半径策略、control enablement、direct screen click、key press、bottom guard、screen clamp、focus、backend dispatch、click diagnostics。
- `_calculate_target_screen_position()` 基本是纯 movement mapping，但会写 `last_click_info`。
- `_execute_click()` 是主副作用边界：bottom guard、clamp、window diagnostics、focus、backend click、fallback、diagnostics。
- `press_key()` 当前绕过 `InputDriver`，直接 `pydirectinput.press()`，这是 testability/hookability 缺口。
- `InputDriver` 是 Win32 adapter。
- `utils/input_probe.py` 是真实诊断 adapter：多种输入策略、dry-run 默认、`--execute` 才发送输入。
- `test_motion_controller.py` 已覆盖半径、zero-delta、诊断、clamp、focus、bottom guard。
- 最早的 input seam 应放在 `MotionController` 背后，形成 `InputCommandSink/GameInputAdapter`，而不是散在 event handler 或 movement executor 里。
- Hook 最适合观察 `MotionController` command/result：before、after、skipped、backend failure、diagnostics snapshot。

更新文档：

- `core/ARCHITECTURE.md`
- `utils/ARCHITECTURE.md`

下一轮计划：读测试总览和剩余 probe。

## Round 12 - 测试、剩余 probes、路线图收束

### A. 本轮目标

- 阅读 `tests/*.py`、`route_context_probe.py`、`navigation_task_probe.py`、顶层 guide。
- 明确哪些 refactor 已有测试保护，哪些需要先补测试。

### C. 本轮发现

- 现有测试保护了部分底层 seam：
  - `MotionController`
  - `PathFinder`
  - `path_utils`
  - `NavigationCore` F2F wall-mask 行为
  - `MapStitcher._merge_frame_weighted()`
  - recognizer dynamic filtering
  - route manager persistence
- 尚未直接保护：
  - event lifecycle
  - portal handler state transitions
  - mapping runtime orchestration
  - navigation intent execution
  - dialog binding
  - GUI map-click behavior
- `route_context_probe.py` 和 `navigation_task_probe.py` 都是好的窄 probe：读 route 数据，调用生产 `RouteContext` / `NavigationTaskBuilder`，不复制路由算法。
- `ARCHITECTURE_GUIDE.md` 已沉淀阶段路线：测试护栏、低风险深模块、runtime facades、event hooks/packages、GUI cleanup、最终包组织。
- 最安全的第一批代码改动：`anchor_path` 测试、共享 phase displacement、weighted merge、motion mapping/bottom guard、nav dialog click-radius estimator。

更新文档：

- `tests/ARCHITECTURE.md`
- `utils/ARCHITECTURE.md`
- `ARCHITECTURE_GUIDE.md`

下一步：

- 如果继续文档：按模块补 `CODEBASE.md` 风格函数/算法级说明。
- 如果开始重构：先补 `anchor_path.py` 和 `EventCoordinator` 测试，再抽低风险纯 helper。

## [SYNC] 2026-05-26 - Advanced Settings 文件 IO 清理

### A. SYNC 范围

触发任务：旧内容审计和低风险、行为保持的工程化清理。

直接源码变更：

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/file_io.py`
- `tests/test_advanced_settings_file_io.py`

预计影响：

- `AdvancedSettingsDialog.save_current_params()` 和 `load_params_from_file()` 现在委托可复用 helper 处理 JSON 持久化。
- 参数 snapshot 不再写进程当前工作目录，默认写入 `configs/advanced_settings/`。
- 新测试保护文件名清洗、显式输出目录、payload 结构、读取校验和非 ASCII 展示格式。

### C. SYNC 结果

关键发现：

- (verified) `advanced_settings/file_io.py` 拥有默认输出目录、文件名清洗、JSON dump/load、payload 校验和展示格式化。
- (verified) `AdvancedSettingsDialog` 仍拥有 Qt 文件对话框、状态标签、recognizer/stitcher apply 时机。
- (verified) 通过完整 `gui` 包导入 `gui.dialogs.advanced_settings.file_io` 会触发无关 GUI/input 依赖；新测试按文件路径加载纯 helper，保持测试隔离。

更新文档：

- `CODEBASE.md`
- `ARCHITECTURE_GUIDE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/ARCHITECTURE_GUIDE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

验证：

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\file_io.py tests\test_advanced_settings_file_io.py`
- `python -m unittest tests.test_advanced_settings_file_io`
- `python -m unittest tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

下一轮计划：

- 继续旧内容审计，先对 `gui/widgets_fixed.py` 做更严格引用检查，再决定是否删除。
- 然后考虑另一个低风险、有测试的抽取，优先 `AdvancedSettingsDialog` presets 或 `NavParametersDialog` 里的纯 helper。

## [SYNC] 2026-05-26 - 删除未使用的 widgets_fixed 备份

### A. SYNC 范围

触发任务：继续旧内容审计。

直接源码变更：

- 删除 `gui/widgets_fixed.py`

预计影响：

- 活动 widget import 仍通过 `gui/widgets/clickable_label.py`、`gui/widgets/scalable_map.py`、`gui/widgets/collapsible_group.py`。
- 删除旧合并备份可减少重复 widget 定义，避免后续误导入旧行为。

### C. SYNC 结果

关键发现：

- (verified) `rg` 没有发现 `gui.widgets_fixed` 运行时 import；引用仅限文档/历史记录和文件自身。
- (verified) `widgets_fixed.py` 包含旧合并版 `ClickableImageLabel`、`ScalableMapWidget`、`CollapsibleMapGroup` 定义。
- (verified) 当前运行时代码导入 `gui/widgets/` 下的拆分 widget 模块。

更新文档：

- `CODEBASE.md`
- `gui/ARCHITECTURE.md`
- `architecture_docs/original/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

验证：

- `python -m py_compile gui\widgets\clickable_label.py gui\widgets\scalable_map.py gui\widgets\collapsible_group.py gui\modes\mapping_widget.py`
- `python -c "from gui.widgets.clickable_label import ClickableImageLabel; from gui.widgets.scalable_map import ScalableMapWidget; from gui.widgets.collapsible_group import CollapsibleMapGroup; print('ok')"`

下一轮计划：

- 继续低风险清理，优先 `AdvancedSettingsDialog` presets 抽取；或者先审计 `k_ratio/y_bias` UI 兼容字段后再改。

## [SYNC] 2026-05-26 - Advanced Settings preset 数据抽取

### A. SYNC 范围

触发任务：旧内容审计后的低风险清理。

直接源码变更：

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/params_adapter.py`
- `gui/dialogs/advanced_settings/presets.py`
- `tests/test_advanced_settings_presets.py`

预计影响：

- preset 选项顺序和非默认 preset 值现在由纯数据 helper 维护。
- `AdvancedSettingsDialog` 不再内联 preset 名称。
- `params_adapter.apply_preset_to_widgets()` 仍保持同样的控件写入和默认 reset 行为。

### C. SYNC 结果

关键发现：

- (verified) `presets.py` 拥有 `DEFAULT_PRESET_NAME`、`PRESET_NAMES` 和非默认 widget-value map。
- (verified) 默认 preset 仍通过 `reset_widgets_to_default()` 走完整 reset。
- (verified) 测试覆盖 preset 顺序、旧值、adapter 应用、默认 reset、未知 preset 返回值，且不构造 Qt dialog。

更新文档：

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

验证：

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\params_adapter.py gui\dialogs\advanced_settings\presets.py tests\test_advanced_settings_presets.py`
- `python -m unittest tests.test_advanced_settings_presets`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

下一轮计划：

- 只有能用窄 adapter 测试覆盖时，才继续拆 `AdvancedSettingsDialog` tab/widget spec；否则先审计 `k_ratio/y_bias` 兼容字段。

## [SYNC] 2026-05-26 - 隐藏旧 k_ratio/y_bias UI

### A. SYNC 范围

触发任务：审计旧 `NavPreferences.k_ratio/y_bias` 兼容字段。

直接源码变更：

- `gui/dialogs/nav_params_dialog.py`
- `tests/test_navigation_params_compat.py`

预计影响：

- 旧 `k_ratio/y_bias` 值仍通过 `NavConfig.nav_preferences` 加载/保存。
- 导航参数面板不再暴露当前 motion mapping 不使用的控件。

### C. SYNC 结果

关键发现：

- (verified) `k_ratio/y_bias` 没有被 `MotionController`、定位、任务调度或移动执行链路引用。
- (verified) 运行时用途仅限配置模型 round-trip 和 `NavParametersDialog` UI/binding。
- (verified) 已移除 UI 控件和 widget-map 绑定，同时保留 `NavPreferences` 以兼容旧 `config.json`。

更新文档：

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

验证：

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\navigation_params.py tests\test_navigation_params_compat.py`
- `python -m unittest tests.test_navigation_params_compat`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

下一轮计划：

- 这批旧内容清理可以先停在这里；更大的 tab 拆分需要单独窄计划和 GUI-aware 测试策略。

## [SYNC] 2026-05-26 - 导航参数屏幕估算器抽取

### A. SYNC 范围

触发任务：继续低风险 dialog 清理，并补齐导航点击半径估算器抽取后的文档同步。

直接源码变更：

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/nav_params/__init__.py`
- `gui/dialogs/nav_params/screen_estimator.py`
- `tests/test_nav_params_screen_estimator.py`

预计影响：

- `NavParametersDialog` 保留 Qt screen enumeration 和 UI 写回。
- `gui.dialogs.nav_params.screen_estimator.estimate_click_radii()` 拥有纯半径策略。
- 测试覆盖普通估算、小屏幕最小值 clamp、大屏幕最大值 clamp、中心点越界。

### C. SYNC 结果

关键发现：

- (verified) `_auto_estimate_click_radius()` 现在把半径数学委托给 `estimate_click_radii(center, screen_bounds)`。
- (verified) `screen_estimator.py` 无 Qt 依赖，可在不导入完整 GUI package 的情况下测试。
- (verified) 物理屏幕检测仍留在 dialog adapter 的 `_screen_physical_bounds_for_center()`。

更新文档：

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`

验证：

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\dialogs\nav_params\screen_estimator.py tests\test_nav_params_screen_estimator.py`
- `python -m unittest tests.test_nav_params_screen_estimator`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_navigation_params_compat tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

下一轮计划：

- 继续旧 debug 输出清理：默认禁用 `ColorPickerDialog.update_preview()` artifact 写入，同时保留显式诊断 opt-in。

## [SYNC] 2026-05-26 - 颜色选择器 debug 输出开关

### A. SYNC 范围

触发任务：在颜色选择器 preview debug artifacts 不再写当前工作目录后，继续旧内容审计清理。

直接源码变更：

- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/color_picker/debug_output.py`
- `tests/test_color_picker_debug_output.py`

预计影响：

- HSV preview rendering 仍更新右侧 preview label。
- `preview_result_*.png`、`preview_before_morph_*.png`、`preview_log_*.txt` 默认不再每次 preview 落盘。
- 设置 `MINIMAP_COLOR_PICKER_DEBUG=1` 时仍可生成 debug artifacts。

### C. SYNC 结果

关键发现：

- (verified) `ColorPickerDialog.update_preview()` 仍构建同样的 wall mask，执行同样的 close morphology，并更新 preview label。
- (verified) 只有 `is_wall_preview_debug_enabled()` 接受 `MINIMAP_COLOR_PICKER_DEBUG` 时才调用 `write_wall_preview_debug()`。
- (verified) debug 开关无需导入 PySide widgets 或构造 dialog 即可测试。

更新文档：

- `CODEBASE.md`
- `ARCHITECTURE_GUIDE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/ARCHITECTURE_GUIDE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

验证：

- `python -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\debug_output.py tests\test_color_picker_debug_output.py`
- `python -m unittest tests.test_color_picker_debug_output`

下一轮计划：

- 当前 docs 和回归测试干净后，再继续另一个低风险纯 helper 抽取。

## [SYNC] 2026-05-26 - MotionController 纯映射抽取

### A. SYNC 范围

触发任务：只做实际实现，不新增/修改测试，不同步英文镜像文档。

直接源码变更：

- `core/motion_controller.py`
- `core/motion_mapping.py`

预计影响：

- `MotionController` 仍是唯一真实输入边界。
- 普通移动点击、近目标精确点击和 bottom-click guard 的纯计算移到 `core/motion_mapping.py`。
- 不改真实点击后端、focus、窗口诊断、fallback 或按键输入行为。

### C. SYNC 结果

关键发现：

- (verified) `calculate_movement_click()` 返回普通移动点击坐标和 click_info。
- (verified) `calculate_mapped_target_click()` 保留不应用 minimum radius 的近目标/事件点点击策略。
- (verified) `apply_bottom_click_guard()` 只做纯投影计算，screen height 仍由 `MotionController` 从 driver/pydirectinput 获取。

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：

- `python -m py_compile core\motion_controller.py core\motion_mapping.py`

下一轮计划：

- 若继续做实现，优先抽 `ColorPickerDialog.update_preview()` 的纯 preview mask/stats，仍不碰英文镜像文档和测试文件。

## [PLAN] 2026-05-26 - core 分层模块化规划

### A. 阅读范围声明

触发任务：对 `D:\ACloud\minimap_stitcher copy 13\core` 做抽象分层、模块化、系统化文件结构梳理，并先产出完整 plan。

本轮只规划，不实施代码移动。

目标文件/资料：

- `core/**` 文件树。
- `CODEBASE.md` 中 core 模块、函数索引、数据流和风险段落。
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`。
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`。

本轮要回答：

- core 当前有哪些系统、模块和适配器。
- 哪些文件应该归到 mapping/localization/routing/input/events/navigation_tasks 等层。
- 哪些移动可以先做 compatibility import，哪些必须等 facade/test/调用方稳定后再做。
- 分阶段迁移计划和风险控制。

### A2. 补充阅读范围声明

用户补充要求：core 对外接口必须纳入规划。外部已经调用的 `core.*` 路径不能因为内部拆分而调用不通；必要时旧文件保留壳子，实际实现移动到新模块。

追加阅读范围：

- 非 `core/**` 文件里对 `core` 的 import/call site。
- `core/__init__.py` 顶层导出。
- 当前 GUI 组合根和导航/建图模式对 core facade 的调用形态。

追加要回答：

- 哪些接口属于 public facade，迁移第一阶段必须冻结。
- 哪些文件移动后必须保留 compatibility wrapper。
- 哪些调用方可以后续逐步改到新包路径。

### C. 本轮发现

关键发现：

- (verified) `gui/app_context.py` 通过 `core.__init__` 导入 `ScreenCapture`、`HSVRecognizer`、`MapStitcher`、`PlayerTracker`、`PathFinder`，所以 `core.__init__` 当前五个导出必须先冻结。
- (verified) `gui/modes/navigation_mode.py` 直接导入 `NavigationCore`、`MotionController`、`RouteManager`、`NavigationTaskController`、`EventCoordinator`、事件 config/capture provider，并且直接读写 `nav_core.draw_scale/crop_offset/nav_wall_layer/explored_map/current_pos/last_frame_registration` 等属性；`NavigationCore` 不能先改成简单代理壳子。
- (verified) `utils/input_probe.py` 直接导入 `core.input_driver.InputDriver`，`utils/event_icon_probe.py` 直接导入 `core.capture.SquareScreenCapture` 和 portal detector/私有 helper，`utils/portal_screen_probe.py` 直接导入 `core.events.window_finder` 和 portal main-view confirmer；这些 probe 路径在迁移期需要兼容。
- (verified) `core/stitcher_core.py` 和 `core/navigation_core.py` 是高状态 facade；更安全的做法是先在原 class 背后抽 `mapping/*`、`localization/*` helper，再考虑把 class 本体迁到新包。
- (verified) 路由相关 `navigation_obstacles/pathfinder/path_utils/anchor_path/route_manager` 更适合第一批整体归组到 `core/routing/`，旧 top-level 文件做 re-export wrapper。

更新文档：

- 新增 `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`。
- 更新 `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`，加入 core 专项计划入口。
- 更新 `architecture_docs/zh-CN/core/ARCHITECTURE.md`，把专项计划列为 core 拆分硬约束。
- 更新 `CODEBASE.md`，补充专项计划文件和核心兼容规则。

覆盖进度更新：

| 文件/范围 | 前状态 | 现状态 | 阅读次数 | 备注 |
| --- | --- | --- | --- | --- |
| `core/**` 文件树 | 浅读 | partial | 2 | 已完成文件清单、行数、导入关系和系统归组审计；未逐行深读所有算法函数。 |
| `core/__init__.py` | 浅读 | 深度完整 | 2 | 确认当前五个对外导出，是 `gui/app_context.py` 的组合入口。 |
| 非 core 对 `core.*` 调用面 | PENDING | partial | 1 | 已审计 `gui/utils/main.py` 中 Python import/call site；文档和历史 plans 只作为参考，不纳入实现兼容清单。 |
| `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md` | 不存在 | 新增 | 1 | 记录目标结构、迁移映射、兼容壳子、分阶段计划和风险清单。 |

下一轮计划：

- 若开始实际实现，按计划优先做 Phase 1：新增 `core/routing/`，迁移路径规划五个低风险文件，并保留旧 wrapper；不碰测试、不碰英文文档。

## [SYNC] 2026-05-26 - core 模块化实施 Phase 1-2

### A. SYNC 范围

触发任务：用户确认按 `core/CORE_MODULARIZATION_PLAN.md` 逐步执行完毕。

本批实施范围：

- Phase 1：新增 `core/routing/`，把路径规划和路线持久化实现迁入新包。
- Phase 2：新增 `core/input/`，把纯 motion mapping 和 Win32 输入适配器迁入新包。
- 保留旧 `core.navigation_obstacles`、`core.pathfinder`、`core.path_utils`、`core.anchor_path`、`core.route_manager`、`core.motion_mapping`、`core.input_driver` 作为 compatibility wrapper。

本批不做：

- 不改测试目录。
- 不更新英文文档。
- 不拆 `MapStitcher`、`NavigationCore`、`NavigationTaskController`。
- 不做 hook。

预期兼容：

- 旧 import 路径继续可用。
- 新 import 路径 `core.routing.*` 和 `core.input.*` 可用。

### A2. 追加 SYNC 范围

Phase 1/2 通过 py_compile 和 import smoke 后继续执行低风险 Phase 3：

- 新增 `core/vision/`，归组 `HSVRecognizer`、`PlayerTracker`、`estimate_phase_displacement`。
- 新增 `core/platform/`，归组 `SquareScreenCapture`。
- 保留旧 `core.capture`、`core.recognizer_optimized`、`core.tracker`、`core.phase_displacement` 作为 compatibility wrapper。

本批仍不拆高状态 facade、不处理测试、不更新英文文档。

### A3. 追加 SYNC 范围

继续执行低风险依赖方向修正：

- 新增 `core/shared/frame_registration.py`。
- `core.events.models` 从 shared re-export `FrameRegistration`，保持旧 import 路径和类型身份。
- `NavigationCore` 改从 `core.shared.frame_registration` 导入，解除定位层对事件 runtime model 的直接依赖。

### A4. 追加 SYNC 范围

继续执行 Phase 4 的低风险 helper 抽取：

- 新增 `core/mapping/package_io.py`，承接 `MapStitcher` 的 `map_data.npz` 保存/加载细节。
- 新增 `core/mapping/weighted_merge.py`，承接 `_merge_frame_weighted()` 的 ROI 裁剪和 layer 写入算法。
- `MapStitcher` 仍保留原公开方法和公开状态字段，只委托 helper。

### A5. 追加 SYNC 范围

继续执行 Phase 5 的低风险 helper 抽取：

- 新增 `core/localization/map_package.py`，承接 `NavigationCore._load_map_data()` 的 `map_data.npz` 加载和缺省字段处理。
- `NavigationCore` 仍保留 `_load_map_data()` 和原公开属性，只委托 helper。

### A6. 追加 SYNC 范围

执行 Phase 6 的兼容入口第一步：

- 新增 `core/navigation_tasks/update_context.py`，定义 grouped context/snapshot。
- `NavigationTaskController.update(**kwargs)` 保留旧 GUI 调用面，内部转换为 `NavigationUpdateContext` 后委托 `update_context()`。
- 暂不拆 `_update_static_task()`、`_update_event_task()` 和定位过滤算法，避免一次性改动过大。

### A7. 追加 SYNC 范围

执行 Phase 7 的低风险配置拆分：

- 新增 `core/events/config_model.py`，承接 `EventSystemConfig`、默认值、deep merge 和 legacy detector mode 兼容。
- 新增 `core/events/config_io.py`，承接 `event_config.json` 路径、加载和保存。
- `core/events/config.py` 保留旧导出，不改 GUI/事件管理弹窗调用。

### A8. 追加 SYNC 范围

执行 Phase 8 的小切片：

- 新增 `core/events/types/portal/minimap_hit_filter.py`，承接 portal 小地图颜色接受过滤，`minimap_detector._portal_color_check` 保留 alias。
- 新增 `core/events/types/portal/environment_signature.py`，承接 portal handler 的小地图环境签名和差异计算，旧私有函数保留 wrapper。
- 不拆 `PortalMinimapDetector` 模式分发和 `PortalEventHandler` 状态机主体。

### A9. 追加 SYNC 范围

继续抽低耦合 helper：

- 新增 `core/mapping/rendering.py`，承接 `MapStitcher.get_cropped_map()` / `get_enhanced_map()` 的显示裁剪和着色。
- 新增 `core/localization/rendering.py`，承接 `NavigationCore.get_map_image()` 的显示地图渲染和 crop offset 写入。
- 新增 `core/navigation_tasks/intent_factory.py`，承接 movement/event action 到 `NavigationIntent` 的转换。

### A10. 追加 SYNC 范围

继续 Phase 8 的小切片：

- 新增 `core/events/types/portal/completion_detector.py`，承接 known-exit 搜索、位置变化和环境变化完成判定。
- `PortalEventHandler._teleport_completion()` 和 `_near_known_exit_portal()` 保留旧方法，内部委托 helper。

### C. SYNC 结果

关键发现：

- (verified) 旧 top-level core 路径已保留 compatibility wrapper：`capture.py`、`recognizer_optimized.py`、`tracker.py`、`phase_displacement.py`、`navigation_obstacles.py`、`pathfinder.py`、`path_utils.py`、`anchor_path.py`、`route_manager.py`、`motion_mapping.py`、`input_driver.py`。
- (verified) 新包路径可用：`core.routing`、`core.input`、`core.vision`、`core.platform`、`core.shared`、`core.mapping`、`core.localization`。
- (verified) `MapStitcher` facade 保留，已委托 `mapping/package_io.py`、`mapping/weighted_merge.py`、`mapping/rendering.py`。
- (verified) `NavigationCore` facade 保留，已委托 `localization/map_package.py`、`localization/rendering.py`，并从 `core.shared.frame_registration` 导入 `FrameRegistration`。
- (verified) `core.events.models.FrameRegistration` 与 `core.shared.frame_registration.FrameRegistration` 是同一个类型，旧 import 路径不产生类型身份分裂。
- (verified) `NavigationTaskController.update(**kwargs)` 保留旧调用面，内部转成 `NavigationUpdateContext` 后委托 `update_context()`；`intent_factory.py` 承接部分 intent 构造。
- (verified) `core.events.config` 保留旧导出，实际配置模型和 IO 已拆到 `config_model.py`、`config_io.py`。
- (verified) portal 小切片已抽出：`minimap_hit_filter.py`、`environment_signature.py`、`completion_detector.py`；旧 `_portal_color_check()`、`_minimap_environment_signature()`、`_signature_difference()` 仍可 import。

保留未拆内容：

- `MapStitcher.add_frame()` 的 keyframe/previous-frame registration 主流程仍在 `stitcher_core.py`。
- `NavigationCore.localize()` 的 F2F/template matching 主流程仍在 `navigation_core.py`。
- `NavigationTaskController` 的 localization filter、static runner、event runner 仍在 `controller.py`。
- `EventMemory` 没有拆。
- hook 系统没有做。

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：

- `python -m py_compile` 覆盖本轮新增/修改的 core 实现文件。
- 旧路径和新路径 import smoke 通过，包括 `core.__init__`、routing/input/vision/platform/shared、`NavigationTaskController`、`EventSystemConfig`、portal 私有兼容 alias。

下一轮建议：

- 若继续执行计划，应优先拆 `NavigationTaskController` 的 `localization_filter.py`、`static_task_runner.py`、`event_task_runner.py`，因为已有 `NavigationUpdateContext` 和 `intent_factory.py` 作为支点。
- 更高风险的 `NavigationCore.localize()` 和 `MapStitcher.add_frame()` 主算法拆分，应分成单独窄任务处理。

## [SYNC-NAVCORE] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/navigation_core.py`（原因：用户明确追问该文件是否可以拆分；它仍承载定位主算法、模板匹配、视觉一致性检查和定位状态写入）
- `core/localization/*.py`（原因：确认当前已抽出的定位模块边界，避免重复抽象）
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`、`architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`（原因：本轮只同步中文文档）

**本轮想弄清楚：**

- `NavigationCore` 哪些逻辑可以继续拆为无状态 helper，且不破坏 `from core.navigation_core import NavigationCore` 和 GUI 对运行时字段的直接访问。
- `localize()` 中哪些状态写入必须暂留门面，避免一次性重写定位行为。
- 是否可以新增更细的 `core.localization` 模块来承接视觉一致性、模板预处理、搜索窗口和配准构建逻辑。

### C. 本轮发现

关键发现：

- (verified) `NavigationCore` 可以继续拆，但不能把旧文件改成简单 proxy；GUI/任务层仍读取 `draw_scale`、`nav_wall_layer`、`explored_map`、`crop_offset`、`current_pos`、`last_good_pos`、`drawing_saved_pos`、`last_frame_registration` 等运行时字段。
- (verified) 已新增 `core/localization/frame_registration.py`，承接 `FrameRegistration` 有效/无效对象构建；`NavigationCore._clear_frame_registration()` 和 `_set_frame_registration()` 保留原私有入口，只做委托。
- (verified) 已新增 `core/localization/frame_matcher.py`，承接墙体模板按 `draw_scale` 放大、闭运算标准化、local/full 搜索窗口选择；真正的 `cv2.matchTemplate()` 调用、置信度判断、jump rejection 和状态写入仍保留在 `NavigationCore.localize()`。
- (verified) 已新增 `core/localization/visual_check.py`，承接 F2F 分支的局部视觉一致性复核，并继续返回 `visual_*` metadata 给 frame registration。
- (verified) `NavigationCore.localize()` 仍保留 recognizer 调用、F2F 接受/拒绝、forced relocalization flag 消费、`current_pos/last_good_pos/is_localized/prev_mask/prev_wall_mask/last_frame_registration` 写入，避免一次性行为重写。

代码变更：

- `core/navigation_core.py`
- `core/localization/__init__.py`
- `core/localization/frame_registration.py`
- `core/localization/frame_matcher.py`
- `core/localization/visual_check.py`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | 本轮精读定位主链，抽出 frame registration、template preparation/search-window 和 visual check；状态写入仍保留 facade。 |
| `core/localization/frame_registration.py` | 新增 | 深度完整 | 1 | 只构建 `FrameRegistration`，不写 `nav_core`。 |
| `core/localization/frame_matcher.py` | 新增 | 深度完整 | 1 | 承接 wall mask scale/close 和 full/local search area 选择，不承担结果接受。 |
| `core/localization/visual_check.py` | 新增 | 深度完整 | 1 | 承接 F2F visual consistency 局部模板复核和 metadata 生成。 |
| `core/localization/__init__.py` | 浅读 | 深度完整 | 追加 | 新增定位 helper 包级导出。 |

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\localization\frame_registration.py core\localization\frame_matcher.py core\localization\visual_check.py`
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\localization\__init__.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_core import NavigationCore; from core.localization.frame_registration import build_frame_registration, clear_frame_registration; from core.localization.frame_matcher import scale_wall_template, select_template_search_area; from core.localization.visual_check import visual_check_position; print('ok')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.localization import build_frame_registration, scale_wall_template, visual_check_position; print('ok')"`

下一轮建议：

- 如果继续拆 `NavigationCore`，优先抽“template match result 数据对象 + 结果解析 helper”，但仍让 facade 负责状态写入。
- 暂不抽 `tracking_state.py`，因为 forced relocalization、F2F、jump rejection 和诊断 metadata 当前交织在同一帧生命周期里，直接抽状态对象更容易引入行为偏差。

## [SYNC-MOTION] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/motion_controller.py`（原因：用户确认希望把 core 中“一个类里很多函数”的实现按功能拆出，再由类导入委托；该文件的输入执行链路比建图配准风险低，适合先拆）
- `core/input/*.py`（原因：确认已有 input 系统边界，避免把点击执行/诊断 helper 放错层）
- `CODEBASE.md`、`architecture_docs/zh-CN/core/ARCHITECTURE.md`、`architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`（原因：本轮只同步中文文档）

**本轮想弄清楚：**

- `MotionController` 哪些方法是外部 interface，必须保留在原 class。
- `_execute_click()` 中哪些内部阶段可以拆成 input helper：窗口诊断、后端发送点击、屏幕边界/保护处理。
- 如何在不改变真实输入行为的前提下，让 `motion_controller.py` 变薄。

### C. 本轮发现

关键发现：

- (verified) `MotionController` 的公开 interface 应保留：`set_params()`、`set_control_enabled()`、`move_to_map_target()`、`click_map_target_once()`、`click_screen_position()`、`press_key()` 和 `last_click_info` 字段。
- (verified) `_execute_click()` 可以拆内部阶段，但应继续留在 facade 中编排顺序：bottom guard -> optional clamp -> diagnostics -> optional focus -> send click -> cursor after -> fallback。
- (verified) 已新增 `core/input/click_executor.py`，承接 Win32/pydirectinput 点击发送和 confirm click。
- (verified) 已新增 `core/input/click_diagnostics.py`，承接 target/foreground window、ClipCursor、Win32 cursor、window info formatting。
- (verified) 已新增 `core/input/screen_bounds.py`，承接 screen height 解析和可选 coordinate clamp。
- (verified) `MotionController._send_click()`、`_clamp_screen_pos()`、`_screen_height()`、`_format_window_info()` 保留为兼容 wrapper，内部委托 helper。

代码变更：

- `core/motion_controller.py`
- `core/input/__init__.py`
- `core/input/click_executor.py`
- `core/input/click_diagnostics.py`
- `core/input/screen_bounds.py`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | (partial) | 追加 | 本轮拆出真实点击发送、窗口诊断和屏幕边界 helper；公开输入 interface 和 `last_click_info` 契约不改。 |
| `core/input/click_executor.py` | 新增 | 深度完整 | 1 | 只发送鼠标点击并返回 backend metadata，不写 controller 状态。 |
| `core/input/click_diagnostics.py` | 新增 | 深度完整 | 1 | 只做 best-effort driver 诊断和日志格式化，不执行点击。 |
| `core/input/screen_bounds.py` | 新增 | 深度完整 | 1 | 只做 screen height 解析和坐标 clamp 纯计算。 |
| `core/input/__init__.py` | 浅读 | 深度完整 | 追加 | 新增 input helper 包级导出。 |

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\motion_controller.py core\input\__init__.py core\input\click_executor.py core\input\click_diagnostics.py core\input\screen_bounds.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.motion_controller import MotionController; from core.input import send_click, collect_window_diagnostics, clamp_screen_pos; print('ok')"`

下一轮建议：

- 可以继续拆 `core/stitcher_core.py`，但先抽低风险的 `mapping/frame_preparation.py`（首帧/普通帧 mask scale、wall thickness 标准化）和 `mapping/performance.py`（`PerformanceMonitor`/`Timer`），不要先重写 keyframe/F2F 配准主流程。

## [SYNC-STITCHER] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/stitcher_core.py`（原因：用户希望 core 中大类内部函数按功能拆出；该文件仍包含性能工具、mask 准备、首帧放置和 keyframe/F2F 主流程）
- `core/mapping/*.py`（原因：确认已有 mapping helper，继续放入同一系统包）
- `CODEBASE.md`、`architecture_docs/zh-CN/core/ARCHITECTURE.md`、`architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`（原因：本轮只同步中文文档）

**本轮想弄清楚：**

- `MapStitcher` 哪些方法是外部 interface，必须保留在原 class。
- 哪些 helper 可以先拆出而不碰 keyframe/F2F 配准行为。
- 如何让 `stitcher_core.py` 变薄，同时继续保留 `MapStitcher.add_frame()` 的状态写入主流程。

### C. 本轮发现

关键发现：

- (verified) `MapStitcher` 公开入口仍应保留：`set_params()`、`get_params()`、`reinitialize_canvas()`、`save_map_package()`、`load_map_package()`、`add_frame()`、`get_cropped_map()`、`get_enhanced_map()`。
- (verified) `add_frame()` 中 keyframe/F2F 配准决策、`current_x/current_y`、`keyframe_mask/prev_mask`、stats 写入仍留在 facade，避免一次性改变建图轨迹。
- (verified) 已新增 `core/mapping/performance.py`，承接 `PerformanceMonitor` 和 `Timer`。
- (verified) 已新增 `core/mapping/frame_preparation.py`，承接 `save_mask/fog_mask` scale、wall thickness 标准化、player local pos scale、IoU 相似度、canvas bounds 判断。
- (verified) `MapStitcher._place_first_frame()`、`standardize_wall_thickness()`、`_is_too_similar()`、`_check_bounds()` 保留为兼容 wrapper，内部委托 helper；`weighted_merge.py` 继续可调用 `stitcher._is_too_similar()`。

代码变更：

- `core/stitcher_core.py`
- `core/mapping/__init__.py`
- `core/mapping/performance.py`
- `core/mapping/frame_preparation.py`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/stitcher_core.py` | (partial) | (partial) | 追加 | 本轮拆出 performance 和 frame preparation；keyframe/F2F 主流程仍留在 `add_frame()`。 |
| `core/mapping/performance.py` | 新增 | 深度完整 | 1 | 承接 rolling timing collector 和 context timer。 |
| `core/mapping/frame_preparation.py` | 新增 | 深度完整 | 1 | 承接 frame masks scale、wall close、player scale、IoU 去重和 bounds 纯计算。 |
| `core/mapping/__init__.py` | 浅读 | 深度完整 | 追加 | 新增 mapping helper 包级导出。 |

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\stitcher_core.py core\mapping\__init__.py core\mapping\performance.py core\mapping\frame_preparation.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.stitcher_core import MapStitcher, PerformanceMonitor, Timer; from core.mapping import prepare_scaled_frame_masks, standardize_wall_thickness, is_too_similar; print('ok')"`

下一轮建议：

- 下一步若继续 `stitcher_core.py`，可以抽 `mapping/registration.py`，但必须只返回结构化 `RegistrationResult`，由 `MapStitcher.add_frame()` 继续写状态。
- 或者继续拆 `navigation_tasks/controller.py` 的 localization filter / static runner / event runner，风险低于重写建图配准。

## [SYNC-FACADE-THINNING] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/motion_controller.py`（原因：用户指出 facade 仍有 300+ 行，需要继续反复抽取）
- `core/input/*.py`（原因：把点击流程编排放入 input 分类模块）
- 后续视验证结果再处理 `core/stitcher_core.py`

**本轮想弄清楚：**

- 如何把 `_execute_click()` 的完整点击 pipeline 移出 `MotionController`，同时保留旧私有方法入口。
- 如何确保 `last_click_info` 字段结构、日志内容、fallback 行为不变。

### C. 本轮发现

关键发现：

- (verified) 已新增 `core/input/click_pipeline.py`，承接 `MotionController._execute_click()` 的 bottom guard、clamp、diagnostics、focus、send click、cursor-after 和 fallback 顺序。
- (verified) `MotionController._execute_click()` 保留旧私有入口，内部只委托 `execute_click(self, screen_pos)`；`motion_controller.py` 从 331 行降到 246 行。
- (verified) 已新增 `core/mapping/frame_pipeline.py`，承接 `MapStitcher.add_frame()` 的 keyframe/F2F 配准、低质量跳过、落图和 match_rate 更新。
- (verified) `MapStitcher.add_frame()` 保留旧公开入口，内部只委托 `add_frame_to_stitcher()`；`stitcher_core.py` 从 388 行降到 224 行。
- (verified) 这次开始抽“流程编排”，不是只抽纯算法；但仍保留 facade class 和旧方法名，外部调用不需要迁移。

代码变更：

- `core/motion_controller.py`
- `core/input/__init__.py`
- `core/input/click_pipeline.py`
- `core/stitcher_core.py`
- `core/mapping/__init__.py`
- `core/mapping/frame_pipeline.py`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\motion_controller.py core\input\__init__.py core\input\click_pipeline.py core\stitcher_core.py core\mapping\__init__.py core\mapping\frame_pipeline.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.motion_controller import MotionController; from core.input import execute_click; from core.stitcher_core import MapStitcher; from core.mapping import add_frame_to_stitcher; print('ok')"`

下一轮建议：

- 继续按同一模式处理 `navigation_tasks/controller.py` 或 `navigation_core.py`：每次只抽一个 pipeline/helper，旧类旧方法名留壳。

## [SYNC-METHOD-AND-LOCALIZE] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md`（原因：用户要求先沉淀这种反复分类抽取方法论）
- `core/navigation_core.py`（原因：继续把长 facade 方法变薄）
- `core/localization/*.py`（原因：把 `NavigationCore.localize()` 主流程归入 localization 系统包）

**本轮想弄清楚：**

- 如何把 `NavigationCore.localize()` 主流程搬到 pipeline helper，同时保留旧公开入口。
- 如何避免改变 F2F、template match、forced relocalization、jump rejection 和 frame registration 行为。

### C. 本轮发现

关键发现：

- (verified) 已新增 `architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md`，沉淀“旧入口保留、分类 helper、小步抽取、pipeline helper、每轮验证”的方法论。
- (verified) 已新增 `core/localization/localize_pipeline.py`，承接 `NavigationCore.localize()` 的 F2F、模板匹配、forced relocalization、jump rejection、frame registration 和定位状态写入。
- (verified) `NavigationCore.localize()` 保留旧公开入口，内部只委托 `localize_frame(self, minimap_img, player_pos=player_pos)`；`navigation_core.py` 当前 222 行。
- (verified) `NavigationCore` 的外部字段和调用面不变，GUI/任务层仍通过原对象读取 `current_pos/last_good_pos/last_frame_registration` 等字段。

代码变更：

- `core/navigation_core.py`
- `core/localization/__init__.py`
- `core/localization/localize_pipeline.py`
- `architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\localization\__init__.py core\localization\localize_pipeline.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_core import NavigationCore; from core.localization import localize_frame; print('ok')"`

下一轮建议：

- 继续处理 `core/navigation_tasks/controller.py`：按方法论抽 `update_pipeline.py` 或拆 `localization_filter.py`、`static_task_runner.py`、`event_task_runner.py`，旧 `NavigationTaskController.update()` 留壳。

## [SYNC-NAVTASKS-CONTROLLER] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/navigation_tasks/controller.py`（原因：当前 core 最长 facade 文件之一，523 行；适合按方法论继续抽 pipeline）
- `core/navigation_tasks/update_context.py`、`intent_factory.py`（原因：已有 context 和 intent helper，可承接 update pipeline）

**本轮想弄清楚：**

- 如何把 `NavigationTaskController.update_context()` 主流程搬到 `update_pipeline.py`。
- 如何保留旧 `update(**kwargs)` 和 `update_context(context)` 调用面。

### C. 本轮发现

关键发现：

- (verified) 已新增 `core/navigation_tasks/update_pipeline.py`，承接 `NavigationTaskController.update_context()` 主调度流程；旧 `update_context()` 只委托。
- (verified) 已新增 `core/navigation_tasks/static_task_runner.py`，承接 required/exit 静态任务处理。
- (verified) 已新增 `core/navigation_tasks/event_task_runner.py`，承接 event approach、`EventCoordinator.run_task()` 和 `EventAction -> NavigationIntent` 处理。
- (verified) 已新增 `core/navigation_tasks/controller_utils.py`，承接坐标格式化和 forced relocalization 判定；旧私有 helper 名保留 wrapper。
- (verified) `controller.py` 从 523 行降到 257 行；`update(**kwargs)` 和 `update_context(context)` 调用面不变。

代码变更：

- `core/navigation_tasks/controller.py`
- `core/navigation_tasks/__init__.py`
- `core/navigation_tasks/update_pipeline.py`
- `core/navigation_tasks/controller_utils.py`
- `core/navigation_tasks/static_task_runner.py`
- `core/navigation_tasks/event_task_runner.py`

更新文档：

- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：

- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\update_pipeline.py core\navigation_tasks\controller_utils.py core\navigation_tasks\static_task_runner.py core\navigation_tasks\event_task_runner.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.controller import NavigationTaskController; from core.navigation_tasks.update_pipeline import update_controller_context; from core.navigation_tasks.static_task_runner import update_static_task; from core.navigation_tasks.event_task_runner import update_event_task; print('ok')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks import NavigationTaskController, update_controller_context, update_static_task, update_event_task; print('ok')"`

下一轮建议：

- 下一个长文件建议处理 `core/navigation_tasks/movement_executor.py` 或 `core/vision/hsv_recognizer.py`。优先 `movement_executor.py`，因为同属 navigation task 系统，能继续按 runner/pipeline 拆。

## [SYNC-MOVEMENT-EXECUTOR] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/navigation_tasks/movement_executor.py`（原因：当前 413 行，是 navigation task 系统内剩余长文件；适合继续按方法论拆）
- `core/navigation_tasks/*` 相邻 helper（原因：保持 movement、route_context、intent runner 的职责边界清晰）

**本轮想弄清楚：**

- `MovementExecutor.step()` 内哪些流程可以搬到 pipeline helper。
- 哪些纯计算 helper 可以先拆出，保留旧私有方法名作为 wrapper。

### C. 本轮发现

关键发现：
- (verified) `MovementExecutor` 的外部稳定入口应保留：`step()`、`record_click()`，以及旧私有兼容入口 `_ensure_path()`、`_plan_path()`、`_anchors_for_path()`、`_active_path_goal_pending()`、`_should_use_exact_path_goal_click()`、`_active_recovery_target()`、`_local_probe()`、`_is_stuck()`、`_recovery_probe()`。
- (verified) 已新增 `core/navigation_tasks/movement_pipeline.py`，承接 `MovementExecutor.step()` 的单帧移动主流程：路径确保、路径投影、lookahead 子目标、exact path-goal click、click cooldown、卡住恢复和 `MovementStep` 返回。
- (verified) 已新增 `movement_path_maintenance.py`，承接路径是否重规划、路径状态写回和 `nav movement planned` 日志。
- (verified) 已新增 `movement_path_planner.py`，承接 anchor-aware A*、direct A* 和 fallback probe 路径选择，依赖方向改为 `core.routing.anchors` / `core.routing.geometry`。
- (verified) 已新增 `movement_recovery.py` 和 `movement_utils.py`，分别承接 local/recovery probe、stuck progress window 和坐标标准化。
- (verified) `movement_executor.py` 从 413 行左右降到 178 行，旧 class 和旧方法名仍在，外部 `from core.navigation_tasks.movement_executor import MovementExecutor` 不变。
- (verified) `core/navigation_tasks/__init__.py` 增加 `MovementExecutor` 和 movement helper 包级导出，便于后续复用而不绕回私有文件。

代码变更：
- `core/navigation_tasks/movement_executor.py`
- `core/navigation_tasks/__init__.py`
- `core/navigation_tasks/movement_pipeline.py`
- `core/navigation_tasks/movement_path_planner.py`
- `core/navigation_tasks/movement_path_maintenance.py`
- `core/navigation_tasks/movement_recovery.py`
- `core/navigation_tasks/movement_utils.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/movement_executor.py` | (partial) | 深度完整 | 追加 | 已确认所有旧入口保留为 facade wrapper，真实 movement 流程拆到 helper。 |
| `core/navigation_tasks/movement_pipeline.py` | 新增 | 深度完整 | 1 | 承接 `step()` 单帧移动编排，不直接执行真实输入。 |
| `core/navigation_tasks/movement_path_maintenance.py` | 新增 | 深度完整 | 1 | 承接重规划判定、路径状态写回和规划日志。 |
| `core/navigation_tasks/movement_path_planner.py` | 新增 | 深度完整 | 1 | 承接 anchor-aware A*、direct A* 和 fallback path 选择。 |
| `core/navigation_tasks/movement_recovery.py` | 新增 | 深度完整 | 1 | 承接 local probe、recovery probe 和卡住进度判定。 |
| `core/navigation_tasks/movement_utils.py` | 新增 | 深度完整 | 1 | 承接坐标标准化。 |
| `core/navigation_tasks/__init__.py` | 深度完整 | 深度完整 | 追加 | 增加 `MovementExecutor` 和 movement helper 包级导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\__init__.py core\navigation_tasks\movement_executor.py core\navigation_tasks\movement_pipeline.py core\navigation_tasks\movement_path_planner.py core\navigation_tasks\movement_path_maintenance.py core\navigation_tasks\movement_recovery.py core\navigation_tasks\movement_utils.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks import MovementExecutor, movement_step, plan_movement_path, ensure_movement_path, local_probe, recovery_probe; from core.navigation_tasks.movement_executor import MovementExecutor as OldPath; print('ok')"`

下一轮建议：
- 继续同样方法处理剩余长文件，优先 `core/navigation_tasks/event_approach.py` 或 `core/navigation_tasks/coordinate_diagnostics.py`；若想先清算法层，也可以处理 `core/vision/hsv_recognizer.py`。`coordinate_diagnostics.py` 状态机较深，建议先读完整函数体再拆。

## [SYNC-COORDINATE-DIAGNOSTICS] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/navigation_tasks/coordinate_diagnostics.py`（原因：当前 core 中最长实现文件之一，包含坐标漂移诊断、证据评分、日志记录和 relocalization request 状态；适合按 facade extraction 方法继续拆，但必须保守处理触发语义。）
- `core/navigation_tasks/*diagnostic*` 相邻 helper（原因：如需抽取，保持在 navigation_tasks 内，不让 diagnostics 反向依赖 GUI/input/events 具体实现。）

**本轮想弄清楚：**

- 哪些部分只是日志 payload/坐标格式化/证据提取，可以先抽为低风险 helper。
- 哪些部分是恢复触发策略和 request 状态机，应该暂时留在 facade 或只抽纯判定函数。

### C. 本轮发现

关键发现：
- (verified) `CoordinateDiagnostics` 的 public 入口只有 `reset()`、`record_session_start()`、`record_localization()`、`record_navigation_state()`、`consume_relocalization_request()`、`mark_relocalization_accepted()`；controller 仍只通过这些入口交互。
- (verified) 已新增 `coordinate_localization.py`，承接定位帧诊断、registration source tracking、raw jump、raw/control gap、long F2F tracking 和 visual mismatch 证据。
- (verified) 已新增 `coordinate_navigation.py`，承接 route deviation、arrival mismatch 和 near-target stall 诊断；这些仍只写日志，不触发强制重定位。
- (verified) 已新增 `coordinate_relocalization.py`，承接 request consume/accept/reject、recovery signal scoring 和 primary signal gate；触发语义保持只有 `visual_mismatch` 与 F2F 下 `raw_jump` 可触发。
- (verified) 已新增 `coordinate_log.py`、`coordinate_formatting.py`、`coordinate_models.py`，把文件日志副作用、registration/字段格式化和 DTO 从 facade 中拆出。
- (verified) `coordinate_diagnostics.py` 从 582 行左右降到 228 行；旧私有 helper 名 `_registration_fields()`、`_float_point_or_none()`、`_distance()`、`_format_fields()`、`_format_value()` 仍保留为 wrapper。

代码变更：
- `core/navigation_tasks/coordinate_diagnostics.py`
- `core/navigation_tasks/coordinate_models.py`
- `core/navigation_tasks/coordinate_formatting.py`
- `core/navigation_tasks/coordinate_log.py`
- `core/navigation_tasks/coordinate_localization.py`
- `core/navigation_tasks/coordinate_navigation.py`
- `core/navigation_tasks/coordinate_relocalization.py`
- `core/navigation_tasks/__init__.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | (partial) | 深度完整 | 追加 | 已保留 stateful facade 和旧 helper wrapper，诊断/请求生命周期外移。 |
| `core/navigation_tasks/coordinate_localization.py` | 新增 | 深度完整 | 1 | 承接定位证据、F2F tracking age、visual mismatch 计数和 raw jump 信号。 |
| `core/navigation_tasks/coordinate_navigation.py` | 新增 | 深度完整 | 1 | 承接 route/task 诊断日志，不触发 relocalization。 |
| `core/navigation_tasks/coordinate_relocalization.py` | 新增 | 深度完整 | 1 | 承接 request 生成、消费、接受、拒绝和 primary signal gate。 |
| `core/navigation_tasks/coordinate_log.py` | 新增 | 深度完整 | 1 | 只写 `logs/coordinate_diagnostics.log`，不污染 console/runtime log。 |
| `core/navigation_tasks/coordinate_formatting.py` | 新增 | 深度完整 | 1 | 承接 registration fields、坐标解析、距离和日志格式化。 |
| `core/navigation_tasks/coordinate_models.py` | 新增 | 深度完整 | 1 | 承接 `CoordinateRelocalizationRequest` 数据契约。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\coordinate_models.py core\navigation_tasks\coordinate_formatting.py core\navigation_tasks\coordinate_log.py core\navigation_tasks\coordinate_localization.py core\navigation_tasks\coordinate_navigation.py core\navigation_tasks\coordinate_relocalization.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.coordinate_diagnostics import CoordinateDiagnostics, CoordinateRelocalizationRequest, coord_log, _registration_fields, _float_point_or_none; from core.navigation_tasks.coordinate_localization import record_localization_diagnostics; from core.navigation_tasks.coordinate_navigation import record_navigation_diagnostics; from core.navigation_tasks.coordinate_relocalization import register_recovery_signal; d=CoordinateDiagnostics(); d.reset(); print('ok')"`

下一轮建议：
- 继续处理 `core/vision/hsv_recognizer.py` 或 `core/events/types/portal/minimap_shape_color_matcher.py`。如果继续 navigation_tasks，同目录剩余长文件 `event_approach.py` 可按 phase/policy/helper 方式拆，但要保持 event approach gate 释放语义不变。

## [SYNC-HSV-RECOGNIZER] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**

- `core/vision/hsv_recognizer.py`（原因：当前 core 最长实现文件，承接 wall/fog/player HSV 识别、动态过滤、预处理和 combined mask 输出；适合按 vision 子系统拆分低风险 helper。）
- `core/vision/*` 相邻 helper（原因：识别算法应留在 vision 包，不反向依赖 mapping/localization/GUI/input。）

**本轮想弄清楚：**

- `HSVRecognizer` 哪些方法是外部稳定入口，必须保留在原 class。
- 哪些函数是纯图像预处理、HSV range/mask、动态对象过滤或 player detection helper，可以拆出而不改变识别阈值语义。

### C. 本轮发现

关键发现：
- (verified) `HSVRecognizer` 的公开方法 `get_params()`、`set_params()`、`preprocess_image()`、`get_raw_gray()`、`extract_walls()`、`extract_fog()`、`extract_player()`、`extract_combined()`、`get_preprocessed_image()` 均保留在 `core/vision/hsv_recognizer.py`，旧 `core.recognizer_optimized.HSVRecognizer` 仍可通过 wrapper 使用。
- (verified) `hsv_params.py` 承接参数快照和 `set_params()` 字段应用，包含 CLAHE 重建、kernel 重建和 player clear radius 非负化。
- (verified) `hsv_preprocessing.py` 承接透明地图 score、wall/fog 预处理和 raw gray matching helper；透明模式的 TopHat/饱和度惩罚语义未改。
- (verified) `hsv_masks.py` 承接 wall/fog/player mask 和小连通域过滤，`enable_wall`、`enable_fog` 的全零降级语义未改。
- (verified) `hsv_combined.py` 承接 combined pipeline：wall/fog 提取、Canny edges、动态彩色区域清理、玩家圆形清理和 weighted match mask 融合。
- (verified) `hsv_recognizer.py` 从长实现文件降为 110 行 facade；新 helper 均在 `core.vision` 内，不反向依赖 mapping/localization/GUI/input。

代码变更：
- `core/vision/hsv_recognizer.py`
- `core/vision/hsv_params.py`
- `core/vision/hsv_preprocessing.py`
- `core/vision/hsv_masks.py`
- `core/vision/hsv_combined.py`
- `core/vision/__init__.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/vision/hsv_recognizer.py` | (partial) | 深度完整 | 追加 | 已确认旧 class/method surface 保留，真实实现改为参数/预处理/mask/combined helper 委托。 |
| `core/vision/hsv_params.py` | 新增 | 深度完整 | 1 | 承接参数导出和应用，重点是 CLAHE 与 morphology kernel 状态同步。 |
| `core/vision/hsv_preprocessing.py` | 新增 | 深度完整 | 1 | 承接 transparent score、wall/fog 预处理和 raw gray，保持 OpenCV 降级路径。 |
| `core/vision/hsv_masks.py` | 新增 | 深度完整 | 1 | 承接 wall/fog/player 二值 mask 生成和小连通域过滤。 |
| `core/vision/hsv_combined.py` | 新增 | 深度完整 | 1 | 承接配准特征组合、动态色彩清理和玩家附近清理。 |
| `core/vision/__init__.py` | 深度完整 | 深度完整 | 追加 | 增加 HSV helper 包级导出，旧 `HSVRecognizer` 仍在同包入口可用。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\vision\hsv_recognizer.py core\vision\hsv_params.py core\vision\hsv_preprocessing.py core\vision\hsv_masks.py core\vision\hsv_combined.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from core.vision.hsv_recognizer import HSVRecognizer; r=HSVRecognizer(); img=np.zeros((32,32,3), dtype=np.uint8); masks=r.extract_combined(img); assert len(masks)==3 and all(m.shape==(32,32) for m in masks); assert r.get_raw_gray(img).shape==(32,32); print('ok')"`

下一轮建议：
- 继续处理 `core/navigation_tasks/event_approach.py`，该文件仍是 navigation task 子系统内较长的状态机文件，适合按“阶段/策略/状态写回”抽取，且要保持 event approach gate 释放语义不变。

## [SYNC-EVENT-APPROACH] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/navigation_tasks/event_approach.py`（原因：navigation_tasks 内剩余长文件之一，承接 event target approach 的阶段状态、距离判定、点击释放、settle/release gate 和调试输出；适合按策略/阶段 helper 拆分，但必须保持旧类和旧方法入口。）
- `core/navigation_tasks/controller.py`、`event_task_runner.py` 相邻调用方（原因：确认外部如何调用 event approach，避免拆分后破坏 task runner 到 approach 状态机的契约。）

**本轮想弄清楚：**
- `EventApproachController` 的公开入口、私有 helper 和状态字段分别由谁调用。
- 哪些函数是纯距离/阶段/日志/intent 构建 helper，可低风险抽出；哪些地方会写状态、释放 event gate 或触发 click，必须保留语义不变。

### C. 本轮发现

关键发现：
- (verified) 外部调用面集中在 `event_task_runner.update_event_task()`：先检查 `event_approach.is_released(task.id)`，未释放时调用 `update()`；ready 后调用 `release_task()`，随后才运行 `event_coordinator.run_task()`。
- (verified) `EventApproachController` 的稳定入口是 `configure()`、`reset()`、`reset_active()`、`finish_task()`、`is_released()`、`release_task()`、`update()`；这些入口全部保留在 `event_approach.py`。
- (verified) 事件靠近主流程已抽到 `event_approach_pipeline.py`，保持原有 far -> approach -> settling -> ready 阶段语义；far 阶段继续使用 route context，approach 阶段继续禁用 route context 并使用短 lookahead。
- (verified) movement step 到 intent 的转换已抽到 `event_approach_motion.py`；`step is None` 仍返回 wait intent，`step.should_click and step.subgoal` 仍返回 MOVE_MAP。
- (verified) 停稳 gate 已抽到 `event_approach_settle.py`；ready 条件仍是 `waited_ms >= settle_ms` 且 `stable_frames >= stable_frames`。
- (verified) 真实视野盒和终点前停靠点插值已抽到 `event_approach_geometry.py`；旧 `_float_point()`、`_int_point()` 私有 helper 仍保留为 wrapper。
- (verified) `event_approach.py` 从 360 行降为 145 行；不改变 event handler 调用时机，不引入 hook。

代码变更：
- `core/navigation_tasks/event_approach.py`
- `core/navigation_tasks/event_approach_models.py`
- `core/navigation_tasks/event_approach_geometry.py`
- `core/navigation_tasks/event_approach_motion.py`
- `core/navigation_tasks/event_approach_settle.py`
- `core/navigation_tasks/event_approach_pipeline.py`
- `core/navigation_tasks/__init__.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/event_approach.py` | (partial) | 深度完整 | 追加 | 已保留 `EventApproachController` facade 和旧私有 helper wrapper，主流程移出。 |
| `core/navigation_tasks/event_approach_models.py` | 新增 | 深度完整 | 1 | 承接 `EventApproachConfig` 和 `EventApproachResult`。 |
| `core/navigation_tasks/event_approach_pipeline.py` | 新增 | 深度完整 | 1 | 承接 far/approach/settling/ready 主流程和 movement force-replan 写入。 |
| `core/navigation_tasks/event_approach_motion.py` | 新增 | 深度完整 | 1 | 承接 movement step 到 NavigationIntent 转换。 |
| `core/navigation_tasks/event_approach_settle.py` | 新增 | 深度完整 | 1 | 承接停稳计时、稳定帧、ready 判定和 settling intent。 |
| `core/navigation_tasks/event_approach_geometry.py` | 新增 | 深度完整 | 1 | 承接真实视野盒、停靠点插值和坐标格式化。 |
| `core/navigation_tasks/__init__.py` | 深度完整 | 深度完整 | 追加 | 增加 EventApproach DTO/controller 包级导出，不破坏原导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\event_approach.py core\navigation_tasks\event_approach_models.py core\navigation_tasks\event_approach_geometry.py core\navigation_tasks\event_approach_motion.py core\navigation_tasks\event_approach_settle.py core\navigation_tasks\event_approach_pipeline.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.event_approach import EventApproachController, EventApproachConfig, EventApproachResult, _float_point, _int_point; c=EventApproachController(); c.configure(enabled=True); assert _float_point((1,2))==(1.0,2.0); assert _int_point((1.2,2.6))==(1,3); print('ok')"`

下一轮建议：
- 继续清理 core 中剩余较长文件。若保持 navigation_tasks 范围，下一步可处理 `controller.py` 剩余定位过滤/required progress helper；若转向 events，优先 `core/events/types/portal/minimap_shape_color_matcher.py` 或 `core/events/memory.py`。

## [SYNC-PORTAL-SHAPE-COLOR-MATCHER] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/events/types/portal/minimap_shape_color_matcher.py`（原因：当前 core 最长文件之一，承担 portal 小地图形状+颜色联合匹配；属于算法文件，适合单独一轮精读后按 mask/candidate/scoring/debug 拆分。）
- `core/events/types/portal/minimap_detector.py`、相关 probe 调用方（原因：确认 matcher 对外入口和 debug payload 契约，避免拆分后破坏 portal detector。）

**本轮想弄清楚：**
- matcher 当前导出的函数/数据结构有哪些，谁在调用。
- 哪些部分是纯 mask 构建、候选提取、候选评分、候选去重、debug artifact，可拆成 helper；哪些阈值和返回 payload 是外部调参/诊断依赖，必须保持不变。

### C. 本轮发现

关键发现：
- (verified) 运行时外部调用面是 `PortalMinimapDetector._detect_shape_color_hits()` 导入 `PortalShapeColorParams` 和 `match_portal_shape_color()`；离线探针 `utils/event_icon_probe.py` 也导入这两个入口。
- (verified) 旧 `minimap_shape_color_matcher.py` 已降为 70 行 compatibility facade，继续导出 `PortalShapeColorParams`、`PortalShapeColorHit`、`PortalShapeColorDebug`、`portal_blue_mask()`、`portal_outer_mask()`、`match_portal_shape_color()`、`merge_shape_color_hits()`，并保留原私有 `_prepare_template()`、`_combined_response()`、`_evaluate_candidate()` 等 wrapper。
- (verified) 新增 `minimap_shape_color_models.py` 承接参数、命中、debug mask、prepared template DTO；数据字段和命中 `center` property 未改。
- (verified) 新增 `minimap_shape_color_masks.py` 承接蓝色核心 mask、白/灰外环 mask、BGR/HSV 转换和缩放。
- (verified) 新增 `minimap_shape_color_templates.py` 承接模板缩放、alpha mask 应用、shape mask 和 Canny edge 准备。
- (verified) 新增 `minimap_shape_color_scoring.py` 承接 response map、F1-like score、HSV color score、signature score 和 reject reasons。
- (verified) 新增 `minimap_shape_color_pipeline.py` 承接 frame mask 构建、模板/scale 遍历、宽松候选收集和候选去重。
- (verified) 阈值、权重、reject reason 字符串、accepted 排序优先级和 debug masks 返回契约保持不变。

代码变更：
- `core/events/types/portal/minimap_shape_color_matcher.py`
- `core/events/types/portal/minimap_shape_color_models.py`
- `core/events/types/portal/minimap_shape_color_masks.py`
- `core/events/types/portal/minimap_shape_color_templates.py`
- `core/events/types/portal/minimap_shape_color_scoring.py`
- `core/events/types/portal/minimap_shape_color_pipeline.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_shape_color_matcher.py` | (partial) | 深度完整 | 追加 | 已成为 compatibility facade，旧 public/private 函数名保留。 |
| `core/events/types/portal/minimap_shape_color_models.py` | 新增 | 深度完整 | 1 | 承接 shape-color 参数、命中、debug mask 和 prepared template DTO。 |
| `core/events/types/portal/minimap_shape_color_masks.py` | 新增 | 深度完整 | 1 | 承接蓝色核心、外环 mask、缩放和颜色空间转换。 |
| `core/events/types/portal/minimap_shape_color_templates.py` | 新增 | 深度完整 | 1 | 承接 template scale、alpha mask 应用和 edge mask 准备。 |
| `core/events/types/portal/minimap_shape_color_scoring.py` | 新增 | 深度完整 | 1 | 承接 response、F1-like 分数、HSV color score、signature score 和 reject reasons。 |
| `core/events/types/portal/minimap_shape_color_pipeline.py` | 新增 | 深度完整 | 1 | 承接主匹配流程和候选去重。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_shape_color_matcher.py core\events\types\portal\minimap_shape_color_models.py core\events\types\portal\minimap_shape_color_masks.py core\events\types\portal\minimap_shape_color_templates.py core\events\types\portal\minimap_shape_color_scoring.py core\events\types\portal\minimap_shape_color_pipeline.py core\events\types\portal\minimap_detector.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from pathlib import Path; from core.events.detectors.template_matcher import TemplateSpec; from core.events.types.portal.minimap_shape_color_matcher import PortalShapeColorParams, match_portal_shape_color, portal_blue_mask; frame=np.zeros((64,64,3), dtype=np.uint8); template=TemplateSpec(name='t', path=Path('t.png'), image=np.zeros((16,16,3), dtype=np.uint8), mask=None); hits, dbg = match_portal_shape_color(frame, [template], [1.0], top_k=2, params=PortalShapeColorParams()); assert dbg.frame_blue_mask.shape==(64,64); assert portal_blue_mask(frame).shape==(64,64); print('ok', len(hits))"`

下一轮建议：
- 继续处理 `core/events/memory.py`，它现在是 core 最长文件，且属于事件实例生命周期/去重/任务表状态管理；应先精读并优先抽 DTO/候选合并/任务清理 helper，不改变事件生命周期语义。

## [SYNC-EVENT-MEMORY] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/events/memory.py`（原因：当前 core 最长文件，负责事件 observation 合并、task 生命周期、去重、过期清理和 overlay 状态；风险较高，必须保留 public API 和事件生命周期语义。）
- `core/events/coordinator.py`、`core/navigation_tasks/task_builder.py` 相邻调用方（原因：确认 EventMemory 对 coordinator 和 navigation task builder 暴露的任务/状态契约。）

**本轮想弄清楚：**
- `EventMemory` 的公开方法和字段如何被 coordinator/navigation 使用。
- 哪些逻辑是纯定位/相似度/候选分配/过期判断/状态快照 helper，可抽出；哪些逻辑直接写 `tasks`、`observations`、`completed_task_ids`，需要保留在 facade 或通过窄 helper 写回。

### C. 本轮发现

关键发现：
- (verified) 外部调用面集中在 `EventCoordinator.observe()`、`EventCoordinator.tasks()`、`EventCoordinator.reset_event_type()` 和 `EventRunner.update()`；`NavigationTaskBuilder` 只读取 coordinator 暴露的 EventTask 列表。
- (verified) `EventMemory` public API 保留：`tasks()`、`active_tasks()`、`clear_event_type()`、`merge_observations()`、`mark_completed()`、`complete_teleport_session()`、`mark_related_completed()`、`suppress_nearby_pending()`、`mark_failed()`。
- (verified) `memory_merge.py` 承接 stable observation -> task 的合并、创建、seen 更新和 confirm frames；本帧 `touched_task_ids` 语义不变。
- (verified) `memory_lookup.py` 承接 task id 查找、dedupe 匹配、teleport exit task 查找、nearest task 和 completed/type cooldown 判定。
- (verified) `memory_completion.py` 承接 teleport session completion、related completed、nearby pending suppression 和 fail retry/ignore。
- (verified) `memory_utils.py` 承接距离、坐标标准化和日志节流；旧 `_distance()`、`_int_pos()` 仍保留 wrapper。
- (verified) `memory.py` 从 393 行降为 132 行；`_tasks`、`_next_id`、`_last_log_ms` 仍由 `EventMemory` 实例统一拥有。

代码变更：
- `core/events/memory.py`
- `core/events/memory_utils.py`
- `core/events/memory_lookup.py`
- `core/events/memory_merge.py`
- `core/events/memory_completion.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/memory.py` | (partial) | 深度完整 | 追加 | 已保留 EventMemory facade 和旧私有 wrapper，状态仍由 facade 拥有。 |
| `core/events/memory_merge.py` | 新增 | 深度完整 | 1 | 承接 observations 合并、task 创建/seen/confirm。 |
| `core/events/memory_lookup.py` | 新增 | 深度完整 | 1 | 承接 dedupe、exit/nearest 查找和 completed cooldown。 |
| `core/events/memory_completion.py` | 新增 | 深度完整 | 1 | 承接 teleport completion、related completion、nearby suppression、failure retry/ignore。 |
| `core/events/memory_utils.py` | 新增 | 深度完整 | 1 | 承接距离、坐标标准化和日志节流。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\memory.py core\events\memory_utils.py core\events\memory_lookup.py core\events\memory_merge.py core\events\memory_completion.py core\events\coordinator.py core\events\runner.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.memory import EventMemory, _distance, _int_pos; from core.events.models import EventObservation; C=type('C', (), {'event': lambda self, t: {'enabled': True, 'memory_confirm_frames': 1, 'cooldown_ms': 1000, 'cooldown_radius': 20}}); m=EventMemory(dedupe_radius=10); obs=EventObservation(event_type='portal', confidence=0.9, observed_at_ms=100, global_pos=(10,20), source='s'); m.merge_observations([obs], C(), 100); tasks=m.tasks(); assert len(tasks)==1 and tasks[0].state.value=='pending'; m.mark_completed(tasks[0], 200); m.merge_observations([obs], C(), 250); assert len(m.tasks())==1; assert round(_distance((0,0),(3,4)),1)==5.0 and _int_pos((1.2,2.8))==(1,2); print('ok')"`

下一轮建议：
- 继续处理 `core/navigation_tasks/controller.py` 或 `core/events/types/portal/minimap_detector.py`。如果继续事件系统，`minimap_detector.py` 可按 mode dispatch、hit-to-detection、logging helper 拆；如果回到 navigation_tasks，`controller.py` 可继续抽定位过滤/required progress。

## [SYNC-GROUP-HELPER-PACKAGES] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/memory*`（原因：上一轮拆成 `memory_*` 扁平 helper，需要收束到 `core/events/memory/` 子包，并保留 `core.events.memory.EventMemory` 导入面。）
- `core/navigation_tasks/event_approach*`、`movement_*`、`coordinate_*`（原因：同一 navigation task 能力组不应铺在目录根；应按 `event_approach/`、`movement/`、`coordinate/` 子包组织。）
- `core/vision/hsv_*`（原因：HSV 参数、预处理、mask、combined pipeline 是同一 recognizer 子模块，应收束到 `core/vision/hsv/`。）
- `core/events/types/portal/minimap_shape_color_*`（原因：shape-color matcher helper 是同一算法族，应收束到 `core/events/types/portal/minimap_shape_color/`。）

**本轮想弄清楚：**
- 哪些旧路径是外部稳定接口，必须保留 facade 或 package `__init__.py`。
- 哪些刚新增的 helper 可以直接迁入子包而不保留扁平 wrapper，避免继续污染目录根。

### C. 本轮发现

关键发现：
- (verified) `core/events/memory.py` 已收束为 `core/events/memory/__init__.py`，旧导入 `from core.events.memory import EventMemory` 继续可用；真实策略文件归组为 `memory/merge.py`、`memory/lookup.py`、`memory/completion.py`、`memory/utils.py`。
- (verified) `core/navigation_tasks/event_approach.py` 已收束为 `core/navigation_tasks/event_approach/__init__.py`，旧导入 `from core.navigation_tasks.event_approach import EventApproachController` 继续可用；真实阶段文件归组为 `event_approach/models.py`、`geometry.py`、`motion.py`、`settle.py`、`pipeline.py`。
- (verified) `MovementExecutor` 旧 facade 仍在 `movement_executor.py`；movement 算法文件已归组到 `core/navigation_tasks/movement/`，并通过 `movement/__init__.py` 提供 `movement_step`、`plan_movement_path` 等聚合导出。
- (verified) `CoordinateDiagnostics` 旧 facade 仍在 `coordinate_diagnostics.py`；coordinate 诊断文件已归组到 `core/navigation_tasks/coordinate/`，并通过 `coordinate/__init__.py` 导出 `CoordinateRelocalizationRequest` 等契约。
- (verified) HSV recognizer 的参数、预处理、mask、combined pipeline 已归组到 `core/vision/hsv/`；`core.vision.hsv_recognizer.HSVRecognizer` 和 `core.recognizer_optimized.HSVRecognizer` 仍是稳定入口。
- (verified) portal shape-color matcher 的 DTO、mask、template、scoring、pipeline 已归组到 `core/events/types/portal/minimap_shape_color/`；旧 `minimap_shape_color_matcher.py` 只保留 compatibility facade 和旧私有 wrapper。
- (verified) `core` 实现引用扫描没有发现旧扁平 helper 模块名的 import；残留主要是文档中的旧路径描述，已同步中文文档和 `CODEBASE.md`。

修订的旧结论：
- 原先“拆到 `memory_*`、`movement_*`、`coordinate_*`、`event_approach_*`、`hsv_*`、`minimap_shape_color_*` 扁平 helper”只是第一阶段过渡；当前确认应以功能子包作为最终阅读/维护单元，facade 负责兼容，helper package 负责真实实现。

代码变更：
- `core/events/memory/__init__.py`
- `core/events/memory/merge.py`
- `core/events/memory/lookup.py`
- `core/events/memory/completion.py`
- `core/events/memory/utils.py`
- `core/navigation_tasks/event_approach/__init__.py`
- `core/navigation_tasks/event_approach/models.py`
- `core/navigation_tasks/event_approach/geometry.py`
- `core/navigation_tasks/event_approach/motion.py`
- `core/navigation_tasks/event_approach/settle.py`
- `core/navigation_tasks/event_approach/pipeline.py`
- `core/navigation_tasks/movement/__init__.py`
- `core/navigation_tasks/movement/pipeline.py`
- `core/navigation_tasks/movement/path_maintenance.py`
- `core/navigation_tasks/movement/path_planner.py`
- `core/navigation_tasks/movement/recovery.py`
- `core/navigation_tasks/movement/utils.py`
- `core/navigation_tasks/coordinate/__init__.py`
- `core/navigation_tasks/coordinate/models.py`
- `core/navigation_tasks/coordinate/formatting.py`
- `core/navigation_tasks/coordinate/log.py`
- `core/navigation_tasks/coordinate/localization.py`
- `core/navigation_tasks/coordinate/navigation.py`
- `core/navigation_tasks/coordinate/relocalization.py`
- `core/vision/hsv/__init__.py`
- `core/vision/hsv/params.py`
- `core/vision/hsv/preprocessing.py`
- `core/vision/hsv/masks.py`
- `core/vision/hsv/combined.py`
- `core/events/types/portal/minimap_shape_color/__init__.py`
- `core/events/types/portal/minimap_shape_color/models.py`
- `core/events/types/portal/minimap_shape_color/masks.py`
- `core/events/types/portal/minimap_shape_color/templates.py`
- `core/events/types/portal/minimap_shape_color/scoring.py`
- `core/events/types/portal/minimap_shape_color/pipeline.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件/目录 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/memory/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 EventMemory 生命周期策略归组到子包，旧 `core.events.memory` 入口保持。 |
| `core/navigation_tasks/event_approach/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 models/geometry/motion/settle/pipeline 归组，旧 EventApproachController 入口保持。 |
| `core/navigation_tasks/movement/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 pipeline/path_maintenance/path_planner/recovery/utils 归组，MovementExecutor 仍是状态 facade。 |
| `core/navigation_tasks/coordinate/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 models/formatting/log/localization/navigation/relocalization 归组，CoordinateDiagnostics 仍是状态 facade。 |
| `core/vision/hsv/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 params/preprocessing/masks/combined 归组，HSVRecognizer 入口保持。 |
| `core/events/types/portal/minimap_shape_color/` | 扁平 helper 已读 | 深度完整 | 追加 | 已按 models/masks/templates/scoring/pipeline 归组，旧 matcher facade 保持。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\memory\__init__.py core\events\memory\utils.py core\events\memory\lookup.py core\events\memory\merge.py core\events\memory\completion.py core\navigation_tasks\event_approach\__init__.py core\navigation_tasks\movement\__init__.py core\navigation_tasks\coordinate\__init__.py core\vision\hsv\__init__.py core\events\types\portal\minimap_shape_color\__init__.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.memory import EventMemory; from core.navigation_tasks.event_approach import EventApproachController; from core.navigation_tasks.movement import movement_step; from core.navigation_tasks.coordinate import CoordinateRelocalizationRequest; from core.vision.hsv import extract_combined_masks; from core.events.types.portal.minimap_shape_color import match_portal_shape_color; print('ok')"`

下一轮建议：
- 继续按同一“facade + 功能子包”方法处理仍偏长的 core 文件，优先候选是 `core/events/types/portal/minimap_detector.py`（mode dispatch/hit conversion/logging 仍可拆）或 `core/navigation_tasks/controller.py`（控制器仍聚合过多系统参数，但已有 update_context/static/event runner 抽取基础）。

## [SYNC-PORTAL-MINIMAP-DETECTOR-PACKAGE] 2026-05-26

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/types/portal/minimap_detector.py`（原因：当前 portal detector 仍混合 mode dispatch、feature/template/shape-color 调用、no-hit 诊断、hit -> EventDetection 转换和 best-hit 日志；适合继续按 facade + 功能子包抽取。）
- `core/events/types/portal/minimap_hit_filter.py`、`core/events/types/portal/minimap_feature_matcher.py`、`core/events/types/portal/minimap_shape_color_matcher.py`（原因：确认 detector helper 对现有算法组件的调用契约，避免破坏 `_portal_color_check` 和 probe 兼容。）

**本轮想弄清楚：**
- 哪些逻辑属于 detector class 的状态拥有权：templates、feature_templates、signature、last_log_ms。
- 哪些逻辑可拆为 `minimap_detection/` 子包：mode 选择、feature templates 刷新、shape-color 参数构造、no-hit logging、hit 过滤与 EventDetection 转换。

### C. 本轮发现

关键发现：
- (verified) `PortalMinimapDetector` 外部稳定入口保持不变：`PortalMinimapDetector.detect()`、`_detector_mode()`、`_refresh_feature_templates()`、`_detect_feature_hits()`、`_detect_shape_color_hits()` 和模块级 `_portal_color_check()` 仍存在。
- (verified) detector class 继续拥有模板缓存、feature template 缓存、feature signature、scales 和 `_last_log_ms`，避免把有状态字段散到 helper。
- (verified) 新增 `minimap_detection/modes.py`，承接 detector mode fallback、feature template signature 刷新、feature/template/shape-color 命中调用、shape-color 参数构造和 `top_k=max(2,max_candidates*3)` 策略。
- (verified) 新增 `minimap_detection/diagnostics.py`，承接 skipped/no-hit/hit-rejected/best-hit/shape-color-rejected 日志，并继续使用 detector `_last_log_ms` 节流，日志字段保持原样。
- (verified) 新增 `minimap_detection/conversion.py`，承接 `portal_color_check()`、hit -> `EventDetection` 构造和 metadata 填充；`minimap_feature_matcher`/`minimap_shape_color_matcher` 的 hit 字段兼容逻辑保持。
- (verified) `_portal_color_check()` 仍委托 `minimap_hit_filter.portal_color_check()`，保护 probe 或临时脚本旧 import。

修订的旧结论：
- 原先 portal 文档认为 mode strategy 仍在 `PortalMinimapDetector.detect()`；现在确认主流程已降为 facade，mode/diagnostics/conversion 已进入 `minimap_detection/` 子包。

代码变更：
- `core/events/types/portal/minimap_detector.py`
- `core/events/types/portal/minimap_detection/__init__.py`
- `core/events/types/portal/minimap_detection/modes.py`
- `core/events/types/portal/minimap_detection/diagnostics.py`
- `core/events/types/portal/minimap_detection/conversion.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_detector.py` | (partial) | 深度完整 | 追加 | 已保留 detector facade 和旧私有 wrapper，状态字段仍由 class 拥有。 |
| `core/events/types/portal/minimap_detection/__init__.py` | 新增 | 深度完整 | 1 | detector helper package 聚合导出。 |
| `core/events/types/portal/minimap_detection/modes.py` | 新增 | 深度完整 | 1 | 承接 mode fallback、feature template 刷新、template/feature/shape-color 命中调用和参数构造。 |
| `core/events/types/portal/minimap_detection/diagnostics.py` | 新增 | 深度完整 | 1 | 承接 detector 运行日志和 `_last_log_ms` 节流写法。 |
| `core/events/types/portal/minimap_detection/conversion.py` | 新增 | 深度完整 | 1 | 承接颜色过滤、EventDetection 构造和 metadata 字段填充。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_detector.py core\events\types\portal\minimap_detection\__init__.py core\events\types\portal\minimap_detection\modes.py core\events\types\portal\minimap_detection\diagnostics.py core\events\types\portal\minimap_detection\conversion.py core\events\types\portal\minimap_hit_filter.py core\events\types\portal\minimap_feature_matcher.py core\events\types\portal\minimap_shape_color_matcher.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.types.portal.config import PortalEventConfig; from core.events.types.portal.minimap_detector import PortalMinimapDetector, _portal_color_check; from core.events.types.portal.minimap_detection import detector_mode; C=PortalEventConfig(); d=PortalMinimapDetector(C); assert d._detector_mode()==detector_mode(C); print('ok', len(d.templates), d._detector_mode(), callable(_portal_color_check))"`
- `D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from core.events.types.portal.config import PortalEventConfig; from core.events.types.portal.minimap_detector import PortalMinimapDetector; T=type('Tick', (), {}); tick=T(); tick.raw_minimap_frame=np.zeros((64,64,3), dtype=np.uint8); tick.now_ms=1000; d=PortalMinimapDetector(PortalEventConfig(detector_mode='feature')); out=d.detect(tick, d.config); assert isinstance(out, list); print('ok', len(out))"`

下一轮建议：
- 继续处理 `core/navigation_tasks/controller.py`，它现在是 core 最长文件之一。可沿用“facade + 子包”方法新增 `navigation_tasks/controller_runtime/` 或继续利用现有 `update_context.py`、`update_pipeline.py`、`static_task_runner.py`、`event_task_runner.py`，把 relocalization intent、required progress 和 active-task cleanup 继续下沉。

## [SYNC-NAVIGATION-TASK-CONTROLLER-RUNTIME] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/navigation_tasks/controller.py`（原因：当前 core 最长文件之一，仍同时承担 public facade、legacy kwargs 入口、required progress 状态维护、forced relocalization intent、static/event runner 桥接和点击记录。）
- `core/navigation_tasks/update_pipeline.py`、`core/navigation_tasks/static_task_runner.py`、`core/navigation_tasks/event_task_runner.py`（原因：确认 controller 已经外移的职责，避免重复拆或破坏调用链。）

**本轮想弄清楚：**
- `NavigationTaskController` 哪些字段必须继续由 facade 拥有。
- 哪些方法可以下沉到 `controller_runtime/` 子包，并通过旧私有 wrapper 保持兼容。
- `update(**kwargs)`、`update_context(context)`、`record_click(intent, now_ms)` 等外部入口如何保持不变。

### C. 本轮发现

关键发现：
- (verified) `NavigationTaskController` 继续拥有全部 runtime 字段：route、route_context、builder、scheduler、movement、event_approach、coordinate_diagnostics、active_task_id、raw/trusted/control pos、route_progress 和 current_intent。
- (verified) `update(**kwargs)` 仍把旧参数组装成 `NavigationUpdateContext`，`update_context(context)` 仍委托 `update_pipeline.update_controller_context()`；主调度链未改。
- (verified) 新增 `controller_runtime/lifecycle.py`，承接 route load、runtime reset、start/stop、route validity 和 intent click record；旧 public 方法仍保留为 wrapper。
- (verified) 新增 `controller_runtime/localization.py`，承接 raw/trusted/control position 更新、jump reject、confidence alpha 和 route progress 单调推进；`observe_localization()` 旧入口仍保留。
- (verified) 新增 `controller_runtime/progress.py`，承接 required point 下一目标、距离到达判定、完成记录、movement reset 和 active task 清理；`_update_required_progress()`、`_next_required_index()` 旧入口仍保留。
- (verified) 新增 `controller_runtime/relocalization.py`，承接 coordinate diagnostics request 消费、movement reset、日志和 WAIT intent metadata；`_consume_relocalization_intent()` 旧入口仍保留。
- (verified) 这轮没有改变 task selection、static/event runner、MovementExecutor 或 EventApproach 语义。

修订的旧结论：
- 原先 `controller.py` 仍混合大量 runtime 细节；现在它已进一步降为 facade/state owner。剩余复杂度主要在 `update_pipeline.py` 的主流程串接，而不是 controller class 内部方法体。

代码变更：
- `core/navigation_tasks/controller.py`
- `core/navigation_tasks/controller_runtime/__init__.py`
- `core/navigation_tasks/controller_runtime/lifecycle.py`
- `core/navigation_tasks/controller_runtime/localization.py`
- `core/navigation_tasks/controller_runtime/progress.py`
- `core/navigation_tasks/controller_runtime/relocalization.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/controller.py` | (partial) | 深度完整 | 追加 | 已保留 public facade、legacy update 和旧私有 wrapper，runtime 细节外移。 |
| `core/navigation_tasks/controller_runtime/__init__.py` | 新增 | 深度完整 | 1 | 聚合 controller runtime helper。 |
| `core/navigation_tasks/controller_runtime/lifecycle.py` | 新增 | 深度完整 | 1 | 承接 route lifecycle、start/stop 和点击记录。 |
| `core/navigation_tasks/controller_runtime/localization.py` | 新增 | 深度完整 | 1 | 承接定位平滑、jump reject 和 route progress 更新。 |
| `core/navigation_tasks/controller_runtime/progress.py` | 新增 | 深度完整 | 1 | 承接 required point 完成判定和状态清理。 |
| `core/navigation_tasks/controller_runtime/relocalization.py` | 新增 | 深度完整 | 1 | 承接 relocalization request 到 WAIT intent 的转换。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\controller_runtime\__init__.py core\navigation_tasks\controller_runtime\lifecycle.py core\navigation_tasks\controller_runtime\localization.py core\navigation_tasks\controller_runtime\progress.py core\navigation_tasks\controller_runtime\relocalization.py core\navigation_tasks\update_pipeline.py core\navigation_tasks\static_task_runner.py core\navigation_tasks\event_task_runner.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.controller import NavigationTaskController, _float_point, _int_point; c=NavigationTaskController(); route={'exit_region': {'center': [100,100], 'radius': 20}, 'required_points': [[10,10]], 'guide_points': [[0,0],[20,20]]}; c.load_route(route); assert c.has_valid_route(); assert c.start(); assert c.observe_localization((10,10), 1.0); c._update_required_progress(); assert 0 in c.completed_required; assert _float_point((1,2))==(1.0,2.0); assert _int_point((1.2,2.8))==(1,3); print('ok')"`

下一轮建议：
- 继续清理 core 中剩余较长文件。优先候选：`core/motion_controller.py`（可按 input facade + controller_runtime/input pipeline 子包继续拆）或 `core/events/position_stabilizer.py`（事件坐标稳定算法可按 clustering/projection/snapshot 拆）。

## [SYNC-MOTION-CONTROLLER-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/motion_controller.py`（原因：当前 core 最长文件之一，承担地图目标到屏幕点击、普通移动点击、事件精确点击、真实点击/按键入口、last_click_info 写入和兼容私有 wrapper。）
- `core/input/motion_mapping.py`、`core/input/click_pipeline.py`、`core/input/click_executor.py`（原因：确认 MotionController 已经委托出去的职责，避免把 input adapter 逻辑重复拆一遍。）

**本轮想弄清楚：**
- `MotionController` 哪些状态和 public API 必须继续由 facade 拥有。
- 哪些 click 目标构造、last_click_info 写入、control enablement/keyboard helpers 可以下沉到功能子包。
- `move_to_target()`、`click_map_target_once()`、`click_screen_position()`、`press_key()` 和旧私有 helper wrapper 如何保持不变。

### C. 本轮发现

关键发现：
- (verified) `MotionController` 外部稳定入口保持不变：`set_params()`、`set_control_enabled()`、`move_to_map_target()`、`click_map_target_once()`、`click_screen_position()`、`press_key()` 和旧私有 helper wrapper 均仍存在。
- (verified) `MotionController` 继续拥有 calibration/control/backend/last_click_info 等状态；helper 接收 controller 实例并写回原字段，不新增独立状态对象。
- (verified) 新增 `core/input/motion_controller/controls.py`，承接参数写入、control enablement、直接屏幕点击和按键。
- (verified) 新增 `core/input/motion_controller/targets.py`，承接普通移动点击、精确地图目标点击、screen position 计算和 bottom click guard wrapper。
- (verified) 新增 `core/input/motion_controller/backend.py`，承接 lazy `InputDriver`、screen clamp、`pydirectinput` 安全调用、点击发送和窗口信息格式化。
- (verified) `core/input/click_pipeline.py`、`motion_mapping.py`、`click_executor.py` 行为未改；`MotionController._execute_click()` 仍委托 click pipeline。

修订的旧结论：
- 原先 `core/motion_controller.py` 自身仍承载 control/target/backend 细节；现在它已降为 input facade/state owner，真实 helper 收束到 `core/input/motion_controller/` 子包。

代码变更：
- `core/motion_controller.py`
- `core/input/motion_controller/__init__.py`
- `core/input/motion_controller/controls.py`
- `core/input/motion_controller/targets.py`
- `core/input/motion_controller/backend.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | 深度完整 | 追加 | 已保留 MotionController facade、旧 public/private 方法和 last_click_info 契约。 |
| `core/input/motion_controller/__init__.py` | 新增 | 深度完整 | 1 | 聚合 controls/targets/backend helper。 |
| `core/input/motion_controller/controls.py` | 新增 | 深度完整 | 1 | 承接参数写入、enablement、直接屏幕点击和按键。 |
| `core/input/motion_controller/targets.py` | 新增 | 深度完整 | 1 | 承接普通/精确地图目标点击和 screen position 计算。 |
| `core/input/motion_controller/backend.py` | 新增 | 深度完整 | 1 | 承接 InputDriver、screen clamp、send click 和 pydirectinput wrapper。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\motion_controller.py core\input\motion_controller\__init__.py core\input\motion_controller\controls.py core\input\motion_controller\targets.py core\input\motion_controller\backend.py core\input\click_pipeline.py core\input\motion_mapping.py core\input\click_executor.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.motion_controller import MotionController; c=MotionController(); c.set_params((100,100), 1.0, 10, 50, 20); pos=c._calculate_target_screen_position((0,0),(10,0)); assert pos==(110,100); assert c.last_click_info['screen_radius']==10; assert c.click_screen_position((1,2)) is None; assert c._format_window_info(None)=='None'; print('ok', pos)"`

下一轮建议：
- 继续处理 `core/events/position_stabilizer.py` 或 `core/events/types/portal/handler.py`。前者是事件坐标稳定算法，适合拆 `projection/clustering/snapshot`；后者是 portal 状态机，适合拆 `interaction/completion/state`。

## [SYNC-CORE-ROADMAP-POSITION-STABILIZER] 2026-05-27

### A. 本轮目标（阅读前声明）

**主线确认：**
- 第一阶段优先优化 `core`：按系统模块把真实实现拆入功能包，旧入口保留 facade。
- 第二阶段再优化 `gui`：让 GUI 只做页面/弹窗/用户工作流组合，减少算法和运行时细节。
- 第三阶段在调用方迁移稳定后，再统一收掉旧兼容 wrapper。

**目标文件/目录：**
- `core/events/position_stabilizer.py`（原因：事件位置稳定算法独立、文件较长，适合按 projection/clustering/snapshot/selection 继续抽取。）
- `core/events/coordinator.py`、`core/events/runner.py`（原因：确认事件稳定器的调用面，避免拆分后破坏事件运行时。）

**本轮想弄清楚：**
- `EventPositionStabilizer` 的 public API、状态字段和返回数据结构。
- 坐标投影、聚类、稳定 snapshot、清理策略分别能否下沉到功能包。
- 旧路径 `core.events.position_stabilizer.EventPositionStabilizer` 如何继续可用。

### C. 本轮发现

关键发现：
- (verified) `EventPositionStabilizer` 当前调用面很窄：`EventCoordinator` 只创建实例并调用 `update()`、`clear_event_type()`；因此适合做同名 package facade 拆分。
- (verified) Python 同时存在 `position_stabilizer.py` 和 `position_stabilizer/` 时会优先加载 package；本轮直接把旧单文件替换为同名 package，保持 import 路径 `core.events.position_stabilizer` 不变。
- (verified) `runtime.py` 保留 `EventPositionStabilizer`、`_project()`、`_merge_sample()`、`_stable_observation()`、`_find_cluster()`、`_expire_old_clusters()` 等旧 wrapper，避免调试/潜在私有调用断裂。
- (verified) `projection.py` 承接 local minimap detection 到 global map coordinate 的纯投影算法。
- (verified) `clusters.py` 承接 cluster 查找、同帧隔离、样本窗口裁剪和 TTL 过期清理，双 portal 同帧相近 detection 不会被合并。
- (verified) `observations.py` 承接 stable frame count、variance、emit interval gate 和 `EventObservation` 构造。
- (verified) `models.py` 承接 `PositionSample`、`PositionCluster`，并保留中心、方差和 confidence 计算。

修订的旧结论：
- 原先 `core/events/position_stabilizer.py` 被视为单个可复用算法组件；现在它已经成为事件定位子系统 package，`EventPositionStabilizer` 是 facade/state owner，真实算法按投影/聚类/输出 gate 分类。

代码变更：
- 删除 `core/events/position_stabilizer.py`
- 新增 `core/events/position_stabilizer/__init__.py`
- 新增 `core/events/position_stabilizer/runtime.py`
- 新增 `core/events/position_stabilizer/models.py`
- 新增 `core/events/position_stabilizer/projection.py`
- 新增 `core/events/position_stabilizer/clusters.py`
- 新增 `core/events/position_stabilizer/observations.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/position_stabilizer.py` | (partial) | 已删除/替换为 package | 追加 | 原单文件职责已按子模块拆分，旧 import 路径由同名 package 接管。 |
| `core/events/position_stabilizer/__init__.py` | 新增 | 深度完整 | 1 | 保留 `EventPositionStabilizer` 和旧 `_PositionCluster/_PositionSample` 导出。 |
| `core/events/position_stabilizer/runtime.py` | 新增 | 深度完整 | 1 | 保留 facade/state owner 和旧私有 wrapper。 |
| `core/events/position_stabilizer/models.py` | 新增 | 深度完整 | 1 | 承接 sample/cluster DTO 和中心/方差/置信度计算。 |
| `core/events/position_stabilizer/projection.py` | 新增 | 深度完整 | 1 | 承接 local->global 坐标投影。 |
| `core/events/position_stabilizer/clusters.py` | 新增 | 深度完整 | 1 | 承接聚类查找、同帧隔离、样本裁剪和过期清理。 |
| `core/events/position_stabilizer/observations.py` | 新增 | 深度完整 | 1 | 承接稳定 gate 和 `EventObservation` 构造。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\position_stabilizer\__init__.py core\events\position_stabilizer\models.py core\events\position_stabilizer\projection.py core\events\position_stabilizer\clusters.py core\events\position_stabilizer\observations.py core\events\position_stabilizer\runtime.py core\events\coordinator.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.position_stabilizer import EventPositionStabilizer, _PositionCluster, _PositionSample; from core.events.models import EventDetection; from core.shared.frame_registration import FrameRegistration; from core.events.config_model import EventSystemConfig; s=EventPositionStabilizer(); cfg=EventSystemConfig.default(); reg=FrameRegistration(valid=True, frame_origin_global=(100.0,200.0), draw_scale=2.0, confidence=0.9, source='smoke'); obs=[]; det=EventDetection('portal',0.9,100,(10,20),'smoke',{'k':'v'}); obs += s.update([det], reg, cfg, 100); obs += s.update([EventDetection('portal',0.8,200,(10,20),'smoke2',{})], reg, cfg, 200); obs += s.update([EventDetection('portal',0.7,300,(10,20),'smoke3',{})], reg, cfg, 900); assert obs and obs[-1].global_pos == (120,240); assert obs[-1].sample_count == 3; assert _PositionCluster is not None and _PositionSample is not None; print('ok', obs[-1].global_pos, obs[-1].sample_count)"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.position_stabilizer import EventPositionStabilizer; from core.events.models import EventDetection; from core.shared.frame_registration import FrameRegistration; from core.events.config_model import EventSystemConfig; s=EventPositionStabilizer(); cfg=EventSystemConfig.default(); reg=FrameRegistration(valid=True, frame_origin_global=(0.0,0.0), draw_scale=1.0); s.update([EventDetection('portal',0.9,100,(10,10),'a',{}), EventDetection('portal',0.9,100,(12,12),'b',{})], reg, cfg, 100); assert len(s._clusters) == 2; print('ok clusters', len(s._clusters))"`

下一轮建议：
- 继续 core 长文件拆分，优先 `core/events/types/portal/handler.py`。它是 portal 状态机，适合按 state/interaction/completion/action 构造拆到 `handler/` 子包，同时保留 `PortalEventHandler` 旧入口。

## [SYNC-PORTAL-HANDLER-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/types/portal/handler.py`（原因：portal 事件执行状态机较长，同时承担任务启动、靠近、交互、等待完成、teleport completion action 构造和日志。）
- `core/events/types/portal/completion_detector.py`、`environment_signature.py`、`config.py`（原因：确认 handler 已委托的 completion 和 config 细节，避免拆分时改变完成判定。）
- `core/events/runner.py`（原因：确认 handler 输出 `EventAction.COMPLETE/FAIL` 后的 memory 更新契约。）

**本轮想弄清楚：**
- `PortalEventHandler` 的 public API：`start()`、`update()`、`reset()`。
- 哪些状态字段必须继续由 handler 实例拥有。
- interaction click/key、等待 completion、completion metadata/action 构造能否下沉到 `handler/` 子包。
- 旧路径 `core.events.types.portal.handler.PortalEventHandler` 如何继续可用。

### C. 本轮发现

关键发现：
- (verified) `PortalEventDefinition.create_handler()` 只从 `.handler` import `PortalEventHandler`，runner 只按 `EventHandler.start/update/reset` 调用；因此可用同名 package facade 接管旧路径。
- (verified) `PortalEventHandler` 继续拥有 `state`、`last_interact_ms`、`interact_pos`、`interact_signature`、`portal_point_click_ms`、`teleport_relocalize_requested`、日志节流字段；helper 只接收 handler 实例并读写原字段。
- (verified) `handler/movement.py` 承接玩家定位缺失、arrival radius、interact radius 和 `force_repeat_click` MOVE_TO 决策。
- (verified) `handler/interaction.py` 承接 portal 点强制点击、点击后等待、按 `D`、交互时间/位置/signature 记录。
- (verified) `handler/completion.py` 承接 `wait_result` 阶段：post-interact settle、completion action、timeout fail、forced full-map relocalize wait。
- (verified) `handler/diagnostics.py` 承接状态变化日志和节流日志。
- (verified) `handler/compat.py` 保留旧 `_minimap_environment_signature()`、`_signature_difference()`、`_int_pos()` 导出。

修订的旧结论：
- 原先 portal handler 被视为“状态机长文件候选”；现在 `handler.py` 已替换为 `handler/` package，状态仍由 `PortalEventHandler` 持有，但阶段逻辑已经分类下沉。后续若继续优化，应优先把 string state 升级为 enum/runtime dataclass，而不是再做简单函数搬运。

代码变更：
- 删除 `core/events/types/portal/handler.py`
- 新增 `core/events/types/portal/handler/__init__.py`
- 新增 `core/events/types/portal/handler/runtime.py`
- 新增 `core/events/types/portal/handler/movement.py`
- 新增 `core/events/types/portal/handler/interaction.py`
- 新增 `core/events/types/portal/handler/completion.py`
- 新增 `core/events/types/portal/handler/diagnostics.py`
- 新增 `core/events/types/portal/handler/compat.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/handler.py` | (partial) | 已删除/替换为 package | 追加 | 原状态机职责已按 movement/interaction/completion/diagnostics/compat 拆分，旧 import 路径由同名 package 接管。 |
| `core/events/types/portal/handler/__init__.py` | 新增 | 深度完整 | 1 | 保留 `PortalEventHandler` 和旧私有 helper 导出。 |
| `core/events/types/portal/handler/runtime.py` | 新增 | 深度完整 | 1 | 保留 handler facade、状态字段、start/update/reset 和 completion wrapper。 |
| `core/events/types/portal/handler/movement.py` | 新增 | 深度完整 | 1 | 承接到达/交互半径和 movement action。 |
| `core/events/types/portal/handler/interaction.py` | 新增 | 深度完整 | 1 | 承接 portal 点点击、等待和按键交互。 |
| `core/events/types/portal/handler/completion.py` | 新增 | 深度完整 | 1 | 承接 wait_result completion/fail/relocalize wait。 |
| `core/events/types/portal/handler/diagnostics.py` | 新增 | 深度完整 | 1 | 承接状态变化和节流日志。 |
| `core/events/types/portal/handler/compat.py` | 新增 | 深度完整 | 1 | 承接旧私有 helper 兼容导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\handler\__init__.py core\events\types\portal\handler\runtime.py core\events\types\portal\handler\movement.py core\events\types\portal\handler\interaction.py core\events\types\portal\handler\completion.py core\events\types\portal\handler\diagnostics.py core\events\types\portal\handler\compat.py core\events\types\portal\definition.py core\events\types\portal\completion_detector.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from types import SimpleNamespace; import numpy as np; from core.events.types.portal.handler import PortalEventHandler, _minimap_environment_signature, _signature_difference, _int_pos; from core.events.types.portal.config import PortalEventConfig; from core.events.models import EventTask, EventTaskState, EventActionType; h=PortalEventHandler(PortalEventConfig(interact_radius=10, arrival_radius=50, portal_point_click_wait_ms=100, post_interact_wait_ms=200)); task=EventTask(id='p1', event_type='portal', global_pos=(100,100), first_seen_ms=0, last_seen_ms=0, state=EventTaskState.PENDING); h.start(task); tick=SimpleNamespace(now_ms=0, player_global_pos=(0,0), raw_minimap_frame=np.zeros((120,120,3), dtype=np.uint8), player_local_minimap_pos=(60,60), event_tasks=[]); assert h.update(tick, task).type == EventActionType.MOVE_TO; tick.player_global_pos=(95,95); a=h.update(tick, task); assert a.type == EventActionType.MOVE_TO and a.metadata.get('force_click_target'); tick.now_ms=50; assert h.update(tick, task).type == EventActionType.WAIT; tick.now_ms=150; a=h.update(tick, task); assert a.type == EventActionType.PRESS_KEY and h.state == 'wait_result'; tick.now_ms=360; a=h.update(tick, task); assert a.type == EventActionType.WAIT and a.metadata.get('force_relocalize'); assert _int_pos((1.2,2.9)) == (1,2); sig=_minimap_environment_signature(tick.raw_minimap_frame,(60,60)); assert sig is not None and _signature_difference(sig,sig) == 0.0; print('ok portal handler smoke')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.types.portal.definition import PortalEventDefinition; d=PortalEventDefinition(); h=d.create_handler({}); from core.events.types.portal.handler import PortalEventHandler; assert isinstance(h, PortalEventHandler); print('ok definition handler')"`

下一轮建议：
- 继续 core 主 facade 瘦身，优先在 `core/stitcher_core.py` 和 `core/navigation_core.py` 中选一个做更细抽取；如果想继续事件包，则处理 `core/events/types/portal/minimap_feature_matcher.py` 或 `minimap_shape_color/scoring.py`，但这两个偏算法密集，收益不如主 facade 明显。

## [SYNC-MAPPING-STITCHER-FACADE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/stitcher_core.py`（原因：当前已大部分委托 mapping helper，适合把 `MapStitcher` 真实实现迁到 mapping 系统包。）
- `core/mapping/frame_pipeline.py`、`core/mapping/frame_preparation.py`、`core/mapping/weighted_merge.py`、`core/mapping/package_io.py`、`core/mapping/rendering.py`（原因：确认新实现模块的依赖方向，避免 mapping/stitcher 反向 import 旧 top-level wrapper。）
- `gui/app_context.py`、`gui/modes/mapping_widget.py`（原因：确认外部仍通过旧 `core.stitcher_core.MapStitcher` 或 `core.__init__` 获取 class，旧入口必须保留。）

**本轮想弄清楚：**
- `MapStitcher` 当前是否可以整体搬到 `core/mapping/stitcher.py`。
- 旧 `core.stitcher_core.MapStitcher` 和 `core.__init__` 导出如何继续可用。
- helper imports 是否需要从相对旧路径改成 mapping/vision 新路径。

### C. 本轮发现

关键发现：
- (verified) `MapStitcher` 外部主调用来自 `core.__init__`，再由 `gui/app_context.py` 构造共享 `stitcher`；旧 `core.stitcher_core.MapStitcher` 必须保留。
- (verified) `core/stitcher_core.py` 已经只剩状态类和 helper 委托，适合整体迁到 `core/mapping/stitcher.py`。
- (verified) 新增 `core/mapping/stitcher.py` 后，`core.stitcher_core.MapStitcher`、`core.mapping.stitcher.MapStitcher`、`core.mapping.MapStitcher` 和 `core.MapStitcher` 都指向同一个 class。
- (verified) `core/mapping/__init__.py` 新增 `MapStitcher` 导出，mapping 系统包现在可以作为建图系统的显式入口。
- (verified) 旧首帧日志包含 emoji，在当前 GBK stdout 下直接 smoke 会触发 `UnicodeEncodeError`；使用 `PYTHONIOENCODING=utf-8` 可通过。这是旧日志环境问题，本轮未改业务行为。

修订的旧结论：
- 原先 `MapStitcher` 被视为 top-level 有状态 facade；现在 top-level `core/stitcher_core.py` 已降为 compatibility wrapper，真实状态类归入 `core.mapping.stitcher`。

代码变更：
- 新增 `core/mapping/stitcher.py`
- 更新 `core/mapping/__init__.py`
- 替换 `core/stitcher_core.py` 为 re-export wrapper

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/stitcher_core.py` | 深度完整 | 深度完整/compat wrapper | 追加 | 旧路径保留，只 re-export `core.mapping.stitcher.MapStitcher`。 |
| `core/mapping/stitcher.py` | 新增 | 深度完整 | 1 | 承接 `MapStitcher` 真实 class、状态字段和旧 public/private 方法。 |
| `core/mapping/__init__.py` | 浅读 | 深度完整 | 追加 | 新增 `MapStitcher` 聚合导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\mapping\stitcher.py core\stitcher_core.py core\mapping\__init__.py core\mapping\frame_pipeline.py core\mapping\weighted_merge.py core\mapping\package_io.py core\mapping\rendering.py`
- `$env:PYTHONIOENCODING='utf-8'; D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from core.stitcher_core import MapStitcher as Legacy; from core.mapping.stitcher import MapStitcher as New; from core import MapStitcher as Root; assert Legacy is New and Root is New; s=Legacy(canvas_size=200, draw_scale=2.0); mask=np.zeros((20,20), dtype=np.uint8); mask[8:12,8:12]=255; ok=s.add_frame(mask, mask, mask, mask, player_pos=(10,10)); assert ok is True; assert s.get_current_position()==(100,100); assert s.wall_layer.sum() > 0; assert s.get_statistics()['total_frames']==1; print('ok stitcher smoke', s.get_current_position())"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.mapping import MapStitcher; from core.stitcher_core import MapStitcher as Legacy; assert MapStitcher is Legacy; print('ok mapping export')"`

下一轮建议：
- 对 `core/navigation_core.py` 做同类收束前需要更谨慎：外部直接读写字段较多，建议先审计字段调用，再决定是否整体迁到 `core/localization/navigation_core.py`。如果风险过高，就先抽 F2F/template result acceptance helper。

## [DECISION-LEGACY-WRAPPERS-DEFERRED] 2026-05-27

### A. 决策记录

用户确认：旧兼容壳子可以先保留，等后续 GUI 优化完成、调用面迁到新系统包后，再集中清理中间兼容旧内容。

执行含义：
- 当前 `core` 阶段只做系统化和真实实现迁移，不主动删除旧 top-level 入口。
- 旧路径如 `core.stitcher_core`、`core.navigation_core`、`core.motion_controller`、`core.navigation_tasks.controller`、`core.events.coordinator` 继续作为 compatibility shell 或 stable semantic entrypoint。
- 后续 `gui` 优化时，优先把组合根迁到新系统包路径；全部迁完并验证后，才进入 legacy surface cleanup。
- 删除 wrapper 前必须做全库引用审计和一轮兼容期；如果 wrapper 成本低且语义清晰，可以永久保留。

同步文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

## [SYNC-NAVIGATION-CORE-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/navigation_core.py`（原因：这是 GUI 直接调用最多的 core 定位入口，当前真实实现仍在 top-level 文件中；需要收束到 localization 系统包，同时保留旧入口。）
- `core/localization/localize_pipeline.py`、`core/localization/frame_matcher.py`、`core/localization/map_package.py`、`core/localization/rendering.py`、`core/localization/visual_check.py`（原因：确认 `NavigationCore` 已经委托出去的定位职责，避免重复拆分或引入反向依赖。）
- `gui/modes/navigation_mode.py`、`gui/modes/navigation/event_adapter.py`、`gui/modes/navigation/viewport_overlay.py`、`gui/modes/navigation/event_overlay.py`（原因：确认 GUI 对 `NavigationCore` 的字段读写面，迁移时不能丢失属性契约。）

**本轮想弄清楚：**
- `NavigationCore` 能否像 `MapStitcher` 一样整体迁到 localization 系统包。
- 哪些字段是外部实际调用契约，不能改名、不能代理丢失。
- 旧 `core.navigation_core.NavigationCore` 如何继续指向同一个真实 class。

### C. 本轮发现

关键发现：
- (verified) 当前只有 `gui/modes/navigation_mode.py` 直接 `from core.navigation_core import NavigationCore`，但导航 overlay/adapter 和导航主循环直接读写 `draw_scale`、`crop_offset`、`nav_wall_layer`、`explored_map`、`current_pos`、`last_good_pos`、`drawing_saved_pos`、`last_frame_registration`、`recognizer`、visual check 配置等字段；因此不能用丢属性的 composition proxy。
- (verified) `NavigationCore` 当前已经把地图加载、定位 pipeline、显示渲染、frame registration、visual check 等核心细节委托给 `core.localization.*` helper，适合整体迁入 localization 系统包并由旧路径 re-export。
- (verified) 新增 `core/localization/navigation_core/` 后，`core.navigation_core.NavigationCore`、`core.localization.NavigationCore`、`core.localization.navigation_core.NavigationCore` 都指向同一个 class。
- (verified) 新增 `navigation_core/state.py`、`registration.py`、`relocalization.py`、`wall_layer.py`、`diagnostics.py` 后，旧 public/private 方法仍保留在 `NavigationCore` class 上，只是委托到分类 helper。
- (verified) 临时最小 `map_data.npz` smoke 可构造 `NavigationCore`，可调用 `set_initial_hint()`、`request_global_relocalization()`、`_clear_frame_registration()`、`get_map_image()`。
- (verified) 旧行为中 `map_data.npz.current_pos` 会由 loader 读取并打印，但随后构造期运行态初始化会把 `drawing_saved_pos` 重置；本轮保留该行为，不把结构迁移混入功能修复。

修订的旧结论：
- 原先 `NavigationCore` 被视为 top-level 有状态 facade；现在 top-level `core/navigation_core.py` 已降为 compatibility wrapper，真实状态类归入 `core.localization.navigation_core`。

代码变更：
- 新增 `core/localization/navigation_core/__init__.py`
- 新增 `core/localization/navigation_core/runtime.py`
- 新增 `core/localization/navigation_core/state.py`
- 新增 `core/localization/navigation_core/registration.py`
- 新增 `core/localization/navigation_core/relocalization.py`
- 新增 `core/localization/navigation_core/wall_layer.py`
- 新增 `core/localization/navigation_core/diagnostics.py`
- 更新 `core/localization/__init__.py`
- 替换 `core/navigation_core.py` 为 re-export wrapper

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | 深度完整 | 深度完整/compat wrapper | 追加 | 旧路径保留，只 re-export `core.localization.navigation_core.NavigationCore`。 |
| `core/localization/navigation_core/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出 `NavigationCore`。 |
| `core/localization/navigation_core/runtime.py` | 新增 | 深度完整 | 1 | 承接 `NavigationCore` 真实 class、public/private wrapper 和状态拥有者职责。 |
| `core/localization/navigation_core/state.py` | 新增 | 深度完整 | 1 | 承接构造期配置和运行态字段初始化。 |
| `core/localization/navigation_core/registration.py` | 新增 | 深度完整 | 1 | 承接 frame registration 写回 wrapper。 |
| `core/localization/navigation_core/relocalization.py` | 新增 | 深度完整 | 1 | 承接初始 hint、强制全图重定位和阈值策略。 |
| `core/localization/navigation_core/wall_layer.py` | 新增 | 深度完整 | 1 | 承接 nav wall 派生和墙模板 wrapper。 |
| `core/localization/navigation_core/diagnostics.py` | 新增 | 深度完整 | 1 | 承接模板匹配失败节流日志。 |
| `core/localization/__init__.py` | 深度完整 | 深度完整 | 追加 | 新增 `NavigationCore` 聚合导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\localization\__init__.py core\localization\navigation_core\__init__.py core\localization\navigation_core\runtime.py core\localization\navigation_core\state.py core\localization\navigation_core\registration.py core\localization\navigation_core\relocalization.py core\localization\navigation_core\wall_layer.py core\localization\navigation_core\diagnostics.py core\localization\localize_pipeline.py core\localization\map_package.py core\localization\rendering.py core\localization\visual_check.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_core import NavigationCore as Legacy; from core.localization import NavigationCore as Package; from core.localization.navigation_core import NavigationCore as New; assert Legacy is Package is New; print('ok navigation class identity')"`
- `$env:PYTHONIOENCODING='utf-8'; D:\ACloud\.venv\Scripts\python.exe -c "import tempfile, pathlib, numpy as np; from core.navigation_core import NavigationCore as Legacy; from core.localization import NavigationCore as Package; assert Legacy is Package; d=tempfile.TemporaryDirectory(); p=pathlib.Path(d.name); wall=np.zeros((80,80), dtype=np.uint8); wall[20:25,20:35]=255; explored=np.ones((80,80), dtype=np.uint8)*255; np.savez(p/'map_data.npz', wall_layer=wall, explored_map=explored, canvas_size=80, draw_scale=2.0, current_pos=np.array([40.0, 40.0]), wall_close_kernel_size=3); n=Legacy(str(p)); assert n.draw_scale == 2.0; assert n.map_draw_scale == 2.0; assert n.drawing_saved_pos is None; assert n.current_pos is None; assert n.nav_wall_layer.shape == wall.shape; n.set_initial_hint((10, 12)); assert n.current_pos == (10, 12) and n.is_localized; n.request_global_relocalization('smoke'); assert n.force_global_relocalization and not n.is_localized; n._clear_frame_registration(0.2, 'smoke'); assert not n.last_frame_registration.valid; img=n.get_map_image(); assert img is not None and img.size > 0; d.cleanup(); print('ok navigation smoke')"`

下一轮建议：
- 继续处理剩余 core 长文件。优先候选是 `core/routing/pathfinder.py`：如果用户仍希望“长算法也分文件夹”，可把 A* 拆为 `routing/pathfinder/` 同名 package，旧 `core.pathfinder.PathFinder` 和 `core.routing.pathfinder.PathFinder` re-export 同一 class。其次是 `core/navigation_tasks/coordinate_diagnostics.py`，可把真实 class 迁入 `navigation_tasks/coordinate/diagnostics.py`，旧文件保留 wrapper。

## [SYNC-ROUTING-PATHFINDER-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/routing/pathfinder.py`（原因：当前是 core 中最长的纯算法文件之一；用户希望长文件继续按功能文件夹拆分，而不是停留在 200+ 行单文件。）
- `core/pathfinder.py`、`core/routing/__init__.py`（原因：确认旧 top-level wrapper 和 routing 包导出在拆成同名 package 后继续可用。）
- `core/navigation_tasks/movement/path_planner.py`、`core/navigation_tasks/movement/pipeline.py`、`gui/app_context.py`（原因：确认 PathFinder 调用面和实例创建方式。）

**本轮想弄清楚：**
- `PathFinder` 的 public API 是否只有构造参数和 `find_path()`。
- A* 主循环、障碍网格构建、起终点吸附、坐标转换能否拆成有实际算法职责的子模块。
- 旧 `core.pathfinder.PathFinder` 和 `core.routing.pathfinder.PathFinder` 如何继续指向同一个 class。

### C. 本轮发现

关键发现：
- (verified) `PathFinder` 外部稳定 public API 是构造参数和 `find_path(wall_map, start_pos, end_pos, explored_map=None)`；调用面来自 `gui/app_context.py` 的共享实例、`mapping_widget.py` 的调试路径查询、`routing/anchors.py` 和 `navigation_tasks/movement/path_planner.py`。
- (verified) 旧私有 helper 没有外部直接引用，但 `PathFinder` class 上继续保留 `_build_obstacle_map()`、`_clear_start_area()`、`_astar()`、`_heuristic()`、`_reconstruct_path()`、`_find_nearest_walkable()` wrapper，降低调试和旧 monkeypatch 风险。
- (verified) `core/routing/pathfinder.py` 已替换为 `core/routing/pathfinder/` 同名 package；Python import `core.routing.pathfinder` 现在解析 package，并从 `__init__.py` re-export `PathFinder`。
- (verified) `core.pathfinder.PathFinder`、`core.routing.PathFinder` 和 `core.routing.pathfinder.PathFinder` 都指向同一个 class。
- (verified) A* 主循环、障碍网格、起终点吸附、坐标转换已经拆成有实际算法职责的模块，不是 pass-through 文件。

修订的旧结论：
- 原先 `routing/pathfinder.py` 被视为算法内聚单文件；现在它已成为同名 package。`PathFinder` 仍是低层 A* planner，anchor policy 继续留在 `routing/anchors.py`。

代码变更：
- 删除 `core/routing/pathfinder.py`
- 新增 `core/routing/pathfinder/__init__.py`
- 新增 `core/routing/pathfinder/runtime.py`
- 新增 `core/routing/pathfinder/grid.py`
- 新增 `core/routing/pathfinder/astar.py`
- 新增 `core/routing/pathfinder/snap.py`
- 新增 `core/routing/pathfinder/coordinates.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/routing/pathfinder.py` | 深度完整 | 已删除，替换为同名 package | 追加 | 原 A* 职责按 runtime/grid/astar/snap/coordinates 拆分。 |
| `core/routing/pathfinder/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出 `PathFinder`。 |
| `core/routing/pathfinder/runtime.py` | 新增 | 深度完整 | 1 | 承接 `PathFinder` class、`find_path()` 和旧私有 wrapper。 |
| `core/routing/pathfinder/grid.py` | 新增 | 深度完整 | 1 | 承接 obstacle grid 构建、explored map 阻挡、安全边距和起点清理。 |
| `core/routing/pathfinder/astar.py` | 新增 | 深度完整 | 1 | 承接 A* 主循环、corner cutting 拒绝、heuristic 和路径回溯。 |
| `core/routing/pathfinder/snap.py` | 新增 | 深度完整 | 1 | 承接最近可走格搜索和 snap 半径转换。 |
| `core/routing/pathfinder/coordinates.py` | 新增 | 深度完整 | 1 | 承接 map/grid 坐标转换和 path 还原。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\pathfinder.py core\routing\__init__.py core\routing\pathfinder\__init__.py core\routing\pathfinder\runtime.py core\routing\pathfinder\coordinates.py core\routing\pathfinder\grid.py core\routing\pathfinder\astar.py core\routing\pathfinder\snap.py core\routing\anchors.py core\navigation_tasks\movement\path_planner.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.pathfinder import PathFinder as Legacy; from core.routing import PathFinder as Routing; from core.routing.pathfinder import PathFinder as Package; assert Legacy is Routing is Package; print('ok pathfinder class identity')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from core.pathfinder import PathFinder; wall=np.zeros((100,100), dtype=np.uint8); wall[40:60,45:55]=255; wall[50,45:55]=0; pf=PathFinder(downsample_factor=5); path=pf.find_path(wall,(10,10),(90,90)); assert path and path[-1]==(90,90); assert pf._heuristic((0,0),(2,3))==5; print('ok pathfinder smoke', len(path), path[0], path[-1])"`

下一轮建议：
- 继续处理 `core/navigation_tasks/coordinate_diagnostics.py`，把真实 `CoordinateDiagnostics` class 迁到 `navigation_tasks/coordinate/diagnostics.py`，旧 `coordinate_diagnostics.py` 保留 re-export wrapper。该文件虽然已经委托了很多 helper，但仍是 top-level 较长 facade，适合沿用本轮“真实类进系统包，旧路径保留”的方式。

## [SYNC-COORDINATE-DIAGNOSTICS-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/navigation_tasks/coordinate_diagnostics.py`（原因：当前仍是 top-level 较长 facade，真实 class 可迁入已经存在的 `navigation_tasks/coordinate/` 系统包。）
- `core/navigation_tasks/coordinate/*.py`（原因：确认现有定位诊断、导航诊断、重定位请求、日志和格式化 helper 的职责，避免重复拆分。）
- `core/navigation_tasks/controller.py`、`core/navigation_tasks/controller_runtime/relocalization.py`、`core/navigation_tasks/update_pipeline.py`（原因：确认 `CoordinateDiagnostics` 调用面和旧 import 路径。）

**本轮想弄清楚：**
- `CoordinateDiagnostics` 的 public API 和旧私有 helper wrapper 是否都能原样保留。
- 真实 class 放入 `core/navigation_tasks/coordinate/diagnostics.py` 后，旧 `core.navigation_tasks.coordinate_diagnostics` 如何继续可用。
- `core.navigation_tasks.coordinate` 是否需要聚合导出 `CoordinateDiagnostics`。

### C. 本轮发现

关键发现：
- (verified) `CoordinateDiagnostics` 调用面来自 `NavigationTaskController`，controller 构造时仍从旧 `coordinate_diagnostics.py` import class；GUI 只通过 `navigation_task_controller.coordinate_diagnostics` 访问实例字段。
- (verified) `CoordinateDiagnostics` public API 是 `reset()`、`record_session_start()`、`record_localization()`、`record_navigation_state()`、`consume_relocalization_request()`、`mark_relocalization_accepted()`；旧私有 helper wrapper 也继续保留。
- (verified) 真实 class 已迁到 `core/navigation_tasks/coordinate/diagnostics.py`；旧 `core.navigation_tasks.coordinate_diagnostics.CoordinateDiagnostics`、新 `core.navigation_tasks.coordinate.CoordinateDiagnostics` 和 `core.navigation_tasks.coordinate.diagnostics.CoordinateDiagnostics` 都指向同一个 class。
- (verified) 现有 helper 分层保持不变：定位证据在 `coordinate/localization.py`，导航证据在 `coordinate/navigation.py`，重定位请求生命周期在 `coordinate/relocalization.py`，日志和格式化在 `coordinate/log.py` 与 `coordinate/formatting.py`。

修订的旧结论：
- 原先 `coordinate_diagnostics.py` 被视为 stateful facade；现在它已降为 compatibility wrapper，真实 stateful facade 归入 `navigation_tasks/coordinate/diagnostics.py`。

代码变更：
- 新增 `core/navigation_tasks/coordinate/diagnostics.py`
- 更新 `core/navigation_tasks/coordinate/__init__.py`
- 替换 `core/navigation_tasks/coordinate_diagnostics.py` 为 re-export wrapper

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | 深度完整 | 深度完整/compat wrapper | 追加 | 旧路径保留，只 re-export `coordinate.diagnostics.CoordinateDiagnostics` 和旧私有 helper。 |
| `core/navigation_tasks/coordinate/diagnostics.py` | 新增 | 深度完整 | 1 | 承接 `CoordinateDiagnostics` 真实 class、public API 和旧私有 wrapper。 |
| `core/navigation_tasks/coordinate/__init__.py` | 深度完整 | 深度完整 | 追加 | 新增 `CoordinateDiagnostics` 和旧 helper 聚合导出。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\coordinate\__init__.py core\navigation_tasks\coordinate\diagnostics.py core\navigation_tasks\coordinate\localization.py core\navigation_tasks\coordinate\navigation.py core\navigation_tasks\coordinate\relocalization.py core\navigation_tasks\controller.py core\navigation_tasks\update_pipeline.py core\navigation_tasks\controller_runtime\relocalization.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.coordinate_diagnostics import CoordinateDiagnostics as Legacy, _distance; from core.navigation_tasks.coordinate import CoordinateDiagnostics as Package; from core.navigation_tasks.coordinate.diagnostics import CoordinateDiagnostics as New; assert Legacy is Package is New; assert _distance((0,0),(3,4)) == 5.0; d=Legacy(); d._register_recovery_signal('raw_jump', 100, severity=3); req=d.consume_relocalization_request(); assert req is not None and req.reason == 'raw_jump'; print('ok coordinate diagnostics smoke', req.reason)"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.navigation_tasks.controller import NavigationTaskController; from core.navigation_tasks.coordinate import CoordinateDiagnostics; c=NavigationTaskController(); assert isinstance(c.coordinate_diagnostics, CoordinateDiagnostics); print('ok controller coordinate diagnostics')"`

下一轮建议：
- 如果继续 core 长文件审计，优先处理 `core/events/coordinator.py` 或 `core/events/debug.py`。前者可按 observe/run/status/reset 拆成 `events/coordinator/` 同名 package；后者可按 action/task/observation formatting 分类。但 `EventCoordinator` 是事件系统 public facade，仍应保留旧路径和 class identity。

## [SYNC-EVENT-COORDINATOR-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/coordinator.py`（原因：事件系统 public facade，当前同时承接 observation flow、task run flow、reset、overlay/status 过滤和 enabled gating。）
- `core/events/runner.py`、`core/events/memory/`、`core/events/scheduler.py`、`core/events/monitor.py`（原因：确认 coordinator 和事件 runtime 其他组件之间的调用契约。）
- `gui/modes/navigation/event_adapter.py`、`core/navigation_tasks/event_task_runner.py`（原因：确认外部对 `EventCoordinator` 的调用面。）

**本轮想弄清楚：**
- `EventCoordinator` 的 public API 是否能作为稳定 wrapper 保留。
- observe/run/status/reset/enable-filter 能否拆到 `events/coordinator/` 同名 package 下的功能 helper。
- 旧 `core.events.coordinator.EventCoordinator` 如何继续指向同一个真实 class。

### C. 本轮发现

关键发现：
- (verified) `EventCoordinator` 的外部 public API 仍是 `observe(tick)`、`run_task(task_id, tick)`、`tasks()`、`reset_event_type(event_type, now_ms=None)`、`overlays()`、`status_summary()`；GUI 和 navigation task runner 不需要改调用点。
- (verified) `observe()` 主流程已经拆到 `coordinator/observation.py`：事件启用检查、detector 调用、位置稳定、memory merge、`tick.event_tasks` 写回和 display task 选择各自仍按原顺序执行。
- (verified) `run_task()` 主流程已经拆到 `coordinator/task_run.py`：按 task id 从 enabled active tasks 查找，缺失时清空 runner，选中时委托 `EventRunner.update()` 并记录最新 action。
- (verified) `reset_event_type()` 已拆到 `coordinator/reset.py`：清理 active handler、memory tasks、position clusters、last detections/observations、selected task 和 last action，不修改 `event_config.json`。
- (verified) `overlays()` 和 `status_summary()` 已拆到 `coordinator/presentation.py`，enabled 过滤和日志节流已拆到 `coordinator/filters.py`。
- (verified) `core.events.coordinator` 现在解析为同名 package，`__init__.py` re-export `runtime.EventCoordinator`，旧 import 路径保持可用。

修订的旧结论：
- 原先 `core/events/coordinator.py` 被视为事件系统单文件 public facade；现在它已经替换为 `core/events/coordinator/` package，真实 stateful facade 位于 `runtime.py`，功能逻辑按 observe/run/reset/presentation/filter 分类下沉。

代码变更：
- 删除 `core/events/coordinator.py`
- 新增 `core/events/coordinator/__init__.py`
- 新增 `core/events/coordinator/runtime.py`
- 新增 `core/events/coordinator/observation.py`
- 新增 `core/events/coordinator/task_run.py`
- 新增 `core/events/coordinator/reset.py`
- 新增 `core/events/coordinator/presentation.py`
- 新增 `core/events/coordinator/filters.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/coordinator.py` | 深度完整 | 已删除/替换为同名 package | 追加 | 原单文件职责已按 observe/run/reset/presentation/filter 拆分，旧 import 路径由同名 package 接管。 |
| `core/events/coordinator/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出 `EventCoordinator`。 |
| `core/events/coordinator/runtime.py` | 新增 | 深度完整 | 1 | 承接 `EventCoordinator` stateful facade、状态字段和旧 public/private wrapper。 |
| `core/events/coordinator/observation.py` | 新增 | 深度完整 | 1 | 承接 detect、position stabilize、memory merge、`tick.event_tasks` 写回和 display task selection。 |
| `core/events/coordinator/task_run.py` | 新增 | 深度完整 | 1 | 承接 task id 查找、runner 委托、缺失 task 降级清空和 action 日志。 |
| `core/events/coordinator/reset.py` | 新增 | 深度完整 | 1 | 承接按 event type 清理 handler/memory/cluster/cache 状态。 |
| `core/events/coordinator/presentation.py` | 新增 | 深度完整 | 1 | 承接 overlay DTO 构造和紧凑 status summary。 |
| `core/events/coordinator/filters.py` | 新增 | 深度完整 | 1 | 承接 event enabled 过滤、active/display task 过滤和 coordinator 日志节流。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\coordinator\__init__.py core\events\coordinator\runtime.py core\events\coordinator\filters.py core\events\coordinator\observation.py core\events\coordinator\task_run.py core\events\coordinator\reset.py core\events\coordinator\presentation.py core\events\runner.py core\events\memory\__init__.py core\events\scheduler.py core\events\monitor.py core\navigation_tasks\event_task_runner.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.coordinator import EventCoordinator; from core.events.config_model import EventSystemConfig; from core.events.registry import EventRegistry; c=EventCoordinator(EventRegistry(), EventSystemConfig.default()); assert c.tasks()==[]; assert c.overlays()==[]; assert c.status_summary()==''; assert c.reset_event_type('portal', now_ms=1)==0; print('ok event coordinator basic')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from types import SimpleNamespace; from core.events.coordinator import EventCoordinator; from core.events.config_model import EventSystemConfig; from core.events.registry import EventRegistry; c=EventCoordinator(EventRegistry(), EventSystemConfig.default()); tick=SimpleNamespace(now_ms=100, player_global_pos=(0,0), frame_registration=None); c.observe(tick); assert hasattr(tick,'event_tasks') and tick.event_tasks == []; assert c.run_task(None, tick) is None; print('ok event coordinator observe/run')"`

下一轮建议：
- 继续处理 `core/events/debug.py`。它当前是事件、导航任务、portal detector/handler 和 GUI 共用的诊断入口，可替换为 `events/debug/` 同名 package，把日志 session/line writer、topic routing、action/task 描述和格式化分开，继续保留 `from core.events.debug import event_log` 等旧入口。

## [SYNC-EVENT-DEBUG-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/debug.py`（原因：当前同时承担事件日志 session、日志文件写入、topic 分流、action/task 描述和字段格式化，并被 GUI、navigation task、portal detector/handler、coordinator、memory 多处共用。）
- `core/events/models.py`（原因：确认 `describe_action()`、`describe_task()` 依赖的 EventAction/EventTask 字段契约。）
- `gui/modes/navigation_mode.py`、`core/navigation_tasks/debug.py`、`core/events/types/portal/*`、`core/events/coordinator/`（原因：确认外部只从 `core.events.debug` import public 函数，拆包后旧入口必须保留。）

**本轮想弄清楚：**
- `event_log()` 和 `start_event_log_session()` 的文件写入副作用是否能原样保留。
- `_event_topic()`、`_topic_from_value()`、`_sanitize_topic()` 是否能拆成独立 topic routing helper。
- `describe_action()`、`describe_task()` 是否能拆成描述格式化模块，并继续使用同一个 `_format_value()` 规则。
- 旧 `core.events.debug` 如何在删除单文件后由同名 package 接管，同时保留 public 函数和必要私有 helper 导出。

### C. 本轮发现

关键发现：
- (verified) 外部实现代码只依赖 `core.events.debug` 的 `event_log()`、`start_event_log_session()`、`describe_action()`、`describe_task()`；当前未发现实现代码直接调用私有 helper，但 `__init__.py` 仍保留 `_format_value()`、`_format_fields()`、`_event_topic()`、`_topic_from_value()`、`_sanitize_topic()`、`_build_line()`、`_new_session_stamp()`、`_write_event_line()` 导出，降低旧调试脚本断裂风险。
- (verified) `event_log()` 的副作用已原样保留：第一次调用自动创建 session stamp，写 `logs/event_runtime.log`、本 run archive、可选 topic log，并 print 同一行到 stdout。
- (verified) `start_event_log_session(label)` 仍会创建新的 run archive，把 label 清洗进文件名，并重置主日志文件的本进程写入头。
- (verified) 因为文件从 `core/events/debug.py` 下沉到 `core/events/debug/writer.py`，项目根目录定位必须从 `parents[2]` 改为 `parents[3]`；smoke 已确认日志仍落到项目根目录 `logs/`，不是 `core/logs/`。
- (verified) topic routing 已拆到 `debug/topics.py`，仍按显式 `event/event_type`、task/entry/exit 字段、message 中 portal/nav/localization 关键字推断 topic。
- (verified) action/task 描述已拆到 `debug/descriptions.py`，仍复用 `debug/formatting.py` 的 Enum、float、tuple/list、dict 格式化规则。

修订的旧结论：
- 原先 `core/events/debug.py` 被视为单文件 logging adapter；现在它已经替换为 `core/events/debug/` package，旧 import 路径不变，真实职责按 writer/topics/descriptions/formatting 分类下沉。

代码变更：
- 删除 `core/events/debug.py`
- 新增 `core/events/debug/__init__.py`
- 新增 `core/events/debug/writer.py`
- 新增 `core/events/debug/topics.py`
- 新增 `core/events/debug/descriptions.py`
- 新增 `core/events/debug/formatting.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/debug.py` | 深度完整 | 已删除/替换为同名 package | 追加 | 原 logging adapter 已按 writer/topics/descriptions/formatting 拆分，旧 import 路径由同名 package 接管。 |
| `core/events/debug/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出旧 public 函数和保守私有 helper 导出。 |
| `core/events/debug/writer.py` | 新增 | 深度完整 | 1 | 承接 session 生命周期、主日志、run archive、topic log 写入和日志行构造。 |
| `core/events/debug/topics.py` | 新增 | 深度完整 | 1 | 承接 portal/navigation/localization topic 推断和 topic 文件名清洗。 |
| `core/events/debug/descriptions.py` | 新增 | 深度完整 | 1 | 承接 EventAction/EventTask 紧凑描述。 |
| `core/events/debug/formatting.py` | 新增 | 深度完整 | 1 | 承接日志字段和值格式化规则。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\debug\__init__.py core\events\debug\formatting.py core\events\debug\descriptions.py core\events\debug\topics.py core\events\debug\writer.py core\events\runner.py core\events\monitor.py core\events\memory\__init__.py core\events\coordinator\runtime.py core\events\types\portal\handler\runtime.py core\navigation_tasks\debug.py gui\modes\navigation_mode.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.debug import event_log, start_event_log_session, describe_action, describe_task, _format_value, _event_topic; from core.events.models import EventAction, EventTask, EventTaskState; a=EventAction.move_to((1,2), reason='r'); assert describe_action(a)=='move_to target=(1,2) reason=r'; t=EventTask(id='p1', event_type='portal', global_pos=(3,4), first_seen_ms=1, last_seen_ms=2, state=EventTaskState.PENDING, confidence=0.5); assert 'event=portal' in describe_task(t); assert _format_value({'a': (1, 2)}) == '{a:(1,2)}'; assert _event_topic('runner action', {'task': describe_task(t)}) == 'portal'; print('ok debug import/format')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "import tempfile, pathlib; import core.events.debug.writer as w; d=tempfile.TemporaryDirectory(); root=pathlib.Path(d.name); w._EVENT_LOG_PATH=root/'event_runtime.log'; w._EVENT_RUN_DIR=root/'event_runs'; w._EVENT_SESSION_STAMP=''; w._EVENT_SESSION_PATH=w._EVENT_RUN_DIR / f'_pid{w._EVENT_SESSION_PID}_event_runtime.log'; w._EVENT_STARTED_PATHS.clear(); from core.events.debug import event_log, start_event_log_session; p=start_event_log_session('portal manual test'); event_log('portal test line', event='portal', value=1.25); assert (root/'event_runtime.log').exists(); assert p.exists(); portal_logs=list((root/'event_runs').glob('*event_portal.log')); assert portal_logs; txt=(root/'event_runtime.log').read_text(encoding='utf-8-sig'); assert 'event log session started' in txt and 'portal test line' in txt; print('ok debug writer smoke', p.name, portal_logs[0].name); d.cleanup()"`

下一轮建议：
- 继续处理 core 中剩余较长或职责偏集中的文件。优先候选：`core/events/types/portal/minimap_feature_matcher.py`（可拆成 feature mask/template/hit merge/response helper package）或 `core/routing/anchors.py`（可拆成 guide projection、corridor shaping、segment scoring）。两者都是纯逻辑，适合继续小步拆分并做 smoke 验证。

## [SYNC-PORTAL-MINIMAP-FEATURE-MATCHER-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/types/portal/minimap_feature_matcher.py`（原因：portal 小地图蓝色本体特征匹配算法集中在单文件中，包含 DTO、HSV mask、多尺度模板准备、响应图 peak 提取、候选评分和 hit 合并；适合拆为同名算法 package。）
- `core/events/types/portal/minimap_detection/modes.py`、`core/events/types/portal/minimap_detector.py`（原因：确认 feature matcher 的运行时调用面和旧 import 路径。）
- `core/events/types/portal/definition.py`、`core/events/types/portal/config.py`（原因：确认 feature matcher 参数来自 portal config schema/defaults，不改变配置契约。）

**本轮想弄清楚：**
- `PortalFeatureTemplate`、`PortalFeatureHit`、`portal_blue_mask()`、`load_feature_templates()`、`match_portal_features()`、`merge_feature_hits()` 是否能保持原签名。
- HSV 蓝色 mask、模板加载、多尺度响应图 peak 提取、候选打分和 hit 合并能否拆成实际算法模块，而不是扁平 helper。
- 旧 `core.events.types.portal.minimap_feature_matcher` 如何由同名 package 接管，并让现有 detector/mode imports 不需要修改或只做最小修改。

### C. 本轮发现

关键发现：
- (verified) 实际 public 函数是 `build_feature_templates()` 而不是 `load_feature_templates()`；本轮修订该旧表述，保持 `PortalFeatureTemplate`、`PortalFeatureHit`、`portal_blue_mask()`、`build_feature_templates()`、`match_portal_features()`、`merge_feature_hits()` 签名不变。
- (verified) 运行时调用面来自 `minimap_detection/modes.py` 和 `minimap_detection/diagnostics.py`，探针调用面来自 `utils/event_icon_probe.py`；这些 import 都仍从 `core.events.types.portal.minimap_feature_matcher` 获取函数，不需要迁移。
- (verified) `PortalFeatureHit.center` 的计算仍留在 DTO 上，hit metadata 字段 `score/mask_score/density_score/scale/top_left/size/template_name/blue_pixels/template_pixels` 未改变。
- (verified) HSV 蓝/青色 body mask 已拆到 `masks.py`；模板蓝色特征准备和 min pixel 过滤已拆到 `templates.py`；多尺度 nearest-neighbor mask resize 和 response peak suppression 已拆到 `response.py`；主匹配/候选评分/近邻合并留在 `pipeline.py`。
- (verified) 合成图 smoke 能用蓝色模板在 raw frame 上命中预期中心点，并验证 `_resize_mask()`、`_response_hits()` 私有 helper 旧导出仍可用。

修订的旧结论：
- 原先 `minimap_feature_matcher.py` 被视为一个可复用但单文件算法组件；现在它已经替换为 `minimap_feature_matcher/` 同名算法 package，旧 import 路径不变，真实职责按 DTO/mask/template/response/pipeline 分类下沉。

代码变更：
- 删除 `core/events/types/portal/minimap_feature_matcher.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/__init__.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/models.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/masks.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/templates.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/response.py`
- 新增 `core/events/types/portal/minimap_feature_matcher/pipeline.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_feature_matcher.py` | 深度完整 | 已删除/替换为同名 package | 追加 | 原蓝色本体特征匹配算法已按 models/masks/templates/response/pipeline 拆分。 |
| `core/events/types/portal/minimap_feature_matcher/__init__.py` | 新增 | 深度完整 | 1 | 保留旧 public API 和 `_resize_mask/_response_hits` 私有 helper 导出。 |
| `core/events/types/portal/minimap_feature_matcher/models.py` | 新增 | 深度完整 | 1 | 承接 `PortalFeatureTemplate`、`PortalFeatureHit` 和 center 计算。 |
| `core/events/types/portal/minimap_feature_matcher/masks.py` | 新增 | 深度完整 | 1 | 承接 HSV 蓝/青色 body mask 提取。 |
| `core/events/types/portal/minimap_feature_matcher/templates.py` | 新增 | 深度完整 | 1 | 承接 `TemplateSpec` -> feature template 构造和 min pixel 过滤。 |
| `core/events/types/portal/minimap_feature_matcher/response.py` | 新增 | 深度完整 | 1 | 承接 mask resize 和 response peak suppression。 |
| `core/events/types/portal/minimap_feature_matcher/pipeline.py` | 新增 | 深度完整 | 1 | 承接主匹配、候选评分和近邻 hit 合并。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_feature_matcher\__init__.py core\events\types\portal\minimap_feature_matcher\models.py core\events\types\portal\minimap_feature_matcher\masks.py core\events\types\portal\minimap_feature_matcher\templates.py core\events\types\portal\minimap_feature_matcher\response.py core\events\types\portal\minimap_feature_matcher\pipeline.py core\events\types\portal\minimap_detection\modes.py core\events\types\portal\minimap_detection\diagnostics.py core\events\types\portal\minimap_detector.py utils\event_icon_probe.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "import numpy as np; from pathlib import Path; from core.events.detectors.template_matcher import TemplateSpec; from core.events.types.portal.minimap_feature_matcher import build_feature_templates, match_portal_features, portal_blue_mask, _resize_mask, _response_hits; template=np.zeros((12,12,3), dtype=np.uint8); template[3:9,3:9]=(255,180,40); specs=[TemplateSpec(name='portal', path=Path('portal.png'), image=template)]; feature_templates=build_feature_templates(specs, min_template_pixels=4); assert len(feature_templates)==1; frame=np.zeros((60,60,3), dtype=np.uint8); frame[20:32,25:37]=template; hits=match_portal_features(frame, feature_templates, [1.0], top_k=2, threshold=0.70, min_blue_pixels=4, max_blue_pixels=200); assert hits, 'expected feature hit'; assert abs(hits[0].center[0]-31)<=2 and abs(hits[0].center[1]-26)<=2, hits[0].center; mask=portal_blue_mask(frame); assert int(np.count_nonzero(mask)) >= 36; assert _resize_mask(feature_templates[0].mask, 1.0).shape == feature_templates[0].mask.shape; response=np.zeros((5,5), dtype=np.float32); response[1,2]=0.9; assert _response_hits(response, 1, 0.5, 1)[0][1] == (2,1); print('ok feature matcher smoke')"`
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.types.portal.minimap_feature_matcher import PortalFeatureHit, PortalFeatureTemplate; from core.events.types.portal.minimap_feature_matcher.models import PortalFeatureHit as NewHit; assert PortalFeatureHit is NewHit; h=PortalFeatureHit(score=1, mask_score=1, density_score=1, scale=1, top_left=(10,20), size=(8,6), template_name='t', blue_pixels=1, template_pixels=1); assert h.center == (14,23); print('ok feature matcher identity')"`

下一轮建议：
- 继续处理 `core/routing/anchors.py`。它是纯 route shaping 算法，可拆成 `routing/anchors/` 同名 package：models/result、projection、corridor shaping、scoring/search，同时保留旧 `core.anchor_path` 和 `core.routing.anchors` 导出。

## [SYNC-ROUTING-ANCHORS-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/routing/anchors.py`（原因：route guide anchor 塑形算法集中在单文件中，包含 DTO、路径累计距离、最近点投影、guide 子序列选择、路径拼接和结果构造；适合拆成 routing/anchors 同名 package。）
- `core/anchor_path.py`、`core/routing/__init__.py`（原因：确认旧 top-level wrapper 和 routing 聚合导出仍可用。）
- `core/navigation_tasks/movement/path_planner.py`、`core/navigation_tasks/route_context.py`（原因：确认外部对 anchor 规划 API 的调用面和返回 DTO 字段。）

**本轮想弄清楚：**
- `AnchorPathResult`、`plan_anchor_path()`、`nearest_polyline_progress()`、`remaining_route_from_progress()` 的签名和返回字段是否能保持不变。
- 最近点投影、路线进度累计、guide 子序列选择、分段 A* 拼接是否能拆到有意义的算法模块。
- 旧 `core.routing.anchors` 如何由同名 package 接管，同时 `core.anchor_path` 继续 re-export 同一批函数和 DTO。

### C. 本轮发现

关键发现：
- (verified) 本轮 A 段的旧函数名表述需要修订：实际 public API 是 `AnchorPathResult`、`plan_path_with_optional_anchors()`、`anchor_route_progress()`、`anchor_progress_map()`；不存在 `plan_anchor_path()`、`nearest_polyline_progress()`、`remaining_route_from_progress()` 这些当前实现函数。
- (verified) 外部调用面很窄：`core.anchor_path` 和 `core.routing.__init__` re-export anchors API；`navigation_tasks/movement/path_planner.py` 只调用 `plan_path_with_optional_anchors()`。
- (verified) `plan_path_with_optional_anchors()` 的语义保持不变：有前方 guide anchor 时只规划到下一个 anchor，A* 成功返回 `anchor_step`，失败返回朝 anchor 的短 probe `anchor_probe`；无前方 anchor 时直接 A* 到 target 并返回 `planned`。
- (verified) `max_anchor_factor`、`max_anchor_branching` 原本就是未使用兼容参数，本轮保留签名不删除，避免把结构拆分混入行为清理。
- (verified) `core.routing.anchors` 现在解析为同名 package；`core.anchor_path.AnchorPathResult`、`core.routing.AnchorPathResult`、`core.routing.anchors.AnchorPathResult` 指向同一个 class。

修订的旧结论：
- 原先 `core/routing/anchors.py` 被视为单文件 guide-anchor planning 工具；现在它已经替换为 `core/routing/anchors/` package，旧 import 路径不变，真实职责按 models/progress/corridor/planner/utils 分类下沉。

代码变更：
- 删除 `core/routing/anchors.py`
- 新增 `core/routing/anchors/__init__.py`
- 新增 `core/routing/anchors/models.py`
- 新增 `core/routing/anchors/utils.py`
- 新增 `core/routing/anchors/progress.py`
- 新增 `core/routing/anchors/corridor.py`
- 新增 `core/routing/anchors/planner.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/routing/anchors.py` | 深度完整 | 已删除/替换为同名 package | 追加 | 原 guide-anchor planning 已按 models/progress/corridor/planner/utils 拆分。 |
| `core/routing/anchors/__init__.py` | 新增 | 深度完整 | 1 | 保留旧 public API 和保守私有 helper 导出。 |
| `core/routing/anchors/models.py` | 新增 | 深度完整 | 1 | 承接 `AnchorPathResult` DTO。 |
| `core/routing/anchors/utils.py` | 新增 | 深度完整 | 1 | 承接整数点标准化和朝锚点 probe 点计算。 |
| `core/routing/anchors/progress.py` | 新增 | 深度完整 | 1 | 承接 anchor 去重、累计距离、polyline progress 投影和 progress map。 |
| `core/routing/anchors/corridor.py` | 新增 | 深度完整 | 1 | 承接前方 ordered guide anchors 过滤。 |
| `core/routing/anchors/planner.py` | 新增 | 深度完整 | 1 | 承接 anchor_step、anchor_probe、planned 主规划流程。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\routing\anchors\__init__.py core\routing\anchors\models.py core\routing\anchors\utils.py core\routing\anchors\progress.py core\routing\anchors\corridor.py core\routing\anchors\planner.py core\anchor_path.py core\routing\__init__.py core\navigation_tasks\movement\path_planner.py`
- `python -` smoke：验证 `anchor_progress_map()`、`anchor_route_progress()`、`_ordered_corridor_anchors()`、`_probe_towards()`、`plan_path_with_optional_anchors()` 的 `anchor_step` 路径和 `core.anchor_path`/`core.routing.anchors.models` class identity。
- `python -` smoke：模拟下一个 anchor A* 不可达，验证返回 `path_kind="anchor_probe"` 且 probe path 为 `[(10,0),(30,0)]`。
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.routing import AnchorPathResult as A; from core.routing.anchors import AnchorPathResult as B; from core.anchor_path import AnchorPathResult as C; assert A is B is C; print('ok anchors exports')"`

下一轮建议：
- 继续 core 长文件审计时，可处理 `core/events/types/portal/minimap_shape_color/scoring.py`（算法密集，可按 response、mask-score、color-score、candidate-evaluation 再拆）或 `core/navigation_tasks/coordinate/localization.py`（定位证据诊断可继续拆成 evidence/rules/logging）。

## [SYNC-PORTAL-SHAPE-COLOR-SCORING-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/events/types/portal/minimap_shape_color/scoring.py`（原因：shape-color matcher 的响应图、F1-like mask score、HSV color similarity、候选接受/拒绝判断集中在单文件中，是当前 portal 算法包内最长文件。）
- `core/events/types/portal/minimap_shape_color/pipeline.py`、`templates.py`、`models.py`（原因：确认 scoring public 函数、DTO 字段和主流程调用契约。）
- `core/events/types/portal/minimap_shape_color_matcher.py`（原因：确认兼容 facade 对 scoring helper 的旧导出是否需要保留。）

**本轮想弄清楚：**
- `combined_response()`、`score_mask_overlap()`、`score_color_similarity()`、`evaluate_candidate()`、`signature_score()` 是否能保持签名不变。
- response 组合、mask overlap、color score、候选评估能否拆成实际评分子模块。
- 如果把 `scoring.py` 替换为同名 package，`minimap_shape_color.pipeline` 的相对 import 是否仍能无缝工作。

### C. 本轮发现

关键发现：
- (verified) 本轮 A 段的函数名需要修订：当前 public 函数是 `combined_shape_color_response()`、`evaluate_shape_color_candidate()`、`mask_response()`、`color_response_map()`、`patch_color_score()`、`f1_score()`、`response_hits()`；不存在 `combined_response()`、`score_mask_overlap()`、`score_color_similarity()`、`evaluate_candidate()`、`signature_score()` 这些当前实现函数名。
- (verified) `pipeline.py` 只从 `.scoring` import `combined_shape_color_response`、`evaluate_shape_color_candidate`、`response_hits`；兼容 facade `minimap_shape_color_matcher.py` 还从 `.scoring` import 旧 public helper 并提供 `_combined_response()`、`_evaluate_candidate()`、`_f1_score()` 等旧私有 wrapper。
- (verified) `scoring.py` 替换成 `scoring/` package 后，相对 import `.scoring import ...` 仍可用；`minimap_shape_color_matcher._f1_score()` 旧 wrapper 仍返回相同行为。
- (verified) 评分逻辑未改阈值：response 组合权重、candidate base score 权重、signature boost、reject reasons 都按原实现搬迁。

修订的旧结论：
- 原先 `minimap_shape_color/scoring.py` 是 shape-color matcher 的单文件评分算法；现在它已经替换为 `minimap_shape_color/scoring/` package，旧 import 路径不变，真实职责按 response/color/overlap/candidate 分类下沉。

代码变更：
- 删除 `core/events/types/portal/minimap_shape_color/scoring.py`
- 新增 `core/events/types/portal/minimap_shape_color/scoring/__init__.py`
- 新增 `core/events/types/portal/minimap_shape_color/scoring/response.py`
- 新增 `core/events/types/portal/minimap_shape_color/scoring/color.py`
- 新增 `core/events/types/portal/minimap_shape_color/scoring/overlap.py`
- 新增 `core/events/types/portal/minimap_shape_color/scoring/candidate.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_shape_color/scoring.py` | 深度完整 | 已删除/替换为同名 package | 追加 | 原 shape-color scoring 已按 response/color/overlap/candidate 拆分。 |
| `core/events/types/portal/minimap_shape_color/scoring/__init__.py` | 新增 | 深度完整 | 1 | 保留旧 scoring public 函数导出。 |
| `core/events/types/portal/minimap_shape_color/scoring/response.py` | 新增 | 深度完整 | 1 | 承接 mask/color response 组合和 response peak suppression。 |
| `core/events/types/portal/minimap_shape_color/scoring/color.py` | 新增 | 深度完整 | 1 | 承接 masked HSV color response 和 patch color score。 |
| `core/events/types/portal/minimap_shape_color/scoring/overlap.py` | 新增 | 深度完整 | 1 | 承接 F1-like mask overlap。 |
| `core/events/types/portal/minimap_shape_color/scoring/candidate.py` | 新增 | 深度完整 | 1 | 承接候选评分、signature boost 和 reject reason 判定。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_shape_color\scoring\__init__.py core\events\types\portal\minimap_shape_color\scoring\response.py core\events\types\portal\minimap_shape_color\scoring\color.py core\events\types\portal\minimap_shape_color\scoring\overlap.py core\events\types\portal\minimap_shape_color\scoring\candidate.py core\events\types\portal\minimap_shape_color\pipeline.py core\events\types\portal\minimap_shape_color_matcher.py core\events\types\portal\minimap_detection\modes.py`
- `python -` smoke：构造 synthetic frame/template/masks，验证 `combined_shape_color_response()`、`mask_response()`、`f1_score()`、`patch_color_score()`、`response_hits()` 和 `evaluate_shape_color_candidate()` 可运行，候选 accepted 且 reject reasons 为空。
- `D:\ACloud\.venv\Scripts\python.exe -c "from core.events.types.portal.minimap_shape_color.scoring import f1_score; from core.events.types.portal.minimap_shape_color.scoring.overlap import f1_score as New; from core.events.types.portal.minimap_shape_color_matcher import _f1_score; assert f1_score is New; import numpy as np; m=np.ones((2,2), dtype=np.uint8)*255; assert _f1_score(m,m)[0] == 1.0; print('ok shape scoring exports')"`

下一轮建议：
- 当前 core 剩余较长文件更多是 stateful facade 或诊断流程：`coordinate/diagnostics.py`、`coordinate/localization.py`、`localization/localize_pipeline.py`、`navigation_tasks/movement/pipeline.py`。若继续拆，建议先选 `coordinate/localization.py`，按 localization evidence、jump/raw/trusted 信号、recovery signal 注册拆分；它和用户关心的“坐标恢复/诊断规范化”更贴近。

## [CORE-OPTIMIZATION-RULES-AND-PLAN-REFRESH] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md`（原因：用户要求先把“不按死行数、按架构准则优化”的规则沉淀成文档。）
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`、`architecture_docs/zh-CN/core/ARCHITECTURE.md`、`CODEBASE.md`（原因：现有规划已经记录大量拆分，但需要按新规则重新聚焦下一阶段优化方案。）
- `core/routing/anchors/`、`core/navigation_tasks/route_context.py`、`core/routing/geometry.py`（原因：RouteContext 与 guide-anchor planner 有 route progress / projection 概念交叉。）
- `core/localization/localize_pipeline.py`、`core/navigation_tasks/coordinate/`、`core/shared/frame_registration.py`（原因：定位证据、坐标恢复和 frame registration 是跨 localization/navigation_tasks/shared 的关键交叉点。）
- `core/events/debug/`、`core/navigation_tasks/debug.py`、`core/navigation_tasks/coordinate/formatting.py`（原因：diagnostics/logging 是当前短期复用但长期可能抽 shared diagnostics 的交叉点。）
- `core/events/models.py`、`core/navigation_tasks/event_task_runner.py`、`core/navigation_tasks/intent_factory.py`（原因：事件动作和导航意图之间是 events 与 navigation_tasks 的稳定 seam。）

**本轮想弄清楚：**
- 当前 core 哪些交叉是合理复用，哪些是重复概念，需要上移或合并。
- 哪些同名文件只是 package 内角色名，不应该误判为重复。
- 下一阶段优化应按什么优先级推进，哪些文件虽然较长但暂不该动。
- 规划文档应如何更新，才能指导后续自动执行。

### C. 本轮发现

关键发现：
- (verified) 已新增 `architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md`，把“不按固定行数拆分”的规则正式沉淀为文档。后续判断标准改为：概念重复、依赖方向、模块深度、状态局部性、真实复用方和主线维护成本。
- (verified) `RouteContext.project()`、`routing.geometry.project_point_onto_path()`、`routing.anchors.progress._project_progress_on_polyline()` 都实现了折线投影/累计 progress；`RouteContext.corridor_anchors()` 与 `routing.anchors.corridor._ordered_corridor_anchors()` 都表达前方 guide anchor 选择。这是当前最明确的重复概念，不是单纯文件长度问题。
- (verified) `localization/localize_pipeline.py` 是定位状态写入主流程，`FrameRegistration` 已在 `core/shared`，`coordinate/localization.py` 消费 raw/trusted/control position、registration fields 和 visual metadata 生成诊断/恢复信号。这里更适合抽 `LocalizationEvidence` 稳定证据模型，而不是把定位 pipeline 机械切碎。
- (verified) `events.debug.formatting` 与 `navigation_tasks.coordinate.formatting` 有纯格式化重复；但 event topic log、coordinate diagnostics log 和 registration field 提取语义不同，短期只适合上移 `format_value/format_fields` 级别的纯格式化，不应急着抽统一 logger。
- (verified) `EventAction` 和 `NavigationIntent` 不是重复模型：前者是 events 的 generic action，后者是 navigation_tasks 的执行意图。`intent_factory.py` 是健康 seam，应固化为唯一翻译层，而不是合并两个模型。
- (verified) 同名文件如 `models.py`、`pipeline.py`、`runtime.py`、`diagnostics.py` 在不同 package 中表达包内角色，不等于重复。只有当同名文件承载同一个稳定契约或同一状态机时，才考虑 shared 或合并。

修订的旧结论：
- 之前“继续拆较长文件”的表述需要收窄。当前 `localize_pipeline.py`、`update_pipeline.py`、`movement/pipeline.py` 等虽然仍有百行以上，但它们是顺序敏感主流程；后续只在发现重复概念或可复用 seam 时拆，不再按行数推进。

新增/更新文档：
- 新增 `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`。
- 更新 `architecture_docs/zh-CN/core/ARCHITECTURE.md`，把规则文档和 V2 规划作为 core 后续优化入口。
- 更新 `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md` 的文档关联。
- 更新 `CODEBASE.md`，补充规则文档和 V2 规划的目录说明与架构摘要。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md` | 新增 | 深度完整 | 1 | 已作为后续 core 优化规则源。 |
| `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md` | 新增 | 深度完整 | 1 | 记录 P1/P2/P3 优化顺序、兼容策略、风险和验证方式。 |
| `core/navigation_tasks/route_context.py` | 深度完整 | 复核完成 | 追加 | 确认 route projection/progress 与 routing 层重复。 |
| `core/routing/geometry.py` | 深度完整 | 复核完成 | 追加 | 确认 `project_point_onto_path()` 是统一 route progress 的主要候选入口。 |
| `core/routing/anchors/progress.py` | 深度完整 | 复核完成 | 追加 | 确认 anchor progress 可委托到未来 `routing/route_progress`。 |
| `core/routing/anchors/corridor.py` | 深度完整 | 复核完成 | 追加 | 确认 corridor policy 与 `RouteContext` 有概念交叉，但阈值暂不合并。 |
| `core/localization/localize_pipeline.py` | 深度完整 | 复核完成 | 追加 | 确认定位状态写入仍应集中，优先抽 evidence 而不是切流程。 |
| `core/navigation_tasks/coordinate/localization.py` | 深度完整 | 复核完成 | 追加 | 确认 raw jump、visual mismatch、long F2F 等应消费稳定证据模型。 |
| `core/navigation_tasks/coordinate/diagnostics.py` | 深度完整 | 复核完成 | 追加 | 确认 public facade 保留，内部可逐步接入 evidence。 |
| `core/shared/frame_registration.py` | 深度完整 | 复核完成 | 追加 | 确认 shared 契约方向正确。 |
| `core/events/debug/` | 深度完整 | 复核完成 | 追加 | 确认 writer/topic/description/formatting 分层合理，暂不抽统一 logger。 |
| `core/events/models.py` | 深度完整 | 复核完成 | 追加 | 确认 `EventAction` 是事件层动作契约。 |
| `core/navigation_tasks/event_task_runner.py` | 深度完整 | 复核完成 | 追加 | 确认事件任务先走 approach gate，再 run handler，再转 intent。 |
| `core/navigation_tasks/intent_factory.py` | 深度完整 | 复核完成 | 追加 | 确认是 EventAction -> NavigationIntent 的翻译 seam。 |

下一轮计划：
- 若开始改实现，优先新增 `core/routing/route_progress/`，让 `RouteContext`、`routing.geometry`、`routing.anchors.progress` 委托同一套 projection/progress 算法。
- 第二优先是 `core/localization/evidence/`，先内部构造并让 coordinate diagnostics 消费，不改 `NavigationCore.localize()` 返回值。
- P2 才处理共享日志格式化和 EventAction/NavigationIntent seam 文档固化。
- 继续保留旧 import 壳子，GUI 优化前不做 legacy cleanup。

## [SYNC-ROUTE-PROGRESS-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/routing/route_progress/`（原因：新增 routing 内部统一折线投影、累计进度和插值算法包，承接 V2 P1。）
- `core/routing/geometry.py`（原因：旧 `build_cumulative_lengths()`、`project_point_onto_path()`、`interpolate_by_distance()` 必须保留返回形态，但实现可委托新包。）
- `core/navigation_tasks/route_context.py`（原因：`RouteContext.project()`、`progress_of()`、`corridor_anchors()` 当前自带一套 route progress 逻辑，应接入统一投影算法。）
- `core/routing/anchors/progress.py`（原因：anchor progress 当前也自带一套 int polyline projection，应委托统一算法并保留旧 helper。）
- `core/routing/anchors/corridor.py`（原因：需要确认 corridor policy 暂不被合并，只复用 progress 算法。）
- `core/navigation_tasks/movement/path_planner.py`、`core/navigation_tasks/movement/pipeline.py`（原因：它们依赖 geometry 和 RouteContext 的旧返回字段，改动后必须验证旧调用面。）

**本轮想弄清楚：**
- 能否把三处折线投影统一到 `core/routing/route_progress/`，同时不改变旧 public API 和 dict/dataclass 返回形态。
- `RouteContext` 的 float 路线点与 anchors 的 int 点能否共用同一算法，且保持各自 wrapper 的坐标精度语义。
- `routing.geometry.project_point_onto_path()` 的字段名 `distance`、`distance_to_path` 能否原样保留，避免 movement pipeline 断裂。
- corridor anchor 阈值是否需要暂时保持各自 policy，只共享 progress/projection 基础能力。

### C. 本轮发现

关键发现：
- (verified) 新增 `core/routing/route_progress/` 后，折线累计长度、点到折线投影和按累计距离插值已有单一实现：`route_progress.projection.build_cumulative_lengths()`、`project_point_on_polyline()`、`interpolate_by_distance()`。
- (verified) `routing.geometry.build_cumulative_lengths()`、`project_point_onto_path()`、`interpolate_by_distance()` 已改为兼容 wrapper；`project_point_onto_path()` 仍返回旧 dict 字段：`point`、`segment_index`、`distance`、`distance_to_path`。
- (verified) `RouteContext.project()` 已委托 `project_point_on_polyline()`，再包装为旧 `RouteProjection` dataclass；`RouteContext.points`、`progress_of()`、`corridor_anchors()` 调用面不变。
- (verified) `routing.anchors.progress._anchor_cumulative_lengths()` 和 `_project_progress_on_polyline()` 已委托 `route_progress`；`anchor_route_progress()` 仍返回 float progress，`anchor_progress_map()` 仍返回 `{int_point: progress}`。
- (verified) 本轮没有合并 corridor policy。`RouteContext.corridor_anchors()` 和 `routing.anchors.corridor._ordered_corridor_anchors()` 仍分别保留自己的阈值语义，只共享底层 projection/progress。

修订的旧结论：
- `RouteContext` 不再是 route projection 算法拥有者；它现在是 navigation task 的 route runtime context。
- `routing.geometry` 不再是投影算法权威实现；它是 legacy-compatible route math surface。
- `routing.anchors.progress` 不再手写投影，只保留 anchor order/dedupe/progress map 和旧私有 helper wrapper。

代码变更：
- 新增 `core/routing/route_progress/__init__.py`
- 新增 `core/routing/route_progress/models.py`
- 新增 `core/routing/route_progress/projection.py`
- 更新 `core/routing/geometry.py`
- 更新 `core/navigation_tasks/route_context.py`
- 更新 `core/routing/anchors/progress.py`
- 更新 `core/routing/__init__.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/routing/route_progress/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出 `PolylineProjection` 和投影/累计/插值 helper。 |
| `core/routing/route_progress/models.py` | 新增 | 深度完整 | 1 | 承接 `PolylineProjection` DTO。 |
| `core/routing/route_progress/projection.py` | 新增 | 深度完整 | 1 | 承接折线累计长度、投影和插值权威算法。 |
| `core/routing/geometry.py` | 深度完整 | 深度完整 | 追加 | 旧 route math API 保留，projection/progress 委托新包。 |
| `core/navigation_tasks/route_context.py` | 复核完成 | 深度完整 | 追加 | `RouteContext.project()` 委托新包并包装旧 `RouteProjection`。 |
| `core/routing/anchors/progress.py` | 复核完成 | 深度完整 | 追加 | anchor progress 旧函数保留，累计/投影委托新包。 |
| `core/routing/anchors/corridor.py` | 复核完成 | 复核完成 | 追加 | corridor policy 暂未合并，只继续使用 anchors progress helper。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\routing\route_progress\__init__.py core\routing\route_progress\models.py core\routing\route_progress\projection.py core\routing\geometry.py core\routing\anchors\progress.py core\routing\anchors\corridor.py core\routing\anchors\planner.py core\routing\__init__.py core\navigation_tasks\route_context.py core\navigation_tasks\movement\path_planner.py core\navigation_tasks\movement\pipeline.py`
- `python -` smoke：验证 `build_cumulative_lengths()`、`project_point_onto_path()`、`interpolate_by_distance()` 和 `project_point_on_polyline()` 的旧/新返回语义。
- `python -` smoke：验证 `RouteContext.project()`、`progress_of()`、`corridor_anchors()` 旧 dataclass/返回行为。
- `python -` smoke：验证 `anchor_progress_map()`、`anchor_route_progress()`、`_project_progress_on_polyline()` 和 `plan_path_with_optional_anchors()` 的 `anchor_step` 行为。

下一轮计划：
- 继续 V2 P1 第二段：新增 `core/localization/evidence/`，先从 `FrameRegistration`、raw/trusted/control position、confidence 构造 evidence，并让 `CoordinateDiagnostics.record_localization()` 内部消费；不改 `NavigationCore.localize()` 返回值，不改诊断阈值。

## [SYNC-LOCALIZATION-EVIDENCE-PACKAGE] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/localization/evidence/`（原因：新增 localization evidence 稳定证据包，承接 V2 P1 第二段。）
- `core/shared/frame_registration.py`（原因：evidence 要从当前共享配准契约读取 source/confidence/player/origin/metadata。）
- `core/navigation_tasks/coordinate/localization.py`（原因：当前定位诊断散读 raw/trusted/control、registration fields 和 visual metadata，应内部改为消费 evidence。）
- `core/navigation_tasks/coordinate/formatting.py`（原因：当前 `registration_fields()` 和 point 标准化逻辑可作为 evidence builder 的输入参照，旧函数必须保留。）
- `core/navigation_tasks/coordinate/diagnostics.py`（原因：`CoordinateDiagnostics.record_localization()` public 签名必须不变，只能内部委托。）
- `core/navigation_tasks/update_pipeline.py`（原因：确认调用方仍按旧参数传入，不改 update 主链。）

**本轮想弄清楚：**
- 是否能定义 `LocalizationEvidence`，稳定承载 raw/trusted/control position、confidence、min_confidence、registration fields 和 visual metadata。
- `record_localization_diagnostics()` 能否内部构造 evidence 后再执行原逻辑，保持 public 签名不变。
- visual mismatch、raw jump、raw/control gap、long F2F tracking、active relocalization 检查能否全部从 evidence 字段读取，不再在流程里反复散读 registration metadata。
- 是否可以做到不改 `NavigationCore.localize()` 返回值、不改 `FrameRegistration` dataclass、不改诊断阈值和恢复信号策略。

### C. 本轮发现

关键发现：
- (verified) 已新增 `core/localization/evidence/`，提供 `LocalizationEvidence`、`VisualCheckEvidence` 和 `build_localization_evidence()`。证据对象稳定承载 raw/trusted/control 坐标、confidence/min_confidence、registration source/confidence/player/origin/metadata 和 visual check 字段。
- (verified) `CoordinateDiagnostics.record_localization()` public 签名未改；`coordinate/localization.record_localization_diagnostics()` 内部先构造 evidence，再执行原诊断流程。
- (verified) raw jump、raw/control gap、visual mismatch、long F2F tracking、active relocalization 检查已从 evidence 字段读取。旧 `reg_fields` 私有调用仍通过兼容 wrapper 可用。
- (verified) `coordinate/formatting.registration_fields()` 和 `float_point_or_none()` 仍保留旧导出，但内部委托 localization evidence builder，避免两套 registration 字段规则。
- (verified) `NavigationCore.localize()` 返回值没有变化，`FrameRegistration` dataclass 没有变化，诊断阈值和恢复信号策略没有变化。

修订的旧结论：
- `FrameRegistration` 仍是 localization 对外的帧配准契约；`LocalizationEvidence` 是 navigation diagnostics 消费层的稳定证据对象，不替代 `FrameRegistration`。
- `coordinate/localization.py` 不再散读 raw registration metadata 作为主逻辑入口，而是从 evidence 的 properties 和 visual DTO 读取。

代码变更：
- 新增 `core/localization/evidence/__init__.py`
- 新增 `core/localization/evidence/models.py`
- 新增 `core/localization/evidence/builder.py`
- 更新 `core/navigation_tasks/coordinate/formatting.py`
- 更新 `core/navigation_tasks/coordinate/localization.py`
- 更新 `core/navigation_tasks/coordinate/diagnostics.py`
- 更新 `core/navigation_tasks/coordinate/relocalization.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/localization/evidence/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出 evidence DTO 和 builder。 |
| `core/localization/evidence/models.py` | 新增 | 深度完整 | 1 | 承接 `LocalizationEvidence`、`VisualCheckEvidence`。 |
| `core/localization/evidence/builder.py` | 新增 | 深度完整 | 1 | 从 `FrameRegistration`、坐标和 confidence 构造 evidence。 |
| `core/navigation_tasks/coordinate/formatting.py` | 深度完整 | 深度完整 | 追加 | registration/point 标准化委托 evidence，日志格式化仍保留。 |
| `core/navigation_tasks/coordinate/localization.py` | 深度完整 | 深度完整 | 追加 | 定位诊断主流程内部消费 evidence，旧 public 函数签名保留。 |
| `core/navigation_tasks/coordinate/diagnostics.py` | 深度完整 | 深度完整 | 追加 | 私有 wrapper 同时支持旧 `reg_fields` 和新 `evidence`。 |
| `core/navigation_tasks/coordinate/relocalization.py` | 深度完整 | 深度完整 | 追加 | active relocalization 检查支持 evidence 和旧 reg_fields。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\localization\evidence\__init__.py core\localization\evidence\models.py core\localization\evidence\builder.py core\navigation_tasks\coordinate\formatting.py core\navigation_tasks\coordinate\localization.py core\navigation_tasks\coordinate\diagnostics.py core\navigation_tasks\coordinate\relocalization.py core\navigation_tasks\update_pipeline.py core\shared\frame_registration.py`
- `python -` smoke：验证 `build_localization_evidence()` 生成 raw/trusted/control、registration fields 和 visual mismatch 证据。
- `python -` smoke：验证 visual mismatch 达到 required frames 后仍生成 relocalization request。
- `python -` smoke：验证 raw jump 仍生成 relocalization request，并且旧 `reg_fields` 私有兼容调用仍能判定 f2f。

下一轮计划：
- 继续 V2 P2：新增 `core/shared/diagnostics/formatting.py`，只上移纯 `format_value/format_fields`，让 `events.debug.formatting` 和 `coordinate.formatting` 委托；不动 event writer、topic routing 或 coordinate log 文件。

## [SYNC-SHARED-DIAGNOSTICS-FORMATTING] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `core/shared/diagnostics/`（原因：新增共享诊断格式化包，只承接纯值/字段字符串格式化。）
- `core/events/debug/formatting.py`（原因：事件日志 `_format_value()`、`_format_fields()` 当前与 coordinate 格式化重复，旧私有导出必须保留。）
- `core/navigation_tasks/coordinate/formatting.py`（原因：坐标日志 `format_value()`、`format_fields()` 可委托 shared，但 registration/point/distance 仍属 coordinate。）
- `core/events/debug/descriptions.py`、`core/events/debug/topics.py`、`core/events/debug/writer.py`（原因：确认事件日志 topic、writer、action/task 描述不改。）
- `core/navigation_tasks/coordinate/log.py`（原因：确认坐标日志文件 writer 不改。）

**本轮想弄清楚：**
- 能否只上移 `format_value()` / `format_fields()`，不引入统一 logger。
- `core.events.debug._format_value`、`_format_fields` 旧私有导出是否能保持。
- `coordinate.formatting.format_value()`、`format_fields()` 旧导出是否能保持。
- event topic routing 和 coordinate log 文件路径是否完全不受影响。

### C. 本轮发现

关键发现：
- (verified) 已新增 `core/shared/diagnostics/formatting.py`，只承接纯 `format_value()`、`format_fields()`。
- (verified) `core/events/debug/formatting.py` 保留 `_format_value()`、`_format_fields()` 旧私有函数名，内部委托 shared diagnostics。
- (verified) `core/navigation_tasks/coordinate/formatting.py` 保留 `format_value()`、`format_fields()` 旧导出，内部委托 shared diagnostics；registration/point/distance 仍留在 coordinate/evidence 相关模块。
- (verified) 本轮没有合并 `events.debug.writer`、`events.debug.topics`、`coordinate.log`；事件 topic log 和 `logs/coordinate_diagnostics.log` 语义不变。

代码变更：
- 新增 `core/shared/diagnostics/__init__.py`
- 新增 `core/shared/diagnostics/formatting.py`
- 更新 `core/events/debug/formatting.py`
- 更新 `core/navigation_tasks/coordinate/formatting.py`

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/shared/diagnostics/__init__.py` | 新增 | 深度完整 | 1 | 聚合导出共享格式化函数。 |
| `core/shared/diagnostics/formatting.py` | 新增 | 深度完整 | 1 | 承接纯值/字段字符串格式化。 |
| `core/events/debug/formatting.py` | 深度完整 | 深度完整 | 追加 | 旧私有函数名保留，委托 shared。 |
| `core/navigation_tasks/coordinate/formatting.py` | 深度完整 | 深度完整 | 追加 | 坐标诊断专属 helper 保留，format 函数委托 shared。 |

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\shared\diagnostics\__init__.py core\shared\diagnostics\formatting.py core\events\debug\formatting.py core\events\debug\descriptions.py core\events\debug\topics.py core\events\debug\writer.py core\navigation_tasks\coordinate\formatting.py core\navigation_tasks\coordinate\log.py core\navigation_tasks\coordinate\localization.py`
- `python -` smoke：验证 shared/event/coordinate 三个入口对 Enum、float、tuple/list、dict 输出一致。
- `python -` smoke：验证 `events.debug.writer._build_line()` 输出仍包含原字段格式。

下一轮计划：
- 固化 V2 P2 的 EventAction -> NavigationIntent seam：更新 `navigation_tasks` 和 `events` 中文架构文档，明确 event handler 只能返回 `EventAction`，`intent_factory.py` 是唯一翻译层；代码层暂不拆 `intent_factory.py`。

## [SYNC-EVENT-ACTION-NAVIGATION-INTENT-SEAM] 2026-05-27

### A. 本轮目标（阅读前声明）

**目标文件/目录：**
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`（原因：固化导航任务系统拥有 `EventAction -> NavigationIntent` 翻译 seam。）
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`（原因：固化事件系统只输出 generic `EventAction`，不执行真实输入。）
- `core/events/models.py`、`core/navigation_tasks/event_task_runner.py`、`core/navigation_tasks/intent_factory.py`（原因：本轮只复核 seam，不拆代码。）

**本轮想弄清楚：**
- 是否需要拆 `intent_factory.py`，还是先只文档固化。
- 是否能明确阻止具体 event handler 直接依赖 `MotionController`、GUI 或输入执行器。
- 是否能保持事件系统和导航任务系统各自模型独立，不合并 `EventAction` 与 `NavigationIntent`。

### C. 本轮发现

关键发现：
- (verified) `EventAction` 和 `NavigationIntent` 是两个不同系统的稳定契约，不应合并。事件系统表达“想做什么”，导航任务系统表达“当前帧要交给 GUI/input 执行什么”。
- (verified) `core/navigation_tasks/event_task_runner.py` 是事件任务执行桥：先经过 event approach gate，再调用 `EventCoordinator.run_task()`，再把 `EventAction` 交给 `intent_factory.py`。
- (verified) `core/navigation_tasks/intent_factory.py` 当前接口窄、语义集中；虽然同时处理 movement step 和 event action，但没有必要为拆而拆。
- (verified) 已在中文 `events` 和 `navigation_tasks` 架构文档中明确：event handler 只能返回 `EventAction | None`，不能直接调用输入执行器；`intent_factory.py` / `event_task_runner.py` 是唯一翻译链路。

代码变更：
- 无。本轮只更新中文架构文档和 CODEBASE，不改实现。

更新文档：
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` | 深度完整 | 已同步 seam 规则 | 追加 | 明确 `intent_factory.py` 是 EventAction 到 NavigationIntent 的稳定翻译层。 |
| `architecture_docs/zh-CN/core/events/ARCHITECTURE.md` | 深度完整 | 已同步 seam 规则 | 追加 | 明确 event handler 只返回 `EventAction`，不执行真实输入。 |
| `core/navigation_tasks/intent_factory.py` | 深度完整 | 暂不改 | 追加 | 接口窄、语义集中，保留单文件。 |
| `core/navigation_tasks/event_task_runner.py` | 深度完整 | 暂不改 | 追加 | 继续作为 event approach + run_task + intent conversion 桥。 |

下一轮计划：
- V2 已规划的 core P1/P2 全部执行完毕。下一轮进入 core 收尾审计：跑一次 core import/compile 汇总，检查新增包文档和 CODEBASE 是否一致，并给出是否还有值得立即动的 core 优化候选。
## [GUI-OPTIMIZATION-PLAN] 2026-05-27

### A. 本轮目标（阅读前声明）
**目标文件/目录：**
- `gui/`（原因：用户要求按 core 的架构优化规则阅读 GUI，先形成结构化拆分规划；本轮只规划，不改实现。）
- `gui/modes/`（原因：导航、建图等主要交互模式通常承担 GUI 编排逻辑，是最可能出现长文件和跨系统耦合的位置。）
- `gui/dialogs/`（原因：高级设置、导航参数、颜色选择等配置 UI 可能混合表单、持久化、参数适配和领域含义，需要判断是否应拆成组件/适配/IO。）
- `gui/widgets` / `gui/*context*` / `gui/navigation_params.py`（原因：确认 GUI 公共组件、应用组合根和参数模型是否已经有模块边界。）
- `CODEBASE.md` 与现有 `architecture_docs/zh-CN/gui/` 文档（原因：先对齐已有项目知识，避免重复规划或覆盖旧结论。）

**本轮想弄清楚：**
- GUI 当前有哪些系统、模块、组件边界，哪些只是旧兼容壳子或历史残留。
- 哪些长文件是合理的状态编排，哪些存在“表单定义/业务适配/文件 IO/运行时控制/渲染组件”混杂。
- GUI 和 core 的调用关系如何迁移到新 core 包结构，同时保留旧兼容入口，避免外部调用断裂。
- 是否需要建立 `gui/modes/navigation/`、`gui/modes/mapping/`、`gui/dialogs/nav_params/` 等包级结构，而不是继续扁平化 helper。
- 下一阶段应按什么优先级执行：先模式拆分、再对话框拆分、再兼容层迁移，还是先迁移 core import。

### C. 本轮发现

关键发现：
- (verified) `gui/modes/navigation_mode.py` 仍是 GUI 最大热点，约 1500+ 行；问题不是行数本身，而是同一个 QWidget 同时拥有 UI 构建、地图加载、配置应用、路线编辑、事件系统 bridge、manual portal test、overlay item 生命周期、导航 QTimer loop、`NavigationIntent` 输入执行和 main-window topmost/lower 管理。
- (verified) `gui/main_window.py::closeEvent()` 当前直接调用 `mapping_widget.capture_timer.stop()` 并调用 `nav_widget.toggle_navigation()`；这是脆弱 shell seam，因为 shell 知道子页面 timer，并且 `toggle_navigation()` 是切换命令，不是幂等 stop。
- (verified) `gui/modes/mapping_widget.py` 约 550 行，核心混合点是 `capture_and_process()`：capture、player fallback、recognizer mask、stitcher add frame、display update、statistics update 住在一个 widget 方法里；现有 `mapping/save_load.py`、`map_renderer.py`、`params_adapter.py` 有价值，但主流程仍在 widget。
- (verified) `gui/dialogs/nav_params_dialog.py` 约 700+ 行，主要混合字段 UI 构建、widget map、`NavConfig` dataclass replace、文本解析和 Qt screen bounds adapter；已经抽出的 `nav_params/screen_estimator.py` 是正确方向。
- (verified) `EventManagerDialog` 虽然有 300+ 行，但已经接近 schema-driven dialog，使用 command-style signals，不应优先拆；只有出现第二个 schema form 时再抽通用 schema renderer。
- (verified) GUI 仍通过旧 core facade import：`core.navigation_core`、`core.motion_controller`、`core.route_manager`、`core.recognizer_optimized` 和 `from core import ...`。本阶段不删 wrapper，新 GUI 模块优先 import core system packages，等 GUI 迁完再清理兼容层。

修订的旧结论：
- 之前“继续拆长文件”的表述需要收窄。GUI 拆分也必须按概念 seam 和状态 locality 推进：先生命周期和输入/配置 seam，再路线/事件 adapter，再 runtime loop；dialog layout 不应先被机械拆成 section helper。

新增/更新文档：
- 新增 `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md`。
- 更新 `architecture_docs/zh-CN/gui/ARCHITECTURE.md`，把 GUI 优化主线指向新规划。
- 更新 `CODEBASE.md`，补充 GUI 优化规划文档说明。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/main_window.py` | 深度完整 | 复核完成 | 追加 | 确认 shutdown seam 是 GUI 第一小步。 |
| `gui/app_context.py` | 深度完整 | 复核完成 | 追加 | 确认仍是共享 core services 对象袋，后续 composition 可加深。 |
| `gui/modes/navigation_mode.py` | 深度完整 | 复核完成 | 追加 | 确认导航 widget 的输入、事件、配置、runtime loop 是优先拆分目标。 |
| `gui/modes/mapping_widget.py` | 深度完整 | 复核完成 | 追加 | 确认建图 capture loop 和 presentation/session 是后续 mapping 主目标。 |
| `gui/dialogs/nav_params_dialog.py` | 深度完整 | 复核完成 | 追加 | 确认 config binding/specs 是 dialog 首要 seam。 |
| `gui/dialogs/event_manager_dialog.py` | 深度完整 | 复核完成 | 追加 | 确认暂不优先拆，保持 schema-driven dialog。 |
| `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md` | 新增 | 深度完整 | 1 | 记录 GUI 分阶段优化计划、目录结构、兼容策略和验证点。 |

下一轮计划：
- 若用户确认执行，先做阶段 A：给 `MappingWidget`、`NavigationModeWidget` 增加幂等 `stop_runtime()`，让 `MainWindow.closeEvent()` 只调用 runtime stop；随后按规划进入 navigation input/window mode 和 intent executor 拆分。
## [GUI-FULL-FILE-READ-PLAN-REFINE] 2026-05-27

### A. 本轮目标（阅读前声明）
**目标文件/目录：**
- `gui/**/*.py`（原因：用户指出上一轮规划只覆盖外层和热点文件，不足以支撑 GUI 全量模块化；本轮必须覆盖 GUI 所有实现文件。）
- `gui/**/*.md` 与 `architecture_docs/zh-CN/gui/**/*.md`（原因：对齐已有 GUI 架构记录和本轮新规划，避免文档结论互相打架。）
- `CODEBASE.md` 中 GUI 相关章节（原因：最终规划必须和 living codebase 文档一致。）

**本轮想弄清楚：**
- `gui` 每个文件的职责、导出、主要依赖、状态归属、是否适合继续拆分。
- `modes/navigation`、`modes/mapping`、`dialogs/*`、`selection`、`widgets` 内部每个文件的真实深度：哪些是深模块，哪些只是浅 adapter，哪些可以合并或加深。
- 全量拆分规划要细化到文件级和包级，不只停留在 shell/modes/dialogs 的外层分类。
- 哪些旧路径必须保留 wrapper，哪些新模块应优先放入子包，避免扁平结构。

### C. 本轮发现

关键发现：
- (verified) 本轮已核对 `gui/` 下 41 个非缓存文件，包括全部 `*.py` 和本地 `ARCHITECTURE.md`，并额外对齐 `architecture_docs/zh-CN/gui/` 现有中文架构文档。
- (verified) `gui/modes/navigation_mode.py` 是 GUI 最大系统化目标；它内部不是一个单纯长文件，而是 shell、map session/config、route editing、event bridge、runtime loop、intent execution、game input window mode、presentation/calibration 八条职责线混合。
- (verified) `gui/modes/navigation/` 下多个同名 helper 不是重复系统，而是“按调用点临时抽出的函数层”：`event_overlay.py`、`route_overlay.py`、`viewport_overlay.py` 偏 presentation，`map_runtime.py` 混合 map IO/config/capture geometry，`event_adapter.py` 是 event bridge。下一步应按 package 深化到 `input/`、`map/`、`route/`、`events/`、`runtime/`、`presentation/`，不是继续平铺 helper。
- (verified) `gui/modes/mapping_widget.py` 的主要问题是 `capture_and_process()` 里把 capture、player fallback、recognizer、stitcher、display、stats 串在一个 QWidget 方法中；应优先抽 `MappingSession.tick()` 和 presenter，不应先机械拆 layout。
- (verified) `gui/dialogs/nav_params_dialog.py` 的主要问题是字段规格、控件创建、信号绑定、`NavConfig` 写回和 screen bounds adapter 混在一个类；应先抽 `config_binding.py` / `field_specs.py`，后抽 section layout。
- (verified) `EventManagerDialog` 虽然不短，但已经是 schema-driven dialog 并使用 command-style signals；不适合优先拆，除非后续出现第二个 schema form。
- (verified) `widgets/selection` 绝大部分是合格 GUI 组件/overlay；明确行为风险是 `ScalableMapWidget.pixel_clicked` 声明和 `MappingWidget.on_map_click()` 连接存在，但 mouse handler 当前不 emit 坐标。

修订的旧结论：
- 上一轮 `GUI_OPTIMIZATION_PLAN.md` 的系统级规划方向仍成立，但粒度不够。本轮新增全文件级 V2 规划，将每个 `gui` 文件明确标注为保留、加深、迁移、拆分或暂缓。
- `modes/navigation` 内部同名/相近文件不代表系统重复，而是同一 navigation mode 中不同 presentation/adapter seam 的早期函数层。后续要按“状态拥有者 + 功能包”重组，而不是合并所有同名 helper。

新增/更新文档：
- 新增 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`。
- 更新 `architecture_docs/zh-CN/gui/ARCHITECTURE.md`，链接全文件级规划。
- 更新 `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md`，说明该文件是阶段主线，逐文件审计以 V2 文档为准。
- 更新 `CODEBASE.md`，补充新 GUI 全文件级规划文档说明。
- 更新 `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/__init__.py` | PENDING | 深度完整 | 1 | 确认只 re-export `MainWindow`，保留兼容入口。 |
| `gui/app_context.py` | 复核完成 | 深度完整 | 追加 | 确认是共享 core service 对象袋，composition root 可后续加深。 |
| `gui/main_window.py` | 复核完成 | 深度完整 | 追加 | 确认 `closeEvent()` 是第一生命周期 seam。 |
| `gui/navigation_params.py` | 深度完整 | 深度完整 | 追加 | 确认是稳定 config contract，暂不移动。 |
| `gui/widgets/__init__.py` | PENDING | 深度完整 | 1 | 只聚合 widget 导出。 |
| `gui/widgets/clickable_label.py` | PENDING | 深度完整 | 1 | 坐标映射组件清晰，可作为 scalable map 点击映射参考。 |
| `gui/widgets/collapsible_group.py` | PENDING | 深度完整 | 1 | 只包装 scalable map 和 zoom buttons。 |
| `gui/widgets/scalable_map.py` | PENDING | 深度完整 | 1 | 确认声明 `pixel_clicked` 但未 emit，是建图页点击语义风险。 |
| `gui/selection/center_selector.py` | PENDING | 深度完整 | 1 | 中心点全屏选择 overlay，调用方负责 DPR 转换。 |
| `gui/selection/indicator_overlay.py` | PENDING | 深度完整 | 1 | 点击穿透监控幕布，后续可替换 print debug。 |
| `gui/selection/region_overlay.py` | PENDING | 深度完整 | 1 | 拉框区域选择 overlay，边界清晰。 |
| `gui/modes/event_test_controller.py` | PENDING | 深度完整 | 1 | 手动事件测试按钮状态同步小模块。 |
| `gui/modes/mapping_widget.py` | 复核完成 | 深度完整 | 追加 | 确认 capture-recognize-stitch session 是主拆分目标。 |
| `gui/modes/mapping/__init__.py` | PENDING | 深度完整 | 1 | mapping helper 包入口。 |
| `gui/modes/mapping/map_renderer.py` | PENDING | 深度完整 | 1 | presentation helper 有价值，可加深为 presenter。 |
| `gui/modes/mapping/params_adapter.py` | PENDING | 深度完整 | 1 | 仍是浅 adapter，后续迁到 params/binding。 |
| `gui/modes/mapping/save_load.py` | PENDING | 深度完整 | 1 | IO helper 有价值，但项目根推导应后续注入。 |
| `gui/modes/navigation_mode.py` | 复核完成 | 深度完整 | 追加 | 完整分组为 shell/map/route/events/runtime/input/presentation/calibration。 |
| `gui/modes/navigation/__init__.py` | PENDING | 深度完整 | 1 | navigation helper 包入口。 |
| `gui/modes/navigation/event_adapter.py` | PENDING | 深度完整 | 1 | event bridge helper；旧 action 接管判定函数暂不删。 |
| `gui/modes/navigation/event_overlay.py` | PENDING | 深度完整 | 1 | event marker 绘制 helper，presentation seam 清晰。 |
| `gui/modes/navigation/map_runtime.py` | PENDING | 深度完整 | 1 | 同时承载 map IO/config/capture geometry，应拆到 map/capture 包。 |
| `gui/modes/navigation/route_overlay.py` | PENDING | 深度完整 | 1 | route overlay 只绘制不改 route 状态，边界正确。 |
| `gui/modes/navigation/viewport_overlay.py` | PENDING | 深度完整 | 1 | 纯矩形几何 helper，可迁到 presentation/capture。 |
| `gui/dialogs/nav_params_dialog.py` | 复核完成 | 深度完整 | 追加 | 确认 config binding/specs 是首要 seam。 |
| `gui/dialogs/nav_params/__init__.py` | PENDING | 深度完整 | 1 | nav params helper 包入口。 |
| `gui/dialogs/nav_params/screen_estimator.py` | PENDING | 深度完整 | 1 | 纯点击半径估算 helper，保留。 |
| `gui/dialogs/advanced_settings_dialog.py` | PENDING | 深度完整 | 1 | legacy 调参面板，先 signal 化直接 parent mutation。 |
| `gui/dialogs/advanced_settings/__init__.py` | PENDING | 深度完整 | 1 | advanced settings helper 包入口。 |
| `gui/dialogs/advanced_settings/file_io.py` | PENDING | 深度完整 | 1 | snapshot IO 边界清晰，保留。 |
| `gui/dialogs/advanced_settings/params_adapter.py` | PENDING | 深度完整 | 1 | 控件属性耦合仍在，后续可 field specs 化。 |
| `gui/dialogs/advanced_settings/presets.py` | PENDING | 深度完整 | 1 | 纯预设数据模块，保留。 |
| `gui/dialogs/color_picker_dialog.py` | PENDING | 深度完整 | 1 | `update_preview()` 是下一步 preview/stats 抽取点。 |
| `gui/dialogs/color_picker/__init__.py` | PENDING | 深度完整 | 1 | color picker helper 包入口。 |
| `gui/dialogs/color_picker/debug_output.py` | PENDING | 深度完整 | 1 | debug 输出 opt-in，保留。 |
| `gui/dialogs/color_picker/hsv_ranges.py` | PENDING | 深度完整 | 1 | 纯 HSV math helper，保留。 |
| `gui/dialogs/color_picker/image_renderer.py` | PENDING | 深度完整 | 1 | Qt image renderer helper，保留。 |
| `gui/dialogs/event_manager_dialog.py` | 复核完成 | 深度完整 | 追加 | schema-driven dialog 足够深，暂缓拆。 |
| `gui/ARCHITECTURE.md` | PENDING | 已读 | 1 | 本地英文/混合架构文档，后续不主动更新。 |
| `gui/modes/ARCHITECTURE.md` | PENDING | 已读 | 1 | 本地 modes 架构文档，中文镜像为准。 |
| `gui/modes/navigation/ARCHITECTURE.md` | PENDING | 已读 | 1 | 本地 navigation 架构文档，中文镜像为准。 |
| `gui/dialogs/ARCHITECTURE.md` | PENDING | 已读 | 1 | 本地 dialogs 架构文档，中文镜像为准。 |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | 新增 | 深度完整 | 1 | 本轮全文件级规划输出，覆盖所有 GUI 文件。 |

验证：
- 本轮只改中文文档和 `CODEBASE.md`，未改实现代码，未运行 GUI py_compile。

下一轮计划：
- 等用户确认执行后，从 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 A 开始：先做 `stop_runtime()` 生命周期收口和 `ScalableMapWidget.pixel_clicked` 行为缺口，再进入 navigation input/config seam。

## [GUI-STAGE-A-LIFECYCLE-CLICK-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 用户确认按 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 开始执行 GUI 优化；本轮执行阶段 A。

**直接变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/navigation_mode.py`
- `gui/main_window.py`
- `gui/widgets/scalable_map.py`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
- `CODEBASE.md`

**预计连带影响：**
- `MainWindow.closeEvent()` 不再依赖子 widget 内部 timer 或 toggle 语义。
- `MappingWidget` 和 `NavigationModeWidget` 对外新增幂等 `stop_runtime()`，旧 UI slot 保留。
- `ScalableMapWidget.pixel_clicked` 从声明状态变成实际可用 signal，`MappingWidget.on_map_click()` 原接线开始生效。
- 上下文压缩/接力后必须先读 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`，再继续后续 GUI 阶段。

### C. SYNC 结果

关键发现：
- (verified) `MappingWidget.toggle_monitoring()` 的停止分支已改为调用 `stop_runtime()`；`stop_runtime()` 停止 capture timer、复位 `app_context.monitoring` 并恢复开始按钮文本。
- (verified) `NavigationModeWidget.toggle_navigation()` 的停止分支已改为调用 `stop_runtime()`；`stop_runtime()` 幂等关闭 nav timer、motion controller、auto navigation、manual portal test、navigation task controller 和游戏输入窗口模式。
- (verified) `MainWindow.closeEvent()` 已不再直接访问子页面 timer，也不再调用 toggle 命令，而是只调用两个 mode 的 `stop_runtime()`。
- (verified) `ScalableMapWidget` 已区分拖拽和点击；释放左键且累计拖拽位移不超过 3 像素时，把 label 坐标按当前居中偏移和缩放比例映射回原图坐标并发出 `pixel_clicked`。

代码变更：
- `gui/modes/mapping_widget.py`
- `gui/modes/navigation_mode.py`
- `gui/main_window.py`
- `gui/widgets/scalable_map.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\main_window.py gui\modes\mapping_widget.py gui\modes\navigation_mode.py gui\widgets\scalable_map.py` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/main_window.py` | 深度完整 | 已同步 Stage A | 追加 | `closeEvent()` 只依赖 mode lifecycle seam。 |
| `gui/modes/mapping_widget.py` | 深度完整 | 已同步 Stage A | 追加 | 新增幂等 `stop_runtime()`，停止监控不再散落在 shell。 |
| `gui/modes/navigation_mode.py` | 深度完整 | 已同步 Stage A | 追加 | 新增幂等 `stop_runtime()`，停止导航不再依赖 toggle 语义。 |
| `gui/widgets/scalable_map.py` | 深度完整 | 已同步 Stage A | 追加 | `pixel_clicked` 由声明变成真实原图坐标 signal。 |

下一轮计划：
- 进入 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 B：抽 `navigation/input/window_mode.py`、`navigation/input/intent_executor.py`、`navigation/map/config_applier.py`，保持 `NavigationModeWidget` 旧方法作为 shell wrapper。
## [GUI-PLAN-EXECUTION-RESUME] 2026-05-27

### A. 本轮目标（阅读前声明）
**触发任务：** 根据 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 继续执行 GUI 模块化优化，并在上下文压缩后先阅读计划文档恢复现场。

**目标文件：**
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`（恢复 GUI 全文件优化计划、阶段顺序、已完成/待执行项）
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`（确认上一轮 Stage A 是否已完整记录 C 结果）
- `gui/main_window.py`、`gui/modes/mapping_widget.py`、`gui/modes/navigation_mode.py`、`gui/widgets/scalable_map.py`（复核 Stage A 实际改动与验证范围）
- 后续按计划进入 Stage B：`gui/modes/navigation/input/*`、`gui/modes/navigation/map/*` 及其调用方

**本轮想弄清楚：**
- Stage A 是否只剩日志/验证收尾，是否存在未同步的 CODEBASE 内容。
- Stage B 的输入、窗口模式、配置应用 seam 应该以哪些文件和调用点为最小安全批次推进。

## [GUI-STAGE-B-NAVIGATION-INPUT-CONFIG-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 按 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 B 拆分 Navigation 输入与配置 seam，并保留 `NavigationModeWidget` 旧方法作为兼容壳子。

**直接变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/input/__init__.py`
- `gui/modes/navigation/input/window_mode.py`
- `gui/modes/navigation/input/intent_executor.py`
- `gui/modes/navigation/map/__init__.py`
- `gui/modes/navigation/map/config_applier.py`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
- `CODEBASE.md`

**预计连带影响：**
- `NavigationModeWidget._set_game_input_window_mode()` 保留方法名，但真实窗口 topmost/lower/restore 逻辑迁入 `navigation/input/window_mode.py`。
- `NavigationModeWidget._execute_navigation_intent()` 保留方法名，但真实 `MOVE_MAP`、`CLICK_SCREEN`、`PRESS_KEY` 分发迁入 `navigation/input/intent_executor.py`。
- `NavigationModeWidget._apply_config_to_core()` 和 `_configure_navigation_task_controller()` 保留方法名，但真实 `NavConfig -> nav_core/pathfinder/motion_controller/task_controller` 写入规则迁入 `navigation/map/config_applier.py`。
- 不改变 `MotionController` 调用参数、不改变 `draw_scale` 以 map npz 为权威的规则、不改变外部旧入口。

### C. SYNC 结果

关键发现：
- (verified) `GameInputWindowMode` 已成为唯一窗口输入模式 adapter；`NavigationModeWidget._set_game_input_window_mode()` 只保留旧方法名并委托 `set_enabled()`。
- (verified) `execute_navigation_intent()` 已集中处理 `MOVE_MAP`、`CLICK_SCREEN`、`PRESS_KEY`；`MOVE_MAP` 仍保持原有 `force_click_target -> click_map_target_once()`、普通移动 -> `move_to_map_target()` 的分支，并在真实点击后回写 `record_intent_click()`。
- (verified) `apply_navigation_config_to_core()` 已集中 recognizer、draw_scale、导航墙层、PathFinder 半径、MotionController 参数和 NavigationTaskController 参数写入；`map_draw_scale` 仍然覆盖配置 draw_scale 并写事件日志。
- (verified) `NavigationModeWidget` 外部入口和旧私有方法名保持可用，当前只是由 shell 调新功能包，没有迁移外部调用方。

代码变更：
- 新增 `gui/modes/navigation/input/__init__.py`
- 新增 `gui/modes/navigation/input/window_mode.py`
- 新增 `gui/modes/navigation/input/intent_executor.py`
- 新增 `gui/modes/navigation/map/__init__.py`
- 新增 `gui/modes/navigation/map/config_applier.py`
- 修改 `gui/modes/navigation_mode.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\input\__init__.py gui\modes\navigation\input\window_mode.py gui\modes\navigation\input\intent_executor.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\config_applier.py` 通过。
- `python -` smoke：用 fake window 验证 `GameInputWindowMode.set_enabled(True/False)` 启停状态与 lower/restore 调用。
- `python -` smoke：用 fake motion/controller 验证 `execute_navigation_intent(MOVE_MAP)` 会启用输入模式、调用 `set_control_enabled(True)`、调用 `move_to_map_target()`、回写 `record_intent_click()` 并返回 `click r/raw` 后缀。
- `python -` smoke：用 fake config/motion/controller 验证 `apply_motion_controller_config()` 传递 `movement_precision_click_max_radius`，`configure_navigation_task_controller()` 写入 movement/event approach/visual check 参数。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 Stage A | 已同步 Stage B | 追加 | input/window mode、intent 执行和 config 应用已变成 shell wrapper。 |
| `gui/modes/navigation/input/__init__.py` | 新增 | 深度完整 | 1 | navigation input adapter 包入口。 |
| `gui/modes/navigation/input/window_mode.py` | 新增 | 深度完整 | 1 | 主窗口 topmost/lower/restore 状态集中到单一 adapter。 |
| `gui/modes/navigation/input/intent_executor.py` | 新增 | 深度完整 | 1 | `NavigationIntent` 到 `MotionController` 的唯一 GUI input 执行 adapter。 |
| `gui/modes/navigation/map/__init__.py` | 新增 | 深度完整 | 1 | navigation map/config adapter 包入口。 |
| `gui/modes/navigation/map/config_applier.py` | 新增 | 深度完整 | 1 | `NavConfig` 到 core/gui runtime 对象的写入规则集中，保留 draw_scale 权威规则。 |

下一轮计划：
- 进入阶段 C：拆 Navigation route/events seam。优先新建 `navigation/route/editor.py` 收束 `route.json` 编辑和 click mode，再迁移 `ManualEventTestController` 到 `navigation/events/manual_test_controller.py`，最后抽 `events/panel_adapter.py` 收束 event dialog wiring。

## [GUI-STAGE-C-NAVIGATION-ROUTE-EVENTS-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 按 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 C 拆分 Navigation route/events seam，并保留旧入口兼容。

**目标文件：**
- `gui/modes/navigation_mode.py`（原因：当前仍直接拥有 route click mode、route.json 编辑命令、event dialog wiring 和 manual portal test 状态。）
- `gui/modes/event_test_controller.py`（原因：当前手动事件测试控制器位于 modes 扁平层，需迁入 navigation/events 功能包并保留 wrapper。）
- `gui/modes/navigation/route/*`（原因：新增 route 编辑功能包，避免继续平铺 helper。）
- `gui/modes/navigation/events/*`（原因：新增 events 功能包，承载 manual test controller 和可抽出的 event dialog adapter。）

**本轮想弄清楚：**
- 哪些 route 编辑逻辑能安全从 `NavigationModeWidget` 移出，同时不改变按钮状态、status 文案和 `route.json` 结构。
- `ManualEventTestController` 迁移后旧 import 是否需要保留。
- event dialog wiring 是否适合本轮抽成 adapter，还是应先迁移 controller 并等待下一批。

### C. SYNC 结果

关键发现：
- (verified) route 编辑命令可安全下沉到 `RouteEditor`：它只拥有 click mode 和 `RouteManager` 命令，不触碰 Qt 按钮、scene、状态栏或 `NavigationTaskController`。
- (verified) `NavigationModeWidget` 仍负责 UI 同步：按钮 checked 状态、overlay 重绘、状态栏文案和 `navigation_task_controller.load_route()` 调用不迁移，避免 route 模块反向依赖 GUI。
- (verified) `ManualEventTestController` 已迁入 `navigation/events/manual_test_controller.py`；旧 `gui/modes/event_test_controller.py` 作为 wrapper 保留，旧 import 不会断。
- (verified) event dialog wiring 适合本轮小步抽取：`panel_adapter.py` 只负责创建 dialog、信号重连、上下文刷新和配置摘要，不改变 event config 保存、portal reset、handler 执行或导航调度。

代码变更：
- 新增 `gui/modes/navigation/route/__init__.py`
- 新增 `gui/modes/navigation/route/editor.py`
- 新增 `gui/modes/navigation/events/__init__.py`
- 新增 `gui/modes/navigation/events/manual_test_controller.py`
- 新增 `gui/modes/navigation/events/panel_adapter.py`
- 修改 `gui/modes/navigation_mode.py`
- 修改 `gui/modes/event_test_controller.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\event_test_controller.py gui\modes\navigation\route\__init__.py gui\modes\navigation\route\editor.py gui\modes\navigation\events\__init__.py gui\modes\navigation\events\manual_test_controller.py` 通过。
- `python -` smoke：用临时目录和真实 `RouteManager` 验证 `RouteEditor` 可设置出口、添加必经点、添加途经点并保存 `route.json`。
- `python -` smoke：用 fake signal/dialog 验证 `connect_event_dialog_signals()` 重复调用不会重复连接，`refresh_event_dialog()` 会传入 registry/config/coordinator/map_name。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 Stage B | 已同步 Stage C | 追加 | route 编辑和 event dialog wiring 已变成 shell wrapper，runtime loop 未动。 |
| `gui/modes/event_test_controller.py` | 深度完整 | wrapper | 追加 | 旧入口保留，真实类迁到 navigation/events。 |
| `gui/modes/navigation/route/__init__.py` | 新增 | 深度完整 | 1 | route editing adapter 包入口。 |
| `gui/modes/navigation/route/editor.py` | 新增 | 深度完整 | 1 | route click mode 和 route.json 编辑命令集中。 |
| `gui/modes/navigation/events/__init__.py` | 新增 | 深度完整 | 1 | navigation events UI adapter 包入口。 |
| `gui/modes/navigation/events/manual_test_controller.py` | 新增 | 深度完整 | 1 | 手动事件测试按钮状态同步迁入 navigation/events。 |
| `gui/modes/navigation/events/panel_adapter.py` | 新增 | 深度完整 | 1 | event dialog wiring 集中，不推进事件运行逻辑。 |

下一轮计划：
- 阶段 D：拆 Navigation presentation/runtime。先抽 `navigation/presentation/status_presenter.py` 或 `map_presenter.py`，再处理 `_navigation_loop_unified()`；不要直接一次性搬 runtime loop。

## [GUI-STAGE-D-NAVIGATION-PRESENTATION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 按 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 D 继续拆分 Navigation presentation/runtime；本轮先做 presentation 小 seam，不直接抽 `_navigation_loop_unified()`。

**目标文件：**
- `gui/modes/navigation_mode.py`（原因：仍直接构造导航循环状态栏字符串、地图 QPixmap/QGraphicsItem、玩家/目标/视野 item 更新。）
- `gui/modes/navigation/presentation/*`（原因：新增 presentation 功能包，避免把 presenter 平铺到 navigation 根目录。）

**本轮想弄清楚：**
- 哪些 presentation 逻辑能安全迁移，不改变定位、事件调度、输入执行和 route 编辑。
- `status_label` 字符串构造是否可先拆成纯 helper。
- 地图渲染/marker 更新是否适合本轮抽出，还是应留到 runtime loop 拆分前再动。

### C. SYNC 结果

关键发现：
- (verified) 状态栏文案构造可作为纯 helper 下沉：`build_navigation_status_text()` 只依赖 localized 坐标、confidence、capture_rect、intent 和 event status。
- (verified) 地图 scene 初始 item 创建和常见 marker/rect 更新可下沉到 presenter；`NavigationModeWidget` 仍保留刷新时机、route/event overlay 列表清空和 runtime 编排。
- (verified) 本轮没有移动 `_navigation_loop_unified()` 的定位、事件观察、任务调度或输入执行，只把 UI item 操作和文案拼接迁到 presentation 包。

代码变更：
- 新增 `gui/modes/navigation/presentation/__init__.py`
- 新增 `gui/modes/navigation/presentation/map_presenter.py`
- 新增 `gui/modes/navigation/presentation/status_presenter.py`
- 修改 `gui/modes/navigation_mode.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\map_presenter.py gui\modes\navigation\presentation\status_presenter.py` 通过。
- `python -` smoke：验证 `build_navigation_status_text()` 对 localized/定位中两类状态输出坐标、置信度、监视尺寸、intent message、path kind 和 event status。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 Stage C | 已同步 Stage D presentation | 追加 | 地图 item 创建/更新和状态栏文案已委托 presentation；runtime loop 编排仍保留。 |
| `gui/modes/navigation/presentation/__init__.py` | 新增 | 深度完整 | 1 | navigation presentation 包入口。 |
| `gui/modes/navigation/presentation/map_presenter.py` | 新增 | 深度完整 | 1 | 地图 scene item、玩家/目标/提示点/视野框更新集中。 |
| `gui/modes/navigation/presentation/status_presenter.py` | 新增 | 深度完整 | 1 | 导航循环状态栏文案构造集中。 |

下一轮计划：
- 阶段 D 后续：先抽 `navigation/runtime/models.py` 承载 navigation loop tick/presentation result，再小步收束 `_navigation_loop_unified()`，不要一次性搬完整循环。

## [GUI-STAGE-D-NAVIGATION-RUNTIME-MODELS-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续阶段 D，先抽 navigation runtime models/helper，降低 `_navigation_loop_unified()` 局部状态噪音，但不搬完整循环。

**目标文件：**
- `gui/modes/navigation_mode.py`（原因：`_navigation_loop_unified()` 同时维护 capture/localization/event/task/presentation/input 多类局部状态。）
- `gui/modes/navigation/runtime/*`（原因：新增 runtime 功能包，先承载小 DTO/纯 helper，为后续 loop 拆分铺路。）

**本轮想弄清楚：**
- 能否抽出定位结果 DTO，统一 `global_x/global_y/conf/localized_pos/fallback_pos` 的判定。
- 能否把 lookahead 计算、event-run enabled 判定这类纯运行时小逻辑迁出。
- 这一步是否能减少主循环认知负担，同时不改变定位、事件调度或输入执行顺序。

### C. SYNC 结果

关键发现：
- (verified) `NavigationLocalizationResult` 可安全承接 `NavigationCore.localize()` 的 `(global_x, global_y, confidence)` 三元组，并统一 `localized_pos/is_localized` 判定。
- (verified) `compute_navigation_lookahead()` 保留原公式 `max(36.0, min(capture_width * draw_scale * 0.18, 120.0))`；`should_run_navigation_tasks()` 保留“自动导航或手动事件测试任一启用即运行”的规则。
- (verified) `_navigation_loop_unified()` 的调用顺序未改变：capture -> localize -> event observe -> task update -> presentation -> input/terminal handling。

代码变更：
- 新增 `gui/modes/navigation/runtime/__init__.py`
- 新增 `gui/modes/navigation/runtime/models.py`
- 新增 `gui/modes/navigation/runtime/loop_helpers.py`
- 修改 `gui/modes/navigation_mode.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\models.py gui\modes\navigation\runtime\loop_helpers.py` 通过。
- `python -` smoke：验证 `NavigationLocalizationResult.from_core_result()` 的 localized/未 localized 判定、lookahead 下限/上限和 event-run enabled 判定。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 Stage D presentation | 已同步 Stage D runtime models | 追加 | 主循环开始使用定位结果 DTO 和 runtime 小 helper；完整 loop 仍未搬移。 |
| `gui/modes/navigation/runtime/__init__.py` | 新增 | 深度完整 | 1 | navigation runtime helper 包入口。 |
| `gui/modes/navigation/runtime/models.py` | 新增 | 深度完整 | 1 | `NavigationLocalizationResult` 统一定位结果判定。 |
| `gui/modes/navigation/runtime/loop_helpers.py` | 新增 | 深度完整 | 1 | lookahead 公式和 task-run enabled 判定集中。 |

下一轮计划：
- 若继续推进 GUI，应在阶段 D 的基础上考虑 `runtime/loop.py`，但需要再切一层小 seam：例如先抽 capture/player local position 获取，而不是一次搬完整 `_navigation_loop_unified()`。

## [GUI-STAGE-D-NAVIGATION-RUNTIME-LOOP-HELPERS] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续阶段 D runtime 小步拆分，抽取玩家局部坐标解析和 task controller update 参数组装。

**目标文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/runtime/loop.py`
- `gui/modes/navigation/runtime/__init__.py`

**本轮想弄清楚：**
- 区域截图模式的 `recognizer.extract_player()` / `tracker.detect_player()` fallback 链路能否独立，且不改变上一帧 fallback 行为。
- `NavigationTaskController.update()` 的长参数列表能否由 helper 统一组装，且不改变 route、wall_map、explored_map、frame_registration 的来源。

### C. SYNC 结果

关键发现：
- (verified) `resolve_player_local_position()` 保持原区域截图逻辑：检测到玩家就用检测值；检测失败用上一帧局部坐标；仍失败用截图中心。非区域模式仍直接使用 `build_capture_geometry()` 返回的默认 player pos。
- (verified) `update_navigation_task_controller()` 只收口 `NavigationTaskController.update()` 的长参数列表，route 仍取 `(route_data or {}).get("routes", {}).get("main", {})`，frame registration 仍取 `nav_core.last_frame_registration`。
- (verified) `_navigation_loop_unified()` 的完整流程仍在 `NavigationModeWidget`，本轮未改变 capture/localize/event observe/presentation/input 的执行顺序。

代码变更：
- 新增 `gui/modes/navigation/runtime/loop.py`
- 修改 `gui/modes/navigation/runtime/__init__.py`
- 修改 `gui/modes/navigation_mode.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\loop.py gui\modes\navigation\runtime\models.py gui\modes\navigation\runtime\loop_helpers.py` 通过。
- `python -` smoke：验证 `resolve_player_local_position()` 在中心截图、区域截图检测失败有上一帧、区域截图检测失败无上一帧三种路径的返回值；验证 `update_navigation_task_controller()` 传入 localized_pos、route、frame_registration。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 Stage D runtime models | 已同步 Stage D runtime loop helpers | 追加 | 玩家局部坐标解析和 task controller update 参数组装已委托 runtime helper。 |
| `gui/modes/navigation/runtime/__init__.py` | 深度完整 | 已同步 loop helper 导出 | 追加 | 新增 runtime loop helper 导出。 |
| `gui/modes/navigation/runtime/loop.py` | 新增 | 深度完整 | 1 | 收口玩家局部坐标解析和 task controller update 参数组装。 |

下一轮计划：
- 当前 navigation 主类已经完成 input/config/route/events/presentation/runtime 小 seam 拆分。继续深入可选方向：进一步抽完整 `runtime/loop.py`，或先转入 Mapping mode 的 `runtime/session`，避免在导航循环上一次性过度拆分。

## [GUI-STAGE-E-MAPPING-RUNTIME-SESSION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 按 `GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 阶段 E 转入 Mapping mode，先抽 `runtime/models.py` 和 `runtime/session.py`，收束 `capture_and_process()` 中的 capture-recognize-stitch 主流程。

**目标文件：**
- `gui/modes/mapping_widget.py`（原因：`capture_and_process()` 混合截图、玩家 fallback、recognizer、stitcher、display、stats。）
- `gui/modes/mapping/runtime/*`（原因：新增 mapping runtime 功能包，承载 tick result 和 session。）
- `gui/modes/mapping/map_renderer.py`、`params_adapter.py`、`save_load.py`（原因：确认已有 helper 的边界，避免重复抽取。）

**本轮想弄清楚：**
- `capture_and_process()` 中哪些步骤是 runtime session，哪些仍属于 widget presentation/stats。
- `MappingSession.tick()` 是否能在不改变 `app_context.monitoring`、`screen_capture`、`recognizer`、`stitcher` 调用顺序的前提下抽出。
- 是否需要先抽 `MappingTickResult`，让 widget 继续决定如何更新 display 和 status。

### C. SYNC 结果

关键发现：
- (verified) `capture_and_process()` 的 capture -> player fallback -> `recognizer.extract_combined()` -> `recognizer.get_raw_gray()` -> `stitcher.add_frame()` -> `recognizer.get_preprocessed_image()` 可作为 `MappingSession.tick()` 下沉。
- (verified) widget 仍负责 timer/monitoring、`last_capture_size/last_player_local_pos` 状态、`update_displays()` 和 `update_statistics()`，没有把 presentation/stats 混进 session。
- (verified) 中心截图模式 player pos 仍固定为 monitor size 中心；区域截图模式仍按 tracker detection -> last player pos -> capture center 的顺序 fallback。

代码变更：
- 新增 `gui/modes/mapping/runtime/__init__.py`
- 新增 `gui/modes/mapping/runtime/models.py`
- 新增 `gui/modes/mapping/runtime/session.py`
- 修改 `gui/modes/mapping_widget.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\runtime\__init__.py gui\modes\mapping\runtime\models.py gui\modes\mapping\runtime\session.py` 通过。
- `python -` smoke：用 fake `app_context` 验证中心截图走 `capture_square()` 且 player pos 为截图中心；区域截图 tracker 失败时回退上一帧 player pos；session 会调用 `stitcher.add_frame()` 并返回 preprocessed image、combined mask、player pos 和 capture size。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | 深度完整 | 已同步 Stage E runtime session | 追加 | `capture_and_process()` 已委托 `MappingSession.tick()`，保留 display/stats。 |
| `gui/modes/mapping/runtime/__init__.py` | 新增 | 深度完整 | 1 | mapping runtime session 包入口。 |
| `gui/modes/mapping/runtime/models.py` | 新增 | 深度完整 | 1 | `MappingTickResult` DTO。 |
| `gui/modes/mapping/runtime/session.py` | 新增 | 深度完整 | 1 | 单帧 capture-recognize-stitch 主流程。 |

下一轮计划：
- Mapping 阶段 E 后续：抽 `capture/selection_controller.py` 或 `presentation/map_presenter.py`。建议先抽 presentation/map_presenter，因为现有 `map_renderer.py` 已经是稳定 helper，迁移风险更低。

## [GUI-STAGE-E-MAPPING-PRESENTATION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 Mapping 阶段 E，基于已有 `mapping/map_renderer.py` 抽 `mapping/presentation/map_presenter.py`，收束 `MappingWidget.update_displays()` 的显示写入。

**目标文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/presentation/*`
- `gui/modes/mapping/map_renderer.py`

**本轮想弄清楚：**
- `update_displays()` 能否只保留兼容入口，并把 capture label、global map widget、crop offset 计算交给 presenter。
- 是否能复用现有 `pixmap_from_bgr()`、`render_global_map_pixmap()`、`unpack_enhanced_map_result()`，避免重新实现图像渲染。

### C. SYNC 结果

关键发现：
- (verified) `update_displays()` 可安全作为兼容 wrapper，实际 capture label、global map widget、`map_crop_offset` 更新迁入 `mapping/presentation/map_presenter.py`。
- (verified) 新 presenter 复用现有 `mapping/map_renderer.py` 的 `pixmap_from_bgr()`、`render_global_map_pixmap()`、`unpack_enhanced_map_result()`，没有重复实现图像渲染算法。
- (verified) global map 为空时保留旧 crop offset，不触碰 global map widget；非空时返回 `(crop_x1, crop_y1)` 供 widget 写回。

代码变更：
- 新增 `gui/modes/mapping/presentation/__init__.py`
- 新增 `gui/modes/mapping/presentation/map_presenter.py`
- 修改 `gui/modes/mapping_widget.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\presentation\__init__.py gui\modes\mapping\presentation\map_presenter.py` 通过。
- `python -` smoke：初始化 `QApplication` 后验证 global map 为空时保留 crop offset；global map 非空时 capture label 和 global map widget 均收到 pixmap，返回新 crop offset。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | 已同步 Stage E runtime session | 已同步 Stage E presentation | 追加 | `update_displays()` 已委托 mapping presenter。 |
| `gui/modes/mapping/presentation/__init__.py` | 新增 | 深度完整 | 1 | mapping presentation 包入口。 |
| `gui/modes/mapping/presentation/map_presenter.py` | 新增 | 深度完整 | 1 | capture/global map display 写入集中。 |

下一轮计划：
- Mapping 阶段 E 剩余可继续抽 `capture/selection_controller.py` 或 `io/config_store.py`。当前 GUI 主线已完成一轮较大的结构化拆分，建议先停在这里做人工功能回归。
## [GUI-STAGE-E-MAPPING-CAPTURE-SELECTION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 Mapping 阶段 E，抽取捕获区域/中心点选择 seam，把 overlay 生命周期和选择结果写回规则从 `MappingWidget` 主类中下沉到 `mapping/capture` 功能包。
**目标文件：**
- `gui/modes/mapping_widget.py`（原因：当前直接管理区域 overlay、中心点 selector、DPI 坐标转换、monitor 配置写回和按钮状态。）
- `gui/modes/mapping/capture/*`（原因：新增 mapping capture 功能包，承载选择器生命周期和选择结果应用规则，避免 helper 扁平化。）

**本轮想弄清楚：**
- `select_region()` / `on_region_selected()` / `select_center_point()` / `on_center_selected()` 中哪些行为属于可下沉的 capture selection controller，哪些必须留在 widget 做 UI 状态同步。
- 逻辑像素、物理像素、monitor center/size 的写回规则是否能保持原样迁移。
- 是否需要把 `open_color_picker()` 一并纳入本轮，还是只读取其依赖关系，避免捕获选择 seam 和颜色采样 dialog 混在一起。

### C. SYNC 结果

关键发现：
- (verified) 区域选择和中心点选择的 overlay 生命周期、active flag、DPI 转换、`app_context.monitor_region/monitor_logical_center/monitor_size` 写回可以下沉到 `MappingCaptureSelectionController`；`MappingWidget` 只需要接收 `CaptureSelectionResult` 后更新 label、按钮和保存配置。
- (verified) `select_region()`、`on_region_selected()`、`select_center_point()`、`on_center_selected()`、`update_capture_size()` 均保留旧 slot/API 名称，外部调用不需要迁移。
- (verified) `open_color_picker()` 本轮不拆。它依赖 `self.monitor_center` 和 AppContext 截图配置；现在由 `_handle_capture_selection_result()` 同步 controller 返回的 `physical_center`，行为保持原路径。
- (verified) `load_saved_params()` 中保存配置回填现在通过 `restore_from_context()` 恢复物理中心和 label，避免重复散落 DPI 换算。

代码变更：
- 新增 `gui/modes/mapping/capture/__init__.py`
- 新增 `gui/modes/mapping/capture/selection_controller.py`
- 修改 `gui/modes/mapping_widget.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\capture\__init__.py gui\modes\mapping\capture\selection_controller.py` 通过。
- `python -` smoke：用 fake AppContext 和 `compute_scale=(1.5, 2.0)` 验证区域选择物理像素转换、中心点物理坐标、size 更新和 restore-from-context。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | 已同步 Stage E presentation | 已同步 Stage E capture selection | 追加 | 区域/中心点选择 slot 已委托 capture controller，保留 UI 状态和保存时机。 |
| `gui/modes/mapping/capture/__init__.py` | 新增 | 深度完整 | 1 | mapping capture 包入口。 |
| `gui/modes/mapping/capture/selection_controller.py` | 新增 | 深度完整 | 1 | overlay 生命周期、DPI 转换、monitor 配置写回集中。 |

下一轮计划：
- Mapping 阶段 E 剩余主要是 `mapping/io/config_store.py` 和 `mapping/params/binding.py`。建议先做 IO/config store，因为它会继续缩小 `MappingWidget.save_map()` / `save_config()` / `load_saved_params()`，且比参数绑定更容易用纯文件 smoke 覆盖。
## [GUI-STAGE-E-MAPPING-IO-CONFIG-STORE-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 Mapping 阶段 E，抽取 `mapping/io/config_store.py`，把 project root 推导、根配置读写、地图目录创建和地图配置读写从扁平 `mapping/save_load.py` 加深到 IO 功能包，同时保留旧 `save_load.py` 导入兼容。
**目标文件：**
- `gui/modes/mapping/save_load.py`（原因：当前承载路径推导、JSON IO、config dict 构造，位于 mapping 根目录，和 runtime/presentation/capture 分层不一致。）
- `gui/modes/mapping/io/*`（原因：新增 mapping IO 功能包，承载配置存储职责，避免 helper 扁平化。）
- `gui/modes/mapping_widget.py`（原因：确认保存地图、根配置保存和启动加载仍通过旧函数入口，不破坏调用。）

**本轮想弄清楚：**
- `save_load.py` 中哪些函数是纯 IO/store，哪些属于 config payload 构造，是否本轮一起迁入 `config_store.py`。
- `MappingWidget.save_map()` / `save_config()` / `load_saved_params()` 对返回值、异常和路径推导的隐含依赖。
- 旧 `gui.modes.mapping.save_load` 是否应完整 re-export，确保后续 GUI 兼容层清理前外部调用不坏。

### C. SYNC 结果

关键发现：
- (verified) `save_load.py` 全部函数都属于 IO/config store seam：project root 推导、`map_data` 路径、地图目录创建、根/地图 JSON 读写、mapping config payload 构造均可迁入 `mapping/io/config_store.py`。
- (verified) `MappingWidget` 对这些函数的依赖只关心返回 `Path`、读写 JSON 和 config dict 字段；旧 import 路径可通过 `save_load.py` re-export 保持不变。
- (verified) `json.dump(..., indent=4)`、`Path(file_path).resolve().parents[2]` 和 `load_root_config()` 不存在时返回 `None` 的行为保持原样，没有引入新的 root 注入机制。

代码变更：
- 新增 `gui/modes/mapping/io/__init__.py`
- 新增 `gui/modes/mapping/io/config_store.py`
- 修改 `gui/modes/mapping/save_load.py` 为兼容 wrapper

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping\save_load.py gui\modes\mapping\io\__init__.py gui\modes\mapping\io\config_store.py gui\modes\mapping_widget.py` 通过。
- `python -` smoke：临时项目目录下验证 `map_data_dir()`、`ensure_map_folder()`、`save_root_config()`、`load_root_config()`、`save_map_config()`、`load_json_config()` 和旧 `save_load` re-export identity。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/save_load.py` | 深度完整 | wrapper | 追加 | 旧导入路径保留，真实实现迁入 `mapping/io/config_store.py`。 |
| `gui/modes/mapping/io/__init__.py` | 新增 | 深度完整 | 1 | mapping IO 包入口。 |
| `gui/modes/mapping/io/config_store.py` | 新增 | 深度完整 | 1 | project root、map_data、config JSON IO 和 mapping config payload 集中。 |

下一轮计划：
- Mapping 阶段 E 剩余主要是 `mapping/params/binding.py`。建议下一轮把 `params_adapter.py` 加深到 `mapping/params/binding.py`，仍保留旧 `params_adapter.py` wrapper，避免一次性改动控件信号和参数应用时机。
## [GUI-STAGE-E-MAPPING-PARAMS-BINDING-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 Mapping 阶段 E，抽取 `mapping/params/binding.py`，把绘图页参数控件到 recognizer/stitcher 参数 dict 的绑定规则从扁平 `mapping/params_adapter.py` 加深到 params 功能包，同时保留旧 `params_adapter.py` 导入兼容。
**目标文件：**
- `gui/modes/mapping/params_adapter.py`（原因：当前承载控件读取、HSV toggle 应用、merge weight 应用、加载配置回填，位于 mapping 根目录，和 runtime/presentation/capture/io 分层不一致。）
- `gui/modes/mapping/params/*`（原因：新增 mapping params 功能包，承载控件绑定和参数 dict 规则。）
- `gui/modes/mapping_widget.py`（原因：确认 update_hsv/feature/merge 和 load_saved_params 的调用时机、信号副作用保持不变。）

**本轮想弄清楚：**
- `params_adapter.py` 中哪些函数纯读取控件并返回 dict，哪些函数直接修改 recognizer/stitcher，迁移时是否要保持这个副作用边界。
- `sync_recognizer_widgets()` / `sync_stitcher_widgets()` 在加载配置时是否依赖触发 Qt 信号，不能随手加 blocker 改行为。
- 旧 `gui.modes.mapping.params_adapter` 是否完整 re-export，确保 MappingWidget 和潜在外部导入不坏。

### C. SYNC 结果

关键发现：
- (verified) `params_adapter.py` 的函数均可迁入 `mapping/params/binding.py`，但副作用边界需要原样保留：`apply_hsv_toggles()` 和 `apply_merge_weight()` 仍直接写 recognizer/stitcher，`feature_params_from_widgets()` 仍只返回 dict。
- (verified) `sync_recognizer_widgets()` / `sync_stitcher_widgets()` 不应在本轮加 `QSignalBlocker`；加载配置时可能触发既有信号副作用，这个行为需要保持。
- (verified) `sync_geometry_widgets()` 的信号阻断仍由 `MappingWidget.load_saved_params()` 外层控制，迁移后不改变这个责任边界。

代码变更：
- 新增 `gui/modes/mapping/params/__init__.py`
- 新增 `gui/modes/mapping/params/binding.py`
- 修改 `gui/modes/mapping/params_adapter.py` 为兼容 wrapper

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping\params_adapter.py gui\modes\mapping\params\__init__.py gui\modes\mapping\params\binding.py gui\modes\mapping_widget.py` 通过。
- `python -` smoke：用 fake checkbox/spinbox 验证 feature 参数 dict、HSV toggle 写入、merge weight 写入、recognizer/stitcher/geometry 控件回填和旧 `params_adapter` re-export identity。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/params_adapter.py` | 深度完整 | wrapper | 追加 | 旧导入路径保留，真实实现迁入 `mapping/params/binding.py`。 |
| `gui/modes/mapping/params/__init__.py` | 新增 | 深度完整 | 1 | mapping params 包入口。 |
| `gui/modes/mapping/params/binding.py` | 新增 | 深度完整 | 1 | 参数控件读取/回填和轻副作用写入集中。 |

下一轮计划：
- Mapping 阶段 E 的计划项已经完成。后续 GUI 优化可转向 Dialogs 阶段 F，或先对 `MappingWidget` 做 UI layout 级拆分；建议优先 Dialogs，因为当前 Mapping 主流程、选择、显示、IO、参数绑定都已有功能包边界。
## [GUI-STAGE-F-COLOR-PICKER-PREVIEW-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 进入 GUI 阶段 F Dialogs，先抽 `dialogs/color_picker/preview.py`，把 `ColorPickerDialog.update_preview()` 中的 HSV mask、morphology、stats 和 debug payload 构造从 dialog 主类中下沉。
**目标文件：**
- `gui/dialogs/color_picker_dialog.py`（原因：当前同时管理采样点 UI、HSV 范围计算、mask preview、morphology、stats、debug 输出和 result packaging。）
- `gui/dialogs/color_picker/preview.py`（原因：新增 preview 功能模块，承载 wall/player mask preview 构造，避免继续把算法细节留在 QDialog 方法中。）
- 现有 `gui/dialogs/color_picker/hsv_ranges.py`、`image_renderer.py`、`debug_output.py`（原因：确认已有 helper 边界，避免重复实现。）

**本轮想弄清楚：**
- `update_preview()` 中哪些步骤可以变成纯函数，哪些必须留在 dialog 做 widget 写入、debug 文件输出和状态保存。
- wall/player 两种模式的 HSV 范围、mask 合并、morphology、stats 文案是否能在不改变显示结果的前提下集中。
- debug 输出是否只需要接收 preview 结果，不在本轮改变 opt-in 行为。

### C. SYNC 结果

关键发现：
- (verified) 当前 `ColorPickerDialog.update_preview()` 实际只预览 wall HSV mask；player HSV 只参与结果返回。本轮只复刻 wall preview，不新增 player preview，避免行为扩张。
- (verified) BGR->HSV、`cv2.inRange()`、白色像素统计、3x3 close、close 后统计和 debug 所需字段可安全迁入 `color_picker/preview.py::build_wall_preview()`。
- (verified) dialog 仍负责 QLabel 显示、`MINIMAP_COLOR_PICKER_DEBUG` 判断和 `write_wall_preview_debug()` 调用，因此 debug opt-in 行为不变。

代码变更：
- 新增 `gui/dialogs/color_picker/preview.py`
- 修改 `gui/dialogs/color_picker_dialog.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\preview.py gui\dialogs\color_picker\debug_output.py gui\dialogs\color_picker\hsv_ranges.py gui\dialogs\color_picker\image_renderer.py` 通过。
- `python -` smoke：构造 4x4 BGR 图，验证 `build_wall_preview()` 的 before mask、close 后 mask、白色像素统计、diff 和空 HSV range 返回 `None`。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/color_picker_dialog.py` | 中深热点 | 已同步 preview seam | 追加 | `update_preview()` 已委托 `build_wall_preview()`，保留显示和 debug 调度。 |
| `gui/dialogs/color_picker/preview.py` | 新增 | 深度完整 | 1 | wall HSV preview mask、morphology 和 stats 集中。 |

下一轮计划：
- Dialogs 阶段 F 后续建议进入 `nav_params/config_binding.py` 或 `nav_params/field_specs.py`。`nav_params_dialog.py` 是更深热点，但应先抽字段绑定/规格，不先拆 layout。
## [GUI-STAGE-F-NAV-PARAMS-CONFIG-BINDING-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 阶段 F Dialogs，先抽 `dialogs/nav_params/config_binding.py` 小 seam，把 `NavParametersDialog` 中 NavConfig 字段路径、控件读写、配置替换规则的可复用部分下沉；本轮不拆 tab layout。
**目标文件：**
- `gui/dialogs/nav_params_dialog.py`（原因：当前同时负责 tab/layout 构造、widget_map、控件信号、配置字段写回、set_config_to_ui 和默认配置保存信号。）
- `gui/dialogs/nav_params/config_binding.py`（原因：新增配置绑定 helper，承载 widget_map 到 NavConfig 的读写规则。）
- `gui/dialogs/nav_params/screen_estimator.py`（原因：确认已有 helper 边界，避免把点击半径估算和 config binding 混在一起。）

**本轮想弄清楚：**
- `widget_map` 的字段 path 到 `NavConfig` / nested dataclass 的写回是否能抽成纯 helper，保持 `dataclasses.replace()` 风格。
- `set_config_to_ui()` 的控件回填是否可抽取为 helper，同时保留 QSignalBlocker 的使用位置和信号阻断语义。
- 哪些字段有特殊解析/格式化（例如 HSV 文本、tuple/list、checkbox/spinbox），本轮是否只抽通用部分，还是可以安全统一。

### C. SYNC 结果

关键发现：
- (verified) `widget_map`、HSV 文本字段 map、`functools.partial` 信号绑定、`ast.literal_eval` 文本解析和 `dataclasses.replace` 不可变写回可以迁入 `gui/dialogs/nav_params/config_binding.py`，`NavParametersDialog` 只保留旧 slot 名称并委托 helper。
- (verified) `set_config_to_ui()` 的控件回填可以迁入 `write_config_to_widgets()`；但 `QSignalBlocker` 必须继续留在 dialog 层，因为它阻断的是本次程序化回填期间所有子控件信号，而不是字段绑定 helper 的职责。
- (verified) `config_binding.py` 当前仍依赖 dialog 控件 attribute names，因此它是 binding seam，不是完整 field spec 系统；下一步应抽 `field_specs.py`，而不是继续扩大 dialog 里的硬编码表。

代码变更：
- 新增 `gui/dialogs/nav_params/config_binding.py`
- 修改 `gui/dialogs/nav_params/__init__.py` re-export 配置绑定 helper
- 修改 `gui/dialogs/nav_params_dialog.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\nav_params_dialog.py gui\dialogs\nav_params\__init__.py gui\dialogs\nav_params\config_binding.py` 通过。
- `python -` smoke：验证 `replace_config_value()` 不原地修改旧 `NavConfig`，根字段和 `recognizer_params` 嵌套字段均可更新；验证 `parse_config_text_value()` 对合法 list 返回值、对未完成输入返回 `(False, None)`；offscreen 创建 `NavParametersDialog` 后 `set_config_to_ui()` 能正确写入 `fps` 和屏幕中心文本。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/nav_params_dialog.py` | 深热点 | 已同步 config binding seam | 追加 | 字段绑定、文本解析、配置 replace 和控件回填已委托 `nav_params/config_binding.py`；UI shell 和 QSignalBlocker 保留。 |
| `gui/dialogs/nav_params/__init__.py` | 深度完整 | 已同步 config binding re-export | 追加 | 包入口现在 re-export 配置绑定 helper。 |
| `gui/dialogs/nav_params/config_binding.py` | 新增 | 深度完整 | 1 | `NavConfig` 字段路径、信号连接、文本解析、不可变写回和控件回填集中。 |
| `gui/dialogs/nav_params/screen_estimator.py` | 深度完整 | 未变更 | 追加 | 点击半径估算边界保持独立，未与 config binding 混合。 |

下一轮计划：
- Dialogs 阶段 F 继续处理 `nav_params/field_specs.py`：先把 movement/path/event/map 等字段的 label、help、range、type、config path 沉淀成规格表，再决定是否引入 widget factory。不要先拆 tab layout。

## [GUI-STAGE-F-NAV-PARAMS-FIELD-SPECS-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 阶段 F Dialogs，在已抽 `config_binding.py` 的基础上新增 `dialogs/nav_params/field_specs.py`，先把字段标识、控件 attribute、配置路径和字段类别沉淀成规格表，降低 binding/write-back 的重复硬编码；本轮不重建 tab layout。
**目标文件：**
- `gui/dialogs/nav_params/config_binding.py`（原因：当前已经集中字段绑定，但 value/text 字段路径和控件回填仍分散在多个硬编码段。）
- `gui/dialogs/nav_params/field_specs.py`（原因：新增规格表模块，承载可复用字段元数据。）
- `gui/dialogs/nav_params_dialog.py`（原因：确认旧 public dialog 不变，只通过 config binding 间接使用 specs。）

**本轮想弄清楚：**
- 是否能先抽“字段规格”而不改变现有控件创建和布局顺序。
- value/text 字段能否共用同一份 `FieldSpec`，让 `connect_config_bindings()` 和 `write_config_to_widgets()` 不再重复声明字段路径。
- 只读显示字段（`draw_scale`、`monitor_region`、`game_screen_center`）是否应留在 `config_binding.py`，避免把 display formatting 过早塞入 specs。

### C. SYNC 结果

关键发现：
- (verified) 可先抽“可编辑字段规格”而不改变 `NavParametersDialog._init_ui()` 的控件创建和 tab 布局顺序；`field_specs.py` 只保存控件 attribute name、config path、kind、writer 和 group。
- (verified) `connect_config_bindings()` 和 `write_config_to_widgets()` 已改为消费 `VALUE_FIELD_SPECS` / `TEXT_FIELD_SPECS`，不再各自重复声明同一批字段路径。
- (verified) 只读显示字段仍应留在 `config_binding.py`：`draw_scale`、`monitor_region`、`game_screen_center` 带 presentation formatting，过早纳入 specs 会让规格表混入 UI 文案和条件格式化。

代码变更：
- 新增 `gui/dialogs/nav_params/field_specs.py`
- 修改 `gui/dialogs/nav_params/config_binding.py`
- 修改 `gui/dialogs/nav_params/__init__.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\nav_params_dialog.py gui\dialogs\nav_params\__init__.py gui\dialogs\nav_params\config_binding.py gui\dialogs\nav_params\field_specs.py` 通过。
- `python -` smoke：offscreen 创建 `NavParametersDialog`，验证 value/text binding 数量与 specs 数量一致，`set_config_to_ui()` 仍写入 `fps` 和屏幕中心文本，`config_value()` 能按 spec 从 `NavConfig` 取值。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/nav_params/field_specs.py` | 新增 | 深度完整 | 1 | 可编辑字段规格表，描述控件 attribute、config path、kind、writer、group。 |
| `gui/dialogs/nav_params/config_binding.py` | 深度完整 | 已同步 field specs seam | 追加 | value/text binding 和控件回填改由 specs 驱动；只读显示格式保留。 |
| `gui/dialogs/nav_params/__init__.py` | 已同步 config binding re-export | 已同步 specs re-export | 追加 | 包入口 re-export specs 和 binding helper。 |
| `gui/dialogs/nav_params_dialog.py` | 已同步 config binding seam | 未变更 | 追加 | dialog 壳子不直接感知 specs；仍通过 config binding 使用。 |

下一轮计划：
- Dialogs 阶段 F 的 `NavParametersDialog` 已完成 binding/specs 两个低风险 seam。后续可二选一：继续把 `field_specs.py` 扩展为 label/help/range 并逐步服务 widget factory，或转向 `AdvancedSettingsDialog` command signal 化，降低 dialog 直接修改 parent recognizer/stitcher 的耦合。

## [GUI-STAGE-F-ADVANCED-SETTINGS-COMMAND-SIGNAL-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 阶段 F Dialogs，处理 `AdvancedSettingsDialog` 的 parent runtime 直接修改耦合，优先建立 command signal seam；本轮不拆 tabs，不改变参数文件 IO 或预设行为。
**目标文件：**
- `gui/dialogs/advanced_settings_dialog.py`（原因：当前弹窗可能直接读取/写入 parent recognizer/stitcher，并决定实时应用时机。）
- `gui/main_window.py` / `gui/modes/mapping_widget.py` / `gui/modes/navigation_mode.py`（原因：确认谁创建 advanced dialog、谁应该接收应用命令，避免改坏外部入口。）
- `gui/dialogs/advanced_settings/params_adapter.py`（原因：确认参数 dict 边界已经存在，不重复抽控件读写。）

**本轮想弄清楚：**
- `AdvancedSettingsDialog.apply_params()`、`load_current_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 哪些仍然直接依赖 parent runtime。
- 是否能新增 signal/command payload，同时保留旧 parent 直接应用路径作为兼容 fallback。
- owner（MappingWidget 或 NavigationModeWidget）是否已有可复用的 recognizer/stitcher 应用方法，可以先接 signal，不要求全局调用方迁移。

### C. SYNC 结果

关键发现：
- (verified) `AdvancedSettingsDialog.apply_params()` 是唯一直接调用 recognizer/stitcher `set_params()` 的高级设置主入口；`load_current_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 只读写控件或临时参数，不直接修改 runtime。
- (verified) `MappingWidget` 是当前实际创建高级设置弹窗的 owner，且 runtime 对象在 `app_context.recognizer/stitcher` 上；dialog 旧的 `hasattr(parent, "recognizer")` 路径对 MappingWidget 并不理想，应由 owner 处理。
- (verified) 弹窗内“应用参数”旧语义是实时应用但不保存配置；对话框 accepted 后才由 `MappingWidget.open_advanced_settings()` 保存。新 command signal 必须保留这个保存时机。

代码变更：
- 修改 `gui/dialogs/advanced_settings_dialog.py`：新增 `apply_params_requested = Signal(dict)`、`use_external_apply_handler()` 和 `_apply_params_directly()` fallback；`apply_params()` 先发 signal，再按兼容开关决定是否 direct apply。
- 修改 `gui/modes/mapping_widget.py`：连接 `apply_params_requested`，以 `save=False` 处理弹窗内实时应用；对话框 accepted 后以 `save=True` 应用并保存。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\advanced_settings_dialog.py gui\modes\mapping_widget.py gui\dialogs\advanced_settings\params_adapter.py` 通过。
- `python -` smoke：offscreen 创建 `AdvancedSettingsDialog`，验证 external apply handler 模式只发出 signal、不 direct 调用 fake recognizer/stitcher；fallback 模式仍 direct 调用 fake recognizer/stitcher。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/advanced_settings_dialog.py` | 深度完整 | 已同步 command signal seam | 追加 | `apply_params()` 发出 command signal；direct runtime mutation 降为 fallback。 |
| `gui/modes/mapping_widget.py` | 已同步 Mapping seams | 已同步 advanced settings owner apply | 追加 | owner 负责应用高级参数；实时 Apply 不保存，accepted 后保存，保持旧时机。 |
| `gui/dialogs/advanced_settings/params_adapter.py` | 深度完整 | 未变更 | 追加 | 参数 dict 边界已足够，本轮未重复抽控件读写。 |

下一轮计划：
- Dialogs 阶段 F 的计划项已经完成：`nav_params/config_binding.py`、`nav_params/field_specs.py`、`color_picker/preview.py`、`advanced_settings` command signal seam 均已落地。下一步建议进入 GUI 收尾审计：旧 compatibility wrapper 和未迁移 fallback 清单，或开始拆更大的 layout/tabs 前先做一次人工功能回归。

## [GUI-STAGE-G-NAV-PRESENTATION-OVERLAY-PACKAGE-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** GUI 收尾结构化，把导航 presentation helper 从 `gui/modes/navigation/` 根目录下沉到 `gui/modes/navigation/presentation/`，旧路径保留 wrapper；本轮只做文件归属移动，不改绘制算法。
**目标文件：**
- `gui/modes/navigation/route_overlay.py`（原因：route/exit/required/guide/current path overlay 属于 presentation，不应继续留在 navigation 根目录。）
- `gui/modes/navigation/viewport_overlay.py`（原因：屏幕幕布、监控绿框、真实视野橙框计算服务地图展示，归入 presentation 更清晰。）
- `gui/modes/navigation/presentation/*`（原因：已有 map_presenter/status_presenter，应承载 overlay helper。）
- `gui/modes/navigation_mode.py`（原因：确认旧导入路径是否需要保留，避免 GUI 主壳调用断开。）

**本轮想弄清楚：**
- 两个 overlay helper 是否有状态或跨系统副作用，能否安全移动为 wrapper re-export。
- `NavigationModeWidget` 当前导入路径是否应继续先指向旧 wrapper，还是可以直接改到 `presentation` 包。
- `CODEBASE.md` 和中文计划里如何标注旧路径 wrapper 和新真实实现。

### C. SYNC 结果

关键发现：
- (verified) `route_overlay.py` 只创建/移除 route 相关 QGraphicsItem，不改 route 数据、任务状态或输入系统；可安全作为 presentation helper 下沉。
- (verified) `viewport_overlay.py` 是纯矩形几何 helper，不创建 Qt item，不读写 runtime；可安全归入 `presentation/viewport_overlay.py`。
- (verified) `NavigationModeWidget` 可以直接从 `navigation.presentation` 导入 route overlay 和 `screen_overlay_geometry`；旧 `navigation.route_overlay`、`navigation.viewport_overlay` 保留 wrapper，潜在外部导入不受影响。

代码变更：
- 新增 `gui/modes/navigation/presentation/route_overlay.py`
- 新增 `gui/modes/navigation/presentation/viewport_overlay.py`
- 修改 `gui/modes/navigation/route_overlay.py` 为兼容 wrapper
- 修改 `gui/modes/navigation/viewport_overlay.py` 为兼容 wrapper
- 修改 `gui/modes/navigation/presentation/__init__.py`、`map_presenter.py`、`gui/modes/navigation_mode.py`

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py gui\modes\navigation\viewport_overlay.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\map_presenter.py gui\modes\navigation\presentation\route_overlay.py gui\modes\navigation\presentation\viewport_overlay.py` 通过。
- `python -` smoke：验证旧 wrapper 与新 presentation 模块导出的 `render_route_overlay` / `game_view_scene_rect` 是同一函数对象，并验证 `screen_overlay_geometry()` 基本坐标缩放结果。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/route_overlay.py` | 新增 | 深度完整 | 1 | route overlay 真实实现下沉到 presentation 包。 |
| `gui/modes/navigation/presentation/viewport_overlay.py` | 新增 | 深度完整 | 1 | 视野/监控/屏幕 overlay 几何真实实现下沉到 presentation 包。 |
| `gui/modes/navigation/route_overlay.py` | 深度完整 | wrapper | 追加 | 旧导入路径保留，re-export presentation route overlay。 |
| `gui/modes/navigation/viewport_overlay.py` | 深度完整 | wrapper | 追加 | 旧导入路径保留，re-export presentation viewport geometry。 |
| `gui/modes/navigation/presentation/__init__.py` | 深度完整 | 已同步 overlay 导出 | 追加 | presentation 包入口导出 route/viewport helper。 |
| `gui/modes/navigation_mode.py` | 已同步多轮 GUI seams | 已同步 presentation overlay import | 追加 | 直接从 `navigation.presentation` 导入 route overlay 和 screen overlay geometry。 |

下一轮计划：
- GUI 收尾可以继续清理同类 wrapper/facade：`event_overlay.py` 是否也应进入 `presentation/`，或先做 compatibility wrapper 清单，等用户回归确认后统一移除旧路径。

## [GUI-STAGE-G-NAV-EVENT-OVERLAY-PRESENTATION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 收尾结构化，把导航事件 marker overlay 从 `gui/modes/navigation/event_overlay.py` 下沉到 `gui/modes/navigation/presentation/event_overlay.py`，旧路径保留 wrapper；本轮只做归属迁移，不改事件绘制算法、不改事件调度。
**目标文件：**
- `gui/modes/navigation/event_overlay.py`（原因：事件 marker 绘制属于 presentation，当前仍在 navigation 根目录。）
- `gui/modes/navigation/presentation/event_overlay.py`（原因：新增真实实现位置，与 route/viewport overlay 归一。）
- `gui/modes/navigation/presentation/route_overlay.py`（原因：当前复用 `global_to_scene`，迁移 event overlay 后应改为同包导入。）
- `gui/modes/navigation_mode.py`（原因：确认事件 overlay 导入路径可以切到 presentation 包，旧 wrapper 仍保留。）

**本轮想弄清楚：**
- `event_overlay.py` 是否只做 QGraphicsItem 绘制/清理，是否能安全移动。
- `global_to_scene()` 是否被 route overlay 和其他模块复用，迁移后如何避免导入环。
- 旧 `navigation.event_overlay` wrapper 是否足以保护潜在外部导入。

### C. SYNC 结果

关键发现：
- (verified) `event_overlay.py` 只负责清理旧 QGraphicsItem、把全局点按 `nav_core.crop_offset` 转换为 scene 坐标、根据 `EventCoordinator.overlays()` 产出的展示模型画圆点和状态文本；没有事件调度、配置保存或输入副作用。
- (verified) `global_to_scene()` 当前由 route overlay 复用；迁入 `presentation/event_overlay.py` 后，`presentation/route_overlay.py` 改成同包导入，避免 presentation 真实实现反向依赖旧根路径 wrapper。
- (verified) 旧 `gui/modes/navigation/event_overlay.py` 改为 re-export wrapper，旧导入路径和新 presentation 路径导出的函数对象一致。

代码变更：
- 新增 `gui/modes/navigation/presentation/event_overlay.py`
- 修改 `gui/modes/navigation/event_overlay.py` 为兼容 wrapper
- 修改 `gui/modes/navigation/presentation/route_overlay.py`，从同包导入 `global_to_scene`
- 修改 `gui/modes/navigation/presentation/__init__.py`，导出 event overlay helper
- 修改 `gui/modes/navigation_mode.py`，直接从 `navigation.presentation` 导入事件 overlay helper

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\event_overlay.py gui\modes\navigation\presentation\event_overlay.py gui\modes\navigation\presentation\route_overlay.py gui\modes\navigation\presentation\__init__.py` 通过。
- `python -` smoke：验证旧 wrapper 与新 presentation 模块导出的 `clear_event_overlay`、`global_to_scene`、`render_event_overlay` 是同一函数对象，且 presentation 包入口导出的 `render_event_overlay` 指向真实实现。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/event_overlay.py` | 新增 | 深度完整 | 1 | 事件 marker overlay 绘制真实实现下沉到 presentation 包。 |
| `gui/modes/navigation/event_overlay.py` | 深度完整 | wrapper | 追加 | 旧导入路径保留，re-export presentation event overlay。 |
| `gui/modes/navigation/presentation/route_overlay.py` | 深度完整 | 已同步同包 event 坐标导入 | 追加 | 不再从旧根路径 wrapper 导入 `global_to_scene()`。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 route/viewport overlay 导出 | 已同步 event overlay 导出 | 追加 | presentation 包入口现在导出 route/event/viewport helper。 |
| `gui/modes/navigation_mode.py` | 已同步 presentation route/viewport import | 已同步 presentation event overlay import | 追加 | 主 UI 直接依赖 `navigation.presentation`，旧 wrapper 留给外部兼容。 |

下一轮计划：
- 继续 GUI 收尾结构化，优先审计 `navigation/map_runtime.py`：它仍混合 map 目录/配置 IO、默认配置合并、logical->physical center 和 capture geometry，适合按 `map/config_store.py` 与 `map/capture_geometry.py` 小步下沉并保留旧 `map_runtime.py` facade。

## [GUI-STAGE-H-NAV-MAP-RUNTIME-PACKAGE-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化，把 `gui/modes/navigation/map_runtime.py` 中混合的地图目录/config IO 与截图几何拆入 `gui/modes/navigation/map/` 功能包；旧 `map_runtime.py` 保留 facade/wrapper，避免外部导入断开。
**目标文件：**
- `gui/modes/navigation/map_runtime.py`（原因：当前同时承担 project root 推导、map_data 目录、NavConfig JSON 读写、默认配置合并、logical/physical 坐标换算和 capture rect 计算。）
- `gui/modes/navigation/map/config_store.py`（原因：新增真实 IO/config 实现位置，和已有 `map/config_applier.py` 同属 map/config 系统。）
- `gui/modes/navigation/map/capture_geometry.py`（原因：新增截图几何实现位置，把纯几何从 IO 中分离。）
- `gui/modes/navigation/map/__init__.py`（原因：作为 navigation map 包入口，统一导出 config applier、config store 和 capture geometry。）
- `gui/modes/navigation_mode.py`（原因：主 UI 应优先从功能包导入新入口，旧 `map_runtime.py` 只服务兼容。）

**本轮想弄清楚：**
- `map_runtime.py` 中哪些函数有文件 IO 副作用，哪些只是几何计算。
- `load_nav_config()` / `save_nav_config()` / `save_default_nav_config()` 是否保留现有 merge 语义和 `config_exists` 契约。
- `NavigationModeWidget` 和潜在外部导入是否可以通过旧 facade 维持兼容。

### C. SYNC 结果

关键发现：
- (verified) `map_runtime.py` 可清晰分为两组：路径/JSON IO/config merge 属于 `map/config_store.py`；`physical_center_from_logical()` 与 `build_capture_geometry()` 是纯截图几何，属于 `map/capture_geometry.py`。
- (verified) `load_nav_config()` 仍保持契约：优先读地图 `config.json` 并返回 `config_exists=True`；地图配置缺失时尝试项目根 `config.json` 并返回 `config_exists=False`；两者都缺失则返回默认 `NavConfig(), False`。
- (verified) `save_nav_config()` 和 `save_default_nav_config()` 仍是 merge 写入：保留已有 mapping-only 字段，`recognizer_params` 以现有值为底、再用 `NavConfig.to_dict()` 中的新值覆盖。
- (verified) 旧 `gui/modes/navigation/map_runtime.py` 已改为 facade，旧导入与 `navigation.map` 包导出的函数对象一致；`NavigationModeWidget` 已改为直接从 `navigation.map` 导入。

代码变更：
- 新增 `gui/modes/navigation/map/config_store.py`
- 新增 `gui/modes/navigation/map/capture_geometry.py`
- 修改 `gui/modes/navigation/map_runtime.py` 为兼容 facade
- 修改 `gui/modes/navigation/map/__init__.py`，统一导出 config applier、config store 和 capture geometry
- 修改 `gui/modes/navigation_mode.py`，从 `navigation.map` 包导入地图配置和截图几何 helper

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map_runtime.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\config_store.py gui\modes\navigation\map\capture_geometry.py` 通过。
- `python -` smoke：验证旧 `map_runtime.py`、新 `navigation.map` 包入口和真实模块导出的 `load_nav_config` / `build_capture_geometry` 是同一函数对象；验证 logical->physical、显式 region 和中心点截图几何结果不变。
- `python -` 文件 IO smoke：验证默认配置 fallback、地图配置 merge 保存、项目根默认配置 merge 保存均保持 mapping-only 字段并写入合法 recognizer params。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/config_store.py` | 新增 | 深度完整 | 1 | 导航 map 目录、NavConfig JSON fallback/merge 保存真实实现。 |
| `gui/modes/navigation/map/capture_geometry.py` | 新增 | 深度完整 | 1 | logical/physical center 换算和截图 rect/player pos 纯几何。 |
| `gui/modes/navigation/map_runtime.py` | 深度完整 | facade wrapper | 追加 | 旧导入路径保留，re-export config store 与 capture geometry。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 config applier 导出 | 已同步 map store/geometry 导出 | 追加 | navigation map 包入口现在覆盖 config applier、store、geometry 三组能力。 |
| `gui/modes/navigation_mode.py` | 已同步多轮 GUI seams | 已同步 navigation.map import | 追加 | 主 UI 不再直接依赖旧 `map_runtime.py` facade。 |

下一轮计划：
- 继续 GUI 结构化时，下一块建议审计 `navigation/event_adapter.py` 的旧 helper：`should_event_action_take_control()` / `is_terminal_event_action()` 可能是旧 UI 级事件动作仲裁残留；先做引用审计和文档判定，不急着删除。

## [GUI-STAGE-I-NAV-EVENT-ADAPTER-LEGACY-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 旧内容审计与结构化收尾，审计 `gui/modes/navigation/event_adapter.py` 中疑似旧链路残留的事件 action helper，确认是否仍被实际实现引用；本轮优先做引用审计和小范围清理，不改事件调度主链路。
**目标文件：**
- `gui/modes/navigation/event_adapter.py`（原因：当前主链路已由 `NavigationTaskController` 调用 `EventCoordinator.run_task()` 并输出 `NavigationIntent`，该文件里的 `should_event_action_take_control()` / `is_terminal_event_action()` 可能属于旧 UI 级事件动作仲裁。）
- `gui/modes/navigation_mode.py`（原因：确认主 UI 是否仍导入或调用这些 helper，以及 event adapter 中其余函数的活跃调用点。）
- `gui/modes/navigation/events/*`（原因：确认事件管理 UI adapter 是否仍通过这些 helper 间接依赖旧链路。）

**本轮想弄清楚：**
- 哪些 event adapter 函数仍在实际实现中被调用，哪些只是旧兼容导出。
- 是否能删除未引用的旧 helper，或者是否应保留并在文档中标为兼容残留。
- 清理后是否保持事件初始化、EventTick 构造、状态文案和事件管理窗口刷新不变。

### C. SYNC 结果

关键发现：
- (verified) `create_default_event_registry()`、`find_default_game_window_rect()`、`build_event_tick()`、`event_status_text()` 仍由 `NavigationModeWidget` 调用；`event_config_summary()` 仍由 `navigation/events/panel_adapter.py` 间接调用。
- (verified) `should_event_action_take_control()` 与 `is_terminal_event_action()` 在 `gui/` 和 `core/` 实现代码中无引用；`EventActionType` 的实际消费点已集中在 `core/navigation_tasks/event_task_runner.py`、`core/navigation_tasks/intent_factory.py` 和 core event runner。
- (verified) 删除旧 UI 级 action helper 后，GUI event adapter 不再导入 `EventActionType`，职责收窄为 event bridge 输入组装与状态展示。

代码变更：
- 修改 `gui/modes/navigation/event_adapter.py`：删除 `should_event_action_take_control()`、`is_terminal_event_action()` 和未使用的 `EventActionType` 导入。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\event_adapter.py gui\modes\navigation_mode.py gui\modes\navigation\events\panel_adapter.py` 通过。
- `python -` smoke：验证默认事件 registry、事件配置摘要、`EventTick` 构造和 coordinator status 文案 helper 正常。
- `rg "should_event_action_take_control|is_terminal_event_action|EventActionType" -n gui core main.py`：旧 helper 无实现引用；`EventActionType` 仅剩 core 层引用。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/event_adapter.py` | 深度完整，旧 action helper 暂留 | 已清理旧 action helper | 追加 | GUI event adapter 不再承载 `EventActionType` 仲裁；只保留 registry/tick/status/window bridge。 |
| `gui/modes/navigation_mode.py` | 已同步多轮 GUI seams | 未变更 | 追加 | 主 UI 只使用 event adapter 活跃函数，未依赖旧 helper。 |
| `gui/modes/navigation/events/panel_adapter.py` | 深度完整 | 未变更 | 追加 | 仍只通过 `event_config_summary()` 获取配置摘要。 |

下一轮计划：
- 后续可以继续 GUI runtime loop 小步拆分，或者先对 `gui/modes/navigation_mode.py` 做剩余方法分组审计，找出可独立迁移的 UI wiring / calibration / route display 小 seam。

## [GUI-STAGE-J-NAVIGATION-MODE-REMAINING-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收尾，对 `gui/modes/navigation_mode.py` 剩余方法做函数级分组审计，选择下一处小而稳的 seam；本轮先读方法清单和局部实现，再决定是否拆 calibration、route display、UI wiring 或 runtime helper。
**目标文件：**
- `gui/modes/navigation_mode.py`（原因：仍是 GUI 最大热点；前面已抽 input/config/map/presentation/runtime 小 helper，需要继续按职责局部收敛。）
- `gui/modes/navigation/runtime/*`、`presentation/*`、`map/*`、`events/*`（原因：确认已有包边界，避免把新逻辑放错包或重复抽象。）
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`（原因：按既定 GUI 拆分准则选择下一 seam。）

**本轮想弄清楚：**
- `NavigationModeWidget` 剩余方法哪些仍属于必须留在 QWidget shell，哪些只是可独立的状态/几何/文案/helper。
- 下一步是否有比完整 `_navigation_loop_unified()` 更低风险的拆分点。
- 新模块应该归入已有功能包还是需要新增 `calibration/` 等子包。

### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget` 剩余方法可继续按职责拆：dialog/window shell、route UI wrapper、event bridge、map display/capture、config save、calibration、runtime loop。完整 `_navigation_loop_unified()` 仍是高耦合点，不适合作为下一刀。
- (verified) 屏幕中心校准是低风险 seam：重复启动防护、`CenterPointSelector` 创建/关闭、DPR 读取和 logical->physical 坐标转换可独立；配置写入、参数弹窗刷新、overlay 刷新、保存配置和完成提示仍留在 widget，保持原副作用顺序。
- (verified) 初始位置 hint 暂不拆：它同时触碰 `nav_core.set_initial_hint()`、scene marker、监控框/真实视野框和状态栏，当前继续留在 widget 比强行抽 controller 更稳。

代码变更：
- 新增 `gui/modes/navigation/calibration/__init__.py`
- 新增 `gui/modes/navigation/calibration/screen_center.py`
- 修改 `gui/modes/navigation_mode.py`：去除直接 `CenterPointSelector` 依赖，新增 `ScreenCenterCalibrationController`；`_compute_scale()` 委托 `screen_scale()`；`_calibrate_screen_center()` 委托 controller 启动选择器；`_handle_calibration_click()` 委托 controller 做坐标转换和关闭选择器。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\calibration\__init__.py gui\modes\navigation\calibration\screen_center.py` 通过。
- `python -` smoke：验证 `physical_point_from_logical()`、controller 防重复启动、坐标转换和关闭 selector 行为。
- `rg "CenterPointSelector|screen_center_calibration|screen_scale" -n gui\modes\navigation_mode.py gui\modes\navigation\calibration`：确认 `NavigationModeWidget` 不再直接导入 `CenterPointSelector`，依赖集中到 calibration helper。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/calibration/__init__.py` | 新增 | 深度完整 | 1 | navigation calibration 包入口，导出屏幕中心校准 helper。 |
| `gui/modes/navigation/calibration/screen_center.py` | 新增 | 深度完整 | 1 | CenterPointSelector 生命周期和 logical->physical DPR 转换。 |
| `gui/modes/navigation_mode.py` | 已同步多轮 GUI seams | 已同步 screen-center calibration seam | 追加 | 校准选择器创建/坐标转换委托 calibration helper；保存和 UI 提示仍在 widget。 |

下一轮计划：
- 下一块可继续做 `NavigationModeWidget` 的 shell 小 seam：dialog ownership (`_toggle_owned_dialog`/`_show_owned_dialog`) 可迁入 `navigation/presentation/dialog_host.py` 或 `navigation/shell/dialog_host.py`；也可以选择 route UI wrapper 继续瘦身。优先级上，dialog host 风险较低但收益小，route UI wrapper 能进一步减少 widget 方法数。

## [GUI-STAGE-K-NAV-ROUTE-PANEL-CONTROLLER-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收尾，把 `NavigationModeWidget` 中 route 按钮状态、click mode 切换和 route 命令结果处理收敛到 `navigation/route/` 下的 GUI route panel controller；旧 widget 方法保留 wrapper，行为和状态栏文案不变。
**目标文件：**
- `gui/modes/navigation_mode.py`（原因：当前仍有 `_set_map_click_mode()`、`toggle_*_mode()`、`_set_route_buttons_enabled()`、`load_route_data()`、`save_route()`、`undo_*()`、`clear_route()` 等 route UI wrapper 方法。）
- `gui/modes/navigation/route/editor.py`（原因：确认现有 route domain/editor seam 输出什么结果，避免重复实现 route JSON 逻辑。）
- `gui/modes/navigation/route/__init__.py`（原因：新增 route panel controller 后统一导出。）
- `gui/modes/navigation/route/panel_controller.py`（原因：新增 GUI route panel controller，集中按钮 checked/enabled、状态栏文案和 route editor 命令编排。）

**本轮想弄清楚：**
- 哪些逻辑属于 route editor/domain，哪些只是 QWidget 按钮和状态栏协调。
- 是否能让 `NavigationModeWidget` 的旧方法变成薄 wrapper，同时保留 `route_data`、`NavigationTaskController.load_route()` 和 overlay 刷新时机。
- 是否需要把 Qt 对象传入 controller，还是只传入按钮/status label 引用以保持局部化。

### C. SYNC 结果

关键发现：
- (verified) `RouteEditor` 仍是 route domain/editor seam：click mode、route.json 变更、`RouteEditResult` 属于它；Qt 按钮 checked/enabled、状态栏操作提示和保存/撤销/清空后的文案属于 GUI route panel seam。
- (verified) 可以让 `NavigationModeWidget` 的旧 route slot 保留为 wrapper：`RoutePanelController` 返回 `RouteCommandResult`，widget 继续负责 `self.route_data` 写回、`NavigationTaskController.load_route()` 同步、overlay 重绘和保存失败 QMessageBox。
- (verified) controller 只需要按钮和 status label 引用，不需要整个 widget；这降低了反向依赖，也避免 controller 接触 scene、event/runtime 或 nav_core。

代码变更：
- 新增 `gui/modes/navigation/route/panel_controller.py`
- 修改 `gui/modes/navigation/route/__init__.py` 导出 `RouteCommandResult`、`RoutePanelController`
- 修改 `gui/modes/navigation_mode.py`：初始化 `RoutePanelController`；`_set_map_click_mode()`、`toggle_*_mode()`、`_set_route_buttons_enabled()`、`save_route()`、`undo_*()`、`clear_route()` 改为委托 panel controller，保留旧方法名和外层 overlay/task 同步行为。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\route\__init__.py gui\modes\navigation\route\editor.py gui\modes\navigation\route\panel_controller.py` 通过。
- `python -` smoke：验证 route panel controller 的 click mode 文案、无 map 时按钮复位、按钮启用批量设置、保存成功/失败结果和撤销必经点文案。中文断言使用 Unicode escape，避免 PowerShell 管道编码误判。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/route/panel_controller.py` | 新增 | 深度完整 | 1 | route 按钮状态、状态栏提示和 route editor 命令结果集中。 |
| `gui/modes/navigation/route/__init__.py` | 深度完整 | 已同步 panel controller 导出 | 追加 | route 包入口导出 editor 与 panel controller。 |
| `gui/modes/navigation_mode.py` | 已同步 screen-center calibration seam | 已同步 route panel controller seam | 追加 | 旧 route slot 保留，内部委托 panel controller；overlay/task 同步仍在 widget。 |

下一轮计划：
- 此时 GUI 主线已经完成一轮较完整的 system/package 化：input、map、route、events、presentation、runtime、calibration、mapping、dialogs 都有功能包。下一步建议先停在这里做一次人工回归；若继续自动推进，优先做 `NavigationModeWidget` 的 dialog ownership 小 seam 或开始整理兼容 wrapper 清单，不建议立刻搬完整 `_navigation_loop_unified()`。
## [GUI-STAGE-L-NAV-DIALOG-HOST-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，把 `NavigationModeWidget` 中只负责 owned dialog 显示、置顶、关闭和引用清理的窗口外壳逻辑迁移到 navigation 功能包；保留 widget 的旧 slot/方法名，避免外部调用断裂。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/presentation/dialog_host.py`（预计新增，若阅读后发现更适合 shell 包则调整）
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`NavigationModeWidget.show_event_dialog()`、`show_nav_params_dialog()`、`show_advanced_settings()`、`show_color_picker()` 仍由 widget 暴露。
- 被调用方：各 dialog class 生命周期不变；dialog closed/destroyed 回调仍需清理对应引用。
- 关联 Flow：按钮点击 -> widget slot -> dialog host show/toggle -> dialog 信号/回调 -> widget 原有配置保存、刷新和参数应用逻辑。

**本轮想弄清楚：**
- `_toggle_owned_dialog()` / `_show_owned_dialog()` 是否只承担 Qt shell 生命周期，是否可以不触碰业务 dialog 信号。
- dialog host 应该接收 owner widget 和引用 getter/setter，还是只做纯函数以降低反向依赖。
- 迁移后是否保持“重复点击关闭同一个弹窗、关闭时清空引用、显示时 raise/activate”的原行为。
### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget._toggle_owned_dialog()` / `_show_owned_dialog()` 只承担 Qt shell 生命周期：空 dialog 保护、已显示且激活时返回 hide 信号、恢复最小化、首次显示按 main window 偏移、show/raise/activate/setActiveWindow。
- (verified) 这块不连接 dialog 业务信号、不保存配置、不刷新事件上下文；事件窗口创建/信号/上下文仍由 `navigation/events/panel_adapter.py` 与 widget 原 slot 负责。
- (verified) 可以把真实实现下沉到 `navigation/presentation/dialog_host.py`，让 `NavigationModeWidget` 保留旧私有方法名作为兼容 wrapper，参数面板和事件面板按钮调用链不变。

代码变更：
- 新增 `gui/modes/navigation/presentation/dialog_host.py`：提供 `toggle_owned_dialog()`、`show_owned_dialog()` 和内部 `_restore_unminimized()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 dialog host helper。
- 修改 `gui/modes/navigation_mode.py`：移除直接 `QApplication` import，旧 `_toggle_owned_dialog()` / `_show_owned_dialog()` 委托 presentation helper。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\dialog_host.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` fake smoke：patch `dialog_host.QApplication` 后验证空 dialog 安全返回、active dialog 返回 hide 信号、hidden/minimized dialog 恢复并 show/raise/activate、已可见但非 active dialog 不重复 move。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/dialog_host.py` | 新增 | 深度完整 | 1 | owned dialog show/toggle shell 行为集中，保留旧偏移和激活顺序。 |
| `gui/modes/navigation/presentation/__init__.py` | 深度完整 | 已同步 dialog host 导出 | 追加 | presentation 包入口现在导出 map/status/route/event/viewport/dialog helper。 |
| `gui/modes/navigation_mode.py` | 已同步 route panel controller seam | 已同步 dialog host seam | 追加 | 旧 dialog 私有方法保留，内部委托 presentation helper；业务 dialog 信号和配置流程未迁移。 |

下一轮计划：
- 继续低风险 seam 优先：建议审计 `NavigationModeWidget` 中 `_update_overlay_display()`、`_toggle_overlay_display()`、`_refresh_game_view_rect_from_known_position()` 等 overlay/view refresh wrapper，判断是否可进一步归入 presentation 或 map package。
- 暂不移动完整 `_navigation_loop_unified()`，它仍同时编排 capture/localization/event/task/presentation/input，适合继续先抽小 helper。
## [GUI-STAGE-M-NAV-OVERLAY-PRESENTATION-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，审计 `NavigationModeWidget` 中 debug overlay 与视野框刷新相关方法，优先把只处理 presentation 写入/可见性/状态栏联动的逻辑迁移到 `navigation/presentation/` 功能包；保留 widget 旧方法名作为兼容 wrapper。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/presentation/viewport_overlay.py` 或新增同包 helper（阅读后决定）
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`_toggle_overlay_display()`、`_update_overlay_display()`、`_update_monitor_rect()`、`_update_game_view_rect()`、`_refresh_game_view_rect_from_known_position()` 仍由 widget 内部调用。
- 被调用方：`OverlayWindow`、`screen_overlay_geometry()`、`update_monitor_rect_item()`、`update_game_view_rect_item()` 的行为必须不变。
- 关联 Flow：参数变化/加载地图/定位循环 -> wrapper 方法 -> presentation helper -> Qt overlay/window/item 更新。

**本轮想弄清楚：**
- 哪些 overlay 方法只是把已有 geometry 写入 Qt item/window，哪些仍依赖 widget 状态选择和用户反馈。
- 是否能只抽 debug overlay window 显示逻辑，不触碰定位循环和真实视野框算法。
- 抽出后是否保持 overlay checkbox、状态栏文案、主窗口 overlay 可见性时机不变。
### C. SYNC 结果

关键发现：
- (verified) `_update_monitor_rect()` 与 `_update_game_view_rect()` 已经是 `map_presenter` wrapper，继续拆收益有限；`_toggle_overlay_display()` 仍含用户可见的配置校验、checkbox 复位和 warning，适合留在 widget。
- (verified) `_update_overlay_display()` 中“capture_rect -> screen_overlay_geometry -> overlay.hide/set_rect_and_show”属于纯 presentation 写入，可迁入 `navigation/presentation/debug_overlay.py`，不触碰定位算法、按钮校验或状态栏。
- (verified) 取消勾选时直接 `self.overlay.hide_overlay()` 是用户动作翻译，继续留在 widget，避免 helper 反向知道按钮状态。

代码变更：
- 新增 `gui/modes/navigation/presentation/debug_overlay.py`：提供 `update_debug_overlay()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 `update_debug_overlay()`。
- 修改 `gui/modes/navigation_mode.py`：移除直接 `screen_overlay_geometry` import，`_update_overlay_display()` 构造 capture geometry 后委托 `update_debug_overlay()`。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\debug_overlay.py gui\modes\navigation\presentation\viewport_overlay.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` fake smoke：验证空 overlay 返回 False、无 capture rect 时 hide、有效 rect 时按 DPR 换算后调用 `set_rect_and_show()` 并携带 anchor。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/debug_overlay.py` | 新增 | 深度完整 | 1 | debug 幕布窗口写入集中，按钮校验和警告仍留在 widget。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 dialog host 导出 | 已同步 debug overlay 导出 | 追加 | presentation 包入口导出 debug overlay helper。 |
| `gui/modes/navigation_mode.py` | 已同步 dialog host seam | 已同步 debug overlay seam | 追加 | `_update_overlay_display()` 保留 wrapper，真实幕布 hide/show 写入委托 presentation helper。 |

下一轮计划：
- 可继续审计 `NavigationModeWidget` 的 map load/config save 周边 wrapper，寻找只做状态展示或配置路径组装的小 seam；但完整 `_navigation_loop_unified()` 仍暂不整块迁移。
## [GUI-STAGE-N-NAV-MAP-CONFIG-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，审计 `NavigationModeWidget` 的地图加载、导航配置保存、默认配置保存和参数变化周边方法，寻找低风险 seam；优先迁移纯状态展示/保存结果处理/已知位置刷新 helper，避免改动 `NavigationCore` 构造、配置应用顺序和文件写入契约。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/map/` 或 `gui/modes/navigation/presentation/` 下 helper（阅读后决定）
- `gui/modes/navigation/*/__init__.py`（如需导出）
**预计连带影响：**
- 调用方：`load_map()`、`_on_parameter_changed()`、`_save_nav_config()`、`_save_nav_default_config()` 保持旧方法名。
- 被调用方：`load_nav_config()`、`save_nav_config()`、`save_default_nav_config()`、`apply_motion_controller_config()`、`apply_navigation_config_to_core()` 的顺序和失败行为不变。
- 关联 Flow：加载地图/参数变化/保存按钮 -> widget wrapper -> config/map helper -> core runtime 应用 -> UI 状态栏和 overlay 刷新。

**本轮想弄清楚：**
- 哪些逻辑只是状态栏文案、按钮启用、overlay 刷新，不应混在配置写入主流程里。
- 是否有可抽取的保存结果处理 helper，同时保持中文状态文案和 QMessageBox 行为不变。
- 是否应该暂缓 `load_map()`，因为它同时创建 core、加载 npz、应用配置、初始化事件系统、刷新 route 和 overlay。
### C. SYNC 结果

关键发现：
- (verified) `load_map()` 仍是高耦合编排点：读取配置、创建 core、应用配置、回填参数弹窗、初始化 route/event、渲染地图、显示上次退出位置和启用按钮都在同一条用户动作链上，不适合整块搬迁。
- (verified) 低风险 seam 是地图加载前置 session：`load_nav_config()` 和 `NavigationCore(map_folder_path)` 可被 map package 包装；缺配置 warning、异常弹窗、配置应用顺序仍由 widget 控制。
- (verified) `_save_nav_config()` / `_on_parameter_changed()` 当前顺序敏感：保存/应用配置后立即刷新 debug overlay 和橙色视野框；本轮不拆，避免改变提示和保存时机。

代码变更：
- 新增 `gui/modes/navigation/map/session.py`：提供 `NavigationMapSettings`、`load_navigation_map_settings()`、`create_navigation_core()`。
- 修改 `gui/modes/navigation/map/__init__.py`：导出 map session helper。
- 修改 `gui/modes/navigation_mode.py`：`load_map()` 使用 `load_navigation_map_settings()` 和 `create_navigation_core()`；移除旧直接 `NavigationCore` 和 `load_nav_config` import。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\session.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：mock `load_nav_config()` 验证 `NavigationMapSettings` 保留 config/existence；mock `NavigationCore` 验证 `create_navigation_core()` 透传 map folder。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/session.py` | 新增 | 深度完整 | 1 | 只封装 NavConfig 读取和 NavigationCore 创建，不移动 load_map 其他副作用。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 config store/capture geometry | 已同步 map session 导出 | 追加 | map 包入口导出 session DTO 与创建 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 debug overlay seam | 已同步 map session seam | 追加 | `load_map()` 首段委托 map/session；缺配置 warning、配置应用、渲染和按钮启用仍在 widget。 |

下一轮计划：
- 建议后续继续小步审计 `load_map()` 后半段，优先候选是“加载成功后的 UI enable/status 编排”或“物理中心回填参数弹窗”这种展示/绑定 seam；配置保存链路暂时保持不动。
## [GUI-STAGE-O-NAV-MAP-LOAD-UI-SEAM] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，围绕 `NavigationModeWidget.load_map()` 后半段审计 UI 回填、地图加载成功后的按钮启用和状态栏提示，优先抽取纯 UI state helper；不移动 `NavigationCore` 创建、`NavConfig` 应用、route/event 初始化和地图渲染顺序。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/presentation/` 或 `gui/modes/navigation/map/` 下 helper（阅读后决定）
- 对应 `__init__.py` 导出
**预计连带影响：**
- 调用方：`load_map()` 保持旧 public slot；`refresh_map_list()`、`_save_nav_config()` 暂不改。
- 被调用方：`params_dialog.set_config_to_ui()`、`_set_route_buttons_enabled()`、`status_label.setText()` 的文案和时机不变。
- 关联 Flow：用户点击加载地图 -> load_map -> config/core/session/apply/route/event/render -> UI enable/status。

**本轮想弄清楚：**
- 成功加载后的按钮启用和状态栏文案是否能从 `load_map()` 中抽出，不改变任何核心副作用。
- 物理中心回填参数弹窗是否应和 map session 放一起，还是因为触碰 dialog 继续留在 widget。
- 是否存在类似 `refresh_map_list()` 的低风险 combo 写入 helper 可以同轮处理。
### C. SYNC 结果

关键发现：
- (verified) `load_map()` 后半段仍有配置应用、route/event 初始化、地图渲染和 overlay 刷新，继续留在 widget 更稳。
- (verified) 地图列表 combo 填充和加载成功后的按钮/状态栏写入是纯 UI state，可迁入 presentation helper，不影响 core 初始化或配置应用顺序。
- (verified) 参数弹窗 `set_config_to_ui()` 触碰具体 dialog 字段和物理中心展示，暂时不迁移，避免把 dialog binding 混入 map session。

代码变更：
- 新增 `gui/modes/navigation/presentation/map_load_state.py`：提供 `populate_map_combo()`、`apply_map_loaded_ui()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 map-load UI helper。
- 修改 `gui/modes/navigation_mode.py`：`refresh_map_list()` 委托 `populate_map_combo()`；`load_map()` 最后委托 `apply_map_loaded_ui()` 写入加载成功 UI 状态。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\map_load_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证 combo 有地图/无地图两条路径，以及加载成功后开始按钮、初始位置按钮、route panel 和中文状态栏文案。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/map_load_state.py` | 新增 | 深度完整 | 1 | 地图 combo 填充与加载成功 UI 状态集中，不触碰 map IO/core/config。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 debug overlay 导出 | 已同步 map-load UI 导出 | 追加 | presentation 包入口导出 map-load UI helper。 |
| `gui/modes/navigation_mode.py` | 已同步 map session seam | 已同步 map-load UI seam | 追加 | `refresh_map_list()` 和 `load_map()` 成功尾部委托 presentation helper。 |

下一轮计划：
- 后续可以继续拆 `load_map()` 的“物理中心计算/参数弹窗回填”或审计 `_save_nav_config()` 的结果处理；建议仍以小 seam 方式推进，不改变保存和应用配置时机。
## [GUI-STAGE-P-NAV-PARAMS-REFILL-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，审计 `NavigationModeWidget.load_map()` 中物理中心计算、`params_dialog.set_config_to_ui()` 回填和 `_capture_center_physical` 缓存写入，判断是否可以抽出低风险 helper；优先保持导航截图坐标缓存时机和参数弹窗回填时机不变。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/map/` 或 `gui/modes/navigation/dialogs/` 下 helper（阅读后决定）
**预计连带影响：**
- 调用方：`load_map()` 保持旧流程；`_build_capture_geometry()` 仍使用 `_capture_center_physical` 缓存。
- 被调用方：`physical_center_from_logical()`、`params_dialog.set_config_to_ui()` 语义不变。
- 关联 Flow：加载地图 -> 读取 nav_config -> apply core config -> 计算物理中心缓存 -> 参数弹窗回填。

**本轮想弄清楚：**
- 物理中心计算是否足够独立，可以返回 `(capture_center_physical, physical_center_for_ui)`。
- 这块应该属于 map/capture geometry，还是 dialog 参数绑定；避免把 dialog 对象传到 map 包。
- 是否能先只抽纯计算，不搬 `params_dialog.set_config_to_ui()`。
### C. SYNC 结果

关键发现：
- (verified) 物理中心计算可以作为纯 geometry helper 返回，不需要把 `params_dialog` 传入 map 包。
- (verified) `params_dialog.set_config_to_ui()` 仍应留在 `load_map()`，因为它触碰具体 dialog 字段和 UI 回填时机。
- (verified) `_build_capture_geometry()` 仍需要 `physical_center_from_logical()` 做懒计算，所以旧 helper 保留。

代码变更：
- 修改 `gui/modes/navigation/map/capture_geometry.py`：新增 `initial_capture_center_for_config()`。
- 修改 `gui/modes/navigation/map/__init__.py`：导出 `initial_capture_center_for_config()`。
- 修改 `gui/modes/navigation_mode.py`：`load_map()` 使用 `initial_capture_center_for_config()` 初始化 `_capture_center_physical` 和参数弹窗物理中心显示值。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\capture_geometry.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证空 config、无 logical center 和有 logical center 三条返回路径。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/capture_geometry.py` | 深度完整 | 已同步 initial capture center helper | 追加 | load-map 初始物理中心计算下沉为纯 helper。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 map session 导出 | 已同步 initial capture center 导出 | 追加 | map 包入口导出初始中心计算 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 map-load UI seam | 已同步 initial capture center seam | 追加 | `load_map()` 仍负责 dialog 回填和 debug print，只委托纯物理中心计算。 |

下一轮计划：
- 可继续审计 `_save_nav_config()` / `_save_nav_default_config()` 的结果处理，优先只抽状态栏和 QMessageBox 文案 helper；若发现保存顺序风险大，则先停在审计结论。
## [GUI-STAGE-Q-NAV-CONFIG-SAVE-RESULT-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `NavigationModeWidget._save_nav_config()` 与 `_save_nav_default_config()` 的保存结果处理，判断是否能抽出纯 UI result helper；严格保持保存顺序、应用配置时机、overlay/视野框刷新和 QMessageBox 文案不变。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/presentation/` helper（阅读后决定）
**预计连带影响：**
- 调用方：参数对话框 `save_requested` 和 `save_default_requested` 信号仍触发旧 slot。
- 被调用方：`save_nav_config()`、`save_default_nav_config()`、`_apply_config_to_core()`、`_update_overlay_display()`、`_refresh_game_view_rect_from_known_position()` 顺序不变。
- 关联 Flow：保存按钮 -> 写 config -> 应用配置 -> overlay/视野框刷新 -> 状态栏/QMessageBox。

**本轮想弄清楚：**
- 成功/失败状态栏和 QMessageBox 是否能用 helper 集中，避免主 widget 承担文案细节。
- helper 是否会引入过度抽象；如果只是两三个 setText/QMessageBox，是否应该保留。
- 默认配置保存和当前地图配置保存是否能共用同一个结果展示接口。
### C. SYNC 结果

关键发现：
- (verified) `_save_nav_config()` 的核心顺序必须保持：`save_nav_config()` 写入 -> `_apply_config_to_core()` 应用 -> `_update_overlay_display()` 刷新 debug overlay -> `_refresh_game_view_rect_from_known_position()` 刷新视野框 -> 展示保存结果。
- (verified) `_save_nav_default_config()` 只负责默认配置写入和结果提示，不应混入当前地图配置应用。
- (verified) 可迁出的部分仅是状态栏与 `QMessageBox` 结果展示；保存、应用、刷新仍留在 `NavigationModeWidget` 旧 slot 中。

代码变更：
- 新增 `gui/modes/navigation/presentation/config_save_state.py`：集中导航参数脏状态、当前地图配置保存结果、默认配置保存结果的中文状态栏和弹窗文案。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 config-save presentation helper。
- 修改 `gui/modes/navigation_mode.py`：`_on_parameter_changed()`、`_save_nav_config()`、`_save_nav_default_config()` 保留旧方法名和业务顺序，内部委托 result helper 展示 UI 结果。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\config_save_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：patch `QMessageBox` 后验证当前地图配置保存成功/失败、默认配置缺失/成功/失败路径的状态栏和弹窗调用。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/config_save_state.py` | 新增 | 深度完整 | 1 | 导航参数保存结果展示集中；不触碰 config IO、core 应用和 overlay 刷新。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 map-load UI 导出 | 已同步 config-save UI 导出 | 追加 | presentation 包入口导出配置保存状态 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 initial capture center seam | 已同步 config-save result seam | 追加 | 保存 slot 保留业务顺序，只把状态栏和 QMessageBox 文案委托给 helper。 |

下一轮计划：
- 继续审计 `NavigationModeWidget` 内事件管理相关结果展示：`_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`，优先抽取纯 UI result helper，不改变 event adapter、manual test controller 和任务状态清理顺序。
## [GUI-STAGE-R-NAV-EVENT-MANAGEMENT-RESULT-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 结构化收敛，审计 `NavigationModeWidget` 中事件管理保存、传送门状态重置、手动测试启动/停止相关的结果展示逻辑；优先迁出状态栏和 `QMessageBox` 文案，不移动事件配置 IO、manual test controller、portal state 清理和 runtime bridge。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/events/` 或 `gui/modes/navigation/presentation/` 下 helper（阅读后决定）
- 对应 `__init__.py` 导出
**预计连带影响：**
- 调用方：`EventManagerDialog` 的 `save_requested`、`manual_test_requested`、`reset_state_requested` 信号仍触发旧 widget slot。
- 被调用方：`NavigationEventPanelAdapter`、`ManualEventTestController`、`PortalMemory`、`NavigationTaskController` 的调用顺序不变。
- 关联 Flow：事件管理弹窗按钮 -> widget 旧 slot -> event adapter/manual test/runtime 状态处理 -> 状态栏/QMessageBox 反馈。

**本轮想弄清楚：**
- 事件配置保存成功/失败、未加载地图警告是否只是展示层，可以集中到 helper。
- 传送门状态重置中的业务动作和提示文案边界在哪里，避免把 `task_controller` 或 `portal_memory` 藏进 presentation。
- 手动测试启动/停止提示是否能拆出，而不改变 screen center 校验和 controller toggle 语义。
### C. SYNC 结果

关键发现：
- (verified) `_save_event_config()` 的业务边界是 `save_event_config()` 写入和 `_refresh_event_dialog()` 刷新；成功/失败/缺上下文提示只是 presentation，可迁出。
- (verified) `_reset_portal_event_state()` 的业务动作包括停止手动测试、`EventCoordinator.reset_event_type("portal")`、重置 event movement runtime、清理/重绘 overlay、刷新 dialog tasks；这些仍留在 widget，状态栏文案可迁出。
- (verified) `_run_portal_manual_test()` 和 `_set_portal_manual_test_active()` 的 runtime 边界包括 nav timer 启动、button reset、route load、task controller start、input window mode 和 motion enabled；本轮只迁出 guard warning 与启动/停止状态栏。

代码变更：
- 新增 `gui/modes/navigation/presentation/event_management_state.py`：集中事件配置保存、事件系统缺失、屏幕中心缺失、传送门状态刷新、手动测试启动/停止的旧中文提示。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 event-management presentation helper。
- 修改 `gui/modes/navigation_mode.py`：`_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`、`_set_portal_manual_test_active()` 保留旧方法名和业务顺序，内部委托 helper 展示反馈。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\event_management_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：patch `QMessageBox` 后验证事件配置缺失/成功/失败、事件系统缺失、屏幕中心缺失、传送门状态刷新、手动测试启动/停止文案。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/event_management_state.py` | 新增 | 深度完整 | 1 | 事件管理用户反馈集中；不触碰 event IO、coordinator、manual test controller 或 motion/input 状态。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 config-save UI 导出 | 已同步 event-management UI 导出 | 追加 | presentation 包入口导出事件管理结果 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 config-save result seam | 已同步 event-management result seam | 追加 | 事件管理旧 slot 保留业务动作，只把 QMessageBox 和状态栏文案委托给 helper。 |

下一轮计划：
- 继续审计 `NavigationModeWidget` 中自动导航启动/停止和导航启动前 guard 的用户反馈；优先只抽按钮/状态栏/warning 文案，避免触碰 `NavigationTaskController`、`MotionController` 和 `nav_timer` 生命周期。
## [GUI-STAGE-S-NAV-RUNTIME-COMMAND-FEEDBACK-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `NavigationModeWidget` 中自动导航切换、导航启动 guard、导航启动/停止状态栏相关的用户反馈；优先迁出 warning/status 文案，不移动 `nav_timer`、`NavigationTaskController`、`MotionController`、route validation 和 input window mode。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增 `gui/modes/navigation/presentation/` 下 helper（阅读后决定）
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`btn_auto_nav.clicked`、`btn_start.clicked` 仍触发旧 widget slot。
- 被调用方：`NavigationTaskController.load_route/start/stop()`、`MotionController.set_control_enabled()`、`nav_timer.start/stop()` 顺序不变。
- 关联 Flow：用户点击自动导航/开始导航 -> widget guard 与 runtime 控制 -> 状态栏/QMessageBox 反馈。

**本轮想弄清楚：**
- 自动导航 guard 中未加载地图、路线无效、自动导航启动/停止文案是否可以集中。
- `toggle_navigation()` 中未校准屏幕中心、地图配置不完整、开始/暂停文案是否可以迁出 presentation。
- 是否能保持按钮 checked/text 仍由 widget 控制，helper 只处理人类可见反馈。
### C. SYNC 结果

关键发现：
- (verified) `toggle_auto_navigation()` 中 `NavigationTaskController.load_route/start/stop()`、自动启动 nav timer、`auto_navigation_enabled`、input window mode 和 route overlay 刷新仍是 runtime 控制逻辑，不能放进 presentation。
- (verified) 自动导航 guard 失败、路线无效、启动/停止状态栏只是用户反馈，可迁出。
- (verified) `toggle_navigation()` 中配置 guard、`_apply_config_to_core()`、tracker reset、`nav_timer.start()`、motion enable 和按钮文字仍由 widget 编排；开始/暂停状态栏和 guard warning 可迁出。

代码变更：
- 新增 `gui/modes/navigation/presentation/navigation_command_state.py`：集中自动导航 guard、路线无效、自动导航启动/停止、导航启动/暂停的旧中文 warning/status 文案。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 navigation-command presentation helper。
- 修改 `gui/modes/navigation_mode.py`：`toggle_auto_navigation()`、`toggle_navigation()`、`stop_runtime()` 保留 runtime 顺序，内部委托 helper 展示用户反馈。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\navigation_command_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：patch `QMessageBox` 后验证自动导航 guard/路线无效、导航 guard、自动导航启动/停止、导航开始/暂停文案。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/navigation_command_state.py` | 新增 | 深度完整 | 1 | 导航命令用户反馈集中；不触碰 route validation、task controller、timer、motion 或按钮状态。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 event-management UI 导出 | 已同步 navigation-command UI 导出 | 追加 | presentation 包入口导出导航命令反馈 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 event-management result seam | 已同步 navigation-command feedback seam | 追加 | 自动导航/导航启动旧 slot 保留控制顺序，只把 warning/status 文案委托给 helper。 |

下一轮计划：
- 继续评估 `NavigationModeWidget` 剩余热点：可优先看 `_toggle_overlay_display()` 的 debug overlay warning/checkbox 复位是否值得抽，或转入更高收益的 `navigation_loop` runtime tick 结果对象；仍避免一次性搬完整循环。
## [GUI-STAGE-T-NAV-MAP-LOAD-FEEDBACK-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `NavigationModeWidget.load_map()` 周边的缺配置 warning、加载异常 critical 和 debug overlay 配置不完整 warning；优先迁出用户反馈文案，不移动 `load_map()` 的 config/core/session/apply/route/event/render 顺序，也不改变 overlay checkbox 复位时机。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增或扩展 `gui/modes/navigation/presentation/map_load_state.py`
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`refresh_map_list()`、`load_map()`、`_toggle_overlay_display()` 保持旧方法名。
- 被调用方：`load_navigation_map_settings()`、`create_navigation_core()`、`apply_navigation_config_to_core()`、`apply_map_loaded_ui()` 调用顺序不变。
- 关联 Flow：加载地图按钮 -> config/core 初始化 -> 用户反馈；debug overlay 勾选 -> config guard -> checkbox 复位/警告。

**本轮想弄清楚：**
- 缺 `config.json` warning 和加载失败 critical 是否可归入 map-load presentation helper。
- debug overlay 配置不完整 warning 是否和地图加载反馈同属 map/overlay command feedback，是否可同 helper 管理。
- 是否必须保留 `self.btn_overlay.setChecked(False)` 在 widget 中，以免 helper 过多知道按钮状态。
### C. SYNC 结果

关键发现：
- (verified) `load_map()` 的核心副作用顺序仍是读取配置 -> 创建 core -> 应用配置 -> 回填参数弹窗 -> 初始化 route/event -> 渲染地图 -> 写加载成功 UI；本轮未移动这些动作。
- (verified) 缺 `config.json` warning、加载失败 critical 和 overlay 配置不完整 warning 都只是用户反馈，可扩展到 `presentation/map_load_state.py`。
- (verified) overlay 配置不完整时的 `nav_toggle_overlay_btn.setChecked(False)` 是命令状态复位，应留在 widget；helper 只弹提示。

代码变更：
- 扩展 `gui/modes/navigation/presentation/map_load_state.py`：新增 `warn_map_config_missing()`、`show_map_load_failed()`、`warn_overlay_map_config_incomplete()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 map-load feedback helper。
- 修改 `gui/modes/navigation_mode.py`：`load_map()` 和 `_toggle_overlay_display()` 保留旧流程，内部委托 helper 展示缺配置、加载失败、overlay 配置不完整提示。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\map_load_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：patch `QMessageBox` 后验证缺 `config.json`、加载失败、overlay 配置不完整三条旧中文提示。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/map_load_state.py` | 已同步 map-load UI seam | 已同步 map-load feedback seam | 追加 | 承载地图 combo/加载成功 UI 以及缺配置、加载失败、overlay 配置不完整提示；不触碰 core/config/按钮复位。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 navigation-command UI 导出 | 已同步 map-load feedback 导出 | 追加 | presentation 包入口导出地图加载反馈 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 navigation-command feedback seam | 已同步 map-load feedback seam | 追加 | `load_map()` 和 `_toggle_overlay_display()` 保留业务顺序，只把 QMessageBox 文案委托给 helper。 |

下一轮计划：
- 继续收敛剩余直接 `QMessageBox/status_label`：路线保存失败、点击移动目标、初始位置提示、校准完成属于 route/calibration command feedback；建议分两轮分别抽 route command feedback 与 calibration feedback，保持每轮小而可验。
## [GUI-STAGE-U-NAV-ROUTE-COMMAND-FEEDBACK-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `NavigationModeWidget` 中 route panel 命令结果、路线保存失败、地图点击 route edit 结果和移动目标提示；优先迁出状态栏和 warning 文案，不移动 `RouteEditor`、`RoutePanelController`、`RouteManager`、`MotionController` 或 route overlay 刷新顺序。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增或扩展 `gui/modes/navigation/presentation/` helper
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：route toolbar 按钮和 scene click 仍触发旧 widget 方法。
- 被调用方：`RoutePanelController.save/undo/clear`、`RouteEditor.handle_click()`、`MotionController.move_to_map_target()` 调用顺序不变。
- 关联 Flow：route 按钮/地图点击 -> route editor/panel controller -> overlay/runtime sync -> 状态栏或 warning。

**本轮想弄清楚：**
- route command result 的状态栏写入是否可集中为一个小 helper。
- 保存路线失败 warning 是否可迁出，不改变保存失败分支的 overlay/task 同步行为。
- 普通移动目标 guard 和成功状态栏是否适合作为 route/map command feedback。
### C. SYNC 结果

关键发现：
- (verified) route 保存/撤销/清空的真实动作已在 `RoutePanelController` 与 `RouteEditor`，`NavigationModeWidget` 仍必须同步 `route_data`、加载 main route 到 `NavigationTaskController` 并重绘 overlay。
- (verified) route command status 文案、保存失败 warning、移动目标未定位 warning 和移动目标坐标状态栏只是用户反馈，可迁出。
- (verified) 普通移动目标成功时仍必须由 widget 调用 `MotionController.move_to_map_target()` 和 `set_target_marker()`，helper 只格式化状态栏。

代码变更：
- 新增 `gui/modes/navigation/presentation/route_command_state.py`：提供 `show_route_command_status()`、`warn_route_save_failed()`、`warn_move_target_requires_localization()`、`show_move_target_set()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 route-command presentation helper。
- 修改 `gui/modes/navigation_mode.py`：route 保存/撤销/清空、route editor click 结果和移动目标 guard/成功提示委托 helper；route data、overlay 和 motion 顺序不变。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\route_command_state.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证 route status 空值不覆盖、保存失败 warning、未定位移动目标 warning、移动目标坐标格式。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/route_command_state.py` | 新增 | 深度完整 | 1 | route/移动目标用户反馈集中；不触碰 route JSON、overlay、task controller 或 motion。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 map-load feedback 导出 | 已同步 route-command feedback 导出 | 追加 | presentation 包入口导出 route 命令反馈 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 map-load feedback seam | 已同步 route-command feedback seam | 追加 | route 命令旧方法保留 route data/overlay/motion 顺序，只把 warning/status 文案委托给 helper。 |

下一轮计划：
- 继续拆 calibration/hint feedback：`set_initial_hint()`、`toggle_hint_mode()`、`_handle_calibration_click()` 的状态栏和完成弹窗可下沉到 calibration/presentation helper；屏幕中心写入、配置保存和 selector 生命周期仍留在 widget/calibration controller。
## [GUI-STAGE-V-NAV-CALIBRATION-FEEDBACK-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `NavigationModeWidget` 中初始位置提示、hint mode 切换和屏幕中心校准完成的用户反馈；优先迁出状态栏和完成弹窗文案，不移动 `nav_core.set_initial_hint()`、`_update_monitor_rect()`、`NavConfig.game_screen_center` 写入、配置保存或 selector 生命周期。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能新增或扩展 `gui/modes/navigation/presentation/` 或 `gui/modes/navigation/calibration/` helper（阅读后决定）
- 对应 `__init__.py` 导出
**预计连带影响：**
- 调用方：hint 按钮和 screen center selector 仍触发旧 widget 方法。
- 被调用方：`ScreenCenterCalibrationController`、`NavConfig`、`save_nav_config()`、`params_dialog.set_config_to_ui()` 顺序不变。
- 关联 Flow：用户点击设置初始位置/校准屏幕中心 -> widget 写 core/config -> 状态栏/QMessageBox 反馈。

**本轮想弄清楚：**
- hint mode 状态栏和初始位置设置状态栏是否可作为 calibration/hint presentation helper。
- 校准完成弹窗是否可迁出，同时保留配置写入和保存顺序。
- helper 放在 `presentation/` 是否比放在 `calibration/` 更合适；本轮只迁用户反馈，倾向 presentation。
### C. SYNC 结果

关键发现：
- (verified) `set_initial_hint()` 的业务动作包括全局坐标换算、`NavigationCore.set_initial_hint()`、hint marker 创建、监控框/视野框刷新和 hint 按钮复位；状态栏文案可迁出。
- (verified) `toggle_hint_mode()` 的 drag/cursor 状态仍由 widget 控制；开启/取消文案可迁出。
- (verified) `_handle_calibration_click()` 的逻辑到物理坐标转换、`NavConfig.game_screen_center` 写入、参数弹窗回填、overlay 刷新、`_save_nav_config()` 和 selector close 时机不变；校准完成弹窗可迁出且仍位于保存之后、关闭 selector 之前。

代码变更：
- 新增 `gui/modes/navigation/presentation/calibration_feedback.py`：提供 `show_initial_hint_set()`、`show_hint_mode_status()`、`show_screen_center_calibrated()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 calibration feedback helper。
- 修改 `gui/modes/navigation_mode.py`：`set_initial_hint()`、`toggle_hint_mode()`、`_handle_calibration_click()` 保留业务顺序，内部委托 helper 展示状态栏和完成弹窗。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\calibration_feedback.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证初始位置坐标显示、hint mode 开启/取消文案和校准完成弹窗文案。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/calibration_feedback.py` | 新增 | 深度完整 | 1 | hint/calibration 用户反馈集中；不触碰 nav_core、config 保存、selector 生命周期。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 route-command feedback 导出 | 已同步 calibration feedback 导出 | 追加 | presentation 包入口导出 hint/calibration 反馈 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 route-command feedback seam | 已同步 calibration feedback seam | 追加 | hint/calibration 旧方法保留写 core/config/selector 顺序，只把状态栏和完成弹窗委托给 helper。 |

下一轮计划：
- 直接 `QMessageBox` 已基本从 `NavigationModeWidget` 的普通命令链路移除，剩余状态栏写入集中在 `_navigation_loop_unified()` 的运行态状态更新。下一步不建议继续按“文案 helper”硬拆，应转向 runtime loop 小步：例如把 intent 后处理/状态追加逻辑整理成 runtime result 或 presentation status update helper。
## [GUI-STAGE-W-NAV-QMESSAGEBOX-IMPORT-CLEANUP] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 在多轮 presentation feedback seam 后，确认 `NavigationModeWidget` 不再直接调用 `QMessageBox`，清理旧 import，避免主 widget 继续表现为弹窗职责持有者。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
**预计连带影响：**
- 无行为影响；所有弹窗调用已迁入 `navigation/presentation/*_state.py` 或 `calibration_feedback.py`。

### C. SYNC 结果

关键发现：
- (verified) `rg -n "QMessageBox" gui/modes/navigation_mode.py` 只剩 import，已无直接调用。
- (verified) 移除 import 后目标编译和全 GUI 编译均通过。

代码变更：
- 修改 `gui/modes/navigation_mode.py`：移除 PySide6 `QMessageBox` import。

更新文档：
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py` 通过。
- 全 GUI `py_compile` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已同步 calibration feedback seam | 已同步 QMessageBox import cleanup | 追加 | 主 widget 不再直接 import/call QMessageBox；普通命令反馈已委托 presentation helper。 |

下一轮计划：
- 转向 runtime loop 小步，而不是继续拆普通文案：优先候选是把 `_navigation_loop_unified()` 后半段的“intent 后处理 + 状态追加”提炼成 runtime/presentation 结果对象，保持 timer/capture/localize/event/task 顺序不变。
## [GUI-STAGE-X-NAV-RUNTIME-STATUS-UPDATE-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `_navigation_loop_unified()` 后半段状态栏写入，优先迁出“基础导航状态、重新定位后缀、到达出口、intent 失败、点击后缀追加”这些 presentation 写入 helper；不移动 capture、localize、event observe、task controller update、intent execution 或 overlay 刷新顺序。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能扩展 `gui/modes/navigation/presentation/status_presenter.py`
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`navigation_loop()` 和 `_navigation_loop_unified()` 仍为旧入口。
- 被调用方：`build_navigation_status_text()`、`update_navigation_task_controller()`、`execute_navigation_intent()` 行为不变。
- 关联 Flow：每帧定位/事件/任务/intent -> presentation status helper -> 状态栏文本。

**本轮想弄清楚：**
- 基础状态栏写入是否可封装为 `show_navigation_status()`，继续复用已有 `build_navigation_status_text()`。
- 重新定位/到达出口/intent 失败/点击后缀是否只是状态栏更新，可迁入 `status_presenter.py`。
- 是否能保持状态追加基于当前 label text 的旧语义，避免改变用户看到的信息顺序。
### C. SYNC 结果

关键发现：
- (verified) `_navigation_loop_unified()` 中基础状态栏写入、force relocalize 后缀、ARRIVED/FAILED 终态文案和 click suffix 追加都是 presentation 写入，可迁入 `status_presenter.py`。
- (verified) relocalize 请求、`event_log()`、intent 执行、终态停止 `NavigationTaskController`、input window mode 和按钮 checked 状态仍是 runtime/control 逻辑，留在 widget。
- (verified) `append_navigation_status_suffix()` 保留旧语义：先读当前 label 文本，再追加 ` | suffix`，所以文案顺序不变。

代码变更：
- 扩展 `gui/modes/navigation/presentation/status_presenter.py`：新增 `show_navigation_runtime_status()`、`append_navigation_status_suffix()`、`show_navigation_relocalizing()`、`show_navigation_arrived()`、`show_navigation_failed()`。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出新增 runtime status helper。
- 修改 `gui/modes/navigation_mode.py`：`_navigation_loop_unified()` 和 `_execute_navigation_intent()` 的状态栏写入委托 `status_presenter.py`；调度、重定位、intent 执行和终态 controller 停止顺序不变。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\status_presenter.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证基础状态构造/写入、后缀追加空值不覆盖、重新定位后缀、到达终态、失败默认文案和自定义失败文案。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/status_presenter.py` | 已同步导航循环状态栏文案构造 | 已同步 runtime status write seam | 追加 | 运行态状态栏写入和后缀追加集中；不触碰 relocalize、intent 执行或 controller 停止。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 calibration feedback 导出 | 已同步 runtime status helper 导出 | 追加 | presentation 包入口导出运行态状态栏 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 QMessageBox import cleanup | 已同步 runtime status update seam | 追加 | `_navigation_loop_unified()` 保留 runtime/control 顺序，只把状态栏写入委托给 presenter。 |

下一轮计划：
- 到此 `NavigationModeWidget` 已不直接持有普通弹窗职责，状态栏写入也只剩通过 presenter；下一步若继续，应围绕 `_navigation_loop_unified()` 的结构性 runtime result 拆分，而不是再拆文案。
## [GUI-STAGE-Y-NAV-LOCALIZATION-VIEW-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 审计 `_navigation_loop_unified()` 中定位结果到 UI marker/viewport 的显示更新：localized 时更新 player marker、监控框、视野框和视图居中；未 localized 时使用 fallback 更新框并隐藏 player marker。目标是迁出纯 presentation 编排，不移动定位、事件、任务调度或状态栏逻辑。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能扩展 `gui/modes/navigation/presentation/map_presenter.py`
- `gui/modes/navigation/presentation/__init__.py`
**预计连带影响：**
- 调用方：`_navigation_loop_unified()` 保持旧入口。
- 被调用方：`update_player_marker()`、`hide_item()`、`_update_monitor_rect()`、`_update_game_view_rect()` 调用时机保持在定位后、状态栏前。
- 关联 Flow：localize -> localization result -> presentation update -> status/update route/intent。

**本轮想弄清楚：**
- 是否可以把 localized/fallback 两条显示路径抽为一个 helper，同时让 widget 继续提供 `_update_monitor_rect()` 和 `_update_game_view_rect()` 回调。
- 是否应把 `view.centerOn()` 也放进 helper；它纯属于 view presentation。
- helper 是否能返回新的 `player_item`，避免 presenter 直接修改 widget 属性。
### C. SYNC 结果

关键发现：
- (verified) localized 分支中的 player marker 更新、监控框/视野框刷新和 `view.centerOn()` 都是定位结果的 UI 展示，可迁入 `map_presenter.py`。
- (verified) 未定位 fallback 分支只使用 `last_good_pos/drawing_saved_pos` 更新框并隐藏玩家 marker，也属于 presentation 更新。
- (verified) presenter 不应知道 widget 私有方法，因此通过 `update_monitor_rect`、`update_game_view_rect` 回调保留旧调用实现，并返回 `player_item` 让 widget 写回属性。

代码变更：
- 扩展 `gui/modes/navigation/presentation/map_presenter.py`：新增 `update_localization_view()`，集中 localized/fallback 显示更新。
- 修改 `gui/modes/navigation/presentation/__init__.py`：导出 `update_localization_view()`。
- 修改 `gui/modes/navigation_mode.py`：`_navigation_loop_unified()` 定位显示分支委托 presenter；定位、事件、任务、状态栏和 intent 顺序不变。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\presentation\__init__.py gui\modes\navigation\presentation\map_presenter.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证 localized 分支更新 player marker、调用监控/视野框回调并居中；未定位 fallback 分支调用回调并隐藏 player marker。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/presentation/map_presenter.py` | 已同步地图 scene item/marker presenter | 已同步 localization view seam | 追加 | 定位结果到 player marker/viewport/fallback hide 的展示编排集中；通过回调保留 widget 私有更新实现。 |
| `gui/modes/navigation/presentation/__init__.py` | 已同步 runtime status helper 导出 | 已同步 localization view helper 导出 | 追加 | presentation 包入口导出定位显示更新 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 runtime status update seam | 已同步 localization view seam | 追加 | `_navigation_loop_unified()` 保留定位和任务调度顺序，只把定位结果显示分支委托给 presenter。 |

下一轮计划：
- 若继续推进 runtime loop，建议抽 `event observation + event dialog refresh` 或 `intent terminal handling` 之一为 helper；不要一次性搬完整 `_navigation_loop_unified()`。
## [GUI-STAGE-Z-NAV-RUNTIME-EVENT-OBSERVATION-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续围绕 `NavigationModeWidget._navigation_loop_unified()` 做 runtime 小步结构化，优先审计“构造 event tick -> EventCoordinator.observe() -> event overlay/dialog refresh”的事件观测分支。注意保留后续可接“总线”的交互边界：本轮不实现 hook/event bus，只把事件观测结果和 UI 刷新边界命名清楚。
**直接变更文件：**
- `gui/modes/navigation_mode.py`
- 可能扩展或新增 `gui/modes/navigation/runtime/` helper
- `gui/modes/navigation/runtime/__init__.py`
**预计连带影响：**
- 调用方：`_navigation_loop_unified()` 保持旧入口。
- 被调用方：`_build_event_tick()`、`EventCoordinator.observe()`、`_render_event_overlay()`、`EventManagerDialog.refresh_tasks()` 调用顺序不变。
- 关联 Flow：每帧定位 -> event tick -> event coordinator observe -> overlay/dialog presentation -> task controller update 使用同一个 `event_tick`。

**本轮想弄清楚：**
- 是否可以把“有 event coordinator 时构造 tick、observe、overlay/dialog refresh”抽成 helper，同时返回 `event_tick` 给后续 task update。
- helper 是否应该接收 callbacks，而不是直接知道 widget 私有 `_build_event_tick()`/`_render_event_overlay()`。
- 这个 helper 如何为后续 hook 总线留出边界：当前可返回 tick，后续可在 observe 前后挂 hook，但本轮不做总线。
### C. SYNC 结果

关键发现：
- (verified) event observation mini-flow 可独立：`build_event_tick()` -> `EventCoordinator.observe()` -> `_render_event_overlay()` -> 可见 event dialog `refresh_tasks()`，最后返回同一个 `event_tick` 给 `NavigationTaskController.update()`。
- (verified) helper 使用 callbacks 接入 widget 私有 `_build_event_tick()` 和 `_render_event_overlay()`，避免 runtime helper 反向依赖 QWidget。
- (verified) 该 helper 是未来 hook/总线的自然边界：可在 observe 前后挂事件，但本轮只命名 seam，不实现 hook/bus，符合“总线先记住、不要急做”的策略。

代码变更：
- 扩展 `gui/modes/navigation/runtime/loop.py`：新增 `observe_navigation_events()`。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 `observe_navigation_events()`。
- 修改 `gui/modes/navigation_mode.py`：`_navigation_loop_unified()` 中事件观测分支委托 runtime helper；定位、任务 update、UI 状态顺序不变。

更新文档：
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `CODEBASE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\loop.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证无 coordinator 时返回 `None` 且不刷新；有 coordinator 时 build/observe/render/isVisible/refresh_tasks 顺序正确，并返回 tick。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/loop.py` | 已同步 player local/task update helper | 已同步 event observation seam | 追加 | 事件观测 mini-flow 集中；返回 event_tick；保留未来 hook/总线边界但不实现 hook。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 runtime helper 导出 | 已同步 event observation helper 导出 | 追加 | runtime 包入口导出事件观测 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 localization view seam | 已同步 event observation seam | 追加 | `_navigation_loop_unified()` 保留每帧主顺序，只把 event observe/overlay/dialog refresh 委托给 runtime helper。 |

下一轮计划：
- 下一步可抽 `intent terminal handling` helper：ARRIVED/FAILED 的 controller 停止、input window 恢复、按钮复位和状态 presenter 调用；同样保留未来总线边界，但不引入 hook 实现。
## [GUI-STAGE-AA-CORE-IMPORT-MIGRATION-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 切换到下一阶段主线：GUI 逐步迁移到新 core 包路径，减少对旧 `core.*` 顶层兼容壳的依赖。旧兼容层不删除，留到 GUI 和脚本迁移完成后统一审计；总线/hook 仍只保留 seam 边界，不实现。
**直接变更文件：**
- 预计优先涉及 `gui/modes/navigation/map/session.py`
- 可能涉及 `gui/modes/navigation_mode.py`
- 可能涉及 `gui/dialogs/color_picker_dialog.py`
- 对应中文文档
**预计连带影响：**
- `NavigationCore` 应从 `core.localization` 或 `core.localization.navigation_core` 新路径导入。
- `MotionController` 应从 `core.input` 系统下的新路径导入。
- `RouteManager` 应从 `core.routing` 系统下的新路径导入。
- `HSVRecognizer` 应从 `core.vision` 系统下的新路径导入。

**本轮想弄清楚：**
- 新 core 包是否已经稳定导出这些类，避免直接猜路径。
- 哪些 GUI import 是旧顶层 facade，哪些本来就是系统包路径（如 `core.events.*`、`core.navigation_tasks.*`）。
- 先做低风险 import-only 迁移，不改调用行为、不删旧壳。

## [GUI-STAGE-AB-MOTION-CONTROLLER-INPUT-ENTRYPOINT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI→core 新系统包迁移，处理剩余 `gui/modes/navigation_mode.py` 对旧 `core.motion_controller.MotionController` 的依赖。目标是在 `core.input` 下建立正式类入口，同时保留旧 `core.motion_controller` 兼容壳，不删除旧路径。
**直接变更文件：**
- `core/input/controller.py`（新增正式输入控制类入口）
- `core/input/__init__.py`（导出 `MotionController`）
- `core/motion_controller.py`（降级为旧兼容壳）
- `gui/modes/navigation_mode.py`（迁移 import）
- 对应中文文档
**预计连带影响：**
- GUI 导航模式从 `core.input` 获取输入控制系统类，不再依赖旧顶层 motion facade。
- 旧调用方仍可通过 `core.motion_controller import MotionController` 使用同一实现。
- `core.input.motion_controller.*` helper 包继续作为类方法的实现层，不改变点击映射、底部防误点、输入 backend 行为。
**本轮想弄清楚：**
- `MotionController` 迁入 `core.input` 后是否会引入循环导入。
- 旧壳是否能保持 import smoke 兼容。
- GUI 中旧 `core.navigation_core/route_manager/recognizer_optimized/motion_controller` facade import 是否可清零。

### C. SYNC 结果

关键发现：
- (verified) `gui/modes/navigation/map/session.py` 可直接从 `core.localization` 导入 `NavigationCore`；该包已稳定导出同一 class identity，旧 `core.navigation_core` 继续作为 wrapper。
- (verified) `gui/modes/navigation_mode.py` 的 `RouteManager` 可直接从 `core.routing` 导入；`gui/dialogs/color_picker_dialog.py` 的 `HSVRecognizer` 可直接从 `core.vision` 导入。
- (verified) `MotionController` 原先没有 `core.input` 包级 class 入口，直接从旧 wrapper 反向导出会增加循环导入风险；更稳妥做法是新增 `core/input/controller.py` 作为正式 state-owner class，旧 `core/motion_controller.py` 降级为兼容 re-export。
- (verified) GUI 中旧 `core.navigation_core`、`core.motion_controller`、`core.route_manager`、`core.recognizer_optimized` facade import 扫描结果为 0；旧 wrapper 仍可 import 并返回同一 `MotionController` class。

代码变更：
- `gui/modes/navigation/map/session.py`：`NavigationCore` 改从 `core.localization` 导入。
- `gui/modes/navigation_mode.py`：`RouteManager` 已从 `core.routing` 导入，`MotionController` 改从 `core.input` 导入。
- `gui/dialogs/color_picker_dialog.py`：`HSVRecognizer` 改从 `core.vision` 导入。
- 新增 `core/input/controller.py`：承接 `MotionController` 正式类入口和输入控制状态。
- 修改 `core/input/__init__.py`：导出 `MotionController`。
- 修改 `core/motion_controller.py`：保留旧路径 wrapper，re-export `core.input.MotionController`。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\input\controller.py core\input\__init__.py core\motion_controller.py gui\modes\navigation_mode.py` 通过。
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\map\session.py gui\dialogs\color_picker_dialog.py` 通过（同轮低风险 import-only 迁移）。
- 全 GUI `py_compile` 通过。
- import smoke：`from core.input import MotionController`、`from core.motion_controller import MotionController as LegacyMotionController`、`from gui.modes.navigation_mode import MotionController as GuiMotionController` 三者 class identity 一致。
- `rg -n "from core\.(navigation_core|motion_controller|route_manager|recognizer_optimized)|import core\.(navigation_core|motion_controller|route_manager|recognizer_optimized)" gui -g "*.py"` 无结果。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/input/controller.py` | 新增 | 深度完整 | 1 | `MotionController` 正式状态拥有者；方法体沿用旧实现并继续委托 `core.input.motion_controller` helper 包。 |
| `core/input/__init__.py` | 已同步 input helper 导出 | 已同步 `MotionController` 包级入口 | 追加 | 新代码可 `from core.input import MotionController`，不需要依赖旧顶层 wrapper。 |
| `core/motion_controller.py` | 深度完整 facade/state owner | 兼容 wrapper | 追加 | 旧路径仍可用并返回同一 class identity；真实实现迁到 `core/input/controller.py`。 |
| `gui/modes/navigation_mode.py` | 已同步 event observation seam | 已同步 core 新包 import | 追加 | `RouteManager`/`MotionController` 使用 `core.routing`/`core.input`，runtime 行为不变。 |
| `gui/modes/navigation/map/session.py` | 已同步 map session seam | 已同步 `core.localization` import | 追加 | 创建 `NavigationCore` 的 helper 不再依赖旧 `core.navigation_core` wrapper。 |
| `gui/dialogs/color_picker_dialog.py` | 已同步 color picker preview seam | 已同步 `core.vision` import | 追加 | `HSVRecognizer` 不再依赖旧 `core.recognizer_optimized` wrapper。 |

下一轮计划：
- 继续阶段 G：审计 `gui/app_context.py` 这类组合根是否仍通过 `core.__init__` 聚合入口拿服务对象；如果可低风险迁移，则改为明确系统包入口。旧 core wrapper 删除仍延后。

## [GUI-STAGE-AC-APP-CONTEXT-CORE-ENTRYPOINT-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续阶段 G：审计 GUI 组合根 `gui/app_context.py` 是否仍通过 `core.__init__` 聚合入口获取服务对象，并在低风险前提下迁移到明确 core 系统包入口。
**直接变更文件：**
- 预计 `gui/app_context.py`
- 可能只同步中文文档：`CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
**预计连带影响：**
- `ScreenCapture` 应从 `core.platform` 导入。
- `HSVRecognizer`、`PlayerTracker` 应从 `core.vision` 导入。
- `MapStitcher` 应从 `core.mapping` 导入。
- `PathFinder` 应从 `core.routing` 导入。
- `core.__init__` 聚合入口继续保留给旧调用方，本轮不删除。
**本轮想弄清楚：**
- 新系统包是否已稳定导出 `ScreenCapture/HSVRecognizer/MapStitcher/PlayerTracker/PathFinder`。
- GUI 中是否还有 `from core import ...` 或旧 top-level facade import。
- 迁移是否为 import-only，不改变 AppContext 初始化顺序和共享对象身份。

### C. SYNC 结果

关键发现：
- (verified) `core.platform`、`core.vision`、`core.mapping`、`core.routing` 均已稳定导出 `ScreenCapture`、`HSVRecognizer`、`PlayerTracker`、`MapStitcher`、`PathFinder`。
- (verified) `gui/app_context.py` 是 GUI 里最后一个 `from core import ...` 聚合入口调用点；迁移后 GUI 对 `core.__init__` 聚合入口不再有直接依赖。
- (verified) 本轮为 import-only 迁移，`AppContext.__init__()` 创建共享服务对象的顺序和字段名保持不变。

代码变更：
- 修改 `gui/app_context.py`：从 `core.mapping`、`core.platform`、`core.routing`、`core.vision` 明确导入共享服务对象。
- 删除 `gui/app_context.py` 中未使用的 `sys/os` import。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\app_context.py` 通过。
- 全 GUI `py_compile` 通过。
- import smoke：`ScreenCapture/HSVRecognizer/MapStitcher/PlayerTracker/PathFinder` 均可从新系统包导入，`gui.app_context.AppContext` 可导入。
- `rg -n "from core import|import core$|from core\.(capture|stitcher_core|recognizer_optimized|tracker|pathfinder|navigation_core|motion_controller|route_manager|input_driver)|import core\.(capture|stitcher_core|recognizer_optimized|tracker|pathfinder|navigation_core|motion_controller|route_manager|input_driver)" gui -g "*.py"` 无结果。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/app_context.py` | 深度完整 | 已同步 core system package imports | 追加 | 共享服务对象创建顺序不变；不再依赖 `core.__init__` 聚合入口。 |
| `core/__init__.py` | 深度完整 | 旧聚合入口保留 | 追加 | GUI 已迁出，但旧脚本/测试兼容仍保留，不删除。 |
| `CODEBASE.md` | 已同步 MotionController 新入口 | 已同步 AppContext 组合根新导入 | 追加 | 增加 `gui/app_context.py` 模块详解，说明明确 core 系统包依赖。 |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | 已同步阶段 G 起步 | 已同步阶段 G AppContext import 迁移 | 追加 | 验证策略加入 `from core import ...` 扫描为 0。 |

下一轮计划：
- 继续 GUI 优化主线：在 GUI 旧 core facade import 已清零后，回到 GUI 内部结构化。优先候选是 `NavigationModeWidget._navigation_loop_unified()` 的终态 intent handling seam，或 `MappingWidget` 的 save/load UI 编排；旧 core wrapper 删除仍延后到脚本迁移审计之后。

## [GUI-STAGE-AD-NAV-TERMINAL-INTENT-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 回到 GUI 内部结构化主线，继续围绕 `NavigationModeWidget._navigation_loop_unified()` 做小步拆分。目标审计 ARRIVED/FAILED 终态 intent handling：controller 停止、游戏输入窗口恢复、按钮状态复位和状态栏展示是否可抽成 helper，同时保留未来 hook/总线边界但不实现 hook。
**直接变更文件：**
- 预计 `gui/modes/navigation_mode.py`
- 可能新增或扩展 `gui/modes/navigation/runtime/terminal_intent.py` 或 `runtime/loop.py`
- `gui/modes/navigation/runtime/__init__.py`
- 对应中文文档
**预计连带影响：**
- `NavigationTaskController.stop()`、`GameInputWindowMode.set_enabled(False)`、`start_button.setChecked(False)`、`start_button.setText("开始导航")` 调用顺序必须保持。
- `show_navigation_arrived()`、`show_navigation_failed()` 仍由 presentation helper 展示文案。
- `_execute_navigation_intent()` 的 MOVE_MAP/CLICK_SCREEN/PRESS_KEY 行为不动。
**本轮想弄清楚：**
- 终态处理是否只依赖 widget 上少量对象，可否通过参数/callback 传入而不让 runtime helper 反向依赖 QWidget。
- ARRIVED 与 FAILED 的差异是否只是状态文案和 failed message。
- 抽出后 `_navigation_loop_unified()` 是否更像“定位 -> 事件观测 -> task update -> intent 消费/终态处理”的流程骨架。

### C. SYNC 结果

关键发现：
- (verified) `_navigation_loop_unified()` 的 ARRIVED 和 FAILED 分支共享同一组运行态收束副作用：停止 `NavigationTaskController`、关闭游戏输入窗口模式、复位自动导航按钮；差异只在终态文案。
- (verified) 终态收束不应该直接放进 presentation，因为它包含 controller/window/button 副作用；也不需要让 helper 依赖 QWidget，通过回调注入即可。
- (verified) 终态收束不停止 `nav_timer`，保持旧行为：自动导航到达/失败后定位循环仍可继续刷新当前位置。

代码变更：
- 新增 `gui/modes/navigation/runtime/terminal_intent.py`：`handle_terminal_navigation_intent()` 处理 ARRIVED/FAILED 并返回是否已处理终态。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 terminal helper。
- 修改 `gui/modes/navigation_mode.py`：`_navigation_loop_unified()` 用 terminal helper 替代重复 ARRIVED/FAILED 分支，并清理未使用 `NavigationIntentType` import。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\terminal_intent.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：验证 ARRIVED 回调顺序为 stop -> disable input -> reset button -> arrived；FAILED 回调顺序为 stop -> disable input -> reset button -> failed(message)；WAIT 返回 False 且不调用回调。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/terminal_intent.py` | 新增 | 深度完整 | 1 | 终态 intent 收束 helper；通过回调保持副作用顺序，不依赖 QWidget。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 event observation helper 导出 | 已同步 terminal intent helper 导出 | 追加 | runtime 包入口导出 ARRIVED/FAILED 收束 helper。 |
| `gui/modes/navigation_mode.py` | 已同步 core 新包 import | 已同步 terminal intent seam | 追加 | `_navigation_loop_unified()` 保留流程骨架，只把 ARRIVED/FAILED 重复收束分支委托给 runtime helper。 |

下一轮计划：
- 继续 GUI 内部结构化。可选路径一：继续瘦 `_navigation_loop_unified()`，抽 capture/localization tick skeleton；可选路径二：转向 `MappingWidget` 的 save/load UI 编排或 layout 组成。按当前风险，建议先扫描 MappingWidget 的剩余长函数，再决定是否拆 save/load seam。

## [GUI-STAGE-AE-MAPPING-SAVE-LOAD-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 GUI 内部结构化。在 Navigation runtime 已继续拆出终态 intent seam 后，扫描 MappingWidget 剩余职责，优先审计 save/load/UI 编排是否还把配置 IO、参数同步、控件状态和用户提示混在主 widget 内。目标是按功能 package 小步抽取，不做扁平 helper。
**直接变更文件：**
- 预计 `gui/modes/mapping_widget.py`
- 可能新增或扩展 `gui/modes/mapping/io/`、`gui/modes/mapping/presentation/`、`gui/modes/mapping/runtime/`
- 对应中文文档
**预计连带影响：**
- `MappingWidget` 仍保留 public class 和旧 slot 名称。
- 建图 tick、capture selection、display presenter、params binding 已存在，本轮不触碰其行为。
- 若拆 save/load，只迁出纯 IO/presentation 编排，不改变 `map_data/<name>/config.json` 和根 `config.json` 结构。
**本轮想弄清楚：**
- `MappingWidget` 里剩余最长函数是否确实是 save/load/advanced settings/layout，而不是已完成的 runtime tick。
- 哪些函数能用现有 `mapping/io/config_store.py` 和 `mapping/params/binding.py` 继续收束。
- 是否存在旧 core facade import 或旧 helper wrapper import 可顺手迁移，但不删除 wrapper。

### C. SYNC 结果

关键发现：
- (verified) `MappingWidget.load_saved_params()` 已经是剩余 mapping 职责里较高耦合的一段：读取根配置、写 AppContext、恢复 capture selection、应用 recognizer/stitcher 参数、同步 Qt 控件和阻断几何控件信号都在一个方法内。
- (verified) 这些职责适合放在 `mapping/io/` 下的 config restore seam，而不是继续留在 widget；但它不是纯文件 IO，因为会写 runtime services 和 Qt 控件，所以文档中明确为“配置恢复编排”。
- (verified) `MappingWidget` 仍保留 `load_saved_params()` 入口和原 `json.JSONDecodeError/KeyError` 错误提示；配置字段结构和保存路径不变。

代码变更：
- 新增 `gui/modes/mapping/io/config_restore.py`：`MappingConfigRestoreTargets` 与 `restore_saved_mapping_config()`。
- 修改 `gui/modes/mapping/io/__init__.py`：导出 config restore helper。
- 修改 `gui/modes/mapping_widget.py`：`load_saved_params()` 委托 restore helper；清理不再使用的 `QSignalBlocker` 和旧 params sync imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\io\__init__.py gui\modes\mapping\io\config_restore.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：使用 offscreen QApplication 和真实 Qt spin/checkbox 控件验证 config restore 会回填 AppContext、恢复 capture selection、同步 FPS/draw_scale/feature 控件、应用 recognizer/stitcher 参数，并在空 stitcher 时调用 reinitialize_canvas。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/io/config_restore.py` | 新增 | 深度完整 | 1 | 启动配置恢复编排 seam；读取根配置后应用到 runtime services、capture selection 和 Qt 控件。 |
| `gui/modes/mapping/io/__init__.py` | 已同步 config store 导出 | 已同步 config restore 导出 | 追加 | mapping IO 包入口导出 `MappingConfigRestoreTargets` 和 `restore_saved_mapping_config()`。 |
| `gui/modes/mapping_widget.py` | 已同步 AppContext core import 迁移影响 | 已同步 config restore seam | 追加 | `load_saved_params()` 保留旧入口和错误提示，内部委托 helper；mapping tick/display/capture/params 既有 seam 不变。 |

下一轮计划：
- Mapping 结构化已覆盖 runtime、capture、presentation、IO store、config restore、params binding。下一步更有价值的是：
  1. 小步优化 `MappingWidget.save_map()` 的保存地图弹窗/成功提示与 map package/config 写入编排；或
  2. 继续导航 loop 的 capture/localization skeleton；或
  3. 开始更细的 dialog layout 拆分（风险较高，收益偏可读性）。
- 按当前准则，建议下一轮优先拆 `MappingWidget.save_map()`，因为它小、边界清晰、可验证，并能继续完成 Mapping mode 的 save/load 收口。

## [GUI-STAGE-AF-MAPPING-SAVE-MAP-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 继续 Mapping mode 收口，审计 `MappingWidget.save_map()` 中保存地图包和地图级配置的 IO 编排。目标是把非 UI 的保存动作迁到 `mapping/io/` 功能包，保留用户输入弹窗和成功提示在 widget 层。
**直接变更文件：**
- 预计新增 `gui/modes/mapping/io/map_save.py`
- `gui/modes/mapping/io/__init__.py`
- `gui/modes/mapping_widget.py`
- 对应中文文档
**预计连带影响：**
- `QInputDialog.getText()` 和 `QMessageBox.information()` 仍留在 `MappingWidget.save_map()`，不改变用户交互文案。
- `ensure_map_folder()`、`stitcher.save_map_package()`、`save_map_config()` 的调用顺序必须保持。
- `map_data/<map_name>/map_data.npz` 和 `map_data/<map_name>/config.json` 输出结构不变。
**本轮想弄清楚：**
- 是否可用一个窄 helper 表达“保存 map package + map config”，避免 widget 直接知道 map folder 创建和 config 文件写入细节。
- helper 是否可以通过 fake stitcher smoke 验证顺序和输出路径。
- 是否需要迁移成功/失败 QMessageBox；本轮不迁，避免 UI 文案和错误行为混入 IO 改动。

### C. SYNC 结果

关键发现：
- (verified) `MappingWidget.save_map()` 的非 UI 部分只有三步：确保地图目录、保存 `map_data.npz`、写地图级 `config.json`；用户输入和成功提示属于 widget/presentation，暂不迁入 IO helper。
- (verified) 保存顺序必须保持：先 `ensure_map_folder()`，再 `stitcher.save_map_package(str(map_folder))`，最后 `save_map_config()`。
- (verified) helper 可用 fake stitcher smoke 验证输出目录、`map_data.npz` 保存路径和 `config.json` 内容。

代码变更：
- 新增 `gui/modes/mapping/io/map_save.py`：`save_mapping_map()`。
- 修改 `gui/modes/mapping/io/__init__.py`：导出 `save_mapping_map()`。
- 修改 `gui/modes/mapping_widget.py`：`save_map()` 委托 map save helper；保留 `QInputDialog` 和 `QMessageBox` 原位置与文案。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\io\__init__.py gui\modes\mapping\io\map_save.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -` smoke：fake stitcher 写入 `map_data.npz`，验证 `save_mapping_map()` 返回 `map_data/<map>`，调用 stitcher 的路径为同一目录，并写入地图级 `config.json`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/io/map_save.py` | 新增 | 深度完整 | 1 | 保存地图包与地图级 config 的 IO 编排 helper；不接管输入框或成功提示。 |
| `gui/modes/mapping/io/__init__.py` | 已同步 config restore 导出 | 已同步 map save 导出 | 追加 | mapping IO 包入口导出 `save_mapping_map()`。 |
| `gui/modes/mapping_widget.py` | 已同步 config restore seam | 已同步 map save seam | 追加 | `save_map()` 保留用户交互，非 UI 保存动作委托 helper。 |

下一轮计划：
- Mapping mode 的 runtime/capture/presentation/io/params 主 seam 已基本覆盖。下一步可转回 Navigation runtime loop，优先审计 `_navigation_loop_unified()` 的 capture/localization 输入段，或开始 Dialog layout 拆分。按风险收益，建议下一轮回到 Navigation loop，因为它仍是 GUI 中最核心的长流程。

## [GUI-STAGE-AG-NAV-CAPTURE-LOCALIZATION-TICK-SEAM-AUDIT] 2026-05-27

### A. SYNC 范围声明
**触发任务：** 按当前主线继续优化 `NavigationModeWidget._navigation_loop_unified()`，本轮聚焦 capture/localization 输入段：构造截图几何、抓屏、解析玩家局部坐标、调用 `NavigationCore.localize()` 并生成 `NavigationLocalizationResult`。目标是抽成 runtime helper，让主循环保留“capture/localize -> observe events -> task update -> presentation -> intent handling”骨架。
**直接变更文件：**
- 预计新增 `gui/modes/navigation/runtime/localization_tick.py`
- `gui/modes/navigation/runtime/__init__.py`
- `gui/modes/navigation_mode.py`
- 对应中文文档
**预计连带影响：**
- `_build_capture_geometry()`、`screen_capture.capture()`、`resolve_player_local_position()`、`nav_core.localize()` 的顺序必须保持。
- `self._current_capture_rect` 和 `self._current_player_local_pos` 写回仍由 widget 明确接收，避免 runtime helper 反向修改 widget。
- 事件观测、task update、presentation 和 intent 执行不改行为。
**本轮想弄清楚：**
- capture/localization 段能否用一个 DTO 返回 `capture_rect/default_player_pos/frame/player_pos/localization`。
- helper 是否需要知道 QWidget；预期不需要，只接收 callbacks 和 runtime services。
- 抽出后 `_navigation_loop_unified()` 是否进一步缩短且更接近总线/hook 未来边界。

## [SYNC] 2026-05-27 23:10 - GUI-STAGE-AG-NAV-CAPTURE-LOCALIZATION-TICK-SEAM-AUDIT
### A. SYNC 范围声明
**触发任务：** 补齐导航运行时定位帧抽取 `localization_tick.py` 的中文文档同步，并继续评估 `_navigation_loop_unified()` 后续可抽取 seam。
**直接变更文件：** `gui/modes/navigation/runtime/localization_tick.py`、`gui/modes/navigation/runtime/__init__.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
**预计连带影响：** 导航模式主循环的截图、玩家局部坐标解析、核心定位调用 Flow；运行时包导出；GUI 拆分计划中 Stage D 进度。

### C. SYNC 结果

关键发现：
- (verified) `capture_navigation_localization_tick()` 已接管 `_navigation_loop_unified()` 的第一段：校验导航配置、构造截图几何、抓屏、解析玩家局部坐标、调用 `NavigationCore.localize()` 并包装为 `NavigationLocalizationResult`。
- (verified) helper 只通过 callback/service 参数工作，不依赖 QWidget，也不反向写 widget 状态；`_current_capture_rect` 与 `_current_player_local_pos` 仍由 `NavigationModeWidget` 在主循环中显式赋值。
- (verified) 本轮没有实现 hook/event bus，只把未来可挂接的 capture/localize 边界命名为 runtime tick seam。

代码变更：
- 新增 `gui/modes/navigation/runtime/localization_tick.py`：定义 `NavigationFrameTick` 和 `capture_navigation_localization_tick()`。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出定位 tick DTO/helper。
- 修改 `gui/modes/navigation_mode.py`：主循环起始段委托定位 tick helper，事件观测、task update、presentation、intent 执行顺序不变。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\localization_tick.py` 通过。
- `python -` smoke：使用 fake capture/nav_core/tracker 验证 `capture_navigation_localization_tick()` 的调用顺序与返回字段。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/localization_tick.py` | 新增 | 深度完整 | 1 | 单帧 capture/localize runtime seam；返回 DTO，不写 QWidget 状态。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 terminal intent 导出 | 已同步 localization tick 导出 | 追加 | runtime 包入口导出 `NavigationFrameTick` 和 `capture_navigation_localization_tick()`。 |
| `gui/modes/navigation_mode.py` | 已同步 terminal intent seam | 已同步 localization tick seam | 追加 | `_navigation_loop_unified()` 的 capture/localize 起始段已委托 helper，后续事件、任务、展示、intent 顺序保持。 |

下一轮计划：
- 继续围绕 `_navigation_loop_unified()` 小步拆分。优先候选是 force relocalize 分支：读取 intent metadata、调用 `request_global_relocalization()`、写事件日志、展示重新定位状态并提前返回。

## [SYNC] 2026-05-27 23:17 - GUI-STAGE-AH-NAV-RELOCALIZATION-INTENT-SEAM-AUDIT
### A. SYNC 范围声明
**触发任务：** 继续拆分 `NavigationModeWidget._navigation_loop_unified()`，本轮聚焦 `intent.metadata.force_relocalize` 分支：请求全局重定位、写事件日志、展示重新定位状态并提前结束本帧 intent 执行。
**直接变更文件：** `gui/modes/navigation/runtime/relocalization_intent.py`、`gui/modes/navigation/runtime/__init__.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
**预计连带影响：** 导航任务控制器返回 recovery intent 后的输入消费边界；`NavigationCore.request_global_relocalization()` 调用点；事件日志 `navigation forced global relocalization`；状态栏重新定位文案。

### C. SYNC 结果

关键发现：
- (verified) `_navigation_loop_unified()` 的 force-relocalize 分支只有四类职责：读取 intent metadata、请求 `NavigationCore.request_global_relocalization(reason)`、写 `navigation forced global relocalization` 事件日志、展示“正在重新定位”状态并提前返回。
- (verified) 该分支是恢复意图消费边界，不应执行 `_execute_navigation_intent()`；抽成 helper 后通过 bool 返回值保留旧的本帧提前 return 语义。
- (verified) helper 通过回调接收 `request_global_relocalization`、`event_log` 和状态展示函数，不 import QWidget，也不实现 hook/event bus。

代码变更：
- 新增 `gui/modes/navigation/runtime/relocalization_intent.py`：定义 `handle_relocalization_navigation_intent()`。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 relocalization intent helper。
- 修改 `gui/modes/navigation_mode.py`：force-relocalize 分支委托 runtime helper；route overlay、输入执行、terminal intent 顺序不变。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\relocalization_intent.py` 通过。
- `python -` smoke：构造 fake intent，验证默认 reason 为 `coordinate_recovery`、日志字段包含 score/player/task、状态展示回调被调用；无 `force_relocalize` 时返回 `False` 且不触发回调。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/relocalization_intent.py` | 新增 | 深度完整 | 1 | force-relocalize intent 消费 seam；通过回调请求全局重定位、写日志和展示状态，返回 bool 控制本帧提前结束。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 localization tick 导出 | 已同步 relocalization intent 导出 | 追加 | runtime 包入口导出 `handle_relocalization_navigation_intent()`。 |
| `gui/modes/navigation_mode.py` | 已同步 localization tick seam | 已同步 relocalization intent seam | 追加 | `_navigation_loop_unified()` 不再内联 force-relocalize 细节，只保留 helper 返回真时提前 return。 |

下一轮计划：
- 继续 GUI 主线。优先审计 `_navigation_loop_unified()` 剩余 intent 后处理：`_execute_navigation_intent()`、手动传送门测试 terminal metadata 和 ARRIVED/FAILED helper 的相邻关系，判断是否适合抽成一个更高层的 intent-consumption helper；避免一次搬完整 loop。

## [SYNC] 2026-05-27 23:44 - GUI-STAGE-AI-NAV-INTENT-CONSUMPTION-SEAM-AUDIT
### A. SYNC 范围声明
**触发任务：** 继续拆分 `NavigationModeWidget._navigation_loop_unified()` 剩余 intent 后处理，审计 `_execute_navigation_intent()`、手动传送门测试 terminal metadata、force-relocalize helper 和 ARRIVED/FAILED terminal helper 是否能组合成一个更清晰的 intent consumption seam。
**直接变更文件：** 预计 `gui/modes/navigation/runtime/intent_consumption.py`、`gui/modes/navigation/runtime/__init__.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`
**预计连带影响：** `_navigation_loop_unified()` 中 route overlay 后的 intent 消费顺序；force relocalize 的提前返回；真实输入执行；手动传送门测试停止；自动导航终态关闭。

### C. SYNC 结果

关键发现：
- (verified) `_navigation_loop_unified()` 剩余 intent 后处理本质是一个固定消费顺序：force-relocalize 先短路；否则执行真实输入；再处理手动传送门测试 terminal metadata；最后处理 ARRIVED/FAILED 终态。
- (verified) 这个顺序适合抽成 runtime 编排 helper，但不应接管 route overlay 或真实输入细节；route overlay 仍在 widget 中先刷新，真实输入仍由 `_execute_navigation_intent()` / `navigation/input/intent_executor.py` 执行。
- (verified) helper 返回 DTO，让 widget 只根据 `skip_remaining_frame` 和 `terminal_navigation` 决定本帧 return 与关闭 `auto_navigation_enabled`。

代码变更：
- 新增 `gui/modes/navigation/runtime/intent_consumption.py`：定义 `NavigationIntentConsumptionResult` 和 `consume_navigation_intent()`。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 intent consumption DTO/helper。
- 修改 `gui/modes/navigation_mode.py`：route overlay 后委托 `consume_navigation_intent()`；主循环不再内联重定位、输入执行、手动事件测试停止和终态收束的相邻流程。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\intent_consumption.py gui\modes\navigation\runtime\relocalization_intent.py gui\modes\navigation\runtime\terminal_intent.py` 通过。
- `python -` smoke：force-relocalize intent 验证只触发 request/log/show，返回 `skip_remaining_frame=True`，不执行输入或终态。
- `python -` smoke：ARRIVED terminal intent 验证执行顺序为 execute -> manual-stop -> stop-nav -> disable-input -> reset-button -> arrived，并返回 `terminal_navigation=True`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/intent_consumption.py` | 新增 | 深度完整 | 1 | intent 消费编排 seam；串联重定位短路、输入执行、手动事件测试 terminal 停止和 ARRIVED/FAILED 终态处理。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 relocalization intent 导出 | 已同步 intent consumption 导出 | 追加 | runtime 包入口导出 `NavigationIntentConsumptionResult` 和 `consume_navigation_intent()`。 |
| `gui/modes/navigation_mode.py` | 已同步 relocalization intent seam | 已同步 intent consumption seam | 追加 | `_navigation_loop_unified()` route overlay 后只消费 helper result，真实输入和状态回调仍通过注入保持旧顺序。 |

下一轮计划：
- `_navigation_loop_unified()` 已接近“capture/localize -> observe events -> update task -> presentation -> consume intent”的骨架。继续推进时优先审计 navigation map loading/config save 或 dialog layout 热点；不建议为了继续缩短主循环而强行搬完整 loop。

## [SYNC] 2026-05-27 23:51 - GUI-STAGE-AJ-NAV-MAP-CONFIG-SEAM-AUDIT
### A. SYNC 范围声明
**触发任务：** 在 runtime loop 已接近骨架后，转向 `NavigationModeWidget` 剩余热点，审计 `load_map()`、`_save_nav_config()`、`_save_nav_default_config()`、overlay/config 刷新周边是否可按 `navigation/map/` 或 `navigation/presentation/` 功能包继续拆分。
**直接变更文件：** 预计 `gui/modes/navigation_mode.py`、可能新增或扩展 `gui/modes/navigation/map/` 或 `gui/modes/navigation/presentation/`，以及中文文档。
**预计连带影响：** 地图加载顺序、NavConfig 应用、参数弹窗回填、route/event 初始化、debug overlay/视野框刷新和保存反馈；必须保留 `NavigationModeWidget.load_map()` 等旧入口。

### C. SYNC 结果

关键发现：
- (verified) `load_map()` 前半段的 map folder 解析、NavConfig 读取、`NavigationCore` 创建和初始物理中心计算属于稳定 map session seam；这些步骤不需要知道 QWidget，也不负责弹窗、渲染或事件初始化。
- (verified) 缺 config warning、配置应用、参数弹窗回填、route/event 初始化、地图渲染、last position marker 和按钮启用顺序仍留在 `NavigationModeWidget.load_map()`，避免改变用户可见行为。
- (verified) `NavigationMapLoadSession` 让 `load_map()` 不再直接 import/调用 `resolve_map_folder()`、`load_navigation_map_settings()`、`create_navigation_core()` 和 `initial_capture_center_for_config()`。

代码变更：
- 扩展 `gui/modes/navigation/map/session.py`：新增 `NavigationMapLoadSession` 和 `prepare_navigation_map_load_session()`。
- 修改 `gui/modes/navigation/map/__init__.py`：导出新的 session DTO/helper。
- 修改 `gui/modes/navigation_mode.py`：`load_map()` 委托 map load session 准备，并清理不再直接使用的 map helper imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\session.py` 通过。
- `python -` smoke：构造临时 `map_data/A/map_data.npz` 和 `config.json`，验证 `prepare_navigation_map_load_session()` 返回 map folder、`config_exists=True`、`NavigationCore`、`capture_center_physical=(20, 60)` 和 `physical_center=(20, 60)`。
- 全 GUI `py_compile` 通过。
- `python -` smoke：从 `gui.modes.navigation.map` 导入 `NavigationMapLoadSession` 和 `prepare_navigation_map_load_session()` 通过。
- GUI 旧 core facade import 扫描无匹配；`navigation_mode.py` 也不再直接引用 `resolve_map_folder()`、`load_navigation_map_settings()`、`create_navigation_core()`、`initial_capture_center_for_config()`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/session.py` | 已同步 core 新包 import | 已同步 map load session seam | 追加 | map session 现在覆盖 folder 解析、配置读取、core 创建和初始物理中心计算，但不应用配置或写 UI。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 map/session 导出 | 已同步 map load session 导出 | 追加 | navigation map 包入口导出 `NavigationMapLoadSession` 和 `prepare_navigation_map_load_session()`。 |
| `gui/modes/navigation_mode.py` | 已同步 intent consumption seam | 已同步 map load session seam | 追加 | `load_map()` 前半段委托 session helper，UI 副作用和后续加载顺序保持原位。 |

下一轮计划：
- 可继续围绕 `NavigationModeWidget` 的 map/config 周边审计 `_save_nav_config()` 和 overlay refresh 顺序，寻找是否能抽出“保存后应用并刷新视图”的小 seam；如果收益不够，转向 dialogs 热点（`advanced_settings_dialog.py` / `nav_params_dialog.py`）会更有价值。

## [SYNC] 2026-05-28 10:41 - GUI-STAGE-AK-NAV-CONFIG-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 按 `ARCHITECTURE_OPTIMIZATION_RULES.md` 提高拆分力度，不再只抽小 helper。本轮聚焦 `NavigationModeWidget` 的导航配置生命周期：参数变化、runtime config apply、当前地图配置保存、默认配置保存、dirty 状态、overlay/视野框刷新和保存反馈。
**直接变更文件：** 预计新增 `gui/modes/navigation/map/config_lifecycle.py`，修改 `gui/modes/navigation/map/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `NavigationModeWidget._on_parameter_changed()`、`_apply_config_to_core()`、`_configure_navigation_task_controller()`、`_save_nav_config()`、`_save_nav_default_config()`；必须保留这些旧方法作为 wrapper，且不改变保存、应用、刷新和提示顺序。

### C. SYNC 结果

关键发现：
- (verified) 按 `ARCHITECTURE_OPTIMIZATION_RULES.md` 判断，本轮不应再抽浅 helper；导航配置生命周期是一个深模块候选，因为参数变化、runtime 应用、保存、dirty 状态、overlay/视野框刷新和反馈顺序原本散在 widget 多个方法中。
- (verified) 原 A 段预期放到 `navigation/map/config_lifecycle.py`，阅读后修正为 `navigation/config/lifecycle.py`：配置生命周期不是纯 map IO，也不是纯 presentation，而是 GUI navigation config module。
- (verified) 顺手修正初始化顺序问题：`RoutePanelController` 在 `init_ui()` 内依赖 `self.route_editor`，现在 `RouteManager/RouteEditor/NavigationTaskController` 会在 `init_ui()` 前创建。

代码变更：
- 新增 `gui/modes/navigation/config/__init__.py`。
- 新增 `gui/modes/navigation/config/lifecycle.py`：`NavigationConfigLifecycleTargets` 和 `NavigationConfigLifecycle`。
- 修改 `gui/modes/navigation_mode.py`：初始化 `config_lifecycle`；`_on_parameter_changed()`、`_apply_config_to_core()`、`_configure_navigation_task_controller()`、`_save_nav_config()`、`_save_nav_default_config()` 变为 wrapper；清理直接 config apply/save/presentation imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\config\__init__.py gui\modes\navigation\config\lifecycle.py` 通过。
- `python -` smoke：monkeypatch lifecycle 依赖，验证 `handle_parameter_changed()` 顺序为 reset capture -> overlay -> apply motion -> configure task -> game view -> dirty；`save_current_map_config()` 顺序为 save map -> apply runtime -> overlay -> game view -> show saved；`save_default_config()` 顺序为 save default -> show default。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/config/lifecycle.py` | 新增 | 深度完整 | 1 | 导航配置生命周期 facade；集中参数变化、应用、保存、刷新和反馈顺序，通过 targets DTO 接入 widget/runtime。 |
| `gui/modes/navigation/config/__init__.py` | 新增 | 深度完整 | 1 | navigation config 包入口，导出 lifecycle facade 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 map load session seam | 已同步 config lifecycle 深模块 | 追加 | 配置相关旧方法保留 wrapper；初始化顺序调整为先建 route/runtime 状态，再构建 UI。 |

下一轮计划：
- 继续按深模块规则拆分，不再只挪小分支。优先候选：`load_map()` 后半段（config warning、apply、params dialog、route/event init、render、last position、loaded UI）可抽成 map loading pipeline；或转向 `advanced_settings_dialog.py` / `nav_params_dialog.py` 的 dialog lifecycle。
## [SYNC] 2026-05-28 10:50 - GUI-STAGE-AL-NAV-MAP-LOAD-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 继续按 `ARCHITECTURE_OPTIMIZATION_RULES.md` 做 GUI 深模块拆分，本轮聚焦 `NavigationModeWidget.load_map()` 后半段：配置告警、运行时配置应用、参数弹窗同步、路线/事件初始化、地图渲染、最后位置标记、路线覆盖层和加载完成 UI 状态。
**直接变更文件：** 预计新增 `gui/modes/navigation/map/load_lifecycle.py`，修改 `gui/modes/navigation/map/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `NavigationModeWidget.load_map()` 保留旧入口和 UI 容器归属，但把“地图加载后半段的固定编排”下沉到 navigation map lifecycle 模块；需要保证原有调用顺序、错误提示、按钮启用、route overlay 初始化和事件计数刷新不变。
### C. SYNC 结果

关键发现：
- (verified) `load_map()` 后半段不是零散 UI helper，而是一个顺序敏感生命周期：写入 map session -> 缺配置提示 -> runtime config apply -> 参数弹窗回填 -> route 数据加载 -> event system 初始化 -> map scene 渲染 -> last position marker -> route/event overlay -> loaded UI。
- (verified) 这个生命周期适合放在 `navigation/map/`，因为它围绕“当前导航地图会话加载完成后如何使 runtime/UI 进入可用状态”；它不是纯 presentation，也不是 config 保存生命周期。
- (verified) `NavigationModeWidget.load_map()` 可保留旧入口，只读取 combo 文本并委托 lifecycle；新模块通过 targets DTO 接入 widget 回调，不直接 import `NavigationModeWidget` 类型。

代码变更：
- 新增 `gui/modes/navigation/map/load_lifecycle.py`：`NavigationMapLoadLifecycleTargets`、`NavigationMapLoadLifecycle`。
- 修改 `gui/modes/navigation/map/__init__.py`：导出 map load lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.map_load_lifecycle`；`load_map()` 委托 `load_selected_map()`；新增 `_set_loaded_map_session()` wrapper；清理不再直接使用的 map-load presentation/session imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- 全 GUI `py_compile` 通过。
- 旧 core facade import 扫描无命中。
- 目标编译通过：`navigation_mode.py`、`navigation/map/__init__.py`、`navigation/map/load_lifecycle.py`。
- `python -` smoke：验证 `apply_loaded_session()` 顺序为 set session -> apply -> params -> route -> event -> render map -> last pos -> route overlay -> enable start/hint/route panel/status；缺地图占位返回 `False`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/load_lifecycle.py` | 新增 | 深度完整 | 1 | map load lifecycle 深模块，集中准备 session 后的 runtime/UI 副作用顺序，失败统一走旧加载失败弹窗。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 map session 导出 | 已同步 map load lifecycle 导出 | 追加 | navigation map 包入口新增 lifecycle facade/targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 config lifecycle 深模块 | 已同步 map load lifecycle 深模块 | 追加 | `load_map()` 不再内联加载后半段；保留旧入口和 `_set_loaded_map_session()` wrapper。 |

下一轮计划：
- 继续按深模块准则审计 `NavigationModeWidget` 剩余系统级职责。优先候选是导航启动/暂停/自动导航生命周期，或事件配置/portal manual test 生命周期；只有当能隐藏一串状态转移和副作用顺序时才拆，不为了行数继续削小 helper。
## [SYNC] 2026-05-28 10:58 - GUI-STAGE-AM-NAV-RUNTIME-COMMAND-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 按深模块准则继续拆 `NavigationModeWidget`，本轮聚焦导航运行命令生命周期：`toggle_navigation()`、`stop_runtime()`、`toggle_auto_navigation()`、`_can_start_auto_navigation()`、`_set_game_input_window_mode()` 共享的 timer、motion、task controller、输入窗口模式、按钮状态和状态栏反馈。
**直接变更文件：** 预计新增 `gui/modes/navigation/runtime/command_lifecycle.py`，修改 `gui/modes/navigation/runtime/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `NavigationModeWidget.toggle_navigation()`、`stop_runtime()`、`toggle_auto_navigation()` 旧入口；运行命令状态机下沉到 runtime lifecycle。必须保持启动 guard、自动导航失败回滚、导航停止幂等、portal manual test 停止、route overlay 刷新和状态栏文案顺序。
### C. SYNC 结果

关键发现：
- (verified) `toggle_navigation()`、`stop_runtime()` 和 `toggle_auto_navigation()` 共享同一组运行态对象：`nav_timer`、`MotionController`、`NavigationTaskController`、`GameInputWindowMode`、开始/自动导航按钮、route overlay、status label 和 `auto_navigation_enabled`。
- (verified) 这组逻辑符合深模块条件：它隐藏启动 guard、失败回滚、timer/motion/task/input-window 顺序、手动事件测试停止和按钮状态恢复；删除该模块会让同一状态机重新散回 Widget。
- (verified) 传送门手动测试仍在 Widget 中独立使用 `start_event_log_session("portal_manual_test")`，因此本轮只迁导航/自动导航 command lifecycle，不顺手改 portal 手动测试。

代码变更：
- 新增 `gui/modes/navigation/runtime/command_lifecycle.py`：`NavigationRuntimeCommandLifecycleTargets`、`NavigationRuntimeCommandLifecycle`。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 runtime command lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.command_lifecycle`；`toggle_navigation()`、`stop_runtime()`、`toggle_auto_navigation()`、`_can_start_auto_navigation()`、`_set_game_input_window_mode()` 变为 wrapper；清理导航命令 presentation imports；恢复 `start_event_log_session` import 供 portal manual test 使用。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\runtime\__init__.py gui\modes\navigation\runtime\command_lifecycle.py` 通过。
- `python -` smoke：验证普通导航启动顺序为 use loop -> navigation log session -> apply config -> reset local pos -> request full localization -> tracker reset -> motion enable -> timer start -> started status；自动导航已运行 timer 分支顺序为 load route -> task start -> input window mode -> auto started；stop runtime 顺序以 timer stop、motion disable、task stop 开头并恢复按钮/状态栏。
- 全 GUI `py_compile` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/command_lifecycle.py` | 新增 | 深度完整 | 1 | runtime command 生命周期深模块，集中导航启动/停止、自动导航开关、timer/motion/task/input-window、按钮回滚和状态栏反馈。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 intent consumption 导出 | 已同步 command lifecycle 导出 | 追加 | runtime 包入口新增 `NavigationRuntimeCommandLifecycle` 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 map load lifecycle 深模块 | 已同步 runtime command lifecycle 深模块 | 追加 | 运行命令旧 slot/private 方法均保留 wrapper，Widget 不再内联导航/自动导航状态机。 |

下一轮计划：
- 继续审计 `NavigationModeWidget` 剩余深职责。优先候选：事件配置/portal manual test lifecycle（`_initialize_event_system()`、`_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`、`_set_portal_manual_test_active()`），或者地图点击 lifecycle（hint、route edit、manual move 三分支）。按准则判断后再拆，不为了行数强拆。
## [SYNC] 2026-05-28 11:06 - GUI-STAGE-AN-NAV-EVENT-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 继续按深模块准则拆 `NavigationModeWidget`，本轮聚焦导航事件生命周期：`_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`、`_set_portal_manual_test_active()`、`_reset_event_move_runtime()` 共享的 event coordinator/config、portal manual test controller、task controller movement reset、input-window 模式、event overlay/dialog 刷新和事件日志。
**直接变更文件：** 预计新增 `gui/modes/navigation/events/lifecycle.py`，修改 `gui/modes/navigation/events/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `_save_event_config()`、`_reset_portal_event_state()`、`_run_portal_manual_test()`、`_set_portal_manual_test_active()` 等旧入口 wrapper；事件生命周期下沉到 navigation/events 包。必须保持保存反馈、portal reset 停止手动测试、event move runtime reset、overlay/dialog refresh、导航 timer fallback 启动和 input-window 模式恢复顺序。
### C. SYNC 结果

关键发现：
- (verified) 事件配置保存、portal reset 和 portal 手动测试启停原本共享同一事件运行态：`event_config/event_coordinator`、`ManualEventTestController`、`NavigationTaskController.movement/event_approach`、input-window 模式、motion control、event overlay 和 event dialog task table。
- (verified) 这组逻辑适合放在 `navigation/events/`，不是 presentation，也不是通用 runtime command；它围绕事件系统生命周期和 portal 手动测试命令，能够隐藏多步状态转移。
- (verified) 手动 portal 测试仍复用正式事件 pipeline：启动 task controller 后，后续每帧仍由导航循环 observe/update/run task/consume intent，不引入 hook 或事件总线。

代码变更：
- 新增 `gui/modes/navigation/events/lifecycle.py`：`NavigationEventLifecycleTargets`、`NavigationEventLifecycle`。
- 修改 `gui/modes/navigation/events/__init__.py`：导出 event lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.event_lifecycle`；`_save_event_config()`、`_reset_portal_event_state()`、`_reset_event_move_runtime()`、`_run_portal_manual_test()`、`_set_portal_manual_test_active()` 变为 wrapper；新增 `_refresh_event_dialog_tasks()`；清理事件保存/portal presentation 和 save_event_config imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\events\__init__.py gui\modes\navigation\events\lifecycle.py` 通过。
- `python -` smoke：验证保存事件配置成功顺序为 save -> refresh dialog -> saved feedback；portal 手动测试启动顺序为 log session -> load route -> task start -> portal button start -> input window on -> motion on -> event log -> status；停止顺序为 portal stop -> movement reset -> approach reset -> input window off -> event log -> status；portal reset active 分支先停止手动测试，再 reset_event_type、重置 runtime、刷新 overlay/dialog、写日志和状态栏。
- 全 GUI `py_compile` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/events/lifecycle.py` | 新增 | 深度完整 | 1 | event lifecycle 深模块，集中事件配置保存、portal reset、portal manual test、event move runtime reset、overlay/dialog refresh 和事件日志。 |
| `gui/modes/navigation/events/__init__.py` | 已同步 panel/manual test 导出 | 已同步 event lifecycle 导出 | 追加 | events 包入口新增 `NavigationEventLifecycle` 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 runtime command lifecycle 深模块 | 已同步 event lifecycle 深模块 | 追加 | 事件配置/portal 手动测试相关旧方法保留 wrapper，Widget 不再内联事件生命周期顺序。 |

下一轮计划：
- 继续审计剩余深职责。优先候选：地图点击 lifecycle（hint 设置、route edit、manual move 三分支）或完整 runtime loop facade。若拆地图点击，应集中点击模式、route 编辑结果、移动目标 guard、target marker/status 和 hint marker/rect 更新；若拆 runtime loop，要小心不要让单帧主循环变成浅传参巨兽。
## [SYNC] 2026-05-28 11:13 - GUI-STAGE-AO-NAV-MAP-CLICK-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 继续按深模块准则拆 `NavigationModeWidget`，本轮聚焦地图点击交互生命周期：`handle_map_click()`、`set_initial_hint()`、`toggle_hint_mode()` 共享的 scene/global 坐标转换、hint marker、监控/视野框即时反馈、route editor 三种 click mode、route overlay/status、手动移动目标 guard、target marker 和 `MotionController.move_to_map_target()`。
**直接变更文件：** 预计新增 `gui/modes/navigation/map/click_lifecycle.py`，修改 `gui/modes/navigation/map/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `handle_map_click()`、`set_initial_hint()`、`toggle_hint_mode()` 旧入口 wrapper；地图点击状态机下沉到 navigation/map 包。必须保持 hint 优先、route edit 次之、手动移动最后的分支顺序，以及 route overlay、状态栏、target marker 和 hint 按钮复位行为。
### C. SYNC 结果

关键发现：
- (verified) `handle_map_click()` 是一个真实交互生命周期，不是单个 click helper：它按 hint -> route edit -> manual move 的优先级解释同一次 scene 点击，且每个分支都写不同运行态和 UI。
- (verified) `set_initial_hint()` 与 `toggle_hint_mode()` 不应继续孤立留在 Widget：hint 分支同时写 `NavigationCore`、QGraphics marker、监控框、真实视野框、按钮 checked、view drag/cursor 和状态栏，属于同一地图点击交互模块。
- (verified) 该模块放在 `navigation/map/` 比放在 presentation 更合理，因为它决定点击语义和运行态副作用；presentation 仍只负责 marker/status 具体绘制/文案。

代码变更：
- 新增 `gui/modes/navigation/map/click_lifecycle.py`：`NavigationMapClickLifecycleTargets`、`NavigationMapClickLifecycle`。
- 修改 `gui/modes/navigation/map/__init__.py`：导出 map click lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.map_click_lifecycle`；`handle_map_click()`、`set_initial_hint()`、`toggle_hint_mode()` 变为 wrapper；清理 hint/move 相关 presentation imports。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map\__init__.py gui\modes\navigation\map\click_lifecycle.py` 通过。
- `python -` smoke：验证 hint 分支先写 `nav_core.set_initial_hint()`，再 marker/monitor/game-view/status/button/view；route edit 分支顺序为 route click -> set mode -> render route -> status；未定位 manual move 分支只 warning；已定位 manual move 分支调用 `MotionController.move_to_map_target()` 后更新 target marker/status。
- 全 GUI `py_compile` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/click_lifecycle.py` | 新增 | 深度完整 | 1 | map click lifecycle 深模块，集中 hint/route edit/manual move 三分支、坐标转换、marker/overlay/status 和移动 guard。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 map load lifecycle 导出 | 已同步 map click lifecycle 导出 | 追加 | map 包入口新增 `NavigationMapClickLifecycle` 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 event lifecycle 深模块 | 已同步 map click lifecycle 深模块 | 追加 | 地图点击相关旧方法保留 wrapper，Widget 不再内联点击语义分支。 |

下一轮计划：
- 当前 `navigation_mode.py` 已降到 1255 行；剩余高价值候选主要是完整 runtime loop facade 或 screen calibration lifecycle。runtime loop 参数较多，需避免抽成传参巨兽；更稳的下一刀可能是 calibration lifecycle（屏幕中心点击 -> 写配置 -> 参数回填 -> overlay -> 保存 -> completion dialog -> selector close）。

## [SYNC] 2026-05-28 11:32 - GUI-STAGE-AP-NAV-SCREEN-CALIBRATION-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 继续按 `ARCHITECTURE_OPTIMIZATION_RULES.md` 的深模块规则优化 GUI，本轮聚焦 `NavigationModeWidget` 的屏幕中心校准生命周期：启动全屏选择器、接收逻辑坐标、转换物理坐标、写回 `NavConfig.game_screen_center`、回填参数弹窗、刷新 overlay、保存导航配置、显示完成反馈并关闭选择器。
**直接变更文件：** 预计新增 `gui/modes/navigation/calibration/lifecycle.py`，修改 `gui/modes/navigation/calibration/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `_calibrate_screen_center()` 和 `_handle_calibration_click()` 旧入口 wrapper；`ScreenCenterCalibrationController` 继续只负责 selector/DPR 基础能力，新 lifecycle 负责导航配置与 UI 副作用顺序；不引入 hook/event bus。

### C. SYNC 结果

关键发现：
- (verified) `_calibrate_screen_center()` 和 `_handle_calibration_click()` 不是单个 UI helper，而是一条完整校准生命周期：selector 启动、逻辑坐标转物理坐标、写 `NavConfig.game_screen_center`、回填参数弹窗、刷新 overlay、保存当前地图配置、完成提示、关闭 selector。
- (verified) `screen_center.py` 应继续保持底层能力边界，只负责 `CenterPointSelector` 生命周期和 DPR/坐标转换；配置写入与 UI 保存反馈应放入新的 `calibration/lifecycle.py`，避免 controller 反向知道导航页配置。
- (verified) 旧 slot `_calibrate_screen_center()` / `_handle_calibration_click()` 可以保留 wrapper，外部 Qt signal 和潜在旧调用不需要迁移。

代码变更：
- 新增 `gui/modes/navigation/calibration/lifecycle.py`：定义 `NavigationScreenCalibrationLifecycleTargets` 和 `NavigationScreenCalibrationLifecycle`。
- 修改 `gui/modes/navigation/calibration/__init__.py`：导出 calibration lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.screen_calibration_lifecycle`；校准旧方法改为委托 lifecycle；移除对 `show_screen_center_calibrated` 的直接依赖。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\calibration\__init__.py gui\modes\navigation\calibration\lifecycle.py gui\modes\navigation\calibration\screen_center.py` 通过。
- `python -` smoke：验证 start 阶段写回 selector，点击阶段顺序为 logical_to_physical -> params dialog -> overlay -> save -> show -> close，并写入 `(20, 60)`。
- 全 GUI `py_compile` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/calibration/lifecycle.py` | 新增 | 深度完整 | 1 | screen calibration lifecycle 深模块，集中校准点击后的配置/UI/保存/关闭 selector 顺序，通过 targets DTO 接入 widget。 |
| `gui/modes/navigation/calibration/__init__.py` | 已同步 screen-center helper 导出 | 已同步 calibration lifecycle 导出 | 追加 | calibration 包入口新增 `NavigationScreenCalibrationLifecycle` 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 map click lifecycle 深模块 | 已同步 screen calibration lifecycle 深模块 | 追加 | `_calibrate_screen_center()` / `_handle_calibration_click()` 保留旧入口，内部委托 lifecycle。 |

下一轮计划：
- 继续按深模块准则审计 `NavigationModeWidget` 剩余职责。下一优先候选是 dialog ownership/UI wiring 小系统，或对 `_navigation_loop_unified()` 做“是否已经足够骨架化”的复核；不为了继续压行数强拆 runtime loop。

## [SYNC] 2026-05-28 11:55 - GUI-STAGE-AQ-NAV-ROUTE-COMMAND-LIFECYCLE-DEEP-MODULE
### A. SYNC 范围声明
**触发任务：** 继续按深模块规则优化 `NavigationModeWidget`，本轮聚焦路线命令生命周期：`load_route_data()`、`save_route()`、`undo_guide_point()`、`undo_required_point()`、`clear_route()` 共享的 route JSON 读取/写入结果、`route_data` 内存态、`NavigationTaskController.load_route()`、route overlay 刷新、状态栏文案和保存失败 warning。
**直接变更文件：** 预计新增 `gui/modes/navigation/route/lifecycle.py`，修改 `gui/modes/navigation/route/__init__.py`、`gui/modes/navigation_mode.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `load_route_data()`、`save_route()`、`undo_guide_point()`、`undo_required_point()`、`clear_route()` 旧入口 wrapper；`RoutePanelController` 继续只处理按钮/click mode/route editor 命令结果，新 lifecycle 负责把结果同步到导航运行态和 overlay。

### C. SYNC 结果

关键发现：
- (verified) `load_route_data()`、`save_route()`、`undo_guide_point()`、`undo_required_point()`、`clear_route()` 共享同一条 route 命令同步链：route 数据变化后必须同步 `NavigationModeWidget.route_data`、`NavigationTaskController.load_route()`、route overlay 和状态栏反馈。
- (verified) `RoutePanelController` 不应该继续扩张到任务控制器或 overlay；它适合保持为按钮/click mode/命令结果 controller。新的 `NavigationRouteLifecycle` 承接运行态同步，边界更清晰。
- (verified) 旧 route slot 可以保留 wrapper，map load lifecycle 和按钮 signal 不需要迁移调用点。

代码变更：
- 新增 `gui/modes/navigation/route/lifecycle.py`：定义 `NavigationRouteLifecycleTargets` 和 `NavigationRouteLifecycle`。
- 修改 `gui/modes/navigation/route/__init__.py`：导出 route lifecycle facade 和 targets DTO。
- 修改 `gui/modes/navigation_mode.py`：初始化 `self.route_lifecycle`；`load_route_data()`、`save_route()`、`undo_guide_point()`、`undo_required_point()`、`clear_route()` 改为 wrapper；移除 route command presentation 的直接 import。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\route\__init__.py gui\modes\navigation\route\lifecycle.py gui\modes\navigation\route\panel_controller.py gui\modes\navigation\route\editor.py` 通过。
- `python -` smoke：验证 load/save/undo required/undo guide/clear 均同步 route_data、task main route、overlay/status；save 失败只走旧 warning。
- 全 GUI `py_compile` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/route/lifecycle.py` | 新增 | 深度完整 | 1 | route command lifecycle 深模块，集中加载/保存/撤销/清空后的 route_data、任务控制器、overlay 和状态栏同步。 |
| `gui/modes/navigation/route/__init__.py` | 已同步 editor/panel 导出 | 已同步 route lifecycle 导出 | 追加 | route 包入口新增 `NavigationRouteLifecycle` 和 targets DTO。 |
| `gui/modes/navigation_mode.py` | 已同步 screen calibration lifecycle 深模块 | 已同步 route command lifecycle 深模块 | 追加 | route 旧 slot 保留 wrapper，运行态同步下沉到 route lifecycle。 |

下一轮计划：
- 继续复核 `NavigationModeWidget` 剩余职责。高价值候选减少后，应优先判断 runtime loop 是否已经足够骨架化；若继续拆，倾向提取 dialog ownership 或 map display lifecycle，但只有在能隐藏完整状态链时才做。

## [SYNC] 2026-05-28 12:20 - GUI-STAGE-AR-NAV-CANONICAL-ENTRY-AND-UI-SHELL-SPLIT
### A. SYNC 范围声明
**触发任务：** 根据最新主线，导航页外部入口可以改变，旧 `navigation_mode.py` 不再作为长期壳子保留；本轮继续把 `NavigationModeWidget` 拆成更轻的组合根，先处理 canonical 入口迁移后的 UI 构建和 signal wiring。
**直接变更文件：** 预计修改 `gui/main_window.py`、`gui/modes/navigation_mode.py`、`gui/modes/navigation/__init__.py`、`gui/modes/navigation/widget.py`，新增 `gui/modes/navigation/ui/`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `gui.modes.navigation.NavigationModeWidget` 作为 canonical 入口；旧 `gui.modes.navigation_mode.NavigationModeWidget` 只作为临时 wrapper。UI builder/signal binder 不改变按钮名称、signal 连接目标和旧 slot wrapper。

### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget.init_ui()` 原本仍内联创建顶部工具栏、`QGraphicsScene/QGraphicsView`、状态栏和 `RoutePanelController`，迁移后只调用 `navigation/ui/layout.py::build_navigation_ui()`，控件字段名和初始化顺序保持一致。
- (verified) `_connect_signals()` 原本仍内联绑定按钮、参数弹窗和事件弹窗信号，迁移后只调用 `navigation/ui/signals.py::connect_navigation_signals()`，绑定目标仍是旧 slot/wrapper，未改变 GUI 行为入口。
- (verified) `gui/main_window.py` 已使用 `from .modes.navigation import NavigationModeWidget`；旧 `gui/modes/navigation_mode.py` 只 re-export 新包入口，后续兼容层清理阶段可删除。
- (verified) `navigation/map/config_store.py::project_root_from_file()` 已能从更深的 `navigation/widget.py` 向上寻找项目根，避免移动真实 widget 文件后 map_data 路径推断错误。

代码变更：
- 修改 `gui/modes/navigation/widget.py`：删除内联 UI 构建和信号绑定大段实现，保留 `init_ui()` / `_connect_signals()` 壳方法并委托 `navigation.ui`。
- 新增/确认 `gui/modes/navigation/ui/__init__.py`、`gui/modes/navigation/ui/layout.py`、`gui/modes/navigation/ui/signals.py`：分别作为 UI shell 包入口、布局构建 helper、信号绑定 helper。
- 保留 `gui/modes/navigation_mode.py` 临时兼容 wrapper；`gui/main_window.py` 使用 canonical 包入口。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py gui\modes\navigation\ui\__init__.py gui\modes\navigation\ui\layout.py gui\modes\navigation\ui\signals.py gui\modes\navigation_mode.py gui\main_window.py` 通过。
- 全 GUI `py_compile` 通过。
- `python -c "from gui.modes.navigation import NavigationModeWidget; from gui.modes.navigation_mode import NavigationModeWidget as Legacy; assert NavigationModeWidget is Legacy"` 通过。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/widget.py` | 已同步 route command lifecycle 深模块 | 已同步 UI shell split | 追加 | `init_ui()` / `_connect_signals()` 只保留壳方法；控件创建和信号绑定下沉到 `navigation/ui/`。 |
| `gui/modes/navigation/ui/__init__.py` | 新增 | 深度完整 | 1 | UI shell 包入口，只聚合导出 layout 与 signals helper。 |
| `gui/modes/navigation/ui/layout.py` | 新增 | 深度完整 | 1 | 创建顶部工具栏、地图 scene/view、状态栏、route panel 和初始图形项字段；不连接信号、不启动业务流程。 |
| `gui/modes/navigation/ui/signals.py` | 新增 | 深度完整 | 1 | 集中绑定导航页按钮、参数弹窗和事件弹窗信号，目标仍是 widget 旧 slot/wrapper。 |
| `gui/modes/navigation_mode.py` | 已迁移 canonical wrapper | 已验证兼容 wrapper | 追加 | 旧路径继续 re-export 新 `gui.modes.navigation.NavigationModeWidget`，等待最终兼容层清理。 |
| `gui/main_window.py` | 已迁移 canonical import | 已验证 canonical import | 追加 | 主窗口直接导入 `gui.modes.navigation.NavigationModeWidget`。 |

下一轮计划：
- 继续复核 `NavigationModeWidget` 剩余 1000 行左右内容。优先看 dialog/event dialog 生命周期和 map display lifecycle 是否还能形成“完整状态链”抽取；不再只按行数切分。

## [SYNC] 2026-05-28 12:55 - GUI-STAGE-AS-NAV-REMAINING-WIDGET-DEEP-SEAM-REVIEW
### A. SYNC 范围声明
**触发任务：** 继续按 GUI/core 模块化主线审计 `NavigationModeWidget` 剩余职责，判断下一刀应拆 dialog lifecycle、map display lifecycle、runtime loop controller，还是暂时保留在组合根中。
**直接变更文件：** 预计先阅读 `gui/modes/navigation/widget.py`、已拆出的 `gui/modes/navigation/ui/*` 和相关 presentation/runtime helper；若发现完整状态链，会新增对应功能包文件并同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 只抽取能隐藏状态顺序和副作用边界的模块；旧 slot/wrapper 可继续保留，外部入口最终等 GUI 迁移完成后统一清理。

### C. SYNC 结果

关键发现：
- (verified) display 相关剩余方法不是单纯“行数问题”，而是同一条 Qt scene item 状态链：地图重建会重置 route/event overlay 和所有 marker 引用；route overlay 渲染后需要同步刷新 event overlay；定位循环会持续回调绿色监控框和橙色视野框；地图加载后会显示上次退出点。
- (verified) 这条状态链只依赖 GUI item 引用和 presentation 小函数，不负责地图 IO、定位、任务调度或真实输入，适合沉到 `navigation/display/` 包。
- (verified) 复核时发现 `_navigation_loop_unified()` 终态分支使用 `show_navigation_arrived()` / `show_navigation_failed()`，但 `widget.py` import 列表缺失；`py_compile` 不会捕捉该 NameError，本轮已补回 import。

代码变更：
- 新增 `gui/modes/navigation/display/__init__.py`：display lifecycle 包入口。
- 新增 `gui/modes/navigation/display/lifecycle.py`：`NavigationMapDisplayLifecycle` 集中处理 scene item 引用写回、route/event overlay 清理和渲染、监控框/视野框刷新、上次退出位置 marker。
- 修改 `gui/modes/navigation/widget.py`：初始化 `self.display_lifecycle`；`_clear_route_overlay()`、`_clear_event_overlay()`、`_global_to_scene()`、`_render_event_overlay()`、`_render_route_overlay()`、`_render_map()`、`_update_monitor_rect()`、`_update_game_view_rect()`、`_refresh_game_view_rect_from_known_position()`、`_show_last_exit_position()` 改为 wrapper；补回终态状态栏函数 import。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py gui\modes\navigation\display\__init__.py gui\modes\navigation\display\lifecycle.py` 通过。
- 全 GUI `py_compile` 通过。
- `from gui.modes.navigation.display import NavigationMapDisplayLifecycle` 导入通过。
- `from gui.modes.navigation.widget import show_navigation_arrived, show_navigation_failed` 导入通过，确认终态分支依赖已恢复。
- GUI 旧 core facade import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/widget.py` | 已同步 UI shell split | 已同步 map display lifecycle | 追加 | display 相关旧私有方法保留为 wrapper；显示状态写回下沉到 `navigation/display/lifecycle.py`；补回终态状态栏 import。 |
| `gui/modes/navigation/display/__init__.py` | 新增 | 深度完整 | 1 | display lifecycle 包入口，只导出 `NavigationMapDisplayLifecycle`。 |
| `gui/modes/navigation/display/lifecycle.py` | 新增 | 深度完整 | 1 | 集中 scene item、route/event overlay、监控框/视野框、上次退出点 marker 的 owner 字段写回；不做地图加载、定位或任务调度。 |

下一轮计划：
- 继续看 event dialog lifecycle：`_ensure_event_dialog()`、`_connect_event_dialog_signals()`、`toggle_event_dialog()`、`_refresh_event_dialog()` 和 manual test button reset 是否能形成独立 dialog subsystem。若边界太薄，则转向 runtime loop controller。

## [SYNC] 2026-05-28 13:25 - GUI-STAGE-AT-NAV-EVENT-DIALOG-AND-COMPAT-SHELL-AUDIT
### A. SYNC 范围声明
**触发任务：** 继续优化 GUI，并开始为 GUI/core 旧兼容壳删除做引用审计。本轮先判断导航事件弹窗生命周期是否能形成 deep module；随后扫描 GUI/core 两侧 wrapper 的真实引用，能安全删除的优先删除，仍被调用的只记录迁移点。
**直接变更文件：** 预计阅读/修改 `gui/modes/navigation/widget.py`、`gui/modes/navigation/events/*`、`gui/main_window.py`、`gui/modes/navigation_mode.py`、core 顶层 wrapper 与调用方；同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 若删除 wrapper，需要同步所有 import 到 canonical package；若发现脚本仍依赖 core 顶层壳，则先迁移脚本调用再删。测试文件按用户要求不纳入实现迁移依据。

### C. SYNC 结果

关键发现：
- (verified) 事件弹窗生命周期已经可以作为独立 deep module：`gui/modes/navigation/events/dialog_lifecycle.py` 负责创建弹窗、连接信号、刷新 registry/config/coordinator/map name，并同步 portal 手动测试按钮；`NavigationModeWidget` 只保留 `_ensure_event_dialog()`、`_connect_event_dialog_signals()`、`toggle_event_dialog()`、`_refresh_event_dialog()` wrapper。
- (verified) GUI 旧入口壳已经删除：`gui/modes/navigation_mode.py`、`gui/modes/mapping/save_load.py`、`gui/modes/mapping/params_adapter.py`、`gui/modes/navigation/map_runtime.py`、`gui/modes/navigation/route_overlay.py`、`gui/modes/navigation/event_overlay.py`、`gui/modes/navigation/viewport_overlay.py`、`gui/modes/event_test_controller.py` 均不再作为实现入口存在。
- (verified) core 旧顶层壳已经删除，`core/__init__.py` 不再聚合导出；实现侧入口改为 `core.platform`、`core.vision`、`core.mapping`、`core.localization`、`core.routing`、`core.input`、`core.navigation_tasks` 等系统包。
- (verified) `core.events.debug`、`core.events.coordinator`、`core.events.memory`、`core.events.position_stabilizer`、`core.events.types.portal.handler` 等仍然可 import，但它们现在是正式同名 package 入口，不是旧 `.py` 文件壳。
- (verified) `NavigationTaskController.update(**kwargs)` 和 `NavigationUpdateContext.from_legacy_kwargs()` 已删除；GUI runtime helper 直接构造 `NavigationUpdateContext` 并调用 `update_context()`。

代码/结构变更确认：
- `gui/main_window.py` 使用 `from .modes.navigation import NavigationModeWidget`。
- `main.py` 使用 `from gui.main_window import MainWindow`。
- `gui/__init__.py` 与 `core/__init__.py` 均回到 package marker。
- `core/platform` 只导出 `SquareScreenCapture`，不再保留 `ScreenCapture = SquareScreenCapture`。
- 旧 core/gui wrapper 文件已从实现树删除；工具脚本已迁移到系统包入口或正式 portal package 入口。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
- `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`
- `architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md`
- `architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md`
- `architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md`
- `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `rg -n "core\.(stitcher_core|pathfinder|navigation_core|motion_controller|capture|recognizer_optimized|tracker|route_manager|input_driver|navigation_obstacles|path_utils|anchor_path|motion_mapping|phase_displacement)|from core import|import core$" core gui main.py logging_system.py utils -g "*.py" --glob "!tests/**" --glob "!debug/**"` 无命中。
- `rg -n "navigation_mode|mapping\.save_load|mapping\.params_adapter|navigation\.map_runtime|navigation\.route_overlay|navigation\.event_overlay|navigation\.viewport_overlay|event_test_controller|widgets_fixed" gui main.py core utils -g "*.py" --glob "!tests/**" --glob "!debug/**"` 无命中。
- `Get-ChildItem -Path core,gui,utils -Recurse -Filter *.py | Where-Object { $_.FullName -notmatch '\\tests\\|\\debug\\' } | ForEach-Object { D:\ACloud\.venv\Scripts\python.exe -m py_compile $_.FullName }` 通过。
- import smoke 通过：`core`/`gui` 可导入；`MainWindow`、`NavigationModeWidget`、`SquareScreenCapture`、`HSVRecognizer`、`MapStitcher`、`NavigationCore`、`PathFinder`、`RouteManager`、`MotionController`、`NavigationTaskController`、`NavigationUpdateContext`、`EventCoordinator`、`PortalEventHandler` 均可从正式入口导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/events/dialog_lifecycle.py` | 新增/未记录完整 | 深度完整 | 1 | 事件弹窗创建、信号连接、刷新和 portal manual test 按钮同步均已从 widget 下沉。 |
| `gui/modes/navigation/widget.py` | 已同步 map display lifecycle | 已同步事件弹窗 lifecycle 与旧壳删除后的正式入口 | 追加 | 真实文件为导航组合根；旧 `navigation_mode.py` 已删除；保留的 wrapper 仅服务 Qt signal 和内部兼容调用。 |
| `core/__init__.py` | 旧聚合入口 | package marker | 追加 | 不再导出 root convenience imports。 |
| `gui/__init__.py` | 旧聚合入口 | package marker | 追加 | `MainWindow` 由 `gui.main_window` 显式导入。 |
| `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md` | 旧“保留壳子”计划 | 当前系统包入口与旧壳删除状态 | 追加 | 文档改为描述正式入口、已删除壳和后续内部 wrapper 清理规则。 |
| `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md` | 旧阶段计划 | 当前 GUI 功能包状态和下一步组合根减重计划 | 追加 | 不再把旧 GUI 入口壳列为目标结构。 |

下一轮计划：
- 继续按“深模块优先、非按行数”规则减轻 `NavigationModeWidget`。优先复核 `_initialize_event_system()` 是否能进入 `navigation/events/` bootstrap，或复核 `__init__` 中 targets DTO 构造是否能进入 composition 模块；若 callback/状态转运过多，则暂缓，不做参数巨兽。

## [SYNC] 2026-05-28 14:05 - GUI-STAGE-AU-NAV-EVENT-SYSTEM-BOOTSTRAP
### A. SYNC 范围声明
**触发任务：** 继续按深模块规则减轻 `NavigationModeWidget`，本轮聚焦 `_initialize_event_system()`：它负责 map folder guard、event config load、`EventCoordinator` 创建、`GameWindowCaptureProvider` 创建、事件弹窗刷新和初始化日志，边界可能适合沉到 `navigation/events/` bootstrap 模块。
**直接变更文件：** 预计阅读/修改 `gui/modes/navigation/widget.py`、`gui/modes/navigation/events/__init__.py`、新增 `gui/modes/navigation/events/bootstrap.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 保留 `NavigationModeWidget._initialize_event_system()` 旧 wrapper；新模块返回 event config/coordinator/capture provider 三个运行态对象，不触碰 Qt 控件和 route/navigation task 状态；初始化日志和弹窗刷新顺序必须保持。

### C. SYNC 结果

关键发现：
- (verified) `_initialize_event_system()` 的完整状态链只有三类产物：`event_config`、`event_coordinator`、`event_capture_provider`。它不依赖 route、timer、输入执行或 task controller 状态，适合沉到 `navigation/events/bootstrap.py`。
- (verified) 初始化顺序需要保持：无地图路径时清空 runtime；有地图时读取 event config -> 创建 coordinator -> 创建 game-window capture provider -> 刷新事件弹窗 -> 写初始化日志。
- (verified) `NavigationModeWidget` 仍需要保留 `_initialize_event_system()` 作为 map-load lifecycle 回调，但内部可以只把 bootstrap 返回值写回字段。

代码变更：
- 新增 `gui/modes/navigation/events/bootstrap.py`：定义 `NavigationEventSystemRuntime` 和 `initialize_navigation_event_system()`。
- 修改 `gui/modes/navigation/events/__init__.py`：导出 event bootstrap DTO 和函数。
- 修改 `gui/modes/navigation/widget.py`：移除对 `GameWindowCaptureProvider`、`load_event_config`、`EventCoordinator` 的直接 import；`_initialize_event_system()` 改为委托 bootstrap 并写回 runtime 字段。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py gui\modes\navigation\events\__init__.py gui\modes\navigation\events\bootstrap.py` 通过。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`initialize_navigation_event_system`、`NavigationEventSystemRuntime`、`NavigationModeWidget`、core 正式入口均可导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。
- no-map smoke 通过：`initialize_navigation_event_system(map_folder_path=None, ...)` 返回三项空 runtime，且不刷新事件弹窗。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/events/bootstrap.py` | 新增 | 深度完整 | 1 | 地图加载后事件系统 runtime 初始化模块，集中 event config/coordinator/capture provider 创建、弹窗刷新和初始化日志。 |
| `gui/modes/navigation/events/__init__.py` | 已同步 event dialog/lifecycle 导出 | 已同步 event bootstrap 导出 | 追加 | events 包入口新增 `NavigationEventSystemRuntime` 和 `initialize_navigation_event_system`。 |
| `gui/modes/navigation/widget.py` | 已同步事件弹窗 lifecycle 与旧壳删除后的正式入口 | 已同步 event system bootstrap | 追加 | `_initialize_event_system()` 保留 wrapper，真实初始化逻辑进入 `events/bootstrap.py`。 |

下一轮计划：
- 继续复核 `NavigationModeWidget.__init__` 中 targets DTO 构造是否能抽到 composition/bootstrap。若抽取后只是把几十个 lambda 平移到另一个文件，则暂缓，转向 `eventFilter()` 的 Qt 鼠标事件解释拆分。

## [SYNC] 2026-05-28 14:35 - GUI-STAGE-AV-NAV-MAP-EVENT-FILTER
### A. SYNC 范围声明
**触发任务：** 继续减轻 `NavigationModeWidget`，本轮优先复核 `eventFilter()`。相比 `__init__` target DTO 构造，Qt 鼠标事件解释边界更清楚：只处理 view drag、hint 光标状态和地图点击转发，不应掺入 core 定位/任务/事件逻辑。
**直接变更文件：** 预计阅读/修改 `gui/modes/navigation/widget.py`、新增 `gui/modes/navigation/map/event_filter.py`、修改 `gui/modes/navigation/map/__init__.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `NavigationModeWidget.eventFilter()` 继续作为 Qt 安装入口；新 helper 只负责根据 watched/event 和当前控件状态决定是否处理，仍通过回调调用 `handle_map_click()`，不改 scene 坐标映射或点击优先级。

### C. SYNC 结果

关键发现：
- (verified) `eventFilter()` 的真实判断条件很窄：watched 必须是导航地图 scene，事件类型必须是 `QEvent.GraphicsSceneMousePress`，按钮必须是 `Qt.LeftButton`。这条规则不需要知道 hint、route edit、manual move 的业务优先级。
- (verified) hint/route/manual move 三分支已经在 `NavigationMapClickLifecycle.handle_map_click()` 中统一处理，Qt 事件层只需要把 `event.scenePos()` 转发进去。
- (verified) `NavigationModeWidget` 仍必须保留 `eventFilter()` 作为 Qt 安装入口；抽取后它只做 helper 委托和 `super().eventFilter()` fallback，不再直接依赖 `QEvent`/`Qt`。

代码变更：
- 新增 `gui/modes/navigation/map/event_filter.py`：定义 `handle_navigation_map_event_filter()`，集中 Qt scene 左键点击识别和 scene 坐标转发。
- 修改 `gui/modes/navigation/map/__init__.py`：导出 `handle_navigation_map_event_filter`，把它纳入 navigation map 包正式入口。
- 修改 `gui/modes/navigation/widget.py`：移除 `QEvent`/`Qt` 直接 import；`eventFilter()` 改为调用 map event-filter helper。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `Get-ChildItem -Path core,gui,utils -Recurse -Filter *.py | Where-Object { $_.FullName -notlike '*\tests\*' -and $_.FullName -notlike '*\debug\*' } | ForEach-Object { D:\ACloud\.venv\Scripts\python.exe -m py_compile $_.FullName }` 通过。
- import smoke 通过：`NavigationModeWidget`、`handle_navigation_map_event_filter`、`initialize_navigation_event_system`、core 正式系统包入口均可导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。
- no-map event bootstrap smoke 通过：无地图路径时返回空 runtime，且不刷新事件弹窗。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/map/event_filter.py` | 新增 | 深度完整 | 1 | Qt scene 鼠标左键事件解释 helper，只负责 `watched/event/button` 判定和 `scenePos()` 转发。 |
| `gui/modes/navigation/map/__init__.py` | 已同步 map load/click lifecycle 导出 | 已同步 map event-filter 导出 | 追加 | navigation map 包入口新增 `handle_navigation_map_event_filter`。 |
| `gui/modes/navigation/widget.py` | 已同步 event system bootstrap | 已同步 map event-filter helper | 追加 | `eventFilter()` 保留 Qt 安装入口，真实事件判断进入 `map/event_filter.py`；hint/route/manual move 仍由 map click lifecycle 处理。 |

下一轮计划：
- 继续深读 `NavigationModeWidget.__init__` 的 lifecycle/controller 构造区和 `_navigation_loop_unified()`。优先寻找能减少组合根字段/targets 组装噪音的模块边界；如果只是把 lambda 和字段赋值平移到别处，则不抽，转向 runtime loop 编排继续减重。

## [SYNC] 2026-05-28 16:00 - GUI-STAGE-AW-NAV-RUNTIME-FRAME-LOOP
### A. SYNC 范围声明
**触发任务：** 继续减轻 `NavigationModeWidget`，本轮在 `__init__` targets 构造和 `_navigation_loop_unified()` 之间选择后者。`__init__` 当前主要是 subsystem 实例化和 targets wiring，直接抽取容易变成参数搬运；导航帧循环则是稳定的运行时状态链，适合沉到 `navigation/runtime/`。
**直接变更文件：** 预计阅读/修改 `gui/modes/navigation/widget.py`、新增 `gui/modes/navigation/runtime/frame_loop.py`、修改 `gui/modes/navigation/runtime/__init__.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `NavigationModeWidget.navigation_loop()` 和 `_navigation_loop_unified()` 继续保留为 Qt timer 兼容入口；真实帧级编排迁入 runtime facade。必须保持旧顺序：截图定位 -> 事件 observe -> task controller update -> localization view/status -> route overlay -> intent consumption。

### C. SYNC 结果

关键发现：
- (verified) `__init__` 目前主要是 lifecycle/controller wiring，强行抽到 composition 文件会把大量 owner 字段和 lambda 平移过去，收益不如先抽帧循环。
- (verified) `_navigation_loop_unified()` 已经由多个小 helper 支撑，但仍在 QWidget 内掌握一帧完整顺序；这个顺序本身是稳定 runtime seam。
- (verified) 为避免制造超大 callback DTO，本轮的 `NavigationRuntimeFrameLoop` 暂时持有 widget owner。它不是 core 算法层，只负责 GUI navigation runtime 编排；后续如果继续工程化，应把 owner 访问收窄成 targets DTO。

代码变更：
- 新增 `gui/modes/navigation/runtime/frame_loop.py`：定义 `NavigationRuntimeFrameLoop`，集中 capture-localize、event observe、task update、localization presentation、route overlay 和 intent consumption 顺序。
- 修改 `gui/modes/navigation/runtime/__init__.py`：导出 `NavigationRuntimeFrameLoop`。
- 修改 `gui/modes/navigation/widget.py`：创建 `self.runtime_frame_loop`；`_navigation_loop_unified()` 只调用 `self.runtime_frame_loop.run()`；移除不再使用的 runtime/presentation/input imports 和 `_execute_navigation_intent()`、`_event_status_text()` 内联方法。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py gui\modes\navigation\runtime\frame_loop.py gui\modes\navigation\runtime\__init__.py` 通过。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`NavigationRuntimeFrameLoop`、`NavigationModeWidget`、event bootstrap、map event filter、core 正式系统包入口均可导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/runtime/frame_loop.py` | 新增 | 深度完整 | 1 | 导航定时器整帧 runtime facade，集中截图定位、事件观测、任务更新、状态展示、路线 overlay 和 intent 消费；暂持有 widget owner，后续可收窄为 targets DTO。 |
| `gui/modes/navigation/runtime/__init__.py` | 已同步 runtime helper 导出 | 已同步 frame loop 导出 | 追加 | 新增 `NavigationRuntimeFrameLoop` 正式导出。 |
| `gui/modes/navigation/widget.py` | 已同步 map event-filter helper | 已同步 runtime frame loop facade | 追加 | `_navigation_loop_unified()` 退化为 Qt timer wrapper，真实帧顺序迁入 `runtime/frame_loop.py`；widget 行数从约 950 行降到约 814 行。 |

下一轮计划：
- 审计 `NavigationModeWidget` 剩余长度。优先处理已经过时的长 docstring：很多方法现在只是 lifecycle wrapper，但注释仍描述旧内联步骤，容易误导后续维护；这属于旧内容审计清理，不改变行为。

## [SYNC] 2026-05-28 16:12 - GUI-STAGE-AX-NAV-WIDGET-STALE-DOCSTRING-CLEANUP
### A. SYNC 范围声明
**触发任务：** 继续旧内容审计。`NavigationModeWidget` 已经变成组合根和 wrapper，但很多长 docstring 仍描述旧内联步骤，和当前委托到 lifecycle/runtime 模块后的真实职责不一致。
**直接变更文件：** 预计修改 `gui/modes/navigation/widget.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 只清理/压缩过时内联说明，不改变函数签名、信号入口、wrapper 调用或 runtime 行为。目标是让 widget 中的注释匹配“组合根 + lifecycle facade”的现状。

### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget` 中多处长 docstring 仍描述“本方法内部执行步骤”，但对应实现已经委托到 `map_load_lifecycle`、`config_lifecycle`、`map_click_lifecycle`、`screen_calibration_lifecycle`、`command_lifecycle` 或 `runtime_frame_loop`。
- (verified) 这些说明不再是有用文档，反而会让后续维护者误以为 wrapper 仍拥有旧内联实现。
- (verified) 清理只影响注释和内联说明，不改变方法签名、信号连接、timer 入口或 runtime 行为。

代码变更：
- 修改 `gui/modes/navigation/widget.py`：压缩 `__init__`、`toggle_params_dialog()`、`refresh_map_list()`、`load_map()`、`_apply_config_to_core()`、`_on_parameter_changed()`、`_save_nav_config()`、`_compute_scale()`、`_toggle_overlay_display()`、`set_initial_hint()`、`toggle_hint_mode()`、`_calibrate_screen_center()`、`_handle_calibration_click()`、`toggle_navigation()` 的旧长 docstring。
- 同步移除少量已经没有信息增量的行尾注释和 overlay toggle 内部步骤注释。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py` 通过。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`NavigationModeWidget`、`NavigationRuntimeFrameLoop`、event bootstrap、map event filter、core 正式系统包入口均可导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/widget.py` | 已同步 runtime frame loop facade | 已同步旧 docstring 清理 | 追加 | 长 docstring 不再重复旧内联步骤；widget 从约 814 行降到约 601 行，保留组合根、Qt 入口和 wrapper 职责。 |
| `CODEBASE.md` | 已同步 runtime frame loop | 已同步 widget 旧说明清理 | 追加 | 导航 widget 职责说明改为组合根/facade，并记录旧长 docstring 已压缩。 |
| `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md` | 已同步 runtime frame loop | 已同步 widget 当前长度和说明清理状态 | 追加 | 当前状态更新为约 600 行，下一步仍按职责边界而非行数硬切。 |

下一轮计划：
- 继续审计 `NavigationModeWidget.__init__` targets wiring 是否能抽为真正的 composition module。如果只是搬运 lambda，则暂缓；更优先找无人调用的内部 wrapper 或仍然混合职责的 lifecycle target。

## [SYNC] 2026-05-28 16:17 - GUI-STAGE-AY-NAV-COMPOSITION-LIFECYCLES
### A. SYNC 范围声明
**触发任务：** 继续优化 `NavigationModeWidget.__init__`。上一轮确认剩余大块主要是系统 lifecycle/controller wiring；本轮只把这部分抽成 navigation 局部 composition module，不改变 lifecycle 本身职责。
**直接变更文件：** 预计新增 `gui/modes/navigation/composition/__init__.py`、`gui/modes/navigation/composition/lifecycles.py`，修改 `gui/modes/navigation/widget.py`，同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** `NavigationModeWidget` 保留核心字段初始化、UI builder、Qt timer entry 和 wrapper 方法；composition module 负责按旧顺序创建 display/config/route/events/map/runtime/calibration lifecycles。不得改变 `_connect_signals()` 与 `portal_test_controller` 创建顺序。

### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget.__init__` 剩余主要复杂度是系统组装顺序，而不是单个业务算法；适合进入 navigation 局部 `composition/`。
- (verified) 必须保留顺序：基础字段 -> `init_ui()` -> pre-signal lifecycle -> `_connect_signals()` -> timer/runtime lifecycle。事件弹窗 lifecycle 必须先于 signal wiring 存在，`portal_test_controller` 必须在延迟创建 event dialog 后绑定按钮。
- (verified) 抽取后没有改变 lifecycle target 内容，只把 owner wiring 移到同一功能包内；后续若继续复用化，应收窄 owner 依赖，而不是再扩大 callback DTO。

代码变更：
- 新增 `gui/modes/navigation/composition/__init__.py`：导出 composition 初始化函数。
- 新增 `gui/modes/navigation/composition/lifecycles.py`：定义 `initialize_navigation_pre_signal_lifecycles(owner)` 和 `initialize_navigation_runtime_lifecycles(owner)`，分别创建 pre-signal lifecycle 与 timer/runtime lifecycle。
- 修改 `gui/modes/navigation/widget.py`：移除大段 lifecycle/controller target 构造；`__init__` 只保留基础字段、`init_ui()`、composition 初始化、signal wiring 和 runtime composition 初始化。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\widget.py gui\modes\navigation\composition\__init__.py gui\modes\navigation\composition\lifecycles.py` 通过。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`NavigationModeWidget`、composition 初始化函数、`NavigationRuntimeFrameLoop`、event bootstrap、map event filter、core 正式系统包入口均可导入；`core.ScreenCapture` 和 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation/composition/__init__.py` | 新增 | 深度完整 | 1 | navigation composition 包入口，只导出 lifecycle 初始化函数。 |
| `gui/modes/navigation/composition/lifecycles.py` | 新增 | 深度完整 | 1 | 集中 display/config/route/events/map/runtime/calibration lifecycle wiring；保留 `_connect_signals()` 前后顺序。 |
| `gui/modes/navigation/widget.py` | 已同步旧 docstring 清理 | 已同步 composition lifecycles | 追加 | `__init__` 不再内联 targets wiring；widget 约 424 行，保留组合根字段、Qt 入口和 wrapper 职责。 |

下一轮计划：
- 继续找可删除的内部 wrapper 或能收窄 owner 依赖的点。优先复核 `NavigationModeWidget` 剩余 wrapper 是否仍被 signal、lifecycle target 或外部入口使用；无人调用的再删，仍作为入口的保留。

## [SYNC] 2026-05-28 16:44 - OPTIMIZATION-EXECUTION-BASELINE
### A. SYNC 范围声明
**触发任务：** 用户要求明确“后续还有哪些内容要做、优化结束标准是什么”，并新建一个后续执行基准文件；本轮按 codebase-ontology 流程读取当前 core/gui 架构文档、旧壳扫描状态和最新导航拆分结果，沉淀可执行路线和验收标准。
**直接变更文件：** 预计新增 `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`，并同步 `CODEBASE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`。
**预计连带影响：** 该文件成为后续优化执行的主线基准；不修改实现代码。后续所有 core/gui 优化应先对照该文件确认阶段、准入条件、退出条件和验证命令。

### C. SYNC 结果

关键发现：
- (verified) 当前旧 core/gui 路径壳已经删除并保持扫描清洁；后续主线不再是“删旧壳”，而是防止旧 import 回流、清理内部 wrapper、收窄 owner 依赖、继续梳理 GUI composition root 与 Mapping/Dialog 深模块。
- (verified) `NavigationModeWidget` 当前已经收敛为组合根、Qt 入口和必要 wrapper；剩余是否继续拆，不按行数判断，而按 wrapper 调用方、owner 依赖透明度、深模块边界和真实复用价值判断。
- (verified) 后续结束标准不能只看“文件变短”或“能 py_compile”，必须同时满足旧壳扫描清零、组合根职责清晰、内部 wrapper 去留有说明、中文文档和 `CODEBASE.md` 同步，以及连续两轮 codebase 审计无新结构问题。

文档变更：
- 新增 `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`：作为后续优化主线基准，记录当前基线、P0-P7 剩余优先级、每轮执行流程、验证命令和优化结束标准。
- 修改 `CODEBASE.md`：在目录结构图中登记新的执行基准文件。
- 修改 `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md`：把执行基准文件加入阅读顺序首位，便于上下文压缩或新会话后先恢复主线。

验证：
- 本轮只改中文文档与 `CODEBASE.md`，没有实现代码变更，未运行全量 `py_compile`。
- 已确认 `OPTIMIZATION_EXECUTION_BASELINE.md` 可读取，并且 `CODEBASE.md`、`ARCHITECTURE_GUIDE.md` 已包含入口引用。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md` | 新增 | 深度完整 | 1 | 后续执行基准，汇总 P0-P7、每轮流程、验证命令和阶段结束标准。 |
| `CODEBASE.md` | 已同步 GUI navigation composition 状态 | 已同步后续执行基准入口 | 追加 | 目录结构图新增执行基准文件，作为当前 codebase 文档体系的一部分。 |
| `architecture_docs/zh-CN/ARCHITECTURE_GUIDE.md` | 顶层架构阅读索引 | 已同步执行基准阅读入口 | 追加 | 阅读顺序首位新增 `OPTIMIZATION_EXECUTION_BASELINE.md`，后续先读基准再读模块文档。 |

下一轮计划：
- 后续直接按 `OPTIMIZATION_EXECUTION_BASELINE.md` 执行。优先进入 P1/P2：审计 GUI 内部 wrapper 的真实调用方，能删则删；不能删则记录保留原因。随后推进 AppContext/GUI composition root 与 Mapping/Dialog 深模块收口。实现代码变更后继续执行旧壳扫描、import smoke 和中文文档同步。

## [SYNC] 2026-05-28 16:54 - GUI-STAGE-AZ-WRAPPER-AUDIT
### A. SYNC 范围声明
**触发任务：** 用户要求开始按 `OPTIMIZATION_EXECUTION_BASELINE.md` 执行后续优化；本轮进入 P1/P2，先审计 GUI 内部 wrapper 的真实调用方和 navigation/mapping 组合模块的 owner 依赖，优先删除无人调用或只转发无语义的 wrapper，无法安全删除的记录保留原因。
**直接变更文件：** 预计读取 `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`、`architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`、`gui/modes/navigation/widget.py`、`gui/modes/navigation/composition/lifecycles.py`、`gui/modes/navigation/runtime/frame_loop.py`、`gui/modes/mapping_widget.py` 及其相关 helper；根据审计结果修改低风险目标，并同步 `CODEBASE.md`、相关中文架构文档和本日志。
**预计连带影响：** 不改 hook、不改算法阈值、不改用户功能流程；必须保持 Qt signal/timer/public class 入口、按钮状态、状态栏文案和导航/建图调用顺序。实现变更后运行非 tests/debug `py_compile`、import smoke 和旧壳扫描。

### C. SYNC 结果

关键发现：
- (verified) `NavigationModeWidget` 剩余很多 wrapper 仍被 `composition/lifecycles.py`、`runtime/frame_loop.py` 或 `ui/signals.py` 作为 Qt/lifecycle target 使用，当前直接删除会改变 signal/timer 或 callback 边界；本轮不机械删除这些 wrapper。
- (verified) `MappingWidget` 的 runtime、IO、presentation、params seam 已稳定，原 `create_control_panel()` / `create_display_panel()` 已经符合 P4 的“最后拆 layout”时机，可以迁入 `mapping/ui/` 深模块。
- (verified) `MappingWidget._show_image()` 已无人调用；display 写入由 `mapping/presentation/map_presenter.py` 和 `mapping/map_renderer.py` 承接，因此该私有 wrapper 和 `pixmap_from_bgr` import 可以删除。

代码变更：
- 新增 `gui/modes/mapping/ui/__init__.py`：导出 `build_mapping_ui`。
- 新增 `gui/modes/mapping/ui/layout.py`：集中建图页控制面板、显示面板、控件默认值和 signal wiring；只创建控件并写回 owner 字段，不读写 config、不启动 timer、不调用 recognizer/stitcher。
- 修改 `gui/modes/mapping_widget.py`：`setup_ui()` 改为委托 `build_mapping_ui(self)`；删除原内联 `create_control_panel()`、`create_display_panel()`；删除无人调用的 `_show_image()` 和对应 `pixmap_from_bgr` import。`MappingWidget` 当前约 327 行。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `Get-ChildItem -Path core,gui,utils -Recurse -Filter *.py | Where-Object { $_.FullName -notlike '*\tests\*' -and $_.FullName -notlike '*\debug\*' } | ForEach-Object { D:\ACloud\.venv\Scripts\python.exe -m py_compile $_.FullName }` 通过。
- import smoke 通过：`MappingWidget`、`build_mapping_ui`、`NavigationModeWidget`、`NavigationRuntimeFrameLoop`、event bootstrap 和 core 正式系统包入口均可导入；`core.ScreenCapture` 与 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。
- `git diff --check` 通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/ui/__init__.py` | 新增 | 深度完整 | 1 | mapping UI shell 包入口，只导出 `build_mapping_ui`。 |
| `gui/modes/mapping/ui/layout.py` | 新增 | 深度完整 | 1 | 控制面板和显示面板构建模块；写回原 owner 字段并保持原 signal 目标，不承担运行态或持久化职责。 |
| `gui/modes/mapping_widget.py` | 已同步 Mapping runtime/IO/presentation/params seam | 已同步 UI layout 抽取和死 wrapper 删除 | 追加 | 组合根保留 timer、保存时机、路径预览、advanced settings 和 topmost；不再内联 control/display panel 构建。 |
| `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md` | 后续执行基准 | 已同步 Mapping UI layout 完成状态 | 追加 | P4 中 layout 抽取标记完成，下一步转向 runtime lifecycle/save-state/AppContext 等更有价值边界。 |

下一轮计划：
- 继续按执行基准推进。优先候选：`MappingWidget` 的 start/stop/capture timer 生命周期是否值得迁入 `mapping/runtime/lifecycle.py`，或 `save_map()` 的地图名输入与成功/失败展示是否值得迁入 `mapping/presentation/save_state.py`。同时继续审计 GUI 内部 wrapper，只有确认无人调用或 signal 能直接迁移时再删除。

## [SYNC] 2026-05-28 17:09 - GUI-STAGE-BA-MAPPING-RUNTIME-LIFECYCLE
### A. SYNC 范围声明
**触发任务：** 用户要求继续按原计划自动执行直到达到优化验收标准；本轮接续 `OPTIMIZATION_EXECUTION_BASELINE.md` 的 P4，审计 `MappingWidget` 的 start/stop/capture timer 生命周期是否能迁入 `mapping/runtime/lifecycle.py`，以减少组合根对运行态切换细节的直接拥有。
**直接变更文件：** 预计读取/修改 `gui/modes/mapping_widget.py`、`gui/modes/mapping/runtime/__init__.py`、可能新增 `gui/modes/mapping/runtime/lifecycle.py`，并同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`、`architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md` 和本日志。
**预计连带影响：** 不改建图算法、不改截图选择、不改保存格式；必须保持“未选择区域时弹提示并取消 monitoring”“开始后按 FPS 启动 timer”“停止时复位 monitoring 和按钮文本”的旧顺序。实现变更后运行非 tests/debug `py_compile`、import smoke 和旧壳扫描。

### C. SYNC 结果

关键发现：
- (verified) `MappingWidget.toggle_monitoring()` / `stop_runtime()` 的真实职责是 command lifecycle：翻转 `app_context.monitoring`、校验截图配置、启动/停止 `QTimer`、维护按钮文案和 warning。这个行为比单纯 UI slot 更深，适合迁入 `mapping/runtime/lifecycle.py`。
- (verified) `capture_and_process()` 仍应留作 timer tick callback wrapper，因为它衔接 `MappingSession.tick()`、display presenter 和 statistics；直接搬入 lifecycle 会把 runtime command 与单帧建图/展示耦合回一起。
- (verified) 外部只通过 `MainWindow.closeEvent()` 调用 `MappingWidget.stop_runtime()`，没有实现侧直接访问 `capture_timer`，因此可以让 `MappingRuntimeLifecycle` 独占 QTimer。

代码变更：
- 新增 `gui/modes/mapping/runtime/lifecycle.py`：定义 `MappingRuntimeLifecycleTargets` 和 `MappingRuntimeLifecycle`，集中 monitoring flag、capture timer、FPS interval、缺少截图配置 warning 和按钮文案。
- 修改 `gui/modes/mapping/runtime/__init__.py`：导出 runtime lifecycle。
- 修改 `gui/modes/mapping_widget.py`：移除直接 `QTimer` 创建和启停；初始化 `self.runtime_lifecycle`；`toggle_monitoring()` / `stop_runtime()` 只委托 lifecycle。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\runtime\__init__.py gui\modes\mapping\runtime\lifecycle.py` 通过。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`MappingRuntimeLifecycle`、`MappingRuntimeLifecycleTargets`、`MappingWidget`、`NavigationModeWidget` 和 core 正式系统包入口均可导入；`core.ScreenCapture` 与 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping/runtime/lifecycle.py` | 新增 | 深度完整 | 1 | 建图 runtime command lifecycle，独占 QTimer 和 monitoring 状态，保持未配置 warning、FPS interval 和按钮文案顺序。 |
| `gui/modes/mapping/runtime/__init__.py` | 导出 session/model | 已同步 runtime lifecycle 导出 | 追加 | runtime 包入口现在导出 `MappingRuntimeLifecycle` 和 targets DTO。 |
| `gui/modes/mapping_widget.py` | 已同步 UI layout 抽取 | 已同步 runtime lifecycle 抽取 | 追加 | 组合根不再直接拥有 capture timer；`toggle_monitoring()` / `stop_runtime()` 保留稳定入口。 |

下一轮计划：
- 继续按执行基准推进。优先审计 `MappingWidget.save_map()` 是否值得把地图名输入、保存成功提示和错误展示迁入 `mapping/presentation/save_state.py`；如果 deletion test 判断过浅，则转向 `AppContext`/path composition 注入或 dialogs 中的 `AdvancedSettingsDialog` fallback 清理。

## [SYNC] 2026-05-28 17:16 - GUI-STAGE-BB-MAPPING-SAVE-OR-COMPOSITION
### A. SYNC 范围声明
**触发任务：** 继续按验收标准推进；本轮先用 deletion test 审计 `MappingWidget.save_map()` 的 presentation 抽取价值，如果只是把两个弹窗搬到新文件，则暂缓并改做 `AppContext`/project path 组合根这种更深的 seam。
**直接变更文件：** 预计读取 `gui/modes/mapping_widget.py`、`gui/app_context.py`、`gui/main_window.py`、`gui/modes/mapping/io/config_store.py`、`gui/modes/navigation/map/config_store.py`、`gui/dialogs/advanced_settings/file_io.py` 和相关文档；根据审计结果修改最小高价值目标，并同步 `CODEBASE.md`、中文架构文档和本日志。
**预计连带影响：** 不改保存格式、不改地图目录结构、不改启动入口；如果动路径组合根，只先新增集中路径 helper 并逐步替换 `Path(__file__).parents[n]`，保持旧目录解析结果一致。实现变更后运行非 tests/debug `py_compile`、import smoke 和旧壳扫描。

### C. SYNC 结果

关键发现：
- (verified) `MappingWidget.save_map()` 当前只剩 `QInputDialog` 获取名称、调用已抽出的 `save_mapping_map()` 和成功提示；如果只把输入框/提示框搬到 `mapping/presentation/save_state.py`，删除该模块后复杂度只会回到一个调用点，leverage 不高，本轮暂缓。
- (verified) 路径推导是真正重复且有风险的 seam：mapping config store 使用固定 `parents[2]`，navigation map config store 有自己的 root 查找，advanced settings 使用固定 `parents[3]`。这会在目录移动、打包或 helper 迁移后产生不一致。
- (verified) `gui/composition/paths.py` 可以集中 project root、`map_data`、根 `config.json` 和高级参数目录解析，同时保持旧目录结果一致。

代码变更：
- 新增 `gui/composition/__init__.py`：导出 GUI composition 路径 helper。
- 新增 `gui/composition/paths.py`：定义 `project_root_from_file()`、`project_root_from_map_folder()`、`map_data_dir_from_file()`、`root_config_path_from_file()`、`root_config_path_from_map_folder()`、`advanced_settings_dir_from_file()`。
- 修改 `gui/modes/mapping/io/config_store.py`：保留原 public helper 名称，但真实 project root、map_data、root config 路径解析委托 `gui.composition.paths`。
- 修改 `gui/modes/navigation/map/config_store.py`：复用 `gui.composition.paths`，包括从 map folder 解析根 config。
- 修改 `gui/dialogs/advanced_settings/file_io.py`：高级参数 snapshot 默认目录改为由 `advanced_settings_dir_from_file(__file__)` 解析。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\composition\__init__.py gui\composition\paths.py gui\modes\mapping\io\config_store.py gui\modes\navigation\map\config_store.py gui\dialogs\advanced_settings\file_io.py` 通过。
- 路径等价 smoke 通过：从 mapping/navigation/advanced settings 文件解析出的 project root、map_data、root config、advanced settings dir 均等于当前项目预期路径；从 `map_data/A1` 解析 project root 通过。
- GUI 实现侧 `parents[` / `PROJECT_ROOT = Path` / `dirname(` 扫描无命中。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`gui.composition.paths`、`MappingRuntimeLifecycle`、`MappingWidget`、`NavigationModeWidget` 和 core 正式系统包入口均可导入；`core.ScreenCapture` 与 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/composition/__init__.py` | 新增 | 深度完整 | 1 | GUI composition helper 包入口，导出路径解析 helper。 |
| `gui/composition/paths.py` | 新增 | 深度完整 | 1 | 集中 project root、map_data、root config、advanced settings dir 解析，替代 GUI 实现侧固定 `parents[n]`。 |
| `gui/modes/mapping/io/config_store.py` | 使用固定 `parents[2]` | 已委托 composition paths | 追加 | 保留原 public helper 名称和保存格式；真实路径解析集中到 `gui/composition/paths.py`。 |
| `gui/modes/navigation/map/config_store.py` | 自有 project root 查找和 map folder parents 推导 | 已委托 composition paths | 追加 | 保持 map list、map folder、default config 路径行为，减少重复路径规则。 |
| `gui/dialogs/advanced_settings/file_io.py` | 使用固定 `parents[3]` | 已委托 composition paths | 追加 | 高级参数 snapshot 目录仍为 `configs/advanced_settings/`，但项目根解析集中。 |

下一轮计划：
- 继续按验收标准收尾。优先审计 `gui/composition/services.py` 是否值得新增，用于集中 `SquareScreenCapture`、`HSVRecognizer`、`MapStitcher`、`PlayerTracker`、`PathFinder` 构造；如果只是把 `AppContext.__init__` 的 5 行搬出去则暂缓。随后做一次旧 wrapper/owner dependency 总审计，判断是否已经进入连续审计阶段。

## [SYNC] 2026-05-28 17:24 - GUI-STAGE-BC-CORE-SERVICES-COMPOSITION
### A. SYNC 范围声明
**触发任务：** 接续 P3，审计并推进 `gui/composition/services.py`：将 `SquareScreenCapture`、`HSVRecognizer`、`MapStitcher`、`PlayerTracker`、`PathFinder` 构造集中为可注入 services DTO，使 `AppContext` 更接近显式 composition root，而不是直接散落 core service 构造。
**直接变更文件：** 预计新增 `gui/composition/services.py`，修改 `gui/composition/__init__.py`、`gui/app_context.py`，并同步 `CODEBASE.md`、`architecture_docs/zh-CN/gui/ARCHITECTURE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md` 和本日志。
**预计连带影响：** 不改变默认 core service 类型和 `MapStitcher(canvas_size=5000)` 默认值；`AppContext(self)` 调用保持可用，同时允许未来注入 services 进行 smoke/test 或替代 adapter。实现变更后运行非 tests/debug `py_compile`、import smoke 和旧壳扫描。

### C. SYNC 结果

关键发现：
- (verified) `AppContext.__init__()` 直接构造五个共享 core services；虽然代码行数不多，但这些对象是 mapping/navigation 共享运行能力，适合作为显式 services DTO，便于后续注入替代 adapter 或 smoke harness。
- (verified) `MapStitcher(canvas_size=5000)` 是现有默认行为，必须保留在默认 factory 中，避免影响建图画布大小。
- (verified) GUI 中仍有 `ColorPickerDialog` 自己创建临时 `HSVRecognizer`；这是对话框局部预览状态，不属于 AppContext 共享服务，本轮不迁入 shared services。

代码变更：
- 新增 `gui/composition/services.py`：定义 frozen `CoreServices` DTO 和 `create_core_services(canvas_size=5000)`。
- 修改 `gui/composition/__init__.py`：导出 `CoreServices` 和 `create_core_services`。
- 修改 `gui/app_context.py`：移除直接 core service 构造 import，改为接收可选 `services: CoreServices`；未传入时调用 `create_core_services()`，保持 `AppContext(self)` 旧调用方式。

更新文档：
- `CODEBASE.md`
- `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`
- `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\app_context.py gui\composition\__init__.py gui\composition\services.py` 通过。
- services 注入 smoke 通过：`AppContext(services=create_core_services())` 写回的 `screen_capture` 与 DTO 同一对象，`stitcher.canvas_size == 5000`。
- 全 `core,gui,utils` 非 tests/debug `py_compile` 通过。
- import smoke 通过：`CoreServices`、`create_core_services`、`AppContext`、`MappingRuntimeLifecycle`、`MappingWidget`、`NavigationModeWidget` 和 core 正式系统包入口均可导入；`core.ScreenCapture` 与 `NavigationTaskController.update` 均不存在。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/composition/services.py` | 新增 | 深度完整 | 1 | 共享 core services DTO 和默认 factory；保留 `MapStitcher(canvas_size=5000)`。 |
| `gui/composition/__init__.py` | 已导出 paths | 已同步 services 导出 | 追加 | GUI composition 包入口同时导出 paths 和 services。 |
| `gui/app_context.py` | 直接构造 core services | 已委托 services composition | 追加 | `AppContext(self)` 保持可用，同时支持注入 `CoreServices`。 |

下一轮计划：
- 进入阶段验收审计：按 `OPTIMIZATION_EXECUTION_BASELINE.md` 检查旧壳/import、组合根职责、深模块边界、wrapper 去留、owner 依赖、GUI 路径硬编码和文档同步。若发现明确问题再修；若没有新结构问题，记录为第 1 轮收尾审计，后续再做第 2 轮确认。

## [SYNC] 2026-05-28 17:30 - OPTIMIZATION-ACCEPTANCE-AUDIT-1
### A. SYNC 范围声明
**触发任务：** 按 `OPTIMIZATION_EXECUTION_BASELINE.md` 进入阶段验收审计第 1 轮，检查当前 core/gui 工程化优化是否还存在必须处理的结构问题。
**直接变更文件：** 预计先不改实现，读取/扫描 `core/`、`gui/`、`utils/`、`main.py`、`logging_system.py`、`CODEBASE.md` 和中文架构文档；如果发现旧壳/import、GUI 路径硬编码、无人调用 wrapper、不可解释 owner 依赖或 stale 文档，再做针对性修复。
**预计连带影响：** 本轮以验证和审计为主；如果无实现修改，则只补审计记录。仍需运行全量非 tests/debug `py_compile`、import smoke、旧壳扫描、GUI path 硬编码扫描和 wrapper/owner 依赖抽样。
### C. SYNC 结果

关键发现：
- (verified) 实现侧全量非 tests/debug `py_compile` 通过，import smoke 通过；旧 core/gui 顶层壳扫描均无命中，GUI `parents[` / `PROJECT_ROOT = Path` / `dirname(` 路径硬编码扫描无命中。
- (verified) 当前长文件集中在 dialog schema/form、public composition root 和字段规格表：`nav_params_dialog.py`、`advanced_settings_dialog.py`、`NavigationModeWidget`、`EventManagerDialog`、`ColorPickerDialog`、`MappingWidget`、`nav_params/field_specs.py`。按当前规则，它们不是必须按行数继续拆的阻塞项。
- (verified) 审计发现当前态文档仍有旧表述：`gui/modes/ARCHITECTURE.md` 仍说 `_navigation_loop_unified()` 保留整帧编排；`GUI_OPTIMIZATION_PLAN.md` 仍把 navigation runtime loop facade、composition targets 当作下一步；`GUI_FULL_FILE_OPTIMIZATION_PLAN.md` 仍说 mapping/navigation config store 通过 `__file__` 推导项目根；`CODEBASE.md` 仍有 `MappingWidget` 拥有 map package persistence 的旧描述。

文档变更：
- 修正 `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`：当前 navigation runtime frame loop、event bootstrap、composition lifecycles 已下沉，剩余 owner-based facade 有保留理由。
- 修正 `architecture_docs/zh-CN/gui/ARCHITECTURE.md`：当前阶段进入验收审计，组合根不再按行数继续减重。
- 修正 `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md`：下一步改为验收审计；只有审计失败才继续拆 owner targets。
- 修正 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`：mapping/navigation config store 已委托 `gui/composition/paths.py`，不再保留固定 `parents[n]` 结论。
- 修正 `CODEBASE.md`：mapping IO、map save、composition paths/services、剩余 wrapper 保留标准同步为当前实现。

验证：
- `Get-ChildItem -Path core,gui,utils ... py_compile` 通过。
- import smoke 通过，包含 `AppContext`、`CoreServices`、`MappingRuntimeLifecycle`、`NavigationRuntimeFrameLoop`、core 系统包入口，并确认 `core.ScreenCapture` 与 `NavigationTaskController.update` 不存在。
- 旧 core wrapper/import 扫描无命中。
- 旧 GUI wrapper/import 扫描无命中。
- GUI 路径硬编码扫描无命中。
- 当前态 stale 文档扫描只命中 `ARCHITECTURE_ITERATION_LOG.md` 的历史轮次记录；历史日志不回写。
- `git diff --check` 对本轮文档通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` | 当前态局部过期 | 已同步验收前当前态 | 追加 | 修正 navigation frame loop/composition 当前边界和 mapping 后续拆分条件。 |
| `architecture_docs/zh-CN/gui/ARCHITECTURE.md` | in progress | 已同步验收审计状态 | 追加 | 主线改为验收审计，保留 composition roots 的理由明确化。 |
| `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md` | 旧下一步计划 | 已改为验收审计计划 | 追加 | 不再把已完成的 runtime loop/composition 抽取列为下一步。 |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | 局部旧路径结论 | 已同步 composition paths | 追加 | mapping/navigation config store 的路径 seam 描述修正。 |
| `CODEBASE.md` | 局部旧当前态 | 已同步当前实现 | 追加 | mapping IO/map save、wrapper 保留标准和验收主线修正。 |

结论：
- 本轮不是干净验收轮，因为发现并修正了 stale 当前态文档。
- 下一轮重新开始验收审计；只有连续两轮无新结构问题，才宣布当前 core/gui 工程化优化阶段结束。

## [SYNC] 2026-05-28 17:39 - OPTIMIZATION-ACCEPTANCE-AUDIT-2
### A. SYNC 范围声明
**触发任务：** 在修正当前态文档后，重新执行验收审计第 2 轮，判断是否已经达到“第一轮干净审计”。
**直接变更文件：** 预计不改实现；读取/扫描 `core/`、`gui/`、`utils/`、`main.py`、`logging_system.py`、`CODEBASE.md` 和中文架构文档。
**预计连带影响：** 重点确认旧壳/import、GUI 路径硬编码、stale 当前态文档、wrapper/owner 依赖和长文件保留理由。若无新增问题，本轮记为 clean audit round 1；随后再做一轮确认。
### C. SYNC 结果

关键发现：
- (verified) 非 tests/debug `core/`、`gui/`、`utils/` 全量 `py_compile` 通过。
- (verified) import smoke 通过，覆盖 `MainWindow`、`AppContext`、`CoreServices`、`MappingWidget`、`MappingRuntimeLifecycle`、`NavigationModeWidget`、`NavigationRuntimeFrameLoop` 和 core canonical 系统包入口；旧 `core.ScreenCapture` 与 `NavigationTaskController.update` 仍不存在。
- (verified) 旧 core 顶层壳/import 扫描无命中；旧 GUI 壳/import 扫描无命中；旧壳文件 `core/navigation_core.py`、`core/motion_controller.py`、`core/stitcher_core.py`、`gui/modes/navigation_mode.py` 等抽样 `Test-Path` 均为 `False`。
- (verified) GUI 路径硬编码扫描无命中；当前态 stale 文档扫描无命中（历史 `ARCHITECTURE_ITERATION_LOG.md` 不作为 stale 当前态）。
- (verified) owner-based 依赖抽样命中仅剩：mapping/navigation UI layout builder、navigation signal binder、`NavigationMapDisplayLifecycle(owner)`、`NavigationRuntimeFrameLoop(owner)`、composition 中 `NavigationRuntimeFrameLoop(owner)` 创建。它们均属于 Qt 控件构建、signal wiring、display item 写回或整帧 runtime facade，已在中文文档中解释保留理由。
- (verified) `pass` 抽样均为断开 Qt signal 或清理已失效 QGraphicsItem 时吞掉预期 RuntimeError/TypeError，不是空实现遗留。

验证：
- `Get-ChildItem -Path core,gui,utils ... py_compile` 通过。
- import smoke 通过。
- 旧 core wrapper/import 扫描无命中。
- 旧 GUI wrapper/import 扫描无命中。
- GUI path hardcode 扫描无命中。
- stale 当前态文档扫描无命中。
- 长文件列表：`nav_params_dialog.py` 659、`advanced_settings_dialog.py` 649、`navigation/widget.py` 424、`event_manager_dialog.py` 375、`color_picker_dialog.py` 366、`mapping_widget.py` 323、`nav_params/field_specs.py` 317。
- `git diff --check` 对当前文档通过。

保留理由：
- `nav_params_dialog.py` / `advanced_settings_dialog.py` / `event_manager_dialog.py` / `color_picker_dialog.py` 当前主要是 schema/form dialog 或交互态 dialog；已完成第一轮 helper/spec/adapter 拆分，后续新功能触碰时再按 section 拆。
- `NavigationModeWidget` 是 public composition root 和 Qt slot/facade，业务顺序已下沉到 `navigation/*` 功能包。
- `MappingWidget` 是 public composition root，runtime/session/capture/io/presentation/ui layout 已下沉，剩余为保存时机、advanced settings、路径预览和 topmost 状态。
- `field_specs.py` 是字段规格数据表，长是数据规模，不是混合职责。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/`、`gui/`、`utils/` 非 tests/debug Python 文件 | 验收前 | clean audit round 1 | 追加 | 编译、import、旧壳、路径硬编码和 stale 当前态扫描均通过。 |
| `gui/modes/navigation/widget.py` | public composition root | clean audit round 1 | 追加 | wrapper 均服务 Qt/lifecycle/public slot；无新增结构问题。 |
| `gui/modes/mapping_widget.py` | public composition root | clean audit round 1 | 追加 | runtime/capture/io/presentation/ui 已下沉；剩余职责可解释。 |
| `architecture_docs/zh-CN/*` 当前态文档 | 已修正 stale | clean audit round 1 | 追加 | 当前态 stale 扫描无命中。 |

结论：
- 本轮为干净验收审计第 1 轮。
- 下一轮重复关键验证；若仍无新增结构问题，则当前 core/gui 工程化优化阶段可收尾。

## [SYNC] 2026-05-28 17:42 - OPTIMIZATION-ACCEPTANCE-AUDIT-3
### A. SYNC 范围声明
**触发任务：** 执行连续验收审计第 3 轮，作为 clean audit round 2，确认当前 core/gui 工程化优化阶段是否满足结束标准。
**直接变更文件：** 预计不改实现；复跑全量编译、import smoke、旧壳/import 扫描、GUI 路径硬编码扫描、stale 当前态文档扫描、owner/wrapper 抽样和长文件列表。
**预计连带影响：** 如果本轮仍无新增结构问题，将更新 `OPTIMIZATION_EXECUTION_BASELINE.md`、`CODEBASE.md` 和中文架构文档的阶段状态为“本阶段已完成”；hook、新功能和更深 dialog section 拆分转入后续阶段。
### C. SYNC 结果

关键发现：
- (verified) 非 tests/debug `core/`、`gui/`、`utils/` 全量 `py_compile` 再次通过。
- (verified) import smoke 再次通过，canonical core/gui 入口可导入，旧 `core.ScreenCapture` 与 `NavigationTaskController.update` 不存在。
- (verified) 旧 core wrapper/import 扫描无命中；旧 GUI wrapper/import 扫描无命中；GUI path hardcode 扫描无命中。
- (verified) stale 当前态文档扫描无命中；历史日志中的旧计划记录按审计规则保留，不回写。
- (verified) owner-based 抽样与上一轮一致，只剩 UI builder/signal wiring/display lifecycle/runtime frame loop/composition 创建点；均属于当前文档已解释的保留项。
- (verified) 长文件列表与上一轮一致，均有保留理由：schema/form dialog、public composition root 或字段规格表。

阶段状态更新：
- 更新 `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md`：记录本轮 core/gui 工程化优化阶段已完成，`OPTIMIZATION-ACCEPTANCE-AUDIT-2` 与 `OPTIMIZATION-ACCEPTANCE-AUDIT-3` 连续两轮无新增结构问题。
- 更新 `architecture_docs/zh-CN/gui/ARCHITECTURE.md`、`gui/GUI_OPTIMIZATION_PLAN.md`、`gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`gui/modes/ARCHITECTURE.md`：从“验收审计中/下一步验收”改为“本阶段已完成/后续触发式拆分”。
- 更新 `CODEBASE.md`：记录当前 core/gui cleanup phase 已通过两轮 clean acceptance audit，后续 hook/new feature architecture 转入下一阶段。

验证：
- `Get-ChildItem -Path core,gui,utils ... py_compile` 通过。
- import smoke 通过。
- 旧 core wrapper/import 扫描无命中。
- 旧 GUI wrapper/import 扫描无命中。
- GUI path hardcode 扫描无命中。
- owner-based 抽样命中项均为已解释保留项。
- 长文件列表：`nav_params_dialog.py` 659、`advanced_settings_dialog.py` 649、`navigation/widget.py` 424、`event_manager_dialog.py` 375、`color_picker_dialog.py` 366、`mapping_widget.py` 323、`nav_params/field_specs.py` 317。
- 阶段状态更新后，当前态 stale 扫描无命中。
- `git diff --check` 对本轮文档通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/`、`gui/`、`utils/` 非 tests/debug Python 文件 | clean audit round 1 | clean audit round 2 | 追加 | 编译、import、旧壳、路径硬编码和 stale 当前态扫描再次通过。 |
| `architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md` | 验收标准基线 | 本阶段已完成 | 追加 | 记录连续两轮 clean audit 和阶段结束结论。 |
| `architecture_docs/zh-CN/gui/ARCHITECTURE.md` | 验收审计中 | 本阶段已完成 | 追加 | GUI 状态改为完成，后续按触发式拆分。 |
| `architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md` | 下一步验收审计 | 当前结果 + 后续触发式拆分 | 追加 | 移除旧“继续组合根减重”主线。 |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | 执行状态 | 本阶段验收完成 | 追加 | 明确不再为降行数继续拆分。 |
| `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` | 验收审计中 | 本阶段已完成 | 追加 | Navigation/Mapping wrapper 保留理由落文档。 |
| `CODEBASE.md` | acceptance auditing | cleanup phase passed | 追加 | 顶层当前态同步为已通过两轮 clean audit。 |

结论：
- 当前 core/gui 工程化优化阶段达到结束标准。
- 后续开发新功能时，以 `OPTIMIZATION_EXECUTION_BASELINE.md`、`architecture_docs/zh-CN/gui/ARCHITECTURE.md` 和 `CODEBASE.md` 为结构边界；hook、新功能架构、更深 dialog section 拆分和算法阈值调优均进入后续阶段讨论。

## [SYNC] 2026-05-28 17:49 - CORE-GUI-OLD-IMPLEMENTATION-RESIDUE-AUDIT
### A. SYNC 范围声明
**触发任务：** 用户要求“用 codebase 针对 core 和 gui 做一次深度检查，确保优化都完成，并确保没有旧实现残留”。
**直接变更文件：** 预计不改实现；读取/扫描 `core/`、`gui/`、`utils/`、`main.py`、`logging_system.py`、`CODEBASE.md` 和中文架构文档。若发现旧实现残留、旧路径引用、重复活实现、旧壳文件、stale 当前态文档，再做最小针对性修复并同步文档。
**预计连带影响：** 本轮重点不是重复行数验收，而是旧实现残留深查：旧文件是否仍存在、旧 import 是否回流、旧类/函数名是否仍作为活入口、旧 wrapper 是否仍在实现侧被依赖、是否有重复实现和当前态文档误导。验证仍需覆盖 py_compile、import smoke、旧路径扫描、文件存在扫描、调用方扫描、文档当前态扫描和残留目录/模块抽样。
### C. SYNC 结果

关键发现：
- (verified) 源码层旧 core/gui 壳文件不存在；旧路径 import 扫描无命中；GUI path hardcode 扫描无命中。
- (verified) 第一次深查发现 `core/`、`gui/` 下的 `__pycache__` 里还有旧模块 `.pyc`，例如旧顶层 core wrapper 和旧 GUI wrapper 的缓存。这不是源码实现，但属于旧运行产物残留；已删除 63 个 `__pycache__` 目录，并在重新编译后确认旧 `.pyc` 没有再生成。
- (verified) 深查发现几个真正的无行为旧 API 残留：`AppContext.load_global_config()` / `save_global_config()` 空 hook、`MapStitcher.set_merge_mode()` / `set_global_correction()` / `set_motion_smoothing()` / `set_repair_params()` 空方法、`PerformanceMonitor.print_report()` no-op、`SquareScreenCapture.capture_region()` 未调用兼容接口、`NavParametersDialog.set_config_to_ui(config, physical_center)` 的未用兼容参数。实现侧无调用方或可直接改调用点，已删除。
- (verified) 剩余 `legacy/compat` 命中只属于真实数据兼容：portal 事件旧配置 `feature_detector_enabled` 到 `detector_mode` 的迁移。它不是旧实现入口，保留可避免已有地图事件配置行为突变。
- (verified) 剩余 `pass` 命中都是预期异常吞掉：可选依赖 import fallback、Qt signal disconnect、已失效 QGraphicsItem 移除、模板匹配候选读取失败等；不是空壳实现。

实现变更：
- 删除 `gui/app_context.py` 中空的 `load_global_config()`、`save_global_config()` 以及初始化时的空调用。
- 删除 `core/mapping/stitcher.py` 中四个未调用空兼容方法。
- 删除 `core/mapping/performance.py` 中 no-op `print_report()`。
- 删除 `core/platform/screen_capture.py` 中未调用的 `capture_region()`。
- 简化 `gui/dialogs/nav_params_dialog.py::set_config_to_ui()` 签名为只接收 `config`，并同步更新 `navigation/calibration/lifecycle.py` 和 `navigation/map/load_lifecycle.py` 的调用点。
- 将 `HSVRecognizer` 和 `NavigationCore` 内部说明从 legacy/compat 表述改为 canonical/public constructor 表述，避免当前实现注释继续误导。

文档变更：
- 更新 `CODEBASE.md` 中 `AppContext`、`PerformanceMonitor`、`NavigationMapLoadLifecycle`、`NavigationScreenCalibrationLifecycle` 的当前态说明。
- 更新 `architecture_docs/zh-CN/gui/ARCHITECTURE.md` 和 `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`，记录 `AppContext` 空 config hooks 已删除。

验证：
- `Get-ChildItem -Path core,gui,utils ... py_compile` 通过。
- import smoke 通过，并额外断言旧空 API 均不存在：`AppContext.load_global_config/save_global_config`、`MapStitcher.set_merge_mode/set_global_correction/set_motion_smoothing/set_repair_params`、`PerformanceMonitor.print_report`、`SquareScreenCapture.capture_region`。
- `NavParametersDialog.set_config_to_ui` 签名断言为 `['self', 'config']`。
- 旧源码文件存在性扫描无输出。
- 旧 `.pyc` 精确路径扫描无输出。
- 旧 core/gui import 扫描无命中。
- GUI path hardcode 扫描无命中。
- 删除 API 调用方扫描无命中；`set_config_to_ui` 只剩新签名和一参调用。
- `git diff --check` 对本轮相关文件通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/`、`gui/` `__pycache__` | 存在旧 `.pyc` 残留 | 已清理并重新编译 | 1 | 删除 63 个缓存目录；重新编译后旧 wrapper `.pyc` 未再生成。 |
| `gui/app_context.py` | 有空全局配置 hook | 旧空 hook 已删除 | 追加 | `AppContext` 只持有 services 和 monitor state。 |
| `core/mapping/stitcher.py` | 有四个空兼容参数方法 | 空方法已删除 | 追加 | `MapStitcher` 仅保留真实建图/保存/渲染入口。 |
| `core/mapping/performance.py` | 有 no-op `print_report()` | no-op hook 已删除 | 追加 | `PerformanceMonitor` 只保留真实 timing 收集。 |
| `core/platform/screen_capture.py` | 有未调用 `capture_region()` | 兼容接口已删除 | 追加 | 保留 `capture_square()` 与 `capture()` 两个真实截图入口。 |
| `gui/dialogs/nav_params_dialog.py` | `set_config_to_ui` 有未用兼容参数 | 签名收窄 | 追加 | 调用方已改为一参，QSignalBlocker 行为不变。 |
| `CODEBASE.md` / 中文 GUI 文档 | 局部仍描述旧空 hook | 已同步 | 追加 | 当前态文档不再把空 hook 当保留项。 |

结论：
- 本轮确实发现并清除了旧运行产物和无行为旧 API 残留。
- 清理后 core/gui 实现侧没有旧壳文件、旧 import、旧顶层 `.pyc`、无调用空兼容方法或 GUI 路径硬编码残留。
- 保留的唯一 legacy 语义是 portal 配置数据迁移，属于兼容已有配置文件的主动转换，不是旧实现入口。

## [SYNC] 2026-05-28 19:49 - EVENT-HOOKS-VISIBLE-AND-COMPLETE
### A. SYNC 范围声明
**触发任务：** 用户要求新增两个 hook 机制：1）事件被识别且作为当前事件目标，并且事件出现在人物真实视野时触发；2）事件结束之后触发。具体 hook 内容后续自定义，本轮只建立机制和触发点。
**直接变更文件：** 预计读取/修改 `core/events/`、`core/navigation_tasks/`、`gui/modes/navigation/` 中事件观测、事件靠近、事件完成和 runtime 调用链相关文件；新增 hook 模块时必须放入功能 package，不能做扁平 helper。同步 `CODEBASE.md` 和中文架构文档/本日志。
**预计连带影响：** 需要确认“真实视野”当前由 event approach gate 判断还是 GUI viewport 判断；hook 应避免直接执行输入、避免引入 GUI 到 core 的反向依赖、默认无动作、可后续注册自定义处理器。实现后需跑非 tests/debug `py_compile`、import smoke、旧壳/import 扫描和 hook 触发点静态扫描。

### C. SYNC 结果

关键发现：
- (verified) “事件出现在人物真实视野”当前由 `core/navigation_tasks/event_approach/geometry.py::is_event_in_real_view()` 判定，并由 `event_approach/pipeline.py` 在 selected event task 的 approach gate 中使用；不是 GUI viewport overlay 判定。
- (verified) 当前 event handler 不直接执行输入，只返回 `EventAction`；`EventRunner.update()` 在 `COMPLETE` 时先写入 `EventMemory.mark_completed()` 或 `complete_teleport_session()`，再把 action 返回给 navigation task runner。
- (verified) 最小 hook 入口应放在 core 事件扩展包和 navigation task runner 的交界：`core/events/hooks/` 提供 registry/context，`NavigationTaskController.event_hooks` 持有 registry，`event_task_runner.py` 负责按触发点 emit。

实现变更：
- 新增 `core/events/hooks/` 功能包：`models.py` 定义 `event_visible_target`、`event_completed` 和 `EventHookContext`；`registry.py` 定义 `EventHookRegistry`，支持注册/注销/清空/派发，handler 异常只写事件日志；`__init__.py` 统一导出。
- `NavigationTaskController` 新增 `event_hooks = EventHookRegistry()`，作为后续 GUI/组合根注册自定义处理器的稳定入口。
- `EventApproachResult` 新增 `visible`、`became_visible`；`EventApproachController` 维护 `_visible_hook_tasks`，保证同一个 event navigation task 首次进入真实视野只触发一次。
- `event_task_runner.update_event_task()` 在 `became_visible=True` 时发出 `event_visible_target`；在 `EventActionType.COMPLETE` 且 memory 已更新后，完成导航侧清理并发出 `event_completed`。`FAIL` 仍只走失败终态，不发完成 hook。

文档同步：
- 更新 `CODEBASE.md`：新增 hook 文件目录说明、模块说明、`EventHookRegistry.register()/emit()` 行为说明、event approach 执行顺序和 GUI seam 当前态。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：生命周期 hooks 从提案改为当前最小实现，明确两个 hook 的触发语义和边界约束。
- 更新 `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md`：补充 `EventApproachResult.visible/became_visible`、`_visible_hook_tasks` 和 `_update_event_task()` 中两个 emit 点。
- 更新中文当前态文档中“hook 暂缓/未实现”的表述，改为“旧优化阶段未包含，当前后续阶段已新增 core 观察型 hook；GUI 暂未注册 handler”。

验证：
- 非 tests/debug `core/`、`gui/`、`utils/` 全量 `py_compile` 通过。
- import smoke 通过，覆盖 `MainWindow`、`AppContext`、core canonical 包入口、`EventCoordinator`、`PortalEventHandler` 和 `core.events.hooks`。
- hook registry smoke 通过：注册 `event_visible_target` 后 `emit()` 返回 1，handler 收到 `EventHookContext`。
- runner hook smoke 通过：模拟 `became_visible=True` 触发 `event_visible_target`，模拟 `EventAction.complete()` 触发 `event_completed`。
- 旧 core wrapper/import 扫描无命中；旧 GUI wrapper/import 扫描无命中。
- hook 触发点扫描只命中新 hook package、`NavigationTaskController.event_hooks`、`EventApproachResult.became_visible` 和 `event_task_runner` emit 点。
- 当前态中文文档 stale hook 文案扫描无命中；`git diff --check` 对本轮已跟踪文件通过。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/hooks/` | 新增 | 深度完整 | 1 | 新增观察型 hook package，默认 no-op，异常隔离，供后续自定义 handler 注册。 |
| `core/navigation_tasks/event_approach/*` | 无可见 hook 事实输出 | 已输出 `visible/became_visible` | 追加 | 真实视野 gate 仍不执行 handler/输入，只提供一次性可见事实。 |
| `core/navigation_tasks/event_task_runner.py` | 只翻译事件 action | 已增加两个 hook emit 点 | 追加 | selected event 首次进入真实视野发 `event_visible_target`，COMPLETE 后发 `event_completed`。 |
| `core/navigation_tasks/controller.py` | 无 hook registry | 已持有 `event_hooks` | 追加 | 后续 GUI/组合根可在 controller 上注册自定义 hook handler。 |
| `CODEBASE.md` / 中文架构文档 | hook 仍是后续设想/暂缓状态 | 已同步当前最小实现 | 追加 | 当前态文档明确 hook 边界、触发点和 GUI 暂未注册 handler。 |

结论：
- 两个 hook 机制已落地，均为观察型、默认无动作、异常隔离，不改变现有事件识别/导航/输入行为。
- 后续如果要自定义 hook 内容，应在 GUI 组合根或专门 adapter 中注册 handler，不应把具体 portal 行为或真实输入塞回 `NavigationTaskController`。

## [SYNC] 2026-05-28 20:24 - GUI-HOOK-INSTANCE-KEY-PRESS
### A. SYNC 范围声明
**触发任务：** 用户要求在现有两个 hook 触发点之上，新增可注册的 hook 事件实例机制；实例放入独立文件夹，GUI 可自由选择触发时机，一个实例可同时挂到多个 hook。当前先实现一个可自定义按键、按一下的 key press hook，并在事件管理中提供独立 hook 面板/页面。
**直接变更文件：** 预计读取/修改 `core/events/hooks/`、`core/navigation_tasks/event_task_runner.py`、`gui/dialogs/event_manager_dialog.py`、`gui/modes/navigation/events/`、`gui/modes/navigation/widget.py`、`gui/modes/navigation/input/`、`gui/modes/navigation/runtime/` 相关文件；新增 hook 实例 package 和 GUI hook 面板文件夹，避免扁平 helper。
**预计连带影响：** 需要确定 hook handler 注册发生在 GUI 组合根还是事件 dialog lifecycle；按键执行必须复用现有 `MotionController.press_key()` 边界，不让 core hook 直接依赖 GUI 或真实输入；GUI 保存/选择当前只做内存态，除非发现已有配置存储可复用；实现后需跑非 tests/debug `py_compile`、import smoke、hook 注册 smoke、旧壳/import 扫描和文档同步。

### C. SYNC 结果

关键发现：
- (verified) Hook 实例应分为三层：core trigger/registry 只描述生命周期事实，core instance 只描述可复用动作配置和回调协议，GUI runtime 负责把实例注册到当前 `NavigationTaskController.event_hooks` 并复用 `MotionController.press_key()` 执行真实按键。
- (verified) `EventSystemConfig` 已有 map-level `event_config.json` 持久化链路，可直接新增 `hooks.instances`，不需要新建另一套配置文件；点击事件管理窗口保存时会通过既有 `save_event_config()` 一并写入。
- (verified) 同一个 key_press 实例的 `triggers` 可以同时包含 `event_visible_target` 和 `event_completed`，运行时会分别注册到两个 hook name；触发时 `KeyPressHookInstance.__call__()` 再校验当前 hook 是否属于该实例。

实现变更：
- 新增 `core/events/hooks/instances/`：`key_press.py` 定义 `KeyPressHookSettings`、`KeyPressHookInstance`、配置 dict 解析/序列化和按键规范化；该实例只接收注入的 `press_key(key, reason)` 回调，不 import GUI 或平台输入。
- 扩展 `core/events/hooks/models.py`：新增 hook name 列表和中文展示标签，供 GUI 表头和配置过滤共用。
- 扩展 `core/events/config_model.py`：默认配置新增 `hooks.instances`，`EventSystemConfig` 新增 `hooks` 字段，`from_dict()/to_dict()` 保证 hooks 可加载、保存。
- 新增 `gui/modes/navigation/hooks/registration.py`：`NavigationHookRuntime.apply_event_config()` 先注销上一轮 handler，再按配置把 enabled key_press 实例注册到所选 triggers；按键执行通过 `enable_game_input_mode()`、`motion_controller.set_control_enabled(True)`、`motion_controller.press_key()` 完成。
- 新增 `gui/dialogs/event_manager/hooks/panel.py`：事件管理窗口独立 Hooks 页，支持新增/删除 key_press 实例，编辑启用、名称、按键，并分别勾选“事件进入真实视野”和“事件完成之后”。
- 修改 `gui/dialogs/event_manager_dialog.py` 和 `gui/modes/navigation/widget.py`：事件管理窗口使用“事件 / Hooks”分页；Hook 面板变化发出 `config_changed`，导航页收到后重新应用 hook runtime。

文档同步：
- 更新 `CODEBASE.md`：补充 hook 实例包、GUI hook runtime、事件管理 Hooks 页、`NavigationHookRuntime.apply_event_config()`、`KeyPressHookInstance.__call__()` 和相关 Flow。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：补充 `hooks/instances/key_press.py`、`hooks.instances` JSON 示例和 key_press 边界。
- 更新 `architecture_docs/zh-CN/gui/ARCHITECTURE.md`、`architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`、`architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`、`architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md` 和 core 相关计划文档，移除“GUI 暂未注册 handler / Hook 暂缓”的当前态表述。

验证：
- 非 tests/debug `core/`、`gui/`、`utils/` 全量 `py_compile` 通过。
- import smoke 通过，覆盖 `NavigationModeWidget`、`NavigationHookRuntime`、`EventHookPanel`、`EventSystemConfig`、core hook 常量和 `KEY_PRESS_HOOK_TYPE`。
- hook 注册 smoke 通过：一个 key_press 实例同时注册到 `event_visible_target` 和 `event_completed`，两次 `emit()` 均通过 fake `MotionController.press_key()` 记录到 `f` 按键。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。
- stale hook 当前态文档扫描无命中。
- `git diff --check` 对本轮相关文件通过，仅提示既有 LF/CRLF 工作区警告。
- 清理编译生成的 68 个 `__pycache__` 目录，复查剩余数量为 0。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/hooks/instances/key_press.py` | 新增 | 深度完整 | 1 | key_press hook 实例只保存配置和回调协议，真实输入由 GUI runtime 注入。 |
| `gui/modes/navigation/hooks/registration.py` | 新增 | 深度完整 | 1 | 将 `event_config.hooks.instances` 注册到 core hook registry，并复用 `MotionController.press_key()`。 |
| `gui/dialogs/event_manager/hooks/panel.py` | 新增 | 深度完整 | 1 | 独立 Hooks 页只编辑配置，不直接注册 handler 或执行输入。 |
| `gui/dialogs/event_manager_dialog.py` | 事件管理单页 | 已同步 Hooks 分页 | 追加 | 对话框转为“事件 / Hooks”分页，Hook 配置变化走既有 `config_changed` 链路。 |
| `gui/modes/navigation/widget.py` | 无 hook runtime | 已挂接 hook runtime | 追加 | 地图事件系统初始化和事件配置变化时重新应用 hook 注册。 |
| `core/events/config_model.py` | 无 hooks 字段 | 已支持 `hooks.instances` | 追加 | 复用 map-level event config 持久化，无需新配置文件。 |

结论：
- 本轮已完成首个可配置 hook 实例：按键 hook 可在 GUI 独立 Hooks 页新增、编辑按键、选择一个或两个触发时机，并在事件配置保存链路中持久化。
- 当前只实现“按一下”；长按、组合键、延迟、条件过滤、脚本回调等都保留为后续 hook instance 类型或 settings 扩展，不挤进本次最小实现。

## [SYNC] 2026-05-28 21:01 - GUI-HOOK-EVENT-BINDING
### A. SYNC 范围声明
**触发任务：** 用户指出 hook 还需要选择和哪个事件绑定，不能所有事件都触发 hook。当前要在 key_press hook 实例上增加事件类型过滤，让一个实例可绑定一个或多个事件类型，并继续独立选择 hook 触发时机。
**直接变更文件：** 预计读取/修改 `core/events/hooks/instances/key_press.py`、`gui/dialogs/event_manager/hooks/panel.py`、`gui/dialogs/event_manager_dialog.py`、`gui/modes/navigation/hooks/registration.py`、`core/events/config_model.py`，并同步 `CODEBASE.md` 和中文架构文档。
**预计连带影响：** `EventHookContext.event_type` 已存在，可直接作为过滤字段；GUI hook 面板需要知道当前事件 registry/config 里的可用事件类型；配置需要保存 `event_types` 字段。默认新建 key_press hook 应绑定当前可用事件而不是所有事件，避免后续新增事件类型时误触发。实现后运行 py_compile、import/hook smoke、旧壳扫描和文档 stale 扫描。

### C. SYNC 结果

关键发现：
- (verified) `EventHookContext.event_type` 已由 `event_task_runner.update_event_task()` 在两个 hook emit 点填充，适合作为 hook 实例事件绑定过滤字段。
- (verified) 事件管理窗口已经通过 `build_tui_event_options()` 拿到完整事件包列表，Hook 面板可以复用这份列表动态生成事件绑定列，不需要硬编码 `portal`。
- (verified) 缺少 `event_types` 的 key_press 配置如果继续按旧行为执行，会在后续新增事件类型时误触发；本轮改为不注册、不执行。

实现变更：
- `core/events/hooks/instances/key_press.py`：`KeyPressHookSettings` 新增 `event_types`；配置解析支持 `event_types` 列表，也兼容读取旧的单数 `event_type`；`KeyPressHookInstance.__call__()` 在 hook name 命中后继续校验 `context.event_type`。
- `gui/modes/navigation/hooks/registration.py`：`apply_event_config()` 只注册同时具备 enabled、key、`event_types` 和 `triggers` 的 key_press 实例。
- `gui/dialogs/event_manager/hooks/panel.py`：Hook 表格改为动态列，基础列为启用/名称/类型/按键，随后按当前完整事件列表生成事件类型勾选列，最后是两个 hook 触发时机列。新增 key_press hook 默认绑定第一个可用事件。
- `gui/dialogs/event_manager_dialog.py`：刷新 Hooks 页时把当前 `_event_options` 传入 Hook 面板。

文档同步：
- 更新 `CODEBASE.md`：记录 `event_types` 绑定语义、GUI 动态事件列、runtime 跳过无事件绑定实例、`KeyPressHookInstance.__call__()` 的事件过滤步骤。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：JSON 示例新增 `"event_types": ["portal"]`，并明确空 `event_types` 不注册执行。
- 更新 GUI/core 中文计划文档：key_press hook 当前为事件类型 + 触发时机双重绑定。

验证：
- 局部 `py_compile` 通过：`key_press.py`、`registration.py`、`panel.py`、`event_manager_dialog.py`。
- key_press 事件绑定 smoke 通过：同一实例绑定 `portal` 后，`event_type="portal"` 的 visible/completed 两次触发按键，`event_type="other"` 不触发。
- 缺少 `event_types` 的旧形态配置 smoke 通过：`NavigationHookRuntime.apply_event_config()` 返回 0，不注册 handler。
- GUI Hook 面板 offscreen smoke 通过：新增 hook 默认写入 `event_types=["portal"]`，动态列数符合基础列 + 事件列 + 两个触发列。
- 非 tests/debug `core/`、`gui/`、`utils/` 全量 `py_compile` 通过。
- import smoke 通过，覆盖 `NavigationModeWidget`、`NavigationHookRuntime`、`EventHookPanel`、`EventSystemConfig`、core hook 常量和 `KEY_PRESS_HOOK_TYPE`。
- 旧 core 顶层 wrapper import 扫描无命中；旧 GUI wrapper import 扫描无命中。
- stale hook 扫描没有旧“暂缓/未注册 handler”表述；唯一含“所有事件”的命中是“不会默认对所有事件触发”的当前正确说明。
- `git diff --check` 对本轮相关文件通过，仅提示既有 LF/CRLF 工作区警告。
- 清理编译生成的 69 个 `__pycache__` 目录，复查剩余数量为 0。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/hooks/instances/key_press.py` | 只按 hook 时机过滤 | 已加入事件类型过滤 | 追加 | `event_types` 为空不触发，避免默认全事件。 |
| `gui/modes/navigation/hooks/registration.py` | 注册 enabled/key/triggers 实例 | 已要求 `event_types` | 追加 | 无事件绑定的实例不进入 registry。 |
| `gui/dialogs/event_manager/hooks/panel.py` | 只编辑按键和触发时机 | 已支持动态事件绑定列 | 追加 | 根据事件管理窗口的完整事件列表生成 checkbox 列。 |
| `gui/dialogs/event_manager_dialog.py` | Hook 面板只接收 config | 已传入 `_event_options` | 追加 | Hook 页与事件列表共享同一份完整事件包来源。 |
| `CODEBASE.md` / 中文架构文档 | hook 默认语义不完整 | 已同步事件绑定语义 | 追加 | 明确 key_press 是事件类型 + hook 时机双重绑定。 |

结论：
- key_press hook 已不再对所有事件生效；必须在 Hooks 页勾选具体事件类型，同时勾选触发时机，才会在对应事件生命周期点执行。
- 后续新增事件类型时，旧 hook 不会因为只配置了触发时机而自动作用到新事件。

## [PLAN] 2026-05-28 21:41 - LOOT-PICKUP-EVENT-DESIGN
### A. 规划阅读范围声明
**触发任务：** 用户要求规划一个新的掉落物拾取事件：掉落物图标多样且可能堆叠，不要求逐个精准标记，只需识别“这块有掉落物”，定位后像锚点一样用 A* 导航过去，进入拾取范围后按 A，视野内没有掉落物则结束，并处理与其他事件的执行顺序冲突和地图显示消失/已拾取状态。
**目标文件/目录：**
- `core/events/types/portal/`：参考现有事件包结构、detector/handler/config/schema 拆分方式。
- `core/events/`、`core/navigation_tasks/`：确认事件 memory、scheduler、event task、approach gate、完成态和 overlay 的复用边界。
- `gui/modes/navigation/`、`gui/dialogs/event_manager_dialog.py`：确认 GUI 事件配置和 overlay 展示可复用点。
- `D:/ACloud/image/掉落`：粗看掉落物图标素材形态，判断检测策略。
**本轮想弄清楚：** 掉落物事件应复用哪些 portal/event 基础设施；检测应优先模板/颜色/聚类中的哪条路线；拾取行为应放在 event handler 还是 hook；与 portal/其它事件冲突时应如何排优先级；“消失/已拾取”应由 memory、cooldown 还是 detector absence 驱动。

### C. 规划阅读结果

关键发现：
- (verified) 默认事件注册点在 `gui/modes/navigation/event_adapter.py::create_default_event_registry()`，当前只注册 `PortalEventDefinition()`；掉落物应新增 `LootEventDefinition()` 并注册到同一 registry。
- (verified) 事件包最小结构已经清晰：`definition.py` 暴露 `event_type/default_config/config_schema/create_detector/create_handler`；detector 返回 `EventDetection(local_minimap_pos)`；`EventPositionStabilizer` 复用 frame registration 把小地图局部坐标投影成全局坐标；`EventMemory` 合并 observations 并生成 `EventTask`。
- (verified) 事件冲突已有两层排序：`EventScheduler.pick()` 在 event memory 内按 priority、距离、first_seen 选择展示/状态任务；`NavigationTaskScheduler.pick()` 把 dynamic event tasks 和 required/exit 静态任务按路线进度窗口合并排序，并用 priority 参与同路线窗口内的选择。running event task 会被 active lock 保持，避免执行中频繁切换。
- (verified) portal handler 的移动/交互拆分可复用思路：`movement.py` 按距离返回 `EventAction.move_to()`，`interaction.py` 到达后返回 `EventAction.press_key()`，`completion.py` 决定完成/失败。掉落物 handler 应更简单：靠近拾取范围 -> 按 `A` -> 短等待 -> 通过“视野/小地图检测不到该聚类”或 nearby suppression 完成。
- (verified) 现有 overlay 通过 `EventCoordinator.overlays()` 和 `gui/modes/navigation/presentation/event_overlay.py` 渲染 event tasks；completed/ignored 会灰色显示。掉落物“没有就消失/已拾取”可先走 memory 完成/忽略状态和 overlay 过滤/灰显策略，不需要单独 UI 系统。
- (verified) `D:/ACloud/image/掉落` 当前有 6 张模板，尺寸约 38x49 到 104x86，颜色/形状差异明显，且用户给出的堆叠图会导致单模板精确匹配不稳定；检测应以“区域级有掉落物”为目标，而不是逐个图标实例精确匹配。

初步设计结论：
- 掉落物应作为正式事件类型 `loot`，不是 hook。hook 适合额外动作扩展；掉落物需要识别、定位、导航、执行、完成态和冲突排序，属于 event package。
- 第一版检测推荐“多模板候选 + 颜色/亮度/边缘区域聚类 + NMS 合并”为主，不要求每个掉落物都单独标记。检测输出一个或少数区域中心点，后续由 position stabilizer 和 memory 做跨帧稳定。
- 第一版执行推荐复用 `EventAction.move_to()` 和 `EventAction.press_key("a")`，不直接调用 `MotionController`。

下一步计划：
- 等用户确认冲突优先级策略后，把设计整理成正式计划文档，再进入 implementation plan。

## [PROTOTYPE] 2026-05-28 21:58 - LOOT-DETECTION-WEIGHTED-PROBE
### A. 原型范围声明
**触发任务：** 用户确认掉落物只需要小地图识别，并要求先测试识别算法，按传送门同类思路从外形、颜色、模板匹配三个方向加权。
**直接变更文件：** 预计新增一次性原型脚本 `debug/loot_detection_prototype.py`，不接入正式 `core.events.types.loot`，不改生产事件链路。原型运行可在 `debug/loot_detection_probe/` 生成合成输入图和标注输出图。
**预计连带影响：** 该脚本只用于验证算法可行性：读取 `D:/ACloud/image/掉落` 模板；若未传入真实小地图图像，则自动合成堆叠样例；输出候选的 template/shape/color/weighted 分数和 NMS 后区域。验证后再决定正式 detector 的配置参数和模块拆分。
## [SYNC] 2026-05-28 22:20 - LOOT-PICKUP-EVENT-FORMAL-INTEGRATION
### A. SYNC 范围声明
**触发任务：** 用户确认按当前“小地图模板/外形/颜色加权 + blob 合并”算法正式接入项目，并要求提供单独测试入口，重点覆盖识别、导航、按 A、拾取半径参数。
**直接变更文件：** 预计新增 `core/events/types/loot/` 正式事件包，包含配置、模板资产、加权 blob 检测、EventDetection 转换、拾取 handler；修改默认事件注册与事件配置模型；新增独立 debug/smoke 探针用于检测与 handler 行为验证；同步 `CODEBASE.md` 和中文架构文档。
**预计连带影响：** `gui/modes/navigation/event_adapter.py::create_default_event_registry()` 会新增 `LootEventDefinition()`，事件管理 GUI 应自动出现 `loot` 配置；`EventTask` 调度、位置稳定、overlay、hook 事件过滤复用既有链路；handler 只返回 `EventAction.move_to()` / `press_key("a")` / `complete()`，真实输入仍由 navigation runner 执行；拾取半径、到达半径、按键、等待、重试、缺失确认都放入 loot config。

### C. SYNC 结果

关键发现：
- (verified) `loot` 已作为正式事件类型接入 registry；默认 registry 输出 `['portal', 'loot']`。
- (verified) 掉落物模板已复制到项目内 `assets/event_templates/loot/minimap/`，正式 detector 不依赖 `D:/ACloud/image/掉落` 外部路径。
- (verified) production detector 在 `D:/ACloud/image/test` 两张测试图上均输出 1 个 `loot` detection，分数分别约 `0.60` 和 `0.69`。
- (verified) `pickup_radius` 不只在 handler 内判断，还会通过 detection metadata -> EventTask metadata -> NavigationTask metadata `event_stop_radius` 进入 `EventApproachController`，控制通用事件靠近层何时释放 handler。

实现变更：
- 新增 `core/events/types/loot/`：`LootEventDefinition`、`LootEventConfig`、`LootMinimapDetector`、`detection/` 加权 blob 检测模块和 `handler/` 拾取状态机。
- 修改 `gui/modes/navigation/event_adapter.py`：默认注册 `LootEventDefinition()`。
- 修改 `core/events/config_model.py`：新增 `events.loot` 默认配置。
- 修改 `core/navigation_tasks/task_builder.py` 和 `core/navigation_tasks/event_approach/*`：支持事件任务级 `event_stop_radius`，当前用于 loot 拾取半径。
- 修改 `gui/dialogs/event_manager_dialog.py`：事件配置摘要加入 loot 关键参数。
- 新增 `debug/loot_event_probe.py`：单独调用生产 detector/handler，输出 JSON 和 overlay。
- 新增 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`，并同步 `CODEBASE.md`、事件架构文档和导航任务架构文档。

验证：
- `py_compile` 覆盖新增 loot 包、修改的 event adapter、config model、task builder、event approach 和 debug probe。
- import smoke：`create_default_event_registry()` 返回 `portal` 和 `loot`；`EventSystemConfig.default().event("loot")` 有 `pickup_radius=58`、`pickup_key="a"`。
- production probe：`D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --handler-smoke` 通过；两张测试图均识别，handler smoke 输出 `move_to -> press_key(a) -> wait -> complete`。
- 半径链路 smoke：构造 `loot` EventTask 且 metadata `pickup_radius=72` 时，`NavigationTaskBuilder` 输出 `radius=72.0`、`event_stop_radius=72.0`。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/loot/` | 新增 | 深度完整 | 1 | 正式事件包，含检测、转换、配置和 handler 状态机。 |
| `assets/event_templates/loot/minimap/` | 新增 | 已接入 | 1 | 项目内模板资产，避免外部绝对路径依赖。 |
| `gui/modes/navigation/event_adapter.py` | 只注册 portal | 已注册 portal+loot | 追加 | GUI 事件管理和 EventMonitor 可枚举 loot。 |
| `core/events/config_model.py` | 默认配置只含 portal | 已含 loot defaults | 追加 | 识别阈值、拾取半径、按键、等待和 cooldown 已可配置。 |
| `core/navigation_tasks/task_builder.py` / `event_approach/` | 全局事件停靠半径 | 支持 per-task event_stop_radius | 追加 | loot 使用 pickup_radius 作为通用靠近层释放半径，portal 不变。 |
| `debug/loot_event_probe.py` | 新增 | 深度完整 | 1 | 单独验证 production detector 和 handler 行为。 |

结论：
- 掉落物识别算法已正式接入生产事件系统；当前不是一次性原型。
- `image/test` 两张样例可以识别；真实运行仍建议通过 GUI 参数或 probe 调整阈值/拾取半径。
## [SYNC] 2026-05-28 23:16 - LOOT-PLAYER-MARKER-FALSE-POSITIVE
### A. SYNC 范围声明
**触发任务：** 用户指出当前掉落物检测会把人物/玩家箭头图标识别成掉落物，需要在不破坏已有掉落物样本识别的前提下加入人物标记排除逻辑。
**直接变更文件：** 预计读取/修改 `core/events/types/loot/config.py`、`core/events/types/loot/assets.py`、`core/events/types/loot/minimap_detector.py`、`core/events/types/loot/detection/pipeline.py`、`core/events/types/loot/detection/scoring.py`，必要时新增 `core/events/types/loot/detection/exclusions.py`，并同步 `debug/loot_event_probe.py` 验证入口、`CODEBASE.md` 和中文 loot 架构文档。
**预计连带影响：** 掉落物候选生成阶段需要新增负样本/人物箭头 gate；`LootMinimapDetector` 需要加载排除模板或形状规则；`LootEventConfig` 需要新增开关和阈值；已有 `image/test` 正样本应继续输出 loot detection，人物标记样本应输出 0 个 detection。

### C. SYNC 结果

关键发现：
- (verified) 误判可复现：`D:/ACloud/image/人物/0b799b87-9b87-4458-b026-5d7df13da763.png` 在旧算法下输出 1 个 `loot` detection，位置约 `(9,15)`，分数约 `0.68`。
- (verified) 误判不是纯颜色问题。旧分数中 `template_score≈0.77`、`shape_score≈0.34`、`color_score=1.00`，说明人物箭头同时命中了某个正向掉落模板；因此只提高总阈值或只降低颜色权重都不够稳。
- (verified) 两张掉落正样本在修复前均可识别，作为回归正样本保留。

实现变更：
- 新增 `assets/event_templates/loot/exclude/player_marker/0b799b87-9b87-4458-b026-5d7df13da763.png`，把人物箭头样本纳入项目内负样本资产，正式运行不依赖外部 `D:/ACloud/image/人物`。
- 新增 `core/events/types/loot/detection/exclusions.py`，实现人物箭头排除 gate：负模板匹配、蓝色玩家底色比例、金白箭头/三角形轮廓评分。
- 修改 `LootMinimapDetector` 和 `detection.pipeline`，只在候选已通过正向掉落物分数后执行人物箭头排除；排除逻辑不会改变拾取 handler 或导航任务链路。
- 修改 `LootEventConfig`、默认事件配置和 GUI schema：默认权重改为 `template_weight=0.46`、`shape_weight=0.42`、`color_weight=0.12`，颜色变为辅助信号；新增 `player_marker_*` 排除参数。
- 对旧地图配置中仍保存的旧默认权重 `0.40/0.34/0.26` 做兼容迁移：若配置里没有 `player_marker_exclusion_enabled`，则自动使用新默认权重。

验证：
- 人物箭头负样本：`debug/loot_event_probe.py --image D:/ACloud/image/人物/0b799b87-9b87-4458-b026-5d7df13da763.png` 输出 `detection_count=0`。
- 正样本 1：`D:/ACloud/image/test/004a0390f7bd1283293295aa2da18f3c.png` 输出 1 个 `loot` detection，分数约 `0.58`。
- 正样本 2：`D:/ACloud/image/test/620a06ae5e363165b735820e99ea4d8e.png` 输出 1 个 `loot` detection，分数约 `0.62`。
- `debug/loot_event_probe.py --handler-smoke` 通过，handler 链路仍为 `move_to -> press_key(a) -> wait -> complete`。
- 局部 `py_compile` 通过，覆盖 loot 包、事件默认配置、事件管理 GUI 和正式探针。
- 清理编译/探针产生的 72 个 `__pycache__` 目录。

文档同步：
- `CODEBASE.md` 顶部 loot 补充已记录新权重、负样本资产和人物箭头排除 gate。
- `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md` 已补充 `exclusions.py`、人物箭头负样本算法、参数表、负样本验证命令和剩余风险。

### C. SYNC 结果

关键发现：
- (verified) 误判可复现：`D:/ACloud/image/人物/0b799b87-9b87-4458-b026-5d7df13da763.png` 在旧算法下输出 1 个 `loot` detection，三路分数约为 `template=0.77`、`shape=0.34`、`color=1.00`，说明不是纯颜色误判，正向模板也贡献了高分。
- (verified) 两张真实掉落物正样本在旧算法下均输出 1 个 detection；修正必须保持它们继续可识别。
- (verified) 真实掉落物与人物箭头都可能呈三角/菱形外形，因此负模板或三角形规则不能单独一票否决；人物箭头更稳定的区分信号是蓝/青色玩家底色，正样本蓝色比例为 0，人物箭头蓝色比例约 0.606。

实现变更：
- 新增 `assets/event_templates/loot/exclude/player_marker/0b799b87-9b87-4458-b026-5d7df13da763.png`，把人物箭头负样本纳入项目资产，正式运行不依赖外部 `D:/ACloud/image/人物`。
- 新增 `core/events/types/loot/detection/exclusions.py`，实现 `is_player_marker_candidate()`、负模板匹配、蓝色玩家底色统计和金白区域箭头/三角形外形评分。
- 修改 `core/events/types/loot/config.py`：默认权重改为 `template_weight=0.46`、`shape_weight=0.42`、`color_weight=0.12`，新增 `player_marker_exclusion_enabled`、`player_marker_template_threshold`、`player_marker_exact_template_threshold`、`player_marker_blue_ratio_threshold`、`player_marker_triangle_score_threshold`；对未带人物排除字段且仍使用旧默认权重 `0.40/0.34/0.26` 的旧配置自动迁移到新默认权重。
- 修改 `core/events/types/loot/assets.py` 和 `minimap_detector.py`：加载人物箭头排除模板，并传入 `detect_loot_blobs()`。
- 修改 `core/events/types/loot/detection/pipeline.py`：候选先通过正向模板/外形/颜色加权，再进入人物箭头排除 gate；被排除候选不会进入 clustering。
- 修改 `core/events/config_model.py`、`core/events/types/loot/definition.py`、`gui/dialogs/event_manager_dialog.py`：同步新默认配置、GUI schema 和摘要字段。

验证：
- `D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png`：修正后 `detection_count=0`。
- `D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\004a0390f7bd1283293295aa2da18f3c.png`：修正后 `detection_count=1`，best score 约 `0.58`。
- `D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\620a06ae5e363165b735820e99ea4d8e.png`：修正后 `detection_count=1`，best score 约 `0.62`。
- `D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --handler-smoke`：通过，仍输出 `move_to -> press_key(a) -> wait -> complete`。
- 局部 `py_compile` 覆盖本轮修改的 loot、config、GUI summary 和 debug probe 文件，通过。

文档同步：
- 更新 `CODEBASE.md`：补充 loot 新权重、人物箭头负样本资产、排除 gate 和关键参数。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：补充 `detection/exclusions.py`、负样本路径、算法步骤、参数表、验证命令和风险。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：补充 loot 识别现在以模板/外形为主、颜色为辅，并有人物箭头排除。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/loot/detection/exclusions.py` | 新增 | 深度完整 | 1 | 人物箭头负模板、蓝色底色和箭头外形排除规则。 |
| `core/events/types/loot/detection/pipeline.py` | weighted blob 主流程 | 已加入排除 gate | 追加 | 正向候选通过后再排除，不影响未通过候选的评分链路。 |
| `core/events/types/loot/config.py` | 旧默认权重 | 已迁移新权重和排除参数 | 追加 | 旧默认权重配置自动迁移，新配置保留用户自定义。 |
| `core/events/types/loot/minimap_detector.py` | 只加载正向模板 | 已加载正向+负样本模板 | 追加 | detector 日志包含 exclusion template 数量。 |
| `assets/event_templates/loot/exclude/player_marker/` | 新增 | 已接入 | 1 | 当前包含 1 张人物箭头负样本，后续可继续扩充。 |
## [SYNC] 2026-05-28 23:27 - LOOT-DETECTOR-PERFORMANCE
### A. SYNC 范围声明
**触发任务：** 用户反馈启用拾取事件后整体变卡，需要优化 loot 掉落物检测的运行时资源占用，同时保持人物箭头误判修复和现有掉落物识别能力。
**直接变更文件：** 预计读取/修改 `core/events/types/loot/config.py`、`core/events/types/loot/definition.py`、`core/events/types/loot/minimap_detector.py`、`core/events/types/loot/detection/pipeline.py`、`core/events/config_model.py`、`debug/loot_event_probe.py`，并同步 `CODEBASE.md` 和中文 loot 架构文档。
**预计连带影响：** 需要建立 detector 单帧耗时基线；优先减少全图多尺度模板匹配次数和昂贵 masked color full-frame matching；必要时加入检测间隔/缓存，但不能让 handler 的缺失确认因为跳帧误判完成。

### C. SYNC 结果

关键发现：
- (verified) 卡顿主因不是事件调度或 handler，而是 `detection.pipeline.detect_loot_candidates()` 对整张小地图执行 6 个模板 * 5 个尺度 * 灰度/边缘/masked color 的 full-frame matching。旧基准中 `blank300` 约 1248ms，`positive300` 约 1269ms，`player300` 约 1272ms。
- (verified) 第一轮 ROI 后，空帧已经降到亚毫秒级，但正样本扫描峰值仍在 180-220ms；继续计时确认瓶颈是 masked full-response 和人物排除 gate 重复负模板匹配。
- (verified) 004 正样本依赖 mask 彩色信号补分；因此不能简单关闭 masked color，而应从 full-frame response 改成命中点 patch 局部补分。
- (verified) 人物排除 gate 的稳定区分信号是蓝/青玩家底色；真实掉落物正样本蓝色比例为 0，因此可以先用蓝底色快速过滤，避免正样本候选进入昂贵负模板匹配。

实现变更：
- 新增 `core/events/types/loot/detection/roi.py`：实现 `loot_roi_bboxes()`、HSV 颜色/亮度 ROI mask、连通域过滤、bbox 扩张、bbox 合并和模板最小尺寸保护。
- 修改 `core/events/types/loot/detection/models.py`、`templates.py`：新增 `LootPreparedTemplate` 并预生成多尺度模板的 BGR、mask、灰度、Canny 边缘和像素统计。
- 修改 `core/events/types/loot/detection/pipeline.py`：默认先跑 ROI 预筛；ROI 为空时直接返回；ROI 内先做灰度/边缘响应图，再对命中 patch 用 `masked_patch_score()` 做局部 mask 彩色余弦相似度补分，不再做 full-frame/whole-ROI masked response。
- 修改 `core/events/types/loot/detection/exclusions.py`：人物排除先检查蓝/青玩家底色；无蓝底色直接跳过负模板和三角形重判断；负模板输入支持已预处理模板。
- 修改 `core/events/types/loot/minimap_detector.py`：正向模板和人物负模板都在 detector 初始化或 scales 变化时预处理；新增 `detection_interval_ms` 缓存，间隔内可复用上一帧 detection 并重新打时间戳。
- 修改 `core/events/types/loot/config.py`、`core/events/config_model.py`、`core/events/types/loot/definition.py`、`gui/dialogs/event_manager_dialog.py`：补齐 ROI、检测间隔、masked 局部补分相关默认配置、GUI schema 和摘要字段。
- 修改 `LootEventConfig.from_dict()` 和 `EventSystemConfig.from_dict()`：旧 loot 配置若还没有 `roi_prefilter_enabled` 字段，会迁移到当前性能默认；显式带 ROI 字段的新配置保留用户选择。
- 修改 `debug/loot_event_probe.py`：新增 `--benchmark`，可直接输出 `positive_tiny`、`blank300`、`positive300`、`player300` 的平均耗时、峰值耗时和 detection 数。

验证：
- `py_compile` 覆盖 `roi.py`、`pipeline.py`、`exclusions.py`、`minimap_detector.py`、`config.py`、`config_model.py`、`definition.py`、`event_manager_dialog.py`、`debug/loot_event_probe.py`，通过。
- `debug/loot_event_probe.py --image D:\ACloud\image\test\004a0390f7bd1283293295aa2da18f3c.png`：`detection_count=1`，best score 约 `0.58`。
- `debug/loot_event_probe.py --image D:\ACloud\image\test\620a06ae5e363165b735820e99ea4d8e.png`：`detection_count=1`，best score 约 `0.62`。
- `debug/loot_event_probe.py --image "D:\ACloud\minimap_stitcher copy 13\assets\event_templates\loot\exclude\player_marker\0b799b87-9b87-4458-b026-5d7df13da763.png"`：`detection_count=0`。
- `debug/loot_event_probe.py --benchmark --handler-smoke`：默认缓存下 `blank300` 平均约 `0.25ms`，`positive300` 平均约 `6.24ms`，`player300` 平均约 `6.37ms`；handler smoke 仍为 `move_to -> press_key(a) -> wait -> complete`。
- 强制每帧扫描配置 `detection_interval_ms=0`、`reuse_previous_detections=False`：`blank300` 平均约 `1.08ms`，`positive300` 平均约 `27.05ms`，`player300` 平均约 `29.81ms`。
- 旧配置迁移 smoke：未带 `roi_prefilter_enabled` 且旧存 `masked_color_match_enabled=false` 的 loot 配置会得到 `masked_color_match_enabled=True`、`roi_prefilter_enabled=True`、`detection_interval_ms=450`；显式带 `roi_prefilter_enabled=false` 的配置保持 false。

文档同步：
- 更新 `CODEBASE.md`：记录 ROI 预筛、模板预处理、局部 mask 补分、蓝底色快速排除、检测间隔缓存和 benchmark 命令。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：补充 `roi.py`、完整性能版算法步骤、配置表、性能基准和新风险。

覆盖进度更新：
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/loot/detection/roi.py` | 新增 | 深度完整 | 1 | 低成本 ROI 预筛，负责空帧快速返回和局部重匹配范围收缩。 |
| `core/events/types/loot/detection/pipeline.py` | full-frame 多路匹配 | 已改为 ROI + 局部 masked 补分 | 追加 | 保留模板/外形/颜色三路评分，但移除整图 masked response。 |
| `core/events/types/loot/detection/exclusions.py` | 候选通过后直接重排除 | 已加入蓝底色快速 gate | 追加 | 正样本不再进入负模板重匹配，人物图标仍能被排除。 |
| `core/events/types/loot/minimap_detector.py` | 只预处理正向模板 | 已预处理正向+负样本模板并缓存 detection | 追加 | scales 或 masked 配置变化时刷新 prepared templates。 |
| `debug/loot_event_probe.py` | 单图/handler smoke | 已加入 benchmark | 追加 | 可复现性能基准和正负样本回归。 |

## [SYNC] 2026-05-29 00:50 - LOOT-TRANSPARENT-TEMPLATES-AND-PLAYER-THRESHOLD

触发任务：用户指出人物箭头模板和掉落物模板中的背景应忽略，建议直接把 `assets/event_templates/loot` 中的模板图扣成透明背景；随后要求人物排除阈值降到 `0.75`，并可在 UI 页面调整。

关键发现：
- (verified) 旧 `foreground_mask()` 会把模板截图里的地图背景纳入前景，导致人物箭头、地图边线和掉落物模板互相借背景/颜色得到高分。
- (verified) 仅把 `player_marker_template_threshold` 降到 `0.75` 会误杀两张 `D:/ACloud/image/test` 正样本；因此排除条件必须同时包含结构分数，不能只看 mask 彩色相似度。
- (verified) 事件管理 GUI 已通过 `LootEventDefinition.config_schema()` 的 float 字段自动生成 `QDoubleSpinBox`，`player_marker_template_threshold` 可以在 UI 中调整。

实现变更：
- `assets/event_templates/loot/minimap/*.png` 与 `assets/event_templates/loot/exclude/player_marker/*.png` 已从 `D:/ACloud/image/掉落` / `D:/ACloud/image/人物` 原始素材重新生成透明 PNG；运行时 alpha 通道作为模板 mask。
- `core/events/types/loot/detection/images.py` 新增 alpha 优先的前景 mask、图标前景扣图 fallback、背景连通域过滤和小图 padding 坐标保护。
- `core/events/types/loot/detection/templates.py` 读取模板时保留 alpha mask 语义，并让边缘图只保留 mask 附近的边缘。
- `core/events/types/loot/detection/pipeline.py` 在响应图中加入 mask template response，同时保留灰度/边缘响应；正向通过后增加蓝色地图装饰过滤。
- `core/events/types/loot/detection/exclusions.py` 将人物排除拆成 `template_score` 与 `structure_score`：默认阈值为 `0.75`，但必须有足够灰度/边缘结构分数；蓝底人物可以用较低结构阈值，非蓝底人物仍可通过结构分数排除；纯测试 padding 不触发人物排除。
- `core/events/types/loot/config.py`、`core/events/config_model.py`、`core/events/types/loot/definition.py` 同步默认 `player_marker_template_threshold=0.75`，GUI schema 默认值同步为 `0.75`。

验证：
- `debug/loot_event_probe.py --test-dir D:\ACloud\image\test`：两张正样本均 `detection_count=1`，best score 约 `0.63` / `0.65`。
- `debug/loot_event_probe.py --image D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png`：`detection_count=0`，不再把人物箭头识别成掉落物。
- `debug/loot_event_probe.py --image D:\ACloud\image\bc314efc-1f1e-4770-ae81-c410fb1d1e72.png`：`detection_count=0`。
- `debug/loot_event_probe.py --image D:\ACloud\image\fd4615e6-a089-403f-b2aa-26fceeafc952.png`：`detection_count=0`。
- `debug/loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png`：`detection_count=0`。
- `debug/loot_event_probe.py --benchmark --handler-smoke`：`positive_tiny=1`、`blank300=0`、`positive300=1`、`player300=0`，handler smoke 仍为 `move_to -> press_key(a) -> wait -> complete`。
- `py_compile` 覆盖本轮修改的 loot/config 文件，通过。

文档同步：
- 更新 `CODEBASE.md`：记录透明模板、alpha mask、`player_marker_template_threshold=0.75`、结构分数保护和蓝色地图装饰过滤。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：同步模板扣图规则、人物排除算法、GUI 可调阈值和配置表。

## [SYNC] 2026-05-29 01:35 - LOOT-TWO-STAGE-PRESENCE-AND-CENTER-MASK

触发任务：用户反馈掉落物事件导致移动时明显卡顿，同时实测掉落物没有被识别；用户明确希望先粗略判断是否存在掉落物，存在后再调用几次判断并定位，不要每帧全量判断，并且人物位置固定，应直接用遮罩处理。

关键发现：
- (verified) 运行日志中 loot detector 已初始化，但运行时没有有效 loot detection 记录；当前单独截图到的监控区域为黑帧，因此不能用该帧判断真实召回，只能用静态正负样本建立 detector 回归。
- (verified) 旧 full-frame/ROI 模板扫描在正样本上仍可能出现 100ms 级峰值；人物负模板如果对每个候选都执行，也会把移动时的 CPU 占用放大。
- (verified) 人物图标在小地图中位置固定，适合在粗检 mask 层先挖掉中心区域，而不是对所有候选做人物排除。

实现变更：
- `core/events/types/loot/detection/roi.py`：新增 `loot_seed_bboxes()`、`apply_player_center_mask()` 和中心 patch 人物确认逻辑；粗检阶段先构造掉落物颜色/亮度 mask，再按中心人物箭头模板确认后挖空中心圆形区域。
- `core/events/types/loot/detection/seed_scan.py`：新增 seed 局部复核模块，围绕 seed 中心做少量对齐点的 mask 彩色、mask 灰度和边缘重合评分，不再生成整帧响应图。
- `core/events/types/loot/detection/pipeline.py`：新增 `detect_loot_presence()`；`detect_loot_blobs()` 支持复用 presence 阶段的 `seed_bboxes`，避免重复全图粗检。
- `core/events/types/loot/minimap_detector.py`：改为两阶段状态机。每帧先 presence；无 seed 立刻清缓存；seed 连续达到 `presence_confirm_frames` 后才定位；定位结果在 `detection_interval_ms` 内复用。
- `core/events/types/loot/config.py`、`core/events/config_model.py`、`core/events/types/loot/definition.py`：新增 `presence_confirm_frames=2`、`player_center_mask_enabled=true`、`player_center_mask_radius=28`，并暴露到事件管理 schema。
- `debug/loot_event_probe.py`：单图 probe 会按 `presence_confirm_frames` 连续喂入同一帧，benchmark 也先 warmup presence，保持与运行时两阶段一致。

验证：
- `debug/loot_event_probe.py --test-dir D:\ACloud\image\test --benchmark --handler-smoke`：两张正样本均 `detection_count=1`；`positive_tiny` 平均约 `12.66ms`，`blank300` 平均约 `1.06ms`，`positive300` 平均约 `19.61ms`，`player300` 平均约 `9.10ms`。
- `debug/loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png`：`detection_count=0`。
- `py_compile` 覆盖 `minimap_detector.py`、`config.py`、`definition.py`、`pipeline.py`、`roi.py`、`seed_scan.py`、`debug/loot_event_probe.py`，通过。

文档同步：
- 更新 `CODEBASE.md`：记录 presence 粗检、连续确认、中心人物遮罩、seed 局部复核和新增参数。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：同步两阶段算法、模块结构、配置表、性能数据和风险。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：同步 loot 事件包关键语义。

## [SYNC] 2026-05-29 19:35 - LOOT-1B2A-PROBE-AND-FINAL-CANDIDATE-EXCLUSIONS

触发任务：用户反馈实际运行时仍会把人物识别成掉落物，但真实掉落物没有被识别出来；要求先写探针，在 `D:\ACloud\image\test` 下 `1b2a...` 测试图通过。

关键发现：
- (verified) `1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png` 的真实掉落物位于约 `(137,151)`，候选 bbox 为 `[123,137,28,28]`，需要保留；该候选蓝色比例高但仍有少量金色和较高外形分数。
- (verified) 只做中心遮罩不够。正式 detector 在小图和 padding 场景下仍可能产生 accepted 候选，因此 accepted 候选出口必须保留人物/地图装饰最终排除。
- (verified) 旧根目录负样本 `957...`、`fd461...` 的误检共同特征是蓝/青底比例较高、金色比例接近 0、亮白比例偏高且外形分数低于真实掉落物。

实现变更：
- `core/events/types/loot/detection/seed_scan.py`：accepted 候选出口恢复 `is_player_marker_candidate()`，随后调用 `is_blue_map_artifact_candidate(patch, best.shape_score)`，只对已通过三路评分的少量候选执行最终排除。
- `core/events/types/loot/detection/pipeline.py`：旧 full-region 路径同步把 `shape_score` 传给蓝底 artifact 过滤，保持两条候选路径语义一致。
- `core/events/types/loot/detection/exclusions.py`：`is_player_marker_candidate()` 改为蓝底人物可按普通阈值排除，非蓝底候选必须模板/结构/三角形都很高才排除，避免误杀 `620a...`；`is_blue_map_artifact_candidate()` 增加 shape-aware 规则，过滤蓝/青底、低金色、亮白偏多且外形不足的人物/地图装饰。
- `debug/loot_event_probe.py`：新增 `--expect-count`、`--expect-min-count`、`--expect-center`、`--center-tolerance` 断言参数，不满足时返回非 0；`--dump-stages` 改为走 production padding 路径并还原 bbox/center，debug overlay 与正式 detector 对齐。

验证：
- `debug/loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 137,151 --center-tolerance 8`：通过，`detection_count=1`。
- `debug/loot_event_probe.py --test-dir D:\ACloud\image\test --benchmark --handler-smoke --expect-count 1`：三张正样本均 `detection_count=1`；benchmark 中 `blank300=0`、`positive300=1`、`player300=0`；handler smoke 仍为 `move_to -> press_key(a) -> wait -> complete`。
- `debug/loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png --expect-count 0`：通过。
- `debug/loot_event_probe.py --image D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png --expect-count 0`：通过。
- `debug/loot_event_probe.py --image D:\ACloud\image\bc314efc-1f1e-4770-ae81-c410fb1d1e72.png --expect-count 0`：通过。
- `debug/loot_event_probe.py --image D:\ACloud\image\fd4615e6-a089-403f-b2aa-26fceeafc952.png --expect-count 0`：通过。
- `py_compile` 覆盖 `pipeline.py`、`roi.py`、`seed_scan.py`、`exclusions.py`、`debug/loot_event_probe.py`，通过。

文档同步：
- 更新 `CODEBASE.md`：记录中心遮罩 + accepted 候选最终排除、shape-aware 蓝底 artifact 过滤、1b2a 断言式探针命令。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：同步最终排除算法、断言式 probe、最新性能数据和风险。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：同步 loot 人物/地图装饰过滤摘要。

## [SYNC] 2026-05-29 20:25 - LOOT-TARGET-LOCK-AFTER-CONFIRM

触发任务：用户澄清卡顿不是人物定位本身，而是掉落物事件定位/目标点有问题，体感像每次都做全局定位；要求参考传送门逻辑，并询问 YOLO 是否会更快。

关键发现：
- (verified) loot 事件没有调用 `NavigationCore` 全图定位。事件位置由 `EventPositionStabilizer.project_detection()` 使用 `frame_registration.frame_origin_global + detection.local_minimap_pos * draw_scale` 投影得到。
- (verified) 旧 `EventTask.mark_seen()` 每次稳定观测都会覆盖 `task.global_pos`。loot 是区域/blob 目标，中心点比 portal 图标更容易漂移；后续 `NavigationTaskBuilder` 会把新的 `global_pos` 变成新的 event target，`MovementExecutor.ensure_movement_path()` 看到目标变化后可能触发 A* 重规划和重复点击。
- (verified) YOLO 只可能替换 detector backend，不能自动解决投影、memory 合并和导航目标漂移；如果后续目标点仍连续覆盖，A* 重规划问题仍会存在。

实现变更：
- 新增 `core/events/memory/target_update.py`：实现 `should_update_task_target()`，支持 `continuous`、`lock_after_confirm`、`limited_after_confirm`、`locked` 等目标更新策略。
- 修改 `core/events/models.py`：`EventTask.mark_seen()` 增加 `update_global_pos` 参数，默认保持旧行为；memory 可选择只刷新观测状态，不覆盖目标点。
- 修改 `core/events/memory/merge.py`：命中已有 task 时先按事件配置判断是否允许覆盖 `global_pos`；loot 锁定后仍刷新 `last_seen_ms`、`confidence`、`seen_count`、metadata 和 `last_observed_global_pos`，并写入 `target_drift/target_update_reason` 日志字段。
- 修改 `core/events/config_model.py`、`core/events/types/loot/config.py`、`core/events/types/loot/definition.py`：loot 默认新增 `target_update_mode="lock_after_confirm"`、`target_update_max_drift=0`，事件管理 GUI 可调整。
- 修改 `gui/dialogs/event_manager_dialog.py`：事件摘要显示 `target_update_mode` 和 `target_update_max_drift`。
- 修改 `debug/loot_event_probe.py`：新增 `--target-jitter-smoke`，直接向 `EventMemory` 喂入同一 loot 的多次漂移 observation，并断言确认后 `task.global_pos` 保持首次目标，同时 `last_observed_global_pos` 继续刷新。

验证：
- `py_compile` 覆盖 `core/events/models.py`、`core/events/memory/merge.py`、`core/events/memory/target_update.py`、`core/events/config_model.py`、`core/events/types/loot/config.py`、`core/events/types/loot/definition.py`、`gui/dialogs/event_manager_dialog.py`、`debug/loot_event_probe.py`，通过。
- `debug/loot_event_probe.py --target-jitter-smoke`：通过；后续观测漂移 35、89、41 地图单位时，`final_target` 仍为首次 `(1000,1000)`，`target_locked=true`。
- `debug/loot_event_probe.py --test-dir D:\ACloud\image\test --expect-count 1`：三张正样本均 `detection_count=1`。
- `debug/loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 137,151 --center-tolerance 8`：通过。
- 负样本 `D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png`、`D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png`、`bc314...`、`fd461...` 均 `detection_count=0`。
- `debug/loot_event_probe.py --benchmark --handler-smoke --target-jitter-smoke`：`blank300` 平均约 `0.59ms`，`positive300` 平均约 `12.76ms`，`player300` 平均约 `13.19ms`；handler smoke 仍为 `move_to -> press_key(a) -> wait -> complete`。

文档同步：
- 更新 `CODEBASE.md`：记录 loot 不触发全图定位、目标漂移导致 A* 重规划的原因、`target_update_mode=lock_after_confirm` 和 `--target-jitter-smoke`。
- 更新 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`：新增 `memory/target_update.py` 模块说明和 loot 目标锁定语义。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：新增“事件定位与目标锁定”章节，说明 YOLO 不是当前优先解法。

## [SYNC] 2026-05-29 21:10 - NAVIGATION-MINIMAP-SAMPLE-CAPTURE

触发任务：用户要求在 GUI 页面增加截图模式，用来保存当前监视的小地图，便于收集掉落物/事件识别样本。

关键发现：
- (verified) 导航循环已经在 `capture_navigation_localization_tick()` 中拿到真实监视区域 frame、`capture_rect` 和玩家局部坐标；样本采集应复用这份最近帧，避免点击保存时额外触发事件识别或任务调度。
- (verified) 未启动导航循环时仍可以依据当前 `NavConfig` 的监视几何即时截图一次，因此按钮只需要依赖“已加载地图”，不要求 timer 正在运行。
- (verified) 样本应保存原始监视区域，不做掉落物识别、人物遮罩或后处理，否则会污染后续 detector 回归数据。

实现变更：
- `gui/modes/navigation/runtime/minimap_sample_capture.py`：新增 `MinimapSampleCaptureResult`、`save_minimap_sample()` 和 `capture_current_minimap_frame()`；保存 PNG 与同名 JSON metadata，默认目录为 `debug/minimap_samples/<map_name>/`。
- `gui/modes/navigation/runtime/frame_loop.py`：每帧缓存 `_latest_minimap_frame`、`_latest_minimap_capture_rect`、`_latest_minimap_player_local_pos`。
- `gui/modes/navigation/ui/layout.py`、`gui/modes/navigation/ui/signals.py`：顶部工具栏新增 `保存小地图样本` 按钮，并连接到 widget slot。
- `gui/modes/navigation/widget.py`：新增缓存字段、地图加载后启用按钮、`save_minimap_sample()` 入口；有缓存时保存最近帧，无缓存时即时截图。

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\runtime\minimap_sample_capture.py gui\modes\navigation\runtime\frame_loop.py gui\modes\navigation\ui\layout.py gui\modes\navigation\ui\signals.py gui\modes\navigation\widget.py`：通过。
- helper probe 曾生成 `debug/minimap_samples/probe_map/20240310_000000_123_probe_map_minimap.png` 和同名 JSON，确认文件写入与 metadata 格式可用。

文档同步：
- 更新 `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`：新增小地图样本采集链路、职责边界和风险。
- 更新 `CODEBASE.md`：新增 `runtime/minimap_sample_capture.py` 目录说明、模块详情、frame loop 缓存语义和结构审计记录。

## [SYNC] 2026-05-29 23:45 - LOOT-SMALL-SAMPLE-MASK-AND-ARTIFACT-REGRESSION

触发任务：小地图样本截图功能完成后，继续诊断当前掉落物识别算法；用户反馈真实掉落物漏检、人物/地图装饰误检，并要求用 `D:\ACloud\image\test` 做当前算法验证。

关键发现：
- (verified) `D:\ACloud\image\test` 中两个 21x25/21x26 单图标样本漏检的直接原因是 `erase_player_center_region()` 固定中心人物遮罩半径 28，把整张小图标样本擦掉；该遮罩只适合真实小地图监视帧，不适合单图标 probe。
- (verified) `fd461...` 负样本存在两类误检：黄色人物箭头和右侧蓝白地图装饰。中心遮罩后的半截人物可能在定位阶段绕过 `is_player_marker_candidate()`，因此定位复核必须使用原始帧，中心遮罩只应作用于 presence seed。
- (verified) 蓝白地图装饰的特征是蓝底比例高、金色接近 0、白色/亮色比例偏高且外形分数不足；需要比旧蓝底 artifact 规则更明确地排除。

实现变更：
- `core/events/types/loot/detection/roi.py`：`erase_player_center_region()` 对小尺寸输入增加 guard，输入最短边接近中心遮罩直径时跳过固定中心遮罩。
- `core/events/types/loot/detection/pipeline.py`：`detect_loot_blobs()` 不再对定位复核帧调用 `erase_player_center_region()`；presence seed 仍由 `loot_seed_bboxes()` 处理中心人物遮罩。
- `core/events/types/loot/detection/exclusions.py`：`is_blue_map_artifact_candidate()` 新增蓝白地图装饰过滤分支，要求蓝底高、金色低、白/亮区域偏多且外形分数不足。
- `debug/loot_event_probe.py`：benchmark 中 `positive300` 正样本从小地图正中心移开，避免被固定人物遮罩当成中心玩家区域擦掉，基准更接近“视野内非人物中心掉落物”。

验证：
- `debug/loot_event_probe.py --test-dir D:\ACloud\image\test --out-dir debug\loot_test_after_original_frame_candidates_20260529 --dump-stages --expect-min-count 1`：三张测试正样本均检出；`1b2a...` 当前稳定中心为 `(173,112)`。
- `debug/loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 173,112 --center-tolerance 8`：通过。
- 负样本 `D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png`、`D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png`、`bc314...`、`fd461...` 均 `detection_count=0`。
- `debug\loot_event_probe.py --benchmark --handler-smoke --target-jitter-smoke`：`positive_tiny=1`、`blank300=0`、`positive300=1`、`player300=0`；均值约为 `positive_tiny 9.52ms`、`blank300 1.55ms`、`positive300 9.05ms`、`player300 1.15ms`；handler smoke 和目标锁定 smoke 通过。
- `py_compile` 覆盖 `roi.py`、`pipeline.py`、`exclusions.py`、`debug/loot_event_probe.py`，通过。

文档同步：
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：同步小尺寸遮罩 guard、原始帧定位复核、蓝白 artifact 过滤、当前 1b2a 断言中心和最新 benchmark。
- 更新 `CODEBASE.md`：同步 loot 顶部摘要和断言式 probe 命令。

## [DESIGN] 2026-06-01 - LOOT-ACQUIRE-ONCE-MEMORY-VERIFY

触发任务：用户指出掉落物事件不应该在人物移动时持续重复定位；如果 2-3 帧已经准确定位，后续应在导航地图上标记并复用，特别是掉落物很多时，不能反复触发昂贵全图定位。

设计结论：
- (inferred) 掉落物事件应分成 `首次发现/定位 acquisition`、`地图记忆 memory`、`小 ROI 反投影确认 projected verify` 三层。
- (verified by discussion) full acquire 只用于发现新目标；已确认目标应锁定 `global_pos`，后续导航使用地图坐标，不再每帧覆盖目标点。
- (inferred) 人物移动后判断“是否是同一个掉落物”，应通过已记录 `global_pos` 反投影到当前小地图的 expected local position，再做小 ROI 确认，而不是全图重新识别。
- (inferred) 多掉落物场景下，一次定位可以批量写入 memory；调度器按距离/优先级选择一个，其他保留为地图 marker，避免目标数量增加导致每帧成本线性放大。

建议状态机：
```text
无已知 loot -> 低频 full acquire -> presence 连续 2-3 帧 -> detect_loot_blobs -> 投影 global_pos -> 写入 memory
已有 loot -> global_pos 反投影 expected_local_pos -> 小 ROI verify -> 刷新 last_seen_ms 或累计 missing_seen
正在拾取 -> 降低/暂停新目标 acquire -> 按 A -> ROI 连续缺失后 complete
```

资源预期：
- presence 粗检/空帧：约 1-2ms。
- full acquire 有候选：平均约 9-10ms，峰值可能 40-50ms。
- projected ROI verify：目标 <1-3ms。
- memory 坐标判断和去重：接近可忽略。

落地边界：
- 本条是设计记录，未改实现。
- 正式融合前先等待用户通过 GUI 小地图样本截图收集真实样本，再用 `debug/loot_event_probe.py --test-dir <样本目录> --dump-stages` 做召回/误检/性能回归。
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`，新增 `2026-06-01 设计记录：只定位少数帧，后续按地图记忆复用`。

## [SYNC] 2026-06-03 10:41 - LOOT-DATASET-EVAL-BASELINE

触发任务：用户确认 `D:\ACloud\image\sample` 数据集没有问题，要求写脚本来批量测试当前掉落物识别算法。

关键发现：
- (verified) 数据集当前按 `02_has_loot` / `03_no_loot` 划分正负样本，脚本应直接以目录作为标签来源，不再依赖人工查看 contact sheet。
- (verified) 评估必须调用 production `LootEventDefinition().create_detector(config)`，并按 `presence_confirm_frames` 连续喂帧，否则会绕开运行时的两阶段确认逻辑。
- (verified) 地图 A 当前 `events.loot.weighted_threshold=0.70`，但首轮误检 best confidence 分布约 `0.5423` 到 `0.6626`，说明误检通过的是 `accepted_candidate()` 的强证据直通或后置排除不足，不是单纯全局阈值过低。

实现变更：
- 新增 `debug/loot_dataset_eval.py`：读取 `D:\ACloud\image\sample` 正负样本，加载 `map_data/A/event_config.json` 的 `events.loot` 配置；每张图独立创建 detector，输出 TP/FP/FN/TN、precision、recall、FPR、accuracy 和检测耗时统计。
- 输出目录为 `debug/loot_dataset_eval/<timestamp>/`，包含 `summary.json`、`cases.csv` 和 FP/FN overlay；默认关闭 runtime diagnostic capture，避免评估时额外落盘影响耗时。
- CLI 支持 `--threshold`、`--collect-threshold`、`--presence-confirm-frames`、`--player-center-mask-radius`、`--max-blobs-per-frame`、`--dump-all`、`--strict` 和 `--show-event-log`。

验证：
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile debug\loot_dataset_eval.py`：通过。
- `D:\ACloud\.venv\Scripts\python.exe debug\loot_dataset_eval.py --dataset-root "D:\ACloud\image\sample" --map-config "map_data\A\event_config.json"`：通过，输出 `debug/loot_dataset_eval/20260603_104108/`。
- 首轮基线：total=77，has_loot=25，no_loot=52；TP=25，FP=52，FN=0，TN=0；precision=0.3247，recall=1.0000，FPR=1.0000，accuracy=0.3247；avg=215.747ms，p50=208.257ms，p95=418.551ms，max=485.987ms。

文档同步：
- 更新 `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`：新增数据集评估脚本使用方式、输出约定、首轮基线和后续优化指向。
- 更新 `CODEBASE.md`：顶部 loot 摘要补充 `debug/loot_dataset_eval.py`、当前基线结果和风险判断。
