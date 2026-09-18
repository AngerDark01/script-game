# GUI Modes 架构

## 系统角色

`gui/modes` 拥有两个主工作流：

- Mapping mode：选择截图区域或中心点，捕获 minimap frames，识别墙/雾/玩家，拼接并保存 map package。
- Navigation mode：加载 map package，定位玩家，编辑路线，运行导航任务，桥接事件系统并显示 overlays。

GUI modes 的职责是 Qt 控件、用户动作翻译、状态展示和与 core 系统包的组合；算法和平台副作用应留在 core 或明确的 adapter 中。

## 当前结构

```text
gui/modes/
├── mapping_widget.py              # MappingWidget 组合根
├── mapping/
│   ├── ui/layout.py                # control/display panel construction
│   ├── runtime/lifecycle.py        # monitoring command/timer lifecycle
│   ├── runtime/session.py          # capture -> recognize -> stitch tick
│   ├── capture/selection_controller.py
│   ├── io/config_store.py
│   ├── io/config_restore.py
│   ├── io/map_save.py
│   ├── params/binding.py
│   └── presentation/map_presenter.py
└── navigation/
    ├── widget.py                   # NavigationModeWidget 组合根和正式入口
    ├── ui/
    ├── map/
    ├── config/
    ├── route/
    ├── events/
    ├── hooks/
    ├── display/
    ├── runtime/
    ├── input/
    ├── presentation/
    └── calibration/
```

旧兼容壳已删除：`navigation_mode.py`、`mapping/save_load.py`、`mapping/params_adapter.py`、`navigation/map_runtime.py`、`navigation/route_overlay.py`、`navigation/event_overlay.py`、`navigation/viewport_overlay.py`、`event_test_controller.py`。

## Navigation Mode

详细拆分地图见 [navigation/ARCHITECTURE.md](navigation/ARCHITECTURE.md)。

当前真实入口是 `gui.modes.navigation.NavigationModeWidget`，由 `gui/main_window.py` 直接导入。导航页已经拆出 UI 构建、signal wiring、地图载入、配置生命周期、路线命令生命周期、事件弹窗/事件运行生命周期、hook 注册 runtime、显示 lifecycle、命令 lifecycle、事件 bootstrap、定位 tick、事件观察、任务 context 组装、runtime frame loop 和 intent consumption。

当前剩余热点不是单纯文件长度，而是少量 owner-based GUI composition/facade：

- `navigation/composition/lifecycles.py` 仍接收 `owner`，用于保持 lifecycle 构造顺序、Qt signal 前后依赖和 manual event test controller 绑定。
- `navigation/display/lifecycle.py` 仍接收 `owner`，因为它集中维护 scene item 引用写回、route/event overlay 清理和监控框/视野框刷新。
- `navigation/runtime/frame_loop.py` 仍接收 `owner`，因为整帧循环需要稳定读取 capture/localization/event/task/presentation/input targets；后续只有在依赖难以审计时再收窄为 targets DTO。

## Mapping Mode

`MappingWidget` 已经不再直接拥有区域/中心点选择 overlay 生命周期、capture timer 生命周期、配置 IO、地图包保存细节、参数控件绑定和 display 写入：

- `mapping/ui/layout.py` 承接控制面板滚动外壳、控制内容面板、显示面板、控件默认值和信号连接。
- `mapping/runtime/lifecycle.py` 承接监控启动/停止、capture timer 和 `app_context.monitoring` 状态。
- `mapping/runtime/session.py` 承接 capture-recognize-stitch tick。
- `mapping/capture/selection_controller.py` 承接截图区域/中心点选择、DPR 转换和 `AppContext` 写回。
- `mapping/io/config_store.py`、`config_restore.py`、`map_save.py` 承接配置与地图包保存。
- `mapping/params/binding.py` 承接控件到 recognizer/stitcher 参数的绑定。
- `mapping/presentation/map_presenter.py` 承接 capture/global map 展示写入。

`MappingWidget` 仍拥有保存时机、advanced settings dialog、路径预览和 topmost 状态。save-map 对话框/展示目前只有单一调用点，继续下沉收益不高；后续只有在保存反馈、批量地图管理或 profile/path 注入继续扩展时再拆，而不是重拆 runtime tick。

## 风险和规则

- 不按固定行数拆；只有当状态生命周期、复用边界或依赖方向变清晰时才拆。
- 新模块必须进入功能包，不在 `gui/modes` 根目录平铺 helper。
- GUI 新代码优先导入 core 系统包入口，不再使用旧 core 顶层文件。
- 旧 GUI 文件壳已经删除；后续删除 widget 内部 wrapper 前，先确认 signal 和外部调用点已迁移。

当前状态：本阶段已完成。Navigation 和 Mapping 的主要功能包已经成型；剩余 wrapper 均已按 public slot、Qt signal/timer 入口、lifecycle target 或顺序保护 facade 解释，不能按行数机械删除。后续新功能如果触碰 owner-based facade，再按 targets DTO 或 section builder 继续收窄。
