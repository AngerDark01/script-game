# Perception and Coordinate Mapping Modularization

## Goal

Build a reusable, full-screen perception foundation whose algorithm implementations are independent from game-specific scenes, whose parameter instances can be edited from the GUI, and whose coordinate mapping remains separate from recognition and actions.

## Design Principles

- Existing minimap-specific behavior remains available and is not rewritten as a universal detector.
- Generic algorithms are reusable implementations; game, scene, and target profiles provide parameters and algorithm composition.
- Every detector produces the same target-detection shape, including coordinate space, bounding box, confidence, source, timestamp, and optional evidence.
- Recognition never performs clicks, key presses, movement, or GUI mutations.
- Coordinate mapping converts between explicit spaces and is initialized from runtime window/viewport information rather than fixed screen offsets.
- The GUI edits and tests profiles; it does not import algorithm internals or encode thresholds in widgets.
- Existing canonical imports and Portal/Loot behavior remain compatible during migration.

## Architecture Overview

```text
FrameSource
  -> frame normalization and optional ROI proposal
  -> configurable detector chain
  -> candidate fusion and multi-frame confirmation
  -> TargetDetection results
  -> coordinate mapper
  -> action adapter / workflow
  -> state verification
```

The first implementation layer lives under `core/perception/`:

- `models`: frame metadata, candidates, detections, and evidence.
- `algorithms`: color, shape, masked multi-scale template, feature, OCR, and future ML adapters.
- `profiles`: algorithm parameter instances and game/scene/target compositions.
- `pipeline`: detector execution, fusion, confirmation, and candidate selection.
- `registry`: stable discovery of available algorithms and profiles.

The coordinate layer is introduced incrementally under `core/spatial/`, keeping the existing localization and input packages as adapters until behavior is covered.

The application workflow layer consumes target queries and detections. It decides selection order (for example x/y priority), invokes coordinate mapping, sends actions, and verifies state changes. It does not know which detector implementation produced a target.

## Profile Model

Profiles are layered:

```text
algorithm defaults
  -> game profile
  -> scene profile
  -> target profile
  -> temporary GUI overrides
```

Profiles may specify detector order, fallback detectors, scale policy, optional ROI hints, confidence thresholds, confirmation frames, and selection rules. Position hints are optimization metadata only; correctness must not depend on fixed pixel coordinates.

## Compatibility

- `core.vision.HSVRecognizer` continues to serve the existing minimap mapping/localization flow.
- Existing Portal and Loot detectors remain scenario adapters and continue to emit current event models.
- New generic perception results can be adapted into existing `EventDetection` without changing the event coordinator in the first phase.
- `core.input` remains the action execution seam; virtual gamepad is an optional adapter and must not be imported by perception or domain algorithms.

## GUI Direction

The GUI will eventually expose:

- an algorithm catalog with capability and implementation status;
- profile selection by game, scene, and target;
- schema-driven parameter editing;
- screenshot test runs with overlay boxes, scores, and evidence;
- profile save, copy, and reset operations.

The first code change only establishes data and registry foundations so existing UI behavior is unaffected.

## Migration Sequence

1. Add the generic detection models and algorithm/profile registry with unit tests.
2. Add profile persistence and validation, without connecting it to existing runtime paths.
3. Add the first reusable adapters around existing template/color/shape capabilities.
4. Add coordinate-space and calibration models, then bridge them to existing screen mapping.
5. Add a GUI test bench and profile editor.
6. Migrate individual scenarios (map device, waystone, trial, loot) one at a time.
7. Extract workflow orchestration from the navigation widget and frame loop after the lower seams are stable.

## Non-Goals for the First Phase

- No wholesale rename or relocation of `core/vision`, `core/events`, or `core/input`.
- No changes to Portal/Loot thresholds or navigation behavior.
- No mandatory OCR engine dependency.
- No machine-learning model training pipeline yet.
- No fixed-resolution or fixed-language assumption.
