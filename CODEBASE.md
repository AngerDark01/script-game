# CODEBASE

## 当前补充：Navigation 首帧定位诊断

2026-06-04 新增独立首帧定位探针：`D:\ACloud\.venv\Scripts\python.exe debug\navigation_localization_probe.py --map-folder "D:\ACloud\minimap_stitcher copy 13\map_data\A" --image "D:\ACloud\minimap_stitcher copy 13\debug\minimap_samples\A\20260604_135548_439_A_minimap.png" --top 10`。探针只用于诊断，不接入正式导航循环；它复用正式 `NavigationCore`、`HSVRecognizer`、`NavConfig` 的识别参数、`map_data.npz` 的 `draw_scale/wall_close_kernel_size`，然后输出 `report.json`、`wall_mask.png`、`match_mask.png`、`wall_mask_scaled.png`、`matched_map_patch.png`、`saved_pos_patch.png` 和 `top_candidates_sheet.png`。

本轮样本最新输出目录：`debug/navigation_localization_probe/20260604_142234_20260604_135548_439_A_minimap/`。结果显示当前生产链路首帧全图匹配最高候选为 `(4211,3272)`，confidence=`0.7745`，`frame_origin_global=(3911,2972)`；`map_data.npz` 保存的 `current_pos=(4792.48,3630.25)` 在同一张 `matchTemplate` 响应图上的分数为 `-0.0208`。配置侧没有发现 `draw_scale` 漂移：`config_draw_scale=3.0`、`map_draw_scale=3.0`、`used_draw_scale=3.0`，模板尺寸为 `600x600`。因此当前证据指向“首帧全局模板匹配根据地图墙体选择了另一块高相似区域”，不是掉落物事件、hook 或异步事件线程修改了人物定位坐标。

状态保留修正：`core/localization/navigation_core/state.py::initialize_runtime_state()` 现在保留 `map_data.npz` 读出的 `drawing_saved_pos/last_pos`，用于 UI 上次位置 marker 和首帧 debug 对比；它不会自动把保存点设为 `current_pos`，也不会把 `is_localized` 设为 true，因此不会改变首帧定位算法。复跑探针确认结果仍为 `(4211,3272)`，但首帧 debug 会打印保存点差异 `dx=-581.48, dy=-358.25`。

运行时坐标诊断同步增强：`core/navigation_tasks/coordinate/localization.py` 每 `localization_sample_interval_ms=500` 记录一条 `localization sample`，字段包含 raw/trusted/control、confidence、invalid_reason、active_task、registration source/conf/player/local/origin，以及 `shift`、`visual_delta_dist`、`template_top_left`、`search_offset`、`forced_global` 等关键 metadata。`core/navigation_tasks/coordinate/log.py` 写入项目根目录 `logs/coordinate_diagnostics.log`，并桥接到当前 event session log，方便实跑后直接对齐事件日志和定位日志。

## 当前补充：Loot 掉落物事件

本轮新增正式事件类型 `loot`。实现位置为 `core/events/types/loot/`，正向模板资产在 `assets/event_templates/loot/minimap/`，人物箭头负样本在 `assets/event_templates/loot/exclude/player_marker/`，单图/handler 验证入口为 `debug/loot_event_probe.py`，批量正负样本评估入口为 `debug/loot_dataset_eval.py`。`gui/modes/navigation/event_adapter.py::create_default_event_registry()` 当前默认注册 `PortalEventDefinition()` 和 `LootEventDefinition()`；`core/events/config_model.py::DEFAULT_EVENT_CONFIG` 已包含 `events.loot` 默认配置。

2026-06-03 新增数据集回归入口：`D:\ACloud\.venv\Scripts\python.exe debug\loot_dataset_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json`。脚本读取 `02_has_loot` / `03_no_loot` 作为正负标签，每张图独立创建 detector，并按 `presence_confirm_frames` 连续喂帧；输出 `summary.json`、`cases.csv` 和 FP/FN overlay，默认关闭 runtime diagnostic 落盘。当前基线输出在 `debug/loot_dataset_eval/20260603_104108/`：77 张样本中 TP=25、FP=52、FN=0、TN=0，precision=0.3247、recall=1.0000、FPR=1.0000，平均检测耗时约 215.747ms。误检分数低于地图 A 的 `weighted_threshold=0.70`，说明后续优化重点是 `detection.scoring.accepted_candidate()` 的强证据直通路径和 accepted 后排除规则，而不是只调高总阈值。

2026-06-03 新增独立 ROI 多特征匹配探针：`D:\ACloud\.venv\Scripts\python.exe debug\loot_feature_match_probe.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --dump-all`。该脚本验证“ROI 内滑窗 + masked template + edge overlap + Chamfer + HOG-lite + 轮廓/Hu + 颜色辅助”的 CNN-like 特征响应定位思路；同一套核心算法已经抽到 `core/events/types/loot/detection/feature_match/`，并通过 `detector_mode=async_feature_match` 接入正式 runtime。默认只匹配黄钻、红星、金三角三个形状明确的模板，尺度为 `0.75,0.85,1.0`，每模板每 ROI 取 `top_k=2`，并按模板类型施加语义门槛。探针默认和正式默认必须保持一致：`feature_match_threshold=0.64`、`feature_match_collect_threshold=0.38`、`feature_match_top_k_per_template=2`、`feature_match_max_candidates=5`、`feature_match_search_padding=48`、`feature_match_scales="0.75,0.85,1.0"`。最新完整样本输出在 `debug/loot_feature_match_probe/20260603_174004/`：TP=25、FP=0、FN=0、TN=52，precision=1.0000、recall=1.0000、FPR=0.0000，平均耗时约 341.366ms、p95 约 664.686ms。线程并行 `--workers 4` 墙钟略降但单张图延迟显著上升，因此生产接入采用独立 worker 线程，而不是帧内并行。

`loot` 检测主链路：`LootMinimapDetector.detect(tick, config)` 读取 `tick.raw_minimap_frame`，先调用 `detection.pipeline.detect_loot_presence()` 做轻量存在判断。粗检只构造 HSV 金色/暖色/银白/高亮 mask，并在小地图中心按人物箭头负模板确认后挖掉固定玩家区域；小尺寸图标样本会跳过中心遮罩，避免整张模板样本被擦掉。默认 `detector_mode="async_feature_match"`：存在判断连续达到 `presence_confirm_frames=2` 后，`AsyncLootPerception.maybe_submit()` 在独立 worker 线程复制当前帧并调用 `FeatureLootMatcher.detect()`，主线程只读取缓存 detection，不阻塞导航循环。worker 把命中的局部点投影为全局记录，后续帧只用当前 `FrameRegistration` 把缓存记录投回局部 detection；`async_full_scan_interval_ms=1000` 限制全量提交频率，`async_track_refresh_ms=8000` 避免已知目标被反复全量重识别，`async_track_ttl_ms=8000` 和 absence streak 控制消失。`detector_mode="feature_match"` 是同步回归模式，直接调用同一套 feature matcher；`detector_mode="weighted_blob"` 保留旧三路加权后端，调用 `detect_loot_blobs(frame, prepared_templates, config, exclusion_templates, seed_bboxes=...)`。detector 初始化阶段会预先生成正向模板、feature 模板和人物箭头负模板的多尺度灰度图、边缘图、mask，避免每帧重复 resize/Canny。

2026-06-03 17:40 接入一致性验证：生产 `FeatureLootMatcher.detect()` 同步路径在 `D:/ACloud/image/sample` 上跑出 TP=25、FP=0、FN=0、TN=52；生产默认 `LootMinimapDetector(detector_mode="async_feature_match")` 在同一数据集上模拟有效 `FrameRegistration` 并等待 worker 返回，也跑出 TP=25、FP=0、FN=0、TN=52，默认参数打印为 `async_feature_match 0.64 0.38 2 5 48 0.75,0.85,1.0`。因此后续测试异步路径时需要等待 worker 完成，不能把“本帧尚未返回检测”视为算法漏检。

人物处理现在分两层：`detection.roi.apply_player_center_mask()` 先在粗检 mask 层处理固定中心人物位置，只在中心 patch 有足够亮/金/白/蓝像素且负模板命中人物箭头时，按 `player_center_mask_radius=28` 挖空中心人物前景；候选通过模板/外形/颜色评分后，`detection.seed_scan._best_candidate_for_seed()` 和旧区域扫描路径还会只对已接受候选调用 `detection.exclusions.is_player_marker_candidate()` 与 `is_blue_map_artifact_candidate(patch, shape_score)`。后者用蓝/青底比例、金色比例、亮白比例、白色比例和候选外形分数过滤人物底色、蓝白地图装饰、边线等误检；因为只在 accepted 候选出口执行，成本被 seed 粗检和局部复核限制住。当前掉落物模板和人物负样本模板均为带 alpha 的透明 PNG，`detection.images.foreground_mask()` 会优先使用 alpha 作为匹配 mask，避免小地图背景参与模板响应。2026-06-09 起，`gui/modes/navigation/presentation/event_overlay.py` 会在导航地图上显示中心人物遮罩范围，开关为 `player_center_mask_overlay_enabled=true`，圆半径按 `player_center_mask_radius * nav_core.draw_scale` 换算。随后 `detection.clustering.cluster_candidates()` 把堆叠或相邻候选合并成区域级 `LootCluster`。`detection.conversion.clusters_to_detections()` 将 blob center 写入 `EventDetection.local_minimap_pos`，metadata 写入 bbox、候选数、命中模板、三路分数和 `pickup_radius`。

`loot` 执行主链路：`EventCoordinator.observe()` 仍负责 detect -> position stabilize -> memory merge；`NavigationTaskBuilder.build()` 把 loot `EventTask.metadata["pickup_radius"]` 写入 `NavigationTask.radius` 和 `metadata["event_stop_radius"]`；`EventApproachController.update()` 优先使用 per-task `event_stop_radius`，因此 loot 在拾取半径内停稳后释放给 handler。`LootPickupHandler.update(tick, task)` 距离远时返回 `EventAction.move_to(task.global_pos)`，进入 `pickup_radius` 后返回 `EventAction.press_key(pickup_key)`，默认 `a`；按键后等待 `post_pickup_wait_ms`，若 `task.last_seen_ms` 超过 `absence_confirm_frames * absence_frame_ms` 未刷新，则返回 `EventAction.complete()`。

`loot` 事件定位不是全图定位。`EventPositionStabilizer.project_detection()` 只用当前帧 `FrameRegistration.frame_origin_global + detection.local_minimap_pos * draw_scale` 把小地图局部检测点投影到全局坐标，不调用 `NavigationCore` 的模板全图搜索。移动时“像一直重定位”的体感来自另一条链路：掉落物是 blob/区域目标，检测中心会随堆叠、遮挡和小地图运动轻微漂移；旧 `EventTask.mark_seen()` 每次稳定观测都会覆盖 `task.global_pos`，导致 `NavigationTaskBuilder` 生成的新事件目标点变化，`MovementExecutor.ensure_movement_path()` 因目标变化触发 A* 重规划和重复点击。当前通过 `core/events/memory/target_update.py::should_update_task_target()` 增加事件级目标更新策略，loot 默认 `target_update_mode="lock_after_confirm"`：task 确认进入 `PENDING/RUNNING` 后锁定首次目标，只刷新 `last_seen_ms`、`confidence`、`seen_count`、metadata 和 `last_observed_global_pos`，不再拖动导航目标。这样消失确认仍由最新观测时间驱动，但 A* 目标不会被每次 blob center 漂移带着跑。2026-06-09 起 portal 也恢复锁点配置，默认 `target_update_mode="limited_after_confirm"`、`target_update_max_drift=18`，用于拒绝相邻稳定簇之间的大幅跳点，同时允许确认前和小范围内的稳定修正。

关键参数：`priority=60`、`detector_mode="async_feature_match"`、`feature_match_threshold=0.64`、`feature_match_collect_threshold=0.38`、`feature_match_top_k_per_template=2`、`feature_match_max_candidates=5`、`feature_match_search_padding=48`、`feature_match_scales="0.75,0.85,1.0"`、`async_full_scan_interval_ms=1000`、`async_track_refresh_ms=8000`、`async_track_ttl_ms=8000`、`async_known_seed_radius=72`、`weighted_threshold=0.54`、`collect_threshold=0.28`、`detection_interval_ms=450`、`reuse_previous_detections=true`、`presence_confirm_frames=2`、`masked_color_match_enabled=true`、`roi_prefilter_enabled=true`、`roi_min_area=12`、`roi_max_size=150`、`roi_expand=48`、`template_weight=0.46`、`shape_weight=0.42`、`color_weight=0.12`、`player_marker_exclusion_enabled=true`、`player_marker_template_threshold=0.75`、`player_marker_exact_template_threshold=0.96`、`player_marker_blue_ratio_threshold=0.30`、`player_center_mask_enabled=true`、`player_center_mask_overlay_enabled=true`、`player_center_mask_radius=28`、`max_blobs_per_frame=3`、`target_update_mode="lock_after_confirm"`、`target_update_max_drift=0`、`arrival_radius=90`、`pickup_radius=58`、`pickup_key="a"`、`post_pickup_wait_ms=450`、`absence_confirm_frames=2`、`pickup_press_limit=3`、`cooldown_radius=180`。旧地图配置若还没有 `roi_prefilter_enabled` 字段，会自动迁移到新的性能默认，避免旧的 `masked_color_match_enabled=false` 覆盖新召回策略。portal 默认优先级仍为 100，且默认 `target_update_mode="limited_after_confirm"`、`target_update_max_drift=18`，因此默认调度下传送门优先于顺路拾取，并且确认后不会被大幅跳动观测拖走。

单独验证命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --handler-smoke
```

断言式单图探针：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 173,112 --center-tolerance 8
```

性能探针命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --benchmark --handler-smoke
```

事件目标漂移探针：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --target-jitter-smoke
```

相关中文文档：`architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`。

## 1. 项目概览
PySide6 + OpenCV 的实时小地图拼接与导航工具。绘图模式从游戏小地图截图提取 HSV/墙体特征并写入 `map_data/<name>/map_data.npz`；导航模式读取同一份地图数据、用实时截图定位玩家全局地图坐标，并可基于用户设置的出口、必经点、途经点执行自动导航。当前任务相关的关键约束是：定位截图范围、地图全局坐标、真实主画面点击范围必须分离，不能用旧偏移参数修正定位。

## 2. 目录结构图
```text
main.py - 创建 QApplication 和 MainWindow。
gui/app_context.py - 从 core 系统包初始化共享服务：SquareScreenCapture、HSVRecognizer、MapStitcher、PlayerTracker、PathFinder。
gui/main_window.py - 创建绘图/导航两个模式并共享 AppContext。
gui/navigation_params.py - 定义 NavConfig、RecognizerParams、NavPreferences，并负责 config.json 序列化契约。
gui/composition/__init__.py - GUI composition helper 包入口。
gui/composition/paths.py - GUI 项目根、map_data、根配置和高级参数目录解析 helper。
gui/composition/services.py - GUI 共享 core service DTO 和默认构造工厂。
architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md - GUI 下一阶段结构化优化规划，按 Shell、Navigation、Mapping、Dialogs 分阶段拆分并保留旧入口兼容。
architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md - GUI 全文件级审计与细化拆分规划，覆盖所有 gui 实现文件并给出每个文件的保留、加深、迁移或拆分动作。
architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md - core/gui 后续工程化优化执行基准，定义剩余任务、每轮流程、验证命令和阶段结束标准。
gui/dialogs/nav_params_dialog.py - 导航参数 UI，按定位识别/算法/移动/路径/调试分页，使用 widget_map 将控件变化写回 NavConfig。
gui/dialogs/nav_params/__init__.py - 导航参数 helper 包入口。
gui/dialogs/nav_params/field_specs.py - 导航参数可编辑字段规格表，描述控件属性名、配置路径、写入方式和分组。
gui/dialogs/nav_params/config_binding.py - 导航参数 `NavConfig` 字段绑定、文本解析、dataclass replace 和控件回填 helper。
gui/dialogs/nav_params/screen_estimator.py - 根据校准中心点和屏幕物理边界估算安全点击半径。
gui/dialogs/event_manager_dialog.py - 独立事件管理窗口，提供事件配置页和 Hooks 配置页。
gui/dialogs/event_manager/__init__.py - 事件管理弹窗支撑包入口。
gui/dialogs/event_manager/hooks/__init__.py - 事件管理 Hooks 面板包入口。
gui/dialogs/event_manager/hooks/panel.py - Hooks 独立页，编辑可注册 hook 实例、按键和触发时机。
gui/dialogs/advanced_settings_dialog.py - 高级参数弹窗主类，组合图像预处理、特征、参数管理和拼接算法 tabs。
gui/dialogs/advanced_settings/__init__.py - 高级参数弹窗 helper 包入口。
gui/dialogs/advanced_settings/file_io.py - 高级参数 JSON snapshot 保存/加载、文件名清洗和显式配置目录 helper。
gui/dialogs/advanced_settings/params_adapter.py - 高级参数弹窗控件与参数 dict/预设之间的映射 helper。
gui/dialogs/advanced_settings/presets.py - 高级参数预设名称顺序和控件值数据表。
gui/dialogs/color_picker_dialog.py - 交互式 HSV 颜色采样弹窗，负责采样点交互、预览显示和 debug 输出调度。
gui/dialogs/color_picker/__init__.py - 颜色选择弹窗 helper 包入口。
gui/dialogs/color_picker/debug_output.py - 颜色选择预览 debug 图片/日志输出 helper，并通过环境变量控制是否落盘。
gui/dialogs/color_picker/hsv_ranges.py - 颜色选择弹窗 HSV 转换、采样值提取和范围计算 helper。
gui/dialogs/color_picker/image_renderer.py - 颜色选择弹窗 OpenCV 图像转 QPixmap 和采样点 marker 绘制 helper。
gui/dialogs/color_picker/preview.py - 颜色选择弹窗 wall HSV preview mask、形态学处理和统计结果 helper。
gui/widgets/clickable_label.py - 可点击图像标签，负责显示坐标到原始图像坐标的转换。
gui/widgets/scalable_map.py - 可缩放/拖拽地图显示 widget，并在非拖拽点击时 emit 原图坐标 `pixel_clicked`。
gui/widgets/collapsible_group.py - 带缩放按钮的可折叠地图组。
gui/modes/navigation/__init__.py - 导航模式包入口，导出新的 canonical `NavigationModeWidget`。
gui/modes/navigation/widget.py - 导航模式 QWidget 组合根和临时 facade，负责创建生命周期对象并调用 UI builder/signal binder；旧长 docstring 已压缩为 wrapper 级说明。
gui/modes/navigation/composition/__init__.py - 导航局部 composition 包入口，导出 lifecycle 初始化函数。
gui/modes/navigation/composition/lifecycles.py - 导航页 lifecycle/controller wiring 组合模块，按顺序创建 display/config/route/events/map/runtime/calibration lifecycle。
gui/modes/navigation/ui/__init__.py - 导航 UI shell 包入口，导出布局构建和信号绑定 helper。
gui/modes/navigation/ui/layout.py - 导航页顶部工具栏、地图 scene/view、状态栏和 route panel 的控件构建 helper。
gui/modes/navigation/ui/signals.py - 导航页按钮、参数弹窗和事件弹窗的信号绑定 helper。
gui/modes/navigation/display/__init__.py - 导航地图显示生命周期包入口。
gui/modes/navigation/display/lifecycle.py - 导航地图 scene item、route/event overlay、监控框/视野框和上次退出点显示的状态写入 lifecycle。
gui/modes/navigation/event_adapter.py - 导航模式与事件系统之间的轻量桥接 helper。
gui/modes/navigation/input/__init__.py - 导航输入 adapter 包入口。
gui/modes/navigation/input/window_mode.py - 自动输入期间主窗口取消置顶、降低和停止后恢复置顶的状态 adapter。
gui/modes/navigation/input/intent_executor.py - 将 `NavigationIntent` 的 MOVE_MAP/CLICK_SCREEN/PRESS_KEY 分发到 `MotionController`。
gui/modes/navigation/hooks/__init__.py - 导航 hook runtime 注册包入口。
gui/modes/navigation/hooks/registration.py - 将 `event_config.hooks.instances` 注册到 `NavigationTaskController.event_hooks`，并通过 `MotionController` 执行按键 hook。
gui/modes/navigation/config/__init__.py - 导航配置生命周期包入口。
gui/modes/navigation/config/lifecycle.py - 导航配置参数变化、runtime 应用、当前地图保存、默认保存和反馈顺序的状态 facade。
gui/modes/navigation/map/__init__.py - 导航地图/config adapter 包入口。
gui/modes/navigation/map/click_lifecycle.py - 导航地图点击生命周期 facade，编排 hint、route 编辑和手动移动目标三分支。
gui/modes/navigation/map/session.py - 导航地图加载前置 session helper，封装 map folder 解析、NavConfig 读取、NavigationCore 创建和初始物理中心计算。
gui/modes/navigation/map/load_lifecycle.py - 导航地图加载生命周期 facade，编排缺配置提示、配置应用、参数回填、route/event 初始化、地图渲染和加载完成 UI。
gui/modes/navigation/map/config_applier.py - 将 `NavConfig` 应用到 nav_core、PathFinder、MotionController 和 NavigationTaskController。
gui/modes/navigation/map/event_filter.py - Qt scene 鼠标事件解释 helper，转发左键地图点击。
gui/modes/navigation/map/config_store.py - 导航地图目录、NavConfig JSON 读写、默认配置 fallback 和 merge 保存真实实现。
gui/modes/navigation/map/capture_geometry.py - 导航截图 logical/physical 中心换算和 capture rect/player pos 几何真实实现。
gui/modes/navigation/calibration/__init__.py - 导航校准 helper 包入口。
gui/modes/navigation/calibration/lifecycle.py - 屏幕中心校准生命周期 facade，编排选择器启动、物理坐标写回、参数回填、overlay 刷新、配置保存和完成反馈。
gui/modes/navigation/calibration/screen_center.py - 屏幕中心校准选择器生命周期和逻辑坐标到物理坐标转换 helper。
gui/modes/navigation/route/__init__.py - 导航 route editing adapter 包入口。
gui/modes/navigation/route/editor.py - 导航 route click mode 和 route.json 编辑命令 adapter。
gui/modes/navigation/route/lifecycle.py - 导航 route 命令生命周期 facade，同步 route_data、NavigationTaskController、overlay 和状态栏反馈。
gui/modes/navigation/route/panel_controller.py - 导航 route 按钮状态、状态栏文案和 route editor 命令结果 controller。
gui/modes/navigation/events/__init__.py - 导航事件 UI adapter 包入口。
gui/modes/navigation/events/bootstrap.py - 地图加载后的事件系统 runtime 初始化。
gui/modes/navigation/events/dialog_lifecycle.py - 事件管理弹窗创建、接线、刷新和显示切换生命周期。
gui/modes/navigation/events/manual_test_controller.py - 手动事件测试按钮状态控制器。
gui/modes/navigation/events/lifecycle.py - 导航事件生命周期 facade，编排事件配置保存、portal 状态重置和手动事件测试启停。
gui/modes/navigation/events/panel_adapter.py - 事件管理窗口创建、信号重连、上下文刷新和配置摘要 adapter。
gui/modes/navigation/presentation/__init__.py - 导航 presentation helper 包入口。
gui/modes/navigation/presentation/calibration_feedback.py - 初始位置提示、hint mode 和屏幕中心校准完成反馈 helper。
gui/modes/navigation/presentation/config_save_state.py - 导航参数保存/默认配置保存结果的状态标签和 QMessageBox helper。
gui/modes/navigation/presentation/event_management_state.py - 事件管理保存、传送门状态重置和手动测试反馈的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/navigation_command_state.py - 自动导航和导航启动/停止命令的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/route_command_state.py - route 命令结果、路线保存失败和移动目标反馈的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/map_presenter.py - 导航地图 scene item 创建、定位显示、玩家/目标/提示点/视野框更新 presenter。
gui/modes/navigation/presentation/map_load_state.py - 导航地图列表 combo、地图加载成功 UI 状态和地图/overlay 加载反馈 helper。
gui/modes/navigation/presentation/dialog_host.py - 导航 owned dialog 显示、置顶、恢复最小化和重复点击隐藏判定 helper。
gui/modes/navigation/presentation/debug_overlay.py - 导航 debug 幕布窗口的几何写入、隐藏和显示 helper。
gui/modes/navigation/presentation/route_overlay.py - 导航路线、出口、必经点、途经点、当前路径和子目标 overlay 绘制真实实现。
gui/modes/navigation/presentation/event_overlay.py - 导航事件 marker overlay 绘制和事件 overlay item 清理真实实现。
gui/modes/navigation/presentation/status_presenter.py - 导航循环状态栏文案构造、写入和后缀追加 helper。
gui/modes/navigation/presentation/viewport_overlay.py - 导航屏幕幕布、监控绿框、真实主画面橙框的矩形计算真实实现。
gui/modes/navigation/runtime/__init__.py - 导航 runtime helper 包入口。
gui/modes/navigation/runtime/command_lifecycle.py - 导航运行命令生命周期 facade，编排导航启动/停止、自动导航开关、timer/motion/task/input-window 状态和按钮回滚。
gui/modes/navigation/runtime/frame_loop.py - 导航定时器单帧 runtime facade，编排截图定位、事件观测、任务更新、展示刷新和 intent 消费。
gui/modes/navigation/runtime/minimap_sample_capture.py - 小地图监视区域样本采集 helper，保存 PNG 截图和同名 JSON 元数据。
gui/modes/navigation/runtime/models.py - 导航循环定位结果 DTO。
gui/modes/navigation/runtime/intent_consumption.py - 导航 intent 消费编排 helper，串联重定位短路、真实输入执行、手动事件测试停止和终态收束。
gui/modes/navigation/runtime/localization_tick.py - 导航单帧截图、玩家局部坐标解析和定位结果构造 helper。
gui/modes/navigation/runtime/loop_helpers.py - 导航循环 lookahead 和任务运行开关纯 helper。
gui/modes/navigation/runtime/loop.py - 导航循环玩家局部坐标解析、事件观测和 NavigationUpdateContext 组装 helper。
gui/modes/navigation/runtime/relocalization_intent.py - 导航 force-relocalize intent 的全局重定位请求、事件日志和状态展示 helper。
gui/modes/navigation/runtime/terminal_intent.py - 导航终态 intent 收束 helper，封装 ARRIVED/FAILED 的任务停止、输入窗口恢复、按钮复位和终态展示回调顺序。
gui/modes/mapping_widget.py - 绘图模式主 UI、截图建图循环、地图显示和参数控件同步。
gui/modes/mapping/__init__.py - 绘图模式拆分 helper 包入口。
gui/modes/mapping/ui/__init__.py - 绘图模式 UI 构建包入口。
gui/modes/mapping/ui/layout.py - 绘图模式控制面板、显示面板和控件信号连接构建 helper。
gui/modes/mapping/capture/__init__.py - 绘图模式 capture selection 包入口。
gui/modes/mapping/capture/selection_controller.py - 绘图模式区域/中心点选择 overlay 生命周期和 monitor 配置写回 controller。
gui/modes/mapping/runtime/__init__.py - 绘图模式 runtime 包入口。
gui/modes/mapping/runtime/lifecycle.py - 绘图模式监控启动/停止、capture timer 和 monitoring 状态 lifecycle。
gui/modes/mapping/runtime/models.py - 绘图模式单帧 tick 结果 DTO。
gui/modes/mapping/runtime/session.py - 绘图模式单帧 capture-recognize-stitch 主流程 session。
gui/modes/mapping/presentation/__init__.py - 绘图模式 presentation 包入口。
gui/modes/mapping/presentation/map_presenter.py - 绘图模式 capture/global map display 写入 presenter。
gui/modes/mapping/map_renderer.py - 绘图模式 BGR/QPixmap 转换和全局地图 overlay 绘制 helper。
gui/modes/mapping/params/__init__.py - 绘图模式 params binding 包入口。
gui/modes/mapping/params/binding.py - 绘图模式参数控件与 recognizer/stitcher 运行时参数之间的桥接 helper。
gui/modes/mapping/io/__init__.py - 绘图模式 IO helper 包入口。
gui/modes/mapping/io/config_store.py - 绘图模式项目路径、map_data 目录、config.json 读写和 mapping config payload 构造 helper。
gui/modes/mapping/io/config_restore.py - 绘图模式启动配置恢复编排，负责根配置读取、AppContext 写回、capture selection 恢复和 Qt 控件同步。
gui/modes/mapping/io/map_save.py - 绘图模式保存地图包和地图级 config 的 IO 编排 helper。
core/routing/__init__.py - 路径规划系统包入口，聚合 obstacles/pathfinder/geometry/anchors/route_repository。
core/routing/obstacles.py - 从原始 wall_layer 派生 A* 专用的宽容障碍层，不改变定位用墙图。
core/routing/pathfinder/__init__.py - A* pathfinder package 入口，导出 `PathFinder`。
core/routing/pathfinder/runtime.py - `PathFinder` 真实 class，保留构造参数、`find_path()` 和旧私有 helper wrapper。
core/routing/pathfinder/grid.py - 障碍网格构建、explored map 未知区阻挡、安全边距膨胀和起点附近清障。
core/routing/pathfinder/astar.py - 8 邻接 A* 主循环、禁止斜向穿角、启发式和路径回溯。
core/routing/pathfinder/snap.py - 起点/终点落入障碍时的最近可走格搜索。
core/routing/pathfinder/coordinates.py - map-space/grid-space 坐标转换和 grid path 转全局路径点。
core/routing/geometry.py - 路径平滑、投影、插值、出口区域判断兼容工具；投影/累计长度/插值委托 `routing/route_progress`。
core/routing/route_progress/__init__.py - 统一折线进度算法包入口，导出 `PolylineProjection`、累计长度、投影和插值 helper。
core/routing/route_progress/models.py - `PolylineProjection` DTO，统一表示投影点、累计 progress、segment index 和偏离距离。
core/routing/route_progress/projection.py - 折线累计长度、点到折线投影和按累计距离插值的权威实现。
core/routing/anchors/__init__.py - 可选软锚点路径规划 package 入口，导出旧 `AnchorPathResult`、规划函数和进度 helper。
core/routing/anchors/models.py - `AnchorPathResult` DTO。
core/routing/anchors/utils.py - anchor 路径点整数化和朝锚点 probe 点计算 helper。
core/routing/anchors/progress.py - anchor 去重、进度 map 和旧 helper wrapper；累计距离/折线投影委托 `routing/route_progress`。
core/routing/anchors/corridor.py - 按 start/target progress 选择前方 ordered guide anchors。
core/routing/anchors/planner.py - anchor_step、anchor_probe、planned 三类路径规划主流程。
core/routing/route_repository.py - `route.json` 读写、出口/必经点/途经点编辑和内存缓存。
core/input/__init__.py - 输入系统包入口，聚合 motion mapping、点击执行、点击诊断、屏幕边界和 Win32 输入 adapter。
core/input/motion_mapping.py - 纯地图目标到屏幕点击坐标、近目标精确点击和底部禁点投影策略。
core/input/click_executor.py - 真实鼠标点击发送 helper，封装 Win32 mouse_event 后端、pydirectinput 后端和 confirm click。
core/input/click_diagnostics.py - 点击点窗口、前台窗口、ClipCursor 和 Win32 光标位置诊断 helper。
core/input/click_pipeline.py - `MotionController._execute_click()` 的点击流程编排 helper，维护 bottom guard、clamp、诊断、发送、fallback 顺序。
core/input/screen_bounds.py - 屏幕高度读取和可选点击坐标 clamp helper。
core/input/win32_driver.py - Win32 输入 adapter，封装鼠标移动/点击、窗口描述、前台窗口和光标裁剪查询。
core/input/motion_controller/__init__.py - MotionController helper package 入口，聚合 controls、targets 和 backend helper。
core/input/motion_controller/controls.py - MotionController 参数设置、control enablement、显式屏幕点击和按键 helper。
core/input/motion_controller/targets.py - MotionController 普通移动点击、事件精确地图点击、目标屏幕坐标计算和 bottom guard wrapper。
core/input/motion_controller/backend.py - MotionController lazy InputDriver、screen clamp、pydirectinput 安全调用、点击发送和窗口信息格式化 wrapper。
core/platform/__init__.py - 平台适配包入口。
core/platform/screen_capture.py - mss/PIL 屏幕截图 adapter，正式导出 `SquareScreenCapture`。
core/vision/__init__.py - 图像识别和追踪包入口。
core/vision/hsv_recognizer.py - HSV/wall/fog/player 特征提取器 facade，保留 `HSVRecognizer` 旧类入口。
core/vision/hsv/__init__.py - HSV recognizer 子模块入口，聚合参数、预处理、mask 和 combined pipeline helper。
core/vision/hsv/params.py - `HSVRecognizer` 参数快照和局部应用 helper。
core/vision/hsv/preprocessing.py - wall/fog 预处理、透明地图 score 和 raw gray matching helper。
core/vision/hsv/masks.py - wall/fog/player mask 提取和小连通域过滤 helper。
core/vision/hsv/combined.py - `extract_combined()` 的动态颜色过滤、中心清理和 weighted match mask 组合 helper。
core/vision/player_tracker.py - 玩家局部位置检测和轨迹绘制实现。
core/vision/phase_displacement.py - phase-correlation 位移估计 helper。
core/shared/__init__.py - core 跨系统共享契约包入口。
core/shared/frame_registration.py - 定位和事件系统共享的帧配准契约。
core/shared/diagnostics/__init__.py - 跨系统诊断纯格式化 helper 包入口。
core/shared/diagnostics/formatting.py - 共享 `format_value()`、`format_fields()`，供事件日志和坐标诊断日志复用。
core/mapping/__init__.py - 建图系统包入口，聚合 `MapStitcher`、地图包 IO、帧流程、融合和渲染 helper。
core/mapping/stitcher.py - `MapStitcher` 真实实现，维护 wall/fog/explored/current_pos/keyframe 状态并委托 mapping helper。
core/mapping/package_io.py - `MapStitcher` 的 `map_data.npz` 保存/加载 helper。
core/mapping/performance.py - `MapStitcher` 的性能计时器和 rolling timing 记录 helper。
core/mapping/frame_preparation.py - `MapStitcher` 的帧 mask 缩放、墙体厚度标准化、重复帧相似度和画布边界计算 helper。
core/mapping/frame_pipeline.py - `MapStitcher.add_frame()` 的 keyframe/F2F 配准、低质量跳过、落图和统计更新流程 helper。
core/mapping/weighted_merge.py - `MapStitcher` weighted frame merge helper，更新 wall/fog/explored/canvas layers。
core/mapping/rendering.py - `MapStitcher` cropped/enhanced map display rendering helper。
core/localization/__init__.py - 导航定位系统包入口，聚合 `NavigationCore` 和定位 helper。
core/localization/navigation_core/__init__.py - NavigationCore 运行时包入口。
core/localization/navigation_core/runtime.py - `NavigationCore` 真实 class，保留旧 public/private 方法并委托定位 helper。
core/localization/navigation_core/state.py - `NavigationCore` 构造期配置、地图路径和运行态字段初始化 helper。
core/localization/navigation_core/registration.py - `NavigationCore.last_frame_registration` 写回 wrapper。
core/localization/navigation_core/relocalization.py - 初始位置提示、强制全图重定位和模板匹配阈值策略 helper。
core/localization/navigation_core/wall_layer.py - 导航墙层派生、墙体闭运算 kernel 和模板标准化 wrapper。
core/localization/navigation_core/diagnostics.py - 定位模板匹配失败的节流日志 helper。
core/localization/map_package.py - `NavigationCore` 的 `map_data.npz` 加载和缺省字段处理 helper。
core/localization/localize_pipeline.py - `NavigationCore.localize()` 的 F2F、模板匹配、强制重定位和状态写入流程 helper。
core/localization/rendering.py - `NavigationCore.get_map_image()` 的显示地图渲染和 crop offset 写入 helper。
core/localization/frame_registration.py - `NavigationCore.last_frame_registration` 的有效/无效配准对象构建 helper。
core/localization/frame_matcher.py - 导航定位模板匹配的墙体模板缩放、闭运算标准化和局部/全图搜索窗口选择 helper。
core/localization/visual_check.py - F2F 跟踪期间的截图-地图视觉一致性复核 helper。
core/localization/evidence/__init__.py - 定位证据包入口，导出 `LocalizationEvidence`、`VisualCheckEvidence` 和 evidence builder。
core/localization/evidence/models.py - 定位证据 DTO，稳定承载 raw/trusted/control 坐标、confidence、registration 字段和 visual check 证据。
core/localization/evidence/builder.py - 从 `FrameRegistration`、raw/trusted/control 坐标和 confidence 构造 `LocalizationEvidence`。
core/navigation_tasks/__init__.py - 统一导航任务控制器包入口。
core/navigation_tasks/update_context.py - `NavigationTaskController` 的 grouped update context/snapshot 数据结构。
core/navigation_tasks/update_pipeline.py - `NavigationTaskController.update_context()` 的统一调度流程 helper。
core/navigation_tasks/controller_utils.py - 导航任务控制器共享坐标格式化和 forced relocalization 判定 helper。
core/navigation_tasks/static_task_runner.py - required/exit 静态任务 runner。
core/navigation_tasks/event_task_runner.py - event 任务 runner，衔接 event approach、EventCoordinator 和 NavigationIntent。
core/navigation_tasks/intent_factory.py - 将 MovementStep/EventAction 转换为 NavigationIntent 的 helper。
core/navigation_tasks/models.py - required/exit/event 统一任务、移动步骤和动作意图数据模型。
core/navigation_tasks/route_context.py - 用户辅助锚点路线上下文，保留 `RouteContext` API；折线投影和累计进度委托 `routing/route_progress`。
core/navigation_tasks/controller_runtime/__init__.py - NavigationTaskController runtime helper package 入口，聚合生命周期、定位、required progress 和重定位 intent helper。
core/navigation_tasks/controller_runtime/lifecycle.py - `NavigationTaskController` 路线加载、runtime reset、start/stop、route validity 和 intent click 记录 helper。
core/navigation_tasks/controller_runtime/localization.py - `observe_localization()` 的 raw/trusted/control position 更新、jump reject 和 route progress 单调推进 helper。
core/navigation_tasks/controller_runtime/progress.py - required point 下一目标查找、到达判定、完成记录和 movement reset helper。
core/navigation_tasks/controller_runtime/relocalization.py - 坐标诊断恢复请求消费、WAIT intent 构造和 movement reset helper。
core/navigation_tasks/movement_executor.py - 普通路线和事件目标共用移动执行器 facade，保留 `MovementExecutor` 和旧私有方法入口。
core/navigation_tasks/movement/__init__.py - movement 子模块入口，聚合路径维护、规划、恢复和工具函数。
core/navigation_tasks/movement/pipeline.py - `MovementExecutor.step()` 的路径复用、lookahead 子目标、点击节流和卡住恢复编排 helper。
core/navigation_tasks/movement/path_maintenance.py - movement 路径是否重规划、路径状态写入和规划日志 helper。
core/navigation_tasks/movement/path_planner.py - movement A*、guide anchor、fallback probe 路径规划 helper。
core/navigation_tasks/movement/recovery.py - movement 本地探测、卡住判定和恢复探测点计算 helper。
core/navigation_tasks/movement/utils.py - movement 坐标 float/int 标准化 helper。
core/navigation_tasks/task_builder.py - 把 route.json 静态目标和 EventMemory 动态事件任务合并成 NavigationTask 列表。
core/navigation_tasks/scheduler.py - 在 required、exit、event 中选择当前应处理任务。
core/navigation_tasks/controller.py - 统一导航任务控制器，输出 MOVE_MAP/CLICK_SCREEN/PRESS_KEY/ARRIVED/FAILED 意图。
core/navigation_tasks/coordinate/__init__.py - coordinate diagnostics 子模块入口，聚合 `CoordinateDiagnostics`、请求 DTO、日志、定位/导航诊断和重定位生命周期。
core/navigation_tasks/coordinate/diagnostics.py - `CoordinateDiagnostics` 真实 stateful facade，保留旧 public/private 方法并委托 coordinate helper。
core/navigation_tasks/coordinate/models.py - 坐标重定位请求 DTO。
core/navigation_tasks/coordinate/formatting.py - 坐标诊断的 registration 字段提取兼容入口、坐标标准化、距离和日志字段格式化 helper；registration/point 标准化委托 localization evidence，字段/值格式化委托 shared diagnostics。
core/navigation_tasks/coordinate/log.py - `logs/coordinate_diagnostics.log` 文件日志 writer。
core/navigation_tasks/coordinate/localization.py - 定位帧诊断、F2F 来源跟踪和 visual mismatch 证据记录 helper；内部消费 `LocalizationEvidence`，旧 `record_localization_diagnostics()` 签名保留。
core/navigation_tasks/coordinate/navigation.py - 任务目标、路线偏差、到达不一致和近目标停滞诊断 helper。
core/navigation_tasks/coordinate/relocalization.py - 坐标强制重定位请求生成、消费、接受和拒绝生命周期 helper。
core/navigation_tasks/event_approach/__init__.py - 事件靠近/停稳 gate facade package，保留 `EventApproachController` 和旧私有 helper 入口。
core/navigation_tasks/event_approach/models.py - 事件靠近 gate 的配置和结果 DTO。
core/navigation_tasks/event_approach/geometry.py - 事件真实视野判定、路径停靠点计算和坐标标准化 helper。
core/navigation_tasks/event_approach/motion.py - 事件靠近阶段 movement step 到 NavigationIntent 的转换 helper。
core/navigation_tasks/event_approach/settle.py - 事件触发前停稳计时、稳定帧判断和 settling intent helper。
core/navigation_tasks/event_approach/pipeline.py - `EventApproachController.update()` 的 far/approach/settling/ready 主流程 helper。
core/navigation_tasks/debug.py - 将导航任务日志写入事件运行日志。
architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md - core facade 逐步抽取方法论，说明旧入口保留、分类 helper、pipeline helper 和每轮验证流程。
core/input/controller.py - `MotionController` 正式类入口，拥有输入控制运行态并委托 motion_controller helper 包。
core/events/models.py - 事件系统通用数据结构和动作类型。
core/events/config.py - 事件配置兼容 facade，re-export 配置模型、IO 和 TUI 事件选项输出。
core/events/config_model.py - `EventSystemConfig`、默认事件配置、deep merge 和 legacy detector mode 兼容。
core/events/config_io.py - 地图级 `event_config.json` 路径、加载和保存。
core/events/registry.py - 完整事件包注册表，TUI/Coordinator 只通过它枚举事件。
core/events/hooks/__init__.py - 事件生命周期 hook package 入口，导出 hook 常量、上下文 DTO 和 registry。
core/events/hooks/models.py - `event_visible_target`、`event_completed` 常量、中文标签和 `EventHookContext` payload。
core/events/hooks/registry.py - 同步 no-op-by-default hook registry，支持注册、注销、清空和异常隔离派发。
core/events/hooks/instances/__init__.py - 具体 hook 实例包入口。
core/events/hooks/instances/key_press.py - 可配置按键 hook 实例，接收输入回调并按一次自定义按键。
core/events/coordinator/__init__.py - EventCoordinator 旧路径 package 入口，导出 `EventCoordinator`。
core/events/coordinator/runtime.py - `EventCoordinator` 真实 stateful facade，持有 registry/config/memory/monitor/stabilizer/scheduler/runner。
core/events/coordinator/observation.py - `EventCoordinator.observe()` 的 detect、position stabilize、memory merge 和 display task selection 流程 helper。
core/events/coordinator/task_run.py - `EventCoordinator.run_task()` 的 task 查找、runner 委托和 action 记录 helper。
core/events/coordinator/reset.py - `EventCoordinator.reset_event_type()` 的 handler/memory/cluster/cache 清理 helper。
core/events/coordinator/presentation.py - `EventCoordinator.overlays()` 和 `status_summary()` 的 overlay/status DTO helper。
core/events/coordinator/filters.py - coordinator event enabled 过滤、active/display task 过滤和日志节流 helper。
core/events/memory/__init__.py - 事件实例生命周期 facade package，保留 `EventMemory` public API 和旧私有 helper wrapper。
core/events/memory/merge.py - stable observations 合并为 EventTask、确认帧和创建/seen 日志 helper。
core/events/memory/lookup.py - EventMemory 任务查找、dedupe、出口任务匹配和完成冷却判定 helper。
core/events/memory/completion.py - EventMemory 完成、传送会话、相关任务完成、附近任务抑制和失败重试/忽略 helper。
core/events/memory/utils.py - EventMemory 距离、坐标标准化和日志节流 helper。
core/events/monitor.py - 调用启用事件的 detector，并缓存 detector 避免每帧重载模板。
core/events/scheduler.py - 在 pending/running 事件中选择当前处理任务。
core/events/runner.py - 启动事件 handler 并根据 COMPLETE/FAIL 更新 memory。
core/events/position_stabilizer/__init__.py - 事件位置稳定 package 入口，保留 `EventPositionStabilizer`、`_PositionCluster`、`_PositionSample` 旧导出。
core/events/position_stabilizer/runtime.py - 事件位置稳定 facade，保留 `update()`、`clear_event_type()` 和旧私有 wrapper。
core/events/position_stabilizer/models.py - 事件位置稳定采样和聚类 DTO，并计算加权中心、方差和置信度。
core/events/position_stabilizer/projection.py - 把局部小地图事件候选按帧配准 origin/draw_scale 投影到全局地图坐标。
core/events/position_stabilizer/clusters.py - 事件候选跨帧聚类、同帧隔离、样本裁剪和过期 cluster 清理 helper。
core/events/position_stabilizer/observations.py - 将满足样本数、方差和发射间隔 gate 的 cluster 转成稳定 `EventObservation`。
core/events/debug/__init__.py - 事件诊断日志旧路径 package 入口，导出 `event_log()`、`start_event_log_session()`、`describe_action()` 和 `describe_task()`。
core/events/debug/writer.py - 事件日志 session、`logs/event_runtime.log`、per-run/per-topic 文件写入和 `[Event ... pid=...]` 行构造。
core/events/debug/topics.py - 根据 event/task/message 推断 portal/navigation/localization topic 并清洗 topic 文件名。
core/events/debug/descriptions.py - EventAction/EventTask 的紧凑运行日志描述格式化。
core/events/debug/formatting.py - 事件日志字段和值格式化兼容 helper，委托 shared diagnostics 并保留旧私有函数名。
core/events/capture_provider.py - 为事件 handler 提供小地图/主画面截图来源。
core/events/window_finder.py - Windows 游戏窗口枚举、DPI awareness 和窗口矩形获取。
core/events/detectors/template_matcher.py - 多模板、多尺度图标匹配通用工具。
core/events/types/portal/definition.py - `portal` 完整事件包对外定义。
core/events/types/portal/minimap_detector.py - 传送门小地图图标 detector facade，持有 `PortalMinimapDetector`、模板缓存、feature signature 和日志节流状态。
core/events/types/portal/minimap_detection/__init__.py - portal minimap detector helper package 入口，聚合 mode、诊断和 hit 转换 helper。
core/events/types/portal/minimap_detection/modes.py - portal minimap detector mode 选择、feature template 刷新、template/feature/shape-color 命中调用和 shape-color 参数构造。
core/events/types/portal/minimap_detection/diagnostics.py - portal minimap detector skipped/no-hit/rejected/best-hit 运行日志 helper，集中维护日志节流写法。
core/events/types/portal/minimap_detection/conversion.py - portal minimap hit 颜色过滤、EventDetection 构造和 metadata 字段填充 helper。
core/events/types/portal/minimap_feature_matcher/__init__.py - 传送门小地图蓝色本体特征匹配器 package 入口，保留旧 public/private helper 导出。
core/events/types/portal/minimap_feature_matcher/models.py - `PortalFeatureTemplate`、`PortalFeatureHit` DTO 和 hit center 计算。
core/events/types/portal/minimap_feature_matcher/masks.py - HSV 蓝/青色 portal body 二值 mask 提取。
core/events/types/portal/minimap_feature_matcher/templates.py - 从通用 `TemplateSpec` 构建 portal 蓝色本体 feature templates。
core/events/types/portal/minimap_feature_matcher/response.py - 多尺度 mask resize 和响应图局部峰值提取 helper。
core/events/types/portal/minimap_feature_matcher/pipeline.py - portal feature matcher 主流程、候选评分和近邻 hit 合并。
core/events/types/portal/minimap_hit_filter.py - 传送门小地图 hit 的蓝色像素接受过滤 helper。
core/events/types/portal/minimap_shape_color/__init__.py - shape-color matcher 子模块入口，聚合 DTO、mask、模板准备、评分和主流程。
core/events/types/portal/minimap_shape_color/models.py - shape-color matcher 参数、命中、debug mask 和 prepared template DTO。
core/events/types/portal/minimap_shape_color/masks.py - shape-color matcher 的蓝色核心/外环 mask、缩放和 BGR/HSV 转换 helper。
core/events/types/portal/minimap_shape_color/templates.py - shape-color matcher 的模板多尺度准备 helper。
core/events/types/portal/minimap_shape_color/scoring/__init__.py - shape-color scoring package 入口，保留原 scoring 函数导出。
core/events/types/portal/minimap_shape_color/scoring/response.py - shape-color matcher 的 mask/color 响应图组合和响应峰值提取 helper。
core/events/types/portal/minimap_shape_color/scoring/color.py - masked HSV 颜色相似度和 color response map helper。
core/events/types/portal/minimap_shape_color/scoring/overlap.py - blue/outer/shape/edge mask 的 F1-like overlap 分数 helper。
core/events/types/portal/minimap_shape_color/scoring/candidate.py - shape-color 候选窗口评分、signature boost 和 reject reason 判定 helper。
core/events/types/portal/minimap_shape_color/pipeline.py - shape-color matcher 主匹配流程和候选去重 helper。
core/events/types/portal/main_view_confirmer.py - 传送门主画面蓝紫发光实体 confirmer。
core/events/types/portal/environment_signature.py - portal 交互前后小地图环境签名和差异计算 helper。
core/events/types/portal/completion_detector.py - portal teleport 完成判定 helper，覆盖已知出口、位置变化和环境变化。
core/events/types/portal/handler/__init__.py - portal handler package 入口，只导出 `PortalEventHandler`。
core/events/types/portal/handler/runtime.py - `PortalEventHandler` facade/state owner，保留 `start()`、`update()`、`reset()` 和 completion wrapper。
core/events/types/portal/handler/movement.py - portal 到达半径、交互半径和 forced repeat movement action helper。
core/events/types/portal/handler/interaction.py - portal 点强制点击、点击后等待、按 `D` 交互和交互签名采集 helper。
core/events/types/portal/handler/completion.py - portal `wait_result` 阶段、completion/fail/wait action 和 relocalize request helper。
core/events/types/portal/handler/diagnostics.py - portal handler 状态变化和节流日志 helper。
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
architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md - core 专项模块化迁移计划，记录对外接口冻结、compatibility wrapper、目标包结构、逐文件迁移映射和阶段实施顺序。
architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md - core 后续优化判断准则，明确不按固定行数拆分，而按模块深度、依赖方向、复用价值和状态局部性判断。
architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md - core 下一阶段优化方案，按规则规划 route progress、localization evidence、diagnostics formatting 和 EventAction/NavigationIntent seam。
tests/test_advanced_settings_file_io.py - 高级设置 JSON snapshot 显式目录、文件名清洗、payload 和加载校验测试。
tests/test_advanced_settings_presets.py - 高级设置预设数据和 adapter 应用测试。
tests/test_navigation_params_compat.py - 导航旧 `nav_preferences` 字段读写兼容测试。
tests/test_nav_params_screen_estimator.py - 导航参数点击半径估算 helper 边界测试。
tests/test_color_picker_debug_output.py - 颜色选择器预览 debug 输出开关测试。
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
### `gui/app_context.py`
职责：作为 GUI 共享服务组合根，创建并持有截图、识别、建图、追踪、寻路对象以及当前监控区域状态。
关键导出：`AppContext`。
对外依赖：`core.platform.SquareScreenCapture`、`core.vision.HSVRecognizer`、`core.vision.PlayerTracker`、`core.mapping.MapStitcher`、`core.routing.PathFinder`。
注意事项：`AppContext` 不再通过 `core.__init__` 聚合入口导入服务对象，改为通过 `gui/composition/services.py` 使用明确 core 系统包入口。初始化顺序是先创建或接收 `CoreServices`，再初始化 monitor 状态；旧的空 `load_global_config()` / `save_global_config()` 占位方法已删除，后续若引入真实全局配置，应避免和每地图 `config.json`、导航参数保存链路混淆。

### `gui/navigation_params.py`
职责：定义导航配置数据模型，并把地图 `config.json` 转换为运行时 `NavConfig`。
关键导出：`NavConfig`、`RecognizerParams`、`NavPreferences`、`_parse_hsv_list`。
对外依赖：无内部模块依赖。
注意事项：`monitor_size`/`draw_scale` 服务定位一致性；`game_view_map_size` 和点击半径参数服务主画面移动控制，不能反向影响定位。`NavPreferences.k_ratio/y_bias` 只保留旧 `config.json` 读写兼容，不再由导航参数面板暴露，也不参与当前 motion 映射。`RecognizerParams` 严格接收当前代码声明的字段，包含绘图页写入的 `player_clear_radius`；未知字段不做静默过滤，配置和代码不一致时应直接暴露。

### `core/input/controller.py`
职责：把 `NavigationTaskController` 输出的地图全局子目标转换为屏幕物理坐标点击，是输入控制系统的正式状态拥有者。
关键导出：`MotionController`。
对外依赖：`core.input.click_pipeline`、`core.input.motion_controller` helper 包。
注意事项：当前不负责寻路、不负责定位，只处理“地图方向 -> 屏幕点击”和真实输入派发。`movement_scale_factor`、普通点击半径夹紧、近目标精确点击和底部 UI 防误点策略已委托 `core.input.motion_mapping`；`_execute_click()` 的流程编排已委托 `core.input.click_pipeline`；真实点击发送委托 `core.input.click_executor`；窗口/光标诊断委托 `core.input.click_diagnostics`；屏幕高度和可选 clamp 委托 `core.input.screen_bounds`。`MotionController` 作为 state owner 保留旧 public/private 方法和 `last_click_info` 写入语义：参数设置、显式屏幕点击和按键在 `core.input.motion_controller.controls`，地图目标点击和坐标计算在 `core.input.motion_controller.targets`，lazy InputDriver、screen clamp、安全 pydirectinput 调用和窗口信息格式化在 `core.input.motion_controller.backend`。事件系统的显式屏幕点击走 `click_screen_position()`，事件按键走 `press_key()`，避免 handler 直接调用私有输入细节。

### `core/input/click_executor.py`
职责：封装真实鼠标点击发送路径。
关键导出：`send_click`、`fallback_pydirect_click`。
对外依赖：`pydirectinput`。
注意事项：`send_click()` 先按 `input_backend` 选择 Win32 driver click，成功时返回 `moved_by_driver=True`；否则走 `pydirectinput.click(x, y)`，并按 `confirm_after_click` 可选追加一次 confirm click。该模块只返回执行 metadata，不直接写 `MotionController.last_click_info`。

### `core/input/click_diagnostics.py`
职责：封装点击点窗口、前台窗口、ClipCursor 和 Win32 光标位置诊断。
关键导出：`collect_window_diagnostics`、`focus_window_at`、`win_cursor_pos`、`format_window_info`。
对外依赖：无固定内部模块依赖；只依赖调用方传入的 driver adapter 能力。
注意事项：所有诊断都是 best-effort；driver 不支持某个方法时返回 `None`，异常由 `MotionController._execute_click()` 捕获并打印。该模块不执行点击，不改变 control enabled 状态。

### `core/input/click_pipeline.py`
职责：承接 `MotionController._execute_click()` 的完整点击流程编排。
关键导出：`execute_click`。
对外依赖：`core.input.click_diagnostics`、`core.input.click_executor`。
注意事项：该模块接收 `MotionController` 实例，按旧顺序执行 bottom guard、可选 clamp、窗口诊断、可选 focus、pydirectinput cursor 诊断、真实点击、点击后 cursor 诊断和 fallback。它仍通过 controller 的兼容 wrapper 写 `last_click_info`，所以公开字段结构不变。

### `core/input/screen_bounds.py`
职责：封装屏幕高度解析和点击坐标 clamp 的纯计算。
关键导出：`screen_height_from_driver_or_size`、`clamp_screen_pos`。
对外依赖：无内部业务模块依赖。
注意事项：`screen_height_from_driver_or_size()` 优先使用 Win32 driver 的 `screen_height`，否则使用 `pydirectinput.size()` 结果。`clamp_screen_pos()` 只在调用方开启 `clamp_to_screen` 时被使用；默认导航仍不强制 clamp，避免坐标系误判时把目标改到屏幕边缘。

### `gui/dialogs/nav_params_dialog.py`
职责：导航参数弹窗主类，负责 tab 构建、控件信号、配置写回、保存信号和屏幕信息适配。
关键导出：`NavParametersDialog`。
对外依赖：`gui.navigation_params`、`gui.dialogs.nav_params.config_binding`、`gui.dialogs.nav_params.screen_estimator`。
注意事项：控件到 `NavConfig` 的字段路径、文本解析、dataclass replace 和控件回填已迁入 `config_binding.py`；`NavParametersDialog` 仍保留旧 public class、Qt signal、tab/layout 构造、状态文案、保存按钮和 Qt 屏幕边界读取。`set_config_to_ui()` 仍在 dialog 层使用 `QSignalBlocker` 阻塞程序化写入时的控件信号。

### `gui/dialogs/nav_params/__init__.py`
职责：导航参数弹窗 helper 包入口，集中 re-export 字段规格和配置绑定 helper。
关键导出：`FieldSpec`、`BOUND_FIELD_SPECS`、`TEXT_FIELD_SPECS`、`VALUE_FIELD_SPECS`、`connect_config_bindings`、`parse_config_text_value`、`replace_config_value`、`write_config_to_widgets`。
对外依赖：`gui.dialogs.nav_params.field_specs`、`gui.dialogs.nav_params.config_binding`。
注意事项：只做包级入口，不直接承载 UI 或配置算法。

### `gui/dialogs/nav_params/field_specs.py`
职责：定义导航参数可编辑字段规格，统一描述 dialog 控件属性名、`NavConfig` 字段路径、字段类别、控件写入方式和分组。
关键导出：`FieldSpec`、`TEXT_FIELD_SPECS`、`VALUE_FIELD_SPECS`、`BOUND_FIELD_SPECS`、`resolve_widget`、`config_value`。
对外依赖：`gui.navigation_params`。
注意事项：当前只覆盖会参与 `parameters_changed` 的可编辑绑定字段；`draw_scale`、`monitor_region`、`game_screen_center` 等只读或格式化显示仍留在 `config_binding.py`，避免规格表过早混入 presentation 文案。

### `gui/dialogs/nav_params/config_binding.py`
职责：承载导航参数对话框的字段绑定规则、信号连接、文本解析、不可变配置替换和控件回填。
关键导出：`value_field_bindings`、`text_field_bindings`、`connect_config_bindings`、`replace_config_value`、`parse_config_text_value`、`write_config_to_widgets`。
对外依赖：`gui.navigation_params`、`gui.dialogs.nav_params.field_specs`。
注意事项：可编辑字段的控件解析、路径解析和回填顺序来自 `field_specs.py`；`QSignalBlocker` 不在这里创建，继续由 dialog 控制程序化回填期间的信号阻断语义。只读显示字段的格式化仍在本模块。

### `gui/dialogs/nav_params/screen_estimator.py`
职责：封装从屏幕中心和物理屏幕边界推导最小/最大点击半径的纯策略。
关键导出：`ClickRadiusEstimate`、`estimate_click_radii`。
对外依赖：无内部业务模块依赖；只使用标准库 typing。
注意事项：函数不依赖 Qt，也不读写控件；中心点不在屏幕边界内时返回 `None`，由 dialog 显示失败状态。

### `gui/dialogs/event_manager_dialog.py`
职责：独立事件管理窗口，用于测试、运行时观察事件系统，并通过 Hooks 页编辑 hook 实例。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`、`gui.dialogs.event_manager.hooks.EventHookPanel`。
注意事项：窗口现在使用 `QTabWidget` 分为“事件”和“Hooks”两页。事件选配表只展示完整事件包，例如 `portal`；不会暴露 minimap detector、main-view confirmer、handler 等内部步骤。任务表从 `EventCoordinator.tasks()` 刷新，展示 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。Hooks 页编辑 `event_config.hooks.instances`，当前只支持 key_press 实例：启用、名称、按键、绑定事件类型、是否挂到“事件进入真实视野”和“事件完成之后”。同一个实例可同时绑定多个事件类型，也可同时勾选两个触发点。完整 `refresh()` 会重建事件表、参数控件和 hook 面板；运行中高频更新使用 `refresh_tasks()` 只刷新任务表，避免导航循环反复重建按钮和参数控件。选中事件行后，参数面板根据该事件的 `config_schema()` 自动生成控件，参数变化只更新内存态配置并发出 `config_changed`，点击保存才写入当前地图 `event_config.json`。Hook 面板变化同样发出 `config_changed`，由导航页重新注册 hook handler。

### `gui/dialogs/event_manager/hooks/panel.py`
职责：事件管理窗口的独立 Hooks 页，编辑 hook 实例配置。
关键导出：`EventHookPanel`。
对外依赖：`core.events.hooks`、`core.events.hooks.instances`。
注意事项：该面板只操作 `EventSystemConfig.hooks["instances"]`，不直接注册 handler、不执行输入、不依赖 `NavigationTaskController`。面板从事件管理窗口传入的完整事件列表动态生成事件绑定列，写入 `event_types`。新增按钮创建一个启用的 key_press 实例，默认按键为 `d`，默认绑定第一个可用事件并挂到 `event_visible_target`；用户可同时勾选多个事件类型，也可同时勾选 `event_visible_target` 和 `event_completed`。未绑定事件类型的实例不会触发。删除按钮移除当前选中实例。所有变化只发出 `hooks_changed`，由外层 dialog 转为 `config_changed`。

### `gui/dialogs/advanced_settings_dialog.py`
职责：高级参数弹窗主类，负责 tab 构建、按钮/文件对话框连接、参数文件选择和 recognizer/stitcher 实时应用时机。
关键导出：`AdvancedSettingsDialog`。
对外依赖：`gui.dialogs.advanced_settings.file_io`、`gui.dialogs.advanced_settings.params_adapter`。
注意事项：`load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口保留，内部委托参数映射 helper。`apply_params()` 现在先发出 `apply_params_requested(dict)` command signal；已迁移 owner 可调用 `use_external_apply_handler()` 禁用 dialog 内部 direct runtime mutation。参数 snapshot 的 JSON 格式、文件名清洗、目录创建和读取校验由 `advanced_settings/file_io.py` 维护；本类仍负责打开 `QFileDialog`、更新状态文案，并为未迁移调用方保留 `_apply_params_directly()` fallback。

### `gui/dialogs/advanced_settings/__init__.py`
职责：高级参数弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/advanced_settings/file_io.py`
职责：封装高级参数 JSON snapshot 的保存、加载、展示格式化和默认输出目录。
关键导出：`advanced_settings_output_dir`、`save_params_snapshot`、`load_params_snapshot`、`format_params_for_display`。
对外依赖：无内部业务模块依赖；只使用标准库 `json/pathlib/datetime/re`。
注意事项：默认目录为项目根 `configs/advanced_settings/`，不再写进程当前工作目录。保存文件名使用清洗后的参数名，payload 仍保留用户原始 `name`、ISO `timestamp` 和 `parameters` 字段。加载时要求顶层 JSON 是 object，且 `parameters` 必须是 object；错误向调用方抛出，由 dialog 显示。

### `gui/dialogs/advanced_settings/params_adapter.py`
职责：封装高级参数弹窗控件与参数 dict/预设之间的双向映射。
关键导出：`load_params_to_widgets`、`collect_params_from_widgets`、`reset_widgets_to_default`、`apply_loaded_params_to_widgets`、`apply_preset_to_widgets`。
对外依赖：`gui.dialogs.advanced_settings.presets`。
注意事项：该模块不保存参数文件、不读取 JSON、不调用 recognizer/stitcher。`reset_widgets_to_default()` 保持旧 reset 字段集合，不额外写 `blur_strength_spin`；`load_params_to_widgets()` 仍写入 `blur_strength_spin=3`，保持旧加载当前参数行为。预设名称和值来自 `presets.py`，但写控件仍依赖 dialog attribute names。

### `gui/dialogs/advanced_settings/presets.py`
职责：封装高级参数预设的用户可见顺序和控件赋值数据。
关键导出：`DEFAULT_PRESET_NAME`、`PRESET_NAMES`、`PRESET_VALUES`、`preset_names`、`preset_values`。
对外依赖：无内部业务模块依赖；只使用标准库 `MappingProxyType`。
注意事项：默认预设不在 `PRESET_VALUES` 里，因为它仍代表“完整 reset”，由 `params_adapter.apply_preset_to_widgets()` 委托 `reset_widgets_to_default()`。非默认预设只记录旧实现实际写入的控件值，不额外扩展字段。

### `gui/dialogs/color_picker_dialog.py`
职责：交互式颜色选择弹窗，负责采样点交互、模式切换、HSV 计算流程、预览刷新和结果返回。
关键导出：`ColorPickerDialog`。
对外依赖：`core.vision.HSVRecognizer`、`gui.widgets.clickable_label.ClickableImageLabel`、`gui.dialogs.color_picker.debug_output`、`gui.dialogs.color_picker.hsv_ranges`、`gui.dialogs.color_picker.image_renderer`、`gui.dialogs.color_picker.preview`。
注意事项：`calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口保留，内部委托 helper。`update_preview()` 现在调用 `color_picker/preview.py::build_wall_preview()` 获取 mask 和统计结果，本类只负责把 mask 显示到 preview label，并在 `MINIMAP_COLOR_PICKER_DEBUG=1` 时把 preview 结果传给 `debug_output.py` 写入 `debug/color_picker/`。当前 preview 只复刻旧 wall mask 行为，不新增 player mask 预览。

### `gui/dialogs/color_picker/__init__.py`
职责：颜色选择弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/color_picker/debug_output.py`
职责：封装颜色选择预览 debug 图片和文本日志的 opt-in 开关、输出目录与文件写入。
关键导出：`DEBUG_ENV_VAR`、`is_wall_preview_debug_enabled`、`write_wall_preview_debug`。
对外依赖：无内部业务模块依赖；只使用 OpenCV 和标准库 pathlib/os。
注意事项：默认不会生成 `preview_result_*.png`、`preview_before_morph_*.png`、`preview_log_*.txt`；只有 `MINIMAP_COLOR_PICKER_DEBUG` 为 `1/true/yes/on` 时，`ColorPickerDialog.update_preview()` 才调用写入逻辑，输出目录为 `debug/color_picker/`。

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

### `gui/dialogs/color_picker/preview.py`
职责：构造颜色选择弹窗右侧 wall HSV 二值预览 mask，并返回形态学处理前后统计。
关键导出：`WallPreviewResult`、`build_wall_preview`。
对外依赖：无内部业务模块依赖；使用 OpenCV/Numpy。
注意事项：只实现旧 `update_preview()` 已有的 wall mask 路径：BGR->HSV、`cv2.inRange()`、3x3 close、白色像素统计和 debug 所需字段。不负责 QLabel 显示、不判断 debug env、不写文件。

### `gui/modes/navigation/widget.py`
职责：导航模式 QWidget 组合根和临时 facade，负责持有跨模块运行态、调用 UI builder/signal binder，并委托 composition module 创建 lifecycle/controller。
关键导出：`NavigationModeWidget`。
对外依赖：`MotionController`、`NavigationTaskController`、`RouteManager`、`navigation.composition`、`navigation.event_adapter`、`navigation.presentation`、`navigation.input`、`navigation.map`、`navigation.route`、`navigation.events`、`navigation.ui`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`required_points` 是必须按顺序完成的阶段门；`guide_points` 是有序软锚点/辅助走廊，只在 `MovementExecutor` 规划 required、exit 或 event 目标时塑形路线，不作为独立导航目标。route JSON 编辑和 click mode 状态已委托 `navigation/route/editor.py`；route 按钮 checked/enabled、状态栏操作提示和保存/撤销/清空命令结果已委托 `navigation/route/panel_controller.py`；保存/撤销/清空/加载 route 后的 `route_data`、`NavigationTaskController.load_route()`、overlay 刷新、状态栏文案和保存失败 warning 已委托 `navigation/route/lifecycle.py` 的 `NavigationRouteLifecycle`。顶部工具栏、`QGraphicsScene/QGraphicsView`、状态栏和 `RoutePanelController` 构建已委托 `navigation/ui/layout.py`，按钮、参数弹窗和事件弹窗信号绑定已委托 `navigation/ui/signals.py`；小地图样本按钮同样在这里创建和接线，地图加载成功后才启用。地图 item 创建/更新、定位显示更新、地图列表 combo 填充、地图加载成功 UI 写入、地图加载/overlay 配置反馈、导航配置保存结果展示、route/移动目标命令反馈、hint/calibration 反馈、事件管理结果展示、自动导航/导航启动命令反馈、路线/事件 overlay、debug 幕布窗口写入、owned dialog 显示外壳和状态栏文案构造/写入已委托 `navigation/presentation`。地图目录解析、配置读取、`NavigationCore` 创建和初始物理中心计算已通过 `navigation/map/session.py` 包装；地图加载后半段固定顺序已委托 `navigation/map/load_lifecycle.py` 的 `NavigationMapLoadLifecycle`。导航配置生命周期已委托 `navigation/config/lifecycle.py` 的 `NavigationConfigLifecycle`。屏幕中心校准已拆成两层：`navigation/calibration/screen_center.py` 只负责 selector 生命周期、DPR 读取和 logical->physical 坐标转换，`navigation/calibration/lifecycle.py` 负责配置写回、参数弹窗刷新、overlay、保存、完成提示和 selector 关闭。导航运行命令生命周期已委托 `navigation/runtime/command_lifecycle.py` 的 `NavigationRuntimeCommandLifecycle`，整帧循环已委托 `navigation/runtime/frame_loop.py` 的 `NavigationRuntimeFrameLoop`；frame loop 每帧缓存最近小地图 frame/capture_rect/player_pos，`navigation/runtime/minimap_sample_capture.py` 负责把缓存或即时截图保存为 `debug/minimap_samples/<map_name>/` 下的 PNG+JSON 样本。导航事件生命周期已委托 `navigation/events/lifecycle.py` 的 `NavigationEventLifecycle`；事件弹窗创建/接线/刷新已委托 `navigation/events/dialog_lifecycle.py`；地图加载时的事件系统 runtime bootstrap 已委托 `navigation/events/bootstrap.py`，该模块返回 `event_config`、`event_coordinator`、`event_capture_provider` 后由 widget 写回字段。事件观测 helper 返回 `event_tick` 给后续 task update；当前 hook 机制位于 core 侧，外部可通过 `NavigationTaskController.event_hooks.register(...)` 注册处理器。事件被选中后才调用 `EventCoordinator.run_task()` 推进 handler；事件 `MOVE_TO` 与普通目标共用同一个 `MovementExecutor`，事件 `PRESS_KEY/CLICK_SCREEN` 统一委托 `navigation/input/intent_executor.py` 消费。路线 overlay 与事件 overlay 的 QGraphicsItem 创建/清理由 `gui/modes/navigation/presentation/route_overlay.py` 和 `presentation/event_overlay.py` 承担，旧根路径 overlay 模块已删除。本文件不再打印每帧“当前位置/位置来源”调试块；旧长 docstring 已压缩，避免 wrapper 注释继续描述已下沉的内联实现。导航/事件操作过程走 `logs/event_runtime.log`。初始化顺序已调整为先创建 route/config/runtime 状态对象，再调用 UI builder，避免 `RoutePanelController` 依赖未初始化的 `RouteEditor`。
显示链补充：`navigation/display/lifecycle.py::NavigationMapDisplayLifecycle` 现在承接 scene item 引用写回、route/event overlay 清理和渲染、绿色监控框、橙色视野框、上次退出位置 marker；`NavigationModeWidget._render_map()`、`_render_route_overlay()`、`_render_event_overlay()`、`_update_monitor_rect()`、`_update_game_view_rect()`、`_show_last_exit_position()` 等旧方法只保留 wrapper。
组合链补充：`navigation/composition/lifecycles.py` 现在承接 display/config/route/events/map/runtime/calibration lifecycle 的 targets wiring。`NavigationModeWidget.__init__()` 只保留基础字段初始化、`init_ui()`、pre-signal lifecycle 初始化、signal wiring 和 runtime lifecycle 初始化四段顺序。

### `gui/modes/navigation/composition/__init__.py`
职责：导航局部 composition 包入口。
关键导出：`initialize_navigation_pre_signal_lifecycles`、`initialize_navigation_runtime_lifecycles`。
对外依赖：`navigation.composition.lifecycles`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/composition/lifecycles.py`
职责：集中导航页 lifecycle/controller 的 wiring 顺序。
关键导出：`initialize_navigation_pre_signal_lifecycles(owner)`、`initialize_navigation_runtime_lifecycles(owner)`。
对外依赖：`PySide6.QtCore.QTimer`、`navigation.calibration`、`navigation.config`、`navigation.display`、`navigation.events`、`navigation.map`、`navigation.route`、`navigation.runtime`。
注意事项：这是 navigation 局部 composition module，不实现算法、不处理用户命令。`initialize_navigation_pre_signal_lifecycles()` 必须在 `_connect_signals()` 前执行，创建 display/event-dialog/route/config/calibration/map-load lifecycle；`initialize_navigation_runtime_lifecycles()` 必须在 `_connect_signals()` 后执行，创建 `QTimer`、延迟事件弹窗、manual portal controller、runtime command/event/map-click lifecycle 和 `NavigationRuntimeFrameLoop`。这个模块暂时持有 owner 访问以避免超大构造参数，后续若要增强复用性，应先收窄 owner 依赖。

### `gui/modes/navigation/ui/__init__.py`
职责：导航 UI shell 包导出。
关键导出：`build_navigation_ui`、`connect_navigation_signals`。
对外依赖：`navigation.ui.layout`、`navigation.ui.signals`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/ui/layout.py`
职责：构建导航页的 Qt 控件树和初始图形项字段。
关键导出：`build_navigation_ui(owner)`。
对外依赖：`navigation.route.RoutePanelController`。
注意事项：该 helper 只创建 UI 对象并挂回 owner 字段；会调用 `owner.refresh_map_list()` 填充地图下拉框，并创建 `owner.route_panel`。`save_minimap_sample_button` 初始禁用，必须等地图加载成功后由 widget 启用。它不连接信号、不加载地图、不启动导航。

### `gui/modes/navigation/ui/signals.py`
职责：集中绑定导航页按钮、参数弹窗和事件弹窗信号。
关键导出：`connect_navigation_signals(owner)`。
对外依赖：无内部业务模块依赖。
注意事项：绑定目标仍是 `NavigationModeWidget` 的旧 slot/wrapper，保证迁移期外部行为不变；小地图样本按钮连接到 `owner.save_minimap_sample()`；事件弹窗信号通过 `owner._connect_event_dialog_signals()` 复用已有重连逻辑。

### `gui/modes/navigation/display/__init__.py`
职责：导航地图显示生命周期包导出。
关键导出：`NavigationMapDisplayLifecycle`。
对外依赖：`navigation.display.lifecycle`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/display/lifecycle.py`
职责：集中管理导航地图 scene item 和 overlay 的 owner 字段写回。
关键导出：`NavigationMapDisplayLifecycle`。
对外依赖：`navigation.presentation`。
注意事项：这是 GUI display lifecycle，不是纯 presentation helper；它串联 `presentation` 里的小绘制函数，并维护 `NavigationModeWidget` 上的 `route_overlay_items`、`event_overlay_items`、`route_path_item`、`map_item`、`player_item`、`monitor_rect_item`、`game_view_rect_item` 等引用。它不加载地图、不定位、不启动导航。
### `gui/modes/navigation/input/__init__.py`
职责：导航输入 adapter 包导出。
关键导出：`GameInputWindowMode`、`NavigationIntentExecutionResult`、`execute_navigation_intent`。
对外依赖：`navigation.input.window_mode`、`navigation.input.intent_executor`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/input/window_mode.py`
职责：自动导航或事件输入期间，管理主窗口取消置顶、降低到游戏窗口后方、停止后恢复置顶状态。
关键导出：`GameInputWindowMode`。
对外依赖：无内部业务模块依赖；使用 PySide6 `Qt.WindowStaysOnTopHint`。
注意事项：这是 GUI 专属 input seam；不发送鼠标键盘输入，只维护窗口状态。`set_enabled(True)` 第一次记录原 topmost 状态并 lower 主窗口；`set_enabled(False)` 只在此前启用过时恢复，避免停止命令反复改窗口 flag。
### `gui/modes/navigation/input/intent_executor.py`
职责：把统一导航任务层输出的 `NavigationIntent` 转换为 `MotionController` 调用。
关键导出：`NavigationIntentExecutionResult`、`execute_navigation_intent`。
对外依赖：`core.navigation_tasks.models.NavigationIntentType`。
注意事项：`MOVE_MAP` 会启用游戏输入模式和 motion control；带 `force_click_target` 时调用 `click_map_target_once()`，否则调用 `move_to_map_target()`；成功点击后调用 `NavigationTaskController.record_intent_click()` 并返回状态栏后缀。`CLICK_SCREEN` 和 `PRESS_KEY` 只读取 metadata 中的 `screen_pos` 或 `key`，缺字段时静默跳过。
### `gui/modes/navigation/hooks/__init__.py`
职责：导航 hook runtime 注册包入口。
关键导出：`NavigationHookRuntime`。
对外依赖：`navigation.hooks.registration`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/hooks/registration.py`
职责：把 `EventSystemConfig.hooks.instances` 中的 hook 实例注册到 `NavigationTaskController.event_hooks`。
关键导出：`NavigationHookRuntime`。
对外依赖：`core.events.hooks.instances`。
注意事项：该模块是 GUI 组合根与 core hook registry 的 adapter。`apply_event_config()` 会先注销上一轮由本 runtime 注册的 handler，再按当前配置注册 enabled key_press 实例；实例必须同时有 `event_types` 和 `triggers` 才会注册，避免 hook 默认对所有事件生效。一个实例的 `triggers` 可包含 `event_visible_target` 和 `event_completed`，因此同一个按键 hook 可同时挂两个触发点。按键执行通过注入的 `enable_game_input_mode()` 和 `MotionController.press_key()` 完成，不让 core hook 实例直接依赖 GUI 或平台输入。
### `NavigationHookRuntime.apply_event_config(self, event_config) -> int`
行为：根据当前事件配置重建 hook handler 注册。
算法：1. 调用 `clear()` 注销本 runtime 之前注册的所有 handler。2. 读取 `event_config.hooks["instances"]`，忽略非 dict 或未知类型。3. 对 `type="key_press"` 的实例调用 `key_press_settings_from_dict()` 规范化配置。4. 跳过未启用、空 key、无 `event_types` 或无 triggers 的实例。5. 创建 `KeyPressHookInstance(settings, self._press_key_once)`，并对实例的每个 trigger 调用 `navigation_task_controller.event_hooks.register()`。6. 返回本次注册的 trigger 数量。
副作用：修改 `NavigationTaskController.event_hooks` 的 handler 列表；后续 hook 触发时可能通过 `MotionController.press_key()` 发送一次按键。
失败行为：未知实例类型静默忽略；handler 运行时异常由 core `EventHookRegistry.emit()` 捕获。
调用关系：called by `NavigationModeWidget._initialize_event_system()` after map event config load, and `NavigationModeWidget._on_event_config_changed()` after GUI edits hook/event config。
### `gui/modes/navigation/config/__init__.py`
职责：导航配置生命周期包入口。
关键导出：`NavigationConfigLifecycle`、`NavigationConfigLifecycleTargets`。
对外依赖：`navigation.config.lifecycle`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/config/lifecycle.py`
职责：集中导航配置生命周期：参数变化、runtime 应用、task controller 同步、当前地图保存、默认配置保存和 UI 反馈顺序。
关键导出：`NavigationConfigLifecycleTargets`、`NavigationConfigLifecycle`。
对外依赖：`navigation.map.config_applier`、`navigation.map.config_store`、`navigation.presentation.config_save_state`。
注意事项：这是比单个 helper 更深的 GUI config module。它通过 targets DTO 接收 parent、source file、状态 label、runtime 对象和 widget 回调，不直接持有 `NavigationModeWidget` 类型；保存/应用/刷新顺序集中在 `NavigationConfigLifecycle`，旧 widget 方法保留 wrapper。
### `gui/modes/navigation/map/__init__.py`
职责：导航地图/config adapter 包导出。
关键导出：`MISSING_MAP_DATA_LABEL`、`NavigationMapClickLifecycle`、`NavigationMapClickLifecycleTargets`、`NavigationMapLoadLifecycle`、`NavigationMapLoadLifecycleTargets`、`NavigationMapLoadSession`、`NavigationMapSettings`、`apply_motion_controller_config`、`apply_navigation_config_to_core`、`build_capture_geometry`、`configure_navigation_task_controller`、`create_navigation_core`、`handle_navigation_map_event_filter`、`initial_capture_center_for_config`、`list_map_names`、`load_navigation_map_settings`、`load_nav_config`、`physical_center_from_logical`、`prepare_navigation_map_load_session`、`resolve_map_folder`、`save_default_nav_config`、`save_nav_config`。
对外依赖：`navigation.map.config_applier`、`navigation.map.config_store`、`navigation.map.capture_geometry`、`navigation.map.session`、`navigation.map.load_lifecycle`、`navigation.map.click_lifecycle`、`navigation.map.event_filter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/map/click_lifecycle.py`
职责：集中导航地图点击生命周期：hint 放置、route 编辑、手动移动目标设置、坐标转换、marker/overlay/status 更新。
关键导出：`NavigationMapClickLifecycleTargets`、`NavigationMapClickLifecycle`。
对外依赖：`navigation.presentation.calibration_feedback`、`navigation.presentation.route_command_state`、`navigation.presentation.map_presenter`。
注意事项：这是 map package 内的交互深模块。它通过 targets DTO 接收 view/scene/button、route editor、motion controller 和 widget 回调，不直接持有 `NavigationModeWidget`；分支顺序保持旧行为：hint mode 优先，其次 route editor click mode，最后才是手动移动目标。手动移动目标必须已经定位，失败只弹 warning，不调用 `MotionController`。
### `gui/modes/navigation/map/session.py`
职责：封装导航地图加载前置 session 操作：解析 map folder、读取导航配置、创建 `NavigationCore` 并计算初始物理中心。
关键导出：`NavigationMapSettings`、`NavigationMapLoadSession`、`load_navigation_map_settings`、`create_navigation_core`、`prepare_navigation_map_load_session`。
对外依赖：`core.localization.NavigationCore`、`navigation.map.config_store.load_nav_config`、`navigation.map.config_store.resolve_map_folder`、`navigation.map.capture_geometry.initial_capture_center_for_config`。
注意事项：该模块刻意不应用配置、不弹 QMessageBox、不刷新参数弹窗、不初始化事件系统、不渲染地图；这些副作用由 `navigation.map.load_lifecycle.NavigationMapLoadLifecycle` 按旧顺序执行。`NavigationMapLoadSession` 只承载 map name/folder、`nav_config`、`config_exists`、`nav_core`、`capture_center_physical` 和参数弹窗需要的 `physical_center`。
### `gui/modes/navigation/map/load_lifecycle.py`
职责：集中导航地图加载生命周期的 GUI 编排：准备 map session、写入 widget runtime 状态、应用配置、回填参数弹窗、加载路线、初始化事件系统、渲染地图/退出点/路线覆盖层并启用加载完成 UI。
关键导出：`NavigationMapLoadLifecycleTargets`、`NavigationMapLoadLifecycle`。
对外依赖：`navigation.map.session.prepare_navigation_map_load_session`、`navigation.presentation.map_load_state`。
注意事项：这是 map package 内的深模块，不是 presentation helper。它通过 targets DTO 接收 widget 回调和 UI 控件引用，隐藏加载后半段的顺序敏感副作用；`NavigationModeWidget.load_map()` 保留旧入口但不再内联缺配置提示、参数回填、route/event/render/UI 启用顺序。该模块不直接 import `NavigationModeWidget` 类型，也不改变 `NavConfig` 应用规则。
### `gui/modes/navigation/map/config_applier.py`
职责：集中执行 `NavConfig` 到导航运行对象的写入规则。
关键导出：`apply_navigation_config_to_core`、`apply_motion_controller_config`、`configure_navigation_task_controller`。
对外依赖：`core.events.debug.event_log`。
注意事项：`map_data.npz` 中的 `map_draw_scale` 仍是定位缩放权威；当 `nav_config.draw_scale` 不一致时记录 `navigation draw_scale config mismatch` 并修正内存配置。该模块负责 recognizer 参数、导航墙层重建、PathFinder start/snap 半径、MotionController 屏幕中心/点击半径、NavigationTaskController movement/event approach/coordinate diagnostics 参数写入，但不弹窗、不改按钮。
### `gui/modes/navigation/map/event_filter.py`
职责：封装导航地图 scene 的 Qt 鼠标事件解释。
关键导出：`handle_navigation_map_event_filter`。
对外依赖：`PySide6.QtCore.QEvent`、`PySide6.QtCore.Qt`。
注意事项：只识别 watched scene 上的左键 `GraphicsSceneMousePress`，把 `event.scenePos()` 交给注入的 `handle_map_click` 回调并返回 `True`；其他事件返回 `False`，由 widget 的 `super().eventFilter()` 继续处理。该 helper 不知道 hint/route/manual move 语义，真实点击优先级仍在 `NavigationMapClickLifecycle`。
### `gui/modes/navigation/route/__init__.py`
职责：导航 route editing adapter 包导出。
关键导出：`MapClickMode`、`RouteEditResult`、`RouteEditor`、`NavigationRouteLifecycle`、`NavigationRouteLifecycleTargets`、`RouteCommandResult`、`RoutePanelController`。
对外依赖：`navigation.route.editor`、`navigation.route.lifecycle`、`navigation.route.panel_controller`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/route/editor.py`
职责：集中导航 route click mode 和 `route.json` 编辑命令，使 UI 主类不直接改 route 数据结构。
关键导出：`MapClickMode`、`RouteEditResult`、`RouteEditor`。
对外依赖：无内部业务模块依赖；运行时接收 `RouteManager` 实例。
注意事项：`RouteEditor` 不触碰 Qt 按钮、scene、status label 或 `NavigationTaskController`；它只更新 `RouteManager` 缓存/route.json 数据并返回 `RouteEditResult`。设置出口后会把 click mode 复位为 `NONE`；添加必经点/途经点会保持当前模式，延续连续添加行为。
### `gui/modes/navigation/route/lifecycle.py`
职责：封装导航页 route 命令结果同步生命周期。
关键导出：`NavigationRouteLifecycleTargets`、`NavigationRouteLifecycle`。
对外依赖：`navigation.presentation.show_route_command_status`、`navigation.presentation.warn_route_save_failed`；通过 targets 注入 `RouteEditor`、`RoutePanelController` 和 `NavigationTaskController`。
注意事项：`RoutePanelController` 仍负责按钮/click mode 和 route editor 命令结果；本 lifecycle 只负责把成功结果同步到 `NavigationModeWidget.route_data`、`NavigationTaskController.load_route()`、route overlay 和状态栏。保存失败保持旧 warning；未加载地图时不会弹窗。
### `gui/modes/navigation/route/panel_controller.py`
职责：封装导航 route 相关按钮状态、操作提示文案和 route editor 命令结果。
关键导出：`RouteCommandResult`、`RoutePanelController`。
对外依赖：`navigation.route.editor.MapClickMode`、`RouteEditor`。
注意事项：该 controller 接收具体按钮和 status label 引用，但不弹 QMessageBox、不绘制 overlay、不知道 `NavigationTaskController`。保存失败时只返回 `saved=False`，由 `NavigationRouteLifecycle.save_route()` 继续弹原警告；保存/撤销/清空成功后返回 route_data 和旧状态栏文案，lifecycle 负责同步 controller route 和重绘。
### `gui/modes/navigation/events/__init__.py`
职责：导航事件 UI adapter 包导出。
关键导出：`ManualEventTestController`、`NavigationEventSystemRuntime`、`initialize_navigation_event_system`、`NavigationEventDialogLifecycle`、`NavigationEventDialogLifecycleTargets`、`NavigationEventLifecycle`、`NavigationEventLifecycleTargets`、`summarize_event_config`。
对外依赖：`navigation.events.bootstrap`、`navigation.events.dialog_lifecycle`、`navigation.events.manual_test_controller`、`navigation.events.lifecycle`、`navigation.events.panel_adapter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/events/bootstrap.py`
职责：封装导航地图加载后的事件系统 runtime 初始化。
关键导出：`NavigationEventSystemRuntime`、`initialize_navigation_event_system`。
对外依赖：`core.events.capture_provider.GameWindowCaptureProvider`、`core.events.config.load_event_config`、`core.events.coordinator.EventCoordinator`、`core.events.debug.event_log`、`navigation.events.panel_adapter.summarize_event_config`。
注意事项：这是 map-load 阶段的事件 runtime bootstrap，不触碰路线、timer、输入或 Qt 按钮状态。无 `map_folder_path` 时返回三项空 runtime；有地图时按旧顺序读取 event config、创建 coordinator/capture provider、刷新事件弹窗、写初始化日志，再把三个对象交给 widget 写回。
### `gui/modes/navigation/events/dialog_lifecycle.py`
职责：封装事件管理弹窗创建、信号连接、刷新、显示切换和手动测试按钮同步。
关键导出：`NavigationEventDialogLifecycleTargets`、`NavigationEventDialogLifecycle`。
对外依赖：`navigation.presentation.toggle_owned_dialog`、`navigation.events.panel_adapter.create_event_dialog/connect_event_dialog_signals/refresh_event_dialog`。
注意事项：不保存配置、不重置 portal、不启动手动测试；只持有通过 targets 传入的 dialog getter/setter 和回调。首次创建 dialog 后同步 `ManualEventTestController.button`，避免弹窗延迟创建导致按钮状态丢失。
### `gui/modes/navigation/events/manual_test_controller.py`
职责：维护手动事件测试按钮的 active 状态、文案和 checked 状态。
关键导出：`ManualEventTestController`。
对外依赖：无内部业务模块依赖；只依赖传入 button 对象具备 `setText/isChecked/setChecked`。
注意事项：该控制器不决定事件类型、不启动导航、不调用输入执行器；`button=None` 时仍能维护 active 状态，适合 dialog 尚未创建时使用。
### `gui/modes/navigation/events/lifecycle.py`
职责：集中导航事件生命周期：事件配置保存、portal 状态重置、event move runtime reset、portal 手动测试启动/停止、overlay/dialog 刷新和事件日志。
关键导出：`NavigationEventLifecycleTargets`、`NavigationEventLifecycle`。
对外依赖：`core.events.config.save_event_config`、`core.events.debug.event_log`、`core.events.debug.start_event_log_session`、`navigation.presentation.event_management_state`。
注意事项：这是 events 包内的深模块。它通过 targets DTO 接收 widget/runtime 回调和 UI 对象，不直接 import `NavigationModeWidget`；手动 portal 测试仍复用正式事件 pipeline，只把任务控制器切到 manual-event-only 输入源，真实事件选择和 intent 执行仍在导航循环/task controller/input executor 中。停止手动测试时会重置 movement 与 event approach runtime；若自动导航仍启用，不关闭游戏输入窗口模式。
### `gui/modes/navigation/events/panel_adapter.py`
职责：封装事件管理窗口创建、信号重连、上下文刷新和配置摘要。
关键导出：`create_event_dialog`、`connect_event_dialog_signals`、`refresh_event_dialog`、`summarize_event_config`。
对外依赖：`gui.dialogs.event_manager_dialog.EventManagerDialog`、`navigation.event_adapter.event_config_summary`。
注意事项：该模块不保存 event_config、不重置 portal state、不推进 event handler；它只处理 UI wiring。`connect_event_dialog_signals()` 会先尝试 disconnect 再 connect，避免重复连接导致一次按钮点击触发多次 slot。
### `gui/modes/navigation/presentation/__init__.py`
职责：导航 presentation helper 包导出。
关键导出：`apply_map_loaded_ui`、`populate_map_combo`、`warn_map_config_missing`、`show_map_load_failed`、`warn_overlay_map_config_incomplete`、`show_initial_hint_set`、`show_hint_mode_status`、`show_screen_center_calibrated`、`mark_nav_params_dirty`、`warn_nav_config_missing_map`、`show_nav_config_saved`、`show_nav_config_save_failed`、`warn_default_nav_config_missing`、`show_default_nav_config_saved`、`show_default_nav_config_save_failed`、`warn_event_config_missing`、`show_event_config_saved`、`show_event_config_save_failed`、`warn_event_system_missing`、`show_portal_event_state_reset`、`warn_portal_manual_test_missing_screen_center`、`show_portal_manual_test_started`、`show_portal_manual_test_stopped`、`warn_auto_navigation_unavailable`、`warn_auto_navigation_invalid_route`、`show_auto_navigation_started`、`show_auto_navigation_stopped`、`warn_navigation_missing_screen_center`、`warn_navigation_map_config_incomplete`、`show_navigation_started`、`show_navigation_paused`、`show_route_command_status`、`warn_route_save_failed`、`warn_move_target_requires_localization`、`show_move_target_set`、`create_map_scene_items`、`update_player_marker`、`update_monitor_rect_item`、`update_game_view_rect_item`、`create_last_position_marker`、`create_initial_hint_marker`、`set_target_marker`、`hide_item`、`show_owned_dialog`、`toggle_owned_dialog`、`update_debug_overlay`、`clear_event_overlay`、`global_to_scene`、`render_event_overlay`、`clear_route_overlay`、`render_route_overlay`、`screen_overlay_geometry`、`build_navigation_status_text`、`show_navigation_runtime_status`、`append_navigation_status_suffix`、`show_navigation_relocalizing`、`show_navigation_arrived`、`show_navigation_failed`。
对外依赖：`navigation.presentation.calibration_feedback`、`navigation.presentation.config_save_state`、`navigation.presentation.event_management_state`、`navigation.presentation.navigation_command_state`、`navigation.presentation.route_command_state`、`navigation.presentation.map_load_state`、`navigation.presentation.map_presenter`、`navigation.presentation.dialog_host`、`navigation.presentation.debug_overlay`、`navigation.presentation.status_presenter`、`navigation.presentation.event_overlay`、`navigation.presentation.route_overlay`、`navigation.presentation.viewport_overlay`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/presentation/calibration_feedback.py`
职责：封装初始位置提示、hint mode 状态栏和屏幕中心校准完成弹窗。
关键导出：`show_initial_hint_set`、`show_hint_mode_status`、`show_screen_center_calibrated`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不调用 `NavigationCore.set_initial_hint()`、不更新监控/视野框、不写 `NavConfig`、不保存 config、不关闭 selector；只负责旧中文提示。
### `gui/modes/navigation/presentation/config_save_state.py`
职责：封装导航参数保存和默认配置保存后的状态标签与 QMessageBox 文案。
关键导出：`mark_nav_params_dirty`、`warn_nav_config_missing_map`、`show_nav_config_saved`、`show_nav_config_save_failed`、`warn_default_nav_config_missing`、`show_default_nav_config_saved`、`show_default_nav_config_save_failed`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不写 config、不调用 `_apply_config_to_core()`、不刷新 overlay；只展示保存链路结果。当前地图配置保存成功文案、失败文案和默认配置保存文案保持旧中文文本。
### `gui/modes/navigation/presentation/event_management_state.py`
职责：封装事件管理保存、事件系统缺失、传送门状态刷新和手动测试启动/停止的状态标签与 QMessageBox 文案。
关键导出：`warn_event_config_missing`、`show_event_config_saved`、`show_event_config_save_failed`、`warn_event_system_missing`、`show_portal_event_state_reset`、`warn_portal_manual_test_missing_screen_center`、`show_portal_manual_test_started`、`show_portal_manual_test_stopped`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不保存 `event_config`、不调用 `EventCoordinator.reset_event_type()`、不启动/停止 `ManualEventTestController`、不修改 motion/input window；只负责旧中文提示与状态栏文案。
### `gui/modes/navigation/presentation/navigation_command_state.py`
职责：封装自动导航和导航启动/停止命令的状态标签与 QMessageBox 文案。
关键导出：`warn_auto_navigation_unavailable`、`warn_auto_navigation_invalid_route`、`show_auto_navigation_started`、`show_auto_navigation_stopped`、`warn_navigation_missing_screen_center`、`warn_navigation_map_config_incomplete`、`show_navigation_started`、`show_navigation_paused`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不检查路线、不启动/停止 `NavigationTaskController`、不控制 `nav_timer`、不启用/禁用 `MotionController`；只负责旧中文 warning/status 文案。
### `gui/modes/navigation/presentation/route_command_state.py`
职责：封装 route 命令状态栏、路线保存失败 warning、移动目标定位 guard 和移动目标坐标提示。
关键导出：`show_route_command_status`、`warn_route_save_failed`、`warn_move_target_requires_localization`、`show_move_target_set`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不修改 `route_data`、不保存 `route.json`、不重绘 overlay、不调用 `MotionController`；只消费调用方传入的结果文案或 scene pos。
### `gui/modes/navigation/presentation/map_load_state.py`
职责：封装地图列表 combo 填充、地图加载成功 UI 状态，以及缺配置、加载失败、overlay 配置不完整的用户反馈。
关键导出：`populate_map_combo`、`apply_map_loaded_ui`、`warn_map_config_missing`、`show_map_load_failed`、`warn_overlay_map_config_incomplete`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`，并只依赖传入控件具备 `clear/addItems/addItem/setEnabled/setText` 或 route panel 具备 `set_buttons_enabled()`。
注意事项：不读取 `map_data`、不解析路径、不创建 `NavigationCore`、不应用配置；`populate_map_combo()` 保持旧行为：有地图时添加全部名称，无地图时添加缺省提示项。`apply_map_loaded_ui()` 保持旧中文成功文案，并只启用开始/初始位置按钮和 route panel。overlay 配置不完整时，按钮 checked 复位仍由 widget 控制，helper 只弹旧 warning。
### `gui/modes/navigation/presentation/map_presenter.py`
职责：封装导航地图 QGraphics scene 的 item 创建和常见 marker/rect 更新。
关键导出：`create_map_scene_items`、`update_player_marker`、`update_localization_view`、`update_monitor_rect_item`、`update_game_view_rect_item`、`center_view_on_global_position`、`create_last_position_marker`、`create_initial_hint_marker`、`set_target_marker`、`hide_item`。
对外依赖：`navigation.presentation.viewport_overlay.game_view_scene_rect`、`navigation.presentation.viewport_overlay.monitor_scene_rect`。
注意事项：该模块只接收 scene/view/nav_core/nav_config 和坐标，创建或更新 Qt item；不读取 route_data，不启动/停止导航，不调用输入执行器。`create_map_scene_items()` 会清空 scene 并返回 `map/player/target/monitor/game_view` item dict，调用方仍负责清空 route/event overlay 列表。`update_localization_view()` 通过回调调用 widget 的监控框/视野框更新函数，避免 presenter 直接知道 widget 私有状态，并返回新的 `player_item` 供 caller 写回。
### `gui/modes/navigation/presentation/dialog_host.py`
职责：封装导航页持有弹窗的显示、前置、恢复最小化和重复点击隐藏判定。
关键导出：`show_owned_dialog`、`toggle_owned_dialog`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QApplication`、`QWidget` 和 `Qt.WindowMinimized`。
注意事项：该模块只处理 Qt shell 生命周期，不创建具体 dialog、不连接信号、不保存配置。`toggle_owned_dialog()` 在 dialog 已可见且是 active window 时返回 `True`，由旧 caller 决定 hide；否则调用 `show_owned_dialog()` 显示并前置。`show_owned_dialog()` 仅在 dialog 尚未可见且 owner 存在时按 owner frame 左上角偏移 `(80, 80)` 移动弹窗，保持旧行为。
### `gui/modes/navigation/presentation/debug_overlay.py`
职责：封装导航 debug 幕布窗口的几何写入、隐藏和显示。
关键导出：`update_debug_overlay`。
对外依赖：`navigation.presentation.viewport_overlay.screen_overlay_geometry`。
注意事项：该模块不读取按钮状态、不弹配置警告、不构造截图矩形；调用方负责传入 `capture_rect/nav_config/scale`。当 overlay 为空或几何为空时返回 `False`；几何为空会调用 `overlay.hide_overlay()`，几何有效时调用 `overlay.set_rect_and_show()` 并返回 `True`。
### `gui/modes/navigation/presentation/route_overlay.py`
职责：绘制导航路线、出口圈、必经点、途经点、当前路径和当前子目标的 QGraphics overlay。
关键导出：`clear_route_overlay`、`render_route_overlay`。
对外依赖：`navigation.presentation.event_overlay.global_to_scene`。
注意事项：只接收 scene/nav_core/route_data/current path 等输入并创建/移除 QGraphicsItem，不修改 route 数据或导航任务状态。
### `gui/modes/navigation/presentation/event_overlay.py`
职责：封装导航地图事件 marker 的 QGraphics 绘制、坐标转换和旧事件 overlay item 清理。
关键导出：`clear_event_overlay`、`global_to_scene`、`render_event_overlay`。
对外依赖：无内部业务模块依赖；只接收调用方传入的 `scene/nav_core/event_coordinator/items`。
注意事项：该模块只绘制 `EventCoordinator.overlays()` 产出的 presentation 模型，不决定事件启用、调度或状态；`global_to_scene()` 同时被 route overlay 复用，避免 route/event 各自重复裁剪偏移换算。
### `gui/modes/navigation/presentation/status_presenter.py`
职责：构造并写入导航循环状态栏文案，封装运行态后缀追加和终态提示。
关键导出：`build_navigation_status_text`、`show_navigation_runtime_status`、`append_navigation_status_suffix`、`show_navigation_relocalizing`、`show_navigation_arrived`、`show_navigation_failed`。
对外依赖：无内部业务模块依赖。
注意事项：localized 时输出坐标/置信度/监视尺寸，未 localized 时输出定位中；可附加 intent message、path kind 和 event status。`append_navigation_status_suffix()` 保留旧行为：读取当前 label 文本并在末尾追加 ` | suffix`，因此调用顺序由 `NavigationRuntimeFrameLoop` 控制。
### `gui/modes/navigation/presentation/viewport_overlay.py`
职责：计算屏幕调试 overlay 逻辑矩形、地图内监控绿框和真实主画面橙框。
关键导出：`screen_overlay_geometry`、`monitor_scene_rect`、`game_view_scene_rect`。
对外依赖：无内部业务模块依赖。
注意事项：纯几何 helper；输入坐标必须保持物理像素、逻辑像素和地图全局坐标的边界清晰，避免用游戏视野框修正定位。
### `gui/modes/navigation/runtime/__init__.py`
职责：导航 runtime helper 包导出。
关键导出：`NavigationLocalizationResult`、`NavigationIntentConsumptionResult`、`NavigationFrameTick`、`NavigationRuntimeFrameLoop`、`NavigationRuntimeCommandLifecycle`、`NavigationRuntimeCommandLifecycleTargets`、`consume_navigation_intent`、`capture_navigation_localization_tick`、`compute_navigation_lookahead`、`should_run_navigation_tasks`、`resolve_player_local_position`、`update_navigation_task_controller`、`handle_relocalization_navigation_intent`、`handle_terminal_navigation_intent`。
对外依赖：`navigation.runtime.models`、`navigation.runtime.intent_consumption`、`navigation.runtime.localization_tick`、`navigation.runtime.frame_loop`、`navigation.runtime.command_lifecycle`、`navigation.runtime.loop_helpers`、`navigation.runtime.loop`、`navigation.runtime.relocalization_intent`、`navigation.runtime.terminal_intent`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/runtime/minimap_sample_capture.py`
职责：保存当前小地图监视区域样本，供事件识别和定位算法诊断使用。
关键导出：`MinimapSampleCaptureResult`、`save_minimap_sample(project_root, map_name, frame, capture_rect, monitor_size, player_local_pos, source, now_ms=None)`、`capture_current_minimap_frame(build_capture_geometry, screen_capture)`。
对外依赖：无内部业务模块依赖；只依赖 `cv2`、`numpy` 和文件系统。
注意事项：`save_minimap_sample()` 不做掉落物/传送门识别，也不做人像遮罩，只把输入帧转成 BGR 后写 PNG，并写同名 JSON 元数据。默认输出路径为 `debug/minimap_samples/<safe_map_name>/`，元数据记录 `capture_rect`、`monitor_size`、`player_local_pos`、`frame_shape` 和 `source`，用于复现实机监视区域。`capture_current_minimap_frame()` 是无缓存时的 fallback，调用方必须传入当前导航页的 `_build_capture_geometry` 和 `screen_capture`。

### `gui/modes/navigation/runtime/command_lifecycle.py`
职责：集中导航运行命令生命周期：普通导航启动/停止、自动导航启动/停止、timer/motion/task controller/input-window 状态转移、按钮回滚和状态栏反馈。
关键导出：`NavigationRuntimeCommandLifecycleTargets`、`NavigationRuntimeCommandLifecycle`。
对外依赖：`core.events.debug.start_event_log_session`、`navigation.presentation.navigation_command_state`。
注意事项：这是 runtime command 深模块。它通过 targets DTO 接收 Qt 按钮、timer、motion controller、task controller、输入窗口模式和 widget 回调，不直接持有 `NavigationModeWidget` 类型；保留旧顺序：启动前 guard，启动时应用 runtime config 和请求全图重定位，自动导航失败要复位按钮并停止 task，停止时要幂等关闭 timer/motion/task/input-window、停止手动事件测试、重绘 route overlay 并恢复按钮/状态栏。
### `gui/modes/navigation/runtime/frame_loop.py`
职责：集中导航定时器的单帧 runtime 编排。
关键导出：`NavigationRuntimeFrameLoop`。
对外依赖：`core.events.debug.event_log`、`navigation.event_adapter.event_status_text`、`navigation.input.execute_navigation_intent`、`navigation.presentation`、`navigation.runtime.intent_consumption`、`navigation.runtime.localization_tick`、`navigation.runtime.loop`、`navigation.runtime.loop_helpers`。
注意事项：这是 GUI navigation runtime facade，不是 core 算法层。它持有 `NavigationModeWidget` owner，只编排一帧顺序：截图定位、缓存最近小地图帧、事件 observe、任务 controller update、定位展示/状态栏刷新、route overlay、intent 消费。真实定位仍由 `NavigationCore.localize()` 完成，任务选择仍由 `NavigationTaskController.update_context()` 完成，真实输入仍由 `execute_navigation_intent()` 下发到 `MotionController`。最近帧缓存只服务 `save_minimap_sample()` 这类诊断采样，不改变事件检测路径。`NavigationModeWidget._navigation_loop_unified()` 现在只调用 `runtime_frame_loop.run()`，保持 Qt timer 入口兼容。
### `gui/modes/navigation/runtime/models.py`
职责：封装导航循环单帧定位结果，避免主循环直接散落 `global_x/global_y/conf` 判定。
关键导出：`NavigationLocalizationResult`。
对外依赖：无内部业务模块依赖。
注意事项：`from_core_result()` 保持 `NavigationCore.localize()` 的三元组契约；`localized_pos` 只有在 x/y 均不为 `None` 时返回 `(x, y)`。
### `gui/modes/navigation/runtime/intent_consumption.py`
职责：封装 `NavigationRuntimeFrameLoop.run()` 中 route overlay 之后的单个 intent 消费顺序。
关键导出：`NavigationIntentConsumptionResult`、`consume_navigation_intent`。
对外依赖：`navigation.runtime.relocalization_intent.handle_relocalization_navigation_intent`、`navigation.runtime.terminal_intent.handle_terminal_navigation_intent`。
注意事项：该 helper 不执行 route overlay，也不直接知道 QWidget；真实输入仍由传入的 `execute_intent` 回调处理。执行顺序保持旧逻辑：先 force-relocalize 短路，再执行输入，再处理手动事件测试 terminal metadata，最后处理 ARRIVED/FAILED 终态。返回 DTO 只告诉 widget 是否跳过本帧剩余逻辑、是否关闭 `auto_navigation_enabled`。
### `gui/modes/navigation/runtime/localization_tick.py`
职责：封装导航循环开头的截图与定位输入段。
关键导出：`NavigationFrameTick`、`capture_navigation_localization_tick`。
对外依赖：`navigation.runtime.loop.resolve_player_local_position`、`navigation.runtime.models.NavigationLocalizationResult`。
注意事项：该 helper 不修改 QWidget 状态；它通过 `build_capture_geometry` callback 获取截图几何，通过 `screen_capture.capture()` 抓屏，调用 `resolve_player_local_position()` 得到玩家局部坐标，再调用 `nav_core.localize()` 构造 `NavigationLocalizationResult`。调用方仍负责把返回的 `capture_rect/player_pos` 写回 `_current_capture_rect/_current_player_local_pos`。
### `gui/modes/navigation/runtime/loop_helpers.py`
职责：封装导航循环中纯运行时判定和 lookahead 公式。
关键导出：`should_run_navigation_tasks`、`compute_navigation_lookahead`。
对外依赖：无内部业务模块依赖。
注意事项：`compute_navigation_lookahead()` 保持原公式 `max(36.0, min(capture_width * draw_scale * 0.18, 120.0))`；`should_run_navigation_tasks()` 保持“自动导航或手动事件测试任一启用即运行任务控制器”的规则。
### `gui/modes/navigation/runtime/loop.py`
职责：封装导航循环中仍属于 runtime 编排、但不应留在 QWidget 内的局部步骤。
关键导出：`resolve_player_local_position`、`observe_navigation_events`、`update_navigation_task_controller`。
对外依赖：无内部业务模块依赖；通过参数接收 nav_config、nav_core、tracker、NavigationTaskController、PathFinder 等运行对象。
注意事项：`resolve_player_local_position()` 保持原逻辑：显式 `monitor_region` 模式先用 recognizer/tracker 找玩家局部坐标，失败时回退上一帧局部坐标，再回退截图中心；中心点截图模式直接使用默认玩家坐标。`observe_navigation_events()` 调用传入的 `build_event_tick()`、`EventCoordinator.observe()`、`render_event_overlay()` 和可见 event dialog 的 `refresh_tasks()`，并把 `event_tick` 返回给后续 task update；这是后续接 hook/总线的边界，但当前没有 hook 实现。`update_navigation_task_controller()` 负责构造 `NavigationUpdateContext` 并调用 `navigation_task_controller.update_context()`，不改变任务选择、事件 handler 或输入执行。
### `gui/modes/navigation/runtime/relocalization_intent.py`
职责：封装导航任务返回 force-relocalize intent 后的运行态恢复分支。
关键导出：`handle_relocalization_navigation_intent`。
对外依赖：无内部业务模块依赖；通过回调接收 `NavigationCore.request_global_relocalization()`、`event_log()` 和重新定位状态展示函数。
注意事项：该模块不 import QWidget，也不直接 import `NavigationCore`；它只读取 `intent.metadata.force_relocalize/relocalize_reason/relocalize_score`，保持默认 reason 为 `coordinate_recovery`，并返回 bool 告诉主循环是否应该提前结束本帧。
### `gui/modes/navigation/runtime/terminal_intent.py`
职责：封装导航终态 intent 的运行态收束顺序。
关键导出：`handle_terminal_navigation_intent`。
对外依赖：`core.navigation_tasks.models.NavigationIntentType`。
注意事项：该模块不 import QWidget，不直接知道按钮或 status label；通过回调执行 `NavigationTaskController.stop()`、关闭游戏输入窗口、复位自动导航按钮和显示 ARRIVED/FAILED 文案。非 ARRIVED/FAILED intent 返回 `False` 且不触发任何回调。该 helper 仅处理单个终态 intent 的收束，不停止 `nav_timer`，保持自动导航到达后定位循环继续运行的旧行为。
### `gui/modes/navigation/event_adapter.py`
职责：封装导航模式和事件系统之间的轻量桥接，不推进事件状态机。
关键导出：`create_default_event_registry`、`event_config_summary`、`find_default_game_window_rect`、`build_event_tick`、`event_status_text`。
对外依赖：`core.events.models.EventTick`、`core.events.registry.EventRegistry`、`core.events.types.portal.PortalEventDefinition`、`core.events.window_finder.find_game_window`。
注意事项：该模块只组装事件系统需要的输入和状态文案；事件 handler 的执行由 `NavigationTaskController` 通过 `EventCoordinator.run_task()` 触发，真实输入由 `NavigationRuntimeFrameLoop._execute_navigation_intent()` 统一消费。旧 UI 级 `EventAction` 仲裁 helper 已移除，`EventActionType` 翻译只保留在 core navigation task 层。
### `gui/modes/navigation/map/config_store.py`
职责：封装导航模式地图目录解析、地图列表读取、导航配置 JSON 读写、默认配置 fallback 和 merge 保存。
关键导出：`MISSING_MAP_DATA_LABEL`、`project_root_from_file`、`map_data_dir`、`list_map_names`、`resolve_map_folder`、`load_nav_config`、`save_nav_config`、`default_nav_config_path_from_file`、`default_nav_config_path_from_map_folder`、`save_default_nav_config`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：该模块不弹窗、不改按钮、不初始化 `NavigationCore`；调用方仍负责 UI 状态和异常提示。`load_nav_config()` 优先读取当前地图 `config.json`，缺失时读取项目根 `config.json` 作为默认配置但仍返回 `config_exists=False` 供 UI 提示。`save_nav_config()` 和 `save_default_nav_config()` 合并写入已有 JSON，保留绘图模式字段，并把旧 `recognizer_params` 与 `NavConfig.to_dict()` 中的新值合并后写回。项目根、`map_data` 和默认根配置路径已委托 `gui/composition/paths.py`，不再依赖固定 `parents[n]`。
### `gui/modes/navigation/map/capture_geometry.py`
职责：封装导航截图 logical/physical 中心换算和 capture rect/player pos 几何计算。
关键导出：`physical_center_from_logical`、`initial_capture_center_for_config`、`build_capture_geometry`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：纯几何 helper，不读写文件、不访问 Qt 控件。`initial_capture_center_for_config()` 现在由 `prepare_navigation_map_load_session()` 使用，用于初始化 `_capture_center_physical` 和参数弹窗展示用物理中心；真正截图矩形仍由 `build_capture_geometry()` 计算。`build_capture_geometry()` 保留旧契约：显式 `monitor_region` 返回矩形且 player_pos 为 `None`，中心点模式返回正方形截图矩形和截图中心 player_pos；缺少配置或中心点时返回空几何，由调用方决定隐藏 overlay 或跳过导航循环。
### `gui/modes/navigation/calibration/__init__.py`
职责：导航校准 helper 包导出。
关键导出：`NavigationScreenCalibrationLifecycle`、`NavigationScreenCalibrationLifecycleTargets`、`ScreenCenterCalibrationController`、`physical_point_from_logical`、`screen_scale`。
对外依赖：`navigation.calibration.lifecycle`、`navigation.calibration.screen_center`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/calibration/lifecycle.py`
职责：封装导航页屏幕中心校准的完整 UI/runtime 副作用顺序。
关键导出：`NavigationScreenCalibrationLifecycleTargets`、`NavigationScreenCalibrationLifecycle`。
对外依赖：`navigation.presentation.show_screen_center_calibrated`、`navigation.calibration.screen_center.ScreenCenterCalibrationController`（通过 targets 注入）。
注意事项：该模块负责 `NavConfig.game_screen_center` 写回、参数弹窗回填、overlay 刷新、配置保存、完成提示和 selector 关闭；不负责 DPR 读取或 selector 实例创建细节，这些仍由 `screen_center.py` 的 controller 持有。
### `gui/modes/navigation/calibration/screen_center.py`
职责：封装屏幕中心校准选择器生命周期、DPR 缩放读取和逻辑坐标到物理坐标转换。
关键导出：`ScreenCenterCalibrationController`、`screen_scale`、`physical_point_from_logical`。
对外依赖：`gui.selection.center_selector.CenterPointSelector`。
注意事项：controller 只负责创建/复用/关闭 `CenterPointSelector` 和坐标转换；不写 `NavConfig`、不保存 config、不弹完成提示。`start()` 在选择器已可见时返回 `False` 并避免重复创建，保持旧“重复点击校准按钮不弹多个全屏选择器”的行为。
### `gui/composition/__init__.py`
职责：GUI composition helper 包入口。
关键导出：`CoreServices`、`create_core_services`、`project_root_from_file`、`project_root_from_map_folder`、`map_data_dir_from_file`、`root_config_path_from_file`、`root_config_path_from_map_folder`、`advanced_settings_dir_from_file`。
对外依赖：`gui.composition.paths`、`gui.composition.services`。
注意事项：只聚合导出，不承载业务逻辑；这是正式 package 入口，不是旧兼容壳。
### `gui/composition/services.py`
职责：集中创建 GUI 应用共享的 core service 集合，并提供可注入的 DTO。
关键导出：`CoreServices`、`create_core_services`。
对外依赖：`core.platform.SquareScreenCapture`、`core.vision.HSVRecognizer`、`core.vision.PlayerTracker`、`core.mapping.MapStitcher`、`core.routing.PathFinder`。
注意事项：默认 `create_core_services(canvas_size=5000)` 保持原 `AppContext` 初始化行为；`CoreServices` 是 frozen dataclass，用于未来 smoke/test 或替代 adapter 注入。`ColorPickerDialog` 的临时 `HSVRecognizer` 不在此集中，因为它是对话框局部预览状态，不属于 AppContext 共享服务。
### `gui/composition/paths.py`
职责：集中解析 GUI 层使用的项目根目录、`map_data` 目录、根 `config.json` 和高级参数 snapshot 目录。
关键导出：`project_root_from_file`、`project_root_from_map_folder`、`map_data_dir_from_file`、`root_config_path_from_file`、`root_config_path_from_map_folder`、`advanced_settings_dir_from_file`。
对外依赖：无内部业务模块依赖。
注意事项：`project_root_from_file()` 从传入文件或目录向上查找同时包含 `main.py` 和 `gui/` 的目录，不再依赖固定 `parents[n]`；`project_root_from_map_folder()` 优先识别 `map_data/<map_name>` 结构并返回 `map_data` 父目录。当前替换范围包括 mapping config store、navigation map config store 和 advanced settings file IO；utils/core 中的探针或日志路径暂不纳入 GUI composition。
### `gui/modes/mapping_widget.py`
职责：绘图模式主界面组合根，仍负责路径点击入口、保存时机、参数应用顺序和状态栏更新；UI 控件构建已委托 `mapping/ui/layout.py`，监控启动/停止和 capture timer 已委托 runtime lifecycle，单帧 capture-recognize-stitch 主流程已委托 runtime session，display 写入已委托 presentation presenter，区域/中心点选择已委托 capture controller。
关键导出：`MappingWidget`。
对外依赖：`ColorPickerDialog`、`AdvancedSettingsDialog`、`gui.modes.mapping.capture.MappingCaptureSelectionController`、`gui.modes.mapping.io`、`gui.modes.mapping.map_renderer`、`gui.modes.mapping.params`、`gui.modes.mapping.runtime.MappingRuntimeLifecycle`、`gui.modes.mapping.runtime.MappingSession`、`gui.modes.mapping.ui.build_mapping_ui`。
注意事项：`setup_ui()` 现在只调用 `build_mapping_ui(self)`，原 `create_control_panel()` / `create_display_panel()` 内联布局已删除；控件属性名和 signal 目标仍写回 `MappingWidget`，以保持 config restore、params binding 和外部 slot 不变。`toggle_monitoring()` 与 `stop_runtime()` 作为按钮和 `MainWindow.closeEvent()` 的稳定入口保留，但真实 monitoring flag、QTimer 启停、缺少截图配置 warning 和按钮文案更新已委托 `mapping/runtime/lifecycle.py`。`capture_and_process()` 作为 QTimer tick callback 保留，但现在只检查 monitoring、调用 `MappingSession.tick()`、更新 `last_capture_size/last_player_local_pos`，再刷新 display/stats。`select_region()`、`on_region_selected()`、`select_center_point()`、`on_center_selected()` 和 `update_capture_size()` 仍保留旧 slot/API 名称，但实际 overlay 启动、DPI 转换、`app_context.monitor_region/monitor_logical_center/monitor_size` 写回都委托 `mapping/capture/selection_controller.py`；widget 只负责按钮启用、label 文案和保存配置。`save_map()`、`save_config()`、`load_saved_params()` 作为外部入口保留；路径解析、目录创建、JSON 读写和配置 dict 构造在 `mapping/io/config_store.py`，启动时根配置恢复、AppContext 写回、capture selection restore 和 Qt 控件同步已委托 `mapping/io/config_restore.py`，保存地图包和地图级 config 写入顺序已委托 `mapping/io/map_save.py`。`update_displays()` 入口保留，但 capture label、global map widget 和 `map_crop_offset` 更新已委托 `mapping/presentation/map_presenter.py`；图像转换、全局地图着色、路径线、视野框和当前位置圆点绘制继续由 `mapping/map_renderer.py` 承担。HSV/feature/merge 参数控件读取从 `mapping/params` 导入，旧 `mapping/params_adapter.py` 已删除；本类仍决定何时调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`，以保持原副作用顺序。高分辨率绘图参数 `draw_scale`、`canvas_size`、`player_clear_radius`、`wall_close_kernel_size` 已作为绘图页控件暴露；空地图时几何参数可立即重建画布，已有帧时仅保存为下次重置/新地图使用。

### `gui/modes/mapping/__init__.py`
职责：绘图模式 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。
### `gui/modes/mapping/ui/__init__.py`
职责：绘图模式 UI 构建包入口。
关键导出：`build_mapping_ui`。
对外依赖：`mapping.ui.layout`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/ui/layout.py`
职责：构建绘图模式控制面板和显示面板，把旧内联控件创建、默认值、信号连接和地图显示 widget 初始化集中到 UI shell 模块。
关键导出：`build_mapping_ui`、`create_mapping_control_panel`、`create_mapping_display_panel`。
对外依赖：`gui.widgets.collapsible_group.CollapsibleMapGroup`。
注意事项：该模块只创建 Qt 控件并挂回 owner 字段，不读取/写入 config 文件、不启动 capture timer、不调用 recognizer/stitcher；它仍有意依赖 `MappingWidget` 的稳定 slot 名称和字段名，因为 config restore、params binding 和 runtime wrapper 仍以这些属性为组合根契约。
### `gui/modes/mapping/capture/__init__.py`
职责：绘图模式 capture selection 包导出。
关键导出：`CaptureSelectionResult`、`MappingCaptureSelectionController`。
对外依赖：`mapping.capture.selection_controller`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/capture/selection_controller.py`
职责：封装建图页区域/中心点选择 overlay 生命周期、逻辑像素到物理像素转换、AppContext monitor 字段写回和已保存选择恢复。
关键导出：`CaptureSelectionResult`、`MappingCaptureSelectionController`。
对外依赖：`gui.selection.region_overlay.TransparentOverlay`、`gui.selection.center_selector.CenterPointSelector`。
注意事项：controller 不直接操作建图页按钮、label 或 config 文件；它通过回调把 `CaptureSelectionResult` 交还 widget。`compute_scale`、overlay factory、center selector factory 通过构造参数注入，便于后续多屏/DPR 适配或 smoke 测试替换。
### `gui/modes/mapping/runtime/__init__.py`
职责：绘图模式 runtime 包导出。
关键导出：`MappingRuntimeLifecycle`、`MappingRuntimeLifecycleTargets`、`MappingSession`、`MappingTickResult`。
对外依赖：`mapping.runtime.lifecycle`、`mapping.runtime.models`、`mapping.runtime.session`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/runtime/lifecycle.py`
职责：封装绘图模式监控启动/停止命令、capture timer 生命周期、`app_context.monitoring` 状态和开始按钮文案。
关键导出：`MappingRuntimeLifecycleTargets`、`MappingRuntimeLifecycle`。
对外依赖：无内部业务模块依赖；使用 `QTimer` 和 `QMessageBox`。
注意事项：该 lifecycle 不执行单帧建图算法；timer tick 通过 `on_tick` 回调进入 `MappingWidget.capture_and_process()`。`toggle_monitoring()` 保持旧顺序：先翻转 monitoring，若缺少区域/中心点配置则回滚并弹 warning；配置存在时按 `1000 // fps` 启动 timer 并改按钮文案。`stop_runtime()` 是幂等停止入口，供按钮停止分支和主窗口关闭调用。
### `gui/modes/mapping/runtime/models.py`
职责：承载单帧建图 tick 的输出，让 widget 不必了解 session 内部中间变量。
关键导出：`MappingTickResult`。
对外依赖：无内部业务模块依赖。
注意事项：字段包括 `current_image`、`combined_mask`、`player_pos`、`capture_size`；当前用 `object` 承载 OpenCV/Numpy 图像对象，避免 GUI 层引入额外图像类型约束。
### `gui/modes/mapping/runtime/session.py`
职责：执行单帧建图 runtime 流程：截图、玩家局部坐标 fallback、mask 提取、raw gray 提取、stitcher add frame 和预处理图返回。
关键导出：`MappingSession`。
对外依赖：`mapping.runtime.models.MappingTickResult`。
注意事项：该 session 只通过 `app_context` 调用 `screen_capture/recognizer/tracker/stitcher`，通过回调读取当前物理 monitor center 和上一帧 player pos，不触碰 Qt 控件、不更新 display、不写统计。中心截图模式 player pos 固定为截图中心；区域截图模式检测失败时依次回退上一帧 player pos 和截图中心。
### `gui/modes/mapping/presentation/__init__.py`
职责：绘图模式 presentation 包导出。
关键导出：`MappingDisplayResult`、`update_mapping_displays`。
对外依赖：`mapping.presentation.map_presenter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/presentation/map_presenter.py`
职责：封装绘图模式 capture label 和 global map widget 的显示写入，并返回新的 map crop offset。
关键导出：`MappingDisplayResult`、`update_mapping_displays`。
对外依赖：`mapping.map_renderer.pixmap_from_bgr`、`render_global_map_pixmap`、`unpack_enhanced_map_result`。
注意事项：该 presenter 不调用 `recognizer.extract_combined()` 或 `stitcher.add_frame()`；它只读取 `stitcher.get_enhanced_map()`/`get_current_position()` 生成显示 pixmap。global map 为空时保留旧 crop offset，不触碰 global map widget。

### `gui/modes/mapping/map_renderer.py`
职责：封装绘图模式图像展示相关转换和 OpenCV overlay 绘制。
关键导出：`pixmap_from_bgr`、`unpack_enhanced_map_result`、`render_global_map_pixmap`。
对外依赖：无内部业务模块依赖；只使用 OpenCV/Numpy/PySide6 图像类型。
注意事项：该模块不读取 `app_context`、不调用 stitcher、不设置 Qt 控件；调用方传入已取出的地图图像、裁剪偏移、路径、当前位置、draw_scale、player_pos 和 capture_size。颜色、线宽和 fallback 解包逻辑保持原 `MappingWidget.update_displays()` 行为。

### `gui/modes/mapping/params/__init__.py`
职责：绘图模式 params binding 包导出。
关键导出：`apply_hsv_toggles`、`feature_params_from_widgets`、`apply_merge_weight`、`sync_recognizer_widgets`、`sync_stitcher_widgets`、`sync_geometry_widgets`。
对外依赖：`mapping.params.binding`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/mapping/params/binding.py`
职责：封装绘图模式参数控件到 recognizer/stitcher 参数字段的轻量映射。
关键导出：`apply_hsv_toggles`、`feature_params_from_widgets`、`apply_merge_weight`、`sync_recognizer_widgets`、`sync_stitcher_widgets`。
对外依赖：无内部业务模块依赖；只使用传入的控件和 recognizer/stitcher 对象。
注意事项：该模块不保存配置、不弹窗、不创建控件、不阻断 Qt 信号。`sync_recognizer_widgets()` 和 `sync_stitcher_widgets()` 保持原 `setChecked()`/`setValue()` 写回顺序和默认值，因此仍可能触发既有信号副作用；这是为保持行为不变而刻意保留。

### `gui/modes/mapping/io/__init__.py`
职责：绘图模式 IO helper 包导出。
关键导出：`project_root_from_file`、`map_data_dir`、`map_folder_for_name`、`ensure_map_folder`、`root_config_path`、`build_mapping_config`、`save_json_config`、`load_json_config`、`save_root_config`、`load_root_config`、`save_map_config`、`MappingConfigRestoreTargets`、`restore_saved_mapping_config`、`save_mapping_map`。
对外依赖：`mapping.io.config_store`、`mapping.io.config_restore`、`mapping.io.map_save`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/mapping/io/config_store.py`
职责：封装绘图模式项目根目录解析、`map_data` 目录定位、地图目录创建、根级/地图级 `config.json` 读写和配置 dict 构造。
关键导出：`project_root_from_file`、`map_data_dir`、`map_folder_for_name`、`ensure_map_folder`、`root_config_path`、`build_mapping_config`、`save_json_config`、`load_json_config`、`save_root_config`、`load_root_config`、`save_map_config`。
对外依赖：`gui.composition.paths`；通过传入的 `app_context` 读取当前 recognizer/stitcher 参数。
注意事项：该模块不弹窗、不写 Qt 控件、不调用 `stitcher.save_map_package()`；`json.dump(..., indent=4)` 保持旧保存格式，未设置 `ensure_ascii=False` 以避免改变现有输出行为。项目根、`map_data` 和根配置路径已委托 `gui/composition/paths.py`，原 public helper 名称保留给 mapping IO 调用方。

### `gui/modes/mapping/io/config_restore.py`
职责：封装绘图页启动时根配置恢复编排，把 `config.json` 应用到 AppContext、capture selection controller 和 Qt 控件。
关键导出：`MappingConfigRestoreTargets`、`restore_saved_mapping_config`。
对外依赖：`mapping.io.config_store.load_root_config`、`mapping.params.binding`。
注意事项：该模块不是纯存储层；它会写 `app_context.monitor_*`、调用 `recognizer.set_params()` / `stitcher.set_params()`，必要时在空 stitcher 上调用 `reinitialize_canvas()`，并通过 `QSignalBlocker` 同步几何控件。它不弹窗、不显示 warning、不保存配置；错误仍由 `MappingWidget.load_saved_params()` 外层处理。

### `gui/modes/mapping/io/map_save.py`
职责：封装绘图页保存地图包和地图级配置的 IO 编排。
关键导出：`save_mapping_map`。
对外依赖：`mapping.io.config_store.ensure_map_folder`、`mapping.io.config_store.save_map_config`。
注意事项：该模块不弹输入框、不显示成功消息；`MappingWidget.save_map()` 仍负责 `QInputDialog` 和 `QMessageBox`。保存顺序保持旧行为：先确保 `map_data/<map_name>` 目录，再调用 `stitcher.save_map_package(str(map_folder))`，最后写 `map_folder/config.json`。

### `core/navigation_tasks/*`
职责：方案 C 的统一导航任务层，把静态路线目标和动态事件目标放进同一调度与移动执行链路。
关键导出：`NavigationTaskController`、`NavigationTaskScheduler`、`NavigationTaskBuilder`、`MovementExecutor`、`movement_step`、`plan_movement_path`、`ensure_movement_path`、`CoordinateDiagnostics`、`CoordinateRelocalizationRequest`、`RouteContext`、`NavigationTask`、`NavigationIntent`、`NavigationIntentType`。
对外依赖：`core.routing.anchors`、`core.routing.geometry`、`core.events.models.EventActionType`。
注意事项：`NavigationTaskController` 是自动导航和手动事件测试的唯一运行控制器；原普通导航器、事件路径移动器、事件动作执行器三个旧模块已删除。`NavigationTaskController.update_context()` 已委托 `update_pipeline.py`，required/exit 静态任务委托 `static_task_runner.py`，event 任务委托 `event_task_runner.py`，runtime 生命周期/定位/required progress/重定位 intent 已委托 `controller_runtime/` 子包；旧 `update(**kwargs)`、`update_context(context)`、`observe_localization()`、`_consume_relocalization_intent()`、`_update_required_progress()`、`record_intent_click()` 入口仍保留。`RouteContext` 负责 guide_points 折线投影和单调路线进度；`NavigationTaskBuilder` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中可运行事件转成 `NavigationTask`；`NavigationTaskScheduler` 只对 event 持有 active lock，静态 required/exit 每帧重新仲裁以允许新事件抢占；`MovementExecutor` 现在是薄 facade，保留 `step()`、`record_click()`、`_ensure_path()`、`_plan_path()`、`_local_probe()`、`_is_stuck()` 等旧入口，实际流程委托 `movement/pipeline.py`、`movement/path_maintenance.py`、`movement/path_planner.py` 和 `movement/recovery.py`。事件 `MOVE_TO` 和普通 required/exit 都走 `MovementExecutor.step()`，事件 `PRESS_KEY/CLICK_SCREEN` 直接转成 `NavigationIntent` 由 GUI 消费。`CoordinateDiagnostics` 是内部坐标恢复机制，不进入事件系统，不和 portal 等业务事件竞争调度；当前 `CoordinateDiagnostics` facade 保留旧 public 方法和私有 wrapper，定位诊断、导航状态诊断、重定位请求生命周期和日志格式化已拆到 `coordinate/` 子包。

### `core/localization/navigation_core/runtime.py`
职责：读取 `map_data.npz`，用实时小地图截图定位玩家在全局地图中的坐标，并作为定位系统的状态拥有者。
关键导出：`NavigationCore`。
对外依赖：`core.localization.localize_pipeline`、`core.localization.map_package`、`core.localization.rendering`、`core.localization.visual_check`、`core.vision.phase_displacement`、`core.vision.hsv_recognizer`。
注意事项：`NavigationCore` 仍是对外 facade class，GUI/任务层仍可直接读写 `draw_scale`、`nav_wall_layer`、`explored_map`、`crop_offset`、`current_pos`、`last_good_pos`、`drawing_saved_pos`、`last_frame_registration`。`localize()` 主流程委托 `core.localization.localize_pipeline.localize_frame()`，旧公开入口不改。`draw_scale` 必须与建图保持一致；定位运行时以 `map_data.npz` 里的 `draw_scale` 为权威来源，导航配置里的同名字段只作为旧配置/显示兼容。输出坐标是全局地图坐标，不是屏幕点击坐标。原始 `wall_layer` 必须保持不变并继续服务定位、事件配准和地图显示；`nav_wall_layer` 是由原始墙图派生出的 A* 专用障碍层。`request_full_map_localization()` / `request_global_relocalization()` 只用于清空 F2F 状态并强制下一帧走完整 `wall_layer` 模板匹配。

### `core/localization/navigation_core/state.py`
职责：承接 `NavigationCore.__init__()` 中的 map path/default 参数初始化和运行态字段初始化。
关键导出：`initialize_map_configuration`、`require_map_data_file`、`initialize_runtime_state`。
对外依赖：`core.shared.frame_registration.FrameRegistration`。
注意事项：当前保持旧构造顺序：先加载地图包，再初始化定位运行态字段；因此不修复旧行为中的 `current_pos` 加载后又被运行态重置问题，避免结构整理混入行为变更。

### `core/localization/navigation_core/registration.py`
职责：承接 `NavigationCore._clear_frame_registration()` 和 `_set_frame_registration()` 的状态写回。
关键导出：`clear_navigation_frame_registration`、`set_navigation_frame_registration`。
对外依赖：`core.localization.frame_registration`。
注意事项：该模块写回 `nav_core.last_frame_registration`，旧私有方法名仍在 `NavigationCore` 上作为 wrapper。

### `core/localization/navigation_core/relocalization.py`
职责：承接初始位置提示、强制全图重定位请求、full/local 定位模式判断和模板匹配阈值策略。
关键导出：`set_initial_hint`、`request_full_map_localization`、`is_full_map_localization`、`template_match_required_confidence`。
对外依赖：无内部业务模块依赖。
注意事项：`request_global_relocalization()` 仍是 `NavigationCore` 上的兼容别名。

### `core/localization/navigation_core/wall_layer.py`
职责：承接导航专用墙层派生和墙体模板 wrapper。
关键导出：`rebuild_navigation_wall_layer`、`navigation_wall_close_kernel`、`standardize_navigation_wall_template`。
对外依赖：`core.routing.obstacles`、`core.localization.frame_matcher`。
注意事项：该模块只派生 `nav_wall_layer`，不改变定位用 `wall_layer`。

### `core/localization/navigation_core/diagnostics.py`
职责：承接定位模板匹配失败的节流日志。
关键导出：`log_template_match_failure`。
对外依赖：OpenCV。
注意事项：日志字段保持旧内容，包括置信度、阈值、full_map/forced 状态、raw/scaled mask 尺寸、特征数、搜索区域和闭运算核。

### `core/localization/localize_pipeline.py`
职责：承接 `NavigationCore.localize()` 的完整定位帧处理流程。
关键导出：`localize_frame`。
对外依赖：OpenCV、NumPy、`core.localization.frame_matcher`。
注意事项：该模块接收 `NavigationCore` 实例并写入其定位状态，因为 F2F、模板匹配、forced relocalization、jump rejection、frame registration 属于同一帧生命周期。旧 `NavigationCore.localize()` 保留为公开 facade。

### `core/localization/frame_registration.py`
职责：集中构建 `NavigationCore.last_frame_registration`，把“定位失败帧”和“已知玩家点的有效帧配准”从 facade 中拆出。
关键导出：`clear_frame_registration`、`build_frame_registration`。
对外依赖：`core.shared.frame_registration.FrameRegistration`。
注意事项：该模块只返回 `FrameRegistration` 对象，不直接写 `nav_core` 状态。有效配准的 `frame_origin_global = player_global_pos - player_local_pos * draw_scale`，`frame_size` 从 OpenCV frame shape 转成 `(width, height)`，metadata 会复制成普通 dict，避免调用方后续修改原 dict 污染已保存配准。

### `core/localization/frame_matcher.py`
职责：封装导航模板匹配前的墙体模板处理和搜索窗口选择。
关键导出：`normalized_wall_close_kernel_size`、`wall_close_kernel`、`standardize_wall_template`、`scaled_template_size`、`scale_wall_template`、`select_template_search_area`。
对外依赖：无内部业务模块依赖；只使用 OpenCV。
注意事项：`scale_wall_template()` 保持旧行为：把实时小地图的 1x `wall_mask` 按 `draw_scale` 放大到地图尺度，再按 `wall_match_close_kernel_size` 做 MORPH_CLOSE。`select_template_search_area()` 保持旧 local/full 语义：全图定位直接返回完整 `wall_layer`；局部定位围绕 `current_pos` 取 `local_search_radius` 窗口，若窗口比放大后的模板小则回退全图搜索。该模块不调用 `cv2.matchTemplate()`，匹配结果解析和状态写入仍留在 `NavigationCore.localize()`。

### `core/localization/visual_check.py`
职责：封装 F2F 跟踪期间的视觉一致性复核，即把当前小地图墙体 mask 放到“当前认为的玩家全局位置附近”重新做局部模板匹配，判断截图最佳贴图位置是否偏离当前跟踪坐标。
关键导出：`visual_check_position`。
对外依赖：`core.localization.frame_matcher.scale_wall_template`。
注意事项：该 helper 仍接收 `nav_core`，因为需要读取 `visual_check_interval_ms`、`visual_check_margin`、`visual_check_min_confidence`、`visual_mismatch_threshold`、`draw_scale`、`wall_layer`，并更新 `_last_visual_check_ms` 节流时间。返回 dict 会被写入 `FrameRegistration.metadata`，包括 `visual_conf`、`visual_expected_score`、`visual_player`、`visual_delta`、`visual_delta_dist`、`visual_mismatch`；异常不会传播，而是返回 `visual_check=failed` 和失败原因。

### `core/routing/pathfinder/runtime.py`
职责：把调用方传入的障碍层结合 `explored_map` 转为低分辨率 A* 网格，并输出全局地图路径点。
关键导出：`PathFinder`。
对外依赖：`core.routing.pathfinder.grid`、`astar`、`snap`、`coordinates`。
注意事项：路径点用于地图导航，不能直接当屏幕点击点。默认 `safety_margin=0`、`wall_shrink_iterations=0`，墙体变薄优先在 `NavigationCore.nav_wall_layer` 派生阶段完成，避免双重侵蚀。`start_clear_radius` 会在 A* 网格上清空玩家当前位置附近的小圆，容忍“定位点落在视觉墙像素内”；`walkable_snap_radius` 控制起终点落障碍时寻找最近可走格的半径。`explored_map==0` 必须视为不可走，否则 A* 会穿过地图外黑区。旧 `_build_obstacle_map()`、`_clear_start_area()`、`_astar()`、`_heuristic()`、`_reconstruct_path()`、`_find_nearest_walkable()` 仍保留为 wrapper。

### `core/routing/pathfinder/grid.py`
职责：构建 A* 使用的降采样障碍网格。
关键导出：`build_obstacle_map`、`apply_explored_obstacles`、`apply_safety_margin`、`clear_start_area`。
对外依赖：OpenCV、NumPy。
注意事项：先 threshold 原始 wall map，可选 erode 墙体，再 resize 到 grid 尺寸；`explored_map` 中 0 会转成障碍；`safety_margin` 以 map-space 像素传入并转换成 grid 半径。

### `core/routing/pathfinder/astar.py`
职责：执行 8 邻接 A* 搜索。
关键导出：`astar_path`、`diagonal_cuts_corner`、`heuristic`、`reconstruct_path`。
对外依赖：标准库 `heapq`。
注意事项：斜向移动 cost 为 `1.414`，正交为 `1.0`；如果任一相邻正交格被阻挡，则拒绝斜向移动，防止 corner cutting。

### `core/routing/pathfinder/snap.py`
职责：在起点/终点落入障碍时寻找最近可走格。
关键导出：`find_nearest_walkable`、`walkable_snap_grid_radius`。
对外依赖：无内部模块依赖。
注意事项：使用 Manhattan-radius scan，保持旧“找到第一个可走格就返回”的行为。

### `core/routing/pathfinder/coordinates.py`
职责：集中 map-space 与 grid-space 坐标转换。
关键导出：`map_to_grid`、`grid_size_from_map_shape`、`in_grid_bounds`、`grid_path_to_map_path`。
对外依赖：无内部模块依赖。
注意事项：grid path 转 map-space 时返回每个格子的中心点，并按旧行为追加精确 `end_pos`。

### `core/mapping/stitcher.py`
职责：将实时小地图墙层/地面层融合到全局地图，并输出供绘图模式与导航模式共用的地图包。
关键导出：`MapStitcher`。
对外依赖：`core.mapping.package_io`、`core.mapping.performance`、`core.mapping.frame_preparation`、`core.mapping.frame_pipeline`、`core.mapping.weighted_merge`、`core.mapping.rendering`、`core.vision.phase_displacement`。
注意事项：`save_map_package()`、`load_map_package()`、`add_frame()`、`get_cropped_map()`、`get_enhanced_map()` 等入口不改。当前版本不再把整块截图矩形无脑写入 `explored_map`；优先使用 `fog_mask` 作为精准可见区域，并同步维护 `fog_layer`，这样生成的地图更接近游戏实际小地图结构。性能工具在 `mapping/performance.py`；帧 mask 缩放、墙体厚度标准化、重复相似度和边界判断在 `mapping/frame_preparation.py`；`add_frame()` 主流程在 `mapping/frame_pipeline.py`，`MapStitcher` 仍统一持有状态。

### `core/mapping/performance.py`
职责：封装建图性能计时工具。
关键导出：`PerformanceMonitor`、`Timer`。
对外依赖：标准库 `time`。
注意事项：`PerformanceMonitor.record()` 按名称保留最近 100 次耗时；旧 no-op `print_report()` 已删除，避免保留无行为兼容钩子。`Timer` 是上下文管理器，退出时把耗时毫秒写入 monitor。

### `core/mapping/frame_preparation.py`
职责：封装 `MapStitcher` 在落图前需要的纯计算 helper。
关键导出：`standardize_wall_thickness`、`prepare_scaled_frame_masks`、`scaled_player_pos`、`is_too_similar`、`bounds_in_canvas`。
对外依赖：OpenCV、NumPy。
注意事项：`prepare_scaled_frame_masks()` 保持旧行为：按 `draw_scale` 放大 `save_mask/fog_mask`，再对 `save_mask` 做 MORPH_CLOSE。`is_too_similar()` 保持旧 IoU 逻辑：重叠像素少于 100 时不视为重复，IoU 大于 0.95 才跳过。该模块不写 `MapStitcher` 状态。

### `core/mapping/frame_pipeline.py`
职责：承接 `MapStitcher.add_frame()` 的建图帧处理流程。
关键导出：`add_frame_to_stitcher`。
对外依赖：OpenCV、NumPy、`core.mapping.frame_preparation`。
注意事项：该模块仍接收 `MapStitcher` 实例并写入其状态，因为 keyframe/F2F 配准、低质量跳过、落图和统计更新属于同一帧生命周期。这样可以让 facade 变薄，同时保留旧 `MapStitcher.add_frame()` 调用面。

### `utils/event_icon_probe.py`
职责：不接入导航主循环，只用于验证“原始小地图截图 + 事件图标模板”能否识别出事件候选。
关键导出：`CaptureGeometry`、`parse_args()`、`load_config()`、`build_capture_geometry()`、`probe_frame()`、`main()`。
对外依赖：`core.platform.SquareScreenCapture`。
注意事项：事件识别必须使用 raw minimap frame，不使用 `HSVRecognizer.extract_combined()` 之后的定位特征图；脚本需要和游戏同权限运行，非管理员权限可能抓到黑帧。`--template` 和 `--image` 均可重复传入；静态图片模式用于验证用户提供截图是否能被当前模板资产识别。默认仍可跑整块模板诊断；加 `--portal-feature-detector` 时改用运行时 portal 蓝色本体特征算法，打印 mask/density 分数和蓝色像素范围，用于区分“背景模板不鲁棒”和“本体特征不可分”的问题；加 `--portal-shape-color-detector` 时改用探针专用形状+颜色联合算法，同时保存蓝色 core mask、白/灰 outer-ring mask、combined shape mask 和 accepted/rejected 候选裁剪，用于确认误报是否来自“只有蓝色相似但外环/轮廓不完整”。

### `gui/dialogs/event_manager_dialog.py`
职责：事件系统的非模态管理窗口，展示完整事件选配、事件参数、识别任务状态和 hook 实例配置，并发出保存、测试传送门、刷新传送门状态信号。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`、`gui.dialogs.event_manager.hooks.EventHookPanel`。
注意事项：窗口使用 `Qt.Tool` 且 `WA_DeleteOnClose=False`，避免手动传送门测试期间主窗口进入游戏输入模式后，事件面板跟随父窗口层级被隐藏或关闭后无法再次打开。导航页每次打开事件管理时会确保窗口存在、刷新上下文并显式 `show/raise/activate`。Hooks 页只编辑配置，不注册 handler；真实注册由 `gui/modes/navigation/hooks/registration.py` 根据当前事件配置完成。

### `utils/portal_screen_probe.py`
职责：不接入导航主循环，只用于验证主游戏画面里传送门实体是否能被视觉识别。
关键导出：`main()`。
对外依赖：`core.platform.SquareScreenCapture`、`core.events.window_finder`、`core.events.types.portal.main_view_confirmer`。
注意事项：该探针默认枚举 `UnrealWindow` / `Torchlight` 游戏窗口并抓整块窗口画面；也支持 `--rect` 或 `--full-screen`。探针现在复用 portal 事件包的 main-view confirmer，避免探针算法和运行时算法漂移。

### `core/events/*`
职责：事件系统核心层。`EventCoordinator` 是导航模式唯一事件入口；`EventRegistry` 只注册完整事件包；`EventMemory` 管理事件实例生命周期；`EventRunner` 调用具体事件 handler。
关键导出：`FrameRegistration`、`EventTick`、`EventDetection`、`EventObservation`、`EventTask`、`EventAction`、`EventCoordinator`、`EventRegistry`、`EventSystemConfig`。
对外依赖：标准库；视觉工具依赖 OpenCV/NumPy。
注意事项：事件 handler 不直接操作鼠标键盘，只返回 `EventAction`；TUI/配置层只能看到 `EventDefinition` 级完整事件，例如 `portal`。`EventCoordinator.observe()` 只做检测、事件定位、memory 合并、任务表/overlay 状态更新；`EventCoordinator.run_task(task_id, tick)` 只推进被统一导航调度器选中的事件任务。旧 UI 层事件允许集合兼容入口已删除，避免重新引入 UI 层事件仲裁。`EventPositionStabilizer` 默认仍会按同一帧隔离聚类，但传送门在 detector conversion 层先用 `minimap_nms_radius` 抑制同一图标的局部重复 hit，再用 `localization_cluster_radius/dedupe_radius` 合并多帧投影抖动；如果实测存在真正相邻双门被合并，应在事件面板把这些半径调小。事件执行抢占规则已迁移到 `NavigationTaskScheduler`，事件本身作为动态必经点参与 required/exit 的统一调度。
`EventPositionStabilizer` 当前是同名 facade package：`runtime.py` 保留类和旧私有 wrapper，`projection.py` 只负责 local->global 投影，`clusters.py` 负责聚类/同帧隔离/过期清理，`observations.py` 负责稳定 gate 和 `EventObservation` 构造，`models.py` 负责 sample/cluster 数据结构。旧 import `from core.events.position_stabilizer import EventPositionStabilizer` 仍可用。
`EventMemory` 当前是 facade package：`merge_observations()` 委托 `memory/merge.py`，任务查找和冷却委托 `memory/lookup.py`，传送会话/失败重试/附近任务抑制委托 `memory/completion.py`，距离和日志节流委托 `memory/utils.py`。旧 `_find_*`、`_completed_cooldown_info()`、`_distance()`、`_int_pos()` 仍保留 wrapper。
`core.events.debug` 当前是同名 package：`writer.py` 保留 event log session 和文件写入副作用，`topics.py` 负责 per-topic log 分流，`descriptions.py` 负责 action/task 描述，`formatting.py` 负责统一字段格式化。旧 import `from core.events.debug import event_log, start_event_log_session, describe_action, describe_task` 仍可用；日志路径仍写到项目根目录 `logs/`，不是 `core/logs/`。
`EventCoordinator.reset_event_type(event_type, now_ms)` 是事件管理 UI 的运行时重置入口；它清理同类型 active handler、memory tasks、position clusters、last detections/observations 和 selected task，不改 `event_config.json`，用于同一地图反复识别/执行某类事件。

### `core/events/hooks/__init__.py`
职责：事件生命周期 hook package 入口，向外导出 hook 常量、`EventHookContext`、`EventHookRegistry` 和 handler 类型。
关键导出：`EVENT_HOOK_VISIBLE_TARGET`、`EVENT_HOOK_COMPLETED`、`EventHookContext`、`EventHookHandler`、`EventHookRegistry`。
对外依赖：`core.events.hooks.models`、`core.events.hooks.registry`。
注意事项：这是 core 内的扩展点入口，不依赖 GUI、具体事件包或输入执行器。默认没有注册 handler 时完全 no-op。
### `core/events/hooks/models.py`
职责：定义当前已落地的两个 hook 名称、展示标签和统一 payload。
关键导出：`EVENT_HOOK_VISIBLE_TARGET="event_visible_target"`、`EVENT_HOOK_COMPLETED="event_completed"`、`EVENT_HOOK_NAMES`、`EVENT_HOOK_LABELS`、`EventHookContext`。
对外依赖：无内部业务模块依赖。
注意事项：`EventHookContext` 携带 hook 名、导航任务 ID、事件任务 ID、事件类型、事件全局坐标、玩家全局坐标、时间戳、reason 和 metadata。payload 只描述事实，不携带控制决策返回值。
### `core/events/hooks/registry.py`
职责：同步派发事件 hook handler，并隔离 handler 异常，避免 hook 破坏导航主循环。
关键导出：`EventHookHandler`、`EventHookRegistry`。
对外依赖：`core.events.debug.event_log`、`core.events.hooks.models.EventHookContext`。
注意事项：`register()` 返回注销函数；`emit()` 返回本次匹配到的 handler 数量。handler 抛异常时只写 `event hook handler failed` 日志，不向上传播，不执行任何默认输入动作。
### `EventHookRegistry.register(self, hook_name: str, handler: EventHookHandler) -> Callable[[], None]`
行为：注册一个同步 hook handler，并返回可调用的注销函数。
算法：1. 把 hook 名转为非空字符串，空名抛 `ValueError`。2. 校验 handler 可调用，不可调用时抛 `TypeError`。3. 追加到 `_handlers[hook_name]` 列表，保留注册顺序。4. 返回闭包，调用时委托 `unregister(hook_name, handler)`。
副作用：修改 `EventHookRegistry._handlers`。
失败行为：hook 名为空或 handler 不可调用时立即抛异常；不写日志。
调用关系：called by 外部组合根、GUI adapter 或后续自定义模块；当前 core 默认不注册 handler。
### `EventHookRegistry.emit(self, context: EventHookContext) -> int`
行为：按 `context.hook_name` 查找所有 handler 并同步调用，返回匹配到的 handler 数量。
算法：1. 调用 `handlers(context.hook_name)` 取快照，避免派发时注册表变化影响本轮迭代。2. 按注册顺序调用每个 handler。3. 捕获 handler 抛出的 `Exception`，写入 `event hook handler failed` 日志，继续派发剩余 handler。4. 返回本轮 handler 数量。
副作用：可能触发外部 handler；handler 异常时写事件日志。
失败行为：handler 异常被吞掉并记录，不向导航/事件主流程传播。
调用关系：called by `core.navigation_tasks.event_task_runner._emit_event_hook()`。
### `core/events/hooks/instances/key_press.py`
职责：定义可配置的按键 hook 实例，当前行为是触发时按一次自定义按键。
关键导出：`KEY_PRESS_HOOK_TYPE`、`DEFAULT_KEY_PRESS_HOOK_KEY`、`KeyPressHookSettings`、`KeyPressHookInstance`、`key_press_settings_from_dict()`、`key_press_settings_to_dict()`、`normalized_key()`。
对外依赖：`core.events.debug.event_log`、`core.events.hooks.models`。
注意事项：该实例不直接 import 或创建 `MotionController`，而是接收 `press_key(key, reason)` 回调，因此 core hook 实例仍不依赖 GUI 或平台输入实现。`KeyPressHookInstance.__call__()` 会检查实例启用状态、当前 hook 是否在实例 `triggers` 中、`context.event_type` 是否在实例 `event_types` 中、按键是否非空，然后调用注入的按键回调并写 `key hook pressed` 日志。`event_types` 为空表示未绑定任何事件，不会触发。
### `KeyPressHookInstance.__call__(self, context: EventHookContext) -> None`
行为：在匹配触发点上执行一次按键 hook。
算法：1. 若实例未启用或 `context.hook_name` 不在实例 triggers 中，直接返回。2. 若实例未绑定事件类型，或 `context.event_type` 不在实例 `event_types` 中，直接返回。3. 规范化 key，空 key 写 `key hook skipped` 日志并返回。4. 构造 reason `hook:<instance_id>:<hook_name>:<event_type>`。5. 调用注入的 `press_key(key, reason)`。6. 写 `key hook pressed` 事件日志。
副作用：通过注入回调触发一次按键；写事件日志。
失败行为：空 key 降级为跳过；回调异常由外层 `EventHookRegistry.emit()` 捕获并写 `event hook handler failed`。
调用关系：called by `EventHookRegistry.emit()` after `NavigationHookRuntime` registers the instance to selected triggers。
### `core/events/types/portal/*`
职责：传送门完整事件包。对外暴露 `PortalEventDefinition`，内部拆分小地图 detector、主画面 confirmer 和 handler。
关键导出：`PortalEventDefinition`。
对外依赖：`core.events.detectors.template_matcher`、`core.events.types.portal.minimap_feature_matcher`、`core.events.types.portal.minimap_shape_color`、`core.events.types.portal.main_view_confirmer`。
注意事项：小地图 detector 的识别算法由 `PortalEventConfig.detector_mode` 选择：`template` 只走旧灰度/边缘整块模板；`feature` 只走蓝色本体特征；`feature_then_template` 先走蓝色本体特征、无命中再回退整块模板；`shape_color` 走形状+颜色联合匹配，当前默认使用它压低蓝色相似物误识别。旧配置只含 `feature_detector_enabled` 且没有 `detector_mode` 时仍会兼容映射为旧 feature/template 行为。`PortalMinimapDetector` 现在只保留模板缓存、feature signature 和日志节流状态，mode 选择/命中调用在 `minimap_detection/modes.py`，no-hit/rejected/best-hit 日志在 `minimap_detection/diagnostics.py`，hit 颜色过滤、`minimap_nms_radius` 局部重复合并和 `EventDetection` metadata 构造在 `minimap_detection/conversion.py`。`minimap_feature_matcher/` 当前是同名算法 package：models/masks/templates/response/pipeline 分别承接 DTO、HSV 蓝色 mask、模板准备、响应图峰值提取和主匹配/合并流程。shape+color 同时要求蓝色核心、白/灰外环、组合轮廓、边缘和 HSV 颜色一致，适合压住“蓝色相似但不是传送门”的误报。命中后仍必须通过 `minimap_hit_filter.portal_color_check()`，避免白色墙体、圆形地形细节被识别成传送门。2026-06-04 日志审计发现最近运行仍使用 `feature_then_template` 内存配置，而当前 `map_data/A/event_config.json` 已保存为 `shape_color`；同一轮日志中重复 portal task 的稳定坐标相距约 70-85px，旧 `localization_cluster_radius=56`、`dedupe_radius=32` 无法合并，已改为默认 96 并暴露到事件参数面板。当前传送门主流程是靠近后点击映射传送门点、短暂等待、再按 `D`；即使配置残留 `interaction="click"`，`PortalEventHandler` 也会强制按键交互并记录日志，不再要求主画面蓝紫实体确认。按键/点击后 handler 等待位置变化或小地图周边环境变化才判定传送完成，避免固定等待导致误完成；完成动作会携带入口和出口坐标，runner 将出口附近的传送门任务也标记 completed，防止双门来回触发。`PortalEventHandler` 当前是 `handler/` package：`runtime.py` 保留 handler 状态和 public API，movement/interaction/completion/diagnostics helper 分别承接状态机阶段。

## 5. 函数索引与算法实现
### `memory.merge.merge_event_observations(memory, observations: Iterable[EventObservation], config, now_ms: int) -> None`
行为：把稳定后的 EventObservation 合并进 EventMemory 的任务表，处理 disabled、cooldown、dedupe、创建和确认帧。
算法：
1. 为本帧创建 `touched_task_ids`，防止同一帧多个 observation 复用同一个刚更新 task。
2. 对每个 observation 读取 event-specific config；若事件 disabled，节流记录 `observation skipped disabled` 并跳过。
3. 调用 `memory._completed_cooldown_info()` 检查 type cooldown 和位置 cooldown；命中时节流记录 `observation skipped cooldown` 并跳过。
4. 调用 `memory._find_matching_task()` 在 dedupe 半径内查找同类型、非 completed/ignored、且本帧未被触碰的 task。
5. 命中已有 task 时调用 `task.mark_seen(observation)`，更新位置、confidence、metadata 和 seen_count；必要时记录 `task seen`。
6. 未命中时创建 `EventTask(state=OBSERVED)`，分配 `memory._new_id()`，写入 priority、confidence、metadata，并追加到 `memory._tasks`。
7. 读取 `memory_confirm_frames`；seen_count 达标时 `task.mark_pending()`，并在状态变化时记录 `task confirmed pending`。
8. 仍处于 OBSERVED 时记录 `task waiting confirm`。
副作用：写入 `memory._tasks`、`memory._next_id`、task 状态和 event log。
失败行为：observation.global_pos 为空会在创建新 task 时触发索引错误；上游 `EventPositionStabilizer` 应只产出稳定全局坐标。
调用关系：called by `EventMemory.merge_observations()`；indirectly called by `EventCoordinator.observe()`。

### `memory.lookup.completed_cooldown_info(tasks: list[EventTask], observation: EventObservation, event_config: dict, now_ms: int, dedupe_radius: float) -> dict | None`
行为：判断 observation 是否应被已完成/忽略任务的冷却策略跳过。
算法：
1. 读取 `cooldown_ms` 和 `type_cooldown_ms`；observation 没有 global_pos 时直接返回 None。
2. 遍历同类型 task；completed task 使用 `completed_at_ms`，ignored task 缺失 completed_at 时使用 `last_seen_ms`。
3. 若 `type_cooldown_ms > 0` 且 elapsed 未超过，返回 `cooldown_kind="type"` 和剩余时间。
4. 若位置 cooldown 未启用或 elapsed 已超过 `cooldown_ms`，跳过该 task。
5. 读取 `cooldown_radius`，计算 task.global_pos 到 observation.global_pos 的距离。
6. 距离在半径内时返回 `cooldown_kind="position"`、距离、半径和剩余时间。
7. 所有任务都不命中时返回 None。
副作用：无。
失败行为：坐标不可索引时会在距离计算中抛错；上游应保证 EventTask/Observation 坐标契约。
调用关系：called by `EventMemory._completed_cooldown_info()` and `memory.merge.merge_event_observations()`。

### `memory.completion.complete_teleport_session(memory, entry_task: EventTask, exit_pos: tuple[int, int] | None, now_ms: int, config, exit_task_id: str | None = None, exit_player_pos: tuple[int, int] | None = None) -> tuple[EventTask, EventTask | None]`
行为：完成一次传送会话，把入口传送门和出口附近任务一起标记 completed，避免双门来回触发。
算法：
1. 读取 entry task 对应 event config，并生成 `teleport:{entry_id}:{now_ms}` session id。
2. 优先用显式 `exit_task_id` 找 exit task；没有则按 `exit_pos` 和 `exit_complete_radius/dedupe_radius` 查找同类型最近任务。
3. 标准化 `exit_player_pos` 和 `exit_pos`，并把 session id、role=entry、exit player pos 写入 entry metadata。
4. 标记 entry task completed。
5. 若有 normalized exit pos 但未找到 exit task，创建 synthetic exit task，confidence=1.0，metadata 标记 synthetic 和 complete reason。
6. 若有 exit task，更新 last_seen/global_pos/session metadata/role=exit/complete reason，并标记 completed。
7. 对 entry 和 exit 各调用 `memory.suppress_nearby_pending()`，把附近 active tasks 标记 ignored。
8. 记录 `teleport session completed`，返回 entry 和 exit task。
副作用：写入 `memory._tasks`、entry/exit metadata、状态和日志。
失败行为：config 缺少 event() 时按空配置降级；exit_pos 缺失且找不到 exit task 时只完成 entry。
调用关系：called by `EventMemory.complete_teleport_session()`；indirectly called by `EventRunner.update()` when handler returns COMPLETE with `completion_kind="teleport"`。

### `memory.completion.mark_failed(memory, task: EventTask, now_ms: int, config) -> None`
行为：应用 event handler FAIL 结果，按 retry limit 决定重试或忽略。
算法：
1. 调用 `task.mark_failed(now_ms)`，写入 failed_at_ms。
2. 从 event config 读取 `retry_limit`。
3. 若 `task.attempts >= retry_limit`，把 last_seen/completed_at 设为 now，调用 `task.mark_ignored()`，记录 `task failed ignored`。
4. 否则把 task.state 设回 PENDING，记录 `task failed retry`。
副作用：写入 task 状态、时间戳和 event log。
失败行为：config 缺少 event() 时 retry_limit 视为 0，失败会直接 ignored。
调用关系：called by `EventMemory.mark_failed()`；indirectly called by `EventRunner.update()` when handler returns FAIL。

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

### `minimap_shape_color.masks.portal_blue_mask(image: np.ndarray, *, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95) -> np.ndarray`
行为：从 raw minimap 或模板图中提取传送门蓝/青核心像素，输出 0/255 二值 mask。
算法：
1. 将灰度输入转 BGR，彩色输入取前三通道。
2. BGR 转 HSV。
3. 按 hue 区间、饱和度下限和亮度下限构造蓝/青核心 mask，支持 hue 区间跨 0。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常，调用方负责过滤。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()` and `minimap_shape_color.templates.prepare_shape_color_template()`。

### `minimap_shape_color.masks.portal_outer_mask(image: np.ndarray, *, sat_max: int = 115, val_min: int = 105, blue_mask: np.ndarray | None = None) -> np.ndarray`
行为：提取传送门图标白/灰外环像素，用于把“只有蓝色相似”的假候选排除。
算法：
1. 将输入转 HSV。
2. 选取低饱和、高亮度像素作为白/灰外环候选。
3. 如果传入 `blue_mask`，从外环候选中排除蓝色核心像素。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()` and `minimap_shape_color.templates.prepare_shape_color_template()`。

### `minimap_shape_color.pipeline.match_portal_shape_color(frame: np.ndarray, templates: list[TemplateSpec], scales: list[float], *, top_k: int, params: PortalShapeColorParams | None = None, collect_threshold: float | None = None) -> tuple[list[PortalShapeColorHit], PortalShapeColorDebug]`
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
调用关系：called by `PortalMinimapDetector._detect_shape_color_hits()` and `utils/event_icon_probe.py`。

### `minimap_shape_color.scoring.evaluate_shape_color_candidate(frame: np.ndarray, frame_blue: np.ndarray, frame_outer: np.ndarray, frame_shape: np.ndarray, frame_edges: np.ndarray, prepared: PreparedShapeColorTemplate, top_left: tuple[int, int], response_score: float, params: PortalShapeColorParams) -> PortalShapeColorHit`
行为：对单个 response peak 做精评分，并给出 accepted/reject_reasons。
算法：
1. 按 prepared template 尺寸从 frame blue/outer/shape/edge mask 和原始 frame 中裁剪候选窗口。
2. 分别用 `f1_score()` 计算 blue、outer、combined shape 和 edge 的 F1-like 分数。
3. 用 `patch_color_score()` 在 shape mask 内计算 HSV 平均距离，并转换成 0-1 颜色相似度。
4. 用 `blue*0.31 + outer*0.25 + shape*0.25 + edge*0.11 + color*0.08` 计算 base score。
5. 若 outer、edge、color 同时超过 signature 阈值，则计算 signature score，并用 `max(base_score, signature_score)` 作为最终分。
6. 依次追加 reject reasons：`score`、`blue_shape`、`outer_shape`、`combined_shape`、`blue_pixels_low`、`blue_pixels_high`、`outer_pixels_low`。
7. 返回 `PortalShapeColorHit`，保留各分项、像素计数、模板信息和 accepted 标记。
副作用：无。
失败行为：候选窗口尺寸不匹配时分数会降为 0；调用方继续保留 rejected 候选供 debug。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()`。

### `minimap_shape_color.pipeline.merge_shape_color_hits(hits: list[PortalShapeColorHit], top_k: int, center_radius: float = 12.0) -> list[PortalShapeColorHit]`
行为：把多个模板/尺度产生的传送门候选按中心距离去重。
算法：
1. 按 `(accepted, score)` 降序遍历候选，保证通过门禁的候选不会被同位置高分 rejected 候选挤掉。
2. 对每个候选，计算其中心与已保留候选中心的距离。
3. 距离小于动态半径时视为同一图标，只保留先进入的候选。
4. 保留数量达到 `top_k` 后停止。
副作用：无。
失败行为：空输入返回空列表。
调用关系：called by `match_portal_shape_color()` and probe summary flow。

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
9. 对候选按 `max_candidates` 截断前，逐个调用 `portal_color_check()` 做最终蓝色比例过滤。
10. 通过 `minimap_nms_radius` 检查 accepted hit 与已输出 detection 的小地图局部中心距离；近距离重复 hit 被跳过，避免同一图标因不同模板/尺度进入两个定位簇。
11. 为每个 accepted hit 输出 local-only `EventDetection`，metadata 记录 detector source、template、mask/density/shape score/blue pixel 等诊断字段。
12. 节流记录 `portal minimap hits`，包含 mode、source 和最佳候选各类分数。
副作用：更新 detector 当前 config、feature template cache 和事件日志。
失败行为：未命中返回空列表；不会直接创建全局事件坐标。

### `MotionController._calculate_target_screen_position(self, player_global_pos: tuple, target_global_pos: tuple) -> tuple[int, int] | None`
行为：把地图全局方向映射到人物屏幕中心附近的真实点击点。
算法：
1. 调用 `calculate_movement_click()`，传入玩家/目标地图坐标、屏幕中心、移动比例和 min/max 半径。
2. helper 计算 map delta、map distance、raw radius、clamped radius、direction 和 screen_pos。
3. 将 helper 返回的 `click_info` 写入 `self.last_click_info`。
4. 返回 helper 的 `screen_pos`；zero delta 时为 `None`。
副作用：更新 `self.last_click_info`。
失败行为：目标距离为 0 时不返回点击点。
调用关系：called by `MotionController.move_to_map_target()`；间接 called by `NavigationModeWidget.navigation_loop()`。

### `calculate_movement_click(*, player_global_pos: tuple, target_global_pos: tuple, game_screen_center: tuple, movement_scale_factor: float, movement_min_click_radius: int, movement_max_click_radius: int) -> ClickMappingResult`
行为：纯计算普通移动点击点和诊断字段。
算法：
1. 计算 `delta_map = target_global_pos - player_global_pos`。
2. 用 `math.hypot` 得到地图距离；若距离接近 0，返回 `screen_pos=None` 和 zero-distance click_info。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[movement_min_click_radius, movement_max_click_radius]`。
5. 将地图方向归一化为单位向量。
6. 屏幕点击点等于 `game_screen_center + direction * screen_radius`，四舍五入为整数。
7. 返回 `ClickMappingResult(screen_pos, click_info)`。
副作用：无。
失败行为：目标距离为 0 时返回 `screen_pos=None`。
调用关系：called by `MotionController._calculate_target_screen_position()`。

### `calculate_mapped_target_click(*, player_global_pos: tuple, target_global_pos: tuple, game_screen_center: tuple, movement_scale_factor: float, movement_precision_click_max_radius: int, reason: str) -> ClickMappingResult`
行为：纯计算近目标/事件点强制点击位置，不应用普通移动最小半径。
算法：
1. 计算玩家到目标的地图 delta 和距离。
2. 距离大于 0 时归一化方向；距离接近 0 时方向为 `(0, 0)`。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[0, movement_precision_click_max_radius]`。
5. 投影到 `game_screen_center + direction * screen_radius`。
6. 返回包含 `mapped_target_click=True`、`precision_radius_cap` 和 `reason` 的 click_info。
副作用：无。
失败行为：目标与玩家重合时返回屏幕中心，不抛异常。
调用关系：called by `MotionController._calculate_mapped_target_screen_position()`。

### `MotionController._apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None)`
行为：防止自动导航点击落入游戏底部 UI 区域。
算法：
1. 从 `InputDriver.screen_height` 或 `pydirectinput.size()` 获取屏幕高度。
2. 调用 `apply_bottom_click_guard()`，传入 screen_pos、game_screen_center、screen_height、禁点高度和 margin。
3. 返回 helper 计算后的点击点和 `bottom_guard` 诊断信息。
副作用：无直接鼠标副作用；调用方把结果写入 `last_click_info`。
失败行为：无法获取屏幕高度时保持原点并记录 `reason=no_screen_height`。
调用关系：called by `MotionController._execute_click()`。

### `apply_bottom_click_guard(*, screen_pos: tuple[int, int], game_screen_center: tuple | None, screen_height: int | None, bottom_click_guard_pixels: int, bottom_click_guard_margin: int) -> tuple[tuple[int, int], dict]`
行为：纯计算底部 UI 禁点投影。
算法：
1. 若 `bottom_click_guard_pixels <= 0` 或未校准 `game_screen_center`，直接返回原点击点。
2. 若没有 `screen_height`，保持原点并记录 `reason=no_screen_height`。
3. 计算禁点区顶部 `forbidden_top = screen_height - bottom_click_guard_pixels`，安全线 `safe_y = forbidden_top - bottom_click_guard_margin`。
4. 若目标 `y <= safe_y`，不调整。
5. 若目标不在人物中心下方，不调整。
6. 沿 `game_screen_center -> screen_pos` 线段按比例缩短到 `safe_y`。
7. 返回调整后的点击点和 guard 诊断信息。
副作用：无。
失败行为：无法获取屏幕高度时保持原点。
调用关系：called by `MotionController._apply_bottom_click_guard()`。

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
调用关系：called by `NavigationRuntimeFrameLoop._execute_navigation_intent()` when consuming a `PRESS_KEY` intent.

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

### `toggle_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> bool`
行为：导航页 owned dialog 的切换判定；已显示且激活时通知调用方隐藏，否则显示并前置。
算法：
1. `dialog is None` 时直接返回 `False`，调用方不需要隐藏。
2. 若 `dialog.isVisible()` 且 `dialog.isActiveWindow()` 同时为真，返回 `True`，保持旧“重复点击当前弹窗按钮则隐藏”的语义。
3. 其他情况调用 `show_owned_dialog(dialog, owner)`，负责显示、恢复最小化和前置。
4. 返回 `False`，表示调用方不应再 hide。
副作用：通常会间接显示和激活 Qt dialog。
失败行为：空 dialog 静默降级；真实 Qt 显示/激活失败由 Qt 平台层处理。
调用关系：called by `NavigationModeWidget._toggle_owned_dialog()`。

### `show_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> None`
行为：显示导航页持有的 child dialog，并尽量放到主窗口附近、恢复最小化、前置和激活。
算法：
1. `dialog is None` 时直接返回。
2. 调用 `_restore_unminimized()`；若 dialog 当前最小化，移除 `Qt.WindowMinimized` 状态。
3. 若传入 `owner` 且 dialog 尚未可见，读取 `owner.frameGeometry()`，把 dialog 移动到 owner 左上角偏移 `(80, 80)` 的位置。
4. 调用 `dialog.show()`。
5. 再次调用 `_restore_unminimized()`，覆盖部分平台 show 后仍保留 minimized state 的情况。
6. 顺序调用 `raise_()`、`activateWindow()`、`QApplication.setActiveWindow(dialog)`。
副作用：修改 Qt dialog 的位置、窗口状态、可见性和 active window。
失败行为：空 dialog 静默降级；不同 Qt 平台对 raise/activate 的实际表现可能不同，但调用顺序保持旧实现。
调用关系：called by `toggle_owned_dialog()` and `NavigationModeWidget._show_owned_dialog()`。

### `capture_navigation_localization_tick(*, build_capture_geometry, screen_capture, nav_config, nav_core, tracker, previous_player_local_pos) -> NavigationFrameTick | None`
行为：执行导航循环开头的截图与定位输入段。
算法：
1. 校验 `nav_config` 存在且至少有 `monitor_logical_center` 或 `monitor_region`。
2. 调用 `build_capture_geometry()` 获取 `capture_rect` 和默认玩家局部坐标；无有效截图几何时返回 `None`。
3. 调用 `screen_capture.capture(left, top, width, height)` 抓取小地图帧；抓屏失败返回 `None`。
4. 调用 `resolve_player_local_position()`：区域截图模式从 player mask/tracker 得到局部坐标，失败回退上一帧或截图中心；中心点截图模式使用默认局部坐标。
5. 调用 `nav_core.localize(frame, player_pos=player_pos)` 获取 `(global_x, global_y, confidence)`。
6. 用 `NavigationLocalizationResult.from_core_result()` 包装定位结果。
7. 返回 `NavigationFrameTick(capture_rect, default_player_pos, frame, player_pos, localization)`。
副作用：读取屏幕截图；调用 `nav_core.localize()` 会更新定位核心内部状态。helper 本身不写 QWidget 字段。
失败行为：缺少导航配置、截图几何无效或抓屏失败时返回 `None`；定位异常向上传播，保持原导航循环行为。
调用关系：called by `NavigationRuntimeFrameLoop.run()` before event observation。

### `handle_relocalization_navigation_intent(intent, *, request_global_relocalization, log_event, show_relocalizing) -> bool`
行为：消费带 `metadata.force_relocalize` 的导航 intent，并阻止本帧继续执行移动/点击输入。
算法：
1. 读取 `intent.metadata.get("force_relocalize")`；若为假，返回 `False`，不触发任何回调。
2. 从 `intent.metadata["relocalize_reason"]` 读取重定位原因；缺失时使用旧默认 `"coordinate_recovery"`。
3. 调用 `request_global_relocalization(reason)`，通常是 `NavigationCore.request_global_relocalization()`，让下一帧定位走全图匹配。
4. 调用 `log_event("navigation forced global relocalization", reason=reason, score=..., player=..., task=...)`，保留旧事件日志字段。
5. 调用 `show_relocalizing()`，由调用方绑定到状态栏展示函数。
6. 返回 `True`，通知 `NavigationRuntimeFrameLoop.run()` 立即 `return`，避免执行 `_execute_navigation_intent()`。
副作用：触发全局重定位请求；写入事件运行日志；追加状态栏重新定位提示。
失败行为：intent 缺少 `metadata` 属性时抛出属性错误，开发期暴露；回调异常向上传播，保持旧内联行为。
调用关系：called by `consume_navigation_intent()` before input execution。

### `consume_navigation_intent(intent, *, now_ms: int, request_global_relocalization, log_event, show_relocalizing, execute_intent, is_manual_event_test_active, stop_manual_event_test, stop_navigation_tasks, disable_game_input_mode, reset_auto_navigation_button, show_arrived, show_failed) -> NavigationIntentConsumptionResult`
行为：按固定顺序消费一个导航 intent，并把“本帧是否被重定位短路”和“是否进入导航终态”返回给 widget。
算法：
1. 调用 `handle_relocalization_navigation_intent()`；若返回 `True`，返回 `NavigationIntentConsumptionResult(skip_remaining_frame=True)`，不执行输入、手动测试停止或终态处理。
2. 调用 `execute_intent(intent, now_ms)`，由调用方绑定到 `NavigationRuntimeFrameLoop._execute_navigation_intent()`，真实输入仍留在 input adapter。
3. 若 `intent.metadata["terminal"]` 为真且 `is_manual_event_test_active()` 为真，调用 `stop_manual_event_test(intent.message)`。
4. 调用 `handle_terminal_navigation_intent()` 处理 ARRIVED/FAILED，内部按旧顺序停止任务、关闭游戏输入模式、复位自动导航按钮和展示终态文案。
5. 返回 `NavigationIntentConsumptionResult(terminal_navigation=<terminal helper result>)`。
副作用：可能触发全局重定位请求、真实输入、手动事件测试停止、任务停止、窗口输入模式恢复、按钮复位和状态栏文案更新；具体副作用均由回调承担。
失败行为：intent 缺少 `metadata/type/message` 等字段时抛出属性错误，保持开发期显式失败；回调异常向上传播。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after route overlay render。

### `update_debug_overlay(overlay, *, capture_rect: dict | None, nav_config, scale: tuple[float, float]) -> bool`
行为：把导航截图几何转换为屏幕 debug 幕布窗口的显示矩形，并执行隐藏或显示。
算法：
1. 若 `overlay is None`，直接返回 `False`。
2. 调用 `screen_overlay_geometry(capture_rect, nav_config, scale)`，把物理像素截图矩形转换为 Qt 逻辑像素矩形，并读取可选 anchor。
3. 若返回 rect 为空，调用 `overlay.hide_overlay()` 并返回 `False`。
4. 若 rect 有效，把 `left/top/width/height/anchor` 传给 `overlay.set_rect_and_show()`。
5. 返回 `True`，表示幕布已按有效几何显示。
副作用：可能调用 `OverlayWindow.hide_overlay()` 或 `OverlayWindow.set_rect_and_show()`，改变全屏透明幕布可见性和绘制矩形。
失败行为：空 overlay 静默降级；capture geometry 无效时隐藏幕布。
调用关系：called by `NavigationModeWidget._update_overlay_display()`。

### `load_navigation_map_settings(map_folder_path: str) -> NavigationMapSettings`
行为：读取当前地图目录的导航配置，并保留配置文件是否真实存在的标记。
算法：
1. 调用 `load_nav_config(map_folder_path)`。
2. 接收 `(nav_config, config_exists)`。
3. 构造不可变 `NavigationMapSettings(nav_config=nav_config, config_exists=config_exists)`。
4. 返回该 settings 对象，让 `NavigationModeWidget.load_map()` 决定是否弹缺配置 warning。
副作用：读取 `map_folder_path/config.json`；缺文件时由底层 config store 返回默认配置。
失败行为：JSON 解析或 IO 异常按 `load_nav_config()` 原行为传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 弹错误框。
调用关系：called by `prepare_navigation_map_load_session()`。

### `create_navigation_core(map_folder_path: str) -> NavigationCore`
行为：创建地图目录对应的导航定位核心实例。
算法：
1. 调用 `NavigationCore(map_folder_path)`。
2. 返回创建完成的 core 实例。
副作用：触发 `NavigationCore` 构造期地图包加载和定位状态初始化。
失败行为：地图包缺失或构造异常向上传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 弹错误框。
调用关系：called by `prepare_navigation_map_load_session()`。

### `prepare_navigation_map_load_session(*, source_file: str, map_name: str, scale: tuple[float, float]) -> NavigationMapLoadSession`
行为：准备 `NavigationModeWidget.load_map()` 前半段所需的纯地图会话数据。
算法：
1. 调用 `resolve_map_folder(source_file, map_name)` 得到 `map_data/<map_name>` 绝对路径。
2. 调用 `load_navigation_map_settings(map_folder_path)` 读取 `NavConfig` 和 `config_exists`。
3. 调用 `create_navigation_core(map_folder_path)` 构造 `NavigationCore`，加载地图包和定位状态。
4. 调用 `initial_capture_center_for_config(settings.nav_config, scale)`，把逻辑屏幕中心换算为物理坐标，并生成参数弹窗回填用 `physical_center`。
5. 返回不可变 `NavigationMapLoadSession(map_name, map_folder_path, nav_config, config_exists, nav_core, capture_center_physical, physical_center)`。
副作用：读取地图配置 JSON；构造 `NavigationCore` 时读取地图包。
失败行为：map folder/config/map_data 构造异常向上传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 统一显示加载失败。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()` before config application and UI refresh。

### `NavigationMapLoadLifecycle.load_selected_map(self, map_name: str | None) -> bool`
行为：执行用户选择地图后的完整加载生命周期，并保持旧加载失败提示。
算法：
1. 若 `map_name` 为空或等于缺地图占位文案，返回 `False`，保持旧的静默返回。
2. 调用 `prepare_navigation_map_load_session(source_file, map_name, scale)`，其中 scale 来自 targets 注入的 `compute_scale()`。
3. 调用 `apply_loaded_session(session)` 执行加载后半段固定顺序。
4. 成功时返回 `True`。
5. 捕获加载链路异常，调用 `show_map_load_failed(parent, error)`，返回 `False`。
副作用：读取地图配置/地图包；成功时会触发 `apply_loaded_session()` 的 UI、route、event、render 副作用；失败时弹 Qt critical。
失败行为：异常被本方法捕获并转换为旧中文错误弹窗，不继续传播。
调用关系：called by `NavigationModeWidget.load_map()`。

### `NavigationMapLoadLifecycle.apply_loaded_session(self, session: NavigationMapLoadSession) -> None`
行为：接收准备好的 map session，按旧顺序执行地图加载后半段。
算法：
1. 调用 `set_map_session(session)`，由 widget 写入 `map_folder_path/nav_config/nav_core/_capture_center_physical`。
2. 若 `session.config_exists` 为假，调用 `warn_map_config_missing(parent)`。
3. 调用 `apply_config_to_runtime()`，复用 `NavigationConfigLifecycle.apply_to_runtime()`。
4. 若 `session.capture_center_physical` 存在，打印旧调试行。
5. 调用 `params_dialog.set_config_to_ui(session.nav_config)` 回填参数 UI；物理中心只用于 capture cache，不再作为 dialog 兼容参数传入。
6. 依次调用 `load_route_data()`、`initialize_event_system()`、`render_map()`、`show_last_exit_position()`、`render_route_overlay()`。
7. 调用 `apply_map_loaded_ui()` 启用开始/提示按钮、route panel，并写入加载成功状态栏。
副作用：写入 widget runtime 状态、可能弹缺配置 warning、应用 nav config 到 core/path/motion/task controller、读取 route/event 配置、重建 QGraphicsScene、绘制退出点/路线/事件 overlay、启用按钮和状态栏。
失败行为：本方法不捕获异常；由 `load_selected_map()` 统一转换为加载失败弹窗。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()`；smoke 通过回调顺序验证。

### `populate_map_combo(combo, map_names: Iterable[str], missing_label: str) -> None`
行为：把地图名称列表写入地图选择下拉框，缺地图时写入占位提示。
算法：
1. 调用 `combo.clear()` 清空旧项。
2. 将 `map_names` 转成列表，避免迭代器被重复消费。
3. 若列表非空，调用 `combo.addItems(names)`。
4. 若列表为空，调用 `combo.addItem(missing_label)`。
副作用：重写 QComboBox 条目。
失败行为：控件缺少相关 Qt 方法时抛出属性错误，由调用方开发期暴露。
调用关系：called by `NavigationModeWidget.refresh_map_list()`。

### `apply_map_loaded_ui(*, start_button, hint_button, route_panel, status_label, map_name: str) -> None`
行为：地图加载成功后启用导航入口按钮和 route panel，并写入成功状态栏文案。
算法：
1. 调用 `start_button.setEnabled(True)`。
2. 调用 `hint_button.setEnabled(True)`。
3. 调用 `route_panel.set_buttons_enabled(True)`，继续复用 route panel controller 的批量启用规则。
4. 调用 `status_label.setText()`，写入旧中文文案 `地图 '<map_name>' 加载成功。请设置初始位置或直接开始导航。`。
副作用：写入按钮 enabled 状态和状态栏文本。
失败行为：控件缺少相关方法时抛出属性错误，由调用方开发期暴露。
调用关系：called by `NavigationMapLoadLifecycle.apply_loaded_session()` after map rendering and overlay refresh.

### `warn_map_config_missing(parent) -> None`
行为：当前地图缺少 `config.json` 时提示用户将使用默认参数继续加载。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "未找到 config.json，将使用默认参数。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方继续后续地图加载。
调用关系：called by `NavigationMapLoadLifecycle.apply_loaded_session()` when `NavigationMapSettings.config_exists` is false.

### `show_map_load_failed(parent, error: Exception) -> None`
行为：地图加载链路抛出异常时显示旧中文失败提示，并附带异常文本。
算法：
1. 将 `error` 转为字符串。
2. 调用 `QMessageBox.critical(parent, "错误", f"加载地图失败：{str(error)}")`。
副作用：弹出 Qt 错误框。
失败行为：Qt 弹窗异常向上传播；不吞掉或重试加载异常。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()` exception branch.

### `warn_overlay_map_config_incomplete(parent) -> None`
行为：debug overlay 勾选时发现缺少监控中心/区域配置，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "地图配置不完整，无法显示幕布。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；按钮 checked 复位仍由调用方负责。
调用关系：called by `NavigationModeWidget._toggle_overlay_display()` guard branch.

### `initial_capture_center_for_config(nav_config: NavConfig | None, scale: tuple[float, float]) -> tuple[tuple[int, int] | None, tuple[int, int]]`
行为：根据导航配置中的逻辑中心和 DPR scale，生成加载地图时要缓存的物理截图中心，以及参数弹窗回填用的物理中心。
算法：
1. 若 `nav_config` 为空或没有 `monitor_logical_center`，返回 `(None, (0, 0))`，保持旧 UI 回填缺省值。
2. 调用 `physical_center_from_logical(nav_config.monitor_logical_center, scale)`。
3. 将计算出的物理中心作为第一个返回值，用于 `_capture_center_physical` 缓存。
4. 将同一个物理中心作为第二个返回值；若计算结果为空则回退 `(0, 0)`。
副作用：无。
失败行为：逻辑中心格式不合法时由坐标解包/整数转换抛出异常，沿用旧直接计算行为。
调用关系：called by `prepare_navigation_map_load_session()`。

### `NavigationConfigLifecycle.apply_to_runtime(self) -> bool`
行为：把当前 `NavConfig` 应用到导航 runtime 对象。
算法：
1. 通过 targets 读取 `nav_core` 和 `nav_config`；缺任一对象时返回 `False`。
2. 调用 `reset_capture_center()` 清空物理截图中心缓存。
3. 调用 `apply_navigation_config_to_core()`，把 recognizer、draw_scale、导航障碍层、PathFinder、MotionController 和 NavigationTaskController 参数按旧规则写入 runtime。
4. 返回底层 apply helper 的 bool 结果。
副作用：可能修改 `nav_config.draw_scale`、`nav_core`、PathFinder、MotionController、NavigationTaskController 和 `_capture_center_physical`。
失败行为：底层 apply 过程异常向上传播，保持旧 wrapper 行为。
调用关系：called by `NavigationModeWidget._apply_config_to_core()` and `NavigationConfigLifecycle.save_current_map_config()`。

### `NavigationConfigLifecycle.configure_task_controller(self) -> None`
行为：只同步 NavigationTaskController/coordinate diagnostics/event approach 相关配置。
算法：
1. 从 targets 读取当前 `nav_config` 和 `nav_core`。
2. 调用 `configure_navigation_task_controller()` 写入 movement、coordinate diagnostics 和 event approach 参数。
副作用：修改 `NavigationTaskController` 及其 movement/diagnostics/event approach 子对象；可能写 `nav_core` 视觉诊断参数。
失败行为：底层配置异常向上传播。
调用关系：called by `NavigationModeWidget._configure_navigation_task_controller()` and `NavigationConfigLifecycle.handle_parameter_changed()`。

### `NavigationConfigLifecycle.handle_parameter_changed(self, new_config) -> bool`
行为：处理参数对话框实时变化，并保持“不保存文件但应用部分 runtime 参数”的旧行为。
算法：
1. 若当前没有 `nav_core`，返回 `False`，避免未加载地图时应用参数。
2. 调用 `set_nav_config(new_config)` 更新 widget 持有的 `nav_config`。
3. 调用 `reset_capture_center()` 清空物理中心缓存。
4. 调用 `update_overlay_display()` 刷新 debug overlay。
5. 调用 `apply_motion_controller_config()` 立即同步运动控制参数。
6. 调用 `configure_task_controller()` 同步导航任务控制器参数。
7. 调用 `refresh_game_view_rect_from_known_position()` 刷新橙色真实视野框。
8. 调用 `mark_nav_params_dirty(nav_status_label)` 显示“有未保存的修改”。
9. 返回 `True`。
副作用：更新内存配置、MotionController、NavigationTaskController、overlay、视野框和参数弹窗状态 label；不写 config 文件。
失败行为：回调或底层配置异常向上传播，与旧 `_on_parameter_changed()` 一致。
调用关系：called by `NavigationModeWidget._on_parameter_changed()`。

### `NavigationConfigLifecycle.save_current_map_config(self) -> bool`
行为：保存当前地图的导航配置，并按旧顺序应用配置和刷新 UI。
算法：
1. 读取 `map_folder_path`；为空时调用 `warn_nav_config_missing_map(parent)` 并返回 `False`。
2. 调用 `save_nav_config(map_folder_path, nav_config)` 合并写入地图 `config.json`。
3. 调用 `apply_to_runtime()` 应用完整配置。
4. 调用 `update_overlay_display()` 刷新 debug overlay。
5. 调用 `refresh_game_view_rect_from_known_position()` 刷新橙色真实视野框。
6. 调用 `show_nav_config_saved(parent, nav_status_label)` 展示保存成功。
7. 返回 `True`。
副作用：写 `map_data/<map>/config.json`；修改 runtime 配置、overlay/视野框和状态 label；可能弹成功信息框。
失败行为：写文件或应用异常被捕获，调用 `show_nav_config_save_failed(parent, nav_status_label, error)` 并返回 `False`。
调用关系：called by `NavigationModeWidget._save_nav_config()`。

### `NavigationConfigLifecycle.save_default_config(self) -> bool`
行为：把当前导航参数保存为项目默认配置。
算法：
1. 读取当前 `nav_config`；为空时调用 `warn_default_nav_config_missing(parent)` 并返回 `False`。
2. 调用 `save_default_nav_config(source_file, nav_config)` 合并写入项目根 `config.json`。
3. 调用 `show_default_nav_config_saved(parent, nav_status_label, path)` 展示成功路径。
4. 返回 `True`。
副作用：写项目根默认 `config.json`；更新状态 label 并弹成功信息框。
失败行为：写文件异常被捕获，调用 `show_default_nav_config_save_failed(parent, nav_status_label, error)` 并返回 `False`。
调用关系：called by `NavigationModeWidget._save_nav_default_config()`。

### `show_nav_config_saved(parent, status_label) -> None`
行为：当前地图导航参数保存并应用成功后，更新参数弹窗状态标签并提示用户。
算法：
1. 调用 `status_label.setText("参数已保存并应用")`。
2. 调用 `QMessageBox.information(parent, "成功", "参数已保存并成功应用到当前导航。")`。
副作用：写入 Qt label 文本并弹出信息框。
失败行为：Qt 弹窗异常向上传播；调用点位于保存成功分支末尾。
调用关系：called by `NavigationModeWidget._save_nav_config()` after save/apply/overlay refresh.

### `show_nav_config_save_failed(parent, status_label, error: Exception) -> None`
行为：当前地图导航参数保存失败后，显示错误并标记参数状态。
算法：
1. 调用 `QMessageBox.critical(parent, "保存失败", f"无法写入 config.json: {error}")`。
2. 调用 `status_label.setText("保存失败!")`。
副作用：弹出错误框并写入 Qt label 文本。
失败行为：Qt 弹窗异常向上传播；不吞掉原 error，只把 error 文本展示给用户。
调用关系：called by `NavigationModeWidget._save_nav_config()` exception branch.

### `warn_event_config_missing(parent) -> None`
行为：事件配置保存前发现尚未加载地图或没有事件配置时，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "未加载地图或事件配置。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后直接返回。
调用关系：called by `NavigationEventLifecycle.save_event_config()` guard branch.

### `show_event_config_saved(parent) -> None`
行为：事件配置写入成功后提示用户保存完成。
算法：
1. 调用 `QMessageBox.information(parent, "事件管理", "事件配置已保存。")`。
副作用：弹出 Qt 信息框。
失败行为：Qt 弹窗异常向上传播；调用点在 `_refresh_event_dialog()` 之后。
调用关系：called by `NavigationEventLifecycle.save_event_config()` success branch.

### `show_event_config_save_failed(parent) -> None`
行为：事件配置写入失败后提示用户 `event_config.json` 保存失败。
算法：
1. 调用 `QMessageBox.critical(parent, "事件管理", "保存 event_config.json 失败。")`。
副作用：弹出 Qt 错误框。
失败行为：Qt 弹窗异常向上传播；不重试保存。
调用关系：called by `NavigationEventLifecycle.save_event_config()` failure branch.

### `warn_event_system_missing(parent) -> None`
行为：事件系统尚未初始化时，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "请先加载地图并初始化事件系统。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方负责 reset 按钮或直接返回。
调用关系：called by `NavigationEventLifecycle.reset_portal_event_state()` and `NavigationEventLifecycle.run_portal_manual_test()`.

### `show_portal_event_state_reset(status_label, removed: int) -> None`
行为：传送门事件状态刷新后，把清理任务数写入状态栏。
算法：
1. 按旧模板格式化 `removed`：`传送门状态已刷新，清理 {removed} 个任务；可重新识别测试`。
2. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationEventLifecycle.reset_portal_event_state()` after reset/overlay/dialog refresh.

### `warn_portal_manual_test_missing_screen_center(parent) -> None`
行为：启动传送门手动测试前发现未校准屏幕中心时，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "请先校准屏幕中心。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先 reset 手动测试按钮。
调用关系：called by `NavigationEventLifecycle.run_portal_manual_test()` guard branch.

### `show_portal_manual_test_started(status_label) -> None`
行为：传送门手动测试正式启动后写入状态栏提示。
算法：
1. 调用 `status_label.setText("传送门测试已启动：使用正式事件流程执行")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget._set_portal_manual_test_active(True)`.

### `show_portal_manual_test_stopped(status_label) -> None`
行为：传送门手动测试停止后写入状态栏提示。
算法：
1. 调用 `status_label.setText("传送门测试已停止")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget._set_portal_manual_test_active(False)`.

### `warn_auto_navigation_unavailable(parent, message: str) -> None`
行为：自动导航启动 guard 未通过时，用调用方传入的旧原因文案提示用户。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", message)`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先复位自动导航按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` guard branch.

### `warn_auto_navigation_invalid_route(parent) -> None`
行为：路线数据无法启动 `NavigationTaskController` 时提示用户。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "路线数据无效，无法启动自动导航")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先复位自动导航按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` invalid-route branch.

### `show_auto_navigation_started(status_label) -> None`
行为：自动导航成功进入运行态后写入状态栏提示。
算法：
1. 调用 `status_label.setText("自动导航已启动，等待稳定定位")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` success branch.

### `show_auto_navigation_stopped(status_label) -> None`
行为：自动导航停止后写入状态栏提示。
算法：
1. 调用 `status_label.setText("自动导航已停止")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle._stop_auto_navigation()` stop branch.

### `warn_navigation_missing_screen_center(parent) -> None`
行为：开始导航前发现尚未校准屏幕中心时弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "请先点击'校准屏幕中心'进行设置！")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后复位开始按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` guard branch.

### `warn_navigation_map_config_incomplete(parent) -> None`
行为：开始导航前发现监控中心或监控大小缺失时弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "地图配置不完整，缺少监控中心或大小！")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后复位开始按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` guard branch.

### `show_navigation_started(status_label) -> None`
行为：导航 timer 启动后写入状态栏开始提示。
算法：
1. 调用 `status_label.setText("导航已开始...")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` after `nav_timer.start()`.

### `show_navigation_paused(status_label) -> None`
行为：导航 runtime 停止后写入状态栏暂停提示。
算法：
1. 调用 `status_label.setText("导航暂停")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle.stop_runtime()`.

### `show_route_command_status(status_label, status_text: str | None) -> None`
行为：把 route editor/panel controller 产出的命令状态文案写入状态栏。
算法：
1. 若 `status_text` 为空，直接返回，避免覆盖当前状态。
2. 调用 `status_label.setText(status_text)`。
副作用：可能写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRouteLifecycle._apply_route_command_result()` and `NavigationMapClickLifecycle.handle_map_click()`.

### `warn_route_save_failed(parent) -> None`
行为：路线保存失败后弹出旧中文 warning。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "保存路线失败")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方不更新 route overlay。
调用关系：called by `NavigationRouteLifecycle.save_route()` failure branch.

### `NavigationRouteLifecycle.load_route_data(self) -> dict | None`
行为：加载当前地图 route 数据，并同步给导航任务控制器。
算法：
1. 读取 `get_map_folder_path()`；若为空，调用 `_sync_route_data(None)` 清空内存 route 和任务路线，返回 `None`。
2. 调用 `RouteEditor.load_route_data(map_folder_path, force_reload=True)` 从 `RouteManager` 缓存/route.json 读取路线。
3. 调用 `_sync_route_data(route_data)` 写回 `NavigationModeWidget.route_data` 并加载 main route 到 `NavigationTaskController`。
4. 返回加载得到的 route_data。
副作用：写回导航页 route_data；调用 `NavigationTaskController.load_route()`。
失败行为：`RouteManager.load_route()` 异常向上传播，保持旧行为。
调用关系：called by `NavigationModeWidget.load_route_data()` and map load lifecycle.

### `NavigationRouteLifecycle.save_route(self) -> None`
行为：保存当前 route 并在成功后同步 route runtime 状态。
算法：
1. 调用 `RoutePanelController.save_route(map_folder_path)`，controller 负责委托 `RouteEditor.save_route()`。
2. 若 `result.saved is None`，说明未加载地图，直接返回。
3. 若 `result.saved` 为假，调用 `warn_route_save_failed(parent)`，不刷新 overlay。
4. 保存成功时调用 `_apply_route_command_result(result)`。
副作用：可能写入 route.json；可能写 route_data、task controller、overlay、状态栏；失败时弹 warning。
失败行为：保存异常由 `RoutePanelController/RouteEditor` 传播；保存返回失败时只弹 warning。
调用关系：called by `NavigationModeWidget.save_route()`; calls `RoutePanelController.save_route()` and `_apply_route_command_result()`.

### `NavigationRouteLifecycle.undo_guide_point(self) -> None` / `undo_required_point(self) -> None` / `clear_route(self) -> None`
行为：执行 route 撤销/清空命令，并统一同步结果。
算法：
1. 调用对应的 `RoutePanelController` 方法，得到 `RouteCommandResult`。
2. 调用 `_apply_route_command_result(result)`。
3. `_apply_route_command_result()` 若 route_data 为空则直接返回；否则同步 route_data、加载 main route、重绘 overlay，并写入状态栏文案。
副作用：可能修改 route.json；写回 route_data；调用 `NavigationTaskController.load_route()`；重绘 route overlay；写状态栏。
失败行为：未加载地图时返回空 result，不抛异常；底层 route manager 异常向上传播。
调用关系：called by `NavigationModeWidget.undo_guide_point()`、`undo_required_point()`、`clear_route()`.

### `warn_move_target_requires_localization(parent) -> None`
行为：用户点击移动目标但当前尚未完成定位时弹出旧中文 warning。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "请先完成定位后再点击移动目标。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方不调用 `MotionController`。
调用关系：called by `NavigationMapClickLifecycle.handle_map_click()` before manual move target.

### `show_move_target_set(status_label, pos) -> None`
行为：手动移动目标设置成功后，把 scene 坐标写入状态栏。
算法：
1. 调用 `pos.x()` 和 `pos.y()`。
2. 按旧格式保留 1 位小数：`移动目标: (<x>, <y>)`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：pos 缺少 `x/y()` 或 status label 缺少 `setText()` 时抛出异常，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.handle_map_click()` after `MotionController.move_to_map_target()`.

### `show_initial_hint_set(status_label, global_x: float, global_y: float) -> None`
行为：初始位置提示写入 `NavigationCore` 并刷新 marker 后，把全局坐标写入状态栏。
算法：
1. 将 `global_x/global_y` 转为 `int`，保持旧显示精度。
2. 格式化 `初始位置提示已设置：(<x>, <y>)。`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.set_initial_hint()`.

### `show_hint_mode_status(status_label, active: bool) -> None`
行为：hint mode 开启/取消时写入状态栏提示。
算法：
1. 若 `active` 为真，写入 `请在地图上点击您当前的大致位置...`。
2. 否则写入 `取消设置初始位置`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.toggle_hint_mode()`.

### `show_screen_center_calibrated(parent, screen_center) -> None`
行为：屏幕中心校准保存完成后弹出旧中文完成提示。
算法：
1. 调用 `QMessageBox.information(parent, "校准完成", f"屏幕中心已校准为：{screen_center}")`。
副作用：弹出 Qt 信息框。
失败行为：Qt 弹窗异常向上传播；调用点位于 `_save_nav_config()` 之后、selector close 之前，保持旧时机。
调用关系：called by `NavigationScreenCalibrationLifecycle.handle_screen_center_click()`.

### `NavigationScreenCalibrationLifecycle.start_screen_center_calibration(self) -> bool`
行为：启动屏幕中心校准选择器，并把 selector 引用同步回导航页兼容字段。
算法：
1. 调用 targets 注入的 `ScreenCenterCalibrationController.start(self.handle_screen_center_click)`。
2. controller 内部若已有可见 selector，则返回 `False` 并避免重复创建；否则创建 `CenterPointSelector`、连接 `point_selected`、全屏显示。
3. 无论是否新建 selector，都调用 `set_center_selector(controller.selector)`，保持旧 `NavigationModeWidget.center_selector` 字段可读。
4. 返回 controller 的启动结果。
副作用：可能创建并全屏显示 Qt selector；写回导航页 `center_selector` 兼容字段。
失败行为：selector 创建或 signal 连接异常向上传播。
调用关系：called by `NavigationModeWidget._calibrate_screen_center()`; calls `ScreenCenterCalibrationController.start()`.

### `NavigationScreenCalibrationLifecycle.handle_screen_center_click(self, x: int | float, y: int | float) -> tuple[int, int] | None`
行为：处理校准点击后的完整副作用链，保持旧“写配置 -> 刷 UI -> 保存 -> 完成提示 -> 关闭 selector”顺序。
算法：
1. 读取当前 `NavConfig`；若缺失，关闭 selector 并返回 `None`。
2. 调用 controller 的 `logical_to_physical(x, y)`，按当前 primary screen DPR 把逻辑坐标转换为物理像素。
3. 将转换结果写入 `nav_config.game_screen_center`。
4. 调用 `params_dialog.set_config_to_ui(nav_config)` 回填只读屏幕中心显示。
5. 调用 `update_overlay_display()`，让绿色监控框和橙色视野框按新屏幕中心刷新。
6. 调用 `save_nav_config()`，走 `NavigationConfigLifecycle.save_current_map_config()` 的当前地图配置 merge 保存和保存反馈。
7. 调用 `show_screen_center_calibrated(parent, screen_center)` 显示完成提示。
8. 调用 controller `close()` 关闭 selector。
副作用：修改内存中的 `NavConfig.game_screen_center`；写参数弹窗控件；可能写入当前地图 `config.json`；弹出 Qt 信息框；关闭 selector。
失败行为：`save_nav_config()` 自身捕获保存异常并展示失败反馈；坐标转换、UI 写入或弹窗异常向上传播。
调用关系：called by `NavigationModeWidget._handle_calibration_click()` and selector `point_selected`; calls `ScreenCenterCalibrationController.logical_to_physical()`、`NavigationConfigLifecycle.save_current_map_config()` wrapper、`show_screen_center_calibrated()`.

### `show_navigation_runtime_status(status_label, *, localized_pos, confidence: float, capture_rect: dict, intent=None, event_status: str = "") -> None`
行为：把当前帧定位、intent 和事件状态构造成基础状态栏文本并写入 label。
算法：
1. 调用 `build_navigation_status_text()`。
2. 传入 `localized_pos/confidence/capture_rect/intent/event_status`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：`capture_rect` 缺少 `width/height` 或 status label 缺少 `setText()` 时抛出异常，保持旧显式失败。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after marker/viewport refresh.

### `append_navigation_status_suffix(status_label, suffix: str | None) -> None`
行为：在当前状态栏文本末尾追加一个运行态后缀。
算法：
1. 若 `suffix` 为空，直接返回。
2. 调用 `status_label.text()` 读取当前文本。
3. 写入 `当前文本 | <suffix>`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `text/setText()` 时抛出异常，保持旧显式失败。
调用关系：called by `show_navigation_relocalizing()` and `NavigationRuntimeFrameLoop._execute_navigation_intent()`.

### `show_navigation_relocalizing(status_label) -> None`
行为：在当前帧状态栏后追加正在重新定位提示。
算法：
1. 调用 `append_navigation_status_suffix(status_label, "正在重新定位")`。
副作用：写入 Qt 状态标签文本。
失败行为：同 `append_navigation_status_suffix()`。
调用关系：called by `handle_relocalization_navigation_intent()` callback from `NavigationRuntimeFrameLoop.run()` force-relocalize branch.

### `show_navigation_arrived(status_label) -> None`
行为：导航终态为到达出口时覆盖状态栏文本。
算法：
1. 调用 `status_label.setText("已到达出口区域")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出异常。
调用关系：called by `NavigationRuntimeFrameLoop.run()` ARRIVED branch.

### `show_navigation_failed(status_label, message: str | None) -> None`
行为：导航终态失败时覆盖状态栏文本。
算法：
1. 若 `message` 非空，使用该消息。
2. 否则使用旧默认文案 `自动导航失败`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出异常。
调用关系：called by `NavigationRuntimeFrameLoop.run()` FAILED branch.

### `update_localization_view(*, scene, view, player_item, nav_core, localization, capture_rect, player_local_pos, update_monitor_rect, update_game_view_rect)`
行为：根据当前帧定位结果更新地图上的玩家 marker、绿色监控框、橙色视野框和视图中心。
算法：
1. 若 `localization.is_localized` 为真：
   1. 调用 `update_player_marker(scene, player_item, nav_core, localization.localized_pos)`，得到新的 `player_item` 和显示坐标。
   2. 调用 `update_monitor_rect(localization.localized_pos, capture_rect=capture_rect, player_local_pos=player_local_pos)`。
   3. 调用 `update_game_view_rect(localization.localized_pos)`。
   4. 调用 `view.centerOn(display_x, display_y)`。
   5. 返回新的 `player_item`。
2. 若未定位：
   1. 从 `nav_core.last_good_pos or nav_core.drawing_saved_pos` 取 fallback。
   2. fallback 存在时调用两个矩形更新回调。
   3. 调用 `hide_item(player_item)` 隐藏玩家 marker。
   4. 返回原 `player_item`。
副作用：更新 QGraphicsItem、QGraphicsView center，并通过回调更新监控框/视野框。
失败行为：scene/view/nav_core/localization 缺少必要属性时显式抛出异常；与原 widget 内联逻辑一致。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after task update and before status write.

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

### `NavigationEventLifecycle.save_event_config(self) -> bool`
行为：保存当前地图的事件配置，并保持旧成功/失败反馈。
算法：
1. 读取 `map_folder_path` 和 `event_config`。
2. 若任一为空，调用 `warn_event_config_missing(parent)` 并返回 `False`。
3. 调用 `save_event_config(map_folder_path, event_config)` 写入当前地图 `event_config.json`。
4. 成功时调用 `refresh_event_dialog()` 刷新事件窗口上下文，再调用 `show_event_config_saved(parent)`，返回 `True`。
5. 失败时调用 `show_event_config_save_failed(parent)`，返回 `False`。
副作用：可能写入 `map_data/<map>/event_config.json`、刷新事件窗口、弹出保存结果提示。
失败行为：底层返回 `False` 时只展示失败提示；缺少地图或配置时展示缺配置 warning。
调用关系：called by `NavigationModeWidget._save_event_config()` wrapper。

### `NavigationEventLifecycle.reset_portal_event_state(self, now_ms: int) -> bool`
行为：重置 portal 事件运行态和地图 overlay/dialog 展示。
算法：
1. 若没有 `event_coordinator`，调用 `warn_event_system_missing(parent)` 并返回 `False`。
2. 若 portal 手动测试 active，调用 `set_portal_manual_test_active(False, reason="portal state reset")` 先停止手动测试。
3. 调用 `event_coordinator.reset_event_type("portal", now_ms=now_ms)` 清除 portal 任务/聚类/冷却状态，得到 removed 数量。
4. 调用 `reset_event_move_runtime()` 清空 movement/event approach runtime。
5. 调用 `clear_event_overlay()`、`render_event_overlay()` 重绘事件 marker。
6. 调用 `refresh_event_dialog_tasks()` 刷新任务表。
7. 写入 `event_log("portal event state reset", removed=removed)`，并调用 `show_portal_event_state_reset(status_label, removed)`。
副作用：修改 EventCoordinator portal 状态、停止手动测试、重置 movement runtime、刷新 overlay/dialog 和状态栏。
失败行为：缺少 event coordinator 时只弹 warning 并返回 `False`。
调用关系：called by `NavigationModeWidget._reset_portal_event_state()` wrapper。

### `NavigationEventLifecycle.run_portal_manual_test(self) -> bool`
行为：响应事件管理窗口“测试传送门/停止传送门测试”命令。
算法：
1. 若 portal 手动测试已 active，调用 `set_portal_manual_test_active(False, reason="button stop")`，返回 `False`。
2. 校验 event coordinator 和 nav core；缺失时 reset 按钮、弹事件系统缺失 warning、返回 `False`。
3. 校验 `NavConfig.game_screen_center`；缺失时 reset 按钮、弹屏幕中心缺失 warning、返回 `False`。
4. 若导航 timer 未运行，则设置开始按钮 checked，调用 `toggle_navigation()` 复用普通导航启动；启动失败时 reset 按钮并返回 `False`。
5. 调用 `set_portal_manual_test_active(True, reason="button start")`，返回 `True`。
副作用：可能启动导航 timer、启用输入窗口模式和 motion control、启动 task controller、写事件日志和状态栏。
失败行为：任一前置条件失败会复位按钮并返回 `False`，不启动手动测试。
调用关系：called by `NavigationModeWidget._run_portal_manual_test()` wrapper。

### `NavigationEventLifecycle.set_portal_manual_test_active(self, active: bool, reason: str = "") -> None`
行为：实际切换 portal 手动测试运行态。
算法：
1. active 为真时，启动 `start_event_log_session("portal_manual_test")`。
2. 从 route data 读取 `routes.main`，调用 `NavigationTaskController.load_route(main_route)` 和 `start()`。
3. 调用 `ManualEventTestController.start()` 同步按钮。
4. 打开游戏输入窗口模式，并启用 `MotionController.set_control_enabled(True)`。
5. 写入 `portal manual event test started` 事件日志和状态栏。
6. active 为假时，调用 `ManualEventTestController.stop()`。
7. 调用 `reset_event_move_runtime()` 重置 movement 和 event approach runtime。
8. 若自动导航未启用，关闭游戏输入窗口模式。
9. 写入 `portal manual event test stopped` 事件日志和状态栏。
副作用：启动/停止 task controller、按钮状态、输入窗口模式、motion control、movement runtime、日志和状态栏。
失败行为：本方法不做前置校验；调用方负责在启动前检查系统是否就绪。
调用关系：called by `NavigationModeWidget._set_portal_manual_test_active()` wrapper、`NavigationEventLifecycle.run_portal_manual_test()` and `NavigationEventLifecycle.reset_portal_event_state()`。

### `NavigationMapClickLifecycle.handle_map_click(self, scene_pos) -> bool`
行为：按旧优先级解释地图点击：hint、route 编辑、手动移动目标。
算法：
1. 读取 `nav_core`；若不存在，返回 `False`。
2. 将 scene 坐标加上 `nav_core.crop_offset`，得到 int 全局地图坐标。
3. 若 hint 按钮 checked，调用 `set_initial_hint(scene_pos)`，返回 `True`。
4. 调用 `RouteEditor.handle_click(map_folder_path, global_point)`。
5. 若 route editor 处理了点击，写回 route data；若返回 next mode，则调用 `set_map_click_mode(next_mode)`；随后重绘 route overlay，写入 route 状态栏，返回 `True`。
6. 若当前没有完成定位或没有 `nav_core.current_pos`，弹移动目标需要定位 warning，返回 `False`。
7. 将全局坐标转为 float target，调用 `MotionController.move_to_map_target(current_pos, target)`。
8. 更新 target marker，并写入移动目标状态栏，返回 `True`。
副作用：可能写入 nav core hint、route data、route overlay、target marker、状态栏或触发真实移动点击。
失败行为：无 nav_core 或未定位时不执行移动；route editor 未处理且未定位时只弹 warning。
调用关系：called by `NavigationModeWidget.handle_map_click()` wrapper。

### `NavigationMapClickLifecycle.set_initial_hint(self, scene_pos) -> None`
行为：设置初始定位提示，并刷新 hint marker、监控框、真实视野框和状态栏。
算法：
1. 读取 `nav_core`；若不存在，直接返回。
2. 将 scene 坐标加上 `nav_core.crop_offset` 得到全局 float 坐标。
3. 调用 `nav_core.set_initial_hint((global_x, global_y))`。
4. 调用 `create_initial_hint_marker(scene, old_hint_item, scene_pos)` 并写回 hint item。
5. 调用 `update_monitor_rect((global_x, global_y))` 和 `update_game_view_rect((global_x, global_y))` 提供即时反馈。
6. 打印旧调试信息：scene 坐标、crop offset、全局坐标。
7. 调用 `show_initial_hint_set(status_label, global_x, global_y)`。
8. 取消 hint 按钮 checked，并调用 `toggle_hint_mode()` 恢复拖拽/光标/状态栏。
副作用：写入 `NavigationCore` 初始提示、QGraphics hint item、监控/视野框、按钮 checked、view drag/cursor 和状态栏。
失败行为：无 nav_core 时静默返回，保持旧调用前 guard 语义。
调用关系：called by `NavigationModeWidget.set_initial_hint()` wrapper and `NavigationMapClickLifecycle.handle_map_click()` hint branch。

### `NavigationMapClickLifecycle.toggle_hint_mode(self) -> None`
行为：根据 hint 按钮 checked 状态切换地图视图拖拽模式、光标和状态栏提示。
算法：
1. 读取 `hint_button.isChecked()`。
2. checked 为真时调用 `view.setDragMode(QGraphicsView.NoDrag)`，否则设为 `QGraphicsView.ScrollHandDrag`。
3. checked 为真时设置 `Qt.CrossCursor`，否则设置 `Qt.ArrowCursor`。
4. 调用 `show_hint_mode_status(status_label, is_hint_mode)`。
副作用：写入 QGraphicsView drag mode、cursor 和状态栏。
失败行为：控件缺少相关 Qt 方法时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget.toggle_hint_mode()` wrapper and `NavigationMapClickLifecycle.set_initial_hint()`。

### `NavigationRuntimeCommandLifecycle.can_start_auto_navigation(self) -> tuple[bool, str]`
行为：集中自动导航启动前置条件检查，并返回旧中文失败原因。
算法：
1. 若未加载地图或没有 `nav_core`，返回 `(False, "请先加载地图")`。
2. 从 route data 读取 `routes.main`；若没有 `exit_region`，返回 `(False, "请先设置出口")`。
3. 若 `NavConfig.game_screen_center` 为空，返回 `(False, "请先校准屏幕中心")`。
4. 若缺少监控逻辑中心/监控区域或 `monitor_size`，返回 `(False, "缺少监视窗口配置")`。
5. 全部通过时返回 `(True, "")`。
副作用：无，只读取 targets 提供的状态。
失败行为：缺少状态时返回失败原因，不抛异常。
调用关系：called by `NavigationModeWidget._can_start_auto_navigation()` wrapper and `_start_auto_navigation()`。

### `NavigationRuntimeCommandLifecycle.toggle_auto_navigation(self) -> None`
行为：根据自动导航按钮 checked 状态启动或停止自动导航。
算法：
1. 若 `auto_navigation_button.isChecked()` 为真，调用 `_start_auto_navigation()`。
2. 否则调用 `_stop_auto_navigation()`。
副作用：取决于启动/停止分支，可能启动 task controller、导航 timer、输入窗口模式或停止并重绘路线。
失败行为：启动失败时由 `_start_auto_navigation()` 完成按钮回滚和 warning。
调用关系：called by `NavigationModeWidget.toggle_auto_navigation()` wrapper。

### `NavigationRuntimeCommandLifecycle.start_navigation(self) -> bool`
行为：启动普通导航定位循环，并保持旧 guard/初始化/状态栏顺序。
算法：
1. 调用 `use_unified_navigation_loop()`，确保 timer timeout 连接到统一循环。
2. 调用 `start_event_log_session("navigation")`。
3. 检查 `NavConfig.game_screen_center`；缺失时弹缺屏幕中心 warning，复位开始按钮 checked，返回 `False`。
4. 检查监控配置；缺失时弹地图配置 warning，复位开始按钮 checked，返回 `False`。
5. 调用 `apply_config_to_runtime()`，应用最新导航配置。
6. 调用 `set_current_player_local_pos(None)` 清空上一帧局部位置。
7. 若存在 `nav_core`，调用 `request_full_map_localization("navigation_start")` 请求全图重定位。
8. 若存在 tracker，调用 `tracker.reset()`。
9. 按 `1000 // nav_config.fps` 计算 timer interval。
10. 启用 `MotionController.set_control_enabled(True)`，启动 `nav_timer.start(interval)`。
11. 将开始按钮文本改为“停止导航”，写入导航已开始状态栏，返回 `True`。
副作用：连接 timer、写日志 session、应用 config、请求重定位、重置 tracker、启动 timer/motion、写按钮和状态栏。
失败行为：guard 失败只弹 warning、复位按钮并返回 `False`；不启动 timer。
调用关系：called by `NavigationRuntimeCommandLifecycle.toggle_navigation()` and auto-navigation startup fallback。

### `NavigationRuntimeCommandLifecycle.stop_runtime(self) -> None`
行为：幂等停止导航运行副作用，用于停止按钮和主窗口关闭。
算法：
1. 停止 `nav_timer`。
2. 禁用 `MotionController` 控制。
3. 若存在 `nav_core`，复位 `is_first_frame_localized=False`。
4. 设置 `auto_navigation_enabled=False`。
5. 若手动事件测试 active，调用 `stop_portal_manual_test("navigation stopped")`。
6. 调用 `NavigationTaskController.stop()`。
7. 关闭游戏输入窗口模式。
8. 复位开始按钮和自动导航按钮 checked。
9. 重绘 route overlay，恢复开始按钮文本为“开始导航”，写入导航暂停状态栏。
副作用：停止 timer/task、禁用真实输入控制、恢复窗口模式、复位按钮和状态栏、可能停止手动事件测试。
失败行为：设计为幂等；缺少 `nav_core` 时跳过 first-frame 复位。
调用关系：called by `NavigationModeWidget.stop_runtime()` wrapper and `NavigationRuntimeCommandLifecycle.toggle_navigation()` stop branch。

### `NavigationModeWidget._run_portal_manual_test(self)`
行为：响应“测试传送门/停止传送门测试”按钮，以正式事件 pipeline 启停手动传送门执行。
算法：
1. 若 `portal_test_controller.active` 已为真，停止手动测试并返回。
2. 校验事件协调器、地图定位内核和游戏屏幕中心均已就绪；失败时恢复按钮显示并弹出警告。
3. 若导航定时器未运行，则复用 `toggle_navigation()` 启动定位循环；启动失败时停止继续执行。
4. 调用 `_set_portal_manual_test_active(True)`，开启游戏输入模式和运动控制。
5. 后续每帧由 `NavigationRuntimeFrameLoop.run()` 调用 `EventCoordinator.observe()` 识别事件，再构造 `NavigationUpdateContext(events.manual_event_only=True)` 并调用 `NavigationTaskController.update_context()` 选择并执行事件任务。
副作用：可启动导航循环、启用游戏输入、更新按钮/状态栏并记录事件日志。
失败行为：先决条件缺失时只警告并保持测试未启动。
调用关系：called by `EventManagerDialog.test_portal_requested` signal。

### `RouteEditor.handle_click(self, map_folder_path: str | None, global_point) -> RouteEditResult`
行为：按当前 map click mode 处理地图点击，更新 route 数据并返回 UI 所需的状态文本/下一模式。
算法：
1. 若未加载地图或当前 click mode 为 `NONE`，返回 `handled=False`。
2. 将全局坐标标准化为 int `(x, y)`。
3. `SET_EXIT` 调用 `RouteManager.set_exit_region(map_folder_path, (x, y), radius=28)`，随后重新读取 route data，并把内部 click mode 复位为 `NONE`。
4. `ADD_REQUIRED_POINT` 调用 `RouteManager.add_required_point()`，随后重新读取 route data，保持 click mode 便于连续添加。
5. `ADD_GUIDE_POINT` 调用 `RouteManager.add_guide_point()`，随后重新读取 route data，保持 click mode 便于连续添加。
6. 返回 `RouteEditResult`，由 `NavigationModeWidget.handle_map_click()` 决定是否刷新 overlay、按钮和状态栏。
副作用：写入 `RouteManager` 内存缓存中的 route 数据；保存到 `route.json` 仍由 `RouteEditor.save_route()`/`NavigationModeWidget.save_route()` 控制。
失败行为：未知 mode 被 `_coerce_mode()` 降级为 `NONE`；缺少地图路径时不抛异常。
调用关系：called by `NavigationModeWidget.handle_map_click()`。

### `NavigationRuntimeFrameLoop._execute_navigation_intent(self, intent, now_ms: int) -> None`
行为：消费统一导航控制器输出的动作意图，并把地图目标、屏幕点击或按键转换为真实输入。
算法：
1. 从 owner 读取 `MotionController`、`NavigationTaskController` 和启用游戏输入模式的回调，将它们连同 `intent/now_ms` 传给 `execute_navigation_intent()`。
2. `execute_navigation_intent()` 在 `NONE/WAIT` 时不执行输入。
3. `MOVE_MAP` 校验 `player_pos/subgoal`，打开游戏输入模式并启用 `MotionController`。
4. 若 intent metadata 带 `force_click_target`，调用 `MotionController.click_map_target_once()` 点击映射后的事件目标点；否则调用 `MotionController.move_to_map_target()` 做方向移动点击。
5. 真实点击成功后调用 `NavigationTaskController.record_intent_click()`，让 `MovementExecutor` 更新点击冷却和上次子目标，并返回 `click r/raw` 状态栏后缀。
6. `CLICK_SCREEN` 调用 `MotionController.click_screen_position()`；`PRESS_KEY` 调用 `MotionController.press_key()`。
7. frame loop 只负责把状态栏后缀追加到当前 `status_label`。
副作用：可能触发真实鼠标/键盘输入，更新状态栏点击诊断和 controller 点击节流状态。
失败行为：缺少必要坐标或 key 时跳过输入；底层输入异常由 `MotionController`/输入后端处理。
调用关系：called by `NavigationRuntimeFrameLoop.run()` through `consume_navigation_intent()` after `NavigationTaskController.update_context()`。

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

### `NavigationRuntimeFrameLoop.run(self) -> None`
行为：当前唯一导航循环，统一完成定位、事件观察、任务调度、overlay/status 更新和动作意图消费。
算法：
1. 调用 `capture_navigation_localization_tick()` 执行配置校验、截图几何构造、抓屏、玩家局部坐标解析和 `NavigationCore.localize()`。
2. helper 返回空时直接结束本帧；返回有效 tick 时，widget 写回 `_current_capture_rect/_current_player_local_pos`。
3. 调用 `observe_navigation_events()` 构造 `EventTick`、执行 `EventCoordinator.observe()`、刷新事件 overlay 和可见事件窗口任务表。
4. 自动导航或手动事件测试启用时，计算 lookahead 并调用 `update_navigation_task_controller()`；普通自动导航允许 required/exit/event 统一调度，手动事件测试使用 `manual_event_only=True`。
5. 调用 `update_localization_view()` 更新玩家点、绿色监视框、橙色真实可见框和视图中心。
6. 调用 `show_navigation_runtime_status()` 写入当前帧基础状态栏。
7. 若存在 intent，先重绘 route overlay，再调用 `consume_navigation_intent()` 编排重定位短路、输入执行、手动事件测试停止和 ARRIVED/FAILED 终态处理。
8. 若 consumption result 标记 `skip_remaining_frame`，本帧提前返回；若标记 `terminal_navigation`，关闭 `auto_navigation_enabled`。
9. 无 intent 但存在路线数据时重绘静态 route overlay。
副作用：更新 UI、事件任务表、controller 状态、可能执行真实输入。
失败行为：截图失败、配置缺失或定位低置信时跳过移动，等待下一帧。
调用关系：called by `NavigationModeWidget._navigation_loop_unified()` compatibility entry and QTimer after `_use_unified_navigation_loop()` rewires the timer.

### `capture_geometry.build_capture_geometry(nav_config: NavConfig | None, capture_center_physical)`
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

### `MappingCaptureSelectionController.start_region_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool`
行为：启动建图区域选择全屏 overlay，并把确认结果交给调用方回调。
算法：
1. 如果 `overlay_active=True`，直接返回 `False`，避免重复创建全屏选择器。
2. 通过 `overlay_factory()` 创建 `TransparentOverlay`，并设置 `WA_DeleteOnClose`，关闭后释放 Qt 对象。
3. 将 overlay 的 `region_selected(x, y, width, height)` 信号连接到 `_handle_region_selected()`，由 controller 先应用坐标转换和 AppContext 写回，再回调调用方。
4. 将 `destroyed` 信号连接到 `_clear_region_overlay()`，关闭或取消时复位 active flag 和 overlay 引用。
5. 记录 overlay 引用、置 `overlay_active=True`，调用 `showFullScreen()`。
副作用：创建并显示全屏 Qt overlay；写入 controller 的 overlay 状态。
失败行为：重复启动时返回 `False`；Qt overlay 创建/显示异常向上传播。
调用关系：called by `MappingWidget.select_region()`。

### `MappingCaptureSelectionController.start_center_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool`
行为：启动建图中心点选择全屏 overlay，并把确认结果交给调用方回调。
算法：
1. 如果 `center_selector_active=True`，直接返回 `False`。
2. 通过 `center_selector_factory()` 创建 `CenterPointSelector`，设置 `WA_DeleteOnClose`。
3. 将 `point_selected(x, y)` 信号连接到 `_handle_center_selected()`，由 controller 使用当前 `app_context.monitor_size` 应用中心点选择。
4. 将 `selection_cancelled` 和 `destroyed` 都连接到 `_clear_center_selector()`，取消或关闭时复位状态。
5. 记录 selector 引用、置 `center_selector_active=True`，调用 `showFullScreen()`。
副作用：创建并显示全屏 Qt selector；写入 controller 的 selector 状态。
失败行为：重复启动时返回 `False`；Qt selector 创建/显示异常向上传播。
调用关系：called by `MappingWidget.select_center_point()`。

### `MappingCaptureSelectionController.apply_region_selection(self, x: int, y: int, width: int, height: int) -> CaptureSelectionResult`
行为：把 overlay 发出的逻辑像素矩形转换为物理截图区域，并写入 `app_context.monitor_region`。
算法：
1. 调用注入的 `compute_scale()` 获取 `(sx, sy)`，当前由 `MappingWidget._compute_scale()` 基于 primary screen DPR 返回。
2. 用 `int(logical * scale)` 分别计算 `left/top/width/height` 物理像素。
3. 构造 `{"left": px_left, "top": px_top, "width": px_width, "height": px_height}`。
4. 写入 `app_context.monitor_region`，清空 `app_context.monitor_logical_center`，并清空 controller 的 `monitor_center`，表示当前切回区域截图模式。
5. 返回 `CaptureSelectionResult(mode="region", monitor_region=..., label_text=...)`，由 widget 决定 UI label、按钮和保存。
副作用：写入 `app_context.monitor_region` / `monitor_logical_center` 和 controller `monitor_center`。
失败行为：`compute_scale()` 或 AppContext 字段写入异常向上传播；不校验 width/height 是否大于 0，保持旧 overlay 路径语义。
调用关系：called by `_handle_region_selected()` and `MappingWidget.on_region_selected()` compatibility slot。

### `MappingCaptureSelectionController.apply_center_selection(self, x: int, y: int, monitor_size: int) -> CaptureSelectionResult`
行为：把中心点逻辑像素和截图尺寸写入 AppContext，并计算物理中心点供截图使用。
算法：
1. 将 `(x, y)` 和 `monitor_size` 转为 int。
2. 调用 `compute_scale()` 获取 DPR，计算 `physical_center=(int(x*sx), int(y*sy))`。
3. 写入 `app_context.monitor_logical_center=(x, y)`、`app_context.monitor_size=monitor_size`，并清空 `app_context.monitor_region`，表示切回中心点正方形截图模式。
4. 写入 controller `monitor_center=physical_center`。
5. 返回 `CaptureSelectionResult(mode="center", logical_center=..., physical_center=..., monitor_size=..., label_text=...)`。
副作用：写入 AppContext 截图配置和 controller `monitor_center`。
失败行为：`compute_scale()` 或 AppContext 字段写入异常向上传播。
调用关系：called by `_handle_center_selected()`、`update_capture_size()`、`restore_from_context()` and `MappingWidget.on_center_selected()` compatibility slot。

### `MappingCaptureSelectionController.update_capture_size(self, size: int) -> CaptureSelectionResult | None`
行为：更新中心点截图大小；如果当前不是中心点模式，只保存 size，不刷新中心点 label。
算法：
1. 将 `size` 转 int 并写入 `app_context.monitor_size`。
2. 读取 `app_context.monitor_logical_center`；为空说明当前是区域截图模式或尚未选择，返回 `None`。
3. 若存在逻辑中心点，调用 `apply_center_selection()` 重新计算物理中心和 label 结果。
副作用：总是写入 `app_context.monitor_size`；中心点模式下还会刷新 controller `monitor_center`。
失败行为：中心点 tuple 形状非法时在索引处抛出异常，保持原 `on_center_selected(*center)` 路径风险。
调用关系：called by `MappingWidget.update_capture_size()`。

### `MappingCaptureSelectionController.restore_from_context(self) -> CaptureSelectionResult | None`
行为：从已加载的 AppContext 截图配置恢复 label 和物理中心状态。
算法：
1. 若 `app_context.monitor_logical_center` 存在，调用 `apply_center_selection()`，用当前 `monitor_size` 重新计算 physical center。
2. 否则若 `app_context.monitor_region` 存在，构造 region 模式的 `CaptureSelectionResult`，并清空 controller `monitor_center`。
3. 两种配置都不存在时，清空 controller `monitor_center` 并返回 `None`。
副作用：中心点模式下会重写 AppContext 中心点/尺寸/区域字段；区域或空配置会清空 controller 物理中心。
失败行为：保存配置字段缺失必需 key 时会抛出 `KeyError`，由 `MappingWidget.load_saved_params()` 外层现有异常处理覆盖部分格式错误。
调用关系：called by `restore_saved_mapping_config()` after root config monitor fields are loaded into AppContext。

### `build_mapping_ui(owner) -> None`
行为：构建绘图页左右布局并把控件属性写回 `MappingWidget` owner。
算法：
1. 在 owner 上创建根 `QHBoxLayout`。
2. 调用 `create_mapping_control_panel(owner)` 创建左侧控制面板并以 stretch=1 加入布局。
3. 调用 `create_mapping_display_panel(owner)` 创建右侧实时截图/全局地图显示面板并以 stretch=3 加入布局。
副作用：创建 Qt layout/widgets，并写入 owner 的 UI 字段。
失败行为：owner 缺少预期 slot、`app_context` 或 stitcher/recognizer 字段时沿 Qt 构建路径抛异常。
调用关系：called by `MappingWidget.setup_ui()`。

### `create_mapping_control_panel(owner) -> QWidget`
行为：创建建图页左侧控制面板，并连接区域选择、监控控制、几何、融合、HSV、特征和统计控件。
算法：
1. 创建 panel 和垂直布局。
2. 创建监控区域组：区域选择、中心点选择、截图尺寸、颜色选择和区域状态 label，并连接 owner 的 selection/color slots。
3. 创建监控控制组：FPS、开始/停止、重置、保存和置顶控件，并连接 owner 的 runtime/save/topmost slots。
4. 创建高清绘图参数组：draw scale、canvas size、player clear radius 和 wall close kernel spinbox，默认值读取当前 `app_context.stitcher/recognizer`。
5. 创建融合、HSV 和特征参数组，保持旧默认值和 `update_*_params` 信号连接。
6. 创建统计文本框并返回 panel。
副作用：创建 Qt 控件，写入 owner 的控件字段，连接 Qt signals。
失败行为：owner slot 不存在、Qt 控件构造失败或 app_context 缺少参数字段时抛异常。
调用关系：called by `build_mapping_ui()`。

### `create_mapping_display_panel(owner) -> QWidget`
行为：创建建图页右侧实时截图和全局地图显示面板。
算法：
1. 创建 panel 和垂直布局。
2. 创建实时截图 group、`capture_label`，设置居中、最小尺寸和黑色背景。
3. 创建 `CollapsibleMapGroup`，把 `global_map_widget` 写回 owner。
4. 将 `global_map_widget.pixel_clicked` 连接到 `owner.on_map_click`，保持旧地图点击路径预览行为。
5. 返回 panel。
副作用：创建 Qt 控件，写入 owner 的显示字段，连接地图点击 signal。
失败行为：`CollapsibleMapGroup` 构造或 signal 连接异常向上传播。
调用关系：called by `build_mapping_ui()`。

### `MappingRuntimeLifecycle.toggle_monitoring(self) -> None`
行为：响应建图页开始/停止监控按钮，切换 monitoring 状态并启动或停止 capture timer。
算法：
1. 翻转 `app_context.monitoring`。
2. 若新状态为开启，先检查是否存在 `monitor_region` 或 `monitor_logical_center`。
3. 若缺少截图配置，回滚 `monitoring=False`，弹出“请先选择一个监控区域或中心点。”并返回。
4. 若截图配置存在，按 `1000 // get_fps()` 启动 `capture_timer`。
5. 将开始按钮文案改为“⏸️ 停止监控”。
6. 若新状态为关闭，调用 `stop_runtime()`。
副作用：写入 `app_context.monitoring`，启动/停止 QTimer，修改按钮文案，必要时弹出 QMessageBox。
失败行为：`get_fps()` 返回 0 会触发除零异常；当前 FPS spinbox 范围为 1-60，保持 UI 约束。
调用关系：called by `MappingWidget.toggle_monitoring()` wrapper。

### `MappingRuntimeLifecycle.stop_runtime(self) -> None`
行为：幂等停止建图 capture runtime，用于停止按钮分支和主窗口关闭。
算法：
1. 停止 `capture_timer`。
2. 写入 `app_context.monitoring=False`。
3. 将开始按钮文案恢复为“▶️ 开始监控”。
副作用：停止 QTimer、写 AppContext 运行态、修改按钮文案。
失败行为：设计为幂等；timer 未启动时 `stop()` 无额外副作用。
调用关系：called by `MappingWidget.stop_runtime()` wrapper and `MappingRuntimeLifecycle.toggle_monitoring()` stop branch。

### `project_root_from_file(file_path: str | Path) -> Path`
行为：从 GUI 内任意源文件或目录解析项目根目录。
算法：
1. 将 `file_path` 转为绝对 `Path`。
2. 若传入目录则从该目录开始，否则从文件父目录开始。
3. 从起点一路向上遍历父目录。
4. 第一个同时包含 `main.py` 和 `gui/` 的目录即为项目根目录。
5. 如果遍历结束仍未找到，抛出 `FileNotFoundError`。
副作用：读取文件系统元数据，不写文件。
失败行为：不再按固定 `parents[n]` fallback；找不到项目标记时显式失败，避免静默写错路径。
调用关系：called by `gui.composition.paths` sibling helpers, `mapping.io.config_store.project_root_from_file`, and `navigation.map.config_store.project_root_from_file`。

### `project_root_from_map_folder(map_folder_path: str | Path) -> Path`
行为：从 `map_data/<map_name>` 地图目录解析项目根目录。
算法：
1. 将 `map_folder_path` 转为绝对路径。
2. 从当前路径和所有父目录中查找名字为 `map_data` 的目录。
3. 找到后返回该 `map_data` 目录的父目录。
4. 若路径不在 `map_data` 下，回退到 `project_root_from_file()` 的标记查找。
副作用：读取路径结构，不写文件。
失败行为：路径既不在 `map_data` 下也找不到项目标记时由 `project_root_from_file()` 抛出 `FileNotFoundError`。
调用关系：called by `root_config_path_from_map_folder()` and `navigation.map.config_store.default_nav_config_path_from_map_folder()`。

### `map_data_dir_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析项目 `map_data` 目录。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "map_data"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `mapping.io.config_store.map_data_dir()` and `navigation.map.config_store.map_data_dir()`。

### `root_config_path_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析项目根 `config.json`。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "config.json"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `mapping.io.config_store.root_config_path()` and `navigation.map.config_store.default_nav_config_path_from_file()`。

### `advanced_settings_dir_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析高级参数 snapshot 目录。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "configs" / "advanced_settings"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `gui.dialogs.advanced_settings.file_io.DEFAULT_ADVANCED_SETTINGS_DIR` initialization。

### `create_core_services(*, canvas_size: int = 5000) -> CoreServices`
行为：创建 GUI 默认共享 core services。
算法：
1. 创建 `SquareScreenCapture()`。
2. 创建 `HSVRecognizer()`。
3. 创建 `MapStitcher(canvas_size=canvas_size)`，默认 `canvas_size=5000` 保持旧 AppContext 行为。
4. 创建 `PlayerTracker()`。
5. 创建 `PathFinder()`。
6. 将五个对象打包为 frozen `CoreServices` 返回。
副作用：实例化屏幕捕获、识别器、拼接器、tracker 和 pathfinder；`SquareScreenCapture` 可能初始化底层屏幕捕获 backend。
失败行为：任一 core service 构造失败会向上传播，保持启动期显式失败。
调用关系：called by `AppContext.__init__()` when no services DTO is injected。

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
1. 调用 `map_folder_for_name(file_path, map_name)`。
2. `map_folder_for_name()` 通过 `map_data_dir(file_path)` 定位项目 `map_data`，实际项目根解析委托 `gui/composition/paths.py`。
3. 拼接 `map_data/map_name`。
4. 调用 `mkdir(parents=True, exist_ok=True)` 创建目录。
副作用：可能创建 `map_data/<map_name>` 目录。
失败行为：文件系统权限或非法地图名导致 `OSError` 向上传播，保持原保存失败路径不吞异常。
调用关系：called by `MappingWidget.save_map()`。

### `save_mapping_map(file_path, map_name: str, *, stitcher, config_data: dict)`
行为：保存当前建图结果和地图级配置。
算法：
1. 调用 `ensure_map_folder(file_path, map_name)` 定位并创建 `map_data/<map_name>`。
2. 调用 `stitcher.save_map_package(str(map_folder))` 保存 `map_data.npz`。
3. 调用 `save_map_config(map_folder, config_data)` 写入 `config.json`。
4. 返回 `map_folder`，供调用方需要展示或测试路径。
副作用：创建地图目录、写入地图包和地图级配置文件。
失败行为：目录创建、地图包保存或 JSON 写入异常向上传播；当前 GUI 与旧行为一致，不在 `save_map()` 中捕获。
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

### `restore_saved_mapping_config(file_path, *, app_context, capture_selection, handle_capture_selection_result, stitcher_is_empty, targets: MappingConfigRestoreTargets) -> bool`
行为：读取根配置并按旧启动顺序恢复建图页运行态和控件。
算法：
1. 调用 `load_root_config(file_path)`；配置不存在时返回 `False`。
2. 将 `monitor_logical_center`、`monitor_size`、`monitor_region` 写入 `app_context`。
3. 调用 `capture_selection.restore_from_context()`，若返回结果则回调 `handle_capture_selection_result(result, save=False)`，恢复 label、按钮和物理中心状态。
4. 将 `monitor_size` 和 `fps` 写入 size/fps 控件。
5. 若存在 `recognizer_params`，先调用 `app_context.recognizer.set_params()`，再通过 `sync_recognizer_widgets()` 回填 feature 控件。
6. 若存在 `stitcher_params` 且 `stitcher_is_empty()` 为真，先用 `canvas_size/draw_scale/wall_close_kernel_size` 重建空画布；随后调用 `app_context.stitcher.set_params()` 并同步 merge weight 控件。
7. 为 draw scale、canvas size、player clear radius、wall close kernel 控件创建 `QSignalBlocker`，调用 `sync_geometry_widgets()` 回填几何控件，最后释放 blockers。
8. 返回 `True`。
副作用：读取项目根 `config.json`；写入 AppContext、recognizer/stitcher 参数和 Qt 控件；可能重建空 stitcher 画布。
失败行为：JSON 格式错误由 `load_root_config()` 抛出，字段缺失/控件不匹配按原路径抛出；`MappingWidget.load_saved_params()` 捕获 `json.JSONDecodeError` 和 `KeyError`。
调用关系：called by `MappingWidget.load_saved_params()`。

### `load_root_config(file_path: str | Path) -> dict | None`
行为：读取项目根目录 `config.json`，不存在时保持旧行为直接返回空。
算法：
1. 通过 `root_config_path(file_path)` 定位配置文件。
2. 若文件不存在，返回 `None`。
3. 文件存在时调用 `load_json_config()` 读取 dict。
副作用：读取项目根目录 `config.json`。
失败行为：JSON 格式错误会抛出 `json.JSONDecodeError`，由 `MappingWidget.load_saved_params()` 原有 except 处理。
调用关系：called by `restore_saved_mapping_config()`。

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
调用关系：called by `mapping.presentation.map_presenter.update_mapping_displays()` and `render_global_map_pixmap()`。

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

### `AdvancedSettingsDialog.apply_params(self)`
行为：采集高级参数并请求 owner 应用；兼容模式下仍直接写 parent recognizer/stitcher。
算法：
1. 调用 `collect_params_from_widgets(self)` 生成参数 dict。
2. 发出 `apply_params_requested(params)`，让 owner 处理运行时写入。
3. 如果 `_direct_runtime_apply_enabled` 为真，调用 `_apply_params_directly(params)` 保持旧调用方兼容。
4. 将 `self.current_params` 更新为本次参数 dict。
5. 打印应用成功日志。
副作用：发出 Qt signal；兼容 fallback 模式下可能调用 recognizer/stitcher 的 `set_params()`。
失败行为：owner slot 或 fallback `set_params()` 抛异常时向上传播，保持旧行为。
调用关系：called by `apply_btn.clicked`；indirectly consumed by `MappingWidget._apply_advanced_settings_params()`。

### `AdvancedSettingsDialog.use_external_apply_handler(self)`
行为：关闭 dialog 内部 direct runtime mutation，使参数应用只通过 command signal 交给 owner。
算法：
1. 将 `_direct_runtime_apply_enabled` 置为 `False`。
2. 后续 `apply_params()` 仍发 signal，但不再调用 `_apply_params_directly()`。
副作用：修改 dialog 内部兼容开关。
失败行为：无。
调用关系：called by `MappingWidget.open_advanced_settings()` after connecting `apply_params_requested`。

### `MappingWidget._apply_advanced_settings_params(self, params: dict, *, save: bool = True)`
行为：作为高级参数 command owner，将参数应用到共享 recognizer/stitcher，并按调用时机决定是否保存配置。
算法：
1. 调用 `self.app_context.recognizer.set_params(params)`。
2. 调用 `self.app_context.stitcher.set_params(params)`。
3. 如果 `save=True`，调用 `save_config()` 写回绘图配置。
副作用：修改运行时 recognizer/stitcher；确认对话框 OK 时保存配置。弹窗内“应用参数”通过 signal 调用本函数时传 `save=False`，保留旧实时应用不立即落盘的语义。
失败行为：核心对象 `set_params()` 抛异常时向上传播。
调用关系：called by `AdvancedSettingsDialog.apply_params_requested` with `save=False` and by `MappingWidget.open_advanced_settings()` on accepted dialog with `save=True`。

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
2. 调用 `preset_values(preset)` 取得该预设的数据字典。
3. 若无匹配数据，返回 `False`，调用方当前不使用返回值。
4. 遍历数据字典，用 widget attribute name 找到控件并调用 `setValue(value)`。
5. 返回 `True`。
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

### `build_wall_preview(image, wall_hsv_range) -> WallPreviewResult | None`
行为：根据颜色选择弹窗当前 wall HSV 范围生成右侧二值预览 mask 和 debug 统计。
算法：
1. `wall_hsv_range` 为空时返回 `None`，保持旧 `update_preview()` 未计算墙体范围时直接返回的行为。
2. 解包 `(min_hsv, max_hsv)`，将预处理后的 BGR 截图转换为 HSV。
3. 调用 `cv2.inRange(hsv, min_hsv, max_hsv)` 得到 wall mask。
4. 统计形态学处理前白色像素数、总像素数和白色比例。
5. 创建 3x3 uint8 kernel，复制一份 `mask_before_morph` 和 `mask_after_close`。
6. 调用 `cv2.morphologyEx(mask, MORPH_CLOSE, kernel)` 执行 close。
7. 统计 close 后白色像素数，并计算旧实现中的 `before_count - after_count` 差值。
8. 返回 `WallPreviewResult`，包含 preview mask、before mask、HSV 图、HSV 范围和所有 debug 统计字段。
副作用：无；不写文件、不触碰 Qt 控件。
失败行为：输入图像 shape 或 HSV 范围类型不合法时由 OpenCV/Numpy 异常向上传播。
调用关系：called by `ColorPickerDialog.update_preview()`。

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
调用关系：called by `NavigationRuntimeFrameLoop.run()` before task scheduling.

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

### `EventPositionStabilizer.update(self, detections: Iterable[EventDetection], registration: FrameRegistration | None, config, now_ms: int) -> list[EventObservation]`
行为：把 detector 输出的局部小地图候选转换为稳定全局事件 observation，是所有小地图事件共用的定位阶段。
算法：
1. 检查 `registration` 是否存在、`valid=True` 且 `frame_origin_global` 不为空；无效时节流记录 `event localization skipped` 并返回空列表。
2. 遍历每个 `EventDetection`，从 event config 读取该事件类型配置；事件 disabled 时跳过。
3. 调用 `_project()`，把 `local_minimap_pos` 按 `frame_origin_global + local_minimap_pos * draw_scale` 投影成全局浮点坐标。
4. 调用 `_merge_sample()`，按 `localization_cluster_radius` 或 `dedupe_radius` 找同类型最近 cluster；同一 `now_ms` 的 cluster 不合并，避免一帧内相近双事件被吞成一个。
5. 新 cluster 记录 `event localization cluster created`；已有/新 cluster 追加 `PositionSample`，并按 `localization_max_samples` 只保留最近样本。
6. 调用 `_stable_observation()` 计算 cluster 方差；样本数未达到 `stable_frames/localization_samples/confirm_frames` 时返回 None。
7. 方差超过 `stable_variance/localization_max_variance` 时节流记录 unstable 并返回 None。
8. 若距离上次发射未超过 `localization_emit_interval_ms`，返回 None，避免同一稳定位置过高频写入 memory。
9. 通过 gate 后更新 `last_emitted_ms`，用加权中心四舍五入为 `global_pos`，并把 sample count、variance、sources 写入 metadata。
10. 所有 detection 处理后调用 `_expire_old_clusters()`，按 `localization_cluster_ttl_ms` 清除久未出现的 cluster。
副作用：写入 `self._clusters`、`self._last_log_ms`、cluster 样本/发射时间，并写事件日志。
失败行为：无有效帧配准时不会产生 observation；`detection.local_minimap_pos` 为空时该 detection 被跳过；event config 缺省时按默认阈值降级。
调用关系：called by `EventCoordinator.observe()`；delegates to `projection.project_detection()`、`clusters.merge_sample()`、`observations.stable_observation()`、`clusters.expire_old_clusters()`。

### `position_stabilizer.projection.project_detection(detection: EventDetection, registration: FrameRegistration) -> tuple[float, float] | None`
行为：执行事件局部小地图坐标到全局地图坐标的纯投影。
算法：
1. 若 detection 没有 `local_minimap_pos` 或 registration 没有 `frame_origin_global`，返回 None。
2. 读取帧全局 origin、局部 x/y 和 `draw_scale`，draw_scale 缺省时用 1.0。
3. 返回 `(origin_x + local_x * scale, origin_y + local_y * scale)`。
副作用：无。
失败行为：坐标字段不可解包时抛出调用方数据契约错误。
调用关系：called by `EventPositionStabilizer._project()`。

### `position_stabilizer.clusters.merge_sample(clusters: list[PositionCluster], detection: EventDetection, global_pos: tuple[float, float], event_config: dict, now_ms: int, should_log) -> PositionCluster`
行为：把一次事件检测投影结果合并进同类型位置 cluster，并维护样本窗口。
算法：
1. 读取 `localization_cluster_radius`，没有则回退 `dedupe_radius`，再回退 90。
2. 调用 `find_cluster()` 在同类型 cluster 中找距离当前 global_pos 最近且未超过半径的 cluster。
3. `find_cluster()` 会跳过 `last_seen_ms == now_ms` 的 cluster，保证同一帧的多个相近图标不会被合并。
4. 找不到 cluster 时创建 `PositionCluster(event_type=...)` 并追加到 clusters，记录创建日志。
5. 构造 `PositionSample`：保存 global/local 坐标、confidence、detected_at_ms、source 和 metadata 副本。
6. 更新 `cluster.last_seen_ms = now_ms`。
7. 按 `localization_max_samples` 截断，只保留最后 N 个样本，N 最小为 3。
8. 日志节流通过时记录样本数、加权中心、方差和最大置信度。
副作用：原地修改 clusters、cluster.samples 和 cluster.last_seen_ms，并写事件日志。
失败行为：detection local 坐标不可索引会抛出异常；调用方应只传有效 `EventDetection`。
调用关系：called by `EventPositionStabilizer._merge_sample()`。

### `position_stabilizer.observations.stable_observation(cluster: PositionCluster, detection: EventDetection, event_config: dict, now_ms: int, should_log) -> EventObservation | None`
行为：把通过稳定条件的 cluster 转换为可进入 `EventMemory` 的 `EventObservation`。
算法：
1. 读取 required samples：`stable_frames` -> `localization_samples` -> `confirm_frames`，最小为 1。
2. 读取最大方差：`stable_variance` -> `localization_max_variance`，默认 1600。
3. 读取 `localization_emit_interval_ms`，默认 700ms。
4. 样本数不足时返回 None。
5. 方差超限时节流记录 unstable，包括 samples、required、variance、max_variance 和 center，然后返回 None。
6. 上次发射时间存在且未超过发射间隔时返回 None。
7. 更新 `cluster.last_emitted_ms`。
8. 计算加权中心和最新 sample，写 `event localization stable` 日志。
9. 构造 `EventObservation`：global_pos 使用中心四舍五入，local_minimap_pos 使用最新 sample，source 拼接 `+wall_registration`。
10. metadata 合并最新 sample metadata，并追加 localization sample count、variance 和去重排序后的 sources。
副作用：写入 `cluster.last_emitted_ms` 并写事件日志。
失败行为：cluster 无样本时不应被调用；否则 latest sample 访问会失败。
调用关系：called by `EventPositionStabilizer._stable_observation()`。

### `PortalEventHandler.update(self, tick, task) -> EventAction | None`
行为：推进 portal 事件状态机，但只返回通用 `EventAction`，不直接执行鼠标或键盘。
算法：
1. 记录状态变化日志。
2. 如果 `state == "wait_result"`，委托 `handler.completion.wait_result_action()` 处理 post-interact settle、teleport completion、timeout 和 forced relocalize wait。
3. 非等待完成阶段先委托 `handler.movement.approach_action()`；玩家无定位时返回 WAIT，距离大于 `arrival_radius` 时返回普通 MOVE_TO。
4. 距离小于到达半径但仍大于 `interact_radius` 时返回 MOVE_TO，并在 metadata 设置 `force_repeat_click=True`，保证近距离继续推动角色靠近传送门点。
5. 若 movement helper 未返回 action，说明已进入交互半径，委托 `handler.interaction.interaction_action()`。
6. interaction helper 先发出一次 `force_click_target=True` 的 MOVE_TO，让 GUI 通过 `MotionController.click_map_target_once()` 点击映射的 portal 点。
7. 等待 `portal_point_click_wait_ms` 后，记录交互时间、玩家位置和小地图环境签名，再返回 `PRESS_KEY("d")`。
8. 按键后状态进入 `wait_result`，后续 update 只走 completion helper。
副作用：更新 handler `state`、`last_interact_ms`、`interact_pos`、`interact_signature`、`portal_point_click_ms`、`teleport_relocalize_requested` 和日志节流字段。
失败行为：无定位时只 WAIT；handler 不直接失败，只有 wait_result 超过 `teleport_timeout_ms` 才返回 FAIL。
调用关系：called by `EventRunner.update()`；delegates to `handler.movement.approach_action()`、`handler.interaction.interaction_action()`、`handler.completion.wait_result_action()`。

### `portal.handler.movement.approach_action(handler, tick, task) -> tuple[EventAction | None, float | None]`
行为：根据玩家到 portal task 的距离决定是否还需要移动。
算法：
1. 玩家全局定位为空时节流记录 `portal waiting localization`，返回 WAIT 和 `distance=None`。
2. 计算 task.global_pos 到 tick.player_global_pos 的欧氏距离。
3. 距离大于 `arrival_radius` 时设状态为 `move_near_event`，记录 `portal move near`，返回 `EventAction.move_to(task.global_pos)`。
4. 距离在到达半径内但大于 `interact_radius` 时继续设状态为 `move_near_event`，记录 final radius 日志。
5. final radius 分支返回 MOVE_TO，并在 metadata 设置 `force_repeat_click=True`。
6. 距离已经进入交互半径时返回 `(None, distance)`，交给 interaction helper。
副作用：可能更新 handler.state，并写节流日志。
失败行为：坐标不可索引会抛出调用方数据契约错误；无定位按 WAIT 降级。
调用关系：called by `PortalEventHandler.update()`。

### `portal.handler.interaction.interaction_action(handler, tick, task, distance: float) -> EventAction`
行为：处理 portal 点点击、点击后等待和按键交互。
算法：
1. 如果 config 残留非 `key` interaction，节流记录 `portal forcing key interaction`，但仍强制按键路径。
2. 如果上次交互时间存在且还在 `post_interact_wait_ms` 内，切到 `wait_result` 并返回 cooldown WAIT。
3. 如果还没有点击过 portal map point，把状态设为 `align_on_portal`，记录 `portal_point_click_ms` 和日志。
4. 首次点击分支返回 `EventAction.move_to(task.global_pos)`，metadata 标记 `force_click_target=True` 和原因。
5. 如果 portal 点点击后等待时间未达到 `portal_point_click_wait_ms`，继续返回短 WAIT。
6. 等待完成后，把状态短暂设为 `interact`，记录 `last_interact_ms`、`interact_pos` 和小地图环境签名。
7. 状态切到 `wait_result`，记录 `portal interaction key`，返回 `EventAction.press_key("d")`。
8. 若状态已经被外部置为 `wait_result`，返回 WAIT，避免重复发按键。
副作用：更新 handler 交互时间、portal 点点击时间、交互位置、环境签名和状态，并写事件日志。
失败行为：raw minimap frame 或 player local pos 缺失时环境签名可为 None，completion helper 后续仍可用位置变化策略。
调用关系：called by `PortalEventHandler.update()`。

### `portal.handler.completion.wait_result_action(handler, tick, task) -> EventAction`
行为：处理 portal 按键后的等待完成阶段，输出 COMPLETE、FAIL 或 forced relocalize WAIT。
算法：
1. 计算从 `last_interact_ms` 到当前 tick 的 elapsed；若还没过 `post_interact_wait_ms`，返回 settle WAIT。
2. 调用 `handler._teleport_completion()`，实际委托 `completion_detector.detect_teleport_completion()`。
3. completion 命中时记录 `portal teleport completed`，调用 `completion_action()` 构造 COMPLETE。
4. completion metadata 总是包含 `entry_pos`、`entry_task_id` 和 `completion_kind="teleport"`，再合并 known-exit、position-changed 或 environment-changed 结果。
5. elapsed 超过 `teleport_timeout_ms` 时记录 timeout 并返回 FAIL。
6. 未完成且未超时，节流记录 `portal waiting teleport completion`。
7. 第一次进入该分支时设置 `teleport_relocalize_requested=True` 并记录 `portal request full-map localization`。
8. 返回 WAIT，metadata 标记 `force_relocalize=True`、`relocalize_reason="portal_wait_result"`、`relocalize_score="event"`。
副作用：可能更新 `teleport_relocalize_requested` 并写事件日志。
失败行为：completion detector 无命中且超过超时时返回 FAIL；否则持续 WAIT，不直接输入。
调用关系：called by `PortalEventHandler.update()`。

### `plan_path_with_optional_anchors(*, wall_map, pathfinder, start_pos, target_pos, explored_map=None, anchors=None, max_anchors: int = 48, max_anchor_factor: float = 1.8, max_anchor_branching: int = 4, min_progress: float = 24.0, probe_distance: float = 84.0) -> AnchorPathResult | None`
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
3. 调用 `estimate_click_radii(game_screen_center, bounds)` 执行纯半径策略。
4. 如果 helper 返回 `None`，显示中心点不在屏幕边界内并退出。
5. 写入最小/最大点击半径控件，触发配置变更信号。
副作用：更新参数面板控件和 `nav_status_label`。
调用关系：called by `nav_auto_click_radius_btn.clicked`。

### `connect_config_bindings(panel, update_value: Callable[..., None], update_text: Callable[..., None]) -> None`
行为：把导航参数控件连接到 dialog 提供的配置更新槽。
算法：
1. 遍历 `VALUE_FIELD_SPECS`，用 `resolve_widget(panel, spec)` 找到控件。
2. 从 `spec.field_path` 取得 `(sub_config_name, attr_name)`。
3. 当 `spec.writer == "checked"` 时连接 `stateChanged`，handler 设置 `to_bool=True`，保持旧 bool 转换语义。
4. 其他 value 字段连接 `valueChanged`，handler 通过 `functools.partial` 预绑定字段路径。
5. 遍历 `TEXT_FIELD_SPECS`，连接 `textChanged`，handler 预绑定字段路径并交给 dialog 的 `_update_config_text_value()`。
副作用：连接 Qt 控件信号；不修改配置对象。
失败行为：控件 attribute 缺失时由 Python 抛出 `AttributeError`，表示 dialog 构造和绑定规格不一致。
调用关系：called by `NavParametersDialog._connect_signals()`。

### `replace_config_value(config: NavConfig, sub_config_name: str | None, attr_name: str, value) -> NavConfig`
行为：按字段路径返回一个新的 `NavConfig`，保留原有不可变更新风格。
算法：
1. 如果 `sub_config_name` 为空，目标对象就是根 `NavConfig`。
2. 如果 `sub_config_name` 非空，读取 `getattr(config, sub_config_name)` 作为嵌套 dataclass。
3. 调用 `dataclasses.replace(target_obj, **{attr_name: value})` 生成更新后的目标对象。
4. 嵌套字段时再次 `dataclasses.replace(config, **{sub_config_name: new_sub_config})` 写回根配置。
5. 根字段时直接返回第 3 步生成的新 `NavConfig`。
副作用：无；不会原地修改旧配置对象。
失败行为：字段路径不存在或目标对象不是 dataclass 时抛出标准 `AttributeError` / `TypeError`。
调用关系：called by `NavParametersDialog._update_config_value()`。

### `parse_config_text_value(text: str) -> tuple[bool, Any]`
行为：解析 HSV 文本输入框里的 Python 字面量，并保留输入未完成时“不更新配置”的旧行为。
算法：
1. 调用 `ast.literal_eval(text)` 解析文本。
2. 解析成功时返回 `(True, value)`。
3. 捕获 `ValueError` 和 `SyntaxError`，返回 `(False, None)`。
副作用：无。
失败行为：无效或未完成输入不抛出，调用方跳过配置更新。
调用关系：called by `NavParametersDialog._update_config_text_value()`。

### `write_config_to_widgets(panel, config: NavConfig) -> None`
行为：把一个 `NavConfig` 快照写入已创建好的导航参数对话框控件。
算法：
1. 遍历 `TEXT_FIELD_SPECS`，用 `config_value(config, spec)` 取配置值并 `setText(str(value))`。
2. 遍历 `VALUE_FIELD_SPECS`，根据 `spec.writer` 选择 `setChecked(value)` 或 `setValue(value)`。
3. 写入只读地图信息：`draw_scale`、`monitor_region` 或 `monitor_logical_center`、`monitor_size`。
4. 如果存在 `game_screen_center`，拆分写入 X/Y 文本框；否则显示 `N/A`。
副作用：修改 Qt 控件显示值；控件信号是否阻断由调用方负责。
失败行为：控件 attribute 缺失时抛出 `AttributeError`。
调用关系：called by `NavParametersDialog.set_config_to_ui()`。

### `estimate_click_radii(center: tuple[int, int], screen_bounds: tuple[int, int, int, int]) -> ClickRadiusEstimate | None`
行为：从角色屏幕中心点和屏幕物理边界计算建议点击半径。
算法：
1. 拆分 `center` 为 `cx/cy`，拆分 `screen_bounds` 为 `left/top/right/bottom`。
2. 计算中心点到四条边的距离，并取最小值为 `safe_radius`。
3. 如果 `safe_radius <= 0`，说明中心点不在可用屏幕范围内，返回 `None`。
4. 取 `max_radius = max(180, min(900, int(safe_radius * 0.70)))`。
5. 取 `min_radius = max(120, int(max_radius * 0.55))`。
6. 返回 `ClickRadiusEstimate(min_radius, max_radius)`。
副作用：无。
失败行为：屏幕中心越界时返回 `None`，不抛异常。
调用关系：called by `NavParametersDialog._auto_estimate_click_radius()`。

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

### `NavigationTaskController.update_context(self, context: NavigationUpdateContext) -> NavigationIntent`
行为：消费当前定位、路线、规划资源和事件 memory 快照，统一输出普通路线或事件动作意图。
算法：
1. 从 `context.localization`、`context.route`、`context.planning`、`context.events` 读取 grouped 输入，避免调用方继续传一串松散 kwargs。
2. 路线对象变化时重新 `load_route()` 并保持 controller active。
3. 未 active 时返回 `NONE` intent；定位为空、置信度过低或低置信大跳变时返回 `WAIT`。
4. `observe_localization()` 维护 `trusted_pos/control_pos` 和单调 `route_progress`；若本帧是强制全局模板重定位成功帧，则硬重置 `control_pos`，不做平滑。
5. `CoordinateDiagnostics.record_localization()` 和 `record_navigation_state()` 记录 raw/trusted/control/target/route deviation/frame registration；只有 `NavigationCore` 视觉校验产生的 `visual_mismatch` 或极端 `raw_jump` 会触发强制重定位，路线偏差和近目标卡住只写诊断日志。
6. 若诊断状态机产出 relocalization request，返回 `WAIT` 且在 metadata 标记 `force_relocalize=True`，本帧不点击。
7. `_update_required_progress()` 用距离或路线进度越过判断已完成必经点，完成后清路径和 active task。
8. `NavigationTaskBuilder.build()` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中 runnable 事件合成任务列表。
9. `NavigationTaskScheduler.pick()` 选择当前任务；事件 active 时持锁，静态目标不持锁，允许新事件动态抢占。
10. 任务切换时记录 `nav task transition` 并重置共享 `MovementExecutor`，避免上一任务路径/点击冷却污染下一任务。
11. static required/exit 走 `_update_static_task()`；event 走 `_update_event_task()` 并调用 `EventCoordinator.run_task()`。
12. 返回 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY/WAIT/ARRIVED/FAILED` 之一，由 GUI 层统一执行输入。
副作用：更新定位平滑状态、已完成必经点集合、active task、共享移动执行器、坐标诊断恢复状态和事件 runner 状态。
失败行为：无路径时返回 `WAIT path unavailable`，不会生成穿墙长直线点击；事件上下文缺失时返回 `WAIT`。
调用关系：called by `NavigationRuntimeFrameLoop.run()`。

### `MovementExecutor.step(self, *, task_id: str, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context=None, soft_anchors=None, force_repeat_click: bool = False, click_cooldown_ms: int | None = None) -> MovementStep | None`
行为：为当前 required、exit 或 event 地图目标规划/复用路径，选出本帧 lookahead 子目标和是否应点击。
算法：
1. 标准化当前位置和目标坐标。
2. facade 委托 `movement.pipeline.movement_step()`，再由它调用 `executor._ensure_path()`；旧私有方法保留但实际转发到 `movement.path_maintenance.ensure_movement_path()`。
3. `ensure_movement_path()` 根据目标变化、路径为空、锚点段到达、离路偏差、fallback 过期或强制重规划标记判断是否重规划。
4. 需要规划时，`movement.path_planner.plan_movement_path()` 优先从 `RouteContext.corridor_anchors()` 获取当前位置到当前任务目标之间的前方锚点。
5. 若有前方锚点，调用 `plan_path_with_optional_anchors()` 只规划到下一个锚点；若无锚点则直接 A* 到当前任务目标。
6. 如果 A* 失败，调用 `movement.recovery.local_probe()` 生成玩家附近短距离 `fallback` probe，而不是直接点击远端目标。
7. 将当前位置投影到当前路径，沿累计距离向前插值 `lookahead_distance` 得到 `subgoal`。
8. 如果当前路径终点接近但仍未到达锚点或 planned 目标，切换到 exact path-goal click，设置 `force_click_target=True`，并把有效冷却提升到至少 650ms。
9. 若没有处于 final-goal settle 窗口，调用 `movement.recovery.is_movement_stuck()` 按路径投影进度判断卡住。
10. 卡住且恢复次数未耗尽时，调用 `movement.recovery.recovery_probe()` 朝 active anchor/fallback path goal 生成恢复子目标；恢复次数耗尽时设置 `force_replan=True`。
11. 根据 click cooldown、`force_repeat_click`、active goal pending、上次点击目标距离和离路偏差决定 `should_click`。
12. 返回包含 path、subgoal、path_kind、deviation、force_click_target 的 `MovementStep`。
副作用：更新缓存路径、路径终点、子目标、重规划时间、fallback probe index、进度窗口、恢复次数、final goal settle 状态。
失败行为：路径不可用或投影失败返回 `None`，调用方本帧不输入。
调用关系：called by `NavigationTaskController._update_static_task()` and `_update_event_task()`。

### `movement.path_maintenance.ensure_movement_path(executor, *, task_id: str, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, route_context=None, soft_anchors=None) -> None`
行为：维护 `MovementExecutor` 的缓存路径，在目标变化、路径失效、偏离路径或 fallback 过期时重规划。
算法：
1. 标准化目标坐标，并用 12px 距离阈值判断目标是否变化。
2. 如果当前路径为空、少于两个点、被 `force_replan` 标记或目标变化，则直接需要规划。
3. 如果是 `anchor_step/anchor_probe/fallback` 且已到达当前 path goal，则需要规划下一段。
4. 把当前位置投影到当前路径；投影失败或 `distance_to_path` 超过 `path_deviation_threshold` 时需要重规划。
5. fallback 路径超过 650ms 仍在使用时需要重规划，避免短探测路径长期卡住。
6. 如果刚规划过且目标未变化，260ms 内跳过，避免每帧重复 A*。
7. 调用 `executor._plan_path()` 获取路径、累计长度和 path kind，并写回 executor 的 path/path_lengths/target/path_goal/path_kind 等状态。
8. 重置 subgoal、progress、recovery、final-goal 状态，并写 `nav movement planned` 日志。
副作用：写入 executor 路径状态和导航日志。
失败行为：无异常抛出；若 planner 返回 fallback，也作为有效路径写入。
调用关系：called by `movement.pipeline.movement_step()` through `MovementExecutor._ensure_path()`。

### `movement.path_planner.plan_movement_path(executor, current_pos, target_pos, wall_map, pathfinder, explored_map, *, route_context=None, soft_anchors=None)`
行为：为 movement executor 生成 anchor-aware A*/fallback 路径。
算法：
1. 把 current/target 转为整数地图点。
2. 调用 `executor._anchors_for_path()`，优先从 `RouteContext.corridor_anchors()` 获取当前到目标之间的前方 guide anchors，否则使用 `soft_anchors`。
3. 如果 `wall_map` 和 `pathfinder` 可用，调用 `plan_path_with_optional_anchors()`，让 routing 层决定 `anchor_step/anchor_probe/planned`。
4. 若 anchor-aware 结果有 path，记录 `executor.path_anchor_points`，删除共线点，单点路径补上真实 target，并返回累计长度。
5. 若没有 anchors 且直接 A* 可用，调用 `pathfinder.find_path()` 规划当前到目标。
6. 直接 A* 成功时清空 anchor points，删除共线点，单点路径补上目标，并返回 `path_kind="planned"`。
7. 全部规划失败时清空 anchor points，调用 `executor._local_probe()` 生成两点 fallback path。
副作用：写入 `executor.path_anchor_points`。
失败行为：不会返回 `None`，最差返回 fallback 两点路径。
调用关系：called by `MovementExecutor._plan_path()`。

### `movement.recovery.is_movement_stuck(executor, current_progress: float, now_ms: int) -> bool`
行为：根据路径投影进度判断 movement 是否卡住。
算法：
1. 如果还没有进度基线，则写入当前 progress/time，返回 `False`。
2. 如果当前进度比基线至少增加 `min_progress_delta`，刷新基线并清零恢复次数，返回 `False`。
3. 如果进度不足且 `now_ms - last_progress_ms >= progress_timeout_ms`，返回 `True`。
副作用：更新 executor 的 progress baseline 和 recover attempts。
失败行为：无异常处理；入参 progress/time 由调用方保证可转数值。
调用关系：called by `movement.pipeline.movement_step()` through `MovementExecutor._is_stuck()`。

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
调用关系：called by `NavigationTaskController.update_context()`。

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
副作用：更新 `weight_layer`、`wall_layer`、`fog_layer`、`explored_map`、`canvas`。
失败行为：ROI 裁剪为空时返回 `False`；内容太相似且非 force 时跳过并增加 redundant counter。
调用关系：called by `MapStitcher._place_first_frame()` and `mapping.frame_pipeline.add_frame_to_stitcher()`；implemented by `mapping.weighted_merge.merge_frame_weighted()`。

### `MapStitcher.add_frame(self, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)`
行为：接收一帧小地图识别结果，执行 keyframe/F2F 配准、低质量过滤和落图。
算法：
1. facade 调用 `mapping.frame_pipeline.add_frame_to_stitcher(self, ...)`，并把自身作为状态拥有者传入。
2. `frame_pipeline` 增加 `stats["total_frames"]`，解析玩家在 minimap 内局部坐标。
3. 首帧时调用 `_place_first_frame()`，把 scaled save/fog masks 放到 canvas 中心，设置 keyframe/prev frame 和当前位置。
4. 非首帧优先用 keyframe mask 和当前 match mask 做 phase displacement。
5. keyframe 匹配质量超过 `keyframe_thresh` 且跳变小于 100px 或质量很高时接受 anchor。
6. anchor 接受时从 keyframe position 和 displacement 更新 `current_x/current_y`。
7. anchor 不接受时 fallback 到 previous frame；F2F 质量低或位移超过 50px 时记失败。
8. F2F 成功且当前 feature count 足够时更新 keyframe；否则只保持 previous frame 链路。
9. 匹配成功但质量低于 `draw_quality_gate` 时只更新 previous frame，不落图，避免污染全局地图。
10. 质量通过后准备 scaled save/fog masks，调用 `_merge_frame_weighted()` 写入 map layers。
11. 更新 previous mask/pos、match quality、successful/failed stats 和 match rate。
副作用：写入 `MapStitcher` 当前坐标、keyframe/prev frame、map layers 和 stats。
失败行为：当前实现通常返回 `True`，即使配准失败也会更新 stats；首帧日志含 emoji，在 GBK stdout 下需要 `PYTHONIOENCODING=utf-8` 才能直接 smoke。
调用关系：called by `gui/modes/mapping_widget.py` through shared `AppContext.stitcher`。

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
1. `HSVRecognizer.extract_combined()` 保留旧入口，内部委托 `hsv.combined.extract_combined_masks()`。
2. 先通过 `extract_walls()` 和 `extract_fog()` 得到保存用 wall/fog mask。
3. 对 wall 预处理图转灰度并用 Canny 生成 edges。
4. 若 `sat_filter_enabled`，`dynamic_color_mask()` 从原始图 HSV 饱和度生成动态彩色区域 mask；`sat_filter_radius > 0` 时只在玩家周围生效。
5. 对 dynamic mask 做一次小核膨胀，并从 wall/fog/edges 中剔除，避免彩色事件图标和玩家技能污染静态地图特征。
6. 按 `player_clear_radius` 在玩家位置或图像中心挖圆，进一步压制玩家脚下和近身特效。
7. `weighted_match_mask()` 按 `wall_weight/edge_weight` 把 `wall_mask` 和 `edges` 融合成配准用 `match_mask`。
8. 返回 `(match_mask.astype(np.uint8), wall_mask, fog_mask)`。
副作用：会原地清理本次生成的 wall/fog/edges mask，不写 recognizer 状态。
调用关系：called by `MappingWidget.capture_and_process()` and `NavigationCore.localize()`。

### `HSVRecognizer.extract_walls(self, img, is_processed=False)`
行为：提取保存/定位共用的二值 wall mask。
算法：
1. facade 委托 `hsv.masks.extract_wall_mask()`。
2. `enable_wall=False` 时返回全零 mask。
3. 非 processed 输入先走 `hsv.preprocessing.preprocess_for_wall()`。
4. `transparent_mode=True` 时，`compute_transparency_score()` 计算 `(V - S * penalty)` 与 TopHat 结构 score 的最小值，再按 `trans_wall_thresh` 二值化。
5. 透明模式下做小核 close，并用 `filter_small_components(min_area=20)` 去掉小噪点。
6. 非透明模式下转 HSV 后按 `wall_hsv_min/max` inRange，随后 close、median blur、Gaussian blur、threshold 和小连通域过滤。
副作用：无持久状态写入。
调用关系：called by `extract_combined_masks()` and color-picker/debug flows。

### `hsv.params.apply_recognizer_params(recognizer, params) -> None`
行为：把 GUI/配置层传入的 HSVRecognizer 参数字典应用到 recognizer 实例。
算法：
1. 逐项检查 `wall_hsv_min/max`、`fog_hsv_min/max`、`player_hsv_min/max` 是否存在，存在时转为 `numpy.array` 写回 recognizer。
2. 逐项应用 wall/fog、CLAHE、deepen、gamma、TopHat、sat filter 等布尔开关；缺失键保持旧值。
3. 更新 `clahe_clip` 时直接调用既有 `_clahe.setClipLimit()`；更新 `clahe_grid` 时重建 `cv2.createCLAHE()`，确保 tile grid 尺寸同步。
4. 应用 deepen、blue boost、gamma、TopHat、transparent、sat filter、player clear radius、权重和 Canny 阈值等数值参数。
5. `player_clear_radius` 强制转为非负整数；`kernel_small_size` 和 `kernel_medium_size` 存在时重建对应全 1 morphology kernel。
副作用：原地写入 `recognizer` 实例字段，并可能重建 `recognizer._clahe`、`kernel_small`、`kernel_medium`。
失败行为：未做类型校验；错误类型会在 `numpy.array`、`int()` 或 OpenCV CLAHE/kernel 后续使用处暴露。
调用关系：called by `HSVRecognizer.set_params()`，间接 called by GUI 参数面板和导航参数加载流程。

### `hsv.preprocessing.preprocess_for_wall(recognizer, img)`
行为：生成 wall mask 提取前的增强 BGR 图，服务透明墙体和普通 HSV 墙体识别。
算法：
1. 若 `gamma_enabled`，构建 0-255 查找表并通过 `cv2.LUT()` 调暗/校正输入图。
2. 对输入做 3x3 Gaussian blur，降低局部噪声对 HSV/TopHat 的影响。
3. 若 `clahe_enabled`，转 LAB，对 L 通道应用 recognizer 当前 `_clahe`，再转回 BGR；否则直接使用 blur 结果。
4. 若 `tophat_enabled`，用 `tophat_kernel_size` 的矩形结构元素对增强图做 MORPH_TOPHAT，并把高亮结构加回图像。
5. 尝试用第 40 和 99 百分位做线性拉伸；若 OpenCV/numpy 输入异常或百分位无有效跨度，保持当前图。
6. 若 `deepen_enabled`，用 `convertScaleAbs(alpha=deepen_factor, beta=-60)` 加深，再按 `blue_boost` 放大 B 通道。
7. 返回增强后的 BGR 图，不修改 recognizer 参数。
副作用：无持久状态写入。
失败行为：百分位计算异常被吞掉并降级为未拉伸图；OpenCV 颜色空间和 LUT 错误会传播。
调用关系：called by `HSVRecognizer._preprocess_for_wall()`、`HSVRecognizer.preprocess_image()`、`hsv.masks.extract_wall_mask()`、`hsv.combined.extract_combined_masks()`。

### `hsv.combined.dynamic_color_mask(recognizer, img, player_pos=None)`
行为：识别运行时彩色动态区域，用于从 wall/fog/edge 配准特征中剔除事件图标、技能光效和玩家周边颜色噪声。
算法：
1. 将原始 BGR 小地图转 HSV，并取 S 通道。
2. 用 `sat_filter_thresh` 生成高饱和度布尔 mask。
3. 若 `sat_filter_radius > 0`，创建同尺寸半径 mask：有 `player_pos` 时以玩家坐标为圆心，否则以图像中心为圆心。
4. 将高饱和度 mask 与半径 mask 相交，把过滤范围限制在玩家周边。
5. 转为 0/255 uint8 后，用 `kernel_small` 膨胀 1 次，扩大动态颜色清理范围。
6. 返回布尔 mask，供调用方原地清除 wall/fog/edges 像素。
副作用：无持久状态写入；调用方会依据返回 mask 修改本帧临时 mask。
失败行为：输入不是 BGR 图像时 OpenCV 转 HSV 抛错；`player_pos` 超出图像范围时圆形 mask 可能为空或部分落在图外。
调用关系：called by `hsv.combined.extract_combined_masks()`。

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
1. `NavigationRuntimeFrameLoop.run()` 调用 `capture_navigation_localization_tick()` 获取 `capture_rect`、屏幕截图帧、玩家局部坐标和 `localized_pos=(global_x, global_y)`；副作用是更新定位核心状态，后续再更新地图上的玩家点、绿色定位框、橙色真实可见框和事件 marker。
2. `NavigationCore.localize()` 输入实时小地图截图和 `player_pos`；输出地图全局坐标和置信度；副作用是更新 `current_pos/last_good_pos/prev_mask`。
3. `EventCoordinator.observe()` 输入 `EventTick(frame, frame_registration, player_global_pos)`；输出 memory 中的 active event tasks；副作用是检测 raw minimap 图标、稳定全局事件坐标、更新事件 overlay，但不推进 handler。
4. GUI runtime 构造 `NavigationUpdateContext` 并调用 `NavigationTaskController.update_context()`；context 内含定位、`route["main"]`、`EventCoordinator.tasks()`、`nav_core.nav_wall_layer`、`explored_map` 和 `PathFinder`；控制器先用 `NavigationTaskBuilder` 构造 required/exit/event 任务，再由 `NavigationTaskScheduler` 选择一个当前任务；输出 `NavigationIntent`。
5. 若 `NavigationIntent.metadata.force_relocalize` 为真，`handle_relocalization_navigation_intent()` 调用 `NavigationCore.request_global_relocalization(reason)`、写 `navigation forced global relocalization` 事件日志、追加“正在重新定位”状态栏后缀，并返回 `True` 让主循环提前结束本帧。
6. 静态 required/exit 或事件 `MOVE_TO` 进入 `MovementExecutor.step()`；该执行器通过 `RouteContext.corridor_anchors()` 和 `plan_path_with_optional_anchors()` 优先按前方 guide 点走廊规划 `anchor_step/anchor_probe`，无前方锚点时才直接规划目标，最后输出地图子目标 `subgoal` 和 `path_kind`。
7. 事件任务被选中时，`NavigationTaskController._update_event_task()` 调用 `EventCoordinator.run_task(event_task_id, tick)` 推进 handler；`MOVE_TO` 复用第 6 步，`PRESS_KEY/CLICK_SCREEN/COMPLETE/FAIL` 转成统一 `NavigationIntent`。
8. `NavigationRuntimeFrameLoop._execute_navigation_intent()` 调用 `navigation/input/intent_executor.execute_navigation_intent()` 消费 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY`；`MOVE_MAP` 调用 `MotionController.move_to_map_target()`，带 `force_click_target` 时调用 `click_map_target_once()`，成功点击后回写 `NavigationTaskController.record_intent_click()` 更新点击节流状态。
9. `MotionController._execute_click()` 输入屏幕物理坐标；先用 `_apply_bottom_click_guard()` 避免落入底部 UI，再通过 `InputDriver.click()` 执行 Win32 `SetCursorPos + mouse_event`，失败时才回退 `pydirectinput.click(x, y)`。

### Flow: 导航参数保存和加载
1. `NavigationModeWidget.load_map()` 读取 `map_data/<map>/config.json`。
2. `NavConfig.from_dict()` 将 dict 转为配置对象；缺失新字段时使用默认值。
3. `NavParametersDialog.set_config_to_ui()` 保存当前配置对象，用 `QSignalBlocker` 包住全部子控件，再调用 `write_config_to_widgets()` 将配置同步到控件。
4. 控件变化触发 `_update_config_value()`；HSV 文本先经 `parse_config_text_value()` 解析，无效/未完成输入直接跳过。
5. `_update_config_value()` 调用 `replace_config_value()` 通过 `dataclasses.replace()` 创建新配置并发出 `parameters_changed`。
6. `NavigationModeWidget._on_parameter_changed()` 保存内存态配置，调用 `apply_motion_controller_config()` 立即更新 `MotionController` 的屏幕中心、移动比例、点击半径和底部禁点区，并通过 `_refresh_game_view_rect_from_known_position()` 重绘橙色框。
7. `_apply_config_to_core()` 作为兼容 wrapper 调用 `apply_navigation_config_to_core()`，该函数调用 `NavigationCore.rebuild_navigation_wall_layer(nav_wall_erode_iterations)`，并把 `path_start_clear_radius`、`path_walkable_snap_radius` 写入共享 `PathFinder`。
8. `configure_navigation_task_controller()` 把点击冷却、重复点击阈值、锚点到达半径、卡住判定间隔、最小进度、恢复次数、路径偏离阈值、事件靠近 gate 和坐标诊断阈值写入 `NavigationTaskController`。
9. 用户保存时 `_save_nav_config()` 调用 `NavConfig.to_dict()` 写回地图配置文件，并再次刷新橙色框。
10. 用户点击“保存为默认配置”时，`_save_nav_default_config()` 调用 `save_default_nav_config(__file__, nav_config)` 合并写入项目根 `config.json`，用于没有地图配置时的默认导航参数。

### Flow: 导航 route 编辑
1. 用户点击“设置出口/添加必经点/添加途经点”按钮，`NavigationModeWidget.toggle_*_mode()` 根据按钮 checked 状态调用 `_set_map_click_mode()`。
2. `_set_map_click_mode()` 调用 `RouteEditor.set_click_mode()` 更新 route 编辑状态，再把非当前模式按钮取消选中。
3. 用户点击地图时，`NavigationModeWidget.handle_map_click()` 作为 wrapper 调用 `NavigationMapClickLifecycle.handle_map_click()`，由 lifecycle 把 scene 坐标加上 `nav_core.crop_offset` 得到全局地图坐标。
4. `RouteEditor.handle_click(map_folder_path, global_point)` 根据 `MapClickMode` 调用 `RouteManager.set_exit_region()`、`add_required_point()` 或 `add_guide_point()` 并返回 `RouteEditResult`。
5. `NavigationMapClickLifecycle.handle_map_click()` 接收结果后通过 targets 写回 `route_data`，必要时通过 `RoutePanelController.set_click_mode()` 复位按钮模式，调用 `_render_route_overlay()` 重绘 route 层，并把返回的 `status_text` 写到状态栏。
6. 用户点击保存/撤销/清空路线时，`NavigationModeWidget` 的旧 slot 调用 `NavigationRouteLifecycle`；lifecycle 调用 `RoutePanelController`，controller 委托 `RouteEditor` 写入或更新 route 数据并返回 `RouteCommandResult`，lifecycle 再同步 `NavigationTaskController.load_route()`、重绘 overlay、写状态栏或弹保存失败警告。

### Flow: 绘图模式地图保存和根配置加载
1. 用户点击绘图页保存地图时，`MappingWidget.save_map()` 读取地图名，并构造 `config_data`。
2. `save_mapping_map(__file__, map_name, stitcher=app_context.stitcher, config_data=config_data)` 调用 `ensure_map_folder()` 创建 `map_data/<map_name>`，再调用 `MapStitcher.save_map_package()` 保存地图包；`MapStitcher.save_map_package()` 会把 `wall_layer`、`explored_map`、`fog_layer`、`current_pos`、`canvas_size` 和 `draw_scale` 写入 `map_data.npz`。
3. `MappingWidget._build_mapping_config_with_ui_overrides(include_draw_scale=True)` 读取截图配置、FPS、recognizer/stitcher 参数，并叠加绘图页 `draw_scale/canvas_size/player_clear_radius/wall_close_kernel_size` 控件值；`MapStitcher.save_map_package()` 同时把 `wall_close_kernel_size` 写入 `map_data.npz` 供导航定位复现墙体模板形态学。
4. `save_mapping_map()` 内部调用 `save_map_config(map_folder, config_data)` 写入 `map_data/<map_name>/config.json`。
5. 绘图页参数变化或区域变化触发 `MappingWidget.save_config()`，它通过 `_build_mapping_config_with_ui_overrides(include_draw_scale=False)` 构造根配置并由 `save_root_config(__file__, config)` 写入项目根目录 `config.json`。
6. `MappingWidget.load_saved_params()` 启动时调用 `restore_saved_mapping_config(__file__, ...)`；helper 先调用 `load_root_config()`，不存在时直接返回，存在时回填 `app_context`、恢复 capture selection、同步 Qt 控件和 recognizer/stitcher 参数；当 stitcher 仍为空地图时，几何参数会立即重建画布。

### Flow: 绘图模式捕获区域/中心点选择
1. 用户点击“选择区域”时，`MappingWidget.select_region()` 调用 `MappingCaptureSelectionController.start_region_selection()` 创建 `TransparentOverlay` 并进入全屏拖框。
2. overlay 确认后发出 `region_selected(x, y, width, height)`，controller 调用 `apply_region_selection()`，按 DPR 把逻辑像素转为物理像素并写入 `app_context.monitor_region`，同时清空 `monitor_logical_center`。
3. controller 返回 `CaptureSelectionResult` 给 `MappingWidget._handle_capture_selection_result()`；widget 更新 label、启用开始/颜色按钮并调用 `save_config()`。
4. 用户点击“选择中心点”时，`MappingWidget.select_center_point()` 调用 `MappingCaptureSelectionController.start_center_selection()` 创建 `CenterPointSelector`。
5. selector 确认后发出 `point_selected(x, y)`，controller 调用 `apply_center_selection()` 写入 `app_context.monitor_logical_center` 和 `monitor_size`，清空 `monitor_region`，并计算物理 `monitor_center`。
6. widget 把返回的 `physical_center` 保存到 `self.monitor_center`，供 `MappingSession.tick()` 和 `open_color_picker()` 调用 `screen_capture.capture_square()`。
7. size spin 变化时，`MappingWidget.update_capture_size()` 调用 controller `update_capture_size()`；区域模式只更新 `monitor_size`，中心点模式会重新计算物理中心和 label。
8. 启动时 `restore_saved_mapping_config()` 写入 AppContext 后调用 `capture_selection.restore_from_context()`，用保存配置恢复 UI label 和物理中心。

### Flow: 点击半径诊断
1. `MotionController._calculate_target_screen_position()` 记录 `raw_screen_radius` 和夹紧后的 `screen_radius`。
2. `NavigationModeWidget.navigation_loop()` 在实际点击后追加显示 `click r:<screen_radius>/raw:<raw_screen_radius>`。
3. 如果 `raw` 明显大于 `r`，说明当前点击被 `movement_max_click_radius` 限制；如果 `raw` 和 `r` 都小，说明路径子目标距离或映射比例过小。

### Flow: 事件图标探针
1. `event_icon_probe.main()` 读取 `map_data/A1/config.json`，按 DPR 将小地图逻辑中心转换为物理截图矩形；如果传入 `--image`，仍加载配置用于输出一致的诊断上下文，但跳过实时截图。
2. 实时模式下 `SquareScreenCapture.capture()` 返回 raw minimap frame；静态模式下 `cv2.imread()` 读取每个 `--image` 指定图片。两种输入都必须是未经过定位特征图后处理的事件图标层。
3. 未传 `--portal-feature-detector` 时，`event_icon_probe.probe_frame()` 对每个 `--template` 调用 `core.events.detectors.template_matcher.match_single_template()`，执行多尺度灰度+边缘匹配。
4. 传入 `--portal-feature-detector` 时，脚本调用 `core.events.types.portal.minimap_feature_matcher.build_feature_templates()` 从模板中抠出蓝色本体二值特征，再调用 `match_portal_features()` 在 raw frame 的蓝色二值图上匹配。
5. 传入 `--portal-shape-color-detector` 时，脚本调用 `core.events.types.portal.minimap_shape_color.match_portal_shape_color()`，同时输出蓝色核心、白/灰外环、组合形状 mask、debug 框图和候选裁剪。
6. `core.events.detectors.template_matcher.merge_hits()`、`minimap_feature_matcher.merge_feature_hits()` 或 `minimap_shape_color.merge_shape_color_hits()` 合并不同模板/尺度对同一图标的重复命中。
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
9. 自动导航或手动事件测试启用时，GUI runtime 构造 `NavigationUpdateContext` 并调用 `NavigationTaskController.update_context()`，控制器从 `EventCoordinator.tasks()` 获取 pending/running event tasks，并把它们作为动态必经点和 required/exit 一起调度；手动传送门测试通过 `manual_event_only=True` 只选择事件任务。
10. 被选中的事件任务通过 `EventCoordinator.run_task(task_id, tick)` 推进 handler；handler 返回 `MOVE_TO` 时复用 `MovementExecutor.step()` 规划事件路径和 subgoal，返回 `PRESS_KEY/CLICK_SCREEN` 时直接转成 `NavigationIntent`。
11. `NavigationRuntimeFrameLoop._execute_navigation_intent()` 统一消费事件和普通导航的移动/点击/按键；终态事件 action 会让手动测试按钮自动停止，自动导航则从下一帧按当前位置重新调度 required/event/exit。
12. `NavigationModeWidget._render_event_overlay()` 从 `EventCoordinator.overlays()` 读取启用事件任务，在地图上绘制事件圆点和状态文本；当前 path/subgoal 复用路线 overlay 绘制。
13. 用户点击保存时，`_save_event_config()` 调用 `save_event_config()` 写入当前地图 `event_config.json`。

## 7. 外部集成详情
`main.py` Windows 启动前置条件：先配置 UTF-8 输出和 `logs/runtime.log`，随后默认立即 `FreeConsole()` 释放控制台，再设置 DPI awareness、检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", pythonw.exe, ...)` 触发 UAC 重新启动当前脚本并退出原进程。管理员进程启动后会获取基于项目路径的 Win32 mutex 单实例锁，并扫描已有 `实时小地图拼接系统` 主窗口；如果已有实例存在，新实例直接退出，防止多个 GUI 同时识别事件并向游戏发送移动/按键。默认 GUI 启动不保留控制台，诊断输出写入 `logs/runtime.log`；如需实时控制台，启动前设置 `MINIMAP_DEBUG_CONSOLE=1`，此时不会释放控制台，提权会继续使用 `python.exe` 并把输出同时写入控制台和日志文件。真实游戏输入依赖管理员完整性级别。
`logs/runtime.log` 每次进程启动都会重建，不再把旧会话定位刷屏追加到新会话后面；事件系统另有专用 `logs/event_runtime.log`，用于测试传送门时只看事件链路。

`InputDriver.click(x, y)`：由 `MotionController._execute_click()` 的 `win32_mouse_event` 后端调用，执行 `SetCursorPos(x, y)` 后用 Win32 `mouse_event` 分开发送 left-down/left-up。该路径来自旧脚本 `t2.py` 的可用实现，当前是游戏点击主后端。

`pydirectinput.click(x, y)`：仍作为 `MotionController` 的异常兜底和诊断工具保留。失败风险包括游戏窗口未聚焦、坐标在窗口外、权限/输入钩子被游戏屏蔽。

`pydirectinput.press(key)`：由 `MotionController.press_key()` 在事件 `PRESS_KEY` 动作中调用，目前主要服务传送门事件配置为按键交互时的 `D` 键。它同样依赖管理员权限和正确前台窗口。

`utils/event_icon_probe.py`：独立事件识别探针，依赖 `core.platform.SquareScreenCapture`、OpenCV 模板匹配和 portal 蓝色本体 feature matcher package。真实游戏窗口下需要管理员权限才能可靠捕获 raw minimap；非管理员权限可能返回黑帧，不应误判为识别算法失败。静态 `--image` 模式不依赖截图权限，适合先验证模板资产自身是否覆盖某个用户截图外观；`--portal-feature-detector` 用于验证运行时传送门识别算法。

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
`detector_mode: str` - 小地图传送门识别算法，支持 `template`、`feature`、`feature_then_template`、`shape_color`。当前默认 `shape_color`，用于更严格的形状+颜色联合识别；旧配置缺少 `detector_mode` 但含 `feature_detector_enabled` 时仍兼容旧 feature/template 行为。
`minimap_threshold: float` - 小地图事件识别阈值；portal 当前优先用于蓝色本体 feature score，整块模板兜底也复用该值。
`max_candidates: int` - 单帧最多接受的传送门候选数，默认 2。
`minimap_nms_radius: int` - detector conversion 层的小地图局部命中合并半径，默认 28；用于抑制同一传送门图标的多模板/多尺度重复 hit。
`min_blue_ratio: float` - 模板 bbox 周围必须满足的蓝/青传送门像素比例，过滤白墙误匹配。
`feature_hue_min: int` / `feature_hue_max: int` - portal 本体特征 HSV hue 范围，默认 82..136。
`feature_sat_min: int` / `feature_val_min: int` - portal 本体特征 HSV 饱和度/亮度下限，默认 55/95。
`feature_min_blue_pixels: int` / `feature_max_blue_pixels: int` - portal 候选窗口内蓝色本体像素数量范围，默认 36..420；`feature_max_blue_pixels=0` 表示不设上限。
`shape_outer_sat_max: int` / `shape_outer_val_min: int` - shape_color 模式下白/灰外环 HSV 阈值。
`shape_min_blue_score: float` / `shape_min_outer_score: float` / `shape_min_shape_score: float` - shape_color 模式下蓝色核心、外环和组合形状的最低 F1-like 分数。
`shape_min_outer_pixels: int` - shape_color 模式下候选框内必须包含的最少白/灰外环像素。
`stable_frames: int` - 事件定位稳定帧数，默认 3。
`localization_cluster_radius: int` - 多帧投影稳定簇合并半径，当前默认 96；日志中 70-85px 级别的同门抖动应进入同一簇。
`dedupe_radius: int` - memory 合并同类事件任务的半径，当前默认 96；真实相邻双门被合并时可在事件面板调小。
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
`core/input/win32_driver.py` is part of the movement chain. It wraps Win32 `SetCursorPos`, `WindowFromPoint`, `SetForegroundWindow`, `GetForegroundWindow`, `GetClipCursor`, and `mouse_event`; `click()` performs separate down/up events with a short hold instead of a combined instant click.

`core/input/controller.py` owns the `MotionController` class; map-direction to screen-click conversion lives in `core/input/motion_mapping.py` and click backend access lives under `core/input/motion_controller/`. The main project backend is `win32_mouse_event`: the click pipeline calls `InputDriver.click(x, y, button="primary", hold_seconds=0.05, move_delay=0.02)`. `pydirectinput.click(x, y)` is only used as a fallback if the primary backend raises.

`MotionController.click_map_target_once()` is an event-interaction helper, not normal movement guidance. It maps the target map point to screen space with `movement_scale_factor` and `movement_max_click_radius`, but deliberately does not apply `movement_min_click_radius`; if the player and target overlap, it clicks `game_screen_center`. Portal uses this for the pre-`D` mapped portal-point click when `NavigationIntent.metadata.force_click_target` is set.

`core/navigation_tasks/movement_executor.py` is the single map-space movement planner for required points, exit movement, and event `MOVE_TO`. User-defined guide points shape route intent through `RouteContext.corridor_anchors()`: current-position-before anchors are ignored, forward anchors between the player and current selected task are preserved, and movement advances by `anchor_step` or `anchor_probe` before direct target A*. Anchor path-goal arrival uses configurable `anchor_arrival_radius`; while an anchor/fallback path goal is still pending, the executor allows repeat clicks after the normal cooldown even if the subgoal barely changed, so a successful anchor plan cannot stall only because `auto_min_click_target_delta` suppressed the click. Stuck recovery now probes toward the active anchor/fallback path goal instead of the final route target, and exhausted recovery attempts set an explicit force-replan flag for the next frame. Automatic click cadence, target-delta suppression, anchor radius, stuck timeout, min progress, recover count, and deviation threshold are all exposed in the navigation parameter dialog and applied to `NavigationTaskController.movement`.

When the player is close to the current `anchor_step`/`anchor_probe` path goal but still outside `anchor_arrival_radius`, `MovementExecutor` switches from normal movement clicks to an exact path-goal click. The returned `MovementStep.force_click_target=True` is propagated through `NavigationTaskController` into `NavigationIntent.metadata`, so `NavigationRuntimeFrameLoop._execute_navigation_intent()` uses `MotionController.click_map_target_once()` and bypasses `movement_min_click_radius`. This prevents near-anchor map deltas such as 20-40px from being inflated into 299px screen-radius clicks that overshoot the anchor. During this final-anchor settle window, recovery probes are suppressed for about 2.2s; if the anchor is still not reached, normal stuck recovery can resume.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation/input/window_mode.py::GameInputWindowMode` prevents the PySide main window from intercepting auto-navigation clicks. `NavigationModeWidget._set_game_input_window_mode()` is now only a compatibility wrapper around that adapter. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

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
`core.events.debug` is the shared logging utility package for the event system. It provides `event_log()`, `start_event_log_session()`, `describe_action()`, and `describe_task()` so event modules print consistent `[Event HH:MM:SS.mmm pid=<pid>] ...` lines instead of ad-hoc debug strings. `writer.py` writes to runtime output, `logs/event_runtime.log`, per-run archives under `logs/event_runs/`, and optional topic logs such as `event_portal.log`; `topics.py` decides portal/navigation/localization topic routing; `descriptions.py` formats actions/tasks; `formatting.py` keeps scalar/tuple/list/dict/Enum values consistent. The PID is intentionally included because multiple GUI processes can otherwise interleave event lines and make a portal bounce look like a single state-machine bug.

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
The current portal event is minimap-first. `PortalMinimapDetector` exposes multiple selectable minimap recognition modes in the event manager: `template`, `feature`, `feature_then_template`, and `shape_color`. As of 2026-06-04 the default is `shape_color`, because runtime logs showed the older `feature_then_template` path frequently emitted blue-body matches that could stabilize into nearby duplicate portal tasks. `shape_color` checks the blue/cyan portal body plus the white/gray outer ring, combined shape, edge, and HSV color similarity before the hit becomes a candidate. Every accepted hit still passes `portal_color_check()` before becoming an `EventDetection`; `minimap_nms_radius` then suppresses nearby local duplicate hits before wall-registration projection. The detector emits only local minimap candidates and never creates a trusted global coordinate. `feature_detector_enabled` is retained only for legacy config compatibility; new tuning should use `detector_mode`.

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

`core/events/position_stabilizer/runtime.py::EventPositionStabilizer.update()` is the shared localization stage for all future event types. It rejects detections when no valid frame registration exists, projects candidates through the same wall alignment used for player localization, clusters nearby samples, expires stale clusters, and emits stable observations only after the configured sample and variance gates pass. The old import path `core.events.position_stabilizer.EventPositionStabilizer` now resolves to the package facade.

## 15. Event Four-Phase Methodology
`docs/plans/2026-05-23-portal-event-case-study.md` records the project-level event methodology using `portal` as the first concrete case. Future event work should be evaluated through four phases: event recognition/localization, navigation to trigger point and triggering, event-specific execution, and event completion.

Phase 1 is already mostly shared: concrete detectors emit local `EventDetection` values, `EventPositionStabilizer` projects them through wall registration, and `EventMemory` only accepts stable `EventObservation` values. New minimap-based events should normally replace only detector assets/thresholds and event-specific config, not rewrite localization or memory.

Phase 2 is now shared through the unified navigation task layer and the event approach gate. Before an event handler is allowed to execute, `NavigationTaskController` asks `EventApproachController` to move toward the event with normal A* + guide anchors until the event enters the configured real-view box, then switch to short-lookahead A* without route anchors, stop near the event, and wait for stable frames. After the gate releases the task, handlers may still return `EventAction.move_to(global_pos)`, `PRESS_KEY`, `WAIT`, or `COMPLETE`, and `MovementExecutor` remains the shared A*, click throttling, and fallback-probe engine. The remaining coupling is that `NavigationRuntimeFrameLoop` still reaches into the navigation widget owner for capture/localization/UI overlay dependencies and GUI-owned input/status callbacks; future refactors can replace owner access with a narrower targets DTO without changing the task/controller protocol.

Phase 3 remains event-specific by design. Handlers may maintain complex state machines, but they must express side effects through `EventAction` rather than directly calling mouse/keyboard APIs. Portal is simple because triggering and execution are effectively the same: click the mapped portal point, wait briefly, then press `D`.

Phase 4 requires an explicit completion strategy per event. Portal uses a teleport completion strategy: position jump, local minimap environment change, or landing near another known portal. It then marks both entry and exit tasks completed through `EventMemory.complete_teleport_session()` to prevent bounce loops.

## 16. Structural Audit Snapshot
`gui/modes/navigation/widget.py` is now the main navigation UI composition root, and `gui.modes.navigation.NavigationModeWidget` is the canonical entry used by `MainWindow`. The old `gui/modes/navigation_mode.py` compatibility wrapper has been deleted. The widget still owns the navigation page UI, signal wiring, event tick creation, capture geometry, and unified navigation loop skeleton, but route commands, map loading, config save/apply, event lifecycle, screen calibration, map-click interpretation, presentation writes, command lifecycle, and intent consumption are already delegated into `gui/modes/navigation/*` modules. Final `NavigationIntent` consumption is coordinated through `gui/modes/navigation/runtime/intent_consumption.py`, while real input execution remains in `navigation/input/intent_executor.py`.

After the presentation overlay package split, route QGraphics overlay item construction lives in `gui/modes/navigation/presentation/route_overlay.py`, and event marker overlay construction lives in `gui/modes/navigation/presentation/event_overlay.py`. The old root-level `route_overlay.py` / `event_overlay.py` wrappers have been deleted. `NavigationModeWidget` still owns when overlays refresh and still exposes the original private methods, but no longer contains the long per-item drawing loops for route and event markers.

After the event-adapter cleanup, `gui/modes/navigation/event_adapter.py` owns event registry bootstrapping, config summary strings, default game-window lookup, `EventTick` construction, and coordinator status text. The old UI-level event-action helper predicates were removed because implementation references now flow through `NavigationTaskController` and core `EventAction -> NavigationIntent` translation. `NavigationModeWidget` still owns when to initialize the event system and when to call `EventCoordinator.observe()`.

After the navigation map package split, `gui/modes/navigation/map/config_store.py` owns project/map path resolution, map-name listing, `NavConfig` JSON load/save, default-config fallback, and merge saves; `gui/modes/navigation/map/capture_geometry.py` owns logical-to-physical center conversion and capture geometry calculation. The old `gui/modes/navigation/map_runtime.py` compatibility facade has been deleted. Saving navigation config merges into the existing map `config.json` instead of overwriting it, preserving mapping-only fields such as `stitcher_params` that are needed to keep drawing and navigation environments comparable. `NavigationModeWidget` still owns user feedback, `NavigationCore` construction, button enabling, and applying loaded config to runtime services.

After the calibration lifecycle split, `gui/modes/navigation/calibration/screen_center.py` owns primary-screen DPR lookup, logical-to-physical coordinate conversion, and center selector lifecycle, while `gui/modes/navigation/calibration/lifecycle.py::NavigationScreenCalibrationLifecycle` owns the navigation-page side effects after a calibration click: `NavConfig.game_screen_center` write, params dialog refresh, overlay refresh, config save, completion dialog, and selector close. `NavigationModeWidget._calibrate_screen_center()` and `_handle_calibration_click()` remain public UI slot wrappers.

After the presentation overlay package split, `gui/modes/navigation/presentation/viewport_overlay.py` owns screen overlay geometry, monitor green-rectangle geometry, and game-view orange-rectangle geometry; the old `gui/modes/navigation/viewport_overlay.py` wrapper has been deleted. `NavigationModeWidget` still owns actual Qt item creation and visibility updates.

After the dialog-host split, `gui/modes/navigation/presentation/dialog_host.py` owns the shared owned-dialog show/toggle shell behavior: restore minimized state, first-show offset from the main window, raise/activate, and the active-window hide signal. `NavigationModeWidget._toggle_owned_dialog()` and `_show_owned_dialog()` remain compatibility wrappers, so parameter/event dialog buttons keep the same call path while the large widget no longer carries this generic Qt shell code.

After the debug-overlay split, `gui/modes/navigation/presentation/debug_overlay.py` owns transparent debug overlay hide/show writes after capture geometry has been computed. `NavigationModeWidget._toggle_overlay_display()` still owns user-facing validation, checkbox reset, and warning dialog; `_update_overlay_display()` remains the compatibility wrapper that builds capture geometry and delegates the actual overlay window write.

After the navigation map-session split, `gui/modes/navigation/map/session.py` owns the smallest stable part of map loading: reading `NavConfig` with an existence flag and constructing `NavigationCore`. After the deeper map-load lifecycle split, `gui/modes/navigation/map/load_lifecycle.py::NavigationMapLoadLifecycle` owns the ordered GUI side effects that follow: missing-config warning, runtime config application, params dialog fill, route/event initialization, rendering, last-position marker, route/event overlay, loaded UI, and load-failed critical dialog. `NavigationModeWidget.load_map()` remains the compatibility entrypoint and only reads the selected combo text before delegating.

After the map-load UI split, `gui/modes/navigation/presentation/map_load_state.py` owns map combo population, the final loaded-state UI writes, missing-config warning, load-failed critical dialog, and overlay-config warning. `NavigationModeWidget.refresh_map_list()` still decides where map names come from, and `load_map()` still decides when loading is complete; the helper only writes QComboBox/button/status state or emits old user-facing messages. `_toggle_overlay_display()` still owns resetting the overlay button checked state.

After the initial capture-center split, `gui/modes/navigation/map/capture_geometry.py::initial_capture_center_for_config()` owns the pure logical-center-to-physical-center calculation used during map load. `NavigationModeWidget.load_map()` still writes `_capture_center_physical`, prints the debug line, and calls `params_dialog.set_config_to_ui()` at the original point in the load sequence.

After the config lifecycle split, `gui/modes/navigation/config/lifecycle.py::NavigationConfigLifecycle` owns the full navigation config sequence: parameter-change runtime sync, current-map config save, default config save, applying runtime config, refreshing debug overlay/game-view rect callbacks, dirty status, and save result presentation. `gui/modes/navigation/presentation/config_save_state.py` still owns only the concrete status-label/QMessageBox text. `NavigationModeWidget` keeps `_apply_config_to_core()`, `_configure_navigation_task_controller()`, `_save_nav_config()`, and `_save_nav_default_config()` as compatibility wrappers.

After the event-management presentation split, `gui/modes/navigation/presentation/event_management_state.py` owns only user-facing QMessageBox/status-label text for event config save, portal state reset, and portal manual test start/stop. After the event lifecycle split, `gui/modes/navigation/events/lifecycle.py::NavigationEventLifecycle` owns the surrounding workflow: event config IO, `EventCoordinator.reset_event_type("portal")`, manual-test controller state, movement/event-approach reset, motion/input window mode, overlay refresh, dialog task refresh, and event logs. `NavigationModeWidget` keeps `_save_event_config()`, `_reset_portal_event_state()`, `_reset_event_move_runtime()`, `_run_portal_manual_test()`, and `_set_portal_manual_test_active()` as compatibility wrappers.

After the event dialog/bootstrap split, `gui/modes/navigation/events/dialog_lifecycle.py::NavigationEventDialogLifecycle` owns event-dialog creation, signal wiring, context refresh, toggle behavior, and manual-test button synchronization. `gui/modes/navigation/events/bootstrap.py::initialize_navigation_event_system()` owns map-load-time event runtime construction: load event config, create `EventCoordinator`, create `GameWindowCaptureProvider`, refresh the event dialog, and log initialization. `NavigationModeWidget._initialize_event_system()` only writes the returned runtime objects back to widget fields.

After the map-click lifecycle split, `gui/modes/navigation/map/click_lifecycle.py::NavigationMapClickLifecycle` owns user map-click interpretation: initial hint placement, route editing command dispatch, manual move target guard/execution, hint/view mode toggling, marker writes, route overlay refresh, and click-related status text. `NavigationModeWidget` keeps `handle_map_click()`, `set_initial_hint()`, and `toggle_hint_mode()` as compatibility wrappers while `eventFilter()` remains the Qt event adapter.

After the map event-filter split, `gui/modes/navigation/map/event_filter.py::handle_navigation_map_event_filter()` owns the narrow Qt scene-click recognition rule: watched object must be the map scene, event type must be `GraphicsSceneMousePress`, and button must be left mouse. It forwards `scenePos()` into the injected map-click callback. `NavigationModeWidget.eventFilter()` now only calls this helper and falls back to `super().eventFilter()`.

After the navigation-command presentation split, `gui/modes/navigation/presentation/navigation_command_state.py` owns only user-facing QMessageBox/status-label text for auto-navigation guard/start/stop and navigation start/pause. `NavigationModeWidget` still owns route validation, `NavigationTaskController` lifecycle, `MotionController` control enablement, `nav_timer` start/stop, and button checked/text state.

After the route lifecycle split, `gui/modes/navigation/route/lifecycle.py::NavigationRouteLifecycle` owns route command result synchronization: load/save/undo/clear results update `route_data`, call `NavigationTaskController.load_route()`, refresh the route overlay, show status text, and preserve the old save-failed warning. `gui/modes/navigation/presentation/route_command_state.py` still owns only route command text/warning presentation, while `NavigationModeWidget` keeps the old route slot names as wrappers.

After the calibration-feedback presentation split, `gui/modes/navigation/presentation/calibration_feedback.py` owns only initial-hint status text, hint-mode status text, and screen-center calibrated completion dialog. After the map-click lifecycle split, `gui/modes/navigation/map/click_lifecycle.py::NavigationMapClickLifecycle` owns initial hint placement (`NavigationCore.set_initial_hint()`, marker/monitor/game-view refresh, hint button reset, view drag/cursor) and the full map-click interpretation order (hint -> route edit -> manual move). Screen-center calibration result handling has moved into `NavigationScreenCalibrationLifecycle`; `NavigationModeWidget` only keeps the old slot names.

After the runtime-status presentation split, `gui/modes/navigation/presentation/status_presenter.py` owns not only status text construction but also writing the current-frame runtime status, appending relocalize/click suffixes, and terminal arrived/failed texts. `NavigationRuntimeFrameLoop` now owns when status writes happen in the navigation frame; relocalize requests, terminal task shutdown, input-mode restoration, and button state changes are ordered through runtime intent helpers.

After the localization-view presentation split, `gui/modes/navigation/presentation/map_presenter.py::update_localization_view()` owns the localized/fallback display branch for player marker, monitor/game-view rect callbacks, player marker hiding, and view centering. `NavigationRuntimeFrameLoop` owns localization-frame orchestration, event observation, task updates, status write timing, and callback wiring.

After the event-observation runtime split, `gui/modes/navigation/runtime/loop.py::observe_navigation_events()` owns the per-frame event observation mini-flow: build tick, observe coordinator, render overlay, refresh visible event dialog tasks, and return `event_tick`. The two currently implemented event hooks live in the core task runner path rather than this GUI helper: `event_visible_target` fires when the selected event target first enters the real-view gate, and `event_completed` fires after the runner has completed memory state.

After the localization tick split, `gui/modes/navigation/runtime/localization_tick.py::capture_navigation_localization_tick()` owns the first navigation-loop segment: capture geometry, screen capture, player local-position resolution, and `NavigationCore.localize()` result wrapping. `NavigationRuntimeFrameLoop` owns writing `_current_capture_rect/_current_player_local_pos`, event observation, task update, presentation refresh, and route overlay timing.

After the minimap sample-capture split, `gui/modes/navigation/runtime/minimap_sample_capture.py` owns detector sample persistence: frame normalization to BGR, safe map-name directory creation, PNG writing through `cv2.imencode().tofile()`, and same-stem JSON metadata. `NavigationRuntimeFrameLoop` now also writes `_latest_minimap_frame/_latest_minimap_capture_rect/_latest_minimap_player_local_pos` immediately after localization capture, so the toolbar action can save the exact latest monitored minimap region without re-running event detection. If no cached frame exists, `NavigationModeWidget.save_minimap_sample()` falls back to one immediate capture using the current navigation monitor geometry.

After the intent-consumption split, `gui/modes/navigation/runtime/intent_consumption.py::consume_navigation_intent()` owns the route-overlay-after intent sequence: force-relocalize short-circuit, real-input execution callback, manual event test terminal stop, and ARRIVED/FAILED terminal shutdown. `NavigationRuntimeFrameLoop` supplies the concrete callbacks (`event_log`, `NavigationCore.request_global_relocalization()`, `_execute_navigation_intent()`, `_set_portal_manual_test_active()`, input window mode restore, button reset, and status presentation), so no hook/event bus has been introduced.

After the runtime command lifecycle split, `gui/modes/navigation/runtime/command_lifecycle.py::NavigationRuntimeCommandLifecycle` owns the navigation command state machine around user buttons: start navigation, stop runtime, start/stop auto navigation, guard messages, task-controller route start, timer start, motion control, game-input window mode, button rollback, and paused/started status text. `NavigationModeWidget` keeps the old slots (`toggle_navigation()`, `stop_runtime()`, `toggle_auto_navigation()`, `_can_start_auto_navigation()`, `_set_game_input_window_mode()`) as wrappers so external callers and signal wiring remain stable.

After the mapping IO and composition-path splits, `gui/modes/mapping/io/config_store.py` owns mapping root/map `config.json` read/write, `map_data` folder creation, and mapping config dict construction while delegating project-root/path resolution to `gui/composition/paths.py`. `gui/modes/mapping/io/map_save.py` owns directory creation, `MapStitcher.save_map_package()`, and map-level config writes. The old `gui/modes/mapping/save_load.py` wrapper has been deleted. `MappingWidget` still owns dialog timing, UI control synchronization, recognizer/stitcher parameter application timing, live capture tick delegation, path preview, advanced settings dialog orchestration, and topmost state.

After the sixth split, `gui/modes/mapping/map_renderer.py` owns BGR-to-QPixmap conversion, enhanced-map fallback unpacking, global map coloring, path polyline drawing, green viewport rectangle drawing, and current-position marker drawing. `MappingWidget` still decides when to fetch maps from stitcher and when to set Qt widgets.

After the seventh split, `gui/modes/mapping/params/binding.py` owns feature-parameter dict construction, HSV toggle application, merge-weight application, and loaded recognizer/stitcher parameter widget sync. The old `gui/modes/mapping/params_adapter.py` wrapper has been deleted. `MappingWidget` still decides when to apply runtime params and when to persist config, preserving old side-effect order.

`gui/composition/paths.py` now centralizes GUI project-root, `map_data`, root `config.json`, and advanced-settings directory resolution. Mapping config store, navigation map config store, and advanced-settings snapshot IO all delegate to it, so GUI implementation no longer uses fixed `Path(__file__).parents[n]` for project paths. `gui/composition/services.py` now centralizes the default AppContext core-service construction behind `CoreServices` and `create_core_services()`, preserving `MapStitcher(canvas_size=5000)` while making future injection explicit.

`gui/modes/mapping_widget.py` remains the second GUI page composition root, but it no longer owns capture-region/center-point selection mechanics, inline layout construction, map package persistence, or capture timer command state directly. `gui/modes/mapping/capture/selection_controller.py` owns overlay lifecycle, DPR conversion, AppContext monitor write-back, and restore-from-config selection display data. Mapping IO now lives under `gui/modes/mapping/io/config_store.py` and `map_save.py`; startup config restore now lives under `gui/modes/mapping/io/config_restore.py`; parameter binding now lives under `gui/modes/mapping/params/binding.py`; layout construction now lives under `gui/modes/mapping/ui/layout.py`; monitoring start/stop lives under `gui/modes/mapping/runtime/lifecycle.py`. `MappingWidget` still owns save timing, path preview on map click, advanced settings dialog orchestration, and topmost state. It owns advanced-setting runtime application through `_apply_advanced_settings_params()`: dialog Apply emits a command with `save=False`, accepted dialog applies with `save=True`. The next mapping split should target save-map dialog/presentation only if it reduces ownership ambiguity.

Dialog hotspots are `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/nav_params_dialog.py`, and `gui/dialogs/color_picker_dialog.py`. `AdvancedSettingsDialog` combines tab construction, presets, file IO, runtime recognizer/stitcher application, and default parameter dictionaries. `NavParametersDialog` now has functional tabs for positioning recognition, recognition algorithm values, movement click mapping, path/A* controls, and map/debug controls; field mapping, config mutation, text parsing, signal binding, and UI value writes now live in `gui/dialogs/nav_params/config_binding.py`. It still owns widget construction, Qt screen-bound adapter logic, status labels, action buttons, and default-config save signal. Old `k_ratio/y_bias` compatibility fields remain in `NavPreferences` serialization but are no longer visible or editable in this dialog. `ColorPickerDialog` still combines color sampling, HSV range calculation, preview display, marker drawing, and opt-in debug orchestration, but wall-preview mask construction now lives in `gui/dialogs/color_picker/preview.py`. These are mostly low-to-medium risk because they can be split behind unchanged dialog classes.

After the advanced-settings command split, `gui/dialogs/advanced_settings/params_adapter.py` owns advanced-settings widget-to-dict collection, current-param widget loading, default reset values, loaded-param widget sync, and applying preset data to widgets. `gui/dialogs/advanced_settings/file_io.py` owns advanced-settings JSON snapshot save/load, default `configs/advanced_settings/` output directory, filename sanitization, payload validation, and display formatting. `gui/dialogs/advanced_settings/presets.py` owns preset option order and value dictionaries. `AdvancedSettingsDialog` still owns tab layout, file dialogs, status labels, and print messages, but runtime application is now a command signal for migrated owners; direct recognizer/stitcher mutation remains only as compatibility fallback.

After the ninth split, `gui/dialogs/color_picker/hsv_ranges.py` owns HSV conversion/sample/range math and saturation averaging, while `gui/dialogs/color_picker/image_renderer.py` owns OpenCV-to-QPixmap conversion and sample marker drawing. `gui/dialogs/color_picker/debug_output.py` owns preview debug artifact output under `debug/color_picker/`; after the old-debug cleanup it is disabled by default and enabled only by `MINIMAP_COLOR_PICKER_DEBUG`. `gui/dialogs/color_picker/preview.py` now owns wall preview mask generation, 3x3 close morphology, and preview stats. `ColorPickerDialog` still owns point collection, mode/zoom state, result text, preview label display, debug-output timing, and accept/reject flow.

After the nav-params field-spec split, `gui/dialogs/nav_params/field_specs.py` owns editable field metadata: widget attribute name, config path, field kind, widget writer, and functional group. `gui/dialogs/nav_params/config_binding.py` consumes those specs for Qt signal wiring, HSV text parsing, immutable `NavConfig` replacement, and `NavConfig` snapshot writes to controls. `NavParametersDialog` keeps the facade class and UI shell behavior. After the nav-params screen-estimator split, `gui/dialogs/nav_params/screen_estimator.py` owns click-radius math and `NavParametersDialog` only adapts Qt screen geometry to that helper before writing widget values.

Core hotspots are algorithmically sensitive and should be split in small behaviour-preserving slices. The old top-level compatibility files have been removed: `MapStitcher` now lives under `core/mapping/stitcher.py`; `NavigationCore` lives under `core/localization/navigation_core/runtime.py`; routing, input, vision, platform capture, and navigation tasks are imported from their system packages. Map package persistence is in `core/mapping/package_io.py`, weighted fusion in `core/mapping/weighted_merge.py`, display-map generation in `core/mapping/rendering.py`, and keyframe/F2F frame flow in `core/mapping/frame_pipeline.py`. Navigation construction state is in `navigation_core/state.py`, relocalization helpers in `navigation_core/relocalization.py`, frame-registration writeback in `navigation_core/registration.py`, wall-layer wrappers in `navigation_core/wall_layer.py`, diagnostics in `navigation_core/diagnostics.py`, map package loading in `core/localization/map_package.py`, display rendering in `core/localization/rendering.py`, frame registration object construction in `core/localization/frame_registration.py`, wall-template/search-window preparation in `core/localization/frame_matcher.py`, visual consistency checking in `core/localization/visual_check.py`, localization evidence DTOs/builders in `core/localization/evidence/`, and the shared `FrameRegistration` contract in `core/shared/frame_registration.py`. F2F tracking decisions, template-match result acceptance/rejection, forced relocalization flag consumption, and localization state writes remain centralized in `core/localization/localize_pipeline.py`; `NavigationCore.localize()` still returns `(x, y, confidence)`. `core/navigation_tasks/*` is still the shared route/event movement layer; GUI runtime now constructs `NavigationUpdateContext` directly and calls `NavigationTaskController.update_context()`. `core/input/controller.py` is the input-control boundary and combines map-to-screen conversion delegation, Win32 backend access, pydirectinput fallback, keyboard presses, and click diagnostics.

The event system has comparatively clear module boundaries: `EventCoordinator` observes detections and runs only a selected task, `EventMonitor` runs detectors, `EventPositionStabilizer` localizes detections, `EventMemory` owns task lifecycle/cooldown, `EventScheduler` selects display/event-runner work inside the event layer, and `EventRunner` owns handler lifecycle. There is no event-specific action executor now; event actions become `NavigationIntent` through `NavigationTaskController`, then the GUI consumes the same intent path used by normal route navigation.

## 17. Navigation Conflict Design Options
`docs/plans/2026-05-24-navigation-route-progress-option-b-design.md` records the rejected/intermediate option B for historical comparison. It kept normal navigation and event movement as separate executors with shared route progress, but the user selected scheme C instead, so option B is no longer the active implementation direction.

Option B's useful idea, route progress and guide-anchor consumption, was absorbed into `RouteContext`, `NavigationTaskScheduler`, `MovementExecutor`, and `core/routing/anchors/` rather than implemented as two separate executors.

`docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` records the active architecture now implemented in source: UI-level arbitration and dual executors have been replaced with a unified `NavigationTask` queue where required points, exit, and event tasks are scheduled by one `NavigationTaskController`. Shared movement behavior lives in `MovementExecutor`; old movement wrappers and their tests have been deleted.

`docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md` remains the implementation record. The current source has already passed the planned cleanup boundary: the old ordinary navigator module, old event path mover module, old event action executor module, and their dedicated ordinary-navigator test have been removed; `NavigationModeWidget.navigation_loop()` is only a compatibility wrapper that calls `_navigation_loop_unified()`.

Reusable capabilities already present: `MovementExecutor` is reusable A* + guide-anchor + fallback movement for route and event targets; `core/routing/route_progress/` is now the single reusable route progress/projection implementation used by `RouteContext`, `routing.geometry`, and `routing.anchors.progress`; `RouteContext` remains the navigation-task route runtime context; `core/routing/geometry.py` remains the route math surface; `core/routing/pathfinder/` is reusable A* with grid, snap, coordinates, and search modules separated; `core/routing/anchors/` is reusable guide-anchor planning with progress/corridor/planner modules separated; `core/input/motion_mapping.py` is reusable map-to-screen click math; `core/events/detectors/template_matcher.py` is reusable template matching; `core/events/types/portal/minimap_feature_matcher/` is a reusable pattern for small minimap icons whose stable feature is a colored body rather than full background pixels; `core/events/types/portal/minimap_shape_color/` is a stricter reusable probe pattern for icons with colored core plus light outer-ring/shape constraints; `core/events/types/portal/minimap_hit_filter.py`, `environment_signature.py`, and `completion_detector.py` now hold portal helper logic that used to be embedded in detector/handler files. `core/events/window_finder.py` and `core/input/win32_driver.py` are reusable Windows input/window primitives; `NavConfig` and `EventSystemConfig` are separate runtime configuration contracts. Reusable capabilities now extracted from GUI include route overlay rendering, event overlay rendering, navigation capture geometry, navigation viewport geometry, mapping save/load config IO, mapping display rendering, mapping UI layout construction, mapping parameter control adapters, advanced-settings parameter mapping, color-picker HSV range math, and color-picker image marker rendering. Reusable capabilities still trapped in GUI include larger dialog layout composition and some owner-based composition wrappers.

Recommended refactor order is now: treat the current core/gui cleanup as an acceptance phase. The two GUI composition roots (`gui/modes/navigation/widget.py` and `gui/modes/mapping_widget.py`) are kept as public class entrypoints, and remaining internal wrappers are kept only where they serve Qt signals/timers, lifecycle targets, public slots, or ordering facades. The old top-level compatibility shells have already been removed on both core and GUI sides. Legacy cleanup already completed in this area: color-picker preview artifacts no longer write to CWD, advanced-settings parameter snapshots now write to `configs/advanced_settings/`, the unused `gui/widgets_fixed.py` backup has been removed after reference audit, and old `k_ratio/y_bias` fields are kept for config compatibility but hidden from the navigation parameter UI.

`architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md` 记录了 core 专项模块化迁移过程。当前实现已越过“保留顶层壳子”阶段：`core.capture`、`core.recognizer_optimized`、`core.stitcher_core`、`core.navigation_core`、`core.pathfinder`、`core.route_manager`、`core.motion_controller`、`core.input_driver` 等旧顶层文件已删除；真实实现进入 `core.routing`、`core.input`、`core.vision`、`core.platform`、`core.mapping`、`core.localization`、`core.shared` 等新包。`MapStitcher` 从 `core.mapping` 导入，`NavigationCore` 从 `core.localization` 导入，`MotionController` 从 `core.input` 导入，屏幕捕获从 `core.platform.SquareScreenCapture` 导入。`NavigationCore.localize()` 仍是定位主链入口，状态写入集中在 `core.localization.localize_pipeline.py`。

`architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md` 现在是 core 后续优化的规则源：不按固定行数、固定文件数或固定层级机械拆分，而按概念重复、依赖方向、模块深度、状态局部性和真实复用方判断是否值得动。`architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md` 是按该规则深读 core 后形成的下一阶段计划：P1 统一 `RouteContext`、`routing.geometry`、`routing.anchors.progress` 中重复的 route progress/projection；该 P1 的第一段已经落地到 `core/routing/route_progress/`，旧 geometry dict、RouteContext dataclass 和 anchors progress float 返回形态保持；P1 第二段已经落地到 `core/localization/evidence/`，coordinate diagnostics 现在内部消费 `LocalizationEvidence`，不再在定位诊断流程里散读 raw registration metadata，同时 `NavigationCore.localize()` 和 `CoordinateDiagnostics.record_localization()` 调用面保持不变；P2 共享日志格式化已落地到 `core/shared/diagnostics/formatting.py`，但 event writer、topic routing 和 coordinate log 文件路径没有改变；P2 固化 `EventAction -> NavigationIntent` 翻译层，保持事件 handler 不直接执行输入。V2 原阶段未包含 hook；当前后续阶段已新增 `core/events/hooks/`，先落地 `event_visible_target` 和 `event_completed` 两个观察型 hook，仍不因文件还有数百行就继续机械拆分；旧兼容壳清理已经单独推进并完成顶层文件删除。

`EventAction -> NavigationIntent` seam 已在中文架构文档中固化：`architecture_docs/zh-CN/core/events/ARCHITECTURE.md` 明确 event handler 只能返回 `EventAction | None`，不能直接依赖 `MotionController`、GUI 或输入执行器；`architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` 明确 `core/navigation_tasks/intent_factory.py` 和 `event_task_runner.py` 是唯一翻译链路。当前不拆 `intent_factory.py`，因为它接口窄、语义集中，拆分会降低 locality。

Legacy wrapper cleanup for implementation imports has completed for the top-level core/gui compatibility files listed above. Remaining package `__init__.py` files are kept only where they are canonical system package entrypoints, not legacy file-path shells. The current core/gui cleanup phase has passed two consecutive clean acceptance audits. Public GUI class entrypoints remain stable, justified internal wrappers are retained, and hook/new feature architecture is deferred to the next phase.

## 18. Coordinate Drift Diagnostics
`core/navigation_tasks/coordinate/diagnostics.py` is the dedicated coordinate-mismatch diagnostic and internal relocalization trigger module. The diagnostics system writes file-only records to `logs/coordinate_diagnostics.log` and intentionally does not print to the console or `runtime.log`. `CoordinateDiagnostics.record_localization()` records invalid localization, low confidence, raw-position jumps, large raw-vs-control gaps, long F2F tracking, and visual coordinate mismatch evidence from `FrameRegistration.metadata`. `CoordinateDiagnostics.record_navigation_state()` still records route projection deviation, raw/control arrival disagreement, and "near target but not completed" stalls for the current required/exit/event task, but these are diagnostic-only and no longer trigger forced relocalization. Recovery scoring now has only two primary signals: `visual_mismatch` and `raw_jump`. `visual_mismatch` is produced only after `NavigationCore` locally re-matches the current minimap wall mask near the tracked position and the best visual position stays farther than `coordinate_visual_mismatch_threshold` for `coordinate_visual_mismatch_frames` checks. `raw_jump` remains an emergency trigger for extreme F2F jumps. Route deviation, near-target stall, raw-control smoothing gap, and long F2F duration never force relocalization by themselves.

After the coordinate diagnostics split, `CoordinateDiagnostics` remains the stable stateful facade and is exported from `core.navigation_tasks.coordinate`. `record_localization()` delegates to `coordinate.localization.record_localization_diagnostics()`, `record_navigation_state()` delegates to `coordinate.navigation.record_navigation_diagnostics()`, request consume/accept/reject/scoring delegates to `coordinate/relocalization.py`, and file logging/registration formatting live in `coordinate/log.py` and `coordinate/formatting.py`.

After the event approach split, `EventApproachController` remains the stable navigation-layer facade. `update()` delegates to `event_approach.pipeline.update_event_approach()`, `_move_toward_event()` delegates to `event_approach.motion.move_toward_event()`, `_settle_or_ready()` delegates to `event_approach.settle.settle_or_ready()`, and `_is_event_in_real_view()` / `_approach_target_from_path()` delegate to `event_approach/geometry.py`. The old private helper wrappers remain available, while DTOs live in `event_approach/models.py`.

### `CoordinateDiagnostics.record_localization(self, *, now_ms: int, raw_pos, confidence: float, min_confidence: float, registration, trusted_pos, control_pos, active_task_id: str | None) -> None`
算法：
1. 委托 `record_localization_diagnostics()` 标准化 raw/trusted/control 坐标，并提取 `FrameRegistration` 字段。
2. 更新 registration source tracking：template match 重置 F2F age；F2F 首次出现时记录起点时间。
3. 检查 active relocalization request 是否超时；若 forced global template match 未在 `recovery_timeout_ms` 内成功，则记录 rejected 并清理 active request。
4. raw 缺失或置信度低于 `min_confidence` 时节流写 `localization invalid`，并停止本轮诊断。
5. raw 相对上一帧超过 `raw_jump_threshold` 时写 `raw localization jump`；如果当前 registration 是 F2F，则注册 `raw_jump` 恢复信号。
6. raw/control gap 超过阈值只写诊断日志，不触发重定位。
7. 调用 `record_visual_consistency()` 处理 `FrameRegistration.metadata.visual_*`，只有连续 visual mismatch 达标才注册 `visual_mismatch` 恢复信号。
8. F2F 持续超过 `long_f2f_tracking_ms` 时只写诊断日志。
副作用：更新 raw baseline、F2F age、visual mismatch 计数、recovery signals 和 coordinate diagnostics 日志。
失败行为：输入坐标不可解析时降级为 `None`，不抛异常。
调用关系：called by `update_pipeline.update_controller_context()`。

### `CoordinateDiagnostics.record_navigation_state(self, *, now_ms: int, task_id: str | None, task_kind: str | None, target_pos, raw_pos, trusted_pos, control_pos, confidence: float, route_context, arrival_radius: float, registration) -> None`
算法：
1. 委托 `record_navigation_diagnostics()` 标准化 target/raw/trusted/control；缺 target 或 control 时直接返回。
2. 如果有 `route_context`，把 control 投影到 route，得到 route deviation/progress。
3. route deviation 超过 `route_deviation_threshold` 时写 `route projection deviation`，但不注册恢复信号。
4. raw 已进入 arrival radius 但 control 仍在外部时，写 `arrival mismatch raw inside control outside`。
5. control 位于 `(arrival_radius, arrival_radius + target_near_margin]` 内并持续超过 `target_stall_ms` 时，写 `near target not completed`。
6. 离开 near-target 区间时清理该 task 的 near-target timer。
副作用：更新 `_near_target_since_ms`，写 coordinate diagnostics 日志。
失败行为：缺少关键坐标时静默跳过。
调用关系：called by `update_pipeline.update_controller_context()` after task selection。

`NavigationCore.localize()` now adds a lightweight visual consistency check to the F2F branch. Every `coordinate_visual_check_interval_ms`, it scales the current wall mask to map resolution, searches only a small margin around the current tracked player position, and records `visual_player`, `visual_delta`, `visual_delta_dist`, `visual_conf`, and `visual_expected_score` into the frame registration metadata. This implements the user-facing rule: if the screenshot visually belongs at point A but the navigation point is B, and that difference is stable, then relocalize. It avoids using route shape, anchor state, or A* fallback as evidence of coordinate drift.

`NavigationTaskController.update_context()` now receives `NavigationCore.last_frame_registration` through `NavigationUpdateContext.localization.frame_registration`. The controller uses diagnostics as a navigation-internal recovery event: it returns `WAIT` with `metadata.force_relocalize=True`, resets `MovementExecutor`, and prevents movement clicks during the recovery frame. When a forced global template match succeeds, `observe_localization(..., force_snap=True)` snaps `trusted/control` to the accepted coordinate. Normal coordinate recovery clears the old active task so scheduling replans from the corrected position; portal post-interaction recovery keeps the active event task when `forced_reason="portal_wait_result"` so the same handler can mark the teleport session complete.

`NavigationCore.request_full_map_localization(reason)` is the shared full-map recovery entry point, and `request_global_relocalization(reason)` remains a compatibility alias. It clears `is_localized`, `prev_mask`, and `prev_wall_mask`; the next `localize()` call skips F2F/local search, runs the same full-map `wall_layer` template matching path used on navigation start, uses the base `confidence_threshold` instead of a stricter recovery-only threshold, bypasses normal jump rejection, and tags `FrameRegistration.metadata.forced_global=True`. `NavigationRuntimeFrameLoop` consumes the force-relocalize intent, calls this method, logs `navigation forced global relocalization`, and returns before executing input.

`docs/plans/2026-05-24-coordinate-drift-diagnostics.md` records the current implemented relocalization strategy and the dedicated log events: `coordinate relocalization requested/forced/accepted/rejected`. Fixed global offset parameters remain prohibited.

## 19. Event Approach Stabilization
`core/navigation_tasks/event_approach/__init__.py` is the reusable navigation-layer gate for event trigger positioning. `EventApproachConfig` stores the user-tunable movement contract: `enabled`, `game_view_map_size`, `visible_margin`, `approach_lookahead`, `click_cooldown_ms`, `stop_radius`, `settle_ms`, `stable_frames`, and `max_motion_per_frame`. `EventApproachController.update()` returns an `EventApproachResult`; it now also marks `visible` and one-shot `became_visible` when the selected event task first enters the real-view box. It never calls an event handler directly.

Execution order for an event task is now: `NavigationTaskController._update_event_task()` checks `event_approach.is_released(task.id)`; if not released, `EventApproachController.update()` either returns a movement/wait `NavigationIntent` or marks the task ready. When `became_visible=True`, `_update_event_task()` emits `event_visible_target` through `controller.event_hooks` once for that navigation event task. Only after ready does the controller call `event_coordinator.run_task(event_task_id, event_tick)`. If the returned action is `COMPLETE`, `EventRunner` has already updated `EventMemory`; `_update_event_task()` then resets navigation event runtime and emits `event_completed`. This prevents `PortalEventHandler` from pressing `D` before the shared navigation layer has confirmed the event is inside the real-view box and the player has settled near it.

The approach algorithm has two movement phases. In the far phase, the target is the event global position and `MovementExecutor.step()` receives the normal `RouteContext`, so guide anchors still shape the route toward the event. When the event enters the real-view square centered on the player (`game_view_map_size / 2 + visible_margin`), the controller forces a replan, calls `MovementExecutor.step()` with `route_context=None`, a shorter `approach_lookahead`, and a per-call `click_cooldown_ms` override. This keeps the final approach wall-aware without letting old route anchors pull the player past the event.

The settle phase starts once the player is within `event_stop_radius` of either the event point or the path-derived approach point just before the event. During settling, no movement click is emitted. The gate releases only after `event_settle_ms` has elapsed and `event_stable_frames` consecutive frames stay within `event_max_motion_per_frame`. After release, the task id is recorded so the same event handler can continue through `portal_point_click`, `press D`, and `wait_result` without being blocked by the gate again. `COMPLETE`, `FAIL`, controller stop, route runtime reset, or manual event reset clear that released state.

`MovementExecutor.step()` now accepts an optional per-call `click_cooldown_ms`. This is intentionally not stored as global executor state; normal route navigation and anchor movement continue to use `NavConfig.auto_click_cooldown_ms`, while event final approach uses `NavConfig.event_approach_click_cooldown_ms`.

`gui/navigation_params.py::NavConfig` serializes the event approach parameters, and `gui/dialogs/nav_params_dialog.py` exposes them in the “事件靠近” tab. `gui/modes/navigation/map/config_applier.py::configure_navigation_task_controller()` is the single GUI-side bridge that copies those config values into `NavigationTaskController.event_approach`; `NavigationModeWidget._configure_navigation_task_controller()` remains as the old method wrapper.

### `event_approach.pipeline.update_event_approach(approach, *, task, current_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context, movement) -> EventApproachResult`
行为：执行单帧事件靠近 gate 状态机，决定继续移动、等待定位、停稳，还是释放事件 handler。
算法：
1. 从 task 提取字符串 task id 和 float target；若 gate disabled，直接返回 ready。
2. 若 `current_pos` 或 target 缺失，返回 waiting localization 的 `WAIT` intent，不写释放状态。
3. task id 切换时调用 `approach.reset_active()`，只重置当前活动 gate 状态，不清空已释放集合。
4. 用 `_is_event_in_real_view()` 判断事件目标是否已进入真实主画面范围。
5. 若不可见：清空 settle 状态；当上一阶段不是 `far` 时设置 `movement.force_replan=True`；用 normal lookahead 和 route context 调 `_move_toward_event()` 继续按 route/anchor 靠近；记录 `event approach far`。
6. 若可见且玩家到事件距离小于 `stop_radius`，进入 `_settle_or_ready()`。
7. 若可见但未到停靠半径：必要时强制重规划，改用 `config.approach_lookahead`、禁用 route context，并用 `config.click_cooldown_ms` 控制近距离点击节流。
8. 从 movement step 的 path 中计算距离终点 `stop_radius` 的 approach target；若玩家到事件或 approach target 已足够近，进入 `_settle_or_ready()`。
9. 否则清空 settle 状态，记录 `event approach approach`，返回移动/等待 intent。
副作用：可能写 `approach._task_id`、`movement.force_replan`、settle 状态和 nav log；不调用 event handler。
调用关系：called by `EventApproachController.update()`；indirectly called by `event_task_runner.update_event_task()`。

### `event_approach.motion.move_toward_event(approach, *, task, current, target, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context, movement, phase: str, click_cooldown_ms: int | None) -> EventApproachResult`
行为：把一次 movement executor 结果转换成 event approach 阶段 intent。
算法：
1. 调用 `movement.step()`，传入 task id、current/target、map/pathfinder/explored、now、lookahead、route context 和可选 per-call click cooldown。
2. 若 movement 返回 `None`，记录 path unavailable，并返回 `WAIT` intent，message 为 `event approach path unavailable`。
3. 若 step 可点击且有 subgoal，intent type 为 `MOVE_MAP`；否则为 `WAIT`。
4. 将 step 的 `subgoal/path/path_kind/deviation/force_click_target` 写入 `NavigationIntent`。
5. 在 intent metadata 中写入 `event_approach_phase`，使 UI/诊断能区分 far/approach。
副作用：调用 movement 可能更新 movement 内部路径、点击节流和恢复状态；本函数自身只记录路径不可用日志。
调用关系：called by `EventApproachController._move_toward_event()` and `event_approach.pipeline.update_event_approach()`。

### `event_approach.settle.settle_or_ready(approach, *, task, current, target, approach_target, now_ms: int, distance: float) -> EventApproachResult`
行为：事件触发前停稳 gate，等待玩家在事件附近稳定若干帧并满足 settle 时间。
算法：
1. 用上一帧 player pos 计算本帧 motion；首帧 motion 视为 0。
2. 若 motion 小于等于 `max_motion_per_frame`，累加 `approach._stable_frames`；否则清零 stable frames，并把 settle 起点重置为当前时间。
3. 若 settle 起点为空，设为当前时间。
4. 计算 `waited_ms`，同时满足 `waited_ms >= settle_ms` 和 `stable_frames >= stable_frames` 时 ready。
5. 记录 `event approach settling/ready` 日志，包含 player、target、approach target、distance、waited_ms、stable_frames、motion。
6. ready 时返回 `EventApproachResult(ready=True, phase="ready")`。
7. 未 ready 时返回 `WAIT` intent，subgoal 为 approach target，path_kind 为 `event_settle`，metadata 写入 wait/stable 信息。
副作用：写入 `approach._last_player_pos`、`_stable_frames`、`_settle_started_ms` 和日志节流状态。
调用关系：called by `EventApproachController._settle_or_ready()` and `event_approach.pipeline.update_event_approach()`。

### `event_approach.geometry.approach_target_from_path(config, path, target) -> tuple[float, float] | None`
行为：根据 movement path 计算靠近事件时应停在终点前的目标点。
算法：
1. path 为空时直接返回 event target。
2. 将 path 全部标准化为 float point；长度小于 2 时返回唯一点。
3. 用 `build_cumulative_lengths()` 计算累计路径长度。
4. stop distance 取 `max(8.0, config.stop_radius)`。
5. 若总路径长度小于 stop distance，返回 path 末点。
6. 否则用 `interpolate_by_distance()` 在总长减 stop distance 处插值得到停靠点，失败时回退 path 末点。
副作用：无。
调用关系：called by `EventApproachController._approach_target_from_path()` and `event_approach.pipeline.update_event_approach()`。

Expected event logs for a good portal run are `event approach far`, `event approach approach`, `event approach settling`, `event approach ready`, `event approach released`, then portal-specific logs such as `portal point click before interaction`, `portal interaction key`, and `portal teleport completed`. If the player never releases, inspect the same log fields for `visible`, `distance`, `waited_ms`, `stable_frames`, and `motion` before changing portal handler logic.
