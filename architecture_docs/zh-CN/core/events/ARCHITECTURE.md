# 事件系统架构

## 系统角色

`core/events` 应成为可复用事件 runtime。它观察帧、稳定检测、存储 event tasks、选择 runnable tasks、运行 event handlers，并把 generic actions 返回给 navigation。

事件系统不应知道 GUI widgets、route editing 或具体 mouse/key 执行。它应该只输出 generic actions 和生命周期状态。

## 与导航任务系统的 seam

事件系统和导航任务系统之间的动作契约是 `EventAction`。

规则：

- `EventHandler.update(tick, task)` 只能返回 `EventAction | None`。
- `EventAction` 可以表达移动目标、屏幕点击、按键、等待、完成和失败，但不执行这些动作。
- `EventCoordinator.run_task(task_id, tick)` 只推进被导航任务系统选中的事件任务，并把 handler 返回的 `EventAction` 原样交回导航任务层。
- `core/events` 不依赖 `MotionController`、`NavigationIntent` 执行器、GUI widget 或 PySide。
- `EventAction -> NavigationIntent` 的翻译只发生在 `core/navigation_tasks/intent_factory.py` 和 `event_task_runner.py` 这条导航任务链路内。

这样做的原因是保持仲裁权在 `navigation_tasks`：普通路线移动、事件靠近 gate、事件 handler 动作、强制重定位 WAIT intent 都走同一个 `NavigationIntent` 输出面，避免事件包绕开自动导航调度直接点击。

## 已验证事件生命周期

当前 runtime 生命周期：

```text
EventCoordinator.observe(tick)
  ├── EventMonitor.detect(tick, config)
  │     └── EventDefinition.create_detector(config).detect(...)
  ├── EventPositionStabilizer.update(detections, frame_registration, config, now_ms)
  ├── EventMemory.merge_observations(observations, config, now_ms)
  │     ├── create EventTask(state=OBSERVED)
  │     ├── merge nearby observations into existing EventTask
  │     ├── apply completed cooldown/type cooldown
  │     └── mark EventTask PENDING when confirm frames reached
  ├── tick.event_tasks = EventMemory.tasks()
  └── EventScheduler.pick(active_tasks, player_pos)
        └── only selects display/status task here

NavigationTaskController.update_context(NavigationUpdateContext)
  └── TaskBuilder consumes EventCoordinator.tasks()
      └── selected navigation event task calls EventCoordinator.run_task(task_id, tick)

EventCoordinator.run_task(task_id, tick)
  └── EventRunner.update(selected_task, tick, config)
        ├── start handler if task changed
        │     └── EventDefinition.create_handler(config).start(task)
        ├── EventHandler.update(tick, task) -> EventAction
        ├── COMPLETE -> EventMemory.mark_completed / complete_teleport_session
        ├── FAIL -> EventMemory.mark_failed
        └── returns EventAction to navigation task controller
```

关键点：`EventCoordinator.observe()` 不执行 handlers。它只做检测、稳定、合并 memory、选择 display/status task。只有 navigation 选中某个 event task 并调用 `run_task()` 时，handler 才开始执行。

## 当前模块地图

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `models.py` | Event tick、detection、observation、task、action models。 | 稳定契约候选。 |
| `config.py` | 默认 event config 和 map-level config IO。 | 可拆纯 defaults/schema 和 filesystem adapter。 |
| `registry.py` | Event definition registry。 | 事件包扩展 seam。 |
| `hooks/__init__.py` | Event lifecycle hook package 入口。 | 对外暴露 hook 常量、上下文和 registry。 |
| `hooks/models.py` | `EventHookContext`、当前 hook 名称常量和展示标签。 | 观察型生命周期 payload，不承载控制决策。 |
| `hooks/registry.py` | 同步 hook registry。 | 默认 no-op，handler 异常只写日志不影响主循环。 |
| `hooks/instances/key_press.py` | key_press hook 实例定义和配置解析。 | 读取 `event_types` + `triggers` 双重绑定，只接收按键回调，不直接依赖 GUI 或真实输入实现。 |
| `monitor.py` | 运行 enabled detectors 并缓存它们。 | detection lifecycle hook 点。 |
| `position_stabilizer/__init__.py` | 事件位置稳定 package 入口，保留 `EventPositionStabilizer` 和旧 `_PositionCluster/_PositionSample` 导出。 | 旧 import facade。 |
| `position_stabilizer/runtime.py` | `EventPositionStabilizer` facade，保留 `update()`、`clear_event_type()` 和旧私有 wrapper。 | 状态拥有者。 |
| `position_stabilizer/models.py` | `PositionSample`、`PositionCluster` 和中心/方差/置信度计算。 | 聚类数据模型。 |
| `position_stabilizer/projection.py` | 把 local detections 投影为 global positions。 | 纯坐标算法组件。 |
| `position_stabilizer/clusters.py` | 跨帧聚类、同帧隔离、样本窗口和 cluster 过期。 | 聚类策略组件。 |
| `position_stabilizer/observations.py` | 样本数、方差和发射间隔 gate，通过后构造 `EventObservation`。 | 稳定输出策略组件。 |
| `memory/__init__.py` | Event task lifecycle facade package，保留 `EventMemory` public API 和旧私有 helper wrapper。 | 状态拥有者，真实策略拆到 memory 子包。 |
| `memory/merge.py` | Stable observations 合并、task 创建、seen 更新和确认帧。 | Observation -> EventTask 合并策略层。 |
| `memory/target_update.py` | 事件目标点更新策略，决定 stable observation 是否可以覆盖 `EventTask.global_pos`。 | 区分点目标和区域目标，避免区域型事件拖动导航目标。 |
| `memory/lookup.py` | Task 查找、dedupe、exit task 匹配和 completed cooldown 判定。 | 纯查找/冷却策略层。 |
| `memory/completion.py` | Task 完成、teleport session、附近任务抑制、失败重试/忽略。 | 生命周期终态策略层。 |
| `memory/utils.py` | 距离、坐标标准化和日志节流。 | 小型共享工具。 |
| `scheduler.py` | 选择 pending/running event tasks。 | 小 scheduler module。 |
| `runner.py` | 启动 handlers 并把 complete/fail 应用到 memory。 | 执行生命周期模块。 |
| `coordinator/__init__.py` | navigation loop 的统一 event entrypoint package。 | 旧 `core.events.coordinator.EventCoordinator` import 路径由同名 package 接管。 |
| `coordinator/runtime.py` | `EventCoordinator` stateful facade。 | 持有 registry/config/memory/monitor/stabilizer/scheduler/runner 和旧 public/private wrapper。 |
| `coordinator/observation.py` | observe 阶段：detect -> stabilize -> memory merge -> display task selection。 | 不运行 handlers，只更新 memory、tick.event_tasks 和 status/display task。 |
| `coordinator/task_run.py` | run_task 阶段：按 task_id 找 enabled active task 并委托 EventRunner。 | 只推进被导航任务系统选中的事件任务。 |
| `coordinator/reset.py` | reset_event_type 运行时清理。 | 清理 handler、memory、position clusters、last detections/observations 和 selected/action 状态。 |
| `coordinator/presentation.py` | overlays/status_summary。 | 把 enabled task 过滤、overlay DTO 和紧凑状态文案集中。 |
| `coordinator/filters.py` | coordinator 日志节流和 event enabled 过滤。 | 旧 `_should_log()`、`_enabled_active_tasks()`、`_enabled_display_tasks()`、`_is_event_enabled()` wrapper 的实现。 |
| `capture_provider.py` | 给 handlers 提供 minimap/main-view captures。 | Adapter 边界。 |
| `window_finder.py` | Windows 游戏窗口查找。 | Platform adapter。 |
| `debug/__init__.py` | Event runtime logging package 入口。 | 旧 `core.events.debug` import 路径由同名 package 接管。 |
| `debug/writer.py` | event log session、主日志、run archive、topic log 写入。 | Diagnostics writer adapter；必须保持项目根目录 `logs/` 路径。 |
| `debug/topics.py` | 从 message/fields 推断 portal/navigation/localization topic。 | 日志分流策略，可作为 logging hook 前置点。 |
| `debug/descriptions.py` | `EventAction`/`EventTask` 描述文本。 | 运行时对象展示 adapter，不参与状态决策。 |
| `debug/formatting.py` | Enum、float、tuple/list、dict 字段格式化。 | 共享日志格式规则。 |
| `overlay_models.py` | 把 event task state 转成 overlay data。 | UI-facing DTO adapter；只要无 PySide 依赖，仍 core-safe。 |

当前执行状态：

- `config_model.py` 已新增，承接 `DEFAULT_EVENT_CONFIG`、`EventSystemConfig`、deep merge 和 legacy portal detector mode 兼容。
- `config_io.py` 已新增，承接 `event_config.json` 路径、加载和保存。
- `config.py` 现在是兼容 facade，继续导出 `EventSystemConfig`、`load_event_config()`、`save_event_config()`、`event_config_path()` 和 `build_tui_event_options()`。
- `FrameRegistration` 已移到 `core.shared.frame_registration`，`core.events.models` re-export 同一类型，避免定位层直接依赖事件 runtime model。
- `position_stabilizer.py` 单文件已替换为 `position_stabilizer/` facade package；旧路径 `core.events.position_stabilizer.EventPositionStabilizer` 不变，真实投影、聚类和 observation 构造已分类下沉。
- `coordinator.py` 单文件已替换为 `coordinator/` facade package；旧路径 `core.events.coordinator.EventCoordinator` 不变，observe/run/reset/presentation/filter 已分类下沉。
- `debug.py` 单文件已替换为 `debug/` facade package；旧路径 `core.events.debug.event_log`、`start_event_log_session`、`describe_action`、`describe_task` 不变，日志写入、topic 分流、对象描述和值格式化已分类下沉。

## 当前公共事件包接口

`EventDefinition` 是事件包 seam：

```python
class EventDefinition:
    event_type: str
    display_name: str
    description: str

    def default_config(self) -> dict: ...
    def config_schema(self) -> dict: ...
    def create_detector(self, config): ...
    def create_handler(self, config): ...
```

`EventDetector` interface：

```python
def detect(self, tick, config) -> list[EventDetection]: ...
```

`EventHandler` interface：

```python
def start(self, task) -> None: ...
def update(self, tick, task) -> EventAction | None: ...
def reset(self) -> None: ...
```

这是好的最小 seam，应保持小。不要把 hooks 作为一堆 optional methods 加到 `EventDefinition`；应使用 hook bus/listener。

## 当前生命周期 Hooks

当前已落地一个最小观察型 hook registry：`core.events.hooks.EventHookRegistry`。它由 `NavigationTaskController.event_hooks` 持有，默认没有 handler 时完全 no-op；注册 handler 后同步派发 `EventHookContext`。handler 抛异常只写 `event hook handler failed`，不会中断导航或事件主循环。

已落地 hook：

- `event_visible_target`：事件已被识别成 `EventTask`，再被 `NavigationTaskScheduler` 选为当前 event navigation task，并且 `EventApproachController` 首次确认目标进入人物真实视野盒时触发。
- `event_completed`：event handler 返回 `EventActionType.COMPLETE`，`EventRunner` 已经把完成态写入 `EventMemory` 后，由 navigation event runner 在终态清理后触发。
- `hooks/instances/key_press.py` 提供第一个可注册实例：`type="key_press"`。它读取实例 `key/event_types/triggers/enabled/name/id`，只有当前 `EventHookContext.event_type` 命中 `event_types` 且 hook 名命中 `triggers` 时，才调用外部注入的 `press_key(key, reason)`；当前只做按一下。

事件配置文件当前可保存：

```json
{
  "hooks": {
    "instances": [
      {
        "id": "key_press_1",
        "type": "key_press",
        "name": "按键 Hook",
        "enabled": true,
        "key": "d",
        "event_types": ["portal"],
        "triggers": ["event_visible_target", "event_completed"]
      }
    ]
  }
}
```

同一个实例的 `event_types` 可以绑定一个或多个事件类型，`triggers` 可以同时包含两个触发点，所以一个按键 hook 可以只对指定事件生效，并在事件进入真实视野和事件完成后分别触发。`event_types` 为空表示未绑定事件，运行时不会注册执行，避免默认对所有事件生效。

注册方式：

```python
from core.events.hooks import EVENT_HOOK_VISIBLE_TARGET

unsubscribe = navigation_task_controller.event_hooks.register(
    EVENT_HOOK_VISIBLE_TARGET,
    lambda context: print(context.event_type, context.event_global_pos),
)
```

边界约束：

- hook 只做观察或后续自定义编排入口，不直接执行鼠标/键盘输入。
- hook payload 不返回控制决策；主流程不读取 handler 返回值。
- hook registry 不依赖 GUI、不依赖 portal 具体事件包；GUI 后续如果要注册 handler，应在组合根或 adapter 层完成。
- key_press 实例本身也不创建输入控制器；真实按键由 GUI 层 `NavigationHookRuntime` 注入回调执行。GUI 事件管理 Hooks 页负责把用户勾选的事件类型写入 `event_types`。

## 期望事件包接口

每个事件类型应作为一个 package adapter，提供：

- Event identity 和 display metadata。
- Default config 和 config schema。
- Detector factory。
- Handler factory。
- 可选 overlay formatting。
- 可选 approach policy。
- 可选 validation probes。

核心事件系统不应直接 import portal-specific code，除 registration 外。

细化接口：

```text
Event package
  ├── EventDefinition
  │     ├── identity/display/config schema
  │     ├── detector factory
  │     └── handler factory
  ├── detector components
  ├── handler state machine
  ├── config typed adapter
  ├── assets
  └── optional probes
```

事件包内部可以有 detector variants、confirmers 和 assets，但 app 其它部分应该只看到完整事件类型，如 `portal`。

## Adapter 边界

这些应保持 adapter，不应变成 core policy：

- `config.py` file IO：map-folder `event_config.json` persistence。
- `capture_provider.py`：handlers 用的 static/game-window capture adapter。
- `window_finder.py`：Windows-specific window lookup。
- `overlay_models.py`：core-safe DTO；PySide 渲染仍在 GUI。
- `debug/`：logging hook candidate；`writer.py` 是输出 adapter，`topics.py` 是 topic routing seam。

可能拆分：

```text
core/events/config_model.py       # EventSystemConfig and defaults
core/events/config_io.py          # event_config.json load/save
core/events/hooks/                # EventHookContext/EventHookRegistry/concrete hook instances
core/events/coordinator/          # lifecycle facade package
core/events/debug/                # event runtime diagnostics package
core/events/types/portal/minimap_feature_matcher/  # blue-body feature matcher
```

## Coordinator 拆分

`EventCoordinator` 已按 observe/run/reset/presentation/filter 拆成同名 package：

```text
coordinator/
├── __init__.py       # public import facade
├── runtime.py        # EventCoordinator stateful facade
├── observation.py    # detect -> stabilize -> memory merge -> display selection
├── task_run.py       # run selected task through EventRunner
├── reset.py          # reset_event_type runtime cleanup
├── presentation.py   # overlays/status summary
└── filters.py        # enabled filtering and log throttle
```

拆分后语义保持不变：`observe()` 不执行 handlers，`run_task()` 只推进被导航任务系统选中的 event task。

## Memory Policy

`EventMemory` 是深模块，拥有：

- 把 observations dedupe 成 tasks。
- Confirmation frames。
- Position/type cooldown。
- Retry/ignore behavior。
- Teleport session completion。
- Nearby pending suppression。
- Synthetic related task creation。

当前抽取状态：
- `memory/__init__.py` 保留 `EventMemory` public API：`tasks()`、`active_tasks()`、`clear_event_type()`、`merge_observations()`、`mark_completed()`、`complete_teleport_session()`、`mark_related_completed()`、`suppress_nearby_pending()`、`mark_failed()`。
- `memory/merge.py` 承接 `merge_observations()` 主流程，避免同一帧多个 observation 复用同一 task 的 `touched_task_ids` 语义不变。
- `memory/target_update.py` 承接 per-event 目标更新策略。默认 `continuous` 与旧行为一致；`lock_after_confirm` 在 task 进入 `PENDING/RUNNING` 后只刷新 `last_seen_ms`、`confidence`、`seen_count`、metadata 和 `last_observed_global_pos`，不再覆盖 `global_pos`；`limited_after_confirm` 可围绕首次锁定点做小半径校正，避免逐帧滚动漂移。
- `memory/lookup.py` 承接 `_find_task_by_id()`、`_find_matching_task()`、`_find_session_exit_task()`、`_find_nearest_task()`、`_completed_cooldown_info()`。
- `memory/completion.py` 承接 teleport session completion、related completed、nearby suppression、failure retry/ignore。
- `memory/utils.py` 承接 `_distance()`、`_int_pos()` 和 `_should_log()` 的实现。

拆分后仍要把 `EventMemory` 视为生命周期状态拥有者；helper 接收 memory 实例或 task list 是为了缩短文件，不代表外部可以绕过 `EventMemory` 直接改 task 生命周期。

## Runner Policy

`EventRunner` 是 generic event runtime 和 event package handlers 之间的好 seam：

- selected task 改变时启动 handler。
- runner idle 时 requeue running task。
- 把 `COMPLETE`/`FAIL` 应用到 memory。
- 让 handler actions 作为 generic `EventAction` 回到 navigation。

当前已落地的 hook 位置：

- `event_visible_target` 不在 `EventRunner` 内触发，而是在 navigation event approach gate 首次确认当前事件目标进入真实视野时触发。
- `event_completed` 不在 handler 内触发，而是在 `EventRunner.update()` 返回 `COMPLETE` 且 memory 已完成更新后，由 `event_task_runner.update_event_task()` 触发。

未来如果需要更细粒度 handler 生命周期，可继续补充 `on_handler_started`、`on_handler_action`、`on_task_failed`，但仍应保持观察型，不让 hooks 变成事件包的输入执行器。

## Config 边界警告

`DEFAULT_EVENT_CONFIG` 当前在 `core/events/config.py` 里直接包含 portal-specific defaults。这让 event core 知道第一个事件包。

首选方向：

```text
EventSystemConfig.default(registry)
  └── merge global defaults with each EventDefinition.default_config()
```

这样新事件包可以通过注册自己的 defaults，不必改 event core config。

## 当前状态

状态：partial。已阅读 core event model、coordinator、monitor、memory、scheduler、runner、registry、config、base interfaces、overlay DTO、capture provider。
# 当前事件包补充：loot 掉落物拾取

`core/events/types/loot/` 已作为正式事件包接入，事件类型为 `loot`。它只从小地图识别掉落物区域，不做逐个掉落物实例精确标记；检测输出一个或少数 blob，并交给既有 `EventPositionStabilizer`、`EventMemory`、`NavigationTaskBuilder`、`EventApproachController` 和 `EventRunner` 主链路。

正式结构与算法细节见：`architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`。

当前关键语义：
- `LootMinimapDetector.detect()` 先跑 `detect_loot_presence()` 做轻量存在粗检；连续达到 `presence_confirm_frames=2` 后才调用 `detect_loot_blobs()` 做定位复核，定位结果按 `detection_interval_ms=450` 缓存复用。
- `detect_loot_blobs()` 读取项目内 `assets/event_templates/loot/minimap/` 模板，用局部模板、边缘外形、颜色/亮度三路加权，默认阈值 `weighted_threshold=0.54`；当前权重为模板 `0.46`、外形 `0.42`、颜色 `0.12`，颜色只作为辅助。
- 人物箭头默认先在小地图中心由 `detection.roi.apply_player_center_mask()` 处理：中心 patch 确认像人物箭头后按 `player_center_mask_radius=28` 挖空。定位阶段只对已经 accepted 的少量候选再跑 `detection.exclusions.is_player_marker_candidate()` 和 `is_blue_map_artifact_candidate(patch, shape_score)`，用人物负模板、蓝/青底、金色比例、亮白比例和外形分数过滤人物/地图装饰误检。
- `detection.clustering.cluster_candidates()` 会把堆叠和相邻候选合并为 `LootCluster`，因此输出目标是“可拾取区域”，不是物品清单。
- `conversion.clusters_to_detections()` 把 blob center 写入 `EventDetection.local_minimap_pos`，并把 bbox、三路分数、候选数和 `pickup_radius` 写入 metadata。
- `LootPickupHandler.update()` 只返回标准 `EventAction`：距离远时 `move_to()`，进入 `pickup_radius` 后 `press_key(pickup_key)`，默认按 `a`，小地图缺失确认后 `complete()`。
- loot 事件定位不触发 `NavigationCore` 全图定位。`EventPositionStabilizer` 只把小地图局部点通过当前 `FrameRegistration` 投影到全局坐标。此前移动时的“像全局重定位”体感来自 blob center 漂移反复覆盖 `EventTask.global_pos`，进而触发 `MovementExecutor` 目标变化和 A* 重规划；当前 loot 默认 `target_update_mode="lock_after_confirm"`，确认后锁定导航目标，只刷新最后观测点和消失判断所需时间。
- loot 默认 `priority=60`，portal 默认 `priority=100`，因此同一路线窗口内传送门优先于顺路拾取。

---
