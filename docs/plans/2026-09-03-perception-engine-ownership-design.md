# Perception Engine Ownership Design

## Goal

Make `PerceptionEngine` the actual game-agnostic execution core: it owns detector execution, generic candidate decisions, and short-lived confirmation state, while the old `PerceptionPipeline` remains only a source-compatible forwarding entry point.

## Approved architecture

The user-approved dependency direction is:

```text
GUI / workflow
  -> PerceptionEngine
       -> DetectorRunner
       -> fuse_candidates
       -> ConfirmationTracker
       -> select_candidate
  -> PerceptionRunResult

legacy caller -> PerceptionPipeline -> PerceptionEngine
```

`PerceptionEngine` remains independent of GUI, action/input, navigation, game identifiers beyond profile data, and concrete provider implementations. `PerceptionPipeline` retains its class and method names so existing code imports continue to work, but it cannot own policy, a detector runner, or a confirmation tracker.

The engine continues to accept an explicitly injected legacy `PerceptionPipeline` for compatibility with the P1 constructor contract. That opt-in branch is a bridge only; the default constructor is the required direct-core path. P9 will decide whether the deprecated injection seam can be removed after an import audit.

## Alternatives considered

| Approach | Result | Decision |
|---|---|---|
| Keep Pipeline as composer and present Engine as facade | Smallest immediate diff, but makes the legacy name the real core and hides stage state from the engine. | Rejected. |
| Move composition to Engine; make Pipeline a forwarding adapter | Preserves old imports while making the intended core explicit and testable. | Selected. |
| Delete Pipeline now | Simplest dependency graph, but unnecessarily breaks old callers before the compatibility audit. | Deferred. |

## Tech stack

- Python 3.12 in `D:/ACloud/.venv`
- Standard-library `unittest`
- Existing NumPy/OpenCV detector adapters; no new third-party dependency

## Atomic TDD tasks

### Task 1 — Prove the default engine does not execute through Pipeline

**Files**

- `tests/test_perception_engine.py`

**Add the failing contract test**

```python
def test_default_engine_executes_stages_without_calling_compatibility_pipeline(self):
    engine = PerceptionEngine()
    frame, profile = self._red_marker_frame_and_profile()

    with patch.object(PerceptionPipeline, "run", side_effect=AssertionError("compatibility path used")):
        result = engine.detect(frame, profile)

    self.assertTrue(result.confirmed)
    self.assertEqual("marker", result.selected.target_type)
```

**Run before implementation**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_engine.PerceptionEngineTests.test_default_engine_executes_stages_without_calling_compatibility_pipeline -v
```

Expected before implementation: `FAIL` or `ERROR` with `compatibility path used`.

### Task 2 — Move default execution ownership to PerceptionEngine

**Files**

- `core/perception/engine.py`

**Required implementation shape**

```python
class PerceptionEngine:
    def __init__(self, registry=None, pipeline=None):
        self.registry = registry or (pipeline.registry if pipeline is not None else create_default_algorithm_registry())
        self._compatibility_pipeline = pipeline
        self.runner = None if pipeline is not None else DetectorRunner(self.registry)
        self.confirmation = None if pipeline is not None else ConfirmationTracker()

    def detect(self, frame, profile, *, reference=None):
        self._validate_detect_input(frame, profile)
        if self._compatibility_pipeline is not None:
            return self._compatibility_pipeline.run(frame, profile, reference=reference)
        return self._run_stages(frame, profile, reference=reference)
```

`_run_stages()` must preserve the existing, public behavior exactly: run enabled instances, filter below `profile.min_confidence`, use non-negative `metadata.merge_radius` with a default of `12.0`, confirm by `(game_id, scene_id, target_type)`, select from confirmed candidates, and return `PerceptionRunResult` with raw per-instance outputs and errors. `reset_confirmation()` must directly reset the engine tracker in the default branch and delegate only in the explicit legacy-pipeline branch.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_engine tests.test_perception_stages -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
```

Expected: all selected tests pass and compile command has no output.

### Task 3 — Prove Pipeline is a forwarding compatibility shell

**Files**

- `tests/test_perception_pipeline.py`

**Add the failing contract test**

```python
def test_pipeline_forwards_to_its_engine(self):
    pipeline = PerceptionPipeline(self.registry)
    expected = PerceptionRunResult(())
    with patch.object(pipeline.engine, "detect", return_value=expected) as detect:
        actual = pipeline.run(self.frame, self.profile)

    self.assertIs(expected, actual)
    detect.assert_called_once_with(self.frame, self.profile, reference=None)
```

**Run before implementation**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_pipeline.PerceptionPipelineTests.test_pipeline_forwards_to_its_engine -v
```

Expected before implementation: `ERROR` because `PerceptionPipeline` has no forwarding engine.

### Task 4 — Reduce Pipeline to forwarding only and finalize P2

**Files**

- `core/perception/pipeline.py`
- `core/perception/engine.py` (only if import-cycle compatibility requires a local import)
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`
- `ITERATION_LOG.md`
- `CODEBASE.md`

**Required implementation shape**

```python
class PerceptionPipeline:
    def __init__(self, registry):
        self.registry = registry
        self.engine = PerceptionEngine(registry)

    def run(self, frame, profile, *, reference=None):
        return self.engine.detect(frame, profile, reference=reference)

    def reset_confirmation(self, profile=None):
        self.engine.reset_confirmation(profile)
```

Keep `_fuse_candidates()` as the existing compatibility wrapper. Do not import GUI/action code and do not duplicate thresholds, fusion, confirmation, or selection logic in this file.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_stages tests.test_perception_pipeline tests.test_perception_engine tests.test_perception_models -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
git diff --check
```

Expected: all focused tests pass, compile has no output, and `git diff --check` reports no whitespace error.

**Commit checkpoint**

```text
feat: make perception engine own decision stages
```

## Non-goals

- Do not connect screen capture, OCR, feature matching, or template files yet; those are P3/P4 provider work.
- Do not change GUI workbench calls yet; that is P6.
- Do not bridge Portal, Loot, minimap, map-device, or PoE workflows before their dedicated regression slices.
- Do not alter any `virtual_gamepad/` file.
