# PoE2 双人共同几何首帧定位实现计划

## Goal

在不影响单人中心定位的前提下，为 PoE2 实验页实现双人首帧定位：使用两个可配置颜色 profile 找到两个小地图角色标记，使用两个只读 native anchor 共同求解旋转、比例和平移，并用双 anchor 与墙体形状共同验证结果。

## Architecture Overview

- 颜色检测只负责从当前小地图帧输出未赋身份的 marker 候选；颜色 profile 是可持久化配置，不进入通用几何层。
- 双人注册器先用两个候选和两个内存 anchor 的相对向量估计 similarity transform，再以双方中点建立平移，最后在小范围角度/比例邻域用墙体形状校准。
- 评分同时约束两个 anchor error、两人相对距离误差、墙体覆盖率和候选置信度；任何一名角色不满足门槛都拒绝。
- 单人注册器、绘图模式和正式实时定位链路保持不变；实验页先提供配置和一次性验证入口。

## Tech Stack

- Python 3.11+
- NumPy、OpenCV
- PySide6 配置面板
- pytest

## Implementation Tasks

### Task 1: Add failing tests for configurable dual-color profiles

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/models.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/marker_candidates.py`
- `tests/poe2_live_terrain/test_multiplayer_first_frame.py`

Add tests that construct two HSV profiles, detect only the configured hue ranges, preserve candidate identity hints, reject invalid ranges, and keep the current default detector behavior when no profiles are supplied.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_multiplayer_first_frame.py -k "color_profile"
```

Expected initial result: the new tests fail because `MarkerColorProfile` and profile-aware detection do not yet exist.

### Task 2: Implement profile-aware marker detection and serialization

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/models.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/marker_candidates.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/__init__.py`

Implement immutable `MarkerColorProfile` with hue intervals, saturation/value gates, area/dimension gates, `to_dict`/`from_dict`, and profile-aware `detect_marker_observation`. Support hue wraparound and return diagnostics identifying the profile that produced each candidate. Keep `detect_saturated_marker_observation` as a backward-compatible default wrapper.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_multiplayer_first_frame.py -k "color_profile"
```

Expected result: all color profile tests pass.

### Task 3: Add failing tests for joint vector/midpoint initialization

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_first_frame.py`
- `tests/poe2_live_terrain/test_multiplayer_first_frame.py`

Add deterministic tests where both marker-to-anchor assignments are valid only under one permutation, where scale is recovered from relative distance, where translation is recovered from the pair midpoint, and where a single-player-fitting transform is rejected when it cannot explain the second anchor.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_multiplayer_first_frame.py -k "joint or midpoint or relative"
```

Expected initial result: the new tests fail because registration currently seeds from only the primary player.

### Task 4: Implement joint similarity initialization and local shape refinement

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_first_frame.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/models.py`

Add a private joint initializer:

```python
scale = norm(native_2 - native_1) / max(norm(screen_2 - screen_1), eps)
angle = atan2(native_delta.y, native_delta.x) - atan2(screen_delta.y, screen_delta.x)
translation = native_mid - similarity(screen_mid, angle, scale)
```

Evaluate both assignments, reject degenerate marker pairs, search only a bounded neighborhood around the vector estimate, and score candidates with:

```text
score = w_anchor * min(anchor_confidence_1, anchor_confidence_2)
      + w_shape * shape_coverage
      + w_pair * pair_distance_consistency
      + w_marker * min(marker_confidence_1, marker_confidence_2)
      - w_error * normalized_mean_anchor_error
```

Persist complete diagnostics: assignment, angle, scale, anchor errors, pair error, shape coverage, confidence, and elapsed time. Preserve the existing result contract and single-player behavior.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_multiplayer_first_frame.py
```

Expected result: all existing and new dual registration tests pass.

### Task 5: Add backward-compatible monitor configuration for two color profiles

Files:

- `src/auto_modules/features/poe2/live_terrain/monitor_config.py`
- `src/auto_modules/features/poe2/live_terrain/config_panel.py`
- relevant config tests under `tests/`

Add optional `dual_marker_profiles` to `Poe2MonitorConfig`, load old files with defaults, validate profile values, and save profiles without changing existing single-player fields. Expose two profile rows in the independent PoE2 configuration dialog: hue range, saturation/value thresholds, enable toggle, and live manual editing of each profile; area and size gates remain validated/persisted backend parameters with conservative defaults. The existing visual color calibration action remains available for the shared recognizer parameters.

Verify:

```powershell
pytest -q tests -k "poe2 and config"
```

Expected result: old configuration fixtures still load and new profile round-trip tests pass.

### Task 6: Wire the experimental page to profiles and joint registrar

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/experiment.py`
- `tests/test_poe2_capture_test_page.py`

Pass the configured profiles into observation detection, keep `exclude_player=False` and `exclude_dynamic=False` for dual mode, read both anchors once, and display both candidate positions, assignment, angle, scale, both errors, shape coverage, confidence, and rejection reason. Do not start a continuous timer or alter the single-player button path.

Verify:

```powershell
pytest -q tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_first_frame.py
```

### Task 7: Reproduce the real sample offline before changing defaults

Files:

- `data/poe2_live_terrain_test/samples/` (read-only inputs)
- `data/poe2_live_terrain_test/probe_results/` (new diagnostics)
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`

Replay at least three saved dual-player samples with the exact production detector and registrar. Record per-sample marker count, selected profiles, assignment, angle, scale, both anchor errors, pair error, shape coverage, confidence, elapsed time, and accept/reject reason. Do not lower thresholds to force acceptance; adjust only after identifying a reproducible parameter error.

Verify:

```powershell
python -m auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.experiment --replay data/poe2_live_terrain_test/samples/<sample>
```

Expected result: at least 3 consecutive samples accepted with pair confidence >= 0.75 and no wrong-permutation acceptance.

### Task 8: Full focused verification and checkpoint update

Files:

- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `docs/ARCHITECTURE_ITERATION_LOG.md` when required by repository convention

Run focused tests, compile checks, and diff validation. Manually audit the call chain: configuration load -> capture -> profile detection -> anchor read -> joint registration -> result rendering. Record remaining limitations, sample IDs, thresholds, and exact next test steps in the checkpoint.

Verify:

```powershell
pytest -q tests/poe2_live_terrain/test_multiplayer_first_frame.py tests/test_poe2_capture_test_page.py
python -m compileall -q src/auto_modules
git diff --check
```

Expected result: all focused tests pass, compilation succeeds, and the checkpoint documents the real sample evidence.
