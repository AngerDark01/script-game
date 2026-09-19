# 游戏业务域与通用引擎分离实施计划

## Goal

将火炬之光的传送门、掉落、跟随和技能业务从通用 `core`/应用散点迁移到 `features/torchlight`，保留通用识别、定位、路径、动作和事件运行时，并与 PoE2 形成平级业务域。

## Architecture Overview

- `core/` 只包含与游戏无关的引擎和通用领域运行时。
- `features/torchlight/` 拥有火炬之光业务规则、模型标签、事件和策略。
- `features/poe2/` 拥有 PoE2 业务规则；已有 PoE2 适配器和 UI 修改保持不变。
- `adapters/` 只提供可复用的外部连接；真实副作用由装配层注入。
- `tools/experiments/<game>/` 只保留游戏实验，生产代码不能导入它。
- 迁移按业务域逐步完成，每个阶段都有边界测试和聚焦回归。

## Tech Stack

- Python 3.12
- NumPy/OpenCV/PySide6
- pytest
- Serena Python symbol navigation
- CodeGraph architecture and call-path analysis
- C# services remain under `services/` and are not moved in this phase

## Task 0: Record the Existing Worktree Boundary

Files: `git` metadata only; no source edits.

Before any move, record the current branch, commit, tags, and pre-existing changes. Do not reset, checkout, or clean the worktree. The existing PoE2 files modified by the user remain part of the working tree and are not included in a rollback operation.

Verify:

```powershell
git status --short
git log -2 --oneline --decorate
git tag --list 'pre-reorg/*'
```

Expected: current user changes are visible; `pre-reorg/2026-09-18` remains present.

Commit: no commit; preserve the user's existing worktree state.

## Task 1: Add Architecture Boundary Tests

Files:

- `tests/test_architecture_boundaries.py`
- `src/auto_modules/features/__init__.py`
- `src/auto_modules/features/torchlight/__init__.py`
- `src/auto_modules/features/poe2/__init__.py`

Add the package markers:

```python
"""Game-specific business domains."""
```

Add a test that scans only production Python files and rejects forbidden dependency directions:

```python
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "auto_modules"


def _imports(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_core_does_not_import_application_adapters_ui_or_features():
    forbidden = re.compile(r"(?:from|import) auto_modules\\.(?:application|adapters|ui|features)(?:\\.|\\s|$)")
    violations = []
    for path in (SOURCE / "core").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for line_number, line in enumerate(_imports(path).splitlines(), 1):
            if forbidden.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert not violations, "\\n".join(violations)


def test_production_code_does_not_import_tools():
    violations = []
    for path in SOURCE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for line_number, line in enumerate(_imports(path).splitlines(), 1):
            if re.search(r"(?:from|import) tools(?:\\.|\\s|$)", line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert not violations, "\\n".join(violations)
```

Verify:

```powershell
python -m pytest -q tests/test_architecture_boundaries.py
```

Expected: the test initially reports existing feature imports that must be migrated, then passes after Tasks 3-7.

Commit: `test: define game-domain import boundaries`

## Task 2: Create Public Feature Package Surfaces

Files:

- `src/auto_modules/features/torchlight/__init__.py`
- `src/auto_modules/features/torchlight/portal/__init__.py`
- `src/auto_modules/features/torchlight/loot/__init__.py`
- `src/auto_modules/features/torchlight/follow/__init__.py`
- `src/auto_modules/features/torchlight/skills/__init__.py`
- `src/auto_modules/features/torchlight/composition.py`
- `src/auto_modules/features/poe2/__init__.py`
- `src/auto_modules/features/poe2/live_terrain/__init__.py`
- `src/auto_modules/features/poe2/composition.py`

Use empty public surfaces until each domain is migrated:

```python
"""Torchlight-specific business feature."""

__all__: tuple[str, ...] = ()
```

Do not re-export implementation internals. Each later task adds only the domain contracts needed by callers.

Verify:

```powershell
python -c "import auto_modules.features.torchlight, auto_modules.features.poe2"
```

Expected: imports complete without importing UI, adapters, or tools.

Commit: `refactor: add game feature package boundaries`

## Task 3: Move Generic Event Runtime Out of Feature-Named Code

Files:

- `src/auto_modules/core/events/follow_chain.py`
- `src/auto_modules/core/events/automation/action_sequence.py` (new)
- `tests/test_action_sequence.py` (new)
- `tests/test_follow_chain.py`
- `tests/test_event_button_chords.py`

First add a failing test for a domain-neutral ordered action sequence. The new contract must produce event-neutral actions and use the existing `ActionTarget`/`ActionRequest` model rather than embedding a Torchlight rule. Then move the reusable validation, branching, retry, wait, and emit runtime into `ActionSequenceDefinition` and `ActionSequenceHandler`.

The legacy `FollowChainDefinition` remains only as a thin Torchlight-facing compatibility wrapper during the migration and is removed after the feature imports are updated. If the current contract cannot be made domain-neutral without retaining `follow` terminology, keep it in the Torchlight feature instead of forcing it into `core`.

Verify:

```powershell
python -m pytest -q tests/test_action_sequence.py tests/test_follow_chain.py tests/test_event_button_chords.py
```

Expected: generic sequence tests and existing event tests pass without importing Torchlight modules.

Commit: `refactor: isolate generic action sequence runtime`

## Task 4: Migrate Torchlight Portal

Files:

- All production files under `src/auto_modules/core/events/types/portal/`
- `src/auto_modules/features/torchlight/portal/`
- `src/auto_modules/ui/modes/torchlight/portal/` (new)
- `tests/test_portal_*.py`
- `tools/probes/event_icon_probe.py`
- `tools/probes/portal_screen_probe.py`

Move portal-specific definitions, config, model/template assets, detector, handler, completion rules, and diagnostics under `features/torchlight/portal`. Update imports to the feature public surface. Keep generic `TargetDetection`, template matching, coordinate mapping, navigation tasks, and action contracts in `core`.

The feature public API should expose only the composition contract, for example:

```python
from .definition import TorchlightPortalFeature

__all__ = ["TorchlightPortalFeature"]
```

The feature may depend on `auto_modules.core.*`, but `core` must not import it.

Verify:

```powershell
python -m pytest -q tests -k "portal or event_perception"
rg -n --glob '*.py' 'core\\.events\\.types\\.portal|events/types/portal' src tests tools
```

Expected: portal-focused tests pass; the search returns only migration notes or no production imports.

Commit: `refactor: move Torchlight portal feature out of core`

## Task 5: Migrate Torchlight Loot and Its Evaluation Tools

Files:

- All production files under `src/auto_modules/core/events/types/loot/`
- `src/auto_modules/features/torchlight/loot/`
- `tools/debug/loot_*.py`
- `tools/experiments/torchlight/loot/`
- `tests/test_loot_*.py`
- `resources/games/torchlight/loot/`
- `data/games/torchlight/loot/`

Move loot-specific templates, player-marker exclusions, detector modes, feature scoring, pickup handlers, and diagnostics into the Torchlight domain. Keep reusable image operations, feature backend contracts, bounding boxes, and detector runner in `core/perception`.

Update debug/evaluation tools to import the feature public API. They remain opt-in tools and must not be imported by production packages.

Verify:

```powershell
python -m pytest -q tests -k "loot or perception"
rg -n --glob '*.py' 'core\\.events\\.types\\.loot|from tools|import tools' src tests
```

Expected: loot/perception tests pass; no production source imports `tools` or the old loot path.

Commit: `refactor: move Torchlight loot feature out of core`

## Task 6: Migrate the Torchlight Follow Script

Files:

- `src/auto_modules/application/follow/`
- `src/auto_modules/core/routing/follower_planner.py`
- `src/auto_modules/core/diagnostics/follow_replay.py`
- `src/auto_modules/core/diagnostics/follow_benchmark.py`
- `src/auto_modules/features/torchlight/follow/`
- `src/auto_modules/ui/modes/follow/`
- `src/auto_modules/ui/modes/torchlight/follow/`
- `tests/test_follow_*.py`

Move the script-specific controller, workers, configuration, replay, benchmark, and follower policy into `features/torchlight/follow`. Keep generic pathfinder, localization, geometry, route projection, and action contracts in `core`.

If a follow chain is only a general timed action sequence, use the Task 3 runtime. If it includes Torchlight skill/return semantics, keep the wrapper in `features/torchlight/skills`.

Verify:

```powershell
python -m pytest -q tests -k "follow"
rg -n --glob '*.py' 'application\\.follow|core\\.routing\\.follower_planner|core\\.diagnostics\\.follow_' src tests tools
```

Expected: follow tests pass; remaining references are only explicit migration compatibility points until removed in the same task.

Commit: `refactor: move Torchlight follow script into game domain`

## Task 7: Move Game-Specific UI and Composition

Files:

- `src/auto_modules/ui/modes/navigation/event_adapter.py`
- `src/auto_modules/ui/modes/torchlight/`
- `src/auto_modules/application/composition/torchlight.py`
- `src/auto_modules/application/composition/poe2.py`
- `src/auto_modules/ui/main_window.py`
- `tests/test_main_window_*.py`

Move Torchlight event registration out of the generic navigation UI. Add a Torchlight composition entry point that registers portal, loot, follow, and skills. UI modes call the public feature surface and never import feature internals through `core.events.types.*`.

The PoE2 page continues to use its existing independent adapter and UI service; this task only adds the sibling composition boundary.

Verify:

```powershell
python -m pytest -q tests -k "main_window or navigation or event"
rg -n --glob '*.py' 'PortalEventDefinition|LootEventDefinition' src/auto_modules/ui/modes/navigation
```

Expected: generic navigation UI no longer owns Torchlight event registration.

Commit: `refactor: isolate game UI composition roots`

## Task 8: Rehome Models, Templates, Config, and Experiments

Files:

- `resources/assets/` game-specific model/template files
- `data/events/events.json`
- `data/events/routes.json`
- `tools/experiments/torchlight/`
- `tools/experiments/poe2/`
- `README.md`
- `ARCHITECTURE_GUIDE.md`

Move only files proven to belong to a game. Preserve generic OCR models and provider resources where they are used by multiple domains. Do not create `tools/training/common` abstractions until a second domain consumes them.

Verify:

```powershell
python -m pytest -q tests/test_runtime_paths.py tests/test_distribution.py
python -m compileall -q src tests tools packaging
```

Expected: path and packaging tests pass, and production import discovery does not include experiment directories.

Commit: `refactor: align game resources and experiments`

## Task 9: Remove Old Feature Locations and Enforce Public APIs

Files:

- Old portal/loot/follow files after all imports are migrated
- `src/auto_modules/features/*/__init__.py`
- `tests/test_architecture_boundaries.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Delete only source files that have no remaining references. Do not delete the rollback tag or unrelated user files. Add import checks for the final public APIs and update the living architecture documentation with exact feature ownership and data flows.

Verify:

```powershell
rg -n --glob '*.py' 'from core |from gui |from workflows |from logging_system |core\\.events\\.types\\.(portal|loot)|application\\.follow' src tests tools main.py
python -m pytest -q
python -m compileall -q src tests tools packaging
```

Expected: no old production imports; known Pathfinder behavior failures and missing local dependency metadata remain separately documented if still present.

Commit: `refactor: finalize game-domain boundaries`

## Task 10: CodeGraph and Serena Synchronization

Files:

- `.codegraph/` generated index files
- `.serena/` project metadata if required by activation
- `CODEBASE.md`
- `ITERATION_LOG.md`

Run CodeGraph exploration for the new feature roots, activate the Serena project, and update the living architecture inventory. Record direct changes, callers, affected contracts, and residual risks. Do not report completion until the new imports and public symbols are indexed.

Verify:

```powershell
codegraph explore "Torchlight feature roots, generic perception contracts, composition entry points, and old import paths"
python -m pytest -q tests/test_architecture_boundaries.py
git status --short
```

Expected: feature roots and contracts are discoverable; only intentional user changes and this refactor's changes remain in the worktree.

Commit: `docs: synchronize game-domain architecture inventory`
