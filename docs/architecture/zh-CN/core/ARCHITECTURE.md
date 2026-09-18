# Core 架构

专项拆分计划见 [CORE_MODULARIZATION_PLAN.md](CORE_MODULARIZATION_PLAN.md)。当前实现已经越过“顶层兼容壳先保留”的阶段：GUI 和工具脚本的实现侧调用已迁到系统包入口，旧 `core.*` 顶层兼容文件已删除；只有同名系统包 `__init__.py` 继续作为正式 package 入口。

后续优化判断准则见 [ARCHITECTURE_OPTIMIZATION_RULES.md](ARCHITECTURE_OPTIMIZATION_RULES.md)，下一阶段按准则推进的详细方案见 [CORE_OPTIMIZATION_PLAN_V2.md](CORE_OPTIMIZATION_PLAN_V2.md)。V2 不再按行数机械拆分，而是优先处理 route progress、localization evidence、diagnostics formatting 和 EventAction 到 NavigationIntent 的跨系统 seam。

## 系统角色

`core` 负责所有不应依赖 PySide widgets 的可复用运行行为。它应该对外暴露小接口，覆盖：

- 建图与拼接。
- 图像识别与玩家追踪。
- 导航定位。
- 路径规划与路线工具。
- 移动输入执行。
- 通过子包处理事件和导航任务编排。

## 当前公共包接口

`core/__init__.py` 当前只作为 package marker，不再导出 `ScreenCapture`、`HSVRecognizer`、`MapStitcher`、`PlayerTracker` 或 `PathFinder`。

当前实现侧稳定入口是系统包：

- `core.platform.SquareScreenCapture`
- `core.vision.HSVRecognizer`、`core.vision.PlayerTracker`
- `core.mapping.MapStitcher`
- `core.localization.NavigationCore`
- `core.routing.PathFinder`、`core.routing.RouteManager`
- `core.input.MotionController`
- `core.navigation_tasks.NavigationTaskController`、`core.navigation_tasks.NavigationUpdateContext`
- `core.events.coordinator.EventCoordinator`
- `core.events.debug.event_log` / `start_event_log_session`

重构含义：`core` 根包不再承担组合根导出；组合由 `gui/app_context.py` 和具体 GUI 功能模块显式导入系统包完成。

## 当前模块地图

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `platform/` | 屏幕捕获平台适配。 | 正式入口为 `core.platform.SquareScreenCapture`，不再保留 `core.capture` 或 `ScreenCapture` alias。 |
| `vision/` | HSV 识别、玩家追踪、phase displacement。 | `HSVRecognizer` 仍是状态 facade，真实参数、预处理、mask 和 combined pipeline 已拆到 `core.vision.hsv/`；旧 `recognizer_optimized.py`、`tracker.py`、`phase_displacement.py` 已删除。 |
| `mapping/` | 地图拼接系统。 | `MapStitcher` 从 `core.mapping` 导入；package IO、frame preparation、frame pipeline、weighted merge、rendering 已分层。旧 `stitcher_core.py` 已删除。 |
| `localization/` | 导航定位系统。 | `NavigationCore` 从 `core.localization` 导入；真实 class 在 `localization/navigation_core/runtime.py`，定位主链在 `localize_pipeline.py`。旧 `navigation_core.py` 已删除。 |
| `routing/` | 路径规划、路线几何、guide anchor 和 route repository。 | `PathFinder`、`RouteManager` 从 `core.routing` 导入；旧 `navigation_obstacles.py`、`pathfinder.py`、`path_utils.py`、`anchor_path.py`、`route_manager.py` 已删除。 |
| `input/` | 地图目标到屏幕输入的映射与执行。 | `MotionController` 从 `core.input` 导入；点击映射、pipeline、执行器、诊断、screen bounds、Win32 driver 已分层。旧 `motion_controller.py`、`motion_mapping.py`、`input_driver.py` 已删除。 |
| `navigation_tasks/controller.py` | 统一导航任务控制器 facade 和状态拥有者。 | 主 update 流程委托 `update_pipeline.py`，生命周期/定位/required progress/重定位 intent 委托 `navigation_tasks/controller_runtime/` 子包；旧 public/private 入口保留。 |
| `navigation_tasks/movement_executor.py` | 统一路线/事件目标移动执行器 facade。 | 已把 `step()` 主流程、路径维护、路径规划和恢复探测委托到 `navigation_tasks/movement/` 子包；旧 class 和旧私有方法入口保留。 |
| `navigation_tasks/coordinate/` | 坐标诊断和重定位请求生命周期。 | `CoordinateDiagnostics` 从 `core.navigation_tasks.coordinate` 导入；旧 `coordinate_diagnostics.py` 已删除。 |
| `navigation_tasks/event_approach/__init__.py` | 事件靠近/停稳 gate facade package。 | 已把 update 主流程、movement intent 构建、停稳判定、真实视野/停靠点几何拆到 `navigation_tasks/event_approach/` 子包；旧 class 和旧私有方法入口保留。 |
| `events/memory/__init__.py` | 事件任务生命周期 facade package。 | 已把 observation 合并、任务查找/冷却、完成/传送会话/失败策略委托到 `events/memory/` 子包；旧 `EventMemory` API 和私有 wrapper 保留。 |
| `events/debug/__init__.py` | 事件运行诊断日志 facade package。 | 已把 session/file writer、topic routing、action/task 描述和值格式化拆到 `events/debug/` 子包；旧 `core.events.debug` 函数入口保留。 |
| `events/types/portal/minimap_feature_matcher/__init__.py` | portal 小地图蓝色本体特征匹配 package。 | 已把 DTO、HSV mask、模板准备、响应图 peak 和主匹配/合并拆到同名算法 package；旧 import 路径保留。 |

## 当前包组织状态

```text
core/
├── routing/        # obstacles/pathfinder/geometry/route_progress/anchors/route_repository
├── input/          # motion_controller/ + motion_mapping/click_pipeline/click_executor/click_diagnostics/screen_bounds/win32_driver
├── vision/         # hsv_recognizer facade + hsv/ 子包 + player_tracker/phase_displacement
├── platform/       # screen_capture
├── shared/         # frame_registration + diagnostics formatting
├── mapping/        # stitcher/package_io/performance/frame_preparation/frame_pipeline/weighted_merge/rendering
├── localization/   # navigation_core/ + map_package/localize_pipeline/rendering/frame_registration/frame_matcher/visual_check/evidence
├── navigation_tasks/
│   ├── update_pipeline.py
│   ├── static_task_runner.py
│   ├── event_task_runner.py
│   ├── controller_utils.py
│   ├── controller_runtime/
│   │   ├── lifecycle.py
│   │   ├── localization.py
│   │   ├── progress.py
│   │   └── relocalization.py
│   ├── movement/
│   │   ├── pipeline.py
│   │   ├── path_planner.py
│   │   ├── path_maintenance.py
│   │   └── recovery.py
│   ├── coordinate/
│   │   ├── localization.py
│   │   ├── navigation.py
│   │   └── relocalization.py
│   ├── event_approach/
│   │   ├── pipeline.py
│   │   ├── motion.py
│   │   ├── settle.py
│   │   └── geometry.py
│   └── ...
└── events/
    ├── debug/
    └── ...
```

旧 top-level 兼容文件已删除；外部实现代码应直接使用上面的系统包入口。保留下来的 `__init__.py` 仅作为正式 package 聚合入口，而不是“旧文件路径壳子”。

## 目标系统拆分

```text
core
├── mapping system
│   ├── recognizer pipeline
│   ├── displacement estimator
│   ├── frame merge strategy
│   └── map package repository
├── localization system
│   ├── map package reader
│   ├── frame matcher
│   └── tracking state
├── route planning system
│   ├── obstacle derivation
│   ├── A* pathfinder
│   ├── route geometry
│   └── anchor corridor planner
└── input system
    ├── movement target mapper
    ├── click/key command executor
    └── platform adapters
```

## 立即拆分候选

### `core/mapping/stitcher.py`

当前状态：`MapStitcher` 的正式状态 facade。旧 `core/stitcher_core.py` 已删除，调用方应从 `core.mapping` 导入。

#### 当前风险

当前风险：map package IO、有状态拼接、phase/displacement 行为、weighted merging、可视化输出曾混在一个 top-level 文件中；现在 `MapStitcher` 作为 mapping 系统状态拥有者保留，细节委托 helper。

可能提取模块：

- `core/mapping/package_io.py` - 保存/加载地图包。
- `core/mapping/performance.py` - performance monitor 和 timer。
- `core/mapping/frame_preparation.py` - frame mask scale、wall thickness、similarity、bounds。
- `core/mapping/displacement.py` - phase correlation 和 smoothing。
- `core/mapping/merge.py` - 首帧放置与 weighted frame merge。
- `core/mapping/view.py` - cropped/enhanced map rendering。

已验证职责：

- 有状态 map canvas：`canvas`、`wall_layer`、`fog_layer`、`explored_map`、`weight_layer`、当前位置、keyframe/previous frame。
- Map package IO：`save_map_package()`、`load_map_package()`。
- Frame registration：`add_frame()` 选择 keyframe phase correlation 或 previous-frame fallback。
- 位移工具：`_estimate_displacement()` 委托 `core.vision.phase_displacement.estimate_phase_displacement()`。
- Frame preparation：`prepare_scaled_frame_masks()` 缩放 save/fog masks 并标准化 wall thickness。
- Similarity/bounds：`is_too_similar()` 保持 IoU 去重逻辑，`bounds_in_canvas()` 保持画布边界判断。
- Merge 算法：`_merge_frame_weighted()` 裁剪 frame ROI，更新 wall weight layer，应用 visibility/explored map，写 display canvas。
- Display rendering：`get_cropped_map()`、`get_enhanced_map()`。

`add_frame()` 算法：

1. 增加 frame 计数，并确定玩家在 minimap 内的 local 坐标。
2. 如果是首帧：
   - 把 frame 放到 canvas 中心；
   - 设置 current keyframe 和 previous frame；
   - 返回成功。
3. 尝试 keyframe anchor matching：
   - 对 `keyframe_mask` 和当前 `match_mask` 做 phase correlation；
   - 拒绝低质量；
   - 除非质量很高，否则拒绝大跳变。
4. 如果 anchor 有效：
   - 把 shift 转成 global scaled delta；
   - 从 keyframe position 更新当前 global position。
5. 如果 anchor 无效：
   - 对 `prev_mask` 和当前 `match_mask` 做 phase correlation；
   - 拒绝低质量或过大的 F2F shift；
   - 从 previous position 更新当前 global position；
   - 只有当前 feature count 足够高才更新 keyframe。
6. 如果匹配成功但质量低于 `draw_quality_gate`，更新 previous frame，但跳过地图 merge。
7. 按 `draw_scale` resize save/fog masks。
8. 标准化 wall thickness。
9. 通过 `_merge_frame_weighted()` 合并进地图。
10. 更新 previous frame 和 match statistics。

重构顺序：

1. `estimate_phase_displacement(img1, img2)` 已抽到 `core/phase_displacement.py`；在调用方和测试仍可能 patch 旧方法时，保留 `_estimate_displacement()` 兼容 wrapper。
2. `MapPackageRepository` 已以 `mapping/package_io.py` 函数形式落地。
3. `PerformanceMonitor`/`Timer` 已抽到 `mapping/performance.py`。
4. 帧准备、墙体厚度标准化、重复相似度和边界判断已抽到 `mapping/frame_preparation.py`。
5. 围绕 `_merge_frame_weighted()` 的核心融合已抽到 `mapping/weighted_merge.py`。
6. display rendering 已抽到 `mapping/rendering.py`。
7. `MapStitcher` class 已迁到 `core.mapping.stitcher`；keyframe/F2F registration 主流程由 `mapping/frame_pipeline.py` 承接，后续若继续细化可在 mapping 包内抽 registration result DTO。

### `core/localization/navigation_core/`

2026-06-04 首帧定位诊断补充：新增 `debug/navigation_localization_probe.py` 作为独立探针，专门复跑 `NavigationCore.localize()` 的首帧全图模板匹配。探针读取地图 `config.json` 和 `map_data.npz`，应用正式 `HSVRecognizer` 参数、`draw_scale` 和 `wall_match_close_kernel_size`，输出 `report.json`、实时小地图 wall/match mask、放大后的模板、最高候选地图 patch、保存位置地图 patch 和 top candidate sheet。它不接入导航循环，只用于确认“当前截图在当前地图包中到底匹配到哪里”。

本轮样本 `debug/minimap_samples/A/20260604_135548_439_A_minimap.png` 的最新探针结果在 `debug/navigation_localization_probe/20260604_142234_20260604_135548_439_A_minimap/`：生产链路选择 `(4211,3272)`，confidence=`0.7745`，保存位置 `(4792.48,3630.25)` 的响应分数为 `-0.0208`。配置、npz 和实际使用的 `draw_scale` 均为 `3.0`，没有发现尺度参数漂移。当前证据说明首帧错位应优先排查地图包/截图位置/全图墙体相似区域，而不是掉落物事件线程直接污染了人物定位状态。

同轮小修正：`navigation_core/state.py::initialize_runtime_state()` 保留 `map_data.npz` 读出的 `drawing_saved_pos/last_pos`，只用于 UI 上次位置 marker 和首帧 debug 对比；不会自动设置 `current_pos` 或 `is_localized`，因此不改变首帧 full-map/local-search 决策。

当前状态：`NavigationCore` 的正式状态 facade package。旧 `core/navigation_core.py` 已删除，调用方应从 `core.localization` 导入。

可能提取模块：

- `core/localization/navigation_core/` - `NavigationCore` 状态拥有者和旧私有 wrapper 分组。
- `core/localization/map_package.py` - loaded map data 和坐标 metadata。
- `core/localization/frame_registration.py` - `last_frame_registration` 的有效/无效对象构建。
- `core/localization/frame_matcher.py` - wall template scaling/closing 和 local/global search window selection。
- `core/localization/visual_check.py` - F2F 期间的局部视觉一致性复核。
- `core/localization/evidence/` - 定位帧证据 DTO 和 builder，供坐标诊断消费。
- `core/localization/tracking_state.py` - F2F/localized state transitions。

已验证职责：

- 从 `map_data.npz` 加载地图包。
- 派生 navigation obstacle layer。
- 构造 runtime recognizer。
- 定位状态：current/last/drawing positions、localized flags、previous masks、forced relocalization flags。
- frame registration metadata，供事件定位和坐标诊断使用。
- localization evidence，稳定封装 raw/trusted/control 坐标、confidence、registration fields 和 visual check metadata，避免 coordinate diagnostics 反复散读 `FrameRegistration.metadata`。
- F2F tracking through phase correlation。
- 针对 `wall_layer` 的 local/global template matching。
- 期望玩家位置附近的 visual consistency check。
- display map rendering 和 crop offset 计算。

当前抽取状态：

- `navigation_core/runtime.py` 承接 `NavigationCore` 真实 class。
- `navigation_core/state.py` 承接构造期 map path/default 参数初始化和运行态字段初始化。
- `navigation_core/registration.py` 承接 `_clear_frame_registration()` / `_set_frame_registration()` 写回 wrapper。
- `navigation_core/relocalization.py` 承接 `set_initial_hint()`、full-map relocalization request、full/local mode 判定和模板匹配阈值选择。
- `navigation_core/wall_layer.py` 承接 `nav_wall_layer` 派生、闭运算 kernel 和墙体模板标准化 wrapper。
- `navigation_core/diagnostics.py` 承接模板匹配失败节流日志。
- `map_package.py` 承接 `map_data.npz` 加载、`draw_scale`/`wall_close_kernel_size` 权威值读取、旧地图缺省字段回退。
- `rendering.py` 承接显示地图构建、有效区域 bounding box 裁剪和 `crop_offset` 写入。
- `frame_registration.py` 承接 `FrameRegistration(valid=False)` 和有效 frame origin/size/metadata 构建。
- `frame_matcher.py` 承接 `wall_mask` 按 `draw_scale` 放大、闭运算标准化，以及 full/local search area 选择。
- `visual_check.py` 承接 F2F 分支的局部 `cv2.matchTemplate()` 复核和 visual mismatch metadata 输出。
- `evidence/` 承接 `LocalizationEvidence`、`VisualCheckEvidence` 和从 `FrameRegistration` 构造 evidence 的 builder；`CoordinateDiagnostics.record_localization()` 仍保留旧签名，内部构造并消费 evidence。
- `NavigationCore.localize()` 仍作为旧公开入口，真实流程委托 `localize_pipeline.localize_frame()`；F2F 是否接受、template match 结果是否接受、forced relocalization flag 消费和状态写入仍在该 pipeline 中统一完成。

`localize()` 算法：

1. 拒绝空 frame。
2. 从参数、last player-local position 或 frame center 解析 player position。
3. 用 `HSVRecognizer.extract_combined()` 得到 `match_mask`、`wall_mask`、`fog_mask`。
4. 如果 match/wall feature count 低于阈值，拒绝。
5. 消费 forced-global relocalization flag，并决定 full-map 还是 local search。
6. 如果已经 localized 且未 forced：
   - 对 previous wall mask 和 current wall mask 做 phase correlation；
   - 拒绝低 confidence 或大 shift；
   - 用 `-shift * draw_scale` 更新 current global position；
   - 运行可选 visual consistency check；
   - 设置 frame registration source 为 `f2f`；
   - 返回 position。
7. 如果 F2F 不可用或被拒绝：
   - 选择 full map 或 local search window；
   - 把 wall mask resize 到 map `draw_scale`；
   - 标准化 wall template thickness；
   - 对 search area 做 `cv2.matchTemplate()`；
   - 根据 full/local mode 要求不同 confidence；
   - 用匹配 top-left 和 scaled player local position 算 global player coordinate；
   - 拒绝过大的 local relocalization jump；
   - 更新 localization state 和 frame registration source `template_match`。
8. 失败时清空或降级状态，返回 `(None, None, confidence)`。

重构顺序：

1. `estimate_phase_displacement(img1, img2)` 已抽到 `core/vision/phase_displacement.py`；`NavigationCore._estimate_displacement()` 只作为类内兼容 wrapper。
2. 抽 `MapDataPackage` loader。
3. `FrameRegistrationFactory` 已以 `localization/frame_registration.py` 的函数形式落地。
4. `LocalizationMatcher` 先抽出模板准备和搜索窗口选择；完整 match result acceptance 暂留 facade。
5. `NavigationCore` class 已迁到 `core.localization.navigation_core`，GUI 已改用 `core.localization` 入口，旧 `core.navigation_core` 已删除。

### Route Planning Modules

当前状态：路径规划是 `core` 中比较干净的一块。模块 GUI-free，基本是纯逻辑，并且已经把底层几何、A*、ordered-anchor route shaping 分开。

当前包组织：

```text
core/routing/
├── obstacles.py      # current navigation_obstacles.py
├── pathfinder/       # A* pathfinder package
│   ├── __init__.py
│   ├── runtime.py    # PathFinder facade/class
│   ├── grid.py       # obstacle grid building and start-area clearing
│   ├── astar.py      # A* loop and path reconstruction
│   ├── snap.py       # blocked endpoint walkable snapping
│   └── coordinates.py # map/grid coordinate conversion
├── geometry.py       # legacy-compatible path_utils surface
├── route_progress/   # shared polyline projection/progress implementation
│   ├── __init__.py
│   ├── models.py     # PolylineProjection
│   └── projection.py # cumulative lengths / projection / interpolation
└── anchors/          # guide anchor route shaping package
    ├── __init__.py
    ├── models.py     # AnchorPathResult
    ├── progress.py   # dedupe/progress map and route_progress wrappers
    ├── corridor.py   # forward ordered anchor filtering
    ├── planner.py    # anchor_step/anchor_probe/planned
    └── utils.py      # int point and probe point helpers
```

`PathFinder` 已按同名 package 拆分。当前正式入口是 `core.routing.PathFinder` 或 `core.routing.pathfinder.PathFinder`，旧 `core/pathfinder.py` 已删除。

已验证职责：

- `navigation_obstacles.derive_navigation_wall_layer()` 通过 threshold 和可选 cross-kernel erosion，把 stitched wall layer 转成 navigation-only wall layer。这样 A* 更宽容，但不改变 localization data。
- `PathFinder.find_path()` 是公共 A* planning adapter，输入 map-space start/end，输出 map-space path points。
- `routing/pathfinder/grid.py` 负责 wall/explored map 降采样、墙体可选 erode、安全边距 dilate 和起点附近清障。
- `routing/pathfinder/astar.py` 负责 8-neighbor A*、corner cutting 拒绝、Manhattan heuristic 和 came_from 回溯。
- `routing/pathfinder/snap.py` 负责起终点落障碍时的 Manhattan-radius 最近可走格搜索。
- `routing/pathfinder/coordinates.py` 负责 map-space 与 grid-space 的转换，以及 grid path 转回 map-space center points。
- `path_utils.py` 负责旧路线几何入口：distance、collinear simplification、Bresenham line walkability、shortcut smoothing、path distance、exit-region checks。cumulative distances、projection、interpolation 已委托到 `routing/route_progress/`，但旧 dict 字段和导入路径保持。
- `routing/route_progress/` 是折线累计距离、点到折线投影和按距离插值的权威实现。`RouteContext`、`routing.geometry` 和 `routing.anchors.progress` 都委托到这里，避免三处手写 route progress。
- `routing/anchors/` 负责 ordered user-guide-anchor policy，再 fallback 到 direct A*；旧 `anchor_path.py` 已删除。

`PathFinder.find_path()` 算法：

1. 用 `downsample_factor` 把 map-space start/end 转成 downsampled grid cells。
2. 拒绝越界 start/end cells。
3. 构建 downsampled obstacle grid：
   - threshold wall map；
   - 可选通过 `wall_shrink_iterations` 在 downsample 前 erode wall pixels；
   - 可选把 `explored_map` 中未知 cells 视为 obstacles；
   - 可选按 `safety_margin` dilate obstacles。
4. 基于 `start_clear_radius` 清理 start 附近圆形区域，容忍玩家附近局部 wall noise。
5. 如果 start 或 end 仍被阻塞，在 `walkable_snap_radius` 内用 Manhattan-radius scan 找第一个 walkable cell。
6. 在 8-neighbor grid 上跑 A*：
   - 正交 cost `1.0`；
   - 对角 cost `1.414`；
   - heuristic 是 Manhattan distance；
   - 斜向移动如果任意相邻正交 cell 被阻塞，则拒绝，防止 corner cutting。
7. 从 `came_from` 重建 grid path。
8. 把 grid cells 转回 map-space center points；必要时追加精确 end point。

`path_utils.smooth_path()` 算法：

1. 空路径返回 `[]`。
2. 删除完全共线的中间点。
3. 从当前 anchor 开始，从终点向后探测，直到找到 Bresenham line walkable 的最远点。
4. anchor 跳到这个最远可见点。
5. 重复直到终点。

`anchors.plan_path_with_optional_anchors()` 算法：

1. 把 start、target、anchors 标准化为整数点。
2. 按 authoring order 去重 anchors。
3. 把 start 和 target 投影到 ordered anchor polyline 上得到 progress。
4. 只保留 current progress 到 target progress 之间的 forward anchors，并跳过已经到达的 anchors。
5. 如果还有 forward anchor：
   - 尝试从 start 到下一个 anchor 做 A*；
   - 成功则返回 `path_kind="anchor_step"`；
   - 失败则返回朝该 anchor 的短两点 `path_kind="anchor_probe"`。
6. 如果没有相关 anchors，直接对 target 做 A*，返回 `path_kind="planned"`。
7. 只有在没有 anchor fallback 且 direct A* 失败时返回 `None`。

重构建议：

1. 在 movement/navigation tests 覆盖 route selection 前，保持这些模块源码兼容。
2. 为 `anchor_path.py` 增加直接测试，特别是 forward-anchor filtering、reached-anchor skipping、direct fallback、probe fallback。
3. `PathFinder` 和 `anchors` 已拆成同名 package；后续如继续拆 route planning，应优先处理 `RouteContext` 与 anchors 的重复投影逻辑，而不是把 anchor policy 合进 A*。
4. 不要把 anchor policy 合进 `PathFinder`；A* 应保持低层 planner，anchor planning 保持路线塑形策略。

### `core/motion_controller.py`

当前风险：movement math、click policy、具体 click execution、diagnostics、key execution 都在一个类里。

已验证职责：

- 保存 calibration 和 movement 参数：`game_screen_center`、movement scale、min/max click radius、precision cap、bottom click guard、backend、control enablement。
- 把 map-space player/target 坐标转成围绕 calibrated character center 的 screen click。
- 支持 near-goal 或 event point interaction 的 forced precise mapped target click。
- 支持 event action 的 direct screen click。
- 通过 `pydirectinput.press()` 执行 keyboard interaction。
- 应用 bottom-click guard，避免点击屏幕底部 UI。
- 可选把坐标 clamp 到 visible screen。
- 可选点击前 focus target window。
- 把丰富点击诊断记录进 `last_click_info`。
- 懒加载 `InputDriver`，方便 unit tests 注入 fake。

`move_to_map_target()` 算法：

1. `control_enabled` 为 false 时拒绝。
2. `game_screen_center` 未校准时拒绝。
3. 通过 `motion_mapping.calculate_movement_click()` 计算 screen click 和 click_info。
4. zero-delta 时拒绝点击。
5. 把 click_info 写入 `last_click_info`。
6. 通过 `_execute_click()` 执行 screen click。

`click_map_target_once()` 的区别：

- 通过 `motion_mapping.calculate_mapped_target_click()` 计算。
- 不应用 normal movement minimum radius。
- radius 由 `movement_precision_click_max_radius` 限制。
- 即使 target 几乎和玩家重合也能工作。

`_execute_click()` 算法：

1. 把 requested screen coordinates 转成整数。
2. 如果 backend、diagnostics 或 focus 需要，懒加载 `InputDriver`。
3. 用 `_apply_bottom_click_guard()` 委托 `motion_mapping.apply_bottom_click_guard()` 缩短会落入底部 UI 的向下点击。
4. 可选 clamp screen bounds。
5. 在 `last_click_info` 记录 requested/guarded/final 坐标。
6. debug 开启时收集 target window、foreground window、clip cursor rect、Win32 cursor position。
7. 可选 focus click target 下的窗口。
8. 记录 pydirectinput screen size 和 cursor position。
9. 通过 `_send_click()` 委托 `core.input.click_executor.send_click()` 发送点击。
10. 记录点击后 cursor positions。
11. 首选 backend 失败时打印异常并 fallback 到 `pydirectinput.click()`。

`_apply_bottom_click_guard()` 算法：

1. 从 `InputDriver` 或 `pydirectinput.size()` 解析 screen height。
2. 调用 `motion_mapping.apply_bottom_click_guard()`。
3. helper 处理 guard 禁用、center 缺失、screen height 缺失、安全线判断和线段投影。
4. 返回 adjusted point 和诊断信息。

可能提取模块：

- `core/input/motion_mapping.py` - 已抽取，负责纯 map delta 到 screen coordinate/radius result、precision cap 和 bottom guard。
- `core/input/click_executor.py` - 已抽取，负责 Win32/pydirectinput click backend 和 confirm click。
- `core/input/click_diagnostics.py` - 已抽取，负责 target/foreground window、ClipCursor、Win32 cursor 和窗口信息格式化。
- `core/input/screen_bounds.py` - 已抽取，负责 screen height 解析和可选 coordinate clamp。
- `core/input/click_policy.py` - 后续可承接更多 click policy 和 diagnostic DTOs。
- `core/input/command_sink.py` - click/key command interface 和 hook dispatch。
- `core/input/win32_driver.py` - 当前 Win32 input adapter 实现；旧 `input_driver.py` 已删除。
- `core/input/pydirect_driver.py` - pydirectinput fallback/key adapter。

目标 seam：

```text
NavigationIntentExecutor
  └─ MotionController
       ├─ MovementMapper
       ├─ ClickPolicy
       ├─ InputHookBus
       └─ InputCommandSink
            ├─ Win32MouseEventSink
            └─ PyDirectInputSink
```

Hook 点：

- `before_input_command(command, context)`
- `after_input_command(command, result)`
- `input_command_skipped(reason, context)`
- `input_backend_failed(command, exception)`

Adapter 缺口：

- `press_key()` 当前直接调用 `pydirectinput.press()`，不经过 `InputDriver`。在加更深事件 input hook 前，应引入支持 key 的 command sink。

测试：

- `tests/test_motion_controller.py` 已覆盖 min/max radius mapping、zero-delta skip、`_execute_click()` diagnostics、显式 screen clamp、focus-before-click、bottom guard。
- 抽取前应补 forced target click、direct screen click、key command adapter、hook emission 测试。

## 共享 Phase Displacement

`MapStitcher._estimate_displacement()` 和 `NavigationCore._estimate_displacement()` 现在委托给：

```python
def estimate_phase_displacement(img1, img2, *, dead_zone: float = 0.2) -> tuple[tuple[float, float] | None, float]:
    ...
```

该 helper 执行 Hanning-window phase correlation，把 dead zone 内的微小 shift 归一为 `(0.0, 0.0)`，并保留旧失败契约 `(None, 0.0)`。

测试：

- `tests/test_phase_displacement.py` 覆盖 identical-image dead-zone normalization 和 invalid-input failure。
- `tests/test_navigation_core.py` 仍验证 F2F tracking 把 wall masks 传入 displacement wrapper。
- `tests/test_stitcher_core.py` 继续作为 merge 安全网。

## 当前状态

状态：partial。已阅读 package export、组合使用、建图/定位核心、路径规划、输入系统和 navigation task movement 链路。当前已完成多轮系统包拆分和旧壳清理：`MapStitcher`、`NavigationCore`、`MotionController`、`NavigationTaskController`、`MovementExecutor`、`CoordinateDiagnostics`、`HSVRecognizer`、`EventApproachController` 的真实实现均位于功能包内；旧顶层兼容文件已删除，只有类内旧私有 wrapper 和 package `__init__.py` 作为稳定入口继续存在。

后续继续优化时，应按 [ARCHITECTURE_OPTIMIZATION_RULES.md](ARCHITECTURE_OPTIMIZATION_RULES.md) 判断是否值得动。当前优先级不是继续压缩单个文件行数，而是按 [CORE_OPTIMIZATION_PLAN_V2.md](CORE_OPTIMIZATION_PLAN_V2.md) 收束重复概念和跨系统 seam：先统一 route progress/projection，再整理 localization evidence，随后只抽共享日志格式化，最后在文档和代码结构上固化 EventAction -> NavigationIntent 翻译层。

当前共享诊断范围很窄：`core/shared/diagnostics/formatting.py` 只提供纯 `format_value()` / `format_fields()`。`events.debug.writer`、topic routing 和 `coordinate/log.py` 仍保留在各自系统内，避免把不同语义的日志输出强行合并。
