# GUI 架构

## 系统角色

`gui` 拥有 PySide6 widgets、用户工作流、timers、dialogs、overlays 和配置编辑。它应协调 core systems，但不应包含可复用算法。

## 当前模块地图

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `composition/paths.py` | GUI 项目根、`map_data`、根配置和高级参数目录解析。 | 已成为路径组合 seam；后续可由 AppContext 或 application composition 显式持有。 |
| `composition/services.py` | `CoreServices` DTO 和默认 core service 构造。 | 已让 AppContext 支持 service 注入；后续可扩展为完整 application composition。 |
| `app_context.py` | 持有共享 core services 和 monitor state。 | 已不直接构造 core service 细节；旧空 config hooks 已删除，后续如引入 profile/config 再新增真实实现。 |
| `main_window.py` | 顶层窗口、mode buttons、stacked pages、mode switching。 | 基本较薄；shutdown 时不应知道 timer internals。 |
| `navigation_params.py` | 导航配置和 runtime 参数模型。 | 稳定 config contract 候选；如果 GUI-free，可能放近 core。 |
| `modes/` | Mapping/navigation mode screens 和 helpers。 | 主要 controller/runtime/presenter seam 已成型；navigation hooks runtime 已独立为 `modes/navigation/hooks/`。 |
| `dialogs/` | 参数和工具对话框。 | 事件管理已新增独立 Hooks 页，具体面板在 `dialogs/event_manager/hooks/`；剩余大文件按 schema/form dialog 保留，触碰新功能时再拆 sections。 |
| `selection/` | 区域/中心选择 overlay 工具。 | GUI adapter components。 |
| `widgets/` | 可复用 PySide widgets。 | 活动 widget 包已归一；旧 `widgets_fixed.py` 备份已删除。 |

## 目标 GUI 拆分

```text
gui
├── composition
│   └── app_context / service creation
├── shell
│   └── main window and mode switching
├── modes
│   ├── mapping mode
│   └── navigation mode
├── dialogs
│   ├── parameter forms
│   ├── event manager
│   └── diagnostic tools
├── overlays
│   ├── screen selection
│   ├── map route overlay
│   └── event overlay
└── widgets
    └── reusable PySide components
```

## 主要重构原则

GUI 模块应翻译用户动作、渲染状态。Core 模块应拥有决策。如果某个 PySide 方法里包含 route selection、event scheduling、path planning 或 input policy，这个行为大概率放错了位置。

## 已验证启动归属

`MainWindow.__init__()` 当前：

1. 设置标题和默认 geometry。默认启动尺寸为 `1100x760`，避免单屏测试时主界面一开始占满屏幕；用户仍可手动拉大。
2. 创建 `AppContext(self)`。
3. 调用 `setup_ui()`。
4. 添加 `WindowStaysOnTopHint`。

`setup_ui()` 当前：

1. 创建 mapping/navigation mode buttons。
2. 创建 `QStackedWidget`。
3. 实例化 `MappingWidget(self.app_context, self)`。
4. 实例化 `NavigationModeWidget(self.app_context, self)`。
5. 默认 mapping mode。

`switch_mode(index)` 只切换 stacked widget，并在进入 navigation mode 时刷新地图列表。

`closeEvent()` 现在只调用 `MappingWidget.stop_runtime()` 和 `NavigationModeWidget.stop_runtime()`，不再知道 timer 或 toggle 命令细节。

## Composition Paths

`gui/composition/paths.py` 现在是 GUI 层项目路径的正式 seam：

- `project_root_from_file()` 从文件或目录向上查找同时包含 `main.py` 和 `gui/` 的项目根。
- `map_data_dir_from_file()`、`root_config_path_from_file()`、`root_config_path_from_map_folder()` 服务 mapping 和 navigation 配置链。
- `advanced_settings_dir_from_file()` 服务高级参数 snapshot 目录。

当前已迁移：

- `gui/modes/mapping/io/config_store.py`
- `gui/modes/navigation/map/config_store.py`
- `gui/dialogs/advanced_settings/file_io.py`

后续如果继续收窄组合根，应让 `AppContext` 或新的 application composition 显式持有这些 paths，而不是让 mode/helper 自行从 `__file__` 推导。

## Core Services Composition

`gui/composition/services.py` 现在集中默认 core service 构造：

- `CoreServices` 是 frozen dataclass，包含 `screen_capture`、`recognizer`、`stitcher`、`tracker`、`path_finder`。
- `create_core_services(canvas_size=5000)` 保持旧 `MapStitcher(canvas_size=5000)` 默认值。
- `AppContext(parent, services=...)` 支持注入 services；未注入时创建默认 services。

这让 `AppContext` 更接近显式 composition root，同时保留 `AppContext(self)` 的旧调用方式。

## Composition Root 建议

让 application composition 显式化：

```text
gui/app.py
  create_qapplication(argv)
  create_main_window(app_services)

gui/app_context.py
  AppContext dataclass/QObject with explicit fields
  receives CoreServices from gui/composition/services.py

gui/main_window.py
  only shell, mode switching, and shutdown delegation
```

首选 shutdown 接口：

```text
MappingWidget.stop_runtime()
NavigationModeWidget.stop_runtime()
```

这样 `MainWindow.closeEvent()` 可以停止工作流，而不需要知道 timers 或 navigation 当前是否运行。

## GUI 优化主计划

详细执行计划见 [GUI_OPTIMIZATION_PLAN.md](GUI_OPTIMIZATION_PLAN.md)。

全文件级审计与细化规划见 [GUI_FULL_FILE_OPTIMIZATION_PLAN.md](GUI_FULL_FILE_OPTIMIZATION_PLAN.md)。该文档逐个覆盖 `gui/` 下所有实现文件，记录每个文件的职责、深度、风险和后续拆分动作。

当前主线：

1. Shell 生命周期收口已完成：`MappingWidget.stop_runtime()`、`NavigationModeWidget.stop_runtime()`，`MainWindow.closeEvent()` 不再直接碰 timer 或调用 toggle 命令。
2. Navigation 的 input、config、route、events、presentation、map、calibration、runtime 小 seam 已经进入 `gui/modes/navigation/` 功能包，旧 `navigation_mode.py` 已删除。
3. Mapping 的 runtime session、runtime lifecycle、capture selection、map presenter、config store、config restore、map save、params binding、UI layout 已经进入 `gui/modes/mapping/` 功能包。
4. GUI composition 已新增 paths/services：路径解析集中到 `gui/composition/paths.py`，共享 core service 构造集中到 `gui/composition/services.py`。
5. Dialogs 已完成 nav params binding/specs、color picker preview/debug、advanced settings params/file_io/presets 的第一轮拆分；事件管理窗口新增“事件 / Hooks”分页，Hooks 页由 `dialogs/event_manager/hooks/panel.py` 承担。
6. Navigation 新增 `modes/navigation/hooks/registration.py`，负责把 `event_config.hooks.instances` 注册到 core hook registry，并通过现有 `MotionController` 边界执行 key_press hook。key_press 实例必须同时绑定事件类型 `event_types` 和触发时机 `triggers`，不会默认对所有事件触发。
7. 当前 core/gui 工程化优化阶段已完成：保留 `gui/modes/navigation/widget.py` 和 `gui/modes/mapping_widget.py` 作为 public composition roots，后续只在发现真实职责边界时继续拆，而不是恢复旧壳或按行数硬拆。

核心约束：

- 不按行数机械拆分。
- 新增模块必须落在功能 package 内，不做扁平 helper。
- 旧 GUI/core 顶层兼容壳已删除；保留的 package `__init__.py` 是正式系统入口，不是旧文件壳。

## 当前状态

状态：本阶段已完成。GUI 主要功能包已经成型，旧壳扫描清零；剩余 wrapper/owner 依赖都有保留理由，当前态文档已同步到验收标准。后续新功能开发时，先按本文件和 `OPTIMIZATION_EXECUTION_BASELINE.md` 的边界判断是否需要继续拆分。
