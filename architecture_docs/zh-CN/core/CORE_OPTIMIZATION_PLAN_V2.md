# Core 优化规划 V2

本文承接 [ARCHITECTURE_OPTIMIZATION_RULES.md](ARCHITECTURE_OPTIMIZATION_RULES.md)。V2 的目的不是继续按文件行数“切小”，而是按模块深度、依赖方向、状态局部性和真实复用价值，重新规划 `core` 的下一阶段工程化优化。

## 1. 当前结论

`core` 已经从早期大文件状态进入“系统包 + 兼容壳子”阶段：

- `mapping`、`localization`、`routing`、`input`、`vision`、`platform`、`shared` 已经成形。
- `navigation_tasks` 和 `events` 已经有清晰包边界，且大量 stateful facade 已保留旧入口并把实现委托给分类 helper。
- 旧 `core.*` 调用面仍然重要，尤其是 GUI 还在读写 `NavigationCore`、`MotionController`、`NavigationTaskController` 等对象字段。
- 后续优化的主线应从“拆大文件”转为“收束跨系统重复概念”和“加深接口”。

当前最值得推进的不是继续追求每个文件都很短，而是以下四条 seam：

1. Route Progress / Guide Anchor 统一。
2. Localization Evidence / Coordinate Recovery 证据模型收束。
3. Diagnostics Logging 分层。
4. EventAction -> NavigationIntent 翻译层固化。

## 2. 顶层系统划分

```text
gui
  -> core public facades / system packages

core
  mapping              建图状态、帧配准、地图包保存和显示渲染
  localization         导航定位、F2F/template match、FrameRegistration 产出
  routing              A*、障碍层、路径几何、路线进度、guide anchor
  navigation_tasks     任务调度、movement 复用、事件靠近、坐标诊断、intent 输出
  events               事件检测、稳定、memory、runner、具体事件包
  input                地图目标到屏幕输入、点击/按键执行、Win32 adapter
  vision               HSV、phase displacement、玩家追踪
  platform             截图和平台能力
  shared               跨系统共享契约
```

依赖方向原则：

```text
navigation_tasks -> routing / events.models / shared
events           -> shared / events 内部模型
localization     -> vision / shared / routing.obstacles
mapping          -> vision
input            -> platform
routing          -> 尽量纯逻辑
shared           -> 不依赖具体业务系统
```

## 3. 深读发现

### 3.1 Route Progress 有三处实现

涉及文件：

- `core/navigation_tasks/route_context.py`
- `core/routing/geometry.py`
- `core/routing/anchors/progress.py`
- `core/routing/anchors/corridor.py`
- `core/navigation_tasks/movement/path_planner.py`

发现：

- `RouteContext.project()` 自己实现折线投影、累计进度、偏离距离，并返回 `RouteProjection`。
- `routing.geometry.project_point_onto_path()` 也实现折线投影，返回 dict，字段为 `distance` 和 `distance_to_path`。
- `routing.anchors.progress._project_progress_on_polyline()` 再次实现折线 progress，只返回 progress。
- `RouteContext.corridor_anchors()` 和 `routing.anchors.corridor._ordered_corridor_anchors()` 都在表达“当前位置和目标之间的前方锚点”。

判断：

- 这是“概念重复”，不是普通 helper 重复。
- `routing` 应拥有 route progress 的纯算法，`navigation_tasks.RouteContext` 应更像运行时上下文和兼容 facade。
- 不建议把 guide anchor policy 合进 `PathFinder`；A* 仍应保持低层 planner。

### 3.2 Localization Evidence 跨三层流动

涉及文件：

- `core/localization/localize_pipeline.py`
- `core/localization/frame_registration.py`
- `core/shared/frame_registration.py`
- `core/navigation_tasks/coordinate/localization.py`
- `core/navigation_tasks/coordinate/diagnostics.py`
- `core/navigation_tasks/update_pipeline.py`

发现：

- `localize_pipeline.localize_frame()` 是定位状态写入主流程，直接更新 `NavigationCore.current_pos`、`last_good_pos`、`prev_wall_mask`、`is_localized`、`last_frame_registration` 等字段。
- `FrameRegistration` 已在 `core/shared`，方向正确。
- `coordinate/localization.py` 需要从 raw/trusted/control position、confidence、min_confidence、registration fields、visual metadata 中推断 drift、raw jump、raw/control gap、long F2F、visual mismatch 和 relocalization signal。
- 诊断层现在知道很多 localization 内部字段名字，例如 `reg_source`、`reg_meta.visual_delta_dist`、`forced_global`。

判断：

- 当前行为可用，不应把 `localize_pipeline` 硬拆成很多浅函数。
- 更有价值的是定义更深的 `LocalizationEvidence` 或 `LocalizationFrameEvidence`，让 coordinate diagnostics 消费稳定证据，而不是理解 `NavigationCore` 内部 metadata 细节。
- 该 seam 影响坐标正确性，优先级高于普通文件长度优化。

### 3.3 Diagnostics Logging 存在格式重复，但暂不急着 shared

涉及文件：

- `core/events/debug/formatting.py`
- `core/events/debug/writer.py`
- `core/events/debug/topics.py`
- `core/navigation_tasks/debug.py`
- `core/navigation_tasks/coordinate/formatting.py`
- `core/navigation_tasks/coordinate/log.py`

发现：

- `events.debug.formatting._format_value()` 和 `coordinate.formatting.format_value()` 规则基本一致。
- `navigation_tasks.debug.nav_log()` 只是把导航日志转写到 `events.debug.event_log()`。
- coordinate diagnostics 有独立 `logs/coordinate_diagnostics.log` writer，不走 event topic log。

判断：

- 有重复，但现在还不是 P1。
- 日志“输出格式”可以共享，但日志“语义 topic”和“文件归属”不同。
- 直接抽 `core/diagnostics` 会扩大迁移面，应等 event/nav/coordinate 三类日志稳定后再做。

### 3.4 EventAction 与 NavigationIntent 是健康 seam

涉及文件：

- `core/events/models.py`
- `core/navigation_tasks/event_task_runner.py`
- `core/navigation_tasks/intent_factory.py`

发现：

- `EventAction` 属于事件层 generic action：move_to、click_screen、press_key、wait、complete、fail。
- `NavigationIntent` 属于导航任务层输出：MOVE_MAP、CLICK_SCREEN、PRESS_KEY、WAIT 等，最终由 GUI/input 执行。
- `intent_factory.py` 是实际翻译层，事件 handler 不直接调用 `MotionController`。

判断：

- 这里不应合并 `EventAction` 和 `NavigationIntent`。
- 应把 `intent_factory` 明确记录为跨系统 seam，未来新事件只能返回 `EventAction`，不能绕过导航任务层执行输入。

## 4. 优先级规划

### P1. Route Progress 深化

目标：

- 在 `core/routing` 内沉淀统一的折线 progress/projection 模块。
- 让 `RouteContext` 和 `routing/anchors` 使用同一套投影算法。
- 保持 `RouteProjection`、`RouteAnchor`、`RouteContext.project()`、`RouteContext.corridor_anchors()` 旧行为可用。

建议结构：

```text
core/routing/route_progress/
  __init__.py
  models.py          # PolylineProjection / progress DTO
  projection.py      # build cumulative / project point / interpolate
```

迁移策略：

1. 新增 `route_progress` 包，不删除现有函数。
2. 把 `routing.geometry.build_cumulative_lengths()`、`project_point_onto_path()` 的实现委托到新包，返回 dict 兼容旧调用。
3. 把 `RouteContext.project()` 改为调用新包，再包装成 `RouteProjection`。
4. 把 `anchors.progress._project_progress_on_polyline()` 改为调用新包，只保留旧私有函数作为兼容 wrapper。
5. 对 `RouteContext.corridor_anchors()` 与 `anchors.corridor._ordered_corridor_anchors()` 做一次策略对齐，但不要改阈值语义。

当前状态：

- 已完成 1-4。
- 暂未执行第 5 步；corridor policy 仍分别留在 `RouteContext` 和 `routing.anchors.corridor`，当前只共享 projection/progress 基础算法。

保兼容：

- `from core.routing.geometry import project_point_onto_path` 不变。
- `from core.navigation_tasks.route_context import RouteContext` 不变。
- `from core.routing.anchors import anchor_route_progress` 不变。
- `core.anchor_path` wrapper 不动。

风险：

- progress 字段单位和坐标精度不同：`RouteContext` 使用 float point，anchors 使用 int point。
- corridor 阈值不同：`RouteContext` 用 `reached_radius/target_margin`，anchors 用 `min_progress` 推导 reached radius。
- movement lookahead 依赖 `project_point_onto_path()` 返回 dict 字段名。

验证：

- `py_compile` 覆盖 `routing/geometry.py`、`routing/route_progress/*`、`navigation_tasks/route_context.py`、`routing/anchors/*`、`movement/path_planner.py`。
- import smoke 验证旧入口仍可导入。
- 最小行为 smoke：
  - 一条折线路径上投影点 progress 与旧值一致。
  - `RouteContext.corridor_anchors()` 仍只返回 current 到 target 之间前方 anchor。
  - `plan_path_with_optional_anchors()` 仍产生 `anchor_step`、`anchor_probe`、`planned`。

推荐强度：Strong。

### P1. Localization Evidence 深化

目标：

- 给定位帧产出一个稳定证据对象，减少 coordinate diagnostics 对 `FrameRegistration.metadata` 内部 key 的散读。
- 保持 `NavigationCore.localize()` 主流程集中，不为了拆而拆。

建议结构：

```text
core/localization/evidence/
  __init__.py
  models.py          # LocalizationEvidence / VisualCheckEvidence / RecoveryHint
  builder.py         # 从 raw pos/confidence/FrameRegistration 构造 evidence

core/navigation_tasks/coordinate/
  localization.py    # 消费 evidence，保留旧 record_localization_diagnostics 入口
```

迁移策略：

1. 新增 evidence DTO，不立刻改变 `NavigationCore.localize()` 返回值。
2. 在 `update_pipeline` 或 `coordinate/localization.py` 内先用 `FrameRegistration` 构造 evidence。
3. 让 `record_localization_diagnostics()` 内部逐步改为读取 evidence 字段。
4. 等 GUI 优化后，再考虑让 `NavigationCore` 直接暴露最近一帧 evidence。

当前状态：

- 已完成 1-3。
- `core/localization/evidence/` 已提供 `LocalizationEvidence`、`VisualCheckEvidence` 和 `build_localization_evidence()`。
- `CoordinateDiagnostics.record_localization()` 签名不变，内部构造 evidence；raw jump、visual mismatch、long F2F tracking 和 active relocalization 检查已消费 evidence。
- 暂未执行第 4 步；`NavigationCore.localize()` 仍只返回 `(x, y, confidence)`，`last_frame_registration` 仍是对外证据入口。

保兼容：

- `NavigationCore.localize()` 仍返回 `(x, y, confidence)`。
- `NavigationCore.last_frame_registration` 仍保留。
- `CoordinateDiagnostics.record_localization(...)` 签名不变，内部可以构造 evidence。

风险：

- 证据 DTO 过早设计过宽会变成新的浅模块。
- `FrameRegistration.metadata` 当前承载 visual check、forced global、template offset 等不同语义，迁移时不能丢字段。
- 坐标恢复是主线正确性，不能混入阈值调整。

验证：

- `py_compile` 覆盖 `localization/evidence/*`、`coordinate/localization.py`、`coordinate/diagnostics.py`、`update_pipeline.py`。
- import smoke 验证 `NavigationCore` 和 `CoordinateDiagnostics` 旧路径。
- 最小行为 smoke：
  - raw jump 仍注册 recovery signal。
  - visual mismatch 连续达到 required frames 后仍请求 relocalization。
  - forced global accepted 后仍调用 `mark_relocalization_accepted()`。

推荐强度：Strong，但应在 Route Progress 之后或并行小步推进。

### P2. Diagnostics Logging 分层

目标：

- 减少 event/nav/coordinate 日志格式化重复。
- 不改变日志文件位置和 topic routing。

建议结构：

```text
core/shared/diagnostics/
  __init__.py
  formatting.py      # format_value / format_fields

core/events/debug/
  formatting.py      # wrapper -> shared diagnostics formatting

core/navigation_tasks/coordinate/
  formatting.py      # 保留 registration_fields/distance，format_* 委托 shared
```

迁移策略：

1. 只先上移纯格式化函数。
2. `events.debug.writer`、`topics`、`coordinate.log` 暂不合并。
3. 不新增统一 logger facade，避免牵动日志文件和 topic 语义。

当前状态：

- 已完成。
- `core/shared/diagnostics/formatting.py` 提供共享 `format_value()`、`format_fields()`。
- `core/events/debug/formatting.py` 和 `core/navigation_tasks/coordinate/formatting.py` 保留旧函数名并委托 shared。
- `events.debug.writer`、topic routing、`coordinate/log.py` 均未合并，日志文件路径和 topic 语义不变。

保兼容：

- `core.events.debug._format_value` 仍可导入。
- `core.navigation_tasks.coordinate.formatting.format_value` 仍可导入。
- `logs/event_runtime.log` 和 `logs/coordinate_diagnostics.log` 不改。

风险：

- event log 当前使用私有 `_format_value` 导出保护旧调试脚本。
- coordinate formatting 还包含 `registration_fields()`，不能整体搬 shared。

验证：

- 旧 `_format_value({'a': (1, 2)})` 输出保持。
- coordinate log fields 输出格式保持。

推荐强度：Worth exploring。

### P2. EventAction -> NavigationIntent seam 固化

目标：

- 把 `intent_factory.py` 明确作为事件动作到导航意图的唯一翻译层。
- 防止后续具体事件 handler 直接依赖 `MotionController` 或 GUI。

建议动作：

1. 在 `core/navigation_tasks/ARCHITECTURE.md` 增加 seam 描述。
2. 在 `events` 文档中明确 handler 只能返回 `EventAction`。
3. 可选把 `intent_factory.py` 拆成 `movement.py`、`event_action.py` 两个文件，但当前文件不算浅模块，先不急。

当前状态：

- 已完成 1-2，对应中文文档为 `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` 和 `architecture_docs/zh-CN/core/events/ARCHITECTURE.md`。
- 暂不执行第 3 步；`intent_factory.py` 当前接口窄、语义集中，继续保留单文件。

保兼容：

- `event_action_intent()`、`event_movement_step_intent()`、`forced_event_move_intent()` 旧函数保留。

风险：

- 过早拆 `intent_factory.py` 会让调用方理解更多文件，模块变浅。

推荐强度：Worth exploring，优先文档固化，代码暂不拆。

### P3. Stateful Pipeline 保持而不是机械拆

候选文件：

- `core/localization/localize_pipeline.py`
- `core/navigation_tasks/update_pipeline.py`
- `core/navigation_tasks/movement/pipeline.py`
- `core/mapping/frame_pipeline.py`

判断：

- 这些文件是顺序敏感主流程，不应只因 100 行以上就继续切碎。
- 可以抽出“重复概念”或“稳定证据 DTO”，但不应把流程拆成大量只有一个调用方的一行 helper。

推荐动作：

- 暂不拆主流程。
- 若后续出现具体复用点，例如 movement click cooldown policy 被普通导航和事件靠近以外的第三方使用，再抽深模块。

推荐强度：Defer。

### P3. GUI composition root 迁移

目标：

- GUI 组合根已改用新系统包路径，旧顶层 compatibility wrapper 已删除。
- 后续只审计保留在类内的旧 slot/private wrapper，以及 package `__init__.py` 是否确实有入口价值。

涉及：

- `gui/app_context.py`
- `gui/modes/navigation/widget.py`
- `gui/modes/mapping_widget.py`
- `core/__init__.py`
- package `__init__.py` 入口与类内 wrapper

策略：

1. 保持 GUI 新代码直接 import `core.mapping`、`core.localization`、`core.routing`、`core.input`、`core.vision`、`core.platform`。
2. 工具脚本继续使用系统包入口。
3. 全库 `rg` 审计旧顶层壳引用为 0。
4. 再决定哪些内部 wrapper 可以删除，哪些作为 Qt signal slot 或 public class method 长期保留。

推荐强度：Defer until core P1/P2 stable。

## 5. 同名文件解释

当前 `core` 里大量同名文件不是问题本身：

| 文件名 | 当前意义 |
| --- | --- |
| `models.py` | 当前包内 DTO、enum、dataclass。 |
| `runtime.py` | 当前包内有状态 facade 或状态拥有者。 |
| `pipeline.py` | 当前包内主流程编排。 |
| `diagnostics.py` | 当前包内诊断、日志、失败原因。 |
| `formatting.py` | 当前包内日志/字段格式化。 |
| `__init__.py` | public API 聚合或旧路径兼容。 |

判断标准：

- `events/models.py` 和 `navigation_tasks/models.py` 不应该合并，因为它们属于不同系统契约。
- 多个 `pipeline.py` 不是重复；只有当两个 pipeline 表达同一状态机时才考虑合并。
- 多个 `formatting.py` 有重复迹象，但只有纯格式化函数适合上移，领域字段提取仍留在各包。

## 6. 下一轮实施顺序

建议按这个顺序自动执行，除非遇到主线行为风险：

1. 新增 `core/routing/route_progress/`，统一 projection/progress 纯算法。
2. 让 `RouteContext`、`routing.geometry`、`routing.anchors.progress` 委托到 `route_progress`。
3. 更新 `CODEBASE.md`、`ARCHITECTURE_ITERATION_LOG.md`、core 中文架构文档。
4. 新增 `core/localization/evidence/`，先在 coordinate diagnostics 内部构造并消费 evidence。
5. 只上移 shared diagnostics formatting，暂不动日志 writer。
6. 文档固化 EventAction -> NavigationIntent seam。

每一步都必须：

- 保留旧 import 和旧 public 方法。
- 不改阈值、不改行为策略。
- 不碰 test 目录。
- 跑本轮实际实现文件的 `py_compile` 和旧/新 import smoke。
- 按 `codebase-ontology` 写 A/C，并同步 `CODEBASE.md`。

## 7. 暂不做清单

- V2 优化阶段原范围不包含 hook 实现；当前后续功能阶段已新增 core 生命周期 hook、带事件类型绑定的 key_press hook 实例和 GUI Hooks 页。
- 不删除 compatibility wrapper。
- 不因为某个文件还有 100、200 或 400 行就继续拆。
- 不把 `EventAction` 合并进 `NavigationIntent`。
- 不把 guide anchor policy 合进 `PathFinder`。
- 不把 coordinate diagnostics 改成会直接写定位状态的模块；它只能请求 relocalization。

## 8. 风险清单

| 风险 | 位置 | 触发条件 | 缓解 |
| --- | --- | --- | --- |
| progress 计算细微变化 | `route_context.py`、`routing/anchors/progress.py`、`routing/geometry.py` | 三套实现统一时浮点/整数转换不一致 | 先用 adapter 保持返回形态；用 smoke 对比关键折线路径。 |
| corridor anchor 行为变化 | `RouteContext.corridor_anchors()`、`anchors.corridor` | 合并策略时阈值被顺手改动 | 第一轮只共用投影算法，不合并 policy 阈值。 |
| coordinate recovery 误触发 | `coordinate/localization.py` | evidence DTO 字段映射错误 | 保持 `record_localization()` 签名；先内部构造 evidence，不改外部调用。 |
| 日志路径变化 | `events/debug/writer.py`、`coordinate/log.py` | 过度抽 shared diagnostics | P2 只抽格式化，不动 writer。 |
| 事件绕过导航任务 | portal handler 或未来事件 handler | handler 直接执行 click/key | 文档固化：handler 只能返回 EventAction。 |
| GUI 调用断裂 | top-level `core.*` wrappers | 过早删除旧入口 | 壳子保留到 GUI composition root 迁移后。 |

## 9. 成功标准

V2 阶段完成后，应该达到：

- route progress 只有一个权威算法实现，不再在三个地方手写投影。
- coordinate diagnostics 消费稳定 localization evidence，少读 raw metadata key。
- event/nav/coordinate 日志纯格式化规则统一，但日志文件和 topic 语义不变。
- 事件系统和导航任务系统的 action/intent seam 被文档和代码结构共同保护。
- 旧 GUI 和工具脚本不需要一次性迁移，旧路径仍可用。

