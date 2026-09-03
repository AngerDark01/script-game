# Perception and Coordinate Mapping Modularization Plan

## Goal

Introduce a reusable perception package and profile-driven configuration while preserving all existing minimap, Portal, Loot, navigation, and GUI entry points.

## Architecture Overview

`core/perception` owns generic target-detection data, algorithm descriptors, registries, and profiles. Existing minimap-specific recognizers remain in place and are adapted only through narrow bridges. A later `core/spatial` package will own coordinate spaces and calibration. GUI code consumes profile descriptors and results; it does not depend on OpenCV implementation details.

## Tech Stack

- Python 3.10+ syntax already used by the repository.
- OpenCV and NumPy for the first color/template adapters.
- JSON profile persistence with explicit schema version.
- PySide6 integration deferred until the non-GUI contracts are covered.
- Standard-library `unittest` smoke tests for the new package because the current environment does not include pytest.

## Task 1: Add Generic Perception Models

Files:

- `core/perception/__init__.py`
- `core/perception/models.py`
- `tests/test_perception_models.py`

Add coordinate-space, bounding-box, frame-context, evidence, and target-detection data objects. They must be immutable at the outer object level, accept normalized or pixel coordinates, and preserve arbitrary evidence metadata for debugging.

Test first:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_models -v
```

Expected initial result: the test module is missing. Implement the models, rerun, and expect all tests to pass.

Commit: `feat: add generic perception result models`

## Task 2: Add Profile Schema and Persistence

Files:

- `core/perception/profiles.py`
- `core/perception/profile_store.py`
- `tests/test_perception_profiles.py`

Add algorithm parameter profiles and game/scene/target composition profiles. Persist a versioned JSON document. Validate required identifiers, reject duplicate algorithm entries, preserve unknown metadata, and support profile copy without sharing mutable parameter dictionaries.

Test first and verify with:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_profiles -v
```

Commit: `feat: add perception profile persistence`

## Task 3: Add Algorithm Descriptors and Registry

Files:

- `core/perception/algorithms/__init__.py`
- `core/perception/algorithms/base.py`
- `core/perception/registry.py`
- `tests/test_perception_registry.py`

Add descriptor-driven algorithm registration. The registry must expose available, experimental, and unavailable algorithms without importing GUI code. Duplicate identifiers must fail. Parameter descriptors are data consumed later by the GUI.

Test first and verify with:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_registry -v
```

Commit: `feat: add perception algorithm registry`

## Task 4: Add Reusable Color and Template Adapters

Files:

- `core/perception/algorithms/color.py`
- `core/perception/algorithms/template.py`
- `tests/test_perception_algorithms.py`

Implement full-frame-capable color-region and masked multi-scale template detectors. They must return the generic target-detection shape, keep source algorithm ids in evidence, and never assume a minimap or fixed screen resolution. OCR and feature matching are registered as extension points but remain optional until a provider is selected.

Test first and verify with:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_algorithms -v
```

Commit: `feat: add reusable color and template detectors`

## Task 5: Add Coordinate Spaces and Calibration DTOs

Files:

- `core/spatial/__init__.py`
- `core/spatial/models.py`
- `core/spatial/calibration.py`
- `tests/test_spatial_calibration.py`

Represent explicit coordinate spaces, normalized positions, window rectangles, and anchor-based calibration state. No hard-coded offsets are introduced. The first implementation only validates transforms and calibration data; it does not replace existing click mapping.

Commit: `feat: add coordinate mapping primitives`

## Task 6: Build GUI Profile Test Bench

Files:

- `gui/modes/perception/` (new package)
- `gui/modes/navigation/ui/` integration points
- focused GUI tests

Expose the registry and profile schema as a profile editor and screenshot test bench. Generate controls from parameter descriptors and render candidate boxes with algorithm evidence. Keep the existing navigation and mapping pages unchanged until the test bench is stable.

Commit: `feat: add perception profile test bench`

## Task 7: Bridge Existing Detectors Gradually

Files:

- Existing Portal/Loot adapters only, one target at a time.
- Regression tests for current `EventDetection` output.

Adapt existing minimap-specific detectors to the generic result shape without changing thresholds, event memory, or task scheduling. Keep `HSVRecognizer` as the legacy minimap adapter.

Commit one target at a time, for example: `refactor: adapt loot detection to perception results`

## Task 8: Extract Workflow Orchestration

Files:

- `application/workflows/`
- `gui/modes/navigation/widget.py`
- `gui/modes/navigation/runtime/frame_loop.py`

Move only orchestration out of the navigation widget after the lower seams are covered. Workflows request targets, apply selection policies, invoke coordinate mapping, execute actions, and verify state transitions. They never call algorithm implementations directly.

Commit one workflow at a time: map device, map selection, waystone, enter map, clear map, loot, and trial.

## Verification Rules

- Keep existing canonical imports working.
- Run new unit tests and `compileall` after every task.
- Run focused legacy tests for each adapted detector.
- Never change existing Portal/Loot thresholds as part of structural work.
- Do not add a mandatory OCR dependency before a provider is selected.
