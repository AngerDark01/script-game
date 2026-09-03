# Perception Engine Task Checkpoint

This document is the recovery point for the reusable perception architecture. Update it after every meaningful task, test run, or architecture decision.

## Current Baseline

- Repository: `auto_modules`
- Branch: `main`
- Latest committed UI change: `b988851 fix: keep perception entry compact`
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
- Initial candidate fusion in `core/perception/pipeline.py`.
- Coordinate transform primitives in `core/spatial/`.
- Screenshot-oriented GUI workbench in `gui/dialogs/perception/`.

### Explicitly Missing

- A named, stable `PerceptionEngine` facade.
- Separate runner, fusion, confirmation, and selection modules.
- Provider seams for frame input, OCR, template resources, and optional feature backends.
- Real shape, OCR, feature, and motion implementations or provider contracts.
- Runtime screen capture and automatic window/viewport calibration integration.
- Portal, Loot, map-device, waystone, trial, and scene-transition bridges.
- Workflow orchestration for the complete event chain.

## Ordered Task Queue

| ID | Task | Status | Commit checkpoint |
|---|---|---|---|
| P0 | Checkpoint, plan, and codebase documentation | in progress | `docs: establish perception engine checkpoints` |
| P1 | Perception engine contract and facade | pending | `feat: add perception engine facade` |
| P2 | Detector runner, fusion, confirmation, selection seams | pending | `feat: split perception decision stages` |
| P3 | Frame/resource/OCR provider contracts | pending | `feat: add perception provider seams` |
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

## Audit Notes

- Targeted perception and navigation tests currently pass when run with the project virtual environment.
- Full test discovery still reports legacy import-path errors in unrelated older tests; these must be re-audited in P9 rather than silently ignored.
