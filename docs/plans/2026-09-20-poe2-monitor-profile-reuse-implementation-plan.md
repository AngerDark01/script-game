# PoE2 监控配置复用与实时地形页面实施计划

## Goal

抽取绘图模式的通用监控配置能力，增加正方形/圆形有效区域和本地多 profile，并把 PoE2 页面改造成与绘图模式一致的配置、监控地图、在线地形和人物定位工作台。

## Architecture Overview

- 通用采集几何只处理矩形截图、中心点、形状和遮罩，不知道 PoE2 或绘图业务。
- profile store 只保存本地监控与识别参数，不保存地图和运行状态。
- PoE2 拥有独立的选择器、配置控件和展示组件；这些模块参考绘图模式实现，但不修改绘图模式或让绘图模式依赖它们。
- PoE2 地图只保存在 `MemoryTerrainStore`，人物位置由 localization runtime 输出并叠加在地图上。
- 本阶段不产生任何真实输入或网络副作用。

## Tech Stack

- Python 3.11+、PySide6、pytest、NumPy、现有 `src/auto_modules` 包布局。
- 现有 `ScalableMapWidget`、屏幕捕获后端、`MonitorBinding` 和 PoE2 runtime。

## Task 1: Add generic capture shape and mask contracts

Files:

- `src/auto_modules/core/spatial/capture_geometry.py`
- `src/auto_modules/core/spatial/__init__.py`
- `tests/test_capture_geometry.py`

Test first:

```python
def test_circle_mask_keeps_pixels_inside_radius_only():
    mask = build_capture_mask(5, 5, CaptureShape.CIRCLE)
    assert mask[2, 2]
    assert not mask[0, 0]

def test_square_mask_keeps_every_pixel():
    mask = build_capture_mask(3, 4, CaptureShape.SQUARE)
    assert mask.all()
```

Implement immutable `CaptureShape`, `CaptureGeometry`, `build_capture_mask`, and validation for positive dimensions/radius. The API must return a rectangular NumPy boolean mask and must not import UI or game modules.

Verify:

```powershell
python -m pytest -q tests/test_capture_geometry.py
# Expected: all shape and validation tests pass
```

Commit: `feat: add generic capture shape geometry`

## Task 2: Extend PoE2 monitor configuration with shape and profile payload

Files:

- `src/auto_modules/features/poe2/live_terrain/monitor_config.py`
- `tests/poe2_live_terrain/test_monitor_config.py`

Test first:

```python
def test_monitor_config_round_trips_circle_shape_and_profile_name():
    config = Poe2MonitorConfig(profile_id="single", profile_name="单人圆形", shape=CaptureShape.CIRCLE)
    restored = Poe2MonitorConfig.from_dict(config.as_dict())
    assert restored == config
```

Add profile identity, `shape`, radius, and complete recognition fields while preserving defaults for existing `monitor.json` payloads. Keep snapshots and runtime flags out of the payload. Reject invalid shapes and non-positive sizes.

Verify:

```powershell
python -m pytest -q tests/poe2_live_terrain/test_monitor_config.py
# Expected: legacy/default and circle profile round-trip tests pass
```

Commit: `feat: add shaped PoE2 monitor configuration`

## Task 3: Add local multi-profile store

Files:

- `src/auto_modules/features/poe2/live_terrain/profile_store.py`
- `src/auto_modules/features/poe2/live_terrain/__init__.py`
- `tests/poe2_live_terrain/test_profile_store.py`

Test first:

```python
def test_profile_store_creates_lists_switches_and_deletes_profiles(tmp_path):
    store = Poe2MonitorProfileStore(tmp_path)
    created = store.create("配置 1")
    assert store.active().profile_id == created.profile_id
    store.create("配置 2")
    store.activate(created.profile_id)
    assert store.active().profile_name == "配置 1"
    store.delete(created.profile_id)
    assert store.active() is not None
```

Implement atomic JSON index/profile writes, create/copy/rename/activate/delete operations, deterministic active-profile recovery, and migration from the current single `monitor.json` into one default profile. Keep this store local and independent from terrain snapshots.

Verify:

```powershell
python -m pytest -q tests/poe2_live_terrain/test_profile_store.py
# Expected: persistence, migration, duplicate, and active-profile tests pass
```

Commit: `feat: add local PoE2 monitor profiles`

## Task 4: Add PoE2-local monitor selection controller

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture/selection_controller.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture/__init__.py`
- `tests/poe2_live_terrain/test_capture_selection.py`

Test first:

```python
def test_poe2_selection_supports_region_and_center_modes(fake_context):
    result = controller(fake_context).apply_center_selection(100, 80, 320)
    assert result.mode == "center"
    assert fake_context.monitor_logical_center == (100, 80)
```

Copy the proven mapping selection interaction into the PoE2 feature boundary. Add shape-aware metadata without changing existing mapping code or imports. The PoE2 controller may depend on shared primitive overlays, but its write-back state belongs only to the PoE2 profile model.

Verify:

```powershell
python -m pytest -q tests/poe2_live_terrain/test_capture_selection.py
# Expected: PoE2 region, center, shape, and coordinate tests pass
```

Commit: `feat: add PoE2 monitor selection controller`

## Task 5: Build PoE2-local monitor configuration panel

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/config_panel.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/preview.py`
- `tests/poe2_live_terrain/test_config_panel.py`

Test first:

```python
def test_poe2_panel_exposes_region_center_shape_and_size_controls(qtbot):
    panel = MonitorConfigPanel(...)
    assert panel.select_region_button is not None
    assert panel.select_center_button is not None
    assert panel.shape_combo.currentData() == "square"
```

Implement the PoE2 left-side monitor controls and preview contract by following the mapping layout and signal behavior. The panel emits a profile/config object and accepts a profile object; it does not know how terrain is captured or localized. Do not edit `ui/modes/mapping*` files.

Verify:

```powershell
python -m pytest -q tests/poe2_live_terrain/test_config_panel.py
# Expected: controls, default square shape, circle selection, and signal tests pass
```

Commit: `feat: add PoE2 monitor configuration panel`

## Task 6: Redesign PoE2 monitor dialog as profile editor

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/monitor_dialog.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/profile_toolbar.py`
- `tests/test_poe2_monitor_dialog.py`

Test first:

```python
def test_dialog_edits_circle_profile_without_touching_terrain_snapshot(qtbot, tmp_path):
    dialog = Poe2MonitorConfigDialog(profile_store=store)
    dialog.shape_combo.setCurrentIndex(dialog.shape_combo.findData("circle"))
    dialog.save()
    assert store.active().shape.value == "circle"
```

Replace the numeric-only rectangle dialog with the shared panel and local profile toolbar. Add new/copy/rename/save/delete/activate actions and lock profile editing while runtime is active. Preserve the current config signal used by the PoE2 page.

Verify:

```powershell
python -m pytest -q tests/test_poe2_monitor_dialog.py
# Expected: profile CRUD, shaped selection, save signal, and edit-lock tests pass
```

Commit: `refactor: make PoE2 monitor dialog profile-based`

## Task 7: Compose the PoE2 page with mapping-style layout

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/layout.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `tests/test_poe2_live_terrain_page.py`

Test first:

```python
def test_page_renders_monitor_preview_map_and_player_status(qtbot):
    page = build_page_with_fake_runtime()
    assert page.minimap_preview is not None
    assert page.map_widget is not None
    page.handle_runtime_state(fake_localized_state())
    assert "置信度" in page.localization_status.text()
```

Replace the current vertical prototype with the mapping-style split layout. Keep initialize, capture, reset, start, stop, and logging behavior. Render the raw monitor frame with the active shape mask, render the in-memory terrain map, and overlay the player position from runtime. Do not add path planning or input execution.

Verify:

```powershell
python -m pytest -q tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py
# Expected: lifecycle, layout widgets, preview and player-overlay tests pass
```

Commit: `feat: compose PoE2 terrain page like mapping workbench`

## Task 8: Wire PoE2 composition without touching mapping mode

Files:

- `src/auto_modules/ui/modes/poe2/composition.py`
- `src/auto_modules/ui/main_window.py`
- `tests/test_main_window_poe2_terrain_page.py`
- `tests/test_ui_composition.py`

Test first:

```python
def test_poe2_composition_owns_profile_store_and_runtime(tmp_path):
    composition = build_poe2_live_terrain_composition(..., writable_root=tmp_path)
    assert composition.profile_store.root == tmp_path
```

Inject the PoE2-local monitor panel/controller and local profile store through the PoE2 composition. Keep `MainWindow` as a thin composition root and do not add PoE2-specific logic to core, generic navigation UI, or mapping mode. Verify that mapping files are unchanged by this feature.

Verify:

```powershell
python -m pytest -q tests/test_main_window_poe2_terrain_page.py tests/poe2_live_terrain/test_config_panel.py
# Expected: composition and PoE2 injection tests pass; mapping mode remains untouched
```

Commit: `feat: compose independent PoE2 monitor workbench`

## Task 9: Update checkpoint documentation and run focused regression

Files:

- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `README.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Document local multi-profile storage, square/circle mask semantics, mapping-style PoE2 layout, memory-only terrain snapshots, and the boundary between shared monitor UI and business runtimes. Append a new checkpoint entry; do not rewrite historical entries.

Verify:

```powershell
python -m pytest -q tests/poe2_live_terrain tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py tests/test_poe2_monitor_dialog.py tests/test_main_window_poe2_terrain_page.py tests/poe2_live_terrain/test_capture_selection.py tests/poe2_live_terrain/test_config_panel.py
python -m compileall -q src tests tools packaging
git diff --check
# Expected: focused tests pass; compileall succeeds; diff check is clean
```

Commit: `docs: record shared PoE2 monitor profile design`
