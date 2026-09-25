# PoE2 多帧全局定位与导航定位实施计划

## Goal

在 PoE2 实验台实现可回放、可比较的首帧/恢复全局定位：方案 A 使用有限局部拼图，方案 B 使用多帧共同变换候选；确认后进入正常视觉跟踪，并向导航输出带版本、时效和不确定性的定位结果。整个过程先留在实验目录，不接正式产品页面和任何实际输入执行。

## Architecture Overview

```text
PoE2 capture_test_page
        |
        v
MultiFrameLocalizationSession
        |
        +--> FrameEvidenceCollector --截图/识别/运动门控--> EvidenceWindow
        |                                                     |
        |                                                     +--> RollingSubmap --> Strategy A
        |                                                     +--> FrameSet ---------> Strategy B
        |
        +--> AnchorProvider (每个 recovery_revision 最多一次)
        |
        +--> RegistrationValidator --> RegistrationStateEstimator
                                              |
                                              v
                    PositionEstimate (native 坐标、速度、协方差/候选区、版本、时效)
                                              |
                    NavigationLocalizationAdapter / 页面叠图 / 调试归档
```

新增实验层位于：

`src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/`

它复用现有的 `HybridFrame`、`PositionAnchor`、`SimilarityTransform2D`、`AnchoredAbsoluteRegistrar`、`VisualLocalTracker`、`canonical_wall_mask()`、`estimate_bounded_displacement()`、`MapStitcher` 和 PoE2 测试页。实验层不修改第一页绘图模式，不导入导航 UI，不调用 Xbox、键盘、鼠标、Host 或 LAN。

稳定后再把与 PoE2 无关的能力下沉到 `core/localization`：运动门控、证据窗口、候选不确定性和定位结果契约；PoE2 只保留内存锚点、profile 识别和地形适配器。

## Code Layout

首轮代码按“通用能力、PoE2 适配、实验业务、实验 UI”四层安排。下面是目标目录；带 `new` 的文件是本计划新增内容，现有文件保持原职责。

```text
src/auto_modules/
├── core/
│   ├── localization/
│   │   ├── canonical_wall.py             # 通用 wall mask 规范化（已有）
│   │   ├── displacement.py               # 通用坐标位移变换（已有）
│   │   ├── frame_displacement.py         # phase displacement 门控（已有）
│   │   ├── local_matcher.py              # 有界局部形状匹配（已有）
│   │   └── ...
│   └── mapping/
│       └── stitcher.py                   # 通用帧拼接基础能力（已有）
│
├── features/poe2/live_terrain/
│   ├── capture_adapter.py                # PoE2 地图获取适配（已有）
│   ├── capture_samples.py                # 截图/识别证据（已有）
│   ├── monitor_config.py                 # PoE2 监控 profile（已有）
│   ├── terrain_reference.py              # native terrain reference（已有）
│   ├── orientation.py                    # PoE2 初始方向配置适配（已有）
│   ├── player_position.py                # PoE2 内存人物锚点适配（已有）
│   ├── stitching_session.py              # 现有采集绘图业务（已有）
│   └── experimental/
│       ├── hybrid_localization/          # 现有单帧锚点 + F2F 混合定位
│       │   ├── models.py
│       │   ├── memory_anchor.py
│       │   ├── absolute_registrar.py
│       │   ├── local_tracker.py
│       │   ├── controller.py
│       │   ├── session.py
│       │   └── composition.py
│       │
│       └── multiframe_localization/      # 本计划新增的多帧全局定位实验
│           ├── __init__.py               # 对外导出稳定实验契约
│           ├── models.py                 # evidence/candidate/estimate 数据模型
│           ├── motion_gate.py            # 静止/移动/未知和关键帧准入
│           ├── evidence_window.py        # 有界关键帧和 segment 生命周期
│           ├── rolling_submap.py         # 稀疏 tile 局部拼图
│           ├── shape_registration.py     # 形状评分、ROI、候选验证
│           ├── strategy_a.py             # 拼图达到阈值后注册
│           ├── strategy_b.py             # 多帧共同变换候选
│           ├── state_estimator.py        # 预测/观测门控/协方差
│           ├── coordinator.py            # 全局定位、跟踪、恢复状态机
│           ├── session.py                # 截图、计算和发布调度
│           ├── archive.py                # 显式样本归档和回放契约
│           ├── navigation_adapter.py    # 定位结果到导航 observation
│           └── composition.py            # 只给实验台使用的组合根
│
├── ui/modes/poe2_live_terrain/
│   ├── page.py                           # 正式 PoE2 页面（首轮不接多帧）
│   ├── capture_test_page.py              # 实验台入口
│   ├── capture_monitor_window.py         # 监控窗口（复用）
│   ├── presenter.py                      # 地图/人物/候选显示变换
│   └── multiframe_panel.py               # 本计划新增的 A/B 实验面板
│
tools/debug/poe2_multiframe_localization_probe.py  # 本地回放探针
tests/poe2_live_terrain/test_multiframe_*.py       # 实验契约与算法回归
```

### 目录职责和依赖方向

```text
core/localization, core/mapping
        ↑ 被使用
features/poe2/live_terrain/experimental/multiframe_localization
        ↑ 被 composition 组装
ui/modes/poe2_live_terrain/capture_test_page.py
```

- `core` 不知道 PoE2、内存锚点、地图页面或方案 A/B；稳定后的通用代码才进入这里。
- `features/poe2/live_terrain` 负责截图配置、native 地图格式、内存读取和 PoE2 识别适配。
- `experimental/hybrid_localization` 保留现有单帧/连续跟踪实验；`experimental/multiframe_localization` 负责新 A/B 证据阶段。两者可以共享模型和底层算法，但不共享可变 session 状态。
- `composition.py` 是唯一的组装入口，页面不直接实例化 registrar、strategy 或 estimator。
- `capture_test_page.py` 只负责按钮、定时器和展示状态；算法状态归 `session/coordinator` 所有。
- `page.py` 首轮只保留现有产品链路，避免实验参数污染正式定位。
- `tests/poe2_live_terrain` 按实验包拆分测试；`tests/test_*` 只放已经证明与 PoE2 无关、准备下沉到 core 的通用契约测试。

### 稳定后的下沉规则

第一轮不要提前把 `strategy_a.py`、`strategy_b.py` 或 PoE2 profile 逻辑放入 `core`。经过合成数据、历史样本和实机回放后，只有满足以下条件的代码才下沉：

1. 输入输出不包含 PoE2、native terrain producer、内存读取或页面词汇；
2. 可以用通用 wall mask/位移/候选数据独立测试；
3. 至少存在第二个明确复用场景；
4. 下沉不会要求修改无关业务页面。

预计优先下沉的是 `motion_gate`、`evidence_window`、`shape_registration` 的纯评分部分和 `PositionEstimate` 契约；`strategy_a`、`strategy_b`、`memory_anchor`、PoE2 composition 永远保留在业务适配层。

## Tech Stack

- Python 3.x，`dataclasses`、`typing.Protocol`、NumPy、OpenCV。
- PySide6 `QTimer`，现有 `Poe2CaptureTestPage`。
- pytest；测试使用合成 wall mask、现有样本回放和 fake anchor/capture provider。
- 现有 `MapStitcher` 只作为融合算法适配器，实验版必须包一层有界存储，禁止分配 6000×6000 全画布作为默认滚动窗口。

## 不变量与实现顺序

1. 点使用 `(x, y)`，数组使用 `[y, x]`；native terrain 是定位和导航唯一交换坐标。
2. 图像旋转使用 OpenCV 图像坐标矩阵 `[[cos, sin], [-sin, cos]]`，顺序固定为水平镜像、旋转、比例。
3. 墙体位移 `d_t` 是墙从上一帧到当前帧的移动；人物在地图中的增量为 `M[(c_t-c_prev)-d_t]`。
4. A/B 共用不可变证据快照，不能把 A/B 的结果当成独立测量相乘加权。
5. 静止帧只做低频运动检测，不加入关键帧、不增长拼图、不重复注册。
6. 单次 evidence version 最多一个注册任务；旧版本结果返回时丢弃。
7. 全局定位成功必须同时通过人物锚点、墙体形状、候选歧义、留出帧验证；滤波不能替代注册。

## 实施任务

每项任务都按 TDD 执行：先写失败测试，运行确认失败，实现最小代码，再运行指定测试，最后提交一个独立 checkpoint。计划中的代码片段是接口起点；实现时按现有格式化和类型检查风格调整。

### Task 1: 建立实验多帧数据契约

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/models.py`
- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/__init__.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_models.py`

**先写失败测试：** 覆盖只读 mask、`frame_id` 单调、未知运动状态、候选变换、可信区间和版本字段；空 mask、负时间、非有限坐标必须拒绝。

**接口起点：**

```python
class MotionState(StrEnum):
    STATIONARY = "stationary"
    MOVING = "moving"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class MultiFrameEvidence:
    frame: HybridFrame
    motion: FrameDisplacement
    local_offset: tuple[float, float]
    is_keyframe: bool
    segment_id: int

@dataclass(frozen=True)
class CandidateRegion:
    transform: SimilarityTransform2D
    position: tuple[float, float]
    covariance: np.ndarray | None
    score: float
    support_frames: tuple[int, ...]

@dataclass(frozen=True)
class PositionEstimate:
    status: str
    position: tuple[float, float] | None
    velocity: tuple[float, float] | None
    covariance: np.ndarray | None
    candidate_regions: tuple[CandidateRegion, ...]
    instance_id: str
    registration_version: int
    evidence_version: int
    fresh: bool
    age_ms: int
    source: str
    reason: str
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_models.py
```

预期：初次运行在实现前失败；实现后全部通过，且数组不能被调用方修改。

**提交：** `feat: add multiframe localization contracts`

### Task 2: 实现运动分类和关键帧准入

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/motion_gate.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_motion_gate.py`

**先写失败测试：** 使用合成平移验证三类结果：高质量零位移为 `STATIONARY`；高质量有效位移为 `MOVING`；低 response、冻结帧、超时或过大位移为 `UNKNOWN`，不得误判为静止。

**接口起点：**

```python
@dataclass(frozen=True)
class MotionDecision:
    state: MotionState
    displacement: FrameDisplacement
    should_capture_keyframe: bool
    reason: str

class MotionGate:
    def decide(self, previous: HybridFrame, current: HybridFrame, *, elapsed_ms: int) -> MotionDecision:
        displacement = estimate_bounded_displacement(
            canonical_wall_mask(previous.wall_mask),
            canonical_wall_mask(current.wall_mask),
            min_quality=self.min_quality,
            max_shift=self.max_shift,
        )
        if elapsed_ms > self.max_frame_gap_ms or not displacement.accepted:
            return MotionDecision(MotionState.UNKNOWN, displacement, False, "unreliable_frame")
        moving = displacement.distance >= self.movement_dead_zone
        return MotionDecision(
            MotionState.MOVING if moving else MotionState.STATIONARY,
            displacement,
            moving and displacement.distance >= self.keyframe_distance,
            "moving" if moving else "stationary",
        )
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_motion_gate.py tests/test_frame_displacement.py
```

预期：静止不会产生关键帧；未知状态不会被当作零位移接入轨迹。

**提交：** `feat: gate multiframe evidence by observed motion`

### Task 3: 实现有界证据窗口与位姿片段

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/evidence_window.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_evidence_window.py`

**先写失败测试：** 验证环形关键帧上限、时间/距离/字节上限、相邻帧断链、segment 递增、旧 evidence version 淘汰和只读快照。

**接口起点：**

```python
class EvidenceWindow:
    def append(self, evidence: MultiFrameEvidence) -> bool:
        if evidence.motion.state is not MotionState.MOVING:
            return False
        if self._last is not None and evidence.segment_id != self._segment_id:
            self._frames.clear()
        self._frames.append(evidence)
        self._trim_by_limits()
        self._version += 1
        return True

    def break_segment(self, reason: str) -> int:
        self._segment_id += 1
        self._frames.clear()
        self._version += 1
        self.last_break_reason = reason
        return self._segment_id
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_evidence_window.py
```

预期：窗口内存有界；淘汰不会修改保留帧；断链后禁止跨 segment 直接拼接。

**提交：** `feat: add bounded multiframe evidence window`

### Task 4: 实现有界滚动局部拼图

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/rolling_submap.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_rolling_submap.py`

**先写失败测试：** 合成帧按 `local_offset` 放入局部图，验证未知区域不计为墙，帧淘汰后贡献被移除，重复静止帧不增加权重，重建后不产生重影。

**实现要求：** 可以调用 `MapStitcher` 的 `add_evidence`，但必须配置有限 tile/关键帧输入，并提供从保留关键帧重建的入口；不能暴露 6000×6000 全图作为默认状态。每个 tile 至少维护 `wall_weight`、`observed_weight`、`last_frame_id`。

**接口起点：**

```python
class RollingSubmap:
    def rebuild(self, frames: Sequence[MultiFrameEvidence]) -> SubmapSnapshot:
        self._tiles.clear()
        for item in frames:
            if not item.is_keyframe:
                continue
            self._merge(item.frame.wall_mask, item.local_offset, item.frame.frame_id)
        return self.snapshot()

    def snapshot(self) -> SubmapSnapshot:
        return SubmapSnapshot(
            wall_mask=self._render_sparse_window(),
            observed_mask=self._render_observed_window(),
            origin=self._origin,
            frame_ids=tuple(self._frame_ids),
        )
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_rolling_submap.py tests/poe2_live_terrain/test_stitching_session.py
```

预期：超过窗口后内存和 tile 数保持上限，重建结果等于保留帧重新合并结果。

**提交：** `feat: add bounded rolling visual submap`

### Task 5: 提取稳健墙体评分和候选窗口

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/shape_registration.py`
- 修改 `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`（只提取可复用评分入口，不改变现有默认行为）
- 新增 `tests/poe2_live_terrain/test_multiframe_shape_registration.py`

**先写失败测试：** 验证厚度不同的墙体骨架仍能得分，文字/传送门孤立粗块不会单独造成高分，未知观察区不产生反向惩罚，锚点窗口和截图尺度正确限制 ROI。

**实现要点：**

```python
def score_shape(*, wall_mask, observed_mask, reference_boundary, transform, sigma, threshold):
    projected = transform_points(wall_points(wall_mask), transform)
    distances = reference_boundary.distance(projected)
    valid = observed_mask_for_points(projected, observed_mask)
    residual = huber(np.asarray(distances)[valid] / sigma)
    coverage = float((np.asarray(distances)[valid] <= threshold).mean()) if valid.any() else 0.0
    return ShapeScore(
        forward_error=float(residual.mean()) if residual.size else float("inf"),
        forward_coverage=coverage,
        usable_points=int(valid.sum()),
    )
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_shape_registration.py tests/poe2_live_terrain/test_hybrid_absolute_registrar.py
```

预期：既有单帧 `150/110/top_exclusion_rows=40` 行为不回归；新增评分可以输出结构分、覆盖率、支持点数和拒绝原因。

**提交：** `refactor: expose robust shape scoring for multiframe registration`

### Task 6: 实现方案 A：局部拼图达到阈值后注册

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_a.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_strategy_a.py`

**先写失败测试：** 少量墙体返回 `INSUFFICIENT_EVIDENCE`；达到关键帧、骨架长度、空间跨度和观察覆盖阈值后只提交一次冻结 evidence version；注册失败时新增证据才允许重试；留出帧错误超限不得确认。

**接口起点：**

```python
class StitchThenRegister:
    def evaluate(self, window: EvidenceWindow, submap: RollingSubmap, *, anchor: PositionAnchor,
                 reference: TerrainReference) -> StrategyResult:
        snapshot = submap.snapshot()
        if not self.thresholds.ready(snapshot, window.snapshot()):
            return StrategyResult.insufficient(window.version, "structure_below_threshold")
        frozen_version = window.version
        candidate = self.registrar.register_submap(snapshot, anchor=anchor, reference=reference)
        if candidate is None:
            return StrategyResult.rejected(frozen_version, "registration_failed")
        if not self.validator.holdout(candidate, window.holdout_frames()):
            return StrategyResult.rejected(frozen_version, "holdout_failed")
        return StrategyResult.confirmed(frozen_version, candidate, source="strategy_a")
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_strategy_a.py
```

预期：同一 evidence version 不重复昂贵注册；拼图中的人物位置使用当前帧 offset 换算，不把拼图起点误当当前位置。

**提交：** `feat: add stitch-then-register strategy`

### Task 7: 实现方案 B：多帧共同变换候选

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_b.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_strategy_b.py`

**先写失败测试：** 第一帧生成多个方向/镜像/比例 basin；后续移动帧只在候选预测 ROI 评价并累积误差；重复 seed 去重；相近分数保留多峰；最佳候选只有在支持帧、留出帧和 margin 都合格后确认。

**联合目标：**

```text
E(h) = λ_anchor * anchor_error(h)^2
     + Σ_i w_i * (forward_error_i(h) + λ_reverse * reverse_error_i(h))
     + λ_motion * trajectory_error(h)
```

**接口起点：**

```python
def update(self, frames, *, anchor, reference) -> CandidateSet:
    candidates = self._seed_or_predict(frames, anchor, reference)
    for candidate in candidates:
        candidate.add_scores(self._score_new_frames(candidate, frames, reference))
    candidates = deduplicate_candidates(candidates, angle_tol=0.5, scale_tol=0.01, position_tol=2.0)
    return CandidateSet(rank_candidates(candidates), evidence_version=frames.version)
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_strategy_b.py
```

预期：角度 180° 与 0° 等真正不同 basin 不被合并，不把多峰平均成错误中点；相关帧重复观察不会无限提高置信度。

**提交：** `feat: add joint multiframe candidate strategy`

### Task 8: 实现位置/速度状态估计和可信区间

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/state_estimator.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_state_estimator.py`

**先写失败测试：** 验证位移预测、观测统计门控、异常跳变拒绝、静止不缩小协方差、多峰候选分开输出、版本重置。

**实现公式：**

```python
p_pred = p_prev + delta_native
P_pred = P_prev + Q
innovation = z - p_pred
S = P_pred + R
D2 = innovation.T @ inv(S) @ innovation
K = P_pred @ inv(S)
p_next = p_pred + K @ innovation
P_next = (I - K) @ P_pred @ (I - K).T + K @ R @ K.T
```

`Q` 来自 phase 质量、帧间隔、变换协方差和模型误差；`R` 来自墙体残差、遮挡和候选范围。未校准的 score/phase response 不能直接当概率或方差。

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_state_estimator.py
```

预期：滤波只在已选定的同一方向/镜像/比例候选内运行；候选多峰时返回多个 `CandidateRegion`。

**提交：** `feat: estimate multiframe position uncertainty`

### Task 9: 组合全局定位状态机和一次性恢复

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/coordinator.py`
- 修改 `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`（只增加可注入的全局注册阶段，不改变旧默认 factory）
- 新增 `tests/poe2_live_terrain/test_multiframe_coordinator.py`

**状态：** `IDLE -> ANCHORING -> COLLECTING -> REGISTERING -> TRACKING -> DEGRADED -> RECOVERING/WAITING`。

**先写失败测试：** 首次只读一次锚点；静止不注册；A/B 只消费相同 evidence snapshot；注册成功重置 estimator；视觉连续失败只开启一个 recovery revision；旧异步结果因 instance/profile/evidence/revision 不符被丢弃。

**接口起点：**

```python
def tick(self) -> PositionEstimate:
    prepared = self.controller.prepare_capture()
    if prepared is not None:
        return self._state(reason=prepared.reason)
    raw = self.frame_source.capture(self.config_provider())
    evidence = self.evidence_builder.build(raw, self.config_provider())
    decision = self.motion_gate.decide(self.previous_frame, evidence.frame, elapsed_ms=...)
    item = self.collector.accept(evidence, decision)
    if self.mode in {Mode.ANCHORING, Mode.COLLECTING, Mode.REGISTERING}:
        return self._run_global_strategies(item)
    return self._run_tracking(item)
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_coordinator.py tests/poe2_live_terrain/test_hybrid_localization_controller.py
```

预期：每个 recovery revision 至多一次内存读取；失败停留在等待/收集状态，不后台无限重试。

**提交：** `feat: coordinate multiframe global localization`

### Task 10: 接入实验 session 与冻结异步任务

**文件：**

- 修改 `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`
- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_session.py`

**先写失败测试：** 每个 tick 只 capture/build 一次；注册使用 immutable window snapshot；计算中 UI 不阻塞；结果版本不匹配被丢弃；stop/reset 清空 timer-owned state。

**实现要求：** 将截图、证据、策略计算和发布分开；同一会话最多一个注册任务，待处理队列有界。不要在 Qt timer 中执行完整角度精搜。

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_session.py tests/poe2_live_terrain/test_hybrid_localization_session.py
```

预期：session 结果顺序稳定，停止后没有后台回调继续修改状态。

**提交：** `feat: run multiframe localization from immutable session snapshots`

### Task 11: 为实验台增加 A/B 控制和诊断面板

**文件：**

- 新增 `src/auto_modules/ui/modes/poe2_live_terrain/multiframe_panel.py`
- 修改 `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 新增 `tests/test_poe2_multiframe_panel.py`
- 新增 `tests/test_poe2_capture_test_page_multiframe.py`

**先写失败测试：** 验证开始/停止/重置、A/B 单独开关、快照状态、人物位置、候选范围、方向/镜像、keyframe 数量、运动状态、内存读取次数和错误日志都来自同一 published state；没有地图时按钮禁用。

**界面至少显示：** 原图、清理 wall、局部拼图、native 地图叠图、A/B 最佳结果和前两候选、候选椭圆/多峰区域、证据版本、恢复版本、耗时和拒绝原因。

**验证：**

```powershell
pytest -q tests/test_poe2_multiframe_panel.py tests/test_poe2_capture_test_page_multiframe.py
```

预期：原有捕获页和绘图模式行为不变；关闭页面停止 session、timer 和 pending publication。

**提交：** `feat: add multiframe localization experiment panel`

### Task 12: 注入实验组合根并隔离正式页面

**文件：**

- 修改 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/composition.py`
- 修改 `src/auto_modules/ui/modes/poe2/composition.py`
- 修改 `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_composition.py`

**先写失败测试：** 测试台 factory 能注入 fake capture/anchor/recognizer/reference；正式 PoE2 runtime 不创建多帧实验 session；A/B 共享同一个 frame source 但不共享可变策略状态。

**接口起点：**

```python
def build_poe2_multiframe_experiment(*, snapshot, config_provider, preview_capture,
                                     recognizer, player_position_source,
                                     clock_ms=None) -> MultiframeExperiment:
    shared = SharedEvidencePipeline(...)
    return MultiframeExperiment(
        session=MultiframeSession(shared=shared, strategy_a=..., strategy_b=...),
        strategy_a=..., strategy_b=..., window=shared.window,
    )
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_composition.py tests/test_poe2_composition.py
```

预期：正式页面依旧使用现有 hybrid factory；实验功能只能通过 capture test page 显式启动。

**提交：** `feat: compose multiframe experiment without product runtime coupling`

### Task 13: 增加实验归档和回放探针

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/archive.py`
- 新增 `tools/debug/poe2_multiframe_localization_probe.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_archive.py`

**先写失败测试：** 归档必须包含原图引用、wall/observed mask、时间、锚点和读次数、位移/质量、关键帧决策、候选分解、参数版本、最终状态；不完整临时目录不得发布。

**实现要求：** 复用现有 sample/archive 的原子目录发布，不让运行时默认写盘；CLI 只接受显式 `--replay` 或 `--save`。回放不需要启动游戏，也不读取内存。

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_archive.py
python tools/debug/poe2_multiframe_localization_probe.py --help
```

预期：探针能打印 A/B 结果、候选和误差；缺样本返回非零状态且说明原因。

**提交：** `feat: archive and replay multiframe localization evidence`

### Task 14: 增加定位到导航的结果适配器

**文件：**

- 新增 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/navigation_adapter.py`
- 新增 `tests/poe2_live_terrain/test_multiframe_navigation_adapter.py`

**先写失败测试：** confirmed/fresh/instance 一致时生成只读导航定位结果；ambiguous、lost、过期、版本不符时不生成可执行定位；路径安全半径使用 `r_player + k*sqrt(lambda_max(P)) + r_map_error`。

**接口起点：**

```python
def to_navigation_observation(estimate: PositionEstimate, *, now_ms: int) -> NavigationObservation:
    executable = (
        estimate.status == "confirmed"
        and estimate.fresh
        and estimate.age_ms <= self.max_age_ms
        and bool(estimate.instance_id)
    )
    return NavigationObservation(
        position=estimate.position,
        velocity=estimate.velocity,
        covariance=readonly_covariance(estimate.covariance),
        executable=executable,
        reason=None if executable else estimate.reason or "localization_not_ready",
    )
```

**验证：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_navigation_adapter.py tests/test_localization_result.py
```

预期：适配器只产出领域中立 observation，不调用路径执行、设备或网络。

**提交：** `feat: expose gated localization observations to navigation`

### Task 15: 回归验证、性能门和文档同步

**文件：**

- 修改 `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- 修改 `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`
- 修改 `CODEBASE.md`
- 修改 `ITERATION_LOG.md`
- 新增 `tests/poe2_live_terrain/test_multiframe_end_to_end.py`

**先写失败测试：** 端到端合成回放覆盖首帧稀疏、移动后结构增加、方向歧义、静止、丢帧、恢复、换地图和旧版本结果返回；断言位置/方向/状态，而不是内部调用次数。

**验证命令：**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_*.py tests/test_displacement.py tests/test_frame_displacement.py
python -m compileall src/auto_modules
git diff --check
```

**验收指标：** 首帧/恢复确认率、错误确认率、native 位置误差 P50/P95、墙体投影误差、确认耗时/行走距离、峰值内存、恢复内存读取次数、静止期间关键帧/注册增长量。参数调优集与留出验证集分离。

**文档同步要求：** 每次源代码改动先在 `ITERATION_LOG.md` 声明范围，再更新 `CODEBASE.md` 的受影响函数/数据流/风险。未完成真实游戏验收时，断点文档必须明确写“样本/合成测试通过，实机未验证”。

**提交：** `test: verify multiframe localization end to end`

## 依赖顺序与并行边界

必须按 `1 -> 2 -> 3 -> 4 -> 5 -> (6,7) -> 8 -> 9 -> 10 -> (11,12) -> 13 -> 14 -> 15` 推进。

Task 6 与 Task 7 在 Task 5 后可以分别实现，但都必须使用同一 `EvidenceWindow` 和 `ShapeScore`。Task 11 只能在 Task 10 发布稳定快照后开始；Task 12 不能先于实验层契约测试。Task 14 只能在 `PositionEstimate` 状态和版本门固定后开始。

## 预计不改动的正式链路

首轮计划不改：第一页绘图模式、正式 PoE2 产品定位 factory、Xbox/键鼠/虚拟手柄、Host/LAN、导航自动移动执行。正式链路只在 P6 评审后通过一个领域中立的 `NavigationObservation` 适配器接入。

## 完成定义

- A/B 可以用同一批样本独立运行并输出位置、候选范围、方向、置信度和拒绝原因。
- 静止不积累证据，窗口、tile、候选和任务队列有界。
- 首帧和恢复都能证明人物点、墙体投影、方向和比例一致；不足时保持 ambiguous/collecting。
- 正常移动使用位移预测，周期性局部纠偏，持续失败才单次恢复。
- 导航只消费 fresh、confirmed、实例一致的结果；定位丢失时暂停路线相关执行。
- 合成回放、已有样本回放和 focused pytest 通过；实机结果单独记录，不能用单元测试代替。
