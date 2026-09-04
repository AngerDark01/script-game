# 通用预处理底座与旧链路兼容桥：实现计划

## Goal

将旧 HSV/小地图链路中可复用的图像处理与导航投影下沉到通用底层；旧入口通过兼容 facade 委托新实现，保持现有业务行为和 GUI 调用不变。

## Architecture overview

- `core.perception.preprocessing` 是游戏无关的图像、mask、几何与 recipe 层。
- `ImageArtifact` 保存像素、源帧和 output-to-source 几何关系；处理后结果可回投原始帧。
- `core.vision.hsv` 保留墙/雾/玩家等业务策略，只委托具体图像操作。
- `MapFrameEvidence` 是 `MapStitcher.add_frame(...)` 的新增 typed 入口，旧方法不改。
- `core.navigation.projection` 只做 world-vector 到 view-target 的纯数学；旧 `motion_mapping` 保留原 API。
- 每一项先写失败测试，最小实现使其通过，之后执行相关回归。

## Tech stack

- Python 3、NumPy、OpenCV
- 标准库 `unittest`
- 现有 `core.perception.models`：`CoordinateSpace`、`BoundingBox`、`FrameContext`

## Shared verification rules

```powershell
python -m unittest tests.test_perception_preprocessing
python -m unittest tests.test_recognizer_optimized
python -m unittest tests.test_stitcher_core
python -m compileall -q core
git diff --check
```

只允许显式暂存本计划创建或修改的文件；绝不执行全量 stage，也不触碰 `virtual_gamepad/` 或其他已有未提交修改。

---

### Task 1: 建立 ImageArtifact 与几何回投契约

**Files**

- Create `core/perception/preprocessing/models.py`
- Create `core/perception/preprocessing/__init__.py`
- Modify `core/perception/__init__.py`
- Create `tests/test_perception_preprocessing.py`

**Failing tests first**

```python
def test_identity_geometry_keeps_point_and_box_in_source_frame(self):
    geometry = ImageGeometry.identity(
        width=100,
        height=80,
        coordinate_space=CoordinateSpace.FULL_SCREEN,
    )
    self.assertEqual((12.5, 20.0), geometry.map_point_to_source((12.5, 20.0)))
    self.assertEqual(
        BoundingBox(10, 15, 20, 10),
        geometry.map_box_to_source(BoundingBox(10, 15, 20, 10)),
    )
```

**Minimal implementation**

```python
@dataclass(frozen=True)
class ImageGeometry:
    source_width: int
    source_height: int
    output_width: int
    output_height: int
    coordinate_space: CoordinateSpace
    output_to_source: tuple[tuple[float, float, float], ...]

    @classmethod
    def identity(cls, *, width: int, height: int, coordinate_space: CoordinateSpace) -> "ImageGeometry":
        return cls(width, height, width, height, coordinate_space, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

    def map_point_to_source(self, point: tuple[float, float]) -> tuple[float, float]:
        ...
```

`ImageArtifact` holds `image`, `frame: FrameContext`, `geometry`, and immutable metadata. Validate positive dimensions and a 3×3 transform. Export it from both preprocessing and `core.perception`.

**Verify**

```powershell
python -m unittest tests.test_perception_preprocessing.ImageGeometryTests
# Expected: all geometry-contract tests pass
```

**Checkpoint commit**

```powershell
git add core/perception/preprocessing/models.py core/perception/preprocessing/__init__.py core/perception/__init__.py tests/test_perception_preprocessing.py
git commit -m "feat: add image artifact geometry contract"
```

---

### Task 2: 实现 crop、resize、pad 并组合坐标变换

**Files**

- Create `core/perception/preprocessing/geometry.py`
- Modify `core/perception/preprocessing/__init__.py`
- Modify `tests/test_perception_preprocessing.py`

**Failing tests first**

```python
def test_crop_resize_and_pad_map_back_to_original_coordinates(self):
    artifact = make_artifact(width=200, height=100)
    processed = pad(resize(crop(artifact, left=20, top=10, width=100, height=50), width=200, height=100), left=5, top=7, right=0, bottom=0)
    self.assertEqual((70.0, 35.0), processed.geometry.map_point_to_source((105.0, 57.0)))
```

**Minimal implementation**

- `crop(artifact, *, left, top, width, height)` slices the image and composes a translation from the new output to the prior artifact.
- `resize(artifact, *, width, height, interpolation=cv2.INTER_LINEAR)` uses `cv2.resize` and composes inverse x/y scale.
- `pad(artifact, *, left, top, right, bottom, border_type=cv2.BORDER_CONSTANT, value=0)` uses `cv2.copyMakeBorder` and composes inverse translation.
- Reject non-positive sizes and crops outside the artifact bounds with `ValueError`.

**Verify**

```powershell
python -m unittest tests.test_perception_preprocessing.ImageGeometryTransformTests
# Expected: crop, resize, pad and bbox-backprojection tests pass
```

**Checkpoint commit**

```powershell
git add core/perception/preprocessing/geometry.py core/perception/preprocessing/__init__.py tests/test_perception_preprocessing.py
git commit -m "feat: add image geometry transforms"
```

---

### Task 3: 提取纯像素增强与颜色操作

**Files**

- Create `core/perception/preprocessing/image_ops.py`
- Modify `core/perception/preprocessing/__init__.py`
- Modify `tests/test_perception_preprocessing.py`

**Failing tests first**

```python
def test_percentile_normalize_uses_safe_fallback_for_flat_input(self):
    image = np.full((4, 4, 3), 20, dtype=np.uint8)
    np.testing.assert_array_equal(image, percentile_normalize(image, low=40, high=99))

def test_gamma_and_channel_scale_preserve_uint8_shape(self):
    result = scale_bgr_channels(gamma_correct(sample, gamma=1.2), blue=1.3)
    self.assertEqual(sample.shape, result.shape)
    self.assertEqual(np.uint8, result.dtype)
```

**Minimal implementation**

Implement typed, recognizer-free functions:

```python
def gamma_correct(image: np.ndarray, *, gamma: float) -> np.ndarray: ...
def gaussian_blur(image: np.ndarray, *, kernel_size: int = 3) -> np.ndarray: ...
def median_blur(image: np.ndarray, *, kernel_size: int = 3) -> np.ndarray: ...
def lab_clahe(image: np.ndarray, *, clip_limit: float, tile_grid_size: tuple[int, int]) -> np.ndarray: ...
def top_hat(image: np.ndarray, *, kernel_size: int, strength: float = 1.0) -> np.ndarray: ...
def percentile_normalize(image: np.ndarray, *, low: float, high: float) -> np.ndarray: ...
def scale_bgr_channels(image: np.ndarray, *, blue: float = 1.0, green: float = 1.0, red: float = 1.0) -> np.ndarray: ...
def to_gray(image: np.ndarray) -> np.ndarray: ...
def to_hsv(image: np.ndarray) -> np.ndarray: ...
def canny_edges(image: np.ndarray, *, low: int, high: int) -> np.ndarray: ...
```

All functions validate dimensions and return `uint8`; they do not know wall, fog, player, game, or recognizer concepts.

**Verify**

```powershell
python -m unittest tests.test_perception_preprocessing.ImageOperationTests
# Expected: all deterministic enhancement and colour-operation tests pass
```

**Checkpoint commit**

```powershell
git add core/perception/preprocessing/image_ops.py core/perception/preprocessing/__init__.py tests/test_perception_preprocessing.py
git commit -m "feat: add reusable image preprocessing operations"
```

---

### Task 4: 提取 mask、形态学、候选几何与融合操作

**Files**

- Create `core/perception/preprocessing/masks.py`
- Modify `core/perception/preprocessing/__init__.py`
- Modify `tests/test_perception_preprocessing.py`

**Failing tests first**

```python
def test_filter_small_components_discards_only_components_below_threshold(self):
    mask = np.zeros((10, 10), np.uint8)
    mask[1, 1] = 255
    mask[5:8, 5:8] = 255
    self.assertEqual(9, np.count_nonzero(filter_small_components(mask, min_area=2)))
```

**Minimal implementation**

Implement:

```python
def hsv_range_mask(image, *, lower, upper) -> np.ndarray: ...
def binary_threshold(image, *, threshold: int) -> np.ndarray: ...
def morphology(mask, *, operation: str, kernel_shape: str, kernel_size: int, iterations: int = 1) -> np.ndarray: ...
def filter_small_components(mask, *, min_area: int) -> np.ndarray: ...
def saturation_mask(image, *, threshold: int) -> np.ndarray: ...
def circle_mask(shape, *, center, radius: int, inside: int = 255, outside: int = 0) -> np.ndarray: ...
def subtract_mask(mask, exclusion_mask) -> np.ndarray: ...
def weighted_mask_fusion(*, first, first_weight: float, second, second_weight: float) -> np.ndarray: ...
```

The module works only on masks/images and inputs supplied by callers. It never selects the player centre or assigns semantic meanings to masks.

**Verify**

```powershell
python -m unittest tests.test_perception_preprocessing.MaskOperationTests
# Expected: HSV, morphology, components, exclusion and fusion tests pass
```

**Checkpoint commit**

```powershell
git add core/perception/preprocessing/masks.py core/perception/preprocessing/__init__.py tests/test_perception_preprocessing.py
git commit -m "feat: add reusable mask preprocessing operations"
```

---

### Task 5: 增加可配置、可保存的预处理 recipe

**Files**

- Create `core/perception/preprocessing/recipe.py`
- Modify `core/perception/preprocessing/__init__.py`
- Modify `tests/test_perception_preprocessing.py`

**Failing tests first**

```python
def test_recipe_runs_declared_operations_without_game_specific_context(self):
    recipe = PreprocessingRecipe.from_steps((
        PreprocessingStep("gaussian_blur", {"kernel_size": 3}),
        PreprocessingStep("to_gray", {}),
        PreprocessingStep("canny_edges", {"low": 20, "high": 80}),
    ))
    artifact = recipe.run(make_artifact(width=32, height=32))
    self.assertEqual((32, 32), artifact.image.shape)
```

**Minimal implementation**

- `PreprocessingStep(operation_id: str, parameters: Mapping[str, Any])` is immutable and JSON-safe.
- `PreprocessingRecipe(steps: tuple[PreprocessingStep, ...])` runs an explicit operation registry.
- Pixel-preserving steps return an `ImageArtifact` with unchanged geometry; crop/resize/pad use Task 2 transforms.
- An unknown operation raises `ValueError` with the operation id; parameters are copied before use.

This is the profile/UI-facing seam. It contains no GUI code and no game-specific defaults.

**Verify**

```powershell
python -m unittest tests.test_perception_preprocessing.PreprocessingRecipeTests
# Expected: declared steps execute; bad operation ids fail explicitly
```

**Checkpoint commit**

```powershell
git add core/perception/preprocessing/recipe.py core/perception/preprocessing/__init__.py tests/test_perception_preprocessing.py
git commit -m "feat: add configurable preprocessing recipes"
```

---

### Task 6: 让旧 HSV preprocessing/mask/combined facade 委托通用层

**Files**

- Modify `core/vision/hsv/preprocessing.py`
- Modify `core/vision/hsv/masks.py`
- Modify `core/vision/hsv/combined.py`
- Modify `tests/test_recognizer_optimized.py`
- Create `tests/test_hsv_preprocessing_compat.py`

**Failing tests first**

Capture deterministic reference arrays from representative wall, fog and saturated-icon fixtures before changing the implementation. Add assertions that:

```python
np.testing.assert_array_equal(expected_wall, recognizer.extract_walls(image))
np.testing.assert_array_equal(expected_fog, recognizer.extract_fog(image))
np.testing.assert_array_equal(expected_match, recognizer.extract_combined(image, player_pos=(10, 70))[0])
```

**Minimal implementation**

- Preserve every legacy function name and signature.
- Translate recognizer attributes into generic operation arguments at the facade boundary.
- Keep `transparent_mode`, player-centre defaulting, `player_clear_radius`, saturation exclusion, and wall/edge weights in legacy functions.
- Replace direct OpenCV primitive calls only where a generic equivalent exists.
- Keep the returned `(match_mask, wall_mask, fog_mask)` tuple exactly unchanged.

**Verify**

```powershell
python -m unittest tests.test_recognizer_optimized tests.test_hsv_preprocessing_compat
# Expected: all pre-existing and captured-compatibility tests pass
```

**Checkpoint commit**

```powershell
git add core/vision/hsv/preprocessing.py core/vision/hsv/masks.py core/vision/hsv/combined.py tests/test_recognizer_optimized.py tests/test_hsv_preprocessing_compat.py
git commit -m "refactor: delegate legacy hsv processing to generic operations"
```

---

### Task 7: 为 MapStitcher 增加 typed evidence 入口

**Files**

- Create `core/mapping/evidence.py`
- Modify `core/mapping/stitcher.py`
- Create `tests/test_mapping_evidence.py`

**Failing tests first**

```python
def test_add_evidence_delegates_exactly_to_legacy_add_frame(self):
    stitcher = MapStitcher(canvas_size=100)
    evidence = MapFrameEvidence(image=image, match_mask=match, save_mask=wall, fog_mask=fog, player_position=(8, 9))
    with patch.object(stitcher, "add_frame", return_value="ok") as add_frame:
        self.assertEqual("ok", stitcher.add_evidence(evidence))
    add_frame.assert_called_once_with(image, match, wall, fog, raw_gray=None, player_pos=(8, 9))
```

**Minimal implementation**

```python
@dataclass(frozen=True)
class MapFrameEvidence:
    image: np.ndarray
    match_mask: np.ndarray
    save_mask: np.ndarray
    fog_mask: np.ndarray
    player_position: tuple[float, float] | None = None
    raw_gray: np.ndarray | None = None
    coordinate_space: CoordinateSpace = CoordinateSpace.MINIMAP
    source_frame: FrameContext | None = None
```

`MapStitcher.add_evidence(evidence)` validates the type then calls existing `add_frame`. It does not alter registration, merging, stored map data, or the historical method signature.

**Verify**

```powershell
python -m unittest tests.test_mapping_evidence tests.test_stitcher_core
# Expected: typed ingress and historical stitching regression tests pass
```

**Checkpoint commit**

```powershell
git add core/mapping/evidence.py core/mapping/stitcher.py tests/test_mapping_evidence.py
git commit -m "feat: add typed map frame evidence"
```

---

### Task 8: 抽取世界地图到游戏视野的纯导航投影

**Files**

- Create `core/navigation/__init__.py`
- Create `core/navigation/projection.py`
- Modify `core/input/motion_mapping.py`
- Create `tests/test_navigation_projection.py`
- Modify `tests/test_motion_controller.py` only if a regression needs public-controller coverage

**Failing tests first**

```python
def test_project_world_target_returns_direction_and_clamped_radius(self):
    target = project_world_target(
        player_position=(0.0, 0.0),
        target_position=(3.0, 4.0),
        view_center=(100, 100),
        pixels_per_world_unit=10.0,
        min_radius=60.0,
        max_radius=100.0,
    )
    self.assertEqual((136, 148), target.point)
    self.assertEqual(60.0, target.radius)
```

**Minimal implementation**

- Define immutable `ProjectedViewTarget(point, direction, world_distance, raw_radius, radius)`.
- `project_world_target(...)` handles coincident points explicitly and never sends input.
- `motion_mapping.calculate_movement_click()` and `calculate_mapped_target_click()` retain their signatures and construct their historical `ClickMappingResult` from the generic result.
- `apply_bottom_click_guard()` stays in legacy/input policy because it expresses a game UI exclusion.

**Verify**

```powershell
python -m unittest tests.test_navigation_projection tests.test_motion_controller
# Expected: pure projection and existing input-controller behaviour pass
```

**Checkpoint commit**

```powershell
git add core/navigation/__init__.py core/navigation/projection.py core/input/motion_mapping.py tests/test_navigation_projection.py tests/test_motion_controller.py
git commit -m "refactor: extract reusable navigation projection math"
```

---

### Task 9: 全量验证、架构索引同步与受控提交

**Files**

- Modify `CODEBASE.md`
- Append `ITERATION_LOG.md`
- Modify `docs/PERCEPTION_ENGINE_CHECKPOINT.md`

**Required checks**

```powershell
python -m unittest tests.test_perception_preprocessing tests.test_hsv_preprocessing_compat tests.test_recognizer_optimized tests.test_mapping_evidence tests.test_stitcher_core tests.test_navigation_projection tests.test_motion_controller
python -m unittest discover -s tests
python -m compileall -q core
git diff --check
git status --short
```

Expected result: all relevant and full suites pass; no whitespace errors; only explicitly intended files are staged.

**Documentation update**

- Record new generic preprocessing, MapFrameEvidence and navigation-projection boundaries in `CODEBASE.md`.
- Append results, coverage and remaining Portal/Loot bridge work to `ITERATION_LOG.md`.
- Update `docs/PERCEPTION_ENGINE_CHECKPOINT.md`: P4.5 complete, legacy sensor/mapper bridges remaining.

**Final scoped commit**

```powershell
git add core/perception/preprocessing core/perception/__init__.py core/vision/hsv/preprocessing.py core/vision/hsv/masks.py core/vision/hsv/combined.py core/mapping/evidence.py core/mapping/stitcher.py core/navigation core/input/motion_mapping.py tests/test_perception_preprocessing.py tests/test_hsv_preprocessing_compat.py tests/test_mapping_evidence.py tests/test_navigation_projection.py CODEBASE.md ITERATION_LOG.md docs/PERCEPTION_ENGINE_CHECKPOINT.md docs/plans/2026-09-04-generic-preprocessing-legacy-bridge-design.md docs/plans/2026-09-04-generic-preprocessing-legacy-bridge-implementation-plan.md
git commit -m "refactor: extract reusable perception and navigation primitives"
```

Do not include unrelated existing changes, especially `virtual_gamepad/`, `core/events/window_finder.py`, logs, or other agents’ test files.
