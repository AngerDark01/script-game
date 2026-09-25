# PoE2 自动方向与多帧定位链路补全实施计划

## Goal

移除所有用户手工地图方向所有权，并补齐自动全局注册、连续跟踪纠偏、有界证据、加权局部图和离线重放，使 PoE2 地图、人物和轨迹始终使用同一算法注册版本。

## Architecture Overview

- 所有定位数据在 native `N` 坐标交换；监控和局部拼图位于 `L`；显示 `D` 仅由 presentation adapter 派生。
- `SimilarityTransform2D` 是 `L -> N` 的唯一方向、镜像、尺度和平移事实源。
- 首次定位与丢失恢复共享 A/B 全局注册；正常跟踪使用 F2F 预测并周期性执行局部形状纠偏。
- `EvidenceWindow`、`RollingSubmap`、候选和异步任务均有硬预算；旧手工方向配置和旧归档不兼容。
- 所有实现先保留在 PoE2 实验目录；只有已经存在且领域中立的能力继续复用 `core`。

## Tech Stack

- Python 3.11+
- NumPy、OpenCV
- PySide6
- pytest
- 现有 `auto_modules.core.localization`、PoE2 terrain reference、hybrid localization 和 multiframe experiment

## Safety And Working Tree

- 不发送 Xbox、键盘、鼠标、虚拟手柄、Host 或 LAN 输入。
- 当前工作区已有大量用户改动；每个任务只暂存本任务精确路径。无法隔离提交时，在 `ITERATION_LOG.md` 写 checkpoint，不混入无关文件。
- 每个代码任务先写失败测试，确认失败原因正确，再实现最小变更并运行聚焦回归。

### Task 1: 从配置契约彻底移除手工方向

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/monitor_config.py`
- Modify: `tests/poe2_live_terrain/test_monitor_config_profiles.py`
- Modify: `tests/poe2_live_terrain/test_profile_store.py`

**Failing test**

```python
def test_legacy_manual_orientation_is_ignored_and_not_reserialized():
    config = Poe2MonitorConfig.from_dict({
        "map_rotation": 90,
        "map_flip_horizontal": True,
        "map_flip_vertical": True,
    })
    assert not hasattr(config, "map_rotation")
    assert "map_rotation" not in config.as_dict()
    assert "map_flip_horizontal" not in config.as_dict()
    assert "map_flip_vertical" not in config.as_dict()
```

**Implementation**

Remove the three dataclass fields, their validation and serialization. `from_dict()` intentionally does not read them:

```python
return cls(
    binding=_binding_from_dict(data.get("binding")),
    search_radius=data.get("search_radius", 96),
    match_threshold=data.get("match_threshold", 0.72),
    sample_interval_ms=data.get("sample_interval_ms", 100),
    profile_id=data.get("profile_id", "default"),
    profile_name=data.get("profile_name", "默认配置"),
    selection_mode=data.get("selection_mode", "region"),
    capture_size=data.get("capture_size", 320),
    shape=data.get("shape", CaptureShape.SQUARE.value),
    circle_radius=data.get("circle_radius"),
    recognizer_params=data.get("recognizer_params", {}),
    stitcher_params=data.get("stitcher_params", _default_stitcher_params()),
)
```

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_monitor_config_profiles.py tests/poe2_live_terrain/test_profile_store.py
# Expected: new test fails before implementation, then all pass.
```

**Checkpoint:** `refactor: remove manual orientation from poe2 profiles`

### Task 2: 删除配置面板和对话框中的旋转/镜像控件

**Files**

- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/config_panel.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/monitor_dialog.py`
- Modify: `tests/poe2_live_terrain/test_config_panel.py`
- Modify: `tests/test_poe2_monitor_dialog.py`

**Failing test**

```python
def test_monitor_editor_has_no_manual_orientation_controls(qtbot):
    panel = Poe2MonitorConfigPanel(Poe2MonitorConfig())
    qtbot.addWidget(panel)
    assert not hasattr(panel, "map_rotation_combo")
    assert not hasattr(panel, "map_flip_horizontal_check")
    assert not hasattr(panel, "map_flip_vertical_check")
```

**Implementation**

Delete the entire “地图方向校准” group, all reads/writes of its widgets, dialog aliases and editable-list entries. `current_config()` and `_apply_selection()` rebuild configs using only monitor, recognition and stitcher fields.

```python
return Poe2MonitorConfig(
    binding=self._config.binding,
    search_radius=self.search_radius_spin.value(),
    match_threshold=self.match_threshold_spin.value(),
    sample_interval_ms=self.sample_interval_spin.value(),
    profile_id=self._config.profile_id,
    profile_name=self._config.profile_name,
    selection_mode=self._config.selection_mode,
    capture_size=self.capture_size_spin.value(),
    shape=CaptureShape.coerce(self.shape_combo.currentData()),
    circle_radius=self.circle_radius_spin.value(),
    recognizer_params=self.recognizer_params(),
    stitcher_params=self.stored_stitcher_params(),
)
```

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_config_panel.py tests/test_poe2_monitor_dialog.py
```

**Checkpoint:** `refactor: remove manual orientation controls`

### Task 3: 将正式 runtime、hybrid composition 和采集链统一为 native

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/runtime.py`
- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`
- Modify: `src/auto_modules/features/poe2/live_terrain/capture_samples.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`
- Modify: `tools/debug/poe2_anchor_local_registration_probe.py`
- Modify: corresponding orientation, runtime, sample and page tests

**Failing tests**

```python
def test_hybrid_composition_keeps_reference_and_anchor_native(...):
    experiment = build_poe2_hybrid_localization_experiment(...)
    assert experiment.reference.shape == snapshot.walkable.shape
    assert experiment.anchor_provider.orientation.is_identity

def test_capture_manifest_is_native_and_has_no_manual_orientation(...):
    record = archive.save(...)
    assert record.manifest["coordinate_space"] == "native"
    assert "orientation" not in record.manifest
```

**Implementation**

Use identity orientation only at the memory API boundary and never transform the reference from profile data:

```python
reference = build_reference(snapshot)
anchor_provider = Poe2MemoryAnchorProvider(
    player_position_source,
    TerrainOrientation(),
    (snapshot.metadata.height, snapshot.metadata.width),
    clock_ms=clock_ms,
)
```

`Poe2LocalizationRuntime.configure_monitor()` updates capture/recognizer settings only. Page and capture previews render native until an algorithm registration is published. New sample manifests write:

```python
manifest["coordinate_space"] = "native"
manifest.pop("orientation", None)
```

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_hybrid_memory_anchor.py tests/poe2_live_terrain/test_hybrid_localization_integration.py tests/poe2_live_terrain/test_capture_samples.py tests/test_poe2_live_terrain_page.py tests/test_poe2_capture_test_page.py tests/test_poe2_capture_monitor_window.py
rg -n "map_rotation|map_flip_horizontal|map_flip_vertical" src tests tools
# Expected: no runtime/config/UI occurrence remains; only an explicit migration-rejection fixture may remain.
```

**Checkpoint:** `refactor: make poe2 localization coordinates native`

### Task 4: 为证据窗口增加距离和字节硬预算

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/evidence_window.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_evidence_window.py`

**Failing test**

```python
def test_window_trims_oldest_frame_for_distance_and_byte_budgets():
    window = EvidenceWindow(
        max_keyframes=8,
        max_window_ms=60_000,
        max_travel_distance=10.0,
        max_bytes=900,
    )
    assert window.append(item(1, offset=(0, 0), bytes_per_mask=200))
    assert window.append(item(2, offset=(8, 0), bytes_per_mask=200))
    assert window.append(item(3, offset=(16, 0), bytes_per_mask=200))
    assert window.travel_distance <= 10.0
    assert window.estimated_bytes <= 900
    assert window.snapshot()[-1].frame.frame_id == 3
```

**Implementation**

```python
def _evidence_bytes(item: MultiFrameEvidence) -> int:
    arrays = (item.frame.wall_mask, item.observed_mask, item.raw_frame)
    return sum(int(value.nbytes) for value in arrays if value is not None)

def _trim(self) -> None:
    self._trim_by_time()
    while len(self._frames) > 1 and (
        self._travel_distance() > self.max_travel_distance
        or self.estimated_bytes > self.max_bytes
    ):
        self._frames.popleft()
```

Expose read-only `travel_distance` and `estimated_bytes` diagnostics. Do not use `deque(maxlen=...)`; trim explicitly so every eviction is observable and testable.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_evidence_window.py
```

**Checkpoint:** `feat: bound multiframe evidence by distance and memory`

### Task 5: 将滚动子图改为可逆加权融合

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/rolling_submap.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_rolling_submap.py`

**Failing test**

```python
def test_weighted_submap_removes_evicted_noise_and_preserves_unknown():
    snapshot = RollingSubmap(max_width=64, max_height=64).rebuild((good, noisy))
    assert snapshot.wall_weight.dtype == np.float32
    assert snapshot.observed_weight.dtype == np.float32
    rebuilt = RollingSubmap(max_width=64, max_height=64).rebuild((good,))
    assert rebuilt.wall_mask[noise_y, noise_x] == 0
    assert rebuilt.observed_mask[unknown_y, unknown_x] == 0
```

**Implementation**

`SubmapSnapshot` adds immutable `wall_weight`, `observed_weight` and `last_frame_id`. Rebuild retained frames from zero:

```python
quality = max(0.0, min(1.0, float(item.motion.quality)))
contribution = min(self.max_frame_weight, max(self.min_frame_weight, quality))
visible = visible_src > 0
observed_weight[region][visible] += contribution
wall_weight[region][visible] += contribution * (src[visible] > 0)
last_frame_id[region][visible] = item.frame.frame_id
wall = np.where(
    observed_weight >= self.min_support_weight,
    wall_weight / np.maximum(observed_weight, 1e-6) >= self.wall_probability_threshold,
    False,
).astype(np.uint8) * 255
observed = (observed_weight > 0).astype(np.uint8) * 255
```

All accumulation uses clipped slices without chained-index copies. Rebuilding after eviction or pose correction is mandatory.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_rolling_submap.py tests/poe2_live_terrain/test_multiframe_strategy_a.py
```

**Checkpoint:** `feat: rebuild weighted rolling wall submap`

### Task 6: 完成稳健形状评分和 ROI 缓存

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/shape_registration.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_shape_registration.py`

**Failing tests**

```python
def test_huber_and_trim_limit_resist_coarse_blob_without_hiding_low_coverage(): ...
def test_tangent_consistency_rejects_nearby_parallel_wrong_wall(): ...
def test_reverse_error_uses_only_transformed_observed_support(): ...
def test_reference_roi_cache_reuses_distance_field_for_same_bounds(): ...
```

**Implementation**

```python
def huber(values: np.ndarray, delta: float) -> np.ndarray:
    absolute = np.abs(values)
    return np.where(
        absolute <= delta,
        0.5 * values * values,
        delta * (absolute - 0.5 * delta),
    )

def robust_mean(distances, *, sigma, delta, trim_fraction):
    scaled = np.asarray(distances, dtype=np.float64) / max(float(sigma), 1e-6)
    keep = max(1, int(np.ceil(scaled.size * (1.0 - trim_fraction))))
    retained = np.partition(scaled, keep - 1)[:keep]
    return float(np.mean(huber(retained, float(delta))))
```

`ShapeScore` adds untrimmed coverage, tangent error and component diagnostics. Cache keys contain reference identity/version and exact ROI bounds; cache storage is bounded LRU.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_shape_registration.py
```

**Checkpoint:** `feat: score wall shapes with robust geometry`

### Task 7: 为方案 B 增加粗到细方向、尺度和平移精化

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_b.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_strategy_b.py`

**Failing test**

```python
def test_strategy_b_refines_non_45_degree_rotation():
    result = strategy.update(frames_for(angle=31.0), anchor=anchor, reference_boundary=reference)
    assert abs(angle_delta(result.best.transform.angle_degrees, 31.0)) <= 1.5
    assert result.best.refinement_level == "fine"
```

**Implementation**

Add immutable search levels and local expansion:

```python
@dataclass(frozen=True)
class SearchLevel:
    angle_step: float
    angle_radius: float
    scale_step: float
    scale_radius: float
    translation_step: float
    translation_radius: float

DEFAULT_LEVELS = (
    SearchLevel(15.0, 22.5, 0.10, 0.20, 4.0, 8.0),
    SearchLevel(5.0, 7.5, 0.03, 0.06, 2.0, 4.0),
    SearchLevel(1.0, 2.0, 0.01, 0.02, 1.0, 2.0),
)
```

At each level expand only the best distinct basins, score all training frames, deduplicate, and retain `max_candidates`. Candidate diagnostics record level, component errors and ROI.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_strategy_b.py
```

**Checkpoint:** `feat: refine automatic orientation candidates`

### Task 8: 完成 A/B 汇合、锚点误差和轨迹验证门

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_a.py`
- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_b.py`
- Add: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/registration_validator.py`
- Add: `tests/poe2_live_terrain/test_multiframe_registration_validator.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_strategy_a.py`

**Failing test**

```python
def test_validator_rejects_shape_match_with_wrong_anchor_or_trajectory():
    decision = validator.validate(candidate, anchor=anchor, frames=frames, holdout=holdout)
    assert decision.confirmed is False
    assert decision.reason in {"anchor_uncertainty", "trajectory_error", "holdout_error"}
```

**Implementation**

```python
@dataclass(frozen=True)
class RegistrationDecision:
    confirmed: bool
    reason: str
    candidate: AbsoluteRegistration | None
    diagnostics: Mapping[str, float]
```

The validator checks anchor Mahalanobis distance, holdout shape, transformed trajectory residual, scale prior, real-mode margin and A/B compatibility. A/B remain correlated; select the better validated measurement and treat the other only as consistency evidence.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_registration_validator.py tests/poe2_live_terrain/test_multiframe_strategy_a.py tests/poe2_live_terrain/test_multiframe_strategy_b.py
```

**Checkpoint:** `feat: validate multiframe registration jointly`

### Task 9: 实现有界局部形状纠偏器

**Files**

- Add: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/local_corrector.py`
- Add: `tests/poe2_live_terrain/test_multiframe_local_corrector.py`

**Failing test**

```python
def test_local_corrector_recovers_small_drift_without_global_search():
    result = corrector.correct(
        frame=frame,
        predicted_position=(104.0, 98.0),
        registration=registration,
        reference=reference,
    )
    assert result.accepted
    assert np.allclose(result.position, (100.0, 100.0), atol=1.5)
    assert result.search_bounds.width <= 2 * corrector.translation_radius + 1
```

**Implementation**

```python
@dataclass(frozen=True)
class LocalCorrection:
    accepted: bool
    position: tuple[float, float] | None
    transform: SimilarityTransform2D | None
    covariance: np.ndarray | None
    score: ShapeScore | None
    reason: str
    diagnostics: Mapping[str, object]
```

Search only around the predicted translation and current angle/scale. Return a measurement covariance derived from residual, coverage and best/second margin. Never read memory and never fall back to whole-map search.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_local_corrector.py
```

**Checkpoint:** `feat: add bounded local shape correction`

### Task 10: 在 coordinator 中接入周期纠偏和完整恢复门

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/coordinator.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_coordinator.py`

**Failing tests**

```python
def test_tracking_corrects_drift_even_when_f2f_keeps_succeeding(): ...
def test_single_local_correction_failure_only_degrades(): ...
def test_repeated_motion_or_correction_failure_starts_one_recovery_revision(): ...
def test_registration_switch_updates_map_player_and_track_version_atomically(): ...
```

**Implementation**

Add `LocalCorrectionPolicy` with distance, elapsed-time, covariance and reprojection thresholds. `_run_tracking()` performs F2F prediction first, then conditionally invokes the corrector:

```python
prediction = self._predict_registered_shift(...)
if self.correction_policy.should_correct(self._tracking_metrics(evidence)):
    correction = self.local_corrector.correct(...)
    if correction.accepted:
        update = self.estimator.observe(
            correction.position,
            covariance=correction.covariance,
            now_ms=evidence.frame.captured_at_ms,
        )
        return self._publish_corrected(update, correction)
    self._correction_failures += 1
return prediction
```

Only thresholded repeated failures call `begin_recovery()`. Recovery clears stale motion and registration, increments revision once and waits for the session's one-shot anchor.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_coordinator.py
```

**Checkpoint:** `feat: correct drift and gate multiframe recovery`

### Task 11: 按观测质量校准状态估计噪声

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/state_estimator.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_state_estimator.py`

**Failing test**

```python
def test_covariance_grows_with_elapsed_time_and_low_motion_quality(): ...
def test_shape_measurement_noise_reflects_residual_and_candidate_margin(): ...
```

**Implementation**

```python
process_variance = (
    self.base_process_variance * max(dt_seconds, 1e-3)
    + self.low_quality_variance * (1.0 - clipped_quality)
    + float(registration_variance)
)
self._covariance += np.eye(2) * process_variance
```

`observe()` accepts the local corrector's covariance. Preserve the Mahalanobis gate and Joseph covariance update. Diagnostics report the actual process and measurement variance used.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_state_estimator.py tests/poe2_live_terrain/test_multiframe_coordinator.py
```

**Checkpoint:** `feat: calibrate localization covariance from evidence`

### Task 12: 固化 session 的单任务、单锚点和版本栅栏

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_session.py`

**Failing tests**

```python
def test_each_recovery_revision_reads_memory_at_most_once(): ...
def test_only_one_registration_future_exists_and_queue_is_bounded(): ...
def test_stop_reset_and_new_revision_discard_old_publication(): ...
```

**Implementation**

Capture a generation token at schedule time and validate it before publication:

```python
token = request.token
self._registration_future = self._executor.submit(self._evaluate_timed, request)
self._registration_token = token

if self._registration_token != outcome.request.token:
    return
self.last_estimate = self.coordinator.apply_registration_outcome(outcome)
```

`stop()` and `reset()` increment a session generation and clear pending publication. The executor remains one worker; no unbounded queue is introduced.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_session.py
```

**Checkpoint:** `fix: fence stale localization publications`

### Task 13: 用算法注册驱动唯一显示变换

**Files**

- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- Modify: `src/auto_modules/ui/modes/poe2_live_terrain/multiframe_panel.py`
- Modify: `src/auto_modules/ui/widgets/scalable_map.py`
- Modify: `tests/test_poe2_live_terrain_presenter_position.py`
- Modify: `tests/test_poe2_capture_test_page_multiframe.py`
- Modify: `tests/test_poe2_multiframe_panel.py`

**Failing tests**

```python
def test_map_player_track_and_candidates_share_registration_version(): ...
def test_unregistered_map_shows_native_waiting_state_without_manual_transform(): ...
def test_new_registration_switches_display_atomically(): ...
```

**Implementation**

Create one immutable presentation snapshot:

```python
@dataclass(frozen=True)
class LocalizationPresentation:
    registration_version: int
    map_pixmap: QPixmap
    player_display_position: tuple[float, float] | None
    trajectory_display: tuple[tuple[float, float], ...]
    candidates_display: tuple[CandidateDisplay, ...]
    orientation_status: str
```

Before confirmation, render native and set `orientation_status="waiting_for_automatic_calibration"`. After confirmation, derive one display transform from the confirmed registration and apply it to every overlay in the same function. Never mutate localization coordinates for display.

**Verify**

```powershell
pytest -q tests/test_poe2_live_terrain_presenter_position.py tests/test_poe2_capture_test_page_multiframe.py tests/test_poe2_multiframe_panel.py tests/test_scalable_map_widget.py
```

**Checkpoint:** `feat: render automatic localization orientation atomically`

### Task 14: 升级 native 归档 schema 并实现证据加载器

**Files**

- Modify: `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/archive.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_archive.py`

**Failing tests**

```python
def test_archive_round_trip_reconstructs_multiframe_evidence(): ...
def test_archive_records_native_coordinate_and_registration_diagnostics(): ...
def test_old_manual_orientation_archive_is_rejected(): ...
```

**Implementation**

Use schema 3:

```python
SCHEMA_VERSION = 3
COORDINATE_SPACE = "native"

@dataclass(frozen=True)
class MultiframeReplayBundle:
    evidence: tuple[MultiFrameEvidence, ...]
    anchor: PositionAnchor
    instance_id: str
    diagnostics: Mapping[str, object]

def load(self, directory: str | Path) -> MultiframeReplayBundle:
    manifest = json.loads((Path(directory) / "manifest.json").read_text("utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported multiframe archive schema")
    if manifest.get("coordinate_space") != COORDINATE_SPACE:
        raise ValueError("multiframe archive must use native coordinates")
    # Rebuild HybridFrame, FrameDisplacement and MultiFrameEvidence from NPZ keys.
```

The manifest records anchor, recovery/evidence/registration versions, A/B component scores, refinement steps and rejection reasons. Publication remains atomic.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_archive.py
```

**Checkpoint:** `feat: load native multiframe replay bundles`

### Task 15: 让离线探针真正重跑 A/B 和跟踪链

**Files**

- Modify: `tools/debug/poe2_multiframe_localization_probe.py`
- Add: `tests/poe2_live_terrain/test_multiframe_replay_probe.py`

**Failing test**

```python
def test_probe_replays_evidence_and_reports_candidate_components(tmp_path):
    result = run_probe(tmp_path / "archive", strategy="both")
    assert result["strategy_a"]["status"]
    assert result["strategy_b"]["candidates"]
    assert result["final_estimate"]["registration_version"] >= 1
```

**Implementation**

Expose a testable function and keep CLI thin:

```python
def replay_archive(path: Path, *, strategy: str = "both") -> dict[str, object]:
    bundle = MultiframeArchive().load(path)
    experiment = build_replay_experiment(bundle, strategy=strategy)
    estimates = [experiment.ingest(item) for item in bundle.evidence]
    return replay_report(experiment, estimates)
```

CLI accepts `--strategy a|b|both` and `--json`. It must not initialize the game, memory source or input adapters.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_replay_probe.py
python tools/debug/poe2_multiframe_localization_probe.py --help
```

**Checkpoint:** `feat: replay multiframe localization offline`

### Task 16: 补齐端到端链路和架构边界测试

**Files**

- Modify: `tests/poe2_live_terrain/test_multiframe_end_to_end.py`
- Modify: `tests/poe2_live_terrain/test_multiframe_composition.py`
- Modify: `tests/test_architecture_boundaries.py`

**Failing scenarios**

```python
@pytest.mark.parametrize("angle", [7.0, 31.0, 68.0, 137.0, 223.0, 319.0])
def test_full_chain_registers_tracks_corrects_and_recovers(angle): ...

def test_slow_motion_accumulates_and_does_not_freeze(): ...
def test_wrong_repeated_corridor_stays_ambiguous(): ...
def test_map_change_invalidates_old_worker_and_track(): ...
def test_navigation_observation_fails_closed_during_recovery(): ...
```

Architecture assertions ensure generic modules do not import PoE2/UI and no input/network adapter is reached.

**Verify**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_end_to_end.py tests/poe2_live_terrain/test_multiframe_composition.py tests/test_architecture_boundaries.py
```

**Checkpoint:** `test: verify automatic orientation localization chain`

### Task 17: 完整回归、诊断和断点文档同步

**Files**

- Modify: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- Modify: `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`
- Modify: `CODEBASE.md`
- Modify: `ITERATION_LOG.md`
- Modify: `ARCHITECTURE_ITERATION_LOG.md` if module boundaries change

**Verification**

```powershell
pytest -q tests/poe2_live_terrain/test_multiframe_*.py tests/poe2_live_terrain/test_hybrid_*.py tests/poe2_live_terrain/test_monitor_config_profiles.py tests/poe2_live_terrain/test_capture_samples.py tests/test_poe2_*.py tests/test_scalable_map_widget.py tests/test_architecture_boundaries.py
python -m compileall src/auto_modules tools/debug/poe2_multiframe_localization_probe.py
python tools/debug/poe2_multiframe_localization_probe.py --help
git diff --check
rg -n "map_rotation|map_flip_horizontal|map_flip_vertical" src tests tools
```

Expected:

- All selected tests pass.
- Compile and diff checks pass.
- No runtime/config/UI manual-orientation reference remains.
- Serena diagnostics for changed Python files contain no code errors.
- Documentation explicitly says whether only synthetic/history replay passed or real-game acceptance also passed.

**Checkpoint:** `docs: record automatic orientation chain completion`

## Execution Order

Execute strictly in this order:

```text
1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8
  -> 9 -> 10 -> 11 -> 12 -> 13 -> 14 -> 15 -> 16 -> 17
```

Tasks 4-8 stabilize evidence and global registration before tracking is changed. Task 13 cannot start before the coordinator publishes a single versioned transform. Replay work cannot claim success until schema 3 can reconstruct actual evidence. Real-game calibration remains a separate acceptance step after all deterministic tests pass.
