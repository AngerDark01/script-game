# PoE2 混合实时定位实施计划

## Goal

在 PoE2 实验页实现“首次/丢失时单次内存锚点绝对注册，正常期间纯视觉局部跟踪”的实时人物定位闭环，并保证恢复失败后不会每帧继续读取内存。

## Architecture Overview

新增实验包 `features/poe2/live_terrain/experimental/hybrid_localization/`。领域中立的模型、协议、controller 和 recovery gate 先在该实验包验证；PoE2 memory/terrain/profile 只出现在适配器和 composition。首帧与丢失恢复共用 `AnchoredAbsoluteRegistrar`；正常帧由 `VisualLocalTracker` 固定已确认方向、镜像和比例，只搜索有界平移。CLI 改为依赖实验算法，实验运行代码不得反向 import `tools/debug`。

## Tech Stack

- Python 3.11
- NumPy、OpenCV 4.13
- PySide6
- pytest
- 现有 `LocalizationResult`、`TrajectoryBuffer`、`TerrainOrientation`、`TerrainReference`

## Safety And Scope

- 不启动真实输入、Xbox、Host 或 LAN。
- 不修改第一页绘图模式。
- 每个 recovery revision 最多读取一次内存。
- 所有实现先进入 PoE2 实验边界；通过多地图验收前不下沉正式 runtime。
- 工作区已有大量未提交修改，每次提交只能暂存本任务明确列出的文件。

### Task 1: 建立实验包和不可变模型

Files:

- Create: `src/auto_modules/features/poe2/live_terrain/experimental/__init__.py`
- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/__init__.py`
- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/models.py`
- Test: `tests/poe2_live_terrain/test_hybrid_localization_models.py`

Step 1 — 写失败测试：

```python
from dataclasses import FrozenInstanceError
import pytest

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridLocalizationMode,
    PositionAnchor,
    SimilarityTransform2D,
)


def test_anchor_and_transform_are_finite_immutable_values():
    anchor = PositionAnchor((12.5, 20.0), "Map:A1", 1000, "memory")
    transform = SimilarityTransform2D(219.0, True, 0.85, (4.0, 8.0))
    assert anchor.position == (12.5, 20.0)
    assert transform.scale == 0.85
    assert HybridLocalizationMode.NEED_ABSOLUTE.value == "need_absolute"
    with pytest.raises(FrozenInstanceError):
        anchor.source = "other"


@pytest.mark.parametrize("position", [(float("nan"), 1.0), (1.0, float("inf"))])
def test_anchor_rejects_non_finite_position(position):
    with pytest.raises(ValueError, match="finite"):
        PositionAnchor(position, "Map:A1", 1000, "memory")
```

Step 2 — 验证失败：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_hybrid_localization_models.py
# Expected: collection error, module does not exist
```

Step 3 — 实现最小模型：

```python
class HybridLocalizationMode(StrEnum):
    NEED_ABSOLUTE = "need_absolute"
    LOCAL_TRACKING = "local_tracking"
    RECOVERY_PENDING = "recovery_pending"
    RECOVERY_REQUIRED = "recovery_required"
    STOPPED = "stopped"


@dataclass(frozen=True)
class PositionAnchor:
    position: tuple[float, float]
    area_instance: str
    captured_at_ms: int
    source: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if len(self.position) != 2 or not all(math.isfinite(float(v)) for v in self.position):
            raise ValueError("anchor position must contain two finite values")
        if not self.area_instance:
            raise ValueError("area_instance is required")


@dataclass(frozen=True)
class SimilarityTransform2D:
    angle_degrees: float
    reflect_horizontal: bool
    scale: float
    translation: tuple[float, float]

    def __post_init__(self) -> None:
        values = (self.angle_degrees, self.scale, *self.translation)
        if not all(math.isfinite(float(v)) for v in values) or self.scale <= 0:
            raise ValueError("transform values must be finite and scale must be positive")
```

同时定义 `HybridFrame`、`AbsoluteRegistration` 和 `HybridLocalizationState`，字段严格按设计文档 §6，不添加路线或输入字段。

Step 4 — 验证通过：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_hybrid_localization_models.py
# Expected: 3 passed
```

Step 5 — Commit:

```powershell
git add src/auto_modules/features/poe2/live_terrain/experimental tests/poe2_live_terrain/test_hybrid_localization_models.py
git commit -m "feat: add hybrid localization experiment models"
```

### Task 2: 定义可替换的锚点、绝对注册和局部跟踪协议

Files:

- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/contracts.py`
- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/__init__.py`
- Test: `tests/poe2_live_terrain/test_hybrid_localization_contracts.py`

Step 1 — 写失败测试，使用最小 fake 验证 `runtime_checkable`：

```python
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.contracts import (
    AbsoluteRegistrar,
    AnchorProvider,
    LocalTracker,
)


class AnchorFake:
    def read_once(self, expected_instance_id):
        return None


def test_contracts_accept_structural_implementations():
    assert isinstance(AnchorFake(), AnchorProvider)
```

Step 2 — 验证失败，然后实现：

```python
@runtime_checkable
class AnchorProvider(Protocol):
    def read_once(self, expected_instance_id: str) -> PositionAnchor: ...


@runtime_checkable
class AbsoluteRegistrar(Protocol):
    def register(self, frame, *, reference, anchor, prior=None) -> AbsoluteRegistration | None: ...


@runtime_checkable
class LocalTracker(Protocol):
    def track(self, frame, *, reference, previous_frame, previous) -> AbsoluteRegistration | None: ...
```

Step 3 — Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_hybrid_localization_contracts.py
# Expected: 1 passed
```

Step 4 — Commit: `feat: define hybrid localization contracts`

### Task 3: 实现一次性恢复许可

Files:

- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/recovery.py`
- Test: `tests/poe2_live_terrain/test_hybrid_recovery_policy.py`

Step 1 — 写失败测试：

```python
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.recovery import OneShotRecoveryPolicy


def test_each_revision_can_be_consumed_once():
    policy = OneShotRecoveryPolicy()
    assert policy.begin() == 1
    assert policy.consume(1) is True
    assert policy.consume(1) is False
    assert policy.begin() == 2
    assert policy.consume(2) is True
```

Step 2 — 实现：

```python
class OneShotRecoveryPolicy:
    def __init__(self) -> None:
        self._revision = 0
        self._consumed: set[int] = set()

    @property
    def revision(self) -> int:
        return self._revision

    def begin(self) -> int:
        self._revision += 1
        return self._revision

    def consume(self, revision: int) -> bool:
        if revision != self._revision or revision in self._consumed:
            return False
        self._consumed.add(revision)
        return True
```

Step 3 — Verify: `pytest -q tests/poe2_live_terrain/test_hybrid_recovery_policy.py` → `1 passed`。

Step 4 — Commit: `feat: add one-shot localization recovery policy`

### Task 4: 控制器首次定位只读取一次锚点

Files:

- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`
- Test: `tests/poe2_live_terrain/test_hybrid_localization_controller.py`

Step 1 — 写 fake provider/registrar，断言首次成功后进入 local tracking 且 `reads == 1`。

```python
def test_first_update_reads_one_anchor_and_accepts_absolute(frame, reference, registration):
    provider = AnchorFake(registration.area_instance)
    registrar = AbsoluteRegistrarFake(registration)
    controller = HybridLocalizationController(
        expected_instance_id=registration.area_instance,
        reference=reference,
        anchor_provider=provider,
        absolute_registrar=registrar,
        local_tracker=LocalTrackerFake(),
    )
    state = controller.update(frame)
    assert state.mode is HybridLocalizationMode.LOCAL_TRACKING
    assert state.position == registration.result.position
    assert provider.reads == 1
```

Step 2 — 实现 `start()/update()` 的 absolute 分支：

```python
def _attempt_absolute(self, frame):
    revision = self._recovery.revision
    if not self._recovery.consume(revision):
        return self._state(position=None, reason="recovery_already_consumed")
    anchor = self._anchor_provider.read_once(self.expected_instance_id)
    result = self._absolute_registrar.register(
        frame,
        reference=self.reference,
        anchor=anchor,
        prior=self._last_confirmed,
    )
    if result is None:
        self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
        return self._state(position=None, reason="absolute_registration_failed")
    return self._accept(frame, result)
```

`__init__()` 必须调用 `recovery.begin()` 创建首次 revision；所有依赖只通过协议注入。

Step 3 — Verify: focused test → pass。

Step 4 — Commit: `feat: add first-frame hybrid localization control`

### Task 5: 控制器处理局部成功、局部失败和无陈旧轨迹

Files:

- Modify: `controller.py`
- Test: `test_hybrid_localization_controller.py`

Step 1 — 新增失败测试：首帧成功、第二帧 local 成功、第三帧 local 返回 `None`；断言第三帧 `position is None`、mode 为 `RECOVERY_PENDING`、trajectory 长度不增加、anchor reads 仍为 1。

Step 2 — 实现：

```python
def _track_local(self, frame):
    result = self._local_tracker.track(
        frame,
        reference=self.reference,
        previous_frame=self._previous_frame,
        previous=self._last_confirmed,
    )
    if result is None:
        self.mode = HybridLocalizationMode.RECOVERY_PENDING
        self._recovery.begin()
        return self._state(position=None, reason="local_tracking_failed")
    return self._accept(frame, result)
```

`_accept()` 只在成功结果上更新 previous frame、last confirmed 和 trajectory。

Step 3 — Verify: `pytest -q tests/poe2_live_terrain/test_hybrid_localization_controller.py`。

Step 4 — Commit: `feat: transition hybrid localization into recovery`

### Task 6: 恢复失败后禁止自动重读，显式 retry 才开启新 revision

Files:

- Modify: `controller.py`
- Test: `test_hybrid_localization_controller.py`

Step 1 — 测试序列：local fail → recovery attempt fail → 连续三个 update；断言 reads 只增加一次。调用 `retry_recovery()` 后下一帧允许再增加一次。

Step 2 — 实现：

```python
def retry_recovery(self) -> None:
    if self.mode is not HybridLocalizationMode.RECOVERY_REQUIRED:
        raise RuntimeError("recovery retry is only valid after a failed attempt")
    self._recovery.begin()
    self.mode = HybridLocalizationMode.RECOVERY_PENDING

def update(self, frame):
    if self.mode is HybridLocalizationMode.RECOVERY_REQUIRED:
        return self._state(position=None, reason="recovery_required")
    # dispatch remaining modes
```

同时测试 `stop()` 后 provider、registrar、tracker 都不再被调用。

Step 3 — Verify focused test。

Step 4 — Commit: `feat: gate repeated hybrid localization recovery`

### Task 7: 提取无文件系统副作用的相似变换搜索

Files:

- Create: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/similarity_search.py`
- Modify: `tools/debug/poe2_live_terrain_localization_probe.py`
- Modify: `tests/poe2_live_terrain/test_localization_probe.py`
- Create: `tests/poe2_live_terrain/test_hybrid_similarity_search.py`

Step 1 — 把现有合成旋转/镜像/比例恢复测试复制到新测试，并改为从实验模块导入。

Step 2 — 运行测试确认 import 失败。

Step 3 — 从 debug probe 原样迁移以下纯算法，不改变数值逻辑：

```text
SimilaritySearchConfig (由 ProbeConfig 重命名)
SearchCandidate
transform_feature
terrain_edges
terrain_walkable_mask
local_walkable_region
clean_feature_mask
search_candidates
```

CLI 文件只保留样本读取、参数转换、诊断图片和 `main()`，并提供兼容 re-export：

```python
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    SearchCandidate,
    SimilaritySearchConfig as ProbeConfig,
    clean_feature_mask,
    local_walkable_region,
    search_candidates,
    terrain_edges,
    terrain_walkable_mask,
    transform_feature,
)
```

Step 4 — Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q `
  tests/poe2_live_terrain/test_hybrid_similarity_search.py `
  tests/poe2_live_terrain/test_localization_probe.py
# Expected: all pass with unchanged numeric assertions
```

Step 5 — Commit: `refactor: extract hybrid similarity search experiment`

### Task 8: 将锚点绝对注册从 CLI 拆成可注入组件

Files:

- Create: `absolute_registrar.py`
- Modify: `tools/debug/poe2_anchor_local_registration_probe.py`
- Modify: `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`
- Create: `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py`

Step 1 — 新测试直接构造 `HybridFrame + PositionAnchor + TerrainReference`，验证已知 `45° + flip + 1.2 scale` 返回 `AbsoluteRegistration`。

Step 2 — 提取现有纯算法：crop、prepare、anchor scoring、multi-basin refine 和 status；新增适配器：

```python
class AnchoredAbsoluteRegistrar:
    def __init__(self, config: AnchoredRegistrationConfig | None = None) -> None:
        self.config = config or AnchoredRegistrationConfig()

    def register(self, frame, *, reference, anchor, prior=None):
        search = build_search_space(prior, self.config)
        result = match_anchor_local_arrays(
            terrain=reference.explored_map,
            feature=frame.wall_mask,
            local_player=frame.local_player,
            anchor=anchor.position,
            search=search,
        )
        return absolute_registration_from_probe(result, anchor, prior)
```

Step 3 — prior 测试：传入已确认 transform 后，registrar 的搜索配置只包含该 reflection、固定 angle/scale 细化范围；不得重新枚举完整 16 个方向 basin。

Step 4 — CLI 改为调用新组件，旧 `anchor-local-v2` 样本结果仍为 `219°/flip/0.85`、误差约 `7.10`。

Step 5 — Commit: `refactor: expose anchored absolute registrar`

### Task 9: 实现 PoE2 单次内存锚点适配器

Files:

- Create: `memory_anchor.py`
- Test: `tests/poe2_live_terrain/test_hybrid_memory_anchor.py`

Step 1 — fake `Poe2PlayerPositionSource` 返回 native grid，测试 orientation 后坐标、instance 和 timestamp。

Step 2 — 实现：

```python
class Poe2MemoryAnchorProvider:
    def __init__(self, source, orientation, native_shape, clock_ms):
        self.source = source
        self.orientation = orientation
        self.native_shape = native_shape
        self.clock_ms = clock_ms
        self.read_count = 0

    def read_once(self, expected_instance_id: str) -> PositionAnchor:
        sample = self.source.read_once(expected_instance_id)
        self.read_count += 1
        return PositionAnchor(
            position=self.orientation.transform_point(sample.grid, self.native_shape),
            area_instance=sample.area_instance,
            captured_at_ms=parse_timestamp_ms(sample.captured_at),
            source="poe2_memory",
        )
```

`read_count` 只用于实验诊断；读取失败传播 `PlayerPositionError`，controller 转为失败状态。

Step 3 — Verify focused test。

Step 4 — Commit: `feat: adapt poe2 memory position as recovery anchor`

### Task 10: 实现固定 transform 的视觉局部跟踪器

Files:

- Create: `local_tracker.py`
- Test: `tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py`

Step 1 — 合成两帧测试：第二帧相对第一帧移动已知距离，方向/镜像/比例固定；验证返回位置和 prior transform 的 angle/reflection/scale 完全相同。

Step 2 — 实现组合：

```python
class VisualLocalTracker:
    def __init__(self, matcher, *, search_radius: float = 96.0):
        self.matcher = matcher
        self.search_radius = float(search_radius)

    def track(self, frame, *, reference, previous_frame, previous):
        transformed = transform_feature(
            frame.wall_mask,
            frame.local_player,
            angle=previous.transform.angle_degrees,
            reflect_horizontal=previous.transform.reflect_horizontal,
            scale=previous.transform.scale,
        )
        candidate = self.matcher.match(
            transformed.mask,
            origin=predicted_top_left(previous, previous_frame, frame),
            radius=self.search_radius,
            scale=1.0,
        )
        if not candidate.valid:
            return None
        return registration_from_local_match(candidate, transformed, previous, frame)
```

Step 3 — 增加断言：matcher 失败时返回 `None`，绝不调用全图搜索；候选分差不足返回失败。

Step 4 — Verify focused test。

Step 5 — Commit: `feat: add bounded visual local tracker experiment`

### Task 11: 实现 PoE2 混合定位实验 session

Files:

- Create: `session.py`
- Test: `tests/poe2_live_terrain/test_hybrid_localization_session.py`

Step 1 — 测试一次 tick 只截图一次、只构建一次 evidence，并把同一 `frame_id` 交给 controller。

Step 2 — 实现：

```python
def tick(self, *, now_ms=None):
    stamp = int(self.clock_ms() if now_ms is None else now_ms)
    raw = self.frame_source.capture(self.config_provider())
    evidence = self.evidence_builder.build(raw, self.config_provider())
    frame = HybridFrame.from_evidence(evidence, captured_at_ms=stamp)
    state = self.controller.update(frame)
    self._publish(state)
    return state
```

增加 `start/stop/retry_recovery/reset`；QTimer 仍由 UI 拥有。session 不导入 PySide6。

Step 3 — 测试 listener、stop 后无 tick、失败不发布陈旧位置。

Step 4 — Commit: `feat: add poe2 hybrid localization experiment session`

### Task 12: 增加 composition factory 并证明无输入依赖

Files:

- Create: `composition.py`
- Modify: `src/auto_modules/ui/modes/poe2/composition.py`
- Modify: `tests/test_poe2_composition.py`

Step 1 — 写测试断言 factory 组装 frame source、memory anchor、registrar、tracker、controller、session；依赖图中不存在 gamepad/Host/LAN 类型。

Step 2 — 实现 `build_poe2_hybrid_localization_experiment(...)`，只接收现有 terrain snapshot、monitor config provider、preview capture、recognizer 和 player position source。

Step 3 — Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_composition.py
# Expected: all pass
```

Step 4 — Commit: `feat: compose poe2 hybrid localization experiment`

### Task 13: 在 PoE2 数据采集页接入实验控制与状态

Files:

- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`
- Modify: `tests/test_poe2_capture_test_page.py`
- Modify: `tests/test_poe2_capture_monitor_window.py`

Step 1 — Qt 测试先断言存在：开始混合定位、停止、重新恢复一次；无 terrain 时开始按钮禁用。

Step 2 — 接入 session factory 和独立 QTimer；按钮调用仅限：

```python
self.start_hybrid_button.clicked.connect(self.start_hybrid_localization)
self.stop_hybrid_button.clicked.connect(self.stop_hybrid_localization)
self.retry_hybrid_button.clicked.connect(self.retry_hybrid_recovery)
self.hybrid_timer.timeout.connect(self._tick_hybrid_localization)
```

Step 3 — `handle_hybrid_state()` 更新状态/坐标/置信度/read count/transform 文本，并复用地图 widget overlay 显示成功 marker/trajectory。失败状态保留底图但不画新点。

Step 4 — 关闭窗口时停止 timer/session；不自动保存诊断。

Step 5 — Verify focused Qt tests。

Step 6 — Commit: `feat: add hybrid localization controls to poe2 experiment`

### Task 14: 补齐完整调用链和安全回归

Files:

- Create: `tests/poe2_live_terrain/test_hybrid_localization_integration.py`
- Modify: `tests/test_architecture_boundaries.py`

测试序列：

```text
frame-1 absolute success
frame-2 local success
frame-3 local failure
frame-4 one-shot recovery success
frame-5 local success
```

断言：位置来源依次为 `anchored_absolute/visual_local/failed/anchored_absolute/visual_local`；memory reads 总数为 2；trajectory 只有 4 个成功点。

第二序列恢复失败后继续 10 帧，断言 memory reads 不增加；点击 retry 后只增加 1。

架构测试禁止 experimental/core 导入 UI、virtual gamepad、Host、LAN；禁止 src 导入 `tools.debug`。

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q `
  tests/poe2_live_terrain/test_hybrid_localization_integration.py `
  tests/test_architecture_boundaries.py
# Expected: all pass
```

Commit: `test: cover poe2 hybrid localization lifecycle`

### Task 15: 实机前完整验证与断点同步

Files:

- Modify: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- Modify: `CODEBASE.md`
- Modify: `ITERATION_LOG.md`

Step 1 — 运行完整相关回归：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q `
  tests/poe2_live_terrain `
  tests/test_poe2_capture_test_page.py `
  tests/test_poe2_capture_monitor_window.py `
  tests/test_poe2_live_terrain_presenter.py `
  tests/test_poe2_live_terrain_presenter_position.py `
  tests/test_poe2_composition.py `
  tests/test_main_window_poe2_terrain_page.py `
  tests/test_architecture_boundaries.py
# Expected: all pass
```

Step 2 — 语法和差异检查：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m compileall -q `
  src/auto_modules/features/poe2/live_terrain/experimental `
  src/auto_modules/ui/modes/poe2_live_terrain `
  tools/debug
git diff --check
# Expected: exit code 0; only existing CRLF warnings are allowed
```

Step 3 — CODEBASE SYNC 必须记录：新增文件逐个职责、所有非平凡函数算法、F-POE2-HYBRID-LOCALIZATION 每一跳、状态/数据契约和内存重复读取风险。

Step 4 — 更新断点：说明尚未实机验证，不得写成正式可用；给出下一次游戏内验收步骤和需要观察的日志字段。

Step 5 — Commit: `docs: record poe2 hybrid localization experiment state`

## Execution Order

严格按 Task 1 → 15 执行。Task 7/8 完成前不得让运行时 import CLI；Task 12 前不得接 UI；Task 14 前不得进行实机测试。每个任务先看到预期失败，再写最小实现，并只提交该任务列出的文件。

