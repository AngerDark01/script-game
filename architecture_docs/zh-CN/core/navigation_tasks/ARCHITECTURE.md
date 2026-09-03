# 统一导航任务系统架构

## 系统角色

`core/navigation_tasks` 应成为可复用的编排系统，把路线目标和事件目标转成统一的导航 intent stream。

理想接口：

```text
当前位置 + 路线数据 + 事件任务 + 地图/寻路依赖
    -> selected task
    -> movement step or event action
    -> NavigationIntent
```

## EventAction -> NavigationIntent seam

`navigation_tasks` 是事件动作进入真实导航/输入路径前的唯一翻译层。事件系统只返回 `EventAction`，导航任务系统把它转换为 `NavigationIntent`，GUI/input 层再消费 intent 执行点击或按键。

规则：

- 具体 event handler 不能直接调用 `MotionController`、`InputDriver`、GUI widget 或 PySide 对象。
- `core/events` 只能表达 generic action：`MOVE_TO`、`CLICK_SCREEN`、`PRESS_KEY`、`WAIT`、`COMPLETE`、`FAIL`。
- `core/navigation_tasks/intent_factory.py` 是 `EventAction -> NavigationIntent` 的稳定 seam。
- `core/navigation_tasks/event_task_runner.py` 负责事件靠近 gate、调用 `EventCoordinator.run_task()`、处理 terminal action，并把 action 交给 `intent_factory`。
- `NavigationIntent` 仍是 GUI/input 执行层唯一消费对象；事件系统不能绕过它。

当前不拆 `intent_factory.py`。它虽然同时处理 movement step 和 event action，但接口窄、调用方少、语义集中；拆成多个更小文件会降低 locality。

## 已验证当前接口

主要调用方：`gui/modes/navigation/widget.py::_navigation_loop_unified()`；其中 `gui/modes/navigation/runtime/loop.py::update_navigation_task_controller()` 负责把 GUI 当前帧状态组装成 `NavigationUpdateContext`。

当前调用形态：

```python
context = NavigationUpdateContext(
    now_ms=now_ms,
    localization=LocalizationSnapshot(...),
    route=main_route,
    planning=PlanningSnapshot(...),
    events=EventRuntimeSnapshot(...),
)
intent = navigation_task_controller.update_context(context)
```

旧 `update(**kwargs)` 宽接口已删除。现在调用方仍需要知道本帧定位、路线、规划依赖和事件运行态，但这些字段先进入 context/snapshot，而不是散落为十几个关键字参数。这是后续继续收窄 GUI runtime loop 的基础。

稳定调用形态：

```python
intent = task_controller.update_context(NavigationUpdateContext(...))
```

`NavigationUpdateContext` 分组：

- localization snapshot
- route snapshot
- event snapshot/runner adapter
- path planning dependencies
- timing/options

## 当前模块地图

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `models.py` | Task、movement step、navigation intent 数据模型。 | GUI、route、movement、event 系统之间的稳定契约。 |
| `task_builder.py` | 把 route/event tasks 构造成统一 list。 | 适合成为纯 task composition interface。 |
| `scheduler.py` | 选择当前 required/exit/event task。 | 应把优先级规则藏在窄 selection interface 后。 |
| `controller.py` | `NavigationTaskController` public facade 和状态拥有者。 | 旧入口保留，主 update 委托 pipeline，runtime 细节委托 `controller_runtime/`，并持有 `event_hooks`。 |
| `controller_runtime/__init__.py` | controller runtime helper package 入口。 | 聚合 lifecycle/localization/progress/relocalization。 |
| `controller_runtime/lifecycle.py` | route load、reset、start/stop、route validity、intent click record。 | 控制器生命周期和轻副作用集中层。 |
| `controller_runtime/localization.py` | raw/trusted/control position 更新、jump reject、route progress 单调推进。 | 定位平滑策略层。 |
| `controller_runtime/progress.py` | required point 下一目标和到达完成记录。 | 静态路线进度状态层。 |
| `controller_runtime/relocalization.py` | 坐标恢复请求消费和 WAIT intent 构造。 | forced relocalization intent adapter。 |
| `movement_executor.py` | route/event movement 的 stateful facade，保留 `MovementExecutor` 和旧私有方法入口。 | 只持有状态和兼容入口，具体流程委托 movement helper。 |
| `movement/__init__.py` | movement helper package 入口。 | 聚合 `pipeline/path_maintenance/path_planner/recovery/utils`，并允许 `from core.navigation_tasks.movement import movement_step`。 |
| `movement/pipeline.py` | `MovementExecutor.step()` 的路径复用、lookahead、点击节流、卡住恢复主流程。 | movement 编排层，可独立阅读单帧移动决策。 |
| `movement/path_maintenance.py` | 判断是否重规划、写回路径状态、输出规划日志。 | movement path state 管理层。 |
| `movement/path_planner.py` | anchor-aware A*、direct A*、fallback probe 路径规划。 | movement planning 策略层，依赖 `core.routing`。 |
| `movement/recovery.py` | local probe、stuck detection、recovery probe。 | movement recovery 策略层。 |
| `movement/utils.py` | 坐标 float/int 标准化。 | 小型共享工具。 |
| `route_context.py` | route progress、projection、corridor anchors。 | 好的可复用几何/状态模块。 |
| `coordinate/__init__.py` | coordinate diagnostics package 入口。 | 聚合 `CoordinateDiagnostics`、DTO、日志、格式化、定位诊断、导航诊断和重定位生命周期。 |
| `coordinate/diagnostics.py` | 坐标漂移诊断和 forced relocalization stateful facade。 | 保留 `CoordinateDiagnostics` public 方法和旧私有 wrapper，具体诊断流程继续委托 coordinate helper。 |
| `coordinate/localization.py` | 定位帧诊断、F2F 来源跟踪、visual mismatch 证据记录。 | 定位诊断策略层。 |
| `coordinate/navigation.py` | route deviation、arrival mismatch、near-target stall 诊断。 | 任务/路线诊断策略层。 |
| `coordinate/relocalization.py` | 强制重定位请求打分、生成、消费、接受、拒绝。 | relocalization request 生命周期层。 |
| `coordinate/log.py` | 独立 coordinate diagnostics 文件日志 writer。 | 副作用集中到日志 adapter。 |
| `coordinate/formatting.py` | 坐标、registration、日志字段格式化 helper。 | 纯工具层。 |
| `coordinate/models.py` | `CoordinateRelocalizationRequest` DTO。 | 请求数据契约。 |
| `event_approach/__init__.py` | Event approach stateful facade package，保留 `EventApproachController` 和旧私有方法入口。 | 属于 navigation 层，不应下沉到具体事件包；具体流程委托 event approach helper。 |
| `event_approach/models.py` | Event approach config/result DTO。 | 事件靠近 gate 的稳定数据契约，`EventApproachResult` 携带 `visible/became_visible`。 |
| `event_approach/pipeline.py` | `EventApproachController.update()` 的 far/approach/settling/ready 主流程。 | event approach 编排层，不直接调用 event handler。 |
| `event_approach/motion.py` | movement step 到 event approach intent 的转换。 | 只衔接 MovementExecutor 和 NavigationIntent。 |
| `event_approach/settle.py` | 事件触发前停稳等待和稳定帧判定。 | 负责写 settle 状态，不处理路径规划。 |
| `event_approach/geometry.py` | 真实视野判定、停靠点计算和坐标标准化。 | 纯几何/格式化 helper。 |
| `debug.py` | Navigation task logging。 | 应保持 adapter-like，不影响核心决策。 |

## 当前深模块

这些模块已有有用深度，应大体保留：

- `models.py` - navigation task、movement step、intent 的稳定 DTO/enums。
- `task_builder.py` - 把 route goals 和 event tasks 合成统一 task list。
- `scheduler.py` - 应用 route/event selection policy。
- `route_context.py` - route projection 和 corridor anchor logic。
- `movement_executor.py` - movement stateful facade，保留旧入口；`movement/pipeline.py` - path planning、lookahead、click throttling、stuck recovery、anchor/fallback handling 的单帧编排；`movement/path_planner.py` / `movement/path_maintenance.py` / `movement/recovery.py` 分别承接规划、路径状态维护和恢复探测。
- `coordinate/diagnostics.py` - coordinate diagnostics 真实 stateful facade；`coordinate/localization.py` / `coordinate/navigation.py` / `coordinate/relocalization.py` 分别承接定位证据、导航状态证据和强制重定位请求生命周期。旧 `coordinate_diagnostics.py` 已删除。
- `event_approach/__init__.py` - event approach stateful facade package，保留旧入口；`event_approach/pipeline.py` / `event_approach/motion.py` / `event_approach/settle.py` / `event_approach/geometry.py` 分别承接主流程、movement intent、停稳 gate 和几何计算。

当前主要浅点已从 `controller.py` 转移到 `update_pipeline.py` 的主流程编排：`controller.py` 已进一步降为 facade/state owner，但 update pipeline 仍集中串接定位、诊断、task build、selection 和 runner 调用。

## Controller Runtime 抽取结果

`NavigationTaskController` 仍是外部稳定入口，推荐从 `core.navigation_tasks` 或 `core.navigation_tasks.controller` 导入；`update_context()` 是唯一帧更新入口。`load_route()`、`reset_runtime()`、`start()`、`stop()`、`has_valid_route()`、`observe_localization()`、`_consume_relocalization_intent()`、`_update_required_progress()`、`_next_required_index()`、`record_intent_click()` 继续存在，内部委托 `controller_runtime/` 子包。旧 `update(**kwargs)` 和 `NavigationUpdateContext.from_legacy_kwargs()` 已删除。

当前内部职责拆分：
- `controller_runtime.lifecycle.load_route()` / `reset_runtime()` / `start()` / `stop()` / `has_valid_route()` / `record_intent_click()`：承接控制器生命周期、路线装载、运行状态清理和点击记录。
- `controller_runtime.localization.observe_localization()`：承接 raw/trusted/control position 更新、jump reject、confidence alpha 和 route progress 单调推进。
- `controller_runtime.progress.update_required_progress()` / `next_required_index()`：承接 required point 到达判定、完成记录、movement reset 和 active task 清理。
- `controller_runtime.relocalization.consume_relocalization_intent()`：承接 coordinate diagnostics request 消费、movement reset、日志和 WAIT intent metadata。

语义边界保持不变：controller facade 仍拥有所有 runtime 字段；helper 只接收 controller 实例并写回原字段，不把状态转移到独立对象里。

## Movement Executor 抽取结果

`MovementExecutor` 仍是外部稳定入口，`from core.navigation_tasks.movement_executor import MovementExecutor` 不变；`record_click()`、`step()` 以及 `_ensure_path()`、`_plan_path()`、`_local_probe()`、`_is_stuck()`、`_recovery_probe()` 等旧私有方法继续存在，便于旧调用方、调试脚本或临时 monkeypatch 不被打断。

当前内部职责拆分：
- `movement.pipeline.movement_step()`：承接 `step()` 主流程，负责单帧移动决策、投影、lookahead、exact path-goal click、点击节流和卡住恢复调度。
- `movement.path_maintenance.ensure_movement_path()`：判断是否需要重规划，写回 `path/path_lengths/path_goal/path_kind` 等状态，并记录 `nav movement planned`。
- `movement.path_planner.plan_movement_path()`：执行 anchor-aware planning、direct A* 和 fallback probe 选择；只依赖 `core.routing`，不触碰 GUI/input。
- `movement.recovery.local_probe()` / `recovery_probe()` / `is_movement_stuck()`：承接 fallback 探测点、恢复探测点和路径进度卡住判定。
- `movement.utils.float_point()` / `int_point()`：统一坐标标准化。

这个拆法把“状态拥有者”和“算法阶段”分开，但没有改变 movement 的行为边界：navigation_tasks 仍只输出 `NavigationIntent`，不执行真实鼠标或键盘输入；真实输入仍由 GUI 层消费 intent 后交给 `MotionController`。

## Coordinate Diagnostics 抽取结果

`CoordinateDiagnostics` 仍是外部稳定入口，真实 class 位于 `coordinate/diagnostics.py`，推荐从 `core.navigation_tasks.coordinate` 导入。旧 `core.navigation_tasks.coordinate_diagnostics` 文件已删除。`NavigationTaskController` 仍通过 `controller.coordinate_diagnostics.record_localization()`、`record_navigation_state()`、`consume_relocalization_request()` 和 `mark_relocalization_accepted()` 交互。类内旧私有方法名保留为 wrapper，避免临时诊断脚本或后续 monkeypatch 失效。

2026-06-04 诊断补充：`coordinate.localization.record_localization_evidence()` 新增轻量采样日志，每 `localization_sample_interval_ms=500` 写一条 `localization sample`。字段包含 raw/trusted/control、confidence、invalid_reason、active_task、registration source/conf/player/local/origin，以及 `shift`、`visual_delta_dist`、`visual_conf`、`template_top_left`、`search_offset`、`forced_global` 等关键 metadata。`coordinate.log.coord_log()` 仍写 `logs/coordinate_diagnostics.log`，同时会尝试桥接到当前 `event_log()`，所以实跑后可在 `logs/event_runs/*navigation.log` 中直接对齐事件观察器、掉落物 worker 和人物定位采样。

当前内部职责拆分：
- `coordinate.localization.record_localization_diagnostics()`：承接定位帧诊断、raw jump、raw/control gap、long F2F tracking 和 visual mismatch 证据。
- `coordinate.navigation.record_navigation_diagnostics()`：承接 route deviation、arrival mismatch、near target stall 日志。
- `coordinate/relocalization.py`：承接 request 消费、接受、超时拒绝、信号打分和 primary signal gate。
- `coordinate.log.coord_log()`：只负责写 `logs/coordinate_diagnostics.log`，不向 console/runtime log 输出。
- `coordinate/formatting.py`：承接 registration 字段提取、坐标标准化、距离和日志字段格式化。
- `coordinate/models.py`：承接 `CoordinateRelocalizationRequest` DTO。

语义边界保持不变：只有 `visual_mismatch` 和 F2F 下的极端 `raw_jump` 能进入强制重定位请求打分；route deviation、near-target stall、raw/control gap 和 long F2F tracking 仍只是诊断日志，不触发恢复。

## Event Approach 抽取结果

`EventApproachController` 仍是外部稳定入口，`NavigationTaskController` 仍通过 `controller.event_approach.is_released()`、`update()`、`release_task()`、`finish_task()` 和 `reset/reset_active()` 交互。旧私有方法 `_move_toward_event()`、`_settle_or_ready()`、`_is_event_in_real_view()`、`_approach_target_from_path()`、`_reset_settle()` 继续存在并委托 helper，避免临时诊断脚本或后续 monkeypatch 失效。当前额外维护 `_visible_hook_tasks`，用于保证同一个 event navigation task 的 `event_visible_target` 只触发一次。

当前内部职责拆分：
- `event_approach.pipeline.update_event_approach()`：承接 far/approach/settling/ready 主状态机；控制是否使用 route context、是否强制重规划、是否进入停稳 gate。
- `event_approach.motion.move_toward_event()`：承接 `MovementExecutor.step()` 调用和 `MOVE_MAP/WAIT` intent 构建。
- `event_approach.settle.settle_or_ready()`：承接 motion、stable frames、settle timer 和 ready 判定。
- `event_approach/geometry.py`：承接真实视野盒判定、路径终点前停靠点插值和坐标格式化。
- `event_approach/models.py`：承接 `EventApproachConfig`、`EventApproachResult` DTO；`EventApproachResult.visible` 表示当前帧目标在真实视野盒内，`became_visible` 表示本任务第一次进入真实视野。

语义边界保持不变：event approach gate 只决定“是否允许 event handler 运行”，不直接调用 handler、不执行真实输入；真实 event action 仍由 `event_task_runner.py` 在 gate released 之后调用 `EventCoordinator.run_task()`。`became_visible` 只作为 hook 触发事实，不改变 gate 的 ready/blocked 决策。

## 期望 Hooks

这些 hooks 可以让 navigation 和 events 交互，而不互相拥有内部实现：

- `on_localization_observed(snapshot)` - confidence/jump filtering 后。
- `before_task_build(context)` - adapter 可追加/转换动态 tasks。
- `after_task_build(tasks)` - diagnostics/debug capture。
- `before_task_selection(tasks, active_task_id)` - 检查候选。
- `after_task_selection(task, reason)` - logging、UI state、diagnostics。
- `before_event_handler(task)` - event approach gate 可延迟/释放 handler。
- `before_movement_plan(task, current_pos)` - 注入 anchors、avoid zones、event approach rules。
- `after_movement_step(step)` - diagnostics 和 overlay publication。
- `on_intent(intent)` - UI/input 层消费边界。
- `on_task_terminal(task, status)` - completed/failed cleanup。

Hook 位置：

- Navigation task hooks 属于 `core/navigation_tasks`，因为它们描述 route/task 生命周期。
- Event detection/handler hooks 属于 `core/events`。
- 跨系统 hooks 应由 adapter 桥接，不要让 task controller import GUI 或具体事件包。

## 大文件候选

`controller.py` 约 567 行，职责包括：

- 输入校验和 confidence handling。
- task list construction。
- scheduler invocation。
- event task execution bridge。
- movement executor bridge。
- diagnostics 和 debug metadata。
- intent creation。

目标拆分：

```text
controller.py                   # public facade, thin state owner
update_context.py                # NavigationUpdateContext and snapshots
localization_filter.py           # raw/trusted/control position filtering
static_task_runner.py            # required/exit task progression
event_task_runner.py             # EventCoordinator action -> navigation intent bridge
intent_factory.py                # MovementStep/EventAction/static terminal -> NavigationIntent
diagnostic_policy.py             # coordinate diagnostics integration
```

当前执行状态：

- `update_context.py` 定义 `LocalizationSnapshot`、`PlanningSnapshot`、`EventRuntimeSnapshot` 和 `NavigationUpdateContext`。
- GUI runtime helper 直接构造 `NavigationUpdateContext`，并调用 `NavigationTaskController.update_context(context)`。
- 旧 `NavigationTaskController.update(**kwargs)` 和 `NavigationUpdateContext.from_legacy_kwargs()` 已删除。
- `intent_factory.py` 已新增，承接 `MovementStep/EventAction -> NavigationIntent` 的转换。
- `controller.py` 作为状态 facade 保留；定位过滤、任务选择、static/event runner 主流程已委托 `update_pipeline.py`、`static_task_runner.py`、`event_task_runner.py` 和 `controller_runtime/`。

### `controller.py` 当前算法

当前 `update_context()` 做这些事：

1. 如果 route dict 与 `self.route` 不同，调用 `load_route()` 深拷贝并激活 controller。
2. 如果 inactive，返回 `NavigationIntent(message="navigation task controller inactive")`。
3. 判断最新 frame registration 是否是 forced global relocalization。
4. 通过 `observe_localization()` 过滤定位：
   - 拒绝缺失或低 confidence 位置；
   - 除非 confidence 高或 forced，否则拒绝大跳；
   - 更新 `trusted_pos`；
   - 平滑到 `control_pos`；
   - 投影到 route context 并更新 route progress。
5. 记录 localization diagnostics。
6. 定位无效则返回 `WAIT`。
7. 如果 forced relocalization 被接受：
   - 标记 diagnostics accepted；
   - reset movement；
   - 对 portal wait-result relocalization，可保留 active event task。
8. 把 pending relocalization request 消费成带 `metadata.force_relocalize=True` 的 `WAIT` intent。
9. required points 在 arrival radius 内时标记完成。
10. 从 `event_coordinator.tasks()` 拉动态 event tasks。
11. 用 `NavigationTaskBuilder` 构建统一 tasks。
12. 用 `NavigationTaskScheduler` 选任务。
13. 记录 navigation diagnostics。
14. task selection 后再次消费 relocalization request。
15. 如果 selected task 改变：
   - log transition；
   - reset movement；
   - 非 event tasks 时 reset event approach。
16. 如果是 event task，调用 `_update_event_task()`。
17. 否则调用 `_update_static_task()`。

这个流程是连贯的，但太多东西藏在一个方法里。第一步重构应保留流程，只把阶段移到具名模块。

### Static Task Runner

当前 `_update_static_task()` 处理：

1. `control_pos` 缺失则等待。
2. exit task 检查 `is_inside_exit_region()`；如果已在 exit，stop controller 并返回 `ARRIVED`。
3. required task 若在 `arrival_radius` 内，标记 required 完成、reset movement、返回 `WAIT`。
4. 否则调用 `MovementExecutor.step()`。
5. 把 `MovementStep` 翻译成 `MOVE_MAP` 或 `WAIT`。

提取目标：

```python
class StaticTaskRunner:
    def update(task, state, movement, planning_context, now_ms, lookahead_distance) -> NavigationIntent: ...
```

### Event Task Runner

当前 `_update_event_task()` 处理：

1. event context 缺失则等待。
2. 运行 `EventApproachController`，直到 event task 被释放给 handler。
3. 若本帧 `EventApproachResult.became_visible=True`，通过 `controller.event_hooks` 发出 `event_visible_target`。
4. 调用 `event_coordinator.run_task(event_task_id, event_tick)`。
5. 把 `EventActionType` 转成 `NavigationIntentType`：
   - `MOVE_TO` -> movement step 或 forced target click。
   - `CLICK_SCREEN` -> `CLICK_SCREEN`。
   - `PRESS_KEY` -> `PRESS_KEY`。
   - `WAIT` -> `WAIT`。
   - `COMPLETE` / `FAIL` -> terminal `WAIT` with metadata。
6. `COMPLETE` 后 reset movement/approach，并发出 `event_completed`；`FAIL` 只做 terminal reset，暂不发完成 hook。

提取目标：

```python
class EventTaskRunner:
    def update(task, state, event_context, planning_context, now_ms, lookahead_distance) -> NavigationIntent: ...
```

重要边界：

`EventApproachController` 属于 navigation，而不是 portal event package。它决定 navigation 是否足够近/稳定，可以让 event handler 触发。未来 event package 可提供 approach preferences，但 approach gate 应保持 navigation-layer policy。

## 公共接口提案

引入分组 context objects：

```python
@dataclass
class LocalizationSnapshot:
    pos: tuple[float, float] | None
    confidence: float
    frame_registration: object | None = None

@dataclass
class PlanningSnapshot:
    wall_map: object
    pathfinder: object
    explored_map: object | None
    lookahead_distance: float

@dataclass
class EventRuntimeSnapshot:
    coordinator: object | None
    tick: object | None
    manual_event_only: bool = False

@dataclass
class NavigationUpdateContext:
    now_ms: int
    localization: LocalizationSnapshot
    route: dict | None
    planning: PlanningSnapshot
    events: EventRuntimeSnapshot
```

然后：

```python
def update(self, context: NavigationUpdateContext) -> NavigationIntent: ...
```

这不减少功能，但能稳定接口，并给测试提供一个 fixture object。

## 和 GUI 拆分的关系

一旦有 `NavigationUpdateContext`，`gui/modes/navigation/runtime_loop.py` 可以负责构造 context：

```python
intent = task_controller.update(context)
```

GUI widget 不再需要知道 controller 的完整参数表。

一旦有 `NavigationIntentExecutor`，GUI/navigation adapter 负责把 intent 适配到 `MotionController`。`NavigationTaskController` 已经只输出 intents，这是好的边界。

## 和事件 Hooks 的关系

不要把 portal-specific hooks 放进 `NavigationTaskController`。

推荐形态：

```text
core/events
  emits EventTask + EventAction

core/navigation_tasks
  consumes EventTask through TaskBuilder
  consumes EventAction through EventTaskRunner
  emits NavigationIntent

gui/modes/navigation
  adapts NavigationIntent to MotionController
  adapts event status to UI/dialog/overlay
```

当前已落地的跨系统扩展点保持 generic：

- Event/navigation bridge hook: `event_visible_target`，描述“当前被选中的事件目标首次进入真实视野”。
- Event/navigation terminal hook: `event_completed`，描述“事件 handler 完成且 memory 已更新”。
- 后续仍可增加 “event task changed”“event action translated”等 hook，但不把 portal-specific 逻辑写入 controller。

Portal 可以通过配置/log adapter 观察这些 hook，但 task controller 不应依赖 portal。

## 当前状态

状态：partial。已阅读 main task models、controller、movement executor、scheduler、builder、route context、event approach、coordinate diagnostics。完整分支级测试仍待补。
# 当前事件靠近补充：按事件覆盖停靠半径

`NavigationTaskBuilder` 现在会把 loot 事件任务 metadata 中的 `pickup_radius` 复制到 `NavigationTask.radius` 和 `NavigationTask.metadata["event_stop_radius"]`。`EventApproachController` 在 `event_approach.pipeline.update_event_approach()` 中优先读取该 per-task 半径；如果不存在，继续使用全局 `EventApproachConfig.stop_radius`。

这保证掉落物拾取半径是真正生效的运行参数：loot 不需要像 portal 一样贴到全局 `event_stop_radius=18` 附近才释放 handler，而是在 `pickup_radius` 内停稳后交给 `LootPickupHandler` 按 `pickup_key`。portal 等其它事件未提供 per-task 半径时行为不变。

---
