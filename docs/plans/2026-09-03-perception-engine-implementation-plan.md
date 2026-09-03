# Perception Engine Implementation Plan

## Goal

Create a reusable, provider-backed perception engine that supports game/scene/target profiles, preserves legacy behavior, and gives workflows a target-level interface.

## Architecture Overview

```text
FrameSource -> PerceptionEngine -> TargetDetection
                    |                 |
                    v                 v
              profile stages      CoordinateMapper
                                      |
                                      v
                               workflow/action adapter
```

The engine is GUI-free and action-free. Profiles select algorithm instances; providers adapt OpenCV, OCR, templates, and runtime frame sources; workflows consume target results only.

## Tech Stack

- Python 3.12 runtime in `.venv`.
- NumPy and OpenCV for current detectors.
- PySide6 only in GUI adapters.
- Standard-library `unittest` for deterministic tests.
- JSON profile persistence with explicit schema versions.

## Task P0: Checkpoints and architecture inventory

Files: `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `docs/plans/2026-09-03-perception-engine-implementation-plan.md`, `ITERATION_LOG.md`, `CODEBASE.md`.

Record the baseline, missing seams, task queue, verification policy, and known unrelated failures. Do not change runtime behavior.

Verify:

```powershell
git status --short --branch
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core gui
```

Commit: `docs: establish perception engine checkpoints`

## Task P1: Add the engine facade

Files: `core/perception/engine.py`, `core/perception/__init__.py`, `tests/test_perception_engine.py`.

Test the public contract first:

```python
engine = PerceptionEngine(registry)
result = engine.detect(frame, target_profile)
```

The facade owns registry selection and, after P2, directly owns stage execution. It returns `PerceptionRunResult`; the existing `PerceptionPipeline` remains only as a source-compatible forwarding entry point.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_engine -v
```

Commit: `feat: add perception engine facade`

## Task P2: Deepen decision stages

Files: `core/perception/stages/runner.py`, `fusion.py`, `confirmation.py`, `selection.py`, `core/perception/engine.py`, compatibility updates to `core/perception/pipeline.py`, and focused tests.

Each module must expose a small interface with explicit error and ordering rules. The default engine must preserve per-algorithm evidence, fuse spatially close candidates, require configured stable frames, and apply a configurable candidate selection strategy. `PerceptionPipeline` must forward to that engine and own no decision state.

Verify focused tests, then the existing perception suite.

Commit: `feat: split perception decision stages`

The detailed dependency-reversal design and exact red/green commands are recorded in `docs/plans/2026-09-03-perception-engine-ownership-design.md`.

## Task P3: Add provider seams

Files: `core/perception/providers/`, `core/perception/models.py` only where frame/resource contracts need extension, and provider tests.

Add interfaces for frame sources, template resources, OCR, and optional feature backends. Providers are adapters; algorithms remain independent of concrete screen capture and OCR packages. Unavailable providers must fail explicitly and be visible to configuration tooling.

Commit: `feat: add perception provider seams`

## Task P4: Add reusable algorithm adapters

Files: `core/perception/algorithms/shape.py`, `ocr.py`, `motion.py`, optional feature contracts, built-in descriptors, and tests.

Implement deterministic shape and frame-motion adapters where dependencies already exist. Add OCR and feature interfaces with explicit provider errors when no backend is installed. Do not add game-specific target names to algorithm implementations.

Commit: `feat: add perception algorithm adapters`

## Task P5: Connect runtime spatial mapping

Files: `core/spatial/`, runtime capture/window adapters, and mapping tests.

Keep recognition coordinates and screen action coordinates separate. Add runtime window/viewport metadata and anchor calibration without fixed-resolution offsets. Existing `MotionController` remains the compatibility action seam until tests cover a bridge.

Commit: `feat: connect runtime coordinate mapping`

## Task P6: Rewire the GUI through the engine

Files: `gui/dialogs/perception/`, focused GUI tests, and GUI architecture docs.

The workbench should import only the engine/profile/catalog public APIs. It may edit profiles and show evidence, but it must not construct detector classes directly or perform input actions.

Commit: `refactor: route workbench through perception engine`

## Task P7: Bridge existing targets one at a time

Files: one existing Portal, Loot, or minimap adapter plus regression tests per commit.

Adapt outputs to `TargetDetection` while preserving old thresholds, event memory, navigation scheduling, and canonical imports. Keep legacy adapters isolated and reversible.

## Task P8: Extract workflow orchestration

Files: `application/workflows/` or the repository's existing workflow package, navigation frame-loop adapters, and one workflow test per target.

Implement map device, map selection, waystone, enter-map, clear-map, loot, and trial workflows. Workflows request targets, select candidates, map coordinates, execute actions, verify state, and expose retry/timeout behavior. They never call algorithm classes.

## Task P9: Audit and release gate

Files: audit tests, `CODEBASE.md`, `ITERATION_LOG.md`, and checkpoint document.

Run focused tests, the complete discoverable suite, compile checks, import checks, dependency scans, and a manual smoke check. Classify every failure as introduced, pre-existing, or environmental. Do not mark complete while any newly introduced error remains.
