# core 分层模块化计划

本文记录 `core` 的工程化拆分主线。当前阶段已经从“保留旧顶层壳，先迁实现”推进到“实现侧调用系统包，删除旧顶层壳”。

## 当前目标

- 让 `core` 按工作流拆成稳定系统：平台捕获、视觉识别、建图、定位、路径规划、输入控制、导航任务、事件运行时。
- 算法行为不重写，只把实现按状态生命周期和复用边界下沉到功能包。
- GUI 和工具脚本优先导入系统包入口，不再依赖 `core.__init__` 聚合或旧顶层文件。
- Hook 机制已经进入后续功能阶段：`core/events/hooks/` 提供生命周期 trigger 和实例包，GUI 通过 `NavigationHookRuntime` 注册 key_press 实例；本模块化阶段仍不把 hook 当作旧 core 拆分阻塞项。
- 不处理 tests 目录；验证以实现侧 compile 和 import smoke 为主。

## 当前正式入口

| 能力 | 正式入口 | 备注 |
| --- | --- | --- |
| 屏幕捕获 | `core.platform.SquareScreenCapture` | 不再导出 `ScreenCapture` alias。 |
| HSV 识别 | `core.vision.HSVRecognizer` | 参数、预处理、mask、combined pipeline 已拆到 `core.vision.hsv/`。 |
| 玩家追踪 | `core.vision.PlayerTracker` | 仍是视觉系统能力。 |
| 位移估计 | `core.vision.estimate_phase_displacement` | 建图和定位共用。 |
| 地图拼接 | `core.mapping.MapStitcher` | package IO、frame pipeline、weighted merge、rendering 已拆。 |
| 导航定位 | `core.localization.NavigationCore` | 真实 class 在 `localization/navigation_core/runtime.py`，主定位流程在 `localize_pipeline.py`。 |
| 路径规划 | `core.routing.PathFinder` | A* 已拆成 grid/astar/snap/coordinates。 |
| 路线读写 | `core.routing.RouteManager` | `route.json` 持久化入口。 |
| 输入控制 | `core.input.MotionController` | 点击映射、执行、诊断、screen bounds、Win32 backend 已拆。 |
| Win32 输入适配 | `core.input.InputDriver` | 通过 input package 入口使用。 |
| 导航任务 | `core.navigation_tasks.NavigationTaskController`、`NavigationUpdateContext` | GUI 直接构造 context 并调用 `update_context()`。 |
| 事件协调 | `core.events.coordinator.EventCoordinator` | 同名 package 是正式入口。 |
| 事件日志 | `core.events.debug.event_log` | 同名 package 是正式入口。 |
| Portal handler | `core.events.types.portal.handler.PortalEventHandler` | 同名 package 是正式入口。 |

`core/__init__.py` 当前只作为 package marker，不再承担聚合导出。

## 已删除的旧顶层壳

- `core/capture.py`
- `core/recognizer_optimized.py`
- `core/tracker.py`
- `core/phase_displacement.py`
- `core/stitcher_core.py`
- `core/navigation_core.py`
- `core/navigation_obstacles.py`
- `core/pathfinder.py`
- `core/path_utils.py`
- `core/anchor_path.py`
- `core/route_manager.py`
- `core/motion_mapping.py`
- `core/motion_controller.py`
- `core/input_driver.py`
- `core/navigation_tasks/coordinate_diagnostics.py`
- `core/navigation_tasks/event_approach.py`
- `core/events/coordinator.py`
- `core/events/debug.py`
- `core/events/memory.py`
- `core/events/position_stabilizer.py`
- `core/events/types/portal/handler.py`
- `core/events/types/portal/minimap_feature_matcher.py`
- `core/events/types/portal/minimap_shape_color_matcher.py`

注意：部分旧 `.py` 文件被同名 package 替代，例如 `core.events.debug`、`core.events.coordinator`、`core.events.position_stabilizer`、`core.events.types.portal.handler`。这些 package 是正式入口，不是遗留文件壳。

## 当前系统结构

```text
core/
├── platform/                  # SquareScreenCapture
├── vision/                    # HSVRecognizer, PlayerTracker, phase displacement
├── mapping/                   # MapStitcher + package_io/frame_pipeline/weighted_merge/rendering
├── localization/              # NavigationCore + map_package/localize_pipeline/frame_matcher/evidence
├── routing/                   # obstacles/pathfinder/geometry/route_progress/anchors/route_repository
├── input/                     # MotionController + mapping/click/input backend helpers
├── navigation_tasks/          # task controller, update context, movement, coordinate, event approach
├── events/                    # coordinator, memory, scheduler, runner, debug, event types, lifecycle hooks
└── shared/                    # frame_registration, diagnostics formatting
```

## 关键拆分结果

### Mapping

`MapStitcher` 保留有状态 facade。核心职责分布：

- `package_io.py`：地图包保存/加载。
- `frame_preparation.py`：mask 缩放、墙体厚度标准化、相似度和边界判断。
- `frame_pipeline.py`：首帧、keyframe/F2F registration、质量门禁和 merge 调度。
- `weighted_merge.py`：ROI 裁剪、权重层、可见性、fog/explored 写入。
- `rendering.py`：cropped/enhanced map 输出。

### Localization

`NavigationCore.localize()` 仍是定位主入口，状态写入集中在 `localize_pipeline.py`。拆分结果：

- `navigation_core/runtime.py`：真实 class。
- `navigation_core/state.py`：构造期字段和运行态初始化。
- `navigation_core/relocalization.py`：full/local relocalization 请求和阈值选择。
- `navigation_core/registration.py`：frame registration 写回。
- `navigation_core/wall_layer.py`：导航墙体层派生。
- `map_package.py`：`map_data.npz` 加载和权威参数读取。
- `frame_matcher.py`：模板准备和搜索窗口。
- `visual_check.py`：F2F 视觉一致性复核。
- `evidence/`：定位证据 DTO 和 builder。

### Routing

`PathFinder` 是低层 A* planner；guide anchor 策略保留在 `routing/anchors/`。`routing/route_progress/` 是折线累计距离、投影和插值的共享实现，避免 `RouteContext`、geometry、anchors 三处重复。

### Input

`MotionController` 是输入系统 facade。拆分结果：

- `input/motion_mapping.py`：纯坐标映射和 bottom guard。
- `input/click_pipeline.py`：点击请求编排。
- `input/click_executor.py`：Win32/pydirectinput 发送。
- `input/click_diagnostics.py`：窗口、光标、ClipCursor 等诊断。
- `input/screen_bounds.py`：屏幕尺寸和坐标 clamp。
- `input/win32_driver.py`：平台输入 adapter。

### Navigation Tasks

`NavigationTaskController.update_context()` 是唯一帧更新入口。GUI runtime 组装 `NavigationUpdateContext`，controller 内部再走：

1. 定位过滤和 route progress 更新。
2. required/exit/event task 构建。
3. scheduler 选择当前任务。
4. static runner 或 event runner。
5. `intent_factory.py` 把 `MovementStep` / `EventAction` 转成 `NavigationIntent`。

旧 `update(**kwargs)` 和 `NavigationUpdateContext.from_legacy_kwargs()` 已删除。

### Events

事件系统现在按生命周期拆分：

- `coordinator/`：observe、run_task、reset、overlay/status、enabled filter。
- `memory/`：observation merge、task lookup/cooldown、completion/failure、teleport session。
- `position_stabilizer/`：local detection 到 global coordinate 投影、跨帧聚类、稳定 gate。
- `debug/`：event log session、topic routing、action/task 描述和值格式化。
- `types/portal/`：portal 具体 detector、handler、completion、shape-color/feature matcher。
- `hooks/`：事件生命周期 trigger、`EventHookRegistry`、`EventHookContext` 和具体 hook 实例包；当前实例为可配置 `key_press`，实例通过 `event_types` 绑定具体事件类型，真实按键仍由 GUI adapter 注入 `MotionController.press_key()`。

事件 handler 只能返回 `EventAction`，不能直接执行鼠标/键盘。`EventAction -> NavigationIntent` 的唯一翻译链路在 `core.navigation_tasks`。

## 依赖方向规则

```text
GUI / utils
  -> core system packages

core.navigation_tasks
  -> core.routing
  -> core.events models/actions
  -> 不调用 MotionController 或真实输入

core.events
  -> event detectors/handlers/models
  -> 不调用 GUI 或 MotionController

core.mapping / core.localization
  -> core.vision
  -> core.shared

core.input
  -> core.platform
  -> 不依赖 navigation_tasks/events/mapping/localization

core.routing / core.vision / core.shared
  -> 尽量纯逻辑
```

## 后续候选

1. 继续审计 core 内部是否还有“同名 package 入口只是转发但没有语义”的薄层；只删无价值壳，不删正式 package 聚合入口。
2. 复核 `MotionController.press_key()` 是否需要进入统一 command sink。当前 key_press hook 已复用该边界，后续如果 hook 类型增多，再评估是否抽成统一 command sink。
3. 复核 `EventCoordinator` 与 `NavigationTaskController` 的跨系统 DTO 是否还可以更窄。
4. 继续把 GUI 组合根调用迁到 package 入口，最后删除 widget 内部兼容 wrapper。

## 验证

每轮实现变更后执行：

```powershell
Get-ChildItem -Path core,gui,utils -Recurse -Filter *.py | Where-Object { $_.FullName -notmatch '\\tests\\|\\debug\\' } | ForEach-Object { D:\ACloud\.venv\Scripts\python.exe -m py_compile $_.FullName }
```

实现侧 import 扫描应保持旧顶层壳引用为 0。

当前状态：core 主体系统包拆分和旧顶层壳清理已完成；后续 core 工作以局部语义复用和依赖方向复核为主，不再恢复旧 facade 文件。
