# Architecture Iteration Log

## [2026-09-24] PoE2 首帧业务门槛边界

- 业务适配层 `features/poe2/.../composition.py` 负责 PoE2 的 75% 锚定接受政策；通用 `AnchoredRegistrationConfig` 仍保持 `minimum_confidence=0`、`minimum_score=0.50`、普通 coverage=0.65 的默认契约。
- `minimum_score_when_anchored` 是可选窄接口：只有可信 memory anchor 且 `player_on_walkable` 时才替换 image-only score gate；它不改变无锚点候选、错误实例或普通局部跟踪的规则。
- 诊断数据必须同时记录 confidence、score、coverage、anchor_error、角度、镜像和比例，防止把低视觉分数误报为内存位置错误。

## [SYNC] 2026-09-18 20:39 - 统一事件运行时与工作台边界收口

### A. SYNC 范围声明
**触发任务：** 以已实机验证的 `known-good/event-runtime-2026-09-18` 为基线，将本机事件、远程事件、目录同步与直接发送合并到统一服务，迁移 GUI 后删除四套平行旧实现。

**直接变更文件：**
- `core/events/automation/{__init__,definitions,routes,execution}.py`
- `core/runtime/event_service/{__init__,models,host_bridge,hotkeys,service}.py`
- `gui/modes/events/workbench.py`
- `tests/test_event_{definition_repository,routes,execution_runtime,workbench_ui}.py`
- `core/runtime/tests/test_event_{host_bridge,hotkeys,workbench_service}.py`
- 删除 `core/runtime/{local_event_runtime,remote_event_runtime,event_catalog_runtime,remote_event_sender}.py`
- 删除 `core/runtime/tests/{test_remote_event_delivery,test_event_catalog_runtime}.py`
- `docs/plans/2026-09-18-unified-event-runtime-{design,implementation}.md`

**预计连带影响：** `EventStore` / `EventRecord` 的版本身份契约、`EventSession` 与 XInput 状态输出链、Host/LAN 的 `event.*` 和 `sync.share.*` 协议、GUI 关闭流程、事件模块架构图与相关测试覆盖说明。

### C. SYNC 结果

**关键发现：**

- (verified) 本机和远程事件现在只通过 `EventDefinitionRepository` 解析，执行只通过按 `(source, controller)` 隔离的 `EventExecutionRuntime`；纯 automation 模块没有 PySide、ctypes、Host client 或协议命令依赖。
- (verified) `EventWorkbenchService` 是唯一长期 worker/composition owner；目录 drain 与事件 drain 独立，A -> B/C fanout 隔离单 peer 失败，直接发送使用 Host clock deadline。
- (verified) `EventWorkbenchPage` 只保存 widget 草稿并调用服务，不再读写 JSON/日志、创建 client 或管理三套后台 runtime。
- (verified) Host 揭示真实 device ID 后，本机 catalog owner 会重绑而不改变 ID/revision；删除本机事件会产生同 ID、revision+1 的 tombstone，并在远端应用后隐藏旧记录。
- (verified) 四个旧 runtime/sender 文件和两个绑定旧实现的测试已删除；源码和测试中旧类名/模块名引用为零。
- (verified, P2) `EventWorkbenchService.tick_once()` 当前仍在服务锁内执行同步 bridge IO；Host 阻塞时 GUI status/save 可能等待该锁，已登记为后续并发优化风险。

**修订的旧结论：** 2026-09-17 review 记录的三个事件工作台边界风险已解决，不再是“建议提取统一仓库/执行器/服务”；当前事实是统一模块已经落地，旧平行实现已删除。

**连带重读文件：** `core/events/event_store.py`、`core/events/event_catalog.py`、`core/runtime/event_session.py`、`core/events/gamepad_output.py`、`gui/main_window.py` 以及 Host bridge/service 的调用方与测试。

**CODEBASE.md 更新内容：** §2 新增逐文件目录说明；§3 新增 action-event Level 3 图；§4 新增纯模块、平台服务、GUI 与测试独立小节；§5 补齐关键函数签名/算法/失败行为；§6 新增保存、本机触发、A->B/C、直接发送四条完整 Flow；§7 记录 Host/LAN/文件/热键集成；§8 补齐 DTO 和 wire payload；§9 将三个旧风险标记 resolved，并登记锁内 IO 风险。

**同步文档：** `ARCHITECTURE_GUIDE.md`、`core/ARCHITECTURE.md`、`core/events/ARCHITECTURE.md`、`gui/ARCHITECTURE.md`、`tests/ARCHITECTURE.md`、`CODEBASE.md`。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
| --- | --- | --- | ---: | --- |
| `core/events/automation/__init__.py` | 新增 | 深度完整 | 1 | 确认只聚合纯定义/路由/执行类型，不导出平台 adapter。 |
| `core/events/automation/definitions.py` | 新增 | 深度完整 | 4 | 逐分支核对 parse、版本判定、owner 重绑、legacy identity fallback 与 tombstone 发布。 |
| `core/events/automation/routes.py` | 新增 | 深度完整 | 2 | 核对中英文 endpoint/controller 规范化、文件失败行为和纯 dispatch 过滤。 |
| `core/events/automation/execution.py` | 新增 | 深度完整 | 2 | 核对 session key、定义替换、source cancel neutral frame 与完整 tick state。 |
| `core/events/event_store.py` | 深度完整 | 深度完整 | 2 | 新增 `local_catalog()`，确认活动视图和含 tombstone catalog 视图分离。 |
| `core/runtime/event_service/__init__.py` | 新增 | 深度完整 | 1 | 确认 public service/adapter/status 导出。 |
| `core/runtime/event_service/models.py` | 新增 | 深度完整 | 2 | 核对 trigger/bridge Protocol 全方法和 immutable status 字段。 |
| `core/runtime/event_service/host_bridge.py` | 新增 | 深度完整 | 2 | 核对七个 wire command、payload 字段、独立 drain 和幂等 close。 |
| `core/runtime/event_service/hotkeys.py` | 新增 | 深度完整 | 2 | 核对 VK 表、按下边沿、松开重装、未知键与非 Windows failure。 |
| `core/runtime/event_service/service.py` | 新增 | 深度完整 | 4 | 沿 save/direct send/tick/catalog/local dispatch/fanout/receive/cleanup 完整调用链复核。 |
| `gui/modes/events/workbench.py` | 浅读 | 深度完整 | 3 | 核对所有数据加载/保存/启停/发送/日志/关闭只通过注入服务。 |
| `tests/test_event_definition_repository.py` | 新增 | 深度完整 | 4 | 覆盖 identity、revision、owner、draft、fallback、tombstone 和远端隐藏。 |
| `tests/test_event_routes.py` | 新增 | 深度完整 | 1 | 覆盖 round-trip、dispatch 与非法 route 参数表。 |
| `tests/test_event_execution_runtime.py` | 新增 | 深度完整 | 1 | 覆盖 source/controller、snapshot、cancel 和 validation。 |
| `tests/test_event_workbench_ui.py` | 浅读 | 深度完整 | 2 | 假服务覆盖 UI-only boundary，并断言临时 root 无文件写入。 |
| `core/runtime/tests/test_event_host_bridge.py` | 新增 | 深度完整 | 1 | 精确断言命令序列与 payload。 |
| `core/runtime/tests/test_event_hotkeys.py` | 新增 | 深度完整 | 1 | 覆盖全部 UI key names 和 edge 行为。 |
| `core/runtime/tests/test_event_workbench_service.py` | 新增 | 深度完整 | 3 | 覆盖共享执行、catalog、fanout、source clear、deadline、draft/log/shutdown。 |

**新增 Finding：** P2 - service worker 在锁内执行同步 Host/LAN IO，后续应以不可变 tick snapshot 或 command queue 缩短临界区，并先增加阻塞 fake bridge 的并发测试。

**验证结果：**

- `python -m pytest core/events/tests core/runtime/tests tests/test_action_tracks.py tests/test_event_session.py tests/test_event_lifecycle.py tests/test_event_gamepad_output.py tests/test_event_button_chords.py tests/test_event_definition_repository.py tests/test_event_routes.py tests/test_event_execution_runtime.py tests/test_event_workbench_ui.py -q` -> `67 passed in 0.99s`。
- 旧 runtime/sender 名称搜索 -> 生产源码和测试零命中；架构文档只保留“已删除”说明。
- `core/events/automation` 平台/协议依赖搜索 -> 零命中。
- `gui/modes/events/workbench.py` JSON/Host/旧 runtime/文件 IO 搜索 -> 零命中。
- `python -m compileall -q core/events/automation core/runtime/event_service gui/modes/events ...` -> 成功。
- `git diff --check` -> 无 whitespace error，仅显示 Windows checkout 的 LF->CRLF 提示。
- `dotnet test virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj --no-restore` -> 未执行测试：本机 `dotnet --info` 显示只有 .NET 6 runtime，`No SDKs were found`；未安装 SDK，亦未启动真实 Host/LAN。

**下一轮计划：** 在具备 .NET SDK 的环境补跑 Host/LAN C# 回归；如处理新增并发风险，先加入阻塞 fake bridge 测试再缩短 service 锁临界区。本轮未发送真实输入、未启动真实同步。

This log follows the iterative reading discipline from the codebase workflow: declare scope before reading, read a small set of files, then record findings and the next round.

## [Round 1] 2026-05-26 - Structure, Scale, and Documentation Skeleton

### A. Round Goal

Target files and sources:

- `CODEBASE.md` - coarse read only, used as current-state index.
- `README.md` and `requirements.txt` - confirm project purpose and stack.
- Python file list and line counts - identify large-file split candidates.
- Existing docs search - avoid overwriting existing architecture artifacts.

Questions for this round:

- What are the top-level systems?
- Which files are immediately too large or too mixed in responsibility?
- Where should module-owned documentation live?
- Which modules should be read in Round 2?

### C. Findings

Key findings:

- (verified) The application is a PySide6 + OpenCV desktop tool for minimap stitching, navigation localization, path planning, event handling, and real input execution.
- (verified) Existing `CODEBASE.md` is useful current-state material, but it is a single large encyclopedia. The new documentation should be module-owned and refactor-oriented.
- (verified) The largest file is `gui/modes/navigation_mode.py` at 1525 lines. It is the first large-file split candidate because it mixes GUI construction, map loading, route editing, navigation loop, event integration, overlay rendering, and input-window behavior.
- (verified) Other high-friction files by size include `gui/dialogs/nav_params_dialog.py` at 771 lines, `core/stitcher_core.py` at 647 lines, `gui/dialogs/advanced_settings_dialog.py` at 629 lines, `core/navigation_core.py` at 611 lines, and `core/navigation_tasks/controller.py` at 567 lines.
- (verified) The codebase already has partial modularization around `core/events`, `core/navigation_tasks`, `gui/modes/navigation`, and `gui/modes/mapping`; the refactor should deepen these modules rather than invent unrelated structure.
- (verified) Working tree has existing modified source files. This architecture pass will avoid source edits unless explicitly requested.

Updated documents:

- `ARCHITECTURE_GUIDE.md`
- `core/ARCHITECTURE.md`
- `core/navigation_tasks/ARCHITECTURE.md`
- `core/events/ARCHITECTURE.md`
- `core/events/types/portal/ARCHITECTURE.md`
- `gui/ARCHITECTURE.md`
- `gui/modes/ARCHITECTURE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `utils/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| Project structure | PENDING | shallow | 1 | File list, existing docs, requirements, and current CODEBASE index reviewed. |
| Entry/runtime startup | PENDING | PENDING | 0 | Planned for Round 2 with `main.py`, `gui/app_context.py`, `gui/main_window.py`. |
| Navigation mode | PENDING | shallow | 1 | Only line count and existing CODEBASE summary reviewed; function bodies not yet read. |
| Mapping core | PENDING | shallow | 1 | Identified as system; algorithm details not yet read. |
| Navigation tasks | PENDING | shallow | 1 | Identified as reusable orchestration candidate; function bodies not yet read. |
| Event system | PENDING | shallow | 1 | Identified hook candidate; function bodies not yet read. |
| Portal event | PENDING | shallow | 1 | Identified as first concrete event adapter; function bodies not yet read. |
| GUI dialogs | PENDING | shallow | 1 | Large files identified; dialog behavior not yet read. |
| Probe scripts | PENDING | shallow | 1 | Identified as diagnostics/verification layer; not yet read. |
| Tests | PENDING | shallow | 1 | Test files listed; assertions not yet read. |

Next round plan:

- Read startup and ownership path: `main.py`, `gui/app_context.py`, `gui/main_window.py`.
- Produce concrete startup/system ownership notes in `gui/ARCHITECTURE.md` and `core/ARCHITECTURE.md`.
- Decide whether `AppContext` is deep enough or should become a formal application composition module.

## [Round 2] 2026-05-26 - Startup and Composition Ownership

### A. Round Goal

Target files:

- `main.py` - process setup, runtime output, admin relaunch, single-instance guard, QApplication startup.
- `gui/app_context.py` - shared core object composition.
- `gui/main_window.py` - top-level GUI ownership and mode switching.

Questions for this round:

- Where is the true application composition root?
- Which core systems are constructed eagerly and shared?
- Does startup logic mix platform setup, logging, process control, and GUI boot enough to need extraction?
- Does the GUI shell own mode lifecycle cleanly?

### C. Findings

Key findings:

- (verified) `main.py` owns several process/platform responsibilities before GUI creation: UTF-8/log redirection, optional console hiding, DPI awareness, UAC relaunch, python/pythonw choice, single-instance mutex, old-window detection, and QApplication startup.
- (verified) The current startup chain is `main.py -> QApplication -> MainWindow -> AppContext -> core service instances -> MappingWidget/NavigationModeWidget`.
- (verified) `AppContext` constructs `ScreenCapture`, `HSVRecognizer`, `MapStitcher(canvas_size=5000)`, `PlayerTracker`, and `PathFinder` eagerly, and also stores mutable monitor state.
- (verified) `AppContext.load_global_config()` and `save_global_config()` are placeholders, so configuration ownership is currently not centralized there.
- (verified) `MainWindow` is mostly a thin shell, but `closeEvent()` reaches into `mapping_widget.capture_timer` and calls `nav_widget.toggle_navigation()`. That is a weak shutdown interface because the shell knows implementation details and uses a toggle instead of an idempotent stop command.
- (inferred) `main.py` should be split before major GUI refactors so process bootstrap does not obscure application composition.

Updated documents:

- `ARCHITECTURE_GUIDE.md` - added verified composition ownership.
- `gui/ARCHITECTURE.md` - added startup ownership and shutdown recommendation.
- `core/ARCHITECTURE.md` - added package export/composition note.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `main.py` | PENDING | partial | 1 | Read full file; process bootstrap responsibilities identified, but no refactor patch planned yet. |
| `gui/app_context.py` | PENDING | partial | 1 | Read full file; eager core service composition and placeholder config hooks identified. |
| `gui/main_window.py` | PENDING | partial | 1 | Read full file; shell mostly thin, shutdown interface is brittle. |
| `core/__init__.py` | PENDING | partial | 1 | Read full file; current top-level core exports identified. |
| `gui/__init__.py` | PENDING | partial | 1 | Read full file; exports `MainWindow` only. |

Next round plan:

- Read method grouping in `gui/modes/navigation_mode.py` without trying to document every line yet.
- Produce a concrete split map for `navigation_mode.py` by responsibility and extraction order.
- Confirm which helper modules already cover parts of the split and which responsibilities remain in the 1525-line widget.

## [Round 3] 2026-05-26 - Navigation Mode Large-File Split Map

### A. Round Goal

Target file:

- `gui/modes/navigation_mode.py` - method grouping and responsibility boundaries.

Supporting files if needed:

- `gui/modes/navigation/map_runtime.py`
- `gui/modes/navigation/route_overlay.py`
- `gui/modes/navigation/event_overlay.py`
- `gui/modes/navigation/viewport_overlay.py`
- `gui/modes/navigation/event_adapter.py`

Questions for this round:

- Which responsibilities are still inside the 1525-line widget?
- Which responsibilities already have helper modules?
- What is the safest extraction order?
- What public methods should remain on `NavigationModeWidget` after extraction?

### C. Findings

Key findings:

- (verified) `gui/modes/navigation_mode.py` is 1525 lines by `Measure-Object -Line`.
- (verified) The widget still owns QWidget construction, route editing, map loading, config application, event dialog wiring, event system initialization, manual portal test control, map rendering, viewport overlay updates, navigation timer control, runtime tick logic, and real input intent execution.
- (verified) Existing helper modules already cover some pure helper behavior: `map_runtime.py` for map/config/capture geometry, `route_overlay.py` for route drawing, `event_overlay.py` for event drawing, `viewport_overlay.py` for rectangle geometry, and `event_adapter.py` for event registry/tick/status helpers.
- (verified) `_navigation_loop_unified()` is the highest coupling method: it captures frames, detects player-local position, localizes globally, observes events, refreshes event dialog tasks, calls `NavigationTaskController.update()`, updates player/viewport overlays, formats status text, forces relocalization, executes navigation intents, and handles terminal arrival/failure.
- (verified) `_execute_navigation_intent()` is a good extraction target because it is the only place that translates `NavigationIntentType` into `MotionController` calls and controller click recording.
- (verified) `_set_game_input_window_mode()` is a small, low-risk GUI-specific extraction target because it only mutates main-window topmost/lower behavior.
- (verified) Route editing has a clean command cluster around `RouteManager` and scene-click conversion; it can become `route_editor.py`.
- (inferred) The safest first source change later is adding `start_runtime()` / `stop_runtime()` methods before extracting modules, because current `MainWindow.closeEvent()` calls `toggle_navigation()` and can accidentally start navigation if state and button are inconsistent.

Updated documents:

- `gui/modes/navigation/ARCHITECTURE.md` - detailed split map and extraction order for `navigation_mode.py`.
- `gui/modes/ARCHITECTURE.md` - linked detailed split map.
- `ARCHITECTURE_GUIDE.md` - linked detailed split map.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/modes/navigation_mode.py` | shallow | partial | 1 | Method groups and major branches read; branch-level algorithm details still pending. |
| `gui/modes/navigation/map_runtime.py` | shallow | partial | 1 | Full file read; already good helper for map/config/capture geometry. |
| `gui/modes/navigation/event_adapter.py` | shallow | partial | 1 | Full file read; event registry/tick/status helpers identified. |
| `gui/modes/navigation/route_overlay.py` | shallow | partial | 1 | Full file read; route drawing helper identified. |
| `gui/modes/navigation/event_overlay.py` | shallow | partial | 1 | Full file read; event overlay drawing helper identified. |
| `gui/modes/navigation/viewport_overlay.py` | shallow | partial | 1 | Full file read; viewport rectangle geometry helper identified. |

Next round plan:

- Read `core/navigation_tasks/models.py`, `controller.py`, and `movement_executor.py`.
- Produce a system-level interface proposal for `NavigationTaskController` and identify which GUI responsibilities can move into navigation-task adapters.
- Check whether event hooks belong in `core/events`, `core/navigation_tasks`, or a bridge between them.

## [Round 4] 2026-05-26 - Unified Navigation Task System Interface

### A. Round Goal

Target files:

- `core/navigation_tasks/models.py`
- `core/navigation_tasks/controller.py`
- `core/navigation_tasks/movement_executor.py`
- `core/navigation_tasks/scheduler.py`
- `core/navigation_tasks/task_builder.py`
- `core/navigation_tasks/route_context.py`

Questions for this round:

- What is the real public interface of the unified navigation task system?
- Which parts are reusable core modules and which are GUI/event adapters?
- Where should event hooks connect without coupling event packages to navigation UI?
- Which responsibilities in `controller.py` should be split first?

### C. Findings

Key findings:

- (verified) `models.py` provides stable DTOs and enums: `NavigationTaskKind`, `NavigationTaskState`, `NavigationIntentType`, `RouteProjection`, `RouteAnchor`, `NavigationTask`, `MovementStep`, and `NavigationIntent`.
- (verified) `NavigationTaskController.update()` has a wide keyword-only interface called directly from the GUI runtime loop. It requires localization, route, event coordinator/tick, map layers, pathfinder, timing, manual event mode, and frame registration.
- (verified) `NavigationTaskController.update()` mixes multiple phases: route reload, active-state guard, localization filtering, coordinate diagnostics, relocalization recovery, required-point completion, task building, task scheduling, task transition handling, event task running, static task running, and intent creation.
- (verified) `NavigationTaskBuilder`, `NavigationTaskScheduler`, `RouteContext`, `MovementExecutor`, and `CoordinateDiagnostics` are already reasonably deep modules with distinct responsibilities.
- (verified) `EventApproachController` is a navigation-layer gate before an event handler can trigger; it uses visibility/settling/movement policy and emits `NavigationIntent`. It should not move into a concrete event package, but event packages may later provide approach preferences.
- (verified) `MovementExecutor` centralizes A*/anchor/fallback planning, lookahead subgoal selection, click throttling, exact path-goal click decisions, stuck detection, and recovery probes. It is a strong reusable component and should stay under navigation tasks or route movement.
- (inferred) The next controller refactor should introduce `NavigationUpdateContext` rather than immediately splitting behavior. Grouping parameters first will shrink the GUI dependency surface and make tests easier.
- (inferred) Event hooks should be split by layer: detection/handler hooks in `core/events`, route/task hooks in `core/navigation_tasks`, and cross-system translation hooks in an event-task runner adapter.

Updated documents:

- `core/navigation_tasks/ARCHITECTURE.md` - expanded with verified interface, controller algorithm, split plan, update context proposal, and hook placement.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/navigation_tasks/models.py` | shallow | partial | 1 | Full file read; DTO contract identified. |
| `core/navigation_tasks/controller.py` | shallow | partial | 1 | Full file read; phase-level algorithm and split points identified. |
| `core/navigation_tasks/movement_executor.py` | shallow | partial | 1 | Full file read; reusable movement component identified. |
| `core/navigation_tasks/scheduler.py` | shallow | partial | 1 | Full file read; route/event selection policy identified. |
| `core/navigation_tasks/task_builder.py` | shallow | partial | 1 | Full file read; unified task composition identified. |
| `core/navigation_tasks/route_context.py` | shallow | partial | 1 | Full file read; route projection/corridor anchor behavior identified. |
| `core/navigation_tasks/event_approach.py` | shallow | partial | 1 | Full file read; navigation-layer event approach gate identified. |
| `core/navigation_tasks/coordinate_diagnostics.py` | shallow | partial | 1 | Full file read; diagnostics/relocalization request role identified. |

Next round plan:

- Read `core/events/models.py`, `coordinator.py`, `memory.py`, `monitor.py`, `runner.py`, and `scheduler.py`.
- Define event system lifecycle hooks and decide what should be core hook, debug hook, GUI adapter, or event package adapter.
- Then read portal event package as the first concrete event package implementation.

## [Round 5] 2026-05-26 - Event System Lifecycle and Hooks

### A. Round Goal

Target files:

- `core/events/models.py`
- `core/events/coordinator.py`
- `core/events/monitor.py`
- `core/events/memory.py`
- `core/events/scheduler.py`
- `core/events/runner.py`
- `core/events/registry.py`
- `core/events/config.py`
- `core/events/base/*.py`

Questions for this round:

- What is the real event lifecycle from detection to action?
- Which interfaces are already generic enough for reusable events?
- Where should hooks live?
- Which current responsibilities should be adapters: debug logging, GUI overlay, config IO, capture/window access?

### C. Findings

Key findings:

- (verified) Event lifecycle is two-phase. `EventCoordinator.observe()` detects/stabilizes/merges event tasks but does not execute handlers. `EventCoordinator.run_task()` executes a selected task only when navigation chooses it.
- (verified) `EventDefinition`, `EventDetector`, and `EventHandler` are minimal and useful event package seams.
- (verified) `EventMemory` owns task lifecycle policy: dedupe, confirm frames, cooldown, retry, ignore, teleport session completion, and nearby suppression. It should remain deep and tested before splitting.
- (verified) `EventRunner` is the seam from generic event runtime to concrete handler actions. It starts handlers, updates them, applies complete/fail behavior to memory, and returns `EventAction`.
- (verified) `EventMonitor` lazily creates one detector per enabled event definition and caches detectors by event type.
- (verified) `overlay_models.py` is a core-safe DTO adapter; PySide rendering remains in `gui/modes/navigation/event_overlay.py`.
- (verified) `capture_provider.py` is already an adapter boundary for handlers needing minimap or full game-view captures.
- (verified) `core/events/config.py` currently embeds portal-specific defaults in the event core. This is a coupling point; defaults should eventually come from `EventDefinition.default_config()` through the registry.
- (inferred) Hooks should be implemented as an injected hook bus/listener, not as many optional methods on `EventDefinition`.
- (inferred) Initial hooks should be observational only. Control-changing hooks can come later after lifecycle tests exist.

Updated documents:

- `core/events/ARCHITECTURE.md` - expanded with verified lifecycle, hook bus proposal, adapter boundaries, memory/runner policy, and config coupling warning.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/events/models.py` | shallow | partial | 1 | Full file read; event DTO/action/task model identified. |
| `core/events/coordinator.py` | shallow | partial | 1 | Full file read; observe/run phases identified. |
| `core/events/monitor.py` | shallow | partial | 1 | Full file read; detector cache and enabled definitions identified. |
| `core/events/memory.py` | shallow | partial | 1 | Full file read; lifecycle policy identified. |
| `core/events/runner.py` | shallow | partial | 1 | Full file read; handler execution seam identified. |
| `core/events/scheduler.py` | shallow | partial | 1 | Full file read; display/status task selection identified. |
| `core/events/registry.py` | shallow | partial | 1 | Full file read; event definition registry identified. |
| `core/events/config.py` | shallow | partial | 1 | Full file read; portal-default coupling identified. |
| `core/events/base/*.py` | PENDING | partial | 1 | Base definition/detector/handler interfaces read. |
| `core/events/overlay_models.py` | shallow | partial | 1 | Full file read; core-safe overlay DTO identified. |
| `core/events/capture_provider.py` | shallow | partial | 1 | Full file read; handler capture adapter identified. |

Next round plan:

- Read portal event package as the first concrete event implementation.
- Identify which portal-specific pieces should be reusable detector components, handler state machine pieces, config adapters, or probe-only utilities.
- Confirm whether the proposed event hooks cover portal needs without adding portal-specific core behavior.

## [Round 6] 2026-05-26 - Portal Event Package Boundary

### A. Round Goal

Target files:

- `core/events/types/portal/definition.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/assets.py`
- `core/events/types/portal/minimap_detector.py`
- `core/events/types/portal/minimap_feature_matcher.py`
- `core/events/types/portal/minimap_shape_color_matcher.py`
- `core/events/types/portal/main_view_confirmer.py`
- `core/events/types/portal/handler.py`

Questions for this round:

- Is `portal` a clean event package behind `EventDefinition`?
- Which detector algorithms are reusable components?
- Does `handler.py` need a state-machine split?
- Which portal behaviors require generic event hooks versus package-local hooks?

### C. Findings

Key findings:

- (verified) `PortalEventDefinition` is a clean event package entrypoint. It exposes identity, config defaults/schema, detector factory, and handler factory.
- (verified) `PortalEventConfig` is a typed config adapter with backward-compatible `detector_mode` fallback from `feature_detector_enabled`.
- (verified) `PortalMinimapDetector` is a mode-dispatch adapter plus final color filter and logging. It should delegate mode strategy and hit filtering to smaller modules.
- (verified) `minimap_feature_matcher.py` is a reusable algorithm component for blue-body binary mask matching.
- (verified) `minimap_shape_color_matcher.py` is the most algorithm-heavy component. It combines blue/outer/shape/edge/color responses and then re-evaluates candidates with F1-like scores and signature score.
- (verified) `main_view_confirmer.py` is a reusable full-screen portal-glow confirmer, but it is not currently used inside `PortalEventHandler.update()`.
- (verified) `PortalEventHandler` is a state machine encoded as string state and loose fields. It should gain explicit phase enum/runtime dataclass before further splitting.
- (verified) Portal completion currently checks known exit portal proximity, player position change, and minimap environment signature change.
- (inferred) Portal-specific hooks can mostly map to generic event/navigation hooks. Detailed candidate rejection may remain detector-local until a generic detector debug hook exists.
- (inferred) `core/events/config.py` should eventually derive portal defaults from `PortalEventDefinition.default_config()` rather than hard-code portal values in core event defaults.

Updated documents:

- `core/events/types/portal/ARCHITECTURE.md` - expanded with verified package interface, detector architecture, algorithm summaries, handler state machine, hook mapping, and split priorities.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/events/types/portal/definition.py` | shallow | partial | 1 | Full file read; package entrypoint confirmed. |
| `core/events/types/portal/config.py` | shallow | partial | 1 | Full file read; typed config adapter confirmed. |
| `core/events/types/portal/assets.py` | shallow | partial | 1 | Full file read; asset constants confirmed. |
| `core/events/types/portal/minimap_detector.py` | shallow | partial | 1 | Full file read; mode dispatch and hit filtering identified. |
| `core/events/types/portal/minimap_feature_matcher.py` | shallow | partial | 1 | Full file read; blue-body matcher summarized. |
| `core/events/types/portal/minimap_shape_color_matcher.py` | shallow | partial | 1 | Full file read; shape/color algorithm summarized. |
| `core/events/types/portal/main_view_confirmer.py` | shallow | partial | 1 | Full file read; full-view confirmer summarized. |
| `core/events/types/portal/handler.py` | shallow | partial | 1 | Full file read; state machine and completion checks identified. |

Next round plan:

- Read mapping/localization core: `core/recognizer_optimized.py`, `core/stitcher_core.py`, `core/navigation_core.py`.
- Identify reusable algorithm modules and stateful runtime boundaries for mapping/localization.
- Then read `core/pathfinder.py`, `core/path_utils.py`, and `core/anchor_path.py` for route planning boundaries.

## [Round 7] 2026-05-26 - Mapping and Localization Core Boundaries

### A. Round Goal

Target files:

- `core/recognizer_optimized.py`
- `core/stitcher_core.py`
- `core/navigation_core.py`

Questions for this round:

- Which algorithms should become reusable pure modules?
- Which classes should remain stateful runtime facades?
- Where are IO, visualization, debug logging, and algorithm decisions mixed?
- What split order protects behavior with tests?

### C. Findings

Key findings:

- (verified) `HSVRecognizer` mixes parameter storage, preprocessing, wall/fog/player extraction, dynamic color filtering, and combined registration mask construction.
- (verified) `HSVRecognizer.extract_combined()` is the key shared output for both stitching and navigation localization: `(match_mask, wall_mask, fog_mask)`.
- (verified) `MapStitcher` mixes map state, map package IO, keyframe/F2F registration, weighted merging, stats, and display rendering.
- (verified) `MapStitcher.add_frame()` is the mapping main chain: first-frame placement, keyframe anchor matching, previous-frame fallback, draw-quality gate, resize/standardize masks, and weighted merge.
- (verified) `MapStitcher._merge_frame_weighted()` is a distinct reusable merge algorithm with clipping, wall weight accumulation, fog/explored update, and display canvas write.
- (verified) `NavigationCore` mixes map package loading, recognizer construction, localization state, F2F tracking, template matching, visual consistency checks, frame registration, and display rendering.
- (verified) `NavigationCore.localize()` is the localization main chain: extract masks, reject low feature counts, try F2F phase correlation, fallback to local/global template matching, update registration and state.
- (verified) `MapStitcher._estimate_displacement()` and `NavigationCore._estimate_displacement()` duplicate the same phase-correlation algorithm.
- (inferred) First low-risk algorithm extraction should be shared phase correlation. The next should be package IO, then weighted merge, then localization matching.

Updated documents:

- `core/ARCHITECTURE.md` - expanded mapping, recognizer, localization responsibilities, main algorithms, split order, and shared phase-correlation extraction.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/recognizer_optimized.py` | shallow | partial | 1 | Full file read; preprocessing/mask/combined responsibilities identified. |
| `core/stitcher_core.py` | shallow | partial | 1 | Full file read in chunks; add_frame and merge algorithm summarized. |
| `core/navigation_core.py` | shallow | partial | 1 | Full file read in chunks; localization algorithm and state responsibilities identified. |

Next round plan:

- Read route planning core: `core/pathfinder.py`, `core/path_utils.py`, `core/anchor_path.py`, and `core/navigation_obstacles.py`.
- Identify reusable geometry/path modules and their tests.

## [Round 8] 2026-05-26 - Route Planning and Geometry Core

### A. Round Goal

Target files:

- `core/pathfinder.py`
- `core/path_utils.py`
- `core/anchor_path.py`
- `core/navigation_obstacles.py`

Questions for this round:

- Which route/path functions are already reusable?
- Is A* cleanly separated from navigation UI and movement policy?
- Does anchor planning belong in route geometry or movement execution?
- What tests protect these modules?

### C. Findings

Key findings:

- (verified) `PathFinder` is mostly a clean GUI-free A* adapter. It owns coordinate downsampling, obstacle-map construction, start-area forgiveness, walkable snapping, 8-direction A*, and global-coordinate reconstruction.
- (verified) `PathFinder._astar()` allows diagonal movement but prevents diagonal corner cutting by rejecting a diagonal step when either adjacent orthogonal side cell is blocked.
- (verified) `PathFinder._build_obstacle_map()` supports wall thinning, optional unknown-area blocking from `explored_map`, and optional safety-margin dilation.
- (verified) `navigation_obstacles.derive_navigation_wall_layer()` is a pure adapter from stitched wall layer to navigation wall layer: threshold first, then optionally erode with a cross kernel to make routing more forgiving without mutating localization data.
- (verified) `path_utils.py` is a reusable geometry module: distance, collinear cleanup, Bresenham line walkability, shortcut smoothing, cumulative path length, point projection, interpolation, distance-to-path, and circular exit-region checks.
- (verified) `anchor_path.py` is route-shaping logic for ordered user guide anchors. It advances to the next forward anchor first; if A* to that anchor fails, it returns a short probe path toward the anchor instead of jumping straight to the final target.
- (verified) Existing tests cover `PathFinder` and `path_utils` through `tests/test_pathfinder.py` and `tests/test_path_utils.py`.
- (inferred) These modules should stay mostly intact. A later `core/routing/` package can group them, but splitting individual algorithms further would reduce locality more than it improves reuse.
- (inferred) `anchor_path.py` needs direct tests because it encodes navigation product policy: ordered-anchor progress, reached-anchor skipping, target progress filtering, and probe fallback.

Updated documents:

- `core/ARCHITECTURE.md` - expanded with route/pathfinding responsibilities, algorithm summaries, package grouping recommendation, and test gaps.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/pathfinder.py` | shallow | partial | 1 | Full file read; A* adapter, obstacle derivation, start clearing, snapping, and no-corner-cutting behavior identified. |
| `core/path_utils.py` | shallow | partial | 1 | Full file read; geometry/path utility algorithms and line-of-sight smoothing identified. |
| `core/anchor_path.py` | shallow | partial | 1 | Full file read; ordered-anchor corridor planning and probe fallback identified. |
| `core/navigation_obstacles.py` | shallow | partial | 1 | Full file read; pure navigation wall-layer derivation confirmed. |

Next round plan:

- Read GUI dialog modules: `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/color_picker_dialog.py`, and `gui/dialogs/event_manager_dialog.py`.
- Identify dialog-to-domain seams, reusable parameter models, and large-dialog split opportunities.

## [Round 9] 2026-05-26 - GUI Dialog Boundaries

### A. Round Goal

Target files:

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/event_manager_dialog.py`

Questions for this round:

- Which dialogs are simple widget adapters versus mixed UI/domain modules?
- Which parameter read/write and validation code should become reusable models or presenters?
- Which dialog files are large enough to split first without changing behavior?
- How should dialogs interact with event/navigation systems after hooks and module seams are introduced?

### C. Findings

Key findings:

- (verified) `NavParametersDialog` is the largest dialog seam. One class creates all tabs, owns help text, owns widget-to-`NavConfig` binding, mutates immutable dataclasses with `dataclasses.replace`, parses HSV text with `ast.literal_eval`, emits `parameters_changed`, and estimates click radii from calibrated screen bounds.
- (verified) `NavParametersDialog.set_config_to_ui()` uses `QSignalBlocker` over child widgets while copying `NavConfig` values into controls. This is the right behavior and should survive any split.
- (verified) `NavParametersDialog._connect_signals()` already contains the core extraction candidate: a field map from widget to `(sub_config, attr)` plus text-field HSV binding.
- (verified) `_auto_estimate_click_radius()` is not UI layout; it is a small calibration policy based on `QApplication.screens()`, physical bounds, and `game_screen_center`.
- (verified) `AdvancedSettingsDialog` is an older dict-based tuning dialog. It directly reaches into `parent.recognizer` and `parent.stitcher`, applies params with `set_params()`, and writes/loads JSON presets from the current working directory.
- (verified) `advanced_settings/params_adapter.py` is a useful but shallow extraction: it moves widget read/write/preset code out of the dialog, but it still depends on exact dialog attribute names.
- (verified) `ColorPickerDialog` has already extracted HSV math and image rendering into helper modules, but `update_preview()` still owns OpenCV mask generation, morphology, and debug artifact writes (`preview_result_*.png`, `preview_before_morph_*.png`, `preview_log_*.txt`) in the current working directory.
- (verified) `EventManagerDialog` is the cleanest dialog pattern. It builds event rows and dynamic parameter widgets from `build_tui_event_options()` schema, emits command signals for save/test/reset, and renders live task state from `coordinator.tasks()`.
- (verified) `EventManagerDialog` mutates `config` in place (`config.enabled`, `config.events[event_type][key]`) before emitting `config_changed`; this differs from `NavParametersDialog` immutable update style.
- (inferred) New dialog code should copy the event-manager schema-driven form pattern and avoid the advanced-settings parent-reach pattern.
- (inferred) Dialog extraction should start with field specs and widget binding, not visual layout. That keeps UI behavior stable while moving reusable parameter semantics into testable modules.

Updated documents:

- `gui/dialogs/ARCHITECTURE.md` - expanded with verified dialog responsibilities, current seams, split order, reusable form-binding strategy, and risk points.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/dialogs/nav_params_dialog.py` | shallow | partial | 1 | Full file read in chunks; tab construction, field map binding, immutable config update, HSV text parsing, and click-radius estimator identified. |
| `gui/dialogs/advanced_settings_dialog.py` | shallow | partial | 1 | Full file read; legacy dict params, direct recognizer/stitcher mutation, preset/file IO responsibilities identified. |
| `gui/dialogs/advanced_settings/params_adapter.py` | PENDING | partial | 1 | Full file read; shallow widget-attribute adapter and preset application identified. |
| `gui/dialogs/color_picker_dialog.py` | shallow | partial | 1 | Full file read; interaction shell, HSV sampling, preview generation, and debug artifact writes identified. |
| `gui/dialogs/color_picker/hsv_ranges.py` | PENDING | partial | 1 | Full file read; pure HSV conversion/range/stat helpers confirmed. |
| `gui/dialogs/color_picker/image_renderer.py` | PENDING | partial | 1 | Full file read; Qt image conversion and marker rendering adapter confirmed. |
| `gui/dialogs/event_manager_dialog.py` | shallow | partial | 1 | Full file read; schema-driven event parameter form and live task table confirmed. |

Next round plan:

- Read mapping GUI mode and related widgets.
- Identify how mapping runtime, stitching state, capture loop, and UI controls should split from presentation.

## [Round 10] 2026-05-26 - Mapping GUI Mode Boundary

### A. Round Goal

Target files:

- `gui/modes/mapping_mode.py`
- `gui/modes/mapping_widget.py`
- `gui/widgets/minimap_widget.py`
- `gui/widgets/clickable_label.py`

Questions for this round:

- Which mapping GUI class owns the runtime capture/stitch loop?
- How does mapping GUI talk to `ScreenCapture`, `HSVRecognizer`, and `MapStitcher`?
- Which responsibilities are presentation-only versus reusable mapping session logic?
- What widget helpers can remain generic components?

### C. Findings

Key findings:

- (verified) There is no `gui/modes/mapping_mode.py`; the mapping workflow entrypoint is `gui/modes/mapping_widget.py`.
- (verified) There is no `gui/widgets/minimap_widget.py`; the mapping display uses `CollapsibleMapGroup` plus `ScalableMapWidget`.
- (verified) `MappingWidget` owns UI construction, monitor region/center selection, capture timer, capture/recognize/stitch loop, display rendering, temporary route planning on map click, recognizer/stitcher parameter updates, advanced/color picker dialogs, root config save/load, map package save, and topmost window behavior.
- (verified) `capture_and_process()` is the mapping main loop: capture square/region, detect player when needed, fallback to last/center position, extract combined masks, get raw gray, call `MapStitcher.add_frame()`, store last capture/player state, update displays, and update stats.
- (verified) Existing helper modules are meaningful but incomplete: `mapping/save_load.py` owns project-root/config/map-folder helpers; `mapping/map_renderer.py` owns BGR pixmap conversion and global-map overlay drawing; `mapping/params_adapter.py` owns shallow widget/param synchronization.
- (verified) `save_load.project_root_from_file()` derives project root from `Path(__file__).resolve().parents[2]`; when called from `gui/modes/mapping_widget.py`, this resolves to the repository root.
- (verified) `MappingWidget.save_map()` writes both stitcher package data and map-specific `config.json` under `map_data/<map_name>/`.
- (verified) `ScalableMapWidget` declares `pixel_clicked = Signal(int, int)` and `MappingWidget` connects it to `on_map_click()`, but the widget never emits that signal in its mouse handlers.
- (verified) `ClickableImageLabel` does implement original-coordinate click conversion and emits `pixel_clicked`; it is used by color picker, not the mapping global map.
- (inferred) `MappingWidget` should be split after extracting a `MappingSession` or `MappingRuntimeLoop` that hides capture/recognize/stitch mechanics behind a small interface.
- (inferred) `ScalableMapWidget` either needs coordinate-click support or the mapping route-click feature should be removed from the title and wiring. This is a concrete behavior risk to verify with UI testing before refactor.

Updated documents:

- `gui/modes/ARCHITECTURE.md` - expanded mapping mode with verified runtime loop, helper module roles, target split, and the `ScalableMapWidget.pixel_clicked` risk.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `gui/modes/mapping_widget.py` | shallow | partial | 1 | Full file read in chunks; capture/stitch loop, config save/load, map save, param updates, and display responsibilities identified. |
| `gui/modes/mapping/save_load.py` | PENDING | partial | 1 | Full file read; project root, map folder, root/map config JSON helpers identified. |
| `gui/modes/mapping/map_renderer.py` | PENDING | partial | 1 | Full file read; BGR pixmap and global map overlay rendering identified. |
| `gui/modes/mapping/params_adapter.py` | PENDING | partial | 1 | Full file read; shallow widget-to-params sync helpers identified. |
| `gui/widgets/clickable_label.py` | shallow | partial | 1 | Full file read; original-coordinate click conversion and wheel zoom signal confirmed. |
| `gui/widgets/scalable_map.py` | PENDING | partial | 1 | Full file read; zoom/pan widget read; declared `pixel_clicked` lacks emit. |
| `gui/widgets/collapsible_group.py` | PENDING | partial | 1 | Full file read; wraps `ScalableMapWidget` with zoom buttons and collapsible group. |

Next round plan:

- Read input system modules: `core/motion_controller.py`, `core/input_driver.py`, and relevant probe/usage files.
- Identify the seam between route intent, screen coordinate mapping, and platform input side effects.

## [Round 11] 2026-05-26 - Input System and Motion Boundary

### A. Round Goal

Target files:

- `core/motion_controller.py`
- `core/input_driver.py`
- `utils/input_probe.py`
- `utils/event_icon_probe.py`
- `utils/portal_screen_probe.py`

Questions for this round:

- Where should the seam live between navigation route intent and concrete click/key side effects?
- Which input behavior belongs in reusable movement mapping versus platform adapter code?
- What existing probe utilities reveal about required diagnostics or dry-run hooks?
- How can input hooks be added without making navigation tasks depend on GUI details?

### C. Findings

Key findings:

- (verified) `MotionController` is more than a simple driver wrapper. It owns map-vector to screen-click mapping, min/max/precision radius policy, control enablement, direct screen clicks, key presses, bottom-click guard, optional screen clamping, optional focus-before-click, backend dispatch, and rich click diagnostics.
- (verified) `MotionController._calculate_target_screen_position()` is pure movement mapping except for writing `last_click_info`.
- (verified) `MotionController._execute_click()` is the main side-effect boundary. It applies bottom guard, optional clamping, window diagnostics, optional focus, sends click through backend, records cursor/window details, and falls back to `pydirectinput.click()`.
- (verified) `MotionController.press_key()` bypasses `InputDriver` and calls `pydirectinput.press()` directly. This is an adapter gap for testability and hookability.
- (verified) `InputDriver` is a concrete Win32 adapter around `ctypes.windll.user32`: cursor move, cursor/window diagnostics, foreground focus, mouse down/up/click, and drag.
- (verified) `utils/input_probe.py` is a real diagnostic adapter. It compares several input strategies, collects DPI/window/cursor state, defaults to dry-run, and only sends input with `--execute`.
- (verified) `tests/test_motion_controller.py` already tests click radius clamping, zero-delta skip, `_execute_click()` diagnostics, optional clamping, focus, and bottom guard using a fake input driver and fake `pydirectinput`.
- (verified) `utils/event_icon_probe.py` calls production portal detector components rather than copying detector algorithms. It owns CLI parsing, capture geometry, debug drawing, and artifact writing.
- (verified) `utils/portal_screen_probe.py` calls production main-view portal confirmer/window-finder functions and owns CLI/capture/debug output.
- (inferred) The first input seam should be an `InputCommandSink`/`GameInputAdapter` behind `MotionController`, not in event handlers or movement executor.
- (inferred) Hooks should observe or wrap `MotionController` commands and results: before command, after command, command skipped, backend failure, and diagnostics snapshot.
- (inferred) `input_probe.py` should remain allowed to contain non-production input strategies because its purpose is comparing adapters. Production navigation should use only the chosen adapter through `MotionController`.

Updated documents:

- `core/ARCHITECTURE.md` - expanded input system with verified `MotionController`/`InputDriver` behavior, adapter gaps, hook locations, and split order.
- `utils/ARCHITECTURE.md` - expanded probe responsibilities and rules for production algorithm reuse.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `core/motion_controller.py` | shallow | partial | 1 | Full file read; movement mapping, click execution, bottom guard, diagnostics, backend fallback, and key adapter gap identified. |
| `core/input_driver.py` | shallow | partial | 1 | Full file read; Win32 cursor/window/click adapter responsibilities identified. |
| `utils/input_probe.py` | shallow | partial | 1 | Full file read; dry-run diagnostics, input strategy comparison, admin restart, and execute modes identified. |
| `utils/event_icon_probe.py` | shallow | partial | 1 | Full file read in chunks; production detector reuse and debug artifact responsibilities identified. |
| `utils/portal_screen_probe.py` | shallow | partial | 1 | Full file read; production main-view confirmer reuse and window/rect capture diagnostics identified. |
| `tests/test_motion_controller.py` | PENDING | partial | 1 | Full file read; fake driver tests cover mapping and click execution policies. |

Next round plan:

- Read test index and remaining focused probe/task utilities.
- Then consolidate final architecture roadmap with class/module extraction priorities and cross-doc references.

## [Round 12] 2026-05-26 - Tests, Remaining Probes, and Roadmap Consolidation

### A. Round Goal

Target files:

- `tests/*.py`
- `utils/route_context_probe.py`
- `utils/navigation_task_probe.py`
- `ARCHITECTURE_GUIDE.md`

Questions for this round:

- Which refactor candidates already have tests?
- Which risky splits need tests before source changes?
- Do remaining probes follow the production-adapter rule?
- How should the top-level roadmap sequence module/class extraction work?

### C. Findings

Key findings:

- (verified) Existing tests protect several low-level seams: `MotionController`, `PathFinder`, `path_utils`, `NavigationCore` F2F wall-mask behavior, `MapStitcher._merge_frame_weighted()`, recognizer dynamic filtering, and route manager persistence.
- (verified) Tests do not yet directly protect event lifecycle, portal handler state transitions, mapping runtime orchestration, navigation intent execution, dialog binding, or GUI map-click behavior.
- (verified) `route_context_probe.py` and `navigation_task_probe.py` are good narrow probes: they read route data and call production `RouteContext` / `NavigationTaskBuilder` rather than copying route math.
- (verified) `ARCHITECTURE_GUIDE.md` now has a phased roadmap: test guardrails, low-risk deep modules, runtime facades, event hooks/packages, GUI cleanup, and final package organization.
- (inferred) The safest first code changes are pure/helper extractions with tests: `anchor_path` tests, shared phase displacement, weighted merge, motion mapping/bottom guard, and nav dialog click-radius estimator.
- (inferred) The highest-value large-file split remains `gui/modes/navigation_mode.py`, but it should start with `NavigationIntentExecutor`, config applier, runtime start/stop, and event panel adapter rather than a broad file move.
- (inferred) Event hooks should wait until fake-detector/fake-handler lifecycle tests exist; otherwise hook dispatch may accidentally freeze current incidental behavior.

Updated documents:

- `tests/ARCHITECTURE.md` - expanded with verified test contracts and missing test additions.
- `utils/ARCHITECTURE.md` - expanded route/task probe descriptions.
- `ARCHITECTURE_GUIDE.md` - replaced hypotheses with confirmed themes and a phased refactor roadmap.

Coverage update:

| Area | Previous | Current | Reads | Notes |
| --- | --- | --- | ---: | --- |
| `tests/test_pathfinder.py` | shallow | partial | 1 | Full file read; corner cutting, wall shrinking, unexplored blocking contracts identified. |
| `tests/test_path_utils.py` | shallow | partial | 1 | Full file read; simplification, projection/interpolation, smoothing, and exit-region contracts identified. |
| `tests/test_navigation_core.py` | shallow | partial | 1 | Full file read; F2F wall-mask regression contract identified. |
| `tests/test_stitcher_core.py` | shallow | partial | 1 | Full file read; weighted merge visibility/fog contracts identified. |
| `tests/test_recognizer_optimized.py` | shallow | partial | 1 | Full file read; dynamic saturation filtering contract identified. |
| `tests/test_route_manager.py` | shallow | partial | 1 | Full file read; route defaults, round-trip, and undo contract identified. |
| `utils/route_context_probe.py` | shallow | partial | 1 | Full file read; production `RouteContext` progress inspection confirmed. |
| `utils/navigation_task_probe.py` | shallow | partial | 1 | Full file read; production `NavigationTaskBuilder` inspection confirmed. |
| `ARCHITECTURE_GUIDE.md` | shallow | partial | 2 | Re-read and updated with confirmed roadmap and cross-module rules. |

Next round plan:

- If continuing documentation only: deepen individual function/class documentation in `CODEBASE.md` format for one module at a time.
- If moving to refactor implementation: start with tests for `anchor_path.py` and `EventCoordinator`, then extract low-risk pure helpers.

## [SYNC] 2026-05-26 - Advanced Settings File IO Cleanup

### A. SYNC Scope

Trigger task: legacy content audit and low-risk behavior-preserving cleanup.

Direct source changes:

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/file_io.py`
- `tests/test_advanced_settings_file_io.py`

Expected impact:

- `AdvancedSettingsDialog.save_current_params()` and `load_params_from_file()` now delegate JSON persistence to a reusable helper.
- Saved parameter snapshots no longer write to the process current working directory; they default to `configs/advanced_settings/`.
- Test coverage now protects filename sanitization, explicit output directories, payload shape, validation, and non-ASCII display formatting.

### C. SYNC Result

Key findings:

- (verified) `advanced_settings/file_io.py` owns default output directory, filename sanitization, JSON dump/load, payload validation, and display formatting.
- (verified) `AdvancedSettingsDialog` still owns Qt file dialog usage, status labels, and recognizer/stitcher apply timing.
- (verified) Importing `gui.dialogs.advanced_settings.file_io` through the full `gui` package triggers unrelated GUI/input dependencies; the new test loads the pure helper by file path to keep the test isolated.

Updated documents:

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

Validation:

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\file_io.py tests\test_advanced_settings_file_io.py`
- `python -m unittest tests.test_advanced_settings_file_io`
- `python -m unittest tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue old-content audit with stricter reference checks for `gui/widgets_fixed.py` before any deletion decision.
- Then consider another low-risk extraction with tests, preferably presets from `AdvancedSettingsDialog` or a pure helper from `NavParametersDialog`.

## [SYNC] 2026-05-26 - Remove Unused widgets_fixed Backup

### A. SYNC Scope

Trigger task: continue legacy content audit.

Direct source changes:

- Deleted `gui/widgets_fixed.py`

Expected impact:

- Active widget imports remain through `gui/widgets/clickable_label.py`, `gui/widgets/scalable_map.py`, and `gui/widgets/collapsible_group.py`.
- Removing the old combined backup reduces duplicate widget definitions and prevents accidental reintroduction of stale behavior.

### C. SYNC Result

Key findings:

- (verified) `rg` found no runtime import of `gui.widgets_fixed`; references were limited to docs/history and the file itself.
- (verified) `widgets_fixed.py` contained old combined definitions for `ClickableImageLabel`, `ScalableMapWidget`, and `CollapsibleMapGroup`.
- (verified) Current runtime code imports the split widget modules under `gui/widgets/`.

Updated documents:

- `CODEBASE.md`
- `gui/ARCHITECTURE.md`
- `architecture_docs/original/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\widgets\clickable_label.py gui\widgets\scalable_map.py gui\widgets\collapsible_group.py gui\modes\mapping_widget.py`
- `python -c "from gui.widgets.clickable_label import ClickableImageLabel; from gui.widgets.scalable_map import ScalableMapWidget; from gui.widgets.collapsible_group import CollapsibleMapGroup; print('ok')"`

Next round plan:

- Continue low-risk cleanup with `AdvancedSettingsDialog` presets extraction, or audit `k_ratio/y_bias` UI compatibility fields before changing them.

## [SYNC] 2026-05-26 - Advanced Settings Preset Data Extraction

### A. SYNC Scope

Trigger task: continue low-risk cleanup after legacy audit.

Direct source changes:

- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/params_adapter.py`
- `gui/dialogs/advanced_settings/presets.py`
- `tests/test_advanced_settings_presets.py`

Expected impact:

- Preset option order and non-default preset values now live in a data-only helper.
- `AdvancedSettingsDialog` no longer embeds preset names inline.
- `params_adapter.apply_preset_to_widgets()` still preserves the same widget writes and default reset behavior.

### C. SYNC Result

Key findings:

- (verified) `presets.py` owns `DEFAULT_PRESET_NAME`, `PRESET_NAMES`, and non-default widget-value maps.
- (verified) Default preset remains a full reset path through `reset_widgets_to_default()`.
- (verified) Tests cover preset order, old values, adapter application, default reset, and unknown preset return value without constructing Qt dialogs.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\params_adapter.py gui\dialogs\advanced_settings\presets.py tests\test_advanced_settings_presets.py`
- `python -m unittest tests.test_advanced_settings_presets`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue with `AdvancedSettingsDialog` tab/widget-spec extraction only if a narrow adapter test can cover it, otherwise audit `k_ratio/y_bias` compatibility fields.

## [SYNC] 2026-05-26 - Hide Legacy k_ratio/y_bias UI

### A. SYNC Scope

Trigger task: audit old `NavPreferences.k_ratio/y_bias` compatibility fields.

Direct source changes:

- `gui/dialogs/nav_params_dialog.py`
- `tests/test_navigation_params_compat.py`

Expected impact:

- Old `k_ratio/y_bias` values still load/save through `NavConfig.nav_preferences`.
- The navigation parameter panel no longer exposes controls that do not affect current motion mapping.

### C. SYNC Result

Key findings:

- (verified) `k_ratio/y_bias` are not referenced by `MotionController`, localization, task scheduling, or movement execution.
- (verified) Runtime usage was limited to config model round-trip and `NavParametersDialog` UI/binding.
- (verified) The UI controls and widget-map bindings were removed, while `NavPreferences` remains for old `config.json` compatibility.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/LEGACY_AUDIT.md`

Validation:

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\navigation_params.py tests\test_navigation_params_compat.py`
- `python -m unittest tests.test_navigation_params_compat`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Stop here for this cleanup batch unless another old-content candidate is requested; larger tab extraction needs a separate narrow plan and GUI-aware test strategy.

## [SYNC] 2026-05-26 - Nav Params Screen Estimator Extraction

### A. SYNC Scope

Trigger task: continue low-risk dialog cleanup and finish documentation sync for the extracted navigation click-radius estimator.

Direct source changes:

- `gui/dialogs/nav_params_dialog.py`
- `gui/dialogs/nav_params/__init__.py`
- `gui/dialogs/nav_params/screen_estimator.py`
- `tests/test_nav_params_screen_estimator.py`

Expected impact:

- `NavParametersDialog` keeps Qt screen enumeration and UI writes.
- `gui.dialogs.nav_params.screen_estimator.estimate_click_radii()` owns the pure radius policy.
- Tests cover normal estimate, small-screen minimum clamp, large-screen maximum clamp, and out-of-bounds centers.

### C. SYNC Result

Key findings:

- (verified) `_auto_estimate_click_radius()` now delegates radius math to `estimate_click_radii(center, screen_bounds)`.
- (verified) `screen_estimator.py` has no Qt dependency, so it can be tested without importing the full GUI package.
- (verified) Physical-screen detection remains in the dialog adapter through `_screen_physical_bounds_for_center()`.

Updated documents:

- `CODEBASE.md`
- `gui/dialogs/ARCHITECTURE.md`
- `tests/ARCHITECTURE.md`
- `architecture_docs/original/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/original/tests/ARCHITECTURE.md`
- `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`
- `architecture_docs/zh-CN/tests/ARCHITECTURE.md`

Validation:

- `python -m py_compile gui\dialogs\nav_params_dialog.py gui\dialogs\nav_params\screen_estimator.py tests\test_nav_params_screen_estimator.py`
- `python -m unittest tests.test_nav_params_screen_estimator`
- `python -m unittest tests.test_advanced_settings_file_io tests.test_advanced_settings_presets tests.test_navigation_params_compat tests.test_phase_displacement tests.test_navigation_core tests.test_stitcher_core`

Next round plan:

- Continue old debug-output cleanup by disabling `ColorPickerDialog.update_preview()` artifact writes by default while preserving an explicit diagnostic opt-in.

## [SYNC] 2026-05-26 - Color Picker Debug Output Gating

### A. SYNC Scope

Trigger task: continue old-content audit cleanup after moving color-picker preview debug artifacts out of the current working directory.

Direct source changes:

- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/color_picker/debug_output.py`
- `tests/test_color_picker_debug_output.py`

Expected impact:

- HSV preview rendering still updates the right-side preview label.
- `preview_result_*.png`, `preview_before_morph_*.png`, and `preview_log_*.txt` are no longer written on every preview by default.
- Debug artifacts remain available by setting `MINIMAP_COLOR_PICKER_DEBUG=1`.

### C. SYNC Result

Key findings:

- (verified) `ColorPickerDialog.update_preview()` still builds the same wall mask, performs the same close morphology, and updates the preview label.
- (verified) `write_wall_preview_debug()` is only called when `is_wall_preview_debug_enabled()` accepts `MINIMAP_COLOR_PICKER_DEBUG`.
- (verified) The debug switch is testable without importing PySide widgets or constructing the dialog.

Updated documents:

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

Validation:

- `python -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\debug_output.py tests\test_color_picker_debug_output.py`
- `python -m unittest tests.test_color_picker_debug_output`

Next round plan:

- Continue with another low-risk pure/helper extraction only after current docs and regression tests are clean.

## [Review] 2026-09-17 - Generic-Layer Boundary Compliance

### A. Review Scope (declared before source inspection)

**Goal:** Review the current implementation against the workspace rule that
lower layers provide reusable, business-neutral capabilities and upper business
features compose them without polluting their contracts.

**Initial target paths:**

- `core/events/`, including the portal event package and its runtime boundary
- `core/navigation_tasks/` and `core/input`/movement ownership boundaries
- GUI, virtual-gamepad, and LAN adapters that may bypass common execution paths

**Questions to answer:**

1. Do shared modules contain portal-, game-, role-, or feature-specific policy?
2. Do business features duplicate or bypass recognition, localization,
   navigation, scheduling, controller-output, or transport capabilities?
3. Are real side effects confined to explicit execution adapters?
4. Is mutable state correctly scoped per controller/device/source/feature
   instance, rather than shared by unrelated work?

**Method:** CodeGraph call-path and blast-radius inspection first, followed by
symbol-reference checks and focused source confirmation only where needed. This
is a review-only round: no source-code change is authorized.

### C. Review Findings

**Key findings:**

- (verified) The navigation/event pathway honors the intended effect boundary:
  `PortalEventHandler.update()` returns `EventAction`; `EventRunner` and
  `NavigationTaskController` pass actions/intents onward; device IO is owned by
  dedicated action adapters and the virtual-gamepad Host.
- (verified) Host controller state is separated by controller and event source:
  `ControllerRegistry.SetEventState()` writes to a per-controller `StateStore`
  under a normalized source, then merges sources at submission time. This is
  consistent with independent controller/device/source state ownership.
- (verified, P1) `LocalEventRuntime._load()` and
  `RemoteEventRuntime._definitions()` both parse `events.json` into parallel
  `ActionTrack`/`SimpleNamespace` definitions. The local runtime also duplicates
  catalog-payload and live-peer selection concerns that exist in
  `EventCatalogRuntime`. A new event-schema or execution semantic can therefore
  require edits in multiple runtime implementations instead of one shared
  definition/execution contract.
- (verified, P2) `LocalEventRuntime._run()` mixes Windows trigger polling,
  route-file interpretation, event-session scheduling, LAN fanout, catalog
  publication, and Host `event.state`/`event.clear` output. It is an adapter
  with several independent ownership domains rather than a composition of
  reusable trigger, route, execution, and output modules.
- (verified, P2) `EventWorkbenchPage` owns JSON loading/saving, route-model
  mutation, direct remote sending, and construction/lifecycle of three
  background runtimes. The UI is therefore a second composition root with
  persistence and execution policy, instead of a thin adapter over a shared
  event-workbench service.

**Non-findings:** `PortalEventHandler` does not access mouse, keyboard,
virtual-gamepad, Host, or network APIs directly; `FollowChainHandler` likewise
emits declarative event metadata without a device dependency. Do not refactor
these as though they were effect-boundary violations.

**Recommended next round:** Extract one normalized event-definition repository
and one reusable execution runtime. Put keyboard polling behind a trigger
source adapter, route normalization behind a route repository/router, and Host
or LAN delivery behind output adapters. Then make `EventWorkbenchPage` depend
on a composed workbench service rather than constructing/parsing runtimes.

## [SYNC] 2026-09-23 - PoE2 multiframe localization experiment

### A. Scope

- Review the completed `experimental/multiframe_localization` package and its PoE2 capture-test composition against the bottom-up generalization rule.
- Confirm that recognition, displacement, shape scoring, registration lifecycle, navigation observation, UI, persistence, and side effects retain explicit ownership boundaries.

### C. Result

- (verified) The experiment composes existing canonical-wall, phase-displacement and anchored-registration capabilities; it does not duplicate controller output, path execution, Host, LAN, keyboard, or mouse behavior.
- (verified) The feature-specific composition and memory anchor stay under `features/poe2`; generic-looking motion/evidence/scoring modules remain experimental until a second reuse case and real-game calibration justify promotion to `core`.
- (verified) Mutable state is session-scoped: each experiment owns its window, submap, estimator, coordinator, worker and archive; formal and experimental runtimes do not share sessions.
- (verified) Registration uses a bounded single worker and a four-part version token, so asynchronous results cannot cross map instances, recovery revisions, evidence versions or segments.
- (verified) Navigation receives a domain-neutral, fail-closed observation only; the adapter cannot execute a route or emit device/network side effects.
- Validation: focused PoE2 localization/UI/composition/displacement/architecture suite `261 passed`; compileall and diff checks passed. Real-game A/B calibration remains explicitly pending.
## 2026-09-24 - PoE2 center capture invariant and adaptive similarity calibration

- 通用空间层新增 `resize_binding_around_marker()`：只处理物理矩形、锚点和 DPI 元数据；PoE2 profile/UI 组合该能力，底层不感知游戏业务。
- `Poe2MonitorConfig` 自身保证 center 模式 `capture_size == binding.width == binding.height`，避免页面、正式 runtime、测试台或直接 profile 加载产生不同截图尺寸。
- PoE2 实验 registrar 继续自动搜索 angle/reflection/scale；真实 capture size 只调整可见范围和噪声排除，不把某台电脑实测的 `0.77` 固化为配置。
- 实机 300px 首帧通过 `confidence=0.81177`，无输入或网络副作用；算法仍留在 PoE2 experimental 边界，等待多地图/多 UI scale 证据后再评估可下沉部分。

### 2026-09-24 PoE2 首帧门槛调整

PoE2 组合将首帧 `minimum_confidence` 调整为 `0.70`；通用 registrar、形状覆盖率门和其他业务组合保持不变。

## [SYNC] 2026-09-25 - PoE2 双人匹配特征预览策略

### A. SYNC 范围声明

**触发任务：** 排查双人“匹配特征”中的圆环和预览刷新是否仍应用单人人物擦除。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/test_poe2_capture_test_page.py`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`。
**预计连带影响：** 双人首帧按钮、同页 `refresh_preview()` 定时回调、单人和多帧启动及地图重新捕获；共享 `HSVRecognizer.extract_combined()` 的调用参数不改变其默认契约。

### C. SYNC 结果

**连带重读文件：** `capture_test_page.py` 的按钮、预览回调和状态复位路径；`hsv/combined.py`、`hsv_recognizer.py` 的擦除门控；`marker_candidates.py` 的双人候选检测；页面回归测试。
**关键发现（verified）：** 双人注册本帧从未执行人物圆形擦除；截图中的圆环是独立地图图标的亮边，人物候选在其右上方。预览定时刷新此前确实退回单人默认提取，可能使显示与双人本帧注册参数不一致；现在页面状态保证双人后续刷新使用无擦除参数，回到其他实验时复位。
**修订的旧结论：** “双人注册仍在人物附近清空一圈”改为“注册不清空；地图图标亮边形成圆环，且预览刷新曾使用单人默认提取”。
**CODEBASE.md 更新内容：** PoE2 测试页职责和 F-POE2-DUAL-FIRST-FRAME-PREVIEW 数据流；未改通用 HSV 默认值。
**覆盖进度更新：** `capture_test_page.py` 和页面测试聚焦复读；共享 HSV 与颜色候选只核对相关函数，保留为局部覆盖，不虚报整文件深度完整。
**下一轮计划：** 如需过滤图标，先为 PoE2 双人样本建立图标与相连墙体的像素级标注，再验证只移除图标而不损失墙体；不得恢复半径擦除。

## [SYNC] 2026-09-25 - PoE2 双人运动定位实验

### A. SYNC 范围声明

**触发任务：** 在双人首帧注册后实验连续视觉跟踪、局部纠偏与一次性内存恢复。
**直接变更文件：** `experimental/multiplayer_localization/dual_motion.py`、同包 `__init__.py`、`capture_test_page.py` 和双人运动/页面测试。
**预计连带影响：** 现有双人首帧结果、通用墙体位移与有界匹配、地图方向展示、测试页启动/停止/换图链路；单人中心链路仅调用停止双人计时器，不改变算法。

### C. SYNC 结果

**连带重读文件：** 双人首帧模型/候选/组合、单人 `VisualLocalTracker`、通用位移/有界 matcher、地图 overlay、测试页的启动/停止/换图及现有页面测试。
**关键发现（verified）：** 双人运动只需维护一份固定相似变换中的平移；两名人物位置可独立由颜色候选映射。缺失标记不代表共同墙体失效；局部匹配成功时必须把平移修正反变换给身份预测。
**修订的旧结论：** “位移失败、局部纠偏成功即可直接按原屏幕位置分配身份”改为“必须从纠偏平移恢复屏幕视口位移，否则会把复现的角色误判为跳动”。
**CODEBASE.md 更新内容：** §2 新增双人包文件职责、§4 双人运动模块和页面职责、§5 运动算法、§6 实验调用链、§9 GUI 阻塞和实机未验风险。
**覆盖进度更新：** `dual_motion.py` 和新增测试按函数/分支复读并通过；首帧注册、marker detector、地图 matcher、UI 只按本次调用链局部复读，不宣称整文件深度完整。
**下一轮计划：** 实机双人连续走动保存同一地图的帧/日志，核验两人异步运动、短暂遮挡和恢复频率；再决定是否把实验 worker 化及是否推广至正式页面。
**验证结果：** 双人运动、首帧、测试页、多帧页面、单人局部跟踪和地图控件聚焦测试 `46 passed`；新增实验模块 Ruff、编译和 diff 检查通过；Serena 对新增运动模块无诊断，UI 新增调用段无诊断。当前无 PoE2 进程，真实连续双人运动尚未验证。

## [SYNC] 2026-09-26 - PoE2 双人运动定位正式页接入

### A. SYNC 范围声明

**触发任务：** 将已经在数据采集测试页验证的双人首帧、纯视觉运动跟踪、局部纠偏和一次性恢复正式接入 PoE2 定位页。
**直接变更文件：** `monitor_config.py`、双人 `product_session.py`/`composition.py`、`hybrid_product_runtime.py`、PoE2 composition、正式 page、配置 panel、`scalable_map.py` 以及对应测试。
**边界：** 不改单人中心定位、原绘图模式、设备输入、LAN 或网络同步；双人 memory adapter 仍是 PoE2 业务适配器，通用 tracker 保持独立。

### C. SYNC 结果

**关键调用链：** profile `tracking_mode=dual` → `Poe2HybridProductRuntime` 选择 `build_poe2_dual_localization_experiment` → worker 线程调用 `Poe2DualLocalizationSession.tick()` → 首帧 `Poe2DualMemoryAnchorProvider.read_once()` + 同帧候选/几何注册 → `DualVisualTracker.start()` → 后续视觉位移和候选映射 → 失败达到门槛后 `recovery_required` → worker 等待 UI 重定位 → 下一轮只读一次内存。

**边界检查：** 双人 session 不在 GUI 线程做首帧；普通帧没有内存读取；正式状态适配保留单人字段并增加双人映射；地图组件只增加通用的多 marker overlay，不知道 PoE2 业务身份；双人 evidence builder 显式关闭人物/动态擦除，保留墙体证据。

**验证结果：** 正式 PoE2 相关集合 `300 passed`；正式接入聚焦集合 `78 passed`；compileall、diff check 通过。地图 overlay 同时支持两个 marker 和各自轨迹。实机双人连续运动仍待用户在正式定位页验证，不能由合成测试代替。

## [SYNC] 2026-09-27 - PoE2 多设备跟随实验基础链路

实验层新增 `experimental/multiplayer_follow/`：角色与地图实例身份、位置新鲜度、
手动/预览/模拟/程序状态、点击目标和安全路线运行时均保持业务中立。点击目标由
`ScalableMapWidget` 发出显示像素，经 presenter 逆旋转/镜像还原为 canonical map 坐标；
路线基于 terrain reference 的完整 wall layer，并在原始网格逐段验证，模拟步进再次做碰撞检查。
测试页仅提供 P1/P2 模拟和 P1 手动/P2 模拟两种实验，不打开 LAN、不连接真实手柄。
`ProgramFollowOutput` 作为独立的显式授权适配器保留后续真实输出边界。聚焦回归 41 项通过，
compileall 通过；实机控制和跨设备传输仍保持 opt-in。

## [SYNC] 2026-09-27 - 跟随实验四项审查问题修复

### A. SYNC 范围声明

**触发任务：** 修复角色身份绑定、初始化生命周期、不可达路线重复搜索、移动目标旧路线失效。
**直接变更文件：** 跟随运行时、PoE2 实验页及对应测试；必要时更新实验断点。
**预计连带影响：** 双人定位状态到跟随角色的绑定、地图叠加层刷新、A* 路线缓存/失败退避、手动控制优先级；不触碰真实输入或 LAN。

**本轮待验证：** 明确角色身份如何映射为 P1/P2；失败规划何时重新尝试；目标短距离位移如何避免旧路线误停。

### C. SYNC 结果

**直接变更：** `experimental/multiplayer_follow/runtime.py`、`capture_test_page.py`、两份聚焦测试和本断点；通用寻路、视觉识别、正式定位、真实手柄与 LAN 未改。
**连带复读：** `VectorPathTracker.command()` 的旧终点零向量语义、地图 overlay 刷新、双人定位启动/恢复/换图、测试页初始化与停止路径。
**关键发现（verified）：** 无路线状态过去每 100 ms 重跑整套降采样 A*；旧终点距新目标介于 1–2 个到达半径时，tracker 可输出零向量但页面仍报告路线可用。字典顺序不保证 P1/P2 身份；初始化清图前没有停双人/跟随计时器。画面刷新和独立跟随计时器还可能重复推进模拟。
**修复：** 显式选择两名不同且有效的角色；初始化/换图清除绑定并停止计时器；失败路线按角色冷却，显著移动或目标变化立即重试；旧终点离开新目标到达圈即重规划，旧终点仍在到达圈但跟踪向量为零时尝试精确新目标一次，仍不可前进才进入 BLOCKED；画面刷新只复绘缓存结果。
**边界：** 失败冷却为 1 秒，起点/目标改变超过到达半径提前失效；这是实验调度策略，不下沉通用寻路。仍为纯模拟，不发送真实输入或网络消息。
**验证：** 新增测试先复现四个缺陷、到达圈内目标小幅移动及双重刷新，再修复；PoE2 实验与地图/适配器相关回归 `321 passed`，compileall 与 diff check 通过。Ruff 对本轮跟随 runtime 和测试无报错；对实验页面其他旧代码仍报告 13 条既有 TRY401/TRY004/UP017 提示，未在本轮跨范围修改。真实 PoE2 双人持续运动与大图首轮规划的 GUI 延迟尚待人工实机验证。
**覆盖进度：** 跟随 runtime、测试页跟随/生命周期方法和对应新测试按本次调用链完整复读；`PathFinder`、地图 widget、正式双人 session 仅做受影响接口级复读，不宣称全文件深度覆盖。
## [SYNC] 2026-09-28 — PoE2 未知版本初始化自动探测

### A. SYNC 范围声明

**触发任务：** 用户批准方案 B：每次初始化实时计算客户端指纹；未知 build 仅在只读探测和结构验证全部通过时接受，失败即停止。
**预计直接变更文件：** `D:/ACloud/poe2-map-research/windows_capture.py`、该研究项目的针对性测试、必要的 PoE2 采集适配器与计划/断点文档。
**预计连带影响：** 实验采集器 `live_preview.py init` → `resolve_poe2_descriptor` → 地形/人物布局验证 → session 缓存与后续 capture；不得仅扩大指纹白名单，不发送输入或开启 LAN。
**本轮需查明：** 现有 AOB 与布局验证是否足以安全接受未知指纹；哪些布局字段仍依赖固定偏移；测试与实机只读验证如何区分。

### C. SYNC 结果

**根因与改动：** 旧 `resolve_poe2_descriptor` 在计算指纹后立刻查询静态 `POE2_BUILDS`，未知版本在 AOB/布局验证前报错。外部 producer 现新增 `resolve_build_layout`：已知版本校验元信息并保留快路径；未知版本初始化忽略未验证的 preferred RVA，强制 AOB + 唯一结构匹配，再对 descriptor 元数据/guard 和 4 KiB 内稳定样本校验；动态 contract 仅进 session，不永久白名单。研究仓库旧路由测试路径也兼容 `src/auto_modules` 现有布局。
**调用链：** 正式页 → `Poe2TerrainService.initialize` → `Poe2CaptureAdapter.initialize` → 外部 `live_preview.py init` → `fingerprint_executable` → `resolve_build_layout` → `resolve_poe2_layout_fast` → descriptor/guard 校验 → session；后续 `capture` 重验进程、构建、布局并双读完整地形。
**证据：** 研究仓库 `38 passed, 20 subtests passed`；正式 PoE2 地形/采集页/正式页面聚焦回归 `322 passed`；compileall 与本仓库 `git diff --check` 通过。当前真实 PID 39068 的未知指纹 `3440AC1DBDF822DC8A5F25F0` 初始化成功，AOB 槽位 `0x45D4ED8`；同一 session 后续抓图并转换 `MapFlotsam:73DCFC09`，地图 `3382×1863`。该实测是只读采集，未测试双人组件或定位/跟随。
**覆盖进度：** 研究采集器中的 PE 指纹、AOB、state/layout、descriptor guard、稳定样本、session init/capture 调用链与对应测试已复读；正式适配器/服务/UI 初始化入口经 CodeGraph 和回归检查。未对双人组件内存偏移或游戏画面定位链做本轮版本兼容审计。
**剩余边界：** 新版本若 AOB、固定偏移或语义变化，则安全拒绝并需要人工适配；真实 UI 端点击与双人运动跟踪仍需用户测试。外部研究目录无 Git 仓库，本轮未在其中提交。

## [SYNC] 2026-09-28 — PoE2 跟随实验目标等待与坐标漂移

### A. SYNC 范围声明

**触发任务：** 用户反馈开始跟随时人物在大地图飘移、无目标直接报错，并要求点击地图后启动、连续点击更新目标。
**预计直接变更文件：** PoE2 数据采集测试页的跟随生命周期/地图点击处理、必要的跟随实验 runtime 或地图 overlay 契约及对应测试。
**预计连带影响：** 双人定位与跟随实验的状态共享、canonical/display 坐标变换、角色 marker/路线 overlay、会话重置和停止行为；不触发真实手柄或 LAN。
**本轮需查明：** 飘移发生在定位数据、地图变换还是跟随输出覆盖；目标未设置的启动顺序与连续点击刷新是否符合现有 runtime 契约。

### C. SYNC 结果

**根因：** 双人定位每帧把真实视觉人物绘在地图上，跟随 overlay 随后又以模拟 runtime 的 follower 位置覆盖同一组人物标记；模拟位置移动被误看成真实人物飘移。启动跟随还在无目标时直接启动 100 ms 计时器，反复产出 `target_not_seeded`，覆盖了等待点击提示。
**调用链与修复：** `start_follow_experiment` 只装配角色和运行时并显示等待状态；首次有效 `map_widget.pixel_clicked` → `_on_follow_map_click` 逆变换坐标、设置共享目标、启动计时器并计算；后续点击覆盖目标并更新。`_render_follow_overlay` 取 `DualMotionState.players` 作为实心真实人物，模拟位置仅作为虚线圈，路线与目标仍使用同一变换。`stop_follow_experiment` 清除目标/路线并恢复实时定位 overlay。双人定位帧只复绘跟随结果，不额外推进模拟。
**证据：** 新页面回归先分别复现无目标就启动计时器和预测位置覆盖真实人物两处失败，修复后通过；覆盖首次/连续点击、标记分离和停止恢复。PoE2 相关页面、定位、跟随、组合与主窗口回归 `326 passed`。
**覆盖进度：** 跟随实验的启动、地图点击、计时、双人视觉刷新、overlay 和停止路径已按本次调用链复读；通用地图 widget 与模拟 runtime 只复核受影响契约，未改动。
**剩余边界：** 真实游戏界面上的人物位置与鼠标点击频率仍待用户手动验证；本次没有发送真实输入或启用 LAN。

## [SYNC] 2026-09-28 - 双人实时首帧复用与跟随移动链路审查

### A. SYNC 范围声明

**触发任务：** 用户反馈双人首帧按钮可通过，但启动双人实时定位时首帧拒绝；点击地图后跟随人物不移动，要求分别修复定位链路并验证单人/双人跟随移动。
**直接变更文件：** 待根因确认后确定，预计涉及 `capture_test_page.py`、双人实时 tracker、跟随 runtime/output 适配器及对应测试。
**预计连带影响：** 首帧注册参数与实时 tracker 的初始状态、地图坐标变换、模拟/程序移动状态、角色控制模式；不得未经显式安全验证发送真实设备输入或开启 LAN。
**本轮需查明：** 实时启动是否重复采集导致与按钮实验不同；失败阈值/帧内容是否不一致；点击目标后 runtime 是否只绘制而未产生可执行移动命令；单人和双人的移动接口是否有清晰的模拟与真实输出边界。

### C. SYNC 结果

**根因：** 实时启动失败路径清除了已接受的首帧，下一次重试会重新抓取瞬态截图；程序跟随首次点击直接申请 Host lease，但 Host 要求控制器先暂停，且点击回调没有捕获输出异常，因此真实失败表现为“点击后不移动”。默认 UI 模式本身还是模拟模式，容易被误解为真实控制。

**修复：** `_start_dual_motion()` 的构造异常保留已接受首帧；`ProgramGamepadOutput.start()` 在显式程序模式下先暂停对应 controller 再申请 lease；页面捕获 arm/write 异常并显示状态、记录日志，停止时 release 并关闭每个专属 client；模式文案明确区分模拟与真实手柄，新增角色 arm 和周期性 vector 日志；程序角色每个跟随 tick 回写最新视觉位置，达到目标后进入 `ARRIVED` 并释放 lease；后续点击新目标会重新 arm 已释放角色，即使跟随 timer 尚在运行。

**边界：** 默认模拟模式仍无真实输入；真实输入只发生在用户选择单人/双人“程序控制”并点击有效地图目标之后。未开启 LAN，不改单人中心定位、双人视觉 tracker 或绘图模式。

**验证：** `15 passed`（program adapter/runtime）、`21 passed`（capture page，含单控和双控输出）、相关 PoE2/跟随集合 `325 passed`，VirtualGamepadHost C# 合约测试 `57 passed`，compileall/diff check 通过。非管理员探针无法打开管理员工作台的 `AutoModules.VirtualGamepad.v1` 管道；这属于完整性级别边界，仍需从管理员工作台进行一次真实移动验证。页面会明确报告 Host 前置条件，不再静默失败。

**下一步断点：** Host 能连接后，按 `docs/MULTI_DEVICE_FOLLOW_CURRENT_STATE.md` 的六步顺序验证 P1 单人、P2 单人和双人程序控制；重点保留 `program_armed`、`PROGRAM_READY`、`program.state`、`ARRIVED/BLOCKED`、`program.release` 日志。
## 2026-09-28 双人首帧 PoE2 配置边界修复

- 现象：`P2_7:54BE4D92` 双人首帧识别到 2 个 marker、内存读取成功，但因通用锚定覆盖率 `0.60` 拒绝，最佳形状覆盖率 `0.5175`、anchor 平均误差约 `0.02`。
- 根因：PoE2 双人数据采集入口和正式组合都实例化了默认 `DualFirstFrameRegistrar`，没有传递 PoE2 已校准的 `first_frame_anchored_coverage`。
- 修复：新增 `build_poe2_dual_first_frame_registrar()`，两条入口统一从配置读取 PoE2 锚定门槛，且显式保持双人 `player_clear_radius=0`、`top_exclusion_rows=0`，不遮挡人物周边墙体。
- 验证：双人首帧、采集页、PoE2 composition 聚焦回归 `44 passed`；compileall 和 diff check 通过。

## 2026-09-28 程序移动实验租约时间戳竞态

- 现象：双人实时定位持续正常，但第一次地图点击进入程序控制时 Host 返回 `Start request is stale or predates a local stop`。
- 根因：`ProgramGamepadOutput` 先调用 `pause`，Host 在当前毫秒记录 local stop；紧接着 `program.acquire` 使用相同毫秒 `requestedAtMs`，被防重放条件误拒绝，尚未发送任何摇杆状态。
- 修复：通用程序输出适配器在 pause 响应后等待 Host 时钟严格进入下一毫秒，再申请 program lease；增加时间戳竞态回归测试。
- 验证：程序输出、跟随运行时、采集页聚焦集合 `37 passed`；compileall 和 diff check 通过。现有地图点击跟随链路可作为单角色附近点程序移动实验入口，默认模拟模式仍不发送真实输入。
## 2026-09-28 PoE2 独立地图点移动实验与输出诊断

- **边界确认**：实机 Host 日志已证明跟随规划产生的 `program.state` 会进入
  `ReportLoop -> ViGEm SubmitReport`；“人物不移动”不能再按定位/路线失败处理。
- **实验隔离**：在 PoE2 实验页新增独立地图点移动实验。它只依赖当前双人视觉位置、
  当前地图和通用 `ProgramFollowOutput`，不启动跟随策略、不启用 LAN。
- **真实输入门禁**：必须选择角色、点击地图目标，并通过确认框后才申请程序租约；
  每 50ms 持续写摇杆，遇到到达、阻塞、位置失效或停止立即中性并释放。
- **可观测性**：`ProgramGamepadOutput.diagnostics()` 读取 Host status/state；跟随
  每 10 tick 记录输出边界；页面右侧增加最多 500 行会话日志，不压缩截图和大地图。
- **验证**：Python 相关回归 38 passed（本轮目标集），`compileall`、`git diff --check`
  通过；Host C# 回归 57 passed。真实游戏移动仍待管理员工作台实测确认。

## [诊断] 2026-09-29 — 独立真实手柄移动实验

### A. 本轮目标（阅读前声明）

**目标文件：** `tools/debug/program_input_probe.py`、`src/auto_modules/adapters/virtual_gamepad/program_output.py`、`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`；必要时追踪 Host 的 program/state/report 路径。
**本轮想弄清楚：** 游戏窗口前台、管理员完整性级别、控制器槽位与持续摇杆写入，哪一环阻止了游戏内真实位移；实验必须短时自动释放，并用测试前后人物坐标验证。

### C. 本轮发现

**关键发现：** (verified) 非管理员进程读 PoE2 内存、连接管理员 Host 管道均返回 WinError 5；经用户 UAC 确认后管理员只读探针成功连接 Host 并读取当前人物 grid=(529.50,1088.50)。首次真实移动探针在开始写入前检测 `focus_lost`，`ticks=0`，因此没有发送方向帧。
**修订的旧结论：** Host 连通或路线 ready 并不能证明人物移动；这轮确认失败发生于前台门禁之前，而非移动方向或导航计算。
**覆盖进度更新：** `tools/debug/program_input_probe.py` 浅读（原探针只发 120ms）；`program_output.py` (partial)（确认 start/write/stop 契约，未复读整个 Host）；`capture_test_page.py` (partial)（确认独立实验停止路径）；新增 `poe2_movement_probe.py` 与安全门禁测试 `7 passed`。
**下一轮计划：** 用户切回游戏需要时间；在发送前等待 10 秒，再以同一短时前台门禁探针验证位置位移。

## [SYNC] 2026-09-29 — 移动前等待游戏前台

### A. SYNC 范围声明

**触发任务：** 用户明确要求输入前 10 秒等待以便切回 PoE2。
**直接变更文件：** `tools/debug/poe2_movement_probe.py`、对应安全测试。
**预计连带影响：** 只影响独立探针的输入时序；保留前台校验、中性释放、最长两秒输出与管理员门禁，不改变正式跟随。

### C. SYNC 结果

**实机结果：** 管理员 P1 独立探针在发送前等待 10.002 秒；PoE2 前台门禁通过后，1.2 秒内写入 24 帧。Host 记录 `ViGEm SubmitReport controller=1` 左摇杆 X 从 9000 增至 32767；同一 `P2_7:54BE4D92` 实例的人物 grid 从 `(529.50,1088.50)` 变为 `(557.02,1055.46)`，位移 43.00 网格。用户画面确认确有移动。`run_bounded_output` 的 finally 中性并释放；其调用正常返回。没有将此误记为已验证路径规划。
**测试：** 新安全门禁和通用程序输出聚焦回归 7 passed，探针编译通过。
**CODEBASE 同步待办：** 更新独立诊断脚本职责、函数索引、输出链路和焦点/地图实例风险。

## [诊断] 2026-09-29 — 重启后穿门规划实验

### A. 本轮目标（阅读前声明）

**目标文件：** `experimental/multiplayer_follow/runtime.py`、`capture_test_page.py`、`terrain_reference.py` 及相关测试/地图元数据。
**本轮想弄清楚：** 重启后当前实例是否仍与存档地形一致、P1 到门后目标有无静态无碰撞路径、视觉位置与摇杆方向是否一致；仅在这些门禁通过后试行有界实机路径。

## [SYNC] 2026-09-29 — 穿门规划器障碍值契约修复

### A. SYNC 范围声明

**触发任务：** 旧地图只读离线复盘中，可走连通区内的起点与门后候选点被 PoE2 跟随运行时误判为无安全路线。
**直接变更文件：** `experimental/multiplayer_follow/runtime.py`、对应路线回归测试；尚未发送任何真实输入。
**预计连带影响：** 通用 `PathFinder` 的 0/255 障碍图契约、`line_is_walkable` 原图逐段验算、实验页地图点移动和模拟跟随。
**待验证根因：** 运行时若把 255 障碍压成 1，规划器的 50 阈值会把墙视作空地，候选直线随后被原图校验拒绝。先补失败回归，再修复并复跑旧图。

### C. SYNC 结果

**根因已证实：** `SimulatedFollowRuntime` 曾把非零墙体压成 1；通用 `PathFinder` 只把大于 50 视作墙，原图几何却把任何非零当墙。门口回归修复前失败，改为 0/255 后通过；另补起点→首节点、末节点→终点的碰撞复核，单独的缺口回归修复前失败、修复后通过。
**离线复盘：** 9 月 28 日旧实例 `P2_7:54BE4D92` 存档上，旧 P1 约 `(557,1055)` 到候选 `(630,925)` 得到 26 节点路线，起点、全部中间段、终点连接段均通过原图 corner-safe 校验。这不是重启后当前实例的实机穿门证明。
**聚焦回归：** 跟随运行时 15 passed；此前合并路径/页面/输出组 50 passed，新增连接段回归后合计应为 51，待最终复跑。通用寻路器源码未改；三条旧测试显式禁用 30 像素起点清墙后通过。
**实机门禁：** 重启后 PoE2 与 Host 在运行，但当前地图存档仍为旧实例。一次管理员只读校验的 UAC 被取消，故没有读取当前人物/地图，也没有发送新输入。默认地图→摇杆轴基尚未双轴标定，不能把旧图路线当作当前可执行路线。
**下一步：** 获得用户确认的管理员只读访问后刷新当前地图/人物实例；标定短时双轴位移；先短程闭环验证方向，再以当前地图安全落点测试门口。失焦、位置过期、地图实例变化或超时立即中性释放；动态门需要额外交互时停止并如实记录。

## [SYNC] 2026-10-01 — 门后路径实验输入门禁

### A. SYNC 范围声明

**直接变更文件：** adapters/windows/window_finder.py、adapters/windows/__init__.py、ui/modes/poe2_live_terrain/capture_test_page.py、相关 CODEBASE 记录。
**目标：** 让实验页在真实门后路线测试前自动找到 PoE2 PID/HWND，同时不抢焦点、不移动鼠标，并阻止过期视觉状态继续输出。

### C. SYNC 结果

- 新增只读窗口查询：按进程枚举可见顶层窗口，读取 HWND、标题、类名、矩形和 PID；提供前台 PID 检查，不调用 SetForegroundWindow、SetCursorPos 或鼠标输入 API。
- 程序移动点击确认后等待 10 秒，用户切回 PoE2 后才申请 Host lease；每 50ms tick 检查 PoE2 前台、视觉定位年龄不超过 700ms、总运行时间不超过 30 秒。
- 失焦、窗口缺失、定位帧过期或超时均立即发送中性并释放；规划器仍只输出路线和向量，窗口门禁属于输入适配边界。
- 聚焦回归：44 passed；compileall 通过。当前尚未发送门后实机输入；仍需用重启后的当前实例重新获取地图并完成双轴方向标定后再测试。

## [SYNC] 2026-10-01 — PoE2 路线输入映射与实验页布局

### A. SYNC 范围声明

**触发任务：** 用户反馈真实路线移动后卡在墙前，并要求 PoE 实验页将控制/日志移到侧栏，避免截图和大地图被压缩。
**直接变更文件：** `src/auto_modules/features/poe2/live_terrain/movement.py`、`src/auto_modules/features/poe2/live_terrain/__init__.py`、`src/auto_modules/ui/main_window.py`、`tools/debug/poe2_route_probe.py`、`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/poe2_live_terrain/test_movement_basis.py`。
**预计连带影响：** PoE 实验页真实手柄输出、独立路线探针、采集页 Qt 布局和相关回归；通用 `ProgramGamepadOutput` 默认基底与绘图模式不变。
**本轮疑问：** native 地图路线已通过原图碰撞校验但实机向墙偏移，需核对游戏等距摄像机的 map-space 到 left-stick 变换是否缺少约 45° 投影。

### C. SYNC 结果

**根因确认：** (verified) 当前地图 `P2_7:54BE4D92` 的 native 坐标与数组原点一致；路线碰撞检查没有发现墙体穿越。此前固定摇杆 `(1,0)` 的实测位移为 native `(+27.52,-33.04)`，说明 PoE2 左摇杆与 native 地图不是简单 Y 翻转，而是约 45° 的等距投影。路线探针按旧基底输出时会斜向撞墙，日志中的 `route.finished` 只移动 `19.55` 网格且未到目标，不能算穿门成功。
**实现：** 新增 PoE2 适配层常量 `POE2_MAP_TO_STICK_BASIS=(0.5,-0.5,0.5,0.5)`；正式 PoE2 实验页的程序输出工厂和独立 `poe2_route_probe.py` 使用该基底，通用 `ProgramGamepadOutput` 默认值、绘图模式及其他游戏不变。采集页重排为主视觉区（截图/预处理/特征 + 大地图）和可滚动侧栏（控制、状态、跟随/移动实验、日志），不改识别、地图和定位链路。
**验证：** PoE2 页面、采集页、程序输出、跟随运行时和新基底测试 `49 passed`；`compileall`、`git diff --check` 通过；离屏布局检查在 1600x900 下得到主地图约 `1186x562`、预览单格约 `391x220`、侧栏宽 `360`。新基底尚未在游戏内做第二个正交方向实测，因此门后路线仍需重新执行短程验证，不能把本轮改动报告为实机穿门通过。
**下一步：** 重新启动 PoE2 后先用独立短程实验验证 native X/Y 两个方向的位移符号，再用当前实例刷新地图执行门后路线；若仍卡墙，记录每 tick 的 before/after native 坐标和输出向量，继续校准适配层，而不是修改通用寻路器。

## [SYNC] 2026-10-01 — 首帧旋转注册进入路线输入

### A. SYNC 范围声明

**触发任务：** 用户明确指出路线卡墙的坐标根因是“获取的大地图方向与游戏小地图方向不一致”，不能只旋转展示地图。
**直接变更文件：** `src/auto_modules/core/localization/displacement.py`、`src/auto_modules/features/poe2/live_terrain/movement.py`、`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`、`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` 及对应测试。

### C. SYNC 结果

**历史结论（已修订）：** 路线仍在 native wall map 上规划，点击目标也已由显示坐标逆变换回 native；当时曾认为真实输入需要继续应用首帧 registration 的旋转/镜像。实机 Host 轴值复盘证明这是二次变换，会把正确路线转向错误墙体。
**当前实现：** `inverse_transform_local_displacement()` 和 `native_map_vector_to_local()` 保留为通用几何能力，但 PoE2 程序跟随和地图点移动改用 `native_route_vector_for_program_output()` 原样传递 reference/native 向量，再由 `ProgramGamepadOutput` 唯一应用 PoE2 等距基底；缺少 map transform 仍 fail-closed。
**验证：** 旧旋转/镜像/缩放几何回归保留，新增加二次变换回归共 `43 passed`，compileall 通过；尚未发送新的实机输入，因此门后路线尚未宣称通过。

## [SYNC] 2026-10-01 — Qt 实时定位崩溃取证与边界稳定化

### A. SYNC 范围声明

**触发任务：** 用户反馈点击双人实时/移动实验后页面容易报错退出、卡死，要求检查日志和完整链路。
**证据范围：** `data/logs/poe2_live_terrain.log`、Windows Application Error 事件、双人实时页面和 Qt 图像转换边界。
**安全边界：** 本轮未发送新的真实手柄输入，未启动 LAN；只做离线回归和原生崩溃证据核对。

### C. SYNC 结果

- 实机日志确认首帧接受、双人实时约 600 帧持续 tracking，`memory_reads=1`，无 recovery 风暴、Host lease 错误或 Python traceback。
- Windows 事件确认故障模块为 `Qt6Gui.dll`，异常码 `0xc0000005`；不能把它误判为定位算法失败。
- `frame_pixmap()` 的非连续 NumPy 视图已可稳定复现 `BufferError`；现已在 Qt 边界做 `uint8 + ascontiguousarray + QImage.copy()`，防止 Python 异常和 Qt 借用失效内存。
- `ScalableMapWidget.focus_on_point()` 跳过未变化的滚动目标；双人帧路径复用 `extract_combined_with_processed()` 的预处理结果，并记录分段耗时，降低主线程重复计算和重绘压力。

### V. 验证与未决项

聚焦回归 `37 passed`，compileall 和 `git diff --check` 通过。Qt6Gui 原生访问冲突尚未在离线压力测试中复现，下一次实机测试必须保存 `dual_motion.timing` 日志并对照 Application Error 时间；若仍发生崩溃，继续检查 Qt 对象关闭顺序和线程归属，而不是调整定位阈值。

## [SYNC] 2026-10-01 — 地图点击目标即时反馈与坐标链路日志

### A. SYNC 范围声明

**触发任务：** 用户要求点击定位地图后立即看到点击位置，并能通过详细日志核对显示坐标、native 坐标及旋转/镜像/比例变换。
**直接变更文件：** `ui/widgets/scalable_map.py`、`ui/modes/poe2_live_terrain/capture_test_page.py` 及对应 Qt 回归。
**安全边界：** 本轮只处理显示和记录；点击未启动跟随时不创建 runtime，不发送手柄，不启动 LAN。

### B. 影响分析与重读范围

- `ScalableMapWidget.pixel_clicked` 发出的是未缩放原图 pixmap 坐标；PoE2 页面先逆 `SimilarityTransform2D` 回 native，再做边界判断。
- 原 `set_overlay()` 会整体替换 marker 状态，点击发生在两帧之间时会丢掉人物/路线；新增 `set_target()` 只改目标标记。
- 双人实时和跟随 overlay 均显式带入页面的点击目标状态，停止跟随后清除，避免把模拟目标冒充人物位置。

### C. SYNC 结果

- 页面保存 `source_pixmap -> native -> display` 三份点击坐标，并计算 display 正向回投的 round-trip error。
- `map_click.received/transformed/accepted/rejected/cleared` 日志包含模式、角度、镜像、比例、平移、source size、地图边界和拒绝原因，便于分析坐标漂移和方向错误。
- 离线 Qt 回归覆盖“跟随未启动也即时显示”“只更新目标不覆盖人物 marker”“停止清理目标”。聚焦 `3 passed`，PoE2 页面/采集/地图集合 `31 passed`；未发送真实输入或启动 LAN。

## [SYNC] 2026-10-01 — 实机点击/程序移动日志复盘

### A. 证据

当前运行实例 `P2_7:54BE4D92` 的双人首帧在 21:01:29 `accepted`：角度 `221°`、水平镜像、比例 `0.863`，两个 anchor error 约 `0.457`，pair confidence `0.819`。21:01—21:02 两次地图目标点击均完成逆/正变换闭环（round-trip `0.0000`），两次程序移动均找到 PoE2 窗口、成功申请 controller 1、发送非零左摇杆，随后 neutral/release，无 Host 或 Python 错误。双人 tracker 长时间 `tracking`，仅 frame 1351/1352 短暂 degraded 后恢复。

### B. 未决根因边界

日志尚不能证明人物实际移动量：程序移动只记录 tick 1/8/16，停止时没有记录 reason；双人 tick 只记录身份和 quality，没有记录 native 位置前后值。因此“输入已发送”和“游戏人物实际到达/撞墙/被失焦停止”目前不能区分。另有性能证据：30 FPS（33ms）目标下 timing 平均约 66.6ms，186/187 个样本超过 33ms，峰值 298.4ms；这会造成实时画面约 15 FPS，但不是首帧匹配失败。

### C. 下一次最小取证

在不改算法的前提下，先补充 `program_probe.stop` reason、每次输出的 target/current native/distance 和双人 tracker 的 player native before/after delta，再用一个近距离目标复测；只有拿到位置变化或明确停止原因后，才判断是输入方向、路径规划、游戏窗口接收还是性能背压。

## [SYNC] 2026-10-01 — Xbox 路线向量与移动诊断闭环

### A. 范围声明

**触发任务：** 用户指出手柄移动与鼠标点击不是同一模型，要求核对寻路、避障、移动输入，并确保地图转换后的坐标贯穿路线链路。
**直接变更文件：** `tools/debug/poe2_route_probe.py`、`adapters/virtual_gamepad/program_output.py`、`features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`、`ui/modes/poe2_live_terrain/capture_test_page.py`。
**安全边界：** 本轮未发送新的真实输入；只修复离线路线探针错误并增加已有输入链的只读诊断。

### B. 关键发现与结果

- 页面点击、墙体、A*、碰撞、到达判断使用同一 oriented reference/native 坐标；旧版本曾在输入前再次经首帧 registration 逆变换到局部小地图方向，现已确认这是二次变换错误。观察 DTO 显式标记 `coordinate_space=reference_native`。
- 路线探针原来把非零段 `vector` 计算缩进到 `distance < 1e-6` 的 `continue` 分支；已修复，非零路径段现在会实际生成局部方向向量。
- `ProgramGamepadOutput.diagnostics()` 增加 `basis`、`last_command.input_vector`、`basis_vector`、`axes`、`ttl_ms`；follow runtime 增加 route 点数/端点；页面每 5 tick 写入 current/target/distance/native/input vector，并在停止时写 `program_probe.stop` reason/ticks。
- 离线移动/跟随/Host/页面聚焦回归 `45 passed`，compileall 通过。真实人物位移、穿门避障和长距离方向仍需用户在当前实例用新日志复测后确认。

## [SYNC] 2026-10-01 — Native 路线到 Xbox 输出的单一边界

### 影响分析

- `capture_test_page.py` 的地图点击、墙体、A*、碰撞和到达判断继续使用
  `reference/native` 坐标；registration 只负责 source/display 与 native 的转换。
- `ProgramFollowOutput` 与 `poe2_route_probe.py` 不再调用 registration 逆变换，改用
  `native_route_vector_for_program_output()`；该接口只做二维 finite 校验。
- `ProgramGamepadOutput` 保持唯一的 `reference/native -> stick` 适配边界，避免重复
 旋转/镜像，也不改变通用 gamepad 默认基底。

### 结果

新增回归覆盖 angle `221°`、horizontal reflection 和 scale `0.863` 的错误组合，确认
direct native basis 与旧二次变换输出不同；相关聚焦测试 `43 passed`。本轮没有真实设备
输入或网络副作用。旧文档中“输入前逆 registration”的结论已由本节修订。

## [SYNC] 2026-10-01 — 移动实验全链路日志

移动实验边界现在分别记录点击转换、地图实例/墙体上下文、A* 尝试与接受倍率、路线长度
和逐段碰撞、native→input→Host 轴值、视觉帧年龄、租约最终状态，以及 native 初始/最终
位置和位移。路线 overlay 与这些日志共用同一 reference/native → display 变换；日志增强
不改变寻路、输入或 Host 协议。聚焦回归 `48 passed`，未发送真实输入。

## [SYNC] 2026-10-02 — 首帧证据拆分与安全闭环

本轮把双人首帧接受分数拆成 anchor identity、pair geometry、shape evidence 和 profile
consistency 四个独立证据；没有改变单人定位或双人“禁用人物 mask”的契约。通用 routing
新增可选 clearance cost map 与 A* soft traversal cost；PoE2 实验跟随组合显式启用安全
膨胀/靠墙惩罚，`VectorPathTracker` 仅对不可变墙图缓存路线校验。实验 runtime 增加无进度
watchdog 和左右交替侧向恢复 waypoint，恢复失败才进入 BLOCKED/cooldown。验证为 PoE2
实验集与 PathFinder `308 passed`，全仓 `872 passed, 2 skipped`，另有环境缺少
`pydirectinput` 的既有 distribution 测试失败；未发送真实手柄或网络输入。

页面 `program_probe.motion` 与 `follow_experiment.motion` 现在同时写入 clearance 参数、
无进度 tick、恢复次数和恢复目标，便于把“路线贴墙”“摇杆未产生位移”“恢复方向无路”分开。

## [SYNC] 2026-10-02 — 双人候选去重与视觉新鲜度边界

双人定位的候选适配层增加了几何非极大值抑制，负责清除同一 marker 的轮廓/核心重复，
而身份配对、方向和 native 锚点仍由双人注册器负责，未把 PoE2 颜色规则下沉到通用视觉层。
程序移动页保留视觉帧的真实采集时间，避免 UI 控制循环把旧位置变成新鲜位置；输入停止策略仍
由 runtime 的 TTL 和输出适配器共同负责。路线候选在通用 PathFinder 输出之后由 PoE2 组合层按
长度与清距暴露评分选择，通用寻路默认参数不变。形状缓存持有参考数组，修复跨实例距离场串用，
属于通用实验注册器的生命周期修复。

PoE2 跟随 runtime 现在使用有界局部重规划：目标在刷新带内移动时复用已验证路线，只有目标
位移、路线偏离、碰撞失效或 stalled recovery 才重新调用多尺度 A*。这些阈值和诊断字段留在
PoE2 业务组合层，通用 PathFinder 仍只负责给定起终点的障碍搜索。
## [SYNC] 2026-10-02 — 双人实时 latest-frame 与导航闭环诊断

- routing/pathfinder 坐标网格改为 ceil，避免非整除 native 地图边界被截断。
- PoE2 实验跟随 runtime 增加 command/native observed displacement alignment 诊断；方向失配连续三帧触发现有侧向恢复，不把业务概念下沉到 core routing。
- 新增 `Poe2DualMotionWorker` 作为 UI composition 层 adapter：worker 只负责注入的 capture/recognizer/tracker，latest-only channel 丢弃旧帧，内存读取仍只在首帧/恢复边界发生。
- 聚焦回归 `64 passed`，compileall 通过；真实手柄与双人 90% 真值仍未验证。

## [SYNC] 2026-10-02 — 运动闭环的状态边界与快照协同

- 新增实验层运动 DTO 和只读 `MotionSnapshot`；recognition/localization、复杂度、序贯反馈、路线
  和 output adapter 通过显式接口连接，未把 PoE2 或 Xbox 术语下沉到通用 routing。
- 复杂度迟滞和输入校准均按 role 建立独立状态；视觉采集时间贯穿 runtime，过期帧不会被控制 timer
  伪装成新鲜观测。`ProgramFollowOutput` 只负责 lease/output side effect，并使用 command duration。
- 现有 A*/角色碰撞半径/局部控制/卡墙恢复保持原边界，闭环只组合这些能力；真实输入仍是显式实验门禁。

## [SYNC] 2026-10-02 — 路线安全策略与闭环时序复盘

- `SimulatedFollowRuntime` 继续把 A* 拓扑、角色膨胀碰撞和局部控制分层；新增的 relaxed clearance
  只是 PoE2 实验组合在严格候选为空时的显式策略，不下沉到通用 PathFinder，也不覆盖碰撞校验。
- 该策略只对 `footprint_radius>0` 生效，记录严格/回退候选数量和选择模式，避免把业务参数偷偷改变为
  通用默认值。
- `ClosedLoopMotionController` 的命令持续时间是控制器契约，UI timer 只承担调度；避免界面调度抖动改变
  输出语义。页面日志保持坐标、清距、视觉年龄和 Host 诊断的边界。

## [SYNC] 2026-10-02 — 实测窄段回放与适配器关闭安全

- PoE2 组合层的 relaxed clearance 继续只在显式角色 footprint 存在时启用；本次真实地图回放确认
  `radius=2`、最低清距 `2.739` 的路线由膨胀碰撞图保证实体安全，未改变通用 PathFinder 默认策略。
- `SquareScreenCapture` 属于平台资源适配器；关闭操作现在先断开资源引用、再捕获释放异常，避免
  mss 的线程本地 bitmap 在 Qt/worker 跨线程销毁时把资源清理异常升级为工作台退出。
- `Poe2DualMotionWorker` 在 UI 停止路径提供有界等待接口，避免 latest-frame worker 仍持有截图对象时
  页面 QObject 已经销毁；超时仅记录告警，保持主线程可恢复。

## [SYNC] 2026-10-02 — 路线探针离线边界

路线调试工具新增纯离线入口，使用保存的 native wall layer 和显式 native 起终点验证
`SimulatedFollowRuntime` 的组合策略，不穿透进程、Host 或窗口控制边界。实机探针与页面统一显式
提供角色 footprint 和窄段安全余量；通用 PathFinder 默认策略未改变，`relaxed_clearance` 仍只在
PoE2 实验组合层启用。

## [SYNC] 2026-10-02 — PoE2 实验清距策略放宽

PoE2 业务组合将首选 `minimum_clearance` 调整为 `4.0`，角色半径为 `2.0` 时的回退硬下限为
`max(footprint_radius, 2.0)`。这是实验层对地图墙体厚度误差的容错策略；碰撞膨胀图仍负责实体
碰撞安全，通用 PathFinder 的默认清距契约未改变。

## [SYNC] 2026-10-02 — PoE2 中心线窄通道策略

PoE2 实验组合关闭 `inflate_collision`，以 native 墙体中心线作为硬碰撞边界；通用 runtime 的默认
膨胀能力保留。短视窗 `LocalMotionController` 和既有侧向恢复负责实际移动时的贴墙修正，避免把
业务地图中的窄门误判为不可通行。

## [SYNC] 2026-10-02 — 双人实时崩溃防护

- 双人实时 worker 的 capture、recognizer、Qt 渲染边界保持分离：线程本地 capture 只在所属线程释放，
  recognizer 为线程副本，Qt 图像由命名 contiguous buffer 脱离 NumPy 后再进入 `QImage.copy()`。
- UI 停止路径采用 stop + 有界 join；超时的 worker 进入退休集合，直到 finished 后才释放 Python 引用，
  不把业务策略或游戏输入逻辑下沉到通用层。
- 该修复只改变 PoE2 UI composition 的生命周期适配，不改变通用截图、定位和路由契约。

## [SYNC] 2026-10-02 — 局部恢复不可升级为全局不可达

- PoE2 实验跟随 runtime 的恢复策略仍保持在业务组合层：路径规划只接收 native wall map 和起终点，
  不知道门、角色或游戏规则。
- 卡墙状态先重算当前位置到目标的安全路线，再使用多组有限的侧向/前向候选；候选选择只消费已有
  `PathFinder`、几何碰撞校验和 `LocalMotionController`，没有复制底层路径算法。
- 只有局部路线和恢复候选全部失败才发布 `stalled_no_escape`，并通过 typed diagnostics 把候选数量、
  选择下标和规划结果交给 UI/日志。
- 单人定位 worker 的 stop/wait/retirement 属于 UI composition 的资源生命周期边界；runtime 和通用
  screenshot contract 未引入页面状态或 PoE2 术语。

## [SYNC] 2026-10-02 — 墙边 native 栅格边界恢复

- `(verified)` 本次真实停止点 `(575.748,1178.894)` 在 native wall layer 四舍五入后落到墙格
  `(576,1179)`，相邻 `(576,1180)` 是可行走；目标距离 `42.5996`，因此不是 arrival radius。
- `(verified)` 这是 PoE2 feature 组合中的连续坐标→raster 起点量化问题，不修改通用
  `core.routing.geometry.line_is_walkable()` 或 `PathFinder` 的硬碰撞契约。
- `SimulatedFollowRuntime._wall_start_recovery_command()` 只消费现有局部安全路线能力：在半径 12
  native 内找可行走起点，确认该点到真实目标有安全路线，再输出有限恢复脉冲；实际人物位置不被改写。
- 运行观察新增 `observed_position_metrics`，把原始人物栅格与路线使用的恢复起点分开记录，便于区分
  “人物真实位置”和“规划器临时起点”。新回归覆盖首次规划失败、连续同格帧和恢复后 `route_ready`。
- 离线路线探针不再绕过 runtime 直接调用 `_plan_safe_route()`；它通过同一 `tick()` 生成恢复向量，
  同时展示 `route_walkable`（含原始墙边观测段）与 `planning_route_walkable`（从临时起点开始）。
- 相同观测栅格/目标会复用已验证的恢复路线，只重算短脉冲方向；人物离开边界或目标超出刷新带时
  才重新执行局部 A*，避免墙边状态把 CPU 压满。
## 2026-10-02 — 接触证据下沉与 PoE2 局部适配

- 通用层新增 `core/routing/contact_evidence.py`：只处理命令向量、观测位移、方向一致性和连续无进展，不知道 PoE2、屏幕颜色或手柄传输。
- PoE2 实验层新增 `minimap_contact_adapter.py`：只把现有 wall mask 和人物屏幕点解释成前方墙体/左右清空度，保持人物 marker 层独立，禁止中心 mask。
- `multiplayer_follow.runtime` 通过 `update_local_contact()` 接收适配证据；局部脱困和重定位状态由业务运行时组合，不下沉游戏政策。
- `capture_test_page` 只负责把双人 worker 的同帧结果接到适配器，并在重定位请求时停止输入、调用既有恢复入口；程序输出适配器仍只负责 lease/axes/neutralize。

## 2026-10-02 — 墙角接触恢复优先级

- 实机无进展时，业务 runtime 不再让缓存的墙边微脉冲覆盖通用接触证据状态；
  `_contact_recovery_command()` 只在 PoE2 组合层把小地图左右空闲度转换为局部起点选择。
- 起点搜索仍复用通用路线规划和碰撞检查，人物真实观测位置不被改写，也不把人物膨胀规则下沉到
  `core.routing`；两次局部恢复失败后继续发布通用的安全停止/重定位信号。

## 2026-10-02 — 接触证据区分移动与方向校准

- `ContactMonitor` 只用命令幅度和实际位移判断“无进展”；命令与位移的夹角仍是观测诊断，避免把
  手柄延迟或 map→stick 基底误差混入墙体碰撞语义。
- PoE2 组合层保留方向错配的校准计数，但在小地图已有墙证据且人物有明显位移时不把它升级成
  墙体恢复；恢复仍只由连续无位移证据驱动，保持通用层与游戏策略边界。

## 2026-10-05 — 跟随输出的启动切窗边界

- 6 秒切窗等待属于 PoE2 UI 组合层的生命周期策略，不下沉到通用 runtime 或虚拟手柄适配器。
- `Poe2CaptureTestPage` 统一负责 `前台检查 → 启动延迟 → runtime 决策 → 输出 arm/write` 的顺序；地图点击只提交目标意图，不能直接取得输出所有权。
- 纯模拟会话不创建程序输出，因此不被切窗等待拖慢；停止/清图清除组合层延迟状态，保持 controller、device、feature instance 的状态隔离。

## 2026-10-05 — 手动领队与程序跟随器的观测边界

- 实时跟随组合层将手动领队作为目标观测源处理：它的可见坐标直接更新目标，不经过程序输出的 command-odometry innovation gate。
- `CommandRoleTracker` 的预测、视觉拒绝和重定位计数继续限定在程序控制角色；通用 tracker 本身不引入“领队”业务概念，边界由 PoE2 组合层按 `ControlMode`/角色选择实现。
## [SYNC] 2026-10-03 — 接触恢复门与双人重定位续跑

- 通用 `SimulatedFollowRuntime` 只新增 `contact_required_samples` 参数，并在每个角色实例化独立 `ContactMonitor`；默认仍为 2，PoE2 页面组合传 4。接触证据模块继续只处理命令/位移，不知道游戏、地图 UI 或内存。
- PoE2 页面组合拥有 recovery policy：接触恢复两次无可信位移后保存目标、角色和控制器，释放输入，强制调用已有双人首帧内存锚点/几何注册入口；成功后等待新鲜视觉 tracking 帧，再恢复原目标。重定位上下文和内存读取策略留在 UI/实验组合层，没有下沉到 core。
- 新增调用链：`_tick_program_move_probe()` → `stop_program_move_probe()` → `_start_dual_motion(recovery=True)` → `run_dual_first_frame_experiment(force_memory_read=True)` → `DualFirstFrameExperiment.read_anchors/register()`；worker/sync 新帧 → `_maybe_resume_program_probe_after_relocalization()` → `_start_program_move_probe_at()`。
- 失败边界：首帧拒绝、恢复 worker 异常、角色不可见或帧过期都 fail closed；10 秒冷却阻止高频内存读取。真实 Host 输出只有在原有显式确认和前台门禁成功后才重新申请。
