# Core 架构优化判断准则

本文用于约束后续 `core` 优化：不按固定行数、固定文件数量、固定层级机械拆分，而按模块深度、依赖方向、复用价值和主线维护成本判断。

## 1. 总目标

优化目标不是“把文件切小”，而是让系统更工程化：

- 系统职责清楚：mapping、localization、routing、navigation_tasks、events、input、vision、platform、shared 各自知道自己该负责什么。
- 模块接口更深：调用方用小接口获得稳定行为，不需要理解一堆内部阶段。
- 实现局部性更好：某类 bug、阈值、状态转换、诊断证据集中在一个地方改。
- 可复用能力沉到合适层：纯算法、共享契约、平台 adapter 不被业务包私藏。
- 旧调用面可控：GUI 和工具脚本迁移前，旧路径继续作为兼容壳子。

## 2. 先判断“是否值得动”

只有满足下面至少一类，才值得进入优化候选。

### 2.1 概念重复

多个系统各自实现同一概念，且概念会继续演进。

例子：

- `RouteContext` 和 `routing/anchors` 都涉及路线 progress、折线投影、前方 guide anchor。
- localization 和 coordinate diagnostics 都涉及定位证据、可信坐标、跳变恢复。

处理方向：

- 先抽清领域名词。
- 再判断它属于纯算法层、运行态上下文层，还是 shared 契约。

### 2.2 依赖方向不对

低层模块知道了高层业务，或业务 runtime 直接知道平台副作用。

目标方向：

```text
gui
  -> core system facades

navigation_tasks
  -> routing / events models / input intent adapter

events
  -> shared / event package definitions
  -> 不直接调用 MotionController 或 GUI

mapping / localization
  -> vision / shared / routing.obstacles

input
  -> platform

routing / vision / shared
  -> 尽量纯逻辑
```

处理方向：

- 共享数据结构放 `core/shared`。
- 平台副作用放 `core/platform` 或 `core/input` adapter。
- 事件 handler 输出 generic action，不直接执行鼠标键盘。

### 2.3 模块太浅

模块只是把一行调用换个名字，调用者仍要理解几乎所有实现细节。

判断问题：

- 删除这个模块后，复杂度会集中到一个更清晰的地方，还是会扩散到多个调用方？
- 调用方是否仍要知道内部顺序、阈值、状态字段、失败分支？
- 模块接口是否比实现还复杂？

处理方向：

- 浅 helper 如果没有复用价值，可以并回 pipeline。
- 浅 wrapper 如果是兼容壳子，可以保留但标明 compatibility。
- 真正要抽的是能隐藏复杂流程的深模块。

### 2.4 状态转换分散

同一状态机的状态字段、转移条件、日志、恢复策略散在多个文件，导致调 bug 要来回跳。

处理方向：

- 状态拥有者保留一个明确 facade。
- 转移规则集中在 runtime/pipeline。
- 诊断只观察和记录，不偷偷改变状态。

### 2.5 复用已出现第二个真实调用方

一个 seam 只有一个调用方时，先不要急着做抽象。两个以上真实调用方出现，才优先抽成稳定模块。

例子：

- `routing/pathfinder` 被普通导航和事件移动复用，是稳定底层 planner。
- `FrameRegistration` 被 localization 和 events/coordinate diagnostics 使用，适合 shared。
- portal 专用 matcher 目前先留在 portal 包；等第二个事件也要类似小图标匹配，再考虑抽 `events/vision` 或 `vision/matching`。

## 3. 优化优先级排序

候选多时，按下面顺序排。

1. **主线调度和坐标正确性**
   - 影响自动导航、定位、事件移动、坐标恢复的优先。

2. **跨系统共享契约**
   - 比如 frame registration、route progress、navigation intent、event action。

3. **错误依赖方向**
   - 先断开高层/低层混杂，再考虑细拆。

4. **重复算法或重复证据**
   - projection、progress、mask/response、诊断 evidence。

5. **文件过长**
   - 行数只作为提示，不作为决策依据。
   - 如果长文件是单一 pipeline，且接口深、状态局部，可以暂时保留。

## 4. 什么时候不拆

以下情况先不拆：

- 只是因为文件超过某个行数。
- pipeline 虽长，但完整表达一个顺序敏感流程。
- 拆完需要调用方理解更多文件，模块反而变浅。
- 只有一个调用方，且未来复用不明确。
- 当前行为刚验证可用，拆分会混入阈值、状态机、异常策略修改。
- 旧 GUI 调用面尚未迁移，删除兼容壳子会扩大风险。

## 5. 什么时候合并或上移

### 5.1 合并

如果多个 helper 只是 pass-through，且没有独立测试/复用/领域含义，可以合并回更深的 pipeline。

### 5.2 上移到系统包

如果能力属于一个系统内部复用，放到系统包。

例子：

- route progress -> `core/routing`
- localization evidence -> `core/localization` 或 `core/navigation_tasks/coordinate`
- event memory lifecycle -> `core/events/memory`

### 5.3 上移到 shared

只有当两个以上系统需要同一契约，且该契约不带具体业务含义，才放 `core/shared`。

适合：

- `FrameRegistration`
- 纯坐标 DTO
- 通用 runtime diagnostic record

不适合：

- `EventTask`
- `PortalShapeColorHit`
- GUI widget config

## 6. 同名文件规则

不同 package 下的同名文件是允许的，它们表达“包内角色”，不是全局唯一概念。

常见含义：

| 文件名 | 含义 |
| --- | --- |
| `models.py` | 当前 package 的 DTO、dataclass、enum |
| `runtime.py` | 有状态 facade 或状态拥有者 |
| `pipeline.py` | 主流程编排 |
| `diagnostics.py` | 诊断、日志、失败原因 |
| `utils.py` | 小型无状态 helper |
| `__init__.py` | package public API 或旧路径兼容导出 |

注意：

- 同名不等于重复。
- 只有当两个 `models.py` 里出现同一个稳定契约，才考虑抽 shared。
- 只有当两个 `pipeline.py` 里出现同一状态机，才考虑合并。

## 7. 兼容壳子规则

同名 package 替换单文件时，允许旧路径保持不变：

```text
core/routing/anchors.py
-> core/routing/anchors/
   ├── __init__.py
   ├── planner.py
   └── ...
```

外部仍然使用：

```python
from core.routing.anchors import plan_path_with_optional_anchors
```

壳子清理顺序：

1. 先拆真实实现。
2. 保留旧路径。
3. GUI/工具脚本逐步改到新系统路径。
4. 全库引用审计。
5. 再决定是否删除壳子；如果壳子语义清晰、成本低，可以长期保留。

## 8. 每轮优化工作流

每轮必须按 `codebase-ontology` 风格做：

1. 在 `ARCHITECTURE_ITERATION_LOG.md` 写 A 段，声明目标和想弄清楚的问题。
2. 阅读目标文件、调用方、被调用方和相关文档。
3. 判断它属于：
   - 拆分
   - 合并
   - 上移 shared
   - 暂不动
   - 只更新文档
4. 如果改代码：
   - 保留旧 public API。
   - 不混入行为优化。
   - 跑 `py_compile`、import smoke、必要的最小行为 smoke。
5. 同步：
   - `CODEBASE.md`
   - 对应中文架构文档
   - `ARCHITECTURE_ITERATION_LOG.md` C 段。

## 9. 当前已识别的优先优化方向

### A. Route Progress / Guide Anchor 统一

涉及：

- `core/navigation_tasks/route_context.py`
- `core/routing/anchors/`
- `core/routing/geometry.py`

目标：

- 把纯折线投影、累计 progress、前方 anchor 过滤沉到 routing。
- 让 `RouteContext` 更像 navigation runtime context，而不是几何算法容器。

### B. Localization Evidence / Coordinate Recovery

涉及：

- `core/localization/localize_pipeline.py`
- `core/navigation_tasks/coordinate/localization.py`
- `core/navigation_tasks/coordinate/diagnostics.py`
- `core/shared/frame_registration.py`

目标：

- 定义清晰的定位证据输入。
- coordinate diagnostics 消费 evidence，而不是理解太多 localization 内部字段。

### C. Diagnostics Logging 分层

涉及：

- `core/events/debug/`
- `core/navigation_tasks/debug.py`
- `core/navigation_tasks/coordinate/formatting.py`

目标：

- 短期继续复用 event log。
- 长期如果导航和事件日志都稳定复用，抽 `core/diagnostics`。

### D. GUI 组合根迁移

涉及：

- `gui/app_context.py`
- `gui/modes/navigation/widget.py`
- `gui/modes/mapping_widget.py`

目标：

- 新 GUI 代码优先依赖系统包。
- 旧 `core.*` 顶层壳已删除；后续只清理无价值的内部 wrapper，保留正式 package 入口。
