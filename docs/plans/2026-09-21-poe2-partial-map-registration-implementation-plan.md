# PoE2 Partial Map Registration Experiment Implementation Plan

## Goal

Build an isolated, offline PoE2 experiment that recovers position, rotation, uniform scale, and optional horizontal reflection by matching a thickness-normalized local stitched map against a full native terrain map.

## Architecture Overview

The experiment lives entirely under `tools/debug` and is exercised from `tests/poe2_live_terrain`. It derives one-pixel structural skeletons from both images, uses OpenCV `GeneralizedHoughGuil` to generate global similarity-transform candidates, verifies them with symmetric trimmed Chamfer distance, and emits reproducible reports and overlays. No production runtime or `core` module changes are allowed in this plan.

## Tech Stack

- Python 3.11+
- NumPy
- OpenCV 4.13.0
- pytest
- Existing PoE2 stitching-session JSON/PNG archives

## Safety And Scope Guard

Before every task, verify the changed paths are limited to:

```text
tools/debug/poe2_partial_map_registration_probe.py
tests/poe2_live_terrain/test_partial_map_registration_probe.py
docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md
data/poe2_live_terrain_test/probe_results/shape-registration-*/
```

Do not modify `src/`, the first-page drawing mode, profiles, input devices, Host, or LAN code.

### Task 1: Define Experimental Contracts

Files:

- Create `tools/debug/poe2_partial_map_registration_probe.py`
- Create `tests/poe2_live_terrain/test_partial_map_registration_probe.py`

Add the failing contract test:

```python
from tools.debug.poe2_partial_map_registration_probe import (
    HoughConfig,
    RegistrationCandidate,
    RegistrationConfig,
)


def test_registration_config_rejects_invalid_trim_fraction():
    try:
        RegistrationConfig(trim_fraction=1.0)
    except ValueError as exc:
        assert "trim_fraction" in str(exc)
    else:
        raise AssertionError("expected invalid trim fraction to fail")


def test_candidate_serializes_transform_fields():
    candidate = RegistrationCandidate(
        center=(12.5, 18.0),
        angle=45.0,
        scale=0.35,
        reflected=True,
        hough_votes=(20, 30, 40),
    )
    assert candidate.as_dict()["center"] == [12.5, 18.0]
    assert candidate.as_dict()["reflected"] is True
```

Run:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py -q
# Expected: collection error because the module does not exist.
```

Implement the minimal contracts:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class HoughConfig:
    min_angle: float = 0.0
    max_angle: float = 360.0
    angle_step: float = 5.0
    min_scale: float = 0.10
    max_scale: float = 0.50
    scale_step: float = 0.02
    min_distance: float = 24.0
    position_threshold: int = 8
    angle_threshold: int = 20
    scale_threshold: int = 10


@dataclass(frozen=True)
class RegistrationConfig:
    hough: HoughConfig = HoughConfig()
    trim_fraction: float = 0.20
    distance_tolerance: float = 3.0
    max_candidates: int = 24
    min_skeleton_pixels: int = 80

    def __post_init__(self) -> None:
        if not 0.0 <= self.trim_fraction < 0.5:
            raise ValueError("trim_fraction must be in [0, 0.5)")
        if self.distance_tolerance <= 0.0:
            raise ValueError("distance_tolerance must be positive")


@dataclass(frozen=True)
class RegistrationCandidate:
    center: tuple[float, float]
    angle: float
    scale: float
    reflected: bool
    hough_votes: tuple[int, int, int]
    score: float = 0.0
    forward_coverage: float = 0.0
    reverse_coverage: float = 0.0
    forward_distance: float = float("inf")
    reverse_distance: float = float("inf")

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["center"] = list(self.center)
        result["hough_votes"] = list(self.hough_votes)
        return result
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py -q
# Expected: 2 passed
```

Commit: `test: define partial map registration contracts`

### Task 2: Normalize Wall Thickness With A Skeleton

Files:

- Modify `tools/debug/poe2_partial_map_registration_probe.py`
- Modify `tests/poe2_live_terrain/test_partial_map_registration_probe.py`

Add the failing test:

```python
import cv2
import numpy as np

from tools.debug.poe2_partial_map_registration_probe import normalize_shape


def test_normalize_shape_is_stable_across_wall_thickness():
    thin = np.zeros((120, 160), dtype=np.uint8)
    thick = np.zeros_like(thin)
    points = np.array([[10, 95], [45, 30], [105, 30], [145, 85]], np.int32)
    cv2.polylines(thin, [points], False, 255, 2)
    cv2.polylines(thick, [points], False, 255, 11)

    thin_shape = normalize_shape(thin)
    thick_shape = normalize_shape(thick)
    distance = cv2.distanceTransform(np.where(thin_shape > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 3)
    assert np.mean(distance[thick_shape > 0] <= 2.0) >= 0.95
    assert 0.75 <= np.count_nonzero(thick_shape) / np.count_nonzero(thin_shape) <= 1.25
```

Run and expect failure because `normalize_shape` is missing.

Implement:

```python
def binary_mask(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("shape image must be a non-empty 2D array")
    return np.where(array > 0, 255, 0).astype(np.uint8)


def morphological_skeleton(mask: np.ndarray) -> np.ndarray:
    work = binary_mask(mask)
    skeleton = np.zeros_like(work)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(work):
        eroded = cv2.erode(work, element)
        opened = cv2.dilate(eroded, element)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(work, opened))
        work = eroded
    return skeleton


def normalize_shape(image: np.ndarray, *, min_component_area: int = 8) -> np.ndarray:
    skeleton = morphological_skeleton(image)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(skeleton, 8)
    output = np.zeros_like(skeleton)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= int(min_component_area):
            output[labels == label] = 255
    return output
```

Verify the focused test passes.

Commit: `feat: normalize map walls into thickness independent skeletons`

### Task 3: Preserve Anchor Coordinates Through Reflection And Similarity Transform

Files:

- Modify both experiment files.

Add a failing test that transforms a known anchor and verifies the output:

```python
from tools.debug.poe2_partial_map_registration_probe import project_point


def test_project_point_applies_reflection_rotation_scale_and_translation():
    result = project_point(
        (30.0, 20.0),
        local_center=(20.0, 20.0),
        global_center=(100.0, 80.0),
        angle=90.0,
        scale=2.0,
        reflected=False,
    )
    assert np.allclose(result, (100.0, 100.0), atol=1e-5)
```

Implement:

```python
def project_point(
    point: tuple[float, float],
    *,
    local_center: tuple[float, float],
    global_center: tuple[float, float],
    angle: float,
    scale: float,
    reflected: bool,
) -> tuple[float, float]:
    x = float(point[0]) - float(local_center[0])
    y = float(point[1]) - float(local_center[1])
    if reflected:
        x = -x
    radians = np.deg2rad(float(angle))
    cosine, sine = float(np.cos(radians)), float(np.sin(radians))
    return (
        float(global_center[0]) + scale * (cosine * x - sine * y),
        float(global_center[1]) + scale * (sine * x + cosine * y),
    )
```

Verify the focused test passes.

Commit: `feat: preserve player anchors through similarity transforms`

### Task 4: Generate Global Candidates With Generalized Hough Guil

Files:

- Modify both experiment files.

Add a synthetic failing test. Build an asymmetric local skeleton, project it into a larger target at `(260, 190)`, angle `35°`, scale `0.8`, and add unrelated lines. Assert at least one candidate is within `8 px`, `3°`, and `0.06` scale of ground truth.

Use this complete helper in the test:

```python
def place_shape(shape, size, center, angle, scale):
    matrix = cv2.getRotationMatrix2D(
        ((shape.shape[1] - 1) / 2.0, (shape.shape[0] - 1) / 2.0),
        -angle,
        scale,
    )
    matrix[0, 2] += center[0] - (shape.shape[1] - 1) / 2.0
    matrix[1, 2] += center[1] - (shape.shape[0] - 1) / 2.0
    return cv2.warpAffine(shape, matrix, size, flags=cv2.INTER_NEAREST)
```

Implement candidate generation:

```python
def generate_hough_candidates(
    local_shape: np.ndarray,
    terrain_shape: np.ndarray,
    *,
    config: HoughConfig,
    reflected: bool,
) -> list[RegistrationCandidate]:
    template = cv2.flip(local_shape, 1) if reflected else local_shape
    detector = cv2.createGeneralizedHoughGuil()
    detector.setMinDist(config.min_distance)
    detector.setMinAngle(config.min_angle)
    detector.setMaxAngle(config.max_angle)
    detector.setAngleStep(config.angle_step)
    detector.setMinScale(config.min_scale)
    detector.setMaxScale(config.max_scale)
    detector.setScaleStep(config.scale_step)
    detector.setPosThresh(config.position_threshold)
    detector.setAngleThresh(config.angle_threshold)
    detector.setScaleThresh(config.scale_threshold)
    detector.setTemplate(template)
    positions, votes = detector.detect(terrain_shape)
    if positions is None or votes is None:
        return []
    result = []
    for position, vote in zip(positions[0], votes[0]):
        x, y, scale, angle = position
        result.append(
            RegistrationCandidate(
                center=(float(x), float(y)),
                angle=float(angle) % 360.0,
                scale=float(scale),
                reflected=reflected,
                hough_votes=tuple(int(value) for value in vote),
            )
        )
    return result
```

Run:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py -q -k hough
# Expected: synthetic Hough test passes.
```

Commit: `feat: generate partial map candidates with generalized hough`

### Task 5: Verify Candidates With Trimmed Chamfer Distance

Files:

- Modify both experiment files.

Add a failing test with one correct candidate and one wrong candidate. Add a filled text-like rectangle covering at least `15%` of the local pixels. Assert the correct candidate still receives the higher score with `trim_fraction=0.20`.

Implement the scoring primitives:

```python
def trimmed_mean(values: np.ndarray, trim_fraction: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=np.float32).reshape(-1))
    keep = max(1, int(round(ordered.size * (1.0 - trim_fraction))))
    return float(np.mean(ordered[:keep]))


def distance_field(shape: np.ndarray) -> np.ndarray:
    return cv2.distanceTransform(
        np.where(binary_mask(shape) > 0, 0, 255).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )


def warp_candidate(
    local_shape: np.ndarray,
    target_shape: tuple[int, int],
    candidate: RegistrationCandidate,
) -> np.ndarray:
    template = cv2.flip(local_shape, 1) if candidate.reflected else local_shape
    center = ((template.shape[1] - 1) / 2.0, (template.shape[0] - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -candidate.angle, candidate.scale)
    matrix[0, 2] += candidate.center[0] - center[0]
    matrix[1, 2] += candidate.center[1] - center[1]
    return cv2.warpAffine(template, matrix, (target_shape[1], target_shape[0]), flags=cv2.INTER_NEAREST)
```

Implement `score_candidate()` so it:

1. warps the local skeleton;
2. samples the terrain distance field at projected local pixels;
3. builds a dilated observed support mask around the projected local bounding region;
4. samples the projected-local distance field at terrain pixels inside that support;
5. computes trimmed means and coverage at `distance_tolerance`;
6. returns a replaced immutable candidate with all score fields populated.

Use this explicit score:

```python
distance_score = np.exp(-(forward_distance + reverse_distance) / (2.0 * tolerance))
score = 0.40 * forward_coverage + 0.25 * reverse_coverage + 0.35 * distance_score
```

Verify the noise test passes.

Commit: `feat: rank registration candidates with trimmed chamfer`

### Task 6: Reject Ambiguous Direction Results

Files:

- Modify both experiment files.

Add tests for:

- correct top candidate with sufficient margin returns `accepted=True`;
- two equal candidates in repeated rooms return `accepted=False` and reason `ambiguous`;
- no candidates return reason `no_match`.

Add:

```python
@dataclass(frozen=True)
class RegistrationResult:
    accepted: bool
    reason: str
    candidates: tuple[RegistrationCandidate, ...]
    score_margin: float


def decide_result(
    candidates: list[RegistrationCandidate],
    *,
    minimum_score: float = 0.68,
    minimum_margin: float = 0.05,
) -> RegistrationResult:
    ordered = tuple(sorted(candidates, key=lambda item: item.score, reverse=True))
    if not ordered:
        return RegistrationResult(False, "no_match", (), 0.0)
    second = ordered[1].score if len(ordered) > 1 else 0.0
    margin = float(ordered[0].score - second)
    if ordered[0].score < minimum_score:
        return RegistrationResult(False, "low_score", ordered, margin)
    if len(ordered) > 1 and margin < minimum_margin:
        return RegistrationResult(False, "ambiguous", ordered, margin)
    return RegistrationResult(True, "accepted", ordered, margin)
```

Verify all decision tests pass.

Commit: `feat: fail closed on ambiguous map direction`

### Task 7: Add One End-To-End Registration Function

Files:

- Modify both experiment files.

Add a synthetic end-to-end test that varies wall thickness and includes clutter, then asserts the accepted transform recovers angle, scale, and center within the agreed tolerances.

Implement:

```python
def register_partial_map(
    local_image: np.ndarray,
    terrain_image: np.ndarray,
    *,
    config: RegistrationConfig | None = None,
) -> RegistrationResult:
    config = config or RegistrationConfig()
    local_shape = normalize_shape(local_image)
    terrain_shape = normalize_shape(terrain_image)
    if cv2.countNonZero(local_shape) < config.min_skeleton_pixels:
        return RegistrationResult(False, "insufficient_local_shape", (), 0.0)
    candidates = []
    for reflected in (False, True):
        candidates.extend(
            generate_hough_candidates(
                local_shape,
                terrain_shape,
                config=config.hough,
                reflected=reflected,
            )
        )
    candidates.sort(key=lambda item: item.hough_votes, reverse=True)
    candidates = candidates[: config.max_candidates]
    scored = [
        score_candidate(local_shape, terrain_shape, candidate, config=config)
        for candidate in candidates
    ]
    return decide_result(scored)
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py -q
# Expected: all experiment tests pass.
```

Commit: `feat: compose offline partial map registration experiment`

### Task 8: Load Stitching Sessions Without Borrowing Stale Terrain

Files:

- Modify both experiment files.

Add temporary-directory tests that verify:

- a session-local `terrain.png` is preferred;
- an explicit external terrain path is accepted and recorded;
- missing `stitched_map.png` fails;
- missing terrain fails instead of silently using a historical file;
- `session.json` map origin and current position produce the correct local player anchor.

Implement `load_probe_input(session_directory, terrain_input=None)` returning a frozen dataclass with images, source paths, hashes, manifest, and local player position:

```text
local_player = current_position - map_origin
```

Use `hashlib.sha256(path.read_bytes()).hexdigest()` for provenance. Do not infer instance identity from filenames.

Verify loader tests pass.

Commit: `feat: load reproducible stitching registration inputs`

### Task 9: Emit Reports And Diagnostic Overlays

Files:

- Modify both experiment files.

Add tests asserting an output directory contains:

```text
report.json
local_skeleton.png
terrain_skeleton.png
candidate_01_overlay.png
candidates_sheet.png
```

The report must include:

```json
{
  "schema_version": 1,
  "accepted": false,
  "reason": "...",
  "score_margin": 0.0,
  "input": {
    "session": "...",
    "terrain": "...",
    "stitched_sha256": "...",
    "terrain_sha256": "..."
  },
  "normalization": {
    "local_skeleton_pixels": 0,
    "terrain_skeleton_pixels": 0
  },
  "candidates": []
}
```

Write all files to a hidden sibling temporary directory, then publish with `os.replace`, following the existing archive pattern. Overlays use blue terrain, green projected local shape, yellow overlap, and a red projected player marker.

Verify artifact tests pass.

Commit: `feat: save partial map registration diagnostics`

### Task 10: Add The CLI And Run The Real Sample

Files:

- Modify `tools/debug/poe2_partial_map_registration_probe.py`
- Modify `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`

Add CLI arguments:

```text
--session
--terrain
--output
--min-angle
--max-angle
--angle-step
--min-scale
--max-scale
--scale-step
--trim-fraction
--max-candidates
```

Run focused tests first:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py tests/poe2_live_terrain/test_localization_probe.py -q
# Expected: all focused tests pass.
```

Run the current real sample:

```powershell
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/auto_modules/tools/debug/poe2_partial_map_registration_probe.py `
  --session D:/ACloud/auto_modules/data/poe2_live_terrain_test/stitching_sessions/20260921-121018-260622-a6ccb4c6767e `
  --terrain D:/ACloud/auto_modules/data/poe2_live_terrain_test/samples/20260921-090840-957906-MapFlotsam-5C048CD0/terrain.png `
  --output D:/ACloud/auto_modules/data/poe2_live_terrain_test/probe_results/shape-registration-20260921
```

Inspect `candidate_01_overlay.png` and `candidates_sheet.png`. Record the exact score, angle, scale, reflection, position, margin, and acceptance reason in the current-state document. Do not describe a rejected candidate as a confirmed direction.

Commit: `test: record partial map registration experiment`

### Task 11: Run Regression And Decide Whether Promotion Is Allowed

Files:

- Modify `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` only with measured results.

Run:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain -q
& D:/ACloud/.venv/Scripts/python.exe -m compileall tools/debug/poe2_partial_map_registration_probe.py
git diff --check
```

Expected:

- all PoE2 focused tests pass;
- compileall passes;
- no whitespace errors;
- no files under `src/` changed.

Promotion decision:

- If the synthetic suite passes but the real sample is ambiguous, keep the code in `tools/debug`, record the failing evidence, and collect a larger or cleaner paired session.
- If one real map passes, keep it experimental and verify a second map instance.
- Only after at least two map instances and multi-block consistency pass, create a separate design for a game-neutral `core` registration interface.

Commit: `docs: record shape registration promotion decision`

