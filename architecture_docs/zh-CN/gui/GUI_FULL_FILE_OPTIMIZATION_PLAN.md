# GUI 全文件级优化规划

## 1. 本轮范围

本轮重新阅读 `gui/` 下全部非缓存文件，包括 `modes/`、`dialogs/` 内部 helper 和局部架构文档。结论不再只按 `shell / modes / dialogs` 外层分类，而是落到每个文件的职责、深度、风险和后续动作。

本轮只做规划，不改实现。后续执行时继续遵守：

- 上下文压缩或新会话恢复后，先阅读本文件和 `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md` 最新一轮，再继续执行；不要只凭压缩摘要推进。
- 入口策略更新：`gui.modes.navigation.NavigationModeWidget` 是导航页 canonical 入口；旧 `gui.modes.navigation_mode` 文件已删除，外部入口直接使用 canonical 包路径。
- 新模块必须放入功能 package，不把 helper 平铺到 `gui/modes` 或 `gui/dialogs`。
- 先抽稳定 seam，再拆 UI layout。避免只是把 1000 行文件切成多个浅函数文件。
- GUI 负责用户动作翻译、Qt 生命周期、状态展示和平台窗口行为；core 负责算法、定位、寻路、事件调度和输入策略。
- 该 GUI 优化阶段只做模块化、系统化和旧内容审计后的结构收敛；当前后续功能阶段已新增事件 Hooks 页和 navigation hook runtime，GUI 可按 `event_config.hooks.instances` 注册 key_press handler。

当前执行状态：阶段 A、阶段 B、阶段 C 已完成，阶段 D 的 presentation 与 runtime 小 seam 已完成，阶段 E 的 Mapping runtime session、runtime lifecycle、presentation presenter、capture selection controller、IO config store、config restore、map save、params binding、UI layout 已完成。`MappingWidget.stop_runtime()`、`NavigationModeWidget.stop_runtime()`、`MainWindow.closeEvent()` 生命周期收口和 `ScalableMapWidget.pixel_clicked` 点击坐标映射已经落地；Navigation 输入窗口模式、`NavigationIntent` 执行和 `NavConfig` 应用规则已迁入功能包；route 编辑、route panel controller、route command lifecycle、event dialog wiring 和 manual event test controller 已迁入功能包；地图场景 item 创建/更新、地图加载 UI 写入、配置保存结果展示、路线/事件 overlay、debug overlay 写入、状态栏文案和 owned dialog 显示外壳已迁入 presentation 包；导航 map config store、map session 载入入口、map load session 准备、map load lifecycle 编排与 capture geometry 已迁入 `navigation/map/` 功能包；屏幕中心校准已拆成 `navigation/calibration/screen_center.py`（selector/DPR/坐标转换）和 `navigation/calibration/lifecycle.py`（配置写回、参数回填、overlay、保存、完成提示、关闭 selector）；定位结果 DTO、lookahead/event-run helper、单帧截图/定位 tick、玩家局部坐标解析、事件观测、`NavigationUpdateContext` 组装、runtime command lifecycle、force-relocalize intent 处理、intent consumption 编排和终态 intent 收束已迁入 runtime 包；Mapping capture-recognize-stitch 主 tick 已迁入 `mapping/runtime/session.py`，监控启动/停止和 capture timer 已迁入 `mapping/runtime/lifecycle.py`，display 写入已迁入 `mapping/presentation/map_presenter.py`，区域/中心点选择 overlay 生命周期和 monitor 配置写回已迁入 `mapping/capture/selection_controller.py`，project root/map_data/config.json 读写已迁入 `mapping/io/config_store.py`，启动时根配置恢复已迁入 `mapping/io/config_restore.py`，地图包和地图级 config 保存已迁入 `mapping/io/map_save.py`，控件到参数 dict 的绑定已迁入 `mapping/params/binding.py`，控制面板/显示面板构建已迁入 `mapping/ui/layout.py`。旧 `navigation_mode.py`、`mapping/save_load.py`、`mapping/params_adapter.py`、`navigation/map_runtime.py`、`navigation/*_overlay.py` 和 `event_test_controller.py` 兼容壳已删除。GUI 对旧 core 顶层兼容壳和 `core.__init__` 聚合入口的实现侧 import 已清零；对应调用改为 `core.localization`、`core.input`、`core.routing`、`core.vision`、`core.platform`、`core.mapping` 新系统包入口。

当前阶段结果：core/gui 工程化优化已完成验收。后续不再为了降低行数继续拆分；只有新功能触碰、owner 依赖难以审计或出现真实复用边界时，才继续按功能 package 深化。

本轮追加状态：导航页顶部工具栏、地图 `QGraphicsScene/QGraphicsView`、状态栏和 `RoutePanelController` 构建已迁入 `navigation/ui/layout.py`；按钮、参数弹窗和事件弹窗信号绑定已迁入 `navigation/ui/signals.py`。`NavigationModeWidget.init_ui()` 与 `_connect_signals()` 现在只保留稳定壳方法；后续重点从 UI shell 转向 owner 依赖收窄和新功能触碰时的 dialog section 拆分。

本轮追加状态 2：map display lifecycle 已迁入 `navigation/display/lifecycle.py`。它负责 scene item 引用写回、route/event overlay 清理和渲染、绿色监控框、橙色视野框、上次退出位置 marker；`NavigationModeWidget` 保留原私有方法名作为转发壳。继续拆分时优先看 owner targets 是否已经难以审计，而不是继续按 wrapper 数量硬拆。

本轮追加状态 3：导航定时器整帧编排已迁入 `navigation/runtime/frame_loop.py`。`NavigationRuntimeFrameLoop` 负责 capture-localize、event observe、task update、localization presentation、route overlay 和 intent consumption 的固定顺序；`NavigationModeWidget._navigation_loop_unified()` 只保留 Qt timer 兼容入口。

本轮追加状态 4：`NavigationModeWidget` 的旧长 docstring 已清理。保留的说明改为 wrapper/组合根级别，不再在 widget 中重复描述已经迁到 lifecycle/runtime 模块里的旧内联步骤。

本轮追加状态 5：导航 lifecycle/controller wiring 已迁入 `navigation/composition/lifecycles.py`。`NavigationModeWidget.__init__()` 只保留基础字段初始化、UI 构建、pre-signal lifecycle 初始化、signal wiring 和 runtime lifecycle 初始化顺序。

## 2. 全文件审计表

| 文件 | 当前职责 | 深度判断 | 主要问题 | 后续动作 |
| --- | --- | --- | --- | --- |
| `gui/__init__.py` | GUI 包标识。 | 浅入口 | 不再 re-export `MainWindow`，避免旧聚合入口。 | 保留为空入口。 |
| `gui/app_context.py` | 持有 capture、recognizer、stitcher、tracker、pathfinder 和 monitor 状态。 | 中等但边界清晰 | core service 构造已迁入 `composition/services.py`，`AppContext` 支持注入 `CoreServices`；旧 `load_global_config()` / `save_global_config()` 空实现已删除。 | 保留旧 `AppContext(self)` 入口；后续如引入 profile/config，再新增真实配置服务。 |
| `gui/main_window.py` | 顶层窗口、模式按钮、stacked pages、关闭流程。 | 薄 shell | 阶段 A 已收口：`closeEvent()` 只调用 mode 的 `stop_runtime()`。 | 后续保持 shell 不知道子页面 timer。 |
| `gui/navigation_params.py` | `NavConfig`、`RecognizerParams`、`NavPreferences` 和配置兼容序列化。 | 稳定契约 | 已接近 GUI-free，但仍被 GUI 大量依赖。 | 暂不迁移；后续可移动到 shared/config 时保留 wrapper。 |
| `gui/ARCHITECTURE.md` | GUI 本地架构说明。 | 文档 | 英文/混合文档，用户要求后续只同步中文文档。 | 不再更新，中文以 `architecture_docs/zh-CN/gui` 为准。 |
| `gui/composition/__init__.py` | GUI composition helper 包入口。 | 浅入口 | 导出路径解析 helper。 | 保留；正式入口，不是旧壳。 |
| `gui/composition/paths.py` | GUI 项目根、`map_data`、根配置和高级参数目录解析。 | 深路径 seam | mapping/navigation/advanced settings 已复用；不再在 GUI 实现侧固定 `parents[n]`。 | 保留；后续由 AppContext/application composition 显式持有 paths。 |
| `gui/composition/services.py` | GUI 共享 core services DTO 和默认构造工厂。 | 中等 service composition seam | `AppContext` 支持注入 `CoreServices`，默认仍创建 `SquareScreenCapture`、`HSVRecognizer`、`MapStitcher(canvas_size=5000)`、`PlayerTracker`、`PathFinder`。 | 保留；后续如引入 profile/config，可从这里扩展服务构造。 |
| `gui/widgets/__init__.py` | 聚合 widget 导出。 | 浅入口 | 无。 | 保留。 |
| `gui/widgets/clickable_label.py` | 可点击图像 label，显示坐标转原图坐标。 | 合格组件 | 当前只服务 color picker。 | 保留，可作为 `ScalableMapWidget` 点击映射参考。 |
| `gui/widgets/collapsible_group.py` | 带缩放按钮的地图组。 | 合格组件 | `_on_toggled()` 使用 `controls_layout.parentWidget()`，依赖 Qt layout 父级行为。 | 低优先级清理，暂保留。 |
| `gui/widgets/scalable_map.py` | 可缩放、拖拽、fit-to-view 的地图显示。 | 中等组件 | 阶段 A 已补齐 `pixel_clicked`：释放时若不是拖拽，会把当前缩放图坐标映射回原图坐标。 | 后续可补 UI smoke 或 widget 单测。 |
| `gui/selection/center_selector.py` | 全屏点击选择中心点。 | 合格 overlay | 坐标以 Qt 逻辑像素发出，调用方负责 DPR 转换。 | 保留，后续归入 `overlays/selection` 可选。 |
| `gui/selection/indicator_overlay.py` | 点击穿透的监控区域幕布。 | 合格 overlay | 有 print debug；只支持 primary screen。 | 保留，后续用 logging 和多屏 adapter 优化。 |
| `gui/selection/region_overlay.py` | 全屏拖框选择区域。 | 合格 overlay | 取消时只 close，不发取消 signal；调用方用 destroyed 复位。 | 保留，后续统一 selection controller。 |
| `gui/modes/ARCHITECTURE.md` | modes 本地架构说明。 | 文档 | 英文/混合文档。 | 不再更新，中文镜像为准。 |
| `gui/modes/mapping_widget.py` | 建图页组合根、参数同步、保存时机；capture timer、capture-recognize-stitch tick、display 写入、capture selection、IO helper、config restore、map save、params binding、UI layout 已委托功能包。 | 深热点 | `setup_ui()` 已委托 `mapping/ui/layout.py`；`toggle_monitoring()`/`stop_runtime()` 已委托 `mapping/runtime/lifecycle.py`；`capture_and_process()` 已瘦身为 session tick + display/stats；`update_displays()` 已委托 presenter；`select_region()` / `select_center_point()` 等入口已变成 capture controller wrapper；`load_saved_params()` 已委托 config restore helper；`save_map()` 已委托 map save helper；旧 `save_load.py` 与 `params_adapter.py` 已删除，调用改到 `mapping/io` 与 `mapping/params`。 | 当前阶段保留为 public composition root；后续只有 save-map presentation、profile/path 注入或高级参数 dialog 扩展出真实边界时再拆。 |
| `gui/modes/mapping/__init__.py` | mapping helper 包入口。 | 浅入口 | 无导出。 | 保留。 |
| `gui/modes/mapping/ui/__init__.py` | mapping UI shell 包入口。 | 浅入口 | 导出 `build_mapping_ui`。 | 保留。 |
| `gui/modes/mapping/ui/layout.py` | 建图页控制面板滚动外壳、控制内容面板和显示面板构建。 | UI shell seam | 创建控件、默认值、signal 连接并写回 owner；控制面板通过 `QScrollArea` 支持小窗口；不读写 config、不启动 timer、不调用 recognizer/stitcher。 | 保留；后续如收窄 owner，可改成 targets DTO 或 section builders。 |
| `gui/modes/mapping/capture/__init__.py` | mapping capture 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/mapping/capture/selection_controller.py` | 区域/中心点选择 overlay 生命周期、DPI 坐标转换、AppContext monitor 配置写回。 | 中等 capture seam | 仍依赖 primary screen DPR；overlay 类仍在 `gui/selection`。 | 保留；后续如统一 overlay 系统，可迁移 factory 注入位置。 |
| `gui/modes/mapping/runtime/__init__.py` | mapping runtime 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/mapping/runtime/lifecycle.py` | 建图页监控启动/停止、capture timer 和 monitoring 状态。 | 深 runtime command seam | 持有 QTimer，通过 targets DTO 接收按钮、FPS 和 tick callback；保持未选择区域 warning、timer interval 和按钮文案顺序。 | 保留。 |
| `gui/modes/mapping/runtime/models.py` | `MappingTickResult` DTO。 | 小纯模型 | 承载 current image、combined mask、player pos、capture size。 | 保留。 |
| `gui/modes/mapping/runtime/session.py` | 单帧 capture-recognize-stitch 主流程。 | 中等 runtime seam | 通过回调读取当前 monitor center/上一帧 player pos，不触碰 UI。 | 保留；后续可扩展为完整 MappingSession lifecycle。 |
| `gui/modes/mapping/presentation/__init__.py` | mapping presentation 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/mapping/presentation/map_presenter.py` | capture label 和 global map widget 写入 presenter。 | 中等 presenter | 复用 `map_renderer.py`，不调用 recognizer/stitcher add frame。 | 保留；后续可继续收束 display state。 |
| `gui/modes/mapping/map_renderer.py` | BGR/QPixmap 转换和全局地图 overlay 绘制。 | 有价值 helper | 仍是函数集合，未形成 presenter。 | 保留为 renderer helper，由 `presentation/map_presenter.py` 调用。 |
| `gui/modes/mapping/params/__init__.py` | mapping params 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/mapping/params/binding.py` | 从控件读写 recognizer/stitcher 参数，保持原副作用边界。 | 浅 adapter | 仍由 widget 决定何时应用和保存；sync 函数不阻断 Qt 信号，保持旧行为。 | 保留；后续若做命令式参数系统，再返回 typed command/dict。 |
| `gui/modes/mapping/io/__init__.py` | mapping IO 包导出。 | 浅入口 | 导出 config store 与 config restore helper。 | 保留。 |
| `gui/modes/mapping/io/config_store.py` | 根 config、map folder、map config 读写和 mapping config payload 构造。 | 中等 IO store | 已委托 `gui/composition/paths.py` 解析 project root、`map_data` 和根 `config.json`，GUI 实现侧不再固定 `parents[n]`。 | 保留；后续如引入 profile，可从 `AppContext` 或 application composition 注入项目根。 |
| `gui/modes/mapping/io/config_restore.py` | 启动时根配置恢复到 AppContext、capture selection 和 Qt 控件。 | 中等 restore seam | 不是纯存储层，会写 runtime services 和控件；用 `QSignalBlocker` 保持几何控件回填不触发保存。 | 保留；后续若做 composition，可把 targets DTO 由 builder 生成。 |
| `gui/modes/mapping/io/map_save.py` | 保存地图包和地图级 config。 | 小型 IO seam | 不弹输入框/成功提示，只执行目录创建、`save_map_package()` 和 `config.json` 写入。 | 保留；后续可统一保存失败展示。 |
| `gui/modes/navigation/widget.py` | 导航页 QWidget 组合根和 facade；保留基础 runtime 字段、UI 构建、Qt signal/timer 入口和少量 wrapper。 | 中等组合根 | input/config/route/events/presentation/runtime/calibration 已委托功能包；lifecycle/controller wiring 已迁入 `navigation/composition/lifecycles.py`；runtime frame loop 已承接整帧循环；旧长 docstring 已压缩；`RouteManager` 与 `MotionController` 已改用 `core.routing`/`core.input` 新入口；旧文件路径壳已删除。 | 后续只在发现真实职责边界时继续拆，不为降行数硬拆。 |
| `gui/modes/navigation/composition/__init__.py` | navigation composition 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/navigation/composition/lifecycles.py` | 导航页 lifecycle/controller targets wiring：pre-signal lifecycle、timer/runtime lifecycle、manual event controller、frame loop。 | composition seam | 持有 owner 访问以避免超大参数列表；必须保持 `_connect_signals()` 前后顺序。 | 保留；后续可按 owner 依赖收窄 targets。 |
| `gui/modes/navigation/__init__.py` | navigation 包 canonical 入口。 | 浅入口 | 导出 `NavigationModeWidget`。 | 保留；新代码从这里导入导航页。 |
| `gui/modes/navigation/ui/__init__.py` | navigation UI shell 包导出。 | 浅入口 | 导出 `build_navigation_ui` 与 `connect_navigation_signals`。 | 保留。 |
| `gui/modes/navigation/ui/layout.py` | 导航页工具栏、地图 scene/view、状态栏和 `RoutePanelController` 构建。 | UI shell seam | 只创建控件并挂回 owner 字段；不连接信号、不加载地图、不启动导航。 | 保留；后续若做 composition root，可把 owner 参数改成更明确的 targets DTO。 |
| `gui/modes/navigation/ui/signals.py` | 导航页按钮、参数弹窗和事件弹窗信号绑定。 | UI wiring seam | 绑定目标仍是 `NavigationModeWidget` 的稳定 slot。 | 保留；后续如果抽 controller，再同步改 signal 目标。 |
| `gui/modes/navigation/display/__init__.py` | navigation map display lifecycle 包导出。 | 浅入口 | 导出 `NavigationMapDisplayLifecycle`。 | 保留。 |
| `gui/modes/navigation/display/lifecycle.py` | 地图 scene item、route/event overlay、监控框、视野框和上次退出位置 marker 的状态写入 lifecycle。 | 深 display seam | 串联 presentation 小函数并维护 widget 上的 item 引用；不加载地图、不定位、不启动导航。 | 保留；后续可改成 targets DTO 降低对 widget 字段名的直接依赖。 |
| `gui/modes/navigation/ARCHITECTURE.md` | navigation 本地架构说明。 | 文档 | 英文/混合文档。 | 不再更新，中文镜像为准。 |
| `gui/modes/navigation/event_adapter.py` | 事件 registry、EventTick、状态文本、窗口查找。 | 中等 helper | 旧 UI 级 action 仲裁 helper 已确认无实现引用并移除。 | 保留活跃 bridge 函数；不再承载 `EventActionType` 翻译。 |
| `gui/modes/navigation/input/__init__.py` | navigation input 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/navigation/input/window_mode.py` | 主窗口 topmost/lower/restore 状态 adapter。 | 合格 adapter | 仍使用 print debug，依赖 Qt window flag 行为。 | 保留为 input seam，后续可换 logging。 |
| `gui/modes/navigation/input/intent_executor.py` | `NavigationIntent` 到 `MotionController` 的执行 adapter。 | 中等 adapter | 仍由 widget 传入状态栏后缀处理；真实输入副作用集中在此。 | 后续 runtime loop 拆分时保持该 executor 作为唯一 input 消费点。 |
| `gui/modes/navigation/hooks/__init__.py` | navigation hook runtime 注册包导出。 | 浅入口 | 导出 `NavigationHookRuntime`。 | 保留。 |
| `gui/modes/navigation/hooks/registration.py` | 将 `event_config.hooks.instances` 注册到 core hook registry。 | 中等 adapter | 只注册同时具备 `event_types` 和 `triggers` 的 key_press hook；通过 `MotionController.press_key()` 执行，不让 core hook 实例依赖 GUI。 | 保留；后续新增 hook 类型时在此扩展注册策略。 |
| `gui/modes/navigation/config/__init__.py` | navigation config lifecycle 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/navigation/config/lifecycle.py` | 导航配置生命周期 facade：参数变化、runtime 应用、当前地图保存、默认保存、dirty 状态、overlay/视野框刷新和保存反馈。 | 深模块 | 通过 targets DTO 接收 widget/runtime 回调，不直接持有 `NavigationModeWidget`；集中旧 `_on_parameter_changed/_save_nav_config` 顺序。 | 保留；后续若拆组合根，可由 composition 构造 targets。 |
| `gui/modes/navigation/map/__init__.py` | navigation map/config 包导出。 | 浅入口 | 导出 config applier、config store、map session、map load lifecycle、map click lifecycle、map event filter 和 capture geometry。 | 保留。 |
| `gui/modes/navigation/map/click_lifecycle.py` | 地图点击交互生命周期：hint 放置、route 编辑、手动移动目标、marker/overlay/status 更新。 | 深 map interaction seam | 通过 targets DTO 接入 scene/view/route editor/motion controller，不直接持有 `NavigationModeWidget`；保持 hint -> route edit -> manual move 优先级。 | 保留；后续若抽完整 interaction package，可迁移但保持导出。 |
| `gui/modes/navigation/map/event_filter.py` | Qt scene 鼠标事件解释 helper。 | 小型 Qt adapter | 只识别 scene 左键按下并转发 `scenePos()`；不理解 hint/route/manual move 业务语义。 | 保留；widget 继续作为 Qt eventFilter 安装入口。 |
| `gui/modes/navigation/map/session.py` | 导航地图加载前置 session helper，封装 map folder 解析、NavConfig 读取、NavigationCore 创建和初始物理中心计算。 | 中等 map session seam | 不应用配置、不弹窗、不渲染地图；只返回 `NavigationMapLoadSession`，由 load lifecycle 继续后半段。 | 保留。 |
| `gui/modes/navigation/map/load_lifecycle.py` | 导航地图加载生命周期 facade：准备 session、写入 runtime 状态、缺配置提示、配置应用、参数回填、route/event 初始化、地图渲染、退出点、overlay 和加载完成 UI。 | 深 map lifecycle seam | 通过 targets DTO 接入 widget 回调，不直接持有 `NavigationModeWidget`；隐藏 `load_map()` 后半段顺序敏感副作用。 | 保留；后续可由 composition 构造 targets，或把 route/event lifecycle 再独立成更深系统模块。 |
| `gui/modes/navigation/map/config_applier.py` | `NavConfig` 写入 nav_core/path_finder/motion_controller/task_controller。 | 中等 config seam | 会原地修正 `nav_config.draw_scale`，保持 map npz 为权威。 | 保留；后续 map session 拆分时继续复用。 |
| `gui/modes/navigation/map/config_store.py` | map list、NavConfig 读写、默认配置 fallback、merge 保存。 | 中等 IO store | 已委托 `gui/composition/paths.py` 解析 map_data、map folder 对应 project root 和根默认配置；不再保留独立 project-root 推导规则。 | 保留；后续如引入 profile，可从 composition 注入 project root。 |
| `gui/modes/navigation/map/capture_geometry.py` | logical/physical 中心换算、load-map 初始物理中心和 capture rect/player pos 几何。 | 纯 geometry helper | 无 IO/Qt 副作用；不触碰参数弹窗，只返回 UI 回填所需值。 | 保留。 |
| `gui/modes/navigation/calibration/__init__.py` | navigation calibration 包导出。 | 浅入口 | 导出 screen center controller 和 calibration lifecycle。 | 保留。 |
| `gui/modes/navigation/calibration/lifecycle.py` | 屏幕中心校准结果生命周期：坐标转换后写 `NavConfig`、回填参数弹窗、刷新 overlay、保存配置、显示完成提示并关闭 selector。 | 中等 calibration lifecycle seam | 通过 targets DTO 接入 widget/config/presentation；不直接创建 selector 或读取 DPR。 | 保留；旧 `_calibrate_screen_center()` / `_handle_calibration_click()` 继续作为 wrapper。 |
| `gui/modes/navigation/calibration/screen_center.py` | 屏幕中心校准选择器生命周期和逻辑到物理坐标换算。 | 中等 calibration seam | 不写 config、不弹窗；校准结果副作用已迁入 `calibration/lifecycle.py`。 | 保留；后续可统一 overlay selector 基础设施。 |
| `gui/modes/navigation/route/__init__.py` | route editing/lifecycle 包导出。 | 浅入口 | 导出 route editor、panel controller 和 route lifecycle。 | 保留。 |
| `gui/modes/navigation/route/editor.py` | route click mode 和 `route.json` 编辑命令。 | 中等 route seam | 不碰 Qt 按钮/scene，只返回编辑结果；route 运行态同步已迁入 lifecycle。 | 保留；后续 route/presentation 拆分时复用。 |
| `gui/modes/navigation/route/lifecycle.py` | route 命令结果生命周期：加载、保存、撤销、清空后同步 route_data、任务控制器、overlay 和状态栏。 | 中等 route lifecycle seam | 通过 targets DTO 接入 widget 状态；不直接操作按钮 click mode，也不手动解析 route JSON。 | 保留；旧 route slot 继续作为 wrapper。 |
| `gui/modes/navigation/route/panel_controller.py` | route 按钮状态、状态栏提示和 route editor 命令结果。 | 中等 GUI route seam | 接收按钮/status label 引用，但不弹窗、不绘制、不碰任务控制器；命令结果同步交给 lifecycle。 | 保留；后续可继续把 route toolbar 构建下沉。 |
| `gui/modes/navigation/events/__init__.py` | navigation events UI adapter 包导出。 | 浅入口 | 导出 event bootstrap、event dialog lifecycle、manual test controller、event lifecycle 和 panel adapter。 | 保留。 |
| `gui/modes/navigation/events/bootstrap.py` | 地图加载后的事件系统 runtime 初始化。 | 中等 bootstrap seam | 读取 event config、创建 `EventCoordinator` 和 `GameWindowCaptureProvider`、刷新事件弹窗、记录初始化日志；返回 runtime DTO 由 widget 写回字段。 | 保留；后续若事件系统组合根成型，可继续迁移到 events runtime bootstrap。 |
| `gui/modes/navigation/events/dialog_lifecycle.py` | 事件管理弹窗创建、信号连接、刷新、显示切换和手动测试按钮同步。 | 中等 dialog lifecycle seam | 不保存配置、不重置 portal、不启动手动测试；只处理 dialog owner 状态和 signal wiring。 | 保留；后续 dialog schema 抽象时作为事件弹窗 adapter。 |
| `gui/modes/navigation/events/manual_test_controller.py` | 手动事件测试按钮状态同步。 | 小而清晰 | 只同步按钮，不知道事件语义。 | 保留，旧 `gui/modes/event_test_controller.py` 已删除。 |
| `gui/modes/navigation/events/lifecycle.py` | 事件配置保存、portal 状态重置和 portal 手动测试启停生命周期。 | 深 event lifecycle seam | 通过 targets DTO 接入 widget/runtime，不直接持有 `NavigationModeWidget`；集中 save/reset/manual-test 的 IO、coordinator、task、motion/input-window、overlay/dialog 和日志顺序。 | 保留；后续接 hook/总线时可作为 event command 边界。 |
| `gui/modes/navigation/events/panel_adapter.py` | event dialog 创建、信号重连、上下文刷新和配置摘要。 | 中等 UI wiring seam | 不推进事件识别/调度，只管理 dialog wiring。 | 保留；后续 events runtime adapter 可继续扩展。 |
| `gui/modes/navigation/presentation/__init__.py` | navigation presentation 包导出。 | 浅入口 | 导出 map/status/route/event/viewport/dialog/debug-overlay/map-load/config-save presentation helper。 | 保留。 |
| `gui/modes/navigation/presentation/calibration_feedback.py` | 初始位置提示、hint mode 和屏幕中心校准完成反馈。 | 小型 presentation helper | 不写 config、不关闭 selector、不调用 nav_core，只展示结果。 | 保留。 |
| `gui/modes/navigation/presentation/config_save_state.py` | 导航参数保存/默认配置保存的状态标签和 QMessageBox 文案。 | 小型 presentation helper | 不写 config、不应用配置、不刷新 overlay，只展示结果。 | 保留。 |
| `gui/modes/navigation/presentation/event_management_state.py` | 事件配置保存、传送门状态刷新和手动测试启停的状态标签与 QMessageBox 文案。 | 小型 presentation helper | 不保存 event config、不重置 coordinator、不启动/停止 controller，只展示结果。 | 保留。 |
| `gui/modes/navigation/presentation/navigation_command_state.py` | 自动导航和导航启动/停止命令的状态标签与 QMessageBox 文案。 | 小型 presentation helper | 不校验 route、不启动 timer、不控制 motion，只展示结果。 | 保留。 |
| `gui/modes/navigation/presentation/route_command_state.py` | route 命令状态栏、路线保存失败和移动目标反馈。 | 小型 presentation helper | 不改 route 数据、不重绘 overlay、不调用 motion，只展示结果。 | 保留。 |
| `gui/modes/navigation/presentation/map_load_state.py` | 地图列表 combo、地图加载成功 UI 和地图/overlay 加载反馈。 | 小型 presentation helper | 只写 UI 控件或弹旧提示，不读取 map_data、不创建 core、不应用配置。 | 保留。 |
| `gui/modes/navigation/presentation/dialog_host.py` | owned dialog 显示/置顶/恢复最小化/重复点击隐藏判定。 | 小型 Qt shell helper | 只负责 Qt 窗口外壳，不连接 dialog 业务信号、不保存配置。 | 保留；后续若拆 shell 包，可迁移到 `navigation/shell/` 并保留导出。 |
| `gui/modes/navigation/presentation/map_presenter.py` | 地图 scene item 创建、定位显示、玩家/目标/提示点/视野框更新。 | 中等 presenter | 只做 QGraphics item/view 更新，不读写 route/event/runtime 状态；定位显示通过回调更新监控/视野框。 | 保留。 |
| `gui/modes/navigation/presentation/route_overlay.py` | route/exit/required/guide/current path overlay 绘制真实实现。 | presentation helper | 只绘制，不管理 route state。 | 保留。 |
| `gui/modes/navigation/presentation/event_overlay.py` | event marker overlay 绘制真实实现。 | presentation helper | 只绘制 `EventCoordinator.overlays()` 输出，不调度事件；`global_to_scene()` 被 route overlay 复用。 | 保留。 |
| `gui/modes/navigation/presentation/status_presenter.py` | 导航循环状态栏文案构造、写入和运行态后缀/终态提示。 | 小型 presentation helper | 只处理状态栏文本，不请求重定位、不执行 intent、不停止 controller。 | 保留；runtime loop 拆分时复用。 |
| `gui/modes/navigation/presentation/debug_overlay.py` | debug 幕布窗口的几何写入、隐藏和显示。 | 小型 presentation helper | 依赖 `screen_overlay_geometry()`，不决定按钮勾选、不弹配置警告。 | 保留。 |
| `gui/modes/navigation/presentation/viewport_overlay.py` | 屏幕幕布、监控绿框、真实视野橙框矩形计算真实实现。 | 纯 presentation geometry | 几何公式清晰。 | 保留。 |
| `gui/modes/navigation/runtime/__init__.py` | navigation runtime 包导出。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/modes/navigation/runtime/models.py` | 导航循环定位结果 DTO。 | 小纯模型 | 仅封装 core localize 返回值和 localized 判定。 | 保留；后续 loop 拆分时扩展 tick/result DTO。 |
| `gui/modes/navigation/runtime/command_lifecycle.py` | 导航运行命令生命周期：普通导航启动/停止、自动导航启动/停止、timer/motion/task/input-window、按钮回滚和状态栏反馈。 | 深 runtime command seam | 通过 targets DTO 接入 widget/timer/controller，不直接持有 `NavigationModeWidget`；集中旧 `toggle_navigation/stop_runtime/toggle_auto_navigation` 顺序。 | 保留。 |
| `gui/modes/navigation/runtime/frame_loop.py` | 导航定时器单帧 runtime facade：截图定位、事件观察、任务更新、定位展示、route overlay 和 intent 消费。 | 深 runtime frame seam | 持有 widget owner 以避免制造超大 callback DTO；真实算法仍在 core 和 runtime 小 helper 中。 | 保留；后续可把 owner 访问替换为更窄 targets DTO。 |
| `gui/modes/navigation/runtime/intent_consumption.py` | 单个 `NavigationIntent` 的消费编排：重定位短路、真实输入执行回调、手动事件测试停止和终态收束。 | 中等 runtime seam | 不直接执行 route overlay 或真实输入，只通过回调保持旧副作用顺序；返回 DTO 给 widget 控制本帧 return 和自动导航关闭。 | 保留；后续接 hook/总线时可作为 intent consumed/recovery/terminal 边界。 |
| `gui/modes/navigation/runtime/loop_helpers.py` | 导航循环 lookahead 和任务运行开关 helper。 | 小纯 helper | 保持原公式和 boolean 判定。 | 保留；后续 runtime loop 拆分时复用。 |
| `gui/modes/navigation/runtime/localization_tick.py` | 单帧截图、玩家局部坐标解析和 `NavigationCore.localize()` 结果包装。 | 中等 runtime seam | 通过 callback/service 参数避免依赖 QWidget；只返回 `NavigationFrameTick`，widget 仍显式写回当前 capture/player 状态。 | 保留；后续完整 loop 拆分时作为 capture/localize 段边界。 |
| `gui/modes/navigation/runtime/loop.py` | 导航循环玩家局部坐标解析、事件观测和 task controller update 参数组装。 | 中等 runtime seam | 保持原调用顺序；事件观测 helper 仍是后续总线边界；当前两个 event hook 由 core task runner 侧触发，GUI 的注册/输入执行在 `navigation/hooks/registration.py`，不进入 frame loop。 | 保留；后续完整 loop 拆分时继续加深。 |
| `gui/modes/navigation/runtime/relocalization_intent.py` | force-relocalize intent 的全局重定位请求、事件日志和状态展示回调顺序。 | 小型 runtime seam | 使用回调避免依赖 QWidget/Core 具体类；返回 bool 保持旧的本帧提前 return 语义。 | 保留；后续接 hook/总线时可作为恢复事件边界。 |
| `gui/modes/navigation/runtime/terminal_intent.py` | ARRIVED/FAILED 终态 intent 的任务停止、输入窗口恢复、自动导航按钮复位和终态展示回调顺序。 | 小型 runtime seam | 使用回调避免依赖 QWidget；不停止 nav_timer，保持定位循环继续运行。 | 保留；后续接 hook/总线时可作为终态事件边界。 |
| `gui/dialogs/ARCHITECTURE.md` | dialogs 本地架构说明。 | 文档 | 英文/混合文档。 | 不再更新，中文镜像为准。 |
| `gui/dialogs/nav_params_dialog.py` | 导航参数对话框，六个 tabs、控件绑定、`NavConfig` 更新。 | 深热点，已抽 specs/binding seam | tab/layout 和控件创建仍在一个类；字段规格、写回和控件回填已下沉。 | P2 后续抽 sections/widget factory。 |
| `gui/dialogs/nav_params/__init__.py` | nav params helper 包入口。 | 浅入口 | re-export 字段规格和配置绑定 helper。 | 保留。 |
| `gui/dialogs/nav_params/field_specs.py` | 导航参数可编辑字段规格表，描述控件属性名、配置路径、写入方式和分组。 | 中等 specs seam | 只覆盖可编辑绑定字段；只读显示字段暂留 binding。 | 保留；后续扩展 label/help/range 后可服务 widget factory。 |
| `gui/dialogs/nav_params/config_binding.py` | `NavConfig` 字段路径、控件信号绑定、文本解析、dataclass replace 和控件回填。 | 中等 binding seam | 已从 `field_specs.py` 生成绑定和回填；只读显示格式仍在本模块。 | 保留。 |
| `gui/dialogs/nav_params/screen_estimator.py` | 从物理中心和屏幕边界估算点击半径。 | 合格纯 helper | 无 Qt 依赖，边界好。 | 保留。 |
| `gui/dialogs/advanced_settings_dialog.py` | 高级参数调节、参数快照、预设、实时应用。 | 深但已有 command seam | `MappingWidget` 已接管参数应用；dialog 保留未迁移调用方的 direct fallback，tab layout 仍很长。 | 后续拆 tabs 或迁移 fallback。 |
| `gui/dialogs/advanced_settings/__init__.py` | advanced settings helper 包入口。 | 浅入口 | 无。 | 保留。 |
| `gui/dialogs/advanced_settings/file_io.py` | 高级参数 JSON snapshot IO。 | 合格 IO helper | 默认目录通过 `__file__` 推导项目根。 | 保留，后续可注入目录。 |
| `gui/dialogs/advanced_settings/params_adapter.py` | 高级参数控件读写、reset、preset 应用。 | 中等 adapter | 强依赖 dialog attribute names。 | 保留，后续用 field specs 降耦合。 |
| `gui/dialogs/advanced_settings/presets.py` | 预设名称和值数据。 | 合格数据模块 | 无。 | 保留。 |
| `gui/dialogs/color_picker_dialog.py` | 颜色采样交互、HSV 范围计算、preview 显示、结果返回。 | 中等热点 | `update_preview()` 已委托 `color_picker/preview.py` 构造 wall mask 和 stats；`HSVRecognizer` 已改用 `core.vision` 新入口；dialog 仍负责显示、debug 输出开关和采样交互。 | 保留；后续可继续拆 result 文案或 player preview。 |
| `gui/dialogs/color_picker/__init__.py` | color picker helper 包入口。 | 浅入口 | 无。 | 保留。 |
| `gui/dialogs/color_picker/debug_output.py` | 预览 debug 图片/日志 opt-in 输出。 | 合格 IO helper | 输出路径由调用方传字符串。 | 保留。 |
| `gui/dialogs/color_picker/hsv_ranges.py` | BGR->HSV、采样、范围计算、平均饱和度。 | 合格纯算法 helper | 无。 | 保留。 |
| `gui/dialogs/color_picker/image_renderer.py` | 图像转 pixmap、采样 marker 绘制。 | 合格 Qt adapter | 无。 | 保留。 |
| `gui/dialogs/color_picker/preview.py` | wall HSV preview mask、morphology 和统计结果构造。 | 小纯算法 helper | 当前只复刻原 wall preview，不新增 player preview。 | 保留。 |
| `gui/dialogs/event_manager_dialog.py` | 事件管理 shell：事件页、Hooks 页、任务表、命令信号。 | 深但边界更清晰 | 事件 schema form 仍在主 dialog；Hooks 页已拆到 `event_manager/hooks/panel.py`。 | 保留 shell；后续触碰事件 schema form 时再拆 events tab。 |
| `gui/dialogs/event_manager/__init__.py` | event manager 支撑包入口。 | 浅入口 | 无业务逻辑。 | 保留。 |
| `gui/dialogs/event_manager/hooks/__init__.py` | event manager hooks 面板包导出。 | 浅入口 | 导出 `EventHookPanel`。 | 保留。 |
| `gui/dialogs/event_manager/hooks/panel.py` | Hooks 独立页，编辑 hook 实例、绑定事件类型、按键和触发时机。 | 中等 UI adapter | 从事件管理窗口传入的完整事件列表动态生成事件绑定列，只修改 `EventSystemConfig.hooks.instances`；不注册 handler、不执行输入。 | 保留；后续新增 hook 类型时扩展表格/表单。 |

## 3. 系统划分

### 3.1 Shell / Composition

范围：

- `gui/main_window.py`
- `gui/app_context.py`
- `gui/__init__.py`

目标：

- `MainWindow` 只负责窗口骨架、模式切换、关闭时调用每个 mode 的生命周期协议。
- `AppContext` 从可变对象袋变为显式服务组合根，但这个迁移要等 mode 内部 seam 稳定。

目标结构：

```text
gui/
  app_context.py                 # 兼容入口
  main_window.py                 # 兼容入口
  composition/
    services.py                  # SquareScreenCapture/Recognizer/Stitcher/Tracker/PathFinder 构造
    paths.py                     # project root、map_data、config paths
  shell/
    lifecycle.py                 # mode runtime protocol
```

第一步不需要新建完整 shell 包，只要先让 mode 暴露：

```python
MappingWidget.stop_runtime()
NavigationModeWidget.stop_runtime()
```

随后 `MainWindow.closeEvent()` 只依赖幂等 stop，不再知道 timer 或 toggle 行为。

### 3.2 Mapping Mode

当前 `MappingWidget` 同时拥有：

- 区域/中心选择 overlay 启动和结果写入。
- capture timer 生命周期。
- square / region 两种截图策略。
- player local position fallback。
- recognizer mask 提取。
- stitcher add frame。
- live capture 和 global map 渲染。
- map package 保存和 root config 保存。
- 参数控件读写。

目标结构：

```text
gui/modes/mapping/
  runtime/
    models.py                    # MappingTickResult
    session.py                   # capture -> recognize -> stitch
  capture/
    selection_controller.py      # region/center selector 生命周期
    geometry.py                  # logical/physical center 和 capture rect
  io/
    config_store.py              # root/map config 读写
  params/
    binding.py                   # widgets -> parameter dict/command
  presentation/
    map_presenter.py             # capture/global map 渲染
    renderer.py                  # 现有 map_renderer 的迁移目标
```

推荐顺序：

1. 抽 `MappingSession.tick()`，但先保留 `MappingWidget.capture_and_process()` 作为 wrapper。
2. 抽 `MappingTickResult`，承载 `current_image`、`combined_mask`、`player_pos`、`capture_size`、`global_position`。
3. 抽 `MappingPresenter`，集中 `update_displays()` 和 `map_renderer.py` 的 Qt item/pixmap 写入。
4. 把 `save_load.py` 加深为 `MappingConfigStore`，再处理 `__file__` 项目根推导。
5. `[done]` 最后拆 `create_control_panel()` 和 `create_display_panel()`：当前已迁入 `mapping/ui/layout.py`，因为 runtime、IO、presentation 和 params seam 已先稳定。

### 3.3 Navigation Mode

`NavigationModeWidget` 读完后可分为 8 条线：

| 职责线 | 当前方法群 | 目标模块 |
| --- | --- | --- |
| Widget shell | `__init__`、`init_ui`、`_connect_signals`、dialog show/hide | `navigation/ui/layout.py`、`navigation/ui/signals.py`、`presentation/dialog_host.py` |
| Map session/config | `refresh_map_list`、`load_map`、`_apply_config_to_core`、save config | `map/session.py`、`map/config_applier.py`、`map/config_store.py` |
| Route editing | click mode、exit/required/guide add/undo/clear/save | `route/editor.py` |
| Event panel/runtime bridge | event dialog、event config、manual portal test、EventTick | `events/panel_adapter.py`、`events/runtime_adapter.py` |
| Runtime loop | start/stop timer、capture、localize、observe、controller update | `runtime/loop.py`、`runtime/models.py` |
| Intent execution | `NavigationIntent` -> `MotionController` | `input/intent_executor.py` |
| Game input window mode | topmost/lower/restore | `input/window_mode.py` |
| Presentation | map item、player marker、route/event/viewport overlays、status | `presentation/map_presenter.py`、`presentation/status_presenter.py` |

目标结构：

```text
gui/modes/navigation/
  input/
    window_mode.py
    intent_executor.py
  map/
    session.py
    config_store.py
    config_applier.py
    capture_geometry.py
  route/
    editor.py
    lifecycle.py
    models.py
    panel_controller.py
  events/
    panel_adapter.py
    runtime_adapter.py
    manual_test_controller.py
  runtime/
    loop.py
    models.py
  presentation/
    calibration_feedback.py
    config_save_state.py
    event_management_state.py
    navigation_command_state.py
    route_command_state.py
    map_presenter.py
    map_load_state.py
    dialog_host.py
    debug_overlay.py
    route_overlay.py
    event_overlay.py
    viewport_overlay.py
    status_presenter.py
  calibration/
    hint_controller.py
    lifecycle.py
    screen_center.py
```

推荐顺序：

1. `stop_runtime()` 和 `start_runtime()`：先修生命周期 seam。阶段 A 已完成 stop seam，`start_runtime()` 可在后续 runtime 拆分时再补。
2. `input/window_mode.py`：小而独立，降低真实点击打到 GUI 的风险。
3. `input/intent_executor.py`：把 MOVE_MAP / CLICK_SCREEN / PRESS_KEY 分支从 widget 移出。
4. `map/config_applier.py`：集中 `NavConfig` 到 core runtime 对象的写入规则。
5. `route/editor.py`：把 route.json 变更和 click mode 从 widget 中抽出。
6. `events/panel_adapter.py`：收起 event dialog wiring、config save/reset、manual test state。
7. `presentation/map_presenter.py`：集中 QGraphics item 生命周期。
8. `runtime/loop.py`：最后抽最高耦合 tick，避免一开始就碰最大风险。

### 3.4 Dialogs

#### NavParametersDialog

优先抽绑定，不优先抽 layout。

目标结构：

```text
gui/dialogs/nav_params/
  field_specs.py                 # label、help、range、type、config path
  widget_factory.py              # spec -> Qt widget
  config_binding.py              # NavConfig <-> widget values
  sections.py                    # tabs/sections，后置步骤
  screen_estimator.py            # 已有纯 helper
```

执行顺序：

1. 抽现有 widget map 到 `config_binding.py`。
2. 抽 `set_config_to_ui()` 的字段写入表。
3. 把 movement/path/event/map 参数逐组转成 `field_specs.py`。
4. HSV text 字段最后转，因为它有 `ast.literal_eval()` 和输入不完整时不更新的特殊语义。

#### ColorPickerDialog

目标：

```text
gui/dialogs/color_picker/
  preview.py                     # build_wall_preview_mask() + stats
```

`ColorPickerDialog` 保留点选状态、模式、zoom、result packaging；mask、morphology、stats、debug 参数构造下沉到 preview。

#### AdvancedSettingsDialog

已新增 `apply_params_requested` command signal。`MappingWidget` 连接该信号后由 owner 应用 recognizer/stitcher 参数；dialog 保留 direct fallback 兼容未迁移调用方。下一步再考虑拆 tabs 或去掉 fallback。

#### EventManagerDialog

暂缓拆。它已经接近 schema-driven dialog，且通过 command-style signals 与 navigation 页面交互。只有出现第二个 schema form 时再抽通用 renderer。

### 3.5 Widgets / Selection

`widgets` 和 `selection` 不是当前主风险。推荐动作：

- `ClickableImageLabel` 保留，并可复用其坐标映射思想。
- `ScalableMapWidget` 补齐 `pixel_clicked` 语义，或删除标题和连接中的“点击设置导航点”语义。
- `CenterPointSelector`、`TransparentOverlay`、`OverlayWindow` 保留，后续可统一到 `gui/overlays/`。

## 4. 公共接口兼容规则

必须保留：

```text
gui.main_window.MainWindow
gui.app_context.AppContext
gui.modes.mapping_widget.MappingWidget
gui.modes.navigation.NavigationModeWidget
gui.dialogs.nav_params_dialog.NavParametersDialog
gui.dialogs.advanced_settings_dialog.AdvancedSettingsDialog
gui.dialogs.color_picker_dialog.ColorPickerDialog
gui.dialogs.event_manager_dialog.EventManagerDialog
```

拆分策略：

- 保留真实 public class 的原文件，例如 `MappingWidget` 和 `NavigationModeWidget`；纯 re-export 文件路径壳已经删除。
- 新模块优先由组合根调用；后续可以继续把组合根里的旧 slot wrapper 收束到明确 lifecycle/controller。
- GUI 实现侧必须直接使用 canonical core/gui 包路径，不再新增旧 core facade import 或旧 GUI wrapper import。

## 5. 风险登记

| 风险 | 位置 | 触发条件 | 建议 |
| --- | --- | --- | --- |
| 关闭窗口时反向启动/误切导航 | `MainWindow.closeEvent()` 调 `nav_widget.toggle_navigation()` | 导航未启动时关闭窗口，toggle 语义可能不等于 stop | 加 `NavigationModeWidget.stop_runtime()` 并只调用 stop。 |
| 建图地图点击不生效 | `ScalableMapWidget._mouse_press_event()` | `MappingWidget` 连接 `pixel_clicked`，但 widget 从不 emit | 实现缩放后坐标映射，或去掉该行为入口。 |
| 导航页提取过早导致行为偏移 | `_navigation_loop_unified()` | 直接抽 runtime loop 且未先隔离 input/config/event/presenter | 按小 seam 顺序拆，不先抽最大 loop。 |
| `draw_scale` 权威来源被改乱 | `_apply_config_to_core()` | 抽 config applier 时误用 config draw_scale 覆盖 map npz draw_scale | 保留 map npz draw_scale 为权威，并记录 mismatch。 |
| 配置保存丢失绘图字段 | `navigation/map/config_store.py::save_nav_config()`、`save_default_nav_config()` | 写导航配置时覆盖 root/map config | 保留 merge 写入，recognizer params 合并而非替换。 |
| dialog 直接修改 core runtime | `AdvancedSettingsDialog.apply_params()` | 未连接 `apply_params_requested` 的旧调用方仍会走 direct fallback | 全部调用方迁移后删除 fallback，只保留 owner command handler。 |
| 项目根推导脆弱 | `gui/composition/paths.py` | 文件移动、打包或 helper 迁移后路径解析错误 | 已集中为 composition paths；后续若做 application composition，再由 `AppContext` 显式持有 paths。 |

## 6. 执行计划

### 阶段 A：生命周期和明显行为缺口

1. `[done]` `MappingWidget.stop_runtime()`：停止 timer、复位 `app_context.monitoring`、按钮文本保持一致。
2. `[done]` `NavigationModeWidget.stop_runtime()`：停止 timer、禁用 motion、停止 auto navigation/manual event test、恢复 topmost。
3. `[done]` `MainWindow.closeEvent()` 改为只调用两个 stop。
4. `[done]` 补 `ScalableMapWidget.pixel_clicked` 坐标映射；拖拽不触发点击，空白区域不 emit。

### 阶段 B：Navigation 输入与配置 seam

1. `[done]` `navigation/input/window_mode.py`：封装自动输入期间主窗口取消置顶、降低、停止后恢复置顶的状态。
2. `[done]` `navigation/input/intent_executor.py`：集中消费 `MOVE_MAP`、`CLICK_SCREEN`、`PRESS_KEY`，保持 `MotionController` 调用参数不变。
3. `[done]` `navigation/map/config_applier.py`：集中 `NavConfig -> nav_core/path_finder/motion_controller/navigation_task_controller` 写入，保留 map npz draw_scale 权威规则。

### 阶段 C：Navigation route/events seam

1. `[done]` `navigation/route/editor.py`：集中 click mode、出口/必经点/途经点/撤销/清空/保存 route 命令，UI 只处理按钮和状态栏。
2. `[done]` `navigation/events/panel_adapter.py`：集中 event dialog 创建、信号重连、上下文刷新和配置摘要。
3. `[done]` `navigation/events/manual_test_controller.py`：迁移现有 `ManualEventTestController`，旧 `gui/modes/event_test_controller.py` 已删除。
4. `[done]` `navigation/events/lifecycle.py`：按深模块规则迁入事件生命周期，集中事件配置保存、portal 状态重置、portal 手动测试启停、event move runtime reset、overlay/dialog refresh 和事件日志。
5. `[done]` `navigation/route/lifecycle.py`：按深模块规则迁入 route 命令生命周期，集中加载/保存/撤销/清空后的 route_data、任务控制器、overlay 和状态栏同步。

### 阶段 D：Navigation presentation/runtime

1. `[done]` `navigation/presentation/map_presenter.py`：集中地图 scene item 创建、玩家/目标/提示点/视野框更新。
2. `[done]` `navigation/presentation/status_presenter.py`：集中导航循环状态栏文案构造。
3. `[done]` `navigation/presentation/route_overlay.py`、`viewport_overlay.py`、`event_overlay.py`：集中路线/事件 overlay 绘制和视野矩形几何，旧根路径 wrapper 已删除。
4. `[done]` `navigation/presentation/calibration_feedback.py`、`config_save_state.py`、`event_management_state.py`、`navigation_command_state.py`、`route_command_state.py`：集中 hint/calibration、导航配置保存、事件管理、导航命令和 route 命令相关结果文案，业务顺序仍在 `NavigationModeWidget`。
5. `[done]` `navigation/runtime/models.py`：新增 `NavigationLocalizationResult`，统一 `localized_pos/is_localized/confidence` 判定。
6. `[done]` `navigation/runtime/loop_helpers.py`：新增 lookahead 计算和 event-run enabled 判定，保持原公式。
7. `[done]` `navigation/runtime/frame_loop.py`：迁入完整导航帧编排；`navigation/runtime/loop.py` 保留玩家局部坐标解析、事件观测 mini-flow 和 task controller update 参数组装。
8. `[done]` `navigation/runtime/terminal_intent.py`：迁入 ARRIVED/FAILED 终态 intent 收束顺序；通过回调保持 task stop、输入窗口恢复、按钮复位和状态展示顺序。
9. `[done]` `navigation/runtime/localization_tick.py`：迁入 capture geometry、screen capture、玩家局部坐标解析和 `NavigationCore.localize()` 包装；widget 仍负责写回 `_current_capture_rect/_current_player_local_pos`。
10. `[done]` `navigation/runtime/relocalization_intent.py`：迁入 force-relocalize intent 的 `request_global_relocalization()`、事件日志、状态栏重新定位提示和本帧提前返回判定。
11. `[done]` `navigation/runtime/intent_consumption.py`：迁入 route overlay 之后的 intent 消费顺序，串联重定位短路、真实输入执行、手动事件测试 terminal 停止和 ARRIVED/FAILED 收束。
12. `[done]` `navigation/config/lifecycle.py`：按深模块规则迁入导航配置生命周期，集中参数变化、runtime 应用、当前地图保存、默认保存、dirty 状态、overlay/视野框刷新和保存反馈顺序。
13. `[done]` `navigation/map/load_lifecycle.py`：按深模块规则迁入地图加载生命周期，集中缺配置提示、配置应用、参数回填、route/event 初始化、地图渲染、退出点、overlay 和 loaded UI。
14. `[done]` `navigation/runtime/command_lifecycle.py`：按深模块规则迁入导航运行命令生命周期，集中导航启动/停止、自动导航启动/停止、timer/motion/task/input-window、按钮回滚和状态栏反馈。
15. `[done]` `navigation/map/click_lifecycle.py`：按深模块规则迁入地图点击生命周期，集中 hint、route edit、manual move 三分支、坐标转换、marker/overlay/status 和移动 guard。
16. `[done]` `navigation/calibration/lifecycle.py`：按深模块规则迁入屏幕中心校准生命周期，集中 selector 启动回调、物理坐标写回、参数回填、overlay 刷新、配置保存、完成提示和 selector 关闭。

### 阶段 E：Mapping mode

1. `[done]` `mapping/runtime/models.py`：新增 `MappingTickResult`，承载 current image、combined mask、player pos、capture size。
2. `[done]` `mapping/runtime/session.py`：迁入单帧 capture -> player local fallback -> recognizer -> stitcher -> preprocessed image 主流程。
3. `[done]` `mapping/capture/selection_controller.py`：集中区域/中心点选择 overlay 生命周期、逻辑像素到物理像素转换、monitor 配置写回；`MappingWidget` 保留旧 slot wrapper。
4. `[done]` `mapping/io/config_store.py`：迁入 project root、map_data、根配置、地图配置 JSON IO 和 mapping config payload 构造；旧 `mapping/save_load.py` 已删除。
5. `[done]` `mapping/presentation/map_presenter.py`：集中 capture label、global map widget、map crop offset 更新，复用 `map_renderer.py`。
6. `[done]` `mapping/params/binding.py`：迁入 HSV toggle、feature params、merge weight、recognizer/stitcher/geometry 控件同步；旧 `mapping/params_adapter.py` 已删除。
7. `[done]` `mapping/io/config_restore.py`：迁入 `load_saved_params()` 中根配置读取、AppContext 写回、capture selection 恢复、recognizer/stitcher 参数应用和 Qt 控件同步。
8. `[done]` `mapping/io/map_save.py`：迁入 `save_map()` 中地图目录创建、`MapStitcher.save_map_package()` 和地图级 `config.json` 写入编排；地图名输入和成功提示仍留在 widget。
9. `[done]` `mapping/ui/layout.py`：迁入控制面板滚动外壳、控制内容面板、显示面板、控件默认值和 signal wiring；`MappingWidget.setup_ui()` 只保留 UI shell wrapper，控件字段名保持不变以兼容 config restore 和 params binding。
10. `[done]` `mapping/runtime/lifecycle.py`：迁入 monitoring flag、capture timer、开始/停止按钮文案和缺少截图配置 warning；`MappingWidget.toggle_monitoring()` / `stop_runtime()` 只保留稳定入口。

### 阶段 F：Dialogs

1. `[done]` `nav_params/config_binding.py`
2. `[done]` `nav_params/field_specs.py`
3. `[done]` `color_picker/preview.py`
4. `[done]` `advanced_settings` command signal 化

### 阶段 G：GUI -> core 新系统包迁移

1. `[done]` `gui/modes/navigation/map/session.py`：`NavigationCore` 改从 `core.localization` 导入。
2. `[done]` `gui/modes/navigation/widget.py`：`RouteManager` 改从 `core.routing` 导入，`MotionController` 改从 `core.input` 导入，旧 `gui/modes/navigation_mode.py` 已删除。
3. `[done]` `gui/dialogs/color_picker_dialog.py`：`HSVRecognizer` 改从 `core.vision` 导入。
4. `[done]` `gui/app_context.py`：组合根改从 `core.platform/core.vision/core.mapping/core.routing` 明确入口创建共享服务对象，不再依赖 `core.__init__` 聚合导出。
5. `[done]` 旧 core/gui 顶层 wrapper 删除审计已执行，实际实现侧改到 canonical 包路径。

## 7. 验证策略

每个实现小步至少验证：

```powershell
python -m py_compile <本轮修改的 gui 文件>
```

关键 smoke：

- 未启动 mapping/nav 时关闭窗口不报错。
- mapping/nav 启动后关闭窗口不会保留 timer 或 motion enabled。
- `ScalableMapWidget` 点击坐标在缩放和滚动后仍映射到原图坐标。
- MOVE_MAP / CLICK_SCREEN / PRESS_KEY 对 `MotionController` 的调用参数不变。
- route editor 对 `route.json` 的 `exit_region`、`required_points`、`guide_points` 结构不变。
- `save_nav_config()` 不丢失已有 `recognizer_params` 和 mapping-only 字段。
- color picker debug 默认不落盘。
- GUI/工具脚本旧 `core.navigation_core/core.motion_controller/core.route_manager/core.recognizer_optimized` facade import、`from core import ...`、旧 GUI wrapper import 扫描应为 0。

## 8. 本轮结论

GUI 不是只需要“按行数切文件”。真正需要处理的是状态归属和跨系统 seam：

- `NavigationModeWidget` 是首要系统化目标，先拆输入、配置、路线、事件，再拆 runtime loop。
- `MappingWidget` 是第二目标，核心 runtime/session、runtime lifecycle、IO、presentation、params 和 UI layout 已完成；后续重点是 save-map presentation、AppContext/path 注入或高级参数 dialog。
- `NavParametersDialog` 要先抽字段绑定和规格，再抽 tabs。
- `EventManagerDialog` 当前结构反而较好，应作为 schema-driven 样板暂缓拆。
- `widgets/selection` 大体可保留，只修 `ScalableMapWidget.pixel_clicked` 这种明确行为缺口。





