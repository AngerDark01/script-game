# 优化执行基准

本文是后续 core/gui 工程化优化的执行基准。后续新会话或上下文压缩后，先读本文，再读 `ARCHITECTURE_ITERATION_LOG.md` 最新一轮，然后继续执行。

本文优先级高于旧阶段计划。旧计划可作为背景，但后续判断以本文的阶段、准入条件和结束标准为准。

当前状态：本轮 core/gui 工程化优化阶段已完成。2026-05-28 验收中，旧壳/import、GUI 路径硬编码、当前态 stale 文档扫描均通过，并完成连续两轮无新增结构问题的 codebase 审计。后续开发新功能时以本文作为结构边界基线；hook 系统、算法阈值调优和更深 dialog section 拆分不属于本轮收尾范围。

## 1. 当前基线

已完成：

- 旧 core 顶层兼容壳已删除，实际实现侧不再依赖 `core.navigation_core`、`core.motion_controller`、`core.stitcher_core`、`core.pathfinder`、`core.route_manager`、`core.capture` 等旧路径。
- 旧 GUI 路径壳已删除，实际实现侧不再依赖 `gui.modes.navigation_mode`、`mapping.save_load`、`mapping.params_adapter`、`navigation.map_runtime`、`navigation.route_overlay`、`navigation.event_overlay`、`navigation.viewport_overlay`、`event_test_controller`、`widgets_fixed`。
- `core.__init__` 和 `gui.__init__` 只作为 package marker，不再做聚合导出。
- `NavigationModeWidget` 已从约 950 行收敛到约 420 行，保留组合根、Qt 入口和 wrapper 职责；生命周期组装已迁入 `gui/modes/navigation/composition/lifecycles.py`，整帧导航循环已迁入 `gui/modes/navigation/runtime/frame_loop.py`。
- `MappingWidget` 已完成 runtime session、runtime lifecycle、capture selection、IO、params binding、presentation 和 UI layout 初步拆分。
- 英文文档不再同步；只更新中文文档和 `CODEBASE.md`。
- 该优化验收阶段未包含 hook；当前后续阶段已在 core 侧新增 `event_visible_target` / `event_completed` 观察型 hook。

当前仍保留：

- GUI public class 入口：`gui.main_window.MainWindow`、`gui.app_context.AppContext`、`gui.modes.mapping_widget.MappingWidget`、`gui.modes.navigation.NavigationModeWidget`、各 dialog 主类。
- `NavigationModeWidget` 内部 wrapper：服务 Qt signal、timer、lifecycle targets 和外部调用稳定性。它们不是旧路径兼容壳，必须逐个确认调用方后再删除。
- 若干 owner-based composition/facade：`navigation/composition/lifecycles.py`、`navigation/runtime/frame_loop.py`、mapping restore/config helpers。后续目标是收窄依赖，不是机械消灭。

## 2. 后续工作优先级

### P0：守住旧壳清理成果

目标：

- 不允许重新引入旧 core/gui 文件路径壳。
- 不允许实现侧重新使用旧 import。

每轮都要扫描：

```powershell
rg -n "core\.(stitcher_core|pathfinder|navigation_core|motion_controller|capture|recognizer_optimized|tracker|route_manager|input_driver|navigation_obstacles|path_utils|anchor_path|motion_mapping|phase_displacement)|from core import|import core$" core gui main.py logging_system.py utils -g "*.py" --glob "!tests/**" --glob "!debug/**"

rg -n "navigation_mode|mapping\.save_load|mapping\.params_adapter|navigation\.map_runtime|navigation\.route_overlay|navigation\.event_overlay|navigation\.viewport_overlay|event_test_controller|widgets_fixed" gui main.py core utils -g "*.py" --glob "!tests/**" --glob "!debug/**"
```

要求：两个扫描均无命中。`rg` 返回码 1 代表无命中，是通过。

### P1：清理 GUI 内部过渡 wrapper

范围：

- `gui/modes/navigation/widget.py`
- `gui/modes/mapping_widget.py`
- dialog 主类中已经迁出实现的旧 wrapper

执行规则：

- 先用 `rg` 查 wrapper 的真实调用方。
- 如果只被同一个 owner 内部调用，且可直接改到 lifecycle/controller，则删除 wrapper。
- 如果被 Qt signal、timer、public class、lifecycle targets 或外部代码调用，先保留。
- 删除 wrapper 时不得改变信号顺序、timer 顺序、按钮 checked/text 状态、状态栏文案和真实输入调用顺序。

优先候选：

- `NavigationModeWidget` 中的展示 wrapper：只在 composition/frame loop 内使用时，可考虑把 targets 改到 display lifecycle。
- `NavigationModeWidget` 中的 route/event/config wrapper：只有 signal 仍依赖时保留；若 signal 可直连 controller/lifecycle，再删除。
- `MappingWidget` 中的 `save_config()`、`load_saved_params()`、`update_displays()`、capture selection wrapper：逐个确认是否还能直连 `mapping/io`、`mapping/presentation`、`mapping/capture`。

### P2：收窄 owner 依赖

范围：

- `gui/modes/navigation/composition/lifecycles.py`
- `gui/modes/navigation/runtime/frame_loop.py`
- `gui/modes/navigation/display/lifecycle.py`
- `gui/modes/mapping/io/config_restore.py`

目标：

- 把“拿整个 widget owner”逐步改成更窄的 targets DTO。
- 只在能减少隐藏依赖时做；如果只是把字段搬成更长参数列表，暂缓。

完成信号：

- frame loop 明确只依赖 capture/localization/event/task/presentation/input targets。
- composition module 能看出每个子系统的输入输出，不需要阅读整个 widget 才知道依赖。

### P3：GUI Shell 和 AppContext 组合根

范围：

- `gui/app_context.py`
- `gui/main_window.py`
- 未来 `gui/composition/`

目标：

- `AppContext` 从可变对象袋变为显式服务组合根。
- project root、map_data、config path 从各 helper 的 `__file__` 推导中逐步迁出。
- `MainWindow` 继续只知道 mode 生命周期协议，不知道子页面 timer 或内部 controller。

优先动作：

1. `[done]` 新增 `gui/composition/paths.py`，集中 project root、map_data、config 路径；mapping/navigation/advanced settings 已迁入该路径 seam。
2. `[done]` 新增 `gui/composition/services.py`，集中 `SquareScreenCapture`、`HSVRecognizer`、`MapStitcher`、`PlayerTracker`、`PathFinder` 构造；`AppContext` 支持注入 `CoreServices`。
3. 让 mapping/navigation config store 通过组合根接收路径，逐步减少 `Path(__file__).parents[n]`。

### P4：Mapping Mode 收口

范围：

- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/runtime/`
- `gui/modes/mapping/io/`
- `gui/modes/mapping/presentation/`

目标：

- 保留 `MappingWidget` public class。
- 继续把 UI layout、运行命令、保存反馈、参数应用时机拆成深模块。
- 不再新增旧 `mapping/save_load.py` 或 `mapping/params_adapter.py`。

优先动作：

- `[done]` 把 `MappingWidget` 的控制面板/display 面板构建迁入 `mapping/ui/layout.py`，形成清晰 UI shell，控件字段名和 signal 目标保持不变。
- `[done]` 把 start/stop/capture timer 生命周期迁入 `mapping/runtime/lifecycle.py`，保留 `toggle_monitoring()` / `stop_runtime()` 作为 public class 稳定入口。
- 把 map name 输入、保存成功/失败提示迁入 `mapping/presentation/save_state.py`。

### P5：Dialogs 收口

范围：

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/event_manager_dialog.py`

目标：

- `NavParametersDialog` 继续向 field specs + config binding 靠拢。
- `AdvancedSettingsDialog` 最终去掉 direct parent mutation fallback，只保留 command signal。
- `ColorPickerDialog` 保留交互状态，预览和 debug 输出留在 helper。
- `EventManagerDialog` 暂缓拆，作为 schema-driven 样板。

优先动作：

1. `NavParametersDialog`：把 tabs/sections 布局迁入 `nav_params/sections.py` 或 `widget_factory.py`。
2. `AdvancedSettingsDialog`：确认 `MappingWidget` 已覆盖所有应用入口后，删除 direct fallback。
3. `ColorPickerDialog`：继续拆 result packaging 或 player preview，只有出现真实复用时再抽。

### P6：Core 深层优化

这些不是当前 GUI 壳清理的下一刀，但属于后续主线。

优先候选：

- Route Progress / Guide Anchor 统一：`core/navigation_tasks/route_context.py`、`core/routing/anchors/`、`core/routing/geometry.py`。
- Localization Evidence / Coordinate Recovery：`core/localization/`、`core/navigation_tasks/coordinate/`、`core/shared/frame_registration.py`。
- Diagnostics 分层：短期继续复用 event log；只有导航/事件诊断都稳定复用后，再考虑 `core/diagnostics`。

规则：

- 不为了行数拆 core。
- 不混入阈值、算法调参和结构重构。
- core 不能 import PySide widget。
- navigation task 输出 intent，不直接执行真实输入。
- event handler 输出 action/intent，不直接调用 `MotionController`。

### P7：最后的兼容面收口

只有在 GUI、utils、main、logging_system 都稳定使用 canonical 包路径后才做。

当前旧路径壳已删除。最后阶段的重点不是再删旧文件，而是：

- 删除无人调用的内部 wrapper。
- 删除旧文档中的“保留壳子”表述。
- 删除旧注释和旧计划中已经不符合当前实现的段落。
- 保留正式 package `__init__.py`，因为它们是系统入口，不是旧壳。

## 3. 每轮执行流程

每一轮必须按这个顺序执行：

1. 在 `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md` 写 A 段，声明本轮目标、文件范围、预期影响。
2. 阅读目标文件、调用方、被调用方和本文件相关阶段。
3. 判断动作类型：
   - 删除 wrapper
   - 抽深模块
   - 收窄 owner 依赖
   - 只更新文档
   - 暂缓
4. 如果改实现：
   - 不改行为。
   - 不混入 hook。
   - 不改英文文档。
   - 不管 tests，除非用户重新要求；当前只验证实际实现侧。
5. 跑验证命令。
6. 更新 `CODEBASE.md` 和相关中文架构文档。
7. 在迭代日志写 C 段：发现、变更、验证、覆盖进度、下一轮计划。

## 4. 优化结束标准

只有全部满足，才能说“本阶段优化结束”。

### 4.1 旧壳和旧 import 清零

- 旧 core/gui 路径壳文件不存在。
- 旧 core/gui import 扫描无命中。
- `core.__init__`、`gui.__init__` 不恢复聚合导出。
- 新代码只用 canonical 包路径，例如 `core.localization`、`core.input`、`core.routing`、`gui.modes.navigation`。

### 4.2 组合根职责清楚

- `NavigationModeWidget` 只保留基础运行态字段、Qt 入口、public slots 和必要 wrapper；业务顺序在功能包中。
- `MappingWidget` 只保留控件组合、public slots 和必要 wrapper；capture/stitch/save/presentation 主流程在功能包中。
- `AppContext` 或其替代组合根负责创建共享服务，不让 mode 自己到处推导路径或构造底层服务。
- `MainWindow` 只依赖 mode 生命周期协议。

### 4.3 深模块边界稳定

每个系统至少满足：

- `core` 系统包职责清楚：platform、vision、mapping、localization、routing、input、navigation_tasks、events、shared。
- GUI 功能包职责清楚：navigation、mapping、dialogs、widgets/selection。
- 同名文件只表示包内角色，不表示重复；真正重复的契约才上移 shared。
- 任一剩余较长文件必须有明确理由：它是单一 pipeline、稳定 public class 或 schema-driven dialog，而不是混合职责。

### 4.4 内部 wrapper 有去留说明

- 无人调用的 wrapper 已删除。
- 仍保留的 wrapper 必须属于以下之一：
  - public class 外部入口
  - Qt signal/timer 入口
  - lifecycle target 稳定回调
  - 保持用户操作顺序的 facade
- 文档中必须说明为什么保留，不能只因为“先不动”。

### 4.5 owner 依赖可解释

- `composition` 和 `frame_loop` 如果仍持有 owner，必须在文档中说明原因和后续收窄方向。
- 如果 owner 访问已经变成隐藏依赖或难以审计，则必须进入 P2 收窄。

### 4.6 验证通过

最低实现侧验证：

```powershell
Get-ChildItem -Path core,gui,utils -Recurse -Filter *.py | Where-Object { $_.FullName -notlike '*\tests\*' -and $_.FullName -notlike '*\debug\*' } | ForEach-Object { D:\ACloud\.venv\Scripts\python.exe -m py_compile $_.FullName }
```

import smoke：

```powershell
D:\ACloud\.venv\Scripts\python.exe -c "import core, gui; from gui.main_window import MainWindow; from gui.modes.navigation import NavigationModeWidget; from gui.modes.navigation.runtime import NavigationRuntimeFrameLoop; from gui.modes.navigation.events import initialize_navigation_event_system; from core.platform import SquareScreenCapture; from core.vision import HSVRecognizer, PlayerTracker; from core.mapping import MapStitcher; from core.localization import NavigationCore; from core.routing import PathFinder, RouteManager; from core.input import MotionController; from core.navigation_tasks import NavigationTaskController, NavigationUpdateContext; from core.events.coordinator import EventCoordinator; from core.events.types.portal.handler import PortalEventHandler; assert not hasattr(core, 'ScreenCapture'); assert not hasattr(NavigationTaskController, 'update')"
```

旧壳扫描：

```powershell
rg -n "core\.(stitcher_core|pathfinder|navigation_core|motion_controller|capture|recognizer_optimized|tracker|route_manager|input_driver|navigation_obstacles|path_utils|anchor_path|motion_mapping|phase_displacement)|from core import|import core$" core gui main.py logging_system.py utils -g "*.py" --glob "!tests/**" --glob "!debug/**"

rg -n "navigation_mode|mapping\.save_load|mapping\.params_adapter|navigation\.map_runtime|navigation\.route_overlay|navigation\.event_overlay|navigation\.viewport_overlay|event_test_controller|widgets_fixed" gui main.py core utils -g "*.py" --glob "!tests/**" --glob "!debug/**"
```

用户侧 smoke：

- GUI 能启动。
- mapping 基本建图流程能启动/停止。
- navigation 能加载地图、显示地图、启动/停止导航。
- 用户已验证的功能不得回退。

### 4.7 文档同步完成

- `CODEBASE.md` 描述当前实现，不保留过期结论。
- 中文架构文档同步到本轮状态。
- `ARCHITECTURE_ITERATION_LOG.md` 每轮都有 A/C 段。
- 英文文档不要求同步。

### 4.8 连续两轮无新结构发现

最后收尾前必须连续两轮 codebase 审计满足：

- 无旧壳 import。
- 无可删除 wrapper。
- 无明显错误依赖方向。
- 无 stale docstring 或旧计划误导。
- 剩余长文件均有保留理由。

满足以上条件后，才可以宣布“当前 core/gui 工程化优化阶段结束”。

当前结果：已满足。`OPTIMIZATION-ACCEPTANCE-AUDIT-2` 与 `OPTIMIZATION-ACCEPTANCE-AUDIT-3` 连续两轮未发现新增结构问题；本轮优化阶段结束。

## 5. 不属于当前阶段的工作

- hook 系统设计与实现。
- 算法阈值调优。
- 重写业务流程。
- 大规模补测试。
- 英文文档同步。
- 为了行数继续切文件。

这些可以后续开新阶段讨论。

