# Shape Algorithm Adapter Design

## Goal

Add a provider-free, reusable OpenCV shape detector that converts visible contours in one `FrameContext` into `TargetDetection` results using adjustable geometric criteria. It must provide a generic alternative for stable circles, rectangles, rings, and other high-contrast UI elements without taking ownership of existing Portal/Loot-specific logic.

## Architecture

```text
FrameContext.image
  -> grayscale normalization
  -> binary or inverted threshold
  -> optional open/close morphology
  -> external contours
  -> area / polygon vertices / circularity / solidity filters
  -> BoundingBox + DetectionEvidence
  -> TargetDetection
  -> existing runner / fusion / confirmation / selection stages
```

The algorithm accepts only the current frame and data parameters. It never acquires a frame, resolves a template, recognizes text, maps coordinates, performs input, calls a workflow, or names a game-specific target. `target_type` is supplied by the enclosing target profile.

## Parameters

- `threshold`: grayscale threshold in `[0, 255]`, default `128`;
- `threshold_mode`: `binary` (default) or `binary_inverse`;
- `morphology_kernel`: `0` disables morphology; positive values use an odd open/close kernel;
- `min_area` and `max_area`: contour-area range; `max_area=0` disables its upper bound;
- `min_vertices` and `max_vertices`: polygon-vertex range after approximation; `0` disables a bound;
- `approximation_ratio`: positive fraction of contour perimeter used by `approxPolyDP`;
- `min_circularity`: lower filter bound in `[0, 1]`;
- `min_solidity`: lower filter bound in `[0, 1]`;
- `max_results`: `0` retains all matches; positive values retain the strongest candidates.

For each accepted contour, evidence records area, perimeter, vertex count, circularity, solidity, fill ratio, and threshold mode. Confidence is the average of the bounded solidity and bounding-box fill ratio, so it measures contour quality rather than guessing game semantics.

## Failure and Compatibility Rules

1. Invalid or empty image frames return no detections, matching the existing color/template detector convention.
2. Unsupported threshold modes, negative bounds, out-of-range circularity/solidity, invalid max result count, or non-positive approximation ratio raise `ValueError` at construction.
3. The detector only uses `RETR_EXTERNAL`; nested contour/hole interpretation is deliberately out of scope for the first generic slice.
4. Existing Portal/Loot/minimap contour code remains untouched. No provider, ML model, GUI, action, mapping, navigation, or workflow dependency is introduced.

## TDD Slices

### Slice 1 — Circle detection and normalized output

Write a failing synthetic-image test for a bright circle on dark background. Verify the detector returns the configured target type, frame coordinate space, capture time, bounding box/center, `shape` source, and contour evidence.

### Slice 2 — Geometric filtering and validation

Add one failure at a time for vertex filtering that keeps a rectangle while rejecting a circle, morphology/area behavior where needed, invalid threshold modes, and result limits. Implement only the associated parameter behavior.

### Slice 3 — Registry and public surface

Verify the `shape` descriptor becomes available, exposes generic parameter specs, the default registry constructs `ShapeDetector`, and the package public import works. Re-run color/template/OCR/engine regressions.

## Verification

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_shape_algorithm -v
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_algorithms tests.test_perception_ocr_adapter tests.test_perception_template_adapter tests.test_perception_engine tests.test_perception_stages -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
git diff --check
```
