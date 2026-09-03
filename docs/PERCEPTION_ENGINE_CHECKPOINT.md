# Perception Engine Task Checkpoint

This document is the recovery point for the reusable perception architecture. Update it after every meaningful task, test run, or architecture decision.

## Current Baseline

- Repository: `auto_modules`
- Branch: `main`
- Latest committed perception baseline: `6f60d12 feat: split perception decision stages`
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
- Coordinate transform primitives in `core/spatial/`.
- Screenshot-oriented GUI workbench in `gui/dialogs/perception/`.

### Explicitly Missing

- Concrete frame capture, template resource, OCR, feature, shape, and motion adapters.
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
| P4 | Reusable algorithm adapters and capability states | pending | `feat: add perception algorithm adapters` |
| P5 | Runtime coordinate mapping and calibration adapter | pending | `feat: connect runtime coordinate mapping` |
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

## Audit Notes

- Targeted perception and navigation tests currently pass when run with the project virtual environment.
- Full test discovery still reports legacy import-path errors in unrelated older tests; these must be re-audited in P9 rather than silently ignored.
