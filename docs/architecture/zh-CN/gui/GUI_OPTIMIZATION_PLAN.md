# GUI 优化计划

补充说明：逐文件审计、每个模块的细化判断和执行历史见 [GUI_FULL_FILE_OPTIMIZATION_PLAN.md](GUI_FULL_FILE_OPTIMIZATION_PLAN.md)。本文只保留当前主线和下一步计划。

## 目标

- GUI 只负责用户动作翻译、Qt widget 生命周期、状态展示和与 core 系统包组合。
- core 继续负责定位、路径、事件调度、输入映射、地图拼接等业务决策。
- 拆分按系统/模块/组件进行，不按固定行数机械切。
- 新模块进入功能包目录，不在 `gui/modes` 或 `gui/dialogs` 根目录平铺 helper。
- 旧 GUI 兼容壳已删除，后续外部入口以 package 入口为准。

## 当前系统

| 系统 | 当前入口 | 已拆模块 | 剩余问题 |
| --- | --- | --- | --- |
| Shell / Composition | `gui/main_window.py`、`gui/app_context.py`、`gui/composition/` | `AppContext` 已支持 `CoreServices` 注入；路径解析集中到 `composition/paths.py`；`MainWindow` 直接导入 canonical mode 入口。 | `AppContext` 仍是可变服务袋，后续如引入 profile/config 可继续显式化。 |
| Navigation Mode | `gui/modes/navigation/widget.py`、`gui/modes/navigation/` | UI、map、config、route、events、display、runtime、input、presentation、calibration、composition 均已拆功能包；整帧循环已进 `runtime/frame_loop.py`。 | 剩余 owner-based display/composition/frame-loop facade 有保留理由，后续只在依赖难审计时收窄 targets。 |
| Mapping Mode | `gui/modes/mapping_widget.py`、`gui/modes/mapping/` | runtime session/lifecycle、capture selection、IO/config restore、map save、params binding、presentation presenter、UI layout 已拆。 | 保存时机、advanced settings、路径预览和 topmost 状态仍在 widget；当前作为 public composition root 保留。 |
| Dialogs | `gui/dialogs/*` | nav params field specs/config binding/screen estimator、advanced settings params/file_io/presets、color picker hsv/preview/debug/image renderer 已拆。 | 大 dialog class 主要承担 schema/form layout 组装；新功能触碰时再拆 section，不作为当前验收阻塞。 |
| Shared Widgets | `gui/widgets/`、`gui/selection/` | 旧 `widgets_fixed.py` 已删除。 | 短期只修明确行为缺口。 |

## 已完成的壳清理

- GUI 旧壳已删除：`gui/modes/navigation_mode.py`、`gui/modes/mapping/save_load.py`、`gui/modes/mapping/params_adapter.py`、`gui/modes/navigation/map_runtime.py`、`gui/modes/navigation/route_overlay.py`、`gui/modes/navigation/event_overlay.py`、`gui/modes/navigation/viewport_overlay.py`、`gui/modes/event_test_controller.py`、`gui/widgets_fixed.py`。
- `main.py` 直接导入 `gui.main_window.MainWindow`。
- `gui/__init__.py` 不再 re-export `MainWindow`。
- GUI 实现侧已不再导入旧 core 顶层壳；核心服务从 `core.platform`、`core.vision`、`core.mapping`、`core.localization`、`core.routing`、`core.input` 导入。

## 当前结果

当前 core/gui 工程化优化阶段已完成。验收审计确认：

1. 旧 core/gui 壳和旧 import 扫描无命中。
2. GUI 路径硬编码扫描无命中。
3. 剩余 wrapper 均有 public slot、Qt signal/timer、lifecycle target 或顺序保护 facade 的保留理由。
4. 剩余长文件均解释为 schema/form dialog、public composition root 或数据规格表。
5. 连续两轮 codebase 审计未发现新增结构问题。

## 后续触发式拆分

新功能开发时，如果触碰到这些区域，再优先收窄：

1. `navigation/runtime/frame_loop.py` 的 owner targets。
2. `navigation/display/lifecycle.py` 的 scene item targets。
3. `navigation/composition/lifecycles.py` 的生命周期构造 targets。
4. `NavParametersDialog` layout sections。
5. `AdvancedSettingsDialog` tab construction。
6. `ColorPickerDialog` 点位状态和 accept/reject flow。
7. Mapping save-map presentation。

## 暂不做

- Hook 不再属于 GUI/模块化验收阻塞项；当前后续功能阶段已新增事件 Hooks 页和 `NavigationHookRuntime`，可把 key_press 实例绑定到具体事件类型，并挂到 `event_visible_target` / `event_completed`。
- 不改 core 算法阈值和业务策略。
- 不动 tests 目录。
- 不为压行数而拆 runtime loop。
- 不恢复旧兼容壳；后续只保留真正有价值的 package `__init__.py` 入口。

## 验证策略

每轮至少执行：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile <本轮修改的 gui/core 文件>
```

实现侧 import 扫描应保持：

- 旧 GUI wrapper import 为 0。
- 旧 core 顶层 wrapper import 为 0。
- `from core import ...` 为 0。

当前状态：本阶段已完成。Navigation 和 Mapping 的主要功能包拆分已完成，旧 GUI 壳已删除；后续新功能触碰到真实边界时再做触发式拆分。

