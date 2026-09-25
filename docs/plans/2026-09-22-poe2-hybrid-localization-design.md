# PoE2 混合实时定位设计

## 1. 目标

在 PoE2 实验边界内实现实时人物定位：首次进入和视觉跟踪丢失时只读取一次内存人物坐标，以该坐标作为小范围视觉注册锚点；正常运行期间只使用连续小地图画面做局部跟踪。输出人物当前位置、置信度、轨迹、注册变换和可复核诊断，不接路径规划或任何输入设备。

本阶段验证稳定后，再把不含 PoE2 术语的状态机、协议和几何能力下沉 `core`。在验证前，正式 PoE2 runtime、第一页绘图模式和既有导航页面保持不变。

## 2. 非目标

- 不计算目标路线。
- 不控制 Xbox、键盘或鼠标。
- 不连接 Host 或 LAN 同步。
- 不处理多人 marker；首版只支持单人中心模式。
- 不以固定周期读取内存。
- 不在定位失败时沿用旧坐标生成新轨迹。
- 不把单帧 `anchored_candidate` 宣称为跨帧确认。

## 3. 现有能力与问题

### 3.1 可直接复用

- `Poe2PlayerPositionSource.read_once()`：读取当前人物 world/native-grid 坐标和 area instance。
- `TerrainOrientation`：统一变换 terrain 数组、点和位移。
- `TerrainReference`：提供 wall/walkable/explored 层。
- `CaptureEvidence` 与 PoE2 monitor profile：提供同帧 raw/processed/match/wall/fog 视觉层。
- `TrajectoryBuffer` 与 `LocalizationResult`：保存成功轨迹并发布类型化定位结果。
- `MapLocalizer`：已经表达“绝对定位优先、局部跟踪、丢失恢复”的通用状态思想。
- `estimate_phase_displacement()`、`LocalMapMatcher`：帧间预测与有界局部匹配基础能力。
- `poe2_anchor_local_registration_probe.py`：已经验证内存锚点附近的旋转、镜像、比例和平移联合注册。

### 3.2 必须修正

- `Poe2LocalizationRuntime._global_match()` 当前仍用整张 wall layer 的 `cv2.matchTemplate()`，没有消费内存锚点，重复地形和随机方向下不可靠。
- 当前 `MapLocalizer` 在 `NEED_GLOBAL/RECOVERY_REQUIRED` 中每帧调用 global matcher；如果 global matcher 直接读取内存，会形成连续读取。
- 当前 `FrameRegistration` 只明确保存 frame origin 和 draw scale，不能完整表达任意角度、水平镜像和比例组成的二维相似变换。
- 实验算法仍位于 CLI 文件，正式实验 session 不能反向依赖 `tools/debug`。

## 4. 分层架构

```text
PoE2 实验 UI / composition
  Poe2HybridLocalizationExperimentPage
  Poe2HybridLocalizationComposition
        |
        v
PoE2 实验 session 与适配器
  Poe2HybridLocalizationSession
  Poe2MemoryAnchorProvider
  Poe2VisualEvidenceBuilder
        |
        v
实验定位能力（接口保持领域中立）
  HybridLocalizationController
  AnchoredAbsoluteRegistrar
  VisualLocalTracker
  OneShotRecoveryPolicy
        |
        v
现有通用基础能力
  LocalizationResult / TrajectoryBuffer / FrameRegistration
  TerrainOrientation / LocalMapMatcher / phase displacement
  NumPy / OpenCV
```

依赖只向下。内存地址、PoE2 area instance 解析、profile 和 UI 文本不得进入通用控制器或注册算法。

## 5. 模块规划

### 5.1 实验包

计划新增：

```text
src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/
  __init__.py
  models.py
  contracts.py
  controller.py
  recovery.py
  similarity_search.py
  absolute_registrar.py
  local_tracker.py
  memory_anchor.py
  session.py
  composition.py
```

职责：

- `models.py`：不可变输入、锚点、相似变换、绝对注册、运行状态。
- `contracts.py`：`AnchorProvider`、`AbsoluteRegistrar`、`LocalTracker` 协议。
- `controller.py`：只管理状态转换和结果所有权，不截图、不读内存、不调用 OpenCV。
- `recovery.py`：每个 recovery revision 最多消费一次锚点读取许可。
- `similarity_search.py`：从现有 probe 提取纯数组相似变换和 Chamfer 搜索；无 CLI/文件系统依赖。
- `absolute_registrar.py`：组合锚点裁剪、特征清理、多个 transform basin 和置信度门。
- `local_tracker.py`：固定已确认的方向/镜像/比例，只在上一位置附近搜索平移。
- `memory_anchor.py`：把 `Poe2PlayerPositionSource` 适配为 `AnchorProvider`，统一 native/oriented 坐标。
- `session.py`：一次截图、一份 evidence、一次 controller update，并管理轨迹和 listener。
- `composition.py`：组装实际 PoE2 provider、registrar、tracker 和 session。

### 5.2 调试工具

`tools/debug/poe2_live_terrain_localization_probe.py` 和 `poe2_anchor_local_registration_probe.py` 保留 CLI/诊断职责，改为调用实验包中的纯算法；外部命令和已有报告格式保持兼容。

### 5.3 实验 UI

在现有 PoE2 数据采集测试页内增加独立“混合定位实验”区域，不接正式 `Poe2LocalizationRuntime`：

- 开始混合定位。
- 停止定位。
- 恢复失败后“重新恢复一次”。
- 当前状态、坐标、来源、置信度、area instance。
- 当前 transform：角度、镜像、比例、平移。
- memory read count、recovery revision、失败原因。
- 当前小地图、wall mask、局部 terrain overlay。
- terrain 上的人物 marker 和成功轨迹。

## 6. 核心契约

```python
@dataclass(frozen=True)
class PositionAnchor:
    position: tuple[float, float]
    area_instance: str
    captured_at_ms: int
    source: str
    confidence: float = 1.0


@dataclass(frozen=True)
class SimilarityTransform2D:
    angle_degrees: float
    reflect_horizontal: bool
    scale: float
    translation: tuple[float, float]


@dataclass(frozen=True)
class AbsoluteRegistration:
    result: LocalizationResult
    transform: SimilarityTransform2D
    anchor_error: float
    area_instance: str
    diagnostics: Mapping[str, Any]


class AnchorProvider(Protocol):
    def read_once(self, expected_instance_id: str) -> PositionAnchor: ...


class AbsoluteRegistrar(Protocol):
    def register(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchor: PositionAnchor,
        prior: AbsoluteRegistration | None,
    ) -> AbsoluteRegistration | None: ...


class LocalTracker(Protocol):
    def track(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        previous_frame: HybridFrame,
        previous: AbsoluteRegistration,
    ) -> AbsoluteRegistration | None: ...
```

`SimilarityTransform2D` 必须显式保存方向、镜像、比例和平移。`metadata` 只保存诊断，不作为运行必需字段。

## 7. 状态机

```text
NEED_ABSOLUTE
  首次启动；允许一次锚点读取和绝对注册
      | success
      v
LOCAL_TRACKING
  每帧只做视觉预测和有界局部注册
      | local failure
      v
RECOVERY_PENDING
  新 recovery revision；允许读取一次内存
      | success                  | failed
      v                          v
LOCAL_TRACKING             RECOVERY_REQUIRED
                                |
                                | explicit retry
                                v
                         RECOVERY_PENDING

任意状态 -- stop --> STOPPED
地图实例变化 --> 清空 transform/position/trajectory --> NEED_ABSOLUTE
```

规则：

1. 一个 recovery revision 最多调用一次 `AnchorProvider.read_once()`。
2. 恢复失败后 `update()` 只能返回失败状态，不得自动开启新 revision。
3. `retry_recovery()` 是开启新 revision 的唯一入口。
4. 失败帧不更新 latest confirmed position，不追加 trajectory。
5. 新地图实例使旧 transform、位置、前帧和轨迹全部失效。

## 8. 调用链

### 8.1 首次绝对定位

```text
Poe2CaptureTestPage.start_hybrid_localization()
 -> composition.create_session(snapshot, config)
 -> Poe2HybridLocalizationSession.start()
 -> session.tick()
 -> frame_source.capture(config)
 -> evidence_builder.build(raw, config)
 -> controller.update(frame)
 -> recovery_policy.consume(revision=1)
 -> anchor_provider.read_once(snapshot.instance_id)
 -> absolute_registrar.register(frame, reference, anchor, prior=None)
 -> controller._accept_absolute(registration)
 -> trajectory.append(position, source="anchored_absolute")
 -> listener(HybridLocalizationState)
 -> page.handle_hybrid_state(state)
 -> render marker/trajectory/diagnostics
```

### 8.2 正常视觉跟踪

```text
QTimer.timeout
 -> session.tick()
 -> capture/build same-frame evidence
 -> controller.update(frame) [LOCAL_TRACKING]
 -> local_tracker.track(frame, previous_frame, previous_registration)
 -> transform current wall mask with fixed angle/reflection/scale
 -> phase predictor estimates bounded origin
 -> local registrar searches translation inside radius
 -> accepted registration
 -> controller updates previous frame/registration
 -> trajectory.append(source="visual_local")
 -> UI redraws marker and trajectory
```

### 8.3 视觉丢失与恢复

```text
local_tracker.track() -> None
 -> controller mode = RECOVERY_PENDING
 -> current tick returns position=None, reason="local_tracking_failed"
 -> no stale trajectory point

next tick
 -> recovery_policy consumes current revision once
 -> anchor_provider.read_once(expected_instance)
 -> absolute_registrar.register(..., prior=last_confirmed_registration)
 -> same instance: lock angle/reflection/scale, refine translation near anchor
 -> success: LOCAL_TRACKING
 -> failure: RECOVERY_REQUIRED, no further memory reads
```

### 8.4 地图实例变化

```text
anchor_provider returns mismatched area_instance
 -> reject anchor
 -> session invalidates reference/registration
 -> stop timer or request a new terrain capture
 -> UI displays area_instance_changed
```

不得拿新实例人物坐标去裁剪旧 terrain。

## 9. 首帧与恢复复用规则

两种场景都调用 `AnchoredAbsoluteRegistrar.register()`：

- `prior is None`：搜索多个角度、镜像和比例 basin；用于首次进入或地图实例变化。
- `prior.area_instance == anchor.area_instance`：锁定已确认方向、镜像和比例，只在锚点附近细化平移；用于视觉丢失恢复。
- prior 与 anchor 实例不一致：拒绝，不自动降级成全图搜索。

该分支由明确输入状态决定，不允许注册器读取 UI、profile 或进程状态。

## 10. 位置与变换语义

- `PositionAnchor.position` 必须与 `TerrainReference` 使用同一坐标空间。
- PoE adapter 负责调用 `TerrainOrientation.transform_point()`，通用注册器不知道 native-grid。
- `SimilarityTransform2D` 表示当前小地图 frame 到 terrain reference 的映射。
- 人物处于截图中心时无需人物图像识别；`local_player` 来自 capture geometry。
- 多人 marker 识别以后作为另一种 `LocalPlayerProvider` 注入，不修改注册器。

## 11. 一致性与失败规则

- 截图和内存锚点都记录时间；时间差超过配置上限则拒绝本次恢复。
- frame timestamp 必须单调递增，陈旧帧不得更新状态。
- anchor、registration 和 reference 的 area instance 必须一致。
- 非有限坐标、越界锚点、低特征帧、候选分差不足均返回失败。
- controller 捕获 provider/registrar 的预期失败并发布 reason；程序错误保留异常日志，不伪装成普通低置信度。
- stop/reset 后旧 listener 回调不能重新激活 session。

## 12. 日志与诊断

每个 tick 使用同一 `frame_id` 和 `recovery_revision`：

```text
hybrid.tick_start
hybrid.frame_captured
hybrid.local_tracking_success|failed
hybrid.recovery_requested
hybrid.anchor_read_start|success|failed
hybrid.absolute_registration_start|success|failed
hybrid.state_published
```

日志字段至少包含 mode、source、position、confidence、area instance、anchor error、angle、reflection、scale、耗时和失败原因。诊断保存必须由用户显式触发，运行时不持续写盘。

## 13. 测试策略

### 13.1 纯单元测试

- 一次 recovery revision 只允许一次 anchor read。
- 首帧成功后进入 local tracking。
- local failure 进入 pending，但同一失败 tick 不读取内存。
- 恢复成功回到 local tracking。
- 恢复失败停在 required；后续 tick 不读取。
- explicit retry 创建新 revision 并允许一次读取。
- 失败帧不追加轨迹。
- stop/reset/instance change 清理状态。

### 13.2 算法测试

- 已知旋转、镜像、比例和平移恢复。
- prior 存在时锁定方向/镜像/比例，只恢复平移。
- 对称区域返回 ambiguous。
- 锚点范围外高分干扰不进入 Top-K。
- local tracker 只搜索有界区域，不回退全图。

### 13.3 组合测试

- fake frame source + fake memory source + real controller 的首次/局部/恢复完整序列。
- area instance mismatch fail closed。
- 时间偏差超限 fail closed。
- composition 不构造 Xbox、Host 或 LAN 依赖。

### 13.4 实机验收

1. 获取 terrain 后开始混合定位，首帧只产生一次内存读取。
2. 正常行走期间 memory read count 不增加，marker 和轨迹连续。
3. 人为制造视觉失败后只增加一次读取，恢复成功后继续轨迹。
4. 恢复失败时位置为空、轨迹停止；未点击重试时读取次数不再增加。
5. 进入新地图后旧位置和 transform 不再显示。

## 14. 推进边界

第一阶段只在 PoE2 实验页验证。满足多地图、多次丢失恢复和长时间轨迹稳定性后：

1. 将 `models.py`、`contracts.py`、`controller.py`、`recovery.py` 中无 PoE2 语义的能力迁入 `core.localization`。
2. PoE2 只保留 memory anchor、terrain/reference、visual evidence 和 composition 适配器。
3. 纯内存定位模式以后实现为另一种统一 `PositionTracker`，与混合模式共享 UI 输出契约，但不混入本阶段控制器。

