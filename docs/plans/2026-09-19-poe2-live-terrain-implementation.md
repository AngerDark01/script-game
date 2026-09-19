# PoE2 实时地形预览实施计划

## 实施状态（2026-09-19）

本计划的第一阶段已完成。实际运行时适配器位于
`src/auto_modules/adapters/poe2_live_terrain/`；计划中列出的
`tools/experiments/poe2_live_terrain/` 现作为兼容导出层保留，测试和正式 UI
均直接使用 `auto_modules.adapters.poe2_live_terrain`。自动跟随、定位、路径
规划、动态障碍和真实输入仍未实现。

## Goal

实现 PoE2 专属的手动初始化/抓取/内存转换/地图展示页面，不接入自动跟随、输入或正式离线地图。

## Architecture Overview

外部 `live_preview.py` 保持独立；`tools/experiments/poe2_live_terrain` 提供可测试的协议、NPZ 转换、命令适配和内存服务；`src/auto_modules/ui/modes/poe2_live_terrain` 提供注入式 PySide6 页面；`MainWindow` 只负责添加按钮和页面。所有 Python 导入使用 `auto_modules.*`，不创建旧顶层包。

## Tech Stack

Python 3.12、NumPy、PySide6、pytest、现有 `ScalableMapWidget` 与 `auto_modules.paths`。真实 PoE2 只在明确的手动验收阶段运行。

## Tasks

### Task 1: Freeze the in-memory terrain contract

Files:

- Add `tools/experiments/__init__.py`.
- Add `tools/experiments/poe2_live_terrain/__init__.py`.
- Add `tools/experiments/poe2_live_terrain/contracts.py`.
- Add `tests/poe2_live_terrain/__init__.py`.
- Add `tests/poe2_live_terrain/test_contracts.py`.

Implementation: define frozen `TerrainSnapshot`, `CaptureMetadata`, `TerrainSessionState`, `TerrainCaptureError`, and a read-only NumPy-array helper. Validate `yx` arrays are two-dimensional, shapes agree, and copy arrays before exposing them. Do not include a player position.

Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_contracts.py -q
# Expected: contract validation and read-only-copy tests pass.
```

### Task 2: Convert and validate the native grid export

Files:

- Add `tools/experiments/poe2_live_terrain/native_grid.py`.
- Add `tests/poe2_live_terrain/test_native_grid.py`.

Implementation: load NPZ with `allow_pickle=False`; require `raw_cells`, `cell_state`, `known_mask`, `wall_layer`, `explored_map`, `metadata_json`; parse scalar metadata JSON; preserve `height x width` native `yx` order; validate dtype/shape and return `TerrainSnapshot`.

Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_native_grid.py -q
# Expected: valid synthetic NPZ passes; missing key, bad shape, pickle and bad JSON fail closed.
```

### Task 3: Add the external command adapter and memory service

Files:

- Add `tools/experiments/poe2_live_terrain/capture_adapter.py`.
- Add `tools/experiments/poe2_live_terrain/session.py`.
- Add `tools/experiments/poe2_live_terrain/memory_store.py`.
- Add `tests/poe2_live_terrain/test_session.py`.
- Add `tests/poe2_live_terrain/test_capture_adapter.py`.
- Add `tests/poe2_live_terrain/test_memory_store.py`.

Implementation: inject `subprocess.run`, producer script path, Python executable, and output directory. `initialize()` runs the producer `init`; `capture()` requires initialization, runs `capture`, validates `latest.json` tool marker/no checkpoint fields and reads only the new NPZ into memory. A failed capture clears the prior snapshot. `MemoryTerrainStore` exposes the current immutable snapshot and reset; no write path points into `data/maps`.

Verify:

```powershell
python -m pytest tests/poe2_live_terrain/test_session.py tests/poe2_live_terrain/test_capture_adapter.py tests/poe2_live_terrain/test_memory_store.py -q
# Expected: fake subprocess tests cover success, no-process failure, stale/checkpoint rejection, session invalidation, replacement and reset.
```

### Task 4: Build the reusable terrain display presenter

Files:

- Add `src/auto_modules/ui/modes/poe2_live_terrain/__init__.py`.
- Add `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`.
- Add `tests/test_poe2_live_terrain_presenter.py`.

Implementation: convert `TerrainSnapshot.wall_layer` into a QImage/QPixmap using explicit walkable/blocked/unknown colors, keeping y/x orientation and no business-specific renderer state. Return a small display DTO with pixmap and metadata strings.

Verify:

```powershell
python -m pytest tests/test_poe2_live_terrain_presenter.py -q
# Expected: image dimensions and representative pixel colors match the snapshot.
```

### Task 5: Add the PoE2 live terrain page with an injectable service

Files:

- Add `src/auto_modules/ui/modes/poe2_live_terrain/page.py`.
- Add `tests/test_poe2_live_terrain_page.py`.

Implementation: create a QWidget with initialize/capture/reset controls, state and metadata labels, `ScalableMapWidget`, and an injected service protocol. The page must not import the external producer module, pathfinder, gamepad, LAN, or `AppContext` capture state. Use a fake service in tests.

Verify:

```powershell
python -m pytest tests/test_poe2_live_terrain_page.py -q
# Expected: controls, success rendering, failure clearing and reset behavior pass offscreen.
```

### Task 6: Mount the page without changing existing mode ownership

Files:

- Modify `src/auto_modules/ui/main_window.py`.
- Add `tests/test_main_window_poe2_terrain_page.py`.

Implementation: add a new mode button and stack entry, preserve existing indices by appending the new page, and inject a default service only for this page. Update `switch_mode()` to select the new page without refreshing offline maps. Stop/reset the page during close without starting any external process implicitly.

Verify:

```powershell
python -m pytest tests/test_main_window_poe2_terrain_page.py tests/test_navigation_ui_layout.py tests/test_map_editor_page_in_main_window.py -q
# Expected: new page is mounted and existing page/index/close tests remain green.
```

### Task 7: Synchronize documentation and run the focused regression suite

Files:

- Modify `README.md`.
- Modify `ARCHITECTURE_GUIDE.md`.
- Modify `CODEBASE.md`.
- Modify `ITERATION_LOG.md`.

Implementation: document the PoE2 page as a business adapter, its in-memory-only lifecycle, the external producer boundary, and the explicit non-goals. Record tests and safety boundaries.

Verify:

```powershell
python -m compileall -q src tests tools packaging
python -m pytest tests/poe2_live_terrain tests/test_poe2_live_terrain_presenter.py tests/test_poe2_live_terrain_page.py tests/test_main_window_poe2_terrain_page.py tests/test_navigation_ui_layout.py tests/test_map_editor_page_in_main_window.py -q
git diff --check
# Expected: compile succeeds, focused tests pass, diff check has no whitespace errors.
```
