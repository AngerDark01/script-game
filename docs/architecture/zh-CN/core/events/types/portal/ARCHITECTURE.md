# Portal 事件架构

## 包角色

`core/events/types/portal` 是第一个具体事件包。它应证明事件系统可以支持：

- Minimap detection。
- Global position stabilization。
- 向 event target 移动。
- Main-view confirmation。
- click/key 交互。
- teleport completion detection。
- cooldown 和 related-task cleanup。

## 已验证包接口

`PortalEventDefinition` 是唯一预期 public entrypoint：

```python
event_type = "portal"
display_name = "Portal"

def default_config(self) -> dict:
    return PortalEventConfig().to_dict()

def config_schema(self) -> dict:
    ...

def create_detector(self, config):
    return PortalMinimapDetector(PortalEventConfig.from_dict(config))

def create_handler(self, config):
    return PortalEventHandler(PortalEventConfig.from_dict(config))
```

这是干净 package boundary。应用其它部分应注册 `PortalEventDefinition`，不应直接 import detector/handler；probes/tests 除外。

## 当前模块地图

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `definition.py` | Portal event definition 和 factories。 | 应是唯一 registration surface。 |
| `config.py` | Portal config dataclass。 | 好的 typed config adapter。 |
| `assets.py` | Portal asset paths。 | 保持 package-local adapter。 |
| `minimap_detector.py` | 选择 detection mode 的 detector facade。 | 保留 `PortalMinimapDetector`、模板缓存、feature signature 和日志节流状态。 |
| `minimap_detection/__init__.py` | detector helper package 入口。 | 聚合 mode、诊断和 hit 转换 helper。 |
| `minimap_detection/modes.py` | Mode 选择、feature template 刷新、template/feature/shape-color 命中调用。 | detector strategy adapter，不持有 detector 状态。 |
| `minimap_detection/diagnostics.py` | skipped/no-hit/rejected/best-hit 日志。 | 集中日志节流和字段，避免 detector 主流程变长。 |
| `minimap_detection/conversion.py` | hit 颜色过滤、`EventDetection` 构造和 metadata 填充。 | generic hit -> event detection adapter。 |
| `minimap_feature_matcher/__init__.py` | 蓝色 portal body feature matcher package 入口。 | 旧 `minimap_feature_matcher` import 路径由同名 package 接管。 |
| `minimap_feature_matcher/models.py` | `PortalFeatureTemplate`、`PortalFeatureHit` DTO。 | 算法数据契约。 |
| `minimap_feature_matcher/masks.py` | HSV 蓝/青色 body mask 提取。 | 可复用颜色特征组件。 |
| `minimap_feature_matcher/templates.py` | 从通用模板构造蓝色本体 feature templates。 | TemplateSpec -> feature template adapter。 |
| `minimap_feature_matcher/response.py` | mask resize 和响应图 peak suppression。 | 模板响应图小算法组件。 |
| `minimap_feature_matcher/pipeline.py` | feature matcher 主流程、候选评分和 hit 合并。 | 可复用 detector component 主算法。 |
| `minimap_hit_filter.py` | 小地图 hit 的最终蓝色像素接受过滤。 | 已抽出的 detector helper，调用方直接使用 `portal_color_check()`。 |
| `minimap_shape_color/__init__.py` | Shape+color matcher helper package 入口。 | 聚合 DTO、mask、template、scoring、pipeline。 |
| `minimap_shape_color/models.py` | Shape+color matcher DTO。 | 参数、命中、debug mask、prepared template 数据契约。 |
| `minimap_shape_color/masks.py` | Shape+color mask 和颜色空间 helper。 | 蓝色核心、白/灰外环、BGR/HSV 转换和缩放。 |
| `minimap_shape_color/templates.py` | Shape+color template preparation。 | 多尺度模板 mask/edge 准备。 |
| `minimap_shape_color/scoring/__init__.py` | Shape+color scoring package 入口。 | 保留原 scoring 函数导出。 |
| `minimap_shape_color/scoring/response.py` | Shape+color response map 和 peak collection。 | mask/color 响应组合、局部抑制。 |
| `minimap_shape_color/scoring/color.py` | HSV color response 和 patch color score。 | 颜色相似度评分组件。 |
| `minimap_shape_color/scoring/overlap.py` | F1-like mask overlap score。 | blue/outer/shape/edge mask 通用 overlap 评分。 |
| `minimap_shape_color/scoring/candidate.py` | 候选窗口评分和接受/拒绝。 | base score、signature boost、reject reasons。 |
| `minimap_shape_color/pipeline.py` | Shape+color 主匹配流程。 | frame mask 构建、模板遍历、候选收集和 merge。 |
| `main_view_confirmer.py` | Blue glow main-view confirmer。 | 可复用 confirmer component。 |
| `environment_signature.py` | 交互前后小地图环境签名和差异计算。 | 已从 handler 私有函数抽出。 |
| `completion_detector.py` | known-exit、位置变化、环境变化完成判定。 | 已从 handler 中抽出；handler 方法保留 wrapper。 |
| `handler/__init__.py` | portal handler package 入口，只导出 `PortalEventHandler`。 | 包入口。 |
| `handler/runtime.py` | `PortalEventHandler` facade/state owner。 | 保留 `start()`、`update()`、`reset()` 和 completion wrapper。 |
| `handler/movement.py` | 到达半径、交互半径和 forced repeat move action。 | 移动阶段策略。 |
| `handler/interaction.py` | portal 点强制点击、点击后等待、按 `D` 和交互签名采集。 | 交互阶段策略。 |
| `handler/completion.py` | `wait_result` 阶段、completion/fail/wait action 和重定位请求。 | 完成阶段策略。 |
| `handler/diagnostics.py` | 状态变化和节流日志。 | 日志 helper。 |

## Detector 架构

`PortalMinimapDetector.detect()` 当前做了这些事：

1. 把输入 config 标准化为 `PortalEventConfig`。
2. HSV signature 改变时刷新 feature templates。
3. 校验 `tick.raw_minimap_frame` 和 template availability。
4. 选择 detector mode：
   - `feature`
   - `feature_then_template`
   - `shape_color`
   - `template`
5. 运行对应算法：
   - feature matcher；
   - shape+color matcher；
   - generic template matcher fallback。
6. 记录 no-hit diagnostics。
7. 应用 `portal_color_check()` 作为 final acceptance filter。
8. 按 `minimap_nms_radius` 在小地图局部坐标上合并近距离重复 hit，避免同一图标被不同模板/尺度送入多个定位簇。
9. 把 hits 转成 generic `EventDetection`。
10. 记录 best hit summary。

当前这个文件已经降为 mode-dispatch facade：它仍持有 `templates`、`feature_templates`、`_feature_signature`、`_last_log_ms` 等运行状态，但 mode 选择、具体算法调用、日志和 hit 转 detection 均下沉到 `minimap_detection/` 子包。

目标拆分：

```text
minimap_detector.py             # EventDetector adapter only
minimap_detection/
  __init__.py
  modes.py                      # feature/template/shape_color mode strategy
  diagnostics.py                # skipped/no-hit/rejected/best-hit logging
  conversion.py                 # hit color check -> EventDetection
minimap_hit_filter.py           # final color check and hit -> EventDetection
minimap_feature_matcher/        # blue-body feature matcher algorithm package
  __init__.py
  models.py
  masks.py
  templates.py
  response.py
  pipeline.py
minimap_shape_color/
  __init__.py
  models.py
  masks.py
  templates.py
  scoring/
    __init__.py
    response.py
    color.py
    overlap.py
    candidate.py
  pipeline.py
```

当前执行状态：

- `minimap_hit_filter.py` 已抽出颜色接受过滤，探针和 detector 均直接调用 `portal_color_check()`。
- `minimap_detection/modes.py` 已承接 detector mode fallback、feature template signature 刷新、feature/template/shape-color 命中调用和 shape-color params 构造。
- `minimap_detection/diagnostics.py` 已承接 skipped/no-hit/hit-rejected/best-hit/shape-color-rejected 日志，继续使用 detector 的 `_last_log_ms` 做节流。
- `minimap_detection/conversion.py` 已承接 `portal_color_check()`、`minimap_nms_radius` 局部重复合并和 hit -> `EventDetection` metadata 构造。

### 2026-06-04 重复识别诊断

最近实机日志 `logs/event_runs/20260604_201657_742_pid24360_navigation.log` 中，传送门 detector 启动时仍显示 `mode=feature_then_template`，而当前 `map_data/A/event_config.json` 已是 `shape_color`。这说明该轮运行用的是当时内存里的旧配置，或者运行后面板又保存了配置；下次重新加载地图后应按文件中的 `shape_color` 运行。

重复定位的直接证据是同一段日志里多个 portal task 的稳定全局坐标相距约 70-85px，例如 `(2983,1913)` 与 `(3032,1980)`。旧参数 `localization_cluster_radius=56`、`dedupe_radius=32` 小于这个抖动/重复距离，所以 memory 会创建多个 portal 任务。当前修正分三层：

1. 默认 `detector_mode` 改为 `shape_color`，减少蓝色相似物被 feature/template 误命中。
2. 新增 `minimap_nms_radius=28`，在进入全局定位前合并同一图标的局部重复 hit。
3. 传送门默认 `localization_cluster_radius=96`、`dedupe_radius=96`，并在事件参数面板暴露；如果真实相邻双门被合并，再手动调小。

### 2026-06-09 目标锁点恢复

最近实机日志 `logs/event_runs/20260609_144437_302_pid23700_navigation.log` 显示，portal detection 仍能稳定输出 `shape_color` 命中，但同一任务多次出现 `target_updated=True` 和 `target_drift=55~83`，说明确认后的传送门目标仍被新观测拖动。底层 memory 模块一直支持 `target_update_mode`，问题是 portal 默认配置和 schema 没有暴露该字段，旧地图配置加载后会回落到 `continuous`。

当前修正为：

1. `PortalEventConfig` 默认 `target_update_mode="limited_after_confirm"`、`target_update_max_drift=18`。
2. `DEFAULT_EVENT_CONFIG.events.portal` 同步补充这两个字段，旧 `event_config.json` 经 `EventSystemConfig.from_dict()` 深度合并后会自动获得默认值。
3. `PortalEventDefinition.config_schema()` 暴露“目标锁点模式”和“锁点允许漂移”，事件管理面板可直接调参。
4. 语义上仍使用同一套 `core/events/memory/target_update.py`：task 处于 `OBSERVED` 时允许稳定观测修正；进入 `PENDING/RUNNING` 后只接受距离锁点不超过 `target_update_max_drift` 的小修正，超过则只刷新可见性和 metadata，不拖动导航目标。

提议接口：

```python
class PortalMinimapDetectionStrategy:
    def detect(self, frame, config, templates, scales) -> list[PortalHit]: ...

def hit_to_detection(hit, frame, tick, config, source: str) -> EventDetection | None: ...
```

## 期望包边界

```text
PortalEventDefinition
    ├── creates PortalMinimapDetector
    │       ├── feature matcher
    │       ├── shape-color matcher
    │       └── template matcher
    └── creates PortalEventHandler
            ├── approach/move request
            ├── main-view confirmation
            ├── click/key interaction
            └── completion/fail state
```

## 可复用算法组件

### `minimap_feature_matcher/`

角色：通过从 templates 和 frame 提取蓝/青色 body pixels 来匹配 portal。

算法摘要：

1. `portal_blue_mask()` 把 BGR/gray image 转 HSV，并 threshold hue/saturation/value。
2. `build_feature_templates()` 把 loaded template images 转成 binary blue masks，并丢弃 blue pixels 太少的 templates。
3. `match_portal_features()` 创建 frame blue mask，在 binary masks 上运行 scaled template matching，收集 response peaks，按 blue pixel count 过滤，用 `mask_score * 0.86 + density_score * 0.14` 打分，并 merge nearby hits。
4. `merge_feature_hits()` 按 center distance 去重，保留高分 hits。

当前拆分结果：
- `minimap_feature_matcher/__init__.py` 保留旧 public API 和 `_resize_mask()`、`_response_hits()` 私有 helper 导出。
- `minimap_feature_matcher/models.py` 承接 `PortalFeatureTemplate`、`PortalFeatureHit` 和 center 计算。
- `minimap_feature_matcher/masks.py` 承接 HSV 蓝/青色 body mask。
- `minimap_feature_matcher/templates.py` 承接 `TemplateSpec` -> feature template 构造和 min pixel 过滤。
- `minimap_feature_matcher/response.py` 承接多尺度 mask resize 和 response peak suppression。
- `minimap_feature_matcher/pipeline.py` 承接 `match_portal_features()` 与 `merge_feature_hits()` 主流程。

这是好的可复用 detector component。后续若要继续调参，应优先补静态截图 smoke 或小样本对比，而不是把 detector mode dispatch 写回算法 package。

### `minimap_shape_color/` helper package

角色：使用 blue body、white/gray outer ring、combined shape、edge、color similarity 做更严格 portal recognition。

算法摘要：

1. 构建 frame masks：
   - blue portal body mask；
   - 低饱和高亮 outer mask，排除 blue；
   - combined shape mask；
   - Canny edge mask。
2. 对每个 template 和 scale 准备对应 blue/outer/shape/edge template masks。
3. 计算 combined response：
   - blue mask response weight 0.30；
   - outer mask response weight 0.24；
   - shape mask response weight 0.24；
   - edge response weight 0.12；
   - color response weight 0.10。
4. 使用 local suppression 收集 response peaks。
5. 用 F1-like mask scores、HSV color distance、optional signature score 评估候选。
6. 按 score、blue shape、outer shape、combined shape、blue pixel range、outer pixel minimum 拒绝。
7. 按 center radius 合并 accepted/rejected candidates。

当前拆分结果：
- `minimap_shape_color/models.py` 承接 `PortalShapeColorParams`、`PortalShapeColorHit`、`PortalShapeColorDebug`、`PreparedShapeColorTemplate`。
- `minimap_shape_color/masks.py` 承接 `portal_blue_mask()`、`portal_outer_mask()`、BGR/HSV 转换和缩放。
- `minimap_shape_color/templates.py` 承接 template scale/mask/edge 准备。
- `minimap_shape_color/scoring/` 承接 response、F1-like score、HSV color score 和候选评估；其中 response/color/overlap/candidate 已按评分阶段拆分。
- `minimap_shape_color/pipeline.py` 承接 `match_portal_shape_color()` 和 `merge_shape_color_hits()`。

它仍是算法重组件，但现在可以按阶段阅读和测试。后续若调参，应优先针对 scoring/pipeline 写小样本验证，不要把 detector mode dispatch 再写回 matcher facade。

### `main_view_confirmer.py`

角色：在 full game view 中确认 portal-like blue/purple glow。

算法摘要：

1. `build_blue_glow_mask()` threshold cyan、blue、violet HSV ranges。
2. Morphological open/close/dilate 清理 glow mask。
3. `detect_portal_candidates()` 找 contours，按 area、bbox ratio、min size、aspect、circularity、glow ratio 过滤并打分。
4. `is_strict_portal_candidate()` 根据 JSON params 应用更严格 acceptance thresholds。

当前这个 confirmer 未直接接入 `PortalEventHandler.update()`；handler 依赖距离、按键、relocalization、position/environment change、known-exit checks。如果要在交互前做 main-view confirmation，应作为 handler phase 或 hook 加入，而不是藏在 navigation code 里。

## Handler 状态机

`PortalEventHandler` 是真实状态机，当前保留 string state 和多个 timestamp/signature fields 作为 runtime facade 状态；各阶段逻辑已经下沉到 `handler/` 子包。

当前状态：

```text
move_near_event
  ├── if player missing -> WAIT
  ├── if distance > arrival_radius -> MOVE_TO portal
  ├── if distance > interact_radius -> MOVE_TO portal with force_repeat_click
  └── else -> align_on_portal

align_on_portal
  ├── first entry -> MOVE_TO portal with force_click_target
  ├── wait portal_point_click_wait_ms
  └── then -> interact

interact
  ├── record interaction time/player/signature
  ├── press D
  └── -> wait_result

wait_result
  ├── wait post_interact_wait_ms
  ├── if known exit reached -> COMPLETE teleport
  ├── if player moved teleport_min_distance -> COMPLETE teleport
  ├── if minimap environment signature changed -> COMPLETE teleport
  ├── if timeout -> FAIL
  └── otherwise WAIT with force_relocalize metadata
```

当前拆分：

```text
handler/
  __init__.py                # EventHandler adapter 旧入口
  runtime.py                 # PortalEventHandler 状态拥有者
  movement.py                # localization/distance -> MOVE/WAIT
  interaction.py             # force portal-point click -> wait -> press D
  completion.py              # wait_result -> COMPLETE/FAIL/WAIT relocalize
  diagnostics.py             # state/log throttling
  compat.py                  # old private helper aliases
completion_detector.py       # known-exit / position-change / environment-change checks
environment_signature.py     # minimap signature extraction/difference
```

当前执行状态：

- `environment_signature.py` 已抽出 `_minimap_environment_signature()` 和 `_signature_difference()` 的实现，旧私有函数仍在 `handler.py` 中委托。
- `completion_detector.py` 已抽出 known-exit、position-change、environment-change 完成判定，`PortalEventHandler._teleport_completion()` 和 `_near_known_exit_portal()` 保留为 wrapper。
- `handler.py` 单文件已替换为 `handler/` facade package；旧路径 `core.events.types.portal.handler.PortalEventHandler` 不变。
- `handler/movement.py` 已抽出玩家定位缺失、到达半径、交互半径和 `force_repeat_click` 决策。
- `handler/interaction.py` 已抽出 portal 点强制点击、点击后等待、按 `D`、交互位置和 minimap signature 记录。
- `handler/completion.py` 已抽出 `wait_result` 阶段：post-interact settle、teleport completion、timeout 和 forced relocalize wait。

状态模型提案：

```python
class PortalHandlerPhase(str, Enum):
    MOVE_NEAR_EVENT = "move_near_event"
    ALIGN_ON_PORTAL = "align_on_portal"
    INTERACT = "interact"
    WAIT_RESULT = "wait_result"

@dataclass
class PortalHandlerRuntime:
    phase: PortalHandlerPhase
    last_interact_ms: int | None = None
    interact_pos: tuple[int, int] | None = None
    interact_signature: np.ndarray | None = None
    portal_point_click_ms: int | None = None
    teleport_relocalize_requested: bool = False
```

这会让测试和 hooks 明显更容易。

## Hook 候选

不应硬编码到 navigation 的 portal-specific hook 点：

- `on_candidate_detected(candidate, mode)`
- `on_candidate_rejected(candidate, reason)`
- `on_arrival_radius_entered(task)`
- `on_main_view_confirmed(candidate)`
- `on_interaction_requested(action)`
- `on_teleport_detected(completion_signal)`
- `on_exit_portal_suppressed(task)`

映射到 generic hooks：

| Portal 需求 | Generic hook 位置 |
| --- | --- |
| Candidate detected/rejected | Event monitor 或 detector hook：`on_detections`，如果需要详细拒绝原因，再加 detector-local debug hook。 |
| Stable portal task created | Event memory hook：`on_task_created`、`on_task_confirmed`。 |
| Event selected for navigation | Navigation task hook：`after_task_selection`。 |
| Approach released | Navigation event-approach hook：`before_event_handler` / `on_event_approach_released`。 |
| Handler phase changed | Event runner/handler hook：`on_handler_action` 或 package-local hook。 |
| Teleport completed | Event runner hook：`on_task_completed`；memory hook 处理 teleport session completion。 |

## 大文件候选

- `minimap_detector.py` 保留为 detector facade；shape-color 真实算法集中在 `minimap_shape_color/` 子包，detector mode/diagnostics/conversion 集中在 `minimap_detection/` 子包。旧 `minimap_shape_color_matcher.py` 兼容壳已删除，后续重点是补 acceptance/rejection 小样本验证。
- `handler.py` 已降为 `handler/` package；后续如果继续优化，可把 string state 升级为 enum/runtime dataclass，但当前先不改状态字段契约。
- `minimap_feature_matcher/` 已按 DTO、mask、template、response、pipeline 分类拆分；`minimap_shape_color/scoring/` 也已按 response/color/overlap/candidate 分类拆分。后续 shape-color 方向应优先做小样本验证和阈值解释，不要把 detector mode dispatch 写回算法包。

优先级：

1. 对 shape-color matcher 的 scoring/pipeline 补 acceptance/rejection 小样本验证。
2. 若后续需要更多 handler hooks，再把 string state 升级为 `PortalHandlerPhase` enum 和 runtime dataclass。
3. 如果 detector mode 继续增加，再把 `minimap_detection/modes.py` 升级为显式 strategy registry。

## Config 边界

`PortalEventConfig` 是 typed 且有用的。`PortalEventDefinition.config_schema()` 中 schema 很长，但适合 GUI 生成。

重构机会：

```text
config.py
  PortalEventConfig
  portal_config_schema()

definition.py
  delegates config_schema() to portal_config_schema()
```

这样能避免在 definition class 里保留大 schema literal。

## 当前状态

状态：partial。已阅读 definition、config、assets、minimap detector、feature matcher、shape-color matcher、main-view confirmer、handler。当前 feature matcher、shape-color matcher、shape-color scoring、detector mode dispatch 和 handler 状态机均已完成第一轮 facade/helper 拆分；后续重点转向小样本验证或更大的 core/navigation task 文件继续瘦身。
