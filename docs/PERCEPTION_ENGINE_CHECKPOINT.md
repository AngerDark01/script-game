# Perception Engine Task Checkpoint

This document is the recovery point for the reusable perception architecture. Update it after every meaningful task, test run, or architecture decision.

## Current Baseline

- Repository: `auto_modules`
- Branch: `main`
- Current perception implementation checkpoint: `feat: add optional RapidOCR provider` (the commit carrying this document).
- Earlier perception foundation commits: `1afb9f4` through `c6d0698`
- Current worktree contains unrelated, uncommitted `virtual_gamepad/` changes. Do not mix them into perception commits.

## User Outcome

Build a game-agnostic visual automation foundation where reusable algorithms are configured as instances and composed by `game -> scene -> target`. Workflows ask for targets and state verification; they do not call color, template, OCR, or other algorithm implementations directly.

## Architecture Contract

```text
FrameSource / provider
  -> PerceptionEngine
       -> detector runner
       -> candidate fusion
       -> multi-frame confirmation
       -> selection policy
  -> TargetDetection
  -> CoordinateMapper
  -> Action adapter / workflow
  -> State verification
```

Dependency direction:

```text
gui -> application/workflows -> core.perception / core.spatial -> providers
core.perception -/-> gui, input actions, navigation policy, game-specific modules
```

## Status

### Completed

- Generic result models in `core/perception/models.py`.
- Versioned algorithm and target profiles in `core/perception/profiles.py` and `profile_store.py`.
- Descriptor-based registry in `core/perception/registry.py`.
- Color and template detector implementations.
- Engine-owned runner, fusion, confirmation, and selection stages with a Pipeline forwarding bridge.
- Typed frame/template/OCR/feature provider contracts, capability-safe registry, and discovery-only default catalog.
- Optional `RapidOcrProvider`: cached local ONNX OCR, text-polygon-to-`OcrSpan` conversion, ROI crop/full-frame coordinate restoration, and a concrete provider-to-adapter regression suite.
- Coordinate transform primitives in `core/spatial/`.
- Screenshot-oriented GUI workbench in `gui/dialogs/perception/`.

### Explicitly Missing

- Concrete frame capture, template resource, feature, and motion adapters.
- Runtime screen capture and automatic window/viewport calibration integration.
- Portal, Loot, map-device, waystone, trial, and scene-transition bridges.
- Workflow orchestration for the complete event chain.

## Ordered Task Queue

| ID | Task | Status | Commit checkpoint |
|---|---|---|---|
| P0 | Checkpoint, plan, and codebase documentation | complete | `docs: establish perception engine checkpoints` |
| P1 | Perception engine contract and facade | complete | `feat: add perception engine facade` |
| P2 | Detector runner, fusion, confirmation, selection seams | complete | `feat: split perception decision stages` |
| P3 | Frame/resource/OCR provider contracts | complete | `feat: add perception provider seams` |
| P4 | Reusable algorithm adapters and capability states | in progress | `feat: add reusable template algorithm adapters` |
| P5 | Runtime coordinate mapping and calibration adapter | in progress | desktop OCR-to-action proof slice |
| P6 | Rewire GUI workbench through engine public API | pending | `refactor: route workbench through perception engine` |
| P7 | Legacy Portal/Loot/minimap bridges | pending | one target per commit |
| P8 | Workflow modules for the event chain | pending | one workflow per commit |
| P9 | Full dependency, regression, and error audit | pending | `test: complete perception architecture audit` |

## Verification Policy

- Every implementation task starts with a failing or contract-focused test.
- Run focused `unittest` tests and `compileall` after each task.
- Preserve canonical imports and old Portal/Loot/navigation behavior.
- Do not add a mandatory OCR or ML dependency without an explicit provider.
- Never force-push over remote history.
- Record test counts, known pre-existing failures, and new findings below.

## Progress Log

### 2026-09-03 - Reframed the task around the missing engine

- Finding: the existing `PerceptionPipeline` is an initial implementation, not the complete engine requested by the user.
- Decision: introduce a named `PerceptionEngine` and deepen the internal stages behind it.
- Decision: keep existing minimap-specific code as compatibility adapters until each target has regression coverage.
- Next: implement P1 with a small public interface and tests before touching GUI or workflows.

### 2026-09-03 - P1 started

- Scope: add the first stable, GUI-free `PerceptionEngine` facade.
- Contract: profiles are registered and resolved by `(game_id, scene_id, target_type)`; detection accepts a `FrameContext` and `TargetProfile` and returns `PerceptionRunResult`.
- Compatibility rule: the current `PerceptionPipeline` remains the implementation behind the facade until P2 separates its decision stages.
- Next: write the contract test, then implement only the facade and package export.

### 2026-09-03 - P1 complete

- Added `core/perception/engine.py` with a stable `PerceptionEngine` facade.
- The facade registers defensive profile copies by `(game_id, scene_id, target_type)` and resolves them explicitly.
- `detect()` validates the normalized frame/profile contract and delegates to the compatibility pipeline.
- Tests: 3 P1 contract tests pass; compile check passes.
- Next: P2 separates detector execution, fusion, multi-frame confirmation, and candidate selection behind engine-owned stages.

### 2026-09-03 - P2 started

- Scope: extract the four decision stages currently combined in `PerceptionPipeline`.
- Compatibility rule: `PerceptionPipeline` remains the public compatibility class and composes the new stages; existing callers and default one-frame behavior must remain unchanged.
- Confirmation rule: profiles with `confirmation_frames > 1` expose `confirmed=False` until spatially stable candidates meet the configured frame count.
- Selection rule: selection is an explicit result field and never triggers input actions.

### 2026-09-03 - P2 completion gate: engine ownership

- The runner, fusion, confirmation, and selection modules now exist and their targeted contract tests pass.
- Review finding: the default `PerceptionEngine` still delegates to `PerceptionPipeline`, so the legacy layer still owns stage state.
- Approved correction: the default engine will directly compose the four stages; `PerceptionPipeline` will forward `run()` and `reset_confirmation()` to an engine instance.
- Detailed implementation/recovery plan: `docs/plans/2026-09-03-perception-engine-ownership-design.md`.
- Do not mark P2 complete or start P3 until the direct-engine and compatibility-forwarding red/green tests both pass.

### 2026-09-03 - P2 complete

- Default `PerceptionEngine` directly owns `DetectorRunner`, candidate filtering/fusion, `ConfirmationTracker`, candidate selection, and confirmation reset.
- `PerceptionPipeline` is now a source-compatible forwarding shell; it retains only registry ownership, an engine instance, `run()`, `reset_confirmation()`, and the old `_fuse_candidates()` import wrapper.
- Target-type boundary, profile selection-policy validation, profile-replacement reset, direct-engine ownership, and Pipeline forwarding are all regression-tested.
- Verification: 17 focused perception tests passed; `compileall -q core/perception`, public import smoke check, and `git diff --check` completed without errors.
- Next: P3 provider seams for frames, templates, OCR, and feature backends. No GUI/legacy target/workflow bridge starts before those contracts exist.

### 2026-09-03 - P3 started

- Scope: declare typed providers for frame capture, template resources, OCR and feature backends, plus a capability-safe discovery/resolve registry.
- Boundary: providers return raw frames/resources/evidence; P4 adapters alone convert them to `TargetDetection`.
- Availability: unavailable providers remain visible in the catalog but `resolve()` must fail explicitly; P3 adds no mandatory OCR, ML, screen-capture, or feature package.
- Detailed design and test sequence: `docs/plans/2026-09-03-perception-provider-seams-design.md`.

### 2026-09-03 - P3 complete

- `providers/contracts.py` supplies raw DTOs and typed Protocols for frames, template assets, OCR spans, and feature matches; none carries target/action policy.
- `ProviderRegistry` explicitly separates unknown ID, capability mismatch, unavailable provider, and invalid registration errors; it stores objects without invoking them.
- The default catalog exposes four stable unavailable capability IDs so configuration UI can explain missing backends without treating any optional dependency as installed.
- Verification: 24 perception/provider tests passed; `compileall -q core/perception` and `git diff --check` passed, with only existing LF/CRLF warnings.
- Next: P4 adds adapters that consume these providers and normalize their evidence to `TargetDetection`; first implementation should be a resource-provider bridge for existing template matching.

### 2026-09-04 - P4 started: template resource adapter

- User selected the independent adapter approach: `TemplateResourceProvider.load(resource_id)` resolves a raw asset, then an adapter passes only `TemplateResource.image` into the unchanged `TemplateDetector` matching implementation.
- Compatibility rule: existing array and `template_path` parameters remain valid; a provider is required only for `template_resource_id`; ambiguous resource inputs fail explicitly.
- Runtime rule: provider objects are composition dependencies and never enter profile JSON. Profiles persist resource IDs/provider IDs only.
- Detailed design and TDD task sequence: `docs/plans/2026-09-04-template-resource-adapter-design.md`.

### 2026-09-04 - P4 template adapter slice complete

- `ProviderBackedTemplateDetector` resolves one `TemplateResource` through an explicit provider, then delegates only the image array to the existing `TemplateDetector`.
- `create_template_detector()` supports provider-backed resource IDs while preserving array and `template_path` sources; ambiguous and missing sources fail explicitly.
- `PerceptionEngine` accepts runtime algorithm factory overrides, keeping provider objects outside `TargetProfile` and JSON serialization.
- Verification: 32 focused provider/template/perception tests passed; package compilation and public import smoke checks passed.
- P4 remains in progress for future shape, OCR, feature, and motion adapters. Next slice must choose one concrete adapter and retain the same provider/algorithm boundary.

### 2026-09-04 - P4 OCR adapter slice complete

- `ProviderBackedOcrDetector` invokes an explicit `OcrProvider` per frame, filters raw `OcrSpan` values with generic exact, contains, or regular-expression text matching, then emits geometry-preserving `TargetDetection` values.
- The output retains original text, box, coordinate space, confidence, capture time, language, and raw span details. `min_ocr_confidence` filters spans before candidate fusion; optional `max_results` retains the strongest results, while `0` or omission keeps all matches.
- `create_ocr_detector()` requires an explicit runtime provider. `PerceptionEngine.algorithm_factories` composes it without serializing the provider into `TargetProfile` JSON. No OCR package or runtime backend is bundled; the default descriptor remains discoverable but unavailable and now exposes generic editor metadata.
- Verification: 42 focused provider/template/OCR/algorithm/engine/stage/pipeline tests passed; `compileall -q core/perception` passed. No GUI, capture, mapping, input, navigation, or workflow code changed.
- P4 remains in progress for shape, feature, and motion adapters. The next slice should select one adapter and retain the same raw-provider-to-target-detection boundary.

### 2026-09-04 - P4 shape adapter slice complete

- `ShapeDetector` is a provider-free OpenCV contour detector. It thresholds a frame, optionally applies morphology, derives external contour geometry, filters by generic area/vertex/circularity/solidity settings, and emits standardized geometry evidence.
- The default algorithm catalog now marks `shape` available because it uses only the existing OpenCV/NumPy baseline. It exposes editor metadata for thresholding, contour filters, and result limits. It does not modify target-specific Portal/Loot contour logic.
- Verification: 36 focused shape/color/template/OCR/engine/stage tests passed; `compileall -q core/perception` and `git diff --check` passed.
- P4 remains in progress for feature and motion adapters. A concrete optional OCR provider is separately being evaluated for fast text-box localization.

### 2026-09-04 - P4 concrete RapidOCR provider slice complete

- `core/perception/providers/rapidocr.py` adds the first executable OCR backend without changing the package's generic `OcrProvider` contract. It imports `rapidocr_onnxruntime` and creates the ONNX model only on the first `recognize()` call, then reuses that backend instance for subsequent frames.
- A full frame or JSON-configurable ROI now produces `OcrSpan` values whose `BoundingBox`, polygon metadata, and coordinate space are always expressed in the original `FrameContext` space. ROI-local RapidOCR polygons are offset before leaving the provider, so downstream detection, mapping, and action modules do not need special ROI logic.
- Per-instance OCR parameters still flow through `ProviderBackedOcrDetector`; RapidOCR receives only copied provider settings (`roi`, optional language label, and backend call options). Profiles remain serializable and do not contain a model object.
- The dependency is intentionally optional in `requirements-ocr.txt`; importing `core.perception` remains side-effect-free for users who do not install OCR. The default provider catalog advertises `ocr.rapidocr_onnxruntime` as unavailable until application composition supplies a real provider.
- Verification: a red import-contract test first failed as expected; 6 RapidOCR-focused tests then passed, including lazy engine-option application and a real generated-image text-location smoke test. Follow-up provider/catalog coverage passed 12/12; the complete perception suite now passes 68/68. The remaining P4 work is feature and motion adapters; GUI wiring remains P6.

### 2026-09-04 - P4 Traditional-Chinese RapidOCR model resource slice complete

- The first named recognition asset, `rapidocr.ppocr-v6-multilingual-small`, is now a source-controlled manifest entry with a versioned URL and SHA-256. It is deliberately not an embedded ONNX binary and does not change the optional-dependency boundary.
- `resolve_rapidocr_engine_options()` validates a locally installed model before returning a fresh `RapidOcrProvider.engine_options` mapping. It fixes `rec_model_path` to the verified resource while allowing copied host-level tuning options such as ONNX thread counts. The resolver is target/game/workflow agnostic.
- `utils/install_perception_ocr_model.py` is an explicit direct-execution CLI. It downloads to a same-directory temporary file, verifies before atomic replacement, preserves an old file when a replacement fails, and works both as a utility script and a test-imported module. Downloaded assets under `assets/perception_models/` are Git-ignored.
- Verification: the six offline model-resource tests pass; the installer direct-execution regression passes; and the optional real smoke test in the project virtual environment correctly recognizes `開始儀式` and `進入異界地圖` while preserving their full-image bounding boxes. The default bundled Chinese model was not silently replaced; application composition selects this model only where a Traditional-Chinese OCR provider is wanted.
- Next: expose model selection through the future perception workbench/application composition UI (P6) without putting provider objects or raw local file paths into serializable target profiles.

### 2026-09-04 - P5 desktop OCR-to-action mapping proof slice complete

- Added the first explicit distinction between a captured `FULL_SCREEN` image plane and a `PHYSICAL_SCREEN` input-injection plane. `DesktopCoordinateMapper` uses an existing affine transform to derive source-image-to-desktop scale and offset, preserves transform evidence in `MappedPoint`, and refuses invalid spaces or out-of-bounds coordinates instead of silently clamping.
- Added `DesktopFrameSource` plus a Windows virtual-desktop geometry provider. The source captures one complete desktop image and emits a dimensioned `FrameContext` paired with physical bounds and DPI observation. On Windows it establishes per-monitor DPI awareness before geometry/capture/input composition; this order is mandatory because Win32 coordinates otherwise become DPI virtualized.
- Added the separate `core.actions` boundary: `ActionRequest` and `ActionResult` are device-neutral, while `MouseActionAdapter` accepts only a mapped physical point and performs move or exactly one double-click through a minimal mouse protocol. No perception, target text, screen capture, window focus, or navigation policy enters this package.
- Added the thin `DesktopOcrActionProof` workflow and its explicit CLI. It is the only composition point for exact OCR matching, mapper selection, and a double-click request. By default it is dry-run; zero/multiple matches and rejected mappings never reach the action adapter.
- Live verification on the current desktop: MSS capture and virtual geometry both reported `2560x1600` at 150% DPI; the multilingual OCR model found the unique `梦之形` label at `(633.55, 532.05)` with `0.99995` confidence; the mapped physical point was unchanged; and the Win32 adapter executed one double-click at `(634, 532)`. A follow-up read-only foreground-window diagnostic found the launched SDL application.
- Verification: 76 perception tests and 5 new desktop mapping/action/workflow tests pass; compile and public-import checks pass; repeated live dry-run returns the same detection/mapping report. P5 remains in progress for game-window/viewport calibration, multi-display selection policy, and GUI calibration controls.

### 2026-09-04 - Legacy minimap/event integration audit

- Verified correction: the older Torchlight-oriented minimap, localization, navigation, Portal, and Loot paths are **not** already using the new generic perception/spatial/action architecture. The new engine currently coexists beside them.
- Legacy minimap localization accepts a raw cropped minimap array, asks `HSVRecognizer` for domain-specific masks, mutates `NavigationCore`, and returns an untyped stitched-world position/confidence tuple. Its preprocessing has partial internal decomposition but is driven by mutable recognizer state and includes player-center/minimap assumptions.
- Legacy Portal and Loot detectors consume `EventTick.raw_minimap_frame`, own game-specific resource loading, preprocessing, algorithm fallback, temporal state, and output `EventDetection(local_minimap_pos, ...)`. Their event handlers emit legacy `EventAction` values, while the GUI-owned `MotionController` still converts navigation/world positions to clicks and sends input.
- `core/mapping/MapStitcher` is a retainable map-domain core: it independently performs keyframe/frame registration, phase-displacement positioning, wall/fog/exploration weighted merge, and persisted map packages from supplied masks/player position. But `gui/modes/mapping/runtime/session.py` currently captures the old minimap, calls `HSVRecognizer.extract_combined()`, and passes raw arrays/tuples into it. Map construction therefore has no new `FrameContext`/artifact/coordinate contract yet.
- Keep the existing algorithms and handler state machines for compatibility. Do not rewrite them into the generic modules. P7 must add narrow bridges: raw legacy evidence/`EventDetection` to standardized `TargetDetection` where appropriate; explicit stitched-map/global-position projection; and `EventAction`/`NavigationIntent` to the device-neutral `core.actions` boundary. Each target moves only after regression comparison with its old path.
- Preprocessing is now an explicit prerequisite seam: generic image operations and geometry-preserving artifacts should be extracted under `core/perception/preprocessing/`, while Portal/Loot/minimap semantic rules remain profile/adapter policy. This extraction is separate from adding more feature/motion/ML algorithms.

## Audit Notes

- Targeted perception and navigation tests currently pass when run with the project virtual environment.
- Full test discovery still reports legacy import-path errors in unrelated older tests; these must be re-audited in P9 rather than silently ignored.

## 2026-09-04 — Legacy mapping runtime composition migrated

- `gui/modes/mapping/runtime/session.py` is now the first live legacy composition root migrated to a new typed contract: it captures and recognizes exactly as before, then creates `MapFrameEvidence` and calls `MapStitcher.add_evidence(...)`.
- `MapStitcher.add_frame(...)` remains the compatibility implementation. This migration deliberately does not alter minimap HSV semantics, registration, merge behavior, player fallback, or GUI display data.
- Focused regression coverage confirms that the evidence object retains the exact original image/mask/raw-gray objects and player coordinates. The next old-chain candidate is localization result typing, followed by navigation/action dispatch, Portal, and Loot bridges.

## 2026-09-04 — Legacy localization result bridge migrated

- `core.localization.LocalizationResult` is the core-owned, immutable result schema for one legacy minimap localization call: it carries a `GLOBAL_MAP` position (or `None`), confidence, registration source/validity, and a copied metadata snapshot.
- `NavigationCore.localize_result(...)` calls the old `localize(...)` exactly once and adapts only its final three-value result plus the already-written `FrameRegistration`. The old public tuple API and the F2F/template/HSV algorithm remain unchanged.
- `capture_navigation_localization_tick(...)` now receives and returns that core object directly. `NavigationLocalizationResult` stays as an unused compatibility DTO for external callers and accepts both result shapes.
- Focused tests protect single delegation, registration-metadata copying, `GLOBAL_MAP` semantics, and the UI-independent navigation runtime composition. The next slice is action-dispatch translation (`NavigationIntent` / `EventAction` to the device-neutral action boundary); Portal/Loot perception remains separate.

### Current full-suite audit note

- `python -m unittest discover -s tests` ran 170 tests: 166 passed, 2 skipped, 3 `PathFinder` assertions failed, and one advanced-settings test import failed. None uses `LocalizationResult` or the migrated capture tick.
- The advanced-settings failure is a test-loader issue: `tests/test_advanced_settings_file_io.py` executes `gui/dialogs/advanced_settings/file_io.py` outside its package, so its relative import fails.
- The three `PathFinder` failures concern blocked-corner diagonal traversal, unexplored-area walkability, and strict thin-wall expectations. Their policy must be audited separately; do not alter the localization migration to make unrelated legacy tests green.
