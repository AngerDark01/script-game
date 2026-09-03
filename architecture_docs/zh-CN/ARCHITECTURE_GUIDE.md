# 架构指南

这份指南是工程化重构阅读工作的顶层索引。它和 `CODEBASE.md` 的定位不同：`CODEBASE.md` 描述当前代码库状态；本指南关注可复用模块边界、扩展点、大文件拆分候选，以及阶段化重构路线。

## 阅读顺序

先从这里开始，再按模块就近阅读：

- [OPTIMIZATION_EXECUTION_BASELINE.md](OPTIMIZATION_EXECUTION_BASELINE.md) - 后续 core/gui 工程化优化的执行基准，定义剩余任务、每轮流程、验证命令和结束标准。
- [core/ARCHITECTURE.md](core/ARCHITECTURE.md) - 核心系统总览：建图、定位、路径规划、输入控制、共享模型。
- [core/CORE_MODULARIZATION_PLAN.md](core/CORE_MODULARIZATION_PLAN.md) - core 专项模块化迁移计划：对外接口冻结、兼容壳子、目标目录、逐文件迁移表和阶段顺序。
- [core/navigation_tasks/ARCHITECTURE.md](core/navigation_tasks/ARCHITECTURE.md) - 统一导航任务系统，以及它和事件系统的交互。
- [core/events/ARCHITECTURE.md](core/events/ARCHITECTURE.md) - 事件系统生命周期、hook、memory、scheduler、runner 边界。
- [core/events/types/portal/ARCHITECTURE.md](core/events/types/portal/ARCHITECTURE.md) - 传送门作为第一个具体事件适配包。
- [gui/ARCHITECTURE.md](gui/ARCHITECTURE.md) - GUI 壳、共享 app context、dialogs、mode 归属。
- [gui/modes/ARCHITECTURE.md](gui/modes/ARCHITECTURE.md) - 建图模式和导航模式的拆分策略。
- [gui/modes/navigation/ARCHITECTURE.md](gui/modes/navigation/ARCHITECTURE.md) - `gui/modes/navigation/widget.py` 与导航功能包的详细拆分地图。
- [gui/dialogs/ARCHITECTURE.md](gui/dialogs/ARCHITECTURE.md) - 参数、事件、高级设置、颜色选择对话框职责。
- [utils/ARCHITECTURE.md](utils/ARCHITECTURE.md) - 探针脚本和诊断工具。
- [tests/ARCHITECTURE.md](tests/ARCHITECTURE.md) - 现有测试契约和重构安全网。

阅读过程和覆盖进度见 [ARCHITECTURE_ITERATION_LOG.md](ARCHITECTURE_ITERATION_LOG.md)。

## 抽象层级

后续重构计划统一使用这些层级：

- 系统：拥有一个用户可见工作流或长期状态的完整运行能力。
- 模块：有稳定接口和隐藏实现的包或文件组。
- 组件：在一个或多个模块内部复用的类/函数组。
- 适配器：GUI、文件系统、Windows 输入、OpenCV 或具体事件类型的集成实现。
- Hook：生命周期回调或扩展点，让新行为可以加入而不直接改核心循环。

## 一阶系统图

```text
┌──────────────────────────────┐
│ PySide6 Desktop Application  │
└──────────────┬───────────────┘
               │ 拥有 UI 状态和 timers
               ▼
┌──────────────────────────────┐
│ GUI Modes                    │
│ Mapping / Navigation         │
└───────┬──────────────┬───────┘
        │              │
        ▼              ▼
┌──────────────┐   ┌─────────────────────┐
│ Mapping Core │   │ Navigation Runtime  │
│ stitch map   │   │ localize + schedule │
└──────┬───────┘   └──────────┬──────────┘
       │                      │
       ▼                      ▼
┌──────────────┐   ┌─────────────────────┐
│ Map Package  │   │ Task / Event System │
│ npz/config   │   │ route/event/exit    │
└──────────────┘   └──────────┬──────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Input System │
                       │ click/key    │
                       └──────────────┘
```

## 已确认的重构主题

0. 启动流程应拆成“进程 bootstrap”和“Qt 应用组合”。`main.py` 当前同时负责 UTF-8/log 重定向、隐藏控制台、DPI awareness、UAC relaunch、单实例锁、旧窗口检测和 QApplication 启动。
1. `gui/modes/navigation/widget.py` 已成为导航页组合根；运行循环、路线编辑、事件对话框接线、overlay 渲染、配置应用和输入执行已经进入显式功能包。后续重点是继续收窄组合根和删除内部 wrapper。
2. 事件系统应通过 hook bus/listener 暴露生命周期 hook，而不是在 `EventDefinition` 上追加很多可选方法。
3. `core/navigation_tasks` 已接近可复用编排系统。它应继续输出 intent，不拥有 click/key 副作用。
4. 移动输入应留在 `MotionController` 和未来的 command sink 接口之后。Windows API、`pydirectinput`、focus 行为和点击诊断不能泄漏进导航逻辑。
5. 建图和定位共享图像识别与位移估计概念，但它们的有状态运行 facade 应分开。
6. probe 脚本应保持为生产算法/集成的验证适配器。
7. 不是每个模块都要拆。路径/寻路模块已经较内聚，后续最多整体归组到 `core/routing/`。

## 当前启动组合归属

已验证的启动链：

```text
main.py
  ├── configure_runtime_output()
  ├── hide_console_if_not_debugging()
  ├── set_process_dpi_awareness()
  ├── relaunch_as_admin()
  ├── acquire_single_instance_lock()
  ├── has_existing_main_window()
  └── main()
        ├── QApplication(sys.argv)
        └── MainWindow()
              ├── AppContext()
              │     ├── SquareScreenCapture()
              │     ├── HSVRecognizer()
              │     ├── MapStitcher(canvas_size=5000)
              │     ├── PlayerTracker()
              │     └── PathFinder()
              ├── MappingWidget(app_context, main_window)
              └── NavigationModeWidget(app_context, main_window)
```

重构方向：

- `main.py` 应变成短脚本，把进程 setup 委托给 bootstrap 模块，把 GUI 创建委托给 application 模块。
- `AppContext` 应成为显式组合根；如果它继续只是被动对象袋，应重命名或拆分。
- Mode widgets 后续应只接收自己需要的接口，而不是整个可变 context。

## 重构路线图

### Phase 0 - 测试护栏

大规模源码编辑前先做：

- 为 `core/routing/anchors/` 增加 ordered-anchor filtering、reached-anchor skipping、direct fallback、probe fallback 覆盖。
- 用 fake definition/detector/handler/memory timing 测 `EventCoordinator`。
- 用 fake tick/capture 测 `PortalEventHandler` 的 phase/state。
- 用 fake capture/recognizer/tracker/stitcher 测 `MappingSession.tick()`。
- 等 field specs 抽出成非 widget 数据后，再测 `NavParametersDialog` binding。
- 如果 mapping 地图点击继续支持，补 `ScalableMapWidget` 点击坐标映射测试。

### Phase 1 - 低风险深模块

这些已有测试或基本是纯逻辑：

- 共享 `estimate_phase_displacement()` 已抽到 `core/phase_displacement.py`；下一个低风险 core 抽取是 `WeightedMapMerger`。
- 从 `MapStitcher._merge_frame_weighted()` 抽 `WeightedMapMerger`。
- 只有在正好改 imports 时，把路径模块整体归组进 `core/routing/`。
- 已完成：`MotionController` 的 movement mapping、近目标精确点击和 bottom-click guard 纯计算已抽到 `core/motion_mapping.py`。
- 已完成：`NavParametersDialog` 点击半径数学已抽到 `gui/dialogs/nav_params/screen_estimator.py`。

### Phase 2 - 运行 facade

这些能降低 1000+ 行协调文件复杂度，同时不改算法：

- 给 navigation mode 增加幂等 `start_runtime()` / `stop_runtime()`。
- 从 `NavigationModeWidget._execute_navigation_intent()` 抽 `NavigationIntentExecutor`。
- 从 `MappingWidget.capture_and_process()` 抽 `MappingSession`。
- 抽 `NavigationConfigApplier`，负责把 `NavConfig` 应用到 `NavigationCore`、`PathFinder`、`MotionController` 和任务控制器。
- 从 navigation mode 抽 `EventPanelAdapter`。

### Phase 3 - 事件 hooks 和事件包

生命周期测试存在后再加扩展点：

- 引入观察型 `EventHookBus`。
- 触发 observe start/end、detector candidates、task selected、handler action、task completed/failed/ignored 等 hook。
- 除非明确需要 portal debug hook，否则不要在 portal 代码里加特殊 hook。
- 把 portal 默认值从 `core/events/config.py` 移到 event definition/registry。
- 把 `PortalEventHandler` 的字符串状态改成 phase enum + runtime dataclass。

### Phase 4 - GUI 表面清理

这些有价值，但应跟在运行提取之后：

- 把导航参数改成声明式 field specs + 通用 config binding。
- `EventManagerDialog` 基本保留，作为 schema-driven forms 的样板。
- 抽颜色选择器 preview mask/stats 和可控路径的 debug 输出。
- 颜色选择器 debug 输出路径已通过 `gui/dialogs/color_picker/debug_output.py` 显式化，并且现在由 `MINIMAP_COLOR_PICKER_DEBUG` 控制。
- 高级设置 JSON snapshot 已通过 `gui/dialogs/advanced_settings/file_io.py` 写入 `configs/advanced_settings/`，preset 值已进入 `advanced_settings/presets.py`；后续仍需处理 direct parent mutation 和 tab 拆分。
- 如果 `AdvancedSettingsDialog` 继续存在，停止直接修改 parent recognizer/stitcher。
- 根据 `ScalableMapWidget.pixel_clicked` 是否需要，修复或移除 mapping 全局地图点击行为。

### Phase 5 - 包组织

接口稳定后再移动文件：

```text
core/
├── mapping/
├── localization/
├── recognition/
├── routing/
├── input/
├── navigation_tasks/
└── events/

gui/
├── app/
├── modes/
│   ├── mapping/
│   └── navigation/
└── dialogs/
```

## 跨模块规则

- core 模块不能 import PySide widgets。
- event packages 不能直接执行鼠标/键盘输入；它们返回 actions/intents。
- navigation task 模块应输出 `NavigationIntent`，不调用 `MotionController`。
- GUI 模块可以把 signals、timers、widgets 适配到 core facades。
- probes 可以写文件和打印诊断，但 detector/planner/input 算法应留在生产模块里。
